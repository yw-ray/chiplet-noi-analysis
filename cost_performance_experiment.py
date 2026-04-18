"""
Cost-Performance Pareto Experiment
====================================

Compare adjacent brute-force vs express links across internal mesh sizes.
Key claim: express links achieve same performance at lower link cost.

Internal mesh sizes: 2×2, 4×4, 8×8
Grid: K=16 (4×4 chiplet grid)
"""

import math
import json
import time
import subprocess
import numpy as np
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))
from noi_topology_synthesis import ChipletGrid

BOOKSIM = str(Path(__file__).parent / 'booksim2' / 'src' / 'booksim')
CONFIG_DIR = Path(__file__).parent / 'booksim_configs'
RESULTS_DIR = Path(__file__).parent / 'results' / 'cost_perf'
FIGURES_DIR = Path(__file__).parent / 'paper' / 'figures'


# ============================================================
# Config generation for arbitrary internal mesh
# ============================================================

def gen_anynet_config(name, grid, alloc, chip_n, outdir='.'):
    """
    Generate BookSim anynet for K chiplets with chip_n × chip_n internal mesh.
    alloc: dict {(ci, cj): n_links}
    Returns: number of inter-chiplet links placed.
    """
    K = grid.K
    npc = chip_n * chip_n
    outdir = Path(outdir)

    lines = []
    # Intra-chiplet mesh
    for cid in range(K):
        base = cid * npc
        for r in range(chip_n):
            for c in range(chip_n):
                rid = base + r * chip_n + c
                parts = [f"router {rid}", f"node {rid}"]
                if c + 1 < chip_n:
                    parts.append(f"router {base + r * chip_n + c + 1} 1")
                if r + 1 < chip_n:
                    parts.append(f"router {base + (r + 1) * chip_n + c} 1")
                lines.append(" ".join(parts))

    # Inter-chiplet links
    inter_count = 0
    for (ci, cj), n_links in alloc.items():
        if n_links <= 0:
            continue

        ri, cip = grid.positions[ci]
        rj, cjp = grid.positions[cj]
        ci_base = ci * npc
        cj_base = cj * npc
        hops = grid.get_hops(ci, cj)
        latency = max(2, hops * 2)

        # Determine border routers based on relative position
        dr = rj - ri
        dc = cjp - cip

        if abs(dc) > 0 and abs(dc) >= abs(dr):
            # Primarily horizontal
            if dc > 0:  # cj is right
                ci_border = [ci_base + r * chip_n + (chip_n - 1) for r in range(chip_n)]
                cj_border = [cj_base + r * chip_n for r in range(chip_n)]
            else:  # cj is left
                ci_border = [ci_base + r * chip_n for r in range(chip_n)]
                cj_border = [cj_base + r * chip_n + (chip_n - 1) for r in range(chip_n)]
        else:
            # Primarily vertical
            if dr > 0:  # cj is below
                ci_border = [ci_base + (chip_n - 1) * chip_n + c for c in range(chip_n)]
                cj_border = [cj_base + c for c in range(chip_n)]
            else:  # cj is above
                ci_border = [ci_base + c for c in range(chip_n)]
                cj_border = [cj_base + (chip_n - 1) * chip_n + c for c in range(chip_n)]

        n = min(n_links, len(ci_border), len(cj_border))
        for k in range(n):
            lines.append(f"router {ci_border[k]} router {cj_border[k]} {latency}")
            inter_count += 1

    with open(outdir / f"{name}.anynet", "w") as f:
        f.write("\n".join(lines) + "\n")

    with open(outdir / f"{name}.cfg", "w") as f:
        f.write(f"""topology = anynet;
network_file = {name}.anynet;
routing_function = min;
num_vcs = 8;
vc_buf_size = 16;
wait_for_tail_credit = 0;
vc_allocator = separable_input_first;
sw_allocator = separable_input_first;
alloc_iters = 3;
credit_delay = 1;
routing_delay = 0;
vc_alloc_delay = 1;
sw_alloc_delay = 1;
input_speedup = 2;
output_speedup = 1;
internal_speedup = 2.0;
traffic = uniform;
packet_size = 8;
sim_type = latency;
sample_period = 10000;
warmup_periods = 3;
max_samples = 10;
deadlock_warn_timeout = 51200;
injection_rate = 0.02;
""")

    return inter_count


