"""PARL Maskable PPO (arXiv 2510.24113) re-implementation.

Algorithm: Maskable PPO with link-toggle action space.
  State    : flattened mixed traffic + current alloc + scalars.
  Action   : (toggle_type, pair_idx) -> 2 * n_pairs total
             toggle_type=0: add 1 link to pair, type=1: remove 1.
  Mask     : illegal actions masked out
             - add: alloc < per_pair_cap AND hop <= max_dist
             - rem: alloc > 0 AND (not mesh OR alloc > 1) AND hop <= max_dist
  Reward   : -surrogate_latency reduction at each step.
  Output   : single static topology, used for ALL workloads in input set.

Trained per (subset, K, N, bpp). Input traffic = mean over subset workloads.
"""

import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim

sys.path.insert(0, str(Path(__file__).parent))
from noi_topology_synthesis import ChipletGrid
from ml_express_warmstart import surrogate_predict_ra, DEVICE


class PARLPolicy(nn.Module):
    """Maskable actor-critic for chiplet topology RL."""

    def __init__(self, state_dim, n_pairs, hidden=128):
        super().__init__()
        self.trunk = nn.Sequential(
            nn.Linear(state_dim, hidden), nn.ReLU(),
            nn.Linear(hidden, hidden), nn.ReLU(),
        )
        self.actor_add = nn.Linear(hidden, n_pairs)
        self.actor_rem = nn.Linear(hidden, n_pairs)
        self.critic = nn.Linear(hidden, 1)

    def forward(self, state, action_mask=None):
        h = self.trunk(state)
        add_logits = self.actor_add(h)
        rem_logits = self.actor_rem(h)
        if action_mask is not None:
            add_mask, rem_mask = action_mask
            add_logits = add_logits.masked_fill(~add_mask, -1e9)
            rem_logits = rem_logits.masked_fill(~rem_mask, -1e9)
        logits = torch.cat([add_logits, rem_logits], dim=-1)
        value = self.critic(h)
        return logits, value.squeeze(-1)

    def act(self, state, action_mask=None):
        logits, value = self.forward(state, action_mask)
        probs = F.softmax(logits, dim=-1)
        dist = torch.distributions.Categorical(probs)
        action = dist.sample()
        return action, dist.log_prob(action), value, dist.entropy()


