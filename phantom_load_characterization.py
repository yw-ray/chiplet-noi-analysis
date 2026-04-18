"""
Phantom Load Characterization Study
=====================================

Domain contribution: systematic characterization of phantom load
in chiplet Network-on-Interposer (NoI).

Analyses:
  1. Closed-form derivation + validation
  2. Scaling curve: K=4 to K=64
  3. Amplification distribution (avg, median, p95, max)
  4. Mitigation strategy comparison
  5. Design guideline extraction

Output: JSON results + matplotlib figures for paper.
"""

import math
import json
import numpy as np
from pathlib import Path
from collections import defaultdict

import sys
sys.path.insert(0, str(Path(__file__).parent))
from noi_topology_synthesis import (
    ChipletGrid, compute_link_load,
    allocate_uniform, allocate_traffic_proportional,
    allocate_load_aware, allocate_minmax_optimal,
    evaluate_allocation,
)
from express_link_optimizer import (
    express_greedy, compute_load_with_express, compute_max_rho,
    adjacent_uniform, adjacent_load_aware,
)

RESULTS_DIR = Path(__file__).parent / 'results' / 'characterization'
FIGURES_DIR = Path(__file__).parent / 'paper' / 'figures'


# ============================================================
# Traffic matrix generators
# ============================================================

def uniform_random_traffic(K, seed=42, scale=100.0):
    """Uniform random inter-chiplet traffic."""
    rng = np.random.RandomState(seed)
    T = rng.rand(K, K) * scale
    np.fill_diagonal(T, 0)
    T = (T + T.T) / 2
    return T


def hotspot_traffic(K, seed=42, scale=100.0, n_hotspots=2):
    """Traffic with hotspot chiplets that attract more flows."""
    rng = np.random.RandomState(seed)
    T = rng.rand(K, K) * scale * 0.1  # low background
    np.fill_diagonal(T, 0)
    hotspots = rng.choice(K, size=min(n_hotspots, K), replace=False)
    for h in hotspots:
        for j in range(K):
            if j != h:
                extra = scale * rng.uniform(0.5, 1.0)
                T[h][j] += extra
                T[j][h] += extra
    T = (T + T.T) / 2
    return T


def nearest_neighbor_traffic(K, grid, seed=42, scale=100.0, decay=0.3):
    """Traffic decays with distance (locality-aware)."""
    rng = np.random.RandomState(seed)
    T = np.zeros((K, K))
    for i in range(K):
        for j in range(i + 1, K):
            d = grid.get_hops(i, j)
            weight = math.exp(-decay * d) * rng.uniform(0.5, 1.0) * scale
            T[i][j] = weight
            T[j][i] = weight
    return T


def all_to_all_traffic(K, scale=100.0):
    """Uniform all-to-all (worst case for phantom load)."""
    T = np.full((K, K), scale)
    np.fill_diagonal(T, 0)
    return T


WORKLOADS = {
    'uniform_random': uniform_random_traffic,
    'hotspot': hotspot_traffic,
    'all_to_all': lambda K, **kw: all_to_all_traffic(K),
}


# ============================================================
# Analysis 1: Closed-form phantom load derivation
# ============================================================

