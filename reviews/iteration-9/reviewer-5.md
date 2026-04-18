# Review -- Reviewer 5 (Skeptic), Iteration 9

## Summary

This paper analyzes "phantom load" in chiplet 2D grid networks, proves center-link amplification scales as Theta(K^{3/2}), and proposes express links with workload-aware greedy placement. BookSim simulation of five LLM workloads shows 17--52% latency reduction at K=32, N=8, correlated with non-locality fraction (NL%). The iteration 9 revision addresses the proof error (Theta(K) -> Theta(K^{3/2})), adds statistical rigor to the correlation claims, and reports mean+/-std in Table 5.

## Changes from Iteration 8

**Theta(K) -> Theta(K^{3/2}).** The corrected proof now matches the formula alpha_max = R * ceil(C/2) * floor(C/2), which for square grids (R=C=sqrt(K)) gives sqrt(K) * (K/4) = Theta(K^{3/2}). This is a genuine fix that strengthens the analytical contribution -- the amplification grows faster than linear, making the problem more severe than previously claimed.

**Statistical rigor on r.** The paper now reports: (a) 95% CI for r=0.94 at K32N8: [0.37, 1.00]; (b) pooled r=0.66 (p=0.001) across all 20 configurations; (c) Spearman rho=0.57 (p=0.009). This is a significant improvement. The wide CI [0.37, 1.00] honestly reveals that r=0.94 is imprecise on 5 points. The pooled r=0.66 is far more statistically grounded (n=20) and the Spearman confirms monotonicity.

**Table 5 mean+/-std over 3 seeds.** Table 5 (mitigation comparison) now shows variance. This partially addresses my iter-8 W6. However, the main results table (Table IV) still reports single values without error bars, which is the table that matters most.

## Strengths

**[S1] The Theta(K^{3/2}) result is now correct and stronger.** Super-linear growth is a more compelling motivation for topology intervention than linear growth. The proof, formula, and Table I validation are consistent.

**[S2] Statistical honesty on the correlation.** Disclosing r=0.66 pooled alongside r=0.94 (K32N8 only) is the right approach. The wide CI [0.37, 1.00] effectively tells the reader "5 points is insufficient for precision, but the trend is real." The Spearman addition guards against outlier-driven Pearson inflation.

**[S3] Prior strengths carry forward.** The phantom load analysis, ablation (Table VI showing random express is harmful), and traffic-proportional-is-worse-than-uniform result remain solid contributions.

## Weaknesses

**[W1] Workload scoping: improved but still incomplete.**

The author argues that pipeline/ring were excluded entirely (not selectively reported) because the paper scopes to NL>=42% workloads. I accept that scoping is a legitimate methodological choice -- papers routinely define their operating regime. The key question is whether the scoping is disclosed and whether it hides important information.

The paper states "five LLM communication patterns" without mentioning that two standard patterns (ring allreduce, pipeline parallel) were evaluated but excluded because express links are harmful/neutral for them. This is no longer "cherry-picking" in the strong sense (selectively reporting favorable subsets as if they were the whole), but it is still an incomplete disclosure. Ring allreduce is the dominant collective in distributed training. Omitting it without a sentence explaining why creates a false impression of completeness. One sentence in Section V.A ("We exclude ring allreduce and pipeline parallel (NL<15%) as these fall outside our NL>=42% scope; express links provide no benefit for such local patterns") would resolve this entirely.

**[W2] "Same link cost" framing persists in the abstract (line 29).**

The abstract says "at the same link cost as adjacent-only baselines." Express links at distance d have d-times the wire length, area, and power. "Same link count" != "same link cost." Section V.E acknowledges this with specific numbers, but the abstract misleads. At K=32 with MoE, the paper uses 129 express links -- the physical overhead section estimates costs for only 10 express links at average distance 2.5, substantially understating the actual overhead for the configuration where express links are most beneficial.

**[W3] Physical overhead mismatch remains unaddressed.**

The physical overhead analysis (Section V.E) uses "10 express links at average distance 2.5" but the MoE workload at K=32 uses 129 express links. The text then pivots to a different argument ("72 total links including ~19 express instead of 168 adjacent-only"), but 19 express links is also far below 129. These numbers appear to come from different configurations without clearly stating which. The reader cannot reconcile the overhead estimate with the actual express link counts in Table IV.

**[W4] Algorithm 1 traffic-proportional fallback contradiction.**

The greedy algorithm uses traffic-proportional allocation as its fallback (line 248, Section IV.B). But Table 5 shows traffic-proportional is 1.5--2.3x worse than uniform. The paper demonstrates that traffic-proportional allocation is a bad strategy, then uses it as the fallback for its proposed algorithm. This internal contradiction remains from iter-8 and is not addressed. If traffic-proportional is bad for adjacent links, why is it acceptable for residual budget allocation?

**[W5] Table IV (main results) still lacks error bars.**

Table 5 now has mean+/-std, but Table IV -- the paper's central result table showing 52% savings -- reports single values. The 52.1% and 52.7% numbers are the headline claims of the paper. Without variance, the reader cannot distinguish 52+/-1% from 52+/-15%. This is the most important table to have error bars, and it is the one that still lacks them.

## Questions

**Q1.** Can you add one sentence to Section V.A disclosing the exclusion of ring allreduce and pipeline parallel, with their NL% values and the rationale?

**Q2.** In Section V.E, which configuration do the "10 express links" and "72 total links including ~19 express" correspond to? Can you provide the physical overhead for the K=32, N=8 MoE configuration (129 express links)?

**Q3.** Why does Table IV not report mean+/-std when Table 5 does? Are the Table IV values single-seed or multi-seed averages?

**Q4.** If traffic-proportional allocation is demonstrably worse than uniform (Table 5), why is it used as the fallback in Algorithm 1? What would the results look like with uniform fallback instead?

## Rating

| Metric | Score | Comment |
|--------|-------|---------|
| Novelty | 3.0/5 | Phantom load analysis is novel for chiplet NoI; express links less so |
| Technical Quality | 3.0/5 | Proof corrected, stats added; but overhead mismatch, no error bars on Table IV, fallback contradiction |
| Significance | 3.0/5 | Phantom load insight is useful; practical impact unclear without realistic cost accounting |
| Presentation | 3.5/5 | Well-written; abstract "same link cost" and overhead mismatch are presentation problems |
| Overall | 3.0/5 | |
| Confidence | 4.0/5 | |

## Decision

**Borderline Reject (upgraded from Weak Reject).**

The paper has made meaningful progress on the statistical rigor issues I raised in iteration 8. The corrected Theta(K^{3/2}) proof is stronger, the pooled r=0.66 with CI is honest, and the Spearman addition is appropriate. The workload scoping argument is reasonable in principle, though I would like to see explicit disclosure of the excluded workloads.

The remaining issues are: (1) the "same link cost" language in the abstract is still misleading; (2) the physical overhead section's numbers do not correspond to the actual express link counts in the main results; (3) the traffic-proportional fallback in Algorithm 1 contradicts the paper's own evidence; and (4) Table IV, the most important table, still lacks error bars while the less critical Table 5 now has them.

Issues (1) and (4) are straightforward fixes. Issue (2) requires recalculating overhead for the actual MoE configuration, which may weaken the cost argument. Issue (3) is a methodological concern that could affect the reported savings numbers.

If these four issues are resolved in the next revision -- particularly if the realistic physical overhead at 129 express links still shows a favorable cost-benefit and Table IV error bars confirm the headline numbers are stable -- I would be willing to move to Weak Accept. The phantom load analysis and NL%-based prediction framework are genuine contributions worth publishing, but the evaluation needs to be self-consistent.
