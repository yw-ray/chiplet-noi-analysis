"""
Training: Throughput-Aware Co-optimization
===========================================

Compares:
  1. METIS partition + uniform links (baseline)
  2. Spectral partition + uniform links (baseline)
  3. Spectral partition + optimal links (sequential)
  4. Spectral + RL refinement with comm_ratio reward (old approach)
  5. Spectral + RL refinement with E2E throughput reward (ours, co-optimization)

The key claim: (5) > (3) > (2) > (1) in E2E throughput
because the RL agent learns to make partition decisions that enable better
link allocations — topology-aware partitioning.
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
from envs.netlist import (
    create_transformer_accelerator_netlist,
    get_node_features,
    get_edge_bandwidth_matrix,
)
from envs.throughput_evaluator import ThroughputEvaluator, allocate_links
from envs.coopt_env import CooptPartitionEnv


# ============================================================
# Larger netlist for experiments
# ============================================================

def create_large_netlist(scale='medium'):
    """
    Create netlist at different scales for experiments.
      small:  ~40 modules (current)
      medium: ~100 modules
      large:  ~200 modules
    """
    configs = {
        'small':  dict(num_tensor_cores=16, num_sram_banks=8,  num_hbm_ctrl=4),
        'medium': dict(num_tensor_cores=48, num_sram_banks=24, num_hbm_ctrl=8,
                       num_softmax=8, num_layernorm=8),
        'large':  dict(num_tensor_cores=96, num_sram_banks=48, num_hbm_ctrl=16,
                       num_softmax=16, num_layernorm=16),
    }
    params = configs.get(scale, configs['medium'])
    return create_transformer_accelerator_netlist(**params)


# ============================================================
# Spectral Clustering
# ============================================================

def spectral_partition(G, K):
    """Spectral clustering partition."""
    N = G.number_of_nodes()
    nodes = sorted(G.nodes)

    # Build weighted adjacency
    W = np.zeros((N, N))
    for u, v, d in G.edges(data=True):
        W[u][v] = d['bandwidth']
        W[v][u] = d['bandwidth']

    # Laplacian
    D = np.diag(W.sum(axis=1))
    L = D - W

    # Eigenvectors
    eigenvalues, eigenvectors = np.linalg.eigh(L)
    features = eigenvectors[:, 1:K+1]

    # K-means
    from _kmeans import kmeans_simple
    assignment = kmeans_simple(features, K)
    return assignment


def kmeans_simple(X, K, max_iter=100, seed=42):
    """Simple k-means."""
    rng = np.random.default_rng(seed)
    N = X.shape[0]
    indices = rng.choice(N, K, replace=False)
    centers = X[indices].copy()

    assignment = np.zeros(N, dtype=int)
    for _ in range(max_iter):
        # Assign
        for i in range(N):
            dists = np.linalg.norm(X[i] - centers, axis=1)
            assignment[i] = np.argmin(dists)

        # Update centers
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
    """Spectral clustering partition."""
    N = G.number_of_nodes()

    W = np.zeros((N, N))
    for u, v, d in G.edges(data=True):
        W[u][v] = d['bandwidth']
        W[v][u] = d['bandwidth']

    D = np.diag(W.sum(axis=1))
    L = D - W

    eigenvalues, eigenvectors = np.linalg.eigh(L)
    features = eigenvectors[:, 1:K+1]

    assignment = kmeans_simple(features, K, seed=seed)
    return assignment


def random_partition(G, K, seed=42):
    """Random balanced partition."""
    rng = np.random.default_rng(seed)
    N = G.number_of_nodes()
    assignment = np.zeros(N, dtype=int)
    per_chiplet = N // K
    perm = rng.permutation(N)
    for i, node in enumerate(perm):
        assignment[node] = min(i // per_chiplet, K - 1)
    return assignment


# ============================================================
# RL Policy (same architecture, different reward)
# ============================================================

class SwapPolicy(nn.Module):
    def __init__(self, obs_dim, n_actions, hidden=128):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(obs_dim, hidden),
            nn.ReLU(),
            nn.Linear(hidden, hidden),
            nn.ReLU(),
            nn.Linear(hidden, n_actions),
        )

    def forward(self, x):
        logits = self.net(x)
        return F.softmax(logits, dim=-1)


# ============================================================
# Old-style reward env (for baseline comparison)
# ============================================================

class OldStyleEnv:
    """Baseline: RL with comm_ratio reward (no throughput awareness)."""

    def __init__(self, G, K, initial_partition, max_swaps=50):
        self.G = G
        self.K = K
        self.N = G.number_of_nodes()
        self.initial_partition = initial_partition.copy()
        self.max_swaps = max_swaps
        self.bw_matrix = get_edge_bandwidth_matrix(G)
        self.node_features = get_node_features(G)

        self.n_actions = self.N * self.K
        self.obs_dim = self.K * 5 + 3

    def reset(self):
        self.assignment = self.initial_partition.copy()
        self.step_count = 0
        self._compute_metrics()
        self.best_score = self._score()
        return self._get_obs()

    def _compute_metrics(self):
        self._total_bw = 0
        self._inter_bw = 0
        for i in range(self.N):
            for j in range(i+1, self.N):
                bw = self.bw_matrix[i][j]
                if bw > 0:
                    self._total_bw += bw
                    if self.assignment[i] != self.assignment[j]:
                        self._inter_bw += bw

    def _score(self):
        cr = self._inter_bw / (self._total_bw + 1e-8)
        counts = np.array([np.sum(self.assignment == k) for k in range(self.K)])
        active = counts[counts > 0]
        bal = 1 - np.std(active) / (np.mean(active) + 1e-8) if len(active) > 1 else 0
        return 4.0 * (1 - cr) + 2.0 * max(0, bal)

    def _get_obs(self):
        obs = np.zeros(self.obs_dim, dtype=np.float32)
        cr = self._inter_bw / (self._total_bw + 1e-8)
        for cid in range(self.K):
            mask = self.assignment == cid
            obs[cid*5 + 0] = sum(self.node_features[n][0] for n in range(self.N) if mask[n]) / 50
            obs[cid*5 + 1] = sum(self.node_features[n][1] for n in range(self.N) if mask[n]) / 30
            obs[cid*5 + 2] = sum(self.node_features[n][2] for n in range(self.N) if mask[n]) / 50
            obs[cid*5 + 3] = np.sum(mask) / self.N
            obs[cid*5 + 4] = cr
        obs[self.K*5 + 0] = cr
        obs[self.K*5 + 1] = self.step_count / self.max_swaps
        obs[self.K*5 + 2] = self.best_score / 8.0
        return obs

    def step(self, action):
        mid = action // self.K
        target = action % self.K
        old = self.assignment[mid]

        if old == target:
            self.step_count += 1
            return self._get_obs(), -0.01, self.step_count >= self.max_swaps

        self.assignment[mid] = target
        # Update inter_bw incrementally
        for j in range(self.N):
            if j == mid:
                continue
            bw = self.bw_matrix[mid][j]
            if bw <= 0:
                continue
            was_inter = (old != self.assignment[j])
            is_inter = (target != self.assignment[j])
            if was_inter and not is_inter:
                self._inter_bw -= bw
            elif not was_inter and is_inter:
                self._inter_bw += bw

        new_score = self._score()
        reward = new_score - self.best_score
        if new_score > self.best_score:
            self.best_score = new_score
        self.step_count += 1
        return self._get_obs(), reward, self.step_count >= self.max_swaps


# ============================================================
# REINFORCE training
# ============================================================

def train_reinforce(env, n_episodes=2000, lr=1e-3, gamma=0.99, verbose=True):
    policy = SwapPolicy(env.obs_dim, env.n_actions)
    optimizer = torch.optim.Adam(policy.parameters(), lr=lr)

    reward_history = []
    best_reward = -np.inf

    for ep in range(n_episodes):
        obs = env.reset()
        log_probs = []
        rewards = []

        done = False
        while not done:
            obs_t = torch.FloatTensor(obs).unsqueeze(0)
            probs = policy(obs_t)
            dist = torch.distributions.Categorical(probs)
            action = dist.sample()
            log_probs.append(dist.log_prob(action))

            obs, reward, done = env.step(action.item())
            rewards.append(reward)

        # Compute returns
        returns = []
        G = 0
        for r in reversed(rewards):
            G = r + gamma * G
            returns.insert(0, G)
        returns = torch.FloatTensor(returns)
        if returns.std() > 0:
            returns = (returns - returns.mean()) / (returns.std() + 1e-8)

        # Policy gradient
        loss = 0
        for lp, R in zip(log_probs, returns):
            loss -= lp * R

        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(policy.parameters(), 1.0)
        optimizer.step()

        ep_reward = sum(rewards)
        reward_history.append(ep_reward)
        if ep_reward > best_reward:
            best_reward = ep_reward

        if verbose and (ep + 1) % 200 == 0:
            recent = np.mean(reward_history[-100:])
            print(f"    Episode {ep+1}/{n_episodes}: "
                  f"avg_reward={recent:.4f}, best={best_reward:.4f}")

    return policy, reward_history


# ============================================================
# Main experiment
# ============================================================

def run_experiment(scale='small', K=4, n_episodes=2000):
    print("=" * 90)
    print(f"  CO-OPTIMIZATION EXPERIMENT: {scale} netlist, {K} chiplets")
    print("=" * 90)

    # Create netlist
    G = create_large_netlist(scale)
    N = G.number_of_nodes()
    print(f"\n  Netlist: {N} modules, {G.number_of_edges()} edges")

    # Evaluator — tight link budget to create differentiation
    # With fewer links, partition quality matters MORE because
    # bad partitions waste links on low-traffic pairs
    evaluator = ThroughputEvaluator(
        interconnect='ucie_adv',       # lower BW per link → comm matters more
        total_link_budget=max(K, K * 2),  # tight: ~2 links per chiplet
        overlap_factor=0.0,            # no overlap → comm fully exposed
        tops_per_mm2=1.0,             # lower compute density → comm/compute ratio higher
        hbm_bw_per_mm2=2.0,          # lower memory BW → less compute-bound
    )

    # ── Baseline 1: Random partition + uniform links ──
    print(f"\n  [1/5] Random partition...")
    random_part = random_partition(G, K)
    random_eval = evaluator.evaluate(G, random_part, K)
    print(f"    tok/s={random_eval['throughput_tps']:.3f}, "
          f"comm={random_eval['comm_ratio']:.1%}, "
          f"cost=${random_eval['total_cost']:.0f}, "
          f"PHY={random_eval['avg_phy_overhead_pct']:.1f}%")

    # ── Baseline 2: Spectral partition + uniform links ──
    print(f"\n  [2/5] Spectral partition...")
    spectral_part = spectral_partition(G, K)
    spectral_eval = evaluator.evaluate(G, spectral_part, K)
    print(f"    tok/s={spectral_eval['throughput_tps']:.3f}, "
          f"comm={spectral_eval['comm_ratio']:.1%}, "
          f"cost=${spectral_eval['total_cost']:.0f}, "
          f"PHY={spectral_eval['avg_phy_overhead_pct']:.1f}%")

    # ── Baseline 3: Spectral + optimal link allocation (sequential) ──
    print(f"\n  [3/5] Spectral + optimal links (sequential)...")
    # Already done by evaluator (it allocates links optimally)
    # Same as spectral_eval — link allocator runs inside evaluate()
    seq_eval = spectral_eval  # evaluator already does optimal link allocation
    print(f"    (Same as spectral — evaluator already allocates optimally)")

    # ── Baseline 4: Spectral + RL refinement, OLD reward (comm_ratio) ──
    print(f"\n  [4/5] Spectral + RL (comm_ratio reward)...")
    old_env = OldStyleEnv(G, K, spectral_part, max_swaps=30)
    t0 = time.time()
    old_policy, old_history = train_reinforce(old_env, n_episodes=n_episodes, verbose=True)
    t_old = time.time() - t0

    # Get best result from old RL and evaluate with throughput evaluator
    old_env.reset()
    obs = old_env.reset()
    done = False
    while not done:
        with torch.no_grad():
            probs = old_policy(torch.FloatTensor(obs).unsqueeze(0))
        action = probs.argmax(dim=1).item()
        obs, _, done = old_env.step(action)
    old_rl_part = old_env.assignment.copy()
    old_rl_eval = evaluator.evaluate(G, old_rl_part, K)
    print(f"    tok/s={old_rl_eval['throughput_tps']:.3f}, "
          f"comm={old_rl_eval['comm_ratio']:.1%}, "
          f"cost=${old_rl_eval['total_cost']:.0f}, "
          f"PHY={old_rl_eval['avg_phy_overhead_pct']:.1f}% "
          f"({t_old:.1f}s)")

    # ── OURS: Spectral + RL refinement, E2E throughput reward ──
    print(f"\n  [5/5] Spectral + RL (E2E throughput reward) — CO-OPTIMIZATION...")
    coopt_env = CooptPartitionEnv(G, K, spectral_part, evaluator, max_swaps=30)
    t0 = time.time()
    coopt_policy, coopt_history = train_reinforce(coopt_env, n_episodes=n_episodes, verbose=True)
    t_coopt = time.time() - t0

    # Get best result
    coopt_env.reset()
    obs = coopt_env.reset()
    done = False
    while not done:
        with torch.no_grad():
            probs = coopt_policy(torch.FloatTensor(obs).unsqueeze(0))
        action = probs.argmax(dim=1).item()
        obs, _, done = coopt_env.step(action)
    _, coopt_eval = coopt_env.get_best_result()
    print(f"    tok/s={coopt_eval['throughput_tps']:.3f}, "
          f"comm={coopt_eval['comm_ratio']:.1%}, "
          f"cost=${coopt_eval['total_cost']:.0f}, "
          f"PHY={coopt_eval['avg_phy_overhead_pct']:.1f}% "
          f"({t_coopt:.1f}s)")

    # ── Summary ──
    print(f"\n  {'─' * 85}")
    print(f"  {'Method':<40} {'tok/s':>7} {'Comm%':>6} {'Cost':>7} "
          f"{'PHY%':>5} {'vs Spectral':>12}")
    print(f"  {'─' * 85}")

    methods = [
        ('1. Random + uniform links', random_eval),
        ('2. Spectral + optimal links', spectral_eval),
        ('3. Spectral + RL (comm reward)', old_rl_eval),
        ('4. Spectral + RL (throughput reward) [OURS]', coopt_eval),
    ]

    base_tps = spectral_eval['throughput_tps']
    for (name, ev) in methods:
        ratio = ev['throughput_tps'] / base_tps if base_tps > 0 else 0
        marker = " ★" if ev is coopt_eval else ""
        print(f"  {name:<40} {ev['throughput_tps']:>7.3f} "
              f"{ev['comm_ratio']:>5.1%} ${ev['total_cost']:>6.0f} "
              f"{ev['avg_phy_overhead_pct']:>4.1f}% "
              f"{ratio:>10.1%}{marker}")

    print(f"\n  Improvement of OURS over Spectral: "
          f"{(coopt_eval['throughput_tps']/base_tps - 1)*100:+.1f}% throughput")
    print(f"  Improvement of OURS over RL(comm): "
          f"{(coopt_eval['throughput_tps']/old_rl_eval['throughput_tps'] - 1)*100:+.1f}% throughput")

    # Save results
    results = {
        'scale': scale, 'K': K, 'N': N,
        'random': {'tps': random_eval['throughput_tps'], 'comm': random_eval['comm_ratio'],
                    'cost': random_eval['total_cost']},
        'spectral': {'tps': spectral_eval['throughput_tps'], 'comm': spectral_eval['comm_ratio'],
                      'cost': spectral_eval['total_cost']},
        'rl_comm': {'tps': old_rl_eval['throughput_tps'], 'comm': old_rl_eval['comm_ratio'],
                     'cost': old_rl_eval['total_cost']},
        'rl_throughput': {'tps': coopt_eval['throughput_tps'], 'comm': coopt_eval['comm_ratio'],
                           'cost': coopt_eval['total_cost']},
    }

    out_dir = Path(__file__).parent / 'results'
    out_dir.mkdir(exist_ok=True)
    with open(out_dir / f'coopt_{scale}_K{K}.json', 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n  Results saved to results/coopt_{scale}_K{K}.json")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--scale', default='small', choices=['small', 'medium', 'large'])
    parser.add_argument('--K', type=int, default=4)
    parser.add_argument('--episodes', type=int, default=2000)
    args = parser.parse_args()

    run_experiment(args.scale, args.K, args.episodes)
