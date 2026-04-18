# Review -- Reviewer 2 (Systems Pragmatist), Iteration 5

## Summary

Major structural revision. The paper has been substantially reframed around a cost-efficiency thesis ("same performance at 2-3x fewer links") with new experiments across three internal mesh sizes (2x2, 4x4, 8x8). The 8x8 result---72 express links matching 168 adjacent links---is the new headline number. The title has changed to "Breaking the Cost-Performance Ceiling." Six of the original seven tables have been consolidated or replaced; the paper is now shorter, more focused, and makes a single clean argument. I evaluate whether this reframing is technically sound, whether the new experiments are convincing, and whether the iteration-4 issues I flagged have been addressed or rendered moot by the restructuring.

## Assessment of the Reframing

### The cost-performance thesis is the right thesis

The previous version had an identity problem: it oscillated between "express links are faster" and "express links are cheaper." This revision commits fully to the cost story, and it is the correct choice. The reason is simple: in a real tape-out, the question is never "how fast can we go for unlimited budget?" but always "how few links do we need for this latency target?" Table `tab:costmatch` answers exactly that question. This is the table that a chip architect would bookmark.

The title change is appropriate. "Breaking the Cost-Performance Ceiling" is accurate and not overclaimed---there genuinely is a ceiling when adjacent-only topologies hit the phantom load wall, and express links demonstrably break through it.

### The multi-mesh-size experiment closes the key vulnerability

My primary unresolved concern through iterations 1-4 was whether the express link advantage was partly an artifact of constrained border capacity in the 2x2 internal mesh. The paper repeatedly claimed generality, but only demonstrated it on a single mesh size. This revision finally addresses the issue head-on:

- **2x2 internal mesh**: Border=2/edge. Express advantage is marginal (1.0x cost saving). This is expected---both strategies are border-capacity-limited.
- **4x4 internal mesh**: Border=4/edge. Express advantage emerges (2.0x cost saving). The phantom load bottleneck dominates over border constraints.
- **8x8 internal mesh**: Border=8/edge. Express advantage is strongest (2.3x cost saving). With ample border capacity, adjacent topologies waste links on phantom load, and express links eliminate that waste.

The monotonic increase in cost advantage with mesh size (1.0x -> 2.0x -> 2.3x) is the strongest argument in the paper. It proves the express link benefit is not a modeling artifact but a structural consequence of phantom load scaling. This was the single most important experiment to run, and I am glad it is now in the paper.

## Technical Evaluation of New Results

### Table `tab:costmatch` -- the money table

The table is clean and answers the right question: "for a target latency, how many links does each strategy need?" Three observations:

1. **2x2, target ~30 latency**: 48 adj vs 47 expr (1.0x). Correct---at border=2, you simply cannot fit enough express links to make a difference. The paper correctly presents this as "no advantage" rather than hiding it. Good intellectual honesty.

2. **4x4, target ~50 latency**: 96 adj vs 48 expr (2.0x). A clean 2x cost saving. The halving is striking and should be emphasized more---it means a chip architect can provision exactly half the PHY area for the same performance.

3. **8x8, target ~200 latency**: 168 adj vs 72 expr (2.3x). The headline result. Note the target latency is higher (200 vs 50) because the 8x8 mesh has more internal hops. This is a fair comparison---same injection rate, same grid, different internal mesh.

**Minor concern**: The injection rates differ between mesh sizes (the text says "Rate 0.005" in the table caption but the figure caption says "injection rate 0.01"). Which rate is used for the cost-matching comparison? The table says 0.005, the figure says 0.01. These should be reconciled or explained---different injection rates could shift the cost-match point.

### Figure `fig:costperf` -- the visual argument

I cannot view the PDF, but the caption description is clear: "latency at injection rate 0.01 vs. total inter-chiplet links." This is a Pareto-style plot, which is the right visualization for a cost-performance argument. The description of three pairs of curves (one per mesh size) with express consistently below/left of adjacent is compelling. However:

**Missing information**: The figure apparently shows only adjacent uniform and express greedy. Where is the Kite-like (MinMax) baseline? In iteration 4, I specifically asked for Kite-like in the main BookSim table as the strongest evidence that adjacent-only is fundamentally limited. Section 5.3 mentions it qualitatively ("Kite-like produce nearly identical performance") but it does not appear in the figure or in Table `tab:costmatch`. Including Kite-like as a third curve in the figure would strengthen the argument considerably---it would show that the ceiling is not just a property of uniform allocation but of all adjacent-only strategies. This is a regression from iteration 4.

### Section 5.3 -- Adjacent-Only Ceiling

The text states: "Adjacent uniform and Kite-like produce nearly identical performance despite MinMax's optimal allocation." This is a critical claim and it is stated without supporting data. In iteration 4, Table VI had the exact numbers (lat=54.3 vs 54.4 at rate 0.01, both saturating at rate 0.015 with lat=846). Those numbers have been removed. The claim is now weaker because it relies on the reader trusting a qualitative assertion rather than seeing the data.

**Recommendation**: Add Kite-like numbers to Table `tab:costmatch` (or at minimum, state the specific latency values in the text). The sentence "nearly identical performance" should have numbers attached.

### Section 5.6 -- Differential Bandwidth

The BW degradation numbers ("1.8-2.2x at 75% decay, 1.6-1.8x at 50% decay") are stated without a table or figure. The previous version had a dedicated Table V with gamma values. That level of detail is not strictly necessary in this shorter format, but a parenthetical reference to the experimental conditions (e.g., "at 72 total links on K=16, 8x8 mesh") would help the reader verify these numbers. Currently they float without context.

### Ablation (Section 5.4)

"Random express placement is worse than adjacent uniform (congestion 85.4 vs. 62.8 at K=16); greedy outperforms even fully-connected topologies by 2.5x (15.3 vs. 39.0)." My iteration-3 and iteration-4 note about the fully-connected comparison being somewhat unfair (FC uses uniform per-link allocation, not load-aware) remains unaddressed. I flag it once more for completeness: a parenthetical "(with uniform per-link allocation)" would fix this. Not blocking.

## Tracking Iteration-4 Issues

### [M1] Conclusion/abstract BW claim inconsistency -- RENDERED MOOT
The conclusion no longer mentions specific BW degradation numbers for dense traffic. The abstract mentions "2.3x fewer inter-chiplet links" and the conclusion mentions "2-3x more links than topologically necessary." The differential bandwidth section (5.6) handles BW degradation separately. No inconsistency remains. Resolved by restructuring.

### [M2] FC comparison qualifier -- STILL UNADDRESSED
As noted above. Minor.

### [M3] Q4/Q5 derivations -- PARTIALLY ADDRESSED
Guideline 7 still states "per-layer communication (~0.1 us) is negligible versus memory access (~600 us)" without derivation. However, the guideline is now framed more carefully as a regime statement ("NoI is not always the bottleneck") rather than a quantitative claim, which reduces the burden of proof. Acceptable at this stage, though a footnote with the back-of-envelope calculation would still improve reproducibility.

## New Issues in This Revision

### [N1] Injection rate discrepancy (Medium)
Table `tab:costmatch` caption says "Rate 0.005" but Figure `fig:costperf` caption says "injection rate 0.01." Are these different operating points for different purposes (cost-matching vs. general comparison)? If so, explain. If not, fix the inconsistency. A reader trying to reproduce the cost-match numbers needs to know the exact injection rate.

### [N2] Kite-like data regression (Medium)
The removal of Kite-like quantitative data from the main results is a step backward. The iteration-4 version had Kite-like in the main BookSim table with specific numbers proving it was identical to uniform. This revision replaces those numbers with a qualitative sentence. Recommendation: add Kite-like as a row in Table `tab:costmatch` or restore the specific numbers in the text.