def gen_traffic_matrix(grid, traffic, npc, filepath):
    """Generate traffic matrix file for BookSim."""
    K = grid.K
    total_nodes = K * npc
    node_traffic = np.zeros((total_nodes, total_nodes), dtype=int)

    # Normalize chiplet-level traffic to BookSim weights (1-100 range),
    # preserving relative magnitudes regardless of npc.
    max_t = max(traffic[ci][cj]
                for ci in range(K) for cj in range(K)
                if ci != cj and traffic[ci][cj] > 0) if np.any(traffic > 0) else 1.0
    for ci in range(K):
        for cj in range(K):
            if ci == cj or traffic[ci][cj] <= 0:
                continue
            weight = max(1, round(traffic[ci][cj] / max_t * 100))
            for ni in range(npc):
                for nj in range(npc):
                    src = ci * npc + ni
                    dst = cj * npc + nj
                    if src != dst:
                        node_traffic[src][dst] += weight

    # Intra-chiplet background
    for ci in range(K):
        for ni in range(npc):
            for nj in range(npc):
                src, dst = ci * npc + ni, ci * npc + nj
                if src != dst:
                    node_traffic[src][dst] += 1

    with open(filepath, 'w') as f:
        for i in range(total_nodes):
            f.write(' '.join(str(node_traffic[i][j]) for j in range(total_nodes)) + '\n')


# ============================================================
# Allocation strategies
# ============================================================

