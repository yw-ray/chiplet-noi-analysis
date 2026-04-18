# Review -- Reviewer 3 (ML/Application Expert), Iteration 3

## Summary
The paper characterizes "phantom load" in chiplet Network-on-Interposer (NoI) and explores mitigation strategies. This revision adds three significant items addressing my iteration-2 concerns: (1) MoE BookSim validation bridging the gap between workload characterization and cycle-accurate simulation, (2) an end-to-end analysis showing batch-1 LLM decode communication (~0.1 us) is negligible versus memory access (~600 us), and (3) a new design guideline (Guideline 7) explicitly stating that NoI is not the bottleneck for single-token inference. The abstract and conclusion now state that express links are "not universally beneficial."

## Assessment of Changes from v2

**R3-W1 (E2E performance): Honestly addressed.** The authors did not fabricate a speedup number. Instead, they performed the back-of-envelope calculation I requested and reported the honest (and uncomfortable) result: for batch-1 decode, the E2E impact is ~0%. This is a mature scientific response. The Discussion section identifies where phantom load *does* matter (large-batch training, multi-query inference with >100 concurrent requests, MoE dispatch). This is more useful to readers than an inflated speedup claim.

**R3-W2 (SW mitigation comparison): Acknowledged but not addressed.** The paper still does not compare against communication-computation overlap or MoE-specific software optimizations (capacity factor limits, top-k pruning). This remains a gap, but the honest E2E analysis partially mitigates it: if communication is ~0.1 us out of ~600 us for batch-1, SW overlap is irrelevant for that regime. For the communication-heavy regimes where phantom load matters (batch training, multi-query), the omission is more concerning but acceptable for a characterization paper.

**R3-W5 (BookSim disconnected from LLM patterns): Resolved.** Table IX (MoE BookSim) directly connects workload characterization to cycle-accurate simulation. The result is genuinely interesting: greedy places *zero* express links for MoE, confirming that express links are workload-dependent, not universally beneficial. This closes the loop between Sections III-D and V.

## Strengths

1. [S1] **Intellectual honesty in E2E analysis.** Reporting that phantom load mitigation yields ~0% E2E speedup for batch-1 decode takes courage. This result actually *strengthens* the paper because it precisely scopes where the work matters. A reader designing a batch-1 inference accelerator now knows to skip NoI optimization; a reader designing a training chip with frequent all-reduce now knows to pay attention.

2. [S2] **MoE BookSim result is the paper's strongest finding.** The combination of (a) MoE has 88% phantom links at K=32, (b) greedy places zero express links for MoE, and (c) load-aware adjacent allocation suffices for MoE is a coherent, actionable narrative. This is directly useful for architects of MoE accelerators (DeepSeek-V3, Mixtral).

3. [S3] **Seven design guidelines are well-calibrated.** The guidelines now cover both when to intervene (Guideline 1: alpha_max thresholds), how to intervene (Guidelines 2-5: strategy selection), physical cost (Guideline 6), and when *not* to intervene (Guideline 7: batch-1 decode). This is a complete decision framework.

4. [S4] **Counter-intuitive results validated at multiple levels.** Traffic-proportional being 1.5x worse than uniform (analytical + BookSim) and express links being useless for MoE (analytical + BookSim) are both validated across methodology layers, strengthening confidence.

5. [S5] **Routing independence proof remains strong.** The structural argument that no routing algorithm eliminates phantom load (6x imbalance at K=32 under ECMP) is a clean theoretical contribution.

## Weaknesses

1. [W1] **Communication-heavy regime not quantitatively validated.** Guideline 7 identifies large-batch training and multi-query inference as the regimes where phantom load matters, but no quantitative analysis supports these claims. The paper states "communication can reach 10-30% of total time" but does not derive this. A simple calculation for, e.g., 8-way tensor-parallel all-reduce during training with batch size 256 at K=16, estimating the communication fraction and the resulting E2E speedup from a 46% latency reduction, would validate the claimed significance for the regimes where it matters. Without this, the paper identifies the problem and characterizes it, but the practical significance rests on an unsubstantiated assertion.

2. [W2] **MoE traffic model parameters still unspecified.** My Q1 from iteration 2 remains: what expert configuration was assumed for the MoE results in Table V? The paper says "sparse all-to-all traffic where each chiplet sends tokens to a subset of remote experts" but does not specify expert count, top-k, or capacity factor. DeepSeek-V3 (256 experts, top-2) creates fundamentally different traffic than Mixtral (8 experts, top-2). The sensitivity of phantom load to these parameters is important for the MoE finding to be actionable across different MoE architectures.

