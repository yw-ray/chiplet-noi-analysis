# Review — Reviewer 1 (Architecture Expert), Iteration 14

## Summary
Iteration 14 is a meaningful tightening pass on the iter-13 draft rather than a structural rewrite. The Predict–Place–Refine framing, the $\Theta(K^{3/2})$ phantom-load argument, the routing-independence study, and the 28-cell BookSim sweep are all retained. What changed are presentation-level items I previously flagged as internal inconsistencies, plus one new section (§VI.C Ablation) and one new equation (Eq.~(6)) that materially strengthen the central claim that the post-hoc BookSim fallback gives a *measured* zero-regression guarantee. Specifically, the Spearman $\rho$ value is now consistently $0.83$ across Abstract / §IV / Fig.~4 caption / Conclusion (was $0.825$ vs $0.74$ in iter-13), the greedy mean is now uniformly $24.8\%$ (was $25.6\%$ in some places, $24.8\%$ in others), the ablation table breaks the BookSim-selected allocations into 17 greedy-warm vs 11 FBfly-warm sources, the $22/28$ raw-RL strict beat against $\min(\text{greedy},\text{FBfly})$ is reported, and the fallback's $4/28$ activations with $0.22$–$0.87$ cycle rescue magnitude are now an explicit table row tied to a labeled equation. The C2 contribution bullet is also rewritten in concrete terms ("greedy +61.0\% on MoE, FBfly +35.6\% on Uniform Random") instead of the more abstract iter-13 phrasing. The MoE-dominance honesty (excluding MoE, the per-cell mean reduction is $-3.2\%$) is now stated in both §VI.D and the limitations list rather than only in the per-cell discussion. Together these changes close most of my iter-13 *presentation* concerns. However, the two architecture-venue-critical gaps remain: there is still no head-to-head numerical comparison against PARL, and the physical-overhead section is still asserted CoWoS-class wire-length numbers without per-method wire-mm$^2$ accounting. I therefore raise the score by half a point, but not further.

## Strengths

1. **[S1, retained] The structural argument is real and well-presented.** Section~3 (Theorem~1 / Corollary~1 with the $\Theta(K^{3/2})$ scaling) and the routing-independence study in Table~2 do something most chiplet-NoI papers miss: they decouple the *topological* tax of multi-hop adjacency from any specific routing policy. The closed-form max-amplification example on the 4×4 grid (line 151, $\alpha=16\times$) makes the bound easy to sanity-check.

2. **[S2, retained] NL% as a single static, simulation-free predictor at the right level of abstraction.** The pre-routing-demand-matrix definition (Eq. lines 207–210) and the $\rho=0.83$ pooled correlation across 28 cells is exactly the kind of design-time knob a chiplet planner can compute from a workload trace before standing up BookSim. The sharper iter-13 claim — that NL% predicts the *FBfly–RL margin*, not just absolute saving — is now reinforced by the new ablation table showing the warm-start source distribution.

3. **[S3, strengthened] The multi-warm-start design with post-hoc BookSim selection is now formalized as a guarantee.** Iteration~14 adds Eq.~(6) $L_{\text{RL-WS}} = \min(L_{\text{greedy}}, L_{\text{FBfly}}, L_{\text{RL-best}})$ at the measured-latency level. Previously this was prose; now it is a labeled equation referenced from both Section~5.2 and the limitations list. The new §VI.C ablation (Table~7 in iter-14, my Table~7 reference) further reports the activation rate (4/28 cells) and the per-cell rescue magnitude (0.22–0.87 cycle), turning what was an abstract claim into an instrumented one. This is the right way to defend "your RL might silently regress" — and it is now empirically load-bearing rather than rhetorical.

