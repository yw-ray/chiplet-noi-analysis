"""
Additional Experiments for Reviewer Response
=============================================

Experiment A: Adaptive routing — phantom load under different routing algorithms
Experiment B: Real workload traffic patterns — LLM communication patterns
Experiment C: Differential bandwidth — express links with reduced BW

All address specific reviewer concerns.
"""

import math
import json
import numpy as np
from itertools import combinations
from pathlib import Path
from collections import defaultdict

import sys
sys.path.insert(0, str(Path(__file__).parent))
from noi_topology_synthesis import (
    ChipletGrid, compute_link_load,
    allocate_uniform, allocate_load_aware, allocate_minmax_optimal,
    evaluate_allocation,
)
from express_link_optimizer import (
    express_greedy, compute_load_with_express, compute_max_rho,
)

RESULTS_DIR = Path(__file__).parent / 'results' / 'additional'
FIGURES_DIR = Path(__file__).parent / 'paper' / 'figures'


# ============================================================
# Experiment A: Routing algorithm comparison
# ============================================================

def enumerate_minimal_paths(grid, src, dst):
    """Enumerate ALL minimal (shortest) Manhattan paths from src to dst."""
    rs, cs = grid.positions[src]
    rd, cd = grid.positions[dst]
    dr = rd - rs  # positive = down
    dc = cd - cs  # positive = right

    if dr == 0 and dc == 0:
        return [[src]]

    # Steps needed: |dr| vertical + |dc| horizontal
    v_step = 1 if dr > 0 else -1
    h_step = 1 if dc > 0 else -1
    n_v = abs(dr)
    n_h = abs(dc)

    # Generate all permutations of moves
    # 'V' = vertical step, 'H' = horizontal step
    # Total moves = n_v + n_h, choose n_v positions for vertical
    from itertools import combinations as comb
    total_steps = n_v + n_h
    paths = []

    for v_positions in comb(range(total_steps), n_v):
        v_set = set(v_positions)
        path = [src]
        r, c = rs, cs
        for step_idx in range(total_steps):
            if step_idx in v_set:
                r += v_step
            else:
                c += h_step
            path.append(r * grid.cols + c)
        paths.append(path)

    return paths


def compute_load_xy(grid, traffic):
    """Standard XY (X-first) routing load."""
    return compute_link_load(grid, traffic)


def compute_load_yx(grid, traffic):
    """YX (Y-first) routing load."""
    K = grid.K
    load = np.zeros((K, K))

    for i in range(K):
        for j in range(i + 1, K):
            if traffic[i][j] <= 0 and traffic[j][i] <= 0:
                continue
            total_traffic = traffic[i][j] + traffic[j][i]

            # YX routing: move Y (vertical) first, then X (horizontal)
            ri, ci = grid.positions[i]
            rj, cj = grid.positions[j]
            path = [i]
            r, c = ri, ci
            # Vertical first
            while r != rj:
                r += 1 if rj > r else -1
                path.append(r * grid.cols + c)
            # Then horizontal
            while c != cj:
                c += 1 if cj > c else -1
                path.append(r * grid.cols + c)

            for h in range(len(path) - 1):
                a, b = min(path[h], path[h + 1]), max(path[h], path[h + 1])
                load[a][b] += total_traffic

    return load


def compute_load_ecmp(grid, traffic):
    """
    Equal-Cost Multi-Path (ECMP) / randomized minimal routing.
    Traffic is split equally across ALL minimal paths.
    """
    K = grid.K
    load = np.zeros((K, K))

    for i in range(K):
        for j in range(i + 1, K):
            if traffic[i][j] <= 0 and traffic[j][i] <= 0:
                continue
            total_traffic = traffic[i][j] + traffic[j][i]

            paths = enumerate_minimal_paths(grid, i, j)
            n_paths = len(paths)
            per_path_traffic = total_traffic / n_paths

            for path in paths:
                for h in range(len(path) - 1):
                    a, b = min(path[h], path[h + 1]), max(path[h], path[h + 1])
                    load[a][b] += per_path_traffic

    return load


