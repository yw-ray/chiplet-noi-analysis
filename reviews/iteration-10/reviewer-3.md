# Review -- Reviewer 3 (ML/Application Expert), Iteration 10

## Summary

Iteration 10 reframes the paper from "express links help" to a three-step Predict--Place--Refine workflow. The authors directly address two of my top workload-fidelity complaints from iteration 9: MoE now uses Zipf-skewed top-2 dispatch (not uniform), and the TP group size is now 8 (Megatron-style), not 4. They also introduce a new learned method---RL-WS (warm-start REINFORCE with a 288-sample 3-layer MLP surrogate) with a post-hoc measured BookSim fallback---and a zero-shot GNN baseline. Headline numbers are greedy +25.6\%, RL-WS+fb +28.2\% mean vs adjacent-uniform, best 56.4\% on MoE Skewed K32N8 4$\times$. On three unseen workloads (ring-allreduce, pipeline-parallel, all-to-all), RL-WS wins 6/6 evaluated cells; the zero-shot GNN wins ring (+14.7\%) and pipeline (+7.2\%) but collapses on all-to-all ($-23.6$\%). PARL (arXiv 2510.24113) is now cited as the closest prior work. Two of my three iteration-9 W's are materially addressed; one (end-to-end context) is still missing; new RL-methodology and baseline-fairness concerns appear in their place.

## Changes from Iteration 9

**MoE is now Zipf-skewed top-2 dispatch (W1 from iter 9):** Directly addresses my primary workload-fidelity complaint. NL\% for MoE Skewed is 91\%, and Max $\alpha$ of 79.0 with Imbalance 1.7 in Table~4 is now consistent with a popularity-skewed dispatch, not uniform averaging. Headline MoE saving is now +40\% mean (not the old 52\%); the worst-case best single config is +56.4\% at K32N8 4$\times$. I consider W1 resolved to a DATE-acceptable standard.

**TP group size = 8 (W2 from iter 9):** Table~4 lists "mixed TP=8", and the Hybrid TP+PP NL\% has moved from the iter-9 range to 77\%. This matches Megatron-LM 8-GPU-node practice. Saving is now +26.9\% RL-WS (up from 24.0\% greedy), which is a more defensible story than the iter-9 32\% on a TP=4 model. W2 resolved.

**New ML contribution:** RL-WS + post-hoc fallback, plus a zero-shot GNN, plus generalization to 3 unseen workloads, plus PARL as prior-work anchor. This is a substantial re-scoping of the paper. The new safety-property framing ($L_\text{RL-WS} \le L_\text{greedy}$ by construction, measured not surrogate-predicted) is the single most valuable addition.

**Unchanged: no end-to-end ML context (W3 from iter 9):** Still no Amdahl-style estimate of what fraction of LLM iteration time is NoI-bound. A 40\% NoI-latency reduction on MoE is reported as-if the whole-system speedup, but with compute-communication overlap, real impact may be a small fraction of that. This gap has persisted across three iterations now and remains the main ML-significance weakness.

**New concerns:** The RL methodology (288-sample surrogate, REINFORCE for a few hundred episodes, no reported seeds/CIs) and the GNN baseline fairness (zero-shot only, no fine-tuning, no PARL experimental comparison) now need to be defended at the level of an ML-systems paper rather than a pure architecture paper.

## Strengths

**[S1] Workload fidelity materially improved.** The MoE-skew fix is non-cosmetic: with popularity-skewed top-2 routing, the dispatch traffic is concentrated on hot experts, which is exactly the operating regime that motivates express links. Combined with TP=8, the workload mix is now closer to real Megatron+MoE training than any previous iteration. For DATE, this is now defensible even without traced workloads.

**[S2] The post-hoc measured-fallback guarantee is genuinely novel.** Most learned placement papers (including PARL) offer no worst-case guarantee relative to a deterministic heuristic. The construction $L_\text{RL-WS} = \min(L_\text{greedy}^\text{measured}, L_\text{RL}^\text{measured})$ is a simple but effective safety mechanism. Crucially, the guarantee is measured, not surrogate-predicted, so surrogate error cannot produce silent regressions. This is the contribution I find most distinctive.

**[S3] Warm-start ablation is interpretable and honest.** Table~7 (the ablation) quantifies how much of the "safety" comes from warm-start vs fallback: warm RL's mean barely moves with fallback ($-3.6\% \to -3.7\%$), whereas cold RL's mean jumps $-1.3\% \to -3.6\%$ once fallback masks regressions. This is a clean demonstration that warm-start does most of the work and fallback acts as a cheap insurance layer. Very few RL-for-systems papers present their ablation this cleanly.

