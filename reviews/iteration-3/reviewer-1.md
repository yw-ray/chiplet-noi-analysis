# Review -- Reviewer 1 (Architecture Expert), Iteration 3

## Summary
This paper identifies and characterizes "phantom load" in chiplet Network-on-Interposer (NoI): intermediate links in multi-hop 2D grids accumulate routing traffic far exceeding their direct demand. The authors derive closed-form expressions (under XY routing with uniform traffic) showing center-link amplification grows as Theta(K), demonstrate this effect persists across four routing algorithms (XY, YX, ECMP, Valiant), evaluate six LLM communication patterns (MoE is worst at 88% phantom links), and compare five mitigation strategies. Key findings include traffic-proportional allocation being 1.5x worse than uniform, express links achieving 2.0--2.6x improvement for dense traffic, and express links providing zero benefit for sparse MoE traffic. BookSim validation now covers both dense (46% latency reduction at K=16) and MoE (confirming no express benefit) regimes.

## Assessment of Iteration-2 Concerns

**[W1] Closed-form limited to XY + uniform.** ADDRESSED. The abstract now explicitly states "Through closed-form analysis under XY routing with uniform traffic" (line 28). Theorem 1 carries the precondition in its statement. The paper no longer hides the XY + uniform assumption behind a general claim. The abstract also frames the routing-algorithm result more carefully: "This structural effect persists across routing algorithms: ECMP and Valiant routing reduce imbalance but cannot eliminate it." This is precise and honest.

**[W2] Workload patterns underspecified.** PARTIALLY ADDRESSED. The paper now mentions "parameterized communication patterns" and the Limitations section acknowledges "Traffic matrices are parameterized, not from production RTL." However, the generation procedure (how many experts in MoE, what sparsity, etc.) is still not detailed enough for full reproducibility. For a DATE paper this is acceptable given space constraints; for a longer venue it would need more detail.

**[W3] BookSim too narrow, no MoE validation.** ADDRESSED. Table VII now shows MoE BookSim results at K=16. The result is genuinely interesting and honest: the greedy algorithm places zero express links for MoE traffic, and uniform allocation actually outperforms both Kite-like and express strategies. This is the kind of negative result that strengthens the paper's credibility. The paper now validates both the positive case (dense traffic, express wins) and negative case (sparse MoE, express does not help), which was my primary concern in iteration 2.

**[W4] Area/power unsupported.** ADDRESSED. Guideline 6 now provides a CoWoS-based calculation: "0.8 um wire pitch, UCIe Standard PHY, 10 express links at average distance 2.5 require ~56 mm^2 interposer area (0.56% of 100x100 mm^2) and ~15 W (2.1% of 700 W TDP)." This is a proper back-of-envelope with technology parameters. The 2.1% TDP is non-trivial and the paper correctly notes "This is a real cost that should be weighed against the throughput benefit." Much better than the previous single unsupported sentence.

**[W5] Greedy has no approximation guarantee.** NOT ADDRESSED (acknowledged). The Discussion section still says "Formal approximation bounds remain future work." For a characterization paper at DATE, this is acceptable. The paper does not claim the greedy algorithm is optimal.

**[W6] "Routing-algorithm-independent" overstated.** ADDRESSED. The abstract and body now use "persists across routing algorithms" instead of "routing-algorithm-independent." The abstract states "ECMP and Valiant routing reduce imbalance but cannot eliminate it (6x imbalance at K=32)." This is the correct framing: phantom load is not eliminated by routing, not that routing has no effect.

**[NEW] Kite-like baseline.** ADDRESSED. The evaluation includes "MinMax adjacent" as a Kite-like baseline throughout (Tables V, VII). The Discussion section explicitly compares to Kite and explains why adjacent-only optimization is insufficient for K>=16 with dense traffic. Table VII shows Kite-like performing similarly to uniform for MoE -- an honest result. The Related Work now frames this clearly.

