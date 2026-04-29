# Reviewer 5 (Skeptic) — Iteration 13

**Paper**: "Predict, Place, Refine: Non-Locality-Guided Express Link Placement for LLM Chiplet Networks"
**Track**: Architecture (DAC/DATE-class)
**Calibration**: ISCA-class accept rate ~20%

---

## Summary

The paper proposes a three-step workflow (Predict via NL%, Place via greedy/FBfly, Refine via warm-start REINFORCE with a rate-aware MLP surrogate and BookSim post-hoc selection). Headline claims: (a) NL% predicts saving with Spearman ρ=0.83 across 28 cells; (b) RL-WS strictly beats FBfly on 24/28 cells with overall +35.6% saving vs adjacent-uniform; (c) the headline single-cell number is −83.2% latency on MoE Skewed K=32, N=8, b=4×; (d) NL% acts as a "deployment classifier" (NL≥77% → run RL, NL≤50% → FBfly suffices).

The technical machinery is reasonable and the BookSim-validated selection is a sensible safety net. However, the claims are over-sold: the headline numbers are dominated by a single workload family (MoE Skewed), the "deployment classifier" cutoffs appear to have been chosen on the same 28 cells used to validate them, and the comparison to FBfly is structurally unfair on the workload that drives the entire story. The paper as currently framed does not justify its central claim.

---

## Strengths

- **The Θ(K^{3/2}) phantom-load result is clean and well-motivated.** It frames express links as a topological rather than allocation-level fix, which is a legitimately useful framing.
- **Including BookSim post-hoc selection as a safety net for surrogate error is sound methodology.** The 48-candidate top-k design at least bounds the worst-case regression caused by surrogate inaccuracy.
- **The λ wire-delay sensitivity sweep (Table 8) is a useful robustness check** and is the kind of thing reviewers usually have to demand.
- **The narrative shift to "NL% as deployment classifier" is, in principle, a sharper thesis than a generic latency-reduction claim.** I want to like this framing — but the evidence does not support it (see Weaknesses W2, W3).

---

## Weaknesses

### W1. [MAJOR] The −83.2% headline is a strawman comparison against a workload-blind FBfly on the one workload where it is structurally guaranteed to fail.

The headline single-cell number (MoE Skewed K=32, N=8, b=4×: 67.8 vs 402.8 cycles) compares RL-WS (which sees the skewed traffic matrix) against FBfly (explicitly defined in §6.1 as "ignoring the workload-specific traffic matrix"). MoE Skewed has a few high-traffic expert pairs by design; FBfly spreads links uniformly; therefore FBfly under-provisions exactly the pairs that carry most of the traffic. **This is not a discovery — it is a tautology dressed up as a finding.** The honest baseline here would be a *workload-aware* FBfly variant (e.g., row/column allocation weighted by per-row traffic mass, or FBfly seeded on a row/column permutation that places heavy experts on shared rows). The paper does not construct such a variant. Until it does, the −83.2% headline cannot be claimed as evidence that "RL-WS is essential" — it could equally be evidence that "any workload-aware allocator with a sane permutation would beat workload-blind FBfly on MoE Skewed."

For comparison: greedy (workload-aware) saves +61.0% on MoE vs adj-uniform versus RL-WS's +86.1%. So 25 percentage points of the 86 are attributable to *being workload-aware at all*, not to the RL refinement specifically. The paper conflates these.

### W2. [MAJOR] The headline aggregate "+8.5pp over FBfly, +11.8% latency reduction vs FBfly" is dominated by MoE; without MoE it collapses to ~3%.

From Table 6, the per-workload mean of "vs FBfly" is:
- MoE Skewed: −63.1%
- All-to-all: −4.2%
- Uniform Random: −3.9%
- Hybrid TP+PP: −4.8%
- Tree: −0.8%
- Ring: −3.1%
- Pipeline: −2.4%

Mean of all seven = −11.76% (matches the reported −11.8% — confirming the aggregate is just the per-workload average). Mean of the **six non-MoE workloads is −3.2%**. **One workload contributes more than 70% of the headline gap.** This is not a generalizable result; it is one workload's effect being amortized across the table. The paper must report this stratification explicitly: "MoE drives 71% of the aggregate FBfly gap; on the remaining 6 workloads RL-WS improves over FBfly by a mean of 3.2%." Hiding this is the kind of overclaiming reviewers will catch.

