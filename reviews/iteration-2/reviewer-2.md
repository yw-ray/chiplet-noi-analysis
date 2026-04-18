# Review -- Reviewer 2 (Systems Pragmatist), Iteration 2

## Summary
Revised paper reframes the contribution as "domain characterization + mitigation DSE" for phantom load in chiplet NoI. Key additions: closed-form phantom load analysis (Theorem 1), four routing algorithms (ECMP, Valiant), six LLM workload patterns, five mitigation strategies, differential bandwidth model for express links, and practical design guidelines. BookSim cycle-accurate simulation validates the main claims.

## Assessment of Iteration-1 Concerns

### [W1] No end-to-end application performance -- NOT ADDRESSED
The paper still reports only network-level metrics (rho_max, latency at injection rate, peak throughput). There is no connection to application-level performance: tokens/second, training iteration time, inference latency for an actual model. The workload sensitivity analysis (Table III) is a step forward -- it shows which *communication patterns* are vulnerable -- but it maps patterns to phantom load metrics, not to end-to-end slowdown. A chip architect evaluating whether to add express links needs to answer: "Does the 46% network latency reduction at K=16 translate to 5% or 40% improvement in my LLM training throughput?" This paper cannot answer that question.

**Mitigation**: The reframing as "characterization" partially excuses this -- characterization papers can legitimately stop at the network level. But the guidelines section (Section V, Guideline 3) makes quantitative design recommendations ("add 3-4 express links"), which implicitly promises system-level impact. The disconnect remains.

### [W2] No comparison with commercial topologies -- NOT ADDRESSED
AMD Infinity Fabric uses a ring+crossbar topology with direct links between non-adjacent XCDs. NVIDIA NV-HBI in Blackwell connects two dies with a high-bandwidth direct interface. Intel Ponte Vecchio uses EMIB for selective direct connections. These are all, in some sense, "express link" solutions deployed in production. The paper never discusses whether commercial architectures already solve phantom load, which ones, and how the proposed approach compares. This is a significant omission for a paper claiming practical design guidelines.

The related work (Section II) cites Kite and Florets but not a single commercial architecture. For a systems-oriented venue like DATE, this is a gap.

### [W3] Physical overhead not quantified -- PARTIALLY ADDRESSED
Guideline 3 now states "<0.5% interposer area, <0.1% TDP for 10 express links on a 100x100 mm^2 interposer." This is better than v1, but the numbers appear without derivation or citation. How was 0.5% area computed? What driver circuit assumptions? What about signal integrity for a 30-40 mm trace on an organic interposer vs. silicon interposer? A single sentence with unsubstantiated numbers does not constitute physical overhead analysis. At minimum, a back-of-envelope calculation with stated assumptions would be needed.

### [W4] All links same bandwidth -- ADDRESSED
This is the most significant improvement. The differential bandwidth model (Table V, Fig. 4) with decay factor gamma in [0.5, 1.0] directly addresses my concern. The finding that 50% BW decay still yields 1.6x improvement is convincing and practically relevant. The argument that express links help via hop reduction rather than raw bandwidth is sound and well-supported by the data.

## New Strengths (Iteration 2)

1. [S1] **Closed-form analysis is the highlight.** Theorem 1 with the exact flow count expressions is clean and correct (I verified for small cases). The proof that center link amplification is Theta(K) for square grids is a genuine analytical contribution. This is the kind of result that gets cited.

2. [S2] **Routing algorithm independence is convincing.** Table II showing that ECMP and Valiant reduce imbalance but cannot eliminate it (6x imbalance at K=32 for ECMP) strengthens the "structural property" claim. The observation that Valiant doubles total load while only modestly reducing imbalance is a useful practical insight.

3. [S3] **Traffic-proportional is worse than uniform -- counter-intuitive and important.** Table IV showing 1.5x penalty for the "intuitive" allocation strategy is the kind of result that changes how designers think. This alone justifies the characterization framing.

4. [S4] **MoE vulnerability quantification.** 88% phantom links for MoE at K=32 is a timely result given the industry trend toward MoE architectures. This will resonate with the DATE audience.

5. [S5] **Differential BW model.** As noted above, this directly addresses a key practical concern and the result (hop reduction >> raw bandwidth) has design implications.

## Remaining Weaknesses

1. [W1-still] **Application-level impact gap.** See above. The paper oscillates between "characterization" (which does not need app-level results) and "design guidelines" (which do). Pick one tone and be consistent. If characterization, tone down the guidelines to qualitative recommendations. If design paper, add at least one application-level evaluation (even analytical).

