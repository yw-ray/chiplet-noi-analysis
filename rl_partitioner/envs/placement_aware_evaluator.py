"""
Placement-Aware Throughput Evaluator
=====================================

Key difference from basic evaluator:
  - Chiplets have PHYSICAL POSITIONS on a 2D grid
  - Only ADJACENT chiplets can have direct links
  - Non-adjacent communication uses multi-hop routing (higher latency)
  - This creates a non-trivial interaction between partition and topology

This is what makes co-optimization valuable:
  Spectral doesn't know about physical placement → suboptimal
  Throughput-aware RL learns placement → better partition
"""

import math
import numpy as np
import networkx as nx


def murphy_yield(area_mm2, dd=0.1):
    d = dd * area_mm2 / 100.0
    if d <= 0:
        return 1.0
    return ((1 - math.exp(-d)) / d) ** 2


class ChipletGrid:
    """Physical placement of chiplets on a 2D grid."""

    def __init__(self, rows, cols):
        self.rows = rows
        self.cols = cols
        self.K = rows * cols

        # Positions
        self.positions = {}
        for r in range(rows):
            for c in range(cols):
                cid = r * cols + c
                self.positions[cid] = (r, c)

        # Adjacency (manhattan distance = 1)
        self.adjacent = {}
        for cid in range(self.K):
            r, c = self.positions[cid]
            neighbors = []
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    neighbors.append(nr * cols + nc)
            self.adjacent[cid] = neighbors

        # Hop distance between all pairs
        self.hop_distance = np.zeros((self.K, self.K), dtype=int)
        for i in range(self.K):
            for j in range(self.K):
                ri, ci = self.positions[i]
                rj, cj = self.positions[j]
                self.hop_distance[i][j] = abs(ri - rj) + abs(ci - cj)

    def are_adjacent(self, c1, c2):
        return c2 in self.adjacent[c1]

    def get_hops(self, c1, c2):
        return self.hop_distance[c1][c2]


