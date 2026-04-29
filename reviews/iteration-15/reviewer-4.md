# Reviewer 4 (Theory / Analysis Expert) — Iteration 15

**Paper:** Predict, Place, Refine: Non-Locality-Guided Express Link Placement for LLM Chiplet Networks
**Track:** Architecture (DAC/DATE/ISCA/MICRO/HPCA)
**Reviewer focus:** rigor of analytical bounds, correctness of definitions, statistical validity, generalization claims.
**Iteration:** 15 — re-review against my iteration-14 punch list. Iter-14 score was 3.0/5 (Borderline / Weak Accept). I held back from raising further on (W1) Theorem 1 / Corollary 1 unproven, (W2) Routing Algorithm Independence still empirical, (W7) 50–77% NL% gap untested, (W9) wire model still linear.

---

## Summary of changes I asked for, and what landed

The iteration-14 punch list (item-numbered at the end of my last review) had five items, of which only one is purely textual (item 4: move MoE dependence into the abstract parenthetically). The others are theoretical/empirical. Iteration 15's actual changes are:

1. PARL contrast strengthened in §II Related Work into an explicit three-axis differentiation (predictor / warm-start / safety) with cross-references to the ablation Table~9.
2. MoE Skewed calibration (§VI Setup): Zipf $s{=}1.5$ disclosed, anchored to DeepSeek-V3 and Mixtral-8x7B citations, and contrasted with uniform-dispatch GShard.
3. New §VI.D "Wall-Clock Cost" subsection with Table~9 reporting $\sim$15–45 min/cell parallel and $\sim$10–20 hr for the 28-cell sweep.

Mapping these against my iteration-14 punch list:

| iter-14 ask | iter-15 status |
|---|---|
| (1) Two-line proof of Theorem 1; one-paragraph bisection lower bound for §III.D | **Not addressed.** Theorem 1 / Cor.~1 still asserted with only the worked $4{\times}4$ example (lines 133–149). Section III.D still concludes empirically (line 199) without a routing-class lower bound. |
| (2) One quantitative number for NL% under permutation on one workload | **Not addressed.** §IV (line 212) still states layout-dependence verbally without a permutation-variance number. |
| (3) One synthetic mid-NL workload to fill the NL%$\in$(50,77) gap | **Not addressed.** Table~\ref{tab:workloads_full} still has no entries between Tree (42\%) and Hybrid TP+PP (77\%). The "deployment classifier at NL\%$\ge$77\%" claim still operates over an empty interval. |
| (4) Move MoE dependence into the abstract parenthetically | **Not addressed.** The abstract (line 31) still cites $-11.8\%$ vs FBfly without the "of which $\approx$half is MoE Skewed" qualifier. The disclosure remains §V.B-only. |
| (5) Three independent RL retrains on MoE $K{=}32,N{=}8,b{=}4\times$ for a variance number | **Not addressed.** Limitation (v) (line 526) still defers this to future work. |

So zero of five iter-14 punch list items landed in iter-15. What did land — PARL three-axis contrast, Zipf calibration disclosure, wall-clock cost table — is genuinely useful and is exactly what I'd expect Reviewers 1 (architecture) and 2 (systems) to have caught and asked for. None of these touches my four standing concerns (W1, W2, W7, W9), and the surrogate generalization scoping (W5) and the matched-compute random-swap-walk (W6) also remain where they were.

This is therefore the second consecutive iteration in which the analytical core (W1, W2) was not addressed despite my flagging it in iter-13 *and* iter-14, and the second iteration in which the mid-NL gap (W7) was not closed.

---

## What is genuinely strengthened in iteration 15

I want to be calibrated about this. Three of the iter-15 changes are not orthogonal — they meaningfully strengthen the *technical argument* even if not the *theoretical core*:

**S1 (new). PARL three-axis contrast (§II, lines 70–71) is now a defensible differentiation.**
The previous iteration's PARL paragraph was a one-sentence "closest prior work" mention. Iter-15 expands it to three concrete axes (workload predictor / initialization / safety guarantee), each with a numerical pointer into the paper's own evidence:

