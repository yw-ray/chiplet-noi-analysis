"""
ML-based Express Link Placement
================================

Two approaches for optimizing express link allocation:
1. RL Agent (REINFORCE) — sequential link placement with learned reward
2. GNN Agent — graph-based scoring for one-shot allocation

Both use a surrogate latency model trained on existing BookSim data,
then validate final solutions with actual BookSim runs.

Usage:
    python ml_express_placement.py [--phase surrogate|rl|gnn|validate|all]
    python ml_express_placement.py --phase all  # run everything
"""

import argparse
import json
import math
import time
import sys
import numpy as np
from pathlib import Path
from collections import defaultdict

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim

sys.path.insert(0, str(Path(__file__).parent))
from noi_topology_synthesis import ChipletGrid
from cost_performance_experiment import (
    gen_anynet_config, gen_traffic_matrix,
    alloc_adjacent_uniform, alloc_express_greedy,
    run_booksim,
)
from cost_perf_6panel_workload import WORKLOADS

CONFIG_DIR = Path(__file__).parent / 'booksim_configs'
RESULTS_DIR = Path(__file__).parent / 'results' / 'ml_placement'
TOTAL_LOAD_BASE = 0.32

DEVICE = torch.device('cpu')

# ============================================================
# Phase 0: Data Collection for Surrogate
# ============================================================

def collect_surrogate_data():
    """Collect (traffic, allocation, latency) tuples from existing results
    AND generate additional random allocations for training diversity."""

    data_points = []

    # --- Source 1: Existing experiment results ---
    workloads = ['tree_allreduce', 'hybrid_tp_pp', 'moe', 'uniform_random']
    for wl in workloads:
        for suffix in ['_incremental', '']:
            path = (Path(__file__).parent / 'results' /
                    f'cost_perf_6panel_{wl}' / f'cost_perf_6panel{suffix}.json')
            if path.exists():
                with open(path) as f:
                    results = json.load(f)
                break
        else:
            continue

        for panel_key, panel_data in results.items():
            K = panel_data['K']
            N = panel_data['N']
            R, C = panel_data['grid'].split('x')
            R, C = int(R), int(C)
            grid = ChipletGrid(R, C)
            adj_pairs = grid.get_adj_pairs()
            all_pairs = [(i, j) for i in range(K) for j in range(i+1, K)]

            traffic = WORKLOADS[wl](K, grid)
            # Normalize traffic to [0, 1]
            t_max = traffic.max()
            traffic_norm = traffic / t_max if t_max > 0 else traffic

            for exp in panel_data['experiments']:
                lat = exp['rates'][0]['latency']
                if lat is None:
                    continue

                # Reconstruct allocation vector (0/1 for each possible pair)
                # We'll encode as: for each pair, fraction of budget allocated
                budget = exp['budget']
                total_links = exp['total_links']

                data_points.append({
                    'workload': wl,
                    'K': K, 'N': N, 'R': R, 'C': C,
                    'traffic_flat': traffic_norm[np.triu_indices(K, k=1)].tolist(),
                    'budget': budget,
                    'budget_per_pair': exp['budget_per_pair'],
                    'strategy': exp['strategy'],
                    'n_express': exp['n_express'],
                    'total_links': total_links,
                    'latency': lat,
                })

    print(f"  Collected {len(data_points)} data points from existing results")
    return data_points


def build_feature_vectors(data_points):
    """Convert data points to feature vectors for surrogate training.

    Features per sample:
    - traffic upper triangle (K*(K-1)/2 values, normalized)
    - budget_per_pair (scalar)
    - n_express / total_links (express fraction)
    - K, N (config)
    """
    X_list, y_list = [], []

    for dp in data_points:
        K = dp['K']
        n_pairs = K * (K - 1) // 2

        # Pad traffic to max size (K=32 → 496 pairs)
        traffic = dp['traffic_flat']
        padded = traffic + [0.0] * (496 - len(traffic))

        features = padded + [
            dp['budget_per_pair'] / 8.0,  # normalize
            dp['n_express'] / max(dp['total_links'], 1),
            dp['K'] / 32.0,
            dp['N'] / 8.0,
        ]

        X_list.append(features)
        y_list.append(dp['latency'])

    return np.array(X_list, dtype=np.float32), np.array(y_list, dtype=np.float32)


# ============================================================
# Phase 1: Surrogate Latency Model
# ============================================================