class PlacementAwareEvaluator:
    """
    Evaluates chiplet partition considering physical placement.

    Key: only adjacent chiplets share direct links.
    Non-adjacent traffic routes through intermediate chiplets,
    consuming link bandwidth at each hop and adding latency.
    """

    def __init__(self, grid, bw_per_link_gbs=32, phy_area_per_link=0.15,
                 latency_per_hop_us=0.10, links_per_adjacent_pair=4,
                 tops_per_mm2=1.5, hbm_bw_per_mm2=3.0,
                 wafer_cost=17000, dd=0.10, overlap_factor=0.0):
        self.grid = grid
        self.K = grid.K
        self.bw_per_link = bw_per_link_gbs
        self.phy_area_per_link = phy_area_per_link
        self.latency_per_hop = latency_per_hop_us
        self.links_per_adj = links_per_adjacent_pair
        self.tops_per_mm2 = tops_per_mm2
        self.hbm_bw_per_mm2 = hbm_bw_per_mm2
        self.wafer_cost = wafer_cost
        self.dd = dd
        self.overlap_factor = overlap_factor

    def evaluate(self, G, assignment, workload_layers=80):
        K = self.K
        N = G.number_of_nodes()

        # ── 1. Per-chiplet area ──
        chiplet_logic_area = np.zeros(K)
        chiplet_compute = np.zeros(K)
        chiplet_power = np.zeros(K)
        chiplet_count = np.zeros(K, dtype=int)

        for nid in sorted(G.nodes):
            cid = assignment[nid]
            n = G.nodes[nid]
            chiplet_logic_area[cid] += n['area']
            chiplet_compute[cid] += n['compute']
            chiplet_power[cid] += n['power']
            chiplet_count[cid] += 1

        # ── 2. Inter-chiplet traffic matrix ──
        traffic = np.zeros((K, K))
        total_bw = 0.0
        inter_bw = 0.0
        for u, v, d in G.edges(data=True):
            bw = d['bandwidth']
            total_bw += bw
            cu, cv = assignment[u], assignment[v]
            if cu != cv:
                traffic[cu][cv] += bw
                traffic[cv][cu] += bw
                inter_bw += bw

        comm_ratio = inter_bw / total_bw if total_bw > 0 else 0

        # ── 3. Physical link topology (fixed by grid) ──
        # Only adjacent pairs get direct links
        link_matrix = np.zeros((K, K), dtype=int)
        for i in range(K):
            for j in self.grid.adjacent[i]:
                if j > i:
                    link_matrix[i][j] = self.links_per_adj
                    link_matrix[j][i] = self.links_per_adj

        bw_matrix = link_matrix.astype(float) * self.bw_per_link

        # ── 4. PHY area per chiplet ──
        chiplet_phy_area = np.zeros(K)
        for cid in range(K):
            n_links = sum(link_matrix[cid])
            chiplet_phy_area[cid] = n_links * self.phy_area_per_link

        chiplet_total_area = chiplet_logic_area + chiplet_phy_area
        chiplet_compute_area = chiplet_logic_area

        # ── 5. Effective communication BW ──
        # For non-adjacent pairs: multi-hop reduces effective BW
        # Effective BW between pair (i,j) = min link BW along shortest path / n_hops
        # Also: multi-hop traffic consumes BW on intermediate links

        # Compute effective BW for each communicating pair
        # and total communication latency
        total_comm_data = 0.0
        weighted_latency_sum = 0.0

        # Track link utilization (BW consumed on each link)
        link_utilization = np.zeros((K, K))

        for i in range(K):
            for j in range(i + 1, K):
                if traffic[i][j] <= 0:
                    continue

                hops = self.grid.get_hops(i, j)
                if hops == 0:
                    continue

                # For multi-hop: traffic must traverse intermediate links
                # Each hop consumes bandwidth on that link
                # Simple model: traffic goes along shortest manhattan path
                ri, ci = self.grid.positions[i]
                rj, cj = self.grid.positions[j]

                # Build path
                path = [i]
                cr, cc = ri, ci
                while cr != rj or cc != cj:
                    if cr < rj:
                        cr += 1
                    elif cr > rj:
                        cr -= 1
                    elif cc < cj:
                        cc += 1
                    elif cc > cj:
                        cc -= 1
                    path.append(cr * self.grid.cols + cc)

                # Each hop along the path consumes bandwidth
                for h in range(len(path) - 1):
                    a, b = path[h], path[h + 1]
                    link_utilization[a][b] += traffic[i][j]
                    link_utilization[b][a] += traffic[i][j]

                # Latency for this pair
                pair_latency_us = hops * self.latency_per_hop
                total_comm_data += traffic[i][j]
                weighted_latency_sum += traffic[i][j] * pair_latency_us

        # Average weighted latency
        avg_comm_latency_us = weighted_latency_sum / (total_comm_data + 1e-8)

        # ── 6. Link congestion penalty ──
        # If traffic on a link exceeds its capacity, throughput degrades
        congestion_factor = 1.0
        for i in range(K):
            for j in range(i + 1, K):
                if bw_matrix[i][j] > 0 and link_utilization[i][j] > 0:
                    util_ratio = link_utilization[i][j] / bw_matrix[i][j]
                    if util_ratio > 1.0:
                        # Congestion: throughput degrades proportionally
                        congestion_factor = min(congestion_factor, 1.0 / util_ratio)
                elif link_utilization[i][j] > 0 and bw_matrix[i][j] == 0:
                    # Traffic on non-existent link (shouldn't happen with routing)
                    congestion_factor = min(congestion_factor, 0.1)

        # ── 7. E2E Throughput ──
        n_active = sum(1 for c in chiplet_count if c > 0)
        if n_active == 0:
            return self._make_result(0, 0, 0, 0, K, chiplet_logic_area,
                                     chiplet_phy_area, chiplet_total_area,
                                     comm_ratio, traffic, link_matrix, chiplet_count)

        # Compute time
        total_tops = sum(chiplet_compute_area[c] * self.tops_per_mm2
                         for c in range(K) if chiplet_count[c] > 0)
        avg_tops = total_tops / n_active

        # LLaMA-70B defaults
        h, s, b, db = 8192, 2048, 1, 2
        flops_per_layer = (4*2*b*s*h*h + 2*2*b*64*s*s*128 + 3*2*b*s*h*28672)
        activation_bytes = b * s * h * db
        mem_per_layer = (4*h**2 + 3*h*28672)*db + 2*b*s*h*db + b*s*h*db

        total_hbm = sum(chiplet_total_area[c] * self.hbm_bw_per_mm2
                        for c in range(K) if chiplet_count[c] > 0)
        avg_hbm = total_hbm / n_active

        t_comp = (flops_per_layer / n_active) / (avg_tops * 1e12)
        t_mem = (mem_per_layer / n_active) / (avg_hbm * 1e9)
        t_compute_layer = max(t_comp, t_mem)

        # Communication time per layer
        if n_active > 1 and inter_bw > 0:
            # All-reduce data
            ar_data = 2 * (n_active - 1) / n_active * activation_bytes

            # Effective BW: consider congestion and multi-hop
            # Use minimum of: allocated BW * congestion, or bottleneck link
            min_link_bw = float('inf')
            for i in range(K):
                for j in self.grid.adjacent[i]:
                    if j > i and bw_matrix[i][j] > 0:
                        effective = bw_matrix[i][j] * congestion_factor
                        min_link_bw = min(min_link_bw, effective)

            if min_link_bw == float('inf'):
                min_link_bw = self.bw_per_link

            # Ring all-reduce latency (affected by hop distance)
            # In a grid, ring diameter is larger → more hops per all-reduce step
            avg_hops = sum(self.grid.get_hops(i, (i+1) % K)
                           for i in range(K)) / K
            avg_hops = max(1, avg_hops)

            t_ar = (ar_data / (min_link_bw * 1e9)
                    + 2 * (n_active - 1) * avg_hops * self.latency_per_hop * 1e-6)
            t_comm_layer = 2 * t_ar
        else:
            t_comm_layer = 0
            avg_hops = 0

        t_eff_comm = t_comm_layer * (1 - self.overlap_factor)
        t_per_layer = t_compute_layer + t_eff_comm

        total_us = t_per_layer * workload_layers * 1e6
        compute_us = t_compute_layer * workload_layers * 1e6
        comm_us = t_eff_comm * workload_layers * 1e6
        comm_pct = comm_us / total_us * 100 if total_us > 0 else 0

        throughput_tps = 1e6 / total_us if total_us > 0 else 0

        # ── 8. Cost ──
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
            total_die_cost += self.wafer_cost / (dpw * y) + 8

        pkg_cost = 100 + n_active * 35 + sum(chiplet_total_area) * 0.08
        total_cost = total_die_cost + pkg_cost

        # ── 9. Balance ──
        active_compute = chiplet_compute[chiplet_count > 0]
        if len(active_compute) > 1:
            compute_balance = max(0, 1.0 - np.std(active_compute) / (np.mean(active_compute) + 1e-8))
        else:
            compute_balance = 0.0

        return self._make_result(
            throughput_tps, total_cost, compute_us, comm_us, K,
            chiplet_logic_area, chiplet_phy_area, chiplet_total_area,
            comm_ratio, traffic, link_matrix, chiplet_count,
            comm_pct=comm_pct, congestion=congestion_factor,
            avg_hops=avg_hops, compute_balance=compute_balance,
            chiplet_yields=chiplet_yields, total_tops=total_tops,
            link_utilization=link_utilization, bw_matrix=bw_matrix,
        )

    def _make_result(self, tps, cost, comp_us, comm_us, K,
                     logic_area, phy_area, total_area,
                     comm_ratio, traffic, links, counts,
                     comm_pct=0, congestion=1.0, avg_hops=0,
                     compute_balance=0, chiplet_yields=None,
                     total_tops=0, link_utilization=None, bw_matrix=None):
        active_phy = phy_area[counts > 0]
        active_total = total_area[counts > 0]
        avg_phy_pct = float(np.mean(active_phy / (active_total + 1e-8) * 100)) if len(active_phy) > 0 else 0

        return {
            'throughput_tps': tps,
            'total_cost': cost,
            'total_us': comp_us + comm_us if tps > 0 else float('inf'),
            'compute_us': comp_us,
            'comm_us': comm_us,
            'comm_pct': comm_pct,
            'comm_ratio': comm_ratio,
            'congestion_factor': congestion,
            'avg_hops': avg_hops,
            'total_tops': total_tops,
            'chiplet_logic_area': logic_area.tolist(),
            'chiplet_phy_area': phy_area.tolist(),
            'chiplet_total_area': total_area.tolist(),
            'avg_phy_overhead_pct': avg_phy_pct,
            'compute_balance': compute_balance,
            'chiplet_yields': chiplet_yields or [0]*K,
            'n_active_chiplets': int(sum(1 for c in counts if c > 0)),
            'traffic_matrix': traffic.tolist() if isinstance(traffic, np.ndarray) else traffic,
            'link_matrix': links.tolist() if isinstance(links, np.ndarray) else links,
        }
