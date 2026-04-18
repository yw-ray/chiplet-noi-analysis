# Review -- Reviewer 1 (Architecture Expert), Iteration 8

## Summary

This paper identifies "phantom load" -- the amplified traffic on intermediate links due to multi-hop routing in chiplet Networks-on-Interposer (NoI) -- and proposes express links (direct non-adjacent chiplet connections) with workload-aware greedy placement to address it. The paper proves center-link amplification grows as Theta(K) in K-chiplet grids, demonstrates routing-algorithm independence across four algorithms, and validates through BookSim cycle-accurate simulation that express links reduce latency by 17--52% across five LLM communication patterns on K=16 and K=32 grids. The central finding is that the workload's non-locality fraction (NL%) predicts express link benefit with r=0.94 correlation.

**Note on iteration context**: This is effectively a fresh review. The paper has been substantially restructured since iteration 7. The previous version framed the contribution around cost reduction ("up to 2.3x fewer links"); this version reframes around latency reduction (52%) with NL% as a unifying predictor metric. The evaluation now uses BookSim latency directly rather than rho_max proxy, and the paper drops design guidelines in favor of a tighter experimental narrative. This is a meaningful improvement in framing.

## Strengths

**[S1] Clean analytical framework with practical predictive power.** The closed-form Theta(K) amplification result (Theorem 1) is elegant and verifiable. More importantly, the NL% metric provides architects a genuinely useful decision tool: compute the non-locality fraction from a static traffic matrix, and if NL% > 40%, invest in express links. The r=0.94 correlation across 20 data points (5 workloads x 4 configurations) is compelling. This is the kind of result that could enter the vocabulary of chiplet architects the way "bisection bandwidth" entered NoC design.

**[S2] Comprehensive experimental design.** The evaluation sweeps across two chiplet counts (K=16, 32), two mesh sizes (N=4, 8), five workloads spanning NL% from 42% to 90%, budget sweeps from 1x to Nx, four injection rates, and multiple random seeds. The budget sweep figure (Fig. 4) is particularly well-done: it exposes the crossover budget phenomenon (express links are harmful at low budget) which is a non-obvious and practically important finding. The ablation (Table VI) showing random placement is worse than no express at all is a strong negative result that validates the need for workload-aware placement.

**[S3] Honest treatment of limitations.** The paper does not hide the crossover budget phenomenon where express links degrade performance at low budgets (the -119% MoE result at 2x budget is strikingly candid). The paper also honestly reports that tree all-reduce, a common workload, benefits only modestly (17%). This builds credibility.

## Weaknesses

**[W1] The 52% latency reduction headline conflates budget regime with topology benefit.** The 52% figure is obtained at K=32, N=8 with 8x budget (the maximum point on the budget sweep). At this budget level, the system has substantial over-provisioning even without express links. The more architecturally meaningful comparison would be: for a *fixed* latency target, how many fewer links does the express topology require? The old framing ("2.3x fewer links") was actually more useful for architects making cost decisions. The paper should report both metrics. Without the cost-equivalence comparison, a reader cannot determine whether express links save area/power or only improve latency at the same cost -- these are fundamentally different value propositions.

**[W2] BookSim simulation does not model interposer-specific physics.** The paper assigns express link latency as 2d cycles for distance d (Table VII), which is a reasonable first-order model. However, real interposer wires at 20--40mm face signal integrity challenges (crosstalk, IR drop, timing closure) that may require repeaters or retimers, adding latency beyond the linear model. At distance 4 (40mm on CoWoS), whether a single-cycle-per-hop latency model is realistic is questionable. CNSim (cited but not used) models some of these effects. The paper should either validate the latency model against a physical design reference or present a sensitivity analysis showing how results change if express link latency is, say, 1.5x or 2x the linear estimate.

**[W3] Comparison with state-of-the-art chiplet interconnect papers is insufficient.** The related work table (Table I) compares across five dimensions but does not include several recent and relevant works:
- **Simba** (MICRO 2019) -- a 36-chiplet multi-chip module with a mesh NoI and package-level interconnect that directly addresses multi-hop latency in chiplet grids. The evaluation at K=32 is almost exactly Simba's scale.
- **NVIDIA NVLink/NVSwitch architectures** (various Hot Chips) -- these use a switch-based (rather than mesh-based) NoI topology that fundamentally avoids multi-hop routing. The paper should discuss whether a switch-based topology is an alternative to express links and at what cost.
- **AMD Infinity Fabric** beyond MI300X -- the paper mentions MI300X (K=8) but does not discuss how AMD's approach scales. The claim that K=8 is "manageable" should be quantified against AMD's actual link budget.