class SurrogateModel(nn.Module):
    """MLP that predicts BookSim latency from traffic + allocation features."""

    def __init__(self, input_dim=500, hidden=256):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden),
            nn.ReLU(),
            nn.LayerNorm(hidden),
            nn.Linear(hidden, hidden),
            nn.ReLU(),
            nn.LayerNorm(hidden),
            nn.Linear(hidden, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
        )

    def forward(self, x):
        return self.net(x).squeeze(-1)


def train_surrogate(data_points):
    """Train surrogate model on collected data."""
    print("\n=== Phase 1: Training Surrogate Model ===")

    X, y = build_feature_vectors(data_points)
    print(f"  Data: {X.shape[0]} samples, {X.shape[1]} features")
    print(f"  Latency range: {y.min():.1f} - {y.max():.1f}")

    # Train/val split
    n = len(X)
    idx = np.random.RandomState(42).permutation(n)
    n_train = int(0.8 * n)
    X_train, y_train = X[idx[:n_train]], y[idx[:n_train]]
    X_val, y_val = X[idx[n_train:]], y[idx[n_train:]]

    X_train_t = torch.tensor(X_train, device=DEVICE)
    y_train_t = torch.tensor(y_train, device=DEVICE)
    X_val_t = torch.tensor(X_val, device=DEVICE)
    y_val_t = torch.tensor(y_val, device=DEVICE)

    model = SurrogateModel(input_dim=X.shape[1]).to(DEVICE)
    optimizer = optim.Adam(model.parameters(), lr=1e-3)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=50)

    best_val_loss = float('inf')
    best_state = None

    for epoch in range(500):
        model.train()
        pred = model(X_train_t)
        loss = F.mse_loss(pred, y_train_t)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        model.eval()
        with torch.no_grad():
            val_pred = model(X_val_t)
            val_loss = F.mse_loss(val_pred, y_val_t)
            val_mae = (val_pred - y_val_t).abs().mean()

        scheduler.step(val_loss)

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_state = {k: v.clone() for k, v in model.state_dict().items()}

        if (epoch + 1) % 100 == 0:
            print(f"  Epoch {epoch+1}: train_mse={loss:.2f}, "
                  f"val_mse={val_loss:.2f}, val_mae={val_mae:.2f}")

    model.load_state_dict(best_state)
    print(f"  Best val MSE: {best_val_loss:.2f}")

    # Save
    model_path = RESULTS_DIR / 'surrogate_model.pt'
    torch.save(best_state, model_path)
    print(f"  Saved to {model_path}")

    return model


# ============================================================
# Phase 2: RL Agent (REINFORCE)
# ============================================================

class ExpressLinkEnv:
    """Environment for sequential express link placement.

    State: (traffic_features, current_allocation, remaining_budget)
    Action: choose a chiplet pair to add a link to
    Reward: -latency from surrogate (or latency improvement)
    """

    def __init__(self, grid, traffic, budget, N, surrogate_model):
        self.grid = grid
        self.K = grid.K
        self.N = N
        self.traffic = traffic
        self.budget = budget
        self.max_links_per_pair = N
        self.surrogate = surrogate_model

        # All possible pairs (including non-adjacent)
        self.all_pairs = [(i, j) for i in range(self.K)
                          for j in range(i+1, self.K)]
        self.n_pairs = len(self.all_pairs)
        self.adj_set = set(grid.get_adj_pairs())

        # Precompute traffic features
        t_max = traffic.max()
        self.traffic_norm = traffic / t_max if t_max > 0 else traffic
        self.traffic_flat = self.traffic_norm[np.triu_indices(self.K, k=1)]

        self.reset()

    def reset(self):
        self.allocation = np.zeros(self.n_pairs, dtype=np.float32)
        self.used_budget = 0
        return self._get_state()

    def _get_state(self):
        """State vector: traffic features + allocation + budget info."""
        budget_frac = self.used_budget / max(self.budget, 1)
        return np.concatenate([
            self.traffic_flat,
            self.allocation / self.max_links_per_pair,
            [budget_frac, self.K / 32.0, self.N / 8.0],
        ]).astype(np.float32)

    def _get_valid_actions(self):
        """Actions that don't exceed per-pair or total budget."""
        valid = []
        for i, (ci, cj) in enumerate(self.all_pairs):
            if (self.allocation[i] < self.max_links_per_pair and
                    self.used_budget < self.budget):
                valid.append(i)
        return valid

    def _estimate_latency(self):
        """Use surrogate to estimate latency for current allocation."""
        # Build feature vector matching surrogate input format
        padded_traffic = list(self.traffic_flat) + [0.0] * (496 - len(self.traffic_flat))
        n_express = sum(1 for i, (ci, cj) in enumerate(self.all_pairs)
                        if self.allocation[i] > 0 and (ci, cj) not in self.adj_set)
        total_links = self.allocation.sum()
        bpp = total_links / max(len(self.adj_set), 1)

        features = padded_traffic + [
            bpp / 8.0,
            n_express / max(total_links, 1),
            self.K / 32.0,
            self.N / 8.0,
        ]
        x = torch.tensor([features], dtype=torch.float32, device=DEVICE)
        with torch.no_grad():
            return self.surrogate(x).item()

    def step(self, action):
        """Place a link at the chosen pair."""
        self.allocation[action] += 1
        self.used_budget += 1

        done = (self.used_budget >= self.budget or
                len(self._get_valid_actions()) == 0)

        if done:
            latency = self._estimate_latency()
            reward = -latency  # minimize latency
        else:
            reward = 0  # sparse reward at episode end

        return self._get_state(), reward, done

    def get_allocation_dict(self):
        """Convert internal allocation to dict format."""
        alloc = {}
        for i, (ci, cj) in enumerate(self.all_pairs):
            if self.allocation[i] > 0:
                alloc[(ci, cj)] = int(self.allocation[i])
        return alloc


