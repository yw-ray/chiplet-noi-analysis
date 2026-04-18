"""
Netlist graph abstraction for chiplet partitioning v2.

Key fix: realistic spatial locality — modules communicate mainly with
neighbors, with some long-range connections. This creates natural
cluster structure that a good partitioner should find.
"""

import networkx as nx
import numpy as np
from dataclasses import dataclass


@dataclass
class ModuleType:
    name: str
    area_mm2: float
    power_w: float
    compute_tops: float
    sram_mb: float
    preferred_process: int  # nm, 0 = any


MODULE_TYPES = {
    'tensor_core': ModuleType('tensor_core', 4.0, 5.0, 8.0, 0.5, 5),
    'sram_bank': ModuleType('sram_bank', 3.0, 1.0, 0, 4.0, 5),
    'hbm_ctrl': ModuleType('hbm_ctrl', 5.0, 3.0, 0, 0, 28),
    'noc_router': ModuleType('noc_router', 0.5, 0.5, 0, 0, 0),
    'softmax_unit': ModuleType('softmax_unit', 1.0, 1.0, 1.0, 0, 5),
    'layernorm_unit': ModuleType('layernorm_unit', 0.8, 0.8, 0.5, 0, 5),
    'dma_engine': ModuleType('dma_engine', 1.5, 1.0, 0, 0, 28),
}


