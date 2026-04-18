# Review -- Reviewer 5 (Skeptic), Iteration 2

## Summary
Revised paper characterizes "phantom load" in chiplet mesh NoI, derives closed-form amplification expressions, evaluates routing algorithms and LLM workload patterns, and proposes express (non-adjacent) links placed greedily. Claims 46% latency reduction and 90% throughput improvement at K=16 via BookSim.

## Assessment of Revisions Against Iteration-1 Concerns

### [W3] Max amplification inflated, avg not reported
**Partially addressed.** Table II now includes Avg alpha, Median alpha, and P95 alpha alongside Max alpha. This is a genuine improvement and makes the amplification story much more honest. For example, at K=16, max is 16.0 but avg is 13.3 and median 12.0---showing that the max is not wildly unrepresentative for square grids. However, the abstract still leads with "K/4 times" (the max formula) without mentioning average. The text at line 136 ("average amplification tracks max closely in square grids") partially acknowledges this, but the paper should be clearer that this convergence is a property of square grids specifically; for the 4x8 grid, max=64 vs avg=38.2, which is a 1.7x gap.

**Verdict: Mostly fixed.** The data is now present; the framing could be slightly more balanced.

### [W1] 90% throughput claim misleading (uniform baseline artifact)
**Partially addressed.** The paper now includes a "Note on link budget saturation" (Section V-A) explaining that each chiplet's 2x2 mesh limits adjacent links to 2 per pair, and that adjacent-only topologies saturate beyond ~2x #adj links. It also adds a "K=8big" configuration (line 363-364) where express still wins (5.2% throughput improvement, larger latency gains). This is an improvement---it demonstrates that even when the baseline is not artifactually bottlenecked, express links help.

However, the fundamental concern remains: the 90% throughput claim in the abstract is still driven by K=16 where the uniform baseline saturates at 0.0106 regardless of link budget (Table VII shows identical throughput for L=48/72/96---wait, actually the current Table VII is the new Table VI from the revision... let me re-check). Looking at Table VI (the BookSim table), uniform at K=16 L=72 peaks at 0.0106 while express achieves 0.0200. The "Note on link budget saturation" acknowledges this is a realistic constraint (die-edge PHY density), which is a reasonable argument. But the abstract's "90% throughput improvement" still reads as if express links double the network's capacity, when in reality they provide a way to bypass a physical saturation constraint. The distinction matters: this is not 90% improvement from better traffic management, it is 90% improvement from circumventing a connectivity bottleneck.

**Verdict: Partially fixed.** The explanation is reasonable but the framing remains aggressive. The abstract should qualify that this improvement occurs specifically because adjacent-only topologies saturate at K=16 due to die-edge PHY constraints.

### [W2] Cherry-picked K=16 hero result, K=8 weak
**Partially addressed.** The paper now explicitly states (line 372): "The K=8 improvement is modest (5--10%) because the 2x4 grid has shorter paths and fewer phantom links." The addition of K=8big (4x4 intra-chiplet mesh) showing throughput improvement (0.0229->0.0241, 5.2%) is helpful. The design guidelines (Section VI, Guideline 1) correctly stratify: K<=8 use load-aware allocation, K>=16 use express links.

But the abstract still leads with the K=16 result ("46% latency reduction and 90% throughput improvement at K=16") and the K=8 result is buried in a subordinate clause. For a DATE audience where K=8 is the current commercial reality (MI300X), this ordering is misleading. The abstract should lead with K=8 results and then present K=16 as a forward-looking result.

**Verdict: Partially fixed.** The honest discussion is present but the abstract framing still favors the hero result.

### [W4] No Kite/Florets comparison
**Not addressed.** The related work (Section II) discusses Kite and Florets qualitatively and Table I shows a checkbox comparison, but there is no quantitative comparison. The paper claims these are "adjacent-only" works, but Kite explicitly explores heterogeneous topologies with different link widths. It would be straightforward to take Kite's proposed topology for a comparable grid size and measure its phantom load properties. Without this, the claim of novelty ("first to characterize phantom load") remains unverified---Kite may already implicitly mitigate phantom load through its heterogeneous bandwidth allocation.

**Verdict: Not fixed.** This remains a significant gap. At minimum, the authors should run their phantom load analysis on Kite's published topologies.

