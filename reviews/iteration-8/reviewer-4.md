# Review -- Reviewer 4 (Theory/Analysis Expert), Iteration 8

## Summary

This paper identifies "phantom load" -- the amplification of link traffic due to multi-hop routing in chiplet Networks-on-Interposer (NoI) -- and proves that center-link amplification scales as Theta(K) for K-chiplet square grids under XY routing with uniform all-to-all traffic. The paper proposes express links (direct non-adjacent connections) with a greedy workload-aware placement algorithm, and evaluates via BookSim cycle-accurate simulation across five LLM workloads at K=16 and K=32. The main empirical finding is that express saving correlates with a workload's non-locality fraction (NL%) at r=0.94, achieving 52% latency reduction for MoE/all-to-all workloads at K=32, N=8.

Compared to iteration 7, the paper has been significantly restructured: the design guidelines section has been removed (consistent with the project's paper writing principles), several tables have been consolidated, and the paper is now more compact and focused. The core analytical content and claims are preserved but the presentation has changed materially. This review is therefore a fresh assessment of the restructured manuscript rather than an incremental delta review.

## Strengths

**[S1] The Theta(K) closed-form result is clean and correct.** Theorem 1 (Eqs. 1--3) is well-stated. The derivation for F_H(c) under XY routing is elementary combinatorics -- counting source-destination pairs crossing a column boundary -- and the row-independence property (XY routing performs horizontal movement at source row) is a crisp observation that makes the counting tractable. I verified the formula against Table I entries: 4x4 gives alpha_max = 4*2*2 = 16, 8x8 gives 8*4*4 = 128. Both check out. The Theta(K) scaling for square grids (R=C=sqrt(K)) follows directly from alpha_max = R * ceil(C/2) * floor(C/2) = sqrt(K) * K/4 = O(K^{3/2}/4)... wait. Let me re-derive this carefully below (see W1).

**[S2] Routing algorithm independence argument.** Table III showing four routing algorithms is a strong addition. The paper correctly observes that ECMP reduces imbalance but cannot eliminate Theta(K) amplification, and Valiant doubles total load. This is the right set of algorithms to consider for this argument.

**[S3] The NL% metric is practically useful.** Defining a single scalar predictor for express link benefit is good engineering. The idea that architects can compute NL% from a static traffic analysis without cycle-accurate simulation is the kind of practical contribution that matters for adoption.

**[S4] Negative result on traffic-proportional allocation.** Table IV showing that traffic-proportional allocation is 1.5-1.6x *worse* than uniform is a genuinely useful finding that challenges the naive intuition. The explanation -- that it starves phantom-loaded links carrying no direct traffic -- is correct and insightful.

**[S5] Compact presentation.** Removing the design guidelines section from iteration 7 was the right call. The paper is tighter and lets the data speak.

## Weaknesses

**[W1] The Theta(K) claim has an error in the exponent (MAJOR).** The paper claims alpha_max = Theta(K) for square grids. Let me check: for a square grid, R = C = sqrt(K). Then alpha_max = R * ceil(C/2) * floor(C/2). For even C = sqrt(K): alpha_max = sqrt(K) * (sqrt(K)/2)^2 = sqrt(K) * K/4 = K^{3/2}/4. This is Theta(K^{3/2}), not Theta(K).

However, looking at Table I more carefully: K=4 (2x2) gives alpha=2, K=16 (4x4) gives alpha=16, K=64 (8x8) gives alpha=128. The ratio alpha/K is: 0.5, 1.0, 2.0 -- this is NOT constant, confirming the scaling is super-linear in K. In fact: 2 = 4^{3/2}/4 = 2 (check), 16 = 16^{3/2}/4 = 64/4 = 16 (check), 128 = 64^{3/2}/4 = 512/4 = 128 (check). So the actual scaling is K^{3/2}/4, which is Theta(K^{3/2}).

Wait -- I need to re-examine. The formula as written in Eq. (3) is alpha_max = R * ceil(C/2) * floor(C/2). For 4x4: 4*2*2=16. But the denominator (direct flows per link) is 2, so alpha = F_H / 2 = 16. The paper writes this as Theta(K) -- but K=16 and alpha=16 is coincidental for 4x4. At K=64, alpha=128=2K, which already breaks the Theta(K) claim.

Actually, let me re-read the formula. The paper states: "Since each link has 2 direct flows, the center link amplification is: alpha_max = R * ceil(C/2) * floor(C/2) = Theta(K) for square grids."

For square grids with R=C=n, K=n^2: alpha_max = n * (n/2)^2 = n^3/4 = K^{3/2}/4. This is definitively Theta(K^{3/2}), not Theta(K).

BUT: I now realize Table I also includes non-square grids (2x4, 4x8). For those: 2x4 (K=8): alpha=8, K=8 so alpha/K=1. 4x8 (K=32): alpha=64, K=32 so alpha/K=2. These are also growing faster than K.

For the 2xC family (R=2, C=K/2): alpha_max = 2 * (K/4)^2 = K^2/8, which is Theta(K^2).

**The Theta(K) claim is incorrect.** The actual scaling depends on the aspect ratio. For square grids it is Theta(K^{3/2}); for 2xC strips it is Theta(K^2). The paper should state the correct asymptotic: alpha_max = Theta(R * C^2) = Theta(K * C) or, for square grids, Theta(K^{3/2}).

**CORRECTION/RECONSIDERATION**: Let me re-check with the actual numbers more carefully. For 4x4 grid: F_H(center) = 2*4*2*2 = 32 flows. Direct flows per link = 2 (bidirectional). alpha = 32/2 = 16. K=16. So alpha=K here. For 8x8 grid: F_H(center) = 2*8*4*4 = 256 flows. alpha = 256/2 = 128. K=64. So alpha=2K. For 2x2 grid: F_H(center) = 2*2*1*1 = 4. alpha = 4/2 = 2. K=4. So alpha=K/2.

The sequence is: K=4, alpha=2 (K/2); K=16, alpha=16 (K); K=64, alpha=128 (2K). The ratio alpha/K = {0.5, 1.0, 2.0} which grows as sqrt(K)/2. So alpha = K*sqrt(K)/4 = K^{3/2}/4... no wait, let me just compute directly.

alpha_max = R * floor(C/2) * ceil(C/2) (note: the paper's formula divides F_H by 2 for direct flows). For square n x n: alpha_max = n * (n/2)^2 = n^3/4. With K=n^2, n=K^{1/2}, so alpha_max = K^{3/2}/4.

K=4: n=2, alpha = 8/4 = 2. Check.
K=16: n=4, alpha = 64/4 = 16. Check.
K=64: n=8, alpha = 512/4 = 128. Check.

So it IS K^{3/2}/4, which is Theta(K^{3/2}), NOT Theta(K). The paper's claim of Theta(K) is wrong.

This is a significant analytical error in the paper's central theoretical contribution. While the numerical values in Table I are correct, the asymptotic characterization is incorrect. The correct statement should be: alpha_max = Theta(K^{3/2}) for square grids, or more precisely, Theta(R * C^2) for general R x C grids.

**[W2] The r=0.94 correlation is based on insufficient data (MODERATE).** The paper computes Pearson r=0.94 from 20 data points (5 workloads x 4 configurations). But:

(a) These are not 20 independent observations. The same 5 workloads appear across all 4 configurations, creating strong within-workload correlation. The effective degrees of freedom are much lower than 18.

(b) With 5 distinct NL% values (42, 49, 88, 89, 90), the correlation is effectively driven by a 3-point fit: one cluster at NL~42-49% (low saving) and one at NL~88-90% (high saving). Any monotonic relationship would produce high r with such bimodal grouping.

(c) The paper reports r=0.94 "at K=32, N=8" (line 374 in the manuscript), which is only 5 data points -- far too few for a meaningful Pearson correlation. With 5 points, r=0.94 has a p-value of ~0.017 under H0, which is not overwhelmingly significant, and with the clustering issue above, the effective significance is even lower.

(d) There is no confidence interval or bootstrap analysis. A rigorous treatment would either (i) report the confidence interval for r, (ii) use a rank correlation (Spearman/Kendall) that is more appropriate for small N, or (iii) evaluate on a held-out set of workloads.

The r=0.94 claim, while likely directionally correct (high NL% does correlate with express benefit), is overstated given the statistical evidence.

**[W3] NL% definition lacks formal rigor and edge-case analysis (MODERATE).** The paper defines NL% as "the share of total traffic between non-adjacent chiplet pairs" but does not provide a formal mathematical definition. Specifically:

(a) Is NL% computed on directed or undirected traffic? For asymmetric workloads (e.g., pipeline-parallel), this matters.

(b) Does NL% weight by traffic volume or count flows? The text says "share of traffic," implying volume-weighted, but this is not explicit.

(c) The metric is topology-dependent: "non-adjacent" means Manhattan distance >= 2, which depends on the chiplet layout. If the same set of chiplets were arranged in a 4x8 grid vs. a 2x16 strip, NL% would change even though the logical communication pattern is identical. This limits the generalizability of the r=0.94 result across different physical layouts.

(d) Is NL% defined before or after routing? Pre-routing (based on source-destination pairs) is the natural choice for a "simulation-free predictor," but the paper should state this explicitly.

**[W4] Algorithm 1 has no approximation guarantee (MODERATE).** The greedy algorithm is standard but the paper claims it "achieves 100% budget utilization" without any approximation ratio relative to the optimal placement. Key concerns:

(a) The optimization problem (minimize rho_max subject to link budget) is likely NP-hard (it resembles capacitated network design), but the paper does not state this or cite any hardness result.

(b) Greedy congestion minimization is a well-studied problem in network design. The paper should at minimum acknowledge that no approximation guarantee is provided, and ideally relate the problem to known results (e.g., congestion minimization in multi-commodity flow).

(c) The "traffic-proportional fallback" for the greedy plateau is ad hoc. When the greedy phase terminates (no single link addition improves rho_max), the remaining budget is distributed proportionally to traffic demand. What is the justification for this particular fallback? Has the author compared against other fallback strategies (e.g., uniform distribution of remaining budget, or second-order greedy on a different objective)?

(d) The complexity claim O(L * |C| * K^2 log K) needs unpacking. What is the K^2 log K term? If |C| = O(K^2) and each Dijkstra call is O(K^2 log K) (on a K-node graph), then each greedy iteration is O(K^2 * K^2 log K) = O(K^4 log K), and L iterations gives O(L * K^4 log K). The paper writes O(L * |C| * K^2 log K), which with |C|=O(K^2) gives the same thing. But the Dijkstra is on the chiplet-level graph (K nodes), not the full mesh (K*N^2 nodes), correct? This should be clarified. If routing is on the full mesh, the complexity is much higher.

**[W5] Table III routing results have unexplained anomalies (MINOR but persistent from iteration 7).** For the 4x4 grid, XY gives Max alpha = 111, while YX gives 223 -- a 2x difference. For a square grid, XY and YX should produce symmetric load distributions (one is the 90-degree rotation of the other). The paper claims "both produce the same imbalance (8.2x)" but the Max alpha values differ by 2x. This needs explanation. If the grid is square (4x4), Max alpha should be identical under XY and YX by symmetry. If the "4x4" in Table III refers to the per-chiplet mesh size rather than the chiplet grid, the notation is confusing.

Also: Table III shows Max alpha = 111 for XY at 4x4, but the analytical formula gives alpha_max = 16 for a 4x4 grid (Table I). This 7x discrepancy suggests Table III is measuring something different from Table I -- likely including per-chiplet mesh traffic or using a different normalization. The paper does not explain this discrepancy.

**[W6] Generalizability beyond 2D grids is unaddressed (MINOR).** The entire analysis assumes a 2D rectangular grid layout, which is standard for current interposers. But emerging packaging technologies (2.5D with bridges, 3D stacking, hexagonal layouts) may not conform to this model. The paper should briefly discuss whether the Theta(K) (or rather Theta(K^{3/2})) result generalizes to other topologies, or explicitly state the grid assumption as a limitation.

**[W7] The physical overhead analysis (Table VII) uses rough estimates without uncertainty (MINOR).** The paper estimates wire area, power, and latency for express links based on "CoWoS-class technology parameters." These are point estimates with no error bars or sensitivity analysis. The claim of "net area saving despite longer wires" depends on the PHY area assumption. If PHY modules are smaller than assumed, the net saving could reverse. A brief sensitivity discussion would strengthen this claim.

## Questions for Authors

**[Q1]** Regarding W1: Can you confirm the correct asymptotic scaling? For a square n x n grid (K = n^2), alpha_max = n^3/4 by your own formula, which is Theta(K^{3/2}), not Theta(K). Table I confirms this: the alpha/K ratio grows as {0.5, 1.0, 2.0} across K = {4, 16, 64}. Is the Theta(K) claim in Eq. (3) and the abstract a typo?

**[Q2]** The paper reports Pearson r=0.94 "at K=32, N=8" (5 data points). Have you computed the correlation across all 20 points pooled? What is the 95% confidence interval? Have you tried Spearman rank correlation, which is more robust to the small sample size?

**[Q3]** For Algorithm 1: what happens when you use a different fallback strategy (e.g., uniform distribution) instead of traffic-proportional for the remaining budget after greedy plateau? How sensitive is the final rho_max to this choice?

**[Q4]** Table III shows Max alpha = 111 for XY at "4x4" but Table I shows alpha_max = 16 for a 4x4 chiplet grid. What accounts for this 7x discrepancy? Are these measuring different quantities? What do the grid labels in Table III refer to -- chiplet grid or per-chiplet mesh?

**[Q5]** The NL% metric depends on the physical layout (which pairs are "adjacent"). If architects are considering alternative chiplet arrangements, NL% changes. How should NL% be used when the layout itself is a design variable?

**[Q6]** Is the Dijkstra routing in Algorithm 1 performed on the K-node chiplet graph or the full K*N^2-node mesh? This significantly affects the practical runtime for K=64, N=8 (32,768 nodes).

## Missing References

1. **Oblivious routing and congestion minimization** -- The paper discusses routing algorithm independence but does not cite the foundational work on oblivious routing (Racke 2008, "Optimal Hierarchical Decompositions for Congestion Minimization in Networks") or Valiant-Benes routing analysis. These provide theoretical context for why phantom load is unavoidable.

2. **Network design under budget constraints** -- The greedy placement problem is related to capacitated network design. The paper should cite relevant approximation algorithms (e.g., Garg et al., "Approximate Max-Flow Min-(Multi)Cut Theorems"; Chekuri et al., "Multicommodity demand flow in a tree and packing integer programs").

3. **Recent chiplet NoI work** -- SIMPLE (ISCA 2023) and IntelliNoI (MICRO 2023) are relevant recent references for chiplet network optimization that should be discussed in related work.

4. **Concentration inequality for traffic analysis** -- The workload sensitivity analysis would benefit from citing traffic modeling literature (e.g., Towles and Dally, "Worst-case Traffic for Oblivious Routing Functions," DAC 2002).

## Detailed Comments

### On the Theta(K) Error (W1)

This is the most critical issue. The paper's central analytical contribution is the scaling law, and it is stated incorrectly throughout: in the abstract ("phantom load amplification grows as Theta(K)"), in the introduction ("center links carry Theta(K) times more traffic"), and in Eq. (3). The correct asymptotic is Theta(K^{3/2}) for square grids.

To be fair, the numerical values in Table I are all correct, and the qualitative message (amplification grows super-linearly with chiplet count) is unchanged. The fix is straightforward: replace Theta(K) with Theta(K^{3/2}) everywhere. But for a paper whose primary theoretical contribution is a closed-form scaling law, getting the asymptotic wrong is a significant credibility issue.

One possibility: the authors may be using Theta(K) loosely to mean "grows with K" rather than "grows linearly with K." If so, this is imprecise notation that will mislead theoretically-minded readers.

### On the Correlation Analysis (W2)

The r=0.94 claim appears prominently in the abstract, introduction, and conclusion. For a paper at a top venue, a headline correlation coefficient should be supported by proper statistical analysis. I recommend:

1. Report the 95% confidence interval (bootstrap or Fisher z-transform).
2. Use Spearman rank correlation alongside Pearson.
3. Acknowledge that with effectively 5 distinct NL% levels, the correlation is driven by between-group variance, not within-group precision.
4. Ideally, add 2-3 more workloads (e.g., ring all-reduce, nearest-neighbor stencil, random-sparse) to increase the effective sample size and test the predictive power of NL% on held-out patterns.

### On Algorithm 1 (W4)

The algorithm is sensible engineering but lacks theoretical grounding. At minimum:

1. State that the optimization problem is (presumably) NP-hard.
2. Note that greedy provides no worst-case approximation guarantee for congestion minimization.
3. Justify the traffic-proportional fallback beyond "it achieves 100% budget utilization." Every strategy achieves 100% utilization if you add links until the budget is exhausted -- what makes traffic-proportional the right choice?

### On the Restructured Presentation

The removal of the design guidelines section is a positive change. The paper flows better as: analysis (Section III) -> architecture (Section IV) -> evaluation (Section V). The workload sensitivity subsection in Section III is well-placed, bridging theory and evaluation.

However, the conclusion is too compressed. It reads as a summary list rather than a forward-looking discussion. One sentence about limitations (grid assumption, small workload set) and one about future work (3D integration, automated co-design with floorplanning) would strengthen the ending.

### Minor Issues

- Line 178 (Table III): The "Imbalance" column heading is not defined. Is this max/avg, max/min, or coefficient of variation?
- The caption of Fig. 3 says "best express saving" -- best over what? Budget sweep? This should be explicit.
- Table V (ablation) uses "Avg. 3 Seeds" but the main results (Table VI) do not mention seed averaging. Are the main results single-seed?
- The physical overhead analysis claims 10mm wire for adjacent links. This assumes chiplets are 10mm apart. For smaller chiplets or tighter pitch, this number changes. The assumption should be stated.

## Rating

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Novelty | 3.0/5 | Express links in NoC are not new (Express VC, 2007). The contribution is applying them to chiplet NoI with cost awareness. The phantom load characterization is the novel theoretical part, but the Theta(K) error undermines it. |
| Technical Quality | 3.0/5 | The analytical formula is correct numerically but the asymptotic is wrong. The correlation analysis is statistically underpowered. The algorithm has no theoretical guarantees. The BookSim evaluation is solid but limited to 5 workloads. |
| Significance | 3.5/5 | The phantom load problem is real and important for chiplet scaling. The NL% predictor is practically useful. The results are actionable for architects. |
| Presentation | 3.5/5 | Compact and focused after restructuring. Good figures. But the Theta(K) error propagates through abstract, intro, and conclusion. Table III notation issues. |
| Overall | 3.0/5 | The paper identifies a real problem and proposes a reasonable solution, but the theoretical contribution -- which is presented as the primary novelty -- has an incorrect asymptotic claim, and the correlation claim is overstated. |
| Confidence | 5/5 | I verified the asymptotic scaling algebraically and against the paper's own Table I. The Theta(K) vs Theta(K^{3/2}) discrepancy is unambiguous. |

## Decision

**Weak Reject.** The paper addresses a timely and important problem (phantom load in chiplet NoI) and the experimental methodology is sound. However, for a paper whose central theoretical contribution is a closed-form scaling law, the incorrect asymptotic claim (Theta(K) stated, Theta(K^{3/2}) actual) is a serious issue. This error appears in the abstract, introduction, theorem statement, and conclusion -- it is not a typo but a systematic mischaracterization of the paper's own result.

Additionally, the r=0.94 correlation, which is the other headline claim, is based on effectively 5 data points with bimodal clustering. This does not meet the statistical rigor expected at ISCA.

**Path to acceptance:**
1. **Fix the asymptotic (mandatory):** Replace Theta(K) with Theta(K^{3/2}) throughout, or if the authors intend a different normalization (e.g., per-row amplification), explain it clearly and adjust the theorem statement.
2. **Strengthen correlation analysis (strongly recommended):** Add confidence intervals, use rank correlation, and ideally add more workloads.
3. **Address Algorithm 1 theoretical grounding (recommended):** State complexity class, acknowledge lack of approximation guarantee, justify fallback strategy.
4. **Resolve Table III anomalies (recommended):** Explain the XY vs YX asymmetry for square grids and the discrepancy with Table I values.

If the Theta(K) error is corrected (which strengthens the paper's claim -- K^{3/2} is worse than K, making the case for express links even stronger), and the correlation analysis is properly qualified, this paper would be a candidate for acceptance.
