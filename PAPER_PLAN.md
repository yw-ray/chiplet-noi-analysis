# Paper Plan V2: Multi-Workload Joint RL for Reconfigurable Chiplet NoI

**Last updated**: 2026-04-30
**Supersedes**: PAPER_PLAN_V1.md (single-workload NL%-guided thesis)
**Status**: V3 sweep in progress (BookSim-greedy mask + PARL/GIA baselines)

---

## Title

> **"Joint Multi-Workload Reinforcement Learning for Reconfigurable Chiplet NoI in LLM Systems"**

### Design rationale
- "Joint Multi-Workload" — RL takes workload SET as input (key novelty vs PARL)
- "Reinforcement Learning" — algorithmic core
- "Reconfigurable Chiplet NoI" — runtime reconfig is the contribution gap (vs GIA assembly-time)
- "LLM Systems" — target domain (workload-relevant)

---

## Target Venue

DAC / DATE 2026 (architecture track)

---

## Thesis

A single chiplet NoI hardware can serve diverse LLM workloads near-optimally **if and only if** (i) the link superset is **jointly trained** over the workload set, and (ii) **per-workload subset masks** are activated at runtime. Static topologies (Mesh, Kite, GIA) and single-output RL synthesis (PARL) are dominated under iso-wire-mm² across all (K, N) × workload mix combinations.

---

## Three Contributions

### C1. Joint Multi-Workload RL Formulation
- **Input**: workload set W = {w_1, ..., w_n} + (K, N)
- **State**: concat traffic matrices for all workloads in W
- **Action**: swap-based on superset allocation (remove_idx, add_idx)
- **Reward**: avg latency over W (main metric) + worst-case (sensitivity)
- **Unique vs PARL**: PARL is single mixed-workload one-shot synthesis; we treat workload set as first-class structured input

### C2. Superset + Per-Workload Mask Two-Stage Architecture
- **Stage 1** (design-time, expensive): RL learns superset jointly over W
- **Stage 2** (runtime, cheap): greedy mask postproc selects subset per workload
- **Unique vs GIA**: GIA's "configurable" is assembly-time (set once at integration); ours is runtime (changes with running workload)

### C3. Combinatorial Workload Mix Evaluation
- 4 high-NL LLM workloads × C(4,k) for k∈{2,3,4} = 11 mixes
- 4 cells × 11 mixes × 7 methods = 308 BookSim runs
- Iso-wire-mm² Pareto comparison
- Tests robustness across mix-size scaling (more workloads → harder problem)

---

## V3 Update — Current Plan (2026-04-30)

### Methodology improvements
1. **Stage 2 mask = BookSim-greedy** (not surrogate). The earlier
   surrogate-driven RL mask was OOD on uniform/a2a placements; replacing
   with direct BookSim greedy mask (max_steps=3, candidates=6) yields
   strict latency improvements over raw superset for many workloads
   while saving 5-20% wire.
2. **Kite-M interleave fix**. baselines.py kite_alloc(`medium`) now
   interleaves dist=2 and dist=3 round-robin so Kite-M is a true mixed
   family (was identical to Kite-S before).
3. **Subset sweep**: input workload set is treated as a first-class
   parameter — 2-W (6) + 3-W (4) + 4-W (1) = 11 subsets, demonstrating
   that superset/mask both vary with input set.

### V3 baselines (5-way, **PARL excluded**)
- **Mesh** (sanity floor)
- **Kite-S, Kite-M, Kite-L** (DAC 2020) — `baselines.py` (kite_m interleave fixed)
- **GIA** (ICCAD 2022) — Fat-Tree subnet heuristic in `baseline_gia.py`
- **Ours** — joint multi-W RL superset + BookSim-greedy mask

### Why PARL excluded
- arXiv 2510.24113, code unreleased
- Maskable PPO complex; reproduction details (hyperparams, reward shaping,
  state encoding) not fully specified → re-implementation accuracy uncertain
- Algorithm targeted at single output topology; multi-W extension requires
  inputs (mixed traffic) the paper does not detail
