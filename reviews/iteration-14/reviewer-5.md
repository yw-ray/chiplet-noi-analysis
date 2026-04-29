# Reviewer 5 (Skeptic) — Iteration 14

**Paper**: "Predict, Place, Refine: Non-Locality-Guided Express Link Placement for LLM Chiplet Networks"
**Track**: Architecture (DAC/DATE-class)
**Calibration**: ISCA-class accept rate ~20%
**Prior decision (iter-13)**: Weak Reject 2.0/5

---

## Summary

The iter-14 revision is a serious response to my iter-13 critique. The most-blatant overclaiming has been corrected: numerical inconsistencies (24.8 vs 25.6, ρ=0.74 vs 0.83) are fixed; the headline aggregate is now openly disclosed as MoE-driven (Limitation (ii), §VI.D, Conclusion all state "excluding MoE per-cell mean is -3.2%"); the low-NL narrative has been honestly recast from "FBfly suffices" to "RL-WS strictly beats FBfly on 8/12 with max -5.3% margin, the other 4 are recovered by fallback"; per-cell §VI.D now lists all four MoE cells (no more cherry-picking three out of four); a new §VI.C ablation against `min(greedy, FBfly)` per-cell measured baselines partially defangs the "RL-WS = 48-shot search" attack.

What has not been addressed: the NL%≥77 / NL%≤50 cutoffs are still fitted on the same 28 cells (no held-out workload), the surrogate is still trained on graded cells (acknowledged honestly in Limitation (iv) but not fixed), PARL is still not experimentally reproduced, no workload-aware FBfly variant exists, and there is no multi-seed end-to-end variance study for the headline cells.

The paper now reads like a calibrated, honest characterization of a real but narrow result: NL% predicts express benefit, RL refinement helps modestly on most cells and dramatically on MoE Skewed, and a post-hoc BookSim filter prevents regression. The "deployment classifier" framing is the most fragile part — three of seven workloads land in the explicit (50%, 77%) gap that was never sampled, and no held-out validation exists. Whether this qualifies as a contribution depends on the venue: as a DAC/DATE characterization paper, it is borderline-defensible; as an ISCA/MICRO claim of a learned method that is "essential", it remains under-supported.

---

## Iter-13 Attacks: What Was Closed, What Was Not

