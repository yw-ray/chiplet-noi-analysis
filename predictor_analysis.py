"""Boost A + B analysis: alternative predictors and threshold formalization.

A) Compute 7 candidate workload statistics from each workload's traffic
   matrix and compare their Spearman rho against measured RL-WS saving
   across 28 (workload, K, N) cells.

B) Sweep NL% threshold tau and report precision/recall/F1 for the
   binary decision "RL invocation is worth it" (defined as saving >=
   threshold_save).

We use sweep_v3 saving values; Spearman rho is rank-based so the
single-seed bias on absolute lat values does not change rank order
within a cell. Multi-seed corrections are noted for cells where we have
ground-truth measurements.
"""

import json
import math
import statistics
from pathlib import Path

import numpy as np

from noi_topology_synthesis import ChipletGrid
from cost_perf_6panel_workload import WORKLOADS

ROOT = Path(__file__).parent.resolve()
RESULTS_DIR = ROOT / 'results' / 'ml_placement'

CELLS = [
    ('K16_N4', 16, 4, 4),    # name, K, R, C
    ('K16_N8', 16, 4, 4),
    ('K32_N4', 32, 4, 8),
    ('K32_N8', 32, 4, 8),
]

# 7 workloads (same as sweep_v3)
WORKLOAD_NAMES = ['moe', 'hybrid_tp_pp', 'tree_allreduce',
                  'uniform_random', 'ep_all_to_all', 'fsdp',
                  'ring_allreduce']

# ----------------------------------------------------------------- predictors

