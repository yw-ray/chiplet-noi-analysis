"""PARL-style baseline: maskable PPO from scratch (no greedy warm-start).

PARL (arXiv 2510.24113) uses maskable PPO for NoI topology synthesis with a
multi-objective interference reward. Because the PARL codebase is not public,
we implement a simplified PARL-style variant with the two key PARL design
choices that differentiate it from our RL-WS: (i) cold-start from no express
allocation (greedy is NOT the initial state), and (ii) maskable PPO rather
than REINFORCE. We keep the same BookSim surrogate reward as our own ablation
to ensure the comparison is about the RL algorithm + initialization, not the
reward signal.

Evaluated on the headline MoE Skewed K=32 N=8 b=4x cell, single seed.
"""
import json
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim

import ml_express_warmstart as mw
from ml_express_warmstart import (
    ChipletGrid, WORKLOADS, alloc_express_greedy, gen_traffic_matrix,
    gen_anynet_config, run_booksim, surrogate_predict, load_surrogate,
    CONFIG_DIR, DEVICE, TOTAL_LOAD_BASE,
)

RESULTS_DIR = Path('results/ml_placement')
OUT_FILE = RESULTS_DIR / 'parl_baseline.json'

CELL = ('moe', 32, 8, 4)  # headline cell
SEEDS = [42, 123, 456]
N_EPISODES = 300  # episodes
ROLLOUT_MAX = 160  # max add actions per episode (typically exhausts ~156-link remaining budget)


class MaskablePPOPolicy(nn.Module):
    """Simplified maskable PPO policy: outputs logits over (pair) actions,
    with support for invalid-action masking.
    """

    def __init__(self, state_dim, n_pairs, hidden=128):
        super().__init__()
        self.actor = nn.Sequential(
            nn.Linear(state_dim, hidden), nn.ReLU(),
            nn.Linear(hidden, hidden), nn.ReLU(),
            nn.Linear(hidden, n_pairs),
        )
        self.critic = nn.Sequential(
            nn.Linear(state_dim, hidden), nn.ReLU(),
            nn.Linear(hidden, hidden), nn.ReLU(),
            nn.Linear(hidden, 1),
        )

    def forward(self, state):
        return self.actor(state), self.critic(state).squeeze(-1)

    def act(self, state, action_mask):
        logits, value = self.forward(state)
        # mask: 1 for valid, 0 for invalid
        logits = logits + (action_mask - 1.0) * 1e9
        probs = F.softmax(logits, dim=-1)
        dist = torch.distributions.Categorical(probs)
        action = dist.sample()
        return action, dist.log_prob(action), value, dist.entropy()

    def eval_action(self, state, action_mask, action):
        logits, value = self.forward(state)
        logits = logits + (action_mask - 1.0) * 1e9
        probs = F.softmax(logits, dim=-1)
        dist = torch.distributions.Categorical(probs)
        return dist.log_prob(action), value, dist.entropy()


