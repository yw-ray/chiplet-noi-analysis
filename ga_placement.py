"""Genetic Algorithm for express link placement.

Population: list of allocation vectors (one entry per pair).
Fitness: -surrogate_predict_ra at rate-weighted objective.
Seeds: greedy, FBfly, and set-operation hybrids of the two.
Operators: uniform crossover (pair-level), mutation (random swap).

Key guarantee: greedy and FBfly are explicitly in the initial population
AND always retained via elitism. So the GA's best ≤ min(greedy, FBfly)
at worst, by construction.
"""
import numpy as np
import torch
import random
from collections import Counter


def _allocation_dict_to_vec(alloc_dict, pair_to_idx, n_pairs):
    v = np.zeros(n_pairs, dtype=np.float32)
    for p, n in alloc_dict.items():
        v[pair_to_idx[p]] = n
    return v


def _vec_to_alloc_dict(vec, all_pairs):
    return {p: int(vec[i]) for i, p in enumerate(all_pairs) if vec[i] > 0}


def _repair(vec, adj_set, all_pairs, N, budget, n_adj):
    """Repair allocation to satisfy budget and per-pair cap N.

    Strategy:
    - Cap each entry to N (per-pair max).
    - Ensure total = budget by adjusting to most-needy / least-needy adj pairs.
    """
    vec = np.minimum(vec, N)
    total = int(vec.sum())
    if total == budget:
        return vec
    # Adjust on adj pairs
    adj_idx = [i for i, p in enumerate(all_pairs) if p in adj_set]
    if total < budget:
        # Add to adj pairs with room
        delta = budget - total
        random.shuffle(adj_idx)
        i = 0
        while delta > 0 and i < len(adj_idx) * 10:
            k = adj_idx[i % len(adj_idx)]
            if vec[k] < N:
                vec[k] += 1; delta -= 1
            i += 1
    elif total > budget:
        # Remove from pairs with >1
        delta = total - budget
        non_adj_idx = [i for i, p in enumerate(all_pairs) if p not in adj_set and vec[i] > 0]
        random.shuffle(non_adj_idx)
        i = 0
        while delta > 0 and i < len(non_adj_idx) * 10:
            k = non_adj_idx[i % len(non_adj_idx)]
            if vec[k] > 0:
                vec[k] -= 1; delta -= 1
            i += 1
        # If still need to remove, take from adj_pairs
        if delta > 0:
            random.shuffle(adj_idx)
            i = 0
            while delta > 0 and i < len(adj_idx) * 10:
                k = adj_idx[i % len(adj_idx)]
                if vec[k] > 1:
                    vec[k] -= 1; delta -= 1
                i += 1
    return np.minimum(vec, N)


def _crossover(vec_a, vec_b, rng):
    """Uniform crossover per pair."""
    mask = rng.random(len(vec_a)) < 0.5
    out = np.where(mask, vec_a, vec_b)
    return out.astype(np.float32)


def _mutate_swap(vec, max_swaps, N):
    """Randomly move 1-max_swaps links between pairs."""
    v = vec.copy()
    n = random.randint(1, max(1, max_swaps))
    for _ in range(n):
        # Find pair with > 0 links to take from
        src_candidates = np.where(v > 0)[0]
        if len(src_candidates) == 0: break
        src = random.choice(src_candidates.tolist())
        # Find pair with < N to add to
        dst_candidates = np.where(v < N)[0]
        if len(dst_candidates) == 0: break
        dst = random.choice(dst_candidates.tolist())
        if src != dst:
            v[src] -= 1; v[dst] += 1
    return v


def _set_op_hybrids(greedy_vec, fbfly_vec, adj_set, all_pairs, N, budget, n_adj):
    """Create hybrid placements via set-like operations on express link sets."""
    hybrids = []
    # Union: pair-wise max
    u = np.maximum(greedy_vec, fbfly_vec)
    hybrids.append(_repair(u, adj_set, all_pairs, N, budget, n_adj))
    # Intersection: pair-wise min
    inter = np.minimum(greedy_vec, fbfly_vec)
    hybrids.append(_repair(inter, adj_set, all_pairs, N, budget, n_adj))
    # Average rounded
    avg = np.round((greedy_vec + fbfly_vec) / 2).astype(np.float32)
    hybrids.append(_repair(avg, adj_set, all_pairs, N, budget, n_adj))
    # Greedy on adj + FBfly express
    mix1 = greedy_vec.copy()
    for i, p in enumerate(all_pairs):
        if p not in adj_set:
            mix1[i] = fbfly_vec[i]
    hybrids.append(_repair(mix1, adj_set, all_pairs, N, budget, n_adj))
    # FBfly on adj + greedy express
    mix2 = fbfly_vec.copy()
    for i, p in enumerate(all_pairs):
        if p not in adj_set:
            mix2[i] = greedy_vec[i]
    hybrids.append(_repair(mix2, adj_set, all_pairs, N, budget, n_adj))
    return hybrids


