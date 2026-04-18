"""
Fast evaluator for chiplet partitioning quality.

Given a netlist + partition assignment, computes:
  1. Manufacturing cost (yield-based)
  2. Performance (inter-chiplet communication overhead)
  3. Load balance (compute/area/power balance across chiplets)
  4. Thermal feasibility (power density per chiplet)
"""

import math
import numpy as np
import networkx as nx


def murphy_yield(area_mm2, defect_density=0.1):
    d = defect_density * area_mm2 / 100.0
    if d <= 0:
        return 1.0
    return ((1 - math.exp(-d)) / d) ** 2


def evaluate_partition(G: nx.Graph, assignment: np.ndarray, num_chiplets: int,
                       process_nodes: list[int] | None = None) -> dict:
    """
    Evaluate a chiplet partition.

    Args:
        G: netlist graph
        assignment: array of length N, assignment[i] = chiplet_id for module i
        num_chiplets: number of chiplets
        process_nodes: list of process node (nm) per chiplet, or None for uniform 5nm

    Returns:
        dict with scores and metrics
    """
    if process_nodes is None:
        process_nodes = [5] * num_chiplets

    N = G.number_of_nodes()
    nodes = sorted(G.nodes)

    # ================================================================
    # 1. Per-chiplet metrics
    # ================================================================
    chiplet_area = np.zeros(num_chiplets)
    chiplet_power = np.zeros(num_chiplets)
    chiplet_compute = np.zeros(num_chiplets)
    chiplet_sram = np.zeros(num_chiplets)
    chiplet_module_count = np.zeros(num_chiplets, dtype=int)

    for nid in nodes:
        cid = assignment[nid]
        n = G.nodes[nid]
        chiplet_area[cid] += n['area']
        chiplet_power[cid] += n['power']
        chiplet_compute[cid] += n['compute']
        chiplet_sram[cid] += n['sram']
        chiplet_module_count[cid] += 1

    # PHY overhead: proportional to inter-chiplet edges
    phy_area_per_link = 0.5  # mm²
    inter_edges_per_chiplet = np.zeros(num_chiplets)
    for u, v, d in G.edges(data=True):
        cu, cv = assignment[u], assignment[v]
        if cu != cv:
            inter_edges_per_chiplet[cu] += 1
            inter_edges_per_chiplet[cv] += 1

    chiplet_phy_area = inter_edges_per_chiplet * phy_area_per_link * 0.1  # scaled down
    chiplet_total_area = chiplet_area + chiplet_phy_area

    # ================================================================
    # 2. Manufacturing cost
    # ================================================================
    wafer_costs = {5: 17000, 7: 10000, 14: 5000, 28: 3000}
    total_cost = 0
    chiplet_yields = []
    for cid in range(num_chiplets):
        area = chiplet_total_area[cid]
        if area <= 0:
            chiplet_yields.append(0)
            continue
        pn = process_nodes[cid]
        wc = wafer_costs.get(pn, 17000)
        y = murphy_yield(area)
        chiplet_yields.append(y)
        dpw = max(1, int(math.pi * 150**2 / area * 0.9))
        die_cost = wc / (dpw * y) + 10
        total_cost += die_cost

    # Packaging cost
    pkg_cost = 100 + num_chiplets * 40
    interposer_area = sum(chiplet_total_area) * 1.3
    pkg_cost += interposer_area * 0.1
    total_cost += pkg_cost

    # ================================================================
    # 3. Communication cost (inter-chiplet bandwidth)
    # ================================================================
    total_bw = 0
    inter_chiplet_bw = 0
    for u, v, d in G.edges(data=True):
        bw = d['bandwidth']
        total_bw += bw
        if assignment[u] != assignment[v]:
            inter_chiplet_bw += bw

    comm_ratio = inter_chiplet_bw / total_bw if total_bw > 0 else 0

    # ================================================================
    # 4. Load balance
    # ================================================================
    # Compute balance: std of compute per chiplet (lower = better)
    active_chiplets = [cid for cid in range(num_chiplets) if chiplet_module_count[cid] > 0]
    n_active = len(active_chiplets)

    if n_active > 1:
        active_compute = chiplet_compute[active_chiplets]
        compute_balance = 1.0 - np.std(active_compute) / (np.mean(active_compute) + 1e-8)
        compute_balance = max(0, compute_balance)

        active_area = chiplet_total_area[active_chiplets]
        area_balance = 1.0 - np.std(active_area) / (np.mean(active_area) + 1e-8)
        area_balance = max(0, area_balance)
    else:
        compute_balance = 0.0
        area_balance = 0.0

    # ================================================================
    # 5. Thermal feasibility
    # ================================================================
    # Power density per chiplet (W/mm²)
    power_density = np.zeros(num_chiplets)
    for cid in range(num_chiplets):
        if chiplet_total_area[cid] > 0:
            power_density[cid] = chiplet_power[cid] / chiplet_total_area[cid]

    max_power_density = 1.0  # W/mm² threshold
    thermal_violation = max(0, np.max(power_density) - max_power_density)

    # ================================================================
    # 6. Process affinity
    # ================================================================
    # Penalize if high-compute modules are on slow process
    process_penalty = 0
    for nid in nodes:
        cid = assignment[nid]
        n = G.nodes[nid]
        pref = n['preferred_process']
        if pref > 0 and process_nodes[cid] > pref:
            # Module prefers faster process than assigned
            process_penalty += n['compute'] * (process_nodes[cid] - pref) / 28.0

    # ================================================================
    # 7. Connectivity: penalize disconnected chiplets
    # ================================================================
    empty_penalty = sum(1 for cid in range(num_chiplets) if chiplet_module_count[cid] == 0)

    # ================================================================
    # Composite scores
    # ================================================================
    # Normalized scores (0-1, higher = better)
    cost_score = max(0, 1.0 - total_cost / 2000.0)  # normalize by $2000
    comm_score = 1.0 - comm_ratio  # less inter-chiplet = better
    balance_score = (compute_balance + area_balance) / 2.0
    thermal_score = max(0, 1.0 - thermal_violation)
    process_score = max(0, 1.0 - process_penalty / 10.0)
    empty_score = 1.0 - empty_penalty / num_chiplets

    return {
        # Composite
        'cost_score': cost_score,
        'comm_score': comm_score,
        'balance_score': balance_score,
        'thermal_score': thermal_score,
        'process_score': process_score,
        'empty_score': empty_score,
        # Raw metrics
        'total_cost': total_cost,
        'comm_ratio': comm_ratio,
        'inter_chiplet_bw': inter_chiplet_bw,
        'total_bw': total_bw,
        'chiplet_areas': chiplet_total_area.tolist(),
        'chiplet_compute': chiplet_compute.tolist(),
        'chiplet_power': chiplet_power.tolist(),
        'chiplet_yields': chiplet_yields,
        'max_power_density': float(np.max(power_density)),
        'n_active_chiplets': n_active,
        'compute_balance': compute_balance,
        'area_balance': area_balance,
    }