def compute_load_valiant(grid, traffic, seed=42):
    """
    Valiant routing: each flow (i→j) routes through a random intermediate
    node k: i→k (minimal) then k→j (minimal). Trades latency for load balance.
    """
    K = grid.K
    rng = np.random.RandomState(seed)
    load = np.zeros((K, K))

    for i in range(K):
        for j in range(i + 1, K):
            if traffic[i][j] <= 0 and traffic[j][i] <= 0:
                continue
            total_traffic = traffic[i][j] + traffic[j][i]

            # Choose random intermediate (average over K intermediates)
            per_k_traffic = total_traffic / K
            for k in range(K):
                # i → k (XY routing)
                if k != i:
                    path_ik = grid.shortest_path(i, k)
                    for h in range(len(path_ik) - 1):
                        a, b = min(path_ik[h], path_ik[h + 1]), max(path_ik[h], path_ik[h + 1])
                        load[a][b] += per_k_traffic
                # k → j (XY routing)
                if k != j:
                    path_kj = grid.shortest_path(k, j)
                    for h in range(len(path_kj) - 1):
                        a, b = min(path_kj[h], path_kj[h + 1]), max(path_kj[h], path_kj[h + 1])
                        load[a][b] += per_k_traffic

    return load


def experiment_a_routing():
    """Compare phantom load across routing algorithms."""
    print("=" * 60)
    print("  Experiment A: Routing Algorithm Comparison")
    print("=" * 60)

    results = []
    grid_configs = [(2, 4, '2x4'), (4, 4, '4x4'), (4, 8, '4x8')]

    for R, C, label in grid_configs:
        K = R * C
        grid = ChipletGrid(R, C)
        adj_pairs = grid.get_adj_pairs()

        # Use uniform random traffic
        rng = np.random.RandomState(42)
        traffic = rng.rand(K, K) * 100
        np.fill_diagonal(traffic, 0)
        traffic = (traffic + traffic.T) / 2

        routing_algorithms = {
            'XY': lambda g, t: compute_load_xy(g, t),
            'YX': lambda g, t: compute_load_yx(g, t),
            'ECMP': lambda g, t: compute_load_ecmp(g, t),
            'Valiant': lambda g, t: compute_load_valiant(g, t),
        }

        print(f"\n  {label} (K={K}):")
        print(f"  {'Routing':<12} {'Max Load':>10} {'Min Load':>10} {'Avg Load':>10} "
              f"{'Imbalance':>10} {'Max Amp':>10}")

        grid_result = {'grid': label, 'K': K, 'routing': {}}

        for rname, rfn in routing_algorithms.items():
            print(f"    Computing {rname}...", end=' ', flush=True)
            load = rfn(grid, traffic)

            loads = []
            amps = []
            for (a, b) in adj_pairs:
                ld = load[a][b]
                direct = traffic[a][b] + traffic[b][a]
                loads.append(ld)
                if direct > 0:
                    amps.append(ld / direct)

            max_load = max(loads)
            min_load = min(loads) if min(loads) > 0 else 1e-6
            avg_load = np.mean(loads)
            imbalance = max_load / min_load
            max_amp = max(amps) if amps else 0

            print(f"  {rname:<12} {max_load:>10.1f} {min_load:>10.1f} "
                  f"{avg_load:>10.1f} {imbalance:>10.1f} {max_amp:>10.1f}")

            grid_result['routing'][rname] = {
                'max_load': float(max_load),
                'min_load': float(min_load),
                'avg_load': float(avg_load),
                'imbalance': float(imbalance),
                'max_amp': float(max_amp),
                'load_std': float(np.std(loads)),
                'loads': [float(l) for l in loads],
            }

        results.append(grid_result)

    return results


# ============================================================
# Experiment B: Real workload traffic patterns
# ============================================================

def traffic_ring_allreduce(K, grid, data_size=1000.0):
    """
    Ring all-reduce: each chiplet sends to next neighbor in a ring.
    2*(K-1) steps, each sending data_size/K.
    Traffic pattern: chiplet i → chiplet (i+1) % K.
    """
    T = np.zeros((K, K))
    chunk = data_size / K
    # Ring order: row-major traversal
    for i in range(K):
        j = (i + 1) % K
        T[i][j] = chunk * (K - 1)  # total data through each link in ring
        T[j][i] = chunk * (K - 1)
    return T


def traffic_tree_allreduce(K, grid, data_size=1000.0):
    """
    Tree (recursive halving-doubling) all-reduce.
    At each level, pairs exchange data. Creates hierarchical traffic.
    """
    T = np.zeros((K, K))
    levels = int(math.ceil(math.log2(K)))
    for level in range(levels):
        stride = 2 ** level
        chunk = data_size / (2 ** (level + 1))
        for i in range(K):
            partner = i ^ stride  # XOR partner
            if partner < K:
                T[i][partner] += chunk
                T[partner][i] += chunk
    return T


