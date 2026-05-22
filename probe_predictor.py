"""Cheap-sim probe predictor: measure express-link sensitivity from
one BookSim call vs the demand-based NL% predictor.

For each (workload, cell), run BookSim multi-seed on:
  (a) mesh baseline
  (b) mesh + 1 express PHY link on the heaviest non-adj traffic pair

probe_gain := (lat_mesh - lat_mesh_plus_1_express) / lat_mesh

Compared against NL% (demand-based) for Spearman rho against RL saving.
"""

import json
import math
import statistics
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np

from noi_topology_synthesis import (
    ChipletGrid, gen_booksim_config, gen_traffic_matrix_file,
)
from cost_perf_6panel_workload import WORKLOADS

ROOT = Path(__file__).parent.resolve()
BOOKSIM = (ROOT / 'booksim2' / 'src' / 'booksim').resolve()
CONFIG_DIR = (ROOT / 'booksim_configs_probe_full').resolve()
RESULTS_PATH = (ROOT / 'results' / 'ml_placement' /
                'probe_predictor_full.json').resolve()

# K x N grid: K in {4,8,16,32}, N in {4,8,16}
# Grid layouts: K=4 -> 2x2, K=8 -> 2x4, K=16 -> 4x4, K=32 -> 4x8
# Internal mesh: N=4 -> 2x2, N=8 -> 2x4, N=16 -> 4x4
def _cell(K, N):
    grid = {4: (2, 2), 8: (2, 4), 16: (4, 4), 32: (4, 8)}[K]
    chip = {4: (2, 2), 8: (2, 4), 16: (4, 4)}[N]
    return {
        'name': f'K{K}_N{N}', 'K': K,
        'R': grid[0], 'C': grid[1],
        'chip_rows': chip[0], 'chip_cols': chip[1],
    }

CELLS = [_cell(K, N) for K in (4, 8, 16, 32) for N in (4, 8, 16)]

WORKLOAD_NAMES = ['moe', 'hybrid_tp_pp', 'tree_allreduce',
                  'uniform_random', 'ep_all_to_all', 'fsdp',
                  'ring_allreduce']

SEEDS = [1, 2, 3, 4, 5]
RATE = 0.005
TIMEOUT_S = 1800    # large cells (K=32, N=16) can take minutes per run
MAX_PARALLEL = 8


# ----------------------------------------------------------------- helpers