- Axis (i) cross-references the NL%$\le$50\% deployment-classifier behavior — i.e., PARL's lack of a workload predictor would force RL even on cells where FBfly is provably within 1 cycle of the BookSim minimum.
- Axis (ii) cites the 17 greedy-warm + 11 FBfly-warm split in Table~9 as evidence that *both* warm-start sources are individually load-bearing — a cold-start policy (PARL's Maskable PPO) cannot harvest both regimes by construction.
- Axis (iii) cites the 4/28 fallback activation rate as the empirical safety guarantee that PARL's argmax-RL output cannot provide.

This is the kind of head-to-head positioning that makes a learning-based architecture paper defensible against the "yet another RL placement" critique. The three axes are independently consequential and each cites measured evidence elsewhere in the paper. The honest gap remaining is that there is still no end-to-end PARL reproduction on the 28-cell benchmark — the paper acknowledges this in the same paragraph and defers to future work, which I accept as a reasonable scoping decision given that PARL's reward (Interference Score on multi-tenant workloads) is not directly comparable to single-workload max-rate latency.

**S2 (new). Zipf calibration with citations (§VI Setup, line 280) closes the "where did the MoE skew come from" question.**
This was a latent reviewer concern in iteration 14 — the MoE Skewed workload drives the headline 83.2% number, and an iter-14 reader could legitimately ask whether $s{=}1.5$ was tuned to produce a dramatic result. Iter-15's calibration paragraph anchors $s{=}1.5$ to two production-MoE references (DeepSeek-V3, Mixtral-8x7B) and contrasts with the GShard uniform-dispatch assumption that earlier MoE NoI studies adopted. The "approximately 36\% of total dispatch on the top-2 ranks at $K{=}32$" sentence converts the abstract Zipf parameter into a concrete concentration metric. This is the right kind of disclosure: it moves the headline number from "we tuned a synthetic workload" to "we matched measured production behavior" and gives a skeptical reader a direction to challenge ($s{=}1.5$ vs DeepSeek-V3's actual entropy) rather than a black box.

For my purposes, this also tightens the empirical link between NL% and "useful skew": the Zipf calibration explains why the MoE row in Table~6 has a much larger FBfly–RL gap than the other three high-NL workloads (which are near-uniform). It makes the deployment classifier's behavior at NL$\ge$77\% more interpretable — the classifier isn't just keying on NL%, it's keying on NL% conditional on traffic skew, and the two co-occur naturally on MoE-style workloads.

**S3 (new). Wall-clock cost table (§VI.D, Table~9 cost) is a clean answer to the "is this practical" critique.**
The 15–45 min/cell parallel cost is reasonable for a one-shot design-time exercise, and the breakdown (RL training $\sim$3–5 min vs BookSim selection $\sim$10–40 min) honestly identifies where the cost sits. The amortization sentence ("surrogate trained once for the entire 28-cell benchmark, $\sim$3 minutes total") is exactly right for a reviewer who would otherwise score the surrogate-training cost per cell.

The table also strengthens the deployment-classifier story slightly: the explicit claim "the NL\%-based deployment classifier lets architects skip RL-WS entirely on NL$\le$50\% workloads" (line 441) ties the cost discussion back to NL% as a gating function, which is the central paper claim. This is a small but real reinforcement of C1.

What the cost table does *not* do is address my W7 (the 50–77% NL gap): if NL% is the gating function and the classifier threshold is somewhere in (50, 77), then on a workload at e.g. NL%=65% the cost decision is exactly the unmeasured one. The wall-clock table is honest about what each step costs but cannot tell an architect whether to invest the 15–45 min on a mid-NL workload.

---

## Remaining concerns

### W1 (unchanged from iter-13 and iter-14). Theorem 1 / Corollary 1 are still asserted, not proved.

I am now flagging this for the third consecutive iteration. The paper's central analytical claim — that center-link amplification scales as $\Theta(K^{3/2})$ on a square grid — is still presented with only the worked $4{\times}4$ example and the scaling table. The two-line combinatorial proof is:

