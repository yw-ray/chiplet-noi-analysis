"""
Traffic-Aware NoI Topology Synthesis
=====================================

Given a chiplet partition + workload traffic + link budget,
find the optimal inter-chiplet link allocation.

Three strategies:
  1. Uniform: L / n_pairs links per pair
  2. Traffic-proportional: links ∝ direct traffic T[i][j]
  3. Load-aware (ours): links ∝ actual link load (includes multi-hop routing)

Validated with BookSim cycle-accurate simulation.
"""

import math
import numpy as np
from pathlib import Path


class ChipletGrid:
    def __init__(self, rows, cols):
        self.rows = rows
        self.cols = cols
        self.K = rows * cols
        self.positions = {}
        for r in range(rows):
            for c in range(cols):
                self.positions[r * cols + c] = (r, c)
        self.adjacent = {}
        for cid in range(self.K):
            r, c = self.positions[cid]
            self.adjacent[cid] = [nr * cols + nc
                                  for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]
                                  for nr, nc in [(r+dr, c+dc)]
                                  if 0 <= nr < rows and 0 <= nc < cols]

    def get_hops(self, c1, c2):
        r1, c1p = self.positions[c1]
        r2, c2p = self.positions[c2]
        return abs(r1 - r2) + abs(c1p - c2p)

    def get_adj_pairs(self):
        return [(i, j) for i in range(self.K) for j in self.adjacent[i] if j > i]

    def shortest_path(self, src, dst):
        """Manhattan routing path."""
        path = [src]
        r, c = self.positions[src]
        rt, ct = self.positions[dst]
        while r != rt or c != ct:
            if r < rt: r += 1
            elif r > rt: r -= 1
            elif c < ct: c += 1
            elif c > ct: c -= 1
            path.append(r * self.cols + c)
        return path


# ============================================================
# Load computation
# ============================================================

def compute_link_load(grid, traffic):
    """
    Compute actual load on each adjacent link, including multi-hop traffic.

    Returns: load matrix (K×K) where load[a][b] = total traffic crossing link (a,b)
    """
    K = grid.K
    load = np.zeros((K, K))

    for i in range(K):
        for j in range(i + 1, K):
            if traffic[i][j] <= 0:
                continue
            path = grid.shortest_path(i, j)
            for h in range(len(path) - 1):
                a, b = min(path[h], path[h+1]), max(path[h], path[h+1])
                load[a][b] += traffic[i][j]

    return load


# ============================================================
# Link allocation strategies
# ============================================================

