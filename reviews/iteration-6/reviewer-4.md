# Review -- Reviewer 4 (Theory/Analysis Expert), Iteration 6

## Summary
This paper characterizes "phantom load" in chiplet Network-on-Interposer (NoI), proves center-link amplification grows as Theta(K) in square grids, and demonstrates that express links achieve the same latency as adjacent-only topologies at 2.3x fewer links. The iteration-6 revision is an incremental polish over iteration 5, which itself was the major inflection point. The three changes specifically responding to my iteration-5 minor items are: (1) F_H row-independence is now explained in the Theorem 1 statement, (2) the Kite-like discussion is expanded in Section V-C, and (3) MoE parameters are specified as "top-2 routing across K experts." A full mitigation comparison table (Table IV, five strategies) and a restored ablation table (Table V) are also present. The cost thesis remains the paper's core strength, and the new material polishes rather than restructures the argument.

## Response to Iteration-5 Suggestions

**[Suggestion 1] Table III target latencies uncontrolled across mesh sizes.** The authors acknowledged this concern in the iteration notes. The paper itself does not change Table III---target latencies remain ~30, ~50, ~200 for the three mesh sizes. No normalization by latency-to-floor ratio or fixed utilization level is introduced. The concern stands but, as I noted previously, it does not invalidate the directional result. **Not addressed. Minor; the directional result is robust regardless.**

**[Suggestion 2] Kite-like treatment too brief.** Section V-C ("Adjacent-Only Ceiling") is now expanded relative to iteration 5. The previous version had a single-paragraph subsection; the current version retains explicit BookSim numbers (54.3 vs 54.4 at rate 0.01, both saturating at rate 0.015 with latency >800) and contrasts with express performance (29.4 at rate 0.01, stable through 0.015 at 37.6). Additionally, the Related Work section now includes the sentence: "We include a Kite-like baseline (MinMax adjacent) and show it saturates identically to uniform at K=16." This cross-reference between Related Work and the evaluation strengthens the narrative. **Addressed. The Kite-like result now has adequate prominence.**

**[Suggestion 3] MoE parameters unspecified.** The paper now states "top-2 routing across K experts" in Table IV's workload description (line 186). This specifies the top-k parameter (k=2) and implicitly the expert count (K=32 for the K=32 evaluation). Capacity factor remains unspecified, but top-k and expert count are the two parameters that most directly determine traffic density. **Substantially addressed. Capacity factor is a secondary parameter for the phantom-load analysis; top-k and expert count suffice for reproducibility of the core finding.**

## Assessment of Changes

### Change 1: F_H Row-Independence Explanation in Theorem 1

Line 113 now includes: "where F_H is independent of row position because XY routing performs all horizontal movement at the source row, so every row contributes equally to horizontal link load."

**Assessment:** This is exactly the clarification I requested in iteration 4. The explanation is concise (one subordinate clause) and correctly identifies the mechanism: under XY routing, a packet moves horizontally first (at the source row), then vertically. Therefore, horizontal link (c|c+1) is used by flows from *every* row that need to cross column c, making F_H independent of row index r. The factor 2R in Eq. (2) accounts for the 2 directions times R rows, each contributing the same (c+1)(C-c-1) flow count. This resolves a clarity gap that has persisted since iteration 1.

**Verdict: Clean resolution. The theorem statement is now self-contained.**

### Change 2: Eq. 4 Shown Explicitly

Equation (4) (line 118) now shows the alpha_max formula explicitly:

alpha_max = R * ceil(C/2) * floor(C/2) = Theta(K) for square grids

In iteration 5, the connection from F_H to alpha_max was stated but not shown as a numbered equation. Making this explicit allows the reader to verify the scaling claim directly: for a 4x4 grid (R=4, C=4), alpha_max = 4 * 2 * 2 = 16, matching Table I. For 8x8 (R=8, C=8), alpha_max = 8 * 4 * 4 = 128, again matching Table I. The "since each link has 2 direct flows" (line 116) bridges the gap between flow count F_H and amplification alpha.

**Assessment:** This is a useful improvement for verifiability. A reader can now independently check every row of Table I against Eq. (4) without re-deriving from first principles.

**Verdict: Improves self-containedness. Minor but worthwhile.**

### Change 3: Full Mitigation Comparison Table (Table IV)

Table IV now presents all five strategies (Uniform, Traffic-proportional, Load-aware, MinMax adjacent, Express greedy) across two grid sizes (2x4 and 4x4) and three budget multipliers (3x, 4x, 6x). This is a significant improvement over the iteration-5 presentation, where the mitigation comparison was less systematic.

