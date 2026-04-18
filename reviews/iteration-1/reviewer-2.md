# Review — Reviewer 2 (Systems Pragmatist), Iteration 1

## Summary
Paper proposes "express links" for chiplet NoI to address "phantom load" from multi-hop routing. A greedy algorithm places non-adjacent direct connections to minimize max link congestion. Evaluated with BookSim showing 90% throughput gain for K=16.

## Strengths
1. [S1] **BookSim cycle-accurate validation** is the right approach for network topology papers. The custom matrix traffic extension is a useful contribution to the community.
2. [S2] **Practical design guidelines**: 3-4 express links for 60% benefit, distance ≤ 4 sweet spot, 3-second runtime. These are actionable for designers.
3. [S3] **Ablation is convincing**: random express is worse than uniform (5.6× gap with greedy) proves the algorithm matters, not just the concept.

## Weaknesses
1. [W1] **No end-to-end application performance.** The paper reports network-level metrics (latency, throughput at various injection rates) but never connects to actual workload performance (e.g., tokens/second for LLM inference, training iteration time). A chip designer needs to know: "Does this 46% latency reduction translate to meaningful speedup for my workload?"
2. [W2] **No comparison with commercial chiplet topologies.** AMD MI300X Infinity Fabric, NVIDIA NV-HBI, Intel EMIB—how do real products handle this problem? Do they already use something like express links? If so, the contribution is diminished.
3. [W3] **Physical overhead is not quantified.** How much interposer area do express links consume? What's the power overhead of driving a 30-40mm wire? What about signal integrity? A single paragraph saying "CoWoS can do it" is insufficient for a design paper.
4. [W4] **All links have same bandwidth.** In reality, adjacent links (short wire, low latency) and express links (long wire, higher latency + power) would have different bandwidth characteristics. Modeling them identically is unrealistic.

## Questions for Authors
1. [Q1] For the K=16 configuration, what is the total interposer wire length with express links vs. without? What's the estimated power increase?
2. [Q2] Have you considered express links with lower bandwidth than adjacent links (reflecting physical reality)?

## Missing References
- AMD Infinity Fabric architecture papers
- Intel Ponte Vecchio chiplet topology
- NVIDIA NVSwitch topology

## Detailed Comments
- **Table IV**: The uniform baseline is suspicious—same results for L=48, L=72, L=96. This suggests a simulation artifact (likely the 2×2 mesh can only support 2 links per border, so extra budget is wasted). This makes the comparison unfair.
- **Section III-E**: "PHY circuits are shared with adjacent links" needs justification. Express links at distance 3-4 likely need different driver strength, equalization, and potentially different voltage levels.

## Rating
- Novelty: 3/5
- Technical Quality: 2.5/5
- Significance: 3/5
- Presentation: 3.5/5
- Overall: 3/5
- Confidence: 3/5

## Decision
**Borderline** — Good problem identification with practical guidelines, but the gap between network-level simulation and real system impact is too large. Needs end-to-end workload evaluation and honest physical overhead analysis.
