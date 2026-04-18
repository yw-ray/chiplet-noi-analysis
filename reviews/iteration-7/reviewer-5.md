# Review -- Reviewer 5 (Skeptic), Iteration 7

## Summary

Iteration 7 is a targeted editorial revision addressing the three specific fixes I requested for a full Accept in my iteration-6 review. No new experiments or structural changes; the modifications are confined to wording corrections and a single added sentence. This review verifies whether all three fixes are properly executed.

## Verification of Requested Fixes

### Fix 1: "72 express links" -> "72 total links (including express)"

**Status: FIXED.**

- **Introduction (line 41):** Now reads "only **72 total links (including express) suffice** when they bypass the phantom load." Previously this said "only 72 links suffice when express links bypass the phantom load," which was ambiguous about the link composition. The new phrasing explicitly signals that the 72-link configuration is a *mix* of adjacent and express links, not 72 pure express links.

- **Physical Overhead (line 346):** Now reads "72 total links (including ~19 express) replace 168 adjacent-only links, saving ~96 PHY modules (~48 mm^2 PHY area)." Previously this said "72 express links replace 168 adjacent links." The new phrasing is substantially better: it provides the exact breakdown (~19 express out of 72 total, implying ~53 adjacent), which gives the reader the information needed to assess wire-length-adjusted cost. The "~19 express" detail is a welcome addition beyond what I strictly required.

**Verdict: Cleanly executed.** Both occurrences are corrected. The Physical Overhead phrasing is actually better than my minimum request because it includes the ~19 express breakdown.

### Fix 2: "2.3x" -> "up to 2.3x" in abstract

**Status: FIXED.**

- **Abstract (line 30):** Now reads "Express links achieve the same latency target as adjacent-only topologies using **up to 2.3x fewer inter-chiplet links**." Previously this stated "2.3x fewer inter-chiplet links" without qualification.

The "up to" qualifier is the correct fix. The paper validates across three internal mesh sizes (2x2, 4x4, 8x8) with savings of 1.0x, 2.0x, and 2.3x respectively. Presenting 2.3x as the upper bound rather than the general result is honest and accurate. The abstract also still states "validated in BookSim cycle-accurate simulation across 2x2, 4x4, and 8x8 internal mesh configurations," which contextualizes the range.

I also note:
- **Introduction (line 47):** States "2--3x lower link cost" which is appropriately presented as a range, not a single point. Consistent.
- **Contributions (line 52):** States "2.3x fewer links on realistic 8x8 internal meshes" -- this is acceptable because it is explicitly scoped to the 8x8 mesh, not presented as a general result.

**Verdict: Cleanly executed.** The abstract claim is now properly qualified.

### Fix 3: Note that advantage is strongest at 2-4x budget

**Status: FIXED.**

- **Section V.B, 8x8 mesh paragraph (line 305):** Now includes the sentence: "The advantage is strongest at 2--4x budget per adjacent pair; at higher budgets ($\geq$5x), the greedy algorithm's suboptimal placement can reduce the advantage (see Limitations)."

This sentence is placed in exactly the right location -- immediately after the 2.3x cost saving claim for 8x8 mesh, within the main results section (not buried in Limitations). It achieves three things:
1. **Scopes the advantage** to the 2-4x budget range, which is the practically relevant regime for cost-conscious architects.
2. **Attributes the degradation** to the greedy algorithm (not to express links fundamentally), which is consistent with the Limitations paragraph.
3. **Cross-references Limitations** for readers who want the full story.

The Limitations section (line 372) retains the complementary sentence: "The greedy algorithm shows suboptimal behavior at very high budgets ($\geq$5x per pair) on 8x8 meshes; ILP formulation could improve this." The two sentences together -- one in the main results, one in Limitations -- provide adequate disclosure without belaboring the point.

**Verdict: Well placed and well worded.** The sentence integrates naturally into the 8x8 discussion and does not disrupt the flow.

## Additional Observations

### Consistency Check

I verified that the three fixes do not introduce inconsistencies with the rest of the paper:

- **Table V (line 296):** Reports "Expr Links: 72" for 8x8 mesh. This is consistent with line 41's "72 total links (including express)" -- the table header says "Expr Links" as the column name, which could be read as "links in the express configuration" rather than "links that are express." This is a minor ambiguity but acceptable given the context.

- **Conclusion (line 374):** States "the 2.3x cost advantage confirms the result is not a modeling artifact." This is scoped to 8x8 mesh via the preceding context ("including realistic 8x8 meshes where"), so it is consistent with the "up to 2.3x" in the abstract. No fix needed.

- **Design Guidelines (line 356-358):** Guidelines 3 and 6 reference "2-3x cost saving" as a range. Consistent with both the "up to 2.3x" abstract claim and the range across mesh sizes.

### Prior Weaknesses Status

For completeness, I note the status of all weaknesses from iteration 6:

- **[W1] 8x8 reversal at 5-6x budget:** ADEQUATELY ADDRESSED by Fix 3. The main results now explicitly scope the advantage to 2-4x budget and note the degradation at higher budgets. Combined with the Limitations disclosure, this is sufficient for a conference paper. The full budget sweep data remains unpresented, but the textual qualification removes the risk of reader misunderstanding.

- **[W2] 2.3x claim presented as general:** RESOLVED by Fix 2. The "up to" qualifier in the abstract and the budget-range note in Section V.B together scope the claim appropriately.

- **[W3] "72 express links" factually misleading:** RESOLVED by Fix 1. Both occurrences now correctly describe the mixed topology.

- **[W4] Wire-length-adjusted cost not reported:** PARTIALLY ADDRESSED (unchanged from iter-6). The ~19 express link breakdown in line 346 now gives the reader the raw data to compute the wire-adjusted cost (~1.67x). The paper does not compute this itself, but the information is available. I no longer consider this a blocking issue.

- **[W5] Ablation at 2x2 only:** UNCHANGED. Minor issue, not blocking.

- **[W6] 1/10 seed result unreported:** UNCHANGED. Minor issue, not blocking.

## Strengths (Consolidated, Final)

1. **[S1] Cost framing is the right framing.** The paper asks the architect's question: "to achieve target performance, which topology is cheaper?" This is more actionable than raw performance comparisons.

2. **[S2] Analytical foundation (Theorem 1, Theta(K) scaling) is a standalone contribution.** The closed-form phantom load analysis, routing independence across four algorithms, and workload sensitivity across six LLM patterns are rigorous and independently valuable even without the express link proposal.

3. **[S3] 8x8 mesh experiments confirm the result is not a border-capacity artifact.** This was the critical validity check and it passes: express links save 2.3x even when adjacent links have 8 border routers per edge.

4. **[S4] Kite-like identical saturation (54.3 vs 54.4).** The most striking empirical result in the paper. It proves that even theoretically optimal adjacent allocation cannot break the phantom load ceiling at K=16.

5. **[S5] Ablation demonstrates both express links and greedy placement are necessary.** Random express worse than adjacent uniform; greedy outperforms fully-connected by 2.5x. This decomposes the contribution cleanly.

6. **[S6] Workload-aware design validated by MoE.** The greedy algorithm placing zero express links for sparse MoE traffic is a strong demonstration of workload sensitivity, preventing the paper from being a one-trick "express links are always better" story.

7. **[S7] Practical design guidelines with concrete thresholds.** Seven guidelines with specific K thresholds, area/power overheads, and strategy-to-workload mappings are directly usable by practitioners.

8. **[S8] Honest limitations disclosure.** BookSim store-and-forward artifact, greedy suboptimality at high budgets, and parameterized (not production RTL) traffic matrices are all acknowledged. The paper does not oversell.

## Remaining Minor Issues (Non-Blocking)

- Table II caption says "2x2 Mesh" but shows 4x4 and 4x8 grid results. The caption refers to internal mesh size, which is confusing given the paper uses NxN for both chiplet grids and internal meshes. A notation clarification table would help.
- The paper lacks a notation/setup table consolidating the three uses of "mesh" (chiplet grid, internal mesh, BookSim mesh).
- Sensitivity analysis: the 1/10 seed where express does not win should be briefly characterized.

These are all camera-ready polish items, not acceptance barriers.

## Rating

- Novelty: 3.5/5 (unchanged)
- Technical Quality: 3.75/5 (up from 3.25; the three editorial fixes resolve factual inaccuracies and scope the claims properly)
- Significance: 3.5/5 (unchanged)
- Presentation: 4.0/5 (up from 3.5; the fixes demonstrate responsiveness to review and improve accuracy without disrupting flow)
- Overall: **4.0/5** (up from 3.5)
- Confidence: 4.5/5

## Decision

**Accept.**

All three fixes I specified for a full Accept have been properly executed:

1. "72 express links" is now "72 total links (including express)" in the introduction and "72 total links (including ~19 express)" in the Physical Overhead section. The latter is better than my minimum request because it provides the exact express/adjacent breakdown.

2. "2.3x" is now "up to 2.3x" in the abstract, correctly presenting the result as an upper bound rather than a universal finding.

3. A sentence in Section V.B now explicitly notes the advantage is strongest at 2-4x budget per pair, with degradation at higher budgets attributed to greedy algorithm limitations. This scopes the claim in the main results, not just in Limitations.

These were editorial changes requiring no new experiments, and they were executed cleanly. The paper's core contributions remain strong: the Theta(K) phantom load analysis is a standalone analytical contribution, the cost framing is the right way to evaluate chiplet NoI topologies, and the 8x8 mesh experiments (with proper caveats) confirm the express link advantage is genuine. The workload-aware design (express for dense, adjacent for sparse) prevents overgeneralization.

The paper is ready for publication. The remaining minor issues (notation table, 1/10 seed characterization, Table II caption) are camera-ready items that do not affect the technical conclusions.
