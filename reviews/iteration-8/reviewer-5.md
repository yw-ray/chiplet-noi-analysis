# Review -- Reviewer 5 (Skeptic), Iteration 8

## Summary

This paper identifies "phantom load" -- the amplification of traffic on center links due to multi-hop routing in 2D chiplet grids -- and proves it scales as Theta(K). It proposes express links (direct interposer connections between non-adjacent chiplets) with workload-aware greedy placement, claiming 17-52% latency reduction across five LLM workloads and a strong correlation (r=0.94) between non-locality fraction (NL%) and express benefit. The paper is evaluated on K=16 and K=32 chiplet grids using BookSim cycle-accurate simulation.

This is a major revision from the version I reviewed in iteration 7. The paper has been substantially restructured: the cost-framing thesis is gone, replaced by a latency-reduction thesis; the "2.3x fewer links" claim from the abstract is removed; the budget sweep is now presented per-workload; and the text is considerably tighter (6 pages). The scope is narrower but the claims are better supported by the evidence.

## Strengths

**[S1] The phantom load analysis is a genuine analytical contribution.** The closed-form Theta(K) amplification proof (Theorem 1) with routing-algorithm independence across four algorithms is clean and independently valuable. The concrete numerical validation (Table I, Table II) is convincing.

**[S2] The claim structure is now more honest than previous iterations.** The abstract leads with "52% for MoE and all-to-all" but immediately scopes it with "17% for tree all-reduce." Presenting the range upfront is a significant improvement over earlier versions that led with "2.3x fewer links" as a universal claim.

**[S3] The NL%-vs-saving correlation is a useful predictive tool.** If the r=0.94 result generalizes beyond these 5 workloads (a big "if"), it would give architects a cheap static analysis to decide whether express links are worth investigating. This is the most practical contribution.

**[S4] The ablation (Table VI) is informative.** Random express placement being worse than no express (18.0 vs 14.3) proves that express links are not inherently beneficial -- placement quality matters. This strengthens the paper by preventing the naive interpretation that "any express link helps."

**[S5] Traffic-proportional being worse than uniform (Table III) is a surprising and well-demonstrated result.** This undermines the intuition that "proportional allocation is always better" and supports the topological argument.

## Weaknesses

**[W1] Two workloads were dropped from experiments without disclosure -- and they show express links are harmful.**

The experiment scripts (`cost_perf_6panel_workload.py`) support 7 workloads: the 5 in the paper plus ring allreduce and pipeline parallel. The results directories contain completed BookSim runs for all 7. I examined the dropped results:

- **Ring allreduce** (NL%=12.5% at K=32): At K=8 N=8, express greedy is **3.9x worse** than adjacent uniform at 8x budget (latency 250.7 vs 65.0). At K=32 N=8, express provides 0% benefit (66.2 vs 66.2 at 8x). The greedy algorithm places only 0-1 express links for ring because the traffic is so local, yet those few express links cause catastrophic routing disruption at K=8.

- **Pipeline parallel** (NL%=9.7% at K=32): At K=8 N=8, express greedy is **2.5x worse** at 8x budget (latency 135.4 vs 54.2). At K=32 N=8, express is 0.2% worse at 8x budget.

The paper's narrative is "express links help when NL% is high and are neutral when NL% is low." But the dropped data shows express links can be **severely harmful** when NL% is very low (at smaller K). The paper includes a negative result for MoE at 2x budget (-119%, line 336), which is attributed to budget starvation. But the ring/pipeline results cannot be explained by budget starvation alone -- at K=8 N=8 with 8x budget, there is ample adjacent capacity, yet express still hurts. This is a different failure mode that the paper does not analyze.

Furthermore, including these two workloads would actually improve the r correlation (from 0.944 to 0.983), so the omission cannot be justified by them being outliers that break the correlation. The real reason appears to be that they show express greedy performing catastrophically at K=8, which undermines the paper's thesis. This is cherry-picking.

**[W2] The r=0.94 correlation is computed on only 5 data points (for K32N8) -- this is not statistically meaningful.**

A Pearson correlation on 5 data points has enormous confidence intervals. With n=5, even r=0.94 yields a 95% confidence interval of approximately [0.47, 0.99] (Fisher z-transform). The paper does not report confidence intervals, p-values, or acknowledge the small sample size. Claiming r=0.94 as a "strong predictor" based on 5 workloads is overclaiming. Even if we add the 2 dropped workloads (n=7, r=0.983), the statistical power remains low.

The paper should either: (a) generate many more synthetic workloads at varying NL% to establish a robust regression, or (b) qualify r=0.94 as preliminary/indicative rather than presenting it as a reliable architectural prediction tool. As stated in the abstract and conclusion, r=0.94 sounds like a validated engineering metric, when in reality it is a correlation among 5 hand-selected workloads.

**[W3] The "same link cost" comparison (adjacent uniform vs express greedy) is not apples-to-apples.**

The paper claims express links achieve "52% latency reduction at the same link cost as adjacent-only baselines" (abstract, line 29). But express links at distance d have d-times the wire length, d-times the wire area, and d-times the wire power (Table VII). The paper acknowledges this in Section V.E but the abstract and introduction present "same link cost" without qualification.

