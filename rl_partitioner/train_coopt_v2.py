"""
Co-optimization v2: Placement-Aware Partitioning
==================================================

Key change: chiplets are on a 2D grid with adjacency constraints.
Only adjacent chiplets have direct links. Non-adjacent traffic
pays multi-hop latency + congestion penalty.

This creates the interaction between partition and topology:
  - Spectral minimizes total cut but ignores physical placement
  - Our RL learns to place high-traffic modules on ADJACENT chiplets
  - Result: lower effective communication latency, higher throughput
"""

import sys
import time
import json
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from envs.netlist import create_transformer_accelerator_netlist, get_node_features, get_edge_bandwidth_matrix
from envs.placement_aware_evaluator import PlacementAwareEvaluator, ChipletGrid


# ============================================================
# Partitioning baselines
# ============================================================

def kmeans_simple(X, K, max_iter=100, seed=42):
    rng = np.random.default_rng(seed)
    N = X.shape[0]
    indices = rng.choice(N, K, replace=False)
    centers = X[indices].copy()
    assignment = np.zeros(N, dtype=int)
    for _ in range(max_iter):
        for i in range(N):
            assignment[i] = np.argmin(np.linalg.norm(X[i] - centers, axis=1))
        new_centers = np.zeros_like(centers)
        for k in range(K):
            members = X[assignment == k]
            if len(members) > 0:
                new_centers[k] = members.mean(axis=0)
            else:
                new_centers[k] = X[rng.integers(N)]
        if np.allclose(centers, new_centers):
            break
        centers = new_centers
    return assignment


def spectral_partition(G, K, seed=42):
    N = G.number_of_nodes()
    W = np.zeros((N, N))
    for u, v, d in G.edges(data=True):
        W[u][v] = d['bandwidth']
        W[v][u] = d['bandwidth']
    D = np.diag(W.sum(axis=1))
    L = D - W
    _, eigvecs = np.linalg.eigh(L)
    features = eigvecs[:, 1:K+1]
    return kmeans_simple(features, K, seed=seed)


