# Review -- Reviewer 4 (Theory/Analysis Expert), Iteration 4

## Summary
This paper characterizes "phantom load" in 2D mesh chiplet Network-on-Interposer (NoI), derives closed-form flow-count expressions under XY routing with uniform all-to-all traffic, proves Theta(K) center-link amplification in square grids, demonstrates routing-algorithm independence across four algorithms, and evaluates workload sensitivity across six LLM communication patterns. The mitigation design space exploration compares five strategies, with express links providing 2.0--2.6x improvement for dense traffic and load-aware adjacent allocation shown sufficient for sparse MoE workloads. BookSim cycle-accurate simulation validates both the dense and sparse regimes. The iteration-4 revision adds a Kite-like baseline in the main BookSim table, explains the Table IX anomaly, tightens guideline numbers, adds an AMD/NVIDIA paragraph, and corrects the abstract.

## Response to Iteration-3 Suggestions

**[Suggestion 1] F_H r-independence explanation.** Not addressed in this revision. The proof sketch (lines 111--112) still reads: "A horizontal link at column boundary c|c+1 in row r is crossed by flow (s,d) iff the source is at row r with column <= c and the destination has column >= c+1." This correctly describes the mechanics but does not make explicit the punchline: under XY routing, horizontal traversal happens at the source row, so summing over all source rows yields R as a multiplicative factor independent of r. A reader who works through the math will reach this conclusion, but a single clarifying sentence ("Since XY routing performs all horizontal hops at the source row, the count is identical for every row position r") would remove ambiguity. **Not addressed; remains a minor expository issue. Acceptable for camera-ready.**

**[Suggestion 2] Cite [14] in Related Work text.** Not addressed. Reference [14] (Leighton-Rao, MCF theory) appears only in the bibliography (line 513) but is never cited in the body text. The Discussion section mentions the MCF connection implicitly ("the root cause -- many long-distance flows sharing limited intermediate links") but does not cite [14]. A single sentence in Related Work, e.g., "Phantom load is the chiplet-NoI manifestation of multicommodity flow congestion~\cite{mcf_theory}," would strengthen the theoretical positioning at zero cost. **Not addressed; trivial fix for camera-ready.**

**[Suggestion 3] Table IX anomaly explained.** **Addressed.** The new text after Table IX (line 400) explicitly explains why "Express (0 placed)" shows higher latency than Uniform: "the greedy algorithm produces a non-uniform adjacent allocation (concentrating links on analytically high-load pairs), which can create router-level contention not captured by the link-level analytical model." This is a satisfying explanation -- it identifies the gap between link-level optimization and router-level microarchitectural effects, and cites BookSim as the source of the discrepancy. This also honestly acknowledges a modeling limitation. **Fully addressed.**

## New Additions Evaluated

**Kite-like baseline in main BookSim table (Table VII).** This is a significant addition. The K=16 row now shows three strategies: Adj. Unif. (54.3/846/0.0106), Kite-like (54.4/846/0.0104), and Express (29.4/37.6/0.0200). The fact that Kite-like and Adj. Unif. produce virtually identical results at K=16 is a powerful empirical demonstration that adjacent-only optimization has a hard ceiling. This directly supports the paper's central claim that topology change (express links) is necessary, not merely better allocation. Well-placed addition.

**AMD/NVIDIA paragraph (Discussion).** The new paragraph (line 451) connecting the analysis to AMD MI300X (K=8, alpha_max=8, "manageable" regime) and NVIDIA B200 (K=2, trivially no phantom load) is effective. It grounds the otherwise abstract characterization in real commercial products and provides forward-looking predictions for K >= 16 designs. The claim that AMD's all-to-all Infinity Fabric among XCDs is "effectively a fully-connected topology at small K" is a reasonable simplification for a conference paper, though it elides the hierarchical nature of IF (XCD-to-IOD-to-XCD).

**Abstract correction.** The abstract now correctly states "6x imbalance at K=32" (for ECMP/Valiant), matching Table III values (6.1x ECMP, 5.2x Valiant at 4x8). Previously, the specific number was not verified. Consistent.

**Guideline number consistency.** Checked: Guideline 1 states alpha_max < 5 for K <= 8, alpha_max > 10 for K >= 16. Table II confirms: K=8 (2x4) has max alpha=8.0, K=9 (3x3) has 6.0, K=16 (4x4) has 16.0. The threshold "alpha_max < 5" is actually below K=9's value of 6.0, so the guideline is conservative (K <= 8 means K=4 with alpha=2 or K=8 with alpha=8; alpha=8 > 5). This threshold is somewhat loose -- it says "manageable" when alpha < 5 but the K=8 case has alpha=8 which exceeds 5. The text says "K <= 8 square grids" but K=8 in the paper is a 2x4 grid with alpha_max=8.0, and K=9 (3x3) has alpha_max=6.0. The guideline should perhaps say "K <= 9" for square grids (alpha_max=6) or clarify that the threshold refers to square grids only. This is a minor imprecision that could confuse a careful reader. Not a new issue -- it was present in iteration 3 and I did not flag it then.

## Remaining Strengths

1. [S1] **Theorem 1 is correct and useful.** The closed-form F_H(r,c) = 2R(c+1)(C-c-1) is clean and practically applicable. The Theta(K) amplification bound is the paper's core theoretical contribution.