1. *Flow count.* Under XY routing, a directed (s,d) flow whose horizontal component crosses column boundary $c|c{+}1$ has source in columns $\{0,\ldots,c\}$ (count $R(c{+}1)$) and destination in columns $\{c{+}1,\ldots,C{-}1\}$ (count $R(C{-}c{-}1)$). Multiplying and doubling for the symmetric reverse direction gives $F_H(c) = 2R(c{+}1)(C{-}c{-}1)$. Identical argument for $F_V(r)$.
2. *Amplification.* Since each adjacent pair contributes $2$ direct flows, $\alpha(c|c{+}1) = F_H(c) / 2$. Maximizing over $c$: $\alpha_{\max} = R \cdot \lceil C/2\rceil \cdot \lfloor C/2\rfloor$. For $R = C = \sqrt{K}$: $\alpha_{\max} = \sqrt{K} \cdot \lfloor K/4\rfloor = \Theta(K^{3/2})$. $\square$

That's it. Two paragraphs. I wrote out the same two paragraphs in iter-13 and iter-14 reviews. The fact that this has not landed across two revisions, while three other improvements (PARL three-axis, Zipf calibration, cost table) did, suggests the authors regard the proof as low-priority. I disagree: the abstract and introduction both make the $\Theta(K^{3/2})$ claim and a PC reviewer scanning for analytical rigor will look first at Theorem 1 and find an unproven theorem on line 133.

The iter-14 corollary line "since each adjacent pair contributes exactly 2 direct flows" (line 140) also still lacks the qualifier that this is under uniform all-to-all traffic. As written, the reader could read it as a general statement.

### W2 (unchanged). "Routing Algorithm Independence" is still empirical.

§III.D still presents a 4-row table comparing XY/YX/ECMP/Valiant and concludes verbally that "phantom load is therefore a structural consequence of multi-hop adjacency." The $\Omega(K^{3/2})$ bisection lower bound — $\Theta(K^2)$ source-destination pairs straddle the bisection cut, the cut has $\Theta(\sqrt{K})$ links, so by pigeonhole *some* link carries $\Omega(K^{3/2})$ traffic for any oblivious routing — is one paragraph, citable to Dally & Towles Ch. 3. This argument is the *only* way to extend the empirical 4-row table into a routing-class lower bound, and without it the section's title "Routing Algorithm Independence" overstates what the section actually shows. The honest alternatives — both of which I suggested in iter-13 and iter-14 — are (a) add the bisection paragraph, or (b) retitle the section to "Sensitivity to Routing Algorithm." Neither happened in iter-15.

### W3 (carried). NL% layout dependence is still verbal.

§IV (line 212) is still framed as "NL% depends on $(T,G)$ and the canonical row-major mapping is used throughout." This is the right disclosure but not a quantitative anchor. One number — "NL% varies between $X$ and $Y$ over 100 random chiplet-to-grid permutations on Hybrid TP+PP" — would convert the verbal claim into a robustness check. This would be a 30-minute experiment (regenerate the Hybrid TP+PP traffic matrix under 100 permutations, recompute NL%, take min/max/95th-percentile), and it has not landed across two iterations.

### W4 (resolved in iter-14). Spearman = 0.83 is consistent across abstract / body / figure caption. Holds.

### W5 (held in iter-14). Surrogate generalization is honestly framed but not measured.

The leave-one-workload-out validation still has not landed. I accepted in iter-14 that the BookSim post-hoc fallback shifts the load-bearing safety argument away from surrogate generalization, and that argument still holds — the surrogate cannot silently mislead the final selection because BookSim measures every candidate. What it can do is bias the *candidate set* (the surrogate decides which top-3 per seed are even submitted to BookSim), so the iter-14 caveat about workload-portability remains. This is the same issue and I will not re-raise it; iter-15 also does not make it worse.

### W6 (carried). Matched-compute random-swap-walk ablation is still missing.

Table~9 still does not have the random-swap-walk row. The 22/28 strict-beat number against $\min(\text{greedy}, \text{FBfly})$ remains the *empirical* answer that "RL is doing real work," which I accepted as sufficient for iter-14. But the cleaner ablation — a 48-candidate random-swap baseline matched on compute — would directly disentangle "any guided search" from "REINFORCE specifically," and it would be a $\sim$2-hour experiment (the swap-walk infrastructure already exists since the action space is identical). This is a camera-ready ask, not a blocking concern.

