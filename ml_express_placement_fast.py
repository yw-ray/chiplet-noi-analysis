"""
ML Express Placement — Fast version
=====================================
Optimized for overnight run:
- K=16 only (manageable action space)
- RL: 200 episodes (was 300)
- Multiple budget levels per workload
- K=32: GNN only (skip RL — too slow)
"""

import json
import math
import time
import sys
import numpy as np
from pathlib import Path

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
# Surrogate (reuse trained model)
# ============================================================

class SurrogateModel(nn.Module):
    def __init__(self, input_dim=500, hidden=256):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden), nn.ReLU(), nn.LayerNorm(hidden),
            nn.Linear(hidden, hidden), nn.ReLU(), nn.LayerNorm(hidden),
            nn.Linear(hidden, 64), nn.ReLU(),
            nn.Linear(64, 1),
        )

    def forward(self, x):
        return self.net(x).squeeze(-1)


def load_surrogate():
    model = SurrogateModel(input_dim=500).to(DEVICE)
    path = RESULTS_DIR / 'surrogate_model.pt'
    if path.exists():
        model.load_state_dict(torch.load(path, map_location=DEVICE))
        print(f"  Loaded surrogate from {path}")
    else:
        print("  ERROR: No surrogate model found. Run ml_express_placement.py first.")
        sys.exit(1)
    model.eval()
    return model


# ============================================================
# GNN (reuse trained model)
# ============================================================

class GraphConvLayer(nn.Module):
    def __init__(self, in_dim, out_dim):
        super().__init__()
        self.W_self = nn.Linear(in_dim, out_dim)
        self.W_neigh = nn.Linear(in_dim, out_dim)

    def forward(self, x, adj):
        h_self = self.W_self(x)
        deg = adj.sum(dim=1, keepdim=True).clamp(min=1)
        h_neigh = self.W_neigh(torch.matmul(adj, x) / deg)
        return F.relu(h_self + h_neigh)


class GNNPlacementModel(nn.Module):
    def __init__(self, node_dim, hidden=64, n_layers=3):
        super().__init__()
        self.node_embed = nn.Linear(node_dim, hidden)
        self.convs = nn.ModuleList([
            GraphConvLayer(hidden, hidden) for _ in range(n_layers)
        ])
        self.edge_scorer = nn.Sequential(
            nn.Linear(hidden * 2 + 1, hidden), nn.ReLU(),
            nn.Linear(hidden, 1),
        )

    def forward(self, node_features, adj, edge_features, pair_indices):
        x = F.relu(self.node_embed(node_features))
        for conv in self.convs:
            x = conv(x, adj)
        src = x[pair_indices[:, 0]]
        dst = x[pair_indices[:, 1]]
        edge_input = torch.cat([src, dst, edge_features], dim=-1)
        return self.edge_scorer(edge_input).squeeze(-1)


def load_gnn():
    model = GNNPlacementModel(node_dim=4, hidden=64, n_layers=3).to(DEVICE)
    path = RESULTS_DIR / 'gnn_model.pt'
    if path.exists():
        model.load_state_dict(torch.load(path, map_location=DEVICE))
        print(f"  Loaded GNN from {path}")
    else:
        print("  ERROR: No GNN model found. Run ml_express_placement.py first.")
        sys.exit(1)
    model.eval()
    return model


def build_graph_data(grid, traffic, K):
    t_max = traffic.max()
    traffic_norm = traffic / t_max if t_max > 0 else traffic
    R, C = grid.rows, grid.cols
    node_features = []
    for i in range(K):
        r, c = i // C, i % C
        send = traffic_norm[i].sum()
        recv = traffic_norm[:, i].sum()
        node_features.append([r / R, c / C, send / K, recv / K])
    node_features = torch.tensor(node_features, dtype=torch.float32)
    adj = torch.tensor(traffic_norm, dtype=torch.float32)
    pairs, edge_feats = [], []
    for i in range(K):
        for j in range(i+1, K):
            pairs.append([i, j])
            edge_feats.append([traffic_norm[i, j]])
    return (node_features, adj,
            torch.tensor(edge_feats, dtype=torch.float32),
            torch.tensor(pairs, dtype=torch.long))