**[S4] Generalization story is nuanced, not triumphalist.** The paper explicitly notes the GNN beats RL-WS on ring-allreduce by 3.2\,\%p but collapses on all-to-all. The framing "RL-WS degrades gracefully under distribution shift while GNN does not"---not "RL-WS dominates GNN everywhere"---is appropriately calibrated. I appreciate the honesty.

**[S5] Single-scalar predictor gains a new role.** In iter 9 NL\% only predicted raw express benefit (pooled $\rho$=0.66). In iter 10, the same NL\% also predicts RL-over-greedy headroom (+1.3\%p at NL=42, up to +3.4\%p at NL=89). One scalar driving both \textsc{Predict} and \textsc{Refine} decisions is the kind of unifying observation that justifies the three-step framing.

## Weaknesses

**[W1] RL methodology is under-specified and seed-fragile.** REINFORCE with a 3-layer MLP surrogate trained on 288 BookSim samples is a small training set for a neural reward model, and the paper provides no:
- Train/validation split on the 288 samples (is the surrogate evaluated on held-out configs?),
- Surrogate accuracy metrics (MAE/RMSE on held-out, absolute prediction error percentiles),
- Multi-seed RL results (every RL-WS number in Tables 6--7 is apparently a single seed),
- Confidence intervals on the +28.2\% mean, +2.6\%p uplift, or 35/40 win count,
- Hyperparameter sensitivity (learning rate, episode count "a few hundred", baseline/entropy coefficients).

Without multi-seed CIs, the +2.6\%p RL-WS uplift over greedy is hard to interpret. At n=40 configs with typical REINFORCE variance, I would not be surprised if an adversarial seed choice could swing the mean by $\pm$1\,\%p. The post-hoc fallback trivially guarantees the worst case, but the \textit{mean} improvement is what the paper is selling, and that mean is not error-barred. For ML-systems venues (MLSys, NeurIPS-Systems) this would be a clean reject; for DATE's architecture track it is fixable with a seed-variance paragraph.

**[W2] Surrogate overfitting risk is not discussed.** 288 samples for a 3-layer MLP predicting BookSim latency across 4 training workloads, 2 $K$, 2 $N$, multiple budgets is $\sim$7 samples per workload-config cell. RL-WS then searches over swap actions guided by this surrogate. The relevant question is whether the surrogate generalizes to \textit{unseen link allocations at known configs}, and the paper does not address this. The authors show the surrogate's \texttt{predicted\_latency} in the JSON is often substantially off from the measured \texttt{latency} (e.g., tree K16N8 2$\times$: predicted 37.7, measured 53.1---a 29\% underestimate). This is precisely the regime where RL-WS could be chasing a surrogate artifact; the fallback catches it, but it suggests RL-WS is sometimes "won by fallback" rather than by RL itself. A surrogate-vs-measured calibration plot in the appendix would resolve this.

**[W3] PARL is cited but not experimentally compared.** The paper's framing positions PARL (arXiv 2510.24113) as the closest prior work and claims three differentiators (predictor / warm-start / safety). But Table~6 and Table~7 do not include PARL as a baseline. The GNN "zero-shot with no fine-tuning" is a reasonable fast-inference reference but is not PARL. Without a head-to-head against PARL's maskable PPO, the claim "warm-start + fallback beats cold RL" rests on the authors' own cold-RL implementation (Table~7), not on the actual cited prior work. For DATE, reviewers will ask: how does RL-WS compare to PARL trained from scratch on the same 40 configs? A table row or even a reproduced-implementation bar would strengthen the contribution claim significantly.

**[W4] Zero-shot GNN baseline is likely a strawman.** "Pre-trained on a separate NoI dataset, evaluated without fine-tuning" is a worst-case GNN configuration. A practitioner would at least fine-tune on the 288-sample corpus used to train the surrogate, and probably do a few gradient steps per target configuration. The paper's strongest generalization claim---"RL-WS is the robust choice under distribution shift"---is partly an artifact of comparing adapted RL against unadapted GNN. To make this claim stick, the paper needs either (a) a fine-tuned GNN row on the same unseen workloads, or (b) an explicit acknowledgement that the GNN is used \textit{only} as a fast-inference reference and the distribution-shift comparison is not apples-to-apples.

**[W5] Generalization comparison is uneven (2 cells vs 4 cells).** On unseen workloads, RL-WS is evaluated on 2 configs per workload ($K$=16, $N$=8 at $b \in \{2\times, 4\times\}$), while GNN is evaluated on 4 configs per workload. The Overall line in Table~8 compares "+7.1\%, 6/6" to "$-0.6\%$, 8/12" across different cell subsets. The $-23.6$\% GNN failure on all-to-all dominates its overall mean, but RL-WS is never evaluated on the same 4-cell set. The paper acknowledges per-configuration RL is expensive, which is fair, but an apples-to-apples 2-cell GNN row would clean up the comparison. Current Table~8 risks overstating RL-WS's robustness edge because it exploits the uneven denominator.