def train_parl_ppo(
    surrogate, mix_traffic, K, N, R, C, link_budget,
    n_episodes=150, max_steps_per_ep=20,
    rate_mult=4.0, lr=3e-4, max_dist=3,
    clip_eps=0.2, vf_coef=0.5, ent_coef=0.01,
    n_ppo_epochs=4, verbose=False,
):
    """Train Maskable PPO and return best topology found.

    mix_traffic: (K, K) mixed-workload traffic matrix.
    """
    grid = ChipletGrid(R, C)
    adj_pairs = grid.get_adj_pairs()
    adj_set = set(adj_pairs)
    n_adj = len(adj_pairs)
    all_pairs = [(i, j) for i in range(K) for j in range(i + 1, K)]
    n_pairs = len(all_pairs)
    pair_to_idx = {p: i for i, p in enumerate(all_pairs)}

    hop_mask_np = np.array(
        [grid.get_hops(p[0], p[1]) <= max_dist for p in all_pairs],
        dtype=bool)
    mesh_mask_np = np.array(
        [p in adj_set for p in all_pairs], dtype=bool)
    hop_mask_t = torch.tensor(hop_mask_np, device=DEVICE)
    mesh_mask_t = torch.tensor(mesh_mask_np, device=DEVICE)

    t_max = mix_traffic.max()
    traffic_norm = mix_traffic / t_max if t_max > 0 else mix_traffic
    traffic_flat = traffic_norm[np.triu_indices(K, k=1)].astype(np.float32)

    state_dim = n_pairs + n_pairs + 4
    policy = PARLPolicy(state_dim, n_pairs).to(DEVICE)
    optimizer = optim.Adam(policy.parameters(), lr=lr)

    def compute_masks(alloc):
        alloc_t = torch.tensor(alloc, device=DEVICE)
        add_mask = (alloc_t < N) & hop_mask_t
        rem_mask = (alloc_t > 0) & hop_mask_t & (~mesh_mask_t |
                                                   (alloc_t > 1))
        return add_mask, rem_mask

    def compute_state(alloc):
        budget_used = alloc.sum() / max(link_budget, 1)
        scalars = np.array([budget_used, K / 32.0, N / 8.0,
                            n_adj / 56.0], dtype=np.float32)
        return np.concatenate([traffic_flat, alloc / N, scalars]
                              ).astype(np.float32)

    def predict_lat(alloc):
        budget = max(int(alloc.sum()), 1)
        return surrogate_predict_ra(
            surrogate, traffic_flat, alloc,
            adj_set, all_pairs, K, N, budget, n_adj,
            rate_mult=rate_mult)

    best_alloc = None
    best_lat = float('inf')

    init_alloc = np.zeros(n_pairs, dtype=np.float32)
    for p in adj_pairs:
        init_alloc[pair_to_idx[p]] = 1

    for ep in range(n_episodes):
        alloc = init_alloc.copy()
        prev_lat = predict_lat(alloc)

        states = []
        actions = []
        log_probs = []
        rewards = []
        values = []
        masks = []

        for step in range(max_steps_per_ep):
            state = compute_state(alloc)
            state_t = torch.tensor(state, device=DEVICE)
            add_mask, rem_mask = compute_masks(alloc)

            if not (add_mask.any() or rem_mask.any()):
                break
            if alloc.sum() >= link_budget and not rem_mask.any():
                break

            with torch.no_grad():
                action, log_prob, value, _ = policy.act(
                    state_t, (add_mask, rem_mask))

            action_id = action.item()
            if action_id < n_pairs:
                pair_idx = action_id
                if alloc.sum() >= link_budget:
                    break
                alloc[pair_idx] += 1
            else:
                pair_idx = action_id - n_pairs
                alloc[pair_idx] -= 1

            new_lat = predict_lat(alloc)
            reward = float(prev_lat - new_lat)
            prev_lat = new_lat

            states.append(state_t)
            actions.append(action)
            log_probs.append(log_prob)
            rewards.append(reward)
            values.append(value)
            masks.append((add_mask, rem_mask))

        if alloc.sum() > 0:
            final_lat = predict_lat(alloc)
            if final_lat < best_lat:
                best_lat = final_lat
                best_alloc = alloc.copy()

        if not states:
            continue

        returns = []
        R_g = 0.0
        for r in reversed(rewards):
            R_g = r + 0.99 * R_g
            returns.insert(0, R_g)
        returns_t = torch.tensor(returns, device=DEVICE,
                                 dtype=torch.float32)
        old_log_probs = torch.stack(log_probs).detach()
        old_values = torch.stack(values).detach()
        advantages = returns_t - old_values

        for _ in range(n_ppo_epochs):
            new_logp_list = []
            new_val_list = []
            new_ent_list = []
            for state_t, mask, action in zip(states, masks, actions):
                logits, value = policy.forward(state_t, mask)
                probs = F.softmax(logits, dim=-1)
                dist = torch.distributions.Categorical(probs)
                new_logp_list.append(dist.log_prob(action))
                new_val_list.append(value)
                new_ent_list.append(dist.entropy())
            new_logps = torch.stack(new_logp_list)
            new_values = torch.stack(new_val_list)
            new_ents = torch.stack(new_ent_list)

            ratios = (new_logps - old_log_probs).exp()
            surr1 = ratios * advantages
            surr2 = torch.clamp(ratios, 1 - clip_eps,
                                1 + clip_eps) * advantages
            actor_loss = -torch.min(surr1, surr2).mean()
            critic_loss = F.mse_loss(new_values, returns_t)
            entropy = new_ents.mean()
            loss = actor_loss + vf_coef * critic_loss - ent_coef * entropy

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

        if verbose and (ep + 1) % 50 == 0:
            print(f"  PARL PPO Ep {ep+1}: best_lat={best_lat:.1f}",
                  flush=True)

    result = {}
    for i, p in enumerate(all_pairs):
        if best_alloc is not None and best_alloc[i] > 0:
            result[p] = int(best_alloc[i])
    return result, best_lat


def parl_ppo_alloc(grid, mix_traffic, link_budget, per_pair_cap,
                   max_dist=3, surrogate=None, n_episodes=150):
    """PARL Maskable PPO entry point."""
    K = grid.K
    R = grid.rows if hasattr(grid, 'rows') else int(K ** 0.5)
    C = grid.cols if hasattr(grid, 'cols') else K // R
    if surrogate is None:
        from ml_express_warmstart import load_rate_aware_surrogate
        surrogate = load_rate_aware_surrogate()
    alloc, _ = train_parl_ppo(
        surrogate, mix_traffic, K, per_pair_cap, R, C, link_budget,
        n_episodes=n_episodes, max_dist=max_dist, verbose=False,
    )
    return alloc


if __name__ == '__main__':
    from cost_perf_6panel_workload import WORKLOADS
    grid = ChipletGrid(4, 4)
    moe = WORKLOADS['moe'](16, grid)
    hyb = WORKLOADS['hybrid_tp_pp'](16, grid)
    mix = (moe + hyb) / 2
    alloc = parl_ppo_alloc(grid, mix, link_budget=48, per_pair_cap=4,
                            n_episodes=50)
    print(f"PARL PPO alloc: {len(alloc)} pairs, "
          f"{sum(alloc.values())} links")