def gnn_allocate(model, grid, traffic, K, N, budget):
    node_features, adj, edge_features, pair_indices = build_graph_data(
        grid, traffic, K)
    model.eval()
    with torch.no_grad():
        scores = model(node_features.to(DEVICE), adj.to(DEVICE),
                       edge_features.to(DEVICE), pair_indices.to(DEVICE))
    adj_set = set(grid.get_adj_pairs())
    all_pairs = [(i, j) for i in range(K) for j in range(i+1, K)]

    # Guarantee connectivity: each adj pair gets at least 1 link
    alloc = {}
    used = 0
    for p in adj_set:
        alloc[p] = 1
        used += 1
    if used > budget:
        # Budget too small for even 1 per adj — fall back to adj uniform
        return alloc

    # Fill remaining budget by GNN scores
    sorted_idx = torch.argsort(scores, descending=True).cpu().numpy()
    for idx in sorted_idx:
        if used >= budget:
            break
        pair = all_pairs[idx]
        if pair not in alloc:
            alloc[pair] = 0
        if alloc[pair] < N:
            add = min(N - alloc[pair], budget - used)
            alloc[pair] += add
            used += add
    return alloc


# ============================================================
# RL Agent (optimized — fewer episodes, batch updates)
# ============================================================

class RLPolicy(nn.Module):
    def __init__(self, state_dim, n_actions, hidden=128):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim, hidden), nn.ReLU(),
            nn.Linear(hidden, hidden), nn.ReLU(),
            nn.Linear(hidden, n_actions),
        )

    def forward(self, state):
        return self.net(state)

    def select_action(self, state, valid_actions):
        logits = self.forward(state)
        mask = torch.full_like(logits, -1e9)
        mask[valid_actions] = 0
        probs = F.softmax(logits + mask, dim=-1)
        dist = torch.distributions.Categorical(probs)
        action = dist.sample()
        return action.item(), dist.log_prob(action)


