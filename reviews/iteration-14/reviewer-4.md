# Reviewer 4 (Theory / Analysis Expert) — Iteration 14

**Paper:** Predict, Place, Refine: Non-Locality-Guided Express Link Placement for LLM Chiplet Networks
**Track:** Architecture (DAC/DATE/ISCA/MICRO/HPCA)
**Reviewer focus:** rigor of analytical bounds, correctness of definitions, statistical validity, generalization claims.
**Iteration:** 14 — re-review against my iteration-13 punch list.

---

## Summary of changes I asked for, and what landed

In iteration 13 I gave a Weak Reject (2.5/5) and listed six concrete fixes that would move me to Weak Accept. Iteration 14 addresses three of them cleanly, partially addresses one, and leaves two open. Specifically:

| iter-13 ask | iter-14 status |
|---|---|
| (1) Prove Theorem 1; prove or cite a routing-class lower bound for §3.4 | **Not addressed.** Theorem 1 / Cor. 1 are still asserted with only the worked $4{\times}4$ example. §3.4 is unchanged in structure (XY/YX/ECMP/Valiant table, then a verbal generalization). |
| (2) Clarify NL%'s layout dependency and report variance under permutation | **Partially addressed.** Section IV (line 212) now states explicitly that NL% depends on $(T,G)$ and that the canonical row-major mapping is used throughout, with a useful framing that layout-aware co-location is "exactly what the predictor is telling architects to look for." No quantitative permutation variance, but the conceptual gap is closed. |
| (3) Reconcile Spearman value (0.83 / 0.825 / 0.74) | **Addressed.** Now consistently $\rho{=}0.83$ ($p{=}6.8\times 10^{-8}$) in abstract (line 31), body (line 215), and figure caption (line 352). Internal numerical consistency is now clean. |
| (4) Report leave-one-cell-out (or leave-one-workload-out) surrogate validation | **Disclosure rather than fix.** §IV.B now explicitly says the 80/20 split is uniform-random over all cells, that $\rho{=}0.928$ is therefore in-distribution, and that cross-cell generalization is *not* claimed (line 257, line 487 limitation iv). The safety guarantee is shifted to the post-hoc BookSim fallback Eq.~6. This is intellectually honest; the actual leave-one-cell-out experiment is still missing but the load-bearing role of the surrogate has been correctly downsized. |
| (5) Random-swap-walk ablation isolating REINFORCE from candidate enumeration | **Partially addressed.** The new ablation (Table~9) does not run a matched-compute random-swap-walk, but it *does* show 22/28 cells where raw RL strictly beats $\min(\text{greedy}, \text{FBfly})$ (line 384). That is non-trivial: a 48-shot enumerator centered exactly on greedy and FBfly cannot strictly beat both deterministic baselines on 79% of cells unless the policy gradient is moving the candidate distribution off the warm-start. So while the ideal ablation is missing, an *empirical* answer to "is RL doing real work" is now in the paper. |
| (6) Mid-NL workload (or explicit threshold disclosure) for the 50–77% gap | **Not addressed.** Table~5 still has a gap between Tree (42%) and Hybrid TP+PP (77%); no NL%$\in$(50,77) workload was constructed. The abstract (line 31) and §V.B still operate the classifier at the 77% threshold without acknowledging that 50–77% is unevaluated. |

So roughly 3 fixed, 2 partially fixed, 2 unfixed. In iteration 13 I said the six together would move me to Weak Accept; what landed is closer to "halfway across the gap." I now lean **Borderline / Weak Accept**, with the lean depending on how the chairs weight the unproven theorem.

The paper is also materially better in places I did not ask about: the fallback rule is now stated as a clean equation $L_{\text{RL-WS}} = \min(L_{\text{greedy}}, L_{\text{FBfly}}, L_{\text{RL-best}})$ (Eq.~6), and the new ablation Table~9 is the kind of diagnostic table I missed in iteration 13. The "BookSim-best source" row (greedy-warm 17/28 vs FBfly-warm 11/28) is exactly the data needed to defend the dual-warm-start design.

