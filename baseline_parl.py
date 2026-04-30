"""PARL baseline (arXiv 2510.24113).

Partition-Aware Reinforcement Learner. Maskable PPO learns to add/remove
single express links one at a time on a chiplet NoI graph, given a
single representative traffic profile (or a mixed-workload profile).

Output: a single static topology (no runtime reconfiguration).

Implementation note: this is a PARL re-implementation following the
arXiv paper. Action space = single link toggle, with mask preventing
illegal actions (e.g., violating port budget). Reward = -interference
score (paper's metric) approximated as worst-case latency.

For an apples-to-apples comparison with our framework we use the same
surrogate to produce per-link latency under a candidate topology, then
verify the final placement with BookSim.

TODO: actual Maskable PPO training loop. This file currently exposes:
- parl_alloc(grid, traffic, link_budget, max_dist=3): produces a static
  alloc using a heuristic that mimics PARL's partition-aware bias
  (load-balance partitioned traffic onto skip links).
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from noi_topology_synthesis import ChipletGrid


def parl_heuristic_alloc(grid, traffic, budget, per_pair_cap, max_dist=3):
    """Placeholder heuristic mimicking PARL's partition-aware bias.

    Real PARL uses Maskable PPO; this heuristic ranks non-adjacent pairs by
    interference score (max traffic carried over the path through that link)
    and assigns links proportionally. Used until full PPO trainer is wired in.
    """
    K = grid.K
    adj_pairs = grid.get_adj_pairs()
    adj_set = set(adj_pairs)

    alloc = {p: 1 for p in adj_pairs}
    used = len(adj_pairs)
    if used >= budget:
        return alloc

    candidates = []
    for i in range(K):
        for j in range(i + 1, K):
            if (i, j) in adj_set:
                continue
            hops = grid.get_hops(i, j)
            if hops > max_dist:
                continue
            traf = float(traffic[i, j] + traffic[j, i])
            interference = traf * max(hops - 1, 1)
            candidates.append(((i, j), interference))
    candidates.sort(key=lambda x: -x[1])

    remaining = budget - used
    while remaining > 0 and candidates:
        progressed = False
        for p, _ in candidates:
            if remaining <= 0:
                break
            cur = alloc.get(p, 0)
            if cur < per_pair_cap:
                alloc[p] = cur + 1
                remaining -= 1
                progressed = True
        if not progressed:
            break
    return alloc


def parl_alloc(grid, traffic, budget, per_pair_cap, max_dist=3,
                use_ppo=False):
    """PARL allocator entry point.

    use_ppo=False (default): heuristic placeholder.
    use_ppo=True: Maskable PPO training (TODO).
    """
    if use_ppo:
        raise NotImplementedError(
            "Maskable PPO trainer not yet implemented; use heuristic for now")
    return parl_heuristic_alloc(grid, traffic, budget, per_pair_cap,
                                max_dist=max_dist)


if __name__ == '__main__':
    grid = ChipletGrid(4, 4)
    traffic = np.random.rand(16, 16) * 100
    traffic = (traffic + traffic.T) / 2
    np.fill_diagonal(traffic, 0)
    alloc = parl_alloc(grid, traffic, budget=48, per_pair_cap=4)
    print(f"PARL heuristic alloc: {len(alloc)} pairs, "
          f"{sum(alloc.values())} links")