def closed_form_phantom_load_uniform(R, C):
    """
    Closed-form analysis for uniform all-to-all traffic on R×C grid
    with XY (dimension-order) routing.

    For each adjacent link (a,b), count the number of (src,dst) pairs
    whose XY-routing path crosses (a,b).

    Returns dict with per-link flow counts and aggregate statistics.
    """
    K = R * C
    grid = ChipletGrid(R, C)
    adj_pairs = grid.get_adj_pairs()

    # Count flows crossing each adjacent link
    flow_count = {}
    for (a, b) in adj_pairs:
        flow_count[(a, b)] = 0

    for i in range(K):
        for j in range(K):
            if i == j:
                continue
            path = grid.shortest_path(i, j)
            for h in range(len(path) - 1):
                a, b = min(path[h], path[h + 1]), max(path[h], path[h + 1])
                if (a, b) in flow_count:
                    flow_count[(a, b)] += 1

    # Direct traffic: flows where src or dst is a or b AND they are adjacent
    direct_count = {}
    for (a, b) in adj_pairs:
        # Flows from a->b and b->a
        direct_count[(a, b)] = 2  # (a,b) and (b,a)

    # Compute amplification
    total_pairs = K * (K - 1)  # directed pairs
    amplifications = []
    phantom_links = 0
    for (a, b) in adj_pairs:
        fc = flow_count[(a, b)]
        dc = direct_count[(a, b)]
        amp = fc / dc if dc > 0 else float('inf')
        amplifications.append(amp)
        if fc > dc:
            # Has phantom load (more flows than direct)
            pass
        # A link is "phantom-dominated" if phantom flows > direct flows
        phantom_flows = fc - dc
        if phantom_flows > dc:
            phantom_links += 1

    # Theoretical formula for center link in R×C grid:
    # For a horizontal link at row r, between columns c and c+1:
    #   flows = sum over all (src_row, src_col, dst_row, dst_col)
    #           where XY routing goes through this link
    #   = R * (c+1) * R * (C-c-1) for horizontal links (all rows route through)
    #   Wait, more precisely for XY routing:
    #   A horizontal link between (r, c) and (r, c+1):
    #     flow count = R × (c+1) × (C-c-1) × ... no, need to be careful

    # Actually for XY routing on R×C grid:
    # Horizontal link at column boundary c|c+1 (any row):
    #   Any src with col <= c going to any dst with col >= c+1 routes through
    #   ONE such link at row = src_row (X-first, then Y)
    #   Wait — XY routing goes X first. So for src at (rs, cs) to dst at (rd, cd):
    #   If cd > cs: path goes right along row rs through columns cs..cd, then
    #               up/down from rs to rd.
    #   So horizontal link at (r, c)-(r, c+1) is crossed when:
    #     rs = r AND cs <= c AND cd >= c+1
    #   Flow count = R_dst × (c+1 cols on left) × (C-c-1 cols on right)
    #   where R_dst = R (any destination row)
    #   Hmm let me think again...
    #
    # For XY routing (X first = move horizontally first, then vertically):
    #   src = (rs, cs), dst = (rd, cd)
    #   Horizontal link (r, c) <-> (r, c+1) is used when:
    #     rs == r (source row must be r, since horizontal movement happens at source row)
    #     AND cs <= c < c+1 <= cd  (moving right) OR cd <= c < c+1 <= cs (moving left)
    #   For rightward: cs <= c AND cd >= c+1
    #   Count = |{rs=r}| × |{cs: cs<=c}| × |{(rd,cd): cd>=c+1}|
    #         = 1 (rs=r) × (c+1 choices for cs: 0..c) × (R × (C-c-1) choices for (rd,cd))
    #         But rs=r means src is at row r, any col <= c
    #   Rightward flows through (r,c)-(r,c+1):
    #     src at (r, cs) with cs in [0..c], dst at (rd, cd) with cd in [c+1..C-1], any rd
    #     Count = (c+1) × R × (C-c-1) - (those where src=dst, impossible since different cols)
    #   Leftward flows through (r,c+1)-(r,c):
    #     src at (r, cs) with cs in [c+1..C-1], dst at (rd, cd) with cd in [0..c], any rd
    #     Count = (C-c-1) × R × (c+1)
    #   Total = 2 × R × (c+1) × (C-c-1)
    #
    # Similarly for vertical link at (r, c) <-> (r+1, c):
    #   In XY routing, vertical movement happens at dst column.
    #   src = (rs, cs), dst = (rd, cd)
    #   Vertical link (r,c)-(r+1,c) is used when:
    #     cd == c AND routing path goes through row r to r+1
    #   Downward: rs <= r AND rd >= r+1 AND cd == c
    #     But the vertical part starts after horizontal part, at column cd=c
    #     So src can be at any column (cs), any row rs, as long as:
    #       cd = c, rd >= r+1, and the path goes down through (r,c)
    #     After horizontal move, we're at (rs, cd) = (rs, c), then move vertically.
    #     Vertical link (r,c)-(r+1,c) is crossed when rs <= r and rd >= r+1 and cd=c
    #     OR rs >= r+1 and rd <= r and cd=c
    #   Downward count: C × (r+1) × (R-r-1) -- wait
    #     src: any cs (C choices), rs in [0..r] (r+1 choices)
    #     dst: cd=c (1 choice), rd in [r+1..R-1] (R-r-1 choices)
    #     Count = C × (r+1) × 1 × (R-r-1)
    #   Upward: C × (R-r-1) × (r+1)
    #   Total = 2 × C × (r+1) × (R-r-1)
    #
    # So:
    #   Horizontal link at (r, c)-(r, c+1): flows = 2 × R × (c+1) × (C-c-1)
    #   Vertical link at (r, c)-(r+1, c):   flows = 2 × C × (r+1) × (R-r-1)

    # Validate formula against simulation
    formula_flows = {}
    for (a, b) in adj_pairs:
        ra, ca = grid.positions[a]
        rb, cb = grid.positions[b]
        if ra == rb:  # horizontal link
            c_left = min(ca, cb)
            formula_flows[(a, b)] = 2 * R * (c_left + 1) * (C - c_left - 1)
        else:  # vertical link
            r_top = min(ra, rb)
            formula_flows[(a, b)] = 2 * C * (r_top + 1) * (R - r_top - 1)

    # Max flow count (center link)
    max_h_flow = 2 * R * math.ceil(C / 2) * math.floor(C / 2)  # center horizontal
    max_v_flow = 2 * C * math.ceil(R / 2) * math.floor(R / 2)  # center vertical
    max_flow = max(max_h_flow, max_v_flow)
    min_flow = 2 * R  # edge horizontal (c=0 or c=C-2): 2*R*1*(C-1) wait..
    # Actually minimum is at corner: 2*R*1*1 = 2R (for C>=2) or 2*C*1*1 = 2C

    # Direct flow per link = 2 (one flow each direction between adjacent pair)
    max_amplification = max_flow / 2
    avg_amplification = np.mean([f / 2 for f in formula_flows.values()])

    # Fraction of links that are "phantom-dominated" (phantom > direct)
    phantom_dominated = sum(1 for f in formula_flows.values() if f > 4) / len(adj_pairs)

    # Validate: formula matches simulation?
    validation_ok = all(
        abs(formula_flows[(a, b)] - flow_count[(a, b)]) < 0.01
        for (a, b) in adj_pairs
    )

    return {
        'R': R, 'C': C, 'K': R * C,
        'n_adj_pairs': len(adj_pairs),
        'flow_counts': {f'{a}-{b}': flow_count[(a, b)] for (a, b) in adj_pairs},
        'formula_flows': {f'{a}-{b}': formula_flows[(a, b)] for (a, b) in adj_pairs},
        'formula_validated': validation_ok,
        'max_flow': max_flow,
        'direct_flow_per_link': 2,
        'max_amplification': max_amplification,
        'avg_amplification': float(avg_amplification),
        'phantom_dominated_fraction': phantom_dominated,
        'formula': {
            'horizontal': '2 * R * (c+1) * (C-c-1)',
            'vertical': '2 * C * (r+1) * (R-r-1)',
            'max_horizontal': f'2 * {R} * ceil({C}/2) * floor({C}/2) = {max_h_flow}',
            'max_vertical': f'2 * {C} * ceil({R}/2) * floor({R}/2) = {max_v_flow}',
        },
    }