2. [S2] **Routing independence is now convincingly demonstrated across both theory and practice.** The four-algorithm comparison plus the Kite-like BookSim baseline collectively show the structural nature of phantom load.

3. [S3] **Counter-intuitive results retain their practical value.** Traffic-proportional being 1.5x worse than uniform, express links being unhelpful for MoE, and Kite-like matching uniform at K=16 -- all non-obvious findings.

4. [S4] **The Table IX anomaly explanation is honest and informative.** Acknowledging the link-level vs. router-level modeling gap adds credibility rather than detracting from the work.

5. [S5] **Commercial system connection is effective.** The AMD/NVIDIA paragraph makes the work immediately relevant to practitioners and provides testable predictions for future products.

## Remaining Weaknesses

1. [W1] **[14] is still a phantom citation.** Leighton-Rao appears in the bibliography but is never \cite'd in the text. This is the fourth iteration without addressing this. It is a trivial fix (one sentence) but its persistent absence is notable. A reference that appears only in the bibliography and never in the body will be flagged by any venue's camera-ready checklist.

2. [W2] **F_H r-independence still unexplained.** The proof sketch implicitly assumes the reader will realize that XY routing makes row position irrelevant for horizontal flow counts. One clarifying sentence would resolve this. This is purely expository and does not affect correctness.

3. [W3] **Guideline 1 threshold imprecision.** The guideline says "alpha_max < 5" maps to "K <= 8 square grids," but K=9 (3x3) has alpha_max=6.0, and K=8 as used in the paper is 2x4 (not square) with alpha_max=8.0. The statement is self-consistent only if "K <= 8 square grids" means "square grids with K <= 8," i.e., 2x2 only (alpha_max=2). This threshold language needs tightening. Suggest: "For square grids with K <= 9 (alpha_max <= 6), phantom load is manageable."

4. [W4] **ECMP closed form and LP lower bound remain absent.** These were flagged in iterations 2 and 3 and acknowledged as journal-extension material. The position is acceptable for a conference paper. No change expected.

## Minor Issues

- Guideline 6 still does not specify which CoWoS generation or UCIe revision the 0.8 um wire pitch and Standard PHY area are drawn from. This matters because CoWoS-S, CoWoS-L, and CoWoS-R have different interposer dimensions and routing densities.
- The Kite-like Discussion paragraph (line 453) says "Our MinMax adjacent strategy ('Kite-like' in Table VII)." Verify that the table numbering is correct after all additions -- Table VII is the main BookSim table. (If table numbering shifted due to additions, this cross-reference may be stale.)
- Table III: The YX routing anomaly (exactly 2x all XY values) is still unexplained. This is a recurring minor concern. A one-sentence footnote ("YX loads the longer dimension first in non-square grids, doubling load on fewer links") would suffice.

## Questions for Authors

1. [Q1] Guideline 1 states alpha_max < 5 for K <= 8. But the paper's K=8 configuration (2x4) has alpha_max = 8.0 (Table II). Is the guideline referring only to square grids (2x2, alpha_max=2.0)? If so, the phrasing should be more precise.

2. [Q2] The Kite-like strategy in Table VII shows slightly worse throughput (0.0104) than Adj. Unif. (0.0106) at K=16. Is this within noise, or does MinMax adjacent allocation create some router-level contention similar to the Express (0 placed) anomaly in Table IX?

## Rating

- Novelty: 3/5 (unchanged)
- Technical Quality: 3.5/5 (unchanged; the Table IX explanation improves transparency but no new theoretical content)
- Significance: 4/5 (unchanged; the AMD/NVIDIA paragraph and Kite-like baseline strengthen practical relevance)
- Presentation: 4/5 (unchanged; the two unfixed minor items -- [14] citation and F_H explanation -- prevent improvement)
- Overall: 3.5/5 (unchanged numerically)
- Confidence: 5/5

## Decision

**Weak Accept.** The iteration-4 revision addresses the most actionable item from my iteration-3 feedback: the Table IX "Express (0 placed)" anomaly now has a clear and honest explanation attributing it to the link-level vs. router-level modeling gap. The Kite-like baseline in the main BookSim table (Table VII) is a valuable addition that empirically demonstrates the hard ceiling of adjacent-only optimization. The AMD/NVIDIA paragraph effectively connects the abstract characterization to commercial chiplet systems.

Two of my three iteration-3 suggestions remain unaddressed: (1) the F_H r-independence explanation and (2) citing [14] in the body text. Both are genuinely minor -- one clarifying sentence each -- but their persistent absence across four iterations is mildly concerning. The uncited [14] in particular will be caught by any venue's camera-ready process, as a bibliography entry with no corresponding \cite command is a formatting error.

The paper's contribution is clear and validated: first systematic characterization of phantom load, correct Theta(K) scaling, routing-algorithm independence, workload sensitivity across six patterns, five mitigation strategies with counter-intuitive findings, and BookSim validation in both dense and sparse regimes. The seven design guidelines are actionable and grounded in both analytical and simulation results.

**What would elevate to Accept:** (1) Add one sentence to the proof sketch explaining F_H's r-independence; (2) cite [14] in Related Work or Discussion body text; (3) tighten Guideline 1 threshold language to avoid the K=8/alpha_max=8 inconsistency. All three are camera-ready-level fixes requiring no new experiments or analysis.
