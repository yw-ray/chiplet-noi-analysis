"""BookSim-in-the-loop multi-workload RL.

Replaces the surrogate reward in train_warmstart_rl_multi with direct
BookSim measurements. Each episode rolls out n_swaps actions from the
warm-start, then BookSim-measures the resulting allocation on every
workload in the subset. Reward is the negative mean BookSim latency
(or baseline minus measured), so the policy gradient is computed
against the *true* objective rather than the surrogate.

Cost: ~30-60s per BookSim call × |subset| × n_episodes per seed.
For a 3-workload subset at 50 episodes that is ≈ 75 min/seed.
"""

import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.optim as optim

sys.path.insert(0, str(Path(__file__).parent))
from noi_topology_synthesis import ChipletGrid
from cost_performance_experiment import alloc_express_greedy
from cost_perf_6panel_workload import WORKLOADS
from ml_express_warmstart import DEVICE, SwapPolicy
from run_rl_multi_workload import (
    gen_workload_traffic,
    warm_start_union_greedy,
)
from sweep_v2_mask_greedy import run_booksim_alloc


def vec_to_alloc_dict(vec, all_pairs, N):
    return {p: min(int(vec[i]), N) for i, p in enumerate(all_pairs)
            if vec[i] > 0}


def measure_mean_lat(vec, all_pairs, K, N, R, C, subset, label, cap=None):
    """Run BookSim for each workload in subset, return mean latency."""
    alloc = vec_to_alloc_dict(vec, all_pairs, N)
    if not alloc:
        return None, {}
    per_wl = {}
    for w in subset:
        try:
            res = run_booksim_alloc(f'{label}_{w}', alloc,
                                    K, N, R, C, w)
            per_wl[w] = res.get('latency')
        except Exception as exc:
            print(f"        [WARN] BookSim {w} failed: {exc}",
                  flush=True)
            per_wl[w] = None
    valid = [v for v in per_wl.values() if v is not None]
    if not valid:
        return None, per_wl
    mean = float(np.mean(valid))
    if cap is not None and mean > cap:
        mean = cap
    return mean, per_wl


def train_booksim_in_loop_rl_multi(
    workload_set,
    K, N, R, C,
    budget_per_pair,
    n_episodes=50,
    n_swaps=8,
    warm_start_alloc=None,
    max_dist=3,
    label_prefix='bs_rl',
    cap_mean_lat=None,
    verbose=True,
):
    """REINFORCE multi-workload RL with BookSim reward.

    Returns a dict with the best allocation by *measured* mean BookSim
    latency over the subset, plus the entire training trace.
    """
    grid = ChipletGrid(R, C)
    workload_traffics = gen_workload_traffic(workload_set, K, grid)
    adj_pairs = grid.get_adj_pairs()
    adj_set = set(adj_pairs)
    n_adj = len(adj_pairs)
    budget = int(n_adj * budget_per_pair)
    all_pairs = [(i, j) for i in range(K) for j in range(i + 1, K)]
    n_pairs = len(all_pairs)
    pair_to_idx = {p: i for i, p in enumerate(all_pairs)}

    hop_mask_np = np.array(
        [1 if grid.get_hops(p[0], p[1]) <= max_dist else 0
         for p in all_pairs], dtype=bool,
    )
    hop_mask_t = torch.tensor(hop_mask_np, device=DEVICE)
    mesh_protect_np = np.array(
        [1 if p in adj_set else 0 for p in all_pairs], dtype=bool,
    )
    mesh_protect_t = torch.tensor(mesh_protect_np, device=DEVICE)

    if warm_start_alloc is None:
        warm_vec = warm_start_union_greedy(
            workload_traffics, grid, budget, max_dist, N,
            all_pairs, pair_to_idx)
    else:
        warm_vec = np.zeros(n_pairs, dtype=np.float32)
        for p, v in warm_start_alloc.items():
            warm_vec[pair_to_idx[p]] = v

    traffic_flat_concat = np.concatenate(
        [tf for _, tf, _ in workload_traffics]).astype(np.float32)

    n_workloads = len(workload_set)
    state_dim = n_workloads * n_pairs + n_pairs + 4
    policy = SwapPolicy(state_dim, n_pairs).to(DEVICE)
    optimizer = optim.Adam(policy.parameters(), lr=3e-4)

    # Baseline = warm-start measured latency (one BookSim).
    base_mean, base_per_wl = measure_mean_lat(
        warm_vec, all_pairs, K, N, R, C, workload_set,
        f'{label_prefix}_baseline', cap=cap_mean_lat)
    if base_mean is None:
        if verbose:
            print(f"      [bs_rl] baseline measurement failed", flush=True)
        return {
            'best_alloc_vec': warm_vec.tolist(),
            'best_mean_lat': None,
            'baseline_mean_lat': None,
            'history': [],
        }
    if verbose:
        print(f"      [bs_rl] baseline mean_lat={base_mean:.1f}",
              flush=True)

    best_alloc_vec = warm_vec.copy()
    best_mean = base_mean
    best_per_wl = dict(base_per_wl)

    # Reward baseline tracker (running mean of measured rewards) to
    # reduce variance.
    reward_ema = 0.0
    ema_alpha = 0.1
    history = [{
        'episode': 0, 'event': 'baseline',
        'mean_lat': base_mean, 'per_wl': base_per_wl,
    }]

    for ep in range(n_episodes):
        t_ep = time.time()
        allocation = warm_vec.copy()
        log_probs = []
        for _ in range(n_swaps):
            budget_frac = allocation.sum() / max(budget, 1)
            state = np.concatenate([
                traffic_flat_concat,
                allocation / N,
                [budget_frac, K / 32.0, N / 8.0,
                 n_workloads / 4.0],
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

        mean_lat, per_wl = measure_mean_lat(
            allocation, all_pairs, K, N, R, C, workload_set,
            f'{label_prefix}_ep{ep+1}', cap=cap_mean_lat)
        ep_t = time.time() - t_ep
        if mean_lat is None:
            if verbose:
                print(f"        [bs_rl] ep{ep+1}: BookSim FAIL "
                      f"({ep_t:.0f}s)", flush=True)
            history.append({
                'episode': ep + 1, 'event': 'fail',
                'mean_lat': None, 'time_s': ep_t,
            })
            continue

        if mean_lat < best_mean:
            best_mean = mean_lat
            best_alloc_vec = allocation.copy()
            best_per_wl = dict(per_wl)

        # Reward = improvement over running baseline. Center with EMA.
        raw_reward = base_mean - mean_lat
        reward_ema = (1 - ema_alpha) * reward_ema + ema_alpha * raw_reward
        adv = raw_reward - reward_ema

        if log_probs:
            loss = sum(-lp * adv for lp in log_probs)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

        history.append({
            'episode': ep + 1,
            'mean_lat': mean_lat,
            'per_wl': per_wl,
            'reward': raw_reward,
            'adv': float(adv),
            'best_mean_lat': best_mean,
            'time_s': ep_t,
        })
        if verbose and ((ep + 1) % 5 == 0 or mean_lat <= best_mean):
            print(f"        [bs_rl] ep{ep+1:>3}: lat={mean_lat:>6.1f} "
                  f"best={best_mean:>6.1f} reward={raw_reward:+.1f} "
                  f"({ep_t:.0f}s)", flush=True)

    return {
        'best_alloc_vec': best_alloc_vec.tolist(),
        'best_alloc': vec_to_alloc_dict(best_alloc_vec, all_pairs, N),
        'best_mean_lat': best_mean,
        'best_per_wl': best_per_wl,
        'baseline_mean_lat': base_mean,
        'history': history,
    }