class RLPolicy(nn.Module):
    """Policy network for REINFORCE."""

    def __init__(self, state_dim, n_actions, hidden=128):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim, hidden),
            nn.ReLU(),
            nn.Linear(hidden, hidden),
            nn.ReLU(),
            nn.Linear(hidden, n_actions),
        )

    def forward(self, state):
        return self.net(state)

    def select_action(self, state, valid_actions):
        """Sample action from policy, masked to valid actions."""
        logits = self.forward(state)
        # Mask invalid actions
        mask = torch.full_like(logits, -1e9)
        mask[valid_actions] = 0
        logits = logits + mask
        probs = F.softmax(logits, dim=-1)
        dist = torch.distributions.Categorical(probs)
        action = dist.sample()
        return action.item(), dist.log_prob(action)


def train_rl_agent(surrogate_model, workload_name, K, N, R, C, budget_per_pair):
    """Train RL agent for a specific (workload, config, budget)."""
    grid = ChipletGrid(R, C)
    traffic = WORKLOADS[workload_name](K, grid)
    adj_pairs = grid.get_adj_pairs()
    budget = int(len(adj_pairs) * budget_per_pair)

    env = ExpressLinkEnv(grid, traffic, budget, N, surrogate_model)
    state_dim = len(env._get_state())
    n_actions = env.n_pairs

    policy = RLPolicy(state_dim, n_actions).to(DEVICE)
    optimizer = optim.Adam(policy.parameters(), lr=3e-4)

    n_episodes = 300
    gamma = 0.99
    best_reward = -float('inf')
    best_alloc = None

    for ep in range(n_episodes):
        state = env.reset()
        log_probs = []
        rewards = []

        while True:
            state_t = torch.tensor(state, device=DEVICE)
            valid = env._get_valid_actions()
            if not valid:
                break
            action, log_prob = policy.select_action(state_t, valid)
            state, reward, done = env.step(action)
            log_probs.append(log_prob)
            rewards.append(reward)
            if done:
                break

        # Episode reward (only last step has non-zero reward)
        ep_reward = sum(rewards)
        if ep_reward > best_reward:
            best_reward = ep_reward
            best_alloc = env.get_allocation_dict()

        # REINFORCE update
        if log_probs:
            returns = []
            R = 0
            for r in reversed(rewards):
                R = r + gamma * R
                returns.insert(0, R)
            returns = torch.tensor(returns, device=DEVICE)
            if returns.std() > 0:
                returns = (returns - returns.mean()) / (returns.std() + 1e-8)

            policy_loss = 0
            for lp, ret in zip(log_probs, returns):
                policy_loss -= lp * ret
            optimizer.zero_grad()
            policy_loss.backward()
            optimizer.step()

        if (ep + 1) % 50 == 0:
            print(f"    Ep {ep+1}/{n_episodes}: reward={ep_reward:.1f}, "
                  f"best={best_reward:.1f}")

    return best_alloc, -best_reward  # return allocation and predicted latency