### [W5] Netlist generator not validated
**Partially addressed.** The Discussion section (line 425) now explicitly states: "Our traffic matrices are generated from parameterized netlists; validation on production RTL traces would further strengthen results." The workload sensitivity study (Section III-D) with six LLM communication patterns partially addresses this by showing the analysis is not limited to one traffic model. The workload patterns themselves (ring all-reduce, tensor parallel, MoE, etc.) are well-known and not controversial.

However, the BookSim validation (Section V) still relies on synthetic netlists generated from a parameterized model. The paper does not specify the parameter ranges, how many different netlist configurations were tested, or how sensitive the results are to netlist parameters (only xcr sensitivity is shown). How many different module configurations were tried? Is the result robust to the number of compute vs. memory modules?

**Verdict: Partially fixed.** The honesty is appreciated but the underlying validation gap remains.

## Assessment of New Content

### Routing Algorithm Comparison (Table III)
This is a strong addition. The comparison of XY, YX, ECMP, and Valiant across three grid sizes is methodologically sound. The finding that ECMP reduces imbalance but cannot eliminate it (6.1x at K=32) supports the "routing-algorithm-independent" claim well. The inclusion of Valiant routing showing doubled total load is an honest and useful data point.

**One concern:** The Max alpha column shows extremely large numbers for Valiant (346.8 at 4x4, 417.4 at 4x8). This is because Valiant routes through random intermediaries, creating even more phantom load. But the paper does not discuss this: it focuses on imbalance reduction while ignoring that Valiant massively increases absolute load. The text says Valiant "doubles total network load" (line 158) which is correct, but the implication---that Valiant is a poor choice for phantom load mitigation despite reducing imbalance---deserves more emphasis.

### Workload Patterns (Table IV)
Methodologically sound. Six patterns covering the major LLM communication paradigms is comprehensive. The finding that MoE is most vulnerable (88% phantom links, 6.5x amplification) is well-supported by the sparse all-to-all nature of MoE routing. The ordering (Ring < Pipeline < Hybrid < Tensor < MoE) is intuitive and lends credibility.

**Minor concern:** These patterns are idealized. Real workloads mix patterns dynamically (e.g., tensor parallel within a stage, pipeline parallel across stages). The "Hybrid TP+PP" row partially addresses this but only for one specific mix. The sensitivity to the mixing ratio is not explored.

### Differential Bandwidth (Table V)
This is a useful and well-executed sensitivity study. The finding that express links remain effective at 50% bandwidth degradation (1.6-1.7x improvement) is practically relevant and non-obvious. The decay model B(d) = B_adj * gamma^(d-1) is reasonable for silicon interposer.

**Concern:** The gamma=0.50 case (50% decay per hop) for an express link at distance 3 would give B(3) = B_adj * 0.25. The paper does not clarify whether the decay is per-hop or total. If per-hop, distance-3 express links have 25% bandwidth, which might not be practically useful. The paper should clarify.

### Link Budget Saturation Explanation
The "Note on link budget saturation" (line 345) is a reasonable response to W1. The argument that die-edge PHY density physically limits adjacent links is valid. However, this raises a new question: if the PHY constraint is the fundamental bottleneck, then the paper's contribution is really about showing that express links bypass PHY constraints, not that they mitigate "phantom load" per se. The phantom load characterization is interesting but the practical solution (express links) works primarily because it sidesteps a different problem (PHY density). The paper conflates these two mechanisms.

## New Concerns

### [NC1] Greedy algorithm scalability claim not supported
The Discussion states greedy runs in 3 seconds for K=16 and 86 seconds for K=32. But Algorithm 1 is O(L * |C| * K^2) where |C| can be O(K^2) candidate pairs. For K=64, this could be hours. The paper waves this away with "candidate pruning by distance threshold" but does not demonstrate this or quantify the quality loss from pruning. For a paper targeting K=16-64, this is a notable gap.

### [NC2] Ten-seed robustness not shown in revision
The previous version reportedly had a 10-seed robustness test (my S3 from iteration 1 praised this). I do not see this in the current paper---was it removed? The claim "wins in 9/10 random seeds" (line 397) appears only as a brief mention without the full table. If the data was removed for space, a footnote pointing to supplementary material would be appropriate.