def traffic_pipeline_parallel(K, grid, data_size=1000.0, n_stages=None):
    """
    Pipeline parallelism: sequential stages, traffic flows linearly.
    Stage i sends activations to stage i+1.
    """
    if n_stages is None:
        n_stages = K
    T = np.zeros((K, K))
    # Map stages to chiplets in row-major order
    for stage in range(min(n_stages - 1, K - 1)):
        src = stage
        dst = stage + 1
        if dst < K:
            T[src][dst] = data_size
            T[dst][src] = data_size * 0.1  # gradients (smaller)
    return T


def traffic_tensor_parallel(K, grid, data_size=1000.0, group_size=4):
    """
    Tensor parallelism: all-to-all within groups.
    K chiplets divided into groups of group_size.
    Heavy traffic within group, minimal between groups.
    """
    T = np.zeros((K, K))
    n_groups = max(1, K // group_size)
    for g in range(n_groups):
        start = g * group_size
        end = min(start + group_size, K)
        for i in range(start, end):
            for j in range(start, end):
                if i != j:
                    T[i][j] = data_size / group_size
    # Small cross-group traffic (pipeline between groups)
    for g in range(n_groups - 1):
        src = (g + 1) * group_size - 1
        dst = (g + 1) * group_size
        if dst < K:
            T[src][dst] = data_size * 0.1
            T[dst][src] = data_size * 0.1
    return T


def traffic_moe_expert_parallel(K, grid, data_size=1000.0, top_k=2):
    """
    Mixture-of-Experts: each chiplet (token) sends to top_k experts.
    Creates sparse all-to-all pattern. Each chiplet hosts one expert.
    """
    rng = np.random.RandomState(42)
    T = np.zeros((K, K))
    # Each chiplet sends tokens to top_k random experts
    for i in range(K):
        experts = rng.choice([j for j in range(K) if j != i],
                             size=min(top_k, K - 1), replace=False)
        for e in experts:
            T[i][e] = data_size / top_k
            T[e][i] = data_size / top_k  # return results
    return T


def traffic_hybrid_tp_pp(K, grid, data_size=1000.0, tp_group=4):
    """
    Hybrid Tensor + Pipeline parallelism (most common in practice).
    TP groups of tp_group chiplets, PP stages across groups.
    """
    T = np.zeros((K, K))
    n_groups = max(1, K // tp_group)

    # TP: all-to-all within each group (heavy)
    for g in range(n_groups):
        start = g * tp_group
        end = min(start + tp_group, K)
        for i in range(start, end):
            for j in range(start, end):
                if i != j:
                    T[i][j] += data_size / tp_group

    # PP: forward/backward between consecutive groups (moderate)
    for g in range(n_groups - 1):
        # Last chiplet of group g → first chiplet of group g+1
        src = min((g + 1) * tp_group - 1, K - 1)
        dst = min((g + 1) * tp_group, K - 1)
        if src != dst:
            T[src][dst] += data_size * 0.3  # activations
            T[dst][src] += data_size * 0.3  # gradients

    return T


def experiment_b_workloads():
    """Evaluate phantom load for real workload traffic patterns."""
    print("\n" + "=" * 60)
    print("  Experiment B: Real Workload Traffic Patterns")
    print("=" * 60)

    results = []
    grid_configs = [(2, 4, '2x4'), (4, 4, '4x4'), (4, 8, '4x8')]

    workloads = {
        'Ring All-Reduce': traffic_ring_allreduce,
        'Tree All-Reduce': traffic_tree_allreduce,
        'Pipeline Parallel': traffic_pipeline_parallel,
        'Tensor Parallel': lambda K, g: traffic_tensor_parallel(K, g, group_size=min(4, K)),
        'MoE Expert': traffic_moe_expert_parallel,
        'Hybrid TP+PP': lambda K, g: traffic_hybrid_tp_pp(K, g, tp_group=min(4, K)),
    }

    for R, C, label in grid_configs:
        K = R * C
        grid = ChipletGrid(R, C)
        adj_pairs = grid.get_adj_pairs()

        print(f"\n  {label} (K={K}):")
        print(f"  {'Workload':<20} {'Max Load':>10} {'Avg Load':>10} "
              f"{'Imbalance':>10} {'Max Amp':>10} {'Phantom%':>10}")

        for wl_name, wl_fn in workloads.items():
            traffic = wl_fn(K, grid)
            load = compute_load_xy(grid, traffic)

            loads = []
            amps = []
            phantom_count = 0

            for (a, b) in adj_pairs:
                ld = load[a][b]
                direct = traffic[a][b] + traffic[b][a]
                loads.append(ld)
                if ld > 0 and direct == 0:
                    phantom_count += 1
                if direct > 0:
                    amps.append(ld / direct)

            max_load = max(loads) if loads else 0
            min_load_nz = min(l for l in loads if l > 0) if any(l > 0 for l in loads) else 1
            avg_load = np.mean(loads)
            imbalance = max_load / min_load_nz if min_load_nz > 0 else 0
            max_amp = max(amps) if amps else 0
            phantom_frac = phantom_count / len(adj_pairs)

            print(f"  {wl_name:<20} {max_load:>10.1f} {avg_load:>10.1f} "
                  f"{imbalance:>10.1f} {max_amp:>10.1f} {phantom_frac:>9.0%}")

            results.append({
                'grid': label, 'K': K,
                'workload': wl_name,
                'max_load': float(max_load),
                'avg_load': float(avg_load),
                'load_imbalance': float(imbalance),
                'max_amplification': float(max_amp),
                'phantom_fraction': float(phantom_frac),
                'n_active_links': sum(1 for l in loads if l > 0),
                'n_total_links': len(adj_pairs),
            })

    return results


# ============================================================
# Experiment C: Differential bandwidth model
# ============================================================

def express_greedy_diff_bw(grid, traffic, total_budget,
                            bw_adjacent=32, bw_decay=0.75,
                            max_express_distance=3):
    """
    Express greedy with distance-dependent bandwidth.
    BW = bw_adjacent * bw_decay^(d-1) for express link at distance d.
    """
    K = grid.K
    pairs_adj = grid.get_adj_pairs()
    pairs_express = []
    for i in range(K):
        for j in range(i + 1, K):
            if (i, j) not in set(pairs_adj):
                hops = grid.get_hops(i, j)
                if hops <= max_express_distance:
                    pairs_express.append((i, j))

    # BW per link based on distance
    def get_bw(pair):
        d = grid.get_hops(pair[0], pair[1])
        if d <= 1:
            return bw_adjacent
        return bw_adjacent * (bw_decay ** (d - 1))

    # Start: 1 link per adjacent pair
    alloc = {p: 1 for p in pairs_adj}
    remaining = total_budget - len(pairs_adj)
    if remaining <= 0:
        return alloc

    link_set = set(alloc.keys())
    load = compute_load_with_express(grid, traffic, link_set)

    def compute_max_rho_diffbw(load, alloc):
        max_rho = 0
        for pair, ld in load.items():
            n = alloc.get(pair, 0)
            if n > 0:
                bw = n * get_bw(pair)
                rho = ld / bw
                max_rho = max(max_rho, rho)
            elif ld > 0:
                max_rho = max(max_rho, 999)
        return max_rho

    current_rho = compute_max_rho_diffbw(load, alloc)

    for step in range(remaining):
        best_pair = None
        best_rho = current_rho
        best_is_new = False

        # Try adding to existing pairs
        for p in list(alloc.keys()):
            test_alloc = dict(alloc)
            test_alloc[p] += 1
            test_load = compute_load_with_express(grid, traffic, set(test_alloc.keys()))
            rho = compute_max_rho_diffbw(test_load, test_alloc)
            if rho < best_rho:
                best_rho = rho
                best_pair = p
                best_is_new = False

        # Try new express links
        for p in pairs_express:
            if p in alloc:
                test_alloc = dict(alloc)
                test_alloc[p] += 1
            else:
                test_alloc = dict(alloc)
                test_alloc[p] = 1
            test_load = compute_load_with_express(grid, traffic, set(test_alloc.keys()))
            rho = compute_max_rho_diffbw(test_load, test_alloc)
            if rho < best_rho:
                best_rho = rho
                best_pair = p
                best_is_new = (p not in alloc)

        if best_pair is None:
            break

        if best_is_new:
            alloc[best_pair] = 1
        else:
            alloc[best_pair] += 1
        link_set = set(alloc.keys())
        load = compute_load_with_express(grid, traffic, link_set)
        current_rho = best_rho

    return alloc


def experiment_c_diff_bw():
    """Compare uniform BW vs differential BW for express links."""
    print("\n" + "=" * 60)
    print("  Experiment C: Differential Bandwidth Model")
    print("=" * 60)

    results = []
    grid_configs = [(2, 4, '2x4'), (4, 4, '4x4')]

    bw_models = {
        'Uniform (32 GB/s)': {'bw_adjacent': 32, 'bw_decay': 1.0},
        '75% decay': {'bw_adjacent': 32, 'bw_decay': 0.75},
        '50% decay': {'bw_adjacent': 32, 'bw_decay': 0.50},
    }

    for R, C, label in grid_configs:
        K = R * C
        grid = ChipletGrid(R, C)
        adj_pairs = grid.get_adj_pairs()
        n_adj = len(adj_pairs)

        rng = np.random.RandomState(42)
        traffic = rng.rand(K, K) * 100
        np.fill_diagonal(traffic, 0)
        traffic = (traffic + traffic.T) / 2

        print(f"\n  {label} (K={K}):")

        for budget_mult in [3, 4, 6]:
            budget = n_adj * budget_mult
            print(f"\n    Budget {budget_mult}x ({budget} links):")

            # Baseline: adjacent uniform
            alloc = allocate_uniform(grid, budget)
            ev = evaluate_allocation(grid, traffic, alloc)
            print(f"      {'Adj Uniform':<25} max_ρ={ev['max_rho']:>7.2f}")
            baseline_rho = ev['max_rho']

            for bw_name, bw_params in bw_models.items():
                print(f"      Computing express with {bw_name}...", flush=True)

                bw_adj = bw_params['bw_adjacent']
                bw_decay = bw_params['bw_decay']

                if bw_decay == 1.0:
                    # Use standard express_greedy
                    alloc = express_greedy(grid, traffic, budget,
                                           max_express_distance=3)
                    link_set = set(alloc.keys())
                    load = compute_load_with_express(grid, traffic, link_set)
                    max_rho = compute_max_rho(load, alloc, bw_per_link=bw_adj)
                else:
                    alloc = express_greedy_diff_bw(
                        grid, traffic, budget,
                        bw_adjacent=bw_adj, bw_decay=bw_decay,
                        max_express_distance=3)
                    link_set = set(alloc.keys())
                    load = compute_load_with_express(grid, traffic, link_set)
                    # Compute max_rho with differential BW
                    max_rho = 0
                    for pair, ld in load.items():
                        n = alloc.get(pair, 0)
                        if n > 0:
                            d = grid.get_hops(pair[0], pair[1])
                            bw = bw_adj * (bw_decay ** max(0, d - 1))
                            rho = ld / (n * bw)
                            max_rho = max(max_rho, rho)

                n_express = sum(1 for p in alloc if p not in set(adj_pairs))
                improvement = baseline_rho / max_rho if max_rho > 0 else 0

                print(f"      Express {bw_name:<25} max_ρ={max_rho:>7.2f}  "
                      f"({n_express} express, {improvement:.1f}x vs uniform)")

                results.append({
                    'grid': label, 'K': K,
                    'budget_mult': budget_mult,
                    'bw_model': bw_name,
                    'bw_decay': bw_decay,
                    'max_rho': float(max_rho),
                    'baseline_rho': float(baseline_rho),
                    'improvement': float(improvement),
                    'n_express': n_express,
                })

    return results


# ============================================================
# Figure generation
# ============================================================

def generate_figures(routing_results, workload_results, bw_results):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        'font.size': 9, 'font.family': 'serif',
        'axes.labelsize': 10, 'axes.titlesize': 10,
        'legend.fontsize': 8, 'xtick.labelsize': 8, 'ytick.labelsize': 8,
        'figure.dpi': 150,
    })

    # ---- Fig A: Routing algorithm comparison ----
    fig, axes = plt.subplots(1, 3, figsize=(7.16, 2.4))
    routing_names = ['XY', 'YX', 'ECMP', 'Valiant']
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']

    for idx, gr in enumerate(routing_results):
        ax = axes[idx]
        imbalances = [gr['routing'][rn]['imbalance'] for rn in routing_names]
        bars = ax.bar(range(len(routing_names)), imbalances, color=colors,
                      edgecolor='white', linewidth=0.5)
        ax.set_xticks(range(len(routing_names)))
        ax.set_xticklabels(routing_names, fontsize=8)
        ax.set_ylabel('Load imbalance (max/min)')
        ax.set_title(f'({chr(97+idx)}) {gr["grid"]} (K={gr["K"]})')
        ax.grid(True, alpha=0.3, axis='y')
        for bar, val in zip(bars, imbalances):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                    f'{val:.1f}', ha='center', va='bottom', fontsize=7)

    plt.tight_layout()
    fig.savefig(FIGURES_DIR / 'fig_routing_comparison.pdf', bbox_inches='tight')
    fig.savefig(FIGURES_DIR / 'fig_routing_comparison.png', bbox_inches='tight')
    plt.close()
    print("  [OK] fig_routing_comparison.pdf")

    # ---- Fig B: Workload traffic patterns ----
    fig, axes = plt.subplots(1, 3, figsize=(7.16, 2.6))

    grid_labels = ['2x4', '4x4', '4x8']
    wl_order = ['Ring All-Reduce', 'Tree All-Reduce', 'Pipeline Parallel',
                'Tensor Parallel', 'MoE Expert', 'Hybrid TP+PP']
    wl_short = ['Ring\nAR', 'Tree\nAR', 'Pipe\nPar', 'Tensor\nPar', 'MoE', 'Hybrid\nTP+PP']
    wl_colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']

    for idx, gl in enumerate(grid_labels):
        ax = axes[idx]
        wl_data = [r for r in workload_results if r['grid'] == gl]
        amps = []
        for wl_name in wl_order:
            entry = next((r for r in wl_data if r['workload'] == wl_name), None)
            amps.append(entry['max_amplification'] if entry else 0)

        bars = ax.bar(range(len(wl_order)), amps, color=wl_colors,
                      edgecolor='white', linewidth=0.5)
        ax.set_xticks(range(len(wl_order)))
        ax.set_xticklabels(wl_short, fontsize=6)
        ax.set_ylabel('Max amplification')
        K = wl_data[0]['K'] if wl_data else 0
        ax.set_title(f'({chr(97+idx)}) {gl} (K={K})')
        ax.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    fig.savefig(FIGURES_DIR / 'fig_workload_patterns.pdf', bbox_inches='tight')
    fig.savefig(FIGURES_DIR / 'fig_workload_patterns.png', bbox_inches='tight')
    plt.close()
    print("  [OK] fig_workload_patterns.pdf")

    # ---- Fig C: Differential bandwidth ----
    fig, axes = plt.subplots(1, 2, figsize=(7.16, 2.5))

    bw_labels = ['Uniform (32 GB/s)', '75% decay', '50% decay']
    bw_colors = ['#2ca02c', '#ff7f0e', '#d62728']

    for idx, gl in enumerate(['2x4', '4x4']):
        ax = axes[idx]
        grid_data = [r for r in bw_results if r['grid'] == gl]

        for bw_idx, bw_name in enumerate(bw_labels):
            entries = sorted([r for r in grid_data if r['bw_model'] == bw_name],
                             key=lambda x: x['budget_mult'])
            if entries:
                mults = [e['budget_mult'] for e in entries]
                improvements = [e['improvement'] for e in entries]
                ax.plot(mults, improvements, 'o-', color=bw_colors[bw_idx],
                        label=f'Express ({bw_name})', markersize=5, linewidth=1.5)

        ax.axhline(y=1.0, color='gray', linestyle='--', linewidth=0.8, label='Adj. Uniform')
        K = grid_data[0]['K'] if grid_data else 0
        ax.set_xlabel('Budget multiplier (×adj pairs)')
        ax.set_ylabel('Improvement vs. Uniform')
        ax.set_title(f'({chr(97+idx)}) {gl} (K={K})')
        ax.legend(fontsize=6, loc='upper left')
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    fig.savefig(FIGURES_DIR / 'fig_diff_bandwidth.pdf', bbox_inches='tight')
    fig.savefig(FIGURES_DIR / 'fig_diff_bandwidth.png', bbox_inches='tight')
    plt.close()
    print("  [OK] fig_diff_bandwidth.pdf")


# ============================================================
# Main
# ============================================================

def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    # Experiment A
    routing_results = experiment_a_routing()
    with open(RESULTS_DIR / 'routing_comparison.json', 'w') as f:
        json.dump(routing_results, f, indent=2)

    # Experiment B
    workload_results = experiment_b_workloads()
    with open(RESULTS_DIR / 'workload_patterns.json', 'w') as f:
        json.dump(workload_results, f, indent=2)

    # Experiment C
    bw_results = experiment_c_diff_bw()
    with open(RESULTS_DIR / 'diff_bandwidth.json', 'w') as f:
        json.dump(bw_results, f, indent=2)

    # Generate figures
    print("\n" + "=" * 60)
    print("  Generating figures...")
    print("=" * 60)
    generate_figures(routing_results, workload_results, bw_results)

    print(f"\n  Results: {RESULTS_DIR}")
    print(f"  Figures: {FIGURES_DIR}")


if __name__ == '__main__':
    main()
