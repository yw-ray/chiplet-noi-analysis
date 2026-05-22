"""Measure BookSim latency variance across seeds for one (cell, combo, wl).

Generic across cells: pass --cell K{16,32}_N{4,8}. For each cell, picks
combo=moe+uniform_random and workload=moe (both present in all completed
sweep cells); runs ours_mask, mesh, kite_l with 5 different BookSim seeds
at rate=0.005 and reports mean/median/std/min/max/CV per alloc plus
ours-vs-mesh Cohen's d.

Requires BookSim binary at booksim2/src/booksim (build via `make`
after `apt-get install flex bison`).
"""

import argparse
import json
import subprocess
import time
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np

from noi_topology_synthesis import (
    ChipletGrid, gen_booksim_config, gen_traffic_matrix_file,
)
from cost_perf_6panel_workload import WORKLOADS

# ----------------------------------------------------------------- config

ROOT = Path(__file__).parent.resolve()
BOOKSIM = (ROOT / 'booksim2' / 'src' / 'booksim').resolve()

# Cell geometry: K is chiplet count on a 4x{4,8} grid; N is per-chiplet
# mesh size (4 -> 2x2 internal nodes, 8 -> 2x4 internal nodes).
CELL_GEOM = {
    'K16_N4': {'K': 16, 'N': 4, 'R': 4, 'C': 4, 'chip_rows': 2, 'chip_cols': 2},
    'K16_N8': {'K': 16, 'N': 8, 'R': 4, 'C': 4, 'chip_rows': 2, 'chip_cols': 4},
    'K32_N4': {'K': 32, 'N': 4, 'R': 4, 'C': 8, 'chip_rows': 2, 'chip_cols': 2},
    'K32_N8': {'K': 32, 'N': 8, 'R': 4, 'C': 8, 'chip_rows': 2, 'chip_cols': 4},
}

COMBO = 'moe+uniform_random'
WORKLOAD = 'moe'          # high-NL: ours should win robustly
RATE = 0.005              # same as sweep_v3 measurement point
SEEDS = [1, 2, 3, 4, 5]
TIMEOUT_S = 900

# ----------------------------------------------------------------- helpers

def parse_alloc(alloc_obj):
    """sweep JSON stores alloc as {"i-j": count}; convert to {(i,j): count}."""
    out = {}
    for k, v in alloc_obj.items():
        i, j = k.split('-')
        out[(int(i), int(j))] = int(v)
    return out


def load_allocs(cell):
    """Pick three allocs from `cell` sweep for the chosen combo."""
    sweep_path = (ROOT / 'results' / 'ml_placement' /
                  f'sweep_v3_isowire_seedinject_v3_{cell}.json')
    with open(sweep_path) as f:
        sweep = json.load(f)
    combo = sweep[COMBO][cell]
    s2 = combo['stage2'][WORKLOAD]
    bls = combo['baselines_at_W']
    return {
        f'ours_mask_{WORKLOAD}': parse_alloc(s2['final_mask']),
        'mesh':                  parse_alloc(bls['mesh']['alloc']),
        'kite_l':                parse_alloc(bls['kite_l']['alloc']),
    }


def write_cfg_anynet(label, alloc, grid, chip_rows, chip_cols, config_dir):
    """Generate .cfg + .anynet for one alloc. Returns cfg path basename."""
    config_dir.mkdir(parents=True, exist_ok=True)
    gen_booksim_config(label, grid, alloc,
                       chip_rows=chip_rows, chip_cols=chip_cols,
                       outdir=config_dir)
    return label


def write_traffic_matrix(label, grid, traffic, npc, config_dir):
    traf_file = config_dir / f'traffic_{label}.txt'
    gen_traffic_matrix_file(grid, traffic, traf_file, npc=npc)
    return traf_file


def run_booksim_seeded(label, traffic_file, rate, seed, config_dir):
    """Run BookSim with explicit seed; return latency or None."""
    cmd = [
        str(BOOKSIM),
        f'{label}.cfg',
        f'injection_rate={rate}',
        f'seed={seed}',
        f'traffic=matrix({traffic_file.name})',
    ]
    t0 = time.time()
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=TIMEOUT_S, cwd=str(config_dir),
        )
    except subprocess.TimeoutExpired:
        return {'latency': None, 'wall_s': time.time() - t0, 'reason': 'timeout'}

    lat = None
    tput = None
    for line in result.stdout.split('\n'):
        if 'Packet latency average' in line:
            for i, p in enumerate(line.split()):
                if p == '=':
                    lat = float(line.split()[i + 1])
        if 'Accepted packet rate average' in line:
            for i, p in enumerate(line.split()):
                if p == '=':
                    tput = float(line.split()[i + 1])
    return {'latency': lat, 'throughput': tput, 'wall_s': time.time() - t0,
            'reason': 'ok' if lat is not None else 'no_lat_line'}