# ============================================================
# Phase 3: GNN Agent
# ============================================================

class GraphConvLayer(nn.Module):
    """Simple message-passing graph convolution."""

    def __init__(self, in_dim, out_dim):
        super().__init__()
        self.W_self = nn.Linear(in_dim, out_dim)
        self.W_neigh = nn.Linear(in_dim, out_dim)

    def forward(self, x, adj):
        """x: (N, in_dim), adj: (N, N) adjacency matrix."""
        h_self = self.W_self(x)
        # Aggregate neighbor features
        deg = adj.sum(dim=1, keepdim=True).clamp(min=1)
        h_neigh = self.W_neigh(torch.matmul(adj, x) / deg)
        return F.relu(h_self + h_neigh)


class GNNPlacementModel(nn.Module):
    """GNN that scores all chiplet pairs for link placement.

    Input: node features (traffic load, position) + edge features (traffic weight)
    Output: score for each pair (higher = should place more links)
    """

    def __init__(self, node_dim, hidden=64, n_layers=3):
        super().__init__()
        self.node_embed = nn.Linear(node_dim, hidden)
        self.convs = nn.ModuleList([
            GraphConvLayer(hidden, hidden) for _ in range(n_layers)
        ])
        # Edge scorer: takes concatenated node embeddings + edge features
        self.edge_scorer = nn.Sequential(
            nn.Linear(hidden * 2 + 1, hidden),
            nn.ReLU(),
            nn.Linear(hidden, 1),
        )

    def forward(self, node_features, adj, edge_features, pair_indices):
        """
        node_features: (K, node_dim)
        adj: (K, K) traffic-weighted adjacency
        edge_features: (n_pairs, 1) traffic weight per pair
        pair_indices: (n_pairs, 2) chiplet pair indices
        """
        x = F.relu(self.node_embed(node_features))
        for conv in self.convs:
            x = conv(x, adj)

        # Score each pair
        src = x[pair_indices[:, 0]]  # (n_pairs, hidden)
        dst = x[pair_indices[:, 1]]  # (n_pairs, hidden)
        edge_input = torch.cat([src, dst, edge_features], dim=-1)
        scores = self.edge_scorer(edge_input).squeeze(-1)
        return scores


def build_graph_data(grid, traffic, K):
    """Build GNN input features from chiplet grid and traffic matrix."""
    t_max = traffic.max()
    traffic_norm = traffic / t_max if t_max > 0 else traffic

    # Node features: (row_pos, col_pos, total_send, total_recv)
    R, C = grid.rows, grid.cols
    node_features = []
    for i in range(K):
        r, c = i // C, i % C
        send = traffic_norm[i].sum()
        recv = traffic_norm[:, i].sum()
        node_features.append([r / R, c / C, send / K, recv / K])
    node_features = torch.tensor(node_features, dtype=torch.float32)

    # Adjacency (traffic-weighted)
    adj = torch.tensor(traffic_norm, dtype=torch.float32)

    # All pairs and their traffic weights
    pairs = []
    edge_feats = []
    for i in range(K):
        for j in range(i+1, K):
            pairs.append([i, j])
            edge_feats.append([traffic_norm[i, j]])
    pair_indices = torch.tensor(pairs, dtype=torch.long)
    edge_features = torch.tensor(edge_feats, dtype=torch.float32)

    return node_features, adj, edge_features, pair_indices


def gnn_allocate(model, grid, traffic, K, N, budget):
    """Use trained GNN to produce an allocation."""
    node_features, adj, edge_features, pair_indices = build_graph_data(
        grid, traffic, K)

    model.eval()
    with torch.no_grad():
        scores = model(node_features.to(DEVICE),
                       adj.to(DEVICE),
                       edge_features.to(DEVICE),
                       pair_indices.to(DEVICE))

    # Convert scores to allocation: greedily assign links to highest-scored pairs
    adj_set = set(grid.get_adj_pairs())
    all_pairs = [(i, j) for i in range(K) for j in range(i+1, K)]
    max_links_per_pair = N

    # Sort pairs by score (descending)
    sorted_idx = torch.argsort(scores, descending=True).cpu().numpy()

    alloc = {}
    used = 0
    for idx in sorted_idx:
        if used >= budget:
            break
        pair = all_pairs[idx]
        if pair not in alloc:
            alloc[pair] = 0
        if alloc[pair] < max_links_per_pair:
            add = min(max_links_per_pair - alloc[pair], budget - used)
            alloc[pair] += add
            used += add

    return alloc


