"""Multi-workload joint RL for express link placement (V2 thesis).

Input: workload SET + (K, N) + wire budget.
Stage 1 (this file): joint RL learns superset alloc.
Stage 2: greedy mask postproc selects per-workload subset at runtime.

Compared to ml_express_warmstart.train_warmstart_rl_ra(), this:
- accepts a list of workload names
- concatenates per-workload traffic into the state
- aggregates surrogate-predicted latencies (avg or worst) for the reward
- warm-starts from the union of per-workload greedy allocations
"""

import json
import sys
from pathlib import Path

import numpy as np
import torch
import torch.optim as optim

sys.path.insert(0, str(Path(__file__).parent))
from noi_topology_synthesis import ChipletGrid
from cost_performance_experiment import alloc_express_greedy
from cost_perf_6panel_workload import WORKLOADS
from ml_express_warmstart import (
    DEVICE,
    RESULTS_DIR,
    SwapPolicy,
    load_rate_aware_surrogate,
    surrogate_predict_ra,
)


def gen_workload_traffic(workload_set, K, grid):
    """For each workload, return (traffic_matrix, traffic_flat_normalized, t_max)."""
    out = []
    for name in workload_set:
        traffic = WORKLOADS[name](K, grid)
        t_max = traffic.max()
        traffic_norm = traffic / t_max if t_max > 0 else traffic
        traffic_flat = traffic_norm[np.triu_indices(K, k=1)]
        out.append((traffic, traffic_flat, t_max))
    return out


def aggregate_objective(values, mode='avg', baseline=None):
    if mode == 'avg':
        return float(np.mean(values))
    if mode == 'worst':
        return float(np.max(values))
    if mode == 'normalized_avg':
        if baseline is None:
            raise ValueError("normalized_avg requires baseline")
        return float(np.mean([v / max(b, 1e-9) for v, b in zip(values, baseline)]))
    raise ValueError(f"unknown reward_type: {mode}")


def warm_start_union_greedy(workload_traffics, grid, budget, max_dist,
                            max_lpp, all_pairs, pair_to_idx):
    """Union of per-workload greedy. Mesh adj is always >= 1 (no isolated chips)."""
    union_alloc = np.zeros(len(all_pairs), dtype=np.float32)

    adj_pairs = grid.get_adj_pairs()
    mesh_idx_set = {pair_to_idx[p] for p in adj_pairs}
    for idx in mesh_idx_set:
        union_alloc[idx] = 1

    for traffic, _, _ in workload_traffics:
        per_alloc = alloc_express_greedy(grid, traffic, budget, max_dist=max_dist)
        for p, n in per_alloc.items():
            idx = pair_to_idx[p]
            union_alloc[idx] = max(union_alloc[idx], min(n, max_lpp))

    while union_alloc.sum() > budget:
        eligible = np.where(union_alloc > 0)[0]
        if len(eligible) == 0:
            break
        eligible_trim = []
        for idx in eligible:
            if idx in mesh_idx_set:
                if union_alloc[idx] > 1:
                    eligible_trim.append(idx)
            else:
                eligible_trim.append(idx)
        if not eligible_trim:
            break
        scores = np.zeros(len(eligible_trim))
        for k, idx in enumerate(eligible_trim):
            i, j = all_pairs[idx]
            scores[k] = sum(t[i, j] + t[j, i] for t, _, _ in workload_traffics)
        worst = eligible_trim[int(np.argmin(scores))]
        union_alloc[worst] -= 1

    return union_alloc


