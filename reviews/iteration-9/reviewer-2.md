# Review -- Reviewer 2 (Systems Pragmatist), Iteration 9

## Summary

This paper characterizes "phantom load" in chiplet Networks-on-Interposer, proves center-link amplification grows as Theta(K^{3/2}) for K-chiplet square grids, and proposes express links with workload-aware greedy placement. BookSim cycle-accurate simulation across five LLM communication patterns at K=16/32 with N=4/8 meshes shows 17--52% latency reduction correlated with non-locality fraction (NL%), with r=0.94 at K32_N8 and r=0.66 pooled across all 20 configurations.

## Changes from Iteration 8

Three targeted fixes addressing my previous concerns:

1. **Theta(K) corrected to Theta(K^{3/2}).** The scaling formula now reads alpha_max = R * ceil(C/2) * floor(C/2) = Theta(K^{3/2}) for square grids. This is correct: for R=C=sqrt(K), the expression is sqrt(K) * (sqrt(K)/2)^2 = K^{3/2}/4. The proof error from earlier iterations is resolved. The text, abstract, and conclusion are consistent.

2. **Statistical rigor improved.** The paper now reports 95% CI for the r=0.94 claim ([0.37, 1.00]) and pooled correlation r=0.66 (p=0.001, CI [0.31, 0.85]) alongside Spearman rho=0.57 (p=0.009). This is a meaningful improvement. The wide CI at K32_N8 ([0.37, 1.00]) honestly reflects the small sample size (n=5). The pooled analysis across 20 points with p=0.001 is the stronger statistical claim and the paper appropriately presents both.

3. **Table 5 now reports mean +/- std over 3 seeds.** This addresses my previous question about greedy solution variance. The standard deviations are small relative to means (e.g., Express at K=16: 6.6 +/- 0.4 vs Uniform 14.3 +/- 0.4), suggesting the greedy algorithm is reasonably robust to traffic perturbations.

## Strengths

[S1] **The Theta(K^{3/2}) result is now correct and well-presented.** The super-linear scaling makes a stronger case than the previous Theta(K) claim -- phantom load grows faster than chiplet count, making the problem increasingly urgent at K>=16.

[S2] **Dual correlation reporting is honest and useful.** Reporting both the best-case slice (r=0.94 at K32_N8) and pooled correlation (r=0.66) with CIs gives architects a realistic picture: NL% is a strong predictor at large configurations but only moderate when small-N configurations constrain the budget. This is more informative than the previous single r=0.94 claim.

[S3] **Variance reporting in Table 5 closes the robustness question.** The small standard deviations across seeds confirm that the greedy algorithm's advantage over baselines is not an artifact of a particular traffic realization.

[S4] Strengths S1--S5 from iteration 8 remain: clean thesis, rigorous phantom load analysis, honest negative results, physical overhead closure, and the budget sweep crossover finding.

## Weaknesses

[W1] **Still BookSim-only -- no hardware or FPGA validation.** This remains the primary concern for a top-tier venue. None of the iteration 9 changes address this. The express link latency model (2d cycles for distance d) remains unvalidated against physical signaling models. At distance 4 (40 mm wire at ~2 GHz NoI clock), signal integrity effects (repeater insertion, clock-domain crossing) may make 4-cycle latency optimistic. BookSim also does not model UCIe link-layer overheads (CRC, retry, credit round-trip) that grow with wire length.

[W2] **Absolute latency values still absent.** The paper reports percentage reductions but never states baseline latency in cycles or nanoseconds. The 52% claim cannot be contextualized without knowing whether the baseline is 200 or 2000 cycles.

[W3] **Five workloads with NL% clustering.** The iteration 9 changes do not add workloads. Three of five cluster at NL>85%, leaving only two data points below 50%. The pooled r=0.66 with its wide CI ([0.31, 0.85]) reflects this sparsity. Two or three additional workloads in the NL=20--70% range (ring all-reduce, nearest-neighbor stencil, pipeline-only) would substantially strengthen the NL% predictor claim.

[W4] **No comparison with alternative topologies or production architectures.** The paper compares against adjacent-only baselines but not concentrated mesh, hierarchical ring, Clos/fat-tree, or the bandwidth-doubling alternative (wider adjacent links instead of express links). This comparison gap is significant for practical deployability: a chip architect's real decision is not "express vs. adjacent-only" but "express vs. wider UCIe x16 links vs. NVSwitch-style full connectivity."

[W5] **Deadlock freedom for express routing not addressed.** The paper uses Dijkstra shortest-path routing on the combined topology but does not state whether virtual channels or turn restrictions ensure deadlock freedom. BookSim's VC support may implicitly handle this, but the paper must be explicit -- an architect cannot deploy a routing scheme without a deadlock-freedom guarantee.

[W6] **Traffic matrices remain synthetic.** The five workload patterns are described at the chiplet level but appear analytically derived rather than profiled from real LLM training runs. Temporal burstiness (compute-then-communicate phases) and message size distributions are not modeled.

## Questions

Q1. What are the absolute baseline latencies (in cycles) for each workload at K=32, N=8, maximum injection rate? This is needed to contextualize the 52% claim.

Q2. The pooled r=0.66 is honest but modest. Is NL% the best single predictor, or would a two-variable model (e.g., NL% + K*N) explain more variance? The observation that small N suppresses express benefit suggests configuration size is a confound.

Q3. Has the greedy algorithm runtime been measured? For K=32 with O(L * K^4 * log K) total complexity, is this seconds or hours?

Q4. The paper claims 72 total links vs 168 adjacent-only at K=16. Does this reduction preserve bisection bandwidth? If not, latency reduction may come at the cost of throughput under sustained load.

## Rating

| Criterion | Score | Comment |
|-----------|-------|---------|
| Novelty | 3.0 | Theta(K^{3/2}) is a clean analytical result; express links in NoC are established. NL% predictor is the novel contribution. |
| Technical Quality | 3.5 | Corrected proof, CI reporting, and seed variance are solid improvements. Still simulation-only with synthetic traffic. |
| Significance | 3.0 | Important problem, but practical impact unvalidated without hardware data or absolute latency calibration. |
| Presentation | 3.5 | Clear writing, consistent notation, honest dual-correlation reporting. Bibliography remains thin (13 refs). |
| Overall | 3.0 | Improved rigor over iteration 8. The core limitations (no HW, 5 workloads, no topology comparisons) persist. |
| Confidence | 4.0 | Familiar with chiplet interconnect literature and BookSim evaluation methodology. |

## Decision

**Borderline (Weak Reject for ISCA/MICRO; Accept for DATE/DAC)**

Iteration 9 improves statistical rigor meaningfully: the corrected Theta(K^{3/2}) proof is stronger, the dual correlation reporting with CIs is honest, and the seed variance data closes a previous gap. Technical quality moves from 3.0 to 3.5.

However, the three structural limitations from iteration 8 remain unaddressed:

1. **No hardware validation** -- the latency model and BookSim results are ungrounded in physical measurements.
2. **No absolute latency numbers** -- percentage reductions float without baseline context.
3. **Five synthetic workloads with NL% clustering** -- the predictor is underdetermined in the 20--70% NL range.

For DATE/DAC, the analytical contribution (Theta(K^{3/2}) phantom load, routing independence, NL% predictor with proper statistical qualification) is above the bar. The improved rigor makes this a solid accept at those venues.

For ISCA/MICRO, the gap remains: simulation-only evaluation, no comparison with production architectures, and no end-to-end application performance mapping. The paper is a well-executed design-space exploration, but top-tier architecture venues require validation closer to silicon. The statistical improvements are necessary but not sufficient to close this gap.
