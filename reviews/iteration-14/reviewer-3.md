# Reviewer 3 (ML / LLM Application Expert) — Iteration 14

**Paper:** Predict, Place, Refine: Non-Locality-Guided Express Link Placement for LLM Chiplet Networks

## Summary of Iter-14 Changes Relative to My Iter-13 Review

The authors targeted my two blocking weaknesses directly:

- **W1 (NL% layout-dependent).** Eq. 5 is now `NL%(T,G)` rather than `NL%(T)`, with explicit dependence on `hop_G` (lines 207–211). A new sentence (line 212) states: "NL\% depends on \textit{both} the demand matrix $T$ and the chiplet-to-grid mapping $G$ ... so it is a property of the (workload, layout) pair rather than the workload alone. We compute NL\% under the canonical row-major rank-to-chiplet mapping used throughout the paper; aggressive layout-aware co-location ... will reduce NL\%, and \textit{this is desirable} ...". The Limitations section adds (iii) (line 487) restating the layout dependence, and the deployment-classifier framing now explicitly assumes a fixed canonical mapping. Layout-aware NL%-minimization (NCCL-style co-location) is framed as orthogonal complementary work.
- **W2 (unseen-workload claim contradicted by surrogate scope).** Section IV.B is now explicit (line 257): "trained on 1408 BookSim samples that span all evaluated $(\text{workload}, K, N, b)$ cells. ... The split is uniform-random within the full sample pool, so each (workload, $K$, $N$, $b$) cell is represented in both train and validation: the surrogate is a well-matched in-distribution reward model for refinement, not a held-out generalization predictor." The §VI Generalization subsection has been removed (no longer in the paper). Limitation (iv) (line 487) repeats this and points to the post-hoc BookSim fallback (Eq. 6) as the actual safety mechanism.
- **New Ablation (Table 8, line 374).** Decomposes RL-WS by warm-start source (greedy 17/28, FBfly 11/28), raw-RL beats min(greedy, FBfly) on 22/28, fallback activates on 4/28 with 0.22–0.87 cycle rescue.
- **MoE-dependence disclosure** (Section V.C, line 414, and Limitation (ii) at line 487): excluding MoE, per-cell mean reduction is −3.2% rather than −11.8%. This is also surfaced in Conclusion (line 493).

## Are W1 and W2 Genuinely Fixed?

**W1: Yes, mostly.** The fix is honest in the right places (Eq. 5, prose around Eq. 5, Limitation (iii), Abstract no longer claims NL% as a pure workload statistic). It is *not* a one-line disclaimer hidden in a footnote — it has been propagated to the surrogate-input description (line 212), the deployment-classifier framing (line 215), and the Limitations. The "this is desirable" reframe is intellectually sound: a layout that drops NL% below the threshold is exactly what NL% as a classifier should flag. What is still missing — and what would have moved my score further — is a single empirical demonstration: take Hybrid TP+PP at $K=32$, run it under the canonical row-major mapping (NL% ≈ 77%) *and* under a TP-co-located mapping (where TP-8 groups land on adjacent 2×4 sub-grids), and report the NL% and RL-WS-vs-FBfly margin under each. That experiment would convert the current disclosure into evidence that the deployment-classifier framing is robust under realistic layout choices. As written, the fix is rhetorical robustness rather than empirical robustness, but the rhetorical fix is correctly placed and the limitation is named. **Move from "blocking issue" to "addressed disclosure with one missing experiment."**

**W2: Yes, fully.** This is the cleaner of the two fixes. The previous iter-13 paper had a contradiction — line 256 said samples span all cells, yet the §VI Generalization subsection used the same surrogate to claim wins on "unseen workloads." Iter-14 resolves this by removing the unseen-workload claim entirely, stating the in-distribution scope explicitly, and re-attributing the safety guarantee to the post-hoc BookSim fallback (Eq. 6) rather than to surrogate generalization. The ablation table (Table 8) makes the post-hoc fallback's contribution measurable: 4/28 activations, 0.22–0.87 cycle rescues, never worse-than-baseline by construction. This is the right structure: the surrogate is honest about its scope, and a different mechanism (BookSim fallback) carries the worst-case guarantee. **Resolved.**

## Strengths Going Forward

