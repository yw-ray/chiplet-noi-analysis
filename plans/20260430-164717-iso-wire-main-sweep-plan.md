# V3.2 Plan: Iso-Wire Main Sweep (single W per cell, two-contribution split)

**Created**: 2026-04-30 16:47:17 KST
**Status**: Active (supersedes 20260430-163039-rl-only-bpp3-main-sweep-plan.md)
**Trigger**: User decided to replace bpp budget axis with iso-wire-area W; clarified that Stage-2 mask is runtime power adaptation on already-deployed wire, not wire saving; PARL excluded from comparison; only baselines we already implement (Mesh, Kite-S/M/L, GIA) are reported.

## Two contributions to evaluate

1. **Stage-1: Wire deployment quality.** At a fixed deployed wire W, our BookSim-selected superset reaches lower latency than Mesh / Kite-S / Kite-M / Kite-L / GIA at the same W.
2. **Stage-2: Runtime power efficiency.** On the same deployed W, a per-workload greedy mask deactivates a subset of links so that active-link-count drops while latency stays within tolerance. This is a power knob that PARL and GIA do not have.

These are reported as two different result sections, not collapsed into one.

## Conceptual cleanup of "wire" vs "active"

- **Deployed wire** = the physical interposer wire footprint. Decided once at chip-bringup. All methods compared at the same deployed W.
- **Active links** = subset of deployed wire that is powered on. Per-workload at runtime.
- **Stage-2 mask** changes active links, never deployed wire.
- **`wire_saved_pct` field** in existing JSON is a misnomer; it is actually `active_wire_pct`. Keep the field but rename in any new code/figures to `active_pct` or `power_saving_pct`.

## Iso-wire matrix

| Dim | Spec |
|---|---|
| Cells | K∈{16,32} × N∈{4,8} = 4 |
| W per cell | K=16 → **W = 240 mm²**, K=32 → **W = 520 mm²** (single main; sensitivity W later if time) |
| Subsets | C(4,2)=6 + C(4,3)=4 + C(4,4)=1 = 11 |
| Total combos | 4 × 11 = **44** |

Per combo, evaluate at deployed wire W:

```
Methods (active wire = deployed = W, except Stage-2 mask deactivates):
  - mesh @ W                         (paper baseline)
  - kite_s @ W                       (paper baseline)
  - kite_m @ W                       (paper baseline)
  - kite_l @ W                       (paper baseline)
  - gia @ W                          (paper baseline)
  - ours_stage1 @ W                  (Stage-1 BookSim-selected superset, full active)
  - ours_stage1_plus_mask @ W        (Stage-1 superset + per-workload mask, deactivated)
```

PARL is excluded from the comparison.

## Stage-1 candidate pool

```
greedy_union  (deterministic per-W greedy + union, post-pruned to W)
rl_seed{42, 43, 44, 45, 46}  (5-seed RL warm-started from greedy-union, post-pruned to W)
```

No Mesh / Kite candidates inside the pool. Mesh/Kite/GIA appear only as paper baselines. The selector chooses one of the seven (greedy_union or one RL seed).

## Iso-wire enforcement (Option α — post-prune)

For RL and greedy:

1. Set link-count budget generously: `bpp = ceil(W / (WIRE_AREA[1] * n_adj))`. This gives more links than fit at hop-1 if every link were max-distance, so wire is always the binding constraint.
2. After RL/greedy produces an allocation, run `prune_to_wire(alloc, grid, W)`:
   - Sort links by descending wire cost (hop-3 first, then hop-2, then hop-1).
   - Remove one link at a time until `alloc_wire_mm2(alloc) ≤ W`.
   - Mesh-protect: never remove the last hop-1 link of an adj pair.

For Mesh / Kite-S/M/L: existing `mesh_alloc_iso_wire`, `kite_alloc_iso_wire(..., variant=...)` already greedily fill up to W.