Moreover, "RL-WS vs greedy" — the comparison that actually isolates the RL contribution after both methods are workload-aware — is barely discussed. From Table 6: Greedy 24.8% mean vs RL-WS 35.6% mean ≈ +10.8pp; subtract the MoE contribution (greedy +61, RL-WS +86, weight 4/28) = +25/7 ≈ +3.6pp from MoE, leaving roughly +7.2pp from non-MoE workloads. This is more credible, but the paper does not surface it. The current framing buries the actual contribution of the RL machinery.

### W3. [MAJOR] The "NL% deployment classifier" cutoffs (NL≥77 → RL, NL≤50 → FBfly) are post-hoc fitted to the same 28 cells used to validate them. There is no held-out test.

The abstract and Conclusion claim NL% "tells architects when traffic-aware learned placement is essential versus when a topology-aware heuristic suffices," with specific cutoffs at 77% and 50%. But:

1. The cutoff "77%" is exactly the NL% of the lowest-NL high-group workload (Hybrid TP+PP). It is **selected** as the boundary, not derived from a held-out validation set.
2. The seven workloads were chosen *before* observing the FBfly-vs-RL gap; there is no explicit gap between 50% and 77% NL%, but that gap exists because **no workload was sampled** in (50%, 77%). The classifier's apparent sharpness is an artifact of the workload sampling.
3. The rate-aware surrogate (§5.3) is "trained on 1408 BookSim samples that span all evaluated (workload, K, N, b) cells." That is, the surrogate was trained on the same workloads used to evaluate the classifier. There is **no truly held-out workload**.
4. The paper's earlier draft (per CLAUDE.md history) discussed "generalization on UNSEEN workloads (ring, pipeline, all-to-all) 6/6 wins" — but in this draft, those workloads are now part of the 28-cell training set. What changed?

**For the deployment-classifier claim to be credible, the paper must (a) hold out at least one workload from surrogate training and from the NL% calibration, (b) refit the cutoffs on a development subset, and (c) show that RL-WS still wins on the held-out workload at NL≥cutoff and FBfly suffices below.** Without this, the classifier is a curve-fit on 28 points.

### W4. [MAJOR] Spearman ρ=0.83 across 28 cells almost certainly collapses without MoE.

Four MoE cells contribute saving values that are dramatic outliers (RL-WS +86%, +84%, +82%, +73% per Section 6.3 + Table 6). With 24 cells in a 0–40% saving range and 4 MoE cells in 70–86%, those four points alone anchor the rank correlation. **What is ρ on the 24 non-MoE cells? The paper does not report it.** Standard practice would require leave-one-workload-out ρ to demonstrate that the predictor is not driven by a single outlier cluster. I expect the non-MoE ρ is closer to 0.4–0.6, which would still be "predictor exists" but would substantially weaken the "deployment classifier" framing.

Note also that Fig. 4's caption reports "Pooled Spearman ρ(NL%, RL-WS saving)=0.74" while the abstract and §4 report 0.83 / 0.825. **Which is correct, and on what set?** Either the figure or the text is stale.

### W5. [MAJOR] RL-WS is brute-force search dressed up as RL.

The procedure is: 16 random seeds × top-3 candidates per seed = **48 candidate allocations**, all evaluated by full BookSim. The "selection" is then `argmin` over BookSim measurements. This is essentially a 48-shot random search with a learned proposal distribution. Two specific concerns:

1. **What is the baseline of "48-shot random allocation" or "48-shot greedy with random tiebreaking" + post-hoc BookSim selection?** Without this, we cannot tell whether the REINFORCE policy is contributing anything beyond exploration breadth. A 48-candidate pure-greedy ensemble (e.g., greedy with 48 different random seedings of the candidate-link tiebreaks) would directly probe whether the RL actor is doing useful work, or whether the BookSim "best-of-48" filter is doing all the heavy lifting.
2. **The compute cost is not honestly disclosed.** §7 says "RL-WS takes minutes per configuration"; that's the training time. But the BookSim selection alone is 48 BookSim runs at 4 rates = 192 BookSim runs per cell × 28 cells = 5376 BookSim runs. Plus surrogate training (1408 samples). The paper's "RL-WS is essential at high NL%" claim should be calibrated against an honest compute budget comparison.

### W6. [MAJOR] FBfly is described as "the strongest hand-engineered baseline" but is implemented in a deliberately weak form.

§6.1 defines FBfly as "ignoring the workload-specific traffic matrix" and "distributes links regularly across rows and columns up to a per-pair cap of N." This is a textbook flattened-butterfly, but **a real systems person would never deploy a workload-blind FBfly when the workload matrix is known**. At minimum, a fair FBfly variant should:
- Permute the chiplet-to-grid-position mapping to place high-traffic chiplet groups on the same row/column (1 minute of optimization).
- Optionally weight per-row/column link counts by per-row traffic mass (still topology-aware, not workload-blind).