At K=32 N=8 with 8x budget, MoE uses 129 express links. If the average express distance is 2.5 (a conservative estimate given the 4x8 grid), the wire-length-adjusted cost of the express topology is substantially higher than 168 adjacent-only links, not lower. The "same total link count" is not "same total cost" once wire length is accounted for. This was flagged in my iteration-6 review and the iteration-7 response added breakdown numbers, but the abstract still frames it as "same link cost."

**[W4] The baseline is weak: only adjacent uniform is compared in the main experiment.**

Table IV compares only adjacent uniform vs express greedy. The analytical section shows load-aware and MinMax-adjacent baselines (Table III), but the BookSim cycle-accurate comparison is only against uniform. Why are load-aware and MinMax-adjacent not run in BookSim? The paper claims MinMax-adjacent "saturates identically to uniform" but this is asserted for rho_max, not for cycle-accurate latency. BookSim latency depends on queuing dynamics, not just peak utilization -- an optimized adjacent allocation could have lower tail latency even at the same rho_max.

At minimum, the load-aware baseline (which Table III shows matches MinMax) should be evaluated in BookSim to confirm that the analytical equivalence translates to cycle-accurate equivalence.

**[W5] The K=8 results at N=8 reveal a fundamental problem with the greedy algorithm that is not analyzed.**

At K=8 N=8, for ring allreduce and pipeline parallel, the greedy algorithm places 1 express link and then stops improving -- but that 1 express link is catastrophically bad (3-4x worse latency). This suggests the greedy algorithm's congestion-minimization objective (minimize rho_max) does not capture the actual BookSim latency. The greedy thinks it is improving rho_max, but BookSim shows latency increasing dramatically. This disconnect between the analytical model and cycle-accurate simulation is a serious concern for the paper's methodology.

The paper attributes this to "the greedy algorithm's suboptimal behavior" but does not investigate why. Is it a routing pathology? A flow-conservation issue? A BookSim artifact? Without understanding the root cause, the reader cannot assess whether the express link approach is fundamentally sound or fundamentally fragile.

**[W6] No error bars, confidence intervals, or variance reporting across seeds.**

Table III mentions "Avg. 3 Seeds" and the ablation references "avg. 10 seeds," but no standard deviations or confidence intervals are reported anywhere. For a simulation-based paper, reporting only mean values without variance is unacceptable. The 52% saving claim -- is that 52 +/- 1% or 52 +/- 20%? The reader has no way to assess reliability.

**[W7] BookSim is a monolithic NoC simulator, not a chiplet NoI simulator.**

The paper uses BookSim to model chiplet networks, but BookSim was designed for monolithic mesh NoC. The paper maps each chiplet to an NxN sub-mesh and connects them via anynet links. This means: (a) intra-chiplet traffic is modeled identically to inter-chiplet traffic (same router latency, same buffer sizes), which is physically unrealistic; (b) there is no PHY model, serialization latency, or credit-based flow control at chiplet boundaries; (c) express link latency is modeled as 2d cycles (line 240), but this linear scaling with distance is a simplification -- real interposer wires have RC delay that scales differently.

The paper acknowledges "BookSim models internal mesh as store-and-forward routers" in Limitations, but the implications go deeper: if the intra-chiplet mesh latency dominates, then inter-chiplet topology optimization (the entire point of this paper) becomes a small fraction of total latency. The absolute latency values in Table IV include both intra- and inter-chiplet components, so the "52% saving" is on total latency including the intra-chiplet portion -- is the saving on inter-chiplet latency alone actually much larger or much smaller?

## Questions for Authors

**Q1.** Why were ring allreduce and pipeline parallel dropped from the experiments? These are standard LLM communication patterns. Ring allreduce is the dominant collective in distributed training (used by NCCL, Gloo). Their omission from a paper claiming to evaluate "five LLM communication patterns" needs explicit justification.

**Q2.** At K=8 N=8, express greedy is 3-4x worse than adjacent uniform for ring and pipeline workloads even at 8x budget. Why? If the greedy algorithm places only 1 express link, why does that single link cause such severe latency degradation? Is this a routing pathology (all traffic forced through the express link) or a structural issue?

**Q3.** What is the standard deviation of the 52% MoE saving across the 10 seeds mentioned for MoE? What about for the other 4 workloads?

**Q4.** If NL% is the dominant predictor, what is the express saving at NL%=12.5% (ring) and NL%=9.7% (pipeline)? Would including these data points change the regression line or just strengthen r?

**Q5.** For the r=0.94 claim, what are the 95% confidence intervals? Have you tested with interpolated synthetic workloads at NL%=20%, 30%, 60%, 70%?

**Q6.** In the "same link cost" comparison, what is the total wire-length-adjusted cost (in mm^2 and watts) of the 129-express-link MoE topology vs the 168-adjacent-only topology at K=32 N=8?

**Q7.** Why is the MinMax-adjacent (Kite-like) baseline not evaluated in BookSim? The claim that it "saturates identically" is based on rho_max, not cycle-accurate latency.

