# Review -- Reviewer 3 (ML/Application Expert), Iteration 4

## Summary
The paper characterizes "phantom load" in chiplet Network-on-Interposer (NoI) and explores mitigation strategies. This revision addresses three of my four remaining iteration-3 concerns: (1) the Table VII anomaly (Express worse than Uniform for MoE) is now explained as a router-level vs. link-level modeling gap, (2) Kite-like is present in the main BookSim table confirming adjacent-only limits, and (3) AMD/NVIDIA commercial systems are discussed explicitly. Two concerns remain partially or fully unaddressed: the 10-30% communication fraction is still unsubstantiated, and MoE parameters are still unspecified.

## Assessment of Changes from v3

**Iter-3 W1 (10-30% comm fraction unsubstantiated): NOT addressed.** The Discussion section still states "communication can reach 10-30% of total time" without a worked example. My specific ask was: provide a calculation for, e.g., 8-way tensor-parallel all-reduce during training at batch 256, K=16, showing how you arrive at the 10-30% range. This remains an assertion without derivation. The paper's core practical claim -- that phantom load matters in communication-heavy regimes -- rests on this number. This is the single most important remaining gap.

**Iter-3 W2 (MoE params unspecified): NOT addressed.** The paper still says "sparse all-to-all traffic where each chiplet sends tokens to a subset of remote experts" without specifying expert count, top-k, or capacity factor. The MoE finding (88% phantom links, greedy places zero express links) is the paper's strongest result, and its generalizability across the MoE design space (8 experts vs. 256 experts, top-2 vs. top-8) remains unclear. This is a recurring ask across three iterations now.

**Iter-3 W3 (Table VII anomaly): Addressed.** The text now explains: "Express (0 placed) shows slightly higher latency than uniform despite placing zero express links: this is because the greedy algorithm produces a non-uniform adjacent allocation (concentrating links on analytically high-load pairs), which can create router-level contention not captured by the link-level analytical model." This is a satisfactory explanation that correctly identifies the gap between link-level and router-level modeling. It is honest about the limitation rather than papering over it.

**Iter-3 W4 (SW mitigation gap): Unchanged.** The paper still does not discuss communication-computation overlap (Megatron-LM double buffering, DeepSpeed ZeRO). As noted in iteration 3, this is acceptable for a characterization paper, but it means the practical significance for communication-heavy regimes (the one regime where the work matters per Guideline 7) is presented without accounting for standard software optimizations that reduce effective communication time.

## Strengths

1. [S1] **Table VII anomaly explanation is credible.** Identifying the link-level vs. router-level modeling gap as the source of the anomaly is the correct diagnosis. The greedy algorithm's non-uniform adjacent allocation concentrating links on analytically high-load pairs can indeed create hotspots at specific routers that a link-level model cannot predict. This is a known limitation of analytical NoC/NoI models. Citing BookSim as the ground truth here is appropriate.

2. [S2] **Kite-like in main BookSim table (Table VI) is compelling.** The K=16 row showing Adj. Uniform and Kite-like with nearly identical performance (54.3 vs 54.4 latency, 0.0106 vs 0.0104 throughput) is strong evidence that adjacent-only optimization hits a fundamental ceiling. This directly validates the paper's central claim that phantom load cannot be resolved by reallocation alone.

3. [S3] **Commercial system discussion is well-positioned.** The observation that AMD MI300X (K=8, 2x4) is in the "manageable" regime (alpha_max=8) consistent with its adjacent-only Infinity Fabric design, while future K>=16 products will hit alpha_max>=16, is exactly the kind of forward-looking insight that makes this paper relevant to industry practitioners.

4. [S4] **All prior strengths retained.** The intellectual honesty of Guideline 7, the counter-intuitive findings (traffic-proportional 1.5x worse, express useless for MoE), and the routing independence proof all remain solid.

5. [S5] **Abstract BW claim corrected.** The abstract now correctly states "2.0--2.6x improvement with ideal bandwidth and 1.6--1.8x even with 50% bandwidth degradation," which matches Table V.

## Weaknesses

1. [W1] **10-30% communication fraction still unsubstantiated (carried from iter-3 W1).** This is the third iteration where I have flagged this. The number appears only in the Discussion section without any derivation. A single worked example would suffice: take a specific model (e.g., LLaMA-70B), a specific parallelism configuration (e.g., 8-way TP on K=16), a specific batch size (e.g., 256), compute the all-reduce volume per layer, compute the HBM-bound compute time per layer, and show the resulting communication fraction. This would take 3-4 sentences and would ground the paper's practical significance claim. Without it, a skeptical reader can dismiss the "communication-heavy regime" discussion as hand-waving.

