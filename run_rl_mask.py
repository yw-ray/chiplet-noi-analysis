"""Stage 2 RL: learn the best mask (subset of superset) per workload.

The Stage 1 joint multi-workload RL produces a `superset` of express
links. Stage 2 takes that superset as a hard upper bound and learns,
per workload, which subset of links to activate at runtime.

Differences from Stage 1:
  - the action space is constrained to the superset (`alloc <= superset[p]`)
  - the reward is single-workload (no multi-W aggregation)
  - mesh adj are still protected (alloc >= 1)
"""

import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.optim as optim

sys.path.insert(0, str(Path(__file__).parent))
from noi_topology_synthesis import ChipletGrid
from cost_perf_6panel_workload import WORKLOADS
from ml_express_warmstart import (
    DEVICE, RESULTS_DIR, SwapPolicy,
    load_rate_aware_surrogate, surrogate_predict_ra,
)
from run_rl_multi_workload import greedy_mask_per_workload


def train_mask_rl(surrogate, superset_alloc, workload_name,
                  K, N, R, C, mask_budget,
                  n_episodes=200, n_swaps=None,
                  rate_mult=4.0, verbose=True):
    grid = ChipletGrid(R, C)
    traffic = WORKLOADS[workload_name](K, grid)
    adj_pairs = grid.get_adj_pairs()
    adj_set = set(adj_pairs)
    n_adj = len(adj_pairs)
    all_pairs = [(i, j) for i in range(K) for j in range(i + 1, K)]
    n_pairs = len(all_pairs)
    pair_to_idx = {p: i for i, p in enumerate(all_pairs)}

    superset_vec = np.zeros(n_pairs, dtype=np.float32)
    for p, n in superset_alloc.items():
        superset_vec[pair_to_idx[p]] = n
    max_lpp = int(superset_vec.max())

    superset_mask_np = (superset_vec > 0)
    superset_mask_t = torch.tensor(superset_mask_np, device=DEVICE)

    mesh_protect_np = np.array(
        [1 if p in adj_set else 0 for p in all_pairs], dtype=bool)
    mesh_protect_t = torch.tensor(mesh_protect_np, device=DEVICE)

    init_mask = greedy_mask_per_workload(
        superset_alloc, traffic, grid, mask_budget, max_lpp=N)
    mask_vec_init = np.zeros(n_pairs, dtype=np.float32)
    for p, n in init_mask.items():
        mask_vec_init[pair_to_idx[p]] = n

    t_max = traffic.max()
    traffic_norm = traffic / t_max if t_max > 0 else traffic
    traffic_flat = traffic_norm[np.triu_indices(K, k=1)]

    def _objective(vec):
        b = max(int(vec.sum()), 1)
        return surrogate_predict_ra(
            surrogate, traffic_flat, vec, adj_set, all_pairs, K, N,
            b, n_adj, rate_mult=rate_mult)

    baseline_pred = _objective(mask_vec_init)

    if n_swaps is None:
        n_swaps = max(5, mask_budget // 7)

    state_dim = n_pairs + n_pairs + 3
    policy = SwapPolicy(state_dim, n_pairs).to(DEVICE)
    optimizer = optim.Adam(policy.parameters(), lr=3e-4)

    best_pred = baseline_pred
    best_alloc_vec = mask_vec_init.copy()

    for ep in range(n_episodes):
        allocation = mask_vec_init.copy()
        log_probs = []
        for _ in range(n_swaps):
            budget_frac = allocation.sum() / max(mask_budget, 1)
            state = np.concatenate([
                traffic_flat, allocation / max(N, 1),
                [budget_frac, K / 32.0, N / 8.0],
            ]).astype(np.float32)
            state_t = torch.tensor(state, device=DEVICE)
            alloc_t = torch.tensor(allocation, device=DEVICE)
            rem_idx, add_idx, logp = policy.select_swap(
                state_t, alloc_t, max_lpp,
                hop_mask=superset_mask_t,
                min_alloc_mask=mesh_protect_t,
            )
            if allocation[add_idx] >= superset_vec[add_idx]:
                continue
            allocation[rem_idx] -= 1
            allocation[add_idx] += 1
            log_probs.append(logp)

        pred_lat = _objective(allocation)
        reward = baseline_pred - pred_lat
        if pred_lat < best_pred:
            best_pred = pred_lat
            best_alloc_vec = allocation.copy()

        if log_probs:
            loss = sum(-lp * reward for lp in log_probs)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

        if verbose and (ep + 1) % 50 == 0:
            print(f"    [Mask RL {workload_name}] Ep {ep+1}: "
                  f"pred={pred_lat:.1f}, baseline={baseline_pred:.1f}, "
                  f"best={best_pred:.1f}", flush=True)

    mask_alloc = {p: int(best_alloc_vec[pair_to_idx[p]])
                  for p in all_pairs if best_alloc_vec[pair_to_idx[p]] > 0}
    return {
        'mask_alloc': mask_alloc,
        'best_pred': best_pred,
        'baseline_pred': baseline_pred,
        'workload': workload_name,
    }


def main():
    K, N, R, C = 16, 4, 4, 4
    workloads = ['moe', 'hybrid_tp_pp', 'uniform_random', 'all_to_all']
    grid = ChipletGrid(R, C)

    sweep_data = json.loads(
        (RESULTS_DIR / 'sweep_v2_pilot.json').read_text())
    superset = {tuple(int(x) for x in k.split('-')): v
                for k, v in sweep_data['superset'].items()}
    total_super = sum(superset.values())
    mask_budget = max(1, int(total_super * 0.7))
    print(f"Superset: {len(superset)} pairs, {total_super} links, "
          f"mask_budget={mask_budget}", flush=True)

    surrogate = load_rate_aware_surrogate()

    masks_rl = {}
    for w in workloads:
        print(f"\n  Training Mask RL for {w} ...", flush=True)
        t0 = time.time()
        result = train_mask_rl(
            surrogate, superset, w, K, N, R, C, mask_budget,
            n_episodes=200, rate_mult=4.0, verbose=True,
        )
        masks_rl[w] = result['mask_alloc']
        print(f"  Done {w}: baseline={result['baseline_pred']:.1f}, "
              f"best={result['best_pred']:.1f} "
              f"(improvement {(1 - result['best_pred']/result['baseline_pred'])*100:.2f}%) "
              f"in {time.time()-t0:.1f}s", flush=True)

    out_path = RESULTS_DIR / 'masks_rl.json'
    out_path.write_text(json.dumps({
        'K': K, 'N': N, 'workloads': workloads,
        'mask_budget': mask_budget,
        'superset': {f"{p[0]}-{p[1]}": v for p, v in superset.items()},
        'masks_rl': {w: {f"{p[0]}-{p[1]}": v for p, v in m.items()}
                     for w, m in masks_rl.items()},
    }, indent=2))
    print(f"\nSaved: {out_path}", flush=True)

    print("\nMask diff vs greedy:", flush=True)
    masks_greedy = {w: {tuple(int(x) for x in k.split('-')): v
                        for k, v in m.items()}
                    for w, m in sweep_data['masks'].items()}
    for w in workloads:
        gset = set(masks_greedy[w].keys())
        rset = set(masks_rl[w].keys())
        only_g = gset - rset
        only_r = rset - gset
        print(f"  {w:<18}: greedy {len(gset)} pairs, RL {len(rset)} pairs, "
              f"diff +{len(only_r)} -{len(only_g)}", flush=True)


if __name__ == '__main__':
    main()