# ============================================================
# Analysis 2: Scaling curve
# ============================================================

def phantom_load_scaling(grid_configs, seeds=range(3)):
    """
    Compute phantom load metrics across grid sizes and workloads.

    For each grid, compute:
      - Fraction of phantom-dominated links
      - Max / avg / median / p95 amplification
      - Load distribution (Gini coefficient)
    """
    results = []

    for (R, C, label) in grid_configs:
        K = R * C
        grid = ChipletGrid(R, C)
        adj_pairs = grid.get_adj_pairs()

        for wl_name, wl_fn in WORKLOADS.items():
            print(f"    {label} K={K} workload={wl_name}...")
            seed_results = []
            for seed in seeds:
                if wl_name == 'all_to_all':
                    traffic = wl_fn(K)
                elif wl_name == 'nearest_neighbor':
                    traffic = nearest_neighbor_traffic(K, grid, seed=seed)
                elif wl_name == 'hotspot':
                    traffic = hotspot_traffic(K, seed=seed)
                else:
                    traffic = wl_fn(K, seed=seed)

                load_matrix = compute_link_load(grid, traffic)

                # Per-link analysis
                amplifications = []
                phantom_count = 0
                loads = []
                direct_traffics = []

                for (a, b) in adj_pairs:
                    ld = load_matrix[a][b]
                    direct = traffic[a][b] + traffic[b][a]
                    loads.append(ld)
                    direct_traffics.append(direct)

                    if direct > 0:
                        amp = ld / direct
                    else:
                        amp = float('inf') if ld > 0 else 1.0

                    if ld > 0 and direct == 0:
                        phantom_count += 1
                        amplifications.append(amp)
                    elif direct > 0:
                        amplifications.append(amp)

                # Filter out inf for stats
                finite_amps = [a for a in amplifications if a != float('inf')]
                if not finite_amps:
                    finite_amps = [1.0]

                # Gini coefficient of load distribution
                loads_arr = np.array(loads)
                if loads_arr.sum() > 0:
                    sorted_loads = np.sort(loads_arr)
                    n = len(sorted_loads)
                    index = np.arange(1, n + 1)
                    gini = (2 * np.sum(index * sorted_loads) / (n * np.sum(sorted_loads))) - (n + 1) / n
                else:
                    gini = 0.0

                seed_results.append({
                    'phantom_fraction': phantom_count / len(adj_pairs),
                    'max_amplification': max(finite_amps),
                    'avg_amplification': float(np.mean(finite_amps)),
                    'median_amplification': float(np.median(finite_amps)),
                    'p95_amplification': float(np.percentile(finite_amps, 95)),
                    'load_gini': float(gini),
                    'max_load': float(max(loads)),
                    'min_load': float(min(loads)),
                    'load_ratio': float(max(loads) / max(min(loads), 1e-6)),
                })

            # Average across seeds
            avg_result = {}
            for key in seed_results[0]:
                vals = [sr[key] for sr in seed_results]
                avg_result[key] = float(np.mean(vals))
                avg_result[f'{key}_std'] = float(np.std(vals))

            results.append({
                'grid': label, 'R': R, 'C': C, 'K': K,
                'n_adj': len(adj_pairs),
                'workload': wl_name,
                'avg_hops': float(np.mean([
                    grid.get_hops(i, j) for i in range(K) for j in range(i + 1, K)
                ])),
                **avg_result,
            })

    return results


