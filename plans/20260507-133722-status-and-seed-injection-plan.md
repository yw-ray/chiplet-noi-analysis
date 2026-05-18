# V3.5 Status Summary + Seed Injection Plan

**Created**: 2026-05-07 13:37:22 KST
**Status**: Active — supersedes 20260506-100933 (surrogate retraining), 20260504-151807 (MCTS-only narrowed thesis)
**Trigger**: Surrogate retraining (V3) failed to deliver consistent improvements (mixed: V3 better in 9/27 cells, RA better in 18/27). Dense-only mixes on K=32 still lose to Kite-L by +5–16%. User wants to also win on dense-only mixes. New direction: Seed Injection (warm-start RL/MCTS from baseline allocations) plus Intersection Backbone (replace `union(per-W greedy)` with `intersection` as fixed structure + RL fills the rest). Pairwise ranking loss for surrogate retraining is also planned.

## Status Summary — what we have done so far

### 1. Problem definition (unchanged)

Joint multi-workload chiplet NoI superset selection. Cells K∈{16,32} × N∈{4,8} =
4 cells. Workloads: MoE (Zipf), Hybrid TP+PP, Uniform Random, All-to-All.
Subsets: C(4,2)+C(4,3)+C(4,4) = 11 mixes. Baselines: Mesh, Kite-S/M/L, GIA at
iso-wire (Kite/GIA approximations from `baselines.py`, `baseline_gia.py`).
PARL excluded (no code).

Wire budgets per cell: K=16/N=4 W=240, K=16/N=8 W=960, K=32/N=4 W=520,
K=32/N=8 W=2080 (per-pair traffic ∝ N², so W ∝ N²).

### 2. Framework (current, V3.4 with MCTS)

```text
Stage 1a  candidate generation
   - greedy_union (1 candidate)
   - REINFORCE × 5 seeds (RL)
   - MCTS × 3 seeds (UCB tree search)
   each post-pruned to wire ≤ W

Stage 1b  BookSim-based selection on candidate raw mean lat over subset

Stage 2   per-workload BookSim-greedy mask
            lat_tolerance=1.0 + revert-to-raw guard (mask never increases lat)

Compare to Mesh, Kite-S/M/L, GIA at the same wire W.
```

### 3. Sweeps completed

#### Main sweep — RA surrogate (V3.3)

| Cell | Combos done | Notes |
|---|---|---|
| K16_N4 | 11/11 ✓ | clean win on moe-mixes |
| K16_N8 | 11/11 ✓ | mostly tied with kite_l |
| K32_N4 | 11/11 ✓ | win on moe-mixes, +5–16% loss on dense-only |
| K32_N8 | 4/11 (killed; too slow at 21 h/combo) | partial only |

#### Wire scaling — RA surrogate

| Cell | Ws done | Notes |
|---|---|---|
| K16_N4 | 6/6 ✓ | ours monotonically improves; baselines plateau |
| K16_N8 | 6/6 ✓ | ours wins at W ≥ 960 |
| K32_N4 | 6/6 ✓ | ours wins at W ≥ 520 |
| K32_N8 | 4/6 (killed) | partial |

#### Main sweep — V3 surrogate (V3.4 retraining attempt)

V3 surrogate trained on 3152 pairs from existing sweeps (val MAPE 17%, vs RA
37%). Result: V3 surrogate accuracy improved but RL/MCTS guidance got
**worse** in 18/27 cells (RA produced lower-latency selected superset).

Diagnosis: V3 trained on RA-driven sweep distribution → biased. V3-driven
RL/MCTS produces out-of-distribution alloc patterns, where V3 mispredicts.
Better surrogate accuracy ≠ better RL outcome under distribution mismatch.

| Cell | Combos done |
|---|---|
| K16_N4 v3surr | 11/11 ✓ |
| K16_N8 v3surr | 10/11 (killed at this transition) |
| K32_N4 v3surr | 6/11 (killed) |
| K32_N8 v3surr | 1/11 (killed) |

V3 retraining is now considered **future work** — current V3 weights
(`surrogate_v3.pt`) preserved for the ablation column; not used as
the framework's default surrogate going forward.

### 4. Current results — `ours / kite_l` per (cell, size) — RA surrogate, completed cells