**Assessment:** The table clearly shows:
- Traffic-proportional is consistently the worst strategy (rho_max = 8.2 at K=8 regardless of budget, because it allocates zero capacity to phantom-loaded links with no direct demand). The budget-invariance of traffic-proportional is a powerful visual indicator---the reader immediately sees that this strategy is fundamentally broken.
- Load-aware and MinMax are close but not identical (e.g., 4.2 vs 3.3 at K=8, 3x budget), confirming that MinMax is strictly better than load-aware for adjacent-only topologies.
- Express greedy is consistently the best, with the gap widening at larger K (18% better than MinMax at K=8 vs 19% at K=16 for 3x budget).

The budget multiplier dimension (3x, 4x, 6x) is a welcome addition. It shows that express advantage persists across budget regimes: at generous budgets (6x), express still provides 1.1 vs 1.5 (MinMax) at K=8, and 2.7 vs 3.7 at K=16. The advantage is not an artifact of tight budgets.

**Verdict: The most useful addition to the evaluation section. This table systematically demonstrates that express links dominate across strategies, budgets, and grid sizes.**

### Change 4: Ablation Table Restored (Table V)

Table V restores the ablation study comparing placement strategies: adjacent uniform (62.8), random express (85.4, *worse*), fully connected (39.0), and greedy express (15.3).

**Assessment:** The random-express-is-worse result (85.4 vs 62.8) is the ablation's key insight. It demonstrates that the express link *concept* alone is insufficient---placement quality is critical. Random placement can actually degrade performance because it wastes budget on low-impact links while leaving high-phantom-load links unaddressed. The greedy-vs-fully-connected comparison (15.3 vs 39.0) shows that concentrated placement on high-impact pairs outperforms spreading budget uniformly across all pairs.

The ablation was present in earlier iterations but was compressed to a paragraph in iteration 5. Restoring it as a table improves accessibility without adding significant page budget.

**Verdict: Good restoration. The ablation supports the design-guideline claim that "placement matters more than the concept itself."**

### Change 5: "Why this is a cost problem" Paragraph

This paragraph (lines 141-142) was introduced in iteration 5. In iteration 6, it reads: "To keep the most congested link below utilization target rho*, an adjacent-only topology must provision ceil(alpha_max / rho*) links on center pairs---Theta(K) links per pair. Express links reduce alpha_max toward 1, eliminating this cost overhead."

**Assessment:** Unchanged from iteration 5. As I noted in my previous review, this is the single most impactful addition across all iterations. The two sentences complete the analytical chain: Theta(K) amplification (Theorem 1) implies Theta(K) link provisioning cost (this paragraph) implies 2.3x empirical cost gap (Table III). No further modification needed.

### Change 6: Guideline 1 Threshold Updated

Guideline 1 now reads: "If alpha_max < 8 (K <= 8), adjacent allocation suffices. If alpha_max >= 16 (K >= 16), express links are cost-effective."

**Assessment:** In iteration 5, the threshold was stated as "alpha_max < 5" and "alpha_max > 10," which was inconsistent with the K=8 data (alpha_max = 8 exceeds 5). The updated thresholds (8 and 16) are now consistent with Table I: K=8 yields alpha_max = 8 (at the threshold), K=16 yields alpha_max = 16 (at the express-link threshold). This resolves the threshold imprecision I flagged as a minor issue.

**Verdict: Clean fix. The thresholds are now data-consistent.**

## Strengths

1. [S1] **Cost-efficiency thesis remains the paper's strongest asset.** The "same latency at 2.3x fewer links" framing is unchanged and continues to be the paper's most defensible and actionable claim. The analytical chain (Theorem 1 -> "Why this is a cost problem" -> Table III) is complete and clean.

2. [S2] **Table IV (five-strategy mitigation comparison) is now the most complete experimental result.** The combination of five strategies, two grid sizes, and three budget levels provides a comprehensive design-space map. The traffic-proportional budget-invariance and the consistent express advantage across budget levels are clearly visible.

3. [S3] **F_H row-independence explanation resolves a multi-iteration clarity gap.** The one-sentence addition to Theorem 1 makes the proof self-contained without expanding the page budget.

4. [S4] **Kite-like baseline treatment is now adequate.** The combination of Related Work cross-reference and dedicated subsection (V-C) gives this result the prominence it deserves. The identical-saturation finding (54.3 vs 54.4) is now clearly positioned as evidence that the adjacent-only ceiling is fundamental, not an allocation deficiency.