def alloc_adjacent_uniform(grid, budget):
    """Uniform allocation across adjacent pairs."""
    pairs = grid.get_adj_pairs()
    per = max(1, budget // len(pairs))
    alloc = {}
    remaining = budget
    for p in pairs:
        n = min(per, remaining)
        alloc[p] = n
        remaining -= n
    for p in pairs:
        if remaining <= 0:
            break
        alloc[p] += 1
        remaining -= 1
    return alloc


def alloc_express_greedy(grid, traffic, budget, max_dist=3, bw_per_link=32,
                         initial_alloc=None):
    """Greedy express link placement with re-routing.

    If initial_alloc is provided, start from that allocation and only ADD
    links up to budget. This guarantees monotonicity across budget levels.
    """
    import heapq

    K = grid.K
    pairs_adj = grid.get_adj_pairs()
    pairs_express = []
    for i in range(K):
        for j in range(i + 1, K):
            if (i, j) not in set(pairs_adj):
                hops = grid.get_hops(i, j)
                if hops <= max_dist:
                    pairs_express.append((i, j))

    def compute_load(link_set):
        adj = {i: {} for i in range(K)}
        for (a, b) in link_set:
            w = max(1, grid.get_hops(a, b))
            adj[a][b] = w
            adj[b][a] = w

        def shortest_path(src, dst):
            dist = {i: float('inf') for i in range(K)}
            prev = {i: None for i in range(K)}
            dist[src] = 0
            pq = [(0, src)]
            while pq:
                d, u = heapq.heappop(pq)
                if d > dist[u]:
                    continue
                if u == dst:
                    break
                for v, w in adj[u].items():
                    nd = d + w
                    if nd < dist[v]:
                        dist[v] = nd
                        prev[v] = u
                        heapq.heappush(pq, (nd, v))
            path = []
            u = dst
            while u is not None:
                path.append(u)
                u = prev[u]
            path.reverse()
            return path if path and path[0] == src else []

        load = {}
        for (a, b) in link_set:
            key = (min(a, b), max(a, b))
            load[key] = 0.0
        for i in range(K):
            for j in range(i + 1, K):
                if traffic[i][j] <= 0:
                    continue
                path = shortest_path(i, j)
                if len(path) < 2:
                    continue
                for h in range(len(path) - 1):
                    a, b = min(path[h], path[h + 1]), max(path[h], path[h + 1])
                    if (a, b) in load:
                        load[(a, b)] += traffic[i][j]
        return load

    def max_rho(load, alloc):
        mr = 0
        for pair, ld in load.items():
            n = alloc.get(pair, 0)
            if n > 0:
                mr = max(mr, ld / (n * bw_per_link))
            elif ld > 0:
                mr = max(mr, 999)
        return mr

    # Start from initial_alloc (warm start) or fresh adj baseline
    if initial_alloc is not None:
        alloc = dict(initial_alloc)
        remaining = budget - sum(alloc.values())
    else:
        alloc = {p: 1 for p in pairs_adj}
        remaining = budget - len(pairs_adj)
    if remaining <= 0:
        return alloc

    link_set = set(alloc.keys())
    load = compute_load(link_set)
    current_rho = max_rho(load, alloc)

    for step in range(remaining):
        best_pair = None
        best_rho = current_rho
        best_is_new = False

        for p in list(alloc.keys()):
            test_alloc = dict(alloc)
            test_alloc[p] += 1
            test_load = compute_load(set(test_alloc.keys()))
            rho = max_rho(test_load, test_alloc)
            if rho < best_rho:
                best_rho = rho
                best_pair = p
                best_is_new = False

        for p in pairs_express:
            test_alloc = dict(alloc)
            if p in alloc:
                test_alloc[p] += 1
            else:
                test_alloc[p] = 1
            test_load = compute_load(set(test_alloc.keys()))
            rho = max_rho(test_load, test_alloc)
            if rho < best_rho:
                best_rho = rho
                best_pair = p
                best_is_new = (p not in alloc)

        if best_pair is None:
            # Greedy plateau: no single addition strictly improves max_rho.
            # Fallback: traffic-proportional allocation of remaining budget.
            links_left = remaining - step
            candidates = {}
            for p in alloc:
                t = traffic[min(p[0], p[1])][max(p[0], p[1])]
                if t > 0:
                    candidates[p] = t
            for p in pairs_express:
                if p not in candidates:
                    t = traffic[p[0]][p[1]]
                    if t > 0:
                        candidates[p] = t
            if candidates:
                ranked = sorted(candidates.items(), key=lambda x: -x[1])
                total_t = sum(t for _, t in ranked)
                for p, t in ranked:
                    if links_left <= 0:
                        break
                    share = max(1, round(links_left * t / total_t))
                    total_t -= t
                    if p not in alloc:
                        alloc[p] = share
                    else:
                        alloc[p] += share
                    links_left -= share
            # If budget still remains (sparse traffic), distribute to adj
            if links_left > 0:
                adj_list = list(pairs_adj)
                idx = 0
                while links_left > 0:
                    alloc[adj_list[idx % len(adj_list)]] += 1
                    links_left -= 1
                    idx += 1
            break

        if best_is_new:
            alloc[best_pair] = 1
        else:
            alloc[best_pair] += 1
        link_set = set(alloc.keys())
        load = compute_load(link_set)
        current_rho = best_rho

    return alloc


# ============================================================
# BookSim runner
# ============================================================

def run_booksim(cfg_name, traffic_file, rate, timeout=300):
    """Run BookSim and parse results."""
    cmd = [BOOKSIM, f'{cfg_name}.cfg',
           f'injection_rate={rate}',
           f'traffic=matrix({traffic_file})']
    try:
        result = subprocess.run(cmd, capture_output=True, text=True,
                                timeout=timeout, cwd=str(CONFIG_DIR))
        lat, tput = None, None
        for line in result.stdout.split('\n'):
            if 'Packet latency average' in line:
                parts = line.split()
                for i, p in enumerate(parts):
                    if p == '=':
                        lat = float(parts[i + 1])
            if 'Accepted packet rate average' in line:
                parts = line.split()
                for i, p in enumerate(parts):
                    if p == '=':
                        tput = float(parts[i + 1])
        return {'latency': lat, 'throughput': tput, 'success': lat is not None}
    except (subprocess.TimeoutExpired, Exception):
        return {'latency': None, 'throughput': None, 'success': False}


# ============================================================
# Main experiment
# ============================================================

def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    K = 16
    R, C = 4, 4
    grid = ChipletGrid(R, C)
    adj_pairs = grid.get_adj_pairs()
    n_adj = len(adj_pairs)  # 24

    # Traffic matrix (uniform random, fixed seed)
    rng = np.random.RandomState(42)
    traffic = rng.rand(K, K) * 100
    np.fill_diagonal(traffic, 0)
    traffic = (traffic + traffic.T) / 2

    mesh_sizes = [2, 4, 8]
    # Base rates for N=2 (npc=4). Scale by 4/npc to keep total injection constant.
    base_rates = [0.005, 0.01, 0.015, 0.02]

    all_results = {}

    # First: timing test for 8×8
    print("=" * 60)
    print("  Timing test: 8×8 internal mesh")
    print("=" * 60)
    test_alloc = alloc_adjacent_uniform(grid, n_adj * 2)
    gen_anynet_config('timing_test', grid, test_alloc, chip_n=8, outdir=CONFIG_DIR)
    npc_8 = 64
    gen_traffic_matrix(grid, traffic, npc_8, CONFIG_DIR / 'traffic_timing_test.txt')
    t0 = time.time()
    r = run_booksim('timing_test', 'traffic_timing_test.txt', 0.005 * 4.0 / 64, timeout=300)
    t1 = time.time()
    print(f"  8×8 single run: {t1-t0:.1f}s, lat={r.get('latency')}")
    if t1 - t0 > 120:
        print("  WARNING: 8×8 too slow, will use reduced sweep")
        mesh_sizes = [2, 4]  # Drop 8×8

    for chip_n in mesh_sizes:
        npc = chip_n * chip_n
        mesh_label = f'{chip_n}x{chip_n}'
        max_links_per_pair = chip_n  # border routers per edge

        print(f"\n{'=' * 60}")
        print(f"  Internal mesh: {mesh_label} (border={chip_n}/edge, max_links/pair={max_links_per_pair})")
        print(f"{'=' * 60}")

        # Generate traffic matrix for this mesh size
        traf_file = f'traffic_cp_K{K}_{mesh_label}.txt'
        gen_traffic_matrix(grid, traffic, npc, CONFIG_DIR / traf_file)

        # Budget sweep: 1x to max_useful per adj pair
        budget_per_pair_list = list(range(1, max_links_per_pair + 1))
        # Also add some express-specific budgets
        budget_list = sorted(set(
            [n_adj * bpp for bpp in budget_per_pair_list] +
            [n_adj * 1, n_adj * 2, n_adj * 3]  # ensure small budgets covered
        ))
        # Cap at reasonable max
        budget_list = [b for b in budget_list if b <= n_adj * max_links_per_pair + 20]

        # Scale injection rates: keep total injection constant across mesh sizes
        # N=2 (npc=4) is baseline; for N=n, rate = base_rate * 4 / npc
        rates = [r * 4.0 / npc for r in base_rates]
        print(f"  Scaled rates (base × 4/{npc}): {[f'{r:.4f}' for r in rates]}")

        mesh_results = {'mesh': mesh_label, 'chip_n': chip_n, 'experiments': []}

        for budget in budget_list:
            bpp = budget / n_adj
            print(f"\n  --- Budget: {budget} links ({bpp:.1f}x per adj pair) ---")

            for strategy_name in ['adj_uniform', 'express_greedy']:
                print(f"    {strategy_name}...", end=' ', flush=True)

                if strategy_name == 'adj_uniform':
                    # Cap per-pair at max_links_per_pair
                    effective_budget = min(budget, n_adj * max_links_per_pair)
                    alloc = alloc_adjacent_uniform(grid, effective_budget)
                else:
                    alloc = alloc_express_greedy(grid, traffic, budget, max_dist=3)

                # Count actual links and express links
                total_links = sum(alloc.values())
                n_express = sum(1 for p in alloc if p not in set(adj_pairs))
                n_express_links = sum(alloc[p] for p in alloc if p not in set(adj_pairs))

                # Cap links at border capacity
                capped_alloc = {}
                for p, n in alloc.items():
                    capped_alloc[p] = min(n, max_links_per_pair)
                actual_links = sum(capped_alloc.values())

                # Generate config
                cfg_name = f'cp_K{K}_{mesh_label}_{strategy_name}_L{budget}'
                gen_anynet_config(cfg_name, grid, capped_alloc, chip_n=chip_n,
                                  outdir=CONFIG_DIR)

                # Run BookSim at test rates
                rate_results = []
                for rate in rates:
                    r = run_booksim(cfg_name, traf_file, rate)
                    rate_results.append({
                        'rate': rate,
                        'latency': r['latency'],
                        'throughput': r['throughput'],
                    })
                    lat_str = f"lat={r['latency']:.1f}" if r['latency'] else "fail"
                    print(f"r={rate}:{lat_str}", end=' ', flush=True)

                print(f" [{n_express} expr, {actual_links} total]")

                mesh_results['experiments'].append({
                    'budget': budget,
                    'budget_per_pair': float(bpp),
                    'strategy': strategy_name,
                    'total_links': actual_links,
                    'n_express_pairs': n_express,
                    'n_express_links': n_express_links,
                    'rates': rate_results,
                })

        all_results[mesh_label] = mesh_results

    # Save results
    with open(RESULTS_DIR / 'cost_performance.json', 'w') as f:
        json.dump(all_results, f, indent=2)

    # Generate figures
    print(f"\n{'=' * 60}")
    print("  Generating figures...")
    print(f"{'=' * 60}")
    generate_figures(all_results)

    print(f"\n  Results: {RESULTS_DIR}")
    print(f"  Figures: {FIGURES_DIR}")


def generate_figures(all_results):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        'font.size': 9, 'font.family': 'serif',
        'axes.labelsize': 10, 'axes.titlesize': 10,
        'legend.fontsize': 8, 'xtick.labelsize': 8, 'ytick.labelsize': 8,
        'figure.dpi': 150,
    })

    n_meshes = len(all_results)
    fig, axes = plt.subplots(1, n_meshes, figsize=(3.5 * n_meshes, 3.0))
    if n_meshes == 1:
        axes = [axes]

    # Target rate for comparison
    target_rate = 0.01

    for idx, (mesh_label, data) in enumerate(all_results.items()):
        ax = axes[idx]
        exps = data['experiments']

        for strategy, color, marker, label in [
            ('adj_uniform', '#1f77b4', 'o', 'Adjacent Uniform'),
            ('express_greedy', '#d62728', 's', 'Express Greedy'),
        ]:
            strat_exps = [e for e in exps if e['strategy'] == strategy]
            costs = []
            lats = []
            for e in strat_exps:
                rate_data = [r for r in e['rates'] if abs(r['rate'] - target_rate) < 0.001]
                if rate_data and rate_data[0]['latency']:
                    costs.append(e['total_links'])
                    lats.append(rate_data[0]['latency'])

            if costs:
                ax.plot(costs, lats, f'{marker}-', color=color, label=label,
                        markersize=5, linewidth=1.5)

        ax.set_xlabel('Total inter-chiplet links (cost)')
        ax.set_ylabel(f'Latency @ rate {target_rate}')
        ax.set_title(f'{mesh_label} internal mesh')
        ax.legend(fontsize=7)
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    fig.savefig(FIGURES_DIR / 'fig_cost_performance.pdf', bbox_inches='tight')
    fig.savefig(FIGURES_DIR / 'fig_cost_performance.png', bbox_inches='tight')
    plt.close()
    print("  [OK] fig_cost_performance.pdf")

    # Throughput comparison
    fig, axes = plt.subplots(1, n_meshes, figsize=(3.5 * n_meshes, 3.0))
    if n_meshes == 1:
        axes = [axes]

    for idx, (mesh_label, data) in enumerate(all_results.items()):
        ax = axes[idx]
        exps = data['experiments']

        for strategy, color, marker, label in [
            ('adj_uniform', '#1f77b4', 'o', 'Adjacent Uniform'),
            ('express_greedy', '#d62728', 's', 'Express Greedy'),
        ]:
            strat_exps = [e for e in exps if e['strategy'] == strategy]
            costs = []
            tputs = []
            for e in strat_exps:
                # Find peak throughput (max across all rates)
                valid = [r['throughput'] for r in e['rates'] if r['throughput']]
                if valid:
                    costs.append(e['total_links'])
                    tputs.append(max(valid))

            if costs:
                ax.plot(costs, tputs, f'{marker}-', color=color, label=label,
                        markersize=5, linewidth=1.5)

        ax.set_xlabel('Total inter-chiplet links (cost)')
        ax.set_ylabel('Peak throughput')
        ax.set_title(f'{mesh_label} internal mesh')
        ax.legend(fontsize=7)
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    fig.savefig(FIGURES_DIR / 'fig_cost_throughput.pdf', bbox_inches='tight')
    fig.savefig(FIGURES_DIR / 'fig_cost_throughput.png', bbox_inches='tight')
    plt.close()
    print("  [OK] fig_cost_throughput.pdf")


if __name__ == '__main__':
    main()