## Missing References

- **NVIDIA NVSwitch / NVLink topology** -- the most relevant commercial example of non-adjacent express links in multi-GPU systems. NVSwitch provides full connectivity (effectively infinite express links), and its comparison would contextualize the cost argument.
- **AMD Infinity Fabric topology details** for MI300X -- the paper mentions MI300X but does not cite AMD's specific topology analysis.
- **Interconnect synthesis / NoC topology generation** literature (e.g., SunFloor, NetChip) -- relevant prior work on automated topology design.
- **Chiplet network simulation** (CNSim, cited but not compared against) -- if the claim is that BookSim is adequate for chiplet simulation, this should be discussed relative to CNSim which was specifically designed for chiplets.

## Detailed Comments

1. **Abstract line 29**: "at the same link cost as adjacent-only baselines" -- This is misleading. Same link COUNT, not same link COST. An express link at distance 3 costs 3x the wire area and power. Replace "link cost" with "link count" or add a qualifier.

2. **Table II (routing algorithms)**: The Max alpha column shows XY=111, YX=223 for 4x4 grid. But Theorem 1 predicts alpha_max=16 for 4x4 grid with uniform traffic. The discrepancy is because Table II uses actual workload traffic (not uniform), but the caption does not clarify this. The table header says "Load Imbalance Across Routing Algorithms" -- what workload? Uniform? The specific one?

3. **Algorithm 1 line 7**: "break if no improvement" -- What is the threshold? Is it strict inequality (any epsilon improvement counts) or a meaningful improvement threshold? If strict, the greedy could add a link that improves rho_max by 0.001, which may be noise in BookSim.

4. **Section IV.B**: "remaining budget is allocated proportionally to traffic demand across all candidate pairs." This means the express-greedy strategy is actually a hybrid: greedy placement for the first phase, then traffic-proportional for the remainder. But traffic-proportional was shown to be "2-3x worse than uniform" (Table III). So the fallback strategy is the worst one. Why not uniform fallback? This seems contradictory.

5. **Table IV NL% values**: Tree all-reduce NL%=42%, but the butterfly pattern at K=32 on a 4x8 grid should have distance patterns that depend heavily on chiplet-to-grid mapping. Is the NL% sensitive to the chiplet numbering (row-major vs column-major vs Hilbert)?

6. **Section V.B**: "MoE drops to -119% at 2x" -- This negative saving at low budget is mentioned but the paper does not explain why the greedy algorithm allocates express links at 2x budget if it makes things worse. The greedy should see rho_max increasing and stop placing express links. Why does it continue?

7. **Physical overhead (Section V.E)**: "10 express links at average distance 2.5" -- but K=32 MoE uses 129 express links. The overhead estimate uses 10 express links which is far below the actual usage. This significantly understates the physical overhead for the workloads where express links are most beneficial.

8. **Conclusion**: "invest in express links when NL% exceeds 40%" -- The tree all-reduce at NL%=42% achieves only 17% saving. Is 17% saving worth the design complexity and physical overhead of express links? This threshold may be too aggressive.

## Rating

- Novelty: 3.0/5 -- Express channels in NoC are well-studied (EVC, concentrated mesh). The phantom load analysis is novel for chiplet NoI but the express link idea is a straightforward extension.
- Technical Quality: 2.5/5 -- Dropping 2 workloads that show express links are harmful, r=0.94 on 5 data points without statistical rigor, no error bars, weak baselines (only uniform adjacent in BookSim), unanalyzed catastrophic failures at K=8.
- Significance: 3.0/5 -- The phantom load analysis is independently useful. The express link proposal has merit but the evaluation does not establish reliability.
- Presentation: 3.5/5 -- Well-structured, clear writing, honest about some limitations. But the omission of harmful results and the "same link cost" framing are presentation problems.
- Overall: 2.75/5
- Confidence: 4.0/5

## Decision

**Weak Reject.**

The paper has improved significantly since earlier iterations. The phantom load analysis (Sections III) is a genuine contribution, and the NL%-based prediction framework is a useful idea. However, I cannot recommend acceptance with the current evaluation.

The most serious issue is the omission of ring allreduce and pipeline parallel from the experiments. These are standard LLM communication patterns, the data exists, and the results show express links being catastrophically harmful at K=8 (up to 3.9x worse). This is not a minor edge case -- ring allreduce is the dominant collective in distributed training. A paper that omits harmful results while claiming to evaluate "five LLM communication patterns" has a cherry-picking problem.

The secondary issues compound: r=0.94 on 5 data points is not statistically meaningful; no error bars are reported; the "same link cost" framing is misleading; the main BookSim comparison uses only adjacent uniform as the baseline; and the catastrophic K=8 failures are not analyzed.

To move to Accept, the paper needs: (1) include all 7 workloads with honest discussion of when express links hurt, (2) report error bars/variance, (3) run MinMax-adjacent in BookSim, (4) analyze the K=8 catastrophic failure root cause, (5) fix the "same link cost" language in the abstract, and (6) either add synthetic workloads to strengthen the r correlation or explicitly qualify it as preliminary.
