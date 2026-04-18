# Review -- Reviewer 5 (Skeptic), Iteration 6

## Summary

Iteration 6 restores full paper content (all tables, sensitivity analysis, ablation, design guidelines) with the cost thesis framing from iteration 5. The paper now includes: (1) Kite-like specific numbers (54.3 vs 54.4) in the adjacent-only ceiling section, (2) ablation table with greedy vs random vs fully-connected, (3) sensitivity analysis covering 9/10 random seeds, grid shapes, and diminishing returns, (4) net PHY saving calculation ("72 express replace 168 adjacent, saving ~96 PHY modules (~48 mm^2 PHY area)"), and (5) explicit Limitations sentences acknowledging greedy suboptimality at high budgets and BookSim internal mesh latency inflation.

My iteration-5 score dropped from 3.75 to 3.25 due to three specific concerns: (a) the 8x8 express reversal at 5-6x budget, (b) wire-length-adjusted savings being ~1.67x not 2.3x, and (c) unrealistically high 8x8 absolute latencies. This review evaluates whether the iteration-6 changes address those concerns.

## Assessment of Iteration-5 Concerns

### [W1] 8x8 express reversal at 5-6x budget -- inadequately disclosed

**PARTIALLY ADDRESSED.** The Limitations section (line 372) now reads: "The greedy algorithm shows suboptimal behavior at very high budgets ($\geq$5$\times$ per pair) on 8$\times$8 meshes; ILP formulation could improve this." This is the same single sentence from iteration 5. It has not been expanded or moved into the main results.

What I asked for in iteration 5:
1. Present the full 8x8 budget sweep data -- **NOT DONE.** Fig. 1 (fig_cost_performance.pdf) is referenced but the paper still does not include a table or explicit text showing the reversal at 5-6x.
2. Analyze the root cause of the 5-6x reversal -- **NOT DONE.** The paper attributes it to the greedy algorithm without investigation.
3. Qualify the 2.3x claim with its applicable range -- **NOT DONE.** The abstract still states "2.3x fewer inter-chiplet links" without qualification. The introduction (line 41) still states "only 72 links suffice when express links bypass the phantom load" without noting this is one operating point.
4. Either soften the title or show the reversal is an algorithm problem -- **PARTIALLY DONE.** The Limitations sentence frames it as "greedy algorithm shows suboptimal behavior," implying it is an algorithm problem, not a fundamental express link limitation. But this is an assertion without evidence. The paper does not distinguish between "the greedy algorithm places express links poorly at high budgets" and "express links inherently create routing pathologies at high budgets."

**Verdict: Marginally improved.** The Limitations sentence is honest, but my core complaint stands: a paper titled "Breaking the Cost-Performance Ceiling" that has a region where express links CREATE a lower ceiling than adjacent-only needs to confront this more directly. The single sentence in Limitations is necessary but not sufficient.

### [W2] 2.3x cost claim cherry-picked from specific operating point

**NOT ADDRESSED.** The abstract (line 30) claims "2.3x fewer inter-chiplet links" and the introduction (line 41) presents "72 express links vs 168 adjacent links" as the headline result. Both are unchanged from iteration 5. No qualification of the applicable budget range is provided outside the Limitations section. The claim remains presented as general when it holds at a specific operating point (3x budget/pair, rate 0.005, 8x8 mesh, seed 42).

### [W3] 8x8 absolute latencies unrealistically high (BookSim artifact)

**ADDRESSED.** The Limitations section (line 372) now states: "BookSim models internal mesh as store-and-forward routers, not the high-speed crossbars used in real chiplets; absolute latencies for 8x8 are thus inflated, though relative comparisons remain valid."

This is a good addition. The acknowledgment that real chiplets use high-speed crossbars (not store-and-forward meshes) and that absolute latencies are inflated provides the reader with the right mental model. The claim that "relative comparisons remain valid" is the key assertion, and it is defensible: if both adjacent and express configurations suffer the same internal mesh overhead, the *ratio* between them should be preserved even if the absolute numbers change.

