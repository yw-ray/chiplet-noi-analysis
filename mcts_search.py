"""MCTS-based superset search for joint multi-workload chiplet NoI.

Replaces REINFORCE with Monte Carlo Tree Search. Each tree node holds a
candidate allocation; actions are swap (remove_idx, add_idx) pairs.
Selection uses UCB1, simulation uses random rollouts evaluated by the
rate-aware surrogate, top-K leaf states are returned for BookSim
verification.

Why MCTS: REINFORCE produces a single greedy trajectory and gets stuck in
local optima. MCTS maintains a tree and expands promising branches,
allowing exploration of diverse trajectories simultaneously. With a good
prior (greedy_union warm-start) and sufficient iterations, MCTS escapes
the hub-spoke local optimum that traps REINFORCE on dense workloads.
"""

import math
import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from ml_express_warmstart import surrogate_predict_ra, surrogate_predict_v3


class MCTSNode:
    __slots__ = ('state', 'parent', 'action', 'children', 'visits',
                 'total_value', 'depth', 'untried_actions')

    def __init__(self, state, parent=None, action=None, depth=0,
                 untried_actions=None):
        self.state = state.copy() if state is not None else None
        self.parent = parent
        self.action = action
        self.children = {}
        self.visits = 0
        self.total_value = 0.0
        self.depth = depth
        # Lazy-populated when expansion is needed.
        self.untried_actions = untried_actions

    @property
    def avg_value(self):
        return self.total_value / max(self.visits, 1)

    def ucb_score(self, c=1.4):
        if self.visits == 0:
            return float('inf')
        if self.parent is None or self.parent.visits == 0:
            return self.avg_value
        return (self.avg_value
                + c * math.sqrt(math.log(self.parent.visits) / self.visits))

    def is_fully_expanded(self):
        return (self.untried_actions is not None
                and not self.untried_actions)


def enumerate_swap_actions(state, hop_mask_np, mesh_protect_np, N,
                           max_actions, rng, backbone_mask_np=None):
    """Sample legal swap actions from the current state.

    Removable index: alloc>0 and (not protected OR alloc>1).
    Protection = mesh_protect OR backbone_mask (links that must stay >= 1).
    Addable index: hop_mask True and alloc<N (per-pair cap).
    Returns up to max_actions unique (remove_idx, add_idx) tuples.
    """
    if backbone_mask_np is not None:
        protect_np = mesh_protect_np | backbone_mask_np
    else:
        protect_np = mesh_protect_np

    removable = []
    addable = []
    for i in range(len(state)):
        if state[i] > 0:
            if protect_np[i]:
                if state[i] > 1:
                    removable.append(i)
            else:
                removable.append(i)
        if hop_mask_np[i] and state[i] < N:
            addable.append(i)
    if not removable or not addable:
        return []
    actions = set()
    attempts = 0
    while len(actions) < max_actions and attempts < max_actions * 4:
        attempts += 1
        rem = rng.choice(removable)
        add = rng.choice(addable)
        if rem == add:
            continue
        actions.add((rem, add))
    return list(actions)


def apply_swap(state, action):
    new_state = state.copy()
    rem, add = action
    new_state[rem] -= 1
    new_state[add] += 1
    return new_state


def evaluate_state(state, surrogate, surrogate_args_per_workload,
                   surrogate_version='v2'):
    """Evaluate state under multi-workload surrogate (mean over workloads).

    surrogate_args_per_workload: list of dicts with per-workload args.
    surrogate_version: 'v2' uses surrogate_predict_ra (bpp/express_frac);
                       'v3' uses surrogate_predict_v3 (full alloc_flat).
    """
    lats = []
    for args in surrogate_args_per_workload:
        if surrogate_version == 'v3':
            lat = surrogate_predict_v3(
                surrogate, args['traffic_flat'], state,
                args['all_pairs'], args['N'],
                args['K'], args['N'],
                rate_mult=args.get('rate_mult', 4.0),
            )
        else:
            lat = surrogate_predict_ra(
                surrogate, args['traffic_flat'], state,
                args['adj_set'], args['all_pairs'],
                args['K'], args['N'], args['budget'], args['n_adj'],
                rate_mult=args.get('rate_mult', 4.0),
            )
        lats.append(lat)
    return float(np.mean(lats))


MCTS_PROFILES = {
    'default': dict(n_iters=1500, rollout_depth=12,
                    expansion_branch=25, rollout_branch=8, top_k=1),
    'strong':  dict(n_iters=5000, rollout_depth=20,
                    expansion_branch=40, rollout_branch=12, top_k=1),
}


def mcts_search(
    initial_state,
    surrogate,
    surrogate_args_per_workload,
    hop_mask_np,
    mesh_protect_np,
    N,
    n_iters=600,
    rollout_depth=12,
    expansion_branch=20,
    rollout_branch=8,
    top_k=5,
    seed=42,
    verbose=False,
    surrogate_version='v2',
    backbone_mask_np=None,
):
    """Run MCTS rooted at initial_state, return top-k unique leaf
    allocations by surrogate value (lowest predicted latency first).
    """
    rng = random.Random(seed)
    root = MCTSNode(state=initial_state, depth=0)

    # Track all leaves with their evaluated value (= -mean_pred_lat).
    leaf_records = []  # list of (state, value)

    for it in range(n_iters):
        # === 1. Selection ===
        node = root
        while node.children and node.is_fully_expanded():
            node = max(node.children.values(), key=lambda c: c.ucb_score())

        # === 2. Expansion ===
        if node.depth < rollout_depth:
            if node.untried_actions is None:
                node.untried_actions = enumerate_swap_actions(
                    node.state, hop_mask_np, mesh_protect_np, N,
                    expansion_branch, rng,
                    backbone_mask_np=backbone_mask_np)
            if node.untried_actions:
                action = node.untried_actions.pop()
                child_state = apply_swap(node.state, action)
                child = MCTSNode(
                    state=child_state, parent=node, action=action,
                    depth=node.depth + 1)
                node.children[action] = child
                node = child

        # === 3. Simulation: random rollout to rollout_depth ===
        sim_state = node.state.copy()
        sim_depth = node.depth
        while sim_depth < rollout_depth:
            actions = enumerate_swap_actions(
                sim_state, hop_mask_np, mesh_protect_np, N,
                rollout_branch, rng,
                backbone_mask_np=backbone_mask_np)
            if not actions:
                break
            sim_action = rng.choice(actions)
            sim_state = apply_swap(sim_state, sim_action)
            sim_depth += 1

        # === 4. Evaluation: surrogate on the rolled-out state ===
        pred_lat = evaluate_state(sim_state, surrogate,
                                  surrogate_args_per_workload,
                                  surrogate_version=surrogate_version)
        value = -pred_lat
        leaf_records.append((sim_state.copy(), pred_lat))

        # === 5. Backpropagation ===
        n = node
        while n is not None:
            n.visits += 1
            n.total_value += value
            n = n.parent

        if verbose and ((it + 1) % 100 == 0):
            print(f"      [mcts] iter {it+1:>4}: best_pred_lat="
                  f"{min(r[1] for r in leaf_records):.1f}", flush=True)

    # Deduplicate by state hash and sort ascending by predicted latency.
    seen = set()
    sorted_records = sorted(leaf_records, key=lambda r: r[1])
    top = []
    for state, lat in sorted_records:
        key = tuple(state.tolist())
        if key in seen:
            continue
        seen.add(key)
        top.append((state, lat))
        if len(top) >= top_k:
            break
    return top
