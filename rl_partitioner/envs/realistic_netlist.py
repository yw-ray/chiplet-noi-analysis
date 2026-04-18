"""
Realistic Accelerator Netlist
==============================

Key differences from the simple netlist:
  1. Pipeline stages: compute → reduce → accumulate → output
  2. Shared L2 cache banks that connect to ALL compute modules
  3. HBM controllers that MUST be at grid edges (placement constraint)
  4. Non-uniform traffic: pipeline has high sequential BW, cache has broadcast BW
  5. Cross-cutting dependencies that break clean cluster structure

This creates a netlist where:
  - Spectral finds decent comm_ratio but ignores placement constraints
  - The optimal partition depends on physical grid layout
  - Link allocation trade-offs create meaningful differentiation
"""

import networkx as nx
import numpy as np


def create_realistic_accelerator(
    n_compute_clusters=8,    # number of compute clusters
    cores_per_cluster=4,     # tensor cores per cluster
    n_shared_cache=4,        # shared L2 cache banks
    n_hbm_ctrl=4,            # HBM memory controllers
    n_reduction_units=4,     # all-reduce units
    cross_cluster_ratio=0.3, # ratio of cross-cluster connections
    seed=42,
) -> tuple[nx.Graph, dict]:
    """
    Create a realistic accelerator netlist with:
    - Compute clusters (tensor cores + local SRAM)
    - Shared L2 cache (connects to all clusters)
    - HBM controllers (I/O, must be at edges)
    - Reduction units (for all-reduce operations)
    - Pipeline connections (sequential data flow)
    - Cross-cluster connections (data sharing)

    Returns:
        G: netlist graph
        constraints: dict with placement constraints
    """
    G = nx.Graph()
    rng = np.random.default_rng(seed)
    nid = 0
    constraints = {'edge_only': [], 'must_colocate': []}

    # ── 1. Compute clusters ──
    cluster_cores = {}
    cluster_srams = {}
    for cid in range(n_compute_clusters):
        cores = []
        for i in range(cores_per_cluster):
            G.add_node(nid, name=f'core_{cid}_{i}', type='tensor_core',
                       area=4.0, power=5.0, compute=8.0, sram=0.5,
                       preferred_process=5, cluster=cid)
            cores.append(nid)
            nid += 1
        cluster_cores[cid] = cores

        # Local SRAM per cluster
        sram_id = nid
        G.add_node(nid, name=f'sram_{cid}', type='sram_bank',
                   area=3.0, power=1.0, compute=0.0, sram=8.0,
                   preferred_process=5, cluster=cid)
        cluster_srams[cid] = sram_id
        nid += 1

    # ── 2. Shared L2 cache banks ──
    cache_ids = []
    for i in range(n_shared_cache):
        G.add_node(nid, name=f'l2_cache_{i}', type='shared_cache',
                   area=6.0, power=2.0, compute=0.0, sram=16.0,
                   preferred_process=5, cluster=-1)
        cache_ids.append(nid)
        nid += 1

    # ── 3. HBM controllers ──
    hbm_ids = []
    for i in range(n_hbm_ctrl):
        G.add_node(nid, name=f'hbm_ctrl_{i}', type='hbm_ctrl',
                   area=5.0, power=3.0, compute=0.0, sram=0.0,
                   preferred_process=28, cluster=-1)
        hbm_ids.append(nid)
        constraints['edge_only'].append(nid)  # must be at grid edges
        nid += 1

    # ── 4. Reduction units ──
    reduce_ids = []
    for i in range(n_reduction_units):
        G.add_node(nid, name=f'reduce_{i}', type='reduction',
                   area=2.0, power=2.0, compute=2.0, sram=0.0,
                   preferred_process=5, cluster=-1)
        reduce_ids.append(nid)
        nid += 1

    # ── EDGES ──

    # 5a. Intra-cluster: core ↔ core (high BW)
    for cid in range(n_compute_clusters):
        cores = cluster_cores[cid]
        for i in range(len(cores)):
            for j in range(i + 1, len(cores)):
                G.add_edge(cores[i], cores[j], bandwidth=50.0 + rng.uniform(-5, 5))

    # 5b. Core ↔ local SRAM (very high BW)
    for cid in range(n_compute_clusters):
        for core in cluster_cores[cid]:
            G.add_edge(core, cluster_srams[cid], bandwidth=200.0 + rng.uniform(-10, 10))

    # 5c. Core ↔ shared L2 cache (moderate BW, creates star pattern)
    for cid in range(n_compute_clusters):
        # Each cluster talks to 1-2 cache banks
        assigned_caches = [cache_ids[cid % n_shared_cache]]
        if n_shared_cache > 1:
            assigned_caches.append(cache_ids[(cid + 1) % n_shared_cache])
        for core in cluster_cores[cid]:
            for cache in assigned_caches:
                G.add_edge(core, cache, bandwidth=30.0 + rng.uniform(-3, 3))

    # 5d. Cache ↔ HBM (high BW, memory traffic)
    for i, cache in enumerate(cache_ids):
        hbm = hbm_ids[i % n_hbm_ctrl]
        G.add_edge(cache, hbm, bandwidth=150.0 + rng.uniform(-10, 10))
        # Also connect to secondary HBM
        hbm2 = hbm_ids[(i + 1) % n_hbm_ctrl]
        G.add_edge(cache, hbm2, bandwidth=80.0 + rng.uniform(-5, 5))

    # 5e. Pipeline: cluster[i] → reduction → cluster[i+1] (sequential flow)
    for i in range(n_compute_clusters - 1):
        red = reduce_ids[i % n_reduction_units]
        # Last core of cluster i → reduction unit
        src_core = cluster_cores[i][-1]
        G.add_edge(src_core, red, bandwidth=100.0 + rng.uniform(-5, 5))
        # Reduction unit → first core of cluster i+1
        dst_core = cluster_cores[i + 1][0]
        G.add_edge(red, dst_core, bandwidth=100.0 + rng.uniform(-5, 5))

    # 5f. Cross-cluster connections (all-reduce, data sharing)
    all_cores = [c for cores in cluster_cores.values() for c in cores]
    n_cross = int(len(all_cores) * cross_cluster_ratio)
    for _ in range(n_cross):
        c1 = rng.choice(all_cores)
        c2 = rng.choice(all_cores)
        cid1 = G.nodes[c1]['cluster']
        cid2 = G.nodes[c2]['cluster']
        if c1 != c2 and cid1 != cid2:
            bw = rng.uniform(10, 40)
            if G.has_edge(c1, c2):
                G[c1][c2]['bandwidth'] += bw
            else:
                G.add_edge(c1, c2, bandwidth=bw)

    # 5g. Reduction unit all-to-all (small BW)
    for i in range(len(reduce_ids)):
        for j in range(i + 1, len(reduce_ids)):
            G.add_edge(reduce_ids[i], reduce_ids[j],
                       bandwidth=20.0 + rng.uniform(-2, 2))

    # 5h. SRAM ↔ cache (writeback traffic)
    for cid in range(n_compute_clusters):
        cache = cache_ids[cid % n_shared_cache]
        G.add_edge(cluster_srams[cid], cache, bandwidth=60.0 + rng.uniform(-5, 5))

    # Must-colocate constraints: each core should be with its local SRAM
    for cid in range(n_compute_clusters):
        constraints['must_colocate'].append(
            (cluster_cores[cid], cluster_srams[cid]))

    return G, constraints


def get_edge_modules(grid):
    """Get chiplet IDs that are at the grid edges (for HBM placement)."""
    edge_ids = set()
    for cid in range(grid.K):
        r, c = grid.positions[cid]
        if r == 0 or r == grid.rows - 1 or c == 0 or c == grid.cols - 1:
            edge_ids.add(cid)
    return edge_ids