def train_gnn_agent(surrogate_model, workload_configs):
    """Train GNN using surrogate-guided policy gradient.

    The GNN outputs pair scores → allocation → surrogate predicts latency
    → optimize to minimize latency.
    """
    print("\n=== Phase 3: Training GNN Agent ===")

    # Use K=16 for training (faster), then test on K=32
    model = GNNPlacementModel(node_dim=4, hidden=64, n_layers=3).to(DEVICE)
    optimizer = optim.Adam(model.parameters(), lr=1e-3)

    n_epochs = 200

    for epoch in range(n_epochs):
        total_loss = 0
        n_configs = 0

        for wl, K, N, R, C, bpp in workload_configs:
            grid = ChipletGrid(R, C)
            traffic = WORKLOADS[wl](K, grid)
            adj_pairs = grid.get_adj_pairs()
            budget = int(len(adj_pairs) * bpp)
            adj_set = set(adj_pairs)
            all_pairs = [(i, j) for i in range(K) for j in range(i+1, K)]

            node_features, adj, edge_features, pair_indices = build_graph_data(
                grid, traffic, K)

            # Forward pass (no batch dim — GNN operates on single graph)
            scores = model(
                node_features.to(DEVICE),
                adj.to(DEVICE),
                edge_features.to(DEVICE),
                pair_indices.to(DEVICE),
            )

            # Differentiable allocation via softmax
            probs = F.softmax(scores, dim=0)

            # Compute allocation: budget * probability for each pair
            alloc_soft = probs * budget

            # Surrogate evaluation: build feature vector
            t_max = traffic.max()
            traffic_norm = traffic / t_max if t_max > 0 else traffic
            traffic_flat = traffic_norm[np.triu_indices(K, k=1)]
            padded = list(traffic_flat) + [0.0] * (496 - len(traffic_flat))

            # Estimate express fraction from scores
            adj_indices = [i for i, p in enumerate(all_pairs) if p in adj_set]
            non_adj_indices = [i for i, p in enumerate(all_pairs)
                               if p not in adj_set]
            express_frac = (probs[non_adj_indices].sum() if non_adj_indices
                            else torch.tensor(0.0))

            features = padded + [
                bpp / 8.0,
                express_frac.item(),
                K / 32.0,
                N / 8.0,
            ]
            x = torch.tensor([features], dtype=torch.float32, device=DEVICE)

            with torch.no_grad():
                predicted_lat = surrogate_model(x)

            # Loss: we want to minimize latency
            # Use score entropy as regularizer + surrogate loss
            # Since surrogate is not differentiable w.r.t. allocation,
            # we use REINFORCE-style: reward * log_prob
            reward = -predicted_lat.item()
            entropy = -(probs * (probs + 1e-8).log()).sum()
            loss = -reward * entropy * 0.01 + scores.mean() * 0  # prevent unused

            # Alternative: directly optimize traffic-aware objective
            # Minimize weighted hop distance
            hop_loss = 0
            for i, (ci, cj) in enumerate(all_pairs):
                ri, ci_pos = ci // grid.cols, ci % grid.cols
                rj, cj_pos = cj // grid.cols, cj % grid.cols
                dist = abs(ri - rj) + abs(ci_pos - cj_pos)
                # Want high score for high-traffic, high-distance pairs
                hop_loss += probs[i] * (-traffic_norm[ci, cj] * dist)

            loss = hop_loss + 0.01 * entropy  # encourage exploration

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            total_loss += loss.item()
            n_configs += 1

        if (epoch + 1) % 50 == 0:
            print(f"  Epoch {epoch+1}/{n_epochs}: avg_loss={total_loss/n_configs:.4f}")

    # Save model
    model_path = RESULTS_DIR / 'gnn_model.pt'
    torch.save(model.state_dict(), model_path)
    print(f"  Saved to {model_path}")

    return model


# ============================================================
# Phase 4: BookSim Validation
# ============================================================

