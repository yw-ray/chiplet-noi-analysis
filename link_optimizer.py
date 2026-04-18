"""
Link Allocation Optimizer for Chiplet NoI
==========================================

Given: chiplet grid, inter-chiplet traffic matrix, link budget
Find: per-pair link allocation that minimizes max link utilization

Formulation (min-max congestion):
  minimize  ρ_max
  subject to:
    load[a,b] / (n[a,b] × B) ≤ ρ_max    ∀ (a,b) with load > 0
    Σ n[a,b] ≤ L                          (budget)
    1 ≤ n[a,b] ≤ M_ab                     (connectivity + physical limit)
    n[a,b] integer

Solved via binary search on ρ_max + greedy rounding.

Compared against:
  1. Uniform: L / n_pairs per pair
  2. Traffic-proportional: n ∝ direct traffic T[a,b]
  3. Load-proportional: n ∝ actual load (includes multi-hop)
  4. LP-optimal (this): min max_rho with constraints
"""

import math
import numpy as np
from pathlib import Path

# Import from existing code
import sys
sys.path.insert(0, str(Path(__file__).parent))
from noi_topology_synthesis import (
    ChipletGrid, compute_link_load, evaluate_allocation,
    allocate_uniform, allocate_traffic_proportional,
    allocate_load_aware, gen_booksim_config, gen_traffic_matrix_file,
)


# ============================================================
# LP Solver: min-max congestion with constraints
# ============================================================

def allocate_lp_optimal(grid, traffic, total_budget, bw_per_link=32,
                        max_links_per_pair=4, min_links_per_pair=1):
    """
    Optimal link allocation via constrained min-max optimization.

    Unlike simple proportional heuristics, this handles:
    1. Physical max links per pair (limited by border routers)
    2. Minimum connectivity constraint
    3. Integer allocation with proper rounding
    4. Tight budgets where rounding matters

    Method: binary search on target ρ_max, then greedy allocation.
    """
    load = compute_link_load(grid, traffic)
    pairs = grid.get_adj_pairs()

    # Classify pairs
    loaded_pairs = [(p, load[p[0]][p[1]]) for p in pairs if load[p[0]][p[1]] > 0]
    unloaded_pairs = [p for p in pairs if load[p[0]][p[1]] <= 0]

    if not loaded_pairs:
        return allocate_uniform(grid, total_budget)

    # Sort by load (descending) for greedy allocation
    loaded_pairs.sort(key=lambda x: -x[1])

    # Binary search on ρ_max
    lo, hi = 0.001, 10000.0
    best_alloc = None
    best_rho = float('inf')

    for _ in range(60):  # ~60 iterations gives precision ~1e-18
        mid = (lo + hi) / 2

        # Compute required links for each pair at this ρ_max
        alloc = {}
        needed = 0

        # Unloaded pairs get minimum
        for p in unloaded_pairs:
            alloc[p] = min_links_per_pair
            needed += min_links_per_pair

        # Loaded pairs: n >= ceil(load / (ρ_max × B))
        for (p, ld) in loaded_pairs:
            required = max(min_links_per_pair,
                          math.ceil(ld / (mid * bw_per_link)))
            required = min(required, max_links_per_pair)  # physical limit
            alloc[p] = required
            needed += required

        if needed <= total_budget:
            # Feasible — try to do better
            hi = mid

            # Distribute remaining budget to reduce max_rho further
            remaining = total_budget - needed

            # Greedy: give extra links to the pair with highest current ρ
            while remaining > 0:
                worst_pair = None
                worst_rho = 0
                for (p, ld) in loaded_pairs:
                    if alloc[p] >= max_links_per_pair:
                        continue
                    rho = ld / (alloc[p] * bw_per_link)
                    if rho > worst_rho:
                        worst_rho = rho
                        worst_pair = p
                if worst_pair is None:
                    break
                alloc[worst_pair] += 1
                remaining -= 1

            # Check if this is the best so far
            actual_max_rho = max(ld / (alloc[p] * bw_per_link)
                                 for (p, ld) in loaded_pairs)
            if actual_max_rho < best_rho:
                best_rho = actual_max_rho
                best_alloc = dict(alloc)
        else:
            lo = mid  # infeasible, need higher ρ

    if best_alloc is None:
        # Fallback: all pairs get minimum, give rest to highest-load
        best_alloc = {p: min_links_per_pair for p in pairs}
        remaining = total_budget - len(pairs) * min_links_per_pair
        for (p, ld) in loaded_pairs:
            if remaining <= 0:
                break
            add = min(remaining, max_links_per_pair - min_links_per_pair)
            best_alloc[p] += add
            remaining -= add

    return best_alloc