### [NC3] Multicommodity flow connection is shallow
Section VII-A states "Phantom load is the chiplet-NoI manifestation of flow congestion in multicommodity flow theory" and cites Leighton-Rao [13]. But the paper does not actually use any MCF results. The max-flow min-cut theorem could provide lower bounds on achievable congestion, which would let the authors prove their greedy solution is within a factor of optimal. Without this, the greedy algorithm has no approximation guarantee, and the Discussion acknowledges this. The MCF connection feels like name-dropping rather than a genuine theoretical contribution.

### [NC4] Missing comparison: MinMax adjacent + express
Table IV shows five strategies but express is only compared against adjacent uniform in BookSim (Table VI). What about MinMax adjacent in BookSim? If MinMax adjacent already captures most of the improvement (Table IV shows MinMax adj $\rho_{max}$=8.1 vs Express 6.6 at K=16, 3x budget---only 1.2x difference), then the practical benefit of express over the best adjacent strategy is much smaller than the 2x improvement claimed over uniform. The paper should run BookSim with MinMax adjacent as a baseline.

## Strengths (Retained and New)

1. [S1] **Comprehensive routing analysis (new).** The four-algorithm comparison in Table III is thorough and supports the structural claim convincingly.
2. [S2] **Honest reporting of averages (improved).** Table II now includes avg/median/P95 alpha. This significantly improves credibility.
3. [S3] **Workload diversity (new).** Six LLM communication patterns with clear vulnerability ordering.
4. [S4] **Differential bandwidth analysis (new).** Practical and non-obvious finding about bandwidth degradation tolerance.
5. [S5] **Counter-intuitive result on traffic-proportional allocation.** This remains the paper's most interesting finding and is well-demonstrated.

## Weaknesses (Summary)

1. [W1] **90% throughput claim still driven by baseline saturation.** The explanation is reasonable but the framing is still aggressive. (Partially fixed)
2. [W2] **Abstract still leads with K=16 hero result.** K=8 is the commercially relevant case. (Partially fixed)
3. [W4] **No quantitative Kite/Florets comparison.** (Not fixed)
4. [W5] **Synthetic netlists with limited parameter sensitivity.** (Partially fixed)
5. [NC4] **MinMax adjacent not tested in BookSim.** The gap between MinMax adj and Express in analytical model is only 1.2x; the 2x claim is against uniform, not the best adjacent strategy.

## Questions for Authors

1. [Q1] In Table V, is the bandwidth decay gamma per-hop or total? What is the effective bandwidth for a distance-3 express link at gamma=0.50?
2. [Q2] Why was MinMax adjacent not included in BookSim evaluation? The analytical model suggests the express vs. MinMax-adj gap is only ~1.2x.
3. [Q3] The 10-seed robustness data from the previous version---where did it go?
4. [Q4] For the MoE workload finding: have you tested with actual MoE routing decisions (e.g., from a Mixtral trace) rather than random sparse all-to-all?

## Rating

- Novelty: 3.0/5 (up from 2.5; routing analysis and workload study add genuine content)
- Technical Quality: 3.0/5 (up from 2.5; avg/median alpha, routing comparison, diff BW are solid additions; but Kite comparison still missing, BookSim baseline concern lingers)
- Significance: 3.0/5 (up from 2.5; workload analysis makes the relevance argument stronger, but K=8 results are still underwhelming for current industry)
- Presentation: 3.5/5 (unchanged; paper is well-written but abstract overclaims)
- Overall: 3.0/5 (up from 2.5)
- Confidence: 4/5

## Decision

**Borderline.** The revision substantively addresses the avg/median amplification concern and adds valuable content (routing comparison, workload patterns, differential bandwidth). The paper is significantly improved. However, two major concerns remain: (1) no quantitative Kite/Florets comparison, and (2) the 90% throughput claim is still primarily about bypassing PHY saturation rather than phantom load mitigation per se. The analytical contributions (closed-form expressions, workload vulnerability ranking) are the paper's real strength; the BookSim "hero numbers" in the abstract oversell the practical impact. If the abstract were toned down and a Kite comparison added, this would be a solid accept. As-is, it is borderline---the content is DATE-worthy but the framing still oversells.
