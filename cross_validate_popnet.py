"""Cross-validate BookSim measurements against popnet (LegoSim NoC sim).

Phase 1: K=4 N=4 mesh + uniform_random sanity calibration.
  - Confirm cycle unit + topology semantics match.
  - If lat scale matches (popnet/BookSim ratio consistent across seeds),
    proceed to Phase 2 (K=16 N=8 ep_all_to_all).

For each (cell, workload, alloc, seed):
  1. Use BookSim (already measured, from probe_predictor.json or live)
  2. Build popnet .gv topology from same alloc
  3. Build popnet trace from same traffic matrix + rate
  4. Run popnet, parse avg lat
  5. Compare
"""

import argparse
import json
import math
import random
import re
import statistics
import subprocess
import time
from pathlib import Path

import numpy as np

from noi_topology_synthesis import ChipletGrid
from cost_perf_6panel_workload import WORKLOADS

ROOT = Path(__file__).parent.resolve()
POPNET = (ROOT / 'legosim' / 'popnet_chiplet' / 'build' / 'popnet').resolve()
WORK_DIR = (ROOT / 'popnet_runs').resolve()

# Match BookSim cfg defaults from noi_topology_synthesis.py:302-325
POPNET_VC = 8       # BookSim num_vcs = 8
POPNET_BUF = 16     # BookSim vc_buf_size = 16
POPNET_OUTBUF = 16
POPNET_FLIT = 8     # BookSim packet_size = 8
POPNET_LINK = 1000  # link length um, popnet default
POPNET_SIM_T = 100000   # BookSim: sample_period=10000 * max_samples=10
RATE = 0.005

CELL_GEOM = {
    'K4_N4':  {'K': 4,  'R': 2, 'C': 2, 'chip_rows': 2, 'chip_cols': 2},
    'K16_N8': {'K': 16, 'R': 4, 'C': 4, 'chip_rows': 2, 'chip_cols': 4},
    'K32_N8': {'K': 32, 'R': 4, 'C': 8, 'chip_rows': 2, 'chip_cols': 4},
}

# ----------------------------------------------------------------- topology

