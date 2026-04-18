# Review -- Reviewer 2 (Systems Pragmatist), Iteration 8

## Summary

This paper identifies "phantom load" -- the amplification of link utilization caused by multi-hop routing in chiplet Networks-on-Interposer (NoI) -- and proposes express links (direct non-adjacent connections) with workload-aware greedy placement as a solution. The paper proves center-link amplification grows as Theta(K) for K-chiplet grids, demonstrates routing-algorithm independence of the problem, and evaluates express links via BookSim cycle-accurate simulation across five LLM communication patterns at K=16 and K=32. The headline result is that express link benefit correlates strongly with the workload's non-locality fraction (NL%), achieving 52% latency reduction for MoE/all-to-all (NL=88-90%) and 17% for tree all-reduce (NL=42%), with r=0.94 correlation.

Compared to iteration 7 (which I scored 4.5/5 Accept for DATE/DAC), this is a major rewrite. The paper has shifted from a cost-centric framing (rho_max reduction, cost-matching tables) to a latency-centric framing with BookSim latency measurements, budget sweeps, and the NL% correlation story. Five workloads replace the previous three. The evaluation now spans two chiplet counts and two mesh sizes (4 configurations total). This is a substantially different paper and warrants a fresh review calibrated for ISCA/MICRO.

## Strengths

[S1] **Clean thesis with predictive metric.** The paper's strongest contribution is the NL% predictor: a static, simulation-free metric that predicts express link benefit with r=0.94. This is exactly the kind of design-time heuristic that chiplet architects need. The claim is crisp: "compute NL% from the communication graph; invest in express links when NL% > 40%." This is actionable.

[S2] **Phantom load analysis is rigorous and well-framed.** The closed-form derivation of Theta(K) amplification (Theorem 1) is clean, the routing-algorithm independence study (Table III) is convincing, and the workload sensitivity analysis (Table IV) bridges theory to practice. The progression from mathematical proof to simulation validation is well-structured.

[S3] **Honest negative results build credibility.** The paper reports that express links are worse than adjacent-only at low budgets (e.g., MoE drops to -119% at 2x budget in Fig. 3), that random express placement is worse than no express at all (Table VII), and that traffic-proportional allocation is 1.6x worse than uniform (Table V). These results demonstrate intellectual honesty and a method that is workload-aware rather than blindly optimistic.

[S4] **Physical overhead section closes the cost loop.** Table VIII gives concrete wire area, power, and latency numbers for express links at various distances. The net area saving argument (72 total links vs. 168 adjacent-only, saving 96 PHY modules / 48 mm^2) is the kind of bottom-line calculation that chip architects care about.

[S5] **Budget sweep analysis (Fig. 3) reveals the crossover budget.** This is a practically useful finding: express links require sufficient budget to avoid starving adjacent capacity. The identification of a 3x crossover point for dense workloads is directly usable for design-space exploration.

## Weaknesses

[W1] **No real hardware or FPGA emulation -- simulation only.** This is the elephant in the room for an ISCA/MICRO submission. The entire evaluation is BookSim cycle-accurate simulation, which is a standard NoC simulator, not a chiplet-specific one. Several concerns:

- BookSim models wormhole/virtual-channel routing in an idealized fashion. Real chiplet NoI has PHY-level effects (retimer latency, clock-domain crossing, credit-round-trip delays) that can dominate inter-chiplet latency at distance > 1. The paper assumes express link latency scales linearly as 2d cycles (Table VIII). In practice, a distance-3 express link on a real interposer may have non-linear latency due to signal integrity degradation, repeater insertion, and PHY resynchronization. Is 2d cycles validated against any physical model or measurement?

- BookSim does not model congestion at the PHY level (e.g., UCIe link-layer flow control, retry logic, CRC overhead). These effects are especially relevant for express links that traverse longer wires with higher BER.

- No comparison with CNSim (which the paper cites as a chiplet-specific cycle-accurate simulator). If CNSim is available and designed for chiplet networks, why not use it?