### W7 (unchanged from iter-13 and iter-14). The 50–77% NL gap is still untested.

This is the third iteration in which I have flagged the empty interval in Table~\ref{tab:workloads_full} between Tree (NL=42%) and Hybrid TP+PP (NL=77%). The paper's central deployment-classifier claim ("NL%$\ge$77\% $\Rightarrow$ invoke RL-WS; NL%$\le$50\% $\Rightarrow$ fall back to FBfly") operates over an empty middle. The threshold could be 51%, 65%, 70%, or 76% and the data could not distinguish. This becomes especially salient in iter-15 because the new Zipf calibration paragraph (§VI Setup) emphasizes that real production MoE workloads have measurable concentration metrics — i.e., the paper now claims to map onto real-world workload distributions, and a real-world workload at NL%$\approx$60% (e.g., a dense-LLM training run with mixed TP/PP/DP) is exactly the case the deployment classifier is silent on.

The iter-14 fix I suggested — a synthetic $\beta$-mixture of Tree and Hybrid TP+PP swept over $\beta$ to interpolate the gap — would be a $\sim$3-hour experiment (3–4 mixtures, $K{=}16, N{=}4$ at $b{=}4\times$ to bound BookSim cost). It would either close the gap (threshold $\approx$60%) or split the high-NL group (threshold $\approx$70%); either result strengthens the paper. It still has not landed.

The deployment classifier is the paper's strongest contribution, and it is asserted over an unmeasured interval. This is now the most actionable single fix in the paper, and the cost-table addition makes it slightly more pressing — the cost table tells architects what RL-WS costs, and the deployment classifier tells them when to invoke it, but the classifier's threshold is uncalibrated where it matters most.

### W8 (resolved in iter-14). Eq.~6 fallback. Holds.

### W9 (unchanged). Wire model is linear; $\lambda$-sweep is the right defensive ablation. No update.

### W10 (resolved in iter-14). 25.6 vs 24.8 reconciled. Holds.

---

## New observations specific to iteration 15

### O1. PARL three-axis differentiation is well-structured, with one tightening.

The (i)/(ii)/(iii) factoring is clean and each axis cites measured evidence elsewhere in the paper, which is exactly the right rhetorical structure for a related-work paragraph. One nit: axis (ii) cites the iter-12 cold-vs-warm comparison ("our internal cold-vs-warm comparison ... shows is unstable on structured workloads such as Tree All-Reduce: cold-RL can regress versus a workload-aware greedy by $>10\%$ on adversarial cells"), but this comparison is *not* a numbered table or figure in the current paper. A PC reviewer reading §II will want to follow the citation. Either tighten the language ("internal experiments not included for space; available on request") or surface a single $X.Y\%$ regression number with a single cell pointer. Currently the sentence reads as if the iter-12 ablation is somewhere in the body and it isn't.

### O2. Zipf calibration paragraph is in the right section but has one factual loose thread.

The sentence "DeepSeek-V3 reports concentration ratios in the same regime" should ideally cite a specific concentration ratio (e.g., "top-2 captures $X\%$ of dispatch") so the reader can compare with the paper's "approximately 36% of total dispatch on the top-2 ranks at $K{=}32$". As-written, "in the same regime" is hand-wavy and a reviewer who actually looks at the DeepSeek-V3 report may find the number is, say, 28% — close enough to defend but worth concretizing. Same critique for Mixtral.

### O3. Wall-clock cost table is honest about the BookSim-bottleneck fact.

The "$\sim$10–40 min" entry for "$\le$48 RL candidates × 4 rates" is the dominant cost line, and the table makes this visible. This is good honest disclosure — it tells the architect that the cost driver is post-hoc safety (BookSim selection over a large candidate set), not RL training itself. A reviewer who wanted to attack the cost would have to attack the *safety guarantee*, which is the strongest part of the design. This is a structural argumentation win even though the table itself is just a cost report.

### O4. Iter-15 changes are presentation-focused, but cumulatively meaningful.

