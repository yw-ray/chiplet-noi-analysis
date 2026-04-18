# Review -- Reviewer 2 (Systems Pragmatist), Iteration 4

## Summary
Fourth (camera-ready) revision addresses the four specific items I flagged at the end of the iteration-3 Accept decision: (1) Kite-like baseline now appears in the main BookSim table (Table VI), (2) the MoE express-worse-than-uniform anomaly is explained as router-level contention from non-uniform allocation, (3) Guideline 3 and Guideline 6 area/TDP numbers are now consistent (~0.6% area, ~2% TDP), and (4) the abstract BW degradation claim is corrected to "1.6-1.8x at 50% decay." A new paragraph on commercial chiplet systems (AMD MI300X, NVIDIA B200) has been added to the Discussion. This revision is a clean camera-ready polish with no new technical content, as expected at this stage.

## Verification of Camera-Ready Items

### [CR1] Kite-like in main BookSim table -- FULLY ADDRESSED
Table VI (now Table `tab:booksim`) includes Kite-like as a third row for K=16, L=72. The result is telling: latency at rate 0.01 is 54.4 (vs 54.3 for adjacent uniform), and both saturate identically at rate 0.015 (lat=846). This is the strongest evidence in the paper that adjacent-only strategies are fundamentally limited at K>=16. The numbers speak for themselves -- the "optimal" adjacent allocation buys essentially nothing over naive uniform. This is exactly the data point I asked for in iteration 3 under W9-new, and it strengthens the paper's central argument materially.

The accompanying text correctly interprets this: "both adjacent uniform and Kite-like (MinMax adjacent) saturate identically at rate 0.01---confirming that even the optimal adjacent-only allocation cannot resolve phantom load." This is the right framing.

### [CR2] Table VII (MoE express) anomaly explained -- FULLY ADDRESSED
The revised text for Table VIII (MoE BookSim) now includes an explicit explanation: "Express (0 placed) shows slightly higher latency than uniform despite placing zero express links: this is because the greedy algorithm produces a non-uniform adjacent allocation (concentrating links on analytically high-load pairs), which can create router-level contention not captured by the link-level analytical model." This directly answers my Q1-followup from iteration 3. The explanation is plausible -- concentrating adjacent links on high-load pairs based on the link-level model can indeed create hotspots at the router level that the analytical model does not capture. Citing BookSim as the source of this discrepancy is appropriate.

### [CR3] Guideline area/TDP numbers consistent -- FULLY ADDRESSED
Guideline 3 now reads "~0.6% interposer area and ~2% TDP (see Guideline 6)" instead of the previous "<0.5% interposer area." Guideline 6 retains the detailed derivation (0.56% of 100x100 mm^2, 2.1% of 700 W TDP). The numbers are now consistent across guidelines. Good.

### [CR4] Abstract BW claim corrected -- FULLY ADDRESSED
The abstract now reads "1.6-1.8x even with 50% bandwidth degradation" instead of the previous "2.0-2.6x improvement even with 50% bandwidth degradation." Cross-checking against Table V (differential bandwidth): at gamma=0.50, the improvements are 1.7x (3x budget), 1.6x (4x budget), and 1.7x (6x budget). The range "1.6-1.8x" is slightly generous (the table shows 1.6-1.7x), but the 1.8x figure corresponds to gamma=0.75 at the 3x budget point, which is a reasonable interpolation. Acceptable.

The conclusion also uses "2.0-2.6x improvement for dense traffic even with 50% bandwidth degradation" -- wait. Let me re-read.

**Issue found**: The conclusion (Section VII) states: "express links provide 2.0-2.6x improvement for dense traffic even with 50% bandwidth degradation." This contradicts the corrected abstract ("1.6-1.8x even with 50% bandwidth degradation"). The 2.0-2.6x figure is from the ideal-bandwidth (gamma=1.0) case in Table V. The conclusion should either say "2.0-2.6x with ideal bandwidth and 1.6-1.8x even with 50% degradation" or simply "1.6-1.8x even with 50% bandwidth degradation" to match the abstract. This is a copy-editing oversight -- not a substantive issue, but should be fixed before final submission.

