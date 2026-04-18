"""
Gymnasium environment for chiplet partitioning.

State:  node features + current partial assignment + graph structure
Action: assign next unassigned module to a chiplet
Reward: improvement in partition quality after each assignment

This is a sequential decision problem: the agent assigns modules
one at a time, building up a complete partition.
"""

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from .netlist import (
    create_transformer_accelerator_netlist,
    get_node_features,
    get_edge_bandwidth_matrix,
)
from .evaluator import evaluate_partition


class ChipletPartitionEnv(gym.Env):
    """
    RL environment for chiplet partitioning.

    Episode:
      1. A netlist is loaded
      2. Agent assigns modules to chiplets one by one
      3. Episode ends when all modules are assigned
      4. Final reward based on partition quality

    Observation:
      - Current module's features [F]
      - Per-chiplet aggregated stats [K × S]
      - Assignment progress
      Flattened into a single vector.

    Action:
      - Discrete: chiplet_id in [0, K-1]
    """

    metadata = {'render_modes': ['human']}

    def __init__(self, num_chiplets=4, num_tensor_cores=16, num_sram_banks=8,
                 num_hbm_ctrl=4, reward_weights=None):
        super().__init__()

        self.num_chiplets = num_chiplets
        self.netlist_params = {
            'num_tensor_cores': num_tensor_cores,
            'num_sram_banks': num_sram_banks,
            'num_hbm_ctrl': num_hbm_ctrl,
        }

        # Reward weights
        self.reward_weights = reward_weights or {
            'comm': 5.0,      # inter-chiplet communication (most important)
            'balance': 3.0,   # load balance
            'cost': 1.0,      # manufacturing cost
            'thermal': 1.0,   # thermal feasibility
            'empty': 2.0,     # penalize empty chiplets
        }

        # Build netlist
        self.G = create_transformer_accelerator_netlist(**self.netlist_params)
        self.num_modules = self.G.number_of_nodes()
        self.node_features = get_node_features(self.G)
        self.bw_matrix = get_edge_bandwidth_matrix(self.G)

        # Feature dimensions
        self.node_feat_dim = self.node_features.shape[1]  # 10 (v2 netlist)
        self.chiplet_stat_dim = 4  # area, power, compute, num_modules per chiplet
        self.obs_dim = (self.node_feat_dim          # current module features
                        + self.num_chiplets * self.chiplet_stat_dim  # chiplet stats
                        + 1                         # progress (fraction assigned)
                        + self.num_chiplets)        # inter-chiplet BW to each chiplet

        # Spaces
        self.action_space = spaces.Discrete(num_chiplets)
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf,
            shape=(self.obs_dim,), dtype=np.float32
        )

        # State
        self.assignment = None
        self.current_module = 0
        self.module_order = None

    def _get_module_order(self):
        """Order modules for assignment (BFS from highest-degree node)."""
        # Start from the node with highest total bandwidth
        bw_sum = self.bw_matrix.sum(axis=1)
        start = int(np.argmax(bw_sum))

        # BFS ordering
        visited = set()
        queue = [start]
        order = []
        while queue:
            node = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            order.append(node)
            # Add neighbors sorted by bandwidth (highest first)
            neighbors = [(self.bw_matrix[node][n], n) for n in self.G.neighbors(node)
                         if n not in visited]
            neighbors.sort(reverse=True)
            queue.extend([n for _, n in neighbors])

        # Add any remaining unvisited nodes
        for n in range(self.num_modules):
            if n not in visited:
                order.append(n)

        return order

    def _get_obs(self):
        """Build observation vector."""
        if self.current_module >= len(self.module_order):
            # Episode should be done, return zeros
            return np.zeros(self.obs_dim, dtype=np.float32)

        mod_id = self.module_order[self.current_module]

        # 1. Current module features
        mod_feat = self.node_features[mod_id]

        # 2. Per-chiplet aggregated stats
        chiplet_stats = np.zeros((self.num_chiplets, self.chiplet_stat_dim),
                                 dtype=np.float32)
        for i in range(self.current_module):
            nid = self.module_order[i]
            cid = self.assignment[nid]
            n = self.G.nodes[nid]
            chiplet_stats[cid][0] += n['area']
            chiplet_stats[cid][1] += n['power']
            chiplet_stats[cid][2] += n['compute']
            chiplet_stats[cid][3] += 1

        # Normalize
        chiplet_stats[:, 0] /= 200.0   # area
        chiplet_stats[:, 1] /= 50.0    # power
        chiplet_stats[:, 2] /= 50.0    # compute
        chiplet_stats[:, 3] /= self.num_modules  # count

        # 3. Progress
        progress = np.array([self.current_module / self.num_modules], dtype=np.float32)

        # 4. Bandwidth from current module to each chiplet
        bw_to_chiplet = np.zeros(self.num_chiplets, dtype=np.float32)
        for i in range(self.current_module):
            nid = self.module_order[i]
            cid = self.assignment[nid]
            bw_to_chiplet[cid] += self.bw_matrix[mod_id][nid]
        bw_to_chiplet /= (np.max(bw_to_chiplet) + 1e-8)  # normalize

        obs = np.concatenate([
            mod_feat,
            chiplet_stats.flatten(),
            progress,
            bw_to_chiplet,
        ])
        return obs

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.assignment = np.full(self.num_modules, -1, dtype=int)
        self.module_order = self._get_module_order()
        self.current_module = 0
        return self._get_obs(), {}

    def step(self, action):
        """Assign current module to chiplet `action`."""
        mod_id = self.module_order[self.current_module]

        # Capacity constraint: max modules per chiplet
        max_per_chiplet = int(np.ceil(self.num_modules / self.num_chiplets * 1.5))
        count = np.bincount(self.assignment[self.assignment >= 0],
                            minlength=self.num_chiplets) if np.any(self.assignment >= 0) else np.zeros(self.num_chiplets, dtype=int)

        # If chosen chiplet is full, redirect to least-full chiplet
        if count[action] >= max_per_chiplet:
            action = int(np.argmin(count))

        # Force utilization: last K modules fill empty chiplets
        remaining = self.num_modules - self.current_module
        used = set(np.unique(self.assignment[self.assignment >= 0]))
        unused = sorted(set(range(self.num_chiplets)) - used)
        if remaining <= len(unused) and unused:
            action = unused[0]

        self.assignment[mod_id] = action
        self.current_module += 1

        done = self.current_module >= self.num_modules

        if done:
            # Final evaluation
            metrics = evaluate_partition(self.G, self.assignment, self.num_chiplets)

            # Reward design: must use ALL chiplets AND minimize comm
            n_active = metrics['n_active_chiplets']
            comm_ratio = metrics['comm_ratio']
            balance = metrics['balance_score']

            if n_active < self.num_chiplets:
                # HARD PENALTY: must use all chiplets
                reward = -5.0 + n_active * 1.0  # strongly negative
            else:
                # All chiplets used → optimize comm and balance
                # comm_ratio: lower is better (0 = perfect)
                # balance: higher is better (1 = perfect)
                comm_quality = 1.0 - comm_ratio
                reward = 5.0 * comm_quality + 3.0 * balance + metrics['cost_score']

            info = metrics
        else:
            # Dense intermediate reward: encourage placing near connected modules
            bw_to_same = 0
            bw_total = 0
            count_per_chiplet = np.zeros(self.num_chiplets)

            for i in range(self.current_module):
                nid = self.module_order[i]
                cid = self.assignment[nid]
                bw = self.bw_matrix[mod_id][nid]
                bw_total += bw
                if cid == action:
                    bw_to_same += bw
                count_per_chiplet[cid] += 1

            # Reward for placing with high-BW neighbors
            bw_reward = bw_to_same / (bw_total + 1e-8)

            # Penalty for imbalance (don't overfill one chiplet)
            target_count = self.current_module / self.num_chiplets
            overload = max(0, count_per_chiplet[action] - target_count * 1.3)
            balance_penalty = overload / (self.num_modules + 1e-8)

            reward = 0.1 * bw_reward - 0.05 * balance_penalty
            info = {}

        obs = self._get_obs() if not done else np.zeros(self.obs_dim, dtype=np.float32)
        return obs, reward, done, False, info