However, I note this claim has a subtlety the paper does not address: express links and adjacent links may interact *differently* with internal mesh congestion. An express link concentrates all its traffic at a single border router endpoint, potentially creating a localized hotspot in the internal mesh. Adjacent links distribute traffic across all border routers of a given edge. At 8x8 (8 border routers per edge), this difference matters less than at 2x2, but it is not zero. The "relative comparisons remain valid" assertion would be stronger with evidence -- e.g., showing the same express-vs-adjacent ratio at a lower injection rate where internal congestion is minimal.

**Verdict: Adequately addressed for a conference paper.** The disclosure is honest and the reasoning is sound, though not rigorously proven.

### [W4] Wire-length-adjusted cost comparison missing

**PARTIALLY ADDRESSED.** The new Physical Overhead section (line 346) provides a net PHY saving calculation: "72 express links replace 168 adjacent links, saving ~96 PHY modules (~48 mm^2 PHY area)." This is a useful addition that quantifies the *PHY area* saving, which is arguably more relevant than interposer wire area for cost.

However, this calculation conflates the 72-link express configuration with "72 express links." In my iteration-5 analysis, the 72-link express configuration at 3x budget contains ~53 adjacent links + ~19 express links (totaling 72), not 72 express links. The text "72 express links replace 168 adjacent links" implies all 72 are express, which is misleading. The actual comparison is: "a mixed topology of ~53 adjacent + ~19 express links (72 total) achieves the same latency as 168 adjacent links."

More importantly, the wire-length-adjusted cost comparison I requested in Q4 is still absent. Let me redo the calculation:
- Express configuration: 53 adjacent (distance 1) + 19 express (avg distance ~2.5) = 53 + 47.5 = 100.5 wire-distance-units
- Adjacent configuration: 168 * 1 = 168 wire-distance-units
- Wire-adjusted saving: 168 / 100.5 = 1.67x

The paper reports 2.3x (link count) but the wire-adjusted saving is ~1.67x. The difference matters because interposer routing area scales with wire length. The PHY area saving of ~48 mm^2 is real, but the interposer wire area saving is smaller than the headline number suggests.

**Verdict: Not fully addressed.** The PHY saving is a good addition but the "72 express links replace 168" phrasing is inaccurate, and the wire-length-adjusted comparison is still missing.

### [W5] Ablation numbers disconnected from experimental framework

**ADDRESSED.** Table IV (line 317) now explicitly states the configuration: "$K$=16, $L$=72, 2$\times$2" and reports $\rho_{\max}$ as the metric. The configuration is now specified and the metric is consistent with the analytical framework (rho_max from the link-level model, not BookSim latency). The values (62.8, 85.4, 39.0, 15.3) are from the link-level model at 2x2 mesh, which is the same model used in the mitigation comparison (Table II).

**Verdict: Resolved.** The ablation is now properly contextualized.

## Assessment of New Additions

### Kite-like numbers restored (Section V.C)

The adjacent-only ceiling section (line 309) now includes the specific numbers: "latency 54.3 vs. 54.4 at rate 0.01, both saturating at rate 0.015 (latency >800)." This was the strongest finding from iteration 4 that I noted was "downgraded" in iteration 5. Its restoration is valuable. The near-identical Kite-like and Uniform results (54.4 vs 54.3 -- less than 0.2% difference) remain the paper's most striking empirical demonstration that adjacent-only optimization is futile at K=16.

### Ablation table (Section V.D)

Table IV shows four placement strategies at K=16, L=72, 2x2 mesh. The key findings:
- Random express is *worse* than adjacent uniform (85.4 vs 62.8). This demonstrates that naive express placement hurts performance.
- Greedy outperforms fully-connected by 2.5x (15.3 vs 39.0). This shows that selective placement beats uniform express distribution.
- The 4.1x gap between greedy and adjacent uniform (15.3 vs 62.8) quantifies the express link advantage at the link-level model.

This is a useful ablation that answers the question "is it express links or the greedy algorithm?" The answer is both: express links are necessary (adjacent uniform is 62.8) but not sufficient (random express is 85.4). The greedy algorithm is critical for realizing the benefit.

One concern: this ablation is at 2x2 mesh, not 8x8. Given that the paper's headline claim centers on the 8x8 mesh result, the ablation should ideally be repeated at 8x8 to confirm the same ordering holds. The greedy reversal at 5-6x budget on 8x8 suggests the ablation results may not transfer cleanly to larger meshes.