# ============================================================
# Experiment runner
# ============================================================

def run_comparison(grid, traffic, budgets, bw_per_link=32,
                   max_links_per_pair=4, label=""):
    """Compare all allocation strategies at multiple budgets."""

    print(f"\n  {'='*90}")
    print(f"  {label}")
    print(f"  {'='*90}")

    load = compute_link_load(grid, traffic)
    pairs = grid.get_adj_pairs()

    # Show phantom load stats
    phantom = sum(1 for p in pairs if traffic[p[0]][p[1]] == 0 and load[p[0]][p[1]] > 0)
    max_amp = max((load[p[0]][p[1]] / traffic[p[0]][p[1]] if traffic[p[0]][p[1]] > 0
                   else (999 if load[p[0]][p[1]] > 0 else 0)) for p in pairs)
    print(f"  Phantom links: {phantom}/{len(pairs)} ({phantom/len(pairs):.0%}), "
          f"max load amplification: {max_amp:.0f}x")

    for budget in budgets:
        strategies = {
            'uniform': allocate_uniform(grid, budget),
            'traffic_prop': allocate_traffic_proportional(grid, traffic, budget),
            'load_aware': allocate_load_aware(grid, traffic, budget),
            'LP_optimal': allocate_lp_optimal(grid, traffic, budget, bw_per_link,
                                              max_links_per_pair),
        }

        print(f"\n  Budget={budget}, max_links/pair={max_links_per_pair}:")
        print(f"  {'Strategy':<15} {'max_ρ':>8} {'avg_ρ':>8} {'#SAT':>5} "
              f"{'min_link':>8} {'max_link':>8}")
        print(f"  {'-'*58}")

        for name, alloc in strategies.items():
            ev = evaluate_allocation(grid, traffic, alloc, bw_per_link)
            links = [alloc.get(p, 0) for p in pairs]
            marker = " ★" if name == 'LP_optimal' else ""
            print(f"  {name:<15} {ev['max_rho']:>8.2f} {ev['avg_rho']:>8.2f} "
                  f"{ev['n_saturated']:>5} {min(links):>8} {max(links):>8}{marker}")

    return strategies