[W2] **Latency numbers lack absolute calibration.** The paper reports latency reductions as percentages (17-52%) but never states absolute latency values in cycles or nanoseconds. This makes it impossible to assess whether the baseline latency is already acceptable or whether the improvement matters for end-to-end application performance. For example:

- If baseline all-to-all latency at K=32 is 200 cycles and express links reduce it to 96 cycles, that is meaningful.
- If baseline latency is 2000 cycles and express links reduce it to 960 cycles, the system may still be bandwidth-bound rather than latency-bound, making the reduction less impactful.

Without absolute numbers and an end-to-end throughput or training-iteration-time analysis, the 52% claim floats in a vacuum.

[W3] **Traffic matrices are synthetic, not extracted from real workloads.** The five "LLM communication patterns" are described at the chiplet level (e.g., "MoE sends each token to top-2 remote experts") but appear to be generated synthetically based on pattern descriptions rather than extracted from actual profiling of real LLM training/inference runs. Specifically:

- What is the temporal behavior? Real LLM communication is bursty (all-reduce phases followed by compute-only phases). BookSim steady-state simulation with fixed injection rates does not capture this.
- What is the message size distribution? MoE dispatch sends variable-sized token batches; all-reduce has fixed-size gradient chunks. Are these modeled?
- The NL% values (42%, 49%, 88%, 89%, 90%) are suspiciously clean. Are these computed analytically from the pattern definition or measured from actual traffic traces?

[W4] **Only 5 workloads, and 3 of them cluster at NL > 85%.** The r=0.94 correlation is computed over 5 data points (per configuration), with 3 of them bunched at the high end (NL=88, 89, 90%). This is statistically fragile. With only 2 points in the NL < 50% range, the linear fit is driven by the cluster at the top. To convincingly demonstrate the NL% predictor, the paper needs workloads spanning the full NL% range more uniformly -- e.g., ring all-reduce (NL ~ 10-20%), nearest-neighbor stencil (NL ~ 0-5%), pipeline-parallel only (NL ~ 30%), and more intermediate values.

[W5] **Greedy placement scalability and optimality gap not characterized.** The paper states complexity is O(L * |C| * K^2 log K) per iteration and mentions ILP as future work (from iteration 7 discussions). For ISCA/MICRO, the following are expected:

- Runtime of the greedy algorithm for the evaluated configurations (seconds? minutes? hours?).
- How close is greedy to optimal? Even a small ILP formulation for K=16 would quantify the optimality gap.
- Does the greedy solution change across random seeds of the same traffic pattern? The paper mentions "Avg. 3 Seeds" in some tables but does not report variance.

[W6] **No comparison with state-of-the-art chiplet interconnect designs.** The paper compares against simple baselines (uniform, traffic-proportional, load-aware, MinMax adjacent) but not against published chiplet interconnect architectures:

- AMD Infinity Fabric topology for MI300X (8 XCDs with near-full connectivity). The paper mentions this in Related Work but does not simulate it.
- The paper cites Kite and Florets but only includes a "Kite-like" baseline (MinMax adjacent), not an actual reproduction of Kite's allocation algorithm.
- No comparison with concentrated mesh (cmesh) or hierarchical ring topologies that are used in practice.

[W7] **Express link routing assumes global Dijkstra recomputation.** The paper states routing is "Dijkstra shortest-path on the combined topology, re-computed after each express link addition." In a real system:

- Routing tables must be stored in each router. How much SRAM overhead does this add per router? In a K=32 system with express links, the routing table size grows significantly compared to dimension-order routing.
- Is the Dijkstra routing deadlock-free? The paper cites modular routing for deadlock-freedom but does not state whether the express topology uses virtual channels or turn restrictions for deadlock avoidance. BookSim supports VC-based deadlock avoidance, but this should be explicitly stated and validated.
- Adaptive routing with express links is non-trivial. The paper assumes static shortest-path routing, which may not be optimal under congestion.