- **S1.** Layout-aware NL% framing (line 212) is a stronger and more honest formulation than iter-13's. It actually clarifies the contribution: NL% is a (workload, layout) statistic, and the deployment classifier assumes a specific layout — which is realistic for any deployment that has already committed to a mapping.
- **S2.** Surrogate scope disclosure (line 257) is now textbook-quality: the random-split limitation, the in-distribution-not-generalization clarification, and the fallback as the real safety mechanism are all named explicitly. Reviewers with ML training will appreciate that the authors are not over-claiming.
- **S3.** New ablation table (Table 8, line 374) is the right level of decomposition. 22/28 strict beats vs min(greedy, FBfly) directly counters the "RL-WS is just a 48-shot search around fixed seeds" critique. Both warm-start sources contributing 17/28 vs 11/28 supports the multi-warm-start claim quantitatively.
- **S4.** MoE dependence is no longer hidden. Three places (V.C, Limitation (ii), Conclusion) repeat that the −11.8% headline drops to −3.2% without MoE, and frame this as a feature of the deployment-classifier story rather than a defect.
- **S5.** Lambda sensitivity (Table 9, line 462) demonstrates the express-link benefit is not a wire-delay-model artifact, and notably the RL-WS uplift over greedy *grows* under higher λ. This is a genuinely robust experimental observation that addresses a class of skeptical reviewer concerns I did not raise but that ISCA Reviewer 1 would likely have.

## Remaining Weaknesses (Carried Over from Iter-13, Not Addressed)

- **W3 (still open). MoE software baseline still not engaged.** The headline −83% MoE result still rests on Zipf-skewed top-2 dispatch, a phenomenon that DeepSpeed-MoE, Tutel, expert-affinity placement, and the recent expert-parallel work in DeepSeek-V3 all address at the dispatcher level. The paper does not engage this critique — there is no paragraph saying "if you fix Zipf skew via expert co-location at the software level, NL% drops, and that is exactly what NL% as a classifier should flag." The fix would be a single paragraph in §V.C contrasting "RL-WS solving Zipf in hardware" against "Tutel/DeepSpeed-MoE solving Zipf in dispatcher," noting that both are valid and complementary. Without this, an LLM-systems reviewer will still feel the MoE result is solving the wrong problem.

- **W4 (still open). No Amdahl / wall-clock / step-time decomposition.** The single biggest gap remains: −83% on a single all-to-all collective in BookSim cycles is not −83% on a Mixtral-8x7B training step. A back-of-envelope calculation — even with one assumed compute time per step — would let readers translate the headline into anything practitioner-relevant. This was W4 in iter-13, was not addressed in iter-14, and remains the largest blocker for an LLM-systems-impact claim.

- **W5 (still open). Software AllReduce baselines (NCCL hierarchical, 2D ring) not compared.** The Tree AR / Ring AR results would look different against hierarchical or 2D-ring AllReduce; the paper still does not address whether express links substitute for or complement collective-level optimizations.

- **W6 (still open). MoE traces uncited.** `gen_moe`'s docstring still references DeepSeek-V3 and Mixtral but the bibliography does not. Trivial fix, would have been done if the authors had time.

## Newly Surfaced Issues (Iter-14)

- **N1. Abstract metric-name inconsistency.** Abstract (line 31) reports the headline as "−19.0% on high-NL cells" in §IV vs "−63.1% per-workload mean reduction relative to FBfly" for MoE in Table 7 (line 335). These are not inconsistent (the −19% is averaged across the high-NL group, the −63.1% is MoE-only), but a reader scanning fast will conflate them. A footnote or explicit separation would help.
- **N2. Limitation (v) (line 487) acknowledges no multi-run RL variance study.** This is a reasonable disclosure, but it does mean Table 7's per-cell margins (especially the 4/28 minor-loss cells where raw RL trails by 0.22–0.87 cycle) might fall on the other side of zero under a different random seed. The post-hoc fallback covers the worst case, but the *headline* +35.6% saving has no error bar. A simple addition would be repeating one cell with 5 independent retraining seeds and reporting variance.
- **N3. Layout-aware co-location is framed as future work but cited nowhere.** Limitation (iii) names layout co-optimization but cites no prior work on rank-placement (e.g., NCCL topology-aware ring builder, GShard expert placement). This is a one-line citation fix.

## Detailed Comments (Iter-14 Specific)

- **L31 (Abstract).** The "16 high-NL cells (NL$\ge$77\%) ... 12 low-NL cells (NL$\le$50\%)" stratification is excellent and was added in iter-14. This is the strongest single sentence in the abstract.
- **L212 (NL% layout dependence).** Strong fix. Consider one more half-sentence explicitly naming that NCCL's topology-aware ring builder and Megatron's TP-major linear layout would yield different NL% — would help LLM-systems readers connect to familiar baselines.
- **L257 (Surrogate scope).** Fully resolves W2. Could be tightened by removing "well-matched in-distribution reward model" (slightly self-congratulatory) — "in-distribution reward model" is enough.
- **L266 (Fallback).** Clear and load-bearing. The four activation cells are now named in Section V.C (line 418), which closes the loop nicely.
- **L374 (Table 8).** Best new addition. Three observations under it (lines 397–402) read clearly. (iii) "is the empirical answer to the concern that ... fallback might be a paper artifact" is a sharp rebuttal to a specific reviewer concern.
- **L414 (MoE dependence disclosure).** "We explicitly do not hide this — it is the central empirical answer to *when* workload-aware RL placement is worth the cost" is the right way to frame this. This sentence does heavy lifting.
- **L487 Limitations.** Eight items. (iii) and (iv) address W1 and W2 explicitly. (ii) MoE dependence. (v) RL variance. The list is genuinely comprehensive — the only missing limitation is "no comparison to software-level MoE/AllReduce mitigations" (my W3/W5).
- **L493 (Conclusion).** "The headline gap to FBfly is dominated by MoE Skewed (excluding MoE the per-cell mean reduction is $-3.2\%$), which we present as a feature rather than a defect" is the right move. Conclusion now lands.