def ga_search(surrogate_ra, traffic_flat, greedy_alloc, fbfly_alloc,
               adj_set, all_pairs, K, N, budget, n_adj,
               rate_weights, n_generations=100, pop_size=40,
               elitism=4, mutation_prob=0.3, seed=0, surrogate_predict_ra_fn=None):
    """Run GA for placement search.

    Returns: list of (allocation_vec, predicted_score) sorted best-first,
             including at least unmodified greedy and fbfly.
    """
    rng = np.random.default_rng(seed)
    random.seed(seed)
    pair_to_idx = {p: i for i, p in enumerate(all_pairs)}
    n_pairs = len(all_pairs)

    # Build initial population
    greedy_vec = _allocation_dict_to_vec(greedy_alloc, pair_to_idx, n_pairs)
    fbfly_vec = _allocation_dict_to_vec(fbfly_alloc, pair_to_idx, n_pairs)

    pop = [greedy_vec.copy(), fbfly_vec.copy()]
    pop.extend(_set_op_hybrids(greedy_vec, fbfly_vec, adj_set, all_pairs, N, budget, n_adj))
    # Fill rest with random mutations of greedy/fbfly
    while len(pop) < pop_size:
        base = greedy_vec.copy() if random.random() < 0.5 else fbfly_vec.copy()
        mutant = _mutate_swap(base, max_swaps=max(3, budget // 10), N=N)
        mutant = _repair(mutant, adj_set, all_pairs, N, budget, n_adj)
        pop.append(mutant)
    pop = pop[:pop_size]

    def fitness(vec):
        s = 0.0; w = 0.0
        for r, weight in rate_weights.items():
            p = surrogate_predict_ra_fn(surrogate_ra, traffic_flat, vec, adj_set,
                                         all_pairs, K, N, budget, n_adj, rate_mult=r)
            s += weight * p; w += weight
        return s / max(w, 1e-9)

    # Evaluate initial population
    scores = [fitness(v) for v in pop]

    for gen in range(n_generations):
        # Sort by score (lower = better)
        sorted_idx = np.argsort(scores)
        pop = [pop[i] for i in sorted_idx]
        scores = [scores[i] for i in sorted_idx]

        # Elitism: keep top-k
        new_pop = [pop[i].copy() for i in range(elitism)]
        new_scores = list(scores[:elitism])

        # Fill rest via crossover + mutation
        while len(new_pop) < pop_size:
            # Tournament select 2 parents
            parent_idxs = []
            for _ in range(2):
                cand = random.sample(range(min(len(pop), pop_size)), 3)
                best = min(cand, key=lambda j: scores[j])
                parent_idxs.append(best)
            p1, p2 = pop[parent_idxs[0]], pop[parent_idxs[1]]
            child = _crossover(p1, p2, rng)
            if random.random() < mutation_prob:
                child = _mutate_swap(child, max_swaps=max(3, budget // 10), N=N)
            child = _repair(child, adj_set, all_pairs, N, budget, n_adj)
            new_pop.append(child)
            new_scores.append(fitness(child))

        pop = new_pop
        scores = new_scores

        if (gen + 1) % 20 == 0:
            print(f'      GA gen {gen+1}: best_score={min(scores):.2f}', flush=True)

    # Final ranking + always include greedy/fbfly explicitly
    final = sorted(zip(pop, scores), key=lambda x: x[1])
    # Ensure greedy and fbfly vectors themselves are in the result
    has_greedy = any(np.array_equal(v, greedy_vec) for v, _ in final)
    has_fbfly = any(np.array_equal(v, fbfly_vec) for v, _ in final)
    result = [(v, s) for v, s in final]
    if not has_greedy:
        result.append((greedy_vec, fitness(greedy_vec)))
    if not has_fbfly:
        result.append((fbfly_vec, fitness(fbfly_vec)))
    result = sorted(result, key=lambda x: x[1])
    return result
