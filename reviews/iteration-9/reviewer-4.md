# Review -- Reviewer 4 (Theory/Analysis Expert), Iteration 9

## Summary

This paper characterizes "phantom load" in chiplet Networks-on-Interposer (NoI) and proposes express links with workload-aware greedy placement. The central theoretical result is that center-link amplification scales as Theta(K^{3/2}) for K-chiplet square grids under XY routing. Five LLM workloads are evaluated via BookSim at K=16 and K=32, showing 17--52% latency reduction correlated with the workload's non-locality fraction (NL%).

## Changes from Iteration 8 (what improved)

**[C1] Theta(K^{3/2}) correction (my primary concern).** The asymptotic has been corrected throughout: abstract, introduction, Eq. (3), and conclusion now consistently state Theta(K^{3/2}). I verified against Table I: K=4 gives alpha=2=4^{3/2}/4, K=16 gives 16=16^{3/2}/4, K=64 gives 128=64^{3/2}/4. All check out. This was the most critical issue from iteration 8 and it is fully resolved. The corrected exponent actually *strengthens* the paper's argument -- super-linear growth makes the case for topology intervention more compelling.

**[C2] Statistical rigor significantly improved.** The paper now reports: (a) 95% CI for the K32_N8 correlation [0.37, 1.00], (b) pooled r=0.66 (p=0.001) across all 20 configurations alongside the K32_N8 r=0.94 (p=0.016), and (c) Spearman rho=0.57 (p=0.009). This is a substantial improvement. The pooled r=0.66 is a more honest headline number, and the Spearman correlation confirms the monotonic relationship is robust. The wide CI [0.37, 1.00] for the 5-point slice is now visible to readers, which is appropriate intellectual honesty.

**[C3] Table V (mitigation comparison) now reports mean +/- std over 3 seeds.** This addresses the reproducibility concern directly.

## Strengths

**[S1] Correct and clean scaling law.** Theorem 1 with Theta(K^{3/2}) is now both correct and well-stated. The row-independence property of XY routing remains a crisp observation. Table I validates the formula comprehensively.

**[S2] Honest statistical reporting.** Presenting both the r=0.94 (5-point, K32_N8) and r=0.66 (20-point pooled) numbers side by side, with CIs, is the right approach. The paper no longer oversells the correlation.

**[S3] Routing algorithm independence and negative results.** Table III (four routing algorithms) and Table V (traffic-proportional is worse) remain strong contributions.

**[S4] Compact and focused presentation.** The paper reads well, with a clear flow from analysis to architecture to evaluation.

## Weaknesses

**[W1] NL% still lacks a formal mathematical definition (MODERATE, persists from iter 8).** The paper defines NL% informally as "the share of total traffic between non-adjacent chiplet pairs" but does not provide a formula. Is it volume-weighted or flow-count-weighted? Directed or undirected? Computed pre- or post-routing? The metric is topology-dependent (Manhattan distance >= 2 changes with layout), which limits cross-layout generalizability. A one-line formula (e.g., NL% = sum_{d(i,j)>=2} T[i,j] / sum_{all i,j} T[i,j]) and a note on its topology-dependence would resolve this.

**[W2] Algorithm 1 has no approximation guarantee (MODERATE, persists from iter 8).** The greedy algorithm is reasonable engineering but the paper does not state the hardness of the underlying optimization problem, acknowledge the lack of approximation ratio, or justify the traffic-proportional fallback beyond "100% budget utilization." The complexity claim O(L * |C| * K^2 log K) still needs clarification on whether Dijkstra runs on the K-node chiplet graph or the full K*N^2 mesh.

**[W3] Table III anomalies remain unexplained (MINOR).** XY gives Max alpha=111 and YX gives 223 for the "4x4" grid. For a square grid these should be symmetric. The discrepancy with Table I values (alpha_max=16 for 4x4) is also unexplained -- Table III appears to measure a different quantity (possibly including per-chiplet mesh), but this is not stated.

**[W4] Limited workload diversity (MINOR).** Five workloads with NL% clustered in two groups (42--49% and 88--90%) leave a gap in the 50--85% range. The Spearman rho=0.57 is modest, and a few workloads in the gap (e.g., ring all-reduce, nearest-neighbor stencil) would strengthen the predictive claim.

## Questions

**[Q1]** Can you add a one-line formula for NL%? Specifically: is it sum of traffic volume for pairs with Manhattan distance >= 2, divided by total traffic? Is it computed on the demand matrix (pre-routing)?

**[Q2]** For Algorithm 1, is the Dijkstra routing performed on the K-node chiplet-level graph or the full K*N^2 node mesh? At K=32, N=8 (2048 nodes), this materially affects runtime.

**[Q3]** Why do XY and YX show different Max alpha in Table III for a square grid? Is "4x4" the chiplet grid or the per-chiplet mesh? How do the Table III values relate to Table I's analytical alpha_max?

## Rating

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Novelty | 3.0/5 | Express links in NoC predate this work (Express VC, 2007). The chiplet NoI application with cost awareness and NL% predictor is new but incremental. |
| Technical Quality | 3.5/5 | The Theta(K^{3/2}) scaling law is now correct. Statistical reporting is significantly improved. Algorithm 1 still lacks formal grounding. Table III anomalies persist. |
| Significance | 3.5/5 | Phantom load is a real scaling problem. The NL% predictor is practically useful. Results are actionable for architects. |
| Presentation | 3.5/5 | Clean and focused. Statistical claims are now properly qualified. NL% definition and Table III notation need minor fixes. |
| Overall | 3.5/5 | Solid improvement over iteration 8. The corrected scaling law and honest statistical reporting address the two most critical concerns. Remaining issues are moderate-to-minor. |
| Confidence | 5/5 | I verified the corrected asymptotic, checked all table values, and validated the statistical claims. |

## Decision

**Borderline Accept.** The paper has materially improved since iteration 8. The Theta(K^{3/2}) correction -- my primary concern -- is fully resolved, and the corrected exponent strengthens the paper's narrative. The statistical analysis is now honest and properly qualified with CIs and rank correlation. These were the two issues that warranted rejection in iteration 8, and both are addressed.

Remaining concerns are moderate: NL% needs a formal definition (one line of math), Algorithm 1 needs a brief acknowledgment of its heuristic nature, and Table III notation should be clarified. None of these are blocking for a paper whose primary contribution is an analytical scaling law (now correct) validated by cycle-accurate simulation.

**For final acceptance**, I ask the authors to:
1. **(Strongly recommended)** Add a formal NL% formula and note its topology-dependence.
2. **(Recommended)** Add one sentence acknowledging Algorithm 1 provides no approximation guarantee.
3. **(Recommended)** Clarify Table III grid labels and their relationship to Table I values.