def random_partition(G, K, seed=42):
    rng = np.random.default_rng(seed)
    N = G.number_of_nodes()
    assignment = np.zeros(N, dtype=int)
    per = N // K
    perm = rng.permutation(N)
    for i, node in enumerate(perm):
        assignment[node] = min(i // per, K - 1)
    return assignment


# ============================================================
# Placement-aware RL environment
# ============================================================

class PlacementAwareEnv:
    """
    RL env with physical chiplet placement.

    Observation includes:
      - Per-chiplet: [area, compute, module_frac, phy_area, n_adj_traffic]
      - Grid position features
      - Global: [comm_ratio, congestion, balance, throughput_norm, step_frac]
    """

    def __init__(self, G, grid, evaluator, initial_partition, max_swaps=40):
        self.G = G
        self.grid = grid
        self.K = grid.K
        self.N = G.number_of_nodes()
        self.evaluator = evaluator
        self.initial_partition = initial_partition.copy()
        self.max_swaps = max_swaps
        self.node_features = get_node_features(G)
        self.bw_matrix = get_edge_bandwidth_matrix(G)

        self.n_actions = self.N * self.K
        # Per-chiplet: 6 features + global: 5
        self.obs_dim = self.K * 6 + 5

    def reset(self):
        self.assignment = self.initial_partition.copy()
        self.step_count = 0
        self._cached = self.evaluator.evaluate(self.G, self.assignment)
        self.initial_tps = self._cached['throughput_tps']
        self.best_tps = self.initial_tps
        self.best_assignment = self.assignment.copy()
        return self._obs()

    def _obs(self):
        obs = np.zeros(self.obs_dim, dtype=np.float32)
        ev = self._cached

        for cid in range(self.K):
            b = cid * 6
            obs[b + 0] = ev['chiplet_logic_area'][cid] / 100.0
            obs[b + 1] = sum(self.node_features[n][2] for n in range(self.N)
                             if self.assignment[n] == cid) / 50.0
            obs[b + 2] = sum(1 for n in range(self.N) if self.assignment[n] == cid) / self.N
            obs[b + 3] = ev['chiplet_phy_area'][cid] / 10.0
            # Traffic to adjacent chiplets (high = good placement)
            adj_traffic = sum(ev['traffic_matrix'][cid][j]
                              for j in self.grid.adjacent[cid])
            total_traffic = sum(ev['traffic_matrix'][cid])
            obs[b + 4] = adj_traffic / (total_traffic + 1e-8)  # adjacency ratio
            # Grid position
            r, c = self.grid.positions[cid]
            obs[b + 5] = (r * self.grid.cols + c) / self.K

        g = self.K * 6
        obs[g + 0] = ev['comm_ratio']
        obs[g + 1] = ev['congestion_factor']
        obs[g + 2] = ev['compute_balance']
        obs[g + 3] = ev['throughput_tps'] / (self.initial_tps + 1e-8)
        obs[g + 4] = self.step_count / self.max_swaps
        return obs

    def step(self, action):
        mid = action // self.K
        target = action % self.K
        old = self.assignment[mid]

        if old == target:
            self.step_count += 1
            return self._obs(), -0.001, self.step_count >= self.max_swaps

        # Balance check
        count_t = np.sum(self.assignment == target)
        count_s = np.sum(self.assignment == old)
        max_cap = int(np.ceil(self.N / self.K * 2.0))
        min_cap = max(1, int(np.floor(self.N / self.K * 0.2)))
        if count_t >= max_cap or count_s <= min_cap:
            self.step_count += 1
            return self._obs(), -0.002, self.step_count >= self.max_swaps

        self.assignment[mid] = target
        self._cached = self.evaluator.evaluate(self.G, self.assignment)
        new_tps = self._cached['throughput_tps']

        reward = (new_tps - self.best_tps) * 100  # scale up

        if new_tps > self.best_tps:
            self.best_tps = new_tps
            self.best_assignment = self.assignment.copy()

        self.step_count += 1
        return self._obs(), reward, self.step_count >= self.max_swaps

    def get_best(self):
        ev = self.evaluator.evaluate(self.G, self.best_assignment)
        return self.best_assignment.copy(), ev


# ============================================================
# Policy
# ============================================================

class Policy(nn.Module):
    def __init__(self, obs_dim, n_actions, hidden=128):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(obs_dim, hidden), nn.ReLU(),
            nn.Linear(hidden, hidden), nn.ReLU(),
            nn.Linear(hidden, n_actions),
        )

    def forward(self, x):
        return F.softmax(self.net(x), dim=-1)


def train_rl(env, n_episodes=2000, lr=1e-3, gamma=0.99, verbose=True):
    policy = Policy(env.obs_dim, env.n_actions)
    optimizer = torch.optim.Adam(policy.parameters(), lr=lr)
    history = []
    best = -np.inf

    for ep in range(n_episodes):
        obs = env.reset()
        log_probs, rewards = [], []
        done = False
        while not done:
            probs = policy(torch.FloatTensor(obs).unsqueeze(0))
            dist = torch.distributions.Categorical(probs)
            action = dist.sample()
            log_probs.append(dist.log_prob(action))
            obs, r, done = env.step(action.item())
            rewards.append(r)

        returns = []
        G = 0
        for r in reversed(rewards):
            G = r + gamma * G
            returns.insert(0, G)
        returns = torch.FloatTensor(returns)
        if returns.std() > 0:
            returns = (returns - returns.mean()) / (returns.std() + 1e-8)

        loss = sum(-lp * R for lp, R in zip(log_probs, returns))
        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(policy.parameters(), 1.0)
        optimizer.step()

        ep_r = sum(rewards)
        history.append(ep_r)
        best = max(best, ep_r)

        if verbose and (ep + 1) % 200 == 0:
            print(f"    Ep {ep+1}: avg={np.mean(history[-100:]):.4f} best={best:.4f}")

    return policy, history


def greedy_rollout(env, policy):
    """Deterministic rollout using argmax policy."""
    obs = env.reset()
    done = False
    while not done:
        with torch.no_grad():
            probs = policy(torch.FloatTensor(obs).unsqueeze(0))
        action = probs.argmax(dim=1).item()
        obs, _, done = env.step(action)
    return env.get_best()


# ============================================================
# Main experiment
# ============================================================