| Cell | size 2 | size 3 | size 4 |
|---|---|---|---|
| K16_N4 | 0.91 ✓ | 1.01 ≈ | 0.90 ✓ |
| K16_N8 | 1.01 ≈ | 1.04 ≈ | 1.02 ≈ |
| K32_N4 | 1.04 ≈ | 1.08 ✗ | 1.30 ✗ |

(<1.0 = ours win, ≈1.0 = tie, >1.0 = ours loss; per-workload normalized)

Headline numbers per category:

- **MoE-included mixes**: ours wins by 19 % – 76 % vs Kite-L. Headline result.
- **K=16 dense mixes**: tied within 5 %.
- **K=32 dense-only mixes (no moe)**: ours loses by 5–16 % (worst at K32_N4
  uni+a2a +16 %, K32_N4 4-mix ALL +30 %).

Selector breakdown so far (~38 combos): RL ≈ 73 %, MCTS ≈ 14 %, greedy ≈ 11 %.
MCTS effective on K16_N4 moe-related cells (e.g. moe+uni went 109 → 68 with
MCTS, −38 % MCTS contribution).

### 5. Why dense-only K=32 mixes still lose

Diagnosed. Example K32_N4 uni+a2a:

- Best RL candidate (rl_seed45) raw 54.6, BookSim
- kite_l baseline raw 45.7
- Mask reduces 54.3 → 52.9 (small saving, working as intended).

Root cause: kite_l deploys a uniform hop-3 spine (24 adj + 96 hop-3 = 120 links
at wire 519), the **mathematical optimum for symmetric uniform/all-to-all
traffic**. RL/MCTS without explicit structural prior cannot find this exact
spine — uniform traffic offers no traffic-weighted gradient to bias selection.

The framework as designed (no baseline-derived candidates) **cannot beat
kite_l on dense-symmetric workloads** without additional algorithmic input.

## New plan — Seed Injection + Intersection Backbone

### Approach 1: Seed Injection (immediate fix)

**Idea**: Use Mesh / Kite-L / GIA allocations as RL/MCTS warm-starts. The
final candidate is the RL/MCTS *output* (after swaps), not the baseline alloc
itself. Reframes earlier user "no kite_l in pool" into "no kite_l as direct
candidate"; warm-start is different.

Why this differs from "kite_l as candidate":

- Direct candidate = the candidate is exactly the baseline alloc.
- Warm-start = RL/MCTS starts at baseline alloc and applies swaps; the
  resulting alloc is RL/MCTS-derived.

If RL cannot improve the baseline (already optimal), the output stays close to
or identical to the baseline, providing a performance floor. If RL can find a
"super-kite" (regular spine + workload-specific shortcuts), the output beats
the baseline.

**Implementation**:

1. Add `WARM_START_VARIANTS` in `sweep_v3_isowire.py`:
   - `greedy` (current default)
   - `kite_l_iso` (sized to W)
   - `mesh_iso` (sized to W)
   - `gia_iso` (sized to W)
2. Each RL/MCTS seed picks one warm-start variant. Total ~9 seeds: 3 greedy +
   2 kite_l + 2 mesh + 2 gia. Or weight more seeds toward warm-starts that
   match the workload mix (e.g., more kite_l for uniform/a2a-heavy mixes).
3. Greedy_union remains as a deterministic candidate.

Expected outcome on dense-only K=32:

- Today: ours 54 vs kite_l 46 (+18 %).
- With seed injection: at least ours = 46 (RL keeps kite_l warm-start). Likely
  ours ≤ 46 (RL adds workload-specific shortcuts on top).

Risk: if RL drifts away from a good warm-start (we saw this in cell-3 retry
round 1/2), output could be worse than warm-start. Mitigate with the
`mask_reverted_to_raw` style guard: at the end of training, BookSim-verify
the RL output and revert to the warm-start if RL output is worse.

**Effort**: ~2-3 hours of code changes. Drop-in to `gen_candidates`.

### Approach 2: Intersection Backbone

**Idea**: Replace `warm_start_union_greedy(...)` (current = union of
per-workload greedies) with `warm_start_intersection_backbone(...)`:

```text
backbone   = intersection over workloads of per-W greedy
                = links that ALL workloads agree benefit them
remaining  = W - alloc_wire(backbone)
RL fills remaining with workload-mix-specific links
```