def train_rl(surrogate, workload_name, K, N, R, C, budget_per_pair,
             n_episodes=200):
    grid = ChipletGrid(R, C)
    traffic = WORKLOADS[workload_name](K, grid)
    adj_pairs = grid.get_adj_pairs()
    adj_set = set(adj_pairs)
    n_adj = len(adj_pairs)
    budget = int(n_adj * budget_per_pair)
    all_pairs = [(i, j) for i in range(K) for j in range(i+1, K)]
    n_pairs = len(all_pairs)

    t_max = traffic.max()
    traffic_norm = traffic / t_max if t_max > 0 else traffic
    traffic_flat = traffic_norm[np.triu_indices(K, k=1)]

    # State: traffic_flat + allocation + [budget_frac, K_norm, N_norm]
    state_dim = n_pairs + n_pairs + 3
    policy = RLPolicy(state_dim, n_pairs).to(DEVICE)
    optimizer = optim.Adam(policy.parameters(), lr=3e-4)

    best_reward = -float('inf')
    best_alloc = None

    # Pre-allocate adj pair indices for connectivity guarantee
    adj_pair_indices = {}
    for i, p in enumerate(all_pairs):
        if p in adj_set:
            adj_pair_indices[p] = i

    for ep in range(n_episodes):
        allocation = np.zeros(n_pairs, dtype=np.float32)
        used = 0
        # Guarantee connectivity: 1 link per adj pair before RL starts
        for p, idx in adj_pair_indices.items():
            allocation[idx] = 1
            used += 1
        log_probs = []
        rewards = []

        while used < budget:
            # State
            budget_frac = used / max(budget, 1)
            state = np.concatenate([
                traffic_flat,
                allocation / N,
                [budget_frac, K / 32.0, N / 8.0],
            ]).astype(np.float32)
            state_t = torch.tensor(state, device=DEVICE)

            # Valid actions
            valid = [i for i in range(n_pairs)
                     if allocation[i] < N and used < budget]
            if not valid:
                break

            action, log_prob = policy.select_action(state_t, valid)
            allocation[action] += 1
            used += 1
            log_probs.append(log_prob)
            rewards.append(0)

        # End-of-episode reward from surrogate
        padded = list(traffic_flat) + [0.0] * (496 - len(traffic_flat))
        n_express = sum(1 for i, p in enumerate(all_pairs)
                        if allocation[i] > 0 and p not in adj_set)
        total = allocation.sum()
        bpp = total / max(n_adj, 1)
        features = padded + [bpp / 8.0,
                             n_express / max(total, 1),
                             K / 32.0, N / 8.0]
        x = torch.tensor([features], dtype=torch.float32, device=DEVICE)
        with torch.no_grad():
            pred_lat = surrogate(x).item()

        ep_reward = -pred_lat
        if rewards:
            rewards[-1] = ep_reward

        if ep_reward > best_reward:
            best_reward = ep_reward
            best_alloc_vec = allocation.copy()

        # REINFORCE
        if log_probs:
            returns = []
            R_val = 0
            for r in reversed(rewards):
                R_val = r + 0.99 * R_val
                returns.insert(0, R_val)
            returns = torch.tensor(returns, device=DEVICE)
            if returns.std() > 0:
                returns = (returns - returns.mean()) / (returns.std() + 1e-8)
            loss = sum(-lp * ret for lp, ret in zip(log_probs, returns))
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

        if (ep + 1) % 50 == 0:
            print(f"      Ep {ep+1}: pred_lat={-ep_reward:.1f}, "
                  f"best={-best_reward:.1f}", flush=True)

    # Convert to dict
    alloc = {}
    for i, p in enumerate(all_pairs):
        if best_alloc_vec[i] > 0:
            alloc[p] = int(best_alloc_vec[i])
    return alloc, -best_reward


# ============================================================
# BookSim validation
# ============================================================

def booksim_validate(alloc, grid, traffic, K, N, workload_name, label):
    npc = N * N
    base_rate = TOTAL_LOAD_BASE / (K * npc)
    traf_file = f'traffic_mlf_{workload_name}_{label}.txt'
    gen_traffic_matrix(grid, traffic, npc, CONFIG_DIR / traf_file)
    capped = {p: min(n, N) for p, n in alloc.items()}
    cfg_name = f'mlf_{workload_name}_{label}'
    gen_anynet_config(cfg_name, grid, capped, chip_n=N, outdir=CONFIG_DIR)
    r = run_booksim(cfg_name, traf_file, base_rate, timeout=600)
    return r['latency'], r['throughput']


# ============================================================
# Main
# ============================================================

