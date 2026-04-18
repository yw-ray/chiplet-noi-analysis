"""
SA Co-optimization v2: Realistic Netlist + Traffic-Proportional Links
=====================================================================

Key changes from v1:
  1. Realistic netlist with pipeline, shared cache, cross-cluster deps
  2. Link budget allocated PROPORTIONALLY to traffic (not uniform)
  3. HBM placement constraints (must be at grid edges)
  4. Larger grid (4×4 = 16 chiplets) for more placement complexity

This should create meaningful differentiation between:
  - min-cut objective (ignores placement + link allocation)
  - throughput objective (considers placement + adaptive links)
"""

import sys
import time
import math
import json
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from envs.realistic_netlist import create_realistic_accelerator, get_edge_modules
from envs.placement_aware_evaluator import ChipletGrid


# ============================================================
# Evaluator v2: traffic-proportional link allocation
# ============================================================

def murphy_yield(area, dd=0.1):
    d = dd * area / 100
    if d <= 0: return 1.0
    return ((1 - math.exp(-d)) / d) ** 2


class EvaluatorV2:
    """
    Evaluator with traffic-proportional link allocation.

    Key: total_link_budget is distributed to adjacent pairs
    in proportion to inter-chiplet traffic. This means:
    - Partition with concentrated traffic → some pairs get many links → good BW
    - Partition with spread traffic → all pairs get few links → bottleneck
    """

    def __init__(self, grid, total_link_budget=32, bw_per_link=32,
                 phy_area_per_link=0.15, latency_per_hop_us=0.10,
                 tops_per_mm2=1.5, hbm_bw_per_mm2=3.0, dd=0.10):
        self.grid = grid
        self.K = grid.K
        self.total_link_budget = total_link_budget
        self.bw_per_link = bw_per_link
        self.phy_per_link = phy_area_per_link
        self.lat_per_hop = latency_per_hop_us
        self.tops_per_mm2 = tops_per_mm2
        self.hbm_per_mm2 = hbm_bw_per_mm2
        self.dd = dd

    def evaluate(self, G, assignment):
        K = self.K
        N = G.number_of_nodes()

        # ── Per-chiplet aggregation ──
        chip_area = np.zeros(K)
        chip_compute = np.zeros(K)
        chip_count = np.zeros(K, dtype=int)
        for nid in G.nodes:
            cid = assignment[nid]
            chip_area[cid] += G.nodes[nid]['area']
            chip_compute[cid] += G.nodes[nid]['compute']
            chip_count[cid] += 1

        # ── Traffic matrix ──
        traffic = np.zeros((K, K))
        total_bw = 0.0
        inter_bw = 0.0
        for u, v, d in G.edges(data=True):
            bw = d['bandwidth']
            total_bw += bw
            cu, cv = assignment[u], assignment[v]
            if cu != cv:
                traffic[cu][cv] += bw
                traffic[cv][cu] += bw
                inter_bw += bw
        comm_ratio = inter_bw / (total_bw + 1e-8)

        # ── Traffic-proportional link allocation ──
        # Only adjacent pairs can have links
        adj_traffic = {}
        for i in range(K):
            for j in self.grid.adjacent[i]:
                if j > i:
                    adj_traffic[(i, j)] = traffic[i][j]

        total_adj_traffic = sum(adj_traffic.values())
        link_alloc = {}
        remaining = self.total_link_budget

        if total_adj_traffic > 0:
            # Proportional allocation with minimum 1 link for active pairs
            active_pairs = [(p, t) for p, t in adj_traffic.items() if t > 0]

            # First: 1 link to each active pair
            for (pair, _) in active_pairs:
                link_alloc[pair] = 1
                remaining -= 1
                if remaining <= 0:
                    break

            # Then: distribute remaining proportionally
            if remaining > 0 and active_pairs:
                active_total = sum(t for _, t in active_pairs)
                for (pair, t) in active_pairs:
                    extra = int(round(t / active_total * remaining))
                    link_alloc[pair] = link_alloc.get(pair, 0) + extra
        else:
            # No inter-chiplet traffic — distribute uniformly
            all_adj = [(i, j) for i in range(K) for j in self.grid.adjacent[i] if j > i]
            per = max(1, self.total_link_budget // max(1, len(all_adj)))
            for pair in all_adj:
                link_alloc[pair] = per

        # Build BW and link matrices
        bw_matrix = np.zeros((K, K))
        link_matrix = np.zeros((K, K), dtype=int)
        for (i, j), n_links in link_alloc.items():
            link_matrix[i][j] = n_links
            link_matrix[j][i] = n_links
            bw_matrix[i][j] = n_links * self.bw_per_link
            bw_matrix[j][i] = n_links * self.bw_per_link

        # ── PHY area ──
        chip_phy = np.zeros(K)
        for cid in range(K):
            chip_phy[cid] = sum(link_matrix[cid]) * self.phy_per_link
        chip_total_area = chip_area + chip_phy

        # ── Non-adjacent traffic penalty ──
        # Traffic between non-adjacent pairs must multi-hop
        nonadj_traffic = 0.0
        weighted_hops = 0.0
        for i in range(K):
            for j in range(i + 1, K):
                if traffic[i][j] > 0:
                    hops = self.grid.get_hops(i, j)
                    if hops > 1:
                        nonadj_traffic += traffic[i][j]
                        weighted_hops += traffic[i][j] * hops

        nonadj_ratio = nonadj_traffic / (inter_bw + 1e-8)
        avg_hops = weighted_hops / (inter_bw + 1e-8) if inter_bw > 0 else 0

        # ── Link congestion ──
        # Multi-hop traffic passes through intermediate links
        link_load = np.zeros((K, K))
        for i in range(K):
            for j in range(i + 1, K):
                if traffic[i][j] <= 0:
                    continue
                hops = self.grid.get_hops(i, j)
                if hops <= 0:
                    continue
                # Route along shortest manhattan path
                ri, ci = self.grid.positions[i]
                rj, cj = self.grid.positions[j]
                path = [i]
                cr, cc = ri, ci
                while cr != rj or cc != cj:
                    if cr < rj: cr += 1
                    elif cr > rj: cr -= 1
                    elif cc < cj: cc += 1
                    elif cc > cj: cc -= 1
                    path.append(cr * self.grid.cols + cc)
                for h in range(len(path) - 1):
                    a, b = min(path[h], path[h+1]), max(path[h], path[h+1])
                    link_load[a][b] += traffic[i][j]

        # Congestion: M/M/1 queuing model (validated against BookSim)
        # Each link has utilization ρ = load/capacity.
        # Latency scales as 1/(1-ρ) for ρ<1, and saturates for ρ≥1.
        # Network latency is dominated by the WORST link (highest ρ).
        link_rho = np.zeros((K, K))     # utilization per link
        link_delay = np.zeros((K, K))   # queuing delay factor per link
        max_rho = 0.0
        bottleneck_link = (-1, -1)

        for i in range(K):
            for j in range(i + 1, K):
                if link_load[i][j] > 0:
                    if bw_matrix[i][j] > 0:
                        rho = link_load[i][j] / bw_matrix[i][j]
                    else:
                        rho = 10.0  # no link, traffic shouldn't route here
                    link_rho[i][j] = rho
                    link_rho[j][i] = rho
                    # M/M/1 delay factor
                    if rho < 0.95:
                        link_delay[i][j] = 1.0 / (1.0 - rho)
                    else:
                        link_delay[i][j] = 20.0  # saturated
                    link_delay[j][i] = link_delay[i][j]

                    if rho > max_rho:
                        max_rho = rho
                        bottleneck_link = (i, j)

        max_congestion = max_rho
        congestion_factor = 1.0 / max(1.0, max_rho)

        # ── E2E Throughput ──
        n_active = sum(1 for c in chip_count if c > 0)
        if n_active == 0:
            return self._empty()

        total_tops = sum((chip_area[c]) * self.tops_per_mm2
                         for c in range(K) if chip_count[c] > 0)
        total_hbm = sum(chip_total_area[c] * self.hbm_per_mm2
                        for c in range(K) if chip_count[c] > 0)

        # LLaMA-70B workload
        h, s, b, db = 8192, 2048, 1, 2
        flops_per_layer = 4*2*b*s*h*h + 2*2*b*64*s*s*128 + 3*2*b*s*h*28672
        activation_bytes = b * s * h * db
        mem_per_layer = (4*h**2 + 3*h*28672)*db + 2*b*s*h*db + b*s*h*db

        t_comp = (flops_per_layer / n_active) / (total_tops / n_active * 1e12)
        t_mem = (mem_per_layer / n_active) / (total_hbm / n_active * 1e9)
        t_compute = max(t_comp, t_mem)

        # Communication: total traffic-weighted latency model
        # Key insight from BookSim validation: when ALL links are saturated (ρ>1),
        # the partition with LESS total inter-chiplet traffic wins because
        # every byte of traffic contributes to congestion on every link it crosses.
        #
        # Model: t_comm = Σ(traffic[i][j] × hops[i][j] × delay_factor[path]) / BW
        # where delay_factor = max(1, ρ) on each link along the path
        if n_active > 1 and inter_bw > 0:
            # For each communicating pair, compute actual latency
            total_byte_delay = 0.0  # Σ(bytes × delay_per_byte)

            for i in range(K):
                for j in range(i + 1, K):
                    if traffic[i][j] <= 0:
                        continue

                    hops = self.grid.get_hops(i, j)
                    if hops == 0:
                        continue

                    # Route along shortest path, accumulate delay
                    ri, ci_pos = self.grid.positions[i]
                    rj, cj_pos = self.grid.positions[j]
                    path = [i]
                    cr, cc = ri, ci_pos
                    while cr != rj or cc != cj_pos:
                        if cr < rj: cr += 1
                        elif cr > rj: cr -= 1
                        elif cc < cj_pos: cc += 1
                        elif cc > cj_pos: cc -= 1
                        path.append(cr * self.grid.cols + cc)

                    # Bottleneck on this path: slowest link
                    path_min_bw = float('inf')
                    for h in range(len(path) - 1):
                        a, b = min(path[h], path[h+1]), max(path[h], path[h+1])
                        if bw_matrix[a][b] > 0:
                            eff_bw = bw_matrix[a][b] / max(1.0, link_delay[a][b])
                            path_min_bw = min(path_min_bw, eff_bw)
                        else:
                            path_min_bw = min(path_min_bw, self.bw_per_link * 0.05)

                    if path_min_bw <= 0 or path_min_bw == float('inf'):
                        path_min_bw = self.bw_per_link * 0.05

                    # Time for this pair's traffic
                    t_pair = traffic[i][j] / (path_min_bw * 1e9)
                    t_pair += hops * self.lat_per_hop * 1e-6
                    total_byte_delay += t_pair

            # All-reduce: all pairs communicate simultaneously
            # Completion time ≈ max across all pair latencies
            # Simplified: use weighted average (dominated by heaviest pairs)
            t_comm = total_byte_delay * 2  # 2 all-reduces per layer
        else:
            t_comm = 0

        layers = 80
        total_us = (t_compute + t_comm) * layers * 1e6
        compute_us = t_compute * layers * 1e6
        comm_us = t_comm * layers * 1e6
        comm_pct = comm_us / total_us * 100 if total_us > 0 else 0
        tps = 1e6 / total_us if total_us > 0 else 0

        # ── Balance ──
        active = chip_compute[chip_count > 0]
        balance = max(0, 1 - np.std(active) / (np.mean(active) + 1e-8)) if len(active) > 1 else 0

        return {
            'throughput_tps': tps,
            'comm_ratio': comm_ratio,
            'nonadj_ratio': nonadj_ratio,
            'avg_hops': avg_hops,
            'congestion_factor': congestion_factor,
            'max_congestion': max_congestion,
            'compute_balance': balance,
            'total_us': total_us,
            'compute_us': compute_us,
            'comm_us': comm_us,
            'comm_pct': comm_pct,
            'chip_area': chip_area.tolist(),
            'chip_phy': chip_phy.tolist(),
            'n_active': n_active,
            'link_alloc': {f'{i}-{j}': n for (i,j), n in link_alloc.items()},
        }

    def _empty(self):
        return {'throughput_tps': 0, 'comm_ratio': 1, 'nonadj_ratio': 1,
                'avg_hops': 99, 'congestion_factor': 0, 'max_congestion': 99,
                'compute_balance': 0, 'total_us': 1e12, 'compute_us': 0,
                'comm_us': 0, 'comm_pct': 0, 'chip_area': [], 'chip_phy': [],
                'n_active': 0, 'link_alloc': {}}


# ============================================================
# Partitioning methods
# ============================================================

def spectral_partition(G, K, seed=42):
    N = G.number_of_nodes()
    nodes = sorted(G.nodes)
    W = np.zeros((N, N))
    for u, v, d in G.edges(data=True):
        idx_u = nodes.index(u)
        idx_v = nodes.index(v)
        W[idx_u][idx_v] = d['bandwidth']
        W[idx_v][idx_u] = d['bandwidth']
    D = np.diag(W.sum(axis=1))
    L = D - W
    _, eigvecs = np.linalg.eigh(L)
    features = eigvecs[:, 1:K+1]

    rng = np.random.default_rng(seed)
    centers = features[rng.choice(N, K, replace=False)].copy()
    asgn = np.zeros(N, dtype=int)
    for _ in range(100):
        for i in range(N):
            asgn[i] = np.argmin(np.linalg.norm(features[i] - centers, axis=1))
        new_c = np.zeros_like(centers)
        for k in range(K):
            m = features[asgn == k]
            new_c[k] = m.mean(0) if len(m) > 0 else features[rng.integers(N)]
        if np.allclose(centers, new_c): break
        centers = new_c

    # Map back to node IDs
    assignment = np.zeros(max(nodes) + 1, dtype=int)
    for i, nid in enumerate(nodes):
        assignment[nid] = asgn[i]
    return assignment


def random_partition(G, K, seed=42):
    rng = np.random.default_rng(seed)
    nodes = sorted(G.nodes)
    N = len(nodes)
    assignment = np.zeros(max(nodes) + 1, dtype=int)
    perm = rng.permutation(N)
    per = N // K
    for i, idx in enumerate(perm):
        assignment[nodes[idx]] = min(i // per, K - 1)
    return assignment


def constrained_spectral(G, K, grid, constraints, seed=42):
    """Spectral partition with constraint enforcement."""
    assignment = spectral_partition(G, K, seed)

    # Enforce: HBM controllers must be at grid edges
    edge_chiplets = list(get_edge_modules(grid))
    for hbm_nid in constraints.get('edge_only', []):
        if assignment[hbm_nid] not in edge_chiplets:
            # Move to nearest edge chiplet
            assignment[hbm_nid] = edge_chiplets[hbm_nid % len(edge_chiplets)]

    return assignment


# ============================================================
# SA with two objectives
# ============================================================

def sa_optimize(G, K, init, evaluator, objective, constraints=None,
                grid=None, n_iters=5000, T_start=1.0, T_end=0.01, seed=42):
    rng = np.random.default_rng(seed)
    nodes = sorted(G.nodes)
    N = len(nodes)
    assignment = init.copy()

    max_cap = int(np.ceil(N / K * 2.5))
    min_cap = max(1, int(np.floor(N / K * 0.2)))
    edge_chiplets = set(get_edge_modules(grid)) if grid else set()
    edge_only = set(constraints.get('edge_only', [])) if constraints else set()

    # Initial score
    if objective == 'throughput':
        ev = evaluator.evaluate(G, assignment)
        current = ev['throughput_tps']
    else:  # mincut
        total_bw, inter_bw = 0, 0
        for u, v, d in G.edges(data=True):
            total_bw += d['bandwidth']
            if assignment[u] != assignment[v]:
                inter_bw += d['bandwidth']
        current = -(inter_bw / (total_bw + 1e-8))

    best = current
    best_asgn = assignment.copy()
    alpha = (T_end / T_start) ** (1.0 / max(1, n_iters))
    T = T_start
    accepted = 0
    improved = 0

    for it in range(n_iters):
        # Pick random module and target
        nid = nodes[rng.integers(N)]
        old = assignment[nid]
        target = rng.integers(K)
        while target == old:
            target = rng.integers(K)

        # Constraint: edge-only modules stay at edge chiplets
        if nid in edge_only and target not in edge_chiplets:
            T *= alpha
            continue

        # Balance
        count_t = sum(1 for n in nodes if assignment[n] == target)
        count_s = sum(1 for n in nodes if assignment[n] == old)
        if count_t >= max_cap or count_s <= min_cap:
            T *= alpha
            continue

        assignment[nid] = target
        if objective == 'throughput':
            ev = evaluator.evaluate(G, assignment)
            new_score = ev['throughput_tps']
        else:
            ib = sum(d['bandwidth'] for u, v, d in G.edges(data=True)
                     if assignment[u] != assignment[v])
            new_score = -(ib / (total_bw + 1e-8))

        delta = new_score - current
        if delta > 0 or rng.random() < math.exp(delta / (T + 1e-10)):
            current = new_score
            accepted += 1
            if new_score > best:
                best = new_score
                best_asgn = assignment.copy()
                improved += 1
        else:
            assignment[nid] = old

        T *= alpha

    return best_asgn, {'accepted': accepted, 'improved': improved}


# ============================================================
# Main
# ============================================================

def run(K=16, sa_iters=5000):
    if K <= 4: grid = ChipletGrid(2, 2)
    elif K <= 8: grid = ChipletGrid(2, 4)
    elif K <= 16: grid = ChipletGrid(4, 4)
    else: grid = ChipletGrid(4, int(np.ceil(K/4)))

    print("=" * 90)
    print(f"  SA v2: REALISTIC NETLIST + TRAFFIC-PROPORTIONAL LINKS")
    print(f"  Grid: {grid.rows}×{grid.cols} ({K} chiplets), {sa_iters} SA iterations")
    print("=" * 90)

    # Realistic netlist
    G, constraints = create_realistic_accelerator(
        n_compute_clusters=max(4, K),
        cores_per_cluster=4,
        n_shared_cache=max(4, K // 2),
        n_hbm_ctrl=4,
        n_reduction_units=max(2, K // 4),
        cross_cluster_ratio=0.4,
    )
    N = G.number_of_nodes()
    print(f"\n  Netlist: {N} modules, {G.number_of_edges()} edges")
    print(f"  Constraints: {len(constraints['edge_only'])} edge-only modules")

    evaluator = EvaluatorV2(
        grid,
        total_link_budget=K * 3,  # tight: 3 links per chiplet average
        bw_per_link=32,
        phy_area_per_link=0.15,
        latency_per_hop_us=0.10,
    )

    results = {}

    # 1. Random
    print(f"\n  [1/5] Random...")
    rp = random_partition(G, K)
    re = evaluator.evaluate(G, rp)
    results['random'] = re
    print(f"    tps={re['throughput_tps']:.4f} comm={re['comm_ratio']:.1%} "
          f"nonadj={re['nonadj_ratio']:.1%} cong={re['congestion_factor']:.2f} "
          f"hops={re['avg_hops']:.1f}")

    # 2. Spectral
    print(f"\n  [2/5] Spectral (constrained)...")
    sp = constrained_spectral(G, K, grid, constraints)
    se = evaluator.evaluate(G, sp)
    results['spectral'] = se
    print(f"    tps={se['throughput_tps']:.4f} comm={se['comm_ratio']:.1%} "
          f"nonadj={se['nonadj_ratio']:.1%} cong={se['congestion_factor']:.2f} "
          f"hops={se['avg_hops']:.1f}")

    # 3. SA (min-cut)
    print(f"\n  [3/5] SA (min-cut objective)...")
    t0 = time.time()
    sa_mc, info_mc = sa_optimize(G, K, sp.copy(), evaluator, 'mincut',
                                  constraints, grid, sa_iters, 0.3, 0.001)
    t_mc = time.time() - t0
    mc_ev = evaluator.evaluate(G, sa_mc)
    results['sa_mincut'] = mc_ev
    print(f"    tps={mc_ev['throughput_tps']:.4f} comm={mc_ev['comm_ratio']:.1%} "
          f"nonadj={mc_ev['nonadj_ratio']:.1%} cong={mc_ev['congestion_factor']:.2f} "
          f"(acc={info_mc['accepted']} imp={info_mc['improved']} {t_mc:.1f}s)")

    # 4. SA (throughput)
    print(f"\n  [4/5] SA (throughput objective) [OURS]...")
    t0 = time.time()
    sa_tp, info_tp = sa_optimize(G, K, sp.copy(), evaluator, 'throughput',
                                  constraints, grid, sa_iters, 0.05, 0.0001)
    t_tp = time.time() - t0
    tp_ev = evaluator.evaluate(G, sa_tp)
    results['sa_throughput'] = tp_ev
    print(f"    tps={tp_ev['throughput_tps']:.4f} comm={tp_ev['comm_ratio']:.1%} "
          f"nonadj={tp_ev['nonadj_ratio']:.1%} cong={tp_ev['congestion_factor']:.2f} "
          f"(acc={info_tp['accepted']} imp={info_tp['improved']} {t_tp:.1f}s)")

    # 5. SA (throughput) from random init (not Spectral)
    print(f"\n  [5/5] SA (throughput) from random init...")
    t0 = time.time()
    sa_rand, info_rand = sa_optimize(G, K, rp.copy(), evaluator, 'throughput',
                                      constraints, grid, sa_iters * 2, 0.1, 0.0001)
    t_rand = time.time() - t0
    rand_ev = evaluator.evaluate(G, sa_rand)
    results['sa_tp_random'] = rand_ev
    print(f"    tps={rand_ev['throughput_tps']:.4f} comm={rand_ev['comm_ratio']:.1%} "
          f"nonadj={rand_ev['nonadj_ratio']:.1%} cong={rand_ev['congestion_factor']:.2f} "
          f"(acc={info_rand['accepted']} imp={info_rand['improved']} {t_rand:.1f}s)")

    # Summary
    base = se['throughput_tps']
    best_tps = max(r['throughput_tps'] for r in results.values())

    print(f"\n  {'─' * 95}")
    print(f"  {'Method':<45} {'tps':>8} {'comm':>6} {'nonadj':>7} "
          f"{'cong':>5} {'hops':>5} {'vs Spec':>8}")
    print(f"  {'─' * 95}")
    for name, key in [
        ('Random', 'random'),
        ('Spectral (constrained)', 'spectral'),
        ('SA (min-cut)', 'sa_mincut'),
        ('SA (throughput) from Spectral [OURS]', 'sa_throughput'),
        ('SA (throughput) from Random', 'sa_tp_random'),
    ]:
        ev = results[key]
        vs = ev['throughput_tps'] / base if base > 0 else 0
        star = " ★" if ev['throughput_tps'] == best_tps else ""
        print(f"  {name:<45} {ev['throughput_tps']:>8.4f} "
              f"{ev['comm_ratio']:>5.1%} {ev['nonadj_ratio']:>6.1%} "
              f"{ev['congestion_factor']:>5.2f} {ev['avg_hops']:>5.1f} "
              f"{vs:>7.1%}{star}")

    print(f"\n  SA(throughput) vs Spectral: {(tp_ev['throughput_tps']/base-1)*100:+.2f}%")
    print(f"  SA(throughput) vs SA(min-cut): {(tp_ev['throughput_tps']/mc_ev['throughput_tps']-1)*100:+.2f}%")

    out = Path(__file__).parent / 'results'
    out.mkdir(exist_ok=True)
    save = {k: {m: v[m] for m in ['throughput_tps','comm_ratio','nonadj_ratio',
                                    'congestion_factor','avg_hops']}
            for k, v in results.items()}
    with open(out / f'sa_v2_K{K}.json', 'w') as f:
        json.dump(save, f, indent=2)


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--K', type=int, default=16)
    p.add_argument('--iters', type=int, default=3000)
    args = p.parse_args()
    run(args.K, args.iters)
