"""Power analysis for v2 (improved masking) results.

Reads sweep_v3_isowire_seedinject_v2_K*.json (the new masking results),
runs BookSim with sim_power=1 on:
  - new masked topology (different from old)
  - superset (same as old)
  - kite_l (same as old)

Reuses results from power_analysis.json (old) where the alloc is identical
(superset, kite_l). Only runs new power for masked topology that changed.

Output: results/ml_placement/power_analysis_v2.json
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from analyze_power import (
    run_booksim_power, str_alloc_to_dict, CELLS, RESULTS_DIR
)

POWER_OUT_V2 = RESULTS_DIR / 'power_analysis_v2.json'
POWER_OLD = RESULTS_DIR / 'power_analysis.json'


def loop_once():
    """One pass over all v2 JSON files, processing newly-completed combos."""
    if POWER_OUT_V2.exists():
        results = json.loads(POWER_OUT_V2.read_text())
    else:
        results = {}

    old_results = {}
    if POWER_OLD.exists():
        old_results = json.loads(POWER_OLD.read_text())

    n_new_runs = 0

    for fname in sorted(RESULTS_DIR.glob('sweep_v3_isowire_seedinject_v2_K*.json')):
        sweep = json.loads(fname.read_text())
        cell_key = fname.stem.replace('sweep_v3_isowire_seedinject_v2_', '')
        if cell_key not in CELLS:
            continue
        K, N, R, C = CELLS[cell_key]

        for subset_key, sv in sweep.items():
            cv = sv.get(cell_key, {})
            if not cv.get('stage2') or not cv.get('baselines_at_W'):
                continue

            wl_list = subset_key.split('+')
            combo_key = f'{cell_key}|{subset_key}'
            results.setdefault(combo_key, {})

            selected = cv['selected']
            superset_alloc = str_alloc_to_dict(cv['candidates'][selected]['alloc'])
            kite_l_alloc = str_alloc_to_dict(cv['baselines_at_W']['kite_l']['alloc'])

            old_combo = old_results.get(combo_key, {})

            for wl in wl_list:
                if wl not in cv['stage2']:
                    continue
                wl_entry = results[combo_key].get(wl, {})
                old_wl = old_combo.get(wl, {})

                new_mask_alloc = str_alloc_to_dict(cv['stage2'][wl]['final_mask'])

                # superset: reuse old (same alloc)
                if 'superset' not in wl_entry and old_wl.get('superset'):
                    wl_entry['superset'] = old_wl['superset']
                if 'superset' not in wl_entry:
                    print(f"  [{combo_key}|{wl}] superset ...", flush=True)
                    t0 = time.time()
                    r = run_booksim_power(
                        f'v3si_v2_{cell_key}_{subset_key}_super',
                        superset_alloc, K, N, R, C, wl)
                    print(f"    → power={r.get('total_power')} ({time.time()-t0:.0f}s)",
                          flush=True)
                    wl_entry['superset'] = r
                    n_new_runs += 1

                # kite_l: reuse old (same alloc)
                if 'kite_l' not in wl_entry and old_wl.get('kite_l'):
                    wl_entry['kite_l'] = old_wl['kite_l']
                if 'kite_l' not in wl_entry:
                    print(f"  [{combo_key}|{wl}] kite_l ...", flush=True)
                    t0 = time.time()
                    r = run_booksim_power(
                        f'v3si_v2_{cell_key}_{subset_key}_kitel',
                        kite_l_alloc, K, N, R, C, wl)
                    print(f"    → power={r.get('total_power')} ({time.time()-t0:.0f}s)",
                          flush=True)
                    wl_entry['kite_l'] = r
                    n_new_runs += 1

                # masked: must run new (alloc changed)
                if 'masked' not in wl_entry:
                    print(f"  [{combo_key}|{wl}] masked_v2 ...", flush=True)
                    t0 = time.time()
                    r = run_booksim_power(
                        f'v3si_v2_{cell_key}_{subset_key}_mask_{wl[:4]}',
                        new_mask_alloc, K, N, R, C, wl)
                    print(f"    → power={r.get('total_power')} ({time.time()-t0:.0f}s)",
                          flush=True)
                    wl_entry['masked'] = r
                    n_new_runs += 1

                results[combo_key][wl] = wl_entry
                POWER_OUT_V2.write_text(json.dumps(results, indent=2))

    return n_new_runs


def main():
    while True:
        n = loop_once()
        if n == 0:
            # No new work — wait for remask_v2 to produce more
            print(f"  ...idle, waiting 60s for new v2 combos...", flush=True)
            time.sleep(60)
        else:
            print(f"  >>> processed {n} new BookSim runs this pass", flush=True)


if __name__ == '__main__':
    main()
