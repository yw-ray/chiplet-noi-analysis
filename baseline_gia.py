"""GIA baseline (Li et al., ICCAD 2022).

General Interposer Architecture: a reusable interposer with assembly-time
configurable routers. Internally each chiplet sees a Fat-Tree-like subnet
provided by the interposer (rather than a flat mesh).

Implementation: we approximate GIA's Fat-Tree subnet by augmenting a
mesh with Fat-Tree style "spine" links — links connecting non-adjacent
chiplets along row/column axes that effectively halve the diameter.

Like Kite, this is traffic-agnostic (assembly-time configuration).
Unlike Kite, the link distribution mimics Fat-Tree (more long-range
links between hub points than between leaves).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from noi_topology_synthesis import ChipletGrid


def gia_alloc(grid, budget, per_pair_cap, max_dist=3):
    """GIA Fat-Tree-style alloc: mesh + spine links between hub chiplets.

    Hub chiplets are picked at row/col centroids (a Fat-Tree-like
    aggregation). Long-range spine links connect hubs to each other and to
    edge chiplets, biased toward longer link lengths within max_dist.
    """
    K = grid.K
    R = grid.rows if hasattr(grid, 'rows') else None
    C = grid.cols if hasattr(grid, 'cols') else None
    adj_pairs = grid.get_adj_pairs()
    adj_set = set(adj_pairs)

    if R is None or C is None:
        # Fallback: figure out R, C from grid size
        R = int(K ** 0.5)
        C = K // R

    alloc = {p: 1 for p in adj_pairs}
    used = len(adj_pairs)
    if used >= budget:
        return alloc

    hub_rows = [R // 4, 3 * R // 4] if R >= 4 else [R // 2]
    hub_cols = [C // 4, 3 * C // 4] if C >= 4 else [C // 2]
    hub_ids = set()
    for r in hub_rows:
        for c in hub_cols:
            hub_ids.add(r * C + c)

    spine = []
    for h1 in hub_ids:
        for h2 in hub_ids:
            if h1 >= h2:
                continue
            if (h1, h2) in adj_set:
                continue
            hops = grid.get_hops(h1, h2)
            if hops <= max_dist:
                spine.append((h1, h2))

    leaf_to_hub = []
    for i in range(K):
        if i in hub_ids:
            continue
        for h in hub_ids:
            p = (min(i, h), max(i, h))
            if p in adj_set:
                continue
            hops = grid.get_hops(p[0], p[1])
            if hops <= max_dist:
                leaf_to_hub.append((p, hops))
    leaf_to_hub.sort(key=lambda x: -x[1])  # prefer longer links (Fat-Tree-like)

    remaining = budget - used

    for p in spine:
        if remaining <= 0:
            break
        cur = alloc.get(p, 0)
        if cur < per_pair_cap:
            alloc[p] = cur + 1
            remaining -= 1

    while remaining > 0:
        progressed = False
        for p, _ in leaf_to_hub:
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


if __name__ == '__main__':
    for R, C in [(4, 4), (4, 8)]:
        grid = ChipletGrid(R, C)
        K = R * C
        n_adj = len(grid.get_adj_pairs())
        budget = n_adj * 2
        alloc = gia_alloc(grid, budget, 4)
        from collections import Counter
        hops = Counter()
        for (i, j), n in alloc.items():
            hops[grid.get_hops(i, j)] += n
        print(f"GIA K={K} (R={R} C={C}): {len(alloc)} pairs, "
              f"{sum(alloc.values())} links, hops={dict(sorted(hops.items()))}")