**[NEW] E2E analysis.** ADDRESSED. Guideline 7 and the Discussion section include a batch-1 inference analysis showing ~0.1 us communication vs ~600 us memory access per layer. This is an important reality check: the paper honestly states that NoI optimization is irrelevant for single-token inference. This prevents overclaiming and shows intellectual maturity.

## Strengths

1. [S1] **Closed-form analysis remains the strongest contribution.** Theorem 1 with explicit preconditions, computational validation up to R,C<=8, and the Theta(K) scaling result provide a foundation for understanding phantom load. The preconditions are now clearly stated, making the theorem rigorous.

2. [S2] **MoE BookSim validation is the most important addition.** Table VII showing express links place zero links for MoE traffic is a powerful result. It transforms the paper from "express links are great" to "here is when to use which strategy" -- a much more nuanced and useful message. The fact that the greedy algorithm correctly identifies that express links are not beneficial for MoE demonstrates the framework's generality.

3. [S3] **Counter-intuitive results remain compelling.** Traffic-proportional being 1.5x worse than uniform (Table V), and express links being useless for MoE, are the kinds of findings that change practitioner behavior. These two results alone justify publication.

4. [S4] **Physical overhead quantification adds credibility.** The CoWoS-based area/power calculation (0.56% area, 2.1% TDP for 10 express links) grounds the recommendations in physical reality. Notably, 2.1% TDP is not negligible, and the paper is honest about this.

5. [S5] **E2E analysis prevents overclaiming.** Guideline 7 stating that NoI is not the bottleneck for batch-1 inference is a commendable addition. Too many architecture papers fail to contextualize their contribution within the full system. This section shows the authors understand the practical implications.

6. [S6] **Seven design guidelines are actionable.** The guidelines map directly from workload characteristics to strategy choices, with quantitative thresholds (alpha_max < 5 -> simple allocation, alpha_max > 10 -> topology intervention). A chiplet architect could use these immediately.

## Weaknesses

1. [W1] **BookSim MoE result raises questions about express strategy performance.** Table VII shows that for MoE traffic, Express (0 placed) has lat@0.015 = 43.3 and peak throughput = 0.0150, which is significantly worse than Uniform (37.8, 0.0229) and even Kite-like (39.6, 0.0212). If greedy placed zero express links, the resulting topology should be identical to adjacent uniform. Why does "Express (0 placed)" perform worse than "Uniform"? This suggests some overhead from the express routing framework even when no express links are placed, or a difference in how the base adjacent allocation is done. This discrepancy needs explanation.

2. [W2] **Kite comparison is approximate, not direct.** The "Kite-like (MinMax adjacent)" strategy is the authors' own implementation, not actual Kite. Real Kite uses detailed interconnect modeling including wire delay, power, and area in its optimization loop. The MinMax formulation optimizes only rho_max with uniform link costs. The Discussion section acknowledges this ("approximates this approach"), but the gap between MinMax adjacent and actual Kite could be significant. This should be stated as a limitation rather than presented as a validated comparison.

3. [W3] **Workload generation still lacks key parameters.** For MoE specifically: how many experts, top-k routing, expert capacity factor, and whether experts are mapped to chiplets uniformly or with locality awareness are all critical parameters that affect traffic patterns. The paper identifies MoE as the most vulnerable workload but provides the least detail on how MoE traffic was generated.

4. [W4] **The 2x2 mesh per chiplet is still unrealistically small.** Real chiplets (AMD MI300X XCDs, NVIDIA Blackwell dies) have large internal networks. A 2x2 mesh provides only 2 border routers per edge, which artificially constrains adjacent link count and may exaggerate phantom load relative to real designs with more border routers. The paper should discuss sensitivity to internal mesh size.