### Sensitivity analysis (Section V.F)

The sensitivity analysis (line 338-342) reports:
- Workload robustness: 9/10 seeds show express advantage, avg 3.05x
- Diminishing returns: first 3-4 express links capture 60% of improvement
- Grid shape: 1.7x for 1x8 chains, up to 2.5x for compact 4x2

These are all useful robustness checks. The 9/10 seeds result is particularly important -- it means one seed out of ten does *not* show an express advantage, which aligns with my concern about workload-specific pathologies. The paper should report what happens for the 1/10 failing seed (is it near-parity, or is express worse?).

The diminishing returns result (60% from first 3-4 links) is practically valuable and supports the design guidelines.

### Net PHY saving (Section V.G)

Line 346: "72 express links replace 168 adjacent links, saving ~96 PHY modules (~48 mm^2 PHY area)."

As noted above, the phrasing "72 express links" is misleading -- the 72-link configuration contains a mix of adjacent and express links. The correct framing would be: "A 72-link mixed topology (adjacent + express) replaces a 168-link adjacent-only topology, saving ~96 PHY modules."

The ~48 mm^2 PHY area saving is significant -- this is real silicon area that could be used for compute, memory, or other interconnect. At roughly 0.5 mm^2 per UCIe Standard PHY module, 96 modules = 48 mm^2, which checks out. This is a concrete cost metric that goes beyond abstract link counts.

## Critical Remaining Issues

### Issue 1: The full 8x8 budget sweep is still hidden

This was my #1 request in iteration 5 and remains unaddressed. The paper presents the 8x8 result only at the favorable 3x budget point (Table III: 72 vs 168 links). Fig. 1 (fig_cost_performance.pdf) presumably shows the full sweep as a figure, but without seeing the figure directly, I must rely on the text description (line 281): "Express achieves lower latency at the same cost, or the same latency at fewer links, across all mesh sizes." This figure caption does not mention the reversal at 5-6x budget. If the figure is a smooth curve that happens not to show the non-monotonicity (due to line fitting or aggregation), then the reversal data is effectively invisible.

I maintain that the 5-6x reversal should appear explicitly in either a table or the text. Even a brief note like "At budgets exceeding 5x per pair on 8x8 mesh, greedy express placement degrades due to over-concentration of links on select express pairs; the cost advantage is most robust at 2-4x budget" would suffice.

### Issue 2: The 2.3x claim needs qualification in the abstract

The abstract states: "express links achieve the same latency target as adjacent-only topologies using 2.3x fewer inter-chiplet links." This is accurate for the 8x8 mesh at the specific target latency of ~200 cycles. But the abstract also says "validated in BookSim cycle-accurate simulation across 2x2, 4x4, and 8x8 internal mesh configurations." The savings at 2x2 are 1.0x (effectively zero), at 4x4 are 2.0x, and only at 8x8 are they 2.3x. Presenting 2.3x as the validated result "across" three meshes is misleading -- 2.3x is the *best* result, not the typical result. A more honest abstract would say "up to 2.3x fewer links" or report the range "1.0-2.3x fewer links depending on internal mesh size."

### Issue 3: The "72 express links" phrasing is factually incorrect

Line 41: "only 72 links suffice when express links bypass the phantom load." Line 346: "72 express links replace 168 adjacent links." The 72-link configuration is not 72 express links; it is ~53 adjacent + ~19 express. This distinction matters for the physical cost argument because express links at distance 2-3 consume more interposer routing resources than adjacent links. The paper should use "72 total links (including express)" or "a 72-link mixed topology" throughout.

## Strengths (Consolidated)

1. [S1] **Cost framing remains the right framing (retained from iter-5).** Table III directly answers the architect's cost question. The paper has improved substantially by centering on cost rather than raw performance.

2. [S2] **8x8 experiments address the core validity concern (retained).** Express advantage at 2-4x budget on 8x8 mesh, where adjacent links have ample border capacity, is genuine evidence for the phantom load thesis.

3. [S3] **Analytical foundation is solid (retained).** Theorem 1, Table I, routing independence (Table II), and workload sensitivity (Table III-workloads) are rigorous contributions independent of BookSim.

