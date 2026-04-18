# Review -- Reviewer 4 (Theory/Analysis Expert), Iteration 2

## Summary
The revised paper characterizes "phantom load" in 2D mesh chiplet NoI, now supported by closed-form flow-count expressions (Theorem 1), a proven Theta(K) amplification bound for square grids, routing-algorithm independence analysis across four algorithms, and workload sensitivity across six LLM communication patterns. The greedy express-link placement algorithm has been appropriately de-emphasized from a claimed contribution to a practical tool, with the focus shifted to characterization and design space exploration.

## Response to Iteration-1 Concerns

**[W1] Greedy optimality analysis.** The authors de-emphasized greedy as a tool rather than a contribution, and moved approximation bounds to future work in the Discussion section. This is an acceptable resolution -- the paper no longer over-claims on algorithmic novelty. The honest acknowledgment that "formal approximation bounds remain future work" is preferable to a hand-wavy near-optimality claim.

**[W2] Amplification numbers are workload-dependent.** Substantially addressed. The closed-form expressions (Eqs. 2--3) now provide grid-inherent flow counts for uniform all-to-all traffic. The max amplification formula (Eq. 4) is a clean, workload-independent structural bound for the uniform case. The workload sensitivity table (Table IV) then separately characterizes how realistic workloads deviate from this baseline. This two-level analysis (structural bound + empirical workload sensitivity) is methodologically sound.

**[W3] Manhattan routing assumption.** Fully addressed. Table III now compares XY, YX, ECMP, and Valiant routing. The key finding -- that ECMP reduces imbalance but cannot eliminate it (6.1x at K=32) and Valiant doubles total load -- strengthens the "structural property" claim considerably. This was the most impactful revision.

**[W4] Greedy complexity.** Acknowledged in Discussion. Candidate pruning by distance threshold is mentioned as a practical mitigation for K=64+. Given the de-emphasis of greedy as a contribution, this is adequate.

## Remaining Strengths
1. [S1] **Closed-form theorem is genuinely useful.** Theorem 1 with F_H(r,c) = 2R(c+1)(C-c-1) is elegant and practically useful for NoI designers. The computational validation for all R,C <= 8 is thorough.
2. [S2] **Theta(K) amplification bound is the right result.** Proving that center-link amplification scales as Theta(K) for K-chiplet square grids is the key theoretical insight. This is a clean, memorable result that justifies the paper's premise.
3. [S3] **Routing independence is now convincing.** The four-algorithm comparison elevates the paper from "analysis under one routing model" to "structural characterization." The observation that Valiant eliminates imbalance but doubles total load is an important nuance.
4. [S4] **Counter-intuitive traffic-proportional result.** The 1.5x penalty of traffic-proportional vs. uniform is a strong, practically relevant finding. The explanation -- that it starves phantom-loaded links -- is clear and correct.
5. [S5] **Differential bandwidth analysis is realistic.** Testing express links at gamma=0.5 to 1.0 addresses a genuine physical concern. The result that hop reduction dominates over raw bandwidth is insightful.

## Remaining Weaknesses

1. [W1] **The proof sketch for Theorem 1 is incomplete.** The argument for horizontal flows says "the source is at row r with column <= c and the destination has column >= c+1," but the formula contains a factor of R (total rows), not a factor involving r. The proof sketch should clarify: the horizontal flow count F_H(r,c) is independent of r because, under XY routing, ALL flows crossing column boundary c|c+1 traverse the same horizontal links (horizontal movement is done first, then vertical). This independence of r is a non-obvious fact that deserves explicit statement. As written, a reader might wonder why r does not appear in F_H.

2. [W2] **Eq. 4 does not follow immediately from Eqs. 2-3.** The paper states that "each adjacent link has exactly 2 direct flows (one per direction)" and then gives alpha_max = R * ceil(C/2) * floor(C/2). But Eqs. 2-3 give F_H(r,c) = 2R(c+1)(C-c-1), which is maximized at c = floor((C-1)/2), yielding F_H_max = 2R * ceil(C/2) * floor(C/2). Dividing by 2 direct flows gives alpha_max = R * ceil(C/2) * floor(C/2). This derivation should be shown explicitly rather than stated as if obvious. More importantly: the claim "each adjacent link has exactly 2 direct flows" needs qualification -- it means 2 directed flows under all-to-all traffic, i.e., one flow (a,b) and one flow (b,a). This is true but should be stated precisely.