---

## What is now genuinely defensible

**S1 (carried).** The closed-form max-load result is still correct under the stated assumptions. The $4{\times}4$ worked example ($\alpha{=}16$) and the scaling table (Table~2) remain consistent.

**S2 (improved).** NL% is now defined as $\mathrm{NL\%}(T, G)$ and the layout dependence is stated in the body (line 212). The framing — "a layout that drops NL% below the deployment threshold is exactly what the predictor is telling architects to look for" — is unusually mature. It converts what looked like a definitional bug into a feature of the framework.

**S3 (improved).** The deployment-classifier framing is now backed up by Table~6's per-row breakdown (4/4 strict beats on each high-NL workload, 8/12 strict beats with documented fallback rescues on low-NL) and by the explicit MoE-vs-non-MoE decomposition in §V.B (line 414, "$-11.8\%$ overall vs $-3.2\%$ excluding MoE"). This is the most honest discussion of "where do the headline numbers actually come from" I have seen in this paper across iterations.

**S4 (improved).** The post-hoc BookSim fallback Eq.~6 now does *real* work. Table~9 shows it activates on 4/28 cells, with rescue magnitudes 0.22–0.87 cycle. The phrase "the fallback therefore turns what would be a $-0.87$ cycle worst-case raw-RL regression into a measured zero-regression guarantee" (line 402) is exactly the right load-bearing statement for the safety claim. This is a clean answer to my W8 from iteration 13: greedy and FBfly are *both* in the candidate set and the BookSim argmin therefore trivially dominates them.

**S5 (carried).** The $\lambda$-sensitivity sweep (Table~10) still does its job. The text now also softens the language around monotonicity correctly ("$+3.1\,\text{pp}\!\to\!+5.8\,\text{pp}$" on Uniform; "$+4.4\,\text{pp}\!\to\!+4.9\,\text{pp}$" on MoE — these are now stated as point values, not asserted as monotone in the prose).

---

## Remaining concerns

### W1 (unchanged from iter-13). Theorem 1 / Corollary 1 are still asserted, not proved.

This was the first item on my iteration-13 punch list and it has not been addressed. Specifically:

1. The expressions $F_H(c) = 2R(c{+}1)(C{-}c{-}1)$ and $F_V(r) = 2C(r{+}1)(R{-}r{-}1)$ still need the explicit two-line combinatorial argument: under XY routing, the count of (s,d) pairs whose horizontal-then-vertical path crosses the column boundary $c|c{+}1$ equals (sources in columns $0\ldots c$, $R(c{+}1)$ of them) $\times$ (destinations in columns $c{+}1\ldots C{-}1$, $R(C{-}c{-}1)$ of them), doubled for both traffic directions.
2. The "each adjacent pair contributes exactly 2 direct flows" sentence (line 140) still needs the qualifier that this is under the *uniform all-to-all* assumption — the corollary as written reads as if it held for any traffic.
3. The $\Theta(K^{3/2})$ language in the abstract still describes the *worst-link* amplification, not the *typical* amplification. Table~2 row "Avg $\alpha$" actually grows as $\Theta(K)$ (38.2 at $K{=}32$, 96.0 at $K{=}64$), not $\Theta(K^{3/2})$. Either restrict the abstract to "worst-link amplification scales as $\Theta(K^{3/2})$" or carry both statements.
4. Still no statement on which boundary attains the max for non-square $R\ne C$.

This is a 5-line fix and I am genuinely puzzled it did not land in iteration 14. My iteration-15 patience is finite on this point.

### W2 (unchanged from iter-13). "Routing Algorithm Independence" is still empirical, not analytical.

