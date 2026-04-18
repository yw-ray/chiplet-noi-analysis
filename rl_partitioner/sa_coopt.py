"""
Simulated Annealing: Placement-Aware Chiplet Partitioning
==========================================================

Compare two SA variants:
  1. SA with min-cut objective (proxy, placement-unaware)
  2. SA with E2E throughput objective (ours, placement-aware)

Plus baselines:
  - Random partition
  - Spectral partition
  - Greedy refinement (throughput-aware)

Claim: SA(throughput) > SA(min-cut) > Spectral
because min-cut ignores physical placement constraints.
"""

import sys
import time
import json
import math
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from envs.netlist import create_transformer_accelerator_netlist, get_edge_bandwidth_matrix
from envs.placement_aware_evaluator import PlacementAwareEvaluator, ChipletGrid


# ============================================================
# Spectral partition
# ============================================================

def spectral_partition(G, K, seed=42):
    N = G.number_of_nodes()
    W = np.zeros((N, N))
    for u, v, d in G.edges(data=True):
        W[u][v] = d['bandwidth']
        W[v][u] = d['bandwidth']
    D = np.diag(W.sum(axis=1))
    L = D - W
    _, eigvecs = np.linalg.eigh(L)
    features = eigvecs[:, 1:K+1]

    # K-means
    rng = np.random.default_rng(seed)
    centers = features[rng.choice(N, K, replace=False)].copy()
    assignment = np.zeros(N, dtype=int)
    for _ in range(100):
        for i in range(N):
            assignment[i] = np.argmin(np.linalg.norm(features[i] - centers, axis=1))
        new_c = np.zeros_like(centers)
        for k in range(K):
            m = features[assignment == k]
            new_c[k] = m.mean(0) if len(m) > 0 else features[rng.integers(N)]
        if np.allclose(centers, new_c):
            break
        centers = new_c
    return assignment