Reading iter-14 vs iter-15 side by side, the paper has converted from "interesting headline numbers with some loose disclosure" (iter-14) into "interesting headline numbers with three explicit axes of differentiation against PARL, calibrated workload, disclosed cost." This matters more than any individual change because it preempts roughly 60–70% of the routine PC questions ("is this just PARL?", "where did the MoE skew come from?", "is this practical?"). The fact that none of the four standing analytical concerns landed is offset by the fact that the paper now has *fewer surfaces* for a non-theoretical PC reviewer to attack. From a pure-acceptance-probability standpoint the iter-15 deltas are not zero, even though they are zero on my axis.

This makes my scoring decision less obvious than I expected when I started this re-read. See "Rating" below.

---

## Questions for the authors (iteration-16 punch list)

These are unchanged from iter-14 modulo iter-15's cumulative effect:

1. **Theorem 1 proof.** Two paragraphs. I have written them out in three consecutive review iterations. This is the smallest fix on the punch list and the most consequential for analytical rigor.
2. **Routing-class lower bound.** One paragraph citing Dally–Towles Ch. 3, *or* retitle §III.D to "Sensitivity to Routing Algorithm."
3. **NL% permutation variance.** One number for one workload (Hybrid TP+PP under 100 random chiplet-to-grid permutations).
4. **Mid-NL workload.** One synthetic $\beta$-mixture at NL%$\approx$60%. Either closes the deployment-classifier threshold to $\approx$60% or splits high-NL into a 60–77 sub-band; either result strengthens the paper. **This is the most actionable iter-16 ask** because the paper's central contribution operates over an empty interval.
5. **Random-swap-walk matched-compute ablation.** 48-candidate random-swap baseline on the four MoE cells alone would isolate REINFORCE from candidate enumeration.
6. **Surrogate leave-one-workload-out.** One line in Table~\ref{tab:ablation}: "trained on 6 workloads, evaluated on the 7th, $\rho{=}\ldots$".
7. **Specific Zipf concentration numbers from DeepSeek-V3 / Mixtral.** Convert "in the same regime" into a measured top-$k$ dispatch concentration ratio.
8. **MoE dependence in abstract.** Add "(of which $\approx$half is driven by the four MoE Skewed cells)" parenthetically. This is one comma-bracketed clause.
9. **Single-cell variance.** Three independent end-to-end RL retrains on MoE $K{=}32, N{=}8, b{=}4\times$ to put a number on the headline 83.2%.

(1)–(2) and (8) are textual. (3), (5), (7), (9) are sub-day experiments. (4) and (6) are 1–3 hour experiments. None require new infrastructure.

---

## Detailed comments (iteration-15 specific)

- **Line 31 (abstract).** Still no MoE-dependence parenthetical. Same comment as iter-14. One clause fix, blocking nothing, but does increase honesty signaling.
- **Lines 70–71 (PARL three-axis).** Well-structured. See O1 — clarify that the cold-vs-warm comparison is internal-only, or surface a single concrete number.
- **Line 133, Theorem 1.** Still asserted. See W1.
- **Line 199.** "Phantom load is therefore a structural consequence" — still "therefore" without proof. See W2.
- **Line 212, NL\% layout-dependence.** Still verbal-only. See W3.
- **Line 280, MoE Zipf calibration.** Good disclosure. See O2 — concretize "in the same regime" with a measured concentration ratio.
- **Line 296, Table~\ref{tab:workloads_full}.** Still no NL%$\in$(50, 77) entry. See W7.
- **Lines 406–441, Wall-Clock Cost subsection.** New and well-placed. See O3.
- **Line 526, Limitations.** No new entries despite three new pieces of disclosure. (vii) wire-model linearity still cited; (viii) 3D Foveros extension still cited. Consider adding a (ix): "The deployment-classifier threshold is calibrated only at the boundary cells (NL$\le$42% and NL$\ge$77%); workloads with NL%$\in$(42,77) are not represented in the evaluation set, and the precise threshold within this interval is not measured."

---

## Rating