5. [S5] **MoE parameterization improves reproducibility.** "Top-2 routing across K experts" is sufficient for a reader to reconstruct the traffic matrix.

6. [S6] **Guideline 1 thresholds are now data-consistent.** The alpha_max < 8 / >= 16 boundaries match Table I exactly, removing the previous imprecision.

## Weaknesses

1. [W1] **Table III target latencies remain uncontrolled.** This is the same concern from iteration 5. The 2x2 target (~30) is near the latency floor, the 4x4 target (~50) is moderate, and the 8x8 target (~200) is in a regime where adjacent-only is likely near saturation. A normalized comparison (e.g., latency at 50% of saturation throughput for each configuration) would be more rigorous. I accept this is unlikely to change the directional result, and it may be a space constraint issue. **Severity: Minor.**

2. [W2] **ECMP/Valiant closed-form argument is still absent.** The routing independence claim rests entirely on Table II (empirical). A one-paragraph argument---e.g., "ECMP splits flows across equal-cost paths, reducing peak load by at most a constant factor proportional to path diversity, which is O(min(R,C)) for a grid; since Theta(K) grows as R*C, ECMP reduces alpha_max by at most O(sqrt(K)), leaving Theta(sqrt(K)) amplification. Valiant randomizes destinations, halving concentration but doubling total load, achieving Theta(1) imbalance at Theta(K) total traffic"---would complete the theoretical contribution. This has been flagged since iteration 3. **Severity: Minor for a conference paper; would strengthen a journal extension.**