# ============================================================
# Analysis 3: Mitigation strategy comparison
# ============================================================

def mitigation_comparison(grid_configs, budget_multipliers=[2, 3, 4, 6]):
    """
    Compare all mitigation strategies across grid sizes and budgets.
    Express greedy is only run for K <= 16 (too slow for larger grids).
    """
    results = []

    for (R, C, label) in grid_configs:
        K = R * C
        grid = ChipletGrid(R, C)
        adj_pairs = grid.get_adj_pairs()
        n_adj = len(adj_pairs)
        run_express = (K <= 16)

        print(f"    {label} (K={K}) express={'yes' if run_express else 'skip'}...")

        for seed in range(3):
            traffic = uniform_random_traffic(K, seed=seed)

            for mult in budget_multipliers:
                budget = n_adj * mult

                strategies = {}

                # 1. Uniform
                alloc = allocate_uniform(grid, budget)
                ev = evaluate_allocation(grid, traffic, alloc)
                strategies['uniform'] = {
                    'max_rho': ev['max_rho'],
                    'avg_rho': ev['avg_rho'],
                    'n_sat': ev['n_saturated'],
                }

                # 2. Traffic-proportional
                alloc = allocate_traffic_proportional(grid, traffic, budget)
                ev = evaluate_allocation(grid, traffic, alloc)
                strategies['traffic_prop'] = {
                    'max_rho': ev['max_rho'],
                    'avg_rho': ev['avg_rho'],
                    'n_sat': ev['n_saturated'],
                }

                # 3. Load-aware
                alloc = allocate_load_aware(grid, traffic, budget)
                ev = evaluate_allocation(grid, traffic, alloc)
                strategies['load_aware'] = {
                    'max_rho': ev['max_rho'],
                    'avg_rho': ev['avg_rho'],
                    'n_sat': ev['n_saturated'],
                }

                # 4. MinMax optimal (adjacent only)
                alloc = allocate_minmax_optimal(grid, traffic, budget)
                ev = evaluate_allocation(grid, traffic, alloc)
                strategies['minmax_adj'] = {
                    'max_rho': ev['max_rho'],
                    'avg_rho': ev['avg_rho'],
                    'n_sat': ev['n_saturated'],
                }

                # 5. Express greedy (K<=16 only)
                if run_express:
                    alloc = express_greedy(grid, traffic, budget,
                                           max_express_distance=min(3, max(R, C) - 1))
                    link_set = set(alloc.keys())
                    load = compute_load_with_express(grid, traffic, link_set)
                    max_rho = compute_max_rho(load, alloc)
                    rhos = []
                    for pair, ld in load.items():
                        n = alloc.get(pair, 0)
                        if n > 0:
                            rhos.append(ld / (n * 32))
                    strategies['express_greedy'] = {
                        'max_rho': max_rho,
                        'avg_rho': float(np.mean(rhos)) if rhos else 0,
                        'n_sat': sum(1 for r in rhos if r >= 1.0),
                        'n_express': sum(1 for p in alloc if p not in set(adj_pairs)),
                    }

                results.append({
                    'grid': label, 'K': K, 'budget': budget,
                    'budget_mult': mult, 'seed': seed,
                    'strategies': strategies,
                })

    return results