The paper positions express links as a novel topology intervention, but the architecture community has explored skip-links, express channels, and hierarchical networks extensively. The novelty claim needs sharper differentiation from prior monolithic NoC work beyond the cost argument in Section 2.

**[W4] The workload models are synthetic traffic matrices, not traced from real accelerator execution.** The five workload patterns (tree all-reduce, hybrid TP+PP, MoE dispatch, uniform random, all-to-all) are analytically generated from communication pattern descriptions, not traced from actual GPU/TPU/accelerator execution. Real workloads exhibit temporal dynamics (phases, bursts, congestion feedback) that static traffic matrices cannot capture. For example, MoE expert dispatch in practice shows highly skewed expert popularity (the "winner-take-all" effect in Mixtral/DeepSeek-V3), which would change the traffic matrix significantly from the uniform-top-2 model assumed here. The paper should either (a) use traces from a real MoE implementation, or (b) include a sensitivity analysis varying the traffic matrix skew to show robustness.

**[W5] Missing latency-throughput curves.** The paper reports latency at "maximum injection rate" as the express saving metric, but does not show full latency-throughput curves. This is a standard omission concern in network papers. The shape of the curve matters: express links might shift the saturation point (good) or might reduce latency only at low load while providing no benefit at saturation (less good). A single operating point is insufficient to characterize the benefit. At minimum, showing 2--3 load points for the headline K=32, N=8 configuration would strengthen the evaluation.

## Questions for Authors

1. **Cost vs. latency framing**: For the 52% latency reduction at K=32, N=8, what is the corresponding link-count reduction if the target is to match adjacent-only latency rather than minimize latency at matched cost? Reporting both metrics would make the contribution clearer to architects with different optimization objectives.

2. **Scalability of greedy placement**: The algorithm complexity is O(L * |C| * K^2 log K) per iteration. For K=64 (the projected industry target), with |C| = O(K^2) and L potentially in the hundreds, what is the wall-clock runtime? Is this tractable for design-space exploration, or would an architect need to fall back to heuristics?

3. **Heterogeneous express link bandwidth**: The current model assumes all links (adjacent and express) have the same bandwidth. In practice, longer wires may have lower bandwidth due to signal integrity constraints. Have you evaluated a model where express links have, say, 50% or 75% of adjacent link bandwidth?

## Missing References

- **Simba** (Shao et al., MICRO 2019) -- 36-chiplet multi-chip-module accelerator with package-level mesh NoI. Directly relevant to the K=32 evaluation scale.
- **NVIDIA NVSwitch** (various Hot Chips presentations) -- switch-based chiplet interconnect that avoids multi-hop mesh routing entirely.
- **2.5D NoC Topologies** (Xu et al., DATE 2014; Kannan et al., ICCAD 2015) -- early work on inter-die topology optimization for 2.5D integration.
- **HBM packaging constraints** -- the physical overhead analysis should reference actual CoWoS/EMIB packaging studies (e.g., TSMC CoWoS-L whitepapers) to validate the wire pitch and area assumptions.
- **Multi-chiplet GPU architectures** (MCM-GPU, Arunkumar et al., ISCA 2017) -- multi-chip GPU module design that addresses inter-chiplet communication.

## Detailed Comments

### Introduction (Section 1)
The introduction is well-structured and follows the trend-problem-limitation-contribution arc effectively. Fig. 1 is placed correctly at the top of page 1. The "diminishing returns" argument (4x budget gives 1.5x speedup) is compelling motivation.

Minor: The claim "no routing algorithm eliminates it" in the abstract is slightly stronger than what the paper proves. The paper shows four algorithms (XY, YX, ECMP, Valiant) all exhibit phantom load, but does not prove impossibility for *all* algorithms. The ECMP result (imbalance reduced from 8.2x to 2.3x) suggests that routing does help meaningfully -- the paper should say "no standard routing algorithm eliminates it" or "routing algorithms reduce but cannot eliminate it."

### Phantom Load Analysis (Section 3)
This is the strongest section. The closed-form analysis is clean, the example is pedagogically effective, and Table II provides concrete scaling numbers. The routing algorithm independence (Table III) is a valuable result.

However, the routing table (Table III) shows absolute "Max alpha" values that differ significantly from the closed-form predictions. For example, XY on 4x4 shows Max alpha = 111 in Table III but the closed-form predicts alpha_max = 16 in Table II. The discrepancy likely arises because Table III uses workload traffic while Table II uses uniform traffic, but this is not explained. This will confuse careful readers. Add a sentence clarifying the difference.

### Express Link Architecture (Section 4)
Algorithm 1 is clearly presented. The traffic-proportional fallback for remaining budget after greedy plateau is a good practical detail. However, the paper does not discuss deadlock freedom. Express links create non-standard topology with potential for routing deadlocks. If Dijkstra shortest-path routing is used, how is deadlock avoided? Virtual channels? Turn restrictions? This is a critical implementation detail for any real adoption.

