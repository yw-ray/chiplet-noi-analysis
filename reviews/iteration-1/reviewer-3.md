# Review — Reviewer 3 (ML/Application Expert), Iteration 1

## Summary
The paper addresses inter-chiplet communication bottlenecks by identifying "phantom load" and proposing "express links" to bypass congested intermediate links. Evaluated on synthetic accelerator netlists with BookSim.

## Strengths
1. [S1] **Timely topic.** As LLM accelerators scale beyond reticle limits, chiplet NoI design becomes critical. The paper addresses a real industry need.
2. [S2] **The phantom load concept is intuitive and well-visualized.** Fig. 1 effectively communicates the problem.
3. [S3] **Workload sensitivity analysis** (Table VIII) across xcr 0.1-0.6 shows robustness. This is good practice.

## Weaknesses
1. [W1] **No real workload characterization.** The paper uses a synthetic netlist generator with parametric cross-cluster ratios. But real LLM workloads have very specific communication patterns: all-reduce after attention/FFN layers, pipeline parallelism between stages. These are not captured by random cross-cluster edges.
2. [W2] **The connection to inference throughput is missing.** For K=16 chiplets running LLaMA-70B, what fraction of total inference time is spent on inter-chiplet communication? If it's <5% (as is typical for compute-bound LLM inference), then 90% NoI throughput improvement translates to <5% end-to-end speedup—which may not justify the design complexity.
3. [W3] **No comparison with software-level mitigations.** Communication-computation overlap, pipelining, and collective operation optimization (e.g., ring all-reduce vs. tree all-reduce) can significantly reduce the effective communication overhead. Do express links still help after these optimizations?

## Questions for Authors
1. [Q1] What is the estimated end-to-end inference speedup (tokens/sec) from express links for a specific LLM model?
2. [Q2] How does the traffic pattern change with different parallelism strategies (tensor parallel, pipeline parallel, expert parallel)?
3. [Q3] Would simply using more chiplets with a wider grid (e.g., 2×8 instead of 4×4) avoid the phantom load problem without express links?

## Missing References
- Megatron-LM parallelism strategies
- Communication patterns in transformer training/inference
- DeepSpeed ZeRO communication optimization

## Detailed Comments
- The paper would benefit greatly from a case study: "For LLaMA-70B inference on a 4×4 chiplet accelerator, express links reduce token generation latency from X to Y ms." Without this, the significance is unclear.

## Rating
- Novelty: 3/5
- Technical Quality: 3/5
- Significance: 2.5/5
- Presentation: 4/5
- Overall: 3/5
- Confidence: 3/5

## Decision
**Borderline** — Well-written paper with a clear problem formulation, but the disconnect between network-level metrics and application-level impact weakens the significance claim. Adding even a simple end-to-end case study would substantially strengthen the paper.
