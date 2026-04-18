"""
Express Link Topology Optimizer
================================

Key insight: In a chiplet 2D grid, multi-hop routing creates "phantom load"
on intermediate links. By adding EXPRESS LINKS between non-adjacent chiplet
pairs, we can bypass congested intermediate links and reduce max congestion.

Technique: Greedy topology synthesis
  1. Start with mandatory adjacent links (1 each for connectivity)
  2. For each remaining link in budget:
     a. Try adding it to every possible pair (adjacent AND non-adjacent)
     b. Re-route traffic with the new link
     c. Pick the link that reduces max congestion the most
  3. Repeat until budget exhausted

This is non-trivial because:
  - Express links reduce phantom load (good) but have higher latency (bad)
  - The optimal set depends on full traffic pattern + routing
  - Greedy with re-routing at each step

Compared against:
  - Adjacent-only uniform
  - Adjacent-only load-aware
  - Express greedy (ours)
"""

import math
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from noi_topology_synthesis import ChipletGrid, gen_booksim_config, gen_traffic_matrix_file


# ============================================================
# Routing with express links
# ============================================================

def compute_load_with_express(grid, traffic, link_set):
    """
    Compute load on each link, routing via shortest path that may use express links.

    link_set: set of (i,j) pairs that have links (adjacent + express)
    Returns: dict {(i,j): load}
    """
    K = grid.K
    # Build graph with all links
    import heapq

    adj = {i: {} for i in range(K)}
    for (a, b) in link_set:
        hops = grid.get_hops(a, b)
        # Express link latency proportional to distance (longer wire)
        weight = max(1, hops)
        adj[a][b] = weight
        adj[b][a] = weight

    # Dijkstra shortest paths for each pair
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

        # Reconstruct path
        path = []
        u = dst
        while u is not None:
            path.append(u)
            u = prev[u]
        path.reverse()
        return path if path[0] == src else []

    # Compute load on each link
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
                a, b = min(path[h], path[h+1]), max(path[h], path[h+1])
                key = (a, b)
                if key in load:
                    load[key] += traffic[i][j]

    return load


def compute_max_rho(load, link_count, bw_per_link=32):
    """Compute max utilization across all links."""
    max_rho = 0
    for pair, ld in load.items():
        n = link_count.get(pair, 0)
        if n > 0:
            rho = ld / (n * bw_per_link)
            max_rho = max(max_rho, rho)
        elif ld > 0:
            max_rho = max(max_rho, 999)
    return max_rho


# ============================================================
# Allocation strategies
# ============================================================