Section III.D is still a 4-row table over three routing schemes with the verbal conclusion "Phantom load is therefore a structural consequence of multi-hop adjacency, not an artifact of one routing algorithm" (line 199). I asked for either a retitle to "Sensitivity" or a one-paragraph bisection-bandwidth lower bound applying to *any* oblivious routing on a 2D mesh. Neither happened. The bisection argument is one paragraph: under uniform all-to-all on a $\sqrt{K}\times\sqrt{K}$ grid, $\Theta(K^2)$ source-destination pairs straddle the bisection cut, which has $\Theta(\sqrt{K})$ links, so *some* link must carry $\Omega(K^{3/2})$ traffic regardless of the routing algorithm. Citing Dally & Towles Ch. 3 makes this a one-line addition.

This is the second 5-line fix that did not land. Together with W1, it leaves the analytical core informal in a way that an analytically-minded PC reviewer will fixate on.

### W3 (newly partial). NL% layout dependence is now disclosed but not quantified.

Section IV is much improved (line 212): NL%$(T,G)$ depends on the layout, the canonical row-major mapping is stated, and layout-aware co-location is reframed as orthogonal future work. This closes the conceptual gap I raised. What is still missing is a single number for $\mathrm{Var}_\pi[\mathrm{NL\%}(T, G_\pi)]$ on a representative workload (e.g., Hybrid TP+PP) under random chiplet-to-grid permutation. Even one line — "for Hybrid TP+PP, NL% varies between $X$% and $Y$% over 100 random permutations, all of which place the workload in the high-NL group" — would convert the verbal claim into a quantitative robustness check. As-is the framing is defensible but unverified.

### W4 (resolved). Spearman reconciliation.

Now consistently 0.83 across abstract / body / figure caption. Good. The paper still does not state how ties were handled or report a Fisher-z 95% CI, but both are minor compared to the original three-way inconsistency. I will not re-raise unless the deployment-threshold gap (W7) is contested.

### W5 (downsized but not closed). Surrogate generalization is honestly framed but not measured.

§IV.B now explicitly says "the surrogate is a well-matched in-distribution reward model for refinement, not a held-out generalization predictor" (line 257), and Limitation (iv) repeats this. This is the correct intellectual response: rather than over-claim cross-cell generalization, the paper has shifted the load-bearing safety argument to the post-hoc BookSim fallback. I accept this as a defensible scoping decision.

What still bothers me a little is that the surrogate is what *generates the candidates* — even if the BookSim fallback rescues us against silent regression, it cannot rescue us against *missed* candidates that the surrogate's bias prevented from being surfaced in the top-3. A leave-one-workload-out validation would tell us whether the surrogate's candidate-selection is workload-portable, which directly affects what RL-WS would do on unseen LLM workloads (e.g., a future MoE variant with different skew). I will not block on this for iter-14 since it is honestly disclosed, but it remains the strongest argument against deploying RL-WS on a workload not in the training set.

### W6 (partially addressed). RL is doing work, but the matched-compute random-swap-walk ablation is still missing.

Table~9 row 2 ("Raw RL vs $\min(\text{greedy},\text{FBfly})$ baseline: Strict beat 22/28") is the most informative single number added in this revision. It is a tighter test than I formulated in iteration 13: a 48-candidate enumerator centered exactly on the warm-start solutions cannot strictly beat both deterministic baselines simultaneously on 79% of cells unless the search has actually moved off the initialization. So the policy-gradient component is doing work in aggregate.

The matched-compute random-swap-walk ablation is still cleaner — it would directly tell us *how much* of the 22/28 is "any guided search" vs "REINFORCE specifically" — but Table~9 is a sufficient first-line answer. The strongest version of the paper still adds a "Random swap walk (no policy gradient)" row to Table~9 with the same 48-candidate budget; I urge the authors to attempt this for camera-ready if accepted.

### W7 (unchanged from iter-13). The 50–77% NL gap is still untested.

Table~5 still shows nothing in NL%$\in(50, 77)$. The abstract (line 31), §V.B (line 324), and conclusion (line 493) all operate the classifier at the 77% threshold. The deployment-classifier story would be much stronger with even a single synthetic mid-NL workload — e.g., a parametric mixture $\beta \cdot \text{Tree} + (1-\beta) \cdot \text{Hybrid TP+PP}$ swept over $\beta$ to interpolate the gap. Right now the threshold could be 51%, 65%, or 76% and the data could not distinguish.

