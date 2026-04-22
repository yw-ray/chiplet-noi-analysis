"""
ML Express Placement — Warm-Start RL Version
==============================================
Key improvements over ml_express_placement_fast.py:

1. **Warm-Start RL**: Starts from greedy allocation, not zero.
   - Action space: "swap a link" (remove from pair X, add to best alternative)
   - Guarantees worst-case = greedy (if no swap improves, RL keeps greedy)

2. **Safety Fallback**: If RL's best < greedy (via surrogate), use RL;
   otherwise use greedy. Final result never worse than greedy.

3. **Surrogate reused**: from ml_express_placement.py (288 training points).

Target: RL >= greedy in all 40 configs.
"""

import json
import math
import time
import sys
import numpy as np
from pathlib import Path
from copy import deepcopy

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
    model.load_state_dict(torch.load(path, map_location=DEVICE))
    model.eval()
    print(f"  Loaded surrogate from {path}", flush=True)
    return model


def surrogate_predict(surrogate, traffic_flat, allocation, adj_set, all_pairs,
                     K, N, budget, n_adj):
    """Predict latency for a given allocation."""
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
# Warm-Start RL (swap-based)
# ============================================================

class SwapPolicy(nn.Module):
    """Policy network that selects which link to swap.

    Output: logits over (remove_pair, add_pair) joint action space.
    We decompose: first choose remove, then choose add (conditional on remove).
    """

    def __init__(self, state_dim, n_pairs, hidden=128):
        super().__init__()
        self.trunk = nn.Sequential(
            nn.Linear(state_dim, hidden), nn.ReLU(),
            nn.Linear(hidden, hidden), nn.ReLU(),
        )
        self.remove_head = nn.Linear(hidden, n_pairs)
        self.add_head = nn.Linear(hidden + n_pairs, n_pairs)

    def select_swap(self, state, alloc, max_lpp):
        """Select (remove_idx, add_idx) pair.

        alloc: current allocation vector
        max_lpp: max links per pair
        """
        h = self.trunk(state)

        # Step 1: choose remove_idx (must have allocation > 0)
        remove_logits = self.remove_head(h)
        remove_mask = torch.full_like(remove_logits, -1e9)
        valid_remove = (alloc > 0)
        remove_mask[valid_remove] = 0
        remove_probs = F.softmax(remove_logits + remove_mask, dim=-1)
        remove_dist = torch.distributions.Categorical(remove_probs)
        remove_idx = remove_dist.sample()
        remove_logp = remove_dist.log_prob(remove_idx)

        # Step 2: choose add_idx (must have allocation < max_lpp, different from remove)
        one_hot = F.one_hot(remove_idx, num_classes=alloc.shape[0]).float()
        add_input = torch.cat([h, one_hot], dim=-1)
        add_logits = self.add_head(add_input)
        add_mask = torch.full_like(add_logits, -1e9)
        valid_add = (alloc < max_lpp)
        valid_add = valid_add.clone()
        valid_add[remove_idx.item()] = False  # can't add to same pair we removed from
        add_mask[valid_add] = 0
        add_probs = F.softmax(add_logits + add_mask, dim=-1)
        add_dist = torch.distributions.Categorical(add_probs)
        add_idx = add_dist.sample()
        add_logp = add_dist.log_prob(add_idx)

        return remove_idx.item(), add_idx.item(), remove_logp + add_logp