## Questions for Authors

- **Q1.** For Hybrid TP+PP at $K=32$, what is NL% under (a) the canonical row-major mapping vs (b) a TP-co-located mapping where each TP-8 group occupies a contiguous 2×4 sub-grid? This is the single experiment that would demonstrate the deployment-classifier framing is robust under realistic layout choices.
- **Q2.** What is the per-cell variance under independent end-to-end RL retraining for one MoE cell (e.g., $K=32$, $N=8$, $b=4\times$) and one Tree cell (e.g., $K=16$, $N=4$, $b=4\times$)? Five seeds would be enough to put error bars on the headline.
- **Q3.** For the MoE Zipf result: if you randomize the expert→chiplet placement across 5 seeds (not the RL seed, the *expert* seed), how much of the −83% gain is preserved? I want to understand whether RL-WS is exploiting the fixed Zipf realization or is robust across realizations.
- **Q4.** Could you add a single paragraph in §V.C contrasting RL-WS-on-Zipf against Tutel/DeepSpeed-MoE expert co-location? Even a qualitative framing — "both are valid; hardware solution generalizes across non-Zipf high-NL workloads (Hybrid TP+PP, Uniform Random) where dispatcher-level fixes don't apply" — would close the W3 gap.

## Missing References (Carried from Iter-13, Still Missing)

- DeepSeek-V3, Mixtral (W6). One-line bibliography fix.
- DeepSpeed-MoE (Rajbhandari et al.), Tutel (Hwang et al.). Relevant to W3.
- NCCL topology-aware ring builder; Megatron-LM (Shoeybi et al.). Relevant to W1 framing and W5 baseline.
- 2D Hierarchical AllReduce / ZeRO++. Relevant to W5.

## Rating

| Axis | Score iter-13 | Score iter-14 | Comment |
|---|---|---|---|
| Novelty | 3 | 3 | NL%-as-deployment-classifier remains the core contribution; layout-aware framing strengthens it without changing the underlying novelty. |
| Technical Quality | 3 | 4 | W1 and W2 genuinely fixed at the disclosure level. Surrogate scope is honest. New ablation table (Table 8) is the right kind of decomposition. Lacks a single layout-comparison experiment and per-seed RL variance, but the fixes propagate consistently through the paper. |
| Significance | 2 | 2 | Unchanged. W3 (software MoE baselines) and W4 (no wall-clock translation) are still open. The paper still cannot answer "what fraction of a Mixtral training step does this save?" — which is the question an LLM-systems reader is asking. |
| Presentation | 4 | 4 | Already strong; iter-14 cleans the contradictions in iter-13 (especially around §VI). |
| Overall | 3 | 3.5 | Borderline → Borderline-Accept. The technical-quality fixes are real, not rhetorical. Significance is the remaining ceiling. |
| Confidence | 4 | 4 | Unchanged. |

## Decision

**Borderline Accept** for top-tier (ISCA/MICRO/HPCA), upgraded from Weak Reject in iter-13. **Accept** for DAC/DATE, upgraded from Borderline Accept.

The W1 and W2 fixes are not disclosure rhetoric — they are propagated through Abstract, Eq. 5, surrogate description, Limitations, and Conclusion. The surrogate-scope clarification in particular is textbook-quality and removes the contradiction that would have been catastrophic at top-tier review. The new ablation table provides the right kind of evidence that RL-WS is doing real work beyond enumeration of warm-start seeds.

What still keeps this from a clean Accept at top-tier is the unchanged W3/W4/W5: the LLM-systems-impact argument requires either (a) a back-of-envelope wall-clock decomposition for one Mixtral or DeepSeek-V3 step, or (b) a paragraph engaging software-level MoE/AllReduce mitigations as alternatives or complements. Either single addition would tip me to Weak Accept at ISCA. As written, the paper makes a defensible architecture-track contribution but does not yet make the LLM-systems-impact claim that the title and motivation gesture at.

For DAC/DATE, where the architectural and methodological contributions weigh more heavily and end-to-end LLM impact is less of a hard requirement, this is a clean Accept. The deployment-classifier framing is the kind of operationally useful insight that the architecture community should reward.
