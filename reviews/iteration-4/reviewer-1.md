# Review -- Reviewer 1 (Architecture Expert), Iteration 4

## Summary
This paper identifies, characterizes, and mitigates "phantom load" in chiplet Network-on-Interposer (NoI): intermediate links in multi-hop 2D grids accumulate routing traffic far exceeding their direct demand. Closed-form analysis under XY routing with uniform traffic proves center-link amplification grows as Theta(K). The effect persists across four routing algorithms and six LLM communication patterns. Five mitigation strategies are compared, with express links achieving 2.0--2.6x improvement for dense traffic (1.6--1.8x at 50% bandwidth decay) while being correctly identified as ineffective for sparse MoE workloads. BookSim validation covers both dense (46% latency reduction at K=16) and MoE (no express benefit) regimes. Seven actionable design guidelines are distilled for chiplet architects.

## Assessment of Iteration-3 Concerns

**[W1] Express (0 placed) worse than Uniform in Table VII.** ADDRESSED. The paper now explains this anomaly directly in Section V-D: "the greedy algorithm produces a non-uniform adjacent allocation (concentrating links on analytically high-load pairs), which can create router-level contention not captured by the link-level analytical model." This is a satisfying explanation. Greedy allocates 0 express links but does NOT default to uniform adjacent allocation -- it still uses its own analytically-derived adjacent distribution, which happens to cause router-level hot spots for MoE's sparse, bursty traffic. The paper correctly identifies this as a gap between link-level and router-level modeling. This also teaches an interesting lesson: even among adjacent-only strategies, the allocation that minimizes link-level rho_max is not necessarily the allocation that minimizes router-level latency when traffic is sparse and bursty. This nuance strengthens rather than weakens the paper.

**[W2] Kite comparison is approximate.** NOT CHANGED (acceptable). The paper still uses MinMax adjacent as an approximation for Kite and uses "approximates this approach" language in the Discussion. This is an inherent limitation -- reproducing Kite's full optimization loop with interconnect modeling is outside scope. However, the key insight stands: both Kite-like and uniform produce nearly identical BookSim latencies at K=16 (Table VI: 54.4 vs 54.3 at rate 0.01), confirming that the adjacent-only design space has negligible room for improvement at this scale regardless of how sophisticated the optimization is. This is a powerful result that makes the exact Kite comparison less important.

**[W3] MoE traffic generation underspecified.** NOT CHANGED (acknowledged in Limitations). For DATE page limits, this is acceptable. The paper does state traffic matrices are parameterized, and the MoE characterization (88% phantom links, 6.5x amplification at K=32) is robust to specific expert count as long as the sparse all-to-all structure is maintained.

**[W4] 2x2 mesh per chiplet unrealistically small.** PARTIALLY ADDRESSED. Table VI includes "K=8big" with presumably larger internal mesh (lat@0.01 = 27.2 vs 30.7 for K=8), showing the trend holds. However, K=16 with a larger internal mesh is absent. The "link budget saturation" note in Section V-A provides the right framing: 2x2 mesh limits border routers to 2 per edge, which is a realistic PHY density constraint. Still, explicitly showing K=16 with a 3x3 or 4x4 internal mesh would have been ideal.

**[W5] Hybrid TP+MoE incomplete (no Express row).** ADDRESSED. The camera-ready note confirms this row is intentionally omitted because "same as uniform since 0 express." This makes sense: if TP+MoE traffic is sufficiently symmetric/sparse that greedy places 0 express links, the result would be identical to the Express (0 placed) pathology already explained above, or to uniform if the greedy fallback is uniform. The fact that Uniform and Kite-like produce identical results (25.5, 26.9, 0.0250) confirms the traffic pattern is symmetric enough that MinMax converges to uniform allocation. A one-line footnote stating "Express omitted for Hybrid TP+MoE: greedy places 0 express links, yielding identical allocation to uniform" would be cleaner than just omitting the row, but this is minor.

