# Review — Reviewer 1 (Architecture Expert), Iteration 1

## Summary
The paper identifies "phantom load" in chiplet NoI—multi-hop routing inflates intermediate link utilization by up to 200×—and proposes "express links" (non-adjacent direct connections) placed by a greedy congestion-minimizing algorithm. BookSim validation shows 46% latency reduction and 90% throughput improvement on a 16-chiplet grid.

## Strengths
1. [S1] **Phantom load is a real and well-characterized problem.** The observation that 50% of links in a 4×4 grid carry zero direct traffic yet are congested is compelling and quantitatively supported (Table II).
2. [S2] **The express link concept has a clean "leverage effect"**: 1 link relieves d-1 intermediate links. This is an elegant insight well-explained with figures.
3. [S3] **Comprehensive sensitivity analysis**: budget sweep, grid shapes, workloads, robustness across 10 seeds, diminishing returns. The paper leaves few stones unturned in evaluation.

## Weaknesses
1. [W1] **The idea of non-adjacent links is not new in NoC literature.** Express channels / bypass links have been extensively studied in on-chip networks (e.g., Kumar et al. "Express Virtual Channels" MICRO 2007, Grot et al. ISCA 2009). The paper does not cite or differentiate from this body of work. The novelty concern is significant.
2. [W2] **Synthetic netlists only.** All traffic matrices come from a custom netlist generator. No real accelerator workload traces (e.g., from actual GPU profiling, MLPerf traces, or even SPEC benchmarks). The 200× amplification claim may be an artifact of the synthetic traffic pattern.
3. [W3] **K=8 results are weak.** For K=8 (the most relevant current config—MI300X has 8 XCDs), express links show only 5% improvement and sometimes hurt peak throughput (K=8, L=30: 0.0201 vs 0.0226). The paper's hero result (90% @ K=16) is for a configuration that doesn't exist in production yet.
4. [W4] **No area/power overhead analysis for express links.** Long interposer wires consume routing resources, increase capacitance, and may require repeaters. The "Physical Feasibility" section is hand-wavy ("well within CoWoS capabilities") without quantitative analysis.

## Questions for Authors
1. [Q1] How does this differ from express virtual channels (Kumar et al. MICRO 2007) and concentrated mesh topologies? The concept of bypassing intermediate hops is well-established in NoC.
2. [Q2] What happens with adaptive routing instead of deterministic Manhattan routing? Phantom load distribution changes with routing algorithm—does the advantage hold?
3. [Q3] The 2×2 internal mesh per chiplet is tiny (4 routers). How do results change with realistic 8×8 or 16×16 intra-chiplet meshes?

## Missing References
- Kumar et al., "Express Virtual Channels: Towards the Ideal Interconnection Fabric," ISCA 2007
- Grot et al., "Kilo-NOC: A Heterogeneous Network-on-Chip Architecture for Scalability and Service Guarantees," ISCA 2011
- Balfour & Dally, "Design Tradeoffs for Tiled CMP On-Chip Networks," ICS 2006

## Detailed Comments
- **Section III-A**: System model is clean but oversimplified. Real chiplet systems have heterogeneous chiplet sizes (compute + I/O dies), which changes the traffic pattern fundamentally.
- **Section III-D**: The greedy algorithm is straightforward. O(L·K⁴logK) complexity is concerning for future larger grids—K=32 already takes 86 seconds.
- **Section IV**: The uniform baseline doesn't increase with budget (Table IV shows identical results for L=48/72/96). This seems like a bug—more links should help uniform too. If uniform can't utilize extra budget due to 2×2 mesh border constraints, that's a confound, not a fair comparison.

## Rating
- Novelty: 2/5
- Technical Quality: 3/5
- Significance: 3/5
- Presentation: 4/5
- Overall: 2.5/5
- Confidence: 4/5

## Decision
**Weak Reject** — The phantom load characterization is a genuine contribution, but the express link technique is too similar to well-known NoC concepts (express channels, bypass links) without adequate differentiation. The evaluation on synthetic workloads and the weak K=8 results further weaken the case.
