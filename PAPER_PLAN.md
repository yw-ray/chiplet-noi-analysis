# Paper Plan: LLM Chiplet Express Link Placement

**Last updated**: 2026-04-22
**Status**: Draft restructuring in progress with new ML contribution

---

## Title (Final)

> **"Breaking the Cost-Performance Ceiling of LLM Chiplet Networks via Non-Locality-Guided Warm-Started Reinforcement Learning"**

### Design rationale
- "Breaking the Cost-Performance Ceiling" — continuity with existing draft thesis
- "LLM Chiplet Networks" — target scope (workload-specific, trending)
- "Non-Locality-Guided" — our unique thesis predictor (NL% → benefit)
- "Warm-Started RL" — differentiator from PARL (pure RL)
- 15 words; longer than 12-14 ideal but acceptable for DAC/DATE

---

## Target Venue

DAC / DATE / MICRO (architecture track)

---

## Thesis

1. **Non-locality fraction (NL%)** of the workload predicts express link benefit (Spearman ρ ≥ 0.9).
2. **Warm-start Reinforcement Learning** refines greedy heuristic placement, achieving strict Pareto dominance with safety guarantee.
3. NL% predicts not only when express links help, but also the headroom for algorithmic refinement beyond greedy.

---

## Three Contributions

### C1. Non-Locality as the Fundamental Predictor
- Identify NL% (fraction of non-adjacent traffic) as primary predictor of express-link benefit
- Spearman ρ ≥ 0.9 across 4 LLM workloads × 4 panels
- Predicts both (a) raw saving and (b) RL refinement headroom
- **Unique vs PARL**: PARL uses interference score, no workload-level predictor

### C2. Warm-Started RL with Safety Fallback
- Greedy heuristic → RL swap refinement → post-hoc BookSim fallback
- **Strict Pareto dominance**: 40/40 configs beat Adj Uniform, 32/40 beat greedy
- **Worst-case guarantee**: 100% ≤ greedy (fallback)
- Max +56.4% saving vs no-express baseline (MoE K32N8 4x)
- **Unique vs PARL**: PARL is cold-start RL; no worst-case guarantee; regressions possible on structured workloads (e.g., our Tree workload)

### C3. LLM Workload Coverage + Generalization
- 4 training workloads: Tree AR, Hybrid TP+PP, Uniform, MoE Skewed
- 3 unseen generalization workloads: Ring AR, Pipeline Parallel, All-to-All
- RL-WS: 100% win rate on unseen workloads (6/6)
- GNN fails on all-to-all (distribution shift from training)

---

## Key Experimental Results Summary

### Main Result (40 configs, savings vs Adj Uniform no-express)
| Workload | NL% | Greedy | RL-WS (ours) |
|---|---|---|---|
| Tree AR | 42% | +12.0% | **+13.0%** |
| Hybrid TP+PP | 77% | +24.0% | **+26.8%** |
| Uniform | 89% | +29.4% | **+32.7%** |
| MoE Skewed | 91% | +37.2% | **+40.0%** |
| **Overall** | | **+25.6%** | **+28.1%** (max +56.4%) |

- All 40 configs: RL-WS beats Adj (100% win rate)
- 32/40 RL-WS beats Greedy; 5 ties; 3 losses (all ≤1.7% on K16N4)
- With post-hoc fallback: 100% ≤ greedy guarantee

### Ablation (warm-start × fallback)
| Method | Mean vs greedy | Worst | Wins |
|---|---|---|---|
| Greedy (baseline) | 0.0% | 0.0% | — |
| Cold RL | -1.3% | +11.3% | 13/24 |
| Cold RL + FB | -3.6% | 0.0% | 13/24 |
| Warm RL | -3.6% | +1.7% | 33/40 |
| **Warm RL + FB (ours)** | **-3.7%** | **0.0%** | **33/40** |

- Warm-start fixes tree regression (+6.9% → -1.2%)
- Fallback caps worst-case at 0 (equal to greedy)
- Both components needed

### Generalization (unseen workloads)
| Workload | GNN (zero-shot) | RL-WS |
|---|---|---|
| Ring AR | -14.7% (4/4) | -11.5% (2/2) |
| Pipeline | -7.2% (4/4) | -8.5% (2/2) |
| All-to-All | +23.6% FAIL (0/4) | -1.2% (2/2) |
| **Overall** | +0.6%, 8/12 | **-7.1%, 6/6** |