def train_parl_style(surrogate, wl, K, N, R, C, bpp, seed):
    torch.manual_seed(seed)
    np.random.seed(seed)

    grid = ChipletGrid(R, C)
    traffic = WORKLOADS[wl](K, grid)
    adj_pairs = grid.get_adj_pairs()
    adj_set = set(adj_pairs)
    n_adj = len(adj_pairs)
    budget = int(n_adj * bpp)
    all_pairs = [(i, j) for i in range(K) for j in range(i+1, K)]
    n_pairs = len(all_pairs)
    pair_to_idx = {p: i for i, p in enumerate(all_pairs)}

    # Cold start: begin with mandatory adjacent 1x connectivity only.
    # This mirrors PARL's cold-start setting: the policy must allocate the
    # remaining budget from scratch across adjacent-plus-express pairs.
    cold_vec = np.zeros(n_pairs, dtype=np.float32)
    for p in adj_pairs:
        cold_vec[pair_to_idx[p]] = 1.0
    remaining_budget = budget - int(cold_vec.sum())
    assert remaining_budget >= 0, f"budget {budget} < adj count {int(cold_vec.sum())}"

    t_max = traffic.max()
    traffic_norm = traffic / t_max if t_max > 0 else traffic
    traffic_flat = traffic_norm[np.triu_indices(K, k=1)]

    # Distance cap — allow both adjacent (hop==1) and express (2 <= hop <= max_dist).
    max_dist = max(2, min(3, max(R, C) - 1))
    valid_pairs_idx = []
    for i, (a, b) in enumerate(all_pairs):
        if grid.get_hops(a, b) <= max_dist:
            valid_pairs_idx.append(i)
    valid_mask = np.zeros(n_pairs, dtype=np.float32)
    valid_mask[valid_pairs_idx] = 1.0

    state_dim = n_pairs + n_pairs + 3
    policy = MaskablePPOPolicy(state_dim, n_pairs).to(DEVICE)
    optimizer = optim.Adam(policy.parameters(), lr=3e-4)

    baseline_pred = surrogate_predict(surrogate, traffic_flat, cold_vec,
                                       adj_set, all_pairs, K, N, budget, n_adj)

    best_pred = baseline_pred
    best_alloc_vec = cold_vec.copy()

    for ep in range(N_EPISODES):
        allocation = cold_vec.copy()
        log_probs = []
        values = []
        rewards = []
        states = []
        actions = []
        masks = []

        budget_used = allocation.sum()
        steps = 0

        while steps < ROLLOUT_MAX and budget_used < budget:
            budget_frac = budget_used / max(budget, 1)
            state = np.concatenate([
                traffic_flat, allocation / max(N, 1),
                [budget_frac, K / 32.0, N / 8.0],
            ]).astype(np.float32)
            state_t = torch.tensor(state, device=DEVICE)

            # Mask out pairs already at per-pair cap
            mask_arr = valid_mask.copy()
            capped = allocation >= N
            mask_arr[capped] = 0.0
            if mask_arr.sum() == 0:
                break
            mask_t = torch.tensor(mask_arr, device=DEVICE)

            action, log_prob, value, _ = policy.act(state_t, mask_t)
            act_idx = action.item()
            allocation[act_idx] += 1
            budget_used += 1

            log_probs.append(log_prob)
            values.append(value)
            states.append(state_t)
            actions.append(action)
            masks.append(mask_t)
            rewards.append(0.0)
            steps += 1

        # Final reward: predicted latency gain vs baseline
        pred_lat = surrogate_predict(surrogate, traffic_flat, allocation,
                                      adj_set, all_pairs, K, N, budget, n_adj)
        final_reward = baseline_pred - pred_lat
        if rewards:
            rewards[-1] = final_reward

        if pred_lat < best_pred:
            best_pred = pred_lat
            best_alloc_vec = allocation.copy()

        if not log_probs:
            continue

        # PPO update (1-epoch simple variant)
        returns = torch.tensor(rewards, device=DEVICE, dtype=torch.float32)
        old_log_probs = torch.stack(log_probs).detach()
        advantages = returns - torch.stack(values).detach()
        if advantages.std() > 0:
            advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

        # Single PPO epoch with clipping
        for _ in range(3):
            new_log_probs_list = []
            new_values_list = []
            for st, mk, ac in zip(states, masks, actions):
                nlp, nv, _ = policy.eval_action(st, mk, ac)
                new_log_probs_list.append(nlp)
                new_values_list.append(nv)
            new_log_probs = torch.stack(new_log_probs_list)
            new_values = torch.stack(new_values_list)

            ratio = torch.exp(new_log_probs - old_log_probs)
            eps = 0.2
            surr1 = ratio * advantages
            surr2 = torch.clamp(ratio, 1 - eps, 1 + eps) * advantages
            actor_loss = -torch.min(surr1, surr2).mean()
            critic_loss = F.mse_loss(new_values, returns)
            loss = actor_loss + 0.5 * critic_loss

            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(policy.parameters(), 0.5)
            optimizer.step()

        if (ep + 1) % 100 == 0:
            print(f'    Ep {ep+1}: best_pred={best_pred:.2f}', flush=True)

    best_alloc = {all_pairs[i]: int(best_alloc_vec[i])
                   for i in range(n_pairs) if best_alloc_vec[i] > 0}
    return best_alloc, best_pred


