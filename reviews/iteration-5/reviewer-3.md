# Review -- Reviewer 3 (ML/Application Expert), Iteration 5

## Summary
The paper has undergone a major reframing since iteration 4. The thesis is now explicitly cost-focused ("same performance at 2.3x fewer links"), the evaluation adds 8x8 internal mesh validation to rule out border-capacity artifacts, the MoE negative result is retained, and the structure is significantly tightened -- the paper now reads as a focused 6-page argument rather than an expansive characterization study. The cost-performance comparison across three internal mesh sizes (2x2, 4x4, 8x8) is the most convincing presentation of the express link advantage to date.

## Assessment of Changes from v4

**Major change: Cost-focused thesis reframing.** The paper's central claim is no longer "express links reduce latency" but "express links achieve the same latency at 2.3x fewer links." This is a significant and correct reframing. The cost argument is more actionable for chiplet architects than a latency argument because interposer link count directly maps to PHY area, power, and manufacturing cost. The abstract, introduction, evaluation, and conclusion all consistently use the cost framing. This resolves a presentational weakness that has been present since iteration 1: the paper was always implicitly about cost (phantom load forces over-provisioning), but earlier versions framed it as a performance story.

**Major change: 8x8 internal mesh validation.** This directly addresses Reviewer 1's persistent concern (W4 in iter-4: "K=16 with a larger internal mesh is absent"). The 8x8 internal mesh provides 8 border routers per edge, meaning adjacent links have ample capacity -- 8 links per adjacent pair vs. 2 in the 2x2 case. The key finding: express links still provide 2.3x cost advantage at 8x8, and the advantage actually *increases* with internal mesh size (1.0x at 2x2, 2.0x at 4x4, 2.3x at 8x8). This is the strongest evidence that the express link benefit is not an artifact of constrained border capacity. Table III (cost-matching table) is clean and compelling.

**Iter-4 W1 (10-30% comm fraction): DROPPED -- no longer in paper.** The cost-focused reframing eliminates the need for this claim. Guideline 7 now states the bottleneck argument directly: "For batch-1 LLM decode, per-layer communication (~0.1 us) is negligible versus memory access (~600 us). Phantom load mitigation matters for communication-heavy regimes: large-batch training, multi-query inference." The unsubstantiated "10-30%" figure no longer appears. This is the correct resolution: rather than substantiating a difficult-to-ground claim, the paper simply states that NoI optimization matters when communication is a significant fraction (leaving the reader to evaluate their own workload) and provides the batch-1 counter-example to calibrate expectations. My concern from iterations 2-4 is resolved by removal of the problematic claim.

**Iter-4 W2 (MoE params unspecified): NOT addressed.** The paper still describes MoE traffic as "sparse all-to-all traffic" without specifying expert count, top-k, or capacity factor. Section 5.5 says the greedy algorithm places "zero express links" for MoE but does not specify the MoE configuration used. This is the fourth iteration where I have flagged this. See W1 below for detailed assessment of whether this still matters under the new framing.

**Iter-4 W3 (MoE sensitivity analysis): NOT addressed.** No sensitivity analysis across expert counts.

**Iter-4 W4 (Guideline consistency): ADDRESSED by restructuring.** The guidelines are now simplified to 7 items with consistent numbering. Guideline 3 recommends "3-4 express links capture 60% of total improvement" and separately states "Physical overhead: ~0.6% area, ~2% TDP for 10 links." The 3-4 vs. 10 distinction is now clearer: 3-4 is the recommended minimum, 10 is the upper-bound cost estimate.

**Previous paper structure vs. this version.** The paper has been significantly compressed. The multi-table evaluation with separate BookSim configurations, the Table VII MoE anomaly discussion, the detailed Kite-like comparison -- all are condensed into a tighter narrative. The previous version had ~9-10 tables; this version has 4 tables and 1 figure. This is a better paper structurally, though some detail is lost (notably, the per-routing-algorithm BookSim validation that was present in earlier versions).

## Strengths

1. [S1] **The 8x8 internal mesh result is the paper's most important addition.** The concern that express links only help because 2x2 internal meshes artificially constrain border capacity was the strongest technical objection to the paper's claims. Table III showing 2.3x cost savings at 8x8 -- where each adjacent pair has up to 8 links -- eliminates this objection. Moreover, the monotonic increase in cost advantage (1.0x -> 2.0x -> 2.3x) tells a compelling story: when adjacent links have more room to brute-force the problem, the waste from phantom load taxation becomes *larger*, making express links *more* valuable, not less.

2. [S2] **Cost framing is the right framing.** "Same performance, 2.3x fewer links" is a strictly more actionable claim than "better performance at the same cost." Chiplet architects budget interposer links as a scarce resource (PHY area, power, routing channels). Showing that express links cut the link budget by 2.3x while maintaining performance targets directly maps to design decisions. The cost-matching table (Table III) is the kind of result an architect can take directly to a design review.