def create_transformer_accelerator_netlist(
    num_tensor_cores=16,
    num_sram_banks=8,
    num_hbm_ctrl=4,
    num_softmax=4,
    num_layernorm=4,
) -> nx.Graph:
    """
    Create a Transformer accelerator netlist with SPATIAL LOCALITY.

    Layout: modules are arranged in a 2D grid-like structure.
    Communication is distance-dependent: nearby modules have high BW,
    distant modules have low BW. This mimics real chip layouts.

    Cluster structure:
      - 4 compute clusters (each: tensor cores + SRAM + SFU)
      - 4 HBM controllers at edges
      - Natural partition = 4 clusters
      - But some cross-cluster communication exists (all-reduce, shared cache)
    """
    G = nx.Graph()
    rng = np.random.default_rng(42)

    node_id = 0

    def add_module(mtype_name, x, y, group, cluster_id):
        nonlocal node_id
        nid = node_id
        mtype = MODULE_TYPES[mtype_name]
        G.add_node(nid,
                   name=f"{mtype_name}_{nid}",
                   module_type=mtype_name,
                   group=group,
                   cluster_id=cluster_id,
                   x=x, y=y,
                   area=mtype.area_mm2,
                   power=mtype.power_w,
                   compute=mtype.compute_tops,
                   sram=mtype.sram_mb,
                   preferred_process=mtype.preferred_process)
        node_id += 1
        return nid

    # Create 4 clusters arranged in 2x2 grid
    # Each cluster: 4 tensor cores + 2 SRAM + 1 softmax + 1 layernorm
    cluster_centers = [(0, 0), (10, 0), (0, 10), (10, 10)]
    cluster_modules = {0: [], 1: [], 2: [], 3: []}

    for cid, (cx, cy) in enumerate(cluster_centers):
        # 4 tensor cores per cluster
        for i in range(num_tensor_cores // 4):
            x = cx + (i % 2) * 2 + rng.normal(0, 0.3)
            y = cy + (i // 2) * 2 + rng.normal(0, 0.3)
            nid = add_module('tensor_core', x, y, 'compute', cid)
            cluster_modules[cid].append(nid)

        # 2 SRAM banks per cluster
        for i in range(num_sram_banks // 4):
            x = cx + 4 + rng.normal(0, 0.3)
            y = cy + i * 2 + rng.normal(0, 0.3)
            nid = add_module('sram_bank', x, y, 'memory', cid)
            cluster_modules[cid].append(nid)

        # 1 softmax + 1 layernorm per cluster
        nid = add_module('softmax_unit', cx + 3, cy + 1, 'compute', cid)
        cluster_modules[cid].append(nid)
        nid = add_module('layernorm_unit', cx + 3, cy + 3, 'compute', cid)
        cluster_modules[cid].append(nid)

    # HBM controllers at edges (shared between clusters)
    hbm_positions = [(-3, 5), (13, 5), (5, -3), (5, 13)]
    hbm_ids = []
    for i, (hx, hy) in enumerate(hbm_positions):
        nid = add_module('hbm_ctrl', hx, hy, 'io', i % 4)
        hbm_ids.append(nid)

    # DMA engines
    dma_ids = []
    for i in range(2):
        nid = add_module('dma_engine', 5 + i * 3, -2, 'io', i * 2)
        dma_ids.append(nid)

    # ================================================================
    # Edges: distance-dependent bandwidth
    # ================================================================
    all_nodes = list(G.nodes)

    for i in range(len(all_nodes)):
        for j in range(i + 1, len(all_nodes)):
            ni, nj = all_nodes[i], all_nodes[j]
            xi, yi = G.nodes[ni]['x'], G.nodes[ni]['y']
            xj, yj = G.nodes[nj]['x'], G.nodes[nj]['y']
            dist = np.sqrt((xi - xj)**2 + (yi - yj)**2)

            ti = G.nodes[ni]['module_type']
            tj = G.nodes[nj]['module_type']
            ci = G.nodes[ni]['cluster_id']
            cj = G.nodes[nj]['cluster_id']

            bw = 0

            # Intra-cluster: high bandwidth
            if ci == cj:
                # Tensor core <-> SRAM (very high BW within cluster)
                if {ti, tj} == {'tensor_core', 'sram_bank'}:
                    bw = 200.0 / (dist + 0.5)
                # Tensor core <-> SFU (pipeline)
                elif 'tensor_core' in {ti, tj} and tj in {'softmax_unit', 'layernorm_unit'} or ti in {'softmax_unit', 'layernorm_unit'}:
                    bw = 100.0 / (dist + 0.5)
                # Tensor core <-> Tensor core (intra-cluster reduction)
                elif ti == tj == 'tensor_core':
                    bw = 50.0 / (dist + 0.5)
                # SRAM <-> SRAM
                elif ti == tj == 'sram_bank':
                    bw = 30.0 / (dist + 0.5)

            # Cross-cluster: lower bandwidth
            else:
                # Tensor core all-reduce across clusters
                if ti == tj == 'tensor_core':
                    bw = 5.0 / (dist + 1.0)
                # SRAM coherence across clusters
                elif ti == tj == 'sram_bank':
                    bw = 3.0 / (dist + 1.0)

            # HBM connections (distance-dependent)
            if 'hbm_ctrl' in {ti, tj}:
                other = ti if tj == 'hbm_ctrl' else tj
                if other in {'tensor_core', 'sram_bank'}:
                    bw = max(bw, 40.0 / (dist + 1.0))
                elif other == 'dma_engine':
                    bw = max(bw, 20.0 / (dist + 1.0))

            # DMA connections
            if 'dma_engine' in {ti, tj}:
                other = ti if tj == 'dma_engine' else tj
                if other == 'hbm_ctrl':
                    bw = max(bw, 20.0 / (dist + 1.0))

            if bw > 0.5:  # threshold to avoid noise edges
                G.add_edge(ni, nj, bandwidth=bw, comm_type='distance_based')

    return G


def get_node_features(G: nx.Graph) -> np.ndarray:
    features = []
    for nid in sorted(G.nodes):
        n = G.nodes[nid]
        features.append([
            n['area'],
            n['power'],
            n['compute'],
            n['sram'],
            n['preferred_process'] / 28.0,
            n['x'] / 15.0,  # normalized position
            n['y'] / 15.0,
            1.0 if n['group'] == 'compute' else 0.0,
            1.0 if n['group'] == 'memory' else 0.0,
            1.0 if n['group'] == 'io' else 0.0,
        ])
    return np.array(features, dtype=np.float32)


def get_edge_bandwidth_matrix(G: nx.Graph) -> np.ndarray:
    N = G.number_of_nodes()
    bw = np.zeros((N, N), dtype=np.float32)
    for u, v, d in G.edges(data=True):
        bw[u][v] = d['bandwidth']
        bw[v][u] = d['bandwidth']
    return bw


def get_ground_truth_partition(G: nx.Graph) -> np.ndarray:
    """Get the 'natural' partition based on cluster_id."""
    N = G.number_of_nodes()
    assignment = np.zeros(N, dtype=int)
    for nid in G.nodes:
        assignment[nid] = G.nodes[nid]['cluster_id']
    return assignment


def netlist_summary(G: nx.Graph) -> str:
    total_area = sum(G.nodes[n]['area'] for n in G.nodes)
    total_power = sum(G.nodes[n]['power'] for n in G.nodes)
    total_compute = sum(G.nodes[n]['compute'] for n in G.nodes)
    total_bw = sum(d['bandwidth'] for _, _, d in G.edges(data=True))

    groups = {}
    for n in G.nodes:
        g = G.nodes[n]['group']
        groups[g] = groups.get(g, 0) + 1

    # Measure cluster quality
    intra_bw = sum(d['bandwidth'] for u, v, d in G.edges(data=True)
                   if G.nodes[u]['cluster_id'] == G.nodes[v]['cluster_id'])
    cluster_ratio = intra_bw / total_bw if total_bw > 0 else 0

    lines = [
        f"Netlist: {G.number_of_nodes()} modules, {G.number_of_edges()} edges",
        f"  Groups: {groups}",
        f"  Total area: {total_area:.1f} mm²",
        f"  Total power: {total_power:.1f} W",
        f"  Total compute: {total_compute:.1f} TOPS",
        f"  Total bandwidth: {total_bw:.1f}",
        f"  Intra-cluster BW: {cluster_ratio:.1%} (natural cluster quality)",
    ]
    return "\n".join(lines)
