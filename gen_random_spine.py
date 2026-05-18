"""Random warm-start generators for MCTS-only superset search.

Two methods that produce diverse initial allocations without using
any baseline topology (Mesh, Kite, GIA), so they don't leak
baseline information into the MCTS warm-start pool.

  random_hop3_spine: builds a random hop-3 spanning backbone that
    connects all chips via long-range links, then fills remaining
    budget with random hop-1/hop-2 adjacency to satisfy mesh-protect.

  random_uniform_sample: samples random link pairs within wire budget,
    respecting mesh-protect (adj links always get ≥1) and per-pair cap N.
"""

import random as _random

import numpy as np


def _adj_indices(all_pairs, adj_set):
    return [i for i, p in enumerate(all_pairs) if p in adj_set]


def random_hop3_spine(
    grid, budget, N, all_pairs, pair_to_idx, adj_set, rng=None, seed=None
):
    """Random hop-3 spine warm-start as a numpy allocation vector.

    Picks a random permutation of hop-3 pairs to form a spanning
    backbone. Fills remaining budget slots from a shuffled hop-2 list,
    then adj pairs for mesh-protect. Returns float32 vec of length
    len(all_pairs) with values in [0, N].
    """
    if rng is None:
        rng = _random.Random(seed)
    n_pairs = len(all_pairs)
    vec = np.zeros(n_pairs, dtype=np.float32)

    # Mesh-protect: adj pairs must have ≥1.
    adj_idx = _adj_indices(all_pairs, adj_set)
    for i in adj_idx:
        vec[i] = 1

    hop3_idx = [i for i, p in enumerate(all_pairs)
                if grid.get_hops(p[0], p[1]) == 3 and p not in adj_set]
    hop2_idx = [i for i, p in enumerate(all_pairs)
                if grid.get_hops(p[0], p[1]) == 2 and p not in adj_set]

    rng.shuffle(hop3_idx)
    rng.shuffle(hop2_idx)

    remaining = int(budget - vec.sum())
    for idx_list in [hop3_idx, hop2_idx, adj_idx]:
        for i in idx_list:
            if remaining <= 0:
                break
            add = min(N - int(vec[i]), remaining)
            if add > 0:
                vec[i] += add
                remaining -= add
        if remaining <= 0:
            break

    return vec


def random_uniform_sample(
    grid, budget, N, all_pairs, pair_to_idx, adj_set,
    max_dist=3, rng=None, seed=None
):
    """Random uniform link sample warm-start.

    Uniformly samples pairs (within max_dist hops) and assigns 1 link
    each until budget is consumed. Mesh-protect: adj pairs start at 1.
    Returns float32 vec of length len(all_pairs).
    """
    if rng is None:
        rng = _random.Random(seed)
    n_pairs = len(all_pairs)
    vec = np.zeros(n_pairs, dtype=np.float32)

    adj_idx = _adj_indices(all_pairs, adj_set)
    for i in adj_idx:
        vec[i] = 1

    eligible = [i for i, p in enumerate(all_pairs)
                if grid.get_hops(p[0], p[1]) <= max_dist]
    rng.shuffle(eligible)

    remaining = int(budget - vec.sum())
    for i in eligible:
        if remaining <= 0:
            break
        if vec[i] < N:
            vec[i] += 1
            remaining -= 1

    return vec