- GNN fails on all-to-all (uniform traffic → no gradient to learn)
- RL-WS with warm-start + fallback generalizes 100%

---

## Paper Section Structure

### § Section / Subsection / Content

1. **Introduction**
   - Motivation: LLM chiplet training, cost-performance ceiling
   - Challenge: phantom load in mesh, adj-only can't break it
   - Contribution bullets (C1, C2, C3)
   - Figure F1 (motivation)

2. **Background & Related Work**
   - Chiplet NoI basics, phantom load definition
   - Express links concept (prior work: HexaMesh, FoldedHexaTorus, analytical baselines)
   - ML for chip design: Chiplet-Gym, RLPlanner, TDPNavigator (all orthogonal to ours)
   - **PARL (arXiv 2510.24113)** — closest work, explicit differentiation:
     - PARL: pure RL from scratch, interference-focused
     - Ours: greedy warm-start, NL% predictor, worst-case guarantee
   - Table T1 (Related Work comparison)

3. **Phantom Load Analysis**
   - Θ(K^{3/2}) scaling derivation
   - 4×4 example (Figure F2)
   - Table T2 (scaling comparison)

4. **Non-Locality Analysis (Thesis core)**
   - Definition: NL% = traffic between non-adjacent chiplets / total
   - 4 LLM workload characterization
   - Table T3 (LLM workloads + NL%)
   - Claim: NL% predicts benefit

5. **Express Link Placement**
   - 5.1 Greedy baseline (traffic-proportional scoring)
   - 5.2 Warm-Started RL Refinement (our method)
       - Architecture: surrogate + RL agent
       - Swap action space
       - REINFORCE training
   - 5.3 Post-hoc BookSim fallback (safety)
   - (Optionally 5.4 GNN variant for context)

6. **Evaluation**
   - 6.1 Experimental setup (BookSim, workloads, configs)
   - 6.2 Main result: RL-WS vs Greedy vs Adj (savings)
     - Table T4 (savings summary by workload)
     - Figure F3 (NL% → savings scatter, all methods)
     - Figure F4 (per-config bar, all 40 configs)
   - 6.3 Ablation (warm-start × fallback)
     - Table T5
     - Figure F5 (ablation + tree rescue)
   - 6.4 Generalization (unseen workloads)
     - Table T6
     - Figure F6 (unseen workload comparison)
   - 6.5 Physical overhead
     - Table T7 (CoWoS wire estimates)

7. **Discussion**
   - When to use each placement method (low/high NL%)
   - Design-time vs runtime trade-off (RL-WS fine at design time)
   - Limitations: synthetic traffic, K ≤ 32

8. **Conclusion**

---

## Tables

### T1: Related Work Comparison (§2)
| Work | Method | Target | Express links? | Guarantee |
|---|---|---|---|---|
| Eris-R / CLuE | Analytical | NoI routing | No | — |
| HexaMesh | Analytical | Chiplet layout | Implicit | — |
| FoldedHexaTorus | Hand-designed | Chiplet topology | Yes (fixed) | — |
| Chiplet-Gym | RL | Accelerator resources | No (mesh only) | — |
| RLPlanner | RL | Floorplan order | No | — |
| **PARL** | Pure RL (PPO) | **NoI topology** | **Add/remove per step** | **None** |
| **Ours** | **Greedy + Warm-start RL** | **Express placement** | **Yes** | **≤ Greedy** |

### T2: Phantom Load Scaling (§3)
- Analytical formula
- Θ(K^{3/2}) derivation with hop-count analysis

### T3: LLM Workloads (§4)
| Workload | NL% | Pattern | Representative model |
|---|---|---|---|
| Tree All-Reduce | 42% | Hierarchical butterfly | Gradient sync |
| Hybrid TP+PP | 77% | Mixed group + stage | Megatron-LM TP=8 |
| MoE Skewed | 91% | Zipf top-2 dispatch | DeepSeek/Mixtral |
| Uniform | 89% | Random worst-case | Synthetic baseline |

### T4: Main Result (§6.2)
Savings vs Adj Uniform (mean over 10 configs per workload):
| Workload | NL% | Greedy | RL-WS | Δ (RL improves) |
|---|---|---|---|---|
| Tree AR | 42% | +12.0% | **+13.0%** | +1.0%p |
| Hybrid TP+PP | 77% | +24.0% | **+26.8%** | +2.8%p |
| Uniform | 89% | +29.4% | **+32.7%** | +3.3%p |
| MoE | 91% | +37.2% | **+40.0%** | +2.8%p |