# ----------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cell', required=True, choices=list(CELL_GEOM.keys()))
    args = ap.parse_args()
    cell = args.cell
    geom = CELL_GEOM[cell]
    K = geom['K']; N = geom['N']; R = geom['R']; C = geom['C']
    chip_rows = geom['chip_rows']; chip_cols = geom['chip_cols']
    npc = chip_rows * chip_cols

    config_dir = (ROOT / f'booksim_configs_variance_{cell}').resolve()
    results_path = (ROOT / 'results' / 'ml_placement' /
                    f'multiseed_variance_{cell.lower()}.json').resolve()

    if not BOOKSIM.exists():
        print(f'[ERR] BookSim binary not built: {BOOKSIM}')
        print('Build with: cd booksim2/src && make')
        print('(requires flex + bison: sudo apt-get install -y flex bison)')
        return

    print(f'[setup] cell={cell} combo={COMBO} workload={WORKLOAD} rate={RATE}')
    print(f'        seeds={SEEDS}  (n={len(SEEDS)})')
    print(f'        geom: K={K} N={N} grid={R}x{C} npc={npc}')

    grid = ChipletGrid(R, C)
    builder = WORKLOADS[WORKLOAD]
    traffic = builder(K, grid)

    allocs = load_allocs(cell)
    print(f'[setup] allocs to test: {list(allocs.keys())}')
    print(f'        link counts: '
          + ', '.join(f'{n}={sum(a.values())}' for n, a in allocs.items()))

    # Generate cfg/anynet/traffic ONCE per alloc; seed varies at run time.
    for name, alloc in allocs.items():
        write_cfg_anynet(name, alloc, grid, chip_rows, chip_cols, config_dir)
    traf_file = write_traffic_matrix(WORKLOAD, grid, traffic, npc, config_dir)

    # Parallel sweep over (alloc, seed)
    jobs = [(name, seed) for name in allocs for seed in SEEDS]
    results = {name: [] for name in allocs}
    print(f'[run] {len(jobs)} BookSim runs (parallel up to 6)')
    t_start = time.time()
    with ThreadPoolExecutor(max_workers=6) as ex:
        fut_to_job = {
            ex.submit(run_booksim_seeded, name, traf_file, RATE, seed,
                      config_dir): (name, seed)
            for name, seed in jobs
        }
        for fut in as_completed(fut_to_job):
            name, seed = fut_to_job[fut]
            res = fut.result()
            results[name].append({'seed': seed, **res})
            print(f'  {name:20s} seed={seed}: lat={res["latency"]} '
                  f'tput={res.get("throughput")} '
                  f'({res["wall_s"]:.1f}s, {res["reason"]})')

    # Statistics
    print('\n=== Variance summary ===')
    summary = {}
    for name, rs in results.items():
        lats = [r['latency'] for r in rs if r['latency'] is not None]
        if not lats:
            print(f'  {name}: no successful runs')
            continue
        stats = {
            'n_ok': len(lats),
            'n_total': len(rs),
            'mean': statistics.mean(lats),
            'median': statistics.median(lats),
            'stdev': statistics.stdev(lats) if len(lats) > 1 else 0.0,
            'min': min(lats),
            'max': max(lats),
            'iqr': (
                statistics.quantiles(lats, n=4)[2]
                - statistics.quantiles(lats, n=4)[0]
            ) if len(lats) >= 4 else None,
            'cv': (statistics.stdev(lats) / statistics.mean(lats)
                   if len(lats) > 1 else 0.0),
        }
        summary[name] = stats
        print(f'  {name:20s}: n={stats["n_ok"]}/{stats["n_total"]}, '
              f'mean={stats["mean"]:7.2f}, med={stats["median"]:7.2f}, '
              f'std={stats["stdev"]:6.2f} ({stats["cv"]*100:5.1f}% CV), '
              f'[min={stats["min"]:.1f}, max={stats["max"]:.1f}]')

    # Pairwise: is mesh > ours_mask robust across seeds?
    if 'mesh' in summary and f'ours_mask_{WORKLOAD}' in summary:
        ours = summary[f'ours_mask_{WORKLOAD}']
        mesh = summary['mesh']
        gap = mesh['mean'] - ours['mean']
        pooled_std = ((ours['stdev']**2 + mesh['stdev']**2) / 2) ** 0.5
        cohen_d = gap / pooled_std if pooled_std > 0 else None
        print(f'\n  ours_mask_{WORKLOAD} vs mesh:')
        print(f'    mean gap (mesh - ours) = {gap:+7.2f} cycles')
        print(f'    pooled std             = {pooled_std:7.2f}')
        print(f'    Cohen d (gap/std)      = {cohen_d}')

    print(f'\n[done] elapsed {time.time() - t_start:.1f}s total')

    results_path.parent.mkdir(parents=True, exist_ok=True)
    with open(results_path, 'w') as f:
        json.dump({
            'cell': cell, 'combo': COMBO, 'workload': WORKLOAD,
            'rate': RATE, 'seeds': SEEDS,
            'raw': results, 'summary': summary,
        }, f, indent=2)
    print(f'[done] wrote {results_path}')


if __name__ == '__main__':
    main()
