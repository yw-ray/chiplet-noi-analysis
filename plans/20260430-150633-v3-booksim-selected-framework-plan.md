# V3 Plan: BookSim-Selected Candidate Framework

**Created**: 2026-04-30 15:06:33 KST  
**Status**: Active plan  
**Context**: Partial high-NL V3 sweep exposed regressions in some bpp=2 and K16_N8 cells when the Stage-1 superset is selected only by surrogate-guided RL.

## Plan File Convention

All future planning documents should live under `plans/`.

Filename format:

```text
YYYYMMDD-HHMMSS-short-description.md
```

The newest plan is the file with the lexicographically largest timestamp prefix. Existing root-level plans such as `PAPER_PLAN.md` can remain as historical context, but active continuation plans should use this directory.

## Current Decision

The paper should keep the V3 high-NL target regime:

- MoE Skewed Zipf
- Hybrid TP+PP
- Uniform Random
- All-to-All

Low-NL workloads such as Pipeline Parallel and Ring AllReduce are not part of the main evaluation. They can be described as outside the target regime: if a workload has little non-local traffic, express links can be disabled or power-gated and the workload can run on the baseline mesh/short-link fabric.

## Problem Observed

The current V3 pipeline is:

```text
Stage 1:
  surrogate-guided RL -> one superset allocation

Stage 2:
  BookSim-greedy remove-only mask per workload
```

This produced promising results in many cells, but also clear regressions:

- bpp=2 is unstable.
- K16_N8 has multiple bad rows.
- Some Uniform / All-to-All mixes regress because the surrogate appears to mis-rank candidate topologies.

Representative bad rows from the 60/88 partial sweep:

```text
K16_N4 bpp3, Hybrid+Uniform+A2A:
  Ours 153.0, Mesh 47.5, Kite-L 40.6

K16_N8 bpp2, Uniform+A2A:
  Ours 194.6, Mesh 89.1, Kite-L 365.0

K16_N8 bpp2, Hybrid+Uniform:
  Ours 179.3, Mesh 83.2, Kite-L 195.7

K32_N4 bpp2, MoE+Uniform+A2A:
  Ours 288.5, Mesh 165.2, Kite-L 239.3
```

The likely cause is not that BookSim cannot support these workloads. The issue is that the surrogate is currently acting too much like the final decision-maker. In symmetric dense traffic such as Uniform / All-to-All, the MLP surrogate can mispredict routing balance and bottleneck behavior. The remove-only Stage-2 mask cannot repair a fundamentally bad superset.

## Revised Framework

The revised framework should make the surrogate a candidate generator, not the final judge.

```text
1. Generate candidate supersets
   - current RL candidate
   - multiple RL seeds / top-k surrogate candidates
   - greedy-union baseline
   - Mesh
   - Kite-L / regular topology candidates
   - optional random or FBfly-style candidates

2. BookSim-select the Stage-1 superset
   - evaluate candidate supersets with BookSim on the workload mix
   - select the measured-best candidate

3. Stage-2 per-workload mask
   - run BookSim-greedy mask from the selected superset
   - produce one runtime mask per workload

4. Final measured fallback
   - final reported latency should be measured min(mask, Mesh, Kite-L, optional GIA)
```

Paper phrasing:

```text
The surrogate is used only as a proposal mechanism. All reported allocations
are selected and evaluated by BookSim, preventing surrogate prediction error
from silently determining the final topology.
```

## Does This Require Rerunning?

Yes for final paper numbers, because the algorithm definition changes.

But do not rerun the full 88-cell sweep immediately. First run a bad-cell pilot to check whether BookSim-selected candidates recover the regressions.

## Pilot Before Full Rerun

Target the worst current regressions:

```text
1. K16_N8 bpp2 hybrid_tp_pp+uniform_random
2. K16_N4 bpp3 hybrid_tp_pp+uniform_random+all_to_all
3. K32_N4 bpp2 moe+uniform_random+all_to_all
```

For each pilot cell:

```text
Generate 8-16 candidate supersets:
  - current RL output
  - greedy-union
  - mesh
  - Kite-L-like
  - multiple RL seeds / top-k candidates

BookSim evaluate:
  - raw superset average latency over workloads
  - optionally masked latency if raw selection is inconclusive

Select:
  - measured best candidate
  - compare against current Ours, Mesh, Kite-L
```

Success criterion:

```text
BookSim-selected candidates should eliminate or substantially reduce the
large regressions without destroying the strong MoE/high-NL gains.
```

If the pilot succeeds, rerun the full high-NL sweep under the revised framework.

If the pilot fails, narrow the thesis:

```text
Ours is beneficial in bpp3 / moderate-to-high wire regimes and selected
high-skew workloads, but the current joint-RL formulation is not robust enough
for broad dominance.
```

## Budget Strategy

The current partial data suggests:

- bpp=3 is much more stable than bpp=2.
- bpp=2 may be below the practical crossover point where express links help.
- bpp=4 may be useful as a saturated/high-budget comparison, but it can make regular long-link baselines too strong.

Recommended next budget framing:

```text
Main:
  bpp=3 as the realistic/default budget

Sensitivity:
  bpp=2 as low-budget crossover / failure-prone regime
  bpp=4 as high-budget/saturation regime if time allows
```

Do not average bpp=2 and bpp=3 blindly in the main claim.

## Low-NL Policy

Low-NL workloads are not part of the main V3 target regime.

Recommended wording:

```text
This work targets high-nonlocality LLM traffic regimes where express-link
placement is useful: MoE dispatch, Hybrid TP+PP, Uniform Random, and
All-to-All. Low-NL workloads such as Pipeline and Ring are outside the target
regime; they can run with express links disabled or power-gated on the baseline
mesh/short-link fabric.
```

Avoid claiming measured low-NL power savings unless power-gating and active-link energy are explicitly modeled. Safe phrasing:

```text
Unused express links can be deactivated to avoid dynamic link activity, while
the physical wire area and any standby PHY cost remain part of the shared
superset.
```

## Immediate Next Steps

1. Implement a candidate-generation wrapper for the three bad-cell pilots.
2. Include current RL, greedy-union, Mesh, Kite-L, and multiple top-k RL candidates.
3. BookSim-select the Stage-1 candidate before Stage-2 masking.
4. Compare pilot results against the current partial figures.
5. Decide whether to rerun the full 88-cell high-NL sweep.