**[Minor: Guideline 3 vs 6 inconsistency.** ADDRESSED. Guideline 3 now reads "~0.6% interposer area and ~2% TDP," consistent with the CoWoS-based calculation in Guideline 6. This was the most important camera-ready fix from iteration 3.

**[Minor: Abstract BW claim.** ADDRESSED. Abstract now reads "2.0--2.6x improvement with ideal bandwidth and 1.6--1.8x even with 50% bandwidth degradation," matching Table IV.

## Strengths

1. [S1] **The Kite-like result in Table VI is the iteration's strongest addition.** Showing Kite-like (MinMax adjacent) at lat@0.01 = 54.4 vs uniform 54.3 vs express 29.4 at K=16 is a definitive result. It proves that the entire adjacent-only optimization space is exhausted -- no matter how you redistribute capacity among neighbor links, you cannot beat uniform by more than 0.1 cycles. Express links, by contrast, achieve 46% reduction. This single table row elevates the paper from "express links help" to "adjacent-only optimization is fundamentally limited and topology change is necessary." This is the paper's most impactful empirical finding.

2. [S2] **Counter-intuitive findings remain the paper's hallmark.** Three results that would surprise most chiplet architects: (a) traffic-proportional allocation is 1.5x worse than uniform; (b) the optimal adjacent-only allocation (Kite-like) is essentially identical to uniform at K=16; (c) express links are useless for MoE despite MoE being the most phantom-loaded workload. Each of these contradicts naive intuition and provides actionable insight.

3. [S3] **The closed-form analysis is clean and validated.** Theorem 1 with explicit XY + uniform preconditions, computational validation up to R,C <= 8, and the resulting Theta(K) scaling law provide the theoretical backbone. The formula is simple enough that a chiplet architect can compute amplification factors by hand.

4. [S4] **The Express (0 placed) explanation is insightful.** Rather than hiding or hand-waving the anomaly, the paper explains that greedy's non-uniform adjacent allocation creates router-level contention invisible to link-level analysis. This is an honest acknowledgment of the gap between analytical and cycle-accurate models, and it teaches the reader something about the limitations of link-level optimization in general.

5. [S5] **Commercial system contextualization (MI300X, B200) grounds the work.** The new Discussion paragraph mapping MI300X (K=8, manageable regime) and B200 (K=2, trivially avoids phantom load) to the paper's analytical framework demonstrates practical relevance. The prediction that K >= 16 designs will require topology intervention is a testable, forward-looking claim.

6. [S6] **Seven design guidelines are well-calibrated.** Each guideline has a clear condition, a quantitative threshold, and a recommended action. Guideline 4 (match strategy to workload sparsity) is particularly valuable -- it prevents a blanket "use express links everywhere" misinterpretation.

## Weaknesses

1. [W1] **The Express (0 placed) anomaly, while explained, raises a methodological concern.** The greedy algorithm is supposed to find the congestion-minimizing allocation. For MoE traffic, it produces an allocation that is strictly worse than uniform in cycle-accurate simulation. This means either: (a) the link-level cost model used by greedy is a poor proxy for MoE traffic, or (b) the greedy algorithm needs a different objective for sparse workloads. The paper acknowledges this as a "known gap between link-level and router-level modeling" but does not discuss implications for the greedy algorithm's reliability. If the greedy algorithm's analytical model breaks down for sparse traffic, should Guideline 4 recommend skipping greedy entirely for MoE and using uniform directly? The current text leaves this ambiguous.

2. [W2] **The 10--30% communication time claim for large-batch training is still uncited.** The Discussion states "communication can reach 10--30% of total time" without a citation or back-of-envelope calculation. This was flagged as a minor issue in iteration 3. For a characterization paper that prides itself on quantitative rigor, an uncited claim about the regime where the contribution matters most is a gap. Even a simple calculation (e.g., "for TP=16 with 70B model, each all-reduce of X MB at Y GB/s takes Z us, versus W us compute per layer") would suffice.

3. [W3] **No sensitivity to internal mesh size at K=16.** The K=8big configuration demonstrates sensitivity to internal mesh size at K=8 but not at K=16 where the results are most dramatic. The 46% latency reduction headline number is for K=16 with 2x2 internal mesh. With a larger internal mesh (more border routers per edge, higher adjacent link budget before saturation), the advantage of express links might shrink. This is important because K=16 products would likely have larger internal meshes than 2x2.

4. [W4] **Algorithm 1 Dijkstra ambiguity persists.** The algorithm uses Dijkstra for re-routing after each express link addition, but the edge weight is unclear. For express links with 2d-cycle latency vs 2-cycle for adjacent, is Dijkstra minimizing hop count (favoring express) or latency (potentially penalizing long express links)? The choice affects which express links are selected and could explain why greedy sometimes produces suboptimal results. This was noted in iteration 3 as a minor issue but affects reproducibility.

## Questions for Authors

1. [Q1] Given the Express (0 placed) result, would you recommend that practitioners skip the greedy algorithm entirely for workloads classified as "sparse" (e.g., MoE) and default to uniform allocation? If so, this should be stated explicitly in the guidelines.

2. [Q2] For the "K=8big" configuration in Table VI: what is the internal mesh size, and is there a corresponding "K=16big" result available? The K=16 headline numbers are the most impactful in the paper and their sensitivity to internal mesh size matters.

3. [Q3] The Discussion mentions "communication can reach 10--30% of total time" for training. Can you provide a single concrete example with numbers (model size, batch size, TP degree, compute vs communication time breakdown)?

## Minor Issues

- Table VII caption says "MoE Traffic" but includes Hybrid TP+MoE. Should read "MoE and Hybrid Traffic" or similar.
- The Hybrid TP+MoE row in Table VII has no Express entry. A footnote explaining the omission ("greedy places 0 express links; see Section V-D") would be cleaner than silent omission.
- The Discussion's last sentence on scalability ("86 seconds for K=32") would benefit from mentioning the machine used (single core? how much RAM?).

## Rating

- Novelty: 3.5/5
- Technical Quality: 4/5
- Significance: 3.5/5
- Presentation: 4/5
- Overall: 4/5 (Accept)
- Confidence: 4/5

## Score Justification vs Iteration 3

**Technical quality improved from 3.5 to 4.** The Kite-like result in Table VI is the decisive addition. Showing adjacent uniform and Kite-like producing nearly identical BookSim latencies at K=16 (54.3 vs 54.4) while express achieves 29.4 closes the "what about optimized adjacent-only?" question definitively. Combined with the Express (0 placed) explanation (router-level contention from non-uniform allocation), the paper now has a complete and honest story for both positive and negative results. The Guideline 3/6 consistency fix removes the most jarring presentational flaw. The abstract BW claim correction ensures accuracy.

**Novelty unchanged at 3.5.** The core contributions (Theta(K) scaling, workload sensitivity, counter-intuitive findings) were already established. The Kite-like BookSim row is important validation but does not constitute a new contribution -- it confirms the analytical finding that adjacent-only optimization is fundamentally limited.

**Significance unchanged at 3.5.** The commercial system discussion (MI300X, B200) improves practical contextualization but does not change the contribution's scope. The paper correctly identifies that its findings become relevant for K >= 16, which is the next generation of chiplet products.

**Presentation unchanged at 4.** The minor issues (Table VII caption, Hybrid TP+MoE footnote, uncited 10--30% claim) are small enough not to affect the score. The Express (0 placed) explanation paragraph is well-written and honest.

**Overall improved from 3.5 to 4.** The remaining weaknesses (greedy reliability for sparse traffic, no K=16big, uncited communication fraction, Dijkstra ambiguity) are genuine but do not undermine the core contributions. The paper now has: (1) clean theory with proper preconditions; (2) comprehensive BookSim validation covering dense, sparse, adjacent-only, and express regimes; (3) honest negative results (traffic-proportional worse, express useless for MoE, Kite-like equivalent to uniform at K=16); (4) physically grounded overhead numbers; (5) actionable guidelines with quantitative thresholds. For DATE, this is a solid contribution that advances understanding of chiplet NoI design.

## Decision

**Accept** -- The iteration-4 revisions resolve the two most important open issues from iteration 3. First, the Kite-like BookSim result (Table VI) definitively demonstrates that adjacent-only optimization is exhausted at K=16 -- this transforms a theoretical claim into an empirical fact and is the paper's strongest validation result. Second, the Express (0 placed) anomaly is explained as router-level contention from non-uniform adjacent allocation, an honest and insightful observation that acknowledges modeling limitations. The Guideline 3/6 consistency fix and abstract BW correction address the remaining presentation issues. The paper now delivers a complete characterization story: phantom load is structural, grows quadratically, is workload-dependent, and requires different mitigation strategies depending on traffic density. The counter-intuitive findings (traffic-proportional worse than uniform, Kite-like equivalent to uniform at K=16, express useless for MoE) are the kind of results that change practitioner behavior. The remaining weaknesses (greedy reliability for sparse traffic, no K=16big internal mesh sensitivity, uncited 10--30% claim) are real but are either acknowledged as limitations or minor enough not to affect the core message. This paper makes a clear contribution to the chiplet architecture community and is ready for publication at DATE.
