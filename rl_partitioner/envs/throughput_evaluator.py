"""
E2E Throughput-Aware Evaluator for Chiplet Partitioning
========================================================

Given a netlist partition, this evaluator:
  1. Computes inter-chiplet traffic matrix
  2. Allocates NoI links optimally (proportional to traffic, constrained by PHY budget)
  3. Computes PHY area overhead per chiplet
  4. Estimates E2E inference throughput (tok/s) and manufacturing cost

This is the REWARD FUNCTION for the co-optimization RL agent.
"""

import math
import numpy as np
import networkx as nx


# ============================================================
# Yield & Cost
# ============================================================

def murphy_yield(area_mm2, dd=0.1):
    d = dd * area_mm2 / 100.0
    if d <= 0:
        return 1.0
    return ((1 - math.exp(-d)) / d) ** 2


# ============================================================
# PHY & Interconnect specs
# ============================================================

class InterconnectSpec:
    """Parameterized interconnect specification."""

    def __init__(self, name, bw_per_link_gbs, phy_area_per_link_mm2,
                 latency_per_hop_us, max_links_per_edge=16):
        self.name = name
        self.bw_per_link = bw_per_link_gbs       # GB/s per link
        self.phy_area_per_link = phy_area_per_link_mm2  # mm² per link (one side)
        self.latency_per_hop = latency_per_hop_us  # us per hop
        self.max_links_per_edge = max_links_per_edge


INTERCONNECT_PRESETS = {
    'ucie_adv': InterconnectSpec('UCIe Advanced', 32, 0.15, 0.10, 16),
    'noi_512':  InterconnectSpec('NoI 512GB/s', 64, 0.20, 0.05, 16),
    'noi_1t':   InterconnectSpec('NoI 1TB/s', 64, 0.20, 0.03, 32),
    'custom':   InterconnectSpec('Custom D2D', 100, 0.30, 0.05, 16),
}


# ============================================================
# Link Allocator
# ============================================================

def allocate_links(traffic_matrix, num_chiplets, total_link_budget,
                   min_links_per_active_pair=1, max_links_per_pair=16):
    """
    Allocate inter-chiplet links proportionally to traffic.

    Args:
        traffic_matrix: K×K matrix of inter-chiplet bandwidth demand (GB/s)
        num_chiplets: K
        total_link_budget: total number of links to distribute
        min_links_per_active_pair: minimum links for any pair with traffic > 0
        max_links_per_pair: maximum links per pair

    Returns:
        link_matrix: K×K matrix of allocated links (symmetric)
    """
    K = num_chiplets
    link_matrix = np.zeros((K, K), dtype=int)

    # Collect active pairs and their traffic
    pairs = []
    for i in range(K):
        for j in range(i + 1, K):
            if traffic_matrix[i][j] > 0:
                pairs.append((i, j, traffic_matrix[i][j]))

    if not pairs:
        return link_matrix

    # Step 1: assign minimum links to active pairs
    remaining = total_link_budget
    for (i, j, _) in pairs:
        alloc = min(min_links_per_active_pair, remaining)
        link_matrix[i][j] = alloc
        link_matrix[j][i] = alloc
        remaining -= alloc
        if remaining <= 0:
            break

    if remaining <= 0:
        return link_matrix

    # Step 2: distribute remaining proportionally to traffic
    total_traffic = sum(t for _, _, t in pairs)
    if total_traffic <= 0:
        return link_matrix

    for (i, j, t) in pairs:
        share = t / total_traffic
        extra = int(round(share * remaining))
        current = link_matrix[i][j]
        new_alloc = min(current + extra, max_links_per_pair)
        link_matrix[i][j] = new_alloc
        link_matrix[j][i] = new_alloc

    return link_matrix


# ============================================================
# E2E Throughput Evaluator
# ============================================================