4. [S4] **Kite-like identical-saturation result restored.** The 54.3 vs 54.4 latency and identical saturation at rate 0.015 is the paper's strongest empirical finding. Its restoration from iteration 4 is welcome.

5. [S5] **Ablation demonstrates both express links and greedy placement are necessary.** Random express being worse than adjacent uniform is a key insight that adds rigor.

6. [S6] **Sensitivity analysis improves robustness.** 9/10 seeds, grid shapes, and diminishing returns provide confidence that results are not cherry-picked from a single configuration.

7. [S7] **BookSim latency inflation acknowledged honestly.** The Limitations disclosure about store-and-forward vs high-speed crossbars is appropriate.

8. [S8] **Net PHY saving calculation is a concrete cost metric.** ~96 PHY modules (~48 mm^2) is a tangible area saving that architects can evaluate against their design constraints.

## Weaknesses (Consolidated)

1. [W1] **8x8 reversal at 5-6x budget remains inadequately presented.** (MAJOR, severity reduced from iter-5) The Limitations sentence is honest but the full budget sweep data is still hidden from the main results. The reader cannot see the reversal without access to the raw data. The claim "Breaking the Cost-Performance Ceiling" is undermined by a region where express creates a lower ceiling than the baseline.

2. [W2] **2.3x claim is presented as general, holds at specific operating point.** (MODERATE) The abstract and introduction present the result without the applicable range (2-4x budget/pair). The 2.3x is the 8x8-specific result; 2x2 shows 1.0x savings. "Up to 2.3x" would be more accurate.

3. [W3] **"72 express links" phrasing is factually misleading.** (MODERATE) The 72-link express configuration contains ~53 adjacent + ~19 express links. The text in lines 41 and 346 implies all 72 are express. This matters for physical cost accounting.

4. [W4] **Wire-length-adjusted cost not reported.** (MINOR, downgraded from iter-5) The PHY saving (96 modules, 48 mm^2) partially addresses this, but interposer routing area still favors adjacent links on a per-link basis. The actual saving in total interconnect resources is ~1.67x, not 2.3x, when accounting for longer express wires.

5. [W5] **Ablation at 2x2 only; 8x8 ablation missing.** (MINOR) Given the greedy algorithm's pathology at high budgets on 8x8, the ablation should confirm the same placement strategy ordering holds on larger meshes.

6. [W6] **Sensitivity analysis: 1/10 seed result unreported.** (MINOR) The paper reports 9/10 seeds show express advantage. The 10th seed should be characterized (near-parity or express-worse?) to complete the robustness picture.

## Questions for Authors

1. [Q1] **The "72 express links" in line 346**: How many of the 72 links in the express configuration are actually express (non-adjacent) vs adjacent? The exact breakdown matters for the PHY saving calculation and wire-length cost.

2. [Q2] **The 1/10 failing seed**: What is the express-vs-adjacent ratio for the one seed (out of 10) where express does not win? Is it near-parity (0.95-1.0x) or is express substantially worse?

3. [Q3] **Fig. 1 (fig_cost_performance.pdf)**: Does this figure show the non-monotonic behavior at 5-6x budget for 8x8, or does it present a smoothed/aggregated curve? If the figure shows the non-monotonicity, that partially addresses my concern about data hiding.

4. [Q4] **BookSim internal mesh latency baseline**: What is the zero-load latency for an intra-chiplet packet traversing the full 8x8 mesh (corner to corner)? This would establish the internal mesh "floor" and allow decomposition of the end-to-end latency into internal vs inter-chiplet components.

## Minor Issues

- Line 30 (abstract): "validated in BookSim cycle-accurate simulation across 2x2, 4x4, and 8x8 internal mesh configurations" -- should note savings range from 1.0x to 2.3x across these, not uniformly 2.3x.
- Line 305: "The cost advantage *increases* with mesh size" -- true at 3x budget; the paper does not establish this holds at all budgets. Qualify with "at moderate link budgets."
- Line 346: "72 express links replace 168 adjacent links" -- should be "a 72-link mixed topology replaces 168 adjacent links" (see W3).
- Table II caption says "2x2 Mesh" but the table shows 4x4 and 4x8 grid results. The caption likely refers to internal mesh size (2x2 per chiplet), but this is confusing given the paper also uses NxN to refer to internal meshes in Section V. Clarify.
- The paper lacks a notation/setup table. With three different uses of "mesh" (chiplet grid, internal mesh, BookSim mesh), a clear definition table would prevent confusion.