The paper does not even acknowledge this as a limitation in §V.B or in the limitation list. This is the most actionable iteration-15 fix and it really should have been in iteration 14.

### W8 (resolved). Eq.~6 properly defines the candidate set.

The fallback rule is now explicitly $L_{\text{RL-WS}} = \min(L_{\text{greedy}}, L_{\text{FBfly}}, L_{\text{RL-best}})$ at the measured-latency level. Line 391 ("Worst-case after fallback: 0.0%") makes the safety guarantee concrete. This is exactly the framing I asked for.

### W9 (unchanged). Wire model is still linear.

Limitation (vii) acknowledges this and the $\lambda$-sweep is the right defensive ablation, but no IR-drop, repeater, or via-cost discussion is added. I will not block on this — it is appropriately scoped to future work — but in iteration 13 I noted that the $d{=}4$ cost model is what determines whether RL-WS's preference for distance-4 expresses on MoE Skewed is realistic. Camera-ready could reasonably add a one-paragraph "wire-model fidelity" discussion citing a CoWoS PDK or Florets's wire model.

### W10 (resolved). Greedy 25.6 → 24.8 is reconciled.

Numerical inconsistencies that I flagged in iteration 13 (greedy mean of 25.6% vs 24.8%, etc.) are gone. Table~6 row "Overall" reads $+24.8\%$ for greedy, $+27.1\%$ for FBfly, $+35.6\%$ for RL-WS, and these match abstract / body / conclusion. Good.

---

## New observations specific to iteration 14

### O1. The new ablation Table~9 is well-designed, with one nit.

The "BookSim-best source" decomposition (greedy-warm RL: 17/28; FBfly-warm RL: 11/28) is exactly the diagnostic the paper needed. One nit: the label "Strict beat" against $\min(\text{greedy}, \text{FBfly})$ (22/28) and "Loss by $\le$0.9 cycle" (4/28) and "Tie" (2/28) sums to 28, which is correct. But the four-way breakdown of the 4 fallback-active cells (line 402: Tree $K{=}16,N{=}4$; Pipeline $K{=}16,N{=}4$; Hybrid TP+PP $K{=}16,N{=}4$; Tree $K{=}32,N{=}8$) is interesting — three of them are at $K{=}16, N{=}4$, the smallest interesting grid. Worth noting in the text that the fallback is cell-size-correlated.

### O2. The new "Why mesh + express, not switch-based" paragraph (line 449–450) is good but slightly off-topic.

I do not object to its presence — it preempts a reasonable PC question — but it sits oddly in §VI Discussion. A reviewer scanning Discussion expects design-trade-off content; the switch-fabric exclusion reads as a Background/Related Work item that drifted south. I would move it to §II or to a footnote in §III.A.

### O3. The dual-warm-start framing is now genuinely the central contribution.

Reading iteration 14, the paper's strongest contribution is *not* "we proved $\Theta(K^{3/2})$" (which is a reformulation of textbook bisection) and not "we use REINFORCE" (which is methodologically incremental), but "we discovered that greedy and FBfly are complementary on disjoint workload regimes, and dual-warm-start lets a single RL pipeline harvest both without an explicit pre-classifier." This is a clean, novel, and load-bearing contribution. I would consider sharpening the abstract around it: the current first sentence emphasizes NL% as the predictor, but C2 (dual warm-start) is doing as much work in Table~9 as C1 (NL%).

### O4. The conclusion slightly over-promises.

Line 493: "RL-WS still strictly beats FBfly on 8/12 with smaller margins ($\le$2 cycle), and the 4 cells where it does not are recovered by a post-hoc BookSim fallback." This conflates "does not strictly beat FBfly" with "would regress without fallback." Per Table~9, fallback activates on 4 cells total (some of which are *not* in the low-NL group); per Table~6, the 4 non-strict-beats on low-NL split into 2 ties + 2 minor losses. The conclusion should say "the 2 minor losses" rather than "the 4 cells where it does not." Pedantic, but the reviewer pool will pedant this.