**[W6] End-to-end ML impact still absent (unchanged from iter 9).** The headline RL-WS +40\% on MoE Skewed is NoI-latency saving, not iteration-time saving. With typical compute-communication overlap, NoI is often <20\% of iteration time, so the effective speedup could be <8\%. The paper owes the reader a back-of-envelope calculation, even if rough. This is the last un-addressed concern from iter 9.

**[W7] Workloads are still synthetic.** Zipf-skewed MoE and TP=8 are well-motivated, but there is no traced workload from an actual LLM training run (no DeepSeek/Mixtral traffic dump, no Megatron profiling). For DATE the bar is lower than for ISCA/MICRO, but a single traced workload as a sanity check would elevate the empirical credibility from "plausible" to "grounded."

## Questions

1. **Surrogate quality.** Can you provide the held-out MAE/R$^2$ of the 3-layer MLP surrogate on the 288-sample corpus? How many RL-WS wins in Table~7 survive if the surrogate's top-1 predicted candidate is replaced with the top-5 measured-in-BookSim candidates (i.e., how much of RL-WS's improvement is the search vs the surrogate)?

2. **Seed variance.** What is the $\pm$std over, say, 5 RL-WS seeds on the 40 configs? Does the "35/40 wins over greedy" hold under seed resampling, or does it range (say) 30--38/40?

3. **PARL comparison.** Even a partial reproduction of PARL's maskable PPO---say on the 8 worst configs for greedy, or on the 6 unseen-workload cells---would be the single highest-leverage addition you could make. Is this feasible in the revision timeline?

4. **End-to-end envelope.** For MoE Skewed K=32 N=8 at 4$\times$ (the 56.4\% headline cell), can you give a rough estimate of what fraction of MoE training iteration time is NoI-bound? Even a 2-scenario bracket (10\% NoI-bound $\to$ 5.6\% iteration speedup; 40\% NoI-bound $\to$ 22\% iteration speedup) would make the headline land with ML readers.

5. **Fair GNN baseline.** Would you be willing to add a fine-tuned GNN row on the unseen workloads? If the fine-tuned GNN also handles all-to-all, the "RL-WS is the robust choice" claim weakens, which is useful information. If it still collapses, the claim becomes bulletproof.

6. **Apples-to-apples generalization.** Could you add the 2-cell RL-WS vs 2-cell GNN comparison (same $K$=16, $N$=8, $b \in \{2\times, 4\times\}$) in Table~8 to make the generalization comparison subset-matched?

## Rating

- Novelty: 3.5/5 (three-step framing is clean; post-hoc measured fallback is the most distinctive new piece; warm-start RL itself is incremental over PARL)
- Technical Quality: 3/5 (workload fidelity now acceptable; RL methodology under-specified, no seeds/CIs, surrogate calibration missing; PARL not experimentally compared)
- Significance: 3/5 (NoI placement with a safety guarantee is useful; end-to-end ML impact still unframed so significance to ML-accelerator audience remains a guess)
- Presentation: 4/5 (Predict--Place--Refine scaffolding reads well; Tables 6--8 are well-structured; ablation is interpretable; limitations are explicit)
- Overall: 3/5
- Confidence: 4/5

## Decision

**Borderline** -- The paper has moved clearly upward from iteration 9. Two of my three primary iteration-9 W's (MoE skew, TP=8) are materially resolved, and the new post-hoc measured-fallback framing is a genuine contribution I have not seen in the learned-NoI-placement literature (PARL notably does not offer it). The three-step Predict--Place--Refine workflow is a coherent scaffolding that previous iterations lacked.

However, the ML-methodology rigor has not caught up to the new ML-centric framing. No multi-seed RL confidence intervals, no surrogate calibration, no experimental comparison with the very paper cited as the closest prior work (PARL), and a zero-shot GNN that is likely a strawman baseline mean the +2.6\%p RL-WS uplift is supported by a single-seed single-baseline experiment. The end-to-end ML impact gap from iteration 9 is also still unaddressed.

**Does it clear the DATE bar?** Borderline. For an architecture-track DATE submission, the $\Theta(K^{3/2})$ phantom-load analysis + workload-aware greedy + measured-fallback safety is a publishable core, and the improved workloads are now credible enough to not be a credibility blocker. I would argue for acceptance if (a) PARL is reproduced as at least one baseline row, and (b) RL-WS reports multi-seed $\pm$std. Without either, the RL portion of the contribution rests on claims a careful ML reviewer cannot verify, and I would lean toward rejection at an ML-systems venue. For DATE specifically, I land on **Borderline** and would defer to the other reviewers on whether the architectural contribution alone carries the submission. If the PC uses Borderline as a soft-accept, this is accept; as a soft-reject, this is reject. I would not fight either direction.
