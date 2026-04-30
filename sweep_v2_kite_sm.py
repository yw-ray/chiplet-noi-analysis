"""Re-run iso-wire BookSim with FIXED kite_s and kite_m (interleave).

Uses ours_mask wire from sweep_v2_full_subsets.json, but evaluates the
new kite_s (dist=2 only) and kite_m (interleaved dist=2 and dist=3)
allocations that differ from the kite_l result already measured.
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from noi_topology_synthesis import ChipletGrid
from cost_perf_6panel_workload import WORKLOADS
from cost_performance_experiment import (
    gen_anynet_config, gen_traffic_matrix, run_booksim,
)
from ml_express_warmstart import RESULTS_DIR, CONFIG_DIR, TOTAL_LOAD_BASE
from sweep_v2_iso_wire import (
    alloc_wire_mm2, kite_alloc_iso_wire,
)


CELL_SHAPE = {
    'K16_N4': (16, 4, 4, 4),
    'K16_N8': (16, 8, 4, 4),
    'K32_N4': (32, 4, 4, 8),
    'K32_N8': (32, 8, 4, 8),
}


def run_one(label, alloc, K, N, R, C, w_name, rate_mult=4.0):
    grid = ChipletGrid(R, C)
    traffic = WORKLOADS[w_name](K, grid)
    npc = N * N
    rate = (TOTAL_LOAD_BASE / (K * npc)) * rate_mult
    capped = {p: min(n, N) for p, n in alloc.items() if n > 0}
    cfg = f"v2ksm_{label}_{w_name}_K{K}N{N}"
    traf_file = f"traffic_v2ksm_{label}_{w_name}_K{K}N{N}.txt"
    gen_traffic_matrix(grid, traffic, npc, CONFIG_DIR / traf_file)
    gen_anynet_config(cfg, grid, capped, chip_n=N, outdir=CONFIG_DIR)
    return run_booksim(cfg, traf_file, rate, timeout=900)


def main():
    out_path = RESULTS_DIR / 'sweep_v2_kite_sm.json'
    if out_path.exists():
        try:
            results = json.loads(out_path.read_text())
        except Exception:
            results = {}
    else:
        results = {}

    full = json.loads(
        (RESULTS_DIR / 'sweep_v2_full_subsets.json').read_text())

    for subset_key, sd in full.items():
        results.setdefault(subset_key, {})
        for cell_key, cd in sd.items():
            results[subset_key].setdefault(cell_key, {})
            K, N, R, C = CELL_SHAPE[cell_key]
            grid = ChipletGrid(R, C)
            for bpp_key, bd in cd.items():
                results[subset_key][cell_key].setdefault(bpp_key, {})
                wd = bd.get('workloads', {})
                for w, w_data in wd.items():
                    if w in results[subset_key][cell_key][bpp_key]:
                        continue
                    wire_target = w_data.get('mask_wire')
                    if wire_target is None:
                        continue

                    kite_s_a = kite_alloc_iso_wire(grid, wire_target, N,
                                                    'small')
                    kite_m_a = kite_alloc_iso_wire(grid, wire_target, N,
                                                    'medium')

                    label = (f'{subset_key}_{cell_key}_{bpp_key}_{w}')
                    t0 = time.time()
                    r_s = run_one(f'{label}_s', kite_s_a,
                                  K, N, R, C, w)
                    r_m = run_one(f'{label}_m', kite_m_a,
                                  K, N, R, C, w)
                    elapsed = time.time() - t0

                    results[subset_key][cell_key][bpp_key][w] = {
                        'wire_target': wire_target,
                        'kite_s_lat': r_s.get('latency'),
                        'kite_m_lat': r_m.get('latency'),
                        'kite_s_wire': alloc_wire_mm2(kite_s_a, grid),
                        'kite_m_wire': alloc_wire_mm2(kite_m_a, grid),
                    }
                    s_str = (f'{r_s.get("latency"):.1f}'
                             if r_s.get('latency') is not None else 'FAIL')
                    m_str = (f'{r_m.get("latency"):.1f}'
                             if r_m.get('latency') is not None else 'FAIL')
                    print(f"  {subset_key:<25} {cell_key} {bpp_key} "
                          f"{w:<14}: kite_s={s_str:>7} kite_m={m_str:>7} "
                          f"({elapsed:.1f}s)", flush=True)
                out_path.write_text(json.dumps(results, indent=2))

    print(f"\nSaved: {out_path}", flush=True)


if __name__ == '__main__':
    main()