5. [W5] **Hybrid TP+MoE result in Table VII is incomplete.** Only Uniform and Kite-like are shown for Hybrid TP+MoE, with identical results (25.5, 26.9, 0.0250). Where is the Express strategy result for this workload? And why are Uniform and Kite-like identical -- is this because the traffic pattern is symmetric enough that MinMax converges to uniform?

## Questions for Authors

1. [Q1] Table VII: Why does "Express (0 placed)" perform significantly worse than "Uniform" when zero express links were placed? The topologies should be equivalent.

2. [Q2] For the CoWoS calculation in Guideline 6: what is the assumed UCIe PHY power and area per link? The 15 W for 10 express links implies 1.5 W per link, which seems high for a Standard PHY -- can you break down the power into SerDes, PHY, and routing components?

3. [Q3] Guideline 7 says communication is ~0.1 us/layer for batch-1 at K=16. What model size and tensor parallel degree is assumed? For a 70B parameter model with TP=16, the activation tensor per layer is much larger than for a 7B model with TP=4.

4. [Q4] Table V: Traffic-proportional still shows 8.2 for ALL budget levels at K=8 (same as iteration 2, my Q4 was not answered). Is this because traffic-proportional allocation does not use the budget parameter -- it just distributes the budget proportionally regardless of total?

## Minor Issues

- Table VII caption says "MoE Traffic" but the table also includes "Hybrid TP+MoE" -- caption should reflect both.
- Guideline 3 says "<0.5% interposer area, <0.1% TDP" but Guideline 6 says "0.56% area, 2.1% TDP." These are inconsistent. Guideline 3 appears to use the old unsupported numbers while Guideline 6 has the new CoWoS-based ones. Guideline 3 should be updated to match.
- The Discussion section mentions "communication can reach 10--30% of total time" for large-batch training but does not cite a source or provide the calculation.
- Algorithm 1 still uses "Dijkstra" without clarifying whether this is shortest-path by hop count or by latency (which differs for express links with 2d-cycle delay).

## Rating

- Novelty: 3.5/5
- Technical Quality: 3.5/5
- Significance: 3.5/5
- Presentation: 4/5
- Overall: 3.5/5
- Confidence: 4/5

## Score Justification vs Iteration 2

**Novelty improved from 3 to 3.5.** The MoE negative result (express links provide no benefit) adds a genuinely new dimension. The paper now tells a complete story: characterization + when mitigation works + when it does not. The workload-contingent guidelines are more useful than a blanket "use express links" recommendation.

**Technical quality improved from 3 to 3.5.** BookSim now validates both positive (dense) and negative (MoE) cases. The CoWoS-based area/power calculation replaces unsupported claims. Theorem 1 preconditions are explicit. The remaining gap is the Q1 discrepancy in Table VII (Express 0-placed worse than Uniform) and incomplete Hybrid TP+MoE results.

**Significance improved from 3 to 3.5.** The E2E analysis (Guideline 7) and honest framing of when express links do NOT help make the paper more useful to practitioners. The seven design guidelines with quantitative thresholds are actionable. The paper now avoids the trap of overselling a single technique.

**Presentation remains at 4.** Well-organized, clear figures, and honest limitations. The minor inconsistency between Guidelines 3 and 6 should be fixed.

## Decision

**Weak Accept** -- This iteration addresses the three primary concerns from iteration 2: (1) MoE BookSim validation is now present and produces an honest negative result; (2) the CoWoS-based physical overhead calculation grounds the recommendations; (3) the abstract and theorem properly caveat the closed-form analysis. The paper tells a complete characterization story with nuanced, workload-contingent guidelines. The remaining weaknesses (Table VII discrepancy, approximate Kite comparison, underspecified MoE parameters, small internal mesh) are real but do not undermine the core contributions. For DATE, the characterization depth, counter-intuitive findings (traffic-proportional worse than uniform, express useless for MoE), and actionable guidelines constitute a solid contribution. The inconsistency between Guidelines 3 and 6 must be fixed in camera-ready.