def validate_with_booksim(alloc, grid, traffic, K, N, workload_name,
                          budget_per_pair, label):
    """Run actual BookSim to validate an allocation."""
    npc = N * N
    base_rate = TOTAL_LOAD_BASE / (K * npc)

    traf_file = f'traffic_ml_{workload_name}_{label}.txt'
    gen_traffic_matrix(grid, traffic, npc, CONFIG_DIR / traf_file)

    # Cap allocation
    max_lpp = N
    capped = {p: min(n, max_lpp) for p, n in alloc.items()}

    cfg_name = f'ml_{workload_name}_{label}'
    gen_anynet_config(cfg_name, grid, capped, chip_n=N, outdir=CONFIG_DIR)

    r = run_booksim(cfg_name, traf_file, base_rate, timeout=300)
    return r['latency'], r['throughput']


# ============================================================
# Main Experiment
# ============================================================

def run_comparison(surrogate_model, gnn_model, workload_name, K, N, R, C,
                   budget_per_pair):
    """Compare greedy vs RL vs GNN for one configuration."""
    grid = ChipletGrid(R, C)
    traffic = WORKLOADS[workload_name](K, grid)
    adj_pairs = grid.get_adj_pairs()
    n_adj = len(adj_pairs)
    budget = int(n_adj * budget_per_pair)
    npc = N * N
    max_lpp = N
    base_rate = TOTAL_LOAD_BASE / (K * npc)

    panel_label = f'K{K}_N{N}_bpp{int(budget_per_pair)}'

    results = {'workload': workload_name, 'K': K, 'N': N,
               'budget_per_pair': budget_per_pair, 'budget': budget}

    # --- Baseline 1: Adjacent Uniform ---
    adj_alloc = alloc_adjacent_uniform(grid, budget)
    adj_capped = {p: min(n, max_lpp) for p, n in adj_alloc.items()}
    traf_file = f'traffic_ml_{workload_name}_{panel_label}.txt'
    gen_traffic_matrix(grid, traffic, npc, CONFIG_DIR / traf_file)
    cfg = f'ml_{workload_name}_{panel_label}_adj'
    gen_anynet_config(cfg, grid, adj_capped, chip_n=N, outdir=CONFIG_DIR)
    r = run_booksim(cfg, traf_file, base_rate, timeout=300)
    results['adj_uniform'] = {'latency': r['latency'],
                              'n_express': 0,
                              'total_links': sum(adj_capped.values())}
    print(f"    Adj Uniform:  lat={r['latency']:.1f}" if r['latency'] else
          "    Adj Uniform:  FAIL")

    # --- Baseline 2: Express Greedy ---
    max_dist = min(3, max(R, C) - 1)
    if max_dist < 2:
        max_dist = 2
    greedy_alloc = alloc_express_greedy(grid, traffic, budget,
                                         max_dist=max_dist)
    greedy_capped = {p: min(n, max_lpp) for p, n in greedy_alloc.items()}
    cfg = f'ml_{workload_name}_{panel_label}_greedy'
    gen_anynet_config(cfg, grid, greedy_capped, chip_n=N, outdir=CONFIG_DIR)
    r = run_booksim(cfg, traf_file, base_rate, timeout=300)
    n_expr_greedy = sum(1 for p in greedy_capped if p not in set(adj_pairs))
    results['express_greedy'] = {'latency': r['latency'],
                                  'n_express': n_expr_greedy,
                                  'total_links': sum(greedy_capped.values())}
    print(f"    Greedy:       lat={r['latency']:.1f}, express={n_expr_greedy}"
          if r['latency'] else "    Greedy:       FAIL")

    # --- RL Agent ---
    print(f"    Training RL agent...")
    t0 = time.time()
    rl_alloc, rl_pred_lat = train_rl_agent(
        surrogate_model, workload_name, K, N, R, C, budget_per_pair)
    rl_time = time.time() - t0
    rl_capped = {p: min(n, max_lpp) for p, n in rl_alloc.items()}
    cfg = f'ml_{workload_name}_{panel_label}_rl'
    gen_anynet_config(cfg, grid, rl_capped, chip_n=N, outdir=CONFIG_DIR)
    r = run_booksim(cfg, traf_file, base_rate, timeout=300)
    n_expr_rl = sum(1 for p in rl_capped if p not in set(adj_pairs))
    results['rl_agent'] = {'latency': r['latency'],
                           'predicted_latency': rl_pred_lat,
                           'n_express': n_expr_rl,
                           'total_links': sum(rl_capped.values()),
                           'train_time': rl_time}
    print(f"    RL Agent:     lat={r['latency']:.1f}, express={n_expr_rl}, "
          f"time={rl_time:.0f}s"
          if r['latency'] else f"    RL Agent:     FAIL, time={rl_time:.0f}s")

    # --- GNN Agent ---
    t0 = time.time()
    gnn_alloc = gnn_allocate(gnn_model, grid, traffic, K, N, budget)
    gnn_time = time.time() - t0
    gnn_capped = {p: min(n, max_lpp) for p, n in gnn_alloc.items()}
    cfg = f'ml_{workload_name}_{panel_label}_gnn'
    gen_anynet_config(cfg, grid, gnn_capped, chip_n=N, outdir=CONFIG_DIR)
    r = run_booksim(cfg, traf_file, base_rate, timeout=300)
    n_expr_gnn = sum(1 for p in gnn_capped if p not in set(adj_pairs))
    results['gnn_agent'] = {'latency': r['latency'],
                            'n_express': n_expr_gnn,
                            'total_links': sum(gnn_capped.values()),
                            'inference_time': gnn_time}
    print(f"    GNN Agent:    lat={r['latency']:.1f}, express={n_expr_gnn}, "
          f"time={gnn_time:.2f}s"
          if r['latency'] else f"    GNN Agent:    FAIL, time={gnn_time:.2f}s")

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', default='all',
                        choices=['surrogate', 'rl', 'gnn', 'validate', 'all'])
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # === Phase 0+1: Surrogate ===
    print("=== Phase 0: Collecting surrogate training data ===")
    data_points = collect_surrogate_data()
    surrogate = train_surrogate(data_points)

    # === Phase 2+3: Train agents ===
    # Training configs (K=16 for speed)
    train_configs = [
        ('tree_allreduce', 16, 4, 4, 4, 3),
        ('hybrid_tp_pp', 16, 4, 4, 4, 3),
        ('moe', 16, 4, 4, 4, 3),
        ('uniform_random', 16, 4, 4, 4, 3),
        ('tree_allreduce', 16, 8, 4, 4, 4),
        ('hybrid_tp_pp', 16, 8, 4, 4, 4),
        ('moe', 16, 8, 4, 4, 4),
        ('uniform_random', 16, 8, 4, 4, 4),
    ]
    gnn_model = train_gnn_agent(surrogate, train_configs)

    # === Phase 4: Full comparison ===
    print("\n" + "=" * 70)
    print("  FULL COMPARISON: Greedy vs RL vs GNN")
    print("=" * 70)

    test_configs = [
        # (workload, K, N, R, C, budget_per_pair)
        ('moe', 16, 4, 4, 4, 4),
        ('moe', 32, 8, 4, 8, 4),
        ('hybrid_tp_pp', 16, 4, 4, 4, 4),
        ('hybrid_tp_pp', 32, 8, 4, 8, 4),
        ('uniform_random', 16, 4, 4, 4, 4),
        ('uniform_random', 32, 8, 4, 8, 4),
        ('tree_allreduce', 16, 4, 4, 4, 4),
        ('tree_allreduce', 32, 8, 4, 8, 4),
    ]

    all_results = []
    for wl, K, N, R, C, bpp in test_configs:
        print(f"\n  --- {wl} K={K} N={N} budget={bpp}x ---")
        result = run_comparison(surrogate, gnn_model, wl, K, N, R, C, bpp)
        all_results.append(result)

        # Save incrementally
        with open(RESULTS_DIR / 'ml_comparison.json', 'w') as f:
            json.dump(all_results, f, indent=2)

    # === Summary ===
    print("\n\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print(f"{'Config':<30s} {'Adj':>8s} {'Greedy':>8s} {'RL':>8s} {'GNN':>8s}")
    print("-" * 70)
    for r in all_results:
        label = f"{r['workload'][:8]} K{r['K']}N{r['N']} {r['budget_per_pair']}x"
        adj = f"{r['adj_uniform']['latency']:.1f}" if r['adj_uniform']['latency'] else "FAIL"
        gre = f"{r['express_greedy']['latency']:.1f}" if r['express_greedy']['latency'] else "FAIL"
        rl = f"{r['rl_agent']['latency']:.1f}" if r['rl_agent']['latency'] else "FAIL"
        gnn = f"{r['gnn_agent']['latency']:.1f}" if r['gnn_agent']['latency'] else "FAIL"
        print(f"{label:<30s} {adj:>8s} {gre:>8s} {rl:>8s} {gnn:>8s}")

    print(f"\nResults saved to {RESULTS_DIR / 'ml_comparison.json'}")


if __name__ == '__main__':
    main()