class ThroughputEvaluator:
    """
    Computes end-to-end inference throughput for a chiplet partition.

    Integrates:
      - PHY area overhead (reduces compute area)
      - Communication latency (all-reduce over allocated links)
      - Manufacturing yield & cost
    """

    def __init__(self, interconnect='noi_512', total_link_budget=32,
                 tops_per_mm2=2.43, hbm_bw_per_mm2=4.0,
                 wafer_cost=17000, dd=0.10,
                 overlap_factor=0.3):
        """
        Args:
            interconnect: name of interconnect preset or InterconnectSpec
            total_link_budget: total links available for inter-chiplet connections
            tops_per_mm2: TFLOPS per mm² of compute area
            hbm_bw_per_mm2: GB/s HBM bandwidth per mm² of total chiplet area
            wafer_cost: wafer cost in $
            dd: defect density (defects/cm²)
            overlap_factor: compute-comm overlap (0=none, 1=full)
        """
        if isinstance(interconnect, str):
            self.ic = INTERCONNECT_PRESETS[interconnect]
        else:
            self.ic = interconnect

        self.total_link_budget = total_link_budget
        self.tops_per_mm2 = tops_per_mm2
        self.hbm_bw_per_mm2 = hbm_bw_per_mm2
        self.wafer_cost = wafer_cost
        self.dd = dd
        self.overlap_factor = overlap_factor

    def evaluate(self, G, assignment, num_chiplets,
                 workload_flops_per_step=None, workload_activation_bytes=None,
                 workload_mem_per_step=None, workload_layers=80):
        """
        Full evaluation of a chiplet partition.

        Args:
            G: netlist graph
            assignment: node → chiplet mapping
            num_chiplets: K
            workload_*: LLM inference parameters (optional, uses defaults)
            workload_layers: number of transformer layers

        Returns:
            dict with throughput, cost, breakdown metrics
        """
        K = num_chiplets
        N = G.number_of_nodes()

        # ── 1. Per-chiplet area breakdown ──
        chiplet_logic_area = np.zeros(K)
        chiplet_compute = np.zeros(K)
        chiplet_power = np.zeros(K)
        chiplet_module_count = np.zeros(K, dtype=int)

        for nid in sorted(G.nodes):
            cid = assignment[nid]
            n = G.nodes[nid]
            chiplet_logic_area[cid] += n['area']
            chiplet_compute[cid] += n['compute']
            chiplet_power[cid] += n['power']
            chiplet_module_count[cid] += 1

        # ── 2. Inter-chiplet traffic matrix ──
        traffic_matrix = np.zeros((K, K))
        total_bw = 0.0
        inter_bw = 0.0
        for u, v, d in G.edges(data=True):
            bw = d['bandwidth']
            total_bw += bw
            cu, cv = assignment[u], assignment[v]
            if cu != cv:
                traffic_matrix[cu][cv] += bw
                traffic_matrix[cv][cu] += bw
                inter_bw += bw

        comm_ratio = inter_bw / total_bw if total_bw > 0 else 0

        # ── 3. Link allocation ──
        link_matrix = allocate_links(
            traffic_matrix, K, self.total_link_budget,
            max_links_per_pair=self.ic.max_links_per_edge)

        # BW matrix (actual bandwidth between chiplet pairs)
        bw_matrix = link_matrix.astype(float) * self.ic.bw_per_link

        # ── 4. PHY area per chiplet ──
        chiplet_phy_area = np.zeros(K)
        for cid in range(K):
            n_links = sum(link_matrix[cid])
            chiplet_phy_area[cid] = n_links * self.ic.phy_area_per_link

        chiplet_total_area = chiplet_logic_area + chiplet_phy_area
        chiplet_compute_area = chiplet_logic_area  # logic area = compute area
        phy_overhead_pct = np.where(
            chiplet_total_area > 0,
            chiplet_phy_area / chiplet_total_area * 100, 0)

        # ── 5. Effective TOPS and HBM per chiplet ──
        chiplet_tops = chiplet_compute_area * self.tops_per_mm2
        chiplet_hbm_bw = chiplet_total_area * self.hbm_bw_per_mm2  # HBM scales with total area

        total_tops = np.sum(chiplet_tops)
        total_hbm_bw = np.sum(chiplet_hbm_bw)

        # ── 6. E2E Inference Latency ──
        # Workload defaults (LLaMA-70B FP16-like)
        if workload_flops_per_step is None:
            h, s, b, db = 8192, 2048, 1, 2
            workload_flops_per_step = (4*2*b*s*h*h + 2*2*b*64*s*s*128 + 3*2*b*s*h*28672)
        if workload_activation_bytes is None:
            workload_activation_bytes = 1 * 2048 * 8192 * 2
        if workload_mem_per_step is None:
            h, db = 8192, 2
            wt = (4*h**2 + 3*h*28672) * db
            kv = 2 * 1 * 2048 * h * db
            act = 1 * 2048 * h * db
            workload_mem_per_step = wt + kv + act

        n_active = sum(1 for c in chiplet_module_count if c > 0)
        if n_active == 0:
            return self._empty_result(K)

        # Per-layer compute time (distributed across active chiplets)
        avg_tops = total_tops / n_active if n_active > 0 else 1
        avg_hbm = total_hbm_bw / n_active if n_active > 0 else 1

        t_comp = (workload_flops_per_step / n_active) / (avg_tops * 1e12)
        t_mem = (workload_mem_per_step / n_active) / (avg_hbm * 1e9)
        t_compute_per_layer = max(t_comp, t_mem)

        # Communication: all-reduce across active chiplets
        if n_active > 1:
            # Bottleneck link: minimum BW between any pair in the ring
            # For simplicity, use average allocated BW
            active_chiplets = [c for c in range(K) if chiplet_module_count[c] > 0]
            total_allocated_bw = 0
            n_active_pairs = 0
            for i in active_chiplets:
                for j in active_chiplets:
                    if i < j and bw_matrix[i][j] > 0:
                        total_allocated_bw += bw_matrix[i][j]
                        n_active_pairs += 1

            avg_link_bw = total_allocated_bw / max(1, n_active_pairs)
            if avg_link_bw <= 0:
                avg_link_bw = self.ic.bw_per_link  # fallback: 1 link

            # Ring all-reduce
            ar_data = 2 * (n_active - 1) / n_active * workload_activation_bytes
            t_ar = ar_data / (avg_link_bw * 1e9) + 2 * (n_active - 1) * self.ic.latency_per_hop * 1e-6
            t_comm_per_layer = 2 * t_ar  # 2 all-reduces per layer
        else:
            t_comm_per_layer = 0
            avg_link_bw = 0

        # Apply overlap
        t_effective_comm = t_comm_per_layer * (1 - self.overlap_factor)
        t_per_layer = t_compute_per_layer + t_effective_comm

        # Total latency
        total_compute_us = t_compute_per_layer * workload_layers * 1e6
        total_comm_us = t_effective_comm * workload_layers * 1e6
        total_us = t_per_layer * workload_layers * 1e6
        comm_pct = total_comm_us / total_us * 100 if total_us > 0 else 0

        throughput_tps = 1e6 / total_us if total_us > 0 else 0

        # ── 7. Manufacturing Cost ──
        total_die_cost = 0
        chiplet_yields = []
        for cid in range(K):
            area = chiplet_total_area[cid]
            if area <= 0:
                chiplet_yields.append(0)
                continue
            y = murphy_yield(area, self.dd)
            chiplet_yields.append(y)
            dpw = max(1, int(math.pi * 150**2 / area * 0.9))
            total_die_cost += self.wafer_cost / (dpw * y) + 8  # test cost

        pkg_cost = 100 + n_active * 35 + sum(chiplet_total_area) * 0.08
        total_cost = total_die_cost + pkg_cost

        tops_per_dollar = total_tops / total_cost if total_cost > 0 else 0
        tps_per_dollar = throughput_tps / total_cost if total_cost > 0 else 0

        # ── 8. Balance metrics ──
        active_compute = chiplet_compute[chiplet_module_count > 0]
        if len(active_compute) > 1:
            compute_balance = 1.0 - np.std(active_compute) / (np.mean(active_compute) + 1e-8)
            compute_balance = max(0, compute_balance)
        else:
            compute_balance = 0.0

        active_areas = chiplet_total_area[chiplet_module_count > 0]
        if len(active_areas) > 1:
            area_balance = 1.0 - np.std(active_areas) / (np.mean(active_areas) + 1e-8)
            area_balance = max(0, area_balance)
        else:
            area_balance = 0.0

        # ── 9. Composite score (for RL reward) ──
        # Throughput-centric: throughput is primary, cost is secondary
        throughput_score = throughput_tps  # raw tok/s (higher = better)
        cost_efficiency = tps_per_dollar * 1000  # scale for readability

        return {
            # Primary metrics
            'throughput_tps': throughput_tps,
            'total_cost': total_cost,
            'tops_per_dollar': tops_per_dollar,
            'tps_per_dollar': tps_per_dollar,
            # Latency breakdown
            'total_us': total_us,
            'compute_us': total_compute_us,
            'comm_us': total_comm_us,
            'comm_pct': comm_pct,
            # Area breakdown
            'total_tops': total_tops,
            'chiplet_logic_area': chiplet_logic_area.tolist(),
            'chiplet_phy_area': chiplet_phy_area.tolist(),
            'chiplet_total_area': chiplet_total_area.tolist(),
            'avg_phy_overhead_pct': float(np.mean(phy_overhead_pct[chiplet_module_count > 0])),
            # Communication
            'comm_ratio': comm_ratio,
            'avg_link_bw': avg_link_bw,
            'link_matrix': link_matrix.tolist(),
            'traffic_matrix': traffic_matrix.tolist(),
            # Cost
            'die_cost': total_die_cost,
            'pkg_cost': pkg_cost,
            'chiplet_yields': chiplet_yields,
            # Balance
            'compute_balance': compute_balance,
            'area_balance': area_balance,
            'n_active_chiplets': n_active,
            # Scores
            'throughput_score': throughput_score,
            'cost_efficiency': cost_efficiency,
        }

    def _empty_result(self, K):
        return {
            'throughput_tps': 0, 'total_cost': float('inf'),
            'tops_per_dollar': 0, 'tps_per_dollar': 0,
            'total_us': float('inf'), 'compute_us': 0, 'comm_us': 0, 'comm_pct': 0,
            'total_tops': 0,
            'chiplet_logic_area': [0]*K, 'chiplet_phy_area': [0]*K,
            'chiplet_total_area': [0]*K, 'avg_phy_overhead_pct': 0,
            'comm_ratio': 0, 'avg_link_bw': 0,
            'link_matrix': [[0]*K]*K, 'traffic_matrix': [[0]*K]*K,
            'die_cost': 0, 'pkg_cost': 0, 'chiplet_yields': [0]*K,
            'compute_balance': 0, 'area_balance': 0, 'n_active_chiplets': 0,
            'throughput_score': 0, 'cost_efficiency': 0,
        }