# ============================================================
# Analysis 4: Closed-form scaling (theoretical)
# ============================================================

def theoretical_scaling():
    """
    Compute theoretical phantom load metrics from closed-form formulas.

    For R×C grid with uniform all-to-all traffic + XY routing:
      - Horizontal link at col boundary c: flows = 2R(c+1)(C-c-1)
      - Vertical link at row boundary r:   flows = 2C(r+1)(R-r-1)
      - Direct flows per link: 2
      - Center link amplification: R*ceil(C/2)*floor(C/2) (horizontal)
    """
    results = []
    for R in range(2, 9):
        for C in range(R, 9):  # C >= R to avoid duplicates
            K = R * C
            if K > 64:
                continue

            # All horizontal link amplifications
            h_amps = []
            for c in range(C - 1):
                flows = 2 * R * (c + 1) * (C - c - 1)
                h_amps.append(flows / 2)  # amplification = flows / direct

            # All vertical link amplifications
            v_amps = []
            for r in range(R - 1):
                flows = 2 * C * (r + 1) * (R - r - 1)
                v_amps.append(flows / 2)

            # Each horizontal link exists once per row, each vertical per column
            all_amps = []
            for c in range(C - 1):
                all_amps.extend([h_amps[c]] * R)  # R copies (one per row)
            for r in range(R - 1):
                all_amps.extend([v_amps[r]] * C)  # C copies (one per column)

            n_adj = R * (C - 1) + C * (R - 1)
            n_phantom = sum(1 for a in all_amps if a > 2)  # amp > 2 means phantom > direct

            results.append({
                'R': R, 'C': C, 'K': K,
                'n_adj': n_adj,
                'max_amp': max(all_amps),
                'avg_amp': float(np.mean(all_amps)),
                'median_amp': float(np.median(all_amps)),
                'p95_amp': float(np.percentile(all_amps, 95)),
                'min_amp': min(all_amps),
                'phantom_fraction': n_phantom / n_adj,
                'load_imbalance': max(all_amps) / min(all_amps),
                'shape': f'{R}x{C}',
            })

    return results


# ============================================================
# Main: run all analyses
# ============================================================