2. [W2-still] **No commercial topology discussion.** This is particularly problematic because AMD MI300X literally uses 8 XCDs in a configuration that avoids the worst phantom load scenarios. Is phantom load already solved in practice? If so, the paper's contribution shifts to "explaining why commercial architects already do what they do" -- still valuable, but framed differently.

3. [W5-new] **Workload model fidelity.** The six workload patterns (Table III) are stylized: "Ring All-Reduce" assigns traffic to ring-adjacent chiplets, "MoE Expert" generates sparse random all-to-all. Real MoE traffic depends on expert routing policy (top-k, capacity factor), load balancing, and temporal variation. The paper does not discuss how sensitive the phantom load metrics are to these model parameters. For example, does MoE with top-2 vs. top-1 routing change the 88% phantom link figure significantly?

4. [W6-new] **BookSim configuration realism.** Each chiplet is modeled as a 2x2 mesh with 4 routers. Real chiplets like MI300X XCDs have much more complex internal networks. The 2-cycle inter-chiplet latency and 2d-cycle express latency are stated without justification. How sensitive are the results to these latency assumptions? The note about "link budget saturation" (2 border routers per edge = 2 links per pair) is an artifact of the 2x2 model, not a fundamental physical constraint.

5. [W7-new] **Greedy algorithm properties.** The paper claims greedy "outperforms fully-connected by 2.5x" but fully-connected with equal per-link budget is a straw man (it spreads budget across O(K^2) pairs). What about fully-connected with load-aware budget allocation? Also, the greedy algorithm has no approximation guarantee -- the paper acknowledges this but does not discuss how far from optimal the greedy solution might be. For a design tool, some bound on suboptimality would strengthen confidence.

## Minor Issues

- Table II: YX routing shows exactly 2x the load of XY across all metrics. This is suspicious and should be explained (if YX routes vertically first, more flows pile on vertical links in a 2x4 grid?). If it is an artifact, acknowledge it.
- Theorem 1 proof sketch: "We validate computationally for all grids R,C <= 8" is fine for a conference paper, but stating it as a theorem requires a complete proof. Either provide the full proof in a technical report or call it a "validated closed-form expression."
- The abstract claims "quadratically with grid size" but the actual scaling is Theta(K) where K = R*C. Since K is the grid *area* (number of chiplets), not the grid *size* (side length), "linearly with chiplet count" would be more precise. "Quadratically with side length" is also correct. The current phrasing is ambiguous.
- Section VI, Discussion: "Greedy outperforms the fully-connected topology (an upper bound on any same-budget adjacent+express strategy) by 2.5x" -- fully-connected with uniform allocation is NOT an upper bound. Fully-connected with optimal allocation would be.

## Questions for Authors

1. [Q1] AMD MI300X uses 8 XCDs with what appears to be a fully-connected or near-fully-connected IF topology. Does phantom load arise in their design? If not, is it because K=8 is small enough (your Guideline 1 says alpha_max < 5 for K<=8)?

2. [Q2] For the MoE workload, how does the phantom load metric change if expert assignment is locality-aware (e.g., preferring local experts)? This is a software mitigation that chiplet designers might recommend to ML teams.

3. [Q3] The greedy algorithm targets chiplet 13 with 6/7 top express links (Section IV-D). Is this always the geometric center of the grid, or does it depend on the traffic pattern? If it is always the center, a simpler heuristic (connect center to corners) might suffice.

## Scores

| Criterion | Iter-1 | Iter-2 | Comment |
|-----------|--------|--------|---------|
| Novelty | 3.0 | 3.5 | Closed-form analysis and routing independence strengthen novelty |
| Technical Quality | 2.5 | 3.5 | Differential BW, routing analysis are solid; app-level gap persists |
| Significance | 3.0 | 3.5 | MoE vulnerability + counter-intuitive allocation result are timely |
| Presentation | 3.5 | 4.0 | Well-structured; guidelines section is actionable |
| Overall | 3.0 | 3.5 | |
| Confidence | 3.0 | 4.0 | Clearer scope makes evaluation easier |

## Decision

**Weak Accept** -- The paper has improved substantially. The closed-form analysis, routing algorithm independence, counter-intuitive allocation result, and differential BW model are genuine contributions. The reframing as characterization+DSE is more honest than the v1 algorithm-paper framing. However, two significant gaps remain: (1) no connection to application-level impact, and (2) no discussion of how commercial architectures handle phantom load. For DATE, where the audience is design-oriented, these gaps matter. If the authors add even a brief subsection on commercial topology comparison and tighten the characterization-vs-design-guidelines framing inconsistency, this would be a clear accept.