def adjacent_uniform(grid, total_budget):
    """Baseline: uniform links on adjacent pairs only."""
    pairs = grid.get_adj_pairs()
    per = max(1, total_budget // len(pairs))
    alloc = {}
    remaining = total_budget
    for p in pairs:
        n = min(per, remaining)
        alloc[p] = n
        remaining -= n
    for p in pairs:
        if remaining <= 0: break
        alloc[p] += 1
        remaining -= 1
    return alloc


def adjacent_load_aware(grid, traffic, total_budget, bw_per_link=32):
    """Load-aware on adjacent pairs only."""
    pairs = grid.get_adj_pairs()
    link_set = set(pairs)
    load = compute_load_with_express(grid, traffic, link_set)

    weights = {p: load.get(p, 0) for p in pairs}
    total_w = sum(weights.values())

    alloc = {p: 1 for p in pairs}
    remaining = total_budget - len(pairs)
    if remaining <= 0 or total_w <= 0:
        return alloc

    for p in pairs:
        extra = int(round(weights[p] / total_w * remaining))
        alloc[p] += extra

    # Fix total
    current = sum(alloc.values())
    diff = total_budget - current
    sorted_p = sorted(pairs, key=lambda p: -weights.get(p, 0))
    for p in sorted_p:
        if diff == 0: break
        if diff > 0:
            alloc[p] += 1; diff -= 1
        elif alloc[p] > 1:
            alloc[p] -= 1; diff += 1

    return alloc


def express_greedy(grid, traffic, total_budget, bw_per_link=32,
                   max_express_distance=3):
    """
    Greedy topology synthesis with express links.

    1. Start with 1 link per adjacent pair (connectivity)
    2. For each remaining link: try all possible placements (adj + express)
    3. Pick placement that reduces max_rho the most
    4. Re-route traffic after each addition
    """
    K = grid.K
    pairs_adj = grid.get_adj_pairs()

    # All possible express link pairs (within max distance)
    pairs_express = []
    for i in range(K):
        for j in range(i + 1, K):
            if (i, j) not in set(pairs_adj):
                hops = grid.get_hops(i, j)
                if hops <= max_express_distance:
                    pairs_express.append((i, j))

    # Start: 1 link per adjacent pair
    alloc = {p: 1 for p in pairs_adj}
    remaining = total_budget - len(pairs_adj)

    if remaining <= 0:
        return alloc

    # Current state
    link_set = set(alloc.keys())
    current_load = compute_load_with_express(grid, traffic, link_set)
    current_rho = compute_max_rho(current_load, alloc, bw_per_link)

    # Greedy: add one link at a time
    for step in range(remaining):
        best_pair = None
        best_rho = current_rho
        best_is_new = False

        # Try adding to each existing pair
        for p in list(alloc.keys()):
            test_alloc = dict(alloc)
            test_alloc[p] += 1
            test_load = compute_load_with_express(grid, traffic, set(test_alloc.keys()))
            rho = compute_max_rho(test_load, test_alloc, bw_per_link)
            if rho < best_rho:
                best_rho = rho
                best_pair = p
                best_is_new = False

        # Try adding express links
        for p in pairs_express:
            if p in alloc:
                # Already exists, try adding another
                test_alloc = dict(alloc)
                test_alloc[p] += 1
            else:
                test_alloc = dict(alloc)
                test_alloc[p] = 1

            test_load = compute_load_with_express(grid, traffic, set(test_alloc.keys()))
            rho = compute_max_rho(test_load, test_alloc, bw_per_link)
            if rho < best_rho:
                best_rho = rho
                best_pair = p
                best_is_new = (p not in alloc)

        if best_pair is None:
            break  # no improvement possible

        # Apply best choice
        if best_is_new:
            alloc[best_pair] = 1
            link_set.add(best_pair)
        else:
            alloc[best_pair] += 1

        current_load = compute_load_with_express(grid, traffic, link_set)
        current_rho = best_rho

    return alloc


# ============================================================
# Evaluation
# ============================================================

def evaluate_topology(grid, traffic, alloc, bw_per_link=32):
    """Evaluate a topology (may include express links)."""
    link_set = set(alloc.keys())
    load = compute_load_with_express(grid, traffic, link_set)

    max_rho = 0
    total_rho = 0
    n_links = 0
    n_express = 0
    total_link_count = 0

    pairs_adj = set(grid.get_adj_pairs())

    for pair, n in alloc.items():
        total_link_count += n
        ld = load.get(pair, 0)
        rho = ld / (n * bw_per_link) if n > 0 else 0
        max_rho = max(max_rho, rho)
        total_rho += rho
        n_links += 1
        if pair not in pairs_adj:
            n_express += 1

    return {
        'max_rho': max_rho,
        'avg_rho': total_rho / max(1, n_links),
        'n_links': n_links,
        'n_express': n_express,
        'total_link_count': total_link_count,
    }


# ============================================================
# Main experiment
# ============================================================

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

    configs = [
        ('K8',  8, (2,4), 8, 4, 4, 0.3),
        ('K16', 16, (4,4), 16, 4, 8, 0.3),
        ('K8big', 8, (2,4), 8, 8, 8, 0.4),
    ]

    outdir = Path('booksim_configs')

    for (label, K, gshape, nc, cpc, nsc, xcr) in configs:
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

        n_adj = len(grid.get_adj_pairs())

        print(f"\n{'='*90}")
        print(f"  {label}: K={K}, {gshape[0]}x{gshape[1]} grid, {n_adj} adj pairs")
        print(f"{'='*90}")

        for budget in [n_adj * 2, n_adj * 3, n_adj * 4]:
            print(f"\n  Budget={budget} ({budget/n_adj:.0f} links/adj_pair avg):")

            strategies = {
                'adj_uniform': adjacent_uniform(grid, budget),
                'adj_load': adjacent_load_aware(grid, traffic, budget),
                'express_greedy': express_greedy(grid, traffic, budget,
                                                 max_express_distance=3),
            }

            print(f"  {'Strategy':<18} {'max_ρ':>8} {'avg_ρ':>8} {'#pairs':>7} "
                  f"{'#express':>8} {'total_L':>8}")
            print(f"  {'-'*60}")

            for name, alloc in strategies.items():
                ev = evaluate_topology(grid, traffic, alloc)
                marker = " ★" if name == 'express_greedy' else ""
                print(f"  {name:<18} {ev['max_rho']:>8.2f} {ev['avg_rho']:>8.2f} "
                      f"{ev['n_links']:>7} {ev['n_express']:>8} "
                      f"{ev['total_link_count']:>8}{marker}")

            # Show express links chosen
            expr_alloc = strategies['express_greedy']
            adj_set = set(grid.get_adj_pairs())
            express_links = {p: n for p, n in expr_alloc.items() if p not in adj_set}
            if express_links:
                print(f"  Express links: {express_links}")

        # Generate BookSim configs for best budget
        budget = n_adj * 3
        for sname in ['adj_uniform', 'adj_load', 'express_greedy']:
            alloc = {
                'adj_uniform': adjacent_uniform(grid, budget),
                'adj_load': adjacent_load_aware(grid, traffic, budget),
                'express_greedy': express_greedy(grid, traffic, budget, max_express_distance=3),
            }[sname]
            cfg_name = f"expr_{label}_{sname}_L{budget}"
            # For BookSim: express links need special handling in anynet
            # gen_booksim_config handles adjacent pairs; we need custom for express
            _gen_express_booksim(cfg_name, grid, alloc, outdir)

        gen_traffic_matrix_file(grid, traffic,
                                str(outdir / f"traffic_expr_{label}.txt"), npc=4)

    # Run script
    _gen_run_script(outdir, configs)
    print(f"\n  Run: cd booksim_configs && bash run_express.sh")


def _gen_express_booksim(name, grid, alloc, outdir, chip_r=2, chip_c=2):
    """Generate BookSim config with express links."""
    K = grid.K
    npc = chip_r * chip_c

    lines = []
    for cid in range(K):
        base = cid * npc
        for r in range(chip_r):
            for c in range(chip_c):
                rid = base + r * chip_c + c
                parts = [f"router {rid}", f"node {rid}"]
                if c + 1 < chip_c:
                    parts.append(f"router {base + r * chip_c + c + 1} 1")
                if r + 1 < chip_r:
                    parts.append(f"router {base + (r + 1) * chip_c + c} 1")
                lines.append(" ".join(parts))

    inter_lines = []
    for (ci, cj), n_links in alloc.items():
        if n_links <= 0:
            continue
        hops = grid.get_hops(ci, cj)
        lat = max(2, hops * 2)  # express links: latency proportional to distance

        ci_base = ci * npc
        cj_base = cj * npc
        # Connect border routers
        n = min(n_links, chip_r, chip_c)
        for k in range(n):
            r_ci = ci_base + k  # simplified: use first k routers
            r_cj = cj_base + k
            inter_lines.append(f"router {r_ci} router {r_cj} {lat}")

    outdir = Path(outdir)
    with open(outdir / f"{name}.anynet", "w") as f:
        for l in lines: f.write(l + "\n")
        for l in inter_lines: f.write(l + "\n")

    with open(outdir / f"{name}.cfg", "w") as f:
        f.write(f"topology = anynet;\nnetwork_file = {name}.anynet;\n"
                "routing_function = min;\nnum_vcs = 8;\nvc_buf_size = 16;\n"
                "wait_for_tail_credit = 0;\nvc_allocator = separable_input_first;\n"
                "sw_allocator = separable_input_first;\nalloc_iters = 3;\n"
                "credit_delay = 1;\nrouting_delay = 0;\nvc_alloc_delay = 1;\n"
                "sw_alloc_delay = 1;\ninput_speedup = 2;\noutput_speedup = 1;\n"
                "internal_speedup = 2.0;\ntraffic = uniform;\npacket_size = 8;\n"
                "sim_type = latency;\nsample_period = 10000;\nwarmup_periods = 3;\n"
                "max_samples = 10;\ndeadlock_warn_timeout = 51200;\n"
                "injection_rate = 0.02;\n")

    return len(inter_lines)


def _gen_run_script(outdir, configs):
    outdir = Path(outdir)
    with open(outdir / 'run_express.sh', 'w') as f:
        f.write("#!/bin/bash\nset -e\n")
        f.write('BOOKSIM="../booksim2/src/booksim"\n')
        f.write('RESULTS="../results/express_links"\nmkdir -p "$RESULTS"\n')
        f.write('echo "config,rate,latency,throughput" > "$RESULTS/summary.csv"\n')
        f.write('RATES="0.001 0.002 0.003 0.005 0.007 0.01 0.015 0.02"\n\n')

        for (label, K, gshape, nc, cpc, nsc, xcr) in configs:
            n_adj = len(ChipletGrid(*gshape).get_adj_pairs())
            budget = n_adj * 3
            for sname in ['adj_uniform', 'adj_load', 'express_greedy']:
                cfg = f"expr_{label}_{sname}_L{budget}"
                traf = f"traffic_expr_{label}.txt"
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


if __name__ == '__main__':
    main()