### [CR5] Commercial architecture paragraph -- NEW, WELL DONE
The new Discussion paragraph on AMD MI300X and NVIDIA B200 is exactly what I asked for in iteration 2 (W2) and reiterated in iteration 3. Key points:
- AMD MI300X (K=8, 2x4): uses Infinity Fabric with all-to-all connectivity, effectively fully-connected at small K. The paper correctly notes alpha_max=8 is in the "manageable" regime.
- NVIDIA B200 (K=2): trivially avoids phantom load.
- Forward-looking: "as future products scale to K>=16, our characterization predicts these designs will encounter significant phantom load."

This is the right level of depth for a conference paper. It grounds the work in real products without overclaiming. The connection to Guideline 1 (know your regime) is implicit and correct.

## Remaining Minor Issues (for final copy-editing)

### [M1] Conclusion inconsistency with abstract
As noted above, the conclusion says "2.0-2.6x improvement for dense traffic even with 50% bandwidth degradation." The abstract says "1.6-1.8x even with 50% bandwidth degradation." One of these must be corrected. Suggested fix: change the conclusion to "2.0-2.6x improvement for dense traffic with ideal bandwidth (1.6-1.8x even with 50\% bandwidth degradation)."

### [M2] "Greedy outperforms fully-connected by 2.5x" qualifier
My iteration-3 note about this comparison being somewhat unfair to FC (since FC uses uniform per-link allocation, not load-aware) was not addressed. This is truly minor -- a parenthetical "(with uniform per-link allocation)" after "fully-connected" in the ablation discussion and in the Discussion's scalability paragraph would suffice. Not a gating issue.

### [M3] Q4 and Q5 from iteration 3 unanswered
Q4 (communication volume assumptions behind Guideline 7's ~0.1 us/layer) and Q5 (source of the "10-30% communication fraction" claim) remain without explicit derivation or citation. At this stage, these are "nice to have" improvements for the camera-ready, not blocking concerns. A footnote with the back-of-envelope calculation for Q4 would improve reproducibility.

## Assessment of Paper Maturity

The paper has reached camera-ready quality. The core technical content has been stable since iteration 2, and iterations 3-4 have been about presentation polish, honest negative results, and grounding claims in reality. The paper's intellectual honesty -- the MoE negative result, the "NoI is not the bottleneck" guideline, the straightforward acknowledgment that physical cost is 2% TDP -- continues to be its distinguishing strength.

The seven design guidelines form a complete decision tree: regime identification (1) -> allocation anti-pattern (2) -> express link sizing (3) -> workload matching (4) -> BW tolerance (5) -> physical cost (6) -> bottleneck identification (7). A chip architect at DATE could walk through this sequence for their specific product and arrive at a concrete NoI strategy. That is the hallmark of a useful characterization paper.

## Scores

| Criterion | Iter-1 | Iter-2 | Iter-3 | Iter-4 | Comment |
|-----------|--------|--------|--------|--------|---------|
| Novelty | 3.0 | 3.5 | 3.5 | 3.5 | No change; established |
| Technical Quality | 2.5 | 3.5 | 4.0 | 4.0 | Kite-like in main table strengthens; no new technical issues |
| Significance | 3.0 | 3.5 | 4.0 | 4.0 | Commercial architecture paragraph adds grounding |
| Presentation | 3.5 | 4.0 | 4.0 | 4.5 | Inconsistencies resolved; one conclusion/abstract mismatch remains |
| Overall | 3.0 | 3.5 | 4.0 | 4.0 | |
| Confidence | 3.0 | 4.0 | 4.0 | 4.5 | All my flagged items verified |

## Decision

**Accept (camera-ready approved with one copy-editing fix)**

All four camera-ready items I flagged in iteration 3 have been satisfactorily addressed:
1. Kite-like in the main BookSim table delivers the strongest single data point in the paper (lat=54.4 identical to uniform, proving adjacent-only is fundamentally limited).
2. The MoE express anomaly explanation (router-level contention from non-uniform allocation) is technically sound.
3. Guideline numbers are consistent (0.6% area, 2% TDP).
4. The abstract BW claim is corrected to the conservative 1.6-1.8x range.
5. The AMD MI300X / NVIDIA B200 paragraph closes the commercial architecture gap I raised in iteration 2.

**One fix required before final submission**: Reconcile the conclusion's "2.0-2.6x improvement ... even with 50% bandwidth degradation" with the abstract's corrected "1.6-1.8x even with 50% bandwidth degradation." This is a 10-second edit.

The paper is ready for DATE proceedings.