---

## Questions for the authors (iteration-15 punch list)

1. **Theorem 1 proof.** Two lines; please add. Same combinatorial argument I described in iter-13 W1.
2. **Routing-class lower bound.** Either retitle §III.D or add the one-paragraph bisection argument citing Dally–Towles Ch. 3.
3. **NL% permutation variance.** One number for one workload (Hybrid TP+PP under 100 random permutations is fine). The verbal claim that NL% is "stable enough to act as a deployment classifier" needs at least one quantitative anchor.
4. **Mid-NL workload.** Construct one synthetic NL$\approx$60% workload (e.g., $\beta \cdot$ Tree $+ (1{-}\beta) \cdot$ Hybrid TP+PP at the right $\beta$) and report the FBfly–RL gap. If the gap opens at 60%, your threshold is closer to 50%; if it does not, your threshold is closer to 77%. Either result strengthens the paper.
5. **Random-swap-walk ablation.** 48-candidate matched-compute random search on the four MoE cells alone would be sufficient to confirm that REINFORCE is contributing on the cells that drive the headline numbers.
6. **Surrogate leave-one-workload-out.** One line: "trained on 6 workloads, evaluated on the 7th" with the resulting $\rho$. Even a degraded $\rho{=}0.6$ would be honest and informative; the current "in-distribution only" disclosure is correct but unenlightening.
7. **MoE dependence in headline.** The $-11.8\%$ overall vs $-3.2\%$ ex-MoE split is now disclosed in §V.B but the abstract still says "+35.6\%" without the qualification. Consider adding "(of which approximately half is driven by MoE Skewed cells)" parenthetically. This is honesty signaling that helps with skeptical PC members.

---

## Detailed comments (iteration-14 specific)

- **Line 31 (abstract).** "RL-WS strictly beats FBfly on 24/28 cells (2 ties, 2 minor losses $\le$0.9 cycle); the best single cell reaches $-83.2\%$ latency vs FBfly on MoE Skewed". This is now consistent with body — good. Suggested addition: "(of which $\approx$half of the headline gap is driven by the four MoE Skewed cells)" to preempt the cherry-picking critique.
- **Line 47.** "At $K{=}32$, this amplification reaches 64$\times$ on center links" — Table 2 confirms (4×8 row, max $\alpha$=64). Consistent.
- **Lines 133–149.** Theorem environment unchanged from iter-13. See W1.
- **Line 142.** $\alpha_{\max} = R \cdot \lceil C/2 \rceil \cdot \lfloor C/2 \rfloor$ still without statement of which boundary attains the max. Specifically: for $R{\le}C$, the max is at $c = \lfloor C/2 \rfloor - 1$ (the column boundary closest to the centerline). State.
- **Line 199.** "Phantom load is therefore a structural consequence" — still "therefore" without proof. See W2.
- **Line 212.** "NL\% depends on \textit{both} the demand matrix $T$ and the chiplet-to-grid mapping $G$" — good. Add one sentence: "Empirically, NL\% varies by $X$pp under random chiplet-to-grid permutation on Hybrid TP+PP, all of which keep the workload in the NL$\ge$77\% group."
- **Line 215.** "$\rho=0.83$" — consistent with abstract and figure. Good.
- **Line 257.** "the surrogate is a well-matched in-distribution reward model for refinement, not a held-out generalization predictor" — clean disclosure. Recommend repeating this exact phrasing in §V.B once for emphasis (right now it only appears once).
- **Lines 380–390, Table~9.** Useful. One nit: "Loss by $\le$0.9 cycle (would regress)" is 4/28; the cells are listed in line 402. Cross-reference the table row to the line-402 list for clarity.
- **Line 414.** "$-11.8\%$ excluding MoE the per-cell mean reduction across the remaining 24 cells is $-3.2\%$" — this is the most important honesty-signal in the paper. Move it earlier, ideally to §V.A or even abstract.
- **Line 487, Limitation (iv).** "the safety mechanism that does not depend on cross-cell surrogate generalization is the post-hoc BookSim fallback" — exactly right framing.
- **Line 487, Limitation (v).** "a multi-run variance study … is left to future work" — same as iter-13. The headline 83.2% on MoE $K{=}32, N{=}8, b{=}4\times$ depends on this; one cell, three independent end-to-end RL retrains, three BookSim numbers. This is a half-day experiment, not future work. Strongly recommend for camera-ready.