def allocate_uniform(grid, total_budget):
    """Equal links to all adjacent pairs."""
    pairs = grid.get_adj_pairs()
    per = max(1, total_budget // len(pairs))
    alloc = {}
    remaining = total_budget
    for p in pairs:
        n = min(per, remaining)
        alloc[p] = n
        remaining -= n
    # Distribute leftover
    for p in pairs:
        if remaining <= 0:
            break
        alloc[p] += 1
        remaining -= 1
    return alloc


def allocate_traffic_proportional(grid, traffic, total_budget):
    """Links proportional to direct inter-chiplet traffic."""
    pairs = grid.get_adj_pairs()
    # Only direct traffic between adjacent pairs
    weights = {p: traffic[p[0]][p[1]] for p in pairs}
    return _proportional_alloc(pairs, weights, total_budget)


def allocate_load_aware(grid, traffic, total_budget):
    """Links proportional to actual link load (includes multi-hop)."""
    load = compute_link_load(grid, traffic)
    pairs = grid.get_adj_pairs()
    weights = {p: load[p[0]][p[1]] for p in pairs}
    return _proportional_alloc(pairs, weights, total_budget)


def allocate_minmax_optimal(grid, traffic, total_budget, bw_per_link=32):
    """
    Optimal: minimize max utilization via binary search.

    Binary search on target ρ_max. For each ρ_max, compute required links:
      n[a,b] = ceil(load[a,b] / (ρ_max × bw_per_link))
    Check if Σ n[a,b] ≤ budget.
    """
    load = compute_link_load(grid, traffic)
    pairs = grid.get_adj_pairs()
    loaded_pairs = [(p, load[p[0]][p[1]]) for p in pairs if load[p[0]][p[1]] > 0]
    unloaded_pairs = [p for p in pairs if load[p[0]][p[1]] <= 0]

    if not loaded_pairs:
        return allocate_uniform(grid, total_budget)

    # Binary search on ρ_max
    lo, hi = 0.01, 1000.0
    best_alloc = None

    for _ in range(50):
        mid = (lo + hi) / 2
        needed = 0
        alloc = {}
        for p, ld in loaded_pairs:
            n = max(1, math.ceil(ld / (mid * bw_per_link)))
            alloc[p] = n
            needed += n
        for p in unloaded_pairs:
            alloc[p] = 1
            needed += 1

        if needed <= total_budget:
            best_alloc = dict(alloc)
            hi = mid  # try lower ρ
            # Distribute remaining
            remaining = total_budget - needed
            # Give extra to highest-load pairs
            sorted_pairs = sorted(loaded_pairs, key=lambda x: -x[1])
            for p, _ in sorted_pairs:
                if remaining <= 0:
                    break
                best_alloc[p] += 1
                remaining -= 1
        else:
            lo = mid  # need higher ρ

    if best_alloc is None:
        return allocate_load_aware(grid, traffic, total_budget)

    return best_alloc


def _proportional_alloc(pairs, weights, total_budget):
    """Allocate proportionally with minimum 1 per pair."""
    alloc = {p: 1 for p in pairs}
    remaining = total_budget - len(pairs)
    if remaining <= 0:
        return alloc

    total_w = sum(max(0, weights[p]) for p in pairs)
    if total_w <= 0:
        return alloc

    for p in pairs:
        w = max(0, weights[p])
        extra = int(round(w / total_w * remaining))
        alloc[p] += extra

    # Fix total
    current = sum(alloc.values())
    diff = total_budget - current
    sorted_pairs = sorted(pairs, key=lambda p: -weights.get(p, 0))
    for p in sorted_pairs:
        if diff == 0:
            break
        if diff > 0:
            alloc[p] += 1
            diff -= 1
        elif alloc[p] > 1:
            alloc[p] -= 1
            diff += 1

    return alloc


# ============================================================
# Evaluation: compute max utilization and per-link stats
# ============================================================

def evaluate_allocation(grid, traffic, alloc, bw_per_link=32):
    """Evaluate a link allocation: compute per-link utilization."""
    K = grid.K
    load = compute_link_load(grid, traffic)
    pairs = grid.get_adj_pairs()

    results = []
    max_rho = 0
    total_links = 0

    for p in pairs:
        n = alloc.get(p, 0)
        total_links += n
        bw = n * bw_per_link
        ld = load[p[0]][p[1]]
        rho = ld / bw if bw > 0 else (float('inf') if ld > 0 else 0)
        max_rho = max(max_rho, rho)
        results.append({
            'pair': p, 'links': n, 'bw': bw,
            'load': ld, 'rho': rho,
            'status': 'OK' if rho < 0.8 else 'WARN' if rho < 1.0 else 'SAT',
        })

    return {
        'max_rho': max_rho,
        'total_links': total_links,
        'per_link': results,
        'n_saturated': sum(1 for r in results if r['rho'] >= 1.0),
        'avg_rho': np.mean([r['rho'] for r in results if r['rho'] < float('inf')]),
    }


# ============================================================
# BookSim config generation
# ============================================================

def gen_booksim_config(name, grid, alloc, chip_rows=2, chip_cols=2, outdir='.'):
    """Generate BookSim anynet topology + config."""
    K = grid.K
    npc = chip_rows * chip_cols

    lines = []
    for cid in range(K):
        base = cid * npc
        for r in range(chip_rows):
            for c in range(chip_cols):
                rid = base + r * chip_cols + c
                parts = [f"router {rid}", f"node {rid}"]
                if c + 1 < chip_cols:
                    parts.append(f"router {base + r * chip_cols + c + 1} 1")
                if r + 1 < chip_rows:
                    parts.append(f"router {base + (r + 1) * chip_cols + c} 1")
                lines.append(" ".join(parts))

    inter_lines = []
    for (ci, cj), n_links in alloc.items():
        if n_links <= 0:
            continue
        ri, cip = grid.positions[ci]
        rj, cjp = grid.positions[cj]
        ci_base = ci * npc
        cj_base = cj * npc

        if cjp > cip:
            ci_border = [ci_base + r * chip_cols + (chip_cols-1) for r in range(chip_rows)]
            cj_border = [cj_base + r * chip_cols for r in range(chip_rows)]
        elif cjp < cip:
            ci_border = [ci_base + r * chip_cols for r in range(chip_rows)]
            cj_border = [cj_base + r * chip_cols + (chip_cols-1) for r in range(chip_rows)]
        elif rj > ri:
            ci_border = [ci_base + (chip_rows-1) * chip_cols + c for c in range(chip_cols)]
            cj_border = [cj_base + c for c in range(chip_cols)]
        else:
            ci_border = [ci_base + c for c in range(chip_cols)]
            cj_border = [cj_base + (chip_rows-1) * chip_cols + c for c in range(chip_cols)]

        n = min(n_links, len(ci_border), len(cj_border))
        for k in range(n):
            inter_lines.append(f"router {ci_border[k]} router {cj_border[k]} 2")

    outdir = Path(outdir)
    with open(outdir / f"{name}.anynet", "w") as f:
        for l in lines:
            f.write(l + "\n")
        for l in inter_lines:
            f.write(l + "\n")

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

    return len(inter_lines)


# ============================================================
# Generate traffic matrix file for BookSim custom traffic
# ============================================================

def gen_traffic_matrix_file(grid, traffic, filepath, npc=4):
    """Generate BookSim traffic matrix file from chiplet-level traffic."""
    K = grid.K
    total_nodes = K * npc
    node_traffic = np.zeros((total_nodes, total_nodes), dtype=int)

    for ci in range(K):
        for cj in range(K):
            if ci == cj or traffic[ci][cj] <= 0:
                continue
            weight = max(1, int(traffic[ci][cj] / (npc * npc)))
            for ni in range(npc):
                for nj in range(npc):
                    src = ci * npc + ni
                    dst = cj * npc + nj
                    if src != dst:
                        node_traffic[src][dst] += weight

    # Small intra-chiplet background
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
# Main experiment
# ============================================================

def main():
    import sys
    sys.path.insert(0, str(Path(__file__).parent / 'rl_partitioner'))
    from envs.realistic_netlist import create_realistic_accelerator
    from sa_coopt_v2 import constrained_spectral

    def balanced_spectral(G, K, grid, con, seed=42):
        asgn = constrained_spectral(G, K, grid, con, seed)
        nodes = sorted(G.nodes)
        for _ in range(30):
            compute = np.zeros(K)
            for n in nodes:
                compute[asgn[n]] += G.nodes[n]['compute']
            o, u = np.argmax(compute), np.argmin(compute)
            if compute[o] < compute[u] * 1.5:
                break
            cands = [n for n in nodes if asgn[n] == o]
            if not cands:
                break
            best_n, best_c = None, float('inf')
            for n in cands:
                ic = sum(G[n][nb]['bandwidth'] for nb in G.neighbors(n)
                         if asgn[nb] == o and n != nb)
                if ic < best_c:
                    best_c, best_n = ic, n
            if best_n:
                asgn[best_n] = u
        return asgn

    configs = [
        ('K=4 2×2', 4, (2,2), 4, 4, 4, 0.3),
        ('K=8 2×4', 8, (2,4), 8, 4, 4, 0.3),
        ('K=8 big', 8, (2,4), 8, 8, 8, 0.4),
    ]

    outdir = Path(__file__).parent / 'booksim_configs'

    for (label, K, gshape, nc, cpc, nsc, xcr) in configs:
        grid = ChipletGrid(*gshape)
        G, con = create_realistic_accelerator(
            n_compute_clusters=nc, cores_per_cluster=cpc,
            n_shared_cache=nsc, n_hbm_ctrl=4,
            n_reduction_units=max(2, K//4), cross_cluster_ratio=xcr)

        asgn = balanced_spectral(G, K, grid, con)

        # Compute traffic matrix
        traffic = np.zeros((K, K))
        for u, v, d in G.edges(data=True):
            cu, cv = asgn[u], asgn[v]
            if cu != cv:
                traffic[cu][cv] += d['bandwidth']
                traffic[cv][cu] += d['bandwidth']

        print(f"\n{'='*80}")
        print(f"  {label}: N={G.number_of_nodes()}, E={G.number_of_edges()}")
        print(f"{'='*80}")

        # Sweep link budgets
        for budget in [K * 2, K * 4, K * 8]:
            print(f"\n  --- Link budget: {budget} ---")

            strategies = {
                'uniform': allocate_uniform(grid, budget),
                'traffic_prop': allocate_traffic_proportional(grid, traffic, budget),
                'load_aware': allocate_load_aware(grid, traffic, budget),
                'minmax_opt': allocate_minmax_optimal(grid, traffic, budget),
            }

            print(f"  {'Strategy':<18} {'max_ρ':>8} {'avg_ρ':>8} {'#SAT':>5} "
                  f"{'Links':>6}")
            print(f"  {'─'*50}")

            for name, alloc in strategies.items():
                ev = evaluate_allocation(grid, traffic, alloc)
                marker = " ★" if name == 'minmax_opt' else ""
                print(f"  {name:<18} {ev['max_rho']:>8.2f} {ev['avg_rho']:>8.2f} "
                      f"{ev['n_saturated']:>5} {ev['total_links']:>6}{marker}")

            # Generate BookSim configs for this budget
            safe = label.replace(' ', '_').replace('×', 'x').replace('=', '')
            for sname, alloc in strategies.items():
                cfg_name = f"noi_{safe}_{sname}_L{budget}"
                n_inter = gen_booksim_config(cfg_name, grid, alloc, outdir=outdir)

            # Generate traffic matrix file
            traf_file = outdir / f"traffic_{safe}.txt"
            gen_traffic_matrix_file(grid, traffic, traf_file)

    # Generate run script
    _gen_run_script(outdir, configs)
    print(f"\n  Run: cd booksim_configs && bash run_noi_synthesis.sh")


def _gen_run_script(outdir, configs):
    with open(outdir / "run_noi_synthesis.sh", "w") as f:
        f.write("#!/bin/bash\nset -e\n")
        f.write('BOOKSIM="../booksim2/src/booksim"\nDIR="$(dirname "$0")"\n')
        f.write('RESULTS="${DIR}/../results/noi_synthesis"\nmkdir -p "$RESULTS"\n')
        f.write('echo "config,traffic,rate,latency,throughput" > "$RESULTS/summary.csv"\n\n')
        f.write('RATES="0.005 0.01 0.015 0.02 0.025 0.03 0.04 0.05"\n\n')

        for (label, K, gshape, nc, cpc, nsc, xcr) in configs:
            safe_label = label.replace(' ', '_').replace('×', 'x').replace('=', '')
            traf_file = f"traffic_{safe_label}.txt"

            for budget in [K * 2, K * 4, K * 8]:
                for strat in ['uniform', 'traffic_prop', 'load_aware', 'minmax_opt']:
                    cfg = f"noi_{safe_label}_{strat}_L{budget}"
                    f.write(f'echo "=== {cfg} ==="\n')
                    f.write(f'for rate in $RATES; do\n')
                    f.write(f'  out="$RESULTS/{cfg}_${{rate}}.log"\n')
                    f.write(f'  cd "$DIR"\n')
                    f.write(f'  timeout 120 $BOOKSIM "{cfg}.cfg" injection_rate="$rate" ')
                    f.write(f'"traffic=matrix({traf_file})" > "$out" 2>&1 || true\n')
                    f.write(f'  lat=$(grep "Packet latency average" "$out" | tail -1 | awk \'{{print $5}}\')\n')
                    f.write(f'  tput=$(grep "Accepted packet rate average" "$out" | tail -1 | awk \'{{print $6}}\')\n')
                    f.write('  [ -n "$lat" ] && [ -n "$tput" ] && ')
                    f.write(f'echo "{cfg},matrix,${{rate}},$lat,$tput" >> "$RESULTS/summary.csv" && ')
                    f.write('printf "  rate=%-6s lat=%-10s tput=%s\\n" "$rate" "$lat" "$tput" ')
                    f.write('|| printf "  rate=%-6s (fail)\\n" "$rate"\n')
                    f.write(f'done\necho ""\n\n')

        f.write('echo "Done. Results: $RESULTS/summary.csv"\n')


if __name__ == '__main__':
    main()
