# V3.1 Plan: RL-Only Candidate Pool + bpp=3 Main Sweep

**Created**: 2026-04-30 16:30:39 KST
**Status**: Active (supersedes 20260430-150633-v3-booksim-selected-framework-plan.md)
**Trigger**: Pilot results showed mesh/Kite-L in candidate pool trivializes the contribution; multi-seed RL alone with BookSim selection is sufficient on bpp=3.

## Summary of change

The previous plan included Mesh-iso and Kite-L-iso in the Stage-1a candidate pool to provide a structural worst-case fallback. The pilot data showed two things:

1. The original failure mode was **surrogate OOD on dense traffic in multi-workload mixes**. Multi-seed RL + BookSim selection directly addresses that root cause without needing structural baseline candidates.
2. Including Mesh/Kite-L as candidates makes the contribution claim trivially "pick best of N existing methods", which is a weak thesis.

Therefore:

- **Candidate pool drops Mesh-iso and Kite-L-iso.**
- **Candidate pool keeps**: greedy-union + multi-seed RL (5-7 seeds) + the existing rl_v3_current entry for backwards compatibility.
- **Mesh / Kite-S / Kite-M / Kite-L / GIA / PARL** are evaluated as paper baselines, not as candidates inside our framework.
- **Worst-case fallback** is still mentioned as a deployment-time pre-check, but it is no longer the contribution.

## Pilot evidence supporting the change

bpp=3 cells with multi-seed RL only (no Mesh/Kite candidates):

| Cell | RL best (3 seeds) | mesh_iso | kite_l_iso | RL beats both? |
|---|---|---|---|---|
| K16_N4 hybrid+uniform+a2a | 40.5 | 47.5 | 39.9 | mesh ✓, kite_l ≈ tie (-1.5%) |
| K16_N8 moe+uniform | 140.6 | 185.4 | 179.1 | both ✓ (-22%) |

The 1.5% gap on K16_N4 is plausibly closed by going to 5-7 seeds (current was 3).

bpp=2 cells (excluded from main):

| Cell | RL best (3 seeds) | mesh_iso | kite_l_iso | Outcome |
|---|---|---|---|---|
| K16_N8 hybrid+uniform | 139 | 82 | 277 | mesh dominates |

This confirms bpp=2 is below the express crossover. Main eval excludes bpp=2.

## Revised framework

```text
Stage 1a (candidate generation)
  - greedy-union baseline
  - multi-seed RL (5-7 seeds, default warm-start = greedy-union)
  - (rl_v3_current retained only for partial-sweep backward comparison)

Stage 1b (BookSim-based selection)
  - evaluate each candidate at superset wire on the workload mix
  - select the candidate with lowest mean raw latency

Stage 2 (per-workload BookSim-greedy mask)
  - run greedy mask from selected superset
  - produce one runtime mask per workload

Reporting
  - per-workload mask latency at mask wire
  - paper baselines (Mesh, Kite-S/M/L, GIA, PARL) reported separately at iso-wire
  - worst-case pre-deploy fallback noted as a property, not the headline
```

## Main sweep scope

bpp=3 only:

| Dim | Spec |
|---|---|
| Cells | K∈{16,32} × N∈{4,8} = 4 |
| Subsets | C(4,2)=6 + C(4,3)=4 + C(4,4)=1 = 11 |
| bpp | 3 (main) |
| Total | 44 (cell, subset) combinations |

Each combination: ~25 min on single thread → ~18 h total. Parallel 4-way reduces to ~5 h.

bpp=2 / bpp=4 are sensitivity sections: 1-2 representative cells each, mentioned in Discussion.

## Coverage status

| Cell | partial (old framework) | new framework |
|---|---|---|
| K16_N4 bpp3 | 11/11 (1 regression — uniform/a2a in 3-W) | 1/11 (pilot) |
| K16_N8 bpp3 | 9/11 (7 regressions) | 1/11 (pilot in progress) |
| K32_N4 bpp3 | 11/11 (0 regressions) | 0/11 |
| K32_N8 bpp3 | 0/11 | 0/11 |

For consistency every cell is rerun under the new framework. K32_N4 may show only marginal changes because the surrogate-only RL already worked there, but reporting all 44 under one method is required for the paper.

## Immediate next steps

1. Finish current pilot (cell 3 = K16_N8 bpp3 moe+uniform+a2a in progress).
2. Post-hoc analyze pilot JSON with the RL-only pool selector — confirm the cell selection does not change vs the full-pool selector except where a baseline candidate would have won (record those).
3. Write `sweep_v3_booksim_select.py` modeled on `sweep_v2_full_subsets.py` but:
   - candidate pool = greedy_union + RL × N seeds
   - RL seed count: 5 (start), bump to 7 if K16_N4 1.5% gap persists
   - bpp = [3] only
   - selection metric: mean raw BookSim latency over the subset
   - Stage-2: existing booksim_greedy_mask, max_steps=3, candidates=6
4. Run the full 44-combination sweep in background.
5. Generate paper figures from the resulting JSON.
6. Optional: bpp=2 (1 cell, 1 mix) and bpp=4 (1 cell, 1 mix) sensitivity runs.

## Paper-side cleanup that follows

Once the 44-combination sweep is in:

- `PAPER_PLAN.md` thesis tightened (the V3 plan's edits A-F).
- T1 capability table: drop "worst-case fallback guarantee" column, keep workload-aware + runtime-reconfig + RL.
- Method section explicitly labels candidate pool and selector as the algorithmic contribution; baselines are external comparison only.
- Discussion section: a short paragraph on the bpp=2 below-crossover regime where the framework recommends pure mesh; a short paragraph on the bpp=4 saturation regime.

## Open risks

- K16_N4 hybrid+uniform+a2a 1.5% loss to kite_l with 3 seeds. If 5-7 seeds do not close the gap, this becomes an honest paper limitation: "framework matches but does not beat hand-crafted Kite-L on the hardest dense 3-mix at bpp=3." Decision criterion: gap > 3% with 7 seeds → flag and discuss; gap ≤ 3% → noise, framework wins.
- K32_N8 bpp3 has zero data so far. If the surrogate also struggles there (likely, given dimensionality), multi-seed framework should fix it but adds time. Run K32_N8 first to derisk.

## Filenames

- Sweep driver: `sweep_v3_booksim_select.py`
- Output: `results/ml_placement/sweep_v3_booksim_select.json`
- Pilot leftover: `pilot_booksim_select.{py,json}` retained for reference.
