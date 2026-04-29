"""For each completed (cell, bpp, workload) in mask_greedy sweep,
re-run mesh and kite_l at the SAME wire-area as the final ours mask.
Produces the truly iso-wire comparison.
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
    alloc_wire_mm2, mesh_alloc_iso_wire, kite_alloc_iso_wire,
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
    cfg = f"v2bm_{label}_{w_name}_K{K}N{N}"
    traf_file = f"traffic_v2bm_{label}_{w_name}_K{K}N{N}.txt"
    gen_traffic_matrix(grid, traffic, npc, CONFIG_DIR / traf_file)
    gen_anynet_config(cfg, grid, capped, chip_n=N, outdir=CONFIG_DIR)
    return run_booksim(cfg, traf_file, rate, timeout=900)


def main():
    out_path = RESULTS_DIR / 'booksim_baseline_at_mask_wire.json'
    if out_path.exists():
        try:
            results = json.loads(out_path.read_text())
        except Exception:
            results = {}
    else:
        results = {}

    mg = json.loads((RESULTS_DIR / 'sweep_v2_mask_greedy.json').read_text())

    for cell, cd in mg.items():
        K, N, R, C = CELL_SHAPE[cell]
        grid = ChipletGrid(R, C)
        results.setdefault(cell, {})
        for bpp_key, bd in cd.items():
            results[cell].setdefault(bpp_key, {})
            for w, wd in bd.get('workloads', {}).items():
                if results[cell][bpp_key].get(w):
                    continue
                wire_target = wd['final_wire']
                if wire_target is None or wire_target <= 0:
                    continue

                mesh_a = mesh_alloc_iso_wire(grid, wire_target, N)
                kite_l_a = kite_alloc_iso_wire(grid, wire_target, N, 'large')

                t0 = time.time()
                r_mesh = run_one(f'{cell}_{bpp_key}_mesh',
                                 mesh_a, K, N, R, C, w)
                r_kite = run_one(f'{cell}_{bpp_key}_kite_l',
                                 kite_l_a, K, N, R, C, w)
                elapsed = time.time() - t0

                results[cell][bpp_key][w] = {
                    'wire_target': wire_target,
                    'mesh_lat': r_mesh.get('latency'),
                    'kite_l_lat': r_kite.get('latency'),
                    'mesh_wire': alloc_wire_mm2(mesh_a, grid),
                    'kite_l_wire': alloc_wire_mm2(kite_l_a, grid),
                }
                m_str = (f"{r_mesh.get('latency'):.2f}"
                         if r_mesh.get('latency') is not None else "FAIL")
                k_str = (f"{r_kite.get('latency'):.2f}"
                         if r_kite.get('latency') is not None else "FAIL")
                print(f"  {cell} {bpp_key} {w:<14}: wire_target={wire_target:.1f} "
                      f"| mesh={m_str:>8} | kite_l={k_str:>8} ({elapsed:.1f}s)",
                      flush=True)
                out_path.write_text(json.dumps(results, indent=2))

    print(f"\nSaved: {out_path}", flush=True)


if __name__ == '__main__':
    main()