Such a variant would close most of the MoE gap, since MoE Skewed's high-traffic experts can be co-located by permutation. The paper does not test this. If the answer is "we tried it and it doesn't close the gap," **say so and report the numbers.** As written, FBfly is a strawman.

### W7. [MODERATE] The "−83.2%" arithmetic in the abstract is misleading.

67.8 vs 402.8 cycles = **(402.8−67.8)/402.8 = 83.2% reduction in latency**, which is what the paper claims. Fine. But the abstract leads with this single-cell number ("the best single cell reaches −83.2%") while the *mean* improvement on the same workload is "MoE Skewed... vs FBfly: 4/4, −63.1%" (Table 6). Leading with the best-of-4 cell rather than the workload mean is a presentation choice that emphasizes the most flattering result. The abstract should report the workload-mean, not the cherry-picked best cell.

### W8. [MODERATE] No real hardware validation; reviewer feedback from prior iterations was apparently not addressed.

CLAUDE.md notes "Reviewer feedback (iter 8/9): real HW validation 없음 (BookSim only), workload trace 아닌 synthetic, deadlock freedom 미논의." Deadlock freedom is now addressed (§7), good. But the synthetic-vs-trace and HW-validation gaps remain unaddressed. For a DAC/DATE submission, BookSim-only is acceptable; for ISCA/MICRO, this is a weakness that should at least be discussed in Limitations with a more concrete plan than "future work."

### W9. [MODERATE] The surrogate's "Spearman ρ=0.928 on held-out 20%" is suspect.

The surrogate is trained on 1408 BookSim samples spanning all (workload, K, N, b) cells. A 20% random held-out split within this distribution measures **interpolation** within a covered space, not extrapolation. The relevant question for a "deployment classifier" claim is: how well does the surrogate predict for a workload it has never seen? This is not reported. Given the policy is rewarded by surrogate-predicted latency, a surrogate that fails out-of-distribution would silently mis-rank candidates — but this is masked by the BookSim post-hoc selection, which means **the surrogate's quality is doing less work than the paper implies**, and the BookSim-best-of-48 filter is doing more.

### W10. [MINOR] Pipeline (NL=10) and Ring (NL=13) results are inconsistent with the "NL ≤ 50 → FBfly suffices" claim.

Table 6 shows RL-WS saves +22.8% (Ring) and +15.5% (Pipeline) vs adj-uniform, meaningfully more than the +20.3% / +13.5% FBfly numbers. Per the deployment classifier, on these workloads RL is supposed to be unnecessary. But the table reports 3/4 wins on each. Either (a) "matches within ±1 cycle" hides actual differences, or (b) the classifier rule is more nuanced than the abstract suggests. The paper needs to report absolute cycle differences (not just %), so reviewers can verify whether 3/4 wins on Ring at NL=13% really are within simulation noise.

### W11. [MINOR] Self-citation / contribution C1 is mis-stated.

C1 says "16/16 high-NL cells (NL≥77%) RL-WS strictly beats FBfly". Table 6 shows MoE 4/4, A2A 4/4, Uniform 4/4, Hybrid 4/4 = 16/16. OK. But C1 also says "12 low-NL cells (NL≤50%) FBfly's row/column regularity is already near-optimal and RL-WS matches within ±1 cycle." Table 6 reports Tree 2/4 (1t,1L), Ring 3/4 (1t), Pipeline 3/4 (1L) = 8 strict wins, 2 ties, 2 losses. So RL-WS strictly wins **8/12** even on low-NL workloads. If RL-WS is strictly winning the majority of low-NL cells too, the "deployment classifier" story is weaker — RL just always helps a bit. Either re-frame, or include absolute-cycle data showing those wins are noise.

### W12. [MINOR] Table 6's "vs FBfly" column header conflates per-cell wins and mean reduction.

"4/4, −63.1%" is two different statistics in one cell. Split into two columns. Also clarify whether −63.1% is the **arithmetic mean of per-cell percent reductions** or **percent reduction of the workload-mean cycles** — these can differ substantially in MoE because of one cell's huge ratio.

---

## Questions for the Authors