def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    # ---- Analysis 1: Closed-form validation ----
    print("=" * 60)
    print("  Analysis 1: Closed-form phantom load derivation")
    print("=" * 60)

    cf_results = {}
    for R, C in [(2, 2), (2, 4), (3, 3), (4, 4), (4, 8), (8, 8)]:
        res = closed_form_phantom_load_uniform(R, C)
        cf_results[f'{R}x{C}'] = res
        print(f"\n  {R}x{C} (K={R*C}):")
        print(f"    Formula validated: {res['formula_validated']}")
        print(f"    Max amplification: {res['max_amplification']:.1f}x")
        print(f"    Avg amplification: {res['avg_amplification']:.1f}x")
        print(f"    Phantom-dominated: {res['phantom_dominated_fraction']:.0%}")

    with open(RESULTS_DIR / 'closed_form.json', 'w') as f:
        json.dump(cf_results, f, indent=2, default=str)

    # ---- Analysis 2: Theoretical scaling ----
    print("\n" + "=" * 60)
    print("  Analysis 2: Theoretical phantom load scaling")
    print("=" * 60)

    theo_results = theoretical_scaling()

    # Print summary table
    print(f"\n  {'Grid':<8} {'K':>3} {'#Adj':>5} {'Max':>8} {'Avg':>8} "
          f"{'Med':>8} {'P95':>8} {'Phantom%':>9} {'Imbal':>8}")
    print(f"  {'─' * 72}")
    for r in sorted(theo_results, key=lambda x: x['K']):
        print(f"  {r['shape']:<8} {r['K']:>3} {r['n_adj']:>5} "
              f"{r['max_amp']:>8.1f} {r['avg_amp']:>8.1f} "
              f"{r['median_amp']:>8.1f} {r['p95_amp']:>8.1f} "
              f"{r['phantom_fraction']:>8.0%} {r['load_imbalance']:>8.1f}")

    with open(RESULTS_DIR / 'theoretical_scaling.json', 'w') as f:
        json.dump(theo_results, f, indent=2)

    # ---- Analysis 3: Empirical scaling with workloads ----
    print("\n" + "=" * 60)
    print("  Analysis 3: Empirical phantom load scaling")
    print("=" * 60)

    grid_configs = [
        (2, 2, '2x2'), (2, 3, '2x3'), (2, 4, '2x4'), (3, 3, '3x3'),
        (3, 4, '3x4'), (4, 4, '4x4'), (4, 6, '4x6'), (4, 8, '4x8'),
    ]

    emp_results = phantom_load_scaling(grid_configs)

    # Print summary for uniform_random
    print(f"\n  Uniform random traffic:")
    print(f"  {'Grid':<8} {'K':>3} {'Phantom%':>9} {'Max Amp':>9} "
          f"{'Avg Amp':>9} {'P95 Amp':>9} {'Gini':>6}")
    print(f"  {'─' * 58}")
    for r in emp_results:
        if r['workload'] == 'uniform_random':
            print(f"  {r['grid']:<8} {r['K']:>3} "
                  f"{r['phantom_fraction']:>8.0%} "
                  f"{r['max_amplification']:>9.1f} "
                  f"{r['avg_amplification']:>9.1f} "
                  f"{r['p95_amplification']:>9.1f} "
                  f"{r['load_gini']:>6.3f}")

    with open(RESULTS_DIR / 'empirical_scaling.json', 'w') as f:
        json.dump(emp_results, f, indent=2)

    # ---- Analysis 4: Mitigation comparison ----
    print("\n" + "=" * 60)
    print("  Analysis 4: Mitigation strategy comparison")
    print("=" * 60)

    mit_configs = [
        (2, 2, '2x2'), (2, 4, '2x4'),
        (4, 4, '4x4'), (4, 8, '4x8'),
    ]

    mit_results = mitigation_comparison(mit_configs)

    # Print summary
    for label in ['2x2', '2x4', '4x4', '4x8']:
        entries = [r for r in mit_results if r['grid'] == label and r['seed'] == 0]
        if not entries:
            continue
        print(f"\n  {label} (K={entries[0]['K']}):")
        for e in entries:
            print(f"    Budget {e['budget_mult']}x:")
            for sname in ['uniform', 'traffic_prop', 'load_aware', 'minmax_adj', 'express_greedy']:
                s = e['strategies'].get(sname, {})
                extra = ''
                if 'n_express' in s:
                    extra = f"  ({s['n_express']} express)"
                print(f"      {sname:<18} max_ρ={s.get('max_rho', 0):>7.2f}  "
                      f"avg_ρ={s.get('avg_rho', 0):>6.3f}{extra}")

    with open(RESULTS_DIR / 'mitigation_comparison.json', 'w') as f:
        json.dump(mit_results, f, indent=2, default=str)

    # ---- Generate figures ----
    print("\n" + "=" * 60)
    print("  Generating figures...")
    print("=" * 60)
    generate_figures(theo_results, emp_results, mit_results, cf_results)

    print(f"\n  Results saved to: {RESULTS_DIR}")
    print(f"  Figures saved to: {FIGURES_DIR}")


# ============================================================
# Figure generation
# ============================================================