2. [W2] **MoE parameters still unspecified (carried from iter-3 W2).** Three iterations of asking for expert count, top-k, and capacity factor. The traffic model for MoE determines the sparsity pattern, which directly affects phantom load severity. A 256-expert model with top-2 routing creates a much sparser pattern (each chiplet talks to ~2/256 = 0.8% of experts per token) than an 8-expert model with top-2 (each chiplet talks to 25% of experts). The paper's MoE finding (88% phantom links) may or may not hold across this range. Even a single sentence ("We model 64 experts with top-2 routing distributed evenly across K chiplets") would resolve this.

3. [W3] **Missing sensitivity analysis for MoE parameters (carried from iter-3 Q3).** Related to W2: how does phantom load severity change as expert count varies from 8 to 256 with fixed top-k=2? This would make the MoE finding actionable across the full spectrum of MoE architectures. Without it, a DeepSeek-V3 architect (256 experts) cannot confidently apply the paper's MoE guidelines, which were characterized at an unspecified configuration.

4. [W4] **Guideline consistency check.** Guideline 3 says "Add 3-4 express links for K>=16" and "Physical overhead for 10 express links: ~0.6% interposer area and ~2% TDP." The jump from 3-4 to 10 in the same guideline is slightly confusing. Should the cost estimate be for 3-4 links (the recommended amount) rather than 10?

5. [W5] **Static traffic matrix limitation (carried, acceptable).** Real workloads alternate between patterns (attention all-reduce, MoE dispatch, pipeline boundaries) at millisecond timescales. The paper's per-pattern characterization assumes the designer knows the dominant pattern. This is a known and acknowledged limitation.

## Questions for Authors

1. [Q1] Can you provide a single worked example for the 10-30% communication fraction? E.g., LLaMA-70B with 8-way TP on K=16, batch=256: all-reduce volume = X bytes, compute time = Y us, comm time = Z us, fraction = Z/(Y+Z) = N%.

2. [Q2] What expert count and top-k were used for the MoE traffic model in Tables IV and VII? This has been asked in iterations 2, 3, and 4.

3. [Q3] In the Hybrid TP+MoE row of Table VII, Uniform and Kite-like show identical results (25.5/26.9/0.0250). Is this because the TP component dominates and both strategies handle it similarly, or is there a different explanation?

## Detailed Comments

- The Table VII anomaly explanation is the right kind of honesty. Acknowledging that the greedy algorithm's analytical optimality does not translate to cycle-accurate simulation due to router-level effects is a mature observation. Future work could close this gap by using BookSim-in-the-loop placement.
- The sentence "This highlights a known gap between link-level and router-level modeling in BookSim" should perhaps cite a second reference beyond BookSim itself, if one exists. The gap is between the *analytical model* and BookSim, not within BookSim.
- Guideline 6's cost estimate (56 mm^2, 15 W for 10 express links) remains a valuable addition. Consider adding the per-link cost to make it easier for architects to scale: ~5.6 mm^2 and 1.5 W per express link.
- The Limitations paragraph honestly enumerates the paper's assumptions. This is good practice.

## Rating
- Novelty: 3/5
- Technical Quality: 3.5/5
- Significance: 3.5/5
- Presentation: 4/5
- Overall: 3.5/5 (Weak Accept, borderline Accept)
- Confidence: 4/5

## Score Changes from Iteration 3
- No score changes. The fixes in iteration 4 address presentation issues (Table VII anomaly, Kite-like baseline, commercial systems) but the two substantive gaps that would move the score (communication fraction derivation, MoE parameter specification) remain unaddressed.

## Decision
**Weak Accept (unchanged)** -- The paper has reached a stable state. The characterization is thorough, the theoretical analysis is sound, and the counter-intuitive findings are validated at multiple levels. The Table VII anomaly is now satisfactorily explained. The commercial system discussion adds practical context.

However, the two gaps I have flagged since iteration 2 remain:
1. The 10-30% communication fraction that grounds the paper's practical significance for communication-heavy regimes has no derivation.
2. The MoE traffic model parameters are unspecified, making the paper's strongest finding (88% phantom links, zero express links) non-reproducible and of unknown generalizability.

These are both fixable in under a paragraph each. Their persistent absence is the only reason the score remains at 3.5 rather than 4.0. Neither gap undermines the paper's core theoretical contributions (closed-form analysis, routing independence, counter-intuitive allocation results), but both limit the paper's utility to practitioners -- which is the stated goal of the design guidelines.

The paper is an acceptable contribution to DATE in its current form. The characterization fills a genuine gap in the literature, and the seven design guidelines provide a useful (if incompletely grounded) framework for chiplet architects.
