"""Test: re-run Stage 2 masking for K16_N4 with MASK_MAX_STEPS=20.

Compares old (3 steps, 6 candidates) vs new (20 steps, 15 candidates)
to quantify how much more masking we get with relaxed step limit.
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sweep_v2_mask_greedy import booksim_greedy_mask
from sweep_v3_isowire import CELLS

RESULTS_DIR = Path('results/ml_placement')
CELL_IDX = 3  # K16_N4
K, N, R, C, W = CELLS[CELL_IDX]
CELL_KEY = f'K{K}_N{N}'

NEW_MAX_STEPS = 20
NEW_N_CANDIDATES = 15

src = RESULTS_DIR / f'sweep_v3_isowire_seedinject_{CELL_KEY}.json'
data = json.loads(src.read_text())

print(f"Re-running Stage 2 masking for {CELL_KEY} "
      f"(steps={NEW_MAX_STEPS}, cands={NEW_N_CANDIDATES})")
print("=" * 70)

summary_rows = []

for subset_key, sv in data.items():
    cv = sv.get(CELL_KEY, {})
    if not cv.get('stage2') or not cv.get('selected'):
        continue

    superset_str = cv['candidates'][cv['selected']]['alloc']
    superset = {tuple(int(x) for x in k.split('-')): v
                for k, v in superset_str.items() if v > 0}
    super_links = sum(superset.values())
    wl_list = subset_key.split('+')

    print(f"\n[{subset_key}] selected={cv['selected']} super_links={super_links}")

    for wl in wl_list:
        old = cv['stage2'].get(wl, {})
        old_active = old.get('active_link_count', super_links)
        old_pct = old.get('active_pct', 100.0)
        old_lat = old.get('mask_lat')

        t0 = time.time()
        label = f'testmask_{CELL_KEY}_{subset_key}_{wl}'
        final_mask, history, raw_lat = booksim_greedy_mask(
            superset, K, N, R, C, wl,
            max_steps=NEW_MAX_STEPS,
            max_candidates=NEW_N_CANDIDATES,
            lat_tolerance=1.0,
            label_prefix=label,
        )

        new_active = sum(final_mask.values()) if final_mask else super_links
        new_pct = 100.0 * new_active / super_links
        new_lat = history[-1]['lat'] if history else raw_lat
        elapsed = time.time() - t0
        steps_taken = len(history) - 1  # exclude step 0 (initial)

        delta = old_active - new_active
        old_lat = old.get('mask_lat') or old.get('raw_lat')
        lat_str = (f"lat: {raw_lat:.1f}→{new_lat:.1f} "
                   f"({(new_lat-raw_lat)/raw_lat*100:+.1f}%)"
                   if raw_lat and new_lat else "lat: N/A")
        print(f"  {wl:<18}: "
              f"old={old_active}/{super_links} ({old_pct:.1f}%)  "
              f"new={new_active}/{super_links} ({new_pct:.1f}%)  "
              f"Δ={delta:+d} links  {lat_str}  steps={steps_taken}  ({elapsed:.0f}s)")

        summary_rows.append({
            'subset': subset_key, 'wl': wl,
            'super': super_links,
            'old_active': old_active, 'old_pct': old_pct,
            'new_active': new_active, 'new_pct': new_pct,
            'delta': delta, 'steps': steps_taken,
        })

print("\n" + "=" * 70)
print("SUMMARY")
import numpy as np
old_pcts = [r['old_pct'] for r in summary_rows]
new_pcts = [r['new_pct'] for r in summary_rows]
deltas = [r['delta'] for r in summary_rows]
print(f"  Old mean active: {np.mean(old_pcts):.1f}%")
print(f"  New mean active: {np.mean(new_pcts):.1f}%")
print(f"  Mean links additionally removed: {np.mean(deltas):.1f}")
print(f"  Max additionally removed: {max(deltas)}")
print(f"  Cases with improvement: {sum(1 for d in deltas if d > 0)}/{len(deltas)}")