3. [W3] **Greedy placing zero express links for MoE needs more analysis.** Table IX shows the greedy algorithm places zero express links, but the Express row shows *worse* performance than Uniform (Peak Tput 0.0150 vs 0.0229). This suggests that when greedy places zero express links, it may be distributing budget suboptimally compared to uniform. The paper does not explain this discrepancy. If greedy with zero express links is equivalent to uniform (no express links placed means all budget goes to adjacent pairs), why is performance worse? This needs clarification.

4. [W4] **SW mitigation gap still present for communication-heavy regimes.** For the regimes where phantom load is claimed to matter (large-batch training), communication-computation overlap via double buffering is standard practice (Megatron-LM, DeepSpeed). The effective communication fraction after overlap could be substantially lower than the raw 10-30% cited. This interacts with the significance claim: if overlap reduces effective communication to 3-5%, does 46% latency reduction on that fraction still justify the physical cost of express links (Guideline 6: 56 mm^2, 15 W)?

5. [W5] **Static traffic matrix limitation acknowledged but not addressed.** Real LLM training alternates between attention (TP all-reduce), FFN (TP all-reduce or MoE dispatch), and pipeline boundaries every few milliseconds. The paper uses static traffic matrices for each pattern independently but does not model the time-varying mixture. For a characterization paper this is acceptable, but it means the guidelines assume the designer knows the dominant traffic pattern a priori.

## Questions for Authors

1. [Q1] In Table IX, why does the Express strategy (with 0 express links placed) show *lower* throughput (0.0150) than Uniform (0.0229)? If no express links are placed, how does the allocation differ from Uniform?

2. [Q2] For the claimed 10-30% communication fraction in training, what batch size, model size, and parallelism configuration was assumed? Can you provide a specific example calculation?

3. [Q3] The MoE finding is the strongest result. Can you add a sensitivity analysis showing how phantom load changes as you vary expert count from 8 to 256 while keeping top-k=2? This would make the result actionable for the full spectrum of MoE architectures.

## Missing References
- DeepSeek-V3 architecture (256 experts, auxiliary-loss-free load balancing) -- cited in text but not in bibliography
- Megatron-LM (parallelism strategies, communication-computation overlap) -- relevant to SW mitigation discussion

## Detailed Comments

- The phrase "express links are not universally beneficial" in the abstract is a significant improvement. This was the key missing nuance in v2.
- Guideline 7 is the most practically useful addition. Many chiplet architects will read this paper asking "does this affect my design?" and Guideline 7 gives a clear answer for the most common use case (batch-1 inference).
- Table IX's Hybrid TP+MoE results show Uniform and Kite-like are identical (25.5/26.9/0.0250). Is this because the hybrid pattern's TP component dominates and both strategies handle it similarly?
- The Discussion paragraph on "End-to-end application impact" is well-written and appropriately scoped. The transition from "near-zero E2E speedup" to "communication-heavy regimes" is handled honestly.
- Guideline 6's cost estimate (56 mm^2, 15 W for 10 express links) is a valuable addition. Having concrete physical cost makes the design tradeoff tangible.

## Rating
- Novelty: 3/5
- Technical Quality: 3.5/5
- Significance: 3.5/5
- Presentation: 4/5
- Overall: 3.5/5 (Weak Accept, borderline Accept)
- Confidence: 4/5

## Score Changes from Iteration 2
- Significance: 3 -> 3.5 (honest E2E analysis + MoE BookSim validation scope the practical impact clearly)
- Other scores unchanged

## Decision
**Weak Accept (borderline Accept)** -- The revision addresses the two most critical gaps from iteration 2. The honest E2E analysis (Guideline 7: ~0% for batch-1 decode) and the MoE BookSim validation (greedy places zero express links) together create a well-scoped characterization paper that clearly delineates where phantom load matters and where it does not. The paper no longer overclaims.

The remaining weaknesses are manageable for a DATE characterization paper: (1) the communication-heavy regime significance rests on an unsubstantiated 10-30% communication fraction claim rather than a concrete example calculation, and (2) MoE traffic model parameters are unspecified. To reach a clear Accept, I would need either: (a) one concrete worked example showing E2E speedup in a communication-heavy regime (e.g., 8-way TP training at batch 256, K=16), or (b) MoE sensitivity analysis across expert counts. Either would take the practical impact from "plausible" to "demonstrated."

The paper is an acceptable contribution to DATE in its current form. The characterization is thorough, the theoretical analysis is sound, the counter-intuitive findings (traffic-proportional 1.5x worse, express useless for MoE) are genuinely useful, and the intellectual honesty about batch-1 decode is commendable.