def main():
    print('=== PARL-style maskable PPO baseline ===', flush=True)
    surrogate = load_surrogate()

    existing = []
    if OUT_FILE.exists():
        existing = json.load(open(OUT_FILE))
    done = {r['seed'] for r in existing if r['workload'] == CELL[0]}
    out = list(existing)

    wl, K, N, bpp = CELL
    R, C = (4, 4) if K == 16 else (4, 8)
    grid = ChipletGrid(R, C)
    traffic = WORKLOADS[wl](K, grid)
    adj_pairs = grid.get_adj_pairs()
    adj_set = set(adj_pairs)
    n_adj = len(adj_pairs)
    budget = int(n_adj * bpp)
    npc = N * N
    base_rate = TOTAL_LOAD_BASE / (K * npc)

    # Reference: adj_uniform and greedy (shared across seeds)
    label_ref = f'K{K}_N{N}_bpp{bpp}'
    traf_file = f'traffic_parl_{wl}_{label_ref}.txt'
    gen_traffic_matrix(grid, traffic, npc, CONFIG_DIR / traf_file)

    # adj_uniform
    per_adj = budget // n_adj
    residual = budget - per_adj * n_adj
    adj_alloc = {p: per_adj + (1 if i < residual else 0) for i, p in enumerate(sorted(adj_pairs))}
    adj_capped = {p: min(n, N) for p, n in adj_alloc.items()}
    cfg_adj = f'parl_{wl}_{label_ref}_adj'
    gen_anynet_config(cfg_adj, grid, adj_capped, chip_n=N, outdir=CONFIG_DIR)
    L_adj = run_booksim(cfg_adj, traf_file, base_rate, timeout=900)['latency']

    # greedy
    max_dist = max(2, min(3, max(R, C) - 1))
    greedy_alloc = alloc_express_greedy(grid, traffic, budget, max_dist=max_dist)
    greedy_capped = {p: min(n, N) for p, n in greedy_alloc.items()}
    cfg_g = f'parl_{wl}_{label_ref}_greedy'
    gen_anynet_config(cfg_g, grid, greedy_capped, chip_n=N, outdir=CONFIG_DIR)
    L_g = run_booksim(cfg_g, traf_file, base_rate, timeout=900)['latency']

    print(f'Reference: L_adj={L_adj}, L_greedy={L_g}', flush=True)

    for seed in SEEDS:
        if seed in done:
            print(f'SKIP seed={seed}', flush=True)
            continue
        print(f'\n>>> PARL-style training seed={seed}', flush=True)
        t0 = time.time()
        parl_alloc, _ = train_parl_style(surrogate, wl, K, N, R, C, bpp, seed)
        parl_capped = {p: min(n, N) for p, n in parl_alloc.items()}
        cfg_parl = f'parl_{wl}_{label_ref}_s{seed}'
        gen_anynet_config(cfg_parl, grid, parl_capped, chip_n=N, outdir=CONFIG_DIR)
        L_parl = run_booksim(cfg_parl, traf_file, base_rate, timeout=900)['latency']
        train_time = time.time() - t0
        print(f'    L_parl={L_parl}, train_time={train_time:.1f}s', flush=True)
        if L_adj and L_parl:
            sv = (L_adj - L_parl) / L_adj * 100
            print(f'    PARL saving vs adj = {sv:+.2f}%  '
                  f'(greedy: {(L_adj-L_g)/L_adj*100:+.2f}%)', flush=True)

        out.append({
            'workload': wl, 'K': K, 'N': N, 'budget_per_pair': bpp,
            'seed': seed,
            'L_adj': L_adj, 'L_greedy': L_g, 'L_parl': L_parl,
            'L_parl_fb': min(L_g, L_parl) if (L_g and L_parl) else None,
            'train_time': train_time,
        })
        with open(OUT_FILE, 'w') as f:
            json.dump(out, f, indent=2)

    print(f'\nDone. Wrote {OUT_FILE}', flush=True)


if __name__ == '__main__':
    main()