4. **[S4, new in iter-14] The ablation breakdown directly answers "is the RL doing real work?".** Table~7 reports that on 22/28 cells the RL-trained allocation strictly beats the per-cell measured minimum of greedy and FBfly, with seed-source split 17 greedy-warm / 11 FBfly-warm BookSim-best selections. This is the cleanest possible answer to the iter-13 concern that multi-warm-start was just a 48-shot search around fixed initializations: a 48-shot search around fixed initializations cannot strictly beat *both* baselines on 79% of cells. Combined with the per-cell honesty in §VI.D about MoE-dominance, the headline numbers are now defensible against the obvious "are you just selection-biasing?" pushback.

## Weaknesses

1. **[W1, retained from iter-13] The express-link physical model is still too thin for an architecture venue.** Table~8 (now Table~9 in iter-14, "Physical Overhead of Express Links") still lists wire length / area / power / latency for $d{=}1\!\dots\!4$ as "CoWoS-class estimates" without a derivation, a citation to a wire-delay model (Bakoglu, ITRS, recent CoWoS-S/L characterization), driver/repeater assumption, or via penalty. The maximum express distance $D$ is still never reported per cell — line 223 says "Manhattan distance $d \in [2, D]$" and Table~9 stops at $d{=}4$, but the experiments use $K{=}32$ grids where Manhattan distances reach 9. Iteration 14 added language about "fixed canonical mapping" and "layout-aware NL% minimization is complementary direction" — that addresses NL%-layout-dependence but not the underlying physical-model thinness. For DAC/DATE this is the single most important remaining fix.

2. **[W2, retained from iter-13] No head-to-head against PARL, despite PARL being explicitly named as the closest prior work.** The iter-14 paper still defers PARL to "qualitative positioning in Table~1" (line 71) and the limitations list now includes it explicitly as item (vi): "PARL targets a complementary problem ... we position it qualitatively instead of attempting a head-to-head reproduction." This is a more honest framing than iter-13 but does not address the substance of the concern: PARL's *placement decisions* — which non-adjacent pairs receive express links under a budget — are directly comparable on the 28 cells here, and the RL-WS surrogate machinery means a fast evaluator already exists. Without a numerical PARL bar in Table~6, the central claim "RL-WS strictly beats the strongest learned baseline" remains unsupported; FBfly is a *heuristic* baseline, not the strongest learned placer. For a workshop or DATE-Friday-poster this might suffice; for the full DAC/DATE architecture track it does not.

3. **[W3, retained from iter-13] The architecture-level cost accounting is still workload-blind in exactly the place it should not be.** Section~6.5 (now §VI.E "Physical Overhead", lines 420–439) still frames RL-WS as "inheriting the same per-link overhead as greedy" because both consume the same total link budget. But the *distance distribution* of the chosen express links matters enormously for interposer area: the MoE Skewed mechanism described on line 414 reallocates capacity onto a few heavy long-distance pairs (potentially $d{=}5+$), while FBfly spreads links over $d{=}2$ row/column shortcuts. The paper still does not report (a) the per-method distribution of express-link distances, (b) the total wire-mm$^2$ per method, or (c) the resulting Pareto plot in (wire-mm$^2$, latency) space. The $-83.2\%$ headline cannot be converted into a fair cost-per-performance ratio without these. The MoE-honesty disclosure ("excluding MoE, $-3.2\%$") is welcome and partially mitigates the concern by lowering the headline gap, but it does not provide the physical-cost picture.

4. **[W4, partially closed; minor residue] The $-5.3\%$ low-NL margin claim in the abstract is not directly readable from Table~6.** The iter-14 abstract says low-NL cells "still strictly beat FBfly on 8/12 with max $-5.3\%$ margin." Table~6 reports per-workload means of $-0.8\%, -3.1\%, -2.4\%$ on Tree, Ring, Pipeline. The $-5.3\%$ is presumably a per-cell maximum within those 8 wins, but it is not exposed in any table. A one-line footnote in Table~6 listing the per-cell max would close this.

## Questions for Authors