The backbone is forced to be present in every candidate; RL only chooses what
to add on top. For dense-only mixes the intersection shrinks to a uniform
spine-like structure (because every dense workload prefers similar uniform
distribution); for moe-included mixes the intersection narrows (less shared)
and RL has more remaining wire to add moe-specific shortcuts.

**Implementation**:

- New helper `warm_start_intersection_backbone` in
  `run_rl_multi_workload.py`.
- Modify `train_warmstart_rl_multi` to accept a `frozen_backbone_mask` so RL
  swaps cannot remove backbone links.
- Same for MCTS in `mcts_search.py` (`enumerate_swap_actions` skip backbone
  pairs from the removable set).

**Effort**: ~half a day of code changes plus testing.

Expected outcome:

- Dense-only mixes get a backbone close to "what kite-S/M/L all roughly agree
  on" — a regular structure. RL only fine-tunes.
- MoE mixes have a smaller backbone, RL has more freedom to add hubs.
- This is a clean algorithmic novelty for the paper: not just adapting the
  candidate pool but reformulating the search problem.

### Approach 3: Pairwise ranking surrogate (V3.1) — deferred, not blocking

`collect_surrogate_data_v2` produced ~11k entries with random spine and random
uniform allocs across all 4 cells. This dataset is qualitatively richer than
the V3 training set and was meant to feed V3.1 training.

We will not block on V3.1 for the paper. After Seed Injection + Intersection
Backbone runs, if there is still slack we revisit pairwise loss training.

### Approach 4: Hierarchical search — future work, not in this paper

Cluster-aware search (chiplets grouped, intra-cluster vs. inter-cluster
optimization) is a strong K-scaling story but a separate paper.

## Concrete experiments to run after the changes

1. Implement Approach 1 (Seed Injection) — drop into `sweep_v3_isowire.py`
   and `mcts_search.py`.
2. Implement Approach 2 (Intersection Backbone) —
   `run_rl_multi_workload.py`, `mcts_search.py`.
3. Pilot on K16_N4 (fastest cell, already finished twice; serves as control).
   Compare to RA-surrogate baseline already in
   `sweep_v3_isowire_K16_N4.json`. Decision: if no regression on moe-mixes
   AND ≥ 95 % match with kite_l on dense-only mixes, proceed.
4. Full sweep on 4 cells × 11 subsets × 1 W (44 combos), parallel-4. K=32
   cells expected ~3-7 days each at single-thread; with 4-way parallel,
   wall-clock ~1 week.
5. Wire scaling if time allows: 4 cells × 6 W. ~1 week more wall-clock.

## Output paths

To preserve the V3.4 (RA surrogate, no seed injection) baseline:

- Main sweep: `results/ml_placement/sweep_v3_isowire_seedinject_K{K}_N{N}.json`
- Wire scaling: `results/ml_placement/sweep_v3_wire_scaling_seedinject_K{K}_N{N}.json`

The V3.4 baseline is the existing `sweep_v3_isowire_K{K}_N{N}.json` (without
the `_v3surr` suffix). The V3 surrogate run is preserved under `_v3surr.json`
for the ablation column on surrogate variants.

## Risk register

- Seed injection causes RL to drift away from a near-optimal warm-start (seen
  in earlier retries). Mitigate with revert-on-regression guard at end of
  training: if RL final < warm-start, revert.
- Intersection backbone is empty when workloads are highly heterogeneous (no
  shared link). Mitigate with a minimum backbone size constraint (e.g.,
  always include all adj as backbone; intersection then expands what is
  added beyond mesh-protect).
- Combining seed injection and intersection backbone could conflict (the
  backbone may already overlap with the warm-start). Mitigate by treating
  them as orthogonal: backbone is a structural constraint, warm-start is the
  initial alloc inside that constraint.
- Compute time. K=32_N8 is the slowest cell at ~21 h/combo; with seed
  injection adding extra warm-start seeds, candidate count may grow. Tune
  seed count to keep wall-clock manageable.

## Decision criteria for proceeding

After the K16_N4 pilot:

- ours mean over 11 subsets ≤ best baseline mean on at least 9/11 mixes
  (no large dense-only loss > 5 %).
- moe-included mixes still show ≥ 20 % win vs kite_l.

If these hold, proceed to full sweep on the other 3 cells. If not, revisit
intersection backbone parameters or seed-injection seed count before scaling
up.