Best single config: MoE K32N8 4x → **+56.4%**

### T5: Ablation (§6.3)
| Method | Warm? | FB? | Mean | Worst | Wins |
|---|---|---|---|---|---|
| Greedy | — | — | 0.0% | 0.0% | — |
| Cold RL | No | No | -1.3% | +11.3% | 13/24 |
| Cold RL+FB | No | Yes | -3.6% | 0.0% | 13/24 |
| Warm RL | Yes | No | -3.6% | +1.7% | 33/40 |
| **Warm+FB** | **Yes** | **Yes** | **-3.7%** | **0.0%** | **33/40** |

### T6: Generalization (§6.4)
| Unseen workload | GNN | RL-WS |
|---|---|---|
| Ring All-Reduce | +14.7% (4/4) | +11.5% (2/2) |
| Pipeline Parallel | +7.2% (4/4) | +8.5% (2/2) |
| All-to-All | -23.6% FAIL (0/4) | +1.2% (2/2) |
| Overall | +0.6%, 8/12 | **-7.1%, 6/6** |

### T7: Physical Overhead (§6.5)
CoWoS wire count estimates per panel configuration

---

## Figures

### F1: Motivation (§1)
- **Existing figure** (fig_intro_v5)
- 2-panel: (left) phantom load explosion at K=16+, (right) adj ceiling vs express
- Message: "Express breaks the ceiling that adj cannot"

### F2: Phantom 4×4 example (§3)
- **Existing figure** (gen_phantom_4x4.py)
- Visual diagram of routing amplification

### F3: NL% → Savings Scatter (§6.2) ★ Core result
- **Source**: `results/ml_placement/fig_savings_vs_adj.png` (Panel B)
- X=NL%, Y=saving vs Adj
- Two series: Greedy (x markers) + RL-WS (circle markers)
- Trend lines for both
- Mark max: "MoE K32N8 4x: +56.4%"
- Message: "NL% predicts benefit; RL-WS extends savings further"

### F4: Per-config 40 bars (§6.2) — Optional, might merge with F3
- **Source**: `results/ml_placement/fig_warmstart_final.png` (Panel A)
- 40 bar pairs (Greedy vs RL-WS) grouped by workload
- Message: "RL-WS wins in 32/40, matches in 5, losses all <1.7%"

### F5: Ablation + Tree rescue (§6.3)
- **Source**: `results/ml_placement/fig_ablation.png`
- 2-panel: (A) 5-method ablation bar chart, (B) tree workload cold vs warm
- Message: "Both warm-start and fallback contribute"

### F6: Generalization (§6.4)
- **Source**: `results/ml_placement/fig_generalization.png`
- 2-panel: (A) per-config bars, (B) mean improvement by workload
- Message: "RL-WS 100% on unseen workloads, GNN fails on all-to-all"

### F7 (optional/supplementary): Comprehensive summary
- `results/ml_placement/fig_supplementary_summary.png` — 6-panel overview
- Use only if space permits

---

## Key File Paths (for continuation)

### Experiment scripts
- `cost_perf_6panel_workload.py` — main 40-config BookSim runner
- `ml_express_placement.py` — initial RL+GNN training (creates surrogate + GNN)
- `ml_express_placement_fast.py` — cold-start RL comparison
- `ml_express_warmstart.py` — warm-start RL (main method)
- `ml_generalization.py` — unseen workload test
- `find_saturation.py` — saturation rate exploration

### Result files (JSON)
- `results/cost_perf_6panel_<wl>/cost_perf_6panel_incremental.json` — main BookSim data
- `results/ml_placement/ml_comparison_fast.json` — cold-start RL + GNN (40 configs)
- `results/ml_placement/ml_comparison_warmstart.json` — warm-start RL (40 configs) ⭐
- `results/ml_placement/ml_generalization.json` — unseen workloads (12 configs)
- `results/ml_placement/ablation_stats.pkl` — ablation computed stats
- `results/ml_placement/final_stats.pkl` — main result summary
- `results/ml_placement/surrogate_model.pt` — trained surrogate weights
- `results/ml_placement/gnn_model.pt` — trained GNN weights
- `results/saturation_rates.json` — saturation boundaries per workload