def main():
    sys.path.insert(0, str(Path(__file__).parent / 'rl_partitioner'))
    from envs.realistic_netlist import create_realistic_accelerator
    from sa_coopt_v2 import constrained_spectral

    def balanced_spectral(G, K, grid, con, seed=42):
        asgn = constrained_spectral(G, K, grid, con, seed)
        nodes = sorted(G.nodes)
        for _ in range(30):
            compute = np.zeros(K)
            for n in nodes: compute[asgn[n]] += G.nodes[n]['compute']
            o, u = np.argmax(compute), np.argmin(compute)
            if compute[o] < compute[u] * 1.5: break
            cands = [n for n in nodes if asgn[n] == o]
            if not cands: break
            best_n, best_c = None, float('inf')
            for n in cands:
                ic = sum(G[n][nb]['bandwidth'] for nb in G.neighbors(n)
                         if asgn[nb] == o and n != nb)
                if ic < best_c: best_c, best_n = ic, n
            if best_n: asgn[best_n] = u
        return asgn

    outdir = Path('booksim_configs')

    # ── Experiment 1: K=8 with physical link limit ──
    configs = [
        ('K8_max2', 8, (2,4), 8, 4, 4, 0.3, [16, 20, 24, 32], 2),  # 2×2 mesh → max 2/pair
        ('K8_max4', 8, (2,4), 8, 4, 4, 0.3, [24, 32, 40, 64], 4),  # 4×4 mesh → max 4/pair
        ('K16_max2', 16, (4,4), 16, 4, 8, 0.3, [48, 64, 96], 2),
        ('K8big_max2', 8, (2,4), 8, 8, 8, 0.4, [16, 20, 24, 32], 2),
    ]

    all_booksim = []

    for (label, K, gshape, nc, cpc, nsc, xcr, budgets, max_lpp) in configs:
        grid = ChipletGrid(*gshape)
        G, con = create_realistic_accelerator(
            n_compute_clusters=nc, cores_per_cluster=cpc,
            n_shared_cache=nsc, n_hbm_ctrl=4,
            n_reduction_units=max(2, K//4), cross_cluster_ratio=xcr)
        asgn = balanced_spectral(G, K, grid, con)

        traffic = np.zeros((K, K))
        for u, v, d in G.edges(data=True):
            cu, cv = asgn[u], asgn[v]
            if cu != cv:
                traffic[cu][cv] += d['bandwidth']
                traffic[cv][cu] += d['bandwidth']

        strats = run_comparison(grid, traffic, budgets, max_links_per_pair=max_lpp,
                                label=f"{label} (K={K}, {gshape[0]}x{gshape[1]}, max={max_lpp} links/pair)")

        # Generate BookSim configs for the tightest budget (most differentiation)
        budget = budgets[0]  # tightest
        chip_r, chip_c = (2, 2) if max_lpp <= 2 else (4, 4)

        for sname in ['uniform', 'traffic_prop', 'load_aware', 'LP_optimal']:
            alloc = {
                'uniform': allocate_uniform(grid, budget),
                'traffic_prop': allocate_traffic_proportional(grid, traffic, budget),
                'load_aware': allocate_load_aware(grid, traffic, budget),
                'LP_optimal': allocate_lp_optimal(grid, traffic, budget, 32, max_lpp),
            }[sname]
            cfg_name = f"lp_{label}_{sname}_L{budget}"
            gen_booksim_config(cfg_name, grid, alloc, chip_r, chip_c, str(outdir))
            all_booksim.append((cfg_name, label, budget))

        gen_traffic_matrix_file(grid, traffic,
                                str(outdir / f"traffic_lp_{label}.txt"),
                                npc=chip_r * chip_c)

    # Generate BookSim run script
    with open(outdir / 'run_lp_validation.sh', 'w') as f:
        f.write("#!/bin/bash\nset -e\n")
        f.write('BOOKSIM="../booksim2/src/booksim"\n')
        f.write('RESULTS="../results/lp_validation"\nmkdir -p "$RESULTS"\n')
        f.write('echo "config,rate,latency,throughput" > "$RESULTS/summary.csv"\n')
        f.write('RATES="0.001 0.002 0.003 0.005 0.007 0.01 0.015 0.02"\n\n')

        for (cfg, label, budget) in all_booksim:
            traf = f"traffic_lp_{label}.txt"
            f.write(f'echo "--- {cfg} ---"\n')
            f.write(f'for rate in $RATES; do\n')
            f.write(f'  out="$RESULTS/{cfg}_${{rate}}.log"\n')
            f.write(f'  timeout 120 $BOOKSIM "{cfg}.cfg" injection_rate="$rate" ')
            f.write(f'"traffic=matrix({traf})" > "$out" 2>&1 || true\n')
            f.write('  lat=$(grep "Packet latency average" "$out" | tail -1 | awk \'{print $5}\')\n')
            f.write('  tput=$(grep "Accepted packet rate average" "$out" | tail -1 | awk \'{print $6}\')\n')
            f.write(f'  [ -n "$lat" ] && [ -n "$tput" ] && echo "{cfg},${{rate}},$lat,$tput" >> "$RESULTS/summary.csv" && ')
            f.write('printf "  rate=%-6s lat=%-10s tput=%s\\n" "$rate" "$lat" "$tput" ')
            f.write('|| printf "  rate=%-6s (fail)\\n" "$rate"\n')
            f.write('done\necho ""\n\n')

    print(f"\n  Generated {len(all_booksim)} BookSim configs")
    print(f"  Run: cd booksim_configs && bash run_lp_validation.sh")


if __name__ == '__main__':
    main()