1. **[Q1, retained from iter-13]** What is the maximum express distance $D$ in each of the 28 cells, and how is it set? Is it a fixed constant, a function of $\sqrt{K}$, or a per-cell beachfront/PHY budget? Please report (a) $D$ used per cell, (b) the distribution over $d$ of express links chosen by greedy, FBfly, and RL-WS, and (c) the resulting total wire-mm$^2$ per method. Without this, Table~9 (physical overhead) cannot be tied back to the placements actually used in Table~6.

2. **[Q2, retained from iter-13]** The deadlock-freedom argument on lines 452–453 still says express links inherit the VC class of the dimension whose hop count they reduce. What about express links at distance $d \ge 2$ that move along *both* X and Y (e.g., a diagonal $d{=}3$ link that bypasses 2 X-hops and 1 Y-hop)? Does the placer restrict the express candidate set to axis-aligned pairs, or does it allow diagonals — and if diagonals are allowed, how is the channel-dependency ordering preserved without a third VC class?

3. **[Q3, new in iter-14]** Equation~(6) says $L_{\text{RL-WS}} = \min(L_{\text{greedy}}, L_{\text{FBfly}}, L_{\text{RL-best}})$. The ablation reports 4/28 fallback activations. Of those 4, how many activate to greedy versus FBfly, and what is the per-cell breakdown? §VI.C gives per-cell names (Tree $K{=}16, N{=}4$; Pipeline $K{=}16, N{=}4$; Hybrid TP+PP $K{=}16, N{=}4$; Tree $K{=}32, N{=}8$ at $b{=}2\times$) — please add the actually-selected baseline per cell so a reader can see whether fallback ever picks the *worse* of the two heuristics, which would be diagnostic.

4. **[Q4, new in iter-14]** Table~7 reports that 17/28 BookSim-best selections come from greedy-warm RL and 11/28 from FBfly-warm RL. Does this 17:11 split correlate with NL% (i.e., is greedy-warm RL the winner on low-NL cells, FBfly-warm RL on high-NL cells)? If yes, that is a stronger predictor story; if no, multi-warm-start is doing exploration work that NL% alone does not predict. Either answer is interesting and worth a one-line addition to §VI.C.

## Missing References

(All retained from iter-13; iteration 14 does not appear to have addressed these.)

- **Kite/Florets co-design context.** Cite Bharadwaj et al. on accurate interposer interconnect modeling beyond the Kite-DAC2020 paper, and Sharma et al.'s follow-up if available — the FBfly framing in Section~4 borrows from this lineage and deserves a fuller positioning.
- **AI-Multicast / NoI for ML.** Yin & Ma, "AI Multi-Cast: Optimizing All-Reduce on Chiplet-Based Architectures" (DAC 2023) and Iff et al., "RapidChiplet" (DATE 2024) directly target chiplet NoI for ML traffic and should be discussed; their absence makes the related-work coverage feel narrow.
- **UCIe 2.0 / CoWoS-L characterization.** Cite a concrete CoWoS-L wire-delay characterization (e.g., TSMC OIP / VLSI Symposium 2023–2024 papers) to back the $2d$-cycle model and the $\lambda$ sensitivity sweep — the assertion "linear wire-delay model... reflects CoWoS-class wire delay scaling" still has no source.
- **Express-channel literature beyond EVCs/CMesh.** Concentration networks (Balfour CMesh is cited; consider Grot et al. "Express Cube Topologies" ISCA 2009 / Kim et al. "Flattened Butterfly" MICRO 2007). The FBfly baseline name should cite the original Kim flattened-butterfly paper, which is still missing.
- **PARL.** A serious comparison, not just a citation. See [W2].

## Detailed Comments

**Abstract (lines 28–32).** Numerical consistency is now clean: 35.6% / 24.8% / 27.1% / 24/28 / $-83.2\%$ / $\rho=0.83$ all match the body and Conclusion. The "8/12 with max $-5.3\%$ margin" claim on low-NL cells is not directly readable from Table~6 (see [W4]); a one-line footnote would close this.