## Rating

- Novelty: 3.5/5 (unchanged; the core contribution is the same, the fuller content improves completeness but not novelty)
- Technical Quality: 3.25/5 (up from 3.0; the BookSim latency disclosure, restored Kite-like numbers, ablation, and sensitivity analysis add rigor. However, the 8x8 reversal remains underexplored and the "72 express links" error in the PHY calculation is a factual issue)
- Significance: 3.5/5 (unchanged; the cost framing is actionable, the analytical contribution is solid, the design guidelines are useful)
- Presentation: 3.5/5 (up from 3.5; the restored content is well-integrated, the Limitations disclosures are honest. The "72 express links" misstatement and missing budget qualification in the abstract prevent a higher score)
- Overall: 3.5/5 (up from 3.25)
- Confidence: 4.5/5

## Decision

**Weak Accept.**

The iteration-6 paper is an improvement over iteration 5. The specific improvements that moved my score up:

1. **BookSim latency inflation disclosure (addresses W3 from iter-5).** The acknowledgment that "absolute latencies for 8x8 are inflated, though relative comparisons remain valid" is exactly the right framing. It does not hide the problem; it tells the reader what to trust (ratios) and what not to trust (absolute values). This resolves my biggest concern about the 8x8 simulation fidelity.

2. **Restored Kite-like numbers.** The 54.3 vs 54.4 result, with both saturating at rate 0.015 to latency >800, is the paper's most compelling empirical finding. Its absence in iteration 5 was a mistake.

3. **Ablation with four strategies.** The greedy vs random vs fully-connected comparison adds rigor by demonstrating that both the express link concept AND the greedy algorithm are necessary. Random express being worse than adjacent uniform is a strong result.

4. **Sensitivity with 9/10 seeds.** This substantially reduces the concern that the results are cherry-picked from a favorable traffic matrix.

5. **Net PHY saving.** The ~96 PHY module / ~48 mm^2 calculation gives a concrete area metric beyond abstract link counts.

What still prevents a full Accept:

1. **The 8x8 reversal at 5-6x budget is STILL not presented in the main results.** I asked for this explicitly in iteration 5. The Limitations sentence is there, but the data is hidden. I am downgrading the severity of this concern because (a) the Limitations disclosure is honest, (b) the paper's operating point (3x budget) is the most practically relevant for cost-conscious architects (who would not use 5-6x budget precisely because it is expensive), and (c) the title "Breaking the Cost-Performance Ceiling" is clearly about the 2-4x budget regime where the ceiling exists. But I would still prefer the full sweep to be visible.

2. **The "72 express links" wording is factually incorrect** and appears in both the Physical Overhead section and the introduction. This is a small but fixable error that affects the credibility of the cost argument.

3. **The abstract presents 2.3x without qualification.** Adding "up to" or a range would be more accurate.

These are addressable with minor revisions. The paper's core contributions -- the phantom load analysis (Theorem 1, Theta(K) scaling), routing independence, workload sensitivity, cost framing, Kite-like identical-saturation result, and workload-aware design -- are solid and publishable. The 8x8 mesh experiments, despite their artifacts, demonstrate that the express link advantage is not a border-capacity artifact. The design guidelines are actionable.

I am raising my score from 3.25 to 3.5 because (a) the BookSim latency disclosure adequately addresses my 8x8 fidelity concern, (b) the restored content (Kite-like numbers, ablation, sensitivity) significantly strengthens the evidence base, and (c) the PHY saving calculation adds a concrete cost dimension. The remaining issues (reversal presentation, wording accuracy, abstract qualification) are minor-to-moderate and can be fixed in camera-ready.

**To reach a full Accept (4.0):** Fix the "72 express links" wording to "72 total links (including express)." Add "up to" before "2.3x" in the abstract. Include one sentence in Section V.B noting the express advantage is strongest at 2-4x budget per pair and degrades at higher budgets due to greedy algorithm limitations. These are all editorial changes requiring no new experiments.