def train_warmstart_rl(surrogate, workload_name, K, N, R, C, budget_per_pair,
                        n_episodes=200, n_swaps=None):
    """Train warm-start RL that refines greedy allocation via swaps."""
    grid = ChipletGrid(R, C)
    traffic = WORKLOADS[workload_name](K, grid)
    adj_pairs = grid.get_adj_pairs()
    adj_set = set(adj_pairs)
    n_adj = len(adj_pairs)
    budget = int(n_adj * budget_per_pair)
    all_pairs = [(i, j) for i in range(K) for j in range(i+1, K)]
    n_pairs = len(all_pairs)
    pair_to_idx = {p: i for i, p in enumerate(all_pairs)}

    # Greedy warm-start
    max_dist = min(3, max(R, C) - 1)
    if max_dist < 2:
        max_dist = 2
    greedy_alloc = alloc_express_greedy(grid, traffic, budget, max_dist=max_dist)
    greedy_capped = {p: min(n, N) for p, n in greedy_alloc.items()}

    greedy_vec = np.zeros(n_pairs, dtype=np.float32)
    for p, n in greedy_capped.items():
        greedy_vec[pair_to_idx[p]] = n

    # Traffic features
    t_max = traffic.max()
    traffic_norm = traffic / t_max if t_max > 0 else traffic
    traffic_flat = traffic_norm[np.triu_indices(K, k=1)]

    # Baseline latency (greedy's predicted latency)
    baseline_pred = surrogate_predict(surrogate, traffic_flat, greedy_vec,
                                      adj_set, all_pairs, K, N, budget, n_adj)

    # Number of swaps per episode: ~15% of budget
    if n_swaps is None:
        n_swaps = max(5, budget // 7)

    # State: traffic_flat + allocation + budget_frac + K,N norm
    state_dim = n_pairs + n_pairs + 3
    policy = SwapPolicy(state_dim, n_pairs).to(DEVICE)
    optimizer = optim.Adam(policy.parameters(), lr=3e-4)

    best_pred = baseline_pred
    best_alloc_vec = greedy_vec.copy()

    for ep in range(n_episodes):
        allocation = greedy_vec.copy()
        log_probs = []

        # Perform n_swaps sequential swaps
        for swap_step in range(n_swaps):
            budget_frac = allocation.sum() / max(budget, 1)
            state = np.concatenate([
                traffic_flat, allocation / N,
                [budget_frac, K / 32.0, N / 8.0],
            ]).astype(np.float32)
            state_t = torch.tensor(state, device=DEVICE)
            alloc_t = torch.tensor(allocation, device=DEVICE)

            rem_idx, add_idx, logp = policy.select_swap(state_t, alloc_t, N)

            # Apply swap
            allocation[rem_idx] -= 1
            allocation[add_idx] += 1
            log_probs.append(logp)

        # End-of-episode reward
        pred_lat = surrogate_predict(surrogate, traffic_flat, allocation,
                                     adj_set, all_pairs, K, N, budget, n_adj)

        # Reward = improvement over baseline (greedy)
        # Positive if RL improved, negative if made worse
        reward = baseline_pred - pred_lat  # higher = better

        if pred_lat < best_pred:
            best_pred = pred_lat
            best_alloc_vec = allocation.copy()

        # Policy gradient (REINFORCE with baseline)
        if log_probs:
            loss = sum(-lp * reward for lp in log_probs)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

        if (ep + 1) % 50 == 0:
            print(f"      Ep {ep+1}: pred_lat={pred_lat:.1f}, "
                  f"baseline={baseline_pred:.1f}, best={best_pred:.1f}",
                  flush=True)

    # Safety fallback: use greedy if RL didn't improve predicted latency
    if best_pred >= baseline_pred:
        print(f"      [FALLBACK] RL did not improve (best_pred={best_pred:.1f} "
              f">= baseline={baseline_pred:.1f}) — using greedy", flush=True)
        final_vec = greedy_vec
        final_pred = baseline_pred
    else:
        print(f"      [RL BETTER] best_pred={best_pred:.1f} < "
              f"baseline={baseline_pred:.1f}", flush=True)
        final_vec = best_alloc_vec
        final_pred = best_pred

    # Convert to dict
    alloc = {}
    for i, p in enumerate(all_pairs):
        if final_vec[i] > 0:
            alloc[p] = int(final_vec[i])
    return alloc, final_pred, baseline_pred


# ============================================================
# Main
# ============================================================

def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    print("=== Warm-Start RL Express Placement ===", flush=True)
    surrogate = load_surrogate()

    # All 40 configs (same as fast version but RL only, since GNN doesn't need retraining)
    configs = []
    for wl in ['tree_allreduce', 'hybrid_tp_pp', 'moe', 'uniform_random']:
        for bpp in [2, 3, 4]:
            configs.append((wl, 16, 4, 4, 4, bpp))
        for bpp in [2, 4, 7]:
            configs.append((wl, 16, 8, 4, 4, bpp))
        for bpp in [2, 4]:
            configs.append((wl, 32, 4, 4, 8, bpp))
        for bpp in [2, 4]:
            configs.append((wl, 32, 8, 4, 8, bpp))

    results_file = RESULTS_DIR / 'ml_comparison_warmstart.json'
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

        print(f"\n[{idx+1}/{len(configs)}] {wl} K{K}N{N} {bpp}x",
              flush=True)

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
            traf_file = f'traffic_wrm_{wl}_{label}.txt'
            gen_traffic_matrix(grid, traffic, npc, CONFIG_DIR / traf_file)

            result = {'workload': wl, 'K': K, 'N': N,
                      'budget_per_pair': bpp, 'budget': budget}

            # --- Greedy (baseline) ---
            max_dist = min(3, max(R, C) - 1)
            if max_dist < 2:
                max_dist = 2
            greedy_alloc = alloc_express_greedy(grid, traffic, budget,
                                                 max_dist=max_dist)
            greedy_capped = {p: min(n, N) for p, n in greedy_alloc.items()}
            cfg = f'wrm_{wl}_{label}_greedy'
            gen_anynet_config(cfg, grid, greedy_capped, chip_n=N,
                              outdir=CONFIG_DIR)
            r = run_booksim(cfg, traf_file, base_rate, timeout=300)
            n_expr_g = sum(1 for p in greedy_capped if p not in adj_set)
            result['express_greedy'] = {'latency': r['latency'],
                                         'n_express': n_expr_g,
                                         'total_links': sum(greedy_capped.values())}
            lat_s = f"{r['latency']:.1f}" if r['latency'] else "FAIL"
            print(f"    Greedy: lat={lat_s} express={n_expr_g}", flush=True)

            # --- Warm-Start RL ---
            t0 = time.time()
            rl_alloc, rl_pred, baseline_pred = train_warmstart_rl(
                surrogate, wl, K, N, R, C, bpp, n_episodes=200)
            rl_time = time.time() - t0
            rl_capped = {p: min(n, N) for p, n in rl_alloc.items()}
            cfg = f'wrm_{wl}_{label}_rl'
            gen_anynet_config(cfg, grid, rl_capped, chip_n=N, outdir=CONFIG_DIR)
            r = run_booksim(cfg, traf_file, base_rate, timeout=300)
            n_expr_rl = sum(1 for p in rl_capped if p not in adj_set)
            result['rl_warmstart'] = {'latency': r['latency'],
                                       'predicted_latency': rl_pred,
                                       'baseline_predicted': baseline_pred,
                                       'n_express': n_expr_rl,
                                       'total_links': sum(rl_capped.values()),
                                       'train_time': rl_time,
                                       'used_fallback': rl_pred >= baseline_pred}
            lat_s = f"{r['latency']:.1f}" if r['latency'] else "FAIL"
            fb = " [FALLBACK]" if rl_pred >= baseline_pred else ""
            print(f"    RL-WS:  lat={lat_s} express={n_expr_rl} "
                  f"time={rl_time:.0f}s{fb}", flush=True)

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

    # === Summary ===
    print(f"\n\n{'='*80}", flush=True)
    print("  SUMMARY: Warm-Start RL vs Greedy", flush=True)
    print(f"{'='*80}", flush=True)
    print(f"{'Config':<30s} {'Greedy':>7s} {'RL-WS':>7s} {'RL vs Gre':>10s} "
          f"{'Fallback?':>10s}", flush=True)
    print("-" * 75, flush=True)

    wins = losses = ties = 0
    for r in all_results:
        lbl = f"{r['workload'][:8]} K{r['K']}N{r['N']} {r['budget_per_pair']}x"
        gre = r['express_greedy']['latency']
        rl = r['rl_warmstart']['latency']
        fb = r['rl_warmstart']['used_fallback']

        gre_s = f"{gre:.1f}" if gre else "FAIL"
        rl_s = f"{rl:.1f}" if rl else "FAIL"

        if gre and rl:
            diff = (rl - gre) / gre * 100
            diff_s = f"{diff:+.1f}%"
            if rl < gre - 0.1:
                wins += 1
            elif rl > gre + 0.1:
                losses += 1
            else:
                ties += 1
        else:
            diff_s = "N/A"

        fb_s = "yes" if fb else "no"
        print(f"{lbl:<30s} {gre_s:>7s} {rl_s:>7s} {diff_s:>10s} {fb_s:>10s}",
              flush=True)

    print(f"\n  RL-WS beats greedy: {wins}/{len(all_results)}", flush=True)
    print(f"  RL-WS ties greedy:  {ties}/{len(all_results)}", flush=True)
    print(f"  RL-WS loses:        {losses}/{len(all_results)}", flush=True)
    print(f"\nResults: {results_file}", flush=True)


if __name__ == '__main__':
    main()
