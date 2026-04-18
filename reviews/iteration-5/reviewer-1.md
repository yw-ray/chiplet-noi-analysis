# Review -- Reviewer 1 (Architecture Expert), Iteration 5

## Summary
This paper argues that adjacent-only chiplet NoI topologies suffer a "phantom tax": multi-hop routing forces designers to provision 2--3x more inter-chiplet links than topologically necessary. The closed-form analysis proves center-link amplification grows as Theta(K) for K-chiplet grids. The core experimental claim---validated in BookSim across 2x2, 4x4, and 8x8 internal meshes---is that express links achieve the same latency target as adjacent-only topologies using 2.3x fewer links on realistic 8x8 internal meshes. MoE sparse traffic is a validated negative result where the greedy algorithm correctly places zero express links. Seven design guidelines map chiplet count and workload characteristics to cost-optimal strategy.

## Assessment of Iteration-4 Concerns

**[W1] Greedy algorithm reliability for sparse traffic.** RESOLVED BY REFRAMING. The paper no longer presents a per-workload Table VII where Express (0 placed) competes against Uniform. Instead, MoE is handled in Section V-E as a standalone validation that the greedy algorithm correctly identifies when express links are unnecessary. The old anomaly (greedy's non-uniform adjacent allocation being worse than uniform for MoE) is no longer surfaced as a comparison row, which sidesteps the confusion entirely. More importantly, the new framing (Section V-E) states explicitly that "uniform, Kite-like, and express (0 placed) all perform similarly for MoE," which is exactly the right message: for sparse traffic, strategy choice is irrelevant because phantom load is not concentrated. This is a clean resolution.

**[W2] Uncited 10--30% communication time claim.** RESOLVED. The Discussion no longer makes this claim. Section VI Guideline 7 instead states: "For batch-1 LLM decode, per-layer communication (~0.1 us) is negligible versus memory access (~600 us). Phantom load mitigation matters for communication-heavy regimes: large-batch training, multi-query inference." This is a much more defensible framing: rather than claiming a specific percentage, it identifies when the contribution does and does not matter, with concrete latency numbers. This is better than a citation would have been.

**[W3] No K=16 with larger internal mesh.** FULLY ADDRESSED. This was the most important open concern from iteration 4, and the revision addresses it comprehensively. The paper now presents cost-performance curves across three internal mesh sizes (2x2, 4x4, 8x8) at K=16. The critical result: on 8x8 internal mesh (border=8/edge, meaning each adjacent pair can have up to 8 links), express achieves 194 vs. uniform's 446 latency at 72 links, and matching express at 72 links requires ~168 adjacent links. The 2.3x cost advantage is demonstrated precisely in the regime where skeptics (myself included) predicted the advantage might shrink---large internal meshes with ample border capacity. Table III shows the cost advantage actually *increases* with internal mesh size (1.0x at 2x2, 2.0x at 4x4, 2.3x at 8x8). This is the paper's most convincing result and definitively closes the "2x2 is unrealistic" concern.

**[W4] Algorithm 1 Dijkstra ambiguity.** NOT EXPLICITLY RESOLVED but less important now. The algorithm description still does not specify edge weights. However, the new cost-performance curves across three mesh sizes show the greedy algorithm produces consistent improvements regardless of the internal mesh configuration, which is indirect evidence that the weight choice is reasonable. For full reproducibility, the weight function should still be documented---but this is a minor omission in an otherwise well-validated paper.

**[Q1] Should practitioners skip greedy for sparse workloads?** ADDRESSED by Guideline 4. The guidelines now explicitly state: "Dense cross-chiplet traffic benefits from express links (2--3x cost saving). Sparse MoE traffic does not---use load-aware adjacent allocation." This is the clear recommendation I was looking for.

**[Q2] K=16 with larger internal mesh?** ADDRESSED (see W3 above). This is the defining improvement of iteration 5.

**[Q3] Concrete communication time example?** ADDRESSED via Guideline 7 (see W2 above). The batch-1 decode example with concrete microsecond numbers is sufficient.

## Strengths

1. [S1] **The cost-performance curves across mesh sizes are the paper's definitive contribution.** Fig. 1 showing latency vs. total link count at three mesh sizes transforms the argument from "express links are faster" (which could be dismissed as an artifact of 2x2 border constraints) to "express links are cheaper for the same performance" across realistic configurations. The monotonic increase of cost advantage with mesh size (1.0x, 2.0x, 2.3x) is particularly powerful: it means the more headroom you give adjacent links, the more wasteful they become relative to express. This is counterintuitive and important.

2. [S2] **The title and thesis reframing is exactly right.** "Breaking the Cost-Performance Ceiling" focuses the paper on the right comparison: not "same budget, which is faster?" but "target performance, which is cheaper?" This reframing resolves a persistent tension in earlier iterations where performance improvement percentages were hard to contextualize. The 2.3x link cost reduction is a concrete, actionable number that a chiplet architect can use in a design review.

3. [S3] **The 8x8 internal mesh result closes the strongest objection.** With border=8/edge, each adjacent pair can have up to 8 links. This is ample capacity---and yet the adjacent-only strategy wastes it on phantom load. Needing 168 adjacent links to match what 72 express-enabled links achieve is a damning indictment of adjacent-only design at K=16. The fact that this number (2.3x) aligns with the theoretical Theta(K) prediction for center-link amplification is satisfying.

4. [S4] **Counter-intuitive findings remain strong.** Three results that would surprise most chiplet architects: (a) traffic-proportional allocation is 1.5x worse than uniform; (b) the optimal adjacent-only allocation (Kite-like) saturates identically to naive uniform at K=16; (c) express links are useless for MoE despite MoE having the highest phantom load metric. Each of these contradicts naive intuition and provides actionable insight.

5. [S5] **Physical overhead quantification (0.56% area, 2.1% TDP) with the cost-saving context.** The paper correctly notes that the express wires' physical cost is "more than offset by the 2.3x reduction in total link count, which saves far more PHY area and power than the express wires consume." This is the right way to present overhead: not as a cost to justify, but as an investment with quantifiable return.

6. [S6] **Clean paper structure.** The paper has been significantly streamlined compared to iteration 4. Removing the per-workload Table VII clutter, consolidating the Kite-like result into a paragraph rather than a full subsection, and leading with the cost-performance figure all improve readability. The paper is now focused and direct.

## Weaknesses

1. [W1] **The Kite-like baseline is now underspecified.** In iteration 4, a full Table row showed Kite-like (MinMax) latencies matching uniform at K=16. In iteration 5, Section V-C says "Adjacent uniform and Kite-like produce nearly identical performance despite MinMax's optimal allocation" but does not provide specific numbers. For a result this important---proving that the entire adjacent-only optimization space is exhausted---the reader deserves at least the numerical comparison. A single line like "Kite-like achieves 448 vs. uniform's 446 at 168 links on 8x8 mesh" would be sufficient. Without it, the claim rests on verbal assertion rather than data.

2. [W2] **Ablation subsection (V-D) reports congestion values without mapping them to the cost-performance framework.** The ablation says random express placement has congestion 85.4 vs. uniform's 62.8 and greedy outperforms fully-connected by 2.5x (15.3 vs. 39.0), but these are congestion values, not latency or link counts. Since the paper's core metric is now "links needed for target latency," the ablation should ideally report in the same currency. How many links does random express placement need vs. greedy to achieve the same latency target? The congestion metric is a proxy that the paper itself argues is imperfect (the MoE anomaly from iteration 4 demonstrated that link-level congestion does not always predict cycle-accurate performance).

3. [W3] **The differential bandwidth subsection (V-F) lacks internal mesh context.** The 75% and 50% BW decay results are stated without specifying the internal mesh size. Given that the paper now emphasizes mesh-size sensitivity as a key variable, do the BW decay numbers hold for 8x8 meshes? If these numbers are only from 2x2 meshes, the reader cannot assess whether the BW decay tolerance extends to the realistic regime.

4. [W4] **Table II (routing algorithm independence) reports K=16 with presumably 2x2 internal mesh.** The paper does not specify. Since the main results now span three mesh sizes, the routing independence results should either be mesh-size-agnostic (analytical only) or specify the mesh configuration. If routing independence only holds for 2x2, the generality claim is weakened. This is likely a non-issue (the analytical result is mesh-independent, and the table appears to be analytical), but the text should clarify.

## Questions for Authors

1. [Q1] Can you provide the specific Kite-like latency number for the 8x8 internal mesh result? This is needed to validate the "identical performance" claim in Section V-C.

2. [Q2] For the ablation in Section V-D: what is the link count for each strategy at the same latency target? Reporting congestion proxies rather than the paper's core cost metric creates a disconnect.

3. [Q3] Are the differential bandwidth decay results (Section V-F) from 2x2, 4x4, or 8x8 internal mesh? This matters because the paper's reframing emphasizes that results must hold at realistic mesh sizes.

## Minor Issues

- Table II should specify whether the values are analytical (closed-form/computational) or from BookSim simulation. The "Max alpha" column heading suggests analytical, but the "Imbalance" column is ambiguous.
- Section V-F states "1.8--2.2x improvement" for 75% BW decay. Improvement in what metric---latency, congestion, or link cost? The paper's core metric is link cost, so this should be clarified.
- The abstract states "2.3x fewer inter-chiplet links" without specifying this is for 8x8 internal mesh. Since other mesh sizes show different ratios (1.0x for 2x2, 2.0x for 4x4), the abstract should note this is the realistic (8x8) configuration.

## Rating

- Novelty: 3.5/5
- Technical Quality: 4.5/5
- Significance: 4/5
- Presentation: 4/5
- Overall: 4.0/5 (Accept)
- Confidence: 4/5

## Score Justification vs Iteration 4

**Technical quality improved from 4 to 4.5.** The 8x8 internal mesh result is the single most important addition across all five iterations. It closes the "2x2 is unrealistic" objection definitively by demonstrating a 2.3x cost advantage in exactly the regime skeptics predicted the advantage would vanish. The fact that the advantage *increases* with mesh size (1.0x, 2.0x, 2.3x) is a powerful result that strengthens the theoretical prediction. Table III clearly quantifying cost-to-match-latency across all three mesh sizes is excellent experimental design.

**Novelty unchanged at 3.5.** The conceptual contributions (Theta(K) scaling, phantom load as cost problem, workload sensitivity, express link placement) were established by iteration 2. The 8x8 result is definitive validation, not a new contribution.

**Significance improved from 3.5 to 4.** The reframing from "performance at same budget" to "cost at same performance target" is a meaningful improvement in how the contribution is positioned. Combined with the 8x8 result, the paper now makes a claim that directly maps to real-world chiplet design decisions: at K=16 with realistic internal meshes, you need 2.3x more adjacent links than express-enabled links to hit the same latency target. This is a number a chip architect can take into a design review. The physical overhead quantification (0.56% area, 2.1% TDP) with the explicit argument that total link reduction saves more than express overhead costs is now a complete cost argument.

**Presentation unchanged at 4.** The paper is cleaner and more focused than iteration 4, but the Kite-like data omission (W1) and ablation metric disconnect (W2) prevent a score increase. The streamlining of MoE treatment (standalone subsection rather than table row with anomaly) is a clear improvement in how negative results are presented.

**Overall unchanged at 4.** The paper was already at Accept; this iteration solidifies rather than elevates the score. The 8x8 result removes the single strongest reason to question the contribution's practical relevance. The remaining weaknesses (W1--W4) are minor and addressable in a final revision---none of them challenge the core claims. The paper's overall story is now complete and convincing: phantom load is structural, grows with K, is workload-dependent, creates a measurable cost ceiling for adjacent-only topologies, and express links break through that ceiling with modest physical overhead. The MoE negative result demonstrates intellectual honesty and workload awareness.

## Decision

**Accept** -- Iteration 5 delivers the result I have been asking for since iteration 3: cost-performance validation on realistic 8x8 internal meshes. The 2.3x link cost advantage at K=16 with border=8/edge---where adjacent links have ample capacity---is the paper's strongest empirical result and definitively closes the "2x2 artifact" concern. The monotonic increase of cost advantage with mesh size (1.0x -> 2.0x -> 2.3x) confirms the theoretical prediction and suggests the advantage will only grow with more realistic configurations. The title and thesis reframing ("cost-performance ceiling" rather than "performance improvement") correctly positions the contribution: this paper is about cost efficiency, not raw performance, and the 2.3x number is directly usable in chiplet design decisions. The MoE negative result, physical overhead quantification, and differential bandwidth analysis provide the completeness expected of a characterization paper. The remaining weaknesses (Kite-like numbers omitted, ablation metric mismatch, BW decay mesh size unspecified) are minor and do not affect the core claims. This paper is ready for DATE publication.