- Decision: position PARL as future work in the paper, not direct comparison.
  Honest disclosure: "PARL is the closest RL competitor; we leave direct
  reproduction to future work due to unavailable code."

### Sweep status
- `sweep_v2_full_subsets.json`: in progress (mesh + kite_l + ours)
  - Done: K=16 N=4 (22), K=32 N=4 (22) = 44/88
  - Remaining: K=16 N=8 (12), K=32 N=8 (22)
  - K=32 N=4 4-W bpp=3: ours 49 vs mesh 120 vs kite_l 173 (60-72% better)
- `sweep_v2_kite_sm.py`: re-measure Kite-S/M (now distinct allocs)
- PARL/GIA sweep: pending (heuristic ready, full PPO trainer is followup)

### Eval matrix (target)
| Dim | Spec |
|---|---|
| Methods | mesh, kite_s, kite_m, kite_l, GIA, **ours = 6** (PARL excluded) |
| Subsets | 2-W (6) + 3-W (4) + 4-W (1) = **11** (single excluded) |
| Cells | K∈{16,32} × N∈{4,8} = **4** |
| Bpps | **2, 3** (realistic chiplet wire-area) |
| Total | 11 × 4 × 2 = 88 (subset, cell, bpp); 6 methods each |

### Hyperparameters (locked)
| Parameter | Value | Reason |
|---|---|---|
| Stage 1 RL episodes | 200 | sufficient for swap-RL convergence |
| Stage 2 BookSim-greedy `max_steps` | **3** | wire saving 5-10%, 4-5 step is marginal |
| Stage 2 candidates per step | **6** | ~50% time saved vs 10 |
| Stage 1 reward | `normalized_avg` | per-W best-ratio (scale-invariant across W) |
| Surrogate rate_mult | 4.0 | high-load regime |
| Mask budget (initial) | 70% of superset | balance latency / wire saving |
| Latency tolerance for mask | 1.02× raw | avoid catastrophic mask |
| Mesh-protect | adj×1 forced | prevent isolated chiplets |

### Why these design choices
1. **2-W/3-W/4-W (no single)**: single-workload is V1 thesis. Multi-W set as
   input is V2's contribution; framework value emerges from set diversity.
2. **bpp=2, 3 only**: realistic chiplet wire regime. bpp=1 mesh-only floor,
   bpp=4 saturated regime where Kite-L dominates by "lay every long-link"
   (impractical wire cost).
3. **K=16/32 × N=4/8**: standard chiplet-NoI benchmark grid. K=32 N=4 is the
   sweet spot where multi-W RL value emerges (medium grid, medium wire).
4. **BookSim-greedy mask (not surrogate RL)**: surrogate is OOD on
   uniform/a2a placements (50-70% err); RL trained against surrogate finds
   bad masks. Direct BookSim feedback bypasses surrogate.
5. **PARL excluded**: code unavailable, reproduction uncertain. GIA simpler
   to approximate (Fat-Tree subnet structural).
6. **Cell ordering K=16 N=4 → K=32 N=4 → K=16 N=8 → K=32 N=8 (last)**: K=32
   N=8 is slowest (~60min/combo). Run last so partial results give earlier
   cells fully if time runs out.

### Plan figures
- F-mainBars: 12-panel grouped bar (4 cells × 3 mix sizes), x = wire-area,
  y = ours mask latency, bars colored by workload (`plot_v2_subsets.py`)
- F-pareto: latency vs wire-mm² Pareto curve per cell
  (`plot_v2_wire_pareto.py`)
- F-tableComparison: 2-W subset latency table (mesh / kite_l / ours)

---

## Comparison Matrix (5-way, 7-method count)

| Method | Topology | Workload-aware | Runtime reconfig | RL | Source |
|---|---|---|---|---|---|
| Mesh | regular | ✗ | ✗ | ✗ | trivial baseline |
| Kite-S | hand-crafted | ✗ | ✗ | ✗ | DAC 2020 (short link) |
| Kite-M | hand-crafted | ✗ | ✗ | ✗ | DAC 2020 (medium link) |
| Kite-L | hand-crafted | ✗ | ✗ | ✗ | DAC 2020 (long link) |
| GIA | configurable subnet | ✓ (assembly) | partial (assembly) | ✗ | ICCAD 2022 |
| PARL | RL-synthesized | ✓ (mixed) | ✗ | ✓ | arXiv 2510.24113 |
| **Ours** | **superset + mask** | **✓ (set-aware)** | **✓ (runtime)** | **✓** | this work |

