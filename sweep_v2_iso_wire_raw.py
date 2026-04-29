"""K32_N4 iso-wire sweep with ours = superset_raw (Stage 2 fallback to raw).

For each bpp, baseline allocations are sized to MATCH the ours superset
wire (not the masked wire as before). This is the truly iso-wire
comparison, with ours using the full Stage-1 superset.
"""

import itertools
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


def run_one(label, alloc, K, N, R, C, w_name, rate_mult=4.0):
    grid = ChipletGrid(R, C)
    traffic = WORKLOADS[w_name](K, grid)
    npc = N * N
    rate = (TOTAL_LOAD_BASE / (K * npc)) * rate_mult
    capped = {p: min(n, N) for p, n in alloc.items()}
    cfg = f"v2isoraw_{label}_{w_name}_K{K}N{N}"
    traf_file = f"traffic_v2isoraw_{label}_{w_name}_K{K}N{N}.txt"
    gen_traffic_matrix(grid, traffic, npc, CONFIG_DIR / traf_file)
    gen_anynet_config(cfg, grid, capped, chip_n=N, outdir=CONFIG_DIR)
    return run_booksim(cfg, traf_file, rate, timeout=900)


def main():
    K, N, R, C = 32, 4, 4, 8
    workloads = ['moe', 'hybrid_tp_pp', 'uniform_random', 'all_to_all']
    grid = ChipletGrid(R, C)

    data = json.loads(
        (RESULTS_DIR / 'sweep_v2_pareto_full.json').read_text())
    cd = data['K32_N4']

    raw_data = json.loads(
        (RESULTS_DIR / 'booksim_verify_mask_vs_raw.json').read_text())

    print(f"K=32 N=4 iso-wire (ours = superset_raw): baseline matched to "
          f"superset wire", flush=True)
    print(f"{'bpp':>4} | {'wire':>7} | {'workload':<18} | "
          f"{'mesh':>8} | {'kite_l':>8} | {'ours':>8}", flush=True)
    print('-' * 70, flush=True)

    results = {}
    for bpp_key in sorted(cd.keys(), key=lambda k: int(k.replace('bpp', ''))):
        bd = cd[bpp_key]
        superset = {tuple(int(x) for x in k.split('-')): v
                    for k, v in bd['superset'].items()}
        super_wire = bd['super_wire']
        results[bpp_key] = {'super_wire': super_wire, 'rows': {}}

        for w in workloads:
            wb = super_wire
            mesh_a = mesh_alloc_iso_wire(grid, wb, N)
            kite_l_a = kite_alloc_iso_wire(grid, wb, N, 'large')

            t0 = time.time()
            r_mesh = run_one(f'{bpp_key}_mesh', mesh_a, K, N, R, C, w)
            r_kite = run_one(f'{bpp_key}_kite_l', kite_l_a, K, N, R, C, w)
            elapsed = time.time() - t0

            mesh_lat = r_mesh.get('latency')
            kite_lat = r_kite.get('latency')
            ours_lat = raw_data[bpp_key][w]['raw_lat']

            results[bpp_key]['rows'][w] = {
                'mesh_lat': mesh_lat,
                'kite_l_lat': kite_lat,
                'ours_lat': ours_lat,
                'mesh_wire': alloc_wire_mm2(mesh_a, grid),
                'kite_l_wire': alloc_wire_mm2(kite_l_a, grid),
                'ours_wire': raw_data[bpp_key][w]['raw_wire'],
            }
            print(f"{bpp_key:>4} | {super_wire:>7.1f} | {w:<18} | "
                  f"{(mesh_lat or 0):>8.1f} | {(kite_lat or 0):>8.1f} | "
                  f"{(ours_lat or 0):>8.1f}", flush=True)

    print('\n=== 4-W avg ===', flush=True)
    print(f"{'bpp':>4} | {'super_wire':>10} | {'mesh':>7} | {'kite_l':>7} | {'ours':>7}",
          flush=True)
    for bpp_key, bd in results.items():
        rows = bd['rows']
        m_avg = sum(rows[w]['mesh_lat'] for w in workloads
                    if rows[w]['mesh_lat']) / len(workloads)
        k_avg = sum(rows[w]['kite_l_lat'] for w in workloads
                    if rows[w]['kite_l_lat']) / len(workloads)
        o_avg = sum(rows[w]['ours_lat'] for w in workloads
                    if rows[w]['ours_lat']) / len(workloads)
        print(f"{bpp_key:>4} | {bd['super_wire']:>10.1f} | "
              f"{m_avg:>7.1f} | {k_avg:>7.1f} | {o_avg:>7.1f}", flush=True)

    out = RESULTS_DIR / 'sweep_v2_iso_wire_rawours.json'
    out.write_text(json.dumps(results, indent=2))
    print(f"\nSaved: {out}", flush=True)


if __name__ == '__main__':
    main()