1. **What is Spearman ρ between NL% and RL-WS saving on the 24 non-MoE cells?** And what is ρ for "RL-WS over FBfly margin" vs NL% on the same 24 cells?
2. **What is the FBfly performance on MoE Skewed with a traffic-permuted chiplet-to-grid mapping?** I.e., place the heavy expert pairs co-located by row/column before applying FBfly's regular allocation.
3. **What is the 48-shot greedy-with-random-tiebreaking + BookSim-best-of-48 baseline?** This isolates the contribution of REINFORCE vs the post-hoc selection filter.
4. **Was the NL%≥77 cutoff selected after looking at the 28-cell results?** If so, on what held-out workloads/configurations does the cutoff still hold?
5. **What ρ does the surrogate achieve on a leave-one-workload-out evaluation?** This is the relevant out-of-distribution metric, not a 20% random split.
6. **Why does Fig. 4's caption report ρ=0.74 while the text reports ρ=0.83 / 0.825?** Which is the authoritative number?
7. **What is the variance over independent end-to-end RL-WS re-runs (different REINFORCE seeds, different BookSim seeds)?** Limitation (ii) acknowledges this is missing — but for a 35.6% headline number, single-run results are not enough.
8. **At b=2× and b=3×, does the deployment classifier still hold?** The paper's headline cells are mostly b=4×. The crossover discussion (§6.1) admits express may tie or lose at b=2×, which would invalidate the classifier in that regime.
9. **What does PARL achieve on the same 28 cells?** "Qualitative positioning" of the closest prior work in Table 1 is insufficient. Even a partial reproduction on 4 representative cells would substantially strengthen the contribution.

---

## Missing References

- **Workload-aware permutation/placement work for chiplets** (e.g., placement-aware NoI synthesis, communication-aware chiplet mapping in CoMHisp / COMET style work). The paper claims FBfly is "the strongest no-RL baseline" but the relevant comparator is *workload-aware regular allocators*, not workload-blind FBfly. There is a literature on this; it is not engaged.
- **Best-of-N / search-based architecture optimization (e.g., FlexFlow, ASTRA-sim, AutoML for accelerator design).** The 48-candidate top-k design is essentially this paradigm; positioning would clarify why REINFORCE rather than evolutionary or Bayesian optimization was chosen.
- **Surrogate-based architectural search** (e.g., NAS surrogates, performance predictor work). The 501-dim MLP surrogate is a standard NAS surrogate; the contribution should be calibrated against that body of work.

---

## Detailed Comments (Line References to main.tex)

- **L29 (Abstract)**: "no routing algorithm eliminates this structural tax" — this is shown for XY/YX/ECMP/Valiant in Table 3, but is stated as a general claim. Soften to "across the routing algorithms we evaluated."
- **L31 (Abstract)**: The "RL-WS strictly beats FBfly on 24/28" sentence is fine, but should immediately disclose that 4 of the 4 MoE cells contribute most of the aggregate margin (see W2).
- **L31**: "the best single cell reaches −83.2%" — replace with workload-mean −63.1% for MoE; report best-cell only in Section 6.3 where context is provided (see W7).
- **L51 (Intro)**: "NL% predicts both the raw express-link benefit and when learned RL placement is worth invoking" — these are two different claims with different evidence bases. Separate them and cite distinct ρ values for each.
- **L55 (C1)**: "16/16 high-NL cells (NL≥77%) RL-WS strictly beats FBfly" — fine, but as noted in W11, it strictly wins 8/12 low-NL cells too. The deployment classifier claim is weaker than presented.
- **L84 (Table 1)**: "Predictor: NL%" for "Ours" — but NL% is a property of the workload, not a method contribution. Other cells use "No" (Kite, Florets, PARL). This row should clarify that "Predictor" means "uses an explicit pre-simulation predictor for when learned placement is needed," not "knows about non-locality."
- **L175 (Table 3 caption)**: "comparative, not absolute" disclaimer is good. But then including specific numbers (Max α=111 vs 223) invites readers to compare them. Consider table-of-ratios format instead.
- **L214 (NL% predictor section)**: "Spearman ρ=0.825 (p=6.8×10⁻⁸)" — report ρ on (a) only non-MoE cells, (b) leave-one-workload-out average. Without these, the result is fragile to the inclusion of one workload.
- **L256 (RL-WS surrogate)**: "1408 BookSim samples that span all evaluated (workload, K, N, b) cells" — explicitly state how many samples per cell, and what the train/val split is at the cell granularity (random vs leave-cell-out).
- **L258**: "weights {1:1, 2:1, 3:1, 4:2}" — these weights look hand-tuned. Justify or ablate.
- **L260 (BookSim final selection)**: "the candidate with the lowest max-rate latency is selected" — at which rate, with what tie-breaking? Is the same rate used for selection as for reporting? This is a subtle source of selection bias.
- **L309 (Low-budget regime)**: Acknowledging the b=2× crossover is honest, but the abstract claims the deployment classifier "across 28 cells" — at b=2× the classifier's high-NL-implies-RL-essential rule may not hold. Quantify.
- **L316 (Main result)**: "FBfly's regular row/column allocation saturates at 402.8 cycles while RL-WS attains 67.8 cycles" — please report the *throughput* / *injection rate* at which these cycle counts were measured. A 6× cycle difference often reflects FBfly being above its saturation knee while RL-WS is below — a different comparison than "latency at the same load."
- **L347 (Fig. 4 caption)**: ρ=0.74 contradicts abstract's 0.83. Reconcile (W4).
- **L362–367 (Per-cell)**: Honest disclosure that 3 cells drive the headline. Good. But the text frames this as "characterizing when RL-WS extracts dramatic value," which is generous; the more skeptical reading is "the headline aggregate is one workload's effect amortized over 28 cells" (W2).
- **L370**: "2 are ties within ±0.1 cycle and 2 are minor losses by ≤0.9 cycle" — at this resolution, all four are within BookSim warmup/measurement noise. Report multi-seed BookSim variance to justify the "match within simulation noise" claim quantitatively.
- **L399 (Discussion)**: "RL-WS takes minutes per configuration" — this is training time only. Include BookSim selection time and full end-to-end wall clock to be honest about the cost.
- **L408 (λ sensitivity)**: "RL-WS uplift over greedy *grows* under higher λ" is interesting but the deltas (e.g., +3.1pp → +5.8pp on Uniform) are small enough to be within REINFORCE seed variance. With single-run results this claim is weakly supported.
- **L439 (Limitations)**: Add: (vii) FBfly is workload-blind by construction; a workload-aware regular-topology baseline is not evaluated. (viii) NL% cutoffs (77/50) are not validated on held-out workloads. (ix) The 48-candidate top-k search vs RL contribution is not isolated.

