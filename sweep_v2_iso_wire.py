"""V2 sweep with iso-wire-mm² budget.

For each workload w, set the wire budget = Ours mask wire-area for that
workload. Then re-allocate every static baseline within that wire budget
and run BookSim. This is the apples-to-apples comparison the user asked
for: same wire usage, who wins per workload (and on mix averages)?
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


WIRE_AREA = {1: 2.0, 2: 4.1, 3: 6.1, 4: 8.2}


def alloc_wire_mm2(alloc, grid):
    return sum(n * WIRE_AREA.get(grid.get_hops(p[0], p[1]), 0)
               for p, n in alloc.items())


def mesh_alloc_iso_wire(grid, wire_budget, per_pair_cap):
    adj_pairs = grid.get_adj_pairs()
    if wire_budget < WIRE_AREA[1]:
        return {}
    alloc = {}
    used = 0.0
    remaining_idx = 0
    while True:
        progressed = False
        for p in adj_pairs:
            cur = alloc.get(p, 0)
            if cur >= per_pair_cap:
                continue
            if used + WIRE_AREA[1] > wire_budget:
                continue
            alloc[p] = cur + 1
            used += WIRE_AREA[1]
            progressed = True
        if not progressed:
            break
    return alloc


def kite_alloc_iso_wire(grid, wire_budget, per_pair_cap, variant):
    K = grid.K
    adj_pairs = grid.get_adj_pairs()
    adj_set = set(adj_pairs)

    if variant == 'small':
        target_dists = (2,)
    elif variant == 'medium':
        target_dists = (2, 3)
    elif variant == 'large':
        target_dists = (3,)
    else:
        raise ValueError(f"unknown Kite variant: {variant}")

    alloc = {p: 1 for p in adj_pairs}
    used = len(adj_pairs) * WIRE_AREA[1]
    if used > wire_budget:
        n = int(wire_budget // WIRE_AREA[1])
        return {p: 1 for p in adj_pairs[:n]}

    eligible = [(i, j) for i in range(K) for j in range(i + 1, K)
                if (i, j) not in adj_set
                and grid.get_hops(i, j) in target_dists]
    eligible.sort(key=lambda p: (grid.get_hops(p[0], p[1]), p[0], p[1]))

    while used < wire_budget:
        progressed = False
        for p in eligible:
            link_wire = WIRE_AREA[grid.get_hops(p[0], p[1])]
            if used + link_wire > wire_budget:
                continue
            cur = alloc.get(p, 0)
            if cur < per_pair_cap:
                alloc[p] = cur + 1
                used += link_wire
                progressed = True
                if used >= wire_budget:
                    break
        if not progressed:
            break
    return alloc


def run_one(label, alloc, K, N, R, C, w_name, rate_mult=4.0):
    grid = ChipletGrid(R, C)
    traffic = WORKLOADS[w_name](K, grid)
    npc = N * N
    rate = (TOTAL_LOAD_BASE / (K * npc)) * rate_mult
    capped = {p: min(n, N) for p, n in alloc.items()}
    cfg = f"v2iso_{label}_{w_name}_K{K}N{N}"
    traf_file = f"traffic_v2iso_{label}_{w_name}_K{K}N{N}.txt"
    gen_traffic_matrix(grid, traffic, npc, CONFIG_DIR / traf_file)
    gen_anynet_config(cfg, grid, capped, chip_n=N, outdir=CONFIG_DIR)
    return run_booksim(cfg, traf_file, rate, timeout=600)


def main():
    K, N, R, C = 16, 4, 4, 4
    workloads = ['moe', 'hybrid_tp_pp', 'uniform_random', 'all_to_all']
    grid = ChipletGrid(R, C)

    sweep_data = json.loads(
        (RESULTS_DIR / 'sweep_v2_pilot.json').read_text())
    superset = {tuple(int(x) for x in k.split('-')): v
                for k, v in sweep_data['superset'].items()}
    masks = {w: {tuple(int(x) for x in k.split('-')): v
                 for k, v in m.items()}
             for w, m in sweep_data['masks'].items()}

    ours_wires = {w: alloc_wire_mm2(masks[w], grid) for w in workloads}
    print("Ours mask wire-area per workload:", flush=True)
    for w in workloads:
        n = sum(min(v, N) for v in masks[w].values())
        print(f"  {w:<18}: {ours_wires[w]:>6.1f} mm² ({n} links)",
              flush=True)

    print("\nIso-wire BookSim sweep:", flush=True)
    raw = {m: {} for m in ['mesh', 'kite_s', 'kite_m', 'kite_l', 'ours']}
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
        print(f"\n  workload={w}, wire_budget={wb:.1f} mm²", flush=True)
        for method, alloc in per_method_alloc.items():
            t0 = time.time()
            res = run_one(method, alloc, K, N, R, C, w)
            elapsed = time.time() - t0
            lat = res.get('latency')
            wm = alloc_wire_mm2(alloc, grid)
            n_links = sum(min(v, N) for v in alloc.values())
            raw[method][w] = lat
            wire_used[method][w] = wm
            lat_str = f"{lat:.2f}" if lat is not None else "FAIL"
            print(f"    {method:<8} | wire={wm:>6.1f} | "
                  f"links={n_links:>3} | lat={lat_str:>10} | "
                  f"{elapsed:>5.1f}s", flush=True)

    print("\nMix-avg latency table (iso-wire):", flush=True)
    methods = list(raw.keys())
    header = f"{'mix':<55} | " + " | ".join(f"{m:>9}" for m in methods)
    print(header, flush=True)
    print('-' * len(header), flush=True)
    mix_results = {}
    for k in [2, 3, 4]:
        for combo in itertools.combinations(workloads, k):
            mix_label = '+'.join(combo)
            row = {}
            for m in methods:
                vals = [raw[m].get(w) for w in combo]
                row[m] = (None if any(v is None for v in vals)
                          else sum(vals) / len(vals))
            mix_results[mix_label] = row
            cells = ' | '.join(f"{(v if v is not None else 0):>9.2f}"
                               for v in row.values())
            print(f"{mix_label:<55} | {cells}", flush=True)

    print('-' * len(header), flush=True)
    print('\nWinner per mix (lowest avg latency, iso-wire):', flush=True)
    win_count = {m: 0 for m in methods}
    for mix_label, row in mix_results.items():
        valid = [(m, v) for m, v in row.items() if v is not None]
        if not valid:
            continue
        winner, _ = min(valid, key=lambda x: x[1])
        win_count[winner] += 1
    for m, c in win_count.items():
        print(f"  {m:<10}: {c} / {len(mix_results)} mixes won", flush=True)

    out_path = RESULTS_DIR / 'sweep_v2_iso_wire.json'
    out_path.write_text(json.dumps({
        'K': K, 'N': N, 'workloads': workloads,
        'ours_wires': ours_wires,
        'raw': raw, 'wire_used': wire_used,
        'mix_results': mix_results, 'win_count': win_count,
    }, indent=2))
    print(f"\nSaved: {out_path}", flush=True)


if __name__ == '__main__':
    main()