def build_gv(alloc, K, R, C, chip_rows, chip_cols, gv_path):
    """Build popnet .gv GraphViz topology from BookSim alloc.

    Mirrors logic in noi_topology_synthesis.gen_booksim_config:255-292.
    """
    npc = chip_rows * chip_cols
    total_nodes = K * npc
    edges = []

    # internal mesh edges
    for cid in range(K):
        base = cid * npc
        for r in range(chip_rows):
            for c in range(chip_cols):
                rid = base + r * chip_cols + c
                if c + 1 < chip_cols:
                    edges.append((rid, base + r * chip_cols + (c + 1)))
                if r + 1 < chip_rows:
                    edges.append((rid, base + (r + 1) * chip_cols + c))

    # inter-chiplet edges from alloc (border-router pairing)
    pos = {i: (i // C, i % C) for i in range(K)}
    for (ci, cj), n_links in alloc.items():
        if n_links <= 0:
            continue
        ri, cip = pos[ci]
        rj, cjp = pos[cj]
        ci_base = ci * npc
        cj_base = cj * npc

        if cjp > cip:
            ci_border = [ci_base + r * chip_cols + (chip_cols - 1)
                         for r in range(chip_rows)]
            cj_border = [cj_base + r * chip_cols for r in range(chip_rows)]
        elif cjp < cip:
            ci_border = [ci_base + r * chip_cols for r in range(chip_rows)]
            cj_border = [cj_base + r * chip_cols + (chip_cols - 1)
                         for r in range(chip_rows)]
        elif rj > ri:
            ci_border = [ci_base + (chip_rows - 1) * chip_cols + c
                         for c in range(chip_cols)]
            cj_border = [cj_base + c for c in range(chip_cols)]
        else:
            ci_border = [ci_base + c for c in range(chip_cols)]
            cj_border = [cj_base + (chip_rows - 1) * chip_cols + c
                         for c in range(chip_cols)]

        n = min(n_links, len(ci_border), len(cj_border))
        for k in range(n):
            edges.append((ci_border[k], cj_border[k]))

    # write .gv
    with open(gv_path, 'w') as f:
        f.write('graph G {\n')
        f.write('    edge[weight=1]\n')
        f.write('    node[pipeline_stage_delay=1]\n')
        for (a, b) in edges:
            f.write(f'    {a}--{b}\n')
        f.write('}\n')

    return total_nodes, len(edges)


# ----------------------------------------------------------------- traffic

def build_trace(traffic_chiplet, K, chip_rows, chip_cols, rate, sim_T,
                seed, trace_path):
    """Build popnet trace from chiplet-level traffic matrix.

    Expand chiplet-level T (K×K) to node-level (K*N × K*N) using
    gen_traffic_matrix_file's logic (noi_topology_synthesis.py:335-363).
    Then generate per-node Poisson-process packet events at injection_rate.

    Trace format per popnet README:
      T sx sy dx dy n
    where (sx, sy) is 2D coord. We use 2D layout: sqrt(K*N) × sqrt(K*N)
    if perfect square, else 1D with `-c 1`.

    Returns: (n_packets, side_len_for_-A, cube_dim).
    """
    npc = chip_rows * chip_cols
    total_nodes = K * npc

    # Build node-level traffic matrix (integer weights)
    node_traf = np.zeros((total_nodes, total_nodes), dtype=np.int64)
    for ci in range(K):
        for cj in range(K):
            if ci == cj or traffic_chiplet[ci][cj] <= 0:
                continue
            w = max(1, int(traffic_chiplet[ci][cj] / (npc * npc)))
            for ni in range(npc):
                for nj in range(npc):
                    src = ci * npc + ni
                    dst = cj * npc + nj
                    if src != dst:
                        node_traf[src][dst] += w
    # small intra-chiplet background, same as BookSim's setup
    for ci in range(K):
        for ni in range(npc):
            for nj in range(npc):
                src, dst = ci * npc + ni, ci * npc + nj
                if src != dst:
                    node_traf[src][dst] += 1

    # row PMFs for dest sampling
    row_sums = node_traf.sum(axis=1)

    # 2D layout: try perfect-square side
    side = int(math.isqrt(total_nodes))
    if side * side == total_nodes:
        cube_dim = 2
        ary = side
    else:
        cube_dim = 1
        ary = total_nodes

    def coord(node):
        if cube_dim == 2:
            return node // side, node % side
        return node, 0

    rng = random.Random(seed)
    events = []
    for t in range(sim_T):
        for src in range(total_nodes):
            if row_sums[src] <= 0:
                continue
            if rng.random() < rate:
                # sample dst proportional to node_traf[src]
                r = rng.randint(0, int(row_sums[src]) - 1)
                cumsum = 0
                dst = 0
                for j in range(total_nodes):
                    cumsum += node_traf[src][j]
                    if cumsum > r:
                        dst = j
                        break
                sx, sy = coord(src)
                dx, dy = coord(dst)
                events.append(f'{t:.4e} {sx} {sy} {dx} {dy} {POPNET_FLIT}')

    # write
    with open(trace_path, 'w') as f:
        f.write('\n'.join(events) + '\n')

    return len(events), ary, cube_dim


# ----------------------------------------------------------------- runner

def run_popnet(gv_path, trace_path, ary, cube_dim, seed, log_path):
    cmd = [
        str(POPNET),
        '-A', str(ary),
        '-c', str(cube_dim),
        '-V', str(POPNET_VC),
        '-B', str(POPNET_BUF),
        '-O', str(POPNET_OUTBUF),
        '-F', str(POPNET_FLIT),
        '-L', str(POPNET_LINK),
        '-T', str(POPNET_SIM_T),
        '-r', str(seed),
        '-I', str(trace_path),
        '-R', '1',          # opty (adaptive) routing — uses -G topology
        '-G', str(gv_path),
    ]
    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    except subprocess.TimeoutExpired:
        return {'lat': None, 'wall_s': time.time() - t0, 'reason': 'timeout'}
    with open(log_path, 'w') as f:
        f.write(r.stdout)
        f.write('\n---stderr---\n')
        f.write(r.stderr)
    lat = None
    n_finished = None
    m = re.search(r'total finished:\s*(\d+)', r.stdout)
    if m:
        n_finished = int(m.group(1))
    m = re.search(r'average Delay:\s*(-?nan|-?[0-9.eE+-]+)', r.stdout)
    if m:
        v = m.group(1)
        if 'nan' not in v.lower():
            try:
                lat = float(v)
            except ValueError:
                pass
    reason = 'ok' if lat is not None else ('deadlock' if n_finished == 0 else 'no_lat')
    return {'lat': lat, 'n_finished': n_finished,
            'wall_s': time.time() - t0, 'reason': reason}


# ----------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cell', required=True, choices=list(CELL_GEOM.keys()))
    ap.add_argument('--workload', required=True)
    ap.add_argument('--alloc', choices=['mesh', 'mesh_plus_1'], default='mesh')
    ap.add_argument('--seeds', default='1,2,3,4,5')
    args = ap.parse_args()

    seeds = [int(s) for s in args.seeds.split(',')]
    geom = CELL_GEOM[args.cell]
    K = geom['K']; R = geom['R']; C = geom['C']
    chip_rows = geom['chip_rows']; chip_cols = geom['chip_cols']

    WORK_DIR.mkdir(parents=True, exist_ok=True)
    print(f'[setup] cell={args.cell} workload={args.workload} alloc={args.alloc}')
    print(f'        K={K} R={R} C={C} chip={chip_rows}x{chip_cols}')

    # build alloc — match probe_predictor.py
    grid = ChipletGrid(R, C)
    pos = {i: (i // C, i % C) for i in range(K)}
    adj = set()
    for i in range(K):
        for j in range(i + 1, K):
            dr = abs(pos[i][0] - pos[j][0])
            dc = abs(pos[i][1] - pos[j][1])
            if dr + dc == 1:
                adj.add((i, j))
    mesh_alloc = {p: 4 for p in adj}

    builder = WORKLOADS[args.workload]
    traffic = np.asarray(builder(K, grid), dtype=float)

    if args.alloc == 'mesh_plus_1':
        # heaviest non-adj pair
        best_w = -1; best_pair = None
        for i in range(K):
            for j in range(i + 1, K):
                if (i, j) in adj:
                    continue
                w = float(traffic[i, j] + traffic[j, i])
                if w > best_w:
                    best_w = w; best_pair = (i, j)
        alloc = dict(mesh_alloc); alloc[best_pair] = 1
        print(f'        added express link {best_pair}')
    else:
        alloc = mesh_alloc

    # generate .gv
    gv_path = WORK_DIR / f'{args.cell}_{args.workload}_{args.alloc}.gv'
    n_nodes, n_edges = build_gv(alloc, K, R, C, chip_rows, chip_cols, gv_path)
    print(f'[topo] {n_nodes} nodes, {n_edges} edges → {gv_path.name}')

    # per-seed: generate trace + run popnet
    print(f'[run] {len(seeds)} seeds')
    results = []
    for seed in seeds:
        trace_path = WORK_DIR / f'{args.cell}_{args.workload}_{args.alloc}_s{seed}.trace'
        log_path = WORK_DIR / f'{args.cell}_{args.workload}_{args.alloc}_s{seed}.log'
        t0 = time.time()
        n_pkts, ary, cube_dim = build_trace(traffic, K, chip_rows, chip_cols,
                                            RATE, POPNET_SIM_T, seed, trace_path)
        gen_s = time.time() - t0
        r = run_popnet(gv_path, trace_path, ary, cube_dim, seed, log_path)
        print(f'  seed={seed}: trace={n_pkts} pkts (gen {gen_s:.1f}s), '
              f'lat={r["lat"]}, wall={r["wall_s"]:.1f}s ({r["reason"]})')
        results.append({'seed': seed, 'n_packets': n_pkts,
                        'gen_s': gen_s, **r})

    lats = [r['lat'] for r in results if r['lat'] is not None]
    if lats:
        mean = statistics.mean(lats)
        sd = statistics.stdev(lats) if len(lats) > 1 else 0.0
        print(f'\n=== popnet results ===')
        print(f'  mean={mean:.2f}, std={sd:.2f}, '
              f'CV={sd/mean*100 if mean else 0:.1f}%, n={len(lats)}/{len(seeds)}')

    out = {
        'cell': args.cell, 'workload': args.workload, 'alloc': args.alloc,
        'seeds': seeds, 'results': results,
        'config': {'rate': RATE, 'sim_T': POPNET_SIM_T,
                   'vc': POPNET_VC, 'buf': POPNET_BUF, 'flit': POPNET_FLIT}
    }
    out_path = ROOT / 'results' / 'ml_placement' / f'popnet_{args.cell}_{args.workload}_{args.alloc}.json'
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump(out, f, indent=2)
    print(f'[done] wrote {out_path}')


if __name__ == '__main__':
    main()