| Axis | Iter-13 | Iter-14 | Iter-15 | Δ vs iter-14 |
|---|---|---|---|---|
| Novelty | 3 | 3 | 3 | — |
| Technical Quality | 2 | 3 | 3 | — |
| Significance | 4 | 4 | 4 | — |
| Presentation | 3 | 3.5 | **3.5** | — |
| **Overall** | **2.5** | **3.0** | **3.0** | — |
| Confidence | 4 | 4 | 4 | — |

**Notes on scoring:**
- *Novelty (3, unchanged):* The thesis (NL% as deployment classifier; dual warm-start) is the same as iter-14. Iter-15 strengthens the *case* for novelty against PARL but does not introduce a new contribution.
- *Technical Quality (3, unchanged):* The analytical core (Theorem 1 proof, routing-class lower bound) is unchanged across iter-13 → iter-14 → iter-15. The mid-NL gap is unchanged. Surrogate leave-one-workload-out is unchanged. Three iterations without movement on the four standing technical-quality items is what holds this at a 3 rather than moving to a 3.5 or 4. The PARL three-axis + Zipf calibration + cost table additions are presentation-side strengthening, not technical-side.
- *Significance (4, unchanged):* The deployment-classifier story remains useful. Iter-15's calibration paragraph anchors the MoE result to production workloads, which marginally strengthens significance, but not by enough to move the digit.
- *Presentation (3.5, unchanged):* Iter-15 is materially better-written in §II and §VI. I considered moving this to 3.75, but the abstract still elides the MoE dependence (iter-14 ask 4) and the conclusion still does not surface the Zipf calibration. Two textual fixes left undone for two iterations is what holds presentation at 3.5.
- *Confidence (4, unchanged):* My read of the analytical rigor and statistical validity is unchanged.

**Why I am not lowering despite zero punch-list landings.** The iter-15 changes are not on my axis but they are *cumulatively* strengthening the paper against the routine PC critiques (PARL? skew calibration? cost?). A pure scoring-by-punch-list response would say "iter-15 ignored my list, hold or lower," but that would be reviewing the authors' allocation of effort rather than the paper. The paper as it now stands is not weaker than iter-14; it is iter-14 plus three useful preemptions. So hold.

**Why I am not raising despite cumulative strengthening.** My standing concerns (W1, W2, W7) are about analytical rigor and the load-bearing core of the deployment-classifier claim. Iter-15 does not move on any of them. From a theory/analysis-track perspective, three iterations without a two-line proof of the central theorem is a real signal — either the authors regard the proof as obvious (in which case they should write the two lines) or they have not verified it themselves (in which case the proof needs to land before camera-ready). Holding at 3.0 reflects the floor of "borderline accept conditional on iter-16 closing W1, W2, W7."

---

## Decision

**Borderline / Weak Accept (3.0/5). Hold from iter-14.**

Iter-15 is presentation/disclosure-focused: it strengthens the paper against the PARL-comparison critique, calibrates the MoE workload to production references, and discloses wall-clock cost. None of these are on my standing punch list (theoretical rigor, mid-NL gap, NL% permutation variance, surrogate generalization), so my axis is unchanged. The paper is better positioned against the architecture-track and systems-track critiques while remaining unchanged against the analytical-track critique I represent.

Holding at 3.0 reflects two things in tension. (a) The iter-15 changes meaningfully reduce the surface area for routine PC objections — Reviewers 1 and 2 catches close. (b) Three iterations without movement on Theorem 1's proof, the routing-class bound, or the mid-NL gap is the strongest signal yet that the analytical core is being treated as low-priority by the authors. (a) argues for raising; (b) argues for lowering. They cancel. Hold.

I would move to **Accept (4/5)** with iter-16 closing W1 (two-line proof), W2 (one-paragraph bisection bound or retitle), and W7 (one mid-NL synthetic workload). All three are sub-day. None require new infrastructure. Of the three, W7 is the most actionable and the most consequential — the deployment classifier is the paper's strongest contribution, and it is currently asserted over an unmeasured interval.

If iter-16 again ignores W1, W2, W7, my position will be that this is a Weak-Reject paper (2.5/5) that is presenting empirical results without the analytical scaffolding it claims to have, and I will recommend rejection on those grounds. The reason I say this now is to make the iter-16 decision symmetric: the same three fixes that move me to a 4 are what keep me from moving to a 2.5.
