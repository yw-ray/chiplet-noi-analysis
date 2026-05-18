"""Rate-sweep experiment: evaluate (ours mask alloc + 5 baselines) at multiple injection rates.

Output: results/ml_placement/rate_sweep_v3.json
Format: {cell: {combo: {alloc_name: {wl: {rate: {latency, throughput}}}}}}
"""

import json
import sys
import time
import multiprocessing as mp
from pathlib import Path

sys.path.insert(0, '.')
from noi_topology_synthesis import ChipletGrid
from cost_performance_experiment import (
    gen_anynet_config, gen_traffic_matrix, run_booksim,
)
from cost_perf_6panel_workload import WORKLOADS
from ml_express_warmstart import RESULTS_DIR, CONFIG_DIR

# ============================================================
# Configuration
# ============================================================

# Rates to sweep (covers low-load → saturation → past-saturation)
RATES = [0.001, 0.002, 0.003, 0.005, 0.008, 0.012, 0.018]

# Selected representative (cell, combo) pairs
# combos are listed as alphabetically-sorted+joined WL names exactly as in JSON keys
REPRESENTATIVES = [
    # (cell, combo_key, K, N, R, C, source_json)
    ('K16_N4', 'moe+ep_all_to_all',
     16, 4, 4, 4,
     'results/ml_placement/sweep_v3_isowire_seedinject_v3_K16_N4.json'),
    ('K16_N4', 'tree_allreduce+uniform_random',
     16, 4, 4, 4,
     'results/ml_placement/sweep_v3_isowire_seedinject_v3_K16_N4.json'),
    ('K16_N4', 'moe+uniform_random+ep_all_to_all',
     16, 4, 4, 4,
     'results/ml_placement/sweep_v3_isowire_seedinject_v3_K16_N4.json'),

    ('K16_N8', 'moe+ep_all_to_all',
     16, 8, 4, 4,
     'backup_lowload_v3/sweep_v3_isowire_seedinject_v3_K16_N8.json'),
    ('K16_N8', 'hybrid_tp_pp+fsdp',
     16, 8, 4, 4,
     'backup_lowload_v3/sweep_v3_isowire_seedinject_v3_K16_N8.json'),

    ('K32_N4', 'moe+uniform_random',
     32, 4, 4, 8,
     'backup_lowload_v3/sweep_v3_isowire_seedinject_v3_K32_N4.json'),
    ('K32_N4', 'moe+uniform_random+ep_all_to_all',
     32, 4, 4, 8,
     'backup_lowload_v3/sweep_v3_isowire_seedinject_v3_K32_N4.json'),
    ('K32_N4', 'tree_allreduce+uniform_random+ep_all_to_all',
     32, 4, 4, 8,
     'backup_lowload_v3/sweep_v3_isowire_seedinject_v3_K32_N4.json'),

    ('K32_N8', 'moe+ep_all_to_all',
     32, 8, 4, 8,
     'backup_lowload_v3/sweep_v3_isowire_seedinject_v3_K32_N8.json'),
    ('K32_N8', 'hybrid_tp_pp+ep_all_to_all',
     32, 8, 4, 8,
     'backup_lowload_v3/sweep_v3_isowire_seedinject_v3_K32_N8.json'),
]

N_PARALLEL = 6  # BookSim workers in parallel
OUT_PATH = RESULTS_DIR / 'rate_sweep_v3.json'


def parse_pair(pair_str):
    """'1-3' → (1, 3)."""
    a, b = pair_str.split('-')
    return (int(a), int(b))


def alloc_from_dict(d):
    """JSON dict {'0-1':3, ...} → {(0,1):3, ...}."""
    return {parse_pair(k): v for k, v in d.items()}