3. [W3] **Table II anomaly: YX Max alpha = 223 at 4x4 (exactly 2x XY's 111).** This remains unexplained. For a square 4x4 grid, XY and YX should produce isomorphic load distributions (by symmetry of the grid under 90-degree rotation, swapping row and column indices). The factor-of-2 difference suggests either: (a) the internal mesh is not square (which is possible if F_V and F_H are computed on a non-square sub-grid), (b) the load computation uses directed flows that are not symmetric under transposition, or (c) there is a computation error. This is a verifiable claim---the authors should either explain the asymmetry or correct the value. **Severity: Minor but distracting. A careful reader will notice.**

4. [W4] **The differential bandwidth analysis (Section IV, last paragraph) remains disconnected from the cost framing.** The paragraph states that express links with 75% BW decay provide 1.8-2.2x improvement and with 50% decay provide 1.6-1.8x. These numbers are in terms of rho_max improvement, not link-count savings. Translating to the cost framing: "With 50% BW decay per hop distance, express links achieve the same target latency at approximately 1.6x fewer links rather than 2.3x---still a substantial cost saving." This one-sentence addition would integrate the BW decay analysis with the paper's central thesis. **Severity: Minor.**

5. [W5] **Algorithm 1 does not specify the routing algorithm used for path computation.** Line 229 says "Route traffic on A union {c} (Dijkstra); compute rho_max." Dijkstra computes shortest paths, but the paper analyzes four routing algorithms (XY, YX, ECMP, Valiant). Which routing is used in the greedy algorithm? If Dijkstra (shortest-path), this is a fifth routing algorithm distinct from the four analyzed in Table II. If XY, why not state it explicitly? This ambiguity has not been flagged previously but is relevant for reproducibility.

## Minor Issues

- The abstract mentions "seven actionable design guidelines" but I count exactly seven in Section VI. This is consistent; just a verification note.
- Table II caption says "2x2 Mesh" but the table contains 4x4 and 4x8 results. The caption appears to refer to the internal mesh size used in the simulation, not the chiplet grid. This should be clarified: "Load Imbalance Across Routing Algorithms (2x2 Internal Mesh)" or simply remove the mesh size from the caption since the table body specifies the grid sizes.
- Line 309: "latency 54.3 vs. 54.4" --- the difference (0.1 cycle) is within simulation noise. The paper correctly says "nearly identical," but a parenthetical noting this is within noise (e.g., "within simulation variance") would preempt the question of whether 0.1 cycle is statistically significant.

## Questions for Authors

1. [Q1] Algorithm 1 uses Dijkstra for routing. Is this the routing algorithm used in all greedy placement experiments, or is it only used during the placement phase with a different routing algorithm (e.g., XY) used in BookSim evaluation? If the latter, there is a potential mismatch: links placed optimally for Dijkstra routing may not be optimal for XY routing.

2. [Q2] Table IV shows express greedy at K=16 with 6x budget achieving rho_max = 2.7. At what point does rho_max approach 1.0 (fully de-congested)? If the budget required to reach rho_max = 1.0 with express is significantly lower than with adjacent-only, this would strengthen the cost argument even further.

3. [Q3] The paper mentions "suboptimal behavior at very high budgets (>=5x per pair) on 8x8 meshes" in the Limitations paragraph. Can you characterize this suboptimality? Does the greedy algorithm plateau, or does it actively degrade? If plateau, this is expected diminishing returns. If degradation, it suggests the greedy heuristic makes locally optimal choices that become globally suboptimal at high budgets---which would motivate the ILP formulation mentioned as future work.

## Rating

- Novelty: 3.5/5 (unchanged from iteration 5; no new conceptual contributions in this iteration)
- Technical Quality: 4/5 (unchanged; the F_H explanation and Guideline 1 threshold fix are minor corrections, not quality improvements; Table IV is more systematic but the underlying results were already present)
- Significance: 4/5 (unchanged; the cost thesis remains the paper's central contribution and is well-supported)
- Presentation: 4.5/5 (up from 4/5; the F_H explanation, Table IV systematization, restored ablation table, Kite-like expansion, and threshold fix collectively resolve most of the presentation issues I identified previously)
- Overall: 4/5 (unchanged; the iteration-6 changes are polish, not structural)
- Confidence: 5/5

## Score Justification vs Iteration 5

**Novelty unchanged at 3.5.** No new findings or reframings in this iteration. The changes are clarifications and expansions of existing material.

**Technical quality unchanged at 4.** The F_H row-independence explanation and Guideline 1 threshold fix are correctness improvements (resolving ambiguity and inconsistency), but the underlying analysis was already correct. Table IV systematizes results that were partially present before. The Table II YX anomaly (W3) and Algorithm 1 routing ambiguity (W5) are new observations but minor.

**Significance unchanged at 4.** The cost thesis, 8x8 validation, and workload-aware placement are the same as iteration 5. The MoE parameterization (top-2 across K experts) marginally improves reproducibility but does not change the significance of the finding.

**Presentation improved from 4 to 4.5.** This is the primary dimension of improvement. The accumulated micro-fixes---F_H explanation, explicit Eq. (4), Table IV with five strategies and budget sweep, restored ablation, Kite-like cross-reference, threshold consistency, MoE parameters---collectively bring the presentation to a near-final state. The remaining presentation issues (Table II caption, Table III uncontrolled targets, BW decay integration) are polish items that do not affect comprehension.

**Overall unchanged at 4.** The paper was already at Accept after iteration 5. Iteration 6 is a polishing pass that addresses reviewer feedback items without introducing new material or new risks. The paper's argument chain (Theorem 1 -> cost paragraph -> Table III -> design guidelines) is complete and clean. The remaining weaknesses (W1-W5) are all minor and none is blocking.

## Decision

**Accept.** The iteration-6 revision is a clean polishing pass that resolves three specific items from my iteration-5 review (F_H row-independence, Kite-like prominence, MoE parameters) and adds systematic mitigation comparison (Table IV) and restored ablation (Table V). The core argument is unchanged and remains strong: phantom load forces Theta(K) unnecessary link cost in adjacent-only chiplet NoI, and express links break this cost ceiling at 2.3x fewer links, validated on realistic 8x8 internal meshes.

The remaining weaknesses are genuine but non-blocking:
- Table III target latencies are uncontrolled (directional result is robust regardless).
- ECMP/Valiant closed-form is absent (acceptable for conference; journal material).
- Table II YX anomaly at 4x4 is unexplained (verifiable; likely a minor issue).
- Differential bandwidth is disconnected from cost framing (one sentence would fix it).
- Algorithm 1 routing is unspecified (reproducibility concern, not correctness concern).

None of these weaknesses would change my Accept decision. The paper delivers a correct analytical characterization of phantom load, a complete empirical validation across routing algorithms, workloads, mesh sizes, and mitigation strategies, and actionable design guidelines for chiplet NoI architects. The cost-efficiency framing makes the contribution directly relevant to the DAC/DATE community.

**What would elevate to Strong Accept:** (1) Resolve the Table II YX anomaly with either an explanation or correction; (2) add one paragraph sketching why ECMP/Valiant cannot eliminate Theta(K) amplification; (3) specify Algorithm 1's routing algorithm explicitly; (4) add one sentence connecting BW decay to link-count savings. These are all achievable within the existing page budget and would close every remaining gap I have identified across six iterations.
