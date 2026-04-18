"""
Defense Experiments
====================

1. Objective Generality: multiple optimizers × 2 objectives → throughput obj always wins
2. Real Architecture Netlists: H100-like, MI300X-like accelerator models
3. BookSim Cross-validation: compare analytical model vs cycle-accurate
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
from sa_coopt_v2 import EvaluatorV2, constrained_spectral, sa_optimize


# ============================================================
# Helper: balanced spectral
# ============================================================

def balanced_spectral(G, K, grid, constraints, seed=42):
    asgn = constrained_spectral(G, K, grid, constraints, seed)
    nodes = sorted(G.nodes)
    for _ in range(30):
        compute = np.zeros(K)
        for n in nodes:
            compute[asgn[n]] += G.nodes[n]['compute']
        over, under = np.argmax(compute), np.argmin(compute)
        if compute[over] < compute[under] * 1.5:
            break
        candidates = [n for n in nodes if asgn[n] == over]
        if not candidates:
            break
        best_n, best_cost = None, float('inf')
        for n in candidates:
            internal = sum(G[n][nb]['bandwidth'] for nb in G.neighbors(n)
                          if asgn[nb] == over and n != nb)
            if internal < best_cost:
                best_cost, best_n = internal, n
        if best_n is not None:
            asgn[best_n] = under
    return asgn


# ============================================================
# Defense 1: Objective Generality
# ============================================================

def greedy_optimize(G, K, init, evaluator, objective, constraints=None,
                    grid=None, max_rounds=5):
    """Greedy hill-climbing: try each module in each chiplet, keep best."""
    nodes = sorted(G.nodes)
    N = len(nodes)
    assignment = init.copy()
    max_cap = int(np.ceil(N / K * 2.5))
    min_cap = max(1, int(np.floor(N / K * 0.2)))
    edge_only = set(constraints.get('edge_only', [])) if constraints else set()
    edge_chiplets = set(get_edge_modules(grid)) if grid else set()

    def score(asgn):
        if objective == 'throughput':
            return evaluator.evaluate(G, asgn)['throughput_tps']
        else:
            ib = sum(d['bandwidth'] for u, v, d in G.edges(data=True)
                     if asgn[u] != asgn[v])
            tb = sum(d['bandwidth'] for u, v, d in G.edges(data=True))
            return -(ib / (tb + 1e-8))

    best_score = score(assignment)

    for r in range(max_rounds):
        improved = False
        for nid in nodes:
            old = assignment[nid]
            best_local = best_score
            best_target = old

            for target in range(K):
                if target == old:
                    continue
                if nid in edge_only and target not in edge_chiplets:
                    continue
                count_t = sum(1 for n in nodes if assignment[n] == target)
                count_s = sum(1 for n in nodes if assignment[n] == old)
                if count_t >= max_cap or count_s <= min_cap:
                    continue

                assignment[nid] = target
                s = score(assignment)
                if s > best_local:
                    best_local = s
                    best_target = target

            assignment[nid] = best_target
            if best_target != old:
                best_score = best_local
                improved = True

        if not improved:
            break

    return assignment


def random_restart(G, K, evaluator, objective, constraints, grid,
                   n_restarts=20, sa_iters=1000):
    """Random restart + short SA."""
    nodes = sorted(G.nodes)
    N = len(nodes)
    best_asgn = None
    best_score = -np.inf

    for seed in range(n_restarts):
        rng = np.random.default_rng(seed + 100)
        init = np.zeros(max(nodes) + 1, dtype=int)
        perm = rng.permutation(N)
        per = N // K
        for i, idx in enumerate(perm):
            init[nodes[idx]] = min(i // per, K - 1)

        # Short SA from random init
        asgn, _ = sa_optimize(G, K, init, evaluator, objective,
                               constraints, grid, sa_iters, 0.1, 0.001, seed=seed+200)
        ev = evaluator.evaluate(G, asgn)
        score = ev['throughput_tps'] if objective == 'throughput' else -ev['comm_ratio']

        if score > best_score:
            best_score = score
            best_asgn = asgn.copy()

    return best_asgn


def defense_1_objective_generality():
    """Show: throughput objective wins regardless of optimizer."""
    print("=" * 100)
    print("  DEFENSE 1: Objective Generality")
    print("  Same optimizer + different objectives → throughput always better")
    print("=" * 100)

    configs = [
        ('K=8',  8, (2,4), 8, 4, 4, 0.3, 32),
        ('K=16', 16, (4,4), 16, 4, 8, 0.3, 96),
    ]

    for (name, K, gshape, nc, cpc, nsc, xcr, lb) in configs:
        grid = ChipletGrid(*gshape)
        G, con = create_realistic_accelerator(
            n_compute_clusters=nc, cores_per_cluster=cpc,
            n_shared_cache=nsc, n_hbm_ctrl=4,
            n_reduction_units=max(2, K//4), cross_cluster_ratio=xcr)
        N = G.number_of_nodes()

        ev = EvaluatorV2(grid, total_link_budget=lb, bw_per_link=32,
                         phy_area_per_link=0.15, latency_per_hop_us=0.10)

        bsp = balanced_spectral(G, K, grid, con)
        bse = ev.evaluate(G, bsp)

        print(f"\n  ─── {name} (N={N}, links={lb}) ───")
        print(f"  Baseline (Bal.Spectral): tps={bse['throughput_tps']:.4f}")
        print()
        print(f"  {'Optimizer':<25} {'min-cut obj':>12} {'throughput obj':>14} {'Winner':>8}")
        print(f"  {'─' * 65}")

        optimizers = [
            ('Greedy', lambda obj: greedy_optimize(G, K, bsp.copy(), ev, obj, con, grid, 3)),
            ('SA (3000 iters)', lambda obj: sa_optimize(G, K, bsp.copy(), ev, obj, con, grid, 3000, 0.1, 0.001)[0]),
            ('SA (5000 iters)', lambda obj: sa_optimize(G, K, bsp.copy(), ev, obj, con, grid, 5000, 0.05, 0.0001)[0]),
            ('Random restart ×20', lambda obj: random_restart(G, K, ev, obj, con, grid, 20, 500)),
        ]

        for (opt_name, opt_fn) in optimizers:
            # Min-cut objective
            mc_asgn = opt_fn('mincut')
            mc_ev = ev.evaluate(G, mc_asgn)

            # Throughput objective
            tp_asgn = opt_fn('throughput')
            tp_ev = ev.evaluate(G, tp_asgn)

            winner = "TPUT ✓" if tp_ev['throughput_tps'] > mc_ev['throughput_tps'] else "MINCUT"
            print(f"  {opt_name:<25} {mc_ev['throughput_tps']:>10.4f}   "
                  f"{tp_ev['throughput_tps']:>12.4f}   {winner:>8}")

        print()


# ============================================================
# Defense 2: Real Architecture Netlists
# ============================================================

def create_h100_like_netlist():
    """
    H100-like monolithic accelerator modeled as netlist.
    132 SMs, each with 4 tensor cores + shared L2 + HBM controllers.
    Simplified to ~120 modules.
    """
    import networkx as nx
    G = nx.Graph()
    rng = np.random.default_rng(42)
    nid = 0

    # 8 GPC (Graphics Processing Clusters), each with ~16 SMs
    # Simplified: 8 clusters × 12 modules = 96 compute modules
    n_gpc = 8
    sm_per_gpc = 12
    gpc_modules = {}

    for gpc in range(n_gpc):
        modules = []
        for i in range(sm_per_gpc):
            G.add_node(nid, name=f'SM_{gpc}_{i}', type='tensor_core',
                       area=6.0, power=8.0, compute=15.0, sram=0.25,
                       preferred_process=5, cluster=gpc)
            modules.append(nid)
            nid += 1
        gpc_modules[gpc] = modules

    # L2 cache partitions (6 slices)
    l2_ids = []
    for i in range(6):
        G.add_node(nid, name=f'L2_{i}', type='shared_cache',
                   area=10.0, power=3.0, compute=0.0, sram=32.0,
                   preferred_process=5, cluster=-1)
        l2_ids.append(nid)
        nid += 1

    # HBM3 controllers (6)
    hbm_ids = []
    for i in range(6):
        G.add_node(nid, name=f'HBM_{i}', type='hbm_ctrl',
                   area=8.0, power=4.0, compute=0.0, sram=0.0,
                   preferred_process=28, cluster=-1)
        hbm_ids.append(nid)
        nid += 1

    # NVLink controllers (4)
    nvlink_ids = []
    for i in range(4):
        G.add_node(nid, name=f'NVLink_{i}', type='hbm_ctrl',
                   area=5.0, power=3.0, compute=0.0, sram=0.0,
                   preferred_process=28, cluster=-1)
        nvlink_ids.append(nid)
        nid += 1

    # Edges
    # SM ↔ SM (intra-GPC: high BW)
    for gpc in range(n_gpc):
        mods = gpc_modules[gpc]
        for i in range(len(mods)):
            for j in range(i+1, len(mods)):
                G.add_edge(mods[i], mods[j], bandwidth=40.0 + rng.uniform(-5, 5))

    # SM ↔ L2 (each GPC connected to 1-2 L2 slices)
    for gpc in range(n_gpc):
        l2_primary = l2_ids[gpc % 6]
        l2_secondary = l2_ids[(gpc + 1) % 6]
        for sm in gpc_modules[gpc]:
            G.add_edge(sm, l2_primary, bandwidth=60.0 + rng.uniform(-5, 5))
            G.add_edge(sm, l2_secondary, bandwidth=20.0 + rng.uniform(-3, 3))

    # L2 ↔ HBM (1:1)
    for i in range(6):
        G.add_edge(l2_ids[i], hbm_ids[i], bandwidth=200.0 + rng.uniform(-10, 10))

    # Cross-GPC (all-reduce, tensor parallel)
    all_sms = [sm for mods in gpc_modules.values() for sm in mods]
    for _ in range(int(len(all_sms) * 0.15)):
        a, b = rng.choice(len(all_sms), 2, replace=False)
        ga = G.nodes[all_sms[a]]['cluster']
        gb = G.nodes[all_sms[b]]['cluster']
        if ga != gb:
            bw = rng.uniform(5, 25)
            if G.has_edge(all_sms[a], all_sms[b]):
                G[all_sms[a]][all_sms[b]]['bandwidth'] += bw
            else:
                G.add_edge(all_sms[a], all_sms[b], bandwidth=bw)

    # NVLink ↔ some SMs (for inter-GPU comm)
    for i, nv in enumerate(nvlink_ids):
        gpcs = [i*2, i*2+1]
        for gpc in gpcs:
            if gpc < n_gpc:
                G.add_edge(nv, gpc_modules[gpc][0], bandwidth=100.0)

    constraints = {'edge_only': hbm_ids + nvlink_ids}
    return G, constraints


def create_mi300x_like_netlist():
    """
    MI300X-like: 8 XCD chiplets, each with compute units.
    More heterogeneous, more cross-die traffic.
    """
    import networkx as nx
    G = nx.Graph()
    rng = np.random.default_rng(123)
    nid = 0

    n_xcd = 8
    cu_per_xcd = 8  # simplified from 38
    xcd_modules = {}

    for xcd in range(n_xcd):
        modules = []
        for i in range(cu_per_xcd):
            G.add_node(nid, name=f'CU_{xcd}_{i}', type='tensor_core',
                       area=3.0, power=4.0, compute=6.0, sram=0.5,
                       preferred_process=5, cluster=xcd)
            modules.append(nid)
            nid += 1

        # L1/L2 cache per XCD
        G.add_node(nid, name=f'Cache_{xcd}', type='shared_cache',
                   area=8.0, power=2.0, compute=0.0, sram=16.0,
                   preferred_process=5, cluster=xcd)
        modules.append(nid)
        cache_id = nid
        nid += 1

        xcd_modules[xcd] = (modules, cache_id)

    # IOD: 4 I/O dies with HBM controllers
    iod_ids = []
    for i in range(4):
        G.add_node(nid, name=f'IOD_{i}', type='hbm_ctrl',
                   area=12.0, power=5.0, compute=0.0, sram=0.0,
                   preferred_process=28, cluster=-1)
        iod_ids.append(nid)
        nid += 1

    # Edges
    # Intra-XCD: CU ↔ CU
    for xcd in range(n_xcd):
        mods, cache = xcd_modules[xcd]
        cus = [m for m in mods if m != cache]
        for i in range(len(cus)):
            for j in range(i+1, len(cus)):
                G.add_edge(cus[i], cus[j], bandwidth=30.0 + rng.uniform(-3, 3))
            # CU ↔ Cache
            G.add_edge(cus[i], cache, bandwidth=80.0 + rng.uniform(-5, 5))

    # XCD ↔ IOD (each XCD talks to 1-2 IODs via Infinity Fabric)
    for xcd in range(n_xcd):
        iod_primary = iod_ids[xcd % 4]
        iod_secondary = iod_ids[(xcd + 1) % 4]
        _, cache = xcd_modules[xcd]
        G.add_edge(cache, iod_primary, bandwidth=120.0 + rng.uniform(-10, 10))
        G.add_edge(cache, iod_secondary, bandwidth=40.0 + rng.uniform(-5, 5))

    # Cross-XCD traffic (Infinity Fabric all-reduce)
    # MI300X has significant cross-die traffic
    all_cus = []
    for xcd in range(n_xcd):
        mods, cache = xcd_modules[xcd]
        all_cus.extend([m for m in mods if m != cache])

    for _ in range(int(len(all_cus) * 0.3)):
        a, b = rng.choice(len(all_cus), 2, replace=False)
        ga = G.nodes[all_cus[a]]['cluster']
        gb = G.nodes[all_cus[b]]['cluster']
        if ga != gb:
            bw = rng.uniform(8, 30)
            if G.has_edge(all_cus[a], all_cus[b]):
                G[all_cus[a]][all_cus[b]]['bandwidth'] += bw
            else:
                G.add_edge(all_cus[a], all_cus[b], bandwidth=bw)

    constraints = {'edge_only': iod_ids}
    return G, constraints


def defense_2_real_architectures():
    """Run experiments on H100-like and MI300X-like netlists."""
    print("\n" + "=" * 100)
    print("  DEFENSE 2: Real Architecture Netlists")
    print("  H100-like (monolithic → chiplet) and MI300X-like (already chiplet)")
    print("=" * 100)

    arch_configs = [
        ('H100-like (4 chiplets)', create_h100_like_netlist, 4, (2,2), 24),
        ('H100-like (8 chiplets)', create_h100_like_netlist, 8, (2,4), 48),
        ('MI300X-like (8 XCDs)',   create_mi300x_like_netlist, 8, (2,4), 32),
        ('MI300X-like (16 tiles)', create_mi300x_like_netlist, 16, (4,4), 64),
    ]

    for (name, netlist_fn, K, gshape, lb) in arch_configs:
        grid = ChipletGrid(*gshape)
        G, con = netlist_fn()
        N = G.number_of_nodes()

        ev = EvaluatorV2(grid, total_link_budget=lb, bw_per_link=32,
                         phy_area_per_link=0.15, latency_per_hop_us=0.10)

        # Balanced Spectral
        bsp = balanced_spectral(G, K, grid, con)
        bse = ev.evaluate(G, bsp)

        # SA min-cut
        sa_mc, _ = sa_optimize(G, K, bsp.copy(), ev, 'mincut', con, grid, 5000, 0.3, 0.001)
        me = ev.evaluate(G, sa_mc)

        # SA throughput
        sa_tp, info = sa_optimize(G, K, bsp.copy(), ev, 'throughput', con, grid, 5000, 0.05, 0.0001)
        te = ev.evaluate(G, sa_tp)

        base = bse['throughput_tps']
        gain_mc = (me['throughput_tps']/base - 1)*100 if base > 0 else 0
        gain_tp = (te['throughput_tps']/base - 1)*100 if base > 0 else 0

        print(f"\n  ─── {name} (N={N}, E={G.number_of_edges()}, links={lb}) ───")
        print(f"  {'Method':<30} {'tps':>8} {'comm':>6} {'cong':>5} {'vs Spec':>9}")
        print(f"  {'─' * 65}")
        print(f"  {'Bal.Spectral':<30} {bse['throughput_tps']:>8.4f} {bse['comm_ratio']:>5.1%} "
              f"{bse['congestion_factor']:>5.2f} {'baseline':>9}")
        print(f"  {'SA (min-cut)':<30} {me['throughput_tps']:>8.4f} {me['comm_ratio']:>5.1%} "
              f"{me['congestion_factor']:>5.2f} {gain_mc:>+8.1f}%")
        print(f"  {'SA (throughput) [OURS]':<30} {te['throughput_tps']:>8.4f} {te['comm_ratio']:>5.1%} "
              f"{te['congestion_factor']:>5.2f} {gain_tp:>+8.1f}%")


# ============================================================
# Defense 3: BookSim Cross-Validation
# ============================================================

def defense_3_booksim_validation():
    """
    Generate BookSim configs for Spectral vs SA(throughput) partitions
    so we can validate our analytical congestion model.
    """
    print("\n" + "=" * 100)
    print("  DEFENSE 3: BookSim Cross-Validation Setup")
    print("  Generate configs for cycle-accurate validation")
    print("=" * 100)

    K = 8
    grid = ChipletGrid(2, 4)
    G, con = create_realistic_accelerator(
        n_compute_clusters=8, cores_per_cluster=4,
        n_shared_cache=4, n_hbm_ctrl=4,
        n_reduction_units=4, cross_cluster_ratio=0.3)

    ev = EvaluatorV2(grid, total_link_budget=32, bw_per_link=32,
                     phy_area_per_link=0.15, latency_per_hop_us=0.10)

    bsp = balanced_spectral(G, K, grid, con)
    bse = ev.evaluate(G, bsp)

    sa_tp, _ = sa_optimize(G, K, bsp.copy(), ev, 'throughput', con, grid, 5000, 0.05, 0.0001)
    te = ev.evaluate(G, sa_tp)

    print(f"\n  Model predictions:")
    print(f"    Spectral:       tps={bse['throughput_tps']:.4f}, cong={bse['congestion_factor']:.3f}, "
          f"comm={bse['comm_ratio']:.1%}")
    print(f"    SA(throughput):  tps={te['throughput_tps']:.4f}, cong={te['congestion_factor']:.3f}, "
          f"comm={te['comm_ratio']:.1%}")

    # Generate traffic matrices for BookSim
    print(f"\n  Traffic matrices (for BookSim injection rates):")

    for label, asgn, result in [('Spectral', bsp, bse), ('SA_throughput', sa_tp, te)]:
        # Compute inter-chiplet traffic
        traffic = np.zeros((K, K))
        for u, v, d in G.edges(data=True):
            cu, cv = asgn[u], asgn[v]
            if cu != cv:
                traffic[cu][cv] += d['bandwidth']

        # Normalize to injection rates (0-1 scale)
        max_traffic = traffic.max()
        if max_traffic > 0:
            normalized = traffic / max_traffic

        print(f"\n    {label} inter-chiplet traffic (GB/s):")
        for i in range(K):
            row = [f"{traffic[i][j]:>6.1f}" for j in range(K)]
            print(f"      [{', '.join(row)}]")

        print(f"    Link allocation: {result.get('link_alloc', 'N/A')}")

    # What BookSim would need to validate:
    print(f"""
  To validate with BookSim:
  1. Create 2×4 chiplet topology (8 chiplets, each 4×4 mesh)
  2. Set inter-chiplet links based on link_alloc above
  3. Inject traffic matching the traffic matrices
  4. Measure: throughput, avg latency, max link utilization
  5. Compare: our predicted congestion vs BookSim measured congestion

  Key validation metric:
    Our model predicts Spectral congestion = {bse['congestion_factor']:.3f}
    Our model predicts SA(tput) congestion = {te['congestion_factor']:.3f}
    BookSim should show similar RATIO between the two configurations.
    """)


# ============================================================
# Main
# ============================================================

def main():
    defense_1_objective_generality()
    defense_2_real_architectures()
    defense_3_booksim_validation()


if __name__ == '__main__':
    main()