**Introduction (lines 35–58).** The four-bullet contribution list is now sharper. C2 in particular benefits from the concrete numbers: "greedy +61.0\% on MoE Skewed vs FBfly +40.5\%; FBfly +35.6\% on Uniform Random vs greedy +28.4\%" turns the iter-13 abstract claim of "complementary baselines" into a falsifiable statement. C3 still under-sells the safety guarantee — adding "with a measured zero-regression guarantee on the remaining 4/28 cells via post-hoc fallback" would tie C3 directly to Eq.~(6).

**Section 3.1 (lines 96–105).** The interposer cross-section figure caption is accurate. The statement that express links "may transition between metal layers through vias" is still followed by no via penalty in the cost table (Table~9) — see [W1].

**Theorem~1 / Corollary~1 (lines 133–148).** Unchanged from iter-13. The reviewer comment to add a one-paragraph proof in an appendix or cite a known result if folklore still applies.

**Table~2 routing study (lines 177–197).** The footnote about directional vs undirected loads is now in the body text on line 175 ("not directly comparable to the undirected closed-form values in Table~\ref{tab:scaling}; the point is comparative, not absolute"). This addresses my iter-13 concern about reader confusion, though a footnote *inside* the table caption would be more discoverable.

**Section~4, NL% (lines 205–214).** The iter-13 internal inconsistency between $\rho=0.825$ in the body and $\rho=0.74$ in Fig.~3 caption is closed: both now say $0.83$, and the Fig.~4 caption (line 352) matches. This was a clean fix.

**Section~5.2, RL-WS design (lines 249–268).** The new "in-distribution surrogate" honesty (line 257: "The split is uniform-random within the full sample pool, so each (workload, $K$, $N$, $b$) cell is represented in both train and validation: the surrogate is a well-matched in-distribution reward model for refinement, not a held-out generalization predictor. We rely on the post-hoc BookSim selection step (Eq.~\ref{eq:fallback}) for the actual safety guarantee...") is exactly the right framing. This was the cleanest closure of an iter-13 concern: it stops claiming surrogate accuracy as a generalization guarantee and points to BookSim fallback as the actual safety mechanism. New Eq.~(6) at line 264 formalizes the fallback.

**Section~6.1, Table~6 (lines 311–347).** Numerical consistency with abstract / conclusion is now correct. Per [W4], a one-line footnote with the per-cell maximum margin on low-NL cells would close the last presentation-level loose end.

**Section~6.3 ablation (new in iter-14, lines 365–402).** This is the most substantive iter-14 addition. The three observations — (i) both warm-start sources contribute, (ii) RL is doing real work on 22/28 cells, (iii) post-hoc fallback fires on 4/28 — are exactly the right defenses against the obvious iter-13 pushbacks. One presentation issue: the table format mixes section headers (e.g., "Multi-warm-start (greedy + FBfly)") with data rows in a way that would be cleaner as three separate sub-tables or as a tabular with thin horizontal rules. The numbers themselves are convincing.

**Section~6.4, per-cell analysis (lines 404–418).** The four-MoE-cell breakdown now lists all four (was less explicit in iter-13). The non-MoE high-NL discussion ("12 non-MoE high-NL cells, mean reduction of $-4.3\%$, max $-6.8\%$") is the right level of detail.

**Section~6.5, physical overhead (lines 420–439).** Unchanged from iter-13. This is the weakest section relative to venue expectations. See [W1], [W3].

**Section~7, deadlock argument (lines 452–453).** Unchanged. See [Q2]. "Outside the scope of this paper" is still not adequate for a deadlock claim in an architecture paper.

**Section~7, $\lambda$-sensitivity (lines 455–485).** Genuinely useful — preempts the "your savings are an artifact of the $2d$-cycle model" objection cleanly. Worth keeping.

**Limitations list (line 487).** The iter-14 list is now eight items vs iter-13's five. Items (ii) MoE-dependence, (iii) NL% layout-dependence, (iv) in-distribution surrogate, (vi) PARL-as-future-work, (vii) linear wire-delay-not-SPICE are all new explicit honesty additions. This is a substantive credibility improvement: an iter-13 reviewer would have to dig for items (iii) and (iv); an iter-14 reviewer sees them stated up front. The downside is that limitations (vi)+(vii) restate weaknesses I flagged as [W1] and [W2] — disclosing them does not close them, only documents that the authors know.