def run(K=8, n_episodes=2000):
    # Grid layout
    if K == 4:
        grid = ChipletGrid(2, 2)
    elif K == 8:
        grid = ChipletGrid(2, 4)
    elif K == 16:
        grid = ChipletGrid(4, 4)
    else:
        rows = int(np.ceil(np.sqrt(K)))
        cols = int(np.ceil(K / rows))
        grid = ChipletGrid(rows, cols)

    print("=" * 90)
    print(f"  PLACEMENT-AWARE CO-OPTIMIZATION: {grid.rows}×{grid.cols} grid ({K} chiplets)")
    print("=" * 90)

    # Adjacency info
    for cid in range(K):
        adj = grid.adjacent[cid]
        print(f"  Chiplet {cid} @ {grid.positions[cid]}: adjacent={adj}")

    # Netlist (medium-ish: more modules than chiplets to create non-trivial partition)
    G = create_transformer_accelerator_netlist(
        num_tensor_cores=max(16, K * 4),
        num_sram_banks=max(8, K * 2),
        num_hbm_ctrl=max(4, K),
        num_softmax=max(4, K),
        num_layernorm=max(4, K),
    )
    N = G.number_of_nodes()
    print(f"\n  Netlist: {N} modules, {G.number_of_edges()} edges, {K} chiplets")

    # Evaluator
    evaluator = PlacementAwareEvaluator(
        grid,
        bw_per_link_gbs=32,
        phy_area_per_link=0.15,
        latency_per_hop_us=0.10,
        links_per_adjacent_pair=4,
        tops_per_mm2=1.5,
        hbm_bw_per_mm2=3.0,
        overlap_factor=0.0,  # no overlap → comm fully visible
    )

    # ── Baselines ──
    results = {}

    # 1. Random
    print(f"\n  [1/4] Random partition...")
    rp = random_partition(G, K)
    re = evaluator.evaluate(G, rp)
    results['random'] = re
    print(f"    tok/s={re['throughput_tps']:.4f}, comm={re['comm_ratio']:.1%}, "
          f"congestion={re['congestion_factor']:.2f}, hops={re['avg_hops']:.1f}")

    # 2. Spectral
    print(f"\n  [2/4] Spectral partition...")
    sp = spectral_partition(G, K)
    se = evaluator.evaluate(G, sp)
    results['spectral'] = se
    print(f"    tok/s={se['throughput_tps']:.4f}, comm={se['comm_ratio']:.1%}, "
          f"congestion={se['congestion_factor']:.2f}, hops={se['avg_hops']:.1f}")

    # 3. RL with comm_ratio reward (old, baseline)
    print(f"\n  [3/4] Spectral + RL (comm reward, placement-unaware)...")

    class CommRewardEnv:
        """Simple env: reward = -comm_ratio change (no placement awareness)."""
        def __init__(s, G, K, init, max_swaps=40):
            s.G, s.K, s.N = G, K, G.number_of_nodes()
            s.init = init.copy()
            s.max_swaps = max_swaps
            s.bw_m = get_edge_bandwidth_matrix(G)
            s.nf = get_node_features(G)
            s.n_actions = s.N * K
            s.obs_dim = K * 4 + 3

        def reset(s):
            s.asgn = s.init.copy()
            s.step_n = 0
            s._compute()
            s.best_cr = s._cr
            return s._obs()

        def _compute(s):
            s._total = 0; s._inter = 0
            for i in range(s.N):
                for j in range(i+1, s.N):
                    bw = s.bw_m[i][j]
                    if bw > 0:
                        s._total += bw
                        if s.asgn[i] != s.asgn[j]:
                            s._inter += bw
            s._cr = s._inter / (s._total + 1e-8)

        def _obs(s):
            obs = np.zeros(s.obs_dim, dtype=np.float32)
            for k in range(s.K):
                mask = s.asgn == k
                obs[k*4+0] = sum(s.nf[n][0] for n in range(s.N) if mask[n]) / 50
                obs[k*4+1] = sum(s.nf[n][2] for n in range(s.N) if mask[n]) / 50
                obs[k*4+2] = np.sum(mask) / s.N
                obs[k*4+3] = s._cr
            obs[s.K*4+0] = s._cr
            obs[s.K*4+1] = s.step_n / s.max_swaps
            obs[s.K*4+2] = s.best_cr
            return obs

        def step(s, action):
            mid, tgt = action // s.K, action % s.K
            old = s.asgn[mid]
            if old == tgt:
                s.step_n += 1
                return s._obs(), -0.01, s.step_n >= s.max_swaps
            # Update
            s.asgn[mid] = tgt
            for j in range(s.N):
                if j == mid: continue
                bw = s.bw_m[mid][j]
                if bw <= 0: continue
                was = old != s.asgn[j]
                now = tgt != s.asgn[j]
                if was and not now: s._inter -= bw
                elif not was and now: s._inter += bw
            s._cr = s._inter / (s._total + 1e-8)
            reward = (s.best_cr - s._cr) * 10  # less comm = better
            if s._cr < s.best_cr:
                s.best_cr = s._cr
            s.step_n += 1
            return s._obs(), reward, s.step_n >= s.max_swaps

        def get_best(s):
            return s.asgn.copy()

    comm_env = CommRewardEnv(G, K, sp, max_swaps=40)
    t0 = time.time()
    comm_pol, _ = train_rl(comm_env, n_episodes, verbose=True)
    t_comm = time.time() - t0

    # Evaluate comm-RL result with placement evaluator
    obs = comm_env.reset()
    done = False
    while not done:
        with torch.no_grad():
            probs = comm_pol(torch.FloatTensor(obs).unsqueeze(0))
        obs, _, done = comm_env.step(probs.argmax(1).item())
    comm_part = comm_env.get_best()
    ce = evaluator.evaluate(G, comm_part)
    results['rl_comm'] = ce
    print(f"    tok/s={ce['throughput_tps']:.4f}, comm={ce['comm_ratio']:.1%}, "
          f"congestion={ce['congestion_factor']:.2f}, hops={ce['avg_hops']:.1f} ({t_comm:.0f}s)")

    # 4. OURS: RL with throughput reward (placement-aware)
    print(f"\n  [4/4] Spectral + RL (throughput reward, PLACEMENT-AWARE) [OURS]...")
    our_env = PlacementAwareEnv(G, grid, evaluator, sp, max_swaps=40)
    t0 = time.time()
    our_pol, _ = train_rl(our_env, n_episodes, verbose=True)
    t_ours = time.time() - t0

    _, oe = greedy_rollout(our_env, our_pol)
    results['rl_throughput'] = oe
    print(f"    tok/s={oe['throughput_tps']:.4f}, comm={oe['comm_ratio']:.1%}, "
          f"congestion={oe['congestion_factor']:.2f}, hops={oe['avg_hops']:.1f} ({t_ours:.0f}s)")

    # ── Summary ──
    base_tps = se['throughput_tps']
    print(f"\n  {'─' * 85}")
    print(f"  {'Method':<45} {'tok/s':>8} {'Comm%':>6} {'Cong':>5} "
          f"{'Hops':>5} {'vs Spectral':>12}")
    print(f"  {'─' * 85}")

    for name, key in [('1. Random', 'random'),
                      ('2. Spectral', 'spectral'),
                      ('3. Spectral + RL (comm reward)', 'rl_comm'),
                      ('4. Spectral + RL (throughput, placement) [OURS]', 'rl_throughput')]:
        ev = results[key]
        ratio = ev['throughput_tps'] / base_tps if base_tps > 0 else 0
        marker = " ★" if key == 'rl_throughput' else ""
        print(f"  {name:<45} {ev['throughput_tps']:>8.4f} "
              f"{ev['comm_ratio']:>5.1%} {ev['congestion_factor']:>5.2f} "
              f"{ev['avg_hops']:>5.1f} {ratio:>10.1%}{marker}")

    if base_tps > 0:
        print(f"\n  OURS vs Spectral:    {(oe['throughput_tps']/base_tps - 1)*100:+.2f}%")
        print(f"  OURS vs RL(comm):    {(oe['throughput_tps']/ce['throughput_tps'] - 1)*100:+.2f}%")

    # Save
    out = Path(__file__).parent / 'results'
    out.mkdir(exist_ok=True)
    save = {k: {'tps': v['throughput_tps'], 'comm': v['comm_ratio'],
                'congestion': v['congestion_factor'], 'hops': v['avg_hops']}
            for k, v in results.items()}
    with open(out / f'coopt_v2_K{K}.json', 'w') as f:
        json.dump(save, f, indent=2)


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--K', type=int, default=8)
    p.add_argument('--episodes', type=int, default=2000)
    args = p.parse_args()
    run(args.K, args.episodes)