| Attack (iter-13) | Status (iter-14) | Notes |
|---|---|---|
| W1 (–83.2% strawman) | Partial | Honestly contextualized in §VI.B/D and Limitation (ii); but workload-aware FBfly variant still not run, so the structural strawman objection survives. |
| W2 (MoE drives aggregate) | **Closed** | Limitation (ii), §VI.D, Conclusion all explicitly state "excluding MoE per-cell mean is -3.2%". This is now disclosed at every claim site. |
| W3 (post-hoc-fitted classifier) | **Not closed** | Surrogate is trained on all 28 cells (Limitation (iv) admits this); 77/50 cutoffs are still chosen on the same cells. No held-out workload exists. |
| W4 (ρ=0.83 collapses w/o MoE; ρ=0.74 vs 0.83) | Partial | Numerical reconciliation done (0.83 throughout, p=6.8e-8). But non-MoE ρ still not reported; given §VI.D's "non-MoE mean -3.2% vs FBfly" and the spread of low-NL points, ρ on non-MoE cells is almost certainly substantially lower. |
| W5 (RL = 48-shot search) | Partial | New §VI.C reports 22/28 strict beats over `min(greedy, FBfly)`. This is informative — RL is doing more than enumeration of fixed initializations. But the requested baseline (48-shot greedy with random tiebreaking, BookSim-best-of-48) is still not run. We cannot tell whether REINFORCE specifically beats a search-only ablation. |
| W6 (FBfly is workload-blind strawman) | **Not closed** | No workload-aware FBfly (traffic-permuted chiplet-to-grid mapping) variant. The MoE −83.2% headline is still vs an explicitly workload-blind allocator. |
| W7 (best-cell vs workload-mean in abstract) | Partial | Abstract still leads with the −83.2% best-cell number; the workload-mean −63.1% appears only in Table 6. But §VI.D now lists all four MoE cells, so the cherry-picking is at least visible. |
| W8 (no HW validation) | Unchanged | Acknowledged in Limitation (i); fine for DAC/DATE, weak for ISCA/MICRO. |
| W9 (surrogate ρ=0.928 is in-distribution) | **Closed honestly** | §V.C and Limitation (iv) now explicitly state the 80/20 split is in-distribution; the safety guarantee is BookSim fallback, not surrogate ρ. The honest disclosure is acceptable; it weakens the surrogate's role in the contribution but no longer overclaims. |
| W10 (low-NL "matches" claim) | **Closed** | Abstract and §VI.B now say "RL-WS strictly beats FBfly on 8/12 low-NL cells with max -5.3% margin"; the 4 cells recovered by fallback are explicitly named in §VI.D. |
| W11 (C1 mis-stated) | **Closed** | C1 in iter-14 still says "matches within ±1 cycle" on low-NL, which is still a slight overclaim (the abstract's "8/12 with max -5.3% margin" is more accurate); minor inconsistency. |
| W12 (Table 6 conflated columns) | Cosmetic | Still "4/4, −63.1%" in one cell, but the column header now spells out "per-cell wins (strict latency reduction) and the per-workload mean latency reduction relative to FBfly". Acceptable. |

Net: 4 closed, 4 partially closed, 3 not closed, 1 acknowledged-but-unfixed. This is real progress.

---

## Strengths (iter-14)

- **Honest disclosure of MoE dependence** at every claim site is a meaningful integrity improvement. The "excluding MoE the per-cell mean is -3.2%" disclosure in Limitation (ii), §VI.D, and Conclusion makes overclaim-driven rejection harder. The paper now stands on what it actually shows.
- **Per-cell §VI.D lists all four MoE cells**, including the modest one (K=16, N=4, b=4×: −12.0%). This closes the cherry-picking concern from iter-13 W7. A reviewer skimming Table 6 will see that one of four MoE cells is unspectacular.
- **New ablation §VI.C and Table 7** (`Raw RL vs min(greedy, FBfly)`: 22/28 strict beat) is a real contribution. It demonstrates that the BookSim-selected RL allocation strictly outperforms the per-cell measured-best deterministic baseline on 79% of cells. This was the central iter-13 attack ("RL-WS = 48-shot search dressed up") and the response is substantive: at minimum, RL is finding allocations that neither greedy nor FBfly produce.
- **Surrogate's in-distribution status is now openly stated** (Limitation (iv)). The paper no longer implies cross-cell generalization. The safety claim is correctly attributed to the BookSim fallback rather than the surrogate's ρ.
- **Eq. 6** (`L_RL-WS = min(L_greedy, L_FBfly, L_RL-best)`) makes the worst-case guarantee mechanically explicit. The 4/28 fallback activations with 0.22–0.87 cycle rescue magnitudes are concrete and falsifiable.

---

## Weaknesses (iter-14)

### W1' [MAJOR — survives from iter-13]. The "deployment classifier" cutoffs (NL%≥77, NL%≤50) are still post-hoc fitted on the same 28 cells.

This was iter-13 W3, my most consequential objection. iter-14 acknowledges it (Limitation (iv) addresses surrogate generalization but not classifier generalization), but does not address it: the cutoffs 77 and 50 are still derived from inspecting the 28-cell results and are still validated on those same cells. The (50%, 77%) window is empty by sampling design — no workload was ever picked in that range — yet the paper reports the boundary as if it were physically meaningful. A reviewer asking "does the classifier still hold on a held-out workload at NL%=65%?" cannot be answered with this paper's evidence.

This is the cleanest experimental ask remaining: hold out one or two workloads from surrogate training and from cutoff selection (e.g., a `transformer-fwd-attention` pattern at NL%≈60–70%, easily synthesized), refit cutoffs on the rest, and show the boundary still applies. Until done, the "deployment classifier" framing is a curve-fit on 28 sampled points with a planted gap.

### W2' [MAJOR — survives from iter-13]. No workload-aware FBfly baseline.

Still missing. The −83.2% MoE Skewed headline still compares RL-WS (sees the skewed traffic matrix) against FBfly (workload-blind by construction). A *workload-aware* FBfly variant — e.g., permute the chiplet-to-grid mapping so heavy expert pairs share a row/column before applying regular FBfly allocation — would close some unknown fraction of that −63.1% MoE workload-mean gap. The paper does not run this experiment. Until it does, the structural objection from iter-13 W1 stands: the MoE result, which dominates the aggregate, is partly attributable to baseline weakness rather than RL strength.

### W3' [MAJOR]. The §VI.C ablation (22/28 strict beat) does not isolate REINFORCE from search-only baselines.

The new §VI.C ablation shows that the BookSim-selected RL allocation strictly beats the per-cell `min(greedy, FBfly)` on 22/28 cells. This is informative — but the iter-13 attack was specifically about whether REINFORCE itself contributes, vs whether the contribution is fully attributable to the 48-candidate ensemble + post-hoc BookSim filter. To answer this, one needs:

- **A 48-shot random-policy baseline**: 16 seeds × top-3 random allocations (subject to budget/cap constraints) → 48 candidates → BookSim-best.
- **A 48-shot greedy-with-tiebreak ensemble**: 48 greedy runs with perturbed candidate-link ordering → 48 candidates → BookSim-best.

Without these, "RL is doing real work" remains conditional on "the surrogate-guided REINFORCE policy generates better candidates than random or perturbed-greedy enumeration" — which is plausible, but the paper does not show it. Note that a true ISCA reviewer will assume the worst here unless shown otherwise.

### W4' [MAJOR — survives from iter-13]. Spearman ρ on non-MoE cells is still not reported.

The pooled ρ=0.83 has been verified internally and made consistent across abstract, §IV, Fig. 4 caption (good). But the request from iter-13 W4 was: *what is ρ on the 24 non-MoE cells?* The paper still does not answer. Given Limitation (ii)'s admission that the non-MoE per-cell mean reduction is only -3.2% vs FBfly (vs -11.8% pooled), the four MoE cells are clearly anchoring the rank correlation. A skeptical reviewer at PC discussion will ask for ρ_{non-MoE} and ρ_{leave-one-workload-out}; the paper has no answer.

I expect ρ_{non-MoE} to be in the 0.4–0.7 range (still a positive predictor, but not "0.83" headline strength). Reporting this honestly would weaken the abstract's framing but strengthen the paper's credibility.

### W5' [MODERATE]. The C1 contribution claim and the abstract's low-NL summary are inconsistent.

C1 in §I (line 55) says: *"on 12 low-NL cells (NL≤50%) FBfly's row/column regularity is already near-optimal and RL-WS matches within ±1 cycle"*. The abstract (line 31) says: *"RL-WS still strictly beats FBfly on 8/12 with max −5.3% margin, while the other 4 are ties or minor losses"*. These are not the same claim. "Near-optimal, RL-WS matches" sounds like FBfly is the better default; "RL-WS strictly beats 8/12 with max -5.3%" sounds like RL-WS is the better default with marginal gains. Pick one. The honest framing is the abstract's; C1 in iter-14 still reflects an earlier narrative.

### W6' [MODERATE]. The "deployment classifier" decision rule is itself unstable — at b=2× the rule may invert.

§VI.A admits a crossover at b=2× for highly non-local workloads. Limitation (ii)+(v) acknowledge this but do not quantify it. The deployment classifier as stated ("NL%≥77 → RL-WS; NL%≤50 → FBfly") is implicitly conditioned on b=4×; the abstract does not disclose this conditioning. An architect taking the classifier at face value at b=2× could deploy RL-WS on a high-NL workload and observe a *regression* relative to adjacent-uniform — exactly the regression the post-hoc fallback would not catch (because the fallback compares to the deterministic express baselines, not to no-express). Either disclose b dependence in the abstract, or qualify the classifier scope.

### W7' [MODERATE]. PARL is still positioned only qualitatively.

Limitation (vi) frames PARL as "complementary problem (multi-tenant interference minimization)". This is a defensible position, but it sidesteps the iter-13 question: even a partial reproduction on 4 cells (one per workload group) would substantially strengthen the contribution by showing that NL%-guided warm-start beats a strong learned method, not just deterministic heuristics. The paper as written has the closest prior work in a citation-only state.

### W8' [MODERATE]. Multi-seed end-to-end variance is acknowledged but not measured.

Limitation (v) is candid: "a multi-run variance study is left to future work". For headline numbers like −83.2% and 35.6%, a single end-to-end RL training run per cell is thin evidence. The paper has 16 warm-start seeds inside one cell, but those seeds share the same surrogate; the surrogate itself is trained once on 1408 BookSim samples. A reviewer can ask: "if you retrain the surrogate on a different bootstrap of 1408 samples and re-run the 16-seed RL pipeline, does Hybrid TP+PP K=16 N=8 still beat FBfly by exactly its current margin, or by 0.5x to 2x of that margin?" The paper has no answer.

### W9' [MINOR]. Limitation (iv) and (vi) are honest but disclose more weaknesses than iter-13 carried.

iter-14 *adds* limitations: in-distribution surrogate (iv), no PARL reproduction (vi), no multi-run variance (v). I read this as the authors being calibrated, not as new weaknesses they introduced. But aggregated, the limitations section now flags six distinct empirical gaps. A skeptical PC reviewer will read this list as "the authors know what they did not do". The paper's honest scoping is admirable; whether it is enough is a venue judgment call.

### W10' [MINOR]. The Conclusion's "RL-WS attains 35.6% mean latency saving... excluding MoE the per-cell mean reduction is -3.2%" sentence pair is internally consistent but rhetorically uneven.

The 35.6% is *vs adjacent-uniform*; the -3.2% is *vs FBfly excluding MoE*. These are different baselines and different exclusions. A non-careful reader will conflate them. Either restate the -3.2% as "vs FBfly excluding MoE" explicitly, or report the parallel statistic: "RL-WS attains 35.6% saving vs adjacent-uniform across 28 cells; excluding MoE, the saving is X% (where X is the non-MoE mean of the RL-WS column in Table 6, roughly +25%)." This makes the qualitative shape of the result legible without the reader doing the arithmetic.

### W11' [MINOR]. The ablation Table 7 reports "Loss by ≤0.9 cycle (would regress) 4/28" without saying *which* 4 cells.

§VI.D names them ("Tree K=16 N=4 at b=4×; Tree K=32 N=8 at b=2×; Pipeline K=16 N=4 at b=4×; Ring K=16 N=4 at b=4×"), good. But Table 7 should reference §VI.D so the reader does not have to cross-reference. Cosmetic.

---

## Questions for Authors

1. **Can you report ρ on the 24 non-MoE cells?** This is the single statistic that would most cleanly resolve the "is NL% a real predictor or a MoE artifact" question. If ρ_{non-MoE} ≥ 0.6, the deployment-classifier framing is strengthened; if < 0.4, it is honestly weakened. Report whichever it is.
2. **Workload-aware FBfly variant**: place high-traffic chiplet groups co-located by row/column (e.g., for MoE Skewed, route the heavy expert pairs through the same row), then apply FBfly. Does the −83.2% MoE gap remain? If yes, RL-WS is genuinely essential there; if no, the headline is partly a baseline-tuning effect.
3. **48-shot greedy-with-tiebreaks ensemble baseline**: would isolate the REINFORCE contribution from the BookSim-best-of-48 selection filter. Can this be added?
4. **Held-out workload validation of NL% cutoffs**: hold out at least one workload (or one (workload, K, N) cell), refit the 77/50 cutoffs on the rest, and show the held-out cell falls on the predicted side of the boundary.
5. **Multi-seed end-to-end variance**: re-run the headline cells (MoE Skewed K=32 N=8, Hybrid TP+PP K=32 N=8) with three independent surrogate seeds + RL pipelines. What is the std of the saving on these cells?
6. **Conditioning on b**: does the deployment classifier still hold at b=2× and b=3×? The abstract reads as if it is universal across budget; quantification would help.
7. **C1 vs Abstract inconsistency**: which framing is the canonical one — "FBfly is near-optimal, RL-WS matches" or "RL-WS strictly beats FBfly 8/12, max −5.3%"?

---

## Detailed Comments (line references)

- **L31 (Abstract)**: The "best single cell reaches −83.2%" still leads in the abstract before the workload-mean disclosure. Workload-mean is in Table 6 (−63.1% for MoE), which is more honest. Consider: "...up to −83.2% in the most favorable single cell (workload mean −63.1% on MoE Skewed); excluding MoE the per-cell mean reduction vs FBfly is −3.2%."
- **L55 (C1)**: "RL-WS matches within ±1 cycle" contradicts the abstract (8/12 strict beats with max −5.3%). Reconcile.
- **L215 (NL% predictor)**: report ρ_{non-MoE} and ρ_{leave-one-workload-out} alongside the pooled ρ=0.83.
- **L257 (surrogate)**: the disclosure that 80/20 split is in-distribution is correct and helpful. Add a one-sentence forward reference: "we treat cross-cell generalization as future work; the safety guarantee comes from Eq. (6), not from the surrogate." (This is implicit; making it explicit defangs the iter-13 W9 attack at first read.)
- **L322 (Main result)**: "FBfly's regular row/column allocation saturates at 402.8 cycles while RL-WS attains 67.8 cycles" — please report the *injection rate* and confirm both points are below their respective saturation knees. A 6× cycle-count gap *across* the saturation knee is qualitatively different from a 6× gap *below* both saturation knees.
- **L370 (§VI.D)**: "All four are NL≤50% cells where adjacent demand dominates" is consistent with the abstract; good. Cross-reference Table 7 row "Loss by ≤0.9 cycle: 4/28" to this paragraph for the reader's convenience.
- **L386–392 (Table 7)**: list the 4 fallback-activated cells in the table itself, with absolute cycle deltas. Forces reviewers to engage with the magnitude of "rescue".
- **L400 (§VI.C, observation (ii))**: "If multi-warm-start were merely a 48-shot search..., the BookSim-selected allocation could not strictly beat both baselines simultaneously on 79% of cells." This is a *partial* defense: a 48-shot random-policy ensemble would also beat the deterministic baselines on many cells. The defense holds against "fixed-initialization enumeration" but not against "search with any reasonable proposal distribution". Soften the claim or add the random-policy baseline.
- **L456 (λ sensitivity)**: "the RL-WS uplift over greedy *grows* under higher λ" — uplift deltas are 1–3 percentage points across single-run results. Flag as suggestive rather than statistically significant in absence of multi-seed variance. (Already done partly via "Acknowledging" tone, good.)
- **L487 (Limitations)**: limitation (iv) is well-written. Consider also adding limitation (ix): "the NL%=77 / NL%=50 deployment cutoffs were inspected on the same 28 cells used for evaluation; no held-out workload validates them." This is the iter-13 W3 issue still standing.

---

## Ratings (iter-14 vs iter-13)

| Dimension | iter-13 | iter-14 | Change Driver |
|---|---|---|---|
| Novelty | 2 | **2** | Three-step framing is clearer; PARL still not reproduced; NL%-as-classifier still novel-but-fitted. |
| Technical Quality | 2 | **3** | New §VI.C ablation, eq. (6) explicit, surrogate disclosure honest, low-NL claim recast. Held-out workload, workload-aware FBfly, multi-seed variance still missing — but the paper now does not overclaim what it has. |
| Significance | 2 | **2** | Headline numbers are now disclosed as MoE-driven (-3.2% non-MoE). Honest, but the practical takeaway shrinks correspondingly: a workflow that helps 4 cells dramatically and 18 cells modestly. |
| Presentation | 3 | **4** | Internal consistency (24.8/0.83/Fig 4 caption fixed); per-cell §VI.D lists all 4 MoE cells; ablation Table 7 is clean; limitations are calibrated. The C1-vs-abstract drift on low-NL and the b-conditioning silence are the two remaining presentation issues. |
| Overall | 2 | **3** | Calibrated honest paper with real but narrow contribution. |
| Confidence | 4 | **4** | Same. |

---

## Decision

**Borderline (lean Weak Accept)** — up from iter-13 Weak Reject.

Specifically: I would vote Weak Accept at DAC/DATE; I would vote Borderline-leaning-Weak-Reject at ISCA/MICRO. The asymmetry is because the surviving major weaknesses (post-hoc fitted classifier, no workload-aware FBfly, no multi-seed variance, PARL not reproduced) are venue-typical at DAC/DATE but venue-unusual for ISCA. The paper now does not lie about what it shows; the question is whether what it shows is enough.

What changed my vote from iter-13:

1. **Honest disclosure of MoE dependence at every claim site** (Limitation ii, §VI.D, Conclusion). The paper now stands on its actual evidence rather than over-amortizing one workload's effect.
2. **Per-cell §VI.D lists all four MoE cells**, making the cherry-picking objection no longer applicable.
3. **§VI.C ablation against `min(greedy, FBfly)` on 22/28 cells** is a real addition, even if it does not isolate REINFORCE from a 48-shot search ablation.
4. **Numerical inconsistencies (24.8/0.83/Fig 4 caption) all fixed**, restoring basic credibility.
5. **Surrogate's in-distribution status openly stated**; the safety claim is now correctly attributed to the BookSim fallback.

What would shift to clear Weak Accept:

1. Report ρ on non-MoE cells (single number, one paragraph).
2. Run a workload-aware FBfly variant (1 pp paragraph + 1 column in Table 6); even reporting "we tried, gap shrinks from -63 to -X but still significant" closes W2'.
3. Add 48-shot random-policy baseline to §VI.C ablation (1 row in Table 7).

What would NOT shift it without more work:

- Held-out workload validation of NL% cutoffs (likely needs new experiments).
- Multi-seed end-to-end RL retraining variance (compute-expensive).
- PARL reproduction (substantial engineering).

The first three (ρ_non-MoE, workload-aware FBfly, random-policy ablation) are each ~1 day of work and would close most of the surviving structural objections. As written, the paper is honest enough to deserve an opportunity but thin enough to lose at PC discussion against an aggressive reviewer who fixates on "MoE drives everything and FBfly is workload-blind".

**Final score: 3.0/5 (Borderline, leaning Weak Accept).**