**Conclusion (lines 493).** The Conclusion now matches the abstract on every quantitative claim. The "compute NL% first, fall back to FBfly when NL% is low, invoke RL-WS whenever NL%$\ge$77\%" workflow remains a clear takeaway.

## What changed since iter-13 (delta summary)

| Iter-13 catch | Iter-14 status |
|---|---|
| $\rho$ inconsistency (0.825 vs 0.74) | **Closed** — uniformly 0.83 |
| Greedy mean inconsistency (25.6 vs 24.8) | **Closed** — uniformly 24.8% |
| C2 contribution abstract phrasing | **Closed** — concrete +61.0% / +35.6% numbers |
| Surrogate generalization framing | **Closed** — explicit in-distribution disclosure + Eq.~(6) safety |
| MoE-dominance honesty | **Closed** — $-3.2\%$ ex-MoE in body and limitations |
| Layout-dependence of NL% | **Closed** — explicit in §IV and limitations (iii) |
| Ablation: which warm-start source wins | **Closed** — new Table~7 (17/11/22/4 breakdown) |
| Fallback empirical activation rate | **Closed** — 4/28 cells, 0.22–0.87 cycle rescue |
| Eq.~(6) labeled safety guarantee | **Closed** — new |
| PARL head-to-head | **Not addressed** — still future work |
| Wire-mm$^2$ Pareto / per-method distance distribution | **Not addressed** |
| Maximum express distance $D$ per cell | **Not addressed** |
| $\lambda$ sensitivity beyond 4 cells | **Not addressed** |

## Rating
- Novelty: 3 / 5 (NL% as deployment classifier remains novel; multi-warm-start + Eq.~(6) post-hoc selection is now a sharper engineering combination than iter-13)
- Technical Quality: **3.5** / 5 (iter-13 was 3; raised by the new ablation table, Eq.~(6) safety guarantee, and surrogate-scope honesty; physical-modeling and PARL gaps still cap this at 3.5 rather than 4)
- Significance: 3 / 5 (unchanged; chiplet NoI for LLMs is timely, $-83.2\%$ MoE latency is a real result, but impact is still bounded by missing PARL bar and physical-cost accounting)
- Presentation: **4.5** / 5 (iter-13 was 4; raised by the consistent numbers, the new ablation table, the explicit limitations list, and the labeled Eq.~(6))
- Overall: **3.5** / 5 (iter-13 was 3.0; raised by 0.5 because the iter-14 changes substantively close the *internal-consistency* and *ablation-rigor* gaps I flagged, but the two architecture-venue-critical gaps (PARL head-to-head, wire-mm$^2$ Pareto) remain)
- Confidence: 4 / 5 (unchanged)

## Decision
**Borderline / lean Weak Accept.** Iteration~14 closes most of the presentation-level and ablation-rigor concerns I raised in iter-13: numerical consistency is clean, the post-hoc fallback is now a labeled equation with measured activation statistics, the surrogate-generalization framing is honest, and the MoE-dependence is disclosed up front. These are real fixes, not cosmetic. However, the two architecture-venue-critical gaps remain: there is still no head-to-head numerical comparison against PARL (the only learned-placement competitor), and the physical-overhead section still does not provide per-method wire-mm$^2$ accounting or Pareto curves. For a workshop or DATE poster track this is now publishable; for the full DAC/DATE architecture track I would still want at least one of those two gaps closed before recommending acceptance. I am moving from "lean Weak Reject" to "lean Weak Accept" because the trajectory is unambiguously upward and the iter-14 changes are exactly the right ones, but I am not pushing past 3.5/5 because the substantive architecture-track concerns are documented in the limitations list rather than addressed in the experiments.