[W8] **Missing comparison of express links vs. simply increasing adjacent link bandwidth.** The paper's cost argument is that express links achieve the same performance as adjacent-only at lower total link count. But a chip architect's real decision is: "Should I add express links, or should I use wider adjacent links (e.g., UCIe x16 instead of x8)?" This comparison is absent. Doubling adjacent link bandwidth is a straightforward design choice that does not require topology changes or Dijkstra routing.

## Questions for Authors

Q1. What is the absolute baseline latency (in cycles) for each workload at the maximum injection rate? Without this, the percentage improvements cannot be contextualized.

Q2. The express link latency model assumes 2d cycles for distance d. Is this validated against any physical signaling model? At distance 4 (40 mm wire on interposer), what is the expected signal propagation delay and does it fit within a 2-cycle budget at realistic clock frequencies (e.g., 2 GHz NoI clock)?

Q3. How are the traffic matrices generated? Are they steady-state or do they model the bursty nature of LLM communication (compute phases interlaced with communication phases)?

Q4. What is the variance across the 3 random seeds mentioned in Table V? If the greedy solution is sensitive to traffic perturbations, the placement may not be robust in practice.

Q5. Does the BookSim configuration use virtual channels? If so, how many VCs per port, and how is deadlock freedom ensured with the express link topology?

Q6. Why not use CNSim (cited as [10]) instead of or in addition to BookSim? CNSim is specifically designed for chiplet network simulation and would strengthen the evaluation.

Q7. The paper claims 72 total links vs. 168 adjacent-only at K=16 (Section 5.6). How are these numbers derived? If express links reduce total link count, what happens to the bisection bandwidth? Is bisection bandwidth preserved?

## Missing References

1. **NVIDIA NVSwitch / NVLink architecture** -- The most commercially successful multi-die interconnect. NVIDIA's approach to the same problem (full connectivity via NVSwitch) should be discussed as an alternative architectural solution.

2. **Intel EMIB and Foveros** -- Intel's multi-die interconnect technologies provide real-world data points for inter-chiplet link latency and bandwidth that could validate (or challenge) the paper's physical overhead estimates.

3. **Simba (JSSC 2019)** -- A 36-chiplet multi-chip module for deep learning with a mesh NoI. Directly relevant as a real-hardware data point for the chiplet count range this paper targets.

4. **FLAT (ISCA 2022)** -- Proposes a fully-connected last-level interconnect for chiplets, which is essentially the limiting case of express links (every pair connected). Comparison would contextualize the greedy approach.

5. **Clos/fat-tree topologies for chiplet interconnect** -- The paper only considers 2D mesh. Clos networks are widely used in practice and avoid the phantom load problem by construction via indirect routing.

## Detailed Comments (Section-by-Section)

### Abstract
The abstract is well-structured with the 1-2-3-4 story flow. The thesis ("express link benefit is determined by the workload's non-locality fraction") is stated clearly in the first paragraph. The specific numbers (17-52%, r=0.94) give concrete claims. Minor: the abstract claims "same link cost as adjacent-only baselines" but this needs careful qualification -- same total link count does not mean same cost, because express links have higher per-link wire area and power (Table VIII).

### Section 1: Introduction
Fig. 1 is well-placed and motivates the problem. The "phantom load" framing is effective. The three contributions are clearly stated. However, the introduction oversells the practical impact: "enables architects to predict express benefit from static traffic analysis alone" -- this is true for the NL% metric, but the actual placement still requires the greedy algorithm, which needs the full traffic matrix.

### Section 2: Related Work
Table I is a useful comparison, but the check-marks are self-serving. The paper claims all five check-marks while competitors get at most two. The "Multi-Workload" column is debatable -- Florets evaluates multiple CNN inference workloads. The "Scalability" column meaning is unclear -- does it mean multiple K values were tested? If so, Chiplet Actuary also scales across K values in its cost model.

### Section 3: Phantom Load Analysis
This is the paper's strongest section. The closed-form derivation is clean and the routing-algorithm independence study is convincing. Table III effectively shows that no routing algorithm eliminates phantom load. One concern: the numbers in Table III (Max alpha of 111, 223, 94, 347 for K=16) seem very different from Table II (Max alpha = 16 for K=16). The text should clarify that Table II uses the flow-counting model while Table III uses BookSim simulation with a specific mesh size -- this discrepancy is confusing without explanation.