def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    print("=== ML Express Placement — Fast Version ===", flush=True)
    surrogate = load_surrogate()
    gnn = load_gnn()

    # Test configs: all 4 workloads × multiple budgets × K=16 (RL+GNN) + K=32 (GNN only)
    configs = []
    for wl in ['tree_allreduce', 'hybrid_tp_pp', 'moe', 'uniform_random']:
        # K=16, N=4: budget 2x, 3x, 4x
        for bpp in [2, 3, 4]:
            configs.append((wl, 16, 4, 4, 4, bpp, True))   # RL+GNN
        # K=16, N=8: budget 2x, 4x, 7x
        for bpp in [2, 4, 7]:
            configs.append((wl, 16, 8, 4, 4, bpp, True))   # RL+GNN
        # K=32, N=4: budget 2x, 4x (GNN only)
        for bpp in [2, 4]:
            configs.append((wl, 32, 4, 4, 8, bpp, False))  # GNN only
        # K=32, N=8: budget 2x, 4x (GNN only)
        for bpp in [2, 4]:
            configs.append((wl, 32, 8, 4, 8, bpp, False))  # GNN only

    results_file = RESULTS_DIR / 'ml_comparison_fast.json'
    all_results = []
    if results_file.exists():
        with open(results_file) as f:
            all_results = json.load(f)
        done_keys = set(f"{r['workload']}_{r['K']}_{r['N']}_{r['budget_per_pair']}"
                        for r in all_results)
        print(f"  Loaded {len(all_results)} existing results", flush=True)
    else:
        done_keys = set()

    for idx, (wl, K, N, R, C, bpp, do_rl) in enumerate(configs):
        key = f"{wl}_{K}_{N}_{bpp}"
        if key in done_keys:
            print(f"\n[{idx+1}/{len(configs)}] SKIP {wl} K{K}N{N} {bpp}x",
                  flush=True)
            continue

        print(f"\n[{idx+1}/{len(configs)}] {wl} K{K}N{N} {bpp}x "
              f"({'RL+GNN' if do_rl else 'GNN only'})", flush=True)

        try:
            grid = ChipletGrid(R, C)
            traffic = WORKLOADS[wl](K, grid)
            adj_pairs = grid.get_adj_pairs()
            adj_set = set(adj_pairs)
            n_adj = len(adj_pairs)
            budget = int(n_adj * bpp)
            npc = N * N
            base_rate = TOTAL_LOAD_BASE / (K * npc)

            label = f'K{K}_N{N}_bpp{bpp}'

            # Traffic file (shared)
            traf_file = f'traffic_mlf_{wl}_{label}.txt'
            gen_traffic_matrix(grid, traffic, npc, CONFIG_DIR / traf_file)

            result = {'workload': wl, 'K': K, 'N': N,
                      'budget_per_pair': bpp, 'budget': budget}

            # --- Adj Uniform ---
            adj_alloc = alloc_adjacent_uniform(grid, budget)
            adj_capped = {p: min(n, N) for p, n in adj_alloc.items()}
            cfg = f'mlf_{wl}_{label}_adj'
            gen_anynet_config(cfg, grid, adj_capped, chip_n=N, outdir=CONFIG_DIR)
            r = run_booksim(cfg, traf_file, base_rate, timeout=300)
            result['adj_uniform'] = {'latency': r['latency'],
                                     'total_links': sum(adj_capped.values())}
            lat_s = f"{r['latency']:.1f}" if r['latency'] else "FAIL"
            print(f"    Adj:    lat={lat_s}", flush=True)

            # --- Express Greedy ---
            max_dist = min(3, max(R, C) - 1)
            if max_dist < 2:
                max_dist = 2
            greedy_alloc = alloc_express_greedy(grid, traffic, budget,
                                                 max_dist=max_dist)
            greedy_capped = {p: min(n, N) for p, n in greedy_alloc.items()}
            cfg = f'mlf_{wl}_{label}_greedy'
            gen_anynet_config(cfg, grid, greedy_capped, chip_n=N, outdir=CONFIG_DIR)
            r = run_booksim(cfg, traf_file, base_rate, timeout=300)
            n_expr_g = sum(1 for p in greedy_capped if p not in adj_set)
            result['express_greedy'] = {'latency': r['latency'],
                                         'n_express': n_expr_g,
                                         'total_links': sum(greedy_capped.values())}
            lat_s = f"{r['latency']:.1f}" if r['latency'] else "FAIL"
            print(f"    Greedy: lat={lat_s} express={n_expr_g}", flush=True)

            # --- GNN ---
            t0 = time.time()
            gnn_alloc = gnn_allocate(gnn, grid, traffic, K, N, budget)
            gnn_time = time.time() - t0
            gnn_capped = {p: min(n, N) for p, n in gnn_alloc.items()}
            cfg = f'mlf_{wl}_{label}_gnn'
            gen_anynet_config(cfg, grid, gnn_capped, chip_n=N, outdir=CONFIG_DIR)
            r = run_booksim(cfg, traf_file, base_rate, timeout=300)
            n_expr_gnn = sum(1 for p in gnn_capped if p not in adj_set)
            result['gnn_agent'] = {'latency': r['latency'],
                                    'n_express': n_expr_gnn,
                                    'total_links': sum(gnn_capped.values()),
                                    'inference_time': gnn_time}
            lat_s = f"{r['latency']:.1f}" if r['latency'] else "FAIL"
            print(f"    GNN:    lat={lat_s} express={n_expr_gnn} "
                  f"time={gnn_time:.3f}s", flush=True)

            # --- RL (K=16 only) ---
            if do_rl:
                t0 = time.time()
                rl_alloc, rl_pred = train_rl(surrogate, wl, K, N, R, C, bpp,
                                              n_episodes=150)
                rl_time = time.time() - t0
                rl_capped = {p: min(n, N) for p, n in rl_alloc.items()}
                cfg = f'mlf_{wl}_{label}_rl'
                gen_anynet_config(cfg, grid, rl_capped, chip_n=N, outdir=CONFIG_DIR)
                r = run_booksim(cfg, traf_file, base_rate, timeout=300)
                n_expr_rl = sum(1 for p in rl_capped if p not in adj_set)
                result['rl_agent'] = {'latency': r['latency'],
                                       'predicted_latency': rl_pred,
                                       'n_express': n_expr_rl,
                                       'total_links': sum(rl_capped.values()),
                                       'train_time': rl_time}
                lat_s = f"{r['latency']:.1f}" if r['latency'] else "FAIL"
                print(f"    RL:     lat={lat_s} express={n_expr_rl} "
                      f"time={rl_time:.0f}s", flush=True)
            else:
                result['rl_agent'] = None

            all_results.append(result)
            done_keys.add(key)

            # Save incrementally
            with open(results_file, 'w') as f:
                json.dump(all_results, f, indent=2)
            print(f"    Saved ({len(all_results)}/{len(configs)})", flush=True)

        except Exception as e:
            print(f"    ERROR: {e}", flush=True)
            import traceback
            traceback.print_exc()
            continue

    # === Summary ===
    print(f"\n\n{'='*80}", flush=True)
    print("  SUMMARY", flush=True)
    print(f"{'='*80}", flush=True)
    print(f"{'Config':<35s} {'Adj':>7s} {'Greedy':>7s} {'GNN':>7s} "
          f"{'RL':>7s} {'Best ML vs Greedy':>18s}", flush=True)
    print("-" * 85, flush=True)

    for r in all_results:
        lbl = f"{r['workload'][:8]} K{r['K']}N{r['N']} {r['budget_per_pair']}x"
        adj = r['adj_uniform']['latency']
        gre = r['express_greedy']['latency']
        gnn = r['gnn_agent']['latency']
        rl = r['rl_agent']['latency'] if r.get('rl_agent') else None

        adj_s = f"{adj:.1f}" if adj else "FAIL"
        gre_s = f"{gre:.1f}" if gre else "FAIL"
        gnn_s = f"{gnn:.1f}" if gnn else "FAIL"
        rl_s = f"{rl:.1f}" if rl else "N/A"

        # Best ML
        ml_lats = [x for x in [gnn, rl] if x is not None]
        if ml_lats and gre:
            best_ml = min(ml_lats)
            diff = (best_ml - gre) / gre * 100
            diff_s = f"{diff:+.1f}%"
        else:
            diff_s = "N/A"

        print(f"{lbl:<35s} {adj_s:>7s} {gre_s:>7s} {gnn_s:>7s} "
              f"{rl_s:>7s} {diff_s:>18s}", flush=True)

    print(f"\nResults: {results_file}", flush=True)


if __name__ == '__main__':
    main()
