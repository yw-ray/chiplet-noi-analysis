# Review -- Reviewer 2 (Systems Pragmatist), Iteration 3

## Summary
Third revision adds five substantive elements: (1) MoE BookSim validation showing the greedy algorithm places zero express links (honest negative result), (2) Kite-like MinMax adjacent baseline in BookSim, (3) CoWoS-based physical overhead calculation (0.56% area, 2.1% TDP for 10 links), (4) analytical E2E model for batch-1 LLM decode showing ~0% communication overhead, and (5) expanded design guidelines (5 to 7). The paper has evolved from an algorithm-centric pitch into a well-scoped characterization paper that knows its boundaries.

## Assessment of Prior Concerns

### [W1] No E2E application performance -- ADDRESSED (honestly)
The new E2E analysis (Discussion, Guideline 7) is the right approach: rather than fabricating a system-level benchmark, the authors show analytically that for batch-1 LLM decode, per-layer communication (~0.1 us) is negligible versus HBM access (~600 us). This is an honest negative result that actually increases the paper's credibility. The paper then identifies the regimes where NoI optimization *does* matter: large-batch training, multi-query inference, MoE dispatch with high expert utilization, where communication can reach 10-30% of total time. This framing is exactly right. The paper no longer promises system-level speedup; instead it tells the reader *when to care*. Guideline 7 ("NoI is not the bottleneck for single-token inference") is the kind of sober design advice that a chip architect actually needs.

**Remaining gap**: The "10-30% of total time" claim for communication-heavy regimes is stated without derivation. A brief back-of-envelope (e.g., for 8-way tensor parallelism at batch=128, communication volume X at bandwidth Y = Z us/layer vs compute T us/layer) would make this quantitative rather than qualitative. This is a minor improvement opportunity, not a gating concern.

### [W2] No commercial topology comparison -- PARTIALLY ADDRESSED
The Kite-like (MinMax adjacent) baseline in BookSim is a genuine addition. It approximates the best achievable adjacent-only strategy and demonstrates that even the optimal adjacent allocation cannot match express links for dense traffic at K>=16. The Discussion section now explicitly addresses the relationship to Kite and Florets.

However, the paper still does not discuss AMD Infinity Fabric, NVIDIA NV-HBI, or Intel EMIB. My Q1 from iteration 2 remains unanswered: does phantom load arise in AMD MI300X's 8-XCD configuration? The paper's own data (Table I: alpha_max=8 for K=8) suggests it does, but modestly. A single paragraph noting that K=8 is in the "manageable" regime per Guideline 1, and that commercial architectures at K=8 appear to handle phantom load implicitly (likely through overprovisioned adjacent bandwidth or ring-like communication patterns), would close this gap. This is a presentation issue, not a technical one.

### [W3] Physical overhead not quantified -- ADDRESSED
Guideline 6 now provides a CoWoS-based calculation: 0.8 um wire pitch, UCIe Standard PHY, yielding ~56 mm^2 for 10 express links (0.56% of 100x100 mm^2) and ~15 W (2.1% TDP of 700 W). These numbers are reasonable and derived from stated assumptions. The area figure increased from the iteration-2 claim of "<0.5%" to 0.56%, and TDP from "<0.1%" to 2.1% -- this honesty is appreciated. The 2.1% TDP is non-trivial and appropriately flagged ("real cost that should be weighed against throughput benefit").

**Minor note**: It would be helpful to cite or footnote the specific CoWoS generation (CoWoS-S vs CoWoS-L) and UCIe PHY variant, since these have different wire density and power characteristics. But the current level of detail is acceptable for a conference paper.

### [W4] All links same bandwidth -- ADDRESSED (iter-2)
No change needed. The differential BW model remains solid.

## Assessment of New Additions

### MoE BookSim Validation (Table VIII)
This is the highlight of the revision. The greedy algorithm placing *zero* express links for MoE traffic is a powerful result because it shows the optimization framework is self-correcting -- it does not blindly add express links when they are not helpful. The MoE BookSim results (Table VIII) show all three strategies performing similarly, with express actually slightly worse (latency 36.2 vs 33.4 for uniform). This honest negative result, combined with Guideline 4, makes the paper more trustworthy than if express links had universally won.

**One concern**: Express performs worse than uniform for MoE (lat@0.01: 36.2 vs 33.4, peak tput: 0.0150 vs 0.0229). But the paper says the greedy placed *zero* express links, meaning the "express" configuration should be identical to some adjacent allocation. If zero express links were placed, what is the express configuration doing differently that makes it *worse*? Is the budget being redistributed among adjacent links in a way that hurts MoE? This needs a sentence of explanation.

### Kite-like Baseline
The MinMax adjacent baseline (referred to as "Kite-like") in Table VIII provides a meaningful comparison point. For MoE traffic, Kite-like performs similarly to uniform (slight latency increase: 34.2 vs 33.4), confirming that the sophisticated adjacent-only optimization provides little benefit for sparse traffic. For the main dense-traffic results (Tables VI-VII), Kite-like is not shown -- adding it there would strengthen the paper.

### E2E Analytical Model
Addressed above under W1. The model is simple but appropriate for the claim being made.

