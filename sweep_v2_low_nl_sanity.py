"""Low-NL sanity sweep for the V3 multi-workload thesis.

This is intentionally small: W={pipeline_parallel, ring_allreduce},
cells {K16_N4, K32_N4}, bpp {2,3}.  It evaluates the current V3
pipeline:

  Stage 1: joint RL superset over the low-NL workload set
  Stage 2: BookSim-greedy per-workload mask
  Baselines: Mesh and Kite-L at the same mask wire target

Output is resumable and saved to:
  results/ml_placement/sweep_v2_low_nl_sanity.json
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from noi_topology_synthesis import ChipletGrid
from ml_express_warmstart import RESULTS_DIR, load_rate_aware_surrogate
from run_rl_multi_workload import train_warmstart_rl_multi
from sweep_v2_iso_wire import alloc_wire_mm2, mesh_alloc_iso_wire, kite_alloc_iso_wire
from sweep_v2_mask_greedy import booksim_greedy_mask, run_booksim_alloc


WORKLOAD_SET = ["pipeline_parallel", "ring_allreduce"]
CELLS = [
    (16, 4, 4, 4),
    (32, 4, 4, 8),
]
BPP_POINTS = [2, 3]

RL_EPISODES = 200
MAX_STEPS = 3
N_CANDIDATES = 6


def run_one_combo(results, surrogate, K, N, R, C, bpp):
    cell_key = f"K{K}_N{N}"
    bpp_key = f"bpp{bpp}"
    results.setdefault(cell_key, {})
    if bpp_key in results[cell_key] and results[cell_key][bpp_key].get("workloads"):
        print(f"[skip] {cell_key} {bpp_key}", flush=True)
        return

    t0 = time.time()
    print(f"\n=== low-NL sanity | {cell_key} | {bpp_key} ===", flush=True)

    rl_result = train_warmstart_rl_multi(
        surrogate,
        WORKLOAD_SET,
        K,
        N,
        R,
        C,
        bpp,
        n_episodes=RL_EPISODES,
        rate_mult=4.0,
        reward_type="normalized_avg",
        max_dist=3,
        verbose=False,
    )

    grid = ChipletGrid(R, C)
    superset = rl_result["superset_alloc"]
    super_wire = alloc_wire_mm2(superset, grid)
    print(
        f"  Stage 1 superset: {len(superset)} pairs, "
        f"{sum(superset.values())} links, {super_wire:.1f} mm^2",
        flush=True,
    )

    workloads = {}
    for w in WORKLOAD_SET:
        label = f"low_nl_{cell_key}_{bpp_key}_{w}"
        tw = time.time()
        final_mask, history, raw_lat = booksim_greedy_mask(
            superset,
            K,
            N,
            R,
            C,
            w,
            max_steps=MAX_STEPS,
            max_candidates=N_CANDIDATES,
            label_prefix=label,
        )
        mask_lat = history[-1]["lat"] if history else None
        mask_wire = history[-1]["wire"] if history else None

        if mask_wire is not None:
            mesh_alloc = mesh_alloc_iso_wire(grid, mask_wire, N)
            kite_l_alloc = kite_alloc_iso_wire(grid, mask_wire, N, "large")
            mesh_res = run_booksim_alloc(
                f"{label}_mesh", mesh_alloc, K, N, R, C, w
            )
            kite_res = run_booksim_alloc(
                f"{label}_kite_l", kite_l_alloc, K, N, R, C, w
            )
            mesh_lat = mesh_res.get("latency")
            kite_l_lat = kite_res.get("latency")
        else:
            mesh_lat = None
            kite_l_lat = None

        workloads[w] = {
            "raw_lat": raw_lat,
            "mask_lat": mask_lat,
            "mask_wire": mask_wire,
            "mesh_lat": mesh_lat,
            "kite_l_lat": kite_l_lat,
            "history": history,
            "final_mask": {f"{p[0]}-{p[1]}": v for p, v in final_mask.items()},
        }

        def fmt(x):
            return f"{x:.2f}" if x is not None else "FAIL"

        print(
            f"    {w:<18} raw={fmt(raw_lat):>8} mask={fmt(mask_lat):>8} "
            f"mesh={fmt(mesh_lat):>8} kite_l={fmt(kite_l_lat):>8} "
            f"({time.time() - tw:.1f}s)",
            flush=True,
        )

    results[cell_key][bpp_key] = {
        "workload_set": WORKLOAD_SET,
        "super_wire": super_wire,
        "superset": {f"{p[0]}-{p[1]}": v for p, v in superset.items()},
        "workloads": workloads,
    }
    print(f"  combo done in {(time.time() - t0) / 60:.1f} min", flush=True)


def main():
    out_path = RESULTS_DIR / "sweep_v2_low_nl_sanity.json"
    if out_path.exists():
        try:
            results = json.loads(out_path.read_text())
            print(f"Resuming from {out_path}", flush=True)
        except Exception:
            results = {}
    else:
        results = {}

    surrogate = load_rate_aware_surrogate()
    overall = time.time()
    for K, N, R, C in CELLS:
        for bpp in BPP_POINTS:
            run_one_combo(results, surrogate, K, N, R, C, bpp)
            out_path.write_text(json.dumps(results, indent=2))
            print(f"  saved partial: {out_path}", flush=True)

    print(f"\n=== DONE in {(time.time() - overall) / 60:.1f} min ===", flush=True)
    print(f"Saved: {out_path}", flush=True)


if __name__ == "__main__":
    main()
