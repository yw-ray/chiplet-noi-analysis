"""Re-run Stage 2 masking only, with increased step limit.

Loads existing sweep_v3_isowire_seedinject_K*.json (Stage 1 intact),
re-runs booksim_greedy_mask per workload with new parameters,
saves to sweep_v3_isowire_seedinject_v2_K*.json.

Cell-specific params (early termination makes worst-case estimates pessimistic):
  K16: MAX_STEPS=20, N_CANDIDATES=15
  K32: MAX_STEPS=12, N_CANDIDATES=10  (BookSim ~10x slower)

Run one process per cell in parallel:
  nohup .venv/bin/python3 -u remask_v2.py 0 > logs/remask_v2_K16_N4.log 2>&1 &
  nohup .venv/bin/python3 -u remask_v2.py 1 > logs/remask_v2_K16_N8.log 2>&1 &
  nohup .venv/bin/python3 -u remask_v2.py 2 > logs/remask_v2_K32_N4.log 2>&1 &
  nohup .venv/bin/python3 -u remask_v2.py 3 > logs/remask_v2_K32_N8.log 2>&1 &
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sweep_v2_mask_greedy import booksim_greedy_mask
from sweep_v3_isowire import CELLS, SUBSETS, evaluate_baselines
from noi_topology_synthesis import ChipletGrid

RESULTS_DIR = Path('results/ml_placement')

# Cell-indexed params: (MAX_STEPS, N_CANDIDATES)
CELL_MASK_PARAMS = {
    'K16_N4': (20, 15),
    'K16_N8': (20, 15),
    'K32_N4': (12, 10),
    'K32_N8': (12, 10),
}

# Parallel BookSim per cell process (4 cells × 8 = 32 cores ≈ half of 64)
N_PARALLEL = 8


def remask_cell(cell_idx):
    K, N, R, C, W = CELLS[cell_idx]
    cell_key = f'K{K}_N{N}'
    max_steps, n_cands = CELL_MASK_PARAMS[cell_key]

    src = RESULTS_DIR / f'sweep_v3_isowire_seedinject_{cell_key}.json'
    dst = RESULTS_DIR / f'sweep_v3_isowire_seedinject_v2_{cell_key}.json'

    src_data = json.loads(src.read_text())

    if dst.exists():
        out_data = json.loads(dst.read_text())
        print(f"Resuming {dst}", flush=True)
    else:
        out_data = {}

    n_total = len(SUBSETS)
    n_done = 0
    overall_t0 = time.time()

    for subset in SUBSETS:
        subset_key = '+'.join(subset)
        src_cv = src_data.get(subset_key, {}).get(cell_key, {})

        if not src_cv.get('selected') or not src_cv.get('baselines_at_W'):
            print(f"[skip] {subset_key} — no Stage1 result", flush=True)
            n_done += 1
            continue

        # Resume check
        existing = out_data.get(subset_key, {}).get(cell_key, {})
        if existing.get('stage2') and existing.get('baselines_at_W'):
            n_done += 1
            print(f"[skip {n_done}/{n_total}] {subset_key}", flush=True)
            continue

        t_combo = time.time()
        print(f"\n=== [{n_done+1}/{n_total}] {subset_key} | {cell_key} "
              f"(steps={max_steps}, cands={n_cands}) ===", flush=True)

        # Reconstruct superset from Stage 1
        selected = src_cv['selected']
        superset = {tuple(int(x) for x in k.split('-')): v
                    for k, v in src_cv['candidates'][selected]['alloc'].items()
                    if v > 0}
        super_links = sum(superset.values())

        # Re-run Stage 2 masking
        stage2 = {}
        for wl in subset:
            label = f'v3si_v2_{cell_key}_{subset_key}_{selected}_{wl}'
            t_wl = time.time()
            final_mask, history, raw_lat = booksim_greedy_mask(
                superset, K, N, R, C, wl,
                max_steps=max_steps,
                max_candidates=n_cands,
                lat_tolerance=1.0,
                label_prefix=label,
                n_parallel=N_PARALLEL,
            )
            final_lat = history[-1]['lat'] if history else None
            reverted = False
            if final_lat is None or raw_lat is None or final_lat > raw_lat:
                final_mask = dict(superset)
                final_lat = raw_lat
                reverted = True

            active_links = sum(final_mask.values()) if final_mask else super_links
            active_pct = 100.0 * active_links / super_links if super_links else 100.0
            steps_taken = len(history) - 1
            elapsed = time.time() - t_wl

            rev_str = ' (REVERTED)' if reverted else ''
            print(f"    [mask] {wl:<18}: raw={raw_lat:.1f} mask={final_lat:.1f}{rev_str} "
                  f"active={active_links}/{super_links} ({active_pct:.1f}%) "
                  f"steps={steps_taken} ({elapsed:.0f}s)", flush=True)

            stage2[wl] = {
                'raw_lat': raw_lat,
                'mask_lat': final_lat,
                'mask_reverted_to_raw': reverted,
                'active_link_count': active_links,
                'super_link_count': super_links,
                'active_pct': active_pct,
                'final_mask': {f'{p[0]}-{p[1]}': v for p, v in final_mask.items()},
                'history': history,
            }

        # Copy Stage 1 fields, replace stage2
        out_data.setdefault(subset_key, {})[cell_key] = {
            'W': src_cv['W'],
            'bpp_eq': src_cv['bpp_eq'],
            'candidates': src_cv['candidates'],
            'selected': selected,
            'stage1_lat': src_cv.get('stage1_lat'),
            'stage2': stage2,
            'baselines_at_W': src_cv['baselines_at_W'],
        }
        dst.write_text(json.dumps(out_data, indent=2))
        n_done += 1
        print(f"  Combo done in {(time.time()-t_combo)/60:.1f} min "
              f"({n_done}/{n_total})", flush=True)

    print(f"\n=== ALL DONE {cell_key} in "
          f"{(time.time()-overall_t0)/3600:.1f}h ===", flush=True)
    print(f"Saved: {dst}", flush=True)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: remask_v2.py <cell_idx 0-3>")
        print("  0=K32_N8  1=K16_N8  2=K32_N4  3=K16_N4")
        sys.exit(1)
    remask_cell(int(sys.argv[1]))