3. [W3] **The connection between closed-form analysis and mitigation is underdeveloped.** The closed-form results (Section III) tell us exactly which links have the highest phantom load. This should directly inform express link placement -- the optimal express links should bypass the center links with highest F_H or F_V. Does the greedy algorithm in fact discover this? If so, stating it would strengthen the theory-to-practice bridge. If not, it would be interesting to know why.

4. [W4] **Missing lower bound on mitigation.** The paper shows express links achieve 2.0-2.6x improvement, but what is the theoretical limit? For a given link budget L and grid size K, what is the minimum achievable rho_max? A multicommodity flow relaxation (LP lower bound) would provide this, and it is standard in the network design literature. Without it, we do not know if the greedy solution is capturing 50% or 95% of the achievable improvement. The comparison with fully-connected (Table VI) is a rough proxy, but fully-connected is not tight because it spreads budget across all O(K^2) pairs.

5. [W5] **Theorem 1 holds only for XY routing.** The paper proves the closed form for XY routing, then shows empirically that other algorithms do not eliminate phantom load. But no closed-form result is provided for ECMP or Valiant. For ECMP on a grid, a flow-splitting closed form should be derivable (by symmetry, ECMP splits flows equally among all minimal paths, and the number of minimal paths between two grid points is a binomial coefficient). This would strengthen the "routing-independent" claim with theory, not just empirics.

6. [W6] **The "phantom load" terminology still obscures the underlying theory.** As noted in iteration 1, this is standard multicommodity flow analysis. The Discussion section now acknowledges this ("phantom load is the chiplet-NoI manifestation of flow congestion in multicommodity flow theory"), which is good. However, the related work section still does not cite the Leighton-Rao multicommodity max-flow min-cut theorem (now in the bibliography as [14]) in the main text. A sentence in Related Work connecting to the MCF literature would strengthen positioning.

## New Strengths from Revision
- The paper is now better positioned: characterization paper with practical guidelines, not an algorithm paper.
- The routing independence analysis (Table III) is a significant addition that substantially strengthens the structural claim.
- The Discussion section is honest about limitations and future work.

## Questions for Authors
1. [Q1] Does the greedy algorithm consistently place express links across the center links identified by Theorem 1 as having maximum F_H/F_V? If so, this would close the theory-practice gap nicely.
2. [Q2] For ECMP, the expected flow on each link can be computed in closed form using binomial path-counting. Have you attempted this? It would give a second closed-form result for a different routing algorithm.
3. [Q3] The BookSim validation uses a specific chiplet microarchitecture (2x2 mesh per chiplet). How sensitive are the results to the intra-chiplet topology? If each chiplet were a 4x4 mesh with 4 border routers per edge, the link budget constraint changes -- does the phantom load characterization still hold?

## Minor Issues
- Table III: The YX routing column shows exactly 2x the XY values for all metrics. This is suspicious -- is this because YX routes vertically first, so vertical links (which are more numerous in a 2x4 grid) get loaded first? A brief explanation would help.
- The Valiant routing model should specify: is it Valiant with random intermediate node selection, or Valiant with 2-phase routing? The distinction matters for total load calculation.
- Section V, "6/7 top links target chiplet 13" -- this is a very specific claim. Does chiplet 13 correspond to the grid center? If so, state it in terms of grid position, not chiplet ID.

## Rating
- Novelty: 3/5 (up from 2.5: closed-form theorem and routing independence are genuine contributions, though the underlying theory is standard MCF)
- Technical Quality: 3.5/5 (up from 3: closed form is correct, routing analysis is thorough, but proof exposition needs tightening and LP lower bound is missing)
- Significance: 3.5/5 (up from 3: the Theta(K) scaling result and routing-independence finding are practically important for chiplet designers at K>=16)
- Presentation: 4/5 (unchanged: well-written, good tables and figures, but proof sketch needs work)
- Overall: 3.5/5 (up from 3)
- Confidence: 4/5

## Decision
**Weak Accept.** The revision substantially addresses the iteration-1 concerns. The closed-form theorem, Theta(K) bound, and routing-algorithm independence analysis collectively constitute a solid characterization paper. The remaining theoretical gaps (incomplete proof exposition, no ECMP closed form, no LP lower bound) prevent a strong accept, but the paper now provides genuine value to the chiplet design community. The counter-intuitive traffic-proportional result and the MoE vulnerability finding are practically important. The honest repositioning away from algorithmic claims is appreciated.

The key improvement path for a strong accept: (1) tighten the proof of Theorem 1 with an explicit argument for why F_H is independent of r; (2) derive the ECMP closed form to make the routing-independence claim fully theoretical; (3) compute an LP lower bound to quantify how close the greedy solution is to optimal.
