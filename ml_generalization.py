"""
Generalization Test: Apply trained RL/GNN models to UNSEEN workloads.

Training workloads (original): tree, hybrid, moe, uniform
Test workloads (NEW, unseen):  ring_allreduce, pipeline_parallel, all_to_all

Key question: Does the learned RL swap policy and GNN placement model
generalize to workloads they were NEVER trained on?
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
# Reuse surrogate and GNN architectures
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

    # Connectivity: each adj pair gets at least 1
    alloc = {}
    used = 0
    for p in adj_set:
        alloc[p] = 1
        used += 1
    if used > budget:
        return alloc

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


def surrogate_predict(surrogate, traffic_flat, allocation, adj_set, all_pairs,
                     K, N, n_adj):
    padded = list(traffic_flat) + [0.0] * (496 - len(traffic_flat))
    n_express = sum(1 for i, p in enumerate(all_pairs)
                    if allocation[i] > 0 and p not in adj_set)
    total = allocation.sum()
    bpp = total / max(n_adj, 1)
    features = padded + [bpp / 8.0, n_express / max(total, 1),
                         K / 32.0, N / 8.0]
    x = torch.tensor([features], dtype=torch.float32, device=DEVICE)
    with torch.no_grad():
        return surrogate(x).item()


# ============================================================
# Warm-start RL (reused)
# ============================================================

class SwapPolicy(nn.Module):
    def __init__(self, state_dim, n_pairs, hidden=128):
        super().__init__()
        self.trunk = nn.Sequential(
            nn.Linear(state_dim, hidden), nn.ReLU(),
            nn.Linear(hidden, hidden), nn.ReLU(),
        )
        self.remove_head = nn.Linear(hidden, n_pairs)
        self.add_head = nn.Linear(hidden + n_pairs, n_pairs)

    def select_swap(self, state, alloc, max_lpp):
        h = self.trunk(state)
        remove_logits = self.remove_head(h)
        remove_mask = torch.full_like(remove_logits, -1e9)
        valid_remove = (alloc > 0)
        remove_mask[valid_remove] = 0
        remove_probs = F.softmax(remove_logits + remove_mask, dim=-1)
        remove_dist = torch.distributions.Categorical(remove_probs)
        remove_idx = remove_dist.sample()
        remove_logp = remove_dist.log_prob(remove_idx)

        one_hot = F.one_hot(remove_idx, num_classes=alloc.shape[0]).float()
        add_input = torch.cat([h, one_hot], dim=-1)
        add_logits = self.add_head(add_input)
        add_mask = torch.full_like(add_logits, -1e9)
        valid_add = (alloc < max_lpp).clone()
        valid_add[remove_idx.item()] = False
        add_mask[valid_add] = 0
        add_probs = F.softmax(add_logits + add_mask, dim=-1)
        add_dist = torch.distributions.Categorical(add_probs)
        add_idx = add_dist.sample()
        add_logp = add_dist.log_prob(add_idx)

        return remove_idx.item(), add_idx.item(), remove_logp + add_logp


def train_warmstart_rl_for_workload(surrogate, workload_name, K, N, R, C,
                                     budget_per_pair, n_episodes=150):
    grid = ChipletGrid(R, C)
    traffic = WORKLOADS[workload_name](K, grid)
    adj_pairs = grid.get_adj_pairs()
    adj_set = set(adj_pairs)
    n_adj = len(adj_pairs)
    budget = int(n_adj * budget_per_pair)
    all_pairs = [(i, j) for i in range(K) for j in range(i+1, K)]
    n_pairs = len(all_pairs)
    pair_to_idx = {p: i for i, p in enumerate(all_pairs)}

    max_dist = min(3, max(R, C) - 1)
    if max_dist < 2:
        max_dist = 2
    greedy_alloc = alloc_express_greedy(grid, traffic, budget, max_dist=max_dist)
    greedy_capped = {p: min(n, N) for p, n in greedy_alloc.items()}

    greedy_vec = np.zeros(n_pairs, dtype=np.float32)
    for p, n in greedy_capped.items():
        greedy_vec[pair_to_idx[p]] = n

    t_max = traffic.max()
    traffic_norm = traffic / t_max if t_max > 0 else traffic
    traffic_flat = traffic_norm[np.triu_indices(K, k=1)]

    baseline_pred = surrogate_predict(surrogate, traffic_flat, greedy_vec,
                                      adj_set, all_pairs, K, N, n_adj)

    n_swaps = max(5, budget // 7)
    state_dim = n_pairs + n_pairs + 3
    policy = SwapPolicy(state_dim, n_pairs).to(DEVICE)
    optimizer = optim.Adam(policy.parameters(), lr=3e-4)

    best_pred = baseline_pred
    best_alloc_vec = greedy_vec.copy()

    for ep in range(n_episodes):
        allocation = greedy_vec.copy()
        log_probs = []

        for _ in range(n_swaps):
            budget_frac = allocation.sum() / max(budget, 1)
            state = np.concatenate([
                traffic_flat, allocation / N,
                [budget_frac, K / 32.0, N / 8.0],
            ]).astype(np.float32)
            state_t = torch.tensor(state, device=DEVICE)
            alloc_t = torch.tensor(allocation, device=DEVICE)
            rem_idx, add_idx, logp = policy.select_swap(state_t, alloc_t, N)
            allocation[rem_idx] -= 1
            allocation[add_idx] += 1
            log_probs.append(logp)

        pred_lat = surrogate_predict(surrogate, traffic_flat, allocation,
                                     adj_set, all_pairs, K, N, n_adj)
        reward = baseline_pred - pred_lat

        if pred_lat < best_pred:
            best_pred = pred_lat
            best_alloc_vec = allocation.copy()

        if log_probs:
            loss = sum(-lp * reward for lp in log_probs)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

    if best_pred >= baseline_pred:
        final_vec = greedy_vec
    else:
        final_vec = best_alloc_vec

    alloc = {}
    for i, p in enumerate(all_pairs):
        if final_vec[i] > 0:
            alloc[p] = int(final_vec[i])
    return alloc


# ============================================================
# Main
# ============================================================

def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    print("=== Generalization Test: Unseen Workloads ===", flush=True)

    # Load trained models
    surrogate = SurrogateModel(input_dim=500).to(DEVICE)
    surrogate.load_state_dict(torch.load(RESULTS_DIR / 'surrogate_model.pt',
                                         map_location=DEVICE))
    surrogate.eval()
    print("  Loaded surrogate (trained on tree/hybrid/moe/uniform)", flush=True)

    gnn = GNNPlacementModel(node_dim=4, hidden=64, n_layers=3).to(DEVICE)
    gnn.load_state_dict(torch.load(RESULTS_DIR / 'gnn_model.pt',
                                    map_location=DEVICE))
    gnn.eval()
    print("  Loaded GNN (trained on tree/hybrid/moe/uniform)", flush=True)

    # UNSEEN test workloads
    unseen_workloads = ['ring_allreduce', 'pipeline_parallel', 'all_to_all']
    # Test configs
    configs = []
    for wl in unseen_workloads:
        configs.append((wl, 16, 4, 4, 4, 4))   # K=16 N=4 4x
        configs.append((wl, 16, 8, 4, 4, 4))   # K=16 N=8 4x
        configs.append((wl, 32, 4, 4, 8, 4))   # K=32 N=4 4x
        configs.append((wl, 32, 8, 4, 8, 4))   # K=32 N=8 4x

    print(f"\n  Testing on {len(unseen_workloads)} UNSEEN workloads, "
          f"{len(configs)} configs total", flush=True)

    results_file = RESULTS_DIR / 'ml_generalization.json'
    all_results = []
    done_keys = set()
    if results_file.exists():
        with open(results_file) as f:
            all_results = json.load(f)
        done_keys = set(f"{r['workload']}_{r['K']}_{r['N']}_{r['budget_per_pair']}"
                        for r in all_results)
        print(f"  Loaded {len(all_results)} existing results", flush=True)

    for idx, (wl, K, N, R, C, bpp) in enumerate(configs):
        key = f"{wl}_{K}_{N}_{bpp}"
        if key in done_keys:
            print(f"\n[{idx+1}/{len(configs)}] SKIP {wl} K{K}N{N} {bpp}x",
                  flush=True)
            continue

        print(f"\n[{idx+1}/{len(configs)}] {wl} K{K}N{N} {bpp}x "
              f"(UNSEEN workload)", flush=True)

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
            traf_file = f'traffic_gen_{wl}_{label}.txt'
            gen_traffic_matrix(grid, traffic, npc, CONFIG_DIR / traf_file)

            result = {'workload': wl, 'K': K, 'N': N,
                      'budget_per_pair': bpp, 'budget': budget}

            # --- Greedy ---
            max_dist = min(3, max(R, C) - 1)
            if max_dist < 2:
                max_dist = 2
            greedy_alloc = alloc_express_greedy(grid, traffic, budget,
                                                 max_dist=max_dist)
            greedy_capped = {p: min(n, N) for p, n in greedy_alloc.items()}
            cfg = f'gen_{wl}_{label}_greedy'
            gen_anynet_config(cfg, grid, greedy_capped, chip_n=N,
                              outdir=CONFIG_DIR)
            r = run_booksim(cfg, traf_file, base_rate, timeout=300)
            n_expr_g = sum(1 for p in greedy_capped if p not in adj_set)
            result['express_greedy'] = {'latency': r['latency'],
                                         'n_express': n_expr_g}
            lat_s = f"{r['latency']:.1f}" if r['latency'] else "FAIL"
            print(f"    Greedy: lat={lat_s}", flush=True)

            # --- GNN (zero-shot, no training on this workload) ---
            t0 = time.time()
            gnn_alloc = gnn_allocate(gnn, grid, traffic, K, N, budget)
            gnn_time = time.time() - t0
            gnn_capped = {p: min(n, N) for p, n in gnn_alloc.items()}
            cfg = f'gen_{wl}_{label}_gnn'
            gen_anynet_config(cfg, grid, gnn_capped, chip_n=N, outdir=CONFIG_DIR)
            r = run_booksim(cfg, traf_file, base_rate, timeout=300)
            n_expr_gnn = sum(1 for p in gnn_capped if p not in adj_set)
            result['gnn_agent'] = {'latency': r['latency'],
                                    'n_express': n_expr_gnn,
                                    'inference_time': gnn_time}
            lat_s = f"{r['latency']:.1f}" if r['latency'] else "FAIL"
            print(f"    GNN:    lat={lat_s}", flush=True)

            # --- Warm-Start RL (retrain per config, using pre-trained surrogate) ---
            if K <= 16:  # Only K=16 for RL (K=32 too slow)
                t0 = time.time()
                rl_alloc = train_warmstart_rl_for_workload(
                    surrogate, wl, K, N, R, C, bpp, n_episodes=150)
                rl_time = time.time() - t0
                rl_capped = {p: min(n, N) for p, n in rl_alloc.items()}
                cfg = f'gen_{wl}_{label}_rl'
                gen_anynet_config(cfg, grid, rl_capped, chip_n=N,
                                  outdir=CONFIG_DIR)
                r = run_booksim(cfg, traf_file, base_rate, timeout=300)
                n_expr_rl = sum(1 for p in rl_capped if p not in adj_set)
                result['rl_warmstart'] = {'latency': r['latency'],
                                           'n_express': n_expr_rl,
                                           'train_time': rl_time}
                lat_s = f"{r['latency']:.1f}" if r['latency'] else "FAIL"
                print(f"    RL-WS:  lat={lat_s}", flush=True)
            else:
                result['rl_warmstart'] = None

            all_results.append(result)
            done_keys.add(key)
            with open(results_file, 'w') as f:
                json.dump(all_results, f, indent=2)
            print(f"    Saved ({len(all_results)}/{len(configs)})", flush=True)

        except Exception as e:
            print(f"    ERROR: {e}", flush=True)
            import traceback
            traceback.print_exc()
            continue

    # Summary
    print(f"\n\n{'='*75}", flush=True)
    print(f"  GENERALIZATION SUMMARY — Models trained on "
          f"[tree/hybrid/moe/uniform]", flush=True)
    print(f"  Tested on UNSEEN: [ring/pipeline/all_to_all]", flush=True)
    print(f"{'='*75}", flush=True)
    print(f"{'Config':<30s} {'Greedy':>7s} {'GNN':>7s} {'RL-WS':>7s} "
          f"{'GNN vs Gre':>10s} {'RL vs Gre':>10s}", flush=True)
    print("-" * 85, flush=True)

    for r in all_results:
        lbl = f"{r['workload'][:12]} K{r['K']}N{r['N']} {r['budget_per_pair']}x"
        gre = r['express_greedy']['latency']
        gnn = r['gnn_agent']['latency']
        rl = r['rl_warmstart']['latency'] if r.get('rl_warmstart') else None
        gre_s = f"{gre:.1f}" if gre else "FAIL"
        gnn_s = f"{gnn:.1f}" if gnn else "FAIL"
        rl_s = f"{rl:.1f}" if rl else "N/A"
        gnn_vs = f"{(gnn-gre)/gre*100:+.1f}%" if gre and gnn else "N/A"
        rl_vs = f"{(rl-gre)/gre*100:+.1f}%" if gre and rl else "N/A"
        print(f"{lbl:<30s} {gre_s:>7s} {gnn_s:>7s} {rl_s:>7s} "
              f"{gnn_vs:>10s} {rl_vs:>10s}", flush=True)


if __name__ == '__main__':
    main()