---

## Evaluation Setup

| Dim | Spec |
|---|---|
| Workloads | MoE-Skewed-Zipf, Hybrid TP+PP, Uniform, AllToAll |
| Mixes | C(4,2)=6 + C(4,3)=4 + C(4,4)=1 = 11 |
| Cells | K∈{16,32} × N∈{4,8} = 4 |
| Methods | Mesh, Kite-S/M/L, GIA, PARL, Ours = 7 |
| Wire budget | iso-mm² across methods (same wire envelope per cell) |
| Metrics | avg latency over W (main), max latency over W (sensitivity) |
| Total | 4 × 11 × 7 = 308 BookSim runs (+ surrogate-driven sweep) |

---

## Tables (V2)

### T1: Capability Comparison (5-way)
Workload-aware × Runtime reconfig × RL columns. Shows that only Ours has all three.

### T2: Combinatorial Mix Main Result
Per K-N cell, avg latency for each mix size {2,3,4} × 7 methods. 4 sub-tables (one per cell).

### T3: Worst-Case Sensitivity
Same shape as T2 but max latency. Shows Ours is robust on worst workload too.

### T4: Ablation
- Joint RL vs per-workload-independent + post-hoc union (validates joint training necessity)
- Greedy mask vs RL-learned mask (justifies cheap postproc)
- Wire budget sweep at fixed (K, N, W)

### T5: Wall-clock + Inference Cost
- Joint RL training time (one-time, design-time)
- Mask selection latency at runtime (microseconds — argues amortizable)

---

## Figures

### F1: Motivation
- (a) Single static topology fails on diverse LLM workloads (Mesh ceiling, K=32)
- (b) Per-workload optimal placement differs (heatmap of best-link per workload)
- (c) Runtime reconfig closes the gap (preview of result)

### F2: Framework Architecture
- Stage 1: workload set → joint RL → superset
- Stage 2: superset + workload → mask selection → activate

### F3: Combinatorial Mix Pareto (★ MAIN RESULT)
- 4 panels (K-N cells), each with avg-latency vs wire-mm²
- 7 method curves per panel
- Mix size = 4 (highlight); 2, 3 in supplementary

### F4: Per-Workload Mask Visualization
- Show same superset → different masks for different workloads
- Heatmap: link activation per workload (qualitative interpretability)

---

## Implementation Plan (10 days)

| Day | Task | Output |
|---|---|---|
| **D1 (today)** | PAPER_PLAN.md V2 + train_warmstart_rl_multi() skeleton | design doc + code stub |
| D2 | Pilot: K=16 N=4 W={MoE, Hybrid} 2-mix convergence test | RL converges |
| D3 | Greedy mask postproc + reward stability | mask works |
| D4-5 | Mesh, Kite (S/M/L), GIA implementation | 5 baselines ready |
| D6-7 | PARL reproduction (Maskable PPO from arXiv 2510.24113) | PARL ready |
| D8 | Full sweep 308 runs (surrogate + BookSim verify) | results.json |
| D9 | Pareto figures + BookSim spot-check | figures |
| D10 | main.tex full revision | draft |

---

## Code Architecture

### NEW file: `run_rl_multi_workload.py`
```python
def train_warmstart_rl_multi(
    surrogate_ra,
    workload_set: list[str],          # NEW: workload SET as input
    K, N, R, C,
    budget_per_pair,
    max_lpp,
    warm_start_alloc,                  # union of per-workload greedy as init
    num_episodes=300,
    reward_type='avg',                 # 'avg' | 'worst'
    max_dist=3,
):
    """
    Joint multi-workload RL:
      state  = concat(traffic_flat(w) for w in W)
      action = swap (remove_idx, add_idx) on superset
      reward = -aggregate(L_surrogate(superset, w) for w in W)
    """
    return best_superset_alloc

def greedy_mask_per_workload(
    superset_alloc, traffic_w, mask_budget
) -> mask_alloc:
    """Cheap greedy: rank superset links by traffic*hop benefit, pick top-k."""
    ...
```