def evaluate_alloc(args):
    """Evaluate a single (alloc, wl, rate) via BookSim. Returns (key, ...) so
    the main loop can match results back to jobs even with imap_unordered."""
    key, label, alloc, K, N, R, C, w_name, rate = args
    grid = ChipletGrid(R, C)
    traffic = WORKLOADS[w_name](K, grid)
    npc = N * N
    capped = {p: min(n, N) for p, n in alloc.items() if n > 0}
    cfg = f"rsv3_{label}_{w_name}_K{K}N{N}_r{rate:.4f}"
    traf_file = f"traffic_rsv3_{label}_{w_name}_K{K}N{N}_r{rate:.4f}.txt"
    gen_traffic_matrix(grid, traffic, npc, CONFIG_DIR / traf_file)
    gen_anynet_config(cfg, grid, capped, chip_n=N, outdir=CONFIG_DIR)
    res = run_booksim(cfg, traf_file, rate, timeout=600)
    return (key, label, w_name, rate, res)


def main():
    # Load existing results if any
    if OUT_PATH.exists():
        results = json.loads(OUT_PATH.read_text())
        print(f"Resuming from {OUT_PATH}", flush=True)
    else:
        results = {}

    # Build job list
    jobs = []
    for cell, combo_key, K, N, R, C, src in REPRESENTATIVES:
        src_path = Path(src)
        if not src_path.exists():
            print(f"  SKIP {cell} {combo_key}: {src} not found", flush=True)
            continue
        data = json.loads(src_path.read_text())
        entry = data.get(combo_key, {}).get(cell)
        if not entry:
            print(f"  SKIP {cell} {combo_key}: not in JSON", flush=True)
            continue
        wls = combo_key.split('+')

        # Allocations: ours masked + 5 baselines
        allocs = {}
        for wl in wls:
            s2 = entry.get('stage2', {}).get(wl, {})
            if s2.get('final_mask'):
                allocs[f'ours_mask_{wl}'] = alloc_from_dict(s2['final_mask'])

        baselines = entry.get('baselines_at_W', {})
        for bname, bdat in baselines.items():
            if 'alloc' in bdat:
                allocs[f'baseline_{bname}'] = alloc_from_dict(bdat['alloc'])

        # Build jobs: each (alloc, wl, rate) is one BookSim call
        # For ours_mask_{wl}, only evaluate that specific wl
        # For baseline_*, evaluate all wls in combo
        for alloc_name, alloc in allocs.items():
            target_wls = wls
            if alloc_name.startswith('ours_mask_'):
                target_wls = [alloc_name.replace('ours_mask_', '')]
            for wl in target_wls:
                for rate in RATES:
                    # Check if already done
                    key = f"{cell}|{combo_key}|{alloc_name}|{wl}|{rate:.4f}"
                    if key in results:
                        continue
                    label = f"{cell}_{combo_key}_{alloc_name}"
                    jobs.append((key, (key, label, alloc, K, N, R, C, wl, rate)))

    n_total = len(jobs)
    print(f"\nTotal jobs to run: {n_total} (parallel={N_PARALLEL})", flush=True)
    print(f"Rates: {RATES}\n", flush=True)

    t0 = time.time()
    last_save = t0
    with mp.Pool(N_PARALLEL) as pool:
        for i, res_tuple in enumerate(
                pool.imap_unordered(evaluate_alloc, [a for _, a in jobs])):
            key, label, w_name, rate, res = res_tuple
            results[key] = {
                'label': label, 'wl': w_name, 'rate': rate,
                'latency': res.get('latency'),
                'throughput': res.get('throughput'),
                'success': res.get('success'),
            }
            elapsed = time.time() - t0
            rate_pct = (i + 1) / n_total * 100
            eta_min = (elapsed / (i + 1)) * (n_total - i - 1) / 60
            print(f"  [{i+1}/{n_total} {rate_pct:.0f}%] "
                  f"{label} {w_name} rate={rate:.4f} "
                  f"→ lat={res.get('latency')} (ETA {eta_min:.0f}m)",
                  flush=True)

            # Save every 60s
            if time.time() - last_save > 60:
                OUT_PATH.write_text(json.dumps(results, indent=2))
                last_save = time.time()

    OUT_PATH.write_text(json.dumps(results, indent=2))
    print(f"\n=== DONE in {(time.time()-t0)/60:.1f} min ===", flush=True)
    print(f"Saved: {OUT_PATH}", flush=True)


if __name__ == '__main__':
    main()
