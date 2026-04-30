"""Static topology baselines for V2 multi-workload comparison.

All baselines are TRAFFIC-AGNOSTIC: a single allocation is produced from
(grid, budget, per_pair_cap), independent of any workload.  This is the
defining property that distinguishes them from PARL and our framework,
both of which use traffic information.

Allocation format: dict {(i, j) with i<j : n_links}.  Empty dict means
no express links (mesh).

Topologies implemented here:
  mesh        : no express, just the implicit adjacent grid.
  kite_alloc  : DAC 2020 (Yin et al.), three variants by link length.

GIA and PARL live in separate files (more complex implementations).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from noi_topology_synthesis import ChipletGrid  # noqa: F401  (re-export friendly)


def mesh_alloc(grid, budget, per_pair_cap):
    """Mesh: distribute the wire budget across ADJACENT pairs only.

    Mesh-preserving: every adj pair starts with 1 link, then remaining
    budget is distributed round-robin up to per_pair_cap. Guarantees
    chiplet connectivity (no isolated chips).
    """
    adj_pairs = grid.get_adj_pairs()
    if not adj_pairs or budget <= 0:
        return {}
    n_adj = len(adj_pairs)
    if budget < n_adj:
        return {p: 1 for p in adj_pairs[:budget]}
    alloc = {p: 1 for p in adj_pairs}
    remaining = budget - n_adj
    while remaining > 0:
        progressed = False
        for p in adj_pairs:
            if remaining <= 0:
                break
            if alloc[p] < per_pair_cap:
                alloc[p] += 1
                remaining -= 1
                progressed = True
        if not progressed:
            break
    return alloc


def kite_alloc(grid, budget, per_pair_cap, variant='small'):
    """Kite topology family (Yin et al., DAC 2020).

    Kite augments a mesh with a *fixed-length* family of express links.
    We implement a simplified, traffic-agnostic version: choose the set of
    Manhattan distances allowed for express, then distribute the budget
    uniformly (round-robin) across all non-adjacent pairs at those
    distances, capped at per_pair_cap.

    Variants (chiplet-NoI adaptation, max_dist=3):
      small  : distance 2 only       — short bypass family
      medium : distances 2 and 3     — mixed family
      large  : distance 3 only       — long bypass family

    Returns: {(i,j): n_links} for non-adjacent pairs only.
    """
    K = grid.K
    adj_pairs = grid.get_adj_pairs()
    adj_set = set(adj_pairs)

    if variant == 'small':
        target_dists = (2,)
    elif variant == 'medium':
        target_dists = (2, 3)
    elif variant == 'large':
        target_dists = (3,)
    else:
        raise ValueError(f"unknown Kite variant: {variant}")

    alloc = {p: 1 for p in adj_pairs}
    remaining = budget - len(adj_pairs)

    eligible = []
    for i in range(K):
        for j in range(i + 1, K):
            if (i, j) in adj_set:
                continue
            if grid.get_hops(i, j) in target_dists:
                eligible.append((i, j))

    if remaining <= 0 or not eligible:
        return alloc

    if variant == 'medium':
        # Interleave dist=2 and dist=3 so kite_m gets a true mixed family
        elig_2 = sorted([p for p in eligible
                         if grid.get_hops(p[0], p[1]) == 2])
        elig_3 = sorted([p for p in eligible
                         if grid.get_hops(p[0], p[1]) == 3])
        eligible = []
        for k in range(max(len(elig_2), len(elig_3))):
            if k < len(elig_2):
                eligible.append(elig_2[k])
            if k < len(elig_3):
                eligible.append(elig_3[k])
    else:
        eligible.sort(key=lambda p: (grid.get_hops(p[0], p[1]),
                                      p[0], p[1]))

    while remaining > 0:
        progressed = False
        for p in eligible:
            if remaining <= 0:
                break
            cur = alloc.get(p, 0)
            if cur < per_pair_cap:
                alloc[p] = cur + 1
                remaining -= 1
                progressed = True
        if not progressed:
            break  # every eligible pair is at per_pair_cap
    return alloc


BASELINE_REGISTRY = {
    'mesh':   lambda g, b, c: mesh_alloc(g, b, c),
    'kite_s': lambda g, b, c: kite_alloc(g, b, c, variant='small'),
    'kite_m': lambda g, b, c: kite_alloc(g, b, c, variant='medium'),
    'kite_l': lambda g, b, c: kite_alloc(g, b, c, variant='large'),
}


if __name__ == '__main__':
    grid = ChipletGrid(4, 4)
    n_adj = len(grid.get_adj_pairs())
    budget = n_adj * 2
    print(f"Grid 4x4 (K=16): n_adj={n_adj}, budget={budget}, per_pair_cap=4")
    print()
    for name, fn in BASELINE_REGISTRY.items():
        alloc = fn(grid, budget, 4)
        n_pairs = len(alloc)
        n_links = sum(alloc.values())
        if alloc:
            dists = sorted({grid.get_hops(i, j) for (i, j) in alloc})
        else:
            dists = []
        print(f"  {name:<8s}: {n_pairs:>3d} pairs, {n_links:>3d} links, "
              f"distances {dists}")