---

## Ratings

| Dimension | Score (1–5) | Note |
|---|---|---|
| Novelty | **2** | Three-step framing is reasonable but each piece (NL% as predictor, warm-start RL with surrogate, post-hoc filter) is incremental. PARL is the closest prior work; differentiation is claimed but not experimentally demonstrated. |
| Technical Quality | **2** | Methodology has notable gaps: no held-out workload, no workload-aware FBfly, no isolation of REINFORCE vs random-search-with-BookSim-filter, no multi-seed end-to-end variance. The Θ(K^{3/2}) result and λ sweep are bright spots. |
| Significance | **2** | Headline aggregate is dominated by one workload (MoE) against an arguably strawman baseline. The "deployment classifier" claim is the most novel framing, but it is fitted post-hoc to the same 28 cells used to validate it. Without held-out evidence, the contribution is much smaller than presented. |
| Presentation | **3** | The narrative is clear and the figures are readable. The Predict-Place-Refine framing is memorable. But ρ inconsistencies (0.74 vs 0.83), conflated table cells, and the abstract's cherry-picked best cell undermine credibility. |
| Overall | **2** | |
| Confidence | **4** | I have read the paper carefully, verified key arithmetic against the tables, and have specific concerns grounded in line numbers. Less than 5 only because I have not re-implemented the experiments. |

---

## Decision

**Weak Reject (borderline).**

The paper has a real result hiding in it — that NL% has predictive value, that warm-starting from FBfly diversifies the RL search, and that BookSim-validated post-hoc selection is a sound safety net. But the current framing overclaims. Specifically:

1. The −83.2% headline is a single MoE cell against a workload-blind FBfly; the workload-mean is −63.1%, the non-MoE aggregate gap is ~3%, and the comparison itself is structurally unfair until a workload-aware FBfly variant is evaluated.
2. The "NL% deployment classifier" cutoffs are fit on the same 28 cells used to validate them; no held-out workload exists.
3. RL-WS is operationally a 48-shot search with a learned proposal; the contribution of REINFORCE specifically (vs e.g. 48-shot greedy ensembles) is not isolated.

I would shift to **Weak Accept** if the authors:
- Add a workload-aware FBfly baseline (traffic-permuted chiplet-to-grid mapping) and re-run Table 6;
- Hold out at least one workload from surrogate training and from NL% cutoff selection, then validate the classifier on it;
- Report ρ on non-MoE cells alone, and per-workload leave-one-out;
- Add a 48-shot greedy-ensemble-with-BookSim-filter baseline to isolate the RL contribution;
- Report multi-seed end-to-end RL-WS variance for the headline cells.

Without these, the paper will not survive PC discussion against the obvious "MoE drives the result and FBfly is not properly tuned" critique.