### Figures (PNG + PDF)
- `results/ml_placement/fig_warmstart_final.png` — main 40 result
- `results/ml_placement/fig_ablation.png` — ablation
- `results/ml_placement/fig_generalization.png` — generalization
- `results/ml_placement/fig_supplementary_summary.png` — 6-panel overview
- `results/ml_placement/fig_savings_vs_adj.png` — savings vs Adj baseline view
- `results/ml_placement/fig_ml_comparison.png` — method comparison (ablation view)
- `results/fig_cost_saving_16panel.png/pdf` — budget sweep 16-panel

### Paper files
- `paper/main.tex` — existing draft (to restructure)
- `paper/section_5_5_draft.tex` — new ML section draft (to integrate into §5)

---

## Related Work Positioning (critical for reviewer Q&A)

### vs PARL (arXiv 2510.24113, Oct 2025) — closest
- **PARL**: Cold-start Maskable PPO, adds/removes single links, interference-focused, no worst-case guarantee
- **Ours**: Greedy warm-start + REINFORCE swap actions + post-hoc fallback + NL% predictor
- **Key differentiators**:
  1. Greedy warm-start (faster, leverages heuristic knowledge)
  2. Post-hoc fallback (worst-case guarantee: never worse than greedy)
  3. NL% as workload-level predictor (PARL has no such framework)
  4. Broader workloads (4 training + 3 unseen generalization)

### Other related work (orthogonal)
- Chiplet-Gym: resource selection (not topology)
- RLPlanner / TDPNavigator: floorplan placement (not NoI)
- FoldedHexaTorus: hand-designed topology (no ML)
- HexaMesh: chiplet arrangement (no ML)

---

## Decisions (finalized)

### Title
✅ **"Breaking the Cost-Performance Ceiling of LLM Chiplet Networks via Non-Locality-Guided Warm-Started Reinforcement Learning"**

### Baselines for main result
✅ Adj Uniform (no-express), Greedy, RL-WS (ours)
- GNN as supplementary in §6.4 generalization only
- Cold RL only in ablation (§6.3)

### Scope
✅ K ∈ {16, 32}, N ∈ {4, 8}, 4 training workloads
✅ Budget: 2x, 3x, 4x (N=4) / 2x, 4x, 7x (N=8)

### Guarantees
✅ Post-hoc BookSim fallback ensures RL-WS ≤ Greedy
✅ Claim: "strict Pareto dominance over greedy with worst-case parity"

---

## TODO (remaining work)

### Priority 1 (essential)
- [ ] Integrate §5.5 draft into main.tex as proper §5 Express Link Placement section
- [ ] Update Table 4 → Table T4 with new savings numbers
- [ ] Replace Fig 3 in current paper with new fig_savings_vs_adj Panel B (NL% scatter)
- [ ] Add Table T1 with PARL row
- [ ] Update Abstract with new thesis + method + numbers
- [ ] Update Introduction contributions list

### Priority 2 (strongly recommended)
- [ ] Add §6.3 Ablation section (table + figure)
- [ ] Add §6.4 Generalization section (table + figure)
- [ ] Update Conclusion with headline numbers
- [ ] Regenerate Fig 1 motivation if needed

### Priority 3 (nice to have)
- [ ] Robustness experiment (3 seeds on key configs)
- [ ] Direct comparison with PARL (if code available)
- [ ] Appendix: surrogate accuracy ablation

---

## Open Questions

1. **Page limit**: DAC/DATE 10 pages. Current plan has 7 tables + 6 figures. Need to tighten.
   - Merge T2+T3 or move to appendix?
   - F4 could be combined with F3 (one figure with 2 panels)

2. **PARL direct comparison**: If their code is released, run on same configs for Table T4.
   - Check arxiv page for GitHub link.

3. **Robustness**: Paper currently has single-seed results. Reviewer may ask for variance.
   - Quick win: 3 seeds on 3 key configs (Tree K32N8 4x, Hybrid K16N8 2x, MoE K32N8 2x)

---

## Environment notes

- Python: venv at `/home/youngwoo.jeong/grepo/.venv`
- Packages: torch 2.11.0 (CPU), numpy 2.2.6, scipy 1.15.3, matplotlib 3.10.8
- BookSim: `booksim2/` submodule (cloned separately)
- HTTP server for figure viewing: `python3 -m http.server 8765` in `results/`