def random_partition(G, K, seed=42):
    rng = np.random.default_rng(seed)
    N = G.number_of_nodes()
    a = np.zeros(N, dtype=int)
    per = N // K
    perm = rng.permutation(N)
    for i, node in enumerate(perm):
        a[node] = min(i // per, K - 1)
    return a


# ============================================================
# Fast proxy metrics (no full evaluation needed)
# ============================================================

def compute_comm_ratio(bw_matrix, assignment, N):
    total, inter = 0.0, 0.0
    for i in range(N):
        for j in range(i + 1, N):
            bw = bw_matrix[i][j]
            if bw > 0:
                total += bw
                if assignment[i] != assignment[j]:
                    inter += bw
    return inter / (total + 1e-8)


def compute_comm_ratio_delta(bw_matrix, assignment, module_id, old_cid, new_cid, N,
                              prev_inter, prev_total):
    """Incremental update of inter-chiplet BW after a swap."""
    delta = 0.0
    for j in range(N):
        if j == module_id:
            continue
        bw = bw_matrix[module_id][j]
        if bw <= 0:
            continue
        j_cid = assignment[j]
        was_inter = (old_cid != j_cid)
        is_inter = (new_cid != j_cid)
        if was_inter and not is_inter:
            delta -= bw
        elif not was_inter and is_inter:
            delta += bw
    return prev_inter + delta


# ============================================================
# Simulated Annealing
# ============================================================

def sa_partition(G, K, initial_assignment, evaluator, objective='throughput',
                 n_iters=5000, T_start=1.0, T_end=0.01, seed=42):
    """
    SA-based partition refinement.

    objective:
      'throughput' — maximize E2E throughput (placement-aware)
      'mincut'     — minimize comm_ratio (placement-unaware proxy)
    """
    rng = np.random.default_rng(seed)
    N = G.number_of_nodes()
    assignment = initial_assignment.copy()
    bw_matrix = get_edge_bandwidth_matrix(G)

    # Balance constraints
    max_cap = int(np.ceil(N / K * 2.0))
    min_cap = max(1, int(np.floor(N / K * 0.3)))

    # Initial score
    if objective == 'throughput':
        ev = evaluator.evaluate(G, assignment)
        current_score = ev['throughput_tps']
    else:
        inter_bw = 0.0
        total_bw = 0.0
        for i in range(N):
            for j in range(i + 1, N):
                bw = bw_matrix[i][j]
                if bw > 0:
                    total_bw += bw
                    if assignment[i] != assignment[j]:
                        inter_bw += bw
        current_score = -inter_bw / (total_bw + 1e-8)  # negative: minimize

    best_score = current_score
    best_assignment = assignment.copy()

    # Temperature schedule
    alpha = (T_end / T_start) ** (1.0 / n_iters)

    accepted = 0
    improved = 0
    eval_count = 0
    T = T_start

    for it in range(n_iters):
        # Random swap: pick random module, random target chiplet
        module = rng.integers(N)
        old_cid = assignment[module]
        target_cid = rng.integers(K)
        while target_cid == old_cid:
            target_cid = rng.integers(K)

        # Balance check
        count_target = np.sum(assignment == target_cid)
        count_source = np.sum(assignment == old_cid)
        if count_target >= max_cap or count_source <= min_cap:
            T *= alpha
            continue

        # Evaluate swap
        assignment[module] = target_cid

        if objective == 'throughput':
            ev = evaluator.evaluate(G, assignment)
            new_score = ev['throughput_tps']
            eval_count += 1
        else:
            new_inter = compute_comm_ratio_delta(
                bw_matrix, assignment, module, old_cid, target_cid, N,
                inter_bw, total_bw)
            new_score = -new_inter / (total_bw + 1e-8)

        delta = new_score - current_score

        # Accept or reject
        if delta > 0 or rng.random() < math.exp(delta / (T + 1e-10)):
            current_score = new_score
            accepted += 1
            if objective == 'mincut':
                inter_bw = new_inter
            if new_score > best_score:
                best_score = new_score
                best_assignment = assignment.copy()
                improved += 1
        else:
            assignment[module] = old_cid  # revert

        T *= alpha

    return best_assignment, {
        'best_score': best_score,
        'accepted': accepted,
        'improved': improved,
        'eval_count': eval_count,
        'n_iters': n_iters,
    }


# ============================================================
# Greedy refinement
# ============================================================

def greedy_refine(G, K, initial_assignment, evaluator, max_rounds=5):
    """Simple greedy: for each module, try all chiplets, keep best."""
    N = G.number_of_nodes()
    assignment = initial_assignment.copy()
    max_cap = int(np.ceil(N / K * 2.0))
    min_cap = max(1, int(np.floor(N / K * 0.3)))

    ev = evaluator.evaluate(G, assignment)
    best_tps = ev['throughput_tps']

    for round_i in range(max_rounds):
        improved_this_round = False
        for module in range(N):
            old_cid = assignment[module]
            best_local_tps = best_tps
            best_local_cid = old_cid

            for target in range(K):
                if target == old_cid:
                    continue
                count_t = np.sum(assignment == target)
                count_s = np.sum(assignment == old_cid)
                if count_t >= max_cap or count_s <= min_cap:
                    continue

                assignment[module] = target
                ev = evaluator.evaluate(G, assignment)
                if ev['throughput_tps'] > best_local_tps:
                    best_local_tps = ev['throughput_tps']
                    best_local_cid = target

            assignment[module] = best_local_cid
            if best_local_cid != old_cid:
                best_tps = best_local_tps
                improved_this_round = True

        if not improved_this_round:
            break

    return assignment


# ============================================================
# Main experiment
# ============================================================

def run(K=8, sa_iters=5000):
    if K == 4:
        grid = ChipletGrid(2, 2)
    elif K == 8:
        grid = ChipletGrid(2, 4)
    elif K == 16:
        grid = ChipletGrid(4, 4)
    else:
        rows = int(np.ceil(np.sqrt(K)))
        grid = ChipletGrid(rows, int(np.ceil(K / rows)))

    print("=" * 90)
    print(f"  SA CO-OPTIMIZATION: {grid.rows}×{grid.cols} grid ({K} chiplets), {sa_iters} SA iters")
    print("=" * 90)

    # Netlist
    G = create_transformer_accelerator_netlist(
        num_tensor_cores=max(16, K * 4),
        num_sram_banks=max(8, K * 2),
        num_hbm_ctrl=max(4, K),
        num_softmax=max(4, K),
        num_layernorm=max(4, K),
    )
    N = G.number_of_nodes()
    print(f"\n  Netlist: {N} modules, {G.number_of_edges()} edges")

    evaluator = PlacementAwareEvaluator(
        grid,
        bw_per_link_gbs=32,
        phy_area_per_link=0.15,
        latency_per_hop_us=0.10,
        links_per_adjacent_pair=4,
        tops_per_mm2=1.5,
        hbm_bw_per_mm2=3.0,
        overlap_factor=0.0,
    )

    results = {}

    # ── 1. Random ──
    print(f"\n  [1/6] Random partition...")
    rp = random_partition(G, K)
    re = evaluator.evaluate(G, rp)
    results['random'] = re
    print(f"    tok/s={re['throughput_tps']:.4f}, comm={re['comm_ratio']:.1%}, "
          f"cong={re['congestion_factor']:.2f}")

    # ── 2. Spectral ──
    print(f"\n  [2/6] Spectral partition...")
    sp = spectral_partition(G, K)
    se = evaluator.evaluate(G, sp)
    results['spectral'] = se
    print(f"    tok/s={se['throughput_tps']:.4f}, comm={se['comm_ratio']:.1%}, "
          f"cong={se['congestion_factor']:.2f}")

    # ── 3. SA with min-cut objective ──
    print(f"\n  [3/6] SA (min-cut objective, placement-unaware)...")
    t0 = time.time()
    sa_mc_part, sa_mc_info = sa_partition(
        G, K, sp.copy(), evaluator, objective='mincut',
        n_iters=sa_iters, T_start=0.5, T_end=0.001)
    t_mc = time.time() - t0
    sa_mc_ev = evaluator.evaluate(G, sa_mc_part)
    results['sa_mincut'] = sa_mc_ev
    print(f"    tok/s={sa_mc_ev['throughput_tps']:.4f}, comm={sa_mc_ev['comm_ratio']:.1%}, "
          f"cong={sa_mc_ev['congestion_factor']:.2f} "
          f"(accepted={sa_mc_info['accepted']}, improved={sa_mc_info['improved']}, {t_mc:.1f}s)")

    # ── 4. SA with throughput objective (OURS) ──
    print(f"\n  [4/6] SA (throughput objective, PLACEMENT-AWARE) [OURS]...")
    t0 = time.time()
    sa_tp_part, sa_tp_info = sa_partition(
        G, K, sp.copy(), evaluator, objective='throughput',
        n_iters=sa_iters, T_start=0.05, T_end=0.0001)
    t_tp = time.time() - t0
    sa_tp_ev = evaluator.evaluate(G, sa_tp_part)
    results['sa_throughput'] = sa_tp_ev
    print(f"    tok/s={sa_tp_ev['throughput_tps']:.4f}, comm={sa_tp_ev['comm_ratio']:.1%}, "
          f"cong={sa_tp_ev['congestion_factor']:.2f} "
          f"(accepted={sa_tp_info['accepted']}, improved={sa_tp_info['improved']}, {t_tp:.1f}s)")

    # ── 5. Greedy refinement (throughput) ──
    print(f"\n  [5/6] Greedy refinement (throughput-aware)...")
    t0 = time.time()
    greedy_part = greedy_refine(G, K, sp.copy(), evaluator, max_rounds=3)
    t_gr = time.time() - t0
    greedy_ev = evaluator.evaluate(G, greedy_part)
    results['greedy'] = greedy_ev
    print(f"    tok/s={greedy_ev['throughput_tps']:.4f}, comm={greedy_ev['comm_ratio']:.1%}, "
          f"cong={greedy_ev['congestion_factor']:.2f} ({t_gr:.1f}s)")

    # ── 6. SA(throughput) starting from greedy ──
    print(f"\n  [6/6] Greedy + SA(throughput) [OURS-BEST]...")
    t0 = time.time()
    sa_best_part, sa_best_info = sa_partition(
        G, K, greedy_part.copy(), evaluator, objective='throughput',
        n_iters=sa_iters, T_start=0.02, T_end=0.0001)
    t_best = time.time() - t0
    sa_best_ev = evaluator.evaluate(G, sa_best_part)
    results['greedy_sa'] = sa_best_ev
    print(f"    tok/s={sa_best_ev['throughput_tps']:.4f}, comm={sa_best_ev['comm_ratio']:.1%}, "
          f"cong={sa_best_ev['congestion_factor']:.2f} "
          f"(accepted={sa_best_info['accepted']}, improved={sa_best_info['improved']}, {t_best:.1f}s)")

    # ── Summary ──
    base = se['throughput_tps']
    print(f"\n  {'─' * 90}")
    print(f"  {'Method':<50} {'tok/s':>8} {'Comm%':>6} {'Cong':>5} "
          f"{'vs Spec':>8} {'vs Best':>8}")
    print(f"  {'─' * 90}")

    best_tps = max(r['throughput_tps'] for r in results.values())

    for name, key in [
        ('1. Random', 'random'),
        ('2. Spectral', 'spectral'),
        ('3. SA (min-cut, placement-unaware)', 'sa_mincut'),
        ('4. SA (throughput, placement-aware) [OURS]', 'sa_throughput'),
        ('5. Greedy (throughput-aware)', 'greedy'),
        ('6. Greedy + SA (throughput) [OURS-BEST]', 'greedy_sa'),
    ]:
        ev = results[key]
        vs_spec = ev['throughput_tps'] / base if base > 0 else 0
        vs_best = ev['throughput_tps'] / best_tps if best_tps > 0 else 0
        marker = " ★" if ev['throughput_tps'] == best_tps else ""
        print(f"  {name:<50} {ev['throughput_tps']:>8.4f} "
              f"{ev['comm_ratio']:>5.1%} {ev['congestion_factor']:>5.2f} "
              f"{vs_spec:>7.1%} {vs_best:>7.1%}{marker}")

    print(f"\n  Key results:")
    print(f"    SA(throughput) vs Spectral: "
          f"{(sa_tp_ev['throughput_tps']/base-1)*100:+.2f}%")
    print(f"    SA(throughput) vs SA(min-cut): "
          f"{(sa_tp_ev['throughput_tps']/sa_mc_ev['throughput_tps']-1)*100:+.2f}%")
    print(f"    BEST vs Spectral: "
          f"{(best_tps/base-1)*100:+.2f}%")

    # Save
    out = Path(__file__).parent / 'results'
    out.mkdir(exist_ok=True)
    save = {k: {'tps': v['throughput_tps'], 'comm': v['comm_ratio'],
                'congestion': v['congestion_factor']}
            for k, v in results.items()}
    with open(out / f'sa_coopt_K{K}.json', 'w') as f:
        json.dump(save, f, indent=2)
    print(f"\n  Saved to results/sa_coopt_K{K}.json")


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--K', type=int, default=8)
    p.add_argument('--iters', type=int, default=5000)
    args = p.parse_args()
    run(args.K, args.iters)
