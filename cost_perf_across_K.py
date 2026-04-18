"""
Cost-Performance Across K Values
==================================

Fixed internal mesh: 4×4
Sweep K = 4, 8, 16, 32
Goal: honest data for "cost gap widens with K"
"""

import json
import time
import subprocess
import numpy as np
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))
from noi_topology_synthesis import ChipletGrid
from cost_performance_experiment import (
    gen_anynet_config, gen_traffic_matrix,
    alloc_adjacent_uniform, alloc_express_greedy,
    run_booksim,
)

BOOKSIM = str(Path(__file__).parent / 'booksim2' / 'src' / 'booksim')
CONFIG_DIR = Path(__file__).parent / 'booksim_configs'
RESULTS_DIR = Path(__file__).parent / 'results' / 'cost_perf_K'
FIGURES_DIR = Path(__file__).parent / 'paper' / 'figures'

CHIP_N = 4  # fixed 4×4 internal mesh


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    configs = [
        (2, 2, '2x2', 4),
        (2, 4, '2x4', 8),
        (4, 4, '4x4', 16),
        (4, 8, '4x8', 32),
    ]

    npc = CHIP_N * CHIP_N  # 16
    rates = [0.005, 0.01, 0.015]
    all_results = {}

    for R, C, grid_label, K in configs:
        grid = ChipletGrid(R, C)
        adj_pairs = grid.get_adj_pairs()
        n_adj = len(adj_pairs)
        max_links_per_pair = CHIP_N  # 4

        print(f"\n{'=' * 60}")
        print(f"  K={K} ({grid_label}), {n_adj} adj pairs, internal {CHIP_N}x{CHIP_N}")
        print(f"{'=' * 60}")

        # Traffic matrix
        rng = np.random.RandomState(42)
        traffic = rng.rand(K, K) * 100
        np.fill_diagonal(traffic, 0)
        traffic = (traffic + traffic.T) / 2

        traf_file = f'traffic_cpK_{grid_label}_n{CHIP_N}.txt'
        gen_traffic_matrix(grid, traffic, npc, CONFIG_DIR / traf_file)

        # Budget sweep: 1x to 4x per adj pair
        budget_multipliers = [1, 2, 3, 4]
        k_results = {'K': K, 'grid': grid_label, 'n_adj': n_adj, 'experiments': []}

        for mult in budget_multipliers:
            budget = n_adj * mult
            print(f"\n  --- Budget {mult}x ({budget} links) ---")

            for strategy_name in ['adj_uniform', 'express_greedy']:
                t0 = time.time()
                print(f"    {strategy_name}...", end=' ', flush=True)

                if strategy_name == 'adj_uniform':
                    alloc = alloc_adjacent_uniform(grid, budget)
                else:
                    max_dist = min(3, max(R, C) - 1)
                    if max_dist < 2:
                        max_dist = 2
                    alloc = alloc_express_greedy(grid, traffic, budget, max_dist=max_dist)

                t_algo = time.time() - t0

                # Cap at border capacity
                capped_alloc = {}
                for p, n in alloc.items():
                    capped_alloc[p] = min(n, max_links_per_pair)
                actual_links = sum(capped_alloc.values())
                n_express = sum(1 for p in capped_alloc if p not in set(adj_pairs))

                # Generate BookSim config
                cfg_name = f'cpK_{grid_label}_n{CHIP_N}_{strategy_name}_L{budget}'
                gen_anynet_config(cfg_name, grid, capped_alloc, chip_n=CHIP_N, outdir=CONFIG_DIR)

                # Run BookSim
                rate_results = []
                for rate in rates:
                    r = run_booksim(cfg_name, traf_file, rate, timeout=300)
                    rate_results.append({
                        'rate': rate,
                        'latency': r['latency'],
                        'throughput': r['throughput'],
                    })
                    lat_str = f"lat={r['latency']:.1f}" if r['latency'] else "fail"
                    print(f"r={rate}:{lat_str}", end=' ', flush=True)

                print(f"[{n_express}expr, {actual_links}total, algo={t_algo:.1f}s]")

                k_results['experiments'].append({
                    'budget': budget,
                    'budget_mult': mult,
                    'strategy': strategy_name,
                    'total_links': actual_links,
                    'n_express': n_express,
                    'algo_time': t_algo,
                    'rates': rate_results,
                })

        all_results[grid_label] = k_results

    # Save
    with open(RESULTS_DIR / 'cost_perf_across_K.json', 'w') as f:
        json.dump(all_results, f, indent=2)

    # Generate figure
    print(f"\n{'=' * 60}")
    print("  Generating figures...")
    print(f"{'=' * 60}")
    generate_figures(all_results)


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

    # For each K: find the cost (links) to achieve a "good" latency for adj vs express
    # Use rate=0.005 (low load, shows structural advantage)
    target_rate = 0.005

    fig, axes = plt.subplots(1, 2, figsize=(7.16, 2.8))

    # Panel (a): Latency at rate 0.005, budget=3x, across K
    ax = axes[0]
    Ks = []
    adj_lats = []
    expr_lats = []

    for grid_label, data in all_results.items():
        K = data['K']
        # Get 3x budget results
        adj_entry = next((e for e in data['experiments']
                          if e['strategy'] == 'adj_uniform' and e['budget_mult'] == 3), None)
        expr_entry = next((e for e in data['experiments']
                           if e['strategy'] == 'express_greedy' and e['budget_mult'] == 3), None)

        if adj_entry and expr_entry:
            adj_lat = next((r['latency'] for r in adj_entry['rates']
                            if abs(r['rate'] - target_rate) < 0.001 and r['latency']), None)
            expr_lat = next((r['latency'] for r in expr_entry['rates']
                             if abs(r['rate'] - target_rate) < 0.001 and r['latency']), None)
            if adj_lat and expr_lat:
                Ks.append(K)
                adj_lats.append(adj_lat)
                expr_lats.append(expr_lat)

    ax.plot(Ks, adj_lats, 's-', color='#1f77b4', markersize=6, linewidth=1.8,
            label='Adjacent uniform')
    ax.plot(Ks, expr_lats, 'o-', color='#d62728', markersize=6, linewidth=1.8,
            label='Express greedy')
    ax.fill_between(Ks, expr_lats, adj_lats, alpha=0.15, color='#ff7f0e')
    ax.set_xlabel('Number of chiplets (K)')
    ax.set_ylabel(f'Latency @ rate {target_rate}')
    ax.set_title('(a) Performance gap at 3× budget')
    ax.legend(loc='upper left')
    ax.grid(True, alpha=0.3)

    # Panel (b): Cost ratio (adj_links / expr_links for similar latency) across K
    ax = axes[1]
    Ks_cost = []
    cost_ratios = []

    for grid_label, data in all_results.items():
        K = data['K']
        # Find: what's the best express latency at any budget?
        # Then find: what budget does adj need to match it?
        expr_best_lat = float('inf')
        expr_best_links = 0

        for e in data['experiments']:
            if e['strategy'] == 'express_greedy':
                lat = next((r['latency'] for r in e['rates']
                            if abs(r['rate'] - target_rate) < 0.001 and r['latency']), None)
                if lat and lat < expr_best_lat:
                    expr_best_lat = lat
                    expr_best_links = e['total_links']

        # Find cheapest adj that achieves <= expr_best_lat (or closest)
        adj_best_links = None
        adj_best_lat = float('inf')
        for e in data['experiments']:
            if e['strategy'] == 'adj_uniform':
                lat = next((r['latency'] for r in e['rates']
                            if abs(r['rate'] - target_rate) < 0.001 and r['latency']), None)
                if lat and lat <= expr_best_lat * 1.2:  # within 20%
                    if adj_best_links is None or e['total_links'] < adj_best_links:
                        adj_best_links = e['total_links']
                        adj_best_lat = lat

        if adj_best_links and expr_best_links > 0:
            ratio = adj_best_links / expr_best_links
            Ks_cost.append(K)
            cost_ratios.append(ratio)
            print(f"  K={K}: adj needs {adj_best_links} links (lat={adj_best_lat:.0f}), "
                  f"expr needs {expr_best_links} (lat={expr_best_lat:.0f}), "
                  f"ratio={ratio:.2f}x")
        else:
            # Adj couldn't match expr at any tested budget
            Ks_cost.append(K)
            # Use highest budget adj vs best express
            adj_max = max((e for e in data['experiments']
                           if e['strategy'] == 'adj_uniform'),
                          key=lambda e: e['budget_mult'])
            adj_lat = next((r['latency'] for r in adj_max['rates']
                            if abs(r['rate'] - target_rate) < 0.001 and r['latency']), None)
            ratio = adj_max['total_links'] / expr_best_links if expr_best_links > 0 else 1.0
            cost_ratios.append(ratio)
            print(f"  K={K}: adj best={adj_max['total_links']} links (lat={adj_lat}), "
                  f"expr={expr_best_links} (lat={expr_best_lat:.0f}), "
                  f"ratio={ratio:.2f}x (adj couldn't match)")

    ax.bar(range(len(Ks_cost)), cost_ratios, color=['#2ca02c' if r > 1.2 else '#1f77b4'
                                                     for r in cost_ratios],
           edgecolor='white', linewidth=0.5)
    ax.set_xticks(range(len(Ks_cost)))
    ax.set_xticklabels([f'K={k}' for k in Ks_cost])
    ax.set_ylabel('Cost ratio (adj / express)')
    ax.set_title('(b) Express link cost advantage')
    ax.axhline(y=1.0, color='gray', linestyle='--', linewidth=0.8)
    ax.grid(True, alpha=0.3, axis='y')
    for i, (k, r) in enumerate(zip(Ks_cost, cost_ratios)):
        ax.text(i, r + 0.05, f'{r:.1f}×', ha='center', va='bottom', fontsize=8,
                fontweight='bold')

    plt.tight_layout()
    fig.savefig(FIGURES_DIR / 'fig_intro_motivation.pdf', bbox_inches='tight')
    fig.savefig(FIGURES_DIR / 'fig_intro_motivation.png', bbox_inches='tight')
    plt.close()
    print("  [OK] fig_intro_motivation.pdf (from real data)")


if __name__ == '__main__':
    main()