---

## Rating

| Axis | Iter-13 | Iter-14 | Δ |
|---|---|---|---|
| Novelty | 3 | 3 | — |
| Technical Quality | 2 | **3** | +1 (Spearman reconciled, fallback equation explicit, ablation table added, layout-dependence disclosed) |
| Significance | 4 | 4 | — |
| Presentation | 3 | **3.5** | +0.5 (numerical inconsistencies gone, ablation diagnostic added, MoE dependence honestly disclosed) |
| **Overall** | **2.5** | **3.0** | +0.5 |
| Confidence | 4 | 4 | — |

**Notes on scoring:**
- *Novelty (3, unchanged):* NL% as a deployment classifier and dual-warm-start initialization are genuine novelties; the analytical content remains a reformulation of bisection-style reasoning.
- *Technical Quality (3, up from 2):* The Spearman three-way inconsistency is gone, the fallback rule is now Eq.~6, and the new Table~9 ablation provides the missing diagnostic for whether RL is doing real work. The layout-dependence of NL% is now disclosed. What is still missing — Theorem 1 proof, routing-class lower bound, mid-NL workload — keeps this short of a 4.
- *Significance (4, unchanged):* The deployment-classifier story has held up under iteration; the MoE dependence is honestly disclosed; the work would be useful design-time guidance for a chiplet architect.
- *Presentation (3.5, up from 3):* Internal numerical consistency is now clean. Ablation table is well-designed. Conclusion still over-promises slightly (O4) and abstract still elides the MoE dependence. These are easy fixes.
- *Confidence (4, unchanged):* I am confident in the analytical and statistical assessment; the experimental numbers I take at face value modulo the documented in-distribution scope of the surrogate.

---

## Decision

**Borderline / Weak Accept (3.0/5).**

In iteration 13 I said six fixes would move me to Weak Accept. Iteration 14 delivers about 3.5 of them: the Spearman reconciliation, the fallback equation, the layout-dependence disclosure, and a partial RL-vs-baselines ablation. What is still missing is the proof of Theorem 1, the routing-class lower bound, the mid-NL workload, and the leave-one-cell-out surrogate validation.

The thesis is now defensible and the paper presents itself honestly: the MoE dependence is disclosed in the body, the surrogate's in-distribution scope is stated, and the safety guarantee is a measured BookSim minimum rather than a surrogate prediction. The biggest remaining weakness is that the analytical core (Theorem 1 / routing independence) is still informal in a way that an analytically-minded PC reviewer can hammer. If the chairs weight the architecture-track preference for measured-result rigor more than the analytical-track preference for proven theorems, this is a clear Weak Accept. If they weight them equally, it is borderline.

I would move to **Accept (4/5)** with these iteration-15 fixes, all of which are textual or one-off:
1. Two-line proof of Theorem 1; one-paragraph bisection lower bound for §III.D (or retitle to "Sensitivity").
2. One quantitative number for NL% under permutation on one workload.
3. One synthetic mid-NL workload, even if it is a $\beta$-mixture of Tree and Hybrid TP+PP.
4. Move the MoE dependence into the abstract parenthetically.
5. Three independent RL retrains on MoE $K{=}32,N{=}8,b{=}4\times$ for a single-cell variance number.

None of these require new infrastructure. (1)–(4) are textual; (5) is a half-day on a single cell. If they land, my score is +1 and the paper crosses the architecture-track acceptance bar comfortably.
