# Review -- Reviewer 3 (ML/Application Expert), Iteration 2

## Summary
The paper characterizes "phantom load" in chiplet Network-on-Interposer (NoI): intermediate links on multi-hop grids accumulate routing traffic far beyond their direct demand, with amplification growing quadratically in chiplet count. The revision reframes the work as a characterization paper and adds six LLM communication patterns, closed-form proofs, routing-independence analysis, and design guidelines. Express links are proposed and validated via BookSim.

## Assessment of Changes from v1

The authors addressed my primary concern (W1 from iteration 1) about the absence of real workload characterization. The addition of six LLM communication patterns (Ring AR, Tree AR, Pipeline Parallel, Tensor Parallel, MoE Expert, Hybrid TP+PP) is a meaningful improvement. The MoE finding (88% phantom links at K=32, 6.5x amplification) is the strongest new result and directly relevant to current industry trends (Mixtral, DeepSeek-V3, GPT-4). The characterization-paper framing is more honest and appropriate.

However, two of my three original concerns remain partially or fully unaddressed.

## Strengths
1. [S1] **MoE vulnerability finding is genuinely useful.** The quantitative result that MoE creates 88% phantom links at K=32 is actionable for architects designing next-generation MoE accelerators. This alone justifies publication interest.
2. [S2] **Workload taxonomy is well-chosen.** The six patterns cover the dominant communication motifs in modern LLM systems. The ranking (MoE worst, Ring best) matches intuition but is now backed by quantitative evidence.
3. [S3] **Design guidelines are practical.** Guideline 4 ("Watch out for MoE workloads") and Guideline 5 ("Express link BW degradation is acceptable") are directly actionable. The 3-4 express link rule-of-thumb is useful for early-stage design.
4. [S4] **Routing independence proof strengthens the characterization.** Showing that ECMP and Valiant cannot eliminate phantom load (6x imbalance persists at K=32) elevates this from an empirical observation to a structural result.
5. [S5] **Counter-intuitive traffic-proportional result.** The finding that the "obvious" allocation strategy is 1.5x worse than uniform is a valuable cautionary tale for designers.

## Weaknesses

1. [W1] **Connection to inference throughput still missing (partially addresses R3-W2).** The paper still reports only network-level metrics (rho_max, latency, throughput in flits). My original question remains: for LLaMA-70B inference on a 4x4 chiplet accelerator, what is the end-to-end token generation speedup? The Discussion section acknowledges "validation on production RTL traces would further strengthen results" but does not attempt even a back-of-envelope calculation. A simple analysis like: "At K=16, inter-chiplet communication accounts for X% of total inference time for a 70B MoE model. Our 46% latency reduction translates to Y% end-to-end speedup" would dramatically strengthen the significance claim. Without this, a reader cannot assess whether phantom load mitigation matters for real system performance or is a second-order effect dwarfed by compute time.

2. [W2] **No comparison with SW mitigations (unchanged from R3-W3).** Communication-computation overlap is standard practice in distributed LLM inference. Ring all-reduce already shows minimal phantom load (1.5x amplification). The paper does not discuss whether systems that already use overlapped communication + ring-based collectives would still benefit from express links. For MoE specifically, expert-parallel systems use techniques like capacity factor limits and top-k pruning to reduce communication volume. How does phantom load interact with these software optimizations? This gap matters because it affects whether the problem is as severe in practice as the characterization suggests.

3. [W3] **Workload patterns are simplified.** The six patterns are useful abstractions but are modeled as static traffic matrices. Real LLM inference has temporal phases: attention (tensor-parallel all-reduce), FFN (tensor-parallel all-reduce or MoE dispatch), and pipeline stage boundaries. The traffic matrix changes every layer. Does phantom load severity vary across inference phases? A time-varying analysis, even for 2-3 phases of a single transformer layer, would significantly strengthen the workload characterization claim.

4. [W4] **MoE traffic model not detailed enough.** The paper states MoE creates "sparse all-to-all traffic where each chiplet sends tokens to a subset of remote experts" but does not specify the model parameters: how many experts per chiplet? What top-k routing? What capacity factor? These choices dramatically affect the traffic pattern. DeepSeek-V3 uses 256 experts with top-2 routing, which creates very different traffic than Mixtral's 8 experts with top-2. The sensitivity to these parameters is not explored.

5. [W5] **BookSim validation uses synthetic netlists, not LLM workload patterns.** Table VII (BookSim) uses "accelerator netlists partitioned via balanced spectral clustering" with cross-cluster ratio (xcr) control, but Table V (workload sensitivity) uses LLM communication patterns. These two evaluations are disconnected. The BookSim validation should include at least one LLM workload pattern (e.g., MoE) to close the loop between characterization and validation.

## Questions for Authors
1. [Q1] For the MoE pattern in Table V, what expert configuration was assumed? How does phantom load change with expert count (8 vs. 64 vs. 256) and top-k (1 vs. 2 vs. 4)?
2. [Q2] In a real inference pipeline, the communication pattern alternates between attention (TP all-reduce) and MoE dispatch every few milliseconds. Does the greedy express link placement optimized for MoE also help attention all-reduce, or do the two patterns require different express link placements?
3. [Q3] How does communication-computation overlap ratio affect the practical severity of phantom load? If 80% of communication is overlapped with computation, does the 6.5x MoE amplification still matter?

## Missing References
- DeepSeek-V3 architecture (256 experts, auxiliary-loss-free load balancing)
- Megatron-LM: Training Multi-Billion Parameter Language Models Using Model Parallelism (parallelism strategies)
- GShard: Scaling Giant Models with Conditional Computation and Automatic Sharding (MoE communication patterns)

## Detailed Comments
- Table V would benefit from a column showing the number of active inter-chiplet flows for each pattern, to contextualize the amplification numbers.
- The "Phantom%" column in Table V is very informative but its definition should be stated explicitly in the text (fraction of links where routing traffic exceeds direct traffic, or fraction with alpha > some threshold?).
- Guideline 1's threshold (alpha_max < 5 for K<=8, alpha_max > 10 for K>=16) would be more useful if connected to a performance impact metric rather than the abstract amplification factor.

## Rating
- Novelty: 3/5
- Technical Quality: 3.5/5
- Significance: 3/5
- Presentation: 4/5
- Overall: 3.5/5
- Confidence: 4/5

## Score Changes from Iteration 1
- Technical Quality: 3 -> 3.5 (closed-form proofs + routing independence analysis)
- Significance: 2.5 -> 3 (LLM workload patterns, especially MoE finding)
- Confidence: 3 -> 4 (clearer scope as characterization paper)

## Decision
**Weak Accept** -- The revision addresses the most critical gap (no workload characterization) and the MoE vulnerability finding is a genuinely useful result for the chiplet design community. The characterization-paper framing is appropriate and the closed-form analysis is solid. However, the persistent absence of any end-to-end performance connection (even a back-of-envelope estimate) and the lack of SW mitigation comparison leave the practical significance partially unvalidated. For a DATE characterization paper, this is acceptable but not compelling. The paper would move to a clear accept with either: (a) a simple roofline-style analysis connecting phantom load to inference throughput loss, or (b) BookSim validation using the MoE traffic pattern from Table V.
