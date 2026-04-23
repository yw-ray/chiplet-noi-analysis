# Review -- Reviewer 1 (Architecture Expert), Iteration 10

## Summary

Iteration 10 restructures the paper around a three-step Predict-Place-Refine narrative and introduces a warm-start RL refinement (RL-WS) with a post-hoc BookSim fallback that, by construction, is never worse than the greedy baseline. The headline claims are: NL% predicts express-link saving with Spearman rho=0.744 over 40 configurations (p<1e-7); greedy placement saves 25.6% mean latency versus an adjacent-uniform no-express baseline; RL-WS raises this to 28.2% (best 56.4%) and wins 35/40 configs over greedy; and on three unseen workloads RL-WS wins 6/6 cells while a zero-shot GNN is competitive on ring/pipeline but collapses (-23.6%) on all-to-all. I spot-checked the numbers against results/ml_placement/*.json and they reproduce: mean greedy 25.64%, mean RL-WS+fb 28.23%, best 56.43%, wins 35/40, worst raw regression 1.73%. The paper is considerably better organized than iteration 9 and the new ML contribution genuinely strengthens the story. However, most of the architecture concerns from prior iterations remain open, and a new round of weaknesses around the RL methodology has appeared.

## Changes from Iteration 9

**Fixed:**
- **[W9-S1: Framing]** The three-step Predict-Place-Refine framing is cleaner than the previous "phantom load + express placement" framing and motivates the NL% predictor as a first-class contribution rather than a loose correlation result.
- **[W9-S2: Ablation computation error]** The 32/40 -> 35/40 correction is now documented and consistent with the supplied JSON (I reproduced 35/40 wins on both raw and post-fallback).
- **[W9-S3: Sign error]** Table 7 Overall GNN sign (+0.6% -> -0.6%) is now consistent with (14.7+7.2-23.6)/3 = -0.57%. Good catch.
- **[W9-S4: Correlation scope]** The pooled Spearman rho=0.744 over N=40 (p=3.8e-8) is now the headline, and the wide-CI K32N8 r=0.94 claim has been deprecated. This is the right move and resolves the most problematic part of my iter-9 W4.

**Partially addressed:**
- **[W4 iter 9: Correlation CI width]** The pooled N=40 estimate is statistically stronger than the prior per-slice r=0.94 with CI [0.37,1.00]. However, the paper still reports only a point estimate for rho=0.744; a 95% CI on the Spearman rank correlation (bootstrap over the 40 points) should be trivial and would forestall exactly the critique I made last round. Please add.
- **[W2 iter 9: Switch-based alternatives]** Not addressed as a new experiment, but the Introduction and Related Work now frame express links as a "topological rather than allocation-level fix," which at least positions the scope. Still, not a single sentence comparing mesh+express to NVSwitch/crossbar appears in the paper. An architecture reviewer reading this will keep asking "why not a switch?" and the paper offers no answer.

**Not addressed:**
- **[W1 iter 9: Physical latency model]** The 2d-cycle express latency (Table~\ref{tab:physical}) remains asserted without a CoWoS reference or a sensitivity analysis. Given that RL-WS's reported headroom over greedy is 2-4 %p, a 1.5x or 2x multiplier on express latency could plausibly erase the uplift in some configurations. This is now a bigger problem than in iter 9, because the paper's central new claim (RL-WS strictly dominates greedy) depends on the latency model being realistic.
- **[W3 iter 9: Synthetic-only workloads]** All training workloads are still analytically generated. MoE is now "skewed" rather than uniform (good), but still not traced, and the paper makes no statement about what skew parameter was used.
- **[W-detail iter 9: Deadlock freedom]** The paper now adds express links on top of adjacent XY routing and uses Dijkstra on the chiplet graph. No deadlock-freedom argument is given; the Limitations paragraph acknowledges this but does not address it.
- **[W-detail iter 9: Table II vs Table III discrepancy]** Still unresolved. The caption of Table III now notes "directional" vs "undirected" values, which is a hand-wave rather than a reconciliation.

## Strengths

**[S1] The post-hoc fallback is a genuinely useful engineering contribution.** Most learning-for-architecture papers compare "our ML" versus "some baseline" and hope for the best. Defining L_RL-WS = min(L_greedy^measured, L_RL^measured) and proving it measured (not surrogate-predicted) means that in practice a deployment cannot silently regress on a pathological configuration. This is the single idea I would actually cite.

**[S2] Warm start is the right architectural decision, and the paper quantifies why.** The ablation shows cold RL worst-case +11.3% regression vs greedy; warm start reduces this to +1.7% before fallback and 0.0% after. This is the clearest piece of evidence I have seen in the ML-for-NoI literature that initialization matters more than the RL algorithm itself. Fig.~\ref{fig:tree_rescue} makes the point visually on Tree AR.

**[S3] The PARL comparison (Table~\ref{tab:related}) is well-positioned.** Contrasting our method on three orthogonal axes (predictor, warm-start, safety) rather than a single headline number is a better framing than "we beat PARL by X%". This is the right way to position a contemporaneous arXiv paper.

**[S4] Numbers reproduce.** I independently computed all headline numbers from results/ml_placement/ml_comparison_fast.json and ml_comparison_warmstart.json: mean greedy 25.64%, RL-WS+fb 28.23%, best 56.43%, wins 35/40, worst raw regression 1.73%. Fig.~\ref{fig:cost_saving_4panel} and Fig.~\ref{fig:ml_nonlocality} are derived from the same underlying data. This level of reproducibility is unusual for a conference submission and builds real confidence.

## Weaknesses

**[W1] Physical latency model is still the weakest technical link (unchanged from iter 8-9).** The 2d-cycle express latency has no physical reference, and the saving gap between greedy and RL-WS is small enough (2-4 %p) that a perturbation to the latency model could swallow it. A single supplementary table showing RL-WS saving at latency multipliers {1.0x, 1.5x, 2.0x} would settle this in an afternoon. I have asked for this across three iterations now.

**[W2] No switch-based topology comparison (unchanged).** The architecture community's natural response to "mesh has phantom load" is "don't use mesh." NVSwitch-class crossbars and fat trees avoid multi-hop routing entirely. The paper never says when mesh+express is preferable to a switch, which is the obvious question and the one that ultimately bounds the paper's impact. This does not require new experiments; even a paragraph in Discussion scoping "mesh+express wins when per-link area/power is dominant vs central switch area" would be enough.

**[W3] The RL-WS "win" is quantitatively modest, and the paper does not fully engage with this.** Mean improvement vs greedy is 3.58% (raw) and 3.68% (fb). The 56.4% best case is a single cell (MoE Skewed, K=32, N=8, 4x budget). A reader could reasonably ask whether the engineering complexity of RL-WS (surrogate training, REINFORCE, per-config retrain) is justified when greedy already captures 25.6 of the 28.2 percentage points. The paper leans on "strictly dominates greedy by construction (fallback)" as the answer, which is defensible, but the Discussion should explicitly say "greedy is the right default; RL-WS is a targeted refinement when NL%>=70% and compute is available." The current Discussion gestures at this but does not commit.

**[W4] Generalization claim is structurally asymmetric.** GNN is evaluated on 4 cells per unseen workload (12 total); RL-WS on 2 cells per workload (6 total). The paper acknowledges this (text under Table~\ref{tab:generalization}) but the headline "RL-WS 6/6" versus "GNN 8/12" is not a clean comparison because the cells differ. The right comparison is GNN vs RL-WS on the shared 2-cell subset. With only 2 cells per workload (K=16, N=8, b in {2x,4x}), 6/6 is also a very small sample; I would like to see at least 3 cells per unseen workload before accepting the "RL-WS wins under distribution shift" claim as more than suggestive.

**[W5] Train/test leakage risk in the RL surrogate.** Section~\ref{sec:placement} says "A 3-layer MLP surrogate, trained on 288 BookSim samples." The paper does not say which configurations those 288 samples come from. If the surrogate is trained on the same 40 configurations it is subsequently evaluated on (even with different link allocations), the "RL-WS improves over greedy" claim is partially measuring surrogate-fit rather than true optimization. The fallback protects against this for final numbers, but the magnitude of the "RL-WS headroom" attributed to warm-start in the text is not protected. Please clarify the surrogate training split.

**[W6] Spearman rho=0.744 is lower than prior iteration per-slice values and deserves more honesty in the Abstract.** Iter 9 reported rho=0.94 on K32N8 (with a wide CI); iter 10 correctly reports the pooled rho=0.744. The Abstract and Intro say "rho=0.744 (p<1e-7)" but do not note that this is noticeably weaker than the "sliceable" view that headline-heavy readers will remember from prior versions. A sentence saying "NL% explains roughly 55% of rank variance in saving" would be more honest than letting rho=0.744 read as "strong correlation."

## Questions

1. **Surrogate training split.** Which configurations form the 288 BookSim samples used to train the RL-WS surrogate? If they overlap with the 40 evaluation configurations (even at different allocations), the RL-WS-versus-greedy deltas on those configurations are not independent measurements. If the split is clean (train on a disjoint set, evaluate on 40), please state this explicitly in Section 5.3.

2. **Latency model sensitivity.** Could you re-run the main-result RL-WS mean saving at express latencies of 1.5*d and 2.0*d cycles and report the number in the rebuttal? A 2-line addition to Table~\ref{tab:physical} stating how much RL-WS saving degrades would close the W1 concern I have raised across three iterations.

3. **GNN vs RL-WS on matched cells.** What is the per-cell comparison of GNN and RL-WS on the shared 2-cell subset (K=16, N=8, b in {2x,4x}) for each unseen workload? The current table implies RL-WS wins but does not pin it down at the cell level.

## Rating

- Novelty: 3.5/5 (up from 3 -- warm-start + post-hoc fallback is a real contribution)
- Technical Quality: 3/5 (down from 3.5 -- physical model still unvalidated, surrogate-split unclear)
- Significance: 3.5/5 (unchanged -- small RL-WS headroom but clean engineering story)
- Presentation: 4/5 (up from 4 -- three-step framing is markedly cleaner)
- Overall: 3.5/5 (unchanged overall, but the composition has shifted toward the ML contribution)
- Confidence: 4/5 (unchanged)

## Decision

**Borderline.** The iteration is materially stronger than iteration 9: the three-step framing is sharper, the fallback guarantee is a genuine engineering contribution, the PARL comparison is well positioned, and I was able to independently reproduce every headline number from the released JSON. These are all above-the-bar attributes for DATE. However, the paper still has two open gaps that separate a Borderline Accept from a clean Accept: (1) the 2d-cycle express-latency model remains unvalidated and unperturbed after three iterations, which an architecture PC member will push on hard, and (2) the RL-WS contribution, though theoretically guaranteed, delivers a modest 3.6 %p mean uplift, and the surrogate training split is not stated clearly enough to rule out mild leakage. With the latency-sensitivity table and a one-sentence surrogate-split clarification added in rebuttal, I would move to Accept; without them, I stay at Borderline. The paper would pass the DATE bar if the rebuttal provides at least one of those two, and would not pass without either.
