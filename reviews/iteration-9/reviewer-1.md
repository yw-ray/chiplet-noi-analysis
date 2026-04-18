# Review -- Reviewer 1 (Architecture Expert), Iteration 9

## Summary

This paper identifies phantom load in chiplet NoI and proposes express links with workload-aware greedy placement. Iteration 9 corrects the scaling proof from Theta(K) to Theta(K^{3/2}), adds confidence intervals and pooled vs. slice correlation analysis, and reports mean+/-std over 3 seeds in Table 5 (mitigation comparison).

## Changes from Iteration 8

**Fixed:**
- **[W-prev: Proof error]** The Theta(K) claim from iteration 8 is corrected to Theta(K^{3/2}). Equation (3) now reads alpha_max = R * ceil(C/2) * floor(C/2) = Theta(K^{3/2}) for square grids. This is correct: for an n x n grid (K = n^2), center flow count is O(n * n^2) = O(n^3) = O(K^{3/2}), and alpha divides by 2 (constant). The proof is now sound. Table II values (2, 8, 16, 64, 128) are consistent with the formula.
- **[W-prev: Statistical rigor]** The paper now reports 95% CI for the headline correlation ([0.37, 1.00] at K32_N8), pooled correlation r=0.66 (p=0.001, CI [0.31, 0.85]), and Spearman rho=0.57 (p=0.009). This is a meaningful improvement -- the wide CI at K32_N8 honestly exposes the small-sample limitation.
- **[W-prev: Seed variance]** Table 5 now shows mean+/-std over 3 seeds. The variance is small (e.g., 14.3+/-0.4 for uniform at K=16), confirming simulation stability.

**Partially addressed:**
- **[W1: Cost vs. latency framing]** The abstract and text now mention "same link cost as adjacent-only baselines," which is progress. However, the iso-cost comparison is only at the maximum budget point (Nx). The paper still does not report the inverse metric: for a fixed latency target, how many fewer links does express require? Both metrics are needed.
- **[W5: Correlation gap]** The pooled r=0.66 and honest wide CI partially address the concern about clustering. However, no new workloads in the 55-80% NL% gap were added. The Spearman rho=0.57 does confirm monotonicity, which is sufficient for the practical recommendation (NL% > 40% warrants express), even if the linear fit is imprecise.

**Not addressed:**
- **[W2: Physical latency model]** No sensitivity analysis on express link latency scaling. The 2d-cycle model remains unvalidated.
- **[W3: Missing comparisons]** Simba, NVSwitch, MCM-GPU still absent from related work. The paper does not discuss switch-based alternatives.
- **[W4: Synthetic workloads]** All five workloads remain analytically generated. No traced workloads or skew sensitivity analysis added.
- **[W-detail: Deadlock freedom]** Dijkstra routing on express topology still lacks deadlock analysis.
- **[W-detail: Table II/III discrepancy]** The mismatch between closed-form predictions and workload-based alpha values remains unexplained.

## Strengths

**[S1] Corrected analytical framework.** The Theta(K^{3/2}) result is now correct and stronger than the previous Theta(K) claim. Super-linear growth makes the cost argument more compelling: at K=64, alpha_max=128 is a genuinely alarming number for architects.

**[S2] Statistical transparency.** Reporting the wide CI [0.37, 1.00] alongside the headline r=0.94 is honest and builds credibility. The pooled analysis (r=0.66, Spearman 0.57) with explanation of why it is weaker (budget-limited small configurations) shows mature understanding of the data.

**[S3] Unchanged strengths from iteration 8.** Comprehensive sweep design, honest crossover-budget reporting, strong ablation results all remain.

## Weaknesses

**[W1] Physical model unvalidated (carried from iter 8).** The 2d-cycle latency model for distance-d express links has no physical design reference or sensitivity analysis. This is the single largest technical gap. A table showing results at 1.5x and 2x the linear latency estimate would take minimal effort and would either confirm robustness or reveal a real limitation.

**[W2] No switch-based topology comparison (carried).** The architecture community's natural counter to "mesh has phantom load" is "don't use mesh." NVSwitch-style fat-tree or crossbar topologies avoid multi-hop entirely. Without discussing when mesh+express is preferred over switch-based, the paper's practical scope is unclear.

**[W3] Synthetic-only workloads (carried).** MoE expert dispatch assumes uniform top-2 routing, but real MoE shows heavy expert skew. Even a simple sensitivity test (varying top-k or skewing expert popularity) would strengthen the claim.

**[W4] Correlation CI is very wide.** The 95% CI [0.37, 1.00] at K32_N8 means the true correlation could be as low as 0.37 -- barely moderate. With only 5 points, this is unavoidable, but the paper should temper the "r=0.94" headline by noting the CI width more prominently (currently buried in the text).

## Questions

1. For the Theta(K^{3/2}) result: the formula alpha_max = R * ceil(C/2) * floor(C/2) gives 4*4*4=64 for the 4x8 grid, matching Table II. But for a non-square grid like 2x4, it gives 2*2*1=4, while Table II shows 8. Which dimension is used for the formula in non-square grids? Clarify whether R refers to rows or the shorter dimension.

2. The pooled r=0.66 vs. slice r=0.94 difference is attributed to budget limitations at small N. Could you verify this by plotting the residuals? If small-N points systematically fall below the regression line, this confirms the explanation.

3. At 3 seeds, the standard deviations in Table 5 are reassuringly small. Did you observe any outlier seeds in the BookSim runs, or is 3 sufficient for all configurations?

## Rating

- Novelty: 3/5
- Technical Quality: 3.5/5 (up from 3.5 -- proof correction is net-neutral since the new result is stronger but the error existed)
- Significance: 3.5/5
- Presentation: 4/5
- Overall: 3.5/5
- Confidence: 4/5

## Decision

**Borderline (unchanged).** The proof correction and statistical improvements are necessary fixes that restore confidence in the analytical claims. The Theta(K^{3/2}) result is actually stronger motivation than the previous Theta(K). However, the core weaknesses from iteration 8 -- unvalidated physical model, missing switch-based comparison, synthetic-only workloads -- remain unaddressed. These are the gaps that separate this paper from the ISCA/MICRO accept bar. For the next iteration, I would prioritize: (1) a latency-model sensitivity table (small effort, high impact on reviewer confidence), and (2) one paragraph discussing when switch-based topologies are preferable (no new experiments needed, just honest scoping). The paper remains publishable at a focused venue (NOCS, DATE) and is approaching but not yet at top-venue level.