3. [S3] **The ablation (Section 5.4) is crisp and actionable.** Random express placement being worse than adjacent uniform (congestion 85.4 vs. 62.8) while greedy outperforms even fully-connected by 2.5x (15.3 vs. 39.0) tells the reader two things: (a) express links without placement intelligence are harmful, and (b) smart placement on a sparse set of express links beats brute-force full connectivity. Both are useful design insights.

4. [S4] **MoE negative result properly retained.** Section 5.5 showing greedy places zero express links for MoE, with BookSim confirmation that all strategies perform similarly, remains the paper's most honest and most useful finding. The workload-aware framing ("express for dense, adjacent for sparse") is coherent and actionable.

5. [S5] **Physical overhead section is well-grounded.** The CoWoS-based calculation (56 mm^2 for 10 express links at average distance 2.5, 0.56% of interposer, 15 W or 2.1% TDP) provides concrete numbers. The argument that this cost is offset by the 2.3x reduction in total links is sound -- the net PHY area and power savings from eliminating ~96 unnecessary adjacent links likely far exceeds the cost of 10 express wires.

6. [S6] **Differential bandwidth analysis (Section 5.6) is the right follow-up.** Showing that express links still provide 1.8-2.2x improvement at 75% BW decay and 1.6-1.8x at 50% decay addresses the practical concern that longer wires have lower bandwidth. The conclusion -- "the benefit comes from hop reduction, not raw bandwidth" -- is the correct insight.

## Weaknesses

1. [W1] **MoE parameters still unspecified (carried from iter-2 W2, iter-3 W2, iter-4 W2).** This is the fifth iteration where this is flagged. The paper says "sparse MoE traffic on K=16" without specifying expert count, top-k, or capacity factor. Under the new cost framing, this matters specifically because the claim "greedy places zero express links" depends on the traffic sparsity, which depends on these parameters. An 8-expert top-2 model on K=16 has each chiplet talking to 2/16 = 12.5% of chiplets per token dispatch; a 128-expert top-2 model on K=16 has each chiplet talking to a different subset of 2/128 experts per token, creating a much sparser and more uniform traffic pattern. These produce fundamentally different phantom load profiles. The paper's MoE finding may hold across this range, or it may not -- and the reader cannot assess this without knowing the configuration. A single sentence would suffice: "We model N experts with top-k routing, distributed round-robin across K chiplets."

   **Impact assessment under new framing**: The MoE result is now positioned as a negative-result validation of the greedy algorithm's workload awareness. The cost-focused thesis does not depend on MoE; it depends on the dense-traffic 2.3x result. The MoE finding strengthens the paper by showing the approach is not blindly pro-express, but it is not load-bearing for the main claim. Therefore, while this remains an unresolved gap, its impact on the paper's core contribution is lower than in previous iterations where MoE was presented as a co-equal finding.

2. [W2] **Adjacent-only ceiling (Section 5.3) is asserted, not shown.** The text says "Adjacent uniform and Kite-like produce nearly identical performance despite MinMax's optimal allocation" but provides no numbers. Previous iterations included a BookSim table (Table VI in v4) with specific latency values (54.3 vs. 54.4 at rate 0.01). The compressed paper drops this data, leaving the claim as an assertion. For the paper's most important supporting argument -- that adjacent-only optimization is fundamentally limited -- a single data point or even an inline "(54.3 vs. 54.4 cycles at injection rate 0.01)" would suffice. Without it, a skeptical reader may wonder whether Kite-like actually improves meaningfully and express links are competing against a straw-man uniform baseline.

3. [W3] **Routing algorithm table (Table II) data has unexplained features.** At 4x4, YX routing shows Max alpha = 223 while XY shows 111 -- a 2x difference for dimension-ordered routing variants that should be symmetric on a square grid. If the grid is 4x4 (square), XY and YX should produce the same max alpha under uniform traffic by symmetry (just transposed). This is either a non-square grid effect (but the label says 4x4) or a bug in the computation. Similarly, Valiant's Max alpha = 347 at 4x4 with imbalance 3.1 implies total load is much higher than XY (as expected from Valiant's path doubling), but the table does not normalize for this. A footnote explaining that Valiant's higher max alpha is expected because it doubles path length would help.

4. [W4] **The greedy algorithm's runtime and scalability are underspecified.** The text says "3 seconds for K=16" but does not specify the hardware, the budget L, or how runtime scales with K. For the target audience (chiplet architects at DATE), knowing whether this runs in seconds or hours at K=32 or K=64 matters for practical adoption. A single sentence would suffice.