### Section 4: Express Link Architecture
Algorithm 1 is clearly presented but lacks runtime analysis. The "traffic-proportional fallback" for remaining budget after greedy plateau is mentioned in the text but not shown in the algorithm pseudocode. The physical overhead analysis (Table VIII) is useful but uses CoWoS-class estimates without citing a specific source for the technology parameters (0.8 um pitch, 0.15 pJ/bit/mm). These numbers should be cited.

### Section 5: Evaluation
The evaluation setup is clearly described. The budget sweep (Fig. 3) is the most informative result. However:

- The injection rate sweep (1-4x base load) is mentioned in the setup but results are only shown at "maximum injection rate." Showing the full injection rate sweep for at least one workload would reveal whether express links help more at high or low loads.
- Table VI reports express saving as a single number per configuration. How was this computed -- at what injection rate and budget? The caption does not specify.
- Section 5.3 (adjacent-only ceiling) largely repeats Section 3 results. This could be tightened.

### Section 6: Conclusion
Concise and appropriate. The "NL% > 40%" threshold is a practical takeaway.

### Bibliography
13 references is thin for ISCA/MICRO. The missing references listed above would add depth and context. Several entries are incomplete (e.g., [2] "A. Smith et al." for MI300X -- this should cite the actual Hot Chips presentation with full author list).

## Rating

| Criterion | Score | Comment |
|-----------|-------|---------|
| Novelty | 3.0 | Phantom load characterization is clean; express links in NoC are well-studied (EVC, cmesh). The NL% predictor is the novel angle. |
| Technical Quality | 3.0 | Closed-form analysis is solid. BookSim evaluation is competent but lacks physical validation, absolute latency calibration, and statistical rigor (5 workloads, 3 seeds, no variance reported). |
| Significance | 3.0 | Important problem for future chiplet scaling. But without real-hardware or FPGA validation, the practical impact is uncertain. The 52% claim needs grounding in absolute numbers and end-to-end context. |
| Presentation | 3.5 | Well-written, clean structure, good figures. Some table inconsistencies (alpha values across tables). Thin bibliography. |
| Overall | 3.0 | Solid DATE/DAC paper. For ISCA/MICRO, needs real-hardware validation, wider workload coverage, and deeper comparison with production interconnect architectures. |
| Confidence | 4.0 | I have reviewed chiplet interconnect and NoC papers extensively. BookSim-only evaluation is a common weakness I have seen in this area. |

## Decision

**Borderline (leaning Weak Reject for ISCA/MICRO; Accept for DATE/DAC)**

The paper makes a clean, well-supported argument within its simulation-based scope. The phantom load characterization is a genuine contribution, and the NL% predictor is practically useful. However, for a top-tier architecture venue (ISCA/MICRO/HPCA), I expect:

1. **Real-hardware or FPGA validation** of at least the latency model (express link at distance 2-3 on a real interposer or FPGA emulation board).
2. **Absolute latency numbers** and their mapping to end-to-end application performance (e.g., training iteration time impact).
3. **Wider workload coverage** to strengthen the NL% correlation beyond 5 data points.
4. **Comparison with production interconnect designs** (NVLink/NVSwitch, Infinity Fabric topology, Simba mesh).
5. **Deadlock-freedom proof or protocol** for the express link routing.

For DATE/DAC/ICCAD, the paper is above the bar -- the analytical contribution alone (Theta(K) phantom load, routing independence, NL% predictor) is sufficient, and simulation-only evaluation is standard at those venues. I would score this **Weak Accept** for DATE/DAC.

For ISCA/MICRO, the gap between simulation and silicon is too large. The paper reads as a promising design-space exploration study, not a validated architectural proposal. The claims are simulation-contingent, and the systems community will ask: "Would this actually work on a real interposer?" The paper cannot answer that question today.
