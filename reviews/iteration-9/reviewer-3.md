# Review -- Reviewer 3 (ML/Application Expert), Iteration 9

## Summary

This paper identifies phantom load as a structural cost problem in chiplet NoI, proves center-link amplification grows as Theta(K^{3/2}), and proposes express links with workload-aware greedy placement. BookSim simulation across five LLM patterns shows up to 52% latency reduction for high non-locality workloads. The NL% predictor correlates at r=0.94 (K32_N8) and r=0.66 pooled. Iteration 9 fixes the proof exponent, adds CIs and pooled correlation, and reports mean+/-std in Table 5. My core concerns from iteration 8---workload realism---remain unaddressed.

## Changes from Iteration 8

**Theta(K) -> Theta(K^{3/2})**: Correct fix. The derivation in Eq. 3 now matches the claimed scaling (alpha_max = R * ceil(C/2) * floor(C/2) scales as K^{3/2} for square grids). This strengthens the analytical contribution.

**Statistical rigor**: Reporting pooled r=0.66 (p=0.001, CI [0.31, 0.85]) alongside K32_N8 r=0.94 (CI [0.37, 1.00]) is honest and appreciated. However, the wide CI on r=0.94 (only 5 data points) makes it a suggestive trend, not a strong predictive model. Table 5 mean+/-std is a minor but welcome improvement.

**Workload realism (W1--W5 from iteration 8): NOT addressed.** The MoE model still uses uniform expert routing. TP+PP still uses group_size=4. All-to-all still lacks temporal dynamics. Chiplet granularity is still not grounded in any concrete architecture. No end-to-end performance context added. These were the primary concerns and none were mitigated.

## Strengths

**[S1] Stronger analytical foundation.** The corrected Theta(K^{3/2}) proof with Table 2 validation up to K=64 is now clean and correct. The super-linear growth argument is more compelling than the previous linear claim.

**[S2] Transparent statistical reporting.** Reporting the pooled r=0.66 alongside the cherry-picked K32_N8 r=0.94 is good scientific practice. The Spearman rho=0.57 (p=0.009) as a robustness check is appropriate.

**[S3] Practical findings preserved.** The crossover budget observation (express links harmful at <= 2x), random placement being counterproductive (rho_max 18.0 vs 14.3), and traffic-proportional allocation being worse than uniform remain valuable practical insights.

## Weaknesses

**[W1] MoE traffic model remains unrealistic (unchanged from iter 8).** Real MoE routing exhibits severe expert popularity skew (DeepSeek-V3, Mixtral). The paper's NL=88% with 10-seed uniform averaging does not capture the hot-expert phenomenon. With skewed routing + co-located hot experts, NL% could drop substantially, invalidating the 52% headline number for MoE specifically. This is the paper's most-cited workload in motivation, yet its modeling is the weakest.

**[W2] TP=4 at K=32 remains outdated (unchanged).** Modern LLM training uses TP=8 (Megatron-LM default for 8-GPU nodes). With TP=8, intra-group all-to-all spans non-adjacent chiplets on a 4x8 grid, substantially increasing NL% for hybrid TP+PP. The paper's 32% saving for this workload may be significantly understated.

**[W3] No end-to-end ML context (unchanged).** The 52% NoI latency reduction is meaningless without knowing what fraction of end-to-end training/inference time is NoI-bound. If NoI is 5% of iteration time (common with compute-communication overlap), the practical impact is 2.5%. This framing gap makes the paper's significance to the ML accelerator audience difficult to assess.

**[W4] NL% predictor has limited practical value.** With r=0.66 pooled and only 5 workloads, the predictor is a conceptual insight, not a deployable tool. The wide CI on r=0.94 ([0.37, 1.00]) means we cannot statistically distinguish r=0.94 from r=0.5 at this sample size. The paper should temper claims about "simulation-free prediction."

## Questions

1. With the corrected Theta(K^{3/2}), at K=64 the amplification is 128x. Does the greedy algorithm still converge to meaningful express placement at this scale, or does the combinatorial space become intractable?

2. The pooled r=0.66 suggests NL% explains only ~44% of variance in express saving. What explains the remaining 56%? Is it purely the N-limited budget effect, or are there workload structural features beyond NL% that matter?

3. Has there been any consideration of modeling bursty injection (e.g., on-off traffic at 50% duty cycle) to approximate compute-communication interleaving? This would partially address W3 without requiring a full system simulator.

## Rating

| Criterion | Score |
|-----------|-------|
| Novelty | 3 |
| Technical Quality | 3.5 |
| Significance | 2.5 |
| Presentation | 4 |
| Overall | 3 |
| Confidence | 4 |

## Decision

**Weak Reject** -- The proof correction and statistical improvements are genuine quality gains, raising Technical Quality by 0.5. However, the core weakness from iteration 8 persists: the workload models do not reflect real distributed ML practice, and no end-to-end performance context is provided. For an architecture venue targeting ML accelerators (ISCA/MICRO), workload fidelity is not optional---it is the credibility foundation. The paper's headline results (52% for MoE, 32% for TP+PP) rest on simplified traffic models whose relationship to actual systems is unclear. The analytical contribution (Theta(K^{3/2}) proof, routing independence) is solid and publishable. Recommendation: add at least one skewed-MoE variant, update TP group size to 8, and provide even a back-of-envelope end-to-end impact estimate. This would make the workload story defensible and likely push the paper to borderline accept. Suitable for NOCS or a workshop in current form.
