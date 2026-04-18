# Review — Reviewer 5 (Skeptic), Iteration 1

## Summary
Paper identifies phantom load in chiplet mesh networks and proposes express (non-adjacent) links placed greedily. Claims 46% latency reduction and 90% throughput improvement validated with BookSim.

## Strengths
1. [S1] **Honest about limitations.** The Discussion section acknowledges synthetic netlists, greedy non-optimality, and simplified wire delay model. This is appreciated.
2. [S2] **The ablation study (Table VI) is genuinely surprising:** random express is worse than no express, and greedy beats fully-connected. This is non-obvious and well-demonstrated.
3. [S3] **10-seed robustness test** (Table IX) shows one failure case—honest reporting.

## Weaknesses
1. [W1] **The 90% throughput claim is misleading.** Looking at Table IV carefully: uniform peaks at 0.0106, express at 0.0200. But uniform's result DOES NOT CHANGE across L=48/72/96. This means the uniform baseline is hitting a structural bottleneck (likely the 2×2 intra-chiplet mesh). Express links help because they reduce the NUMBER OF HOPS, not because of better allocation. A fair comparison would use larger intra-chiplet meshes where uniform can actually use the extra budget.
2. [W2] **Cherry-picked hero result.** K=16 shows 90% gain, but K=8 shows -11% to +5%. Since K=8 is the relevant current configuration (MI300X), the paper's claims are based on a future configuration that doesn't exist. The title should say "for K≥16" not imply general applicability.
3. [W3] **Phantom load amplification numbers are inflated.** The paper reports "200× amplification" but this is max across all links for one specific netlist. The AVERAGE amplification (not reported) would be much lower. Reporting only the max is misleading.
4. [W4] **No comparison with Kite or Florets.** The related work section claims these are "adjacent-only" but doesn't actually compare. Kite's heterogeneous topology might already partially address phantom load. Without direct comparison, the claim "first to address phantom load" is unsubstantiated.
5. [W5] **The netlist generator is not validated.** The synthetic accelerator netlist has hand-tuned parameters (cross-cluster ratio, module types). How do we know this resembles a real accelerator's traffic pattern?

## Questions for Authors
1. [Q1] Why does uniform show identical results across L=48/72/96 in Table IV? Isn't this a simulation artifact?
2. [Q2] What is the AVERAGE phantom load amplification, not just the max?
3. [Q3] Have you tried running Kite's topology on the same traffic and comparing?
4. [Q4] The paper claims "same link budget" for greedy vs. fully-connected. But greedy uses 34 pairs while fully-connected uses 120 pairs. How is the budget allocated? Are they really comparable?

## Missing References
- Should compare directly against Kite and Florets using their published configurations
- Network design theory (multicommodity flow, Steiner tree)

## Detailed Comments
- **Abstract**: "90% higher throughput" without qualifying "for K=16 only" is overclaiming.
- **Table IV**: The suspicious uniform baseline undermines the entire evaluation. If uniform can't use extra links due to mesh limitations, the comparison is fundamentally unfair.
- **Section III-E**: "the PHY circuits are shared with adjacent links" — this needs a citation or technical justification. Express links at 30-40mm likely need different analog frontend than 10mm adjacent links.

## Rating
- Novelty: 2.5/5
- Technical Quality: 2.5/5
- Significance: 2.5/5
- Presentation: 3.5/5
- Overall: 2.5/5
- Confidence: 4/5

## Decision
**Weak Reject** — The paper has interesting observations (phantom load, greedy beats fully-connected) but the evaluation has significant fairness concerns (uniform baseline artifact, K=8 weak results). The 90% claim appears inflated by an unfair baseline. Needs major revision to address the uniform baseline issue and provide honest reporting of K=8 results.
