"""
Co-optimization RL Environment
================================

Topology-aware chiplet partitioning: RL decides module placement,
link allocator assigns NoI links optimally, reward = E2E throughput.

Key difference from original env:
  - Reward is actual inference throughput (tok/s), not proxy metrics
  - Link allocation is part of the evaluation (analytical solver)
  - PHY area overhead is deducted from compute area
  - State includes link allocation info

This makes the RL agent implicitly learn which partitions enable
efficient NoI topologies — the essence of "co-optimization."
"""

import numpy as np
import networkx as nx

from .throughput_evaluator import ThroughputEvaluator, allocate_links
from .netlist import get_node_features, get_edge_bandwidth_matrix


class CooptPartitionEnv:
    """
    RL environment for throughput-aware chiplet partitioning.

    Episode flow:
      1. Start from initial partition (Spectral or random)
      2. RL proposes module swaps
      3. After each swap:
         a. Recompute inter-chiplet traffic
         b. Run link allocator
         c. Compute E2E throughput → reward
      4. Episode ends after max_swaps steps

    Observation:
      - Per-chiplet: [area, compute, power, module_count, phy_area, links, bw]
      - Global: [comm_ratio, balance, throughput_normalized, step_progress]

    Action:
      - Discrete: module_id * K + target_chiplet

    Reward:
      - Delta in throughput_tps (positive = improvement)
    """

    def __init__(self, G, num_chiplets, initial_partition,
                 evaluator=None, max_swaps=50):
        self.G = G
        self.K = num_chiplets
        self.N = G.number_of_nodes()
        self.initial_partition = initial_partition.copy()
        self.max_swaps = max_swaps

        # Evaluator
        self.evaluator = evaluator or ThroughputEvaluator()

        # Precompute
        self.node_features = get_node_features(G)
        self.bw_matrix = get_edge_bandwidth_matrix(G)

        # Action space
        self.n_actions = self.N * self.K

        # Observation: per-chiplet stats (7 per chiplet) + global (4)
        self.obs_dim = self.K * 7 + 4

    def reset(self):
        self.assignment = self.initial_partition.copy()
        self.step_count = 0
        self.best_assignment = self.assignment.copy()

        # Full evaluation
        self._cached_eval = self._full_evaluate()
        self.best_throughput = self._cached_eval['throughput_tps']
        self.initial_throughput = self.best_throughput

        return self._get_obs()

    def _full_evaluate(self):
        return self.evaluator.evaluate(self.G, self.assignment, self.K)

    def _fast_traffic_update(self):
        """Recompute traffic matrix incrementally."""
        traffic = np.zeros((self.K, self.K))
        total_bw = 0.0
        inter_bw = 0.0
        for u, v, d in self.G.edges(data=True):
            bw = d['bandwidth']
            total_bw += bw
            cu, cv = self.assignment[u], self.assignment[v]
            if cu != cv:
                traffic[cu][cv] += bw
                traffic[cv][cu] += bw
                inter_bw += bw
        return traffic, total_bw, inter_bw

    def _get_obs(self):
        obs = np.zeros(self.obs_dim, dtype=np.float32)
        ev = self._cached_eval

        for cid in range(self.K):
            base = cid * 7
            obs[base + 0] = ev['chiplet_logic_area'][cid] / 200.0  # normalize
            obs[base + 1] = ev['chiplet_total_area'][cid] / 200.0
            obs[base + 2] = ev['chiplet_phy_area'][cid] / 20.0
            # Compute fraction
            total_compute = sum(self.node_features[n][2] for n in range(self.N))
            chiplet_compute = sum(self.node_features[n][2]
                                  for n in range(self.N) if self.assignment[n] == cid)
            obs[base + 3] = chiplet_compute / (total_compute + 1e-8)
            # Module count fraction
            count = sum(1 for n in range(self.N) if self.assignment[n] == cid)
            obs[base + 4] = count / self.N
            # Links to this chiplet
            link_row = ev['link_matrix'][cid] if isinstance(ev['link_matrix'], list) else ev['link_matrix'][cid].tolist()
            obs[base + 5] = sum(link_row) / 20.0
            # Average BW to this chiplet
            traffic_row = ev['traffic_matrix'][cid] if isinstance(ev['traffic_matrix'], list) else ev['traffic_matrix'][cid].tolist()
            obs[base + 6] = sum(traffic_row) / 100.0

        # Global features
        g_base = self.K * 7
        obs[g_base + 0] = ev['comm_ratio']
        obs[g_base + 1] = ev['compute_balance']
        obs[g_base + 2] = ev['throughput_tps'] / (self.initial_throughput + 1e-8)
        obs[g_base + 3] = self.step_count / self.max_swaps

        return obs

    def step(self, action):
        """Execute a module swap and evaluate."""
        module_id = action // self.K
        target_chiplet = action % self.K

        old_chiplet = self.assignment[module_id]

        # No-op check
        if old_chiplet == target_chiplet:
            self.step_count += 1
            done = self.step_count >= self.max_swaps
            return self._get_obs(), -0.001, done

        # Balance constraint
        count_target = np.sum(self.assignment == target_chiplet)
        count_source = np.sum(self.assignment == old_chiplet)
        max_cap = int(np.ceil(self.N / self.K * 1.8))
        min_cap = max(1, int(np.floor(self.N / self.K * 0.3)))

        if count_target >= max_cap or count_source <= min_cap:
            self.step_count += 1
            done = self.step_count >= self.max_swaps
            return self._get_obs(), -0.002, done

        # Execute swap
        self.assignment[module_id] = target_chiplet

        # Full re-evaluation (link allocation + throughput)
        self._cached_eval = self._full_evaluate()
        new_throughput = self._cached_eval['throughput_tps']

        # Reward: improvement in throughput
        improvement = new_throughput - self.best_throughput
        if new_throughput > self.best_throughput:
            self.best_throughput = new_throughput
            self.best_assignment = self.assignment.copy()

        # Scale reward for RL stability
        reward = improvement * 10.0  # amplify small improvements

        self.step_count += 1
        done = self.step_count >= self.max_swaps

        return self._get_obs(), reward, done

    def get_best_result(self):
        """Return the best partition found and its evaluation."""
        ev = self.evaluator.evaluate(self.G, self.best_assignment, self.K)
        return self.best_assignment.copy(), ev

    def get_current_result(self):
        return self.assignment.copy(), self._cached_eval