### MODIFIED: `ml_express_warmstart.py`
- Reuse `RateAwareSurrogate`, `surrogate_predict_ra`, `SwapPolicy`
- Add `concat_traffic(workload_set, K, N)` helper
- Add `aggregate_reward(latencies, mode)` for avg/worst

### NEW baseline files
- `baseline_kite.py` — Kite-S/M/L topologies (DAC 2020 spec)
- `baseline_gia.py` — Fat-Tree subnet + configurable router (ICCAD 2022)
- `baseline_parl.py` — Maskable PPO reproduction (arXiv 2510.24113)
- `baseline_mesh.py` — trivial mesh (just K×K grid, no express)

### MODIFIED: `paper/main.tex`
Full rewrite — title, abstract, intro, related, §V architecture, §VI evaluation.

---

## Files to Update

- `paper/main.tex` — full rewrite (title, abstract, all sections)
- `PAPER_PLAN_V1.md` — archived (reference for old thesis)
- `CLAUDE.md` (project root) — update Thesis section to V2

---

## Open Questions / Decisions Needed

1. ✅ **Workload mix latency aggregation**: avg main + worst-case sensitivity
2. ✅ **Mask switching cost**: amortized away (long workload runs)
3. ✅ **Iso-wire-mm² normalization**: same wire budget per cell across methods
4. ⚠️ **PARL reward function**: their interference score vs our latency
   - **Recommendation**: re-train PARL with avg latency reward (apples-to-apples)
   - Backup: report both their reward and our reward
5. ⚠️ **Kite (S/M/L)** for K∈{16, 32}: original DAC 2020 paper used K=16 (4×4 chiplets), need to extend topology to K=32 (some hand-mapping required)

---

## Risk Register

| Risk | Mitigation |
|---|---|
| RL doesn't converge in joint multi-workload setting | Pilot D2 first; if no convergence in 3 attempts, fall back to per-workload + meta-RL union |
| PARL reproduction fidelity unclear | Use exact PPO hyperparams from arXiv; verify on their reported benchmarks first |
| 308 BookSim runs too slow | Use surrogate for sweep, BookSim for top-k verify only |
| iso-wire-mm² unfair (Kite has long wires costing more) | Show both: iso-mm² AND iso-link-count tables |
| GIA implementation underspecified | Use authors' reference design (Fat-Tree subnet, SMART router) |

---

## V1 vs V2 Diff Summary

| Aspect | V1 | V2 |
|---|---|---|
| Thesis | NL% predicts express link benefit; warm-start RL refines | Single hardware serves diverse workloads via joint RL superset + runtime mask |
| RL input | single workload | workload set |
| RL output | single placement | superset + per-workload masks |
| Baseline focus | Adj Uniform, Greedy, GNN | Mesh, Kite, GIA, PARL |
| Key novelty | warm-start + post-hoc fallback | joint multi-workload RL + runtime reconfig |
| Eval scope | 4 workloads, 40 configs | 4 workloads × 11 mixes, 4 cells, 7 methods |
| Reusable from V1 | RateAwareSurrogate, BookSim setup, gen_traffic_matrix, NL% characterization | most infrastructure intact |

---

## Notes

- V1 plan (NL%-guided warm-start) archived in PAPER_PLAN_V1.md for reference
- Some V1 infrastructure carries over: rate-aware surrogate, gen_traffic_matrix, BookSim runner, anynet config writer
- `main.tex` needs full rewrite — old structure (§3 Phantom Load + §4 NL% + §5 Express) becomes (§3 Workload Heterogeneity + §4 Joint RL Framework + §5 Two-Stage Architecture)
- NL% characterization (V1 §4) becomes a *motivation prelim* (Why mix matters), not a contribution