### Expanded Design Guidelines
The guidelines grew from 5 to 7, and the new ones (6: physical cost, 7: bottleneck regime) are the most practically useful. The full set now covers: regime identification (1), allocation anti-pattern (2), express link sizing (3), workload matching (4), BW tolerance (5), physical cost (6), and bottleneck identification (7). This is a comprehensive decision tree for a chip architect. Well done.

## Remaining Weaknesses

### [W5-still] Workload model fidelity (from iter-2)
The six workload patterns remain stylized. MoE traffic with top-2 vs top-1 routing, capacity factor variation, and temporal dynamics are not explored. This is an acknowledged limitation but limits the precision of claims like "88% phantom links" for MoE. For a characterization paper, this is acceptable if clearly scoped. The current Limitations paragraph covers this adequately.

### [W6-still] BookSim configuration realism (from iter-2)
The 2x2 mesh per chiplet and 2-cycle inter-chiplet latency remain unjustified. However, given the paper's reframing as characterization (not product design), the specific latency numbers matter less than the relative trends. The saturation phenomenon (846 cycles at K=16) is qualitatively robust to latency assumptions.

### [W8-new] MoE express result inconsistency
As noted above, the express configuration performing *worse* than uniform for MoE (when zero express links were placed) needs explanation. If the greedy allocated budget differently among adjacent links compared to uniform, this should be stated. If it is a BookSim artifact, acknowledge it.

### [W9-new] Missing Kite-like in main BookSim table
Table VI (main BookSim results) shows only adjacent uniform vs express for K=8/16. Adding the Kite-like baseline here would let the reader see the full picture: uniform < Kite-like < express for dense traffic, confirming that topology change (not just allocation optimization) is needed.

## Minor Issues

- Table VIII: The "Hybrid TP+MoE" row shows identical results for Uniform and Kite-like (lat@0.01: 25.5, lat@0.015: 26.9, tput: 0.0250). This suggests the traffic is so localized that allocation strategy is irrelevant. Worth a brief note.
- Guideline 3 still says "<0.5% interposer area" but Guideline 6 says "0.56%". These should be consistent. Either update Guideline 3 to say "~0.6%" or note that Guideline 3 was for a different configuration.
- The abstract is appropriately toned down from iteration 1. "2.0-2.6x improvement even with 50% bandwidth degradation" is stated for express links, but Table V shows 1.6-1.7x at 50% decay. The abstract should use the more conservative 50% number (1.6x) or clarify that 2.0-2.6x is for the ideal-bandwidth case.
- "Greedy outperforms fully-connected by 2.5x" (Section V, Discussion): my iteration-2 note about this being unfair to FC with load-aware allocation was not addressed. Adding "with uniform per-link allocation" would suffice.

## Questions for Authors

1. [Q1-followup] Table VIII shows express performing worse than uniform for MoE despite placing zero express links. What accounts for this performance difference?

2. [Q4] Guideline 7 states communication is ~0.1 us/layer for batch-1 at K=16. What communication volume and link bandwidth assumptions produce this number? A footnote with the calculation would help reproducibility.

3. [Q5] The 10-30% communication fraction for "communication-heavy regimes" -- is this from literature, analytical estimate, or experience? A citation or derivation would strengthen this claim.

## Scores

| Criterion | Iter-1 | Iter-2 | Iter-3 | Comment |
|-----------|--------|--------|--------|---------|
| Novelty | 3.0 | 3.5 | 3.5 | No change; core novelty was established in iter-2 |
| Technical Quality | 2.5 | 3.5 | 4.0 | E2E model, physical overhead, MoE negative result all add rigor |
| Significance | 3.0 | 3.5 | 4.0 | Design guidelines are now actionable; bottleneck regime identification adds practical value |
| Presentation | 3.5 | 4.0 | 4.0 | Good; minor inconsistencies (Guideline 3 vs 6, abstract numbers) |
| Overall | 3.0 | 3.5 | 4.0 | |
| Confidence | 3.0 | 4.0 | 4.0 | |

## Decision

**Accept** -- The paper has matured into a solid characterization contribution. The three additions that pushed it over the threshold:

1. **The MoE negative result** (zero express links placed) demonstrates intellectual honesty and shows the optimization framework is self-aware. This is worth more than another positive result.
2. **The E2E analytical model** honestly acknowledges that batch-1 decode sees ~0% benefit, then precisely identifies when phantom load *does* matter. This "know when not to optimize" framing is more valuable than inflated claims.
3. **The CoWoS physical overhead calculation** grounds the design guidelines in real interposer technology rather than hand-waving.

The remaining weaknesses (commercial architecture discussion, MoE express inconsistency, workload fidelity) are addressable in a camera-ready revision:
- Add one paragraph on commercial architectures at K=8 being in the "manageable" regime.
- Explain the MoE express-worse-than-uniform result in Table VIII.
- Reconcile the Guideline 3 vs Guideline 6 area numbers.
- Clarify the abstract's "2.0-2.6x with 50% BW degradation" vs the actual 1.6-1.7x at 50% decay.

The paper's core message -- phantom load is structural, workload-dependent, and solvable with modest topology changes for the right workloads -- is well-supported and timely for the chiplet scaling era. The seven design guidelines form a practical decision framework that DATE attendees can apply directly.