def train_warmstart_rl_multi(
    surrogate_ra,
    workload_set,
    K, N, R, C,
    budget_per_pair,
    n_episodes=300,
    n_swaps=None,
    rate_mult=4.0,
    reward_type='avg',
    max_dist=3,
    warm_start_alloc=None,
    verbose=True,
):
    grid = ChipletGrid(R, C)
    n_workloads = len(workload_set)
    workload_traffics = gen_workload_traffic(workload_set, K, grid)

    adj_pairs = grid.get_adj_pairs()
    adj_set = set(adj_pairs)
    n_adj = len(adj_pairs)
    budget = int(n_adj * budget_per_pair)
    all_pairs = [(i, j) for i in range(K) for j in range(i + 1, K)]
    n_pairs = len(all_pairs)
    pair_to_idx = {p: i for i, p in enumerate(all_pairs)}

    hop_mask_np = np.array(
        [1 if grid.get_hops(p[0], p[1]) <= max_dist else 0 for p in all_pairs],
        dtype=bool,
    )
    hop_mask_t = torch.tensor(hop_mask_np, device=DEVICE)

    adj_pairs = grid.get_adj_pairs()
    mesh_protect_np = np.array(
        [1 if p in set(adj_pairs) else 0 for p in all_pairs], dtype=bool,
    )
    mesh_protect_t = torch.tensor(mesh_protect_np, device=DEVICE)

    if warm_start_alloc is None:
        greedy_vec = warm_start_union_greedy(
            workload_traffics, grid, budget, max_dist, N, all_pairs, pair_to_idx)
    else:
        greedy_vec = np.zeros(n_pairs, dtype=np.float32)
        for p, n in warm_start_alloc.items():
            greedy_vec[pair_to_idx[p]] = n

    traffic_flat_concat = np.concatenate(
        [tf for _, tf, _ in workload_traffics]
    ).astype(np.float32)

    def _per_workload_latencies(vec):
        latencies = []
        for _, traffic_flat, _ in workload_traffics:
            lat = surrogate_predict_ra(
                surrogate_ra, traffic_flat, vec,
                adj_set, all_pairs, K, N, budget, n_adj,
                rate_mult=rate_mult,
            )
            latencies.append(lat)
        return latencies

    baseline_latencies = _per_workload_latencies(greedy_vec)
    baseline_pred = aggregate_objective(
        baseline_latencies, reward_type, baseline=baseline_latencies)

    if n_swaps is None:
        n_swaps = max(5, budget // 7)

    # State adds 1 extra scalar (n_workloads/4) on top of single-W state.
    state_dim = n_workloads * n_pairs + n_pairs + 4
    policy = SwapPolicy(state_dim, n_pairs).to(DEVICE)
    optimizer = optim.Adam(policy.parameters(), lr=3e-4)

    best_pred = baseline_pred
    best_alloc_vec = greedy_vec.copy()
    best_latencies = baseline_latencies

    for ep in range(n_episodes):
        allocation = greedy_vec.copy()
        log_probs = []
        for _ in range(n_swaps):
            budget_frac = allocation.sum() / max(budget, 1)
            state = np.concatenate([
                traffic_flat_concat,
                allocation / N,
                [budget_frac, K / 32.0, N / 8.0, n_workloads / 4.0],
            ]).astype(np.float32)
            state_t = torch.tensor(state, device=DEVICE)
            alloc_t = torch.tensor(allocation, device=DEVICE)
            rem_idx, add_idx, logp = policy.select_swap(
                state_t, alloc_t, N,
                hop_mask=hop_mask_t,
                min_alloc_mask=mesh_protect_t,
            )
            allocation[rem_idx] -= 1
            allocation[add_idx] += 1
            log_probs.append(logp)

        latencies = _per_workload_latencies(allocation)
        pred_lat = aggregate_objective(
            latencies, reward_type, baseline=baseline_latencies)
        reward = baseline_pred - pred_lat

        if pred_lat < best_pred:
            best_pred = pred_lat
            best_alloc_vec = allocation.copy()
            best_latencies = latencies

        if log_probs:
            loss = sum(-lp * reward for lp in log_probs)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

        if verbose and (ep + 1) % 50 == 0:
            print(f"      [Multi-W |W|={n_workloads} {reward_type}] "
                  f"Ep {ep+1}: pred={pred_lat:.1f}, "
                  f"baseline={baseline_pred:.1f}, best={best_pred:.1f}",
                  flush=True)

    superset_alloc = {
        p: int(best_alloc_vec[pair_to_idx[p]])
        for p in all_pairs if best_alloc_vec[pair_to_idx[p]] > 0
    }
    return {
        'superset_alloc': superset_alloc,
        'best_pred': best_pred,
        'baseline_pred': baseline_pred,
        'best_latencies': best_latencies,
        'baseline_latencies': baseline_latencies,
        'workload_set': workload_set,
        'reward_type': reward_type,
        'K': K, 'N': N, 'budget_per_pair': budget_per_pair,
    }


def greedy_mask_per_workload(superset_alloc, traffic, grid, mask_budget,
                             max_lpp=None):
    """Pick subset of superset for one workload.

    Mesh adjacent links from the superset are ALWAYS on (preserves
    chiplet connectivity). Express links are gated by traffic*hops_saved
    until mask_budget is reached.
    """
    if max_lpp is None:
        max_lpp = mask_budget

    adj_set = set(grid.get_adj_pairs())

    mask_alloc = {p: n for p, n in superset_alloc.items() if p in adj_set}

    candidates = []
    for (i, j), n_links in superset_alloc.items():
        if (i, j) in adj_set:
            continue
        traffic_score = float(traffic[i, j] + traffic[j, i])
        hops = grid.get_hops(i, j)
        benefit = traffic_score * max(hops - 1, 1)
        for _ in range(n_links):
            candidates.append(((i, j), benefit))

    candidates.sort(key=lambda x: -x[1])

    used = sum(mask_alloc.values())
    for (i, j), _ in candidates:
        if used >= mask_budget:
            break
        cur = mask_alloc.get((i, j), 0)
        if cur < max_lpp:
            mask_alloc[(i, j)] = cur + 1
            used += 1
    return mask_alloc


def main():
    print("=== Multi-Workload Joint RL Pilot ===", flush=True)
    surrogate = load_rate_aware_surrogate()

    workload_set = ['moe', 'hybrid_tp_pp']
    K, N, R, C = 16, 4, 4, 4
    budget_per_pair = 2

    print(f"\nPilot: K={K} N={N} W={workload_set} budget={budget_per_pair}x",
          flush=True)

    result = train_warmstart_rl_multi(
        surrogate,
        workload_set=workload_set,
        K=K, N=N, R=R, C=C,
        budget_per_pair=budget_per_pair,
        n_episodes=200,
        rate_mult=4.0,
        reward_type='normalized_avg',
        max_dist=3,
    )

    print("\n=== Result ===", flush=True)
    print(f"Baseline (greedy union) aggregate: {result['baseline_pred']:.2f}",
          flush=True)
    print(f"Best RL aggregate:                 {result['best_pred']:.2f}",
          flush=True)
    if result['baseline_pred'] > 0:
        improvement = (1 - result['best_pred'] / result['baseline_pred']) * 100
        print(f"Improvement: {improvement:.2f}%", flush=True)
    print(f"\nPer-workload baseline: "
          f"{[f'{x:.1f}' for x in result['baseline_latencies']]}", flush=True)
    print(f"Per-workload best:     "
          f"{[f'{x:.1f}' for x in result['best_latencies']]}", flush=True)

    print("\n=== Per-Workload Masks ===", flush=True)
    grid = ChipletGrid(R, C)
    superset = result['superset_alloc']
    total_super = sum(superset.values())
    print(f"Superset: {len(superset)} pairs, {total_super} total links",
          flush=True)

    masks = {}
    for w_name in workload_set:
        traffic = WORKLOADS[w_name](K, grid)
        mask_budget = max(1, int(total_super * 0.7))
        mask = greedy_mask_per_workload(
            superset, traffic, grid, mask_budget, max_lpp=N)
        n_active = sum(mask.values())
        masks[w_name] = mask
        print(f"  {w_name}: {len(mask)} pairs, {n_active} active "
              f"(mask budget {mask_budget})", flush=True)

    out = {
        'workload_set': workload_set,
        'K': K, 'N': N, 'R': R, 'C': C,
        'budget_per_pair': budget_per_pair,
        'baseline_pred': result['baseline_pred'],
        'best_pred': result['best_pred'],
        'baseline_latencies': result['baseline_latencies'],
        'best_latencies': result['best_latencies'],
        'superset_alloc': {f"{p[0]}-{p[1]}": v for p, v in superset.items()},
        'masks': {
            w: {f"{p[0]}-{p[1]}": v for p, v in m.items()}
            for w, m in masks.items()
        },
    }
    out_path = RESULTS_DIR / 'pilot_multi_workload_normalized.json'
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\nSaved: {out_path}", flush=True)


if __name__ == '__main__':
    main()