def adjacency_mask(K, R, C):
    """Return KxK boolean: True for adjacent chiplet pairs (Manhattan=1)."""
    pos = [(i // C, i % C) for i in range(K)]
    adj = np.zeros((K, K), dtype=bool)
    for i in range(K):
        for j in range(K):
            if i == j:
                continue
            dr = abs(pos[i][0] - pos[j][0])
            dc = abs(pos[i][1] - pos[j][1])
            if dr + dc == 1:
                adj[i][j] = True
    return adj


def nl_fraction(T, adj):
    """Non-locality fraction: traffic to non-adjacent pairs / total."""
    total = T.sum()
    if total <= 0:
        return 0.0
    nonadj_mass = T[~adj & (np.eye(T.shape[0]) == 0)].sum()
    return float(nonadj_mass / total)


def normalized_traffic(T):
    """Return T_norm (sums to 1) excluding diagonal."""
    M = T.copy().astype(float)
    np.fill_diagonal(M, 0.0)
    s = M.sum()
    if s <= 0:
        return M
    return M / s


def entropy(T):
    """Shannon entropy of normalized traffic distribution (bits)."""
    P = normalized_traffic(T).flatten()
    P = P[P > 0]
    return float(-(P * np.log2(P)).sum())


def normalized_entropy(T):
    """Entropy / log2(N_nonzero)."""
    P = normalized_traffic(T).flatten()
    P = P[P > 0]
    if len(P) == 0:
        return 0.0
    H = -(P * np.log2(P)).sum()
    return float(H / math.log2(len(P))) if len(P) > 1 else 0.0


def gini(T):
    """Gini coefficient of traffic distribution over chiplet pairs."""
    P = normalized_traffic(T).flatten()
    P = P[P > 0]
    if len(P) == 0:
        return 0.0
    P = np.sort(P)
    n = len(P)
    index = np.arange(1, n + 1)
    return float((2 * (index * P).sum() / (n * P.sum())) - (n + 1) / n)


def cv_pairs(T):
    """Coefficient of variation across nonzero traffic pairs."""
    M = T.copy().astype(float)
    np.fill_diagonal(M, 0.0)
    vals = M.flatten()
    vals = vals[vals > 0]
    if len(vals) < 2:
        return 0.0
    mu = float(vals.mean())
    if mu == 0:
        return 0.0
    return float(vals.std() / mu)


def kurtosis_pairs(T):
    """Excess kurtosis across nonzero traffic pairs."""
    M = T.copy().astype(float)
    np.fill_diagonal(M, 0.0)
    vals = M.flatten()
    vals = vals[vals > 0]
    if len(vals) < 4:
        return 0.0
    mu = vals.mean()
    sd = vals.std()
    if sd == 0:
        return 0.0
    return float(((vals - mu) ** 4).mean() / (sd ** 4) - 3.0)


def max_to_median(T, adj):
    """Max nonadj traffic / median nonadj traffic."""
    M = T.copy().astype(float)
    np.fill_diagonal(M, 0.0)
    nonadj_vals = M[~adj].flatten()
    nonadj_vals = nonadj_vals[nonadj_vals > 0]
    if len(nonadj_vals) < 2:
        return 0.0
    med = np.median(nonadj_vals)
    if med == 0:
        return 0.0
    return float(nonadj_vals.max() / med)


PREDICTORS = {
    'NL%':              lambda T, adj: nl_fraction(T, adj) * 100,
    'entropy':          lambda T, adj: entropy(T),
    'norm_entropy':     lambda T, adj: normalized_entropy(T),
    'gini':             lambda T, adj: gini(T),
    'cv_pairs':         lambda T, adj: cv_pairs(T),
    'kurtosis':         lambda T, adj: kurtosis_pairs(T),
    'max/median_nonadj':lambda T, adj: max_to_median(T, adj),
}

# ----------------------------------------------------------------- saving extraction

def extract_savings(cell_name, K):
    """Return list of (workload, saving%) tuples for this cell.

    Saving = (best_baseline_lat - ours_mask_lat) / best_baseline_lat * 100,
    using sweep_v3 single-seed numbers. Aggregated across all combos that
    contain the workload, taking max over combos (best case for ours).
    """
    fn = RESULTS_DIR / f'sweep_v3_isowire_seedinject_v3_{cell_name}.json'
    if not fn.exists():
        return []
    with open(fn) as f:
        sweep = json.load(f)

    # for each workload, find all combos that include it, take median saving
    per_wl_savings = {w: [] for w in WORKLOAD_NAMES}
    for combo_key, payload in sweep.items():
        c = payload.get(cell_name)
        if not c or 'stage2' not in c:
            continue
        s2 = c['stage2']
        bls = c['baselines_at_W']
        for wl, info in s2.items():
            ours_lat = info.get('mask_lat')
            if ours_lat is None or ours_lat <= 0:
                continue
            bl_lats = []
            for bl_name, bl_data in bls.items():
                bl_lat = bl_data.get('lat', {}).get(wl)
                if bl_lat is not None and bl_lat > 0:
                    bl_lats.append(bl_lat)
            if not bl_lats:
                continue
            best_bl = min(bl_lats)
            saving = (best_bl - ours_lat) / best_bl * 100
            per_wl_savings[wl].append(saving)

    out = []
    for w, savings in per_wl_savings.items():
        if savings:
            out.append((w, statistics.median(savings)))
    return out


# ----------------------------------------------------------------- spearman

def spearman(xs, ys):
    """Spearman rho. Naive O(n log n) tied-rank impl."""
    n = len(xs)
    if n < 2:
        return float('nan')

    def rank(arr):
        sorted_idx = sorted(range(n), key=lambda i: arr[i])
        ranks = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and arr[sorted_idx[j + 1]] == arr[sorted_idx[i]]:
                j += 1
            avg_rank = (i + j) / 2 + 1
            for k in range(i, j + 1):
                ranks[sorted_idx[k]] = avg_rank
            i = j + 1
        return ranks

    rx = rank(xs)
    ry = rank(ys)
    mx = sum(rx) / n
    my = sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    dx = math.sqrt(sum((rx[i] - mx) ** 2 for i in range(n)))
    dy = math.sqrt(sum((ry[i] - my) ** 2 for i in range(n)))
    if dx == 0 or dy == 0:
        return float('nan')
    return num / (dx * dy)


# ----------------------------------------------------------------- main

def main():
    # ---- gather (predictor, saving) data over 28 cells
    rows = []  # list of dict: cell, K, N, workload, NL%, entropy, ..., saving
    for cell_name, K, R, C in CELLS:
        N_int = int(cell_name.split('_N')[1])
        grid = ChipletGrid(R, C)
        adj = adjacency_mask(K, R, C)
        savings_list = extract_savings(cell_name, K)
        savings = dict(savings_list)
        for wl in WORKLOAD_NAMES:
            if wl not in savings:
                continue
            builder = WORKLOADS.get(wl)
            if builder is None:
                continue
            try:
                T = builder(K, grid)
            except TypeError:
                T = builder(K)
            T = np.asarray(T, dtype=float)
            row = {'cell': cell_name, 'K': K, 'N': N_int, 'wl': wl,
                   'saving': savings[wl]}
            for name, fn in PREDICTORS.items():
                row[name] = fn(T, adj)
            rows.append(row)

    n = len(rows)
    print(f'\n[data] {n} cell-workload data points\n')

    if n < 10:
        print('Too few data points for meaningful Spearman.')
        return

    # ---- Boost A: predictor comparison
    savings_vec = [r['saving'] for r in rows]
    print('=== Boost A: Spearman rho of each predictor vs saving ===')
    print(f'{"predictor":<22} {"rho":>7}  {"|rho|":>7}')
    pred_rhos = []
    for name in PREDICTORS:
        vec = [r[name] for r in rows]
        rho = spearman(vec, savings_vec)
        pred_rhos.append((name, rho))
        print(f'{name:<22} {rho:>7.3f}  {abs(rho):>7.3f}')

    pred_rhos.sort(key=lambda x: -abs(x[1]))
    print('\nRanking (by |rho|):')
    for i, (n_, rho) in enumerate(pred_rhos, 1):
        print(f'  {i}. {n_:<22} |rho|={abs(rho):.3f}')

    # ---- Boost B: threshold formalization
    print('\n=== Boost B: NL% threshold for "RL invocation worth it" ===')
    nl_vec = [r['NL%'] for r in rows]
    save_vec = [r['saving'] for r in rows]

    # define "worth it" as saving >= 10% (arbitrary, will sweep)
    for save_thresh in [5.0, 10.0, 15.0, 20.0]:
        labels = [s >= save_thresh for s in save_vec]
        n_pos = sum(labels)
        n_neg = n - n_pos
        print(f'\nSaving threshold = {save_thresh:.0f}%  '
              f'(positives = {n_pos}/{n}, negatives = {n_neg}/{n})')
        if n_pos == 0 or n_neg == 0:
            print('  All-same label, skip')
            continue
        print(f'  {"NL_thresh":>10} {"TP":>3} {"FP":>3} {"FN":>3} {"TN":>3}'
              f'  {"Prec":>5}  {"Rec":>5}  {"F1":>5}')
        best_f1 = -1; best_tau = None; best_stats = None
        for tau in [40, 50, 60, 70, 77, 80, 85, 90]:
            preds = [v >= tau for v in nl_vec]
            tp = sum(1 for p, l in zip(preds, labels) if p and l)
            fp = sum(1 for p, l in zip(preds, labels) if p and not l)
            fn = sum(1 for p, l in zip(preds, labels) if not p and l)
            tn = sum(1 for p, l in zip(preds, labels) if not p and not l)
            prec = tp / max(tp + fp, 1)
            rec  = tp / max(tp + fn, 1)
            f1   = 2 * prec * rec / max(prec + rec, 1e-9)
            print(f'  {tau:>10} {tp:>3} {fp:>3} {fn:>3} {tn:>3}'
                  f'  {prec:>5.2f}  {rec:>5.2f}  {f1:>5.2f}')
            if f1 > best_f1:
                best_f1 = f1; best_tau = tau
                best_stats = (tp, fp, fn, tn, prec, rec, f1)
        tp, fp, fn, tn, prec, rec, f1 = best_stats
        print(f'  -> best F1 at NL%>={best_tau}: '
              f'prec={prec:.2f}, rec={rec:.2f}, F1={f1:.2f}')

    # ---- per-workload, per-cell breakdown
    print('\n=== Per-cell data (sorted by NL%) ===')
    print(f'{"cell":<7} {"wl":<18} {"NL%":>6} {"saving":>8}')
    for r in sorted(rows, key=lambda x: x['NL%']):
        print(f'{r["cell"]:<7} {r["wl"]:<18} {r["NL%"]:>6.1f} {r["saving"]:>7.1f}%')

    # save full data
    out_path = RESULTS_DIR / 'predictor_analysis.json'
    with open(out_path, 'w') as f:
        json.dump({
            'rows': rows,
            'spearman_by_predictor': dict(pred_rhos),
        }, f, indent=2)
    print(f'\n[done] wrote {out_path}')


if __name__ == '__main__':
    main()