### Evaluation (Section 5)
Table IV (main result) is clean and the trend is clear. The budget sweep (Fig. 4) is the most informative figure. The ablation (Table VI) is well-designed.

The correlation analysis (Section 5.5, Fig. 5) with r=0.94 is based on only 5 distinct NL% values (42%, 49%, 88%, 89%, 90%). Three of these are clustered in the 88-90% range. With only 2-3 distinct clusters on the x-axis, a high Pearson r is expected and may overstate the predictive power. The paper should acknowledge this limitation and ideally add 2-3 workloads in the 55-80% NL% range (e.g., ring all-reduce, pipeline-parallel only, 2D stencil) to validate the linear relationship in the gap.

### Physical Overhead (Section 5.6)
The overhead analysis is reasonable but the "net area saving" argument (72 total links vs. 168 adjacent-only) compares different latency points. The adjacent-only system with 168 links achieves a certain latency; the express system with 72 links achieves a different latency. These are not iso-performance comparisons. This muddies the cost argument. Either compare at iso-latency or explicitly state the latency difference.

### Conclusion (Section 6)
The conclusion is appropriately concise and restates the key findings. The "invest in express links when NL% exceeds 40%" guideline is practical and memorable.

### Missing Discussion Topics
- **Thermal implications**: Express links spanning multiple chiplet pitches may create thermal hotspots on the interposer due to concentrated wire power. At 1.15W per distance-3 link and 10+ express links, the localized power density matters.
- **Manufacturing yield**: Longer wires on the interposer have higher defect probability. At 30--40mm, yield impact should be estimated.
- **Dynamic workloads**: Real AI accelerators multiplex workloads (training + inference, mixed batch). A single static traffic matrix may not capture the optimal express topology for a product serving multiple workloads. Is there a universal express topology that works well across all five workloads?

## Rating

- Novelty: 3/5
- Technical Quality: 3.5/5
- Significance: 3.5/5
- Presentation: 4/5
- Overall: 3.5/5
- Confidence: 4/5

## Score Justification

**Novelty (3/5)**: The phantom load analysis and Theta(K) scaling result are technically clean but the concept of multi-hop load amplification is well-understood in the NoC community. Express/skip links have been studied in monolithic NoC for nearly two decades. The novelty lies in (a) applying this to the chiplet cost context and (b) the NL% predictor metric. The predictor is the most novel element, but it needs validation with more diverse workloads (see W4, detailed comments on correlation).

**Technical Quality (3.5/5)**: The analytical framework is sound and the BookSim evaluation is comprehensive in sweep dimensions. However, the lack of physical validation of the latency model (W2), the synthetic-only workloads (W4), the missing latency-throughput curves (W5), and the discrepancy between Table II and Table III values reduce confidence. The deadlock freedom question (detailed comments) is a gap.

**Significance (3.5/5)**: The problem is real and will become more pressing as chiplet counts scale. The NL% predictor has practical value. However, industry may adopt switch-based solutions (NVSwitch-style) rather than mesh+express, which would limit the impact of this work. The paper would be stronger with a discussion of when mesh+express is preferred over switch-based alternatives.

**Presentation (4/5)**: The paper is clearly written with a logical flow. Tables and figures are well-designed. The introduction effectively motivates the problem. The one-file format (no separate section files) reads well. Minor presentation issues: the Table II/III discrepancy, the iso-performance confusion in physical overhead.

**Overall (3.5/5)**: A solid characterization and design exploration paper with a clean analytical contribution and comprehensive (if synthetic) evaluation. The reframing around latency and NL% as a predictor is an improvement over the previous cost-focused framing. However, the paper falls short of the bar for a top architecture venue due to: (a) limited novelty over prior express channel work, (b) synthetic-only workload validation, (c) missing physical/latency model validation, and (d) incomplete comparison with alternative topologies (switch-based). With the additions suggested in W1-W5 and the missing references, this could reach the accept bar.

## Decision

**Borderline** -- The paper makes a technically sound contribution with a useful predictor metric (NL%) and honest evaluation. However, for ISCA/MICRO acceptance (20% rate), I would need to see: (1) at least one traced workload from a real MoE or all-to-all implementation to validate the synthetic models, (2) a cost-equivalence comparison alongside the latency comparison, (3) discussion of switch-based alternatives, and (4) resolution of the correlation analysis concern (more workloads in the 55-80% NL% gap). The paper is publishable at a workshop (e.g., NOCS, DATE) in its current form and could reach a top venue with one more round of strengthening.
