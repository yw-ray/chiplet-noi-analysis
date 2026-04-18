# Review -- Reviewer 3 (ML/Application Expert), Iteration 8

## Summary

This paper proposes express links for chiplet NoI to address "phantom load" from multi-hop routing, validated via BookSim simulation across five LLM communication patterns. The central claim is that a workload's non-locality fraction (NL%) predicts express link benefit with r=0.94 correlation, achieving up to 52% latency reduction for MoE and all-to-all patterns at K=32. From an ML/distributed-systems perspective, the paper tackles a relevant future problem but models LLM workloads at a level of abstraction that omits critical dynamics of real distributed training and inference.

## Strengths

**[S1] Relevant workload selection.** The five patterns (tree all-reduce, hybrid TP+PP, MoE dispatch, uniform random, all-to-all) cover the dominant communication primitives in modern LLM training. MoE and all-to-all are particularly timely given DeepSeek-V3, Mixtral, and sequence parallelism trends.

**[S2] The NL% predictor is practically useful.** A static metric that predicts topology benefit without cycle-accurate simulation is exactly what hardware architects co-designing with ML teams need. The r=0.94 result, while based on limited data points, is a promising direction.

**[S3] Honest reporting of failure modes.** Express links being harmful at low budget (-119% for MoE at 2x) and random placement being worse than none are important practical findings that add credibility.

## Weaknesses

**[W1] MoE traffic model is unrealistically uniform.** The paper models MoE as "top-2 remote experts" with 10-seed averaging, but real MoE routing exhibits severe expert popularity skew. In DeepSeek-V3 and Mixtral, a small subset of experts handles disproportionate traffic (the "hot expert" problem that motivates expert-level load balancing losses). Uniform random expert selection produces NL=88%, but skewed selection could produce NL anywhere from 30% to 95% depending on whether hot experts are co-located. The 10-seed averaging smooths out this critical dynamic rather than capturing it. The paper should model at least two MoE variants: (a) uniform routing (current), and (b) Zipf-skewed routing with concentration ratio matching published expert load distributions.

**[W2] Hybrid TP+PP with group_size=4 is outdated for K=32.** The paper models tensor parallelism within 4-chiplet groups, which maps to TP=4. Modern LLM training at scale uses TP=8 (Megatron-LM default for large models on 8-GPU nodes). At K=32, a realistic mapping would be TP=8, PP=4 (or TP=8 with some combination of expert/context parallelism), not TP=4. With TP=8, the 8-chiplet all-to-all groups span non-adjacent chiplets on a 4x8 grid, substantially increasing NL%. The paper's TP+PP result (NL=49%, 32% saving) may be significantly understated for realistic parallelism configurations.

**[W3] All-to-all as a proxy for SP/CP lacks temporal dynamics.** Sequence parallelism and context parallelism involve all-to-all exchanges interleaved with compute phases in a pipeline fashion. The steady-state injection model in BookSim does not capture: (a) the bursty nature of SP all-to-all (entire activation tensors exchanged at specific pipeline stages), (b) the overlap of communication with computation that modern frameworks (Megatron, DeepSpeed) rely on, (c) message size heterogeneity (SP redistributes full activations vs. all-reduce on gradients). The paper treats all-to-all as a static, steady-state pattern, which overstates the sustained bandwidth demand.

**[W4] Chiplet granularity does not map to real hardware.** The paper assumes K=16/32 chiplets each containing an NxN mesh. But what does one "chiplet" correspond to in real systems? An H100 SXM has one monolithic die. An MI300X has 8 XCDs but each XCD is a full compute die, not a mesh node. The B200 has 2 dies. The paper's K=32 chiplets with 4x4 or 8x8 internal mesh is a hypothetical architecture that does not correspond to any announced or rumored product. Without grounding in a concrete architecture, it is unclear whether the traffic patterns assumed (e.g., one MoE expert per chiplet) are realistic. How many experts per chiplet? How does intra-chiplet communication interact with the NoI?

**[W5] Missing end-to-end ML performance impact.** The 52% latency reduction on the NoI tells us nothing about end-to-end training throughput or inference latency. In real LLM training, communication is often overlapped with computation (pipeline parallelism, gradient accumulation). The critical question is: what fraction of end-to-end iteration time is spent on NoI communication, and how much of that is on the critical path? A 52% reduction on a 5% component yields only 2.5% end-to-end improvement. Without this context, the significance for ML practitioners is unknown.

## Questions for Authors

1. For the MoE workload, what happens if expert routing follows a Zipf distribution (e.g., top 20% of experts handle 80% of tokens)? Does NL% change significantly, and does the express link benefit hold?

2. At K=32, what is the assumed mapping of LLM model components to chiplets? How many transformer layers, experts, or pipeline stages per chiplet? This determines whether the traffic patterns are realistic.

3. Have you considered modeling communication-computation overlap? In Megatron-LM, TP all-reduce is overlapped with the next layer's compute. The effective communication latency on the critical path is lower than the raw NoI latency.

## Missing References

1. **DeepSpeed-MoE** (Rajbhandari et al., ICML 2022) -- Discusses expert placement strategies and load balancing that directly affect inter-node MoE traffic patterns.
2. **Megatron-LM** (Shoeybi et al., 2020; Narayanan et al., SC 2021) -- Defines the standard TP/PP/DP parallelism strategies and their communication patterns at scale. Essential reference for workload realism.
3. **FLAT** (Iff et al., ISCA 2022) -- Full connectivity for multi-chip, the extreme case of express links.

## Rating

| Criterion | Score |
|-----------|-------|
| Novelty | 3 |
| Technical Quality | 3 |
| Significance | 2.5 |
| Presentation | 4 |
| Overall | 3 |
| Confidence | 4 |

## Decision

**Weak Reject** -- The paper addresses a real problem and the NL% predictor is a neat idea, but the ML workload modeling has significant gaps. The MoE model ignores expert load skew, the TP+PP configuration is outdated, and the all-to-all model lacks temporal dynamics. Most critically, without end-to-end ML performance context, it is impossible to judge whether the 52% NoI latency reduction translates to meaningful training/inference speedup. For an architecture venue targeting the ML accelerator audience, the workload models must be grounded in real distributed training practice. Publishable at a networking workshop (NOCS) or as a short paper, but needs substantial workload modeling improvements for ISCA/MICRO.
