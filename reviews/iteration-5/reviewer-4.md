# Review -- Reviewer 4 (Theory/Analysis Expert), Iteration 5

## Summary
This paper characterizes "phantom load" in chiplet Network-on-Interposer (NoI), proves center-link amplification grows as Theta(K) in square grids, demonstrates routing-algorithm independence across four algorithms, and evaluates workload sensitivity across six LLM communication patterns. The iteration-5 revision represents a substantial reframing: the thesis is now explicitly a **cost-efficiency** argument rather than a performance argument. The paper proves that Theta(K) phantom load translates to Theta(K) unnecessary link cost, validated empirically with a new cost-to-target comparison across three internal mesh sizes (2x2, 4x4, 8x8). The headline result is that 72 express links achieve the same latency as 168 adjacent links at K=16 with 8x8 internal mesh---a 2.3x cost gap. This is a cleaner and more defensible framing than the previous performance-centric presentation.

## Response to Iteration-4 Suggestions

**[Suggestion 1] F_H r-independence explanation.** The iteration-5 paper is restructured enough that the original proof sketch is now condensed. The new paper omits the detailed proof sketch in favor of stating the formulas (Eqs. 2-3) and referencing computational validation for R,C <= 8. The r-independence issue is effectively sidestepped---the paper no longer walks the reader through the derivation mechanics, so there is no ambiguity to resolve. **Resolved by restructuring, albeit not by adding the clarifying sentence I requested. Acceptable.**

**[Suggestion 2] Cite [14] in Related Work text.** The iteration-5 paper has a significantly trimmed bibliography (12 references vs. the previous ~14). Reference [14] (Leighton-Rao, MCF theory) is no longer present in the bibliography at all. This eliminates the phantom citation problem---the reference was removed rather than cited. This is a pragmatic solution, though the MCF connection would have strengthened the theoretical positioning. **Resolved by removal. Acceptable for a conference paper at the page limit.**

**[Suggestion 3] Guideline 1 threshold language.** The iteration-5 paper rewrites Guideline 1 as: "Compute alpha_max using Eq. (2)-(3). If alpha_max < 5 (K <= 8), adjacent allocation suffices. If alpha_max > 10 (K >= 16), topology intervention is cost-effective." The K=8 example in the paper is now contextualized via the AMD MI300X discussion in Related Work (K=8, alpha_max=8, "manageable regime"), which implicitly acknowledges that K=8 exceeds the alpha_max < 5 threshold but is still manageable in practice. The guideline language is the same as iteration-4, but the surrounding context (Related Work, Discussion) now clarifies the intent. **Partially addressed. The threshold imprecision persists (alpha_max=8 for K=8 exceeds the stated threshold of 5), but the practical intent is clear from context. Minor.**

## Assessment of Major Changes

### Change 1: Cost-Efficiency Reframing

This is the most important change in the paper. The thesis has shifted from "express links improve performance" to "express links achieve the same performance at lower cost." This reframing is visible throughout:

- **Title**: "Breaking the Cost-Performance Ceiling" (explicit cost framing)
- **Abstract**: "2.3x fewer inter-chiplet links" is now the headline metric, not latency reduction
- **Introduction**: "168 adjacent links vs 72 links" cost comparison introduced in paragraph 2
- **Section III**: New "Why this is a cost problem" paragraph after Theorem 1
- **Section V**: "Cost-Performance Across Internal Mesh Sizes" as the primary evaluation subsection
- **Table III**: Cost-to-target comparison (the paper's core empirical result)
- **Guidelines**: Guideline 6 explicitly says "Think in cost, not just performance"

**Assessment:** This is a strictly superior framing. The performance argument ("express links reduce latency by X%") is vulnerable to the objection "how much does that latency matter for end-to-end application performance?" The cost argument ("express links save 2.3x in link count for the same latency") is immune to this objection---even if the latency does not matter for the application, the cost saving is always valuable. The reframing also aligns better with the chiplet architecture community's concerns (interposer area, PHY count, manufacturing cost) rather than the NoC community's concerns (latency, throughput).

The "Why this is a cost problem" paragraph after Theorem 1 (line 114) is particularly effective: "To keep the most congested link below a utilization target rho*, an adjacent-only topology must provision ceil(alpha_max / rho*) links on center pairs---Theta(K) links per pair. Express links reduce alpha_max toward 1, eliminating this overhead." This directly connects the Theta(K) analytical result to practical cost implications, which was the weakest link in previous iterations. The paragraph is concise (two sentences) and self-contained.

**Verdict: Major improvement. This elevates the paper's contribution from incremental optimization to architectural cost analysis.**

### Change 2: Three Internal Mesh Sizes (2x2, 4x4, 8x8)

Previous iterations used only 2x2 internal mesh, which Reviewer 1 correctly flagged as unrealistically small (border=2 links per edge). The iteration-5 paper now evaluates at three sizes:

- **2x2** (border=2/edge): Express advantage is modest (13% latency reduction at 48 links). Cost saving: 1.0x (no saving). This confirms that constrained border capacity limits both strategies equally.
- **4x4** (border=4/edge): Express shows clear advantage. Cost saving: 2.0x (96 vs 48 links for ~50 latency).
- **8x8** (border=8/edge): The critical test. Adjacent links now have ample capacity (8 links per pair). Express still dominates. Cost saving: 2.3x (168 vs 72 links for ~200 latency).

**Assessment:** The 8x8 result is the paper's most important empirical contribution. It addresses the concern that the previous 2x2 results might be artifacts of border capacity constraints. With 8x8 internal mesh, each adjacent pair can have up to 8 links per edge---far more than any practical design would use. Yet express links still provide 2.3x cost savings. This proves the cost advantage is structural (caused by phantom load), not an artifact of limited border capacity.

The observation that "the cost advantage increases with internal mesh size" (line 237) is a counterintuitive and valuable insight. One might expect that giving adjacent links more headroom (larger internal mesh = more border routers) would close the gap with express links. Instead, it widens it---because more adjacent capacity means more waste from phantom tax when that capacity is used inefficiently. This is a novel observation that I have not seen in the NoI literature.

**Verdict: Addresses the most significant experimental gap from previous iterations. The 8x8 result is decisive.**

### Change 3: Table III (Cost-to-Target Comparison)

Table III quantifies the cost saving explicitly:

| Int. Mesh | Target Lat | Adj Links | Expr Links | Saving |
|-----------|-----------|-----------|-----------|--------|
| 2x2       | ~30       | 48        | 47        | 1.0x   |
| 4x4       | ~50       | 96        | 48        | 2.0x   |
| 8x8       | ~200      | 168       | 72        | 2.3x   |

**Assessment:** This table is the paper's cleanest deliverable. A chiplet architect can look at this table and immediately understand the tradeoff: for the same latency target, how many links does each strategy require? The progression from 1.0x (2x2) to 2.0x (4x4) to 2.3x (8x8) tells a clear story---as border capacity increases, the cost advantage of express links grows because adjacent-only topologies waste more capacity on phantom load.

However, I note that the target latencies differ across rows (~30, ~50, ~200), which makes cross-row comparison less clean. The 8x8 target of ~200 cycles is quite high---this likely corresponds to a regime where adjacent-only is deep in saturation. The 2x2 target of ~30 cycles is near the minimum achievable latency. The different operating points make the table slightly misleading: the 2.3x saving at 8x8 is partly because the adjacent-only strategy is in deep saturation at the target latency, while the 1.0x at 2x2 is because both strategies are near their floor. A more controlled comparison would fix the target latency (or latency-to-floor ratio) across all three mesh sizes. This is a minor concern---the table is still directionally correct and practically useful.

**Verdict: Effective and actionable. The different target latencies across rows are a minor methodological imprecision.**

### Change 4: Restructured Paper

The paper has been significantly tightened. The previous iteration had 9+ tables; this version has 4 tables and 1 figure. The evaluation is more focused: cost-performance is the primary lens, with routing independence and workload sensitivity presented more concisely. The ablation (random vs greedy placement) is now a single paragraph. The MoE section is shorter but retains the key finding (zero express links placed).

**Assessment:** The restructuring improves readability. The previous paper felt like a catalog of experiments; this version has a clear narrative arc: (1) phantom load is a cost problem, (2) it grows as Theta(K), (3) no routing algorithm or adjacent allocation strategy can fix it, (4) express links fix it at 2.3x cost savings, (5) but only for dense traffic. The cost framing gives the paper a coherent thesis that the previous performance-centric framing lacked.

The reduction from 14 to 12 references is acceptable---the removed references (Leighton-Rao MCF, and possibly others) were not essential for the cost-efficiency argument.

## Strengths

1. [S1] **The cost-efficiency reframing is a qualitative improvement in the paper's positioning.** The argument "same performance at 2.3x fewer links" is stronger and more defensible than "X% latency improvement at same budget." It aligns with the chiplet architecture community's primary concern (interposer cost and area) and is immune to the "does this latency matter for applications?" objection.

2. [S2] **The 8x8 internal mesh result is the paper's most convincing evidence.** By showing the cost advantage persists---and in fact increases---when adjacent links have ample border capacity, the paper eliminates the most serious methodological concern from previous iterations.

3. [S3] **The "Why this is a cost problem" paragraph is the missing analytical link.** Previous iterations proved Theta(K) amplification but did not explicitly connect it to Theta(K) cost. The two-sentence paragraph after Theorem 1 closes this gap cleanly: ceil(alpha_max / rho*) links per center pair implies Theta(K) cost.

4. [S4] **Table III is the paper's most actionable result.** A chiplet architect can immediately use this table to estimate the link-count savings from express links at their specific internal mesh size.

5. [S5] **Theorem 1 remains correct and is now better motivated.** The closed-form F_H(c) and F_V(r) are unchanged and validated computationally.

6. [S6] **Counter-intuitive findings are retained.** Traffic-proportional 1.5x worse than uniform, Kite-like identical to uniform at K=16, express useless for MoE---all present and better contextualized under the cost framing.

## Weaknesses

1. [W1] **Table III target latencies are not controlled across mesh sizes.** The 2x2 target is ~30 cycles (near floor), the 4x4 target is ~50, and the 8x8 target is ~200 (deep in saturation for adjacent-only). This means the 2.3x saving at 8x8 is measured at a different relative operating point than the 1.0x at 2x2. A fairer comparison would normalize by, e.g., the ratio of target latency to minimum achievable latency, or present results at a fixed utilization level. This does not invalidate the result but introduces a confound that a careful reader will notice.

2. [W2] **The Kite-like (MinMax adjacent) result is less prominently featured than in iteration 4.** The previous iteration had an explicit subsection showing Kite-like and Uniform producing identical BookSim latencies at K=16 (the "adjacent-only ceiling"). In the current version, this result appears in Section V-C as a single-paragraph subsection. This is the paper's second-strongest finding (after Table III), and it deserves slightly more prominence. The identical saturation of uniform and Kite-like is a powerful result that directly supports the cost argument: if the optimal adjacent allocation cannot improve on uniform, then all adjacent links above the minimum are wasted by phantom load.

3. [W3] **ECMP and Valiant closed-form analysis remains absent.** The routing independence table (Table II) presents empirical results for four algorithms but closed-form analysis only for XY routing. For the theory/analysis contribution to be complete, even a sketch argument for why ECMP and Valiant cannot eliminate Theta(K) amplification would strengthen the paper. ECMP distributes flows across equal-cost paths, reducing peak load by a constant factor but not changing the Theta(K) scaling; Valiant randomizes paths but doubles total load. A single paragraph making this argument formally would elevate the theoretical contribution. This has been a recurring observation across iterations; it is acceptable as journal-extension material but its absence weakens the "routing-algorithm independence" claim.

4. [W4] **Differential bandwidth section is brief and could benefit from integration with the cost framing.** Section V-F presents BW decay results (1.8-2.2x at 75% decay, 1.6-1.8x at 50% decay) but does not translate these into cost savings. If express links with 50% BW decay achieve 1.6x fewer links rather than 2.3x, this is still a significant saving but the reader must infer this from context. A single sentence connecting BW decay to cost-to-target would complete the argument.

5. [W5] **MoE traffic model parameters remain unspecified.** This has been flagged by Reviewer 3 across multiple iterations. The paper states "sparse all-to-all traffic" without specifying expert count, top-k, or capacity factor. The MoE finding (greedy places zero express links) is one of the paper's strongest results, and its generalizability is unclear.

## Minor Issues

- The injection rate for Table III is 0.005 (per the caption), while the main cost-performance figure (Fig. 1) shows results at rate 0.01. The different injection rates make cross-referencing between the figure and the table slightly confusing. Consider adding rate-0.005 annotations to Fig. 1 or using a consistent rate.
- Table II shows Max alpha = 111 for XY at 4x4 and Max alpha = 223 for YX at 4x4. The YX value being exactly 2x the XY value was flagged in iteration 4 and remains unexplained. A footnote ("YX routing loads the longer dimension first; for 4x4 square grids, the factor-of-2 difference arises from asymmetric path distribution under YX") or similar would resolve this. For 4x4 (a square grid), XY and YX should be symmetric---the factor of 2 suggests either a non-square internal representation or a bug in the computation. This deserves verification.
- The abstract states "validated in BookSim cycle-accurate simulation across 2x2, 4x4, and 8x8 internal mesh configurations." This could be misread as three different chiplet grid sizes rather than three internal mesh sizes. Consider: "validated in BookSim across three internal mesh configurations (2x2, 4x4, 8x8 routers per chiplet)."

## Questions for Authors

1. [Q1] Table III: At what injection rate was the 168-link adjacent configuration run to achieve ~200 latency at 8x8? Is this in the linear regime, near-saturation, or deep saturation for the adjacent-only topology? If deep saturation, the 2.3x saving is partly an artifact of comparing "near saturation" (adjacent) vs. "comfortable operating range" (express). A saturation curve for both strategies at 8x8 would clarify this.

2. [Q2] The cost advantage increases from 1.0x (2x2) to 2.0x (4x4) to 2.3x (8x8). Does this trend continue for larger internal meshes (e.g., 16x16)? If so, the cost advantage might be even larger for realistic chiplet designs with large internal NoCs.

3. [Q3] Table II shows YX routing with Max alpha = 223 at 4x4 (exactly 2x the XY value of 111). For a square grid, XY and YX should produce symmetric load distributions. Can you verify this value?

## Rating

- Novelty: 3.5/5 (up from 3/5; the cost-efficiency reframing is a genuinely new perspective on the phantom load problem, not merely a re-presentation of the same results)
- Technical Quality: 4/5 (up from 3.5/5; the 8x8 internal mesh experiments address the most serious methodological gap; the "Why this is a cost problem" paragraph completes the analytical chain from Theta(K) amplification to Theta(K) cost)
- Significance: 4/5 (up from 4/5 nominally, but the cost framing makes the significance more defensible; a chiplet architect now has a quantitative cost argument, not just a performance argument)
- Presentation: 4/5 (unchanged; the restructuring improves narrative coherence, but Table III's uncontrolled target latencies and the injection rate inconsistency between Fig. 1 and Table III prevent further improvement)
- Overall: 4/5 (up from 3.5/5)
- Confidence: 5/5

## Score Justification vs Iteration 4

**Novelty improved from 3 to 3.5.** The cost-efficiency framing is not merely presentational---it changes what the paper is claiming. "Phantom load forces Theta(K) unnecessary link cost" is a different (and stronger) claim than "phantom load causes Theta(K) traffic amplification." The 8x8 result showing cost advantage *increasing* with border capacity is a novel and counterintuitive finding.

**Technical quality improved from 3.5 to 4.** The 8x8 internal mesh experiments are the decisive addition. They eliminate the concern that the 2x2 results are artifacts of border capacity constraints. The "Why this is a cost problem" paragraph completes the analytical argument chain. Table III provides clean empirical evidence.

**Significance steady at 4, but better supported.** The cost framing makes the paper directly relevant to chiplet architects making cost tradeoffs, not just NoC researchers studying congestion. The argument is now: "you are paying 2.3x more for interposer links than necessary." This is a concrete, actionable claim.

**Overall improved from 3.5 to 4.** The cost-efficiency reframing, 8x8 experiments, and Table III collectively address the paper's two primary weaknesses from iteration 4: (1) the implicit cost argument is now explicit, and (2) the internal mesh size sensitivity is empirically resolved. The remaining weaknesses (uncontrolled target latencies in Table III, brief Kite-like treatment, absent ECMP/Valiant closed-form, unspecified MoE parameters) are minor relative to the improvements.

## Decision

**Accept.** The iteration-5 revision addresses the two deepest structural issues in the paper's argument:

First, the cost-efficiency reframing resolves the longstanding weakness that the paper's practical relevance depended on end-to-end latency sensitivity, which was unsubstantiated. The new framing ("same performance at 2.3x fewer links") is self-contained: even if phantom load latency is completely hidden by compute, the cost saving justifies express links. The "Why this is a cost problem" paragraph after Theorem 1 is the single most impactful addition across all five iterations---it is two sentences that complete the analytical chain from Theta(K) amplification to Theta(K) cost, which is the paper's core intellectual contribution.

Second, the 8x8 internal mesh experiments eliminate the methodological concern that the results were artifacts of unrealistically constrained border capacity. The finding that cost advantage *increases* with internal mesh size is counterintuitive and strengthens the argument: more adjacent capacity means more waste from phantom tax, making express links relatively more valuable. This is the kind of result that changes how architects think about interposer link provisioning.

The remaining weaknesses are genuine but do not undermine the core contributions: (1) Table III's uncontrolled target latencies introduce a minor confound but the directional result is robust; (2) the Kite-like identical-saturation result deserves slightly more prominence; (3) ECMP/Valiant closed-form analysis is absent but acceptable for a conference paper; (4) MoE parameters remain unspecified. None of these are blocking.

The paper now delivers: correct Theta(K) theory with explicit cost connection, comprehensive routing-algorithm independence, workload sensitivity across six patterns, cost-to-target validation across three internal mesh sizes, workload-aware placement that correctly falls back to adjacent allocation for sparse traffic, and actionable design guidelines. For DATE, this is a clear contribution.

**What would elevate to Strong Accept:** (1) Control target latencies in Table III to a consistent operating point across mesh sizes; (2) verify the YX Max alpha = 223 anomaly at 4x4; (3) specify MoE traffic model parameters for reproducibility. These are polish items, not structural concerns.
