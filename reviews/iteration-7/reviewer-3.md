# Review -- Reviewer 3 (ML/Application Expert), Iteration 7

## Summary

Iteration 7 applies three editorial fixes since iteration 6. This is a quick confirmation review. The paper was already at Accept (4.0/5) after iteration 6; the question is whether the fixes are correct and whether any new issues were introduced.

## Assessment of the Three Editorial Fixes

**Fix 1: Abstract "up to 2.3x" (was "2.3x").** Line 30 now reads: "up to 2.3$\times$ fewer inter-chiplet links." This is the right correction. The 2.3x figure holds specifically at the 8x8 internal mesh operating point; the savings at 2x2 are 1.0x and at 4x4 are 2.0x. "Up to" accurately scopes the claim as the best case across the three mesh configurations tested. No issues.

**Fix 2: Section 5.2 budget-range qualification.** The end of the 8x8 paragraph (line 305) now reads: "The advantage is strongest at 2--4$\times$ budget per adjacent pair; at higher budgets ($\geq$5$\times$), the greedy algorithm's suboptimal placement can reduce the advantage (see Limitations)." This is a well-calibrated addition. It tells the reader the applicable regime without burying it in the Limitations section, and it correctly attributes the degradation to the greedy algorithm rather than to express links as a concept. The forward reference to Limitations is appropriate. No issues.

**Fix 3: Physical Overhead wording correction.** Line 346 now reads: "72 total links (including $\sim$19 express) replace 168 adjacent-only links, saving $\sim$96 PHY modules ($\sim$48 mm$^2$ PHY area)." This fixes the factual error where the previous version implied all 72 links were express. The parenthetical "$\sim$19 express" also gives the reader the actual express link count for the first time in the paper, which is useful for physical cost estimation: 19 express links at average distance ~2.5 is a modest physical footprint. No issues.

All three fixes are clean, accurate, and do not introduce new problems.

## Status of My Iteration-6 Weaknesses

**W1 (Table II caption "2x2 Mesh" for 4x4/4x8 data): NOT ADDRESSED.** The caption at line 165 still reads "Load Imbalance Across Routing Algorithms (2$\times$2 Mesh)" while the table body shows 4x4 and 4x8 grid data. The "(2$\times$2 Mesh)" likely refers to the internal mesh size per chiplet, not the chiplet grid dimensions, but this remains confusing. A caption like "Load Imbalance Across Routing Algorithms (2$\times$2 Internal Mesh)" would resolve the ambiguity with a single word insertion. This is a cosmetic issue that does not affect any technical claim.

**W2 (XY vs. YX asymmetry on 4x4 grid): NOT ADDRESSED.** Max alpha = 111 (XY) vs. 223 (YX) on a square 4x4 grid remains unexplained. As noted in iter-6, this does not affect the paper's argument -- the point of Table II is that phantom load persists across all routing algorithms, which it does regardless of specific alpha values.

**W3 (Greedy algorithm runtime): NOT ADDRESSED.** No runtime data. This remains a practical concern for the DATE audience but is not blocking.

**W4 (Guideline 7 precision on memory access numbers): NOT ADDRESSED.** The "~600 us" figure in Guideline 7 still lacks model/HBM specification. The qualitative point is correct regardless.

None of these four items were the target of the iteration-7 fixes, and none are severe enough to affect the paper's accept-worthiness. They are all camera-ready polish items that could be addressed in final formatting.

## Verification: No Regressions

I verified the following are unchanged and intact from iteration 6:
- Table III (6 LLM workloads at K=32) with MoE top-2 routing specification: present and correct.
- Section 5.3 Kite-like inline numbers (54.3 vs. 54.4): present and correct.
- Table V (cost to achieve target latency): present with the 2x2/4x4/8x8 progression.
- Section 5.5 MoE validation (zero express links): present.
- Theorem 1 with F_H row-independence explanation: present.
- BookSim store-and-forward caveat in Limitations: present.
- Greedy suboptimality at high budgets in Limitations: present.
- Seven design guidelines: all present.

No content was removed or degraded. The paper remains complete.

## Strengths

All strengths from iteration 6 (S1-S5) carry forward unchanged. The three editorial fixes collectively improve the paper's honesty and precision without sacrificing clarity:

1. [S1] All load-bearing claims have inline numbers (retained).
2. [S2] MoE specification closes the reproducibility gap (retained).
3. [S3] The cost thesis is fully supported end-to-end (retained).
4. [S4] The 6 LLM workload patterns provide practical coverage (retained).
5. [S5] All prior strengths (8x8 validation, cost framing, ablation, MoE negative result, physical overhead, differential BW) remain intact (retained).
6. [S6, new] The three fixes address the most actionable feedback from the review panel -- "up to" qualification, budget-range scoping, and wording accuracy -- demonstrating responsive revision without over-editing.

## Weaknesses

1. [W1] **Table II caption ambiguity (carried, cosmetic).** "(2$\times$2 Mesh)" should be "(2$\times$2 Internal Mesh)" to distinguish from chiplet grid dimensions.
2. [W2] **XY/YX asymmetry unexplained (carried, minor).** Does not affect conclusions.
3. [W3] **Greedy runtime unspecified (carried, minor).** A single sentence would address this.
4. [W4] **Guideline 7 memory access numbers ungrounded (carried, minor).** A brief qualifier would help.

All four are sub-paragraph fixes. None affect the paper's technical contributions or the validity of its claims.

## Rating

- Novelty: 3/5 (unchanged)
- Technical Quality: 4/5 (unchanged)
- Significance: 4/5 (unchanged)
- Presentation: 4/5 (unchanged)
- Overall: **4/5 (Accept)**
- Confidence: 4/5

## Score Justification

No score changes from iteration 6. The three editorial fixes are correct and improve precision, but they do not alter the paper's substance. The paper was already at Accept; it remains so. The four carried weaknesses are all cosmetic or minor and do not warrant score adjustments.

## Decision

**Accept.** The paper is in final form for its core contributions. The three editorial fixes since iteration 6 are well-executed: "up to 2.3x" honestly scopes the headline claim, the budget-range note in Section 5.2 prevents misinterpretation of the express link advantage, and the "72 total links (including ~19 express)" correction eliminates a factual inaccuracy in the physical overhead argument.

The four remaining weaknesses (Table II caption ambiguity, XY/YX asymmetry, greedy runtime, Guideline 7 precision) are all addressable with single-sentence insertions and do not affect the paper's accept-worthiness. No further iteration is needed.

The paper makes a clear contribution to DATE: it identifies and characterizes phantom load as a cost problem in chiplet NoI, proves its analytical scaling, validates across routing algorithms and workloads, and demonstrates that express links with workload-aware placement break the cost-performance ceiling at 2-4x budget levels. The evidence chain from Theorem 1 through Tables I-VI to the design guidelines is complete, internally consistent, and actionable for chiplet architects.