For GIA: existing `gia_alloc(grid, budget, per_pair_cap)` takes a link budget. Wrap with the same generous-budget + post-prune approach.

## Stage-2 mask in the iso-wire framing

- Run `booksim_greedy_mask` from the selected superset.
- Reinterpret the output: `final_mask` = active link subset; `final_wire` = active wire (≤ W); `final_lat` = latency on active subset.
- Reported metrics:
  - `active_pct` = sum(mask) / sum(superset) (NOT wire saving — wire is already deployed)
  - `mask_lat` (per workload)
  - `mask_lat / raw_lat` (overhead vs full active)

## Output schema

Single JSON `results/ml_placement/sweep_v3_isowire.json`:

```json
{
  "<subset_key>": {
    "<cell_key>": {
      "W": 240.0,
      "candidates": {
        "greedy_union": {"alloc": ..., "wire": ..., "raw_per_wl": ..., "raw_mean_lat": ...},
        "rl_seed42": {...},
        ...
      },
      "selected": "rl_seed42",
      "stage1_lat": {"moe": ..., "uniform_random": ...},
      "stage2": {
        "moe": {
          "raw_lat": ..., "mask_lat": ..., "active_pct": ..., "active_link_count": ...,
          "history": [...], "final_mask": {...}
        },
        ...
      },
      "baselines_at_W": {
        "mesh":   {"alloc": ..., "lat": {"moe": ..., ...}},
        "kite_s": {...},
        "kite_m": {...},
        "kite_l": {...},
        "gia":    {...}
      }
    }
  }
}
```

## Time budget

Per combo:
- Stage-1a generation (5 RL seeds + greedy_union): ~3-5 min
- Stage-1b BookSim raw eval (6 candidates × |W| BookSim runs per workload): ~5-15 min depending on subset size
- Stage-2 mask (3 steps × 6 candidates × |W| workloads): ~5-15 min
- Baselines @W (5 baselines × |W| workloads): ~5-10 min

Total per combo ~25-45 min. 44 combos × 35 min = ~26 h single-thread. 4-way parallel reduces to ~7 h. K32_N8 first.

## Filenames

- Sweep driver: `sweep_v3_isowire.py`
- Output: `results/ml_placement/sweep_v3_isowire.json`
- Helper: `prune_to_wire` and `gia_iso_wire` added to `sweep_v3_isowire.py` (or to `baselines.py`).

## Immediate next steps

1. Let current pilot finish (cell 3 in progress). Diagnostic, not main result.
2. Implement `prune_to_wire` helper.
3. Implement `gia_iso_wire(grid, W, N)` (wrapper around `gia_alloc` + post-prune).
4. Write `sweep_v3_isowire.py`.
5. Commit and push the plan + script.
6. Launch full 44-combo iso-wire sweep in background.

## Paper-side cleanup that follows

- T1: drop "worst-case fallback guarantee" column.
- T2 main result: "Latency at iso-wire W" — 4 cells × 11 subsets × {ours, mesh, kite-s, kite-m, kite-l, gia} = 264 latency values per workload, summarized.
- T3 power result: "Active link % preserved by mask" — same 4 cells × 11 subsets.
- F3 main figure: per-cell latency-at-W bar chart (subset on x-axis, methods as colors).
- F4 power figure: active link % distribution from Stage-2 mask.
- Discussion: low-NL workloads outside target regime (one paragraph). bpp/wire crossover behavior in sensitivity W if added.

## Open risks

- K16_N4 hybrid+uniform+a2a 1.5% gap to kite_l with 3 RL seeds. Going to 5 seeds plus iso-wire framing should close it; if it does not, flag as honest limitation in Discussion.
- W choices (240 / 520) are seeded from typical bpp=3 RL output wire. If reviewers ask "why this W", justify by physical CoWoS budget plus a sensitivity W.
- GIA iso-wire wrapper needs validation that the post-prune does not break the Fat-Tree spine structure that defines GIA. If it does, document the deviation honestly.
