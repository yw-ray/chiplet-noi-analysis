# Review -- Reviewer 1 (Architecture Expert), Iteration 2

## Summary
This revised paper reframes itself as a "domain characterization paper" studying phantom load in chiplet Network-on-Interposer (NoI). The authors derive closed-form expressions showing that center-link traffic amplification grows as Theta(K) in a K-chiplet square grid, prove this is routing-algorithm-independent (XY, YX, ECMP, Valiant all tested), evaluate six LLM workload patterns (MoE is worst), compare five mitigation strategies (traffic-proportional is counter-intuitively worse than uniform), and show express links achieve 2.0--2.6x improvement with greedy placement. BookSim cycle-accurate simulation validates the findings (46% latency reduction, 90% throughput improvement at K=16).

## Assessment of Iteration-1 Concerns

**[W1] Express channels are well-known (Kumar MICRO'07).** PARTIALLY ADDRESSED. The paper now cites express virtual channels and concentrated meshes, and includes a paragraph in Related Work arguing the chiplet domain is different (PHY-constrained die edges, non-negligible wire delay, non-uniform traffic). This is a reasonable differentiation. However, the argument could be sharper -- the paper should quantify how die-edge PHY constraints change the design space (e.g., how many physical bumps are available per edge, what is the actual bandwidth limit). The current framing ("our focus is not the general concept") is better than iteration 1 but still somewhat hand-wavy on why NoI express links are fundamentally different from on-chip express channels beyond the obvious physical differences.

**[W2] Synthetic netlists only.** PARTIALLY ADDRESSED. The paper now includes six LLM workload patterns (Ring All-Reduce, Tree All-Reduce, Pipeline Parallel, Tensor Parallel, MoE Expert, Hybrid TP+PP). This is a meaningful improvement. However, these are still parameterized communication patterns, not traces from real hardware. The gap between "representative LLM communication patterns" and "measured traffic from an actual MI300X or Blackwell" remains. The Limitations section acknowledges this honestly ("validation on production RTL traces would further strengthen results"), which I appreciate.

**[W3] K=8 results weak.** PARTIALLY ADDRESSED. The paper now correctly frames K=8 as the regime where "load-aware adjacent allocation suffices" and focuses the express-link story on K>=16. The BookSim results still show only 5-10% improvement at K=8 (Table VI: 30.7->27.7 latency), and the paper is transparent about this. The design guidelines section properly segments: K<=8 -> adjacent allocation, K>=16 -> express links. This is a mature and honest framing.

**[W4] No area/power analysis.** MINIMALLY ADDRESSED. The paper now states "<0.5% interposer area, <0.1% TDP for 10 express links on a 100x100 mm^2 interposer" in the Design Guidelines section, but this is a single sentence without derivation or citation. How was this computed? What wire pitch was assumed? What about signal integrity for longer routes? A back-of-envelope calculation showing wire width, repeater count, and area consumed would be much more convincing than an unsupported claim.

## Strengths

1. [S1] **Closed-form analysis is a genuine contribution.** Theorem 1 (Eqs. 2-3) provides exact flow counts for XY routing, and the quadratic scaling result (alpha_max = Theta(K)) is clean and insightful. The computational validation for all grids up to R,C<=8 adds confidence. This is the strongest part of the paper and elevates it above a purely empirical study.

2. [S2] **Routing-algorithm independence is well-demonstrated.** Table III shows four routing algorithms across three grid sizes. The key insight that ECMP reduces imbalance but cannot eliminate phantom load (6.1x imbalance persists at K=32) is valuable. Valiant doubling total network load is a useful cautionary note. This section directly addresses my iteration-1 Q2 about adaptive routing.

3. [S3] **Counter-intuitive traffic-proportional result.** The finding that traffic-proportional allocation is 1.5x WORSE than uniform (Table V) is the kind of result that changes how practitioners think. The explanation is clear: traffic-proportional assigns zero capacity to phantom-loaded links. This alone is a useful contribution for the chiplet design community.

4. [S4] **Differential bandwidth analysis is practical.** Table VII showing express links remain effective even at 50% bandwidth decay (1.6x improvement) addresses a real engineering concern. The insight that hop reduction matters more than raw bandwidth is actionable.

5. [S5] **Honest framing.** The paper no longer oversells. K=8 limitations are acknowledged, the greedy algorithm is one tool among many, and the Limitations section is candid about synthetic traffic and homogeneous chiplets.

## Weaknesses

1. [W1] **The closed-form result is limited to XY routing + uniform all-to-all.** Theorem 1 only holds for deterministic dimension-order routing with uniform traffic. The paper's own workload analysis (Table IV) shows huge variation across patterns -- MoE has 88% phantom links while Pipeline Parallel has 6%. The closed-form doesn't help predict phantom load for specific workloads. The paper needs to be clearer that the Theta(K) result is for the worst-case uniform traffic and that actual workloads may see very different scaling. The theorem title says "Under XY routing" but the abstract says "we prove that phantom load amplification grows quadratically with grid size" without the XY + uniform caveats.

2. [W2] **Workload patterns are simplistic abstractions.** "Ring All-Reduce" and "MoE Expert" are described as communication patterns but no detail is given on how they were generated. How many experts in MoE? What sparsity? What is the token routing policy? Real MoE traffic (e.g., DeepSeek-V3 with 256 experts, top-6 routing) has very different characteristics from a toy sparse all-to-all. Without specifying the exact traffic matrix generation procedure, reproducibility is limited.

3. [W3] **BookSim validation is thin.** Only three configurations are tested (K=8, K=8big, K=16) with one traffic pattern each. The paper characterizes six workloads analytically but validates with BookSim using only synthetic netlist-generated traffic. Where is the BookSim evaluation of MoE traffic, which was identified as the worst case? This is a missed opportunity. Additionally, the 2x2 mesh per chiplet is unrealistically small -- real chiplets have much larger internal networks that would affect border router congestion differently.

4. [W4] **Missing comparison to prior topology optimization work.** The paper compares five allocation strategies but does not compare against Kite's heterogeneous topologies or any other published NoI topology. The Related Work table (Table I) shows Kite does "NoI Topo" but no quantitative comparison is made. If Kite already accounts for heterogeneous link widths (which it does), how much of the phantom load problem does it implicitly address?

5. [W5] **Greedy algorithm has no approximation guarantee.** The paper acknowledges this ("Formal approximation bounds remain future work") but for a paper that presents itself as characterization-first, the mitigation section still relies heavily on a heuristic with no quality guarantee. The ablation (Table VIII) shows greedy beats random and fully-connected, but these are weak baselines. What about an ILP-based optimal solution for small K to bound the gap?

6. [W6] **The "routing-algorithm-independent" claim is overstated.** Table III shows ECMP reduces imbalance from 8.2x to 2.3x at K=16. That is a 3.6x reduction -- hardly "independent." What the paper actually shows is that no routing algorithm ELIMINATES phantom load, which is a weaker (but still useful) claim. The abstract and introduction should be more precise.

## Questions for Authors

1. [Q1] Table III: YX routing shows exactly 2x the max load and avg load of XY in every row. Is this expected by symmetry, or is this a bug in the evaluation? The imbalance ratio is identical for XY and YX, which makes sense, but the absolute values doubling is surprising.

2. [Q2] How sensitive is the greedy placement to the traffic matrix? If I design express links for all-to-all traffic but run MoE, how much of the improvement is lost? This is critical for practical design -- chiplet topology is fixed at manufacturing time but workloads change.

3. [Q3] The paper claims express links at distance d have latency 2d cycles. Is this a linear model? Real interposer wire delay is RC-dominated and grows quadratically with length. At what distance does the delay model become unrealistic?

4. [Q4] Table V shows "Traffic prop." at K=8 gives rho_max=8.2 for ALL three budget levels (3x, 4x, 6x). This is suspicious -- more budget should always help. Is traffic-proportional ignoring the budget entirely and just distributing proportionally regardless of total?

## Minor Issues

- Abstract: "6x imbalance persists at K=32" -- this is with ECMP (Table III shows 6.1x). Should specify the routing algorithm.
- Section III-B: "Since each adjacent link has exactly 2 direct flows (one per direction)" -- this assumes uniform all-to-all. Should state the assumption explicitly here, not just at the beginning of the subsection.
- Table II: "Imbal." column for 3x3 grid shows 1.0. This means all links have equal amplification in a square grid with odd dimensions? Worth noting explicitly.
- Algorithm 1: Line 5 says "Route traffic on topology A union {c} (Dijkstra)" -- Dijkstra finds shortest paths, but for weighted links with differential bandwidth, is it shortest-path or minimum-cost routing? This matters for the differential bandwidth experiments.
- Section V (Discussion): "Greedy outperforms even fully-connected topologies by 2.5x" -- this is a comparison of rho_max values from Table VIII (39.0 vs 15.3), which is indeed about 2.5x. But fully-connected spreads budget across O(K^2) pairs; this is not a fair comparison because no one would uniformly distribute across all pairs.

## Rating

- Novelty: 3/5
- Technical Quality: 3/5
- Significance: 3/5
- Presentation: 4/5
- Overall: 3.0/5
- Confidence: 4/5

## Score Justification vs Iteration 1

Novelty improved from 2 to 3: The reframing as characterization, closed-form analysis, and routing independence study make this more than "just express links." The differentiation from on-chip express channels is now present, though could be stronger.

Technical quality remains at 3: The closed-form analysis is rigorous, but BookSim validation is too thin (3 configs, no workload-specific validation), workload patterns lack detail, and the area/power claim is unsupported.

Significance remains at 3: The counter-intuitive results (traffic-proportional worse than uniform, routing independence) are valuable for practitioners. However, the impact is limited by K=8 being the current production regime where improvements are small.

Presentation improved and remains strong at 4: The paper is well-organized, figures are clear, and the honest framing of limitations is commendable.

## Decision

**Borderline** -- The revision substantially improves on iteration 1. The reframing as characterization with closed-form analysis is the right call, and the routing-independence and counter-intuitive allocation results are genuine contributions. However, three issues prevent a clear accept: (1) BookSim validation is too narrow -- the paper identifies MoE as the worst case but never validates it in simulation; (2) workload pattern generation is underspecified, limiting reproducibility; (3) the area/power claim for express links remains unsupported. Addressing these would likely push the paper to accept.