### [N3] Table `tab:routing` -- Max alpha interpretation (Minor)
In the routing algorithm comparison (Table `tab:routing`), the "Max alpha" column shows values like 111, 223, 347 for a 4x4 grid. These seem inconsistent with Table `tab:scaling`, which shows Max alpha = 16 for a 4x4 grid under XY routing. I suspect the routing table uses absolute flow counts or a different normalization than the scaling table. The column header "Max alpha" should clarify units or definition, or use a different label to avoid confusion with the alpha defined in Section 3.

### [N4] The cost argument could be strengthened with area/power (Minor)
The physical overhead section (5.5) makes a qualitative argument that express links are "net positive" because they save more PHY area than they consume. This could be made quantitative: if 72 express links replace 168 adjacent links, the net PHY area saving is (168-72) * PHY_area_per_link - express_wire_area. The paper has all the numbers to compute this but does not. One additional sentence with a concrete net area saving would make the cost argument airtight.

### [N5] Algorithm runtime (Minor)
"The algorithm runs in 3 seconds for K=16." At what internal mesh size? 2x2, 4x4, or 8x8? The search space changes dramatically with mesh size (more candidate links). Clarify.

## Assessment of Paper Maturity

This is a stronger paper than iteration 4. The reframing around cost-performance is cleaner, the multi-mesh-size experiment eliminates the border-capacity artifact concern, and the paper is more concise. The core technical content is sound.

However, the rewrite introduced two regressions: the loss of quantitative Kite-like data (N2) and the injection rate discrepancy (N1). These are fixable in a single pass. The paper is one revision away from final camera-ready.

The design guidelines remain the paper's practical contribution. Guideline 6 ("Think in cost, not just performance") is the most valuable addition in this revision---it reframes the entire research question from a performance optimization problem to a cost optimization problem, which is how real chip architects think.

## Scores

| Criterion | Iter-1 | Iter-2 | Iter-3 | Iter-4 | Iter-5 | Comment |
|-----------|--------|--------|--------|--------|--------|---------|
| Novelty | 3.0 | 3.5 | 3.5 | 3.5 | 3.5 | No change; the contribution is the same, better framed |
| Technical Quality | 2.5 | 3.5 | 4.0 | 4.0 | 4.0 | Multi-mesh experiment is strong; Kite-like data regression is a minor blemish |
| Significance | 3.0 | 3.5 | 4.0 | 4.0 | 4.5 | Cost-performance framing elevates practical impact; 2.3x at 8x8 mesh is a real result |
| Presentation | 3.5 | 4.0 | 4.0 | 4.5 | 4.0 | Cleaner structure, but injection rate discrepancy and missing Kite-like numbers are sloppy |
| Overall | 3.0 | 3.5 | 4.0 | 4.0 | 4.0 | |
| Confidence | 3.0 | 4.0 | 4.0 | 4.5 | 4.5 | The multi-mesh experiment answers my core concern |

## Decision

**Accept (with minor revisions)**

The reframing to a cost-performance thesis is the correct strategic choice, and the multi-mesh-size experiment (2x2, 4x4, 8x8) eliminates the most important technical vulnerability. The 2.3x cost saving at 8x8 internal mesh is a convincing result that will resonate with chip architects at DATE.

Two items should be fixed before final submission:

1. **[N1] Reconcile the injection rate** between Table `tab:costmatch` (0.005) and Figure `fig:costperf` (0.01). If they are intentionally different, explain why.
2. **[N2] Restore quantitative Kite-like data** --- either as a row in Table `tab:costmatch` or as specific latency numbers in Section 5.3. The qualitative "nearly identical" without numbers is weaker than what iteration 4 had.

Three items are desirable but not required:

3. [N3] Clarify the "Max alpha" column definition in Table `tab:routing` to avoid confusion with Table `tab:scaling`.
4. [N4] One sentence quantifying the net PHY area saving (168 - 72 = 96 fewer link PHYs minus express wire overhead).
5. [N5] Specify the internal mesh size for the 3-second runtime claim.

The paper is ready for DATE proceedings once items 1-2 are addressed.
