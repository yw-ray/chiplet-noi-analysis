"""Round 4: BookSim-in-the-loop RL on cell 3.

Cell: K=16, N=8, R=4, C=4, bpp=3, subset = (moe, uniform_random, all_to_all).
Target: beat kite_l_iso mean_raw_lat = 61.1 with BookSim-feedback RL.

Each seed runs train_booksim_in_loop_rl_multi for n_episodes with terminal
BookSim reward. Multiple warm-starts are tried; the best by measured mean
latency is kept.

Output: results/ml_placement/retry_cell3_booksim_rl.json
"""

import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).parent))
from noi_topology_synthesis import ChipletGrid
from ml_express_warmstart import RESULTS_DIR
from rl_booksim_in_loop import train_booksim_in_loop_rl_multi
from sweep_v2_iso_wire import (
    alloc_wire_mm2, kite_alloc_iso_wire, mesh_alloc_iso_wire,
)


CELL = {
    'subset': ('moe', 'uniform_random', 'all_to_all'),
    'K': 16, 'N': 8, 'R': 4, 'C': 4, 'bpp': 3,
}
KITE_L_TARGET = 61.1

# Each entry: (seed, warm_start_kind, n_episodes, n_swaps).
# Kite-warm seeds give RL a known-good starting point; greedy-warm seeds
# explore from a different basin. n_episodes kept moderate to fit in time
# budget; ~30-60s × 3 workloads × n_episodes ≈ 75-150 min/seed at 50 ep.
RUNS = [
    (442, 'kite_l',       60, 8),  # done previously: best=61.1 (preserved)
    (444, 'greedy_union', 60, 8),
    (445, 'greedy_union', 60, 8),
    (446, 'mesh',         60, 8),
]

OUT_PATH = RESULTS_DIR / 'retry_cell3_booksim_rl.json'


def cap_alloc(alloc, N):
    return {p: min(int(n), N) for p, n in alloc.items() if n > 0}


def main():
    if OUT_PATH.exists():
        try:
            results = json.loads(OUT_PATH.read_text())
        except Exception:
            results = {}
    else:
        results = {}

    K, N, R, C = CELL['K'], CELL['N'], CELL['R'], CELL['C']
    bpp = CELL['bpp']
    subset = CELL['subset']
    grid = ChipletGrid(R, C)

    ref_wire = 261.5  # kite_l_iso wire from pilot
    kite_alloc = cap_alloc(kite_alloc_iso_wire(grid, ref_wire, N, 'large'), N)
    mesh_alloc = cap_alloc(mesh_alloc_iso_wire(grid, ref_wire, N), N)

    overall_t0 = time.time()
    overall_best = None

    for seed, warm_kind, n_eps, n_sw in RUNS:
        run_key = f'r4_seed{seed}_{warm_kind}'
        if run_key in results and results[run_key].get('best_mean_lat') is not None:
            print(f"[skip] {run_key} already done", flush=True)
            best = results[run_key]['best_mean_lat']
            if overall_best is None or best < overall_best:
                overall_best = best
            continue
        if warm_kind == 'kite_l':
            warm_alloc = kite_alloc
        elif warm_kind == 'mesh':
            warm_alloc = mesh_alloc
        else:
            warm_alloc = None  # default = greedy union
        torch.manual_seed(seed)
        np.random.seed(seed)
        print(f"\n=== Round 4 seed={seed} warm={warm_kind} "
              f"eps={n_eps} n_swaps={n_sw} ===", flush=True)
        t_seed = time.time()
        rl_res = train_booksim_in_loop_rl_multi(
            list(subset), K, N, R, C, bpp,
            n_episodes=n_eps, n_swaps=n_sw,
            warm_start_alloc=warm_alloc,
            label_prefix=run_key,
            cap_mean_lat=2 * KITE_L_TARGET * 4,  # tame outliers
            verbose=True,
        )
        seed_t = time.time() - t_seed
        best = rl_res.get('best_mean_lat')
        baseline = rl_res.get('baseline_mean_lat')
        delta = (best - KITE_L_TARGET) if best is not None else None
        delta_str = f'{delta:+.1f}' if delta is not None else 'NA'
        print(f"  seed={seed} done in {seed_t/60:.1f} min: "
              f"baseline={baseline}, best={best} "
              f"(Δ={delta_str})", flush=True)

        rl_res['seed'] = seed
        rl_res['warm_kind'] = warm_kind
        rl_res['kite_l_target'] = KITE_L_TARGET
        rl_res['seed_time_s'] = seed_t
        # Keep alloc as dict-stringified keys for JSON friendliness.
        if 'best_alloc' in rl_res:
            rl_res['best_alloc'] = {
                f'{p[0]}-{p[1]}': v
                for p, v in rl_res['best_alloc'].items()
            }
        # Drop the numpy vector; we stored alloc dict already.
        rl_res.pop('best_alloc_vec', None)
        results[run_key] = rl_res
        OUT_PATH.write_text(json.dumps(results, indent=2))

        if best is not None and (overall_best is None or best < overall_best):
            overall_best = best

        if best is not None and best < KITE_L_TARGET:
            print(f"\n*** Round 4 BEAT kite_l: {best:.1f} < "
                  f"{KITE_L_TARGET} ***", flush=True)
            # keep going so we can pick the strict-best across seeds

    print(f"\n=== Round 4 done in "
          f"{(time.time() - overall_t0)/60:.1f} min ===", flush=True)
    print(f"  Overall best mean_lat: {overall_best}", flush=True)
    print(f"  Target: {KITE_L_TARGET}", flush=True)
    print(f"Saved: {OUT_PATH}", flush=True)


if __name__ == '__main__':
    main()