5. [W5] **Missing comparison to CNSim.** The bibliography cites CNSim (Feng and Wei, USENIX ATC 2024) but the paper does not discuss it. CNSim is a cycle-accurate chiplet network simulator that models inter-chiplet communication specifically, as opposed to BookSim which is a general NoC simulator adapted for chiplet use. If CNSim was considered and rejected, a sentence explaining why BookSim was preferred (e.g., maturity, community adoption, configuration flexibility) would strengthen the methodology.

## Questions for Authors

1. [Q1] What expert count and top-k were used for the MoE traffic model? This has been asked in iterations 2, 3, 4, and now 5.

2. [Q2] In Table II, why does YX routing show Max alpha = 223 at 4x4 while XY shows 111? On a square grid with uniform traffic, these should be symmetric.

3. [Q3] Can you add the Kite-like vs. uniform numerical comparison back inline in Section 5.3? Even "(54.3 vs. 54.4 cycles)" from the previous version would suffice to substantiate the claim.

4. [Q4] Does the greedy algorithm's 3-second runtime at K=16 scale polynomially to K=32 and K=64? A single data point for K=32 would address whether this is practically usable at larger scales.

## Detailed Comments

- The title "Breaking the Cost-Performance Ceiling of Chiplet Networks with Express Links" is punchy and accurate. It correctly identifies the contribution (breaking a ceiling) and the mechanism (express links). The "cost-performance" framing matches the paper's thesis.
- The introduction's worked example (168 adjacent links vs. 72 express links for the same target latency) is highly effective. It makes the 2.3x claim concrete immediately.
- The closed-form analysis (Section 3) is unchanged and remains the paper's strongest theoretical contribution. The Theta(K) amplification scaling is clean and memorable.
- Table I (phantom load scaling) remains well-designed. The progression from alpha_max=2 at K=4 to alpha_max=128 at K=64 tells the story at a glance.
- The workload sensitivity table (Table III in v4, now Table III workload table at K=32) is useful but the "Phantom%" column could use a brief definition in the caption or text -- it is not obvious whether this means "percentage of links carrying phantom traffic" or "percentage of total traffic that is phantom."
- The physical overhead argument (Section 5.5) is more convincing under the cost framing: "10 express links cost 56 mm^2 and 15 W, but they *eliminate* ~96 unnecessary adjacent links, saving far more PHY area and power." This offset argument was implicit in earlier versions but is now explicit. Good.
- Guideline 7 ("NoI is not always the bottleneck") remains the paper's most practically useful guideline. It prevents chiplet architects from optimizing NoI when the bottleneck is HBM bandwidth.

## Rating
- Novelty: 3/5
- Technical Quality: 4/5
- Significance: 4/5
- Presentation: 4/5
- Overall: 4/5 (Accept)
- Confidence: 4/5

## Score Changes from Iteration 4
- Significance: 3.5 -> 4. The cost framing + 8x8 internal mesh validation together make the practical contribution substantially stronger. The 2.3x cost saving on a realistic mesh configuration is a concrete, actionable result that chiplet architects can use directly. The monotonic increase in cost advantage with mesh size (1.0x -> 2.0x -> 2.3x) suggests the benefit will persist or grow in production configurations.
- Technical Quality: 3.5 -> 4. The 8x8 mesh experiment addresses the strongest technical objection (border-capacity artifact) from previous iterations. The cost-matching methodology (Table III) is clean and reproducible.
- Overall: 3.5 -> 4. The combination of cost reframing, 8x8 validation, and structural tightening pushes the paper from borderline to clear accept.

## Decision
**Accept** -- This iteration resolves the most important structural weakness of the paper: the thesis is now cost-focused, and the 8x8 internal mesh validation eliminates the border-capacity artifact concern. The 2.3x cost saving at K=16 on realistic mesh configurations is a concrete, actionable result.

My persistent concern about MoE parameter specification (flagged since iteration 2) remains unaddressed but is now less impactful under the cost framing -- the MoE result is a negative-result validation, not the paper's core claim. A single sentence specifying the MoE configuration would still improve reproducibility and is a trivial fix for the camera-ready.

The one substantive issue I would flag for camera-ready is W2 (Section 5.3 missing the Kite-like numerical comparison). The claim that "adjacent-only optimization is fundamentally limited" is the paper's most important supporting argument, and it currently lacks the specific numbers that were present in v4. Adding "(54.3 vs. 54.4 cycles at rate 0.01)" inline would take 10 words and close this gap.

The paper is a clear contribution to DATE: it identifies a real cost problem (phantom load forcing 2-3x link over-provisioning), proves it analytically, validates it across mesh sizes, and provides a workload-aware solution with honest negative results. The design guidelines form a complete decision framework for chiplet NoI architects.