def adjacency_set(K, R, C):
    pos = [(i // C, i % C) for i in range(K)]
    adj = set()
    for i in range(K):
        for j in range(i + 1, K):
            dr = abs(pos[i][0] - pos[j][0])
            dc = abs(pos[i][1] - pos[j][1])
            if dr + dc == 1:
                adj.add((i, j))
    return adj


def build_mesh_alloc(K, R, C, chip_rows, chip_cols):
    """Mesh = saturate adj pairs with chip_rows*1 (or chip_cols*1) border slots
    on the side facing that neighbor. Match sweep_v3 mesh: alloc value
    proportional to border slots so that BookSim caps at min(alloc, border)."""
    adj = adjacency_set(K, R, C)
    # border slots per side: for N=4 (2x2), each side has 2 slots; for N=8 (2x4)
    # each side has either 2 (vertical neighbor) or 4 (horizontal neighbor)
    # but the cap min(alloc, border) handles this — we just set alloc=4 (max)
    return {pair: 4 for pair in adj}


def heaviest_non_adj_pair(T, K, adj):
    """Return the (i, j) non-adj pair (i<j) with maximum sum(T[i,j]+T[j,i])."""
    best_w = -1.0
    best = None
    for i in range(K):
        for j in range(i + 1, K):
            if (i, j) in adj:
                continue
            w = float(T[i, j] + T[j, i])
            if w > best_w:
                best_w = w
                best = (i, j)
    return best


def nl_percent(T, K, R, C):
    pos = [(i // C, i % C) for i in range(K)]
    total = float(T.sum())
    if total <= 0:
        return 0.0
    nonadj = 0.0
    for i in range(K):
        for j in range(K):
            if i == j:
                continue
            dr = abs(pos[i][0] - pos[j][0])
            dc = abs(pos[i][1] - pos[j][1])
            if dr + dc != 1:
                nonadj += T[i, j]
    return 100.0 * nonadj / total


def write_cfg(label, alloc, grid, chip_rows, chip_cols, cfg_dir):
    cfg_dir.mkdir(parents=True, exist_ok=True)
    gen_booksim_config(label, grid, alloc,
                       chip_rows=chip_rows, chip_cols=chip_cols,
                       outdir=cfg_dir)
    return label


def run_booksim(label, traf_file, seed, cfg_dir):
    cmd = [str(BOOKSIM), f'{label}.cfg',
           f'injection_rate={RATE}', f'seed={seed}',
           f'traffic=matrix({traf_file.name})']
    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=TIMEOUT_S, cwd=str(cfg_dir))
    except subprocess.TimeoutExpired:
        return {'lat': None, 'wall_s': time.time() - t0, 'reason': 'timeout'}
    lat = None
    for line in r.stdout.split('\n'):
        if 'Packet latency average' in line:
            for i, p in enumerate(line.split()):
                if p == '=':
                    lat = float(line.split()[i + 1])
    return {'lat': lat, 'wall_s': time.time() - t0,
            'reason': 'ok' if lat is not None else 'no_lat_line'}


# ----------------------------------------------------------------- main

def main():
    if not BOOKSIM.exists():
        print(f'[ERR] BookSim not built: {BOOKSIM}')
        return

    overall_t0 = time.time()
    results = {}  # results[cell_name][wl] = {nl, lat_mesh: [..], lat_p1: [..], probe}

    # ---- prepare all jobs first
    jobs = []   # (cell_name, wl, alloc_label, seed, alloc, traf_file)
    metadata = {}  # (cell, wl) -> {nl, heaviest, cfg_dir}

    for cell in CELLS:
        cn = cell['name']; K = cell['K']; R = cell['R']; C = cell['C']
        chip_rows = cell['chip_rows']; chip_cols = cell['chip_cols']
        cfg_dir = (CONFIG_DIR / cn).resolve()
        grid = ChipletGrid(R, C)
        adj = adjacency_set(K, R, C)
        mesh = build_mesh_alloc(K, R, C, chip_rows, chip_cols)
        results[cn] = {}
        for wl in WORKLOAD_NAMES:
            builder = WORKLOADS.get(wl)
            if builder is None:
                continue
            T = np.asarray(builder(K, grid), dtype=float)
            nl = nl_percent(T, K, R, C)
            heaviest = heaviest_non_adj_pair(T, K, adj)
            if heaviest is None:
                continue
            mesh_plus_1 = dict(mesh); mesh_plus_1[heaviest] = 1
            mesh_label = f'{wl}_mesh'
            mesh1_label = f'{wl}_mesh_plus_1'
            write_cfg(mesh_label, mesh, grid, chip_rows, chip_cols, cfg_dir)
            write_cfg(mesh1_label, mesh_plus_1, grid, chip_rows, chip_cols, cfg_dir)
            traf_file = cfg_dir / f'traffic_{wl}.txt'
            gen_traffic_matrix_file(grid, T, traf_file, npc=chip_rows*chip_cols)
            metadata[(cn, wl)] = {
                'nl': nl, 'heaviest': heaviest, 'cfg_dir': cfg_dir,
                'mesh_lats': [], 'p1_lats': [],
            }
            for seed in SEEDS:
                jobs.append((cn, wl, mesh_label,  'mesh', seed, cfg_dir, traf_file))
                jobs.append((cn, wl, mesh1_label, 'p1',   seed, cfg_dir, traf_file))

    total = len(jobs)
    print(f'[plan] {total} BookSim runs across {len(metadata)} (cell, wl) pairs')
    print(f'       parallelism={MAX_PARALLEL}, est wall '
          f'~{total*30/MAX_PARALLEL/60:.1f} min')

    # ---- execute parallel
    done = 0
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as ex:
        fut2job = {}
        for cn, wl, label, kind, seed, cfg_dir, traf_file in jobs:
            fut = ex.submit(run_booksim, label, traf_file, seed, cfg_dir)
            fut2job[fut] = (cn, wl, kind, seed)
        for fut in as_completed(fut2job):
            cn, wl, kind, seed = fut2job[fut]
            r = fut.result()
            done += 1
            if r['lat'] is not None:
                key = 'mesh_lats' if kind == 'mesh' else 'p1_lats'
                metadata[(cn, wl)][key].append(r['lat'])
            if done % 20 == 0 or done == total:
                el = time.time() - overall_t0
                print(f'  [{done}/{total}] {el:.0f}s elapsed')

    # ---- aggregate
    print('\n=== Probe results ===')
    print(f'{"cell":<7} {"wl":<18} {"NL%":>6} {"heaviest":>10} '
          f'{"lat_mesh":>9} {"lat_p1":>9} {"probe%":>7}')
    rows = []
    for (cn, wl), meta in sorted(metadata.items()):
        if not meta['mesh_lats'] or not meta['p1_lats']:
            continue
        lm = statistics.median(meta['mesh_lats'])
        lp = statistics.median(meta['p1_lats'])
        probe = 100.0 * (lm - lp) / lm if lm > 0 else 0.0
        rows.append({
            'cell': cn, 'wl': wl,
            'nl': meta['nl'],
            'heaviest': list(meta['heaviest']),
            'lat_mesh_median': lm, 'lat_p1_median': lp,
            'lat_mesh_all': meta['mesh_lats'], 'lat_p1_all': meta['p1_lats'],
            'probe_gain': probe,
        })
        hv_s = f'{meta["heaviest"][0]}-{meta["heaviest"][1]}'
        print(f'{cn:<7} {wl:<18} {meta["nl"]:>6.1f} {hv_s:>10} '
              f'{lm:>9.2f} {lp:>9.2f} {probe:>7.2f}')

    # ---- Spearman: NL% vs probe vs saving (saving = empty for now)
    def spearman(xs, ys):
        n = len(xs)
        if n < 2: return float('nan')
        def rank(arr):
            idx = sorted(range(n), key=lambda i: arr[i])
            r = [0.0]*n; i=0
            while i<n:
                j=i
                while j+1<n and arr[idx[j+1]]==arr[idx[i]]: j+=1
                avg=(i+j)/2+1
                for k in range(i,j+1): r[idx[k]] = avg
                i = j+1
            return r
        rx = rank(xs); ry = rank(ys)
        mx=sum(rx)/n; my=sum(ry)/n
        num=sum((rx[i]-mx)*(ry[i]-my) for i in range(n))
        dx=math.sqrt(sum((rx[i]-mx)**2 for i in range(n)))
        dy=math.sqrt(sum((ry[i]-my)**2 for i in range(n)))
        if dx==0 or dy==0: return float('nan')
        return num/(dx*dy)

    print('\n=== Spearman: probe vs NL% ===')
    nl_vec = [r['nl'] for r in rows]
    probe_vec = [r['probe_gain'] for r in rows]
    rho = spearman(nl_vec, probe_vec)
    print(f'rho(NL%, probe_gain) = {rho:.3f}')

    print('\nNote: full predictor comparison vs measured saving needs '
          'multi-seed ours-vs-baselines data; not yet aggregated here.')

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_PATH, 'w') as f:
        json.dump({'cells': CELLS, 'rows': rows,
                   'rho_nl_vs_probe': rho,
                   'wall_s': time.time() - overall_t0}, f, indent=2)
    print(f'\n[done] wrote {RESULTS_PATH} (wall {time.time()-overall_t0:.0f}s)')


if __name__ == '__main__':
    main()