def generate_figures(theo_results, emp_results, mit_results, cf_results):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MaxNLocator

    plt.rcParams.update({
        'font.size': 9,
        'font.family': 'serif',
        'axes.labelsize': 10,
        'axes.titlesize': 10,
        'legend.fontsize': 8,
        'xtick.labelsize': 8,
        'ytick.labelsize': 8,
        'figure.dpi': 150,
    })

    # ---- Figure 1: Phantom load scaling (theoretical) ----
    fig, axes = plt.subplots(1, 3, figsize=(7.16, 2.2))

    # Filter to square-ish grids for clean scaling
    square_grids = [r for r in theo_results if r['R'] == r['C']
                    or (r['R'], r['C']) in [(2, 4), (4, 8)]]
    square_grids = sorted(square_grids, key=lambda x: x['K'])

    # Remove duplicates by K (keep square)
    seen_k = set()
    filtered = []
    for r in square_grids:
        if r['K'] not in seen_k:
            filtered.append(r)
            seen_k.add(r['K'])
    square_grids = filtered

    Ks = [r['K'] for r in square_grids]

    # 1a: Max & Avg amplification
    ax = axes[0]
    ax.plot(Ks, [r['max_amp'] for r in square_grids], 'o-', color='#d62728',
            label='Max', markersize=4, linewidth=1.5)
    ax.plot(Ks, [r['avg_amp'] for r in square_grids], 's-', color='#1f77b4',
            label='Avg', markersize=4, linewidth=1.5)
    ax.plot(Ks, [r['p95_amp'] for r in square_grids], '^--', color='#ff7f0e',
            label='P95', markersize=4, linewidth=1.2)
    ax.set_xlabel('Number of chiplets (K)')
    ax.set_ylabel('Amplification factor')
    ax.set_yscale('log')
    ax.legend(loc='upper left', framealpha=0.9)
    ax.set_title('(a) Phantom load amplification')
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))

    # 1b: Phantom-dominated fraction
    ax = axes[1]
    ax.plot(Ks, [r['phantom_fraction'] * 100 for r in square_grids],
            'o-', color='#2ca02c', markersize=5, linewidth=1.5)
    ax.set_xlabel('Number of chiplets (K)')
    ax.set_ylabel('Phantom-dominated links (%)')
    ax.set_title('(b) Fraction of phantom links')
    ax.set_ylim(-5, 105)
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))

    # 1c: Load imbalance
    ax = axes[2]
    ax.plot(Ks, [r['load_imbalance'] for r in square_grids],
            'o-', color='#9467bd', markersize=5, linewidth=1.5)
    ax.set_xlabel('Number of chiplets (K)')
    ax.set_ylabel('Load imbalance (max/min)')
    ax.set_title('(c) Load imbalance ratio')
    ax.set_yscale('log')
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))

    plt.tight_layout()
    fig.savefig(FIGURES_DIR / 'fig_phantom_scaling.pdf', bbox_inches='tight')
    fig.savefig(FIGURES_DIR / 'fig_phantom_scaling.png', bbox_inches='tight')
    plt.close()
    print("  [OK] fig_phantom_scaling.pdf")

    # ---- Figure 2: Amplification distribution (histogram) ----
    fig, axes = plt.subplots(1, 3, figsize=(7.16, 2.2))
    grid_examples = ['2x4', '4x4', '8x8']
    colors = ['#1f77b4', '#d62728', '#2ca02c']

    for idx, (gname, color) in enumerate(zip(grid_examples, colors)):
        ax = axes[idx]
        r = next((x for x in theo_results if x['shape'] == gname), None)
        if r is None:
            continue

        R, C = r['R'], r['C']
        # Recompute all amplifications for histogram
        all_amps = []
        for c in range(C - 1):
            amp = R * (c + 1) * (C - c - 1)
            all_amps.extend([amp] * R)
        for row in range(R - 1):
            amp = C * (row + 1) * (R - row - 1)
            all_amps.extend([amp] * C)

        ax.hist(all_amps, bins=min(20, len(set(all_amps))),
                color=color, alpha=0.7, edgecolor='white')
        ax.axvline(x=1, color='gray', linestyle='--', linewidth=0.8, label='Direct only')
        ax.set_xlabel('Amplification factor')
        ax.set_ylabel('Number of links')
        ax.set_title(f'({chr(97+idx)}) {gname} (K={r["K"]})')
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    fig.savefig(FIGURES_DIR / 'fig_amp_distribution.pdf', bbox_inches='tight')
    fig.savefig(FIGURES_DIR / 'fig_amp_distribution.png', bbox_inches='tight')
    plt.close()
    print("  [OK] fig_amp_distribution.pdf")

    # ---- Figure 3: Mitigation strategy comparison ----
    fig, axes = plt.subplots(1, 3, figsize=(7.16, 2.4))

    strategy_names = ['uniform', 'traffic_prop', 'load_aware', 'minmax_adj', 'express_greedy']
    strategy_labels = ['Uniform', 'Traffic\nProp.', 'Load\nAware', 'MinMax\nAdj.', 'Express\nGreedy']
    strategy_colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#9467bd', '#d62728']

    for idx, grid_label in enumerate(['2x4', '4x4', '4x8']):
        ax = axes[idx]
        # Average across seeds, budget_mult=3
        entries = [r for r in mit_results
                   if r['grid'] == grid_label and r['budget_mult'] == 3]

        if not entries:
            continue

        rhos = []
        for sname in strategy_names:
            vals = [e['strategies'][sname]['max_rho'] for e in entries
                    if sname in e['strategies']]
            rhos.append(np.mean(vals) if vals else 0)

        bars = ax.bar(range(len(strategy_names)), rhos, color=strategy_colors,
                      edgecolor='white', linewidth=0.5)
        ax.set_xticks(range(len(strategy_names)))
        ax.set_xticklabels(strategy_labels, fontsize=7)
        ax.set_ylabel('Max utilization (ρ_max)')
        K = entries[0]['K']
        ax.set_title(f'({chr(97+idx)}) {grid_label} (K={K}), 3x budget')
        ax.grid(True, alpha=0.3, axis='y')

        # Add value labels on bars
        for bar, val in zip(bars, rhos):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                        f'{val:.1f}', ha='center', va='bottom', fontsize=6)

    plt.tight_layout()
    fig.savefig(FIGURES_DIR / 'fig_mitigation_comparison.pdf', bbox_inches='tight')
    fig.savefig(FIGURES_DIR / 'fig_mitigation_comparison.png', bbox_inches='tight')
    plt.close()
    print("  [OK] fig_mitigation_comparison.pdf")

    # ---- Figure 4: Workload sensitivity ----
    fig, ax = plt.subplots(1, 1, figsize=(3.5, 2.5))

    wl_names = ['uniform_random', 'hotspot', 'all_to_all']
    wl_labels = ['Uniform Random', 'Hotspot', 'All-to-All']
    wl_colors = ['#1f77b4', '#ff7f0e', '#d62728']

    for wl_name, wl_label, color in zip(wl_names, wl_labels, wl_colors):
        wl_data = [r for r in emp_results if r['workload'] == wl_name]
        wl_data = sorted(wl_data, key=lambda x: x['K'])
        if wl_data:
            ax.plot([r['K'] for r in wl_data],
                    [r['max_amplification'] for r in wl_data],
                    'o-', color=color, label=wl_label, markersize=4, linewidth=1.2)

    ax.set_xlabel('Number of chiplets (K)')
    ax.set_ylabel('Max amplification')
    ax.set_yscale('log')
    ax.legend(fontsize=7)
    ax.set_title('Phantom load across workloads')
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    fig.savefig(FIGURES_DIR / 'fig_workload_sensitivity.pdf', bbox_inches='tight')
    fig.savefig(FIGURES_DIR / 'fig_workload_sensitivity.png', bbox_inches='tight')
    plt.close()
    print("  [OK] fig_workload_sensitivity.pdf")

    # ---- Figure 5: Budget scaling for mitigation ----
    fig, axes = plt.subplots(1, 2, figsize=(7.16, 2.5))

    for idx, grid_label in enumerate(['4x4', '4x8']):
        ax = axes[idx]
        for sname, slabel, color in zip(
            strategy_names,
            ['Uniform', 'Traffic Prop.', 'Load Aware', 'MinMax Adj.', 'Express Greedy'],
            strategy_colors
        ):
            entries = [r for r in mit_results
                       if r['grid'] == grid_label and r['seed'] == 0]
            entries = sorted(entries, key=lambda x: x['budget_mult'])
            if not entries:
                continue
            mults = [e['budget_mult'] for e in entries]
            rhos = [e['strategies'].get(sname, {}).get('max_rho', 0) for e in entries]
            ls = '-' if sname != 'express_greedy' else '-'
            lw = 2.0 if sname == 'express_greedy' else 1.2
            ax.plot(mults, rhos, 'o-', color=color, label=slabel,
                    markersize=4, linewidth=lw)

        K = entries[0]['K'] if entries else 0
        ax.set_xlabel('Budget multiplier (×adj pairs)')
        ax.set_ylabel('Max utilization (ρ_max)')
        ax.set_title(f'({chr(97+idx)}) {grid_label} (K={K})')
        ax.legend(fontsize=6, loc='upper right')
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    fig.savefig(FIGURES_DIR / 'fig_budget_mitigation.pdf', bbox_inches='tight')
    fig.savefig(FIGURES_DIR / 'fig_budget_mitigation.png', bbox_inches='tight')
    plt.close()
    print("  [OK] fig_budget_mitigation.pdf")


if __name__ == '__main__':
    main()
