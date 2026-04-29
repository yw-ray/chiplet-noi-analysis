"""V2 Wire-area Pareto sweep: BookSim latency vs wire-mm² budget.

For each (method, workload, wire_budget) we run BookSim and record
the latency. The result is a Pareto curve per workload showing which
method dominates at which wire budget.

Ours uses Stage-2 RL masks per workload, capped at the budget. For
large budgets we re-run RL mask training with the larger superset to
allow more express links.
"""

import itertools
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from noi_topology_synthesis import ChipletGrid
from cost_perf_6panel_workload import WORKLOADS
from cost_performance_experiment import (
    gen_anynet_config, gen_traffic_matrix, run_booksim,
)
from ml_express_warmstart import (
    RESULTS_DIR, CONFIG_DIR, TOTAL_LOAD_BASE,
    load_rate_aware_surrogate,
)
from run_rl_multi_workload import train_warmstart_rl_multi
from run_rl_mask import train_mask_rl
from sweep_v2_iso_wire import (
    WIRE_AREA, alloc_wire_mm2,
    mesh_alloc_iso_wire, kite_alloc_iso_wire,
)


def run_one(label, alloc, K, N, R, C, w_name, rate_mult=4.0):
    grid = ChipletGrid(R, C)
    traffic = WORKLOADS[w_name](K, grid)
    npc = N * N
    rate = (TOTAL_LOAD_BASE / (K * npc)) * rate_mult
    capped = {p: min(n, N) for p, n in alloc.items()}
    cfg = f"v2par_{label}_{w_name}_K{K}N{N}"
    traf_file = f"traffic_v2par_{label}_{w_name}_K{K}N{N}.txt"
    gen_traffic_matrix(grid, traffic, npc, CONFIG_DIR / traf_file)
    gen_anynet_config(cfg, grid, capped, chip_n=N, outdir=CONFIG_DIR)
    return run_booksim(cfg, traf_file, rate, timeout=600)


def main():
    K, N, R, C = 16, 4, 4, 4
    workloads = ['moe', 'hybrid_tp_pp', 'uniform_random', 'all_to_all']
    grid = ChipletGrid(R, C)

    # Budget points: bpp -> (link_budget, approx wire-mm²)
    # K=16 N=4: n_adj=24
    # bpp=1 (24 link, ~48-50 mm²) -- too tight, skip
    # bpp=2 (48 link, ~150 mm²)
    # bpp=3 (72 link, ~250 mm²)
    # bpp=4 (96 link, ~340 mm²)
    bpp_points = [2, 3, 4]

    surrogate = load_rate_aware_surrogate()

    all_results = {}

    for bpp in bpp_points:
        link_budget = 24 * bpp
        print(f"\n=== bpp={bpp} (link_budget={link_budget}) ===", flush=True)

        # Train Stage 1 RL with this link budget
        print(f"  Training Ours Stage 1 RL ({len(workloads)}-W) ...", flush=True)
        t0 = time.time()
        rl_result = train_warmstart_rl_multi(
            surrogate, workloads, K, N, R, C, bpp,
            n_episodes=200, rate_mult=4.0,
            reward_type='normalized_avg', max_dist=3, verbose=False,
        )
        superset = rl_result['superset_alloc']
        super_wire = alloc_wire_mm2(superset, grid)
        print(f"    Stage 1 done in {time.time()-t0:.1f}s, "
              f"superset {len(superset)} pairs, "
              f"{sum(superset.values())} links, "
              f"{super_wire:.1f} mm²", flush=True)

        # Train Stage 2 RL mask per workload
        masks = {}
        total_super = sum(superset.values())
        mask_budget = max(1, int(total_super * 0.7))
        for w in workloads:
            t0 = time.time()
            mres = train_mask_rl(
                surrogate, superset, w, K, N, R, C, mask_budget,
                n_episodes=150, rate_mult=4.0, verbose=False,
            )
            masks[w] = mres['mask_alloc']
            mw = alloc_wire_mm2(masks[w], grid)
            print(f"    Stage 2 mask {w:<18}: {mw:.1f} mm² "
                  f"({sum(masks[w].values())} links, {time.time()-t0:.1f}s)",
                  flush=True)

        # Use Ours mask wire-areas as the iso-wire targets per workload
        ours_wires = {w: alloc_wire_mm2(masks[w], grid) for w in workloads}

        # BookSim sweep at this bpp
        raw = {m: {} for m in
               ['mesh', 'kite_s', 'kite_m', 'kite_l', 'ours']}
        wire_used = {m: {} for m in raw}

        for w in workloads:
            wb = ours_wires[w]
            per_method_alloc = {
                'mesh': mesh_alloc_iso_wire(grid, wb, N),
                'kite_s': kite_alloc_iso_wire(grid, wb, N, 'small'),
                'kite_m': kite_alloc_iso_wire(grid, wb, N, 'medium'),
                'kite_l': kite_alloc_iso_wire(grid, wb, N, 'large'),
                'ours': masks[w],
            }
            for method, alloc in per_method_alloc.items():
                t0 = time.time()
                res = run_one(f'bpp{bpp}_{method}', alloc, K, N, R, C, w)
                elapsed = time.time() - t0
                lat = res.get('latency')
                wm = alloc_wire_mm2(alloc, grid)
                raw[method][w] = lat
                wire_used[method][w] = wm
                lat_str = f"{lat:.2f}" if lat is not None else "FAIL"
                print(f"    {method:<8} | {w:<18} | "
                      f"wire={wm:>6.1f} | "
                      f"links={sum(min(v,N) for v in alloc.values()):>3} | "
                      f"lat={lat_str:>10} | {elapsed:>5.1f}s", flush=True)

        all_results[bpp] = {
            'link_budget': link_budget,
            'super_wire': super_wire,
            'ours_wires': ours_wires,
            'raw': raw,
            'wire_used': wire_used,
            'superset': {f"{p[0]}-{p[1]}": v for p, v in superset.items()},
            'masks': {w: {f"{p[0]}-{p[1]}": v for p, v in m.items()}
                      for w, m in masks.items()},
        }

        # Per-bpp mix avg
        methods = list(raw.keys())
        mix_results = {}
        win_count = {m: 0 for m in methods}
        for k in [2, 3, 4]:
            for combo in itertools.combinations(workloads, k):
                lab = '+'.join(combo)
                row = {}
                for m in methods:
                    vals = [raw[m].get(ww) for ww in combo]
                    row[m] = (None if any(v is None for v in vals)
                              else sum(vals) / len(vals))
                mix_results[lab] = row
                valid = [(m, v) for m, v in row.items() if v is not None]
                if valid:
                    win, _ = min(valid, key=lambda x: x[1])
                    win_count[win] += 1
        all_results[bpp]['mix_results'] = mix_results
        all_results[bpp]['win_count'] = win_count
        print(f"  bpp={bpp} winners: " +
              " ".join(f"{m}={c}" for m, c in win_count.items()),
              flush=True)

    out_path = RESULTS_DIR / 'sweep_v2_wire_pareto.json'
    out_path.write_text(json.dumps(all_results, indent=2))
    print(f"\nSaved: {out_path}", flush=True)

    print("\n=== Pareto summary across budgets ===", flush=True)
    for bpp in bpp_points:
        wc = all_results[bpp]['win_count']
        print(f"  bpp={bpp} (super_wire={all_results[bpp]['super_wire']:.0f}"
              f" mm²): " + " ".join(f"{m}={c}" for m, c in wc.items()),
              flush=True)


if __name__ == '__main__':
    main()
