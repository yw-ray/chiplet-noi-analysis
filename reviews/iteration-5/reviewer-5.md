# Review -- Reviewer 5 (Skeptic), Iteration 5

## Summary

Major revision of the paper, now reframed around cost-efficiency with the title "Breaking the Cost-Performance Ceiling of Chiplet Networks with Express Links." The central claim is now that express links achieve the same latency target using 2.3x fewer inter-chiplet links, validated across 2x2, 4x4, and 8x8 internal meshes in BookSim. The paper has been substantially restructured: the old multi-table characterization format (Tables VI--VIII, seven guidelines, etc.) is replaced with a streamlined cost-performance narrative. New experiments include 8x8 internal mesh sweeps (addressing my iteration-1 concern about 2x2 being unrealistic), a cost-to-target table (Table III), and a differential bandwidth analysis. The MoE negative result is retained. The abstract and introduction are now organized around the "phantom tax" framing.

This is a much-improved paper compared to iteration 4. The reframing is intellectually sharper, the 8x8 experiments are a necessary addition, and the cost-to-target comparison is the right way to present the results. However, I have identified a significant problem in the 8x8 experimental data that the paper does not disclose, and the bold title claim requires careful scrutiny.

## Assessment of Iteration-4 Concerns

### [RC1] Analytical model vs BookSim gap (observation from iter-4)

**PARTIALLY ADDRESSED.** The paper no longer highlights the Kite-like vs Express analytical-vs-BookSim discrepancy as a separate finding. Instead, the adjacent-only ceiling is presented empirically: "Adjacent uniform and Kite-like produce nearly identical performance despite MinMax's optimal allocation" (line 241). This is cleaner. However, the gap between the link-level model (rho_max) used by the greedy algorithm and the cycle-accurate BookSim behavior remains unacknowledged in the methodology. The Limitations section (line 284) mentions "The greedy algorithm shows suboptimal behavior at very high budgets (>=5x per pair) on 8x8 meshes" which is a new and important admission -- more on this below.

### [RC2] Hybrid TP+MoE Express comparison (minor, iter-4)

**DROPPED.** The new paper structure no longer includes the per-workload BookSim table (old Table VII). Hybrid TP+MoE is no longer discussed. This is acceptable given the restructured scope, though it means the paper loses one of its more practically relevant scenarios.

### [W1] "10-30% communication time" unsubstantiated (iter-4)

**IMPROVED.** Guideline 7 (line 276) now frames this more carefully: "per-layer communication (~0.1 us) is negligible versus memory access (~600 us)" for batch-1 decode, and "Phantom load mitigation matters for communication-heavy regimes: large-batch training, multi-query inference." The specific "10-30%" claim is removed. This is a better framing -- it identifies the regime qualitatively without making an unsubstantiated quantitative claim. Not ideal (a worked example would still be better), but acceptable.

### [W2] Netlist generation underspecified (iter-4)

**UNCHANGED.** Line 198: "Traffic matrices are generated from synthetic accelerator netlists with balanced spectral partitioning." No parameters given. Line 284: "Traffic matrices are parameterized, not from production RTL." Acknowledged in Limitations. Acceptable for a conference paper.

### My iter-1 blocker: 2x2 internal mesh unrealistic

**ADDRESSED.** This was my original concern from iteration 1 -- that 2x2 internal mesh (2 border routers per edge) creates an artificial bottleneck that inflates the express link advantage. The paper now includes 4x4 and 8x8 internal meshes, with the 8x8 being "the critical test" (line 217). This is exactly the experiment I asked for. The question is whether the results support the claim.

## Critical Analysis of the 8x8 Internal Mesh Data

This is the core of my review. The paper's headline claim is: "express links achieve the same performance as adjacent-only topologies at 2-3x lower link cost" (line 47), and the 8x8 mesh is presented as the definitive validation ("the critical test", line 217). I have examined the underlying experimental data carefully.

### What the paper reports (correctly)

- At 72 links (3x/pair), express achieves 194 vs adjacent's 446 latency at rate 0.005. This is a 2.3x advantage. (Line 217)
- To match express at 72 links (~200 latency), adjacent must use ~168 links. Hence 2.3x cost saving. (Table III, line 232)

These numbers are accurate per the data.

### What the paper does not report (the reversal problem)

Examining the full 8x8 budget sweep from the experimental data:

| Budget (links) | Budget/pair | Adj Lat @0.005 | Expr Lat @0.005 | Express advantage |
|----------------|-------------|-----------------|------------------|-------------------|
| 24 | 1x | 387.4 | 387.4 | 1.00x (identical, 0 express placed) |
| 48 | 2x | 663.2 | 218.0 | 3.04x better |
| 72 | 3x | 564.5 | 186.8 | 3.02x better |
| 96 | 4x | 483.4 | 187.3 | 2.58x better |
| **120** | **5x** | **338.6** | **431.4** | **0.79x -- express is WORSE** |
| **144** | **6x** | **236.2** | **444.6** | **0.53x -- express is MUCH WORSE** |
| 168 | 7x | 201.2 | 112.4 | 1.79x better |
| 192 | 8x | 168.4 | 109.5 | 1.54x better |

**At 5x budget (120 links), express latency is 431.4 vs adjacent's 338.6 -- express is 27% worse.**

**At 6x budget (144 links), express latency is 444.6 vs adjacent's 236.2 -- express is 88% worse.**

This is a dramatic non-monotonicity. Express latency at 120 links (431.4) is actually *higher* than at 48 links (218.0). Adding more links makes express *worse*. Then at 168 links, it suddenly recovers to 112.4. This is not a minor fluctuation -- it is a factor-of-2 reversal in the 5-6x budget range.

The paper acknowledges this in the Limitations section with a single sentence: "The greedy algorithm shows suboptimal behavior at very high budgets (>=5x per pair) on 8x8 meshes---ILP formulation could improve this" (line 284). This is insufficient disclosure for a finding that directly contradicts the paper's headline claim. The paper states "express links achieve the same performance as adjacent-only topologies at 2-3x lower link cost" -- but at 5-6x budget, express achieves *worse* performance at the *same* cost. The 2.3x cost saving claim holds only at specific budget points, not across the full operating range.

### Possible explanations for the reversal

1. **Greedy algorithm pathology.** At high budgets, the greedy algorithm may be allocating too many express links (40 express links at 5x, 48 at 6x) and too few adjacent links, creating internal mesh bottlenecks at the border routers that serve express link endpoints. The data shows 21 express pairs at 5x/6x but suddenly 22 at 7x/8x -- the pair count is similar, but the link count per pair increases dramatically (40, 48, 55, 63). This suggests the greedy algorithm keeps piling links onto the same express pairs rather than diversifying, creating PHY-level bottlenecks.

2. **BookSim anynet routing artifacts.** With 8x8 internal mesh (64 routers per chiplet, 1024 total routers), the anynet topology with long-distance express links may cause routing pathologies in BookSim's "min" routing algorithm. The router receiving traffic from a long express link may become a hotspot if multiple express links terminate at the same border router.

3. **Traffic matrix interaction.** The random traffic matrix (seed 42) may create an unfortunate interaction with the greedy-selected express pairs at these budget levels.

Regardless of the cause, this is a **methodological problem** that undermines the generality of the 2.3x claim. The paper cherry-picks the 3x budget point (where express wins convincingly) for the headline number and buries the 5-6x reversal in a single Limitations sentence.

### The 8x8 adjacent latencies are also problematic

Adjacent uniform latencies at rate 0.005 on the 8x8 mesh range from 168 to 663 cycles. For comparison, 2x2 latencies at the same rate are 27-33 cycles. This is a 6-20x increase.

Some of this is expected: 8x8 internal mesh means packets traverse more internal hops. But a latency of 663 cycles at 48 links (2x/pair) for a 4x4 chiplet grid suggests the network is heavily congested even at a very low injection rate (0.005). The throughput numbers confirm this: at 48 links, adjacent achieves only 0.00158 throughput vs the injected 0.005 -- the network is saturated at 32% of the injection rate. At 24 links, throughput is 0.000406 -- barely 8% of injection.

This raises a question: **are the 8x8 BookSim configurations realistic, or are they dominated by internal mesh congestion that dwarfs the inter-chiplet phantom load effect?** The paper's thesis is about inter-chiplet link cost. If the dominant bottleneck in the 8x8 simulations is internal mesh congestion (1024 routers with limited bisection bandwidth), then the latency numbers do not meaningfully reflect inter-chiplet topology decisions.

The paper could address this by reporting internal-only latency (intra-chiplet traffic) separately from end-to-end latency. If internal latency is, say, 150 cycles for 8x8, then a total latency of 187 (express at 72 links) would mean only ~37 cycles of inter-chiplet overhead -- and the 564 (adjacent at 72 links) would mean ~414 cycles of inter-chiplet overhead. That would validate the express link story. But without this decomposition, we cannot distinguish inter-chiplet phantom load effects from internal mesh saturation artifacts.

## Assessment of the Title Claim

"Breaking the Cost-Performance Ceiling" is a bold title. Let me evaluate whether the evidence supports it.

**For the claim:**
- At 2-4x budget on 8x8, express consistently outperforms adjacent by 2.3-3.0x in latency. This is a clear and reproducible advantage.
- On 4x4 internal mesh, express outperforms across all budget points tested (though by varying margins).
- The analytical foundation (Theta(K) phantom load) is solid and provides a clear mechanism.
- Table III's cost-to-target comparison (72 vs 168 links for ~200 latency) is a clean result.

**Against the claim:**
- At 5-6x budget on 8x8, express performs *worse* than adjacent. This is not "breaking a ceiling" -- it is creating a new ceiling.
- The 2.3x claim relies on a specific budget/rate combination (72 links at rate 0.005). At rate 0.01, the comparison shifts (express 194.2 vs adjacent 445.7 -- still favorable but the target latency in Table III would change).
- The claim "2.3x fewer links" in the abstract is stated as if it is a general result. It is actually the 8x8-mesh, 3x-budget, rate-0.005 comparison point.
- The 8x8 latency magnitudes (200-600 cycles) are an order of magnitude higher than 2x2 (28-36 cycles). Whether these represent realistic operating points for production chiplet systems is questionable.

**Verdict on the title:** The evidence supports a claim like "express links can significantly reduce link cost at moderate budgets" but not the stronger "breaking the cost-performance ceiling" language, because the data shows a reversal at higher budgets that creates its own ceiling. The title should be softened, or the 5-6x reversal should be prominently analyzed (not relegated to a Limitations footnote).

## Physical Cost Accounting Gap

The paper's cost framing counts inter-chiplet links as the cost metric. But express links at distance d require longer interposer wires than adjacent links. Section V.F (line 254) estimates 56 mm^2 for 10 express links at average distance 2.5. This is presented as "modest" (0.56% of interposer area).

However, the cost comparison in Table III is purely link-count based: 72 express links vs 168 adjacent links. The interposer area comparison should be: 72 links * (average distance of express links) vs 168 links * 1 hop. If express links average distance 2.5 and we assume area scales linearly with wire length, then 72 * 2.5 = 180 wire-distance-units vs 168 * 1 = 168 wire-distance-units. The express configuration actually uses *more* interposer routing area than the adjacent configuration.

Wait -- not all 72 express links are long-distance. Let me recalculate from the data: at budget 72 (3x), the greedy places 17 express pairs with 19 express links (out of 72 total), so 53 are adjacent. At max_dist=3, express links are distance 2 or 3. Assuming average distance 2.5 for express and 1 for adjacent: 53 * 1 + 19 * 2.5 = 100.5 wire-distance-units. The adjacent-only 168 links: 168 * 1 = 168. So express uses less wire overall. But this is for the 72-link express configuration, not a like-for-like comparison.

The paper should include this wire-length-adjusted cost comparison explicitly in Table III. As it stands, the "2.3x fewer links" claim implicitly assumes all links have equal cost, which is precisely what the express link concept violates.

## Assessment of Other Changes

### Streamlined structure
The paper is now significantly shorter and more focused. The old seven guidelines are condensed to a single Design Guidelines section with numbered items. The routing algorithm independence table (old Table II) is retained. The workload sensitivity table (old Table III) is retained at K=32. The cost-performance experiment replaces the old Tables VI-VIII. This is a better structure for the revised thesis.

### MoE negative result retained
Section V.E (line 248) correctly reports that greedy places zero express links for MoE. The old anomaly about "Express (0 placed)" being worse than uniform appears to be absent from this version, which is an improvement -- the paper no longer needs to explain that artifact.

### Differential bandwidth
Section V.G (line 258): "With 75% bandwidth decay per hop distance, express still provides 1.8-2.2x improvement; at 50% decay, 1.6-1.8x." This is a useful robustness check, though the "improvement" metric should specify what is being compared (express vs adjacent at what budget level?).

### Ablation
Section V.D (line 245): Random express worse than adjacent uniform (85.4 vs 62.8 congestion); greedy outperforms fully-connected by 2.5x. These are stated without specifying the internal mesh size or budget. At what configuration? These numbers cannot be from the 8x8 data where latencies are 100-600 cycles and "congestion" is not the metric used elsewhere. This appears to be carryover from earlier iterations with different experimental setups. If so, it should be updated to use the current cost-performance framework.

## Strengths

1. [S1] **The cost framing is the right framing.** Measuring "how many links to achieve target latency" rather than "how much faster at same budget" is the more actionable question for architects. Table III directly answers the cost question. This is the paper's most significant improvement over iteration 4.

2. [S2] **8x8 internal mesh experiments address the core validity concern.** My iteration-1 objection that 2x2 mesh creates artificial border bottlenecks is directly addressed. The paper tests with 8 border routers per edge, which is generous capacity. The express advantage persisting at 3-4x budget on 8x8 meshes is genuine evidence that phantom load is the bottleneck, not border capacity.

3. [S3] **Analytical foundation remains solid.** Theorem 1 with Theta(K) scaling, Table I with validated numbers up to 8x8, and routing algorithm independence (Table II) are clean, reproducible results that do not depend on BookSim configuration choices.

4. [S4] **Honest about limitations.** The Limitations paragraph (line 283) acknowledges parameterized traffic, closed-form assumptions, and the greedy algorithm's high-budget pathology. This is better than many papers.

5. [S5] **MoE workload-awareness.** The greedy algorithm placing zero express links for MoE and the paper correctly framing this as workload-aware design (not a limitation) is intellectually honest and practically useful.

## Weaknesses

1. [W1] **8x8 express link reversal at 5-6x budget is inadequately disclosed and analyzed.** This is the most significant weakness. The express strategy performs dramatically worse than adjacent uniform at budget_per_pair 5-6x (latency 431/445 vs 339/236). A single sentence in Limitations is insufficient for a result that directly contradicts the headline claim. This non-monotonicity should be presented in the main results, analyzed for root cause, and the 2.3x claim should be qualified with its applicable budget range.

2. [W2] **The 2.3x cost claim is cherry-picked from a specific operating point.** The 72 vs 168 comparison in Table III is real, but the paper presents it as a general result. At higher budgets (5-6x), the cost advantage disappears and reverses. The claim should be stated as: "At moderate link budgets (2-4x per pair), express links achieve the same latency at 2-3x fewer links. At higher budgets (>=5x), the greedy algorithm's express placement degrades, and adjacent brute-force becomes competitive."

3. [W3] **8x8 absolute latencies are unrealistically high, raising questions about simulation fidelity.** Latencies of 200-600 cycles at injection rate 0.005 on a 4x4 chiplet grid with 1024 internal routers suggest the network is permanently saturated. Either the traffic intensity is too high for this topology size, or the internal mesh is creating a bottleneck that dominates inter-chiplet effects. The paper does not decompose latency into internal vs inter-chiplet components, making it impossible to isolate the phantom load effect from internal mesh congestion.

4. [W4] **Link-count cost metric ignores wire length.** Table III reports "72 express vs 168 adjacent links" as a 2.3x cost saving. But express links at distance d consume d times more interposer routing resources per link. The paper should report wire-length-adjusted cost alongside link count. Section V.F's area estimate (56 mm^2 for 10 express links) is not integrated into the Table III cost comparison.

5. [W5] **Ablation numbers (Section V.D) appear disconnected from the current experimental framework.** The congestion values (85.4, 62.8, 15.3, 39.0) do not correspond to any metric used in the cost-performance tables. These seem to be from a different experimental setup. They should be updated or removed.

## Questions for Authors

1. [Q1] **Critical:** Can you provide the full 8x8 latency-vs-budget curve (all 8 budget points) for both strategies? The paper currently shows only the figure reference (Fig. 1) and selected text comparisons, but not the reversal at 5-6x budget. A table or figure showing the complete sweep would allow readers to see both the express advantage at low budgets and the reversal at high budgets.

2. [Q2] **Critical:** What causes the non-monotonicity in 8x8 express performance? At budget 120 (5x), express uses 40 express links across 21 express pairs; at 144 (6x), 48 express links across 21 pairs. The link-per-express-pair ratio increases from 1.9 to 2.3. Is the greedy algorithm concentrating too many links on the same express pairs, overwhelming the border routers at those endpoints?

3. [Q3] Can you decompose the 8x8 latency into intra-chiplet hop latency (baseline for a packet traversing from source to border router to destination) and inter-chiplet overhead? This would establish whether the 200-600 cycle latencies are dominated by the 8x8 internal mesh (expected: ~20-30 hops * ~5 cycles = 100-150 cycles internal) or by inter-chiplet congestion.

4. [Q4] For Table III, can you report the total interposer wire length (in mm or hop-distance-units) alongside link count? E.g., for the 72-link express configuration: 53 adjacent + 19 express at avg distance 2.5 = 100.5 wire-units. For the 168-link adjacent: 168 wire-units. This would give a wire-adjusted cost saving of 1.67x rather than 2.3x.

5. [Q5] The ablation section reports "congestion 85.4 vs 62.8" -- what metric is this, and at what configuration?

## Minor Issues

- Abstract line 30: "validated in BookSim cycle-accurate simulation across 2x2, 4x4, and 8x8 internal mesh configurations" -- the validation should note that the advantage does not hold uniformly across all budget levels on 8x8.
- Introduction line 41: "168 adjacent links --- while only 72 links suffice when express links bypass the phantom load" is accurate for the specific target latency but should note this is the ~200-cycle target at rate 0.005.
- Line 237: "The cost advantage *increases* with internal mesh size" -- this is true at 3x budget but false at 5-6x budget. The statement should be qualified.
- The paper no longer reports the Kite-like vs Uniform identical-saturation result that was the strongest finding of iteration 4. Section V.C (line 239) mentions it in passing but does not give numbers. This was the most compelling datapoint in the previous version and should not have been downgraded.

## Rating

- Novelty: 3.5/5 (up from 3.5; the cost framing is genuinely more useful than the previous characterization framing, but the core contribution is unchanged)
- Technical Quality: 3.0/5 (down from 4.0; the 8x8 reversal problem is a significant gap in the experimental analysis that was not present when the paper only used 2x2)
- Significance: 3.5/5 (unchanged; the cost framing makes the work more actionable, but the 8x8 validity questions reduce confidence)
- Presentation: 3.5/5 (down from 4.0; the streamlined structure is better, but selective presentation of 8x8 results is a presentation integrity issue)
- Overall: 3.25/5 (down from 3.75)
- Confidence: 4.5/5 (up from 4; I have now examined the raw data)

## Decision

**Weak Accept, conditional on addressing W1-W2.**

Let me be clear about what has improved and what has regressed.

**Improved:** The cost framing is right. The 8x8 experiments address my long-standing validity concern about 2x2 internal mesh. The streamlined structure reads better. The MoE handling is clean. The Theta(K) analysis and routing independence remain strong.

**Regressed:** The 8x8 experiments, while necessary, reveal a problem that the paper inadequately addresses. At 5-6x budget per pair, express links perform dramatically worse than adjacent (up to 88% higher latency). This is not a minor artifact -- it occurs over a significant portion of the budget sweep and represents exactly the kind of non-robust behavior that an architect would encounter when following the paper's guidelines at higher link budgets.

The paper acknowledges this in one sentence in Limitations and proposes ILP as future work. This is insufficient. A paper titled "Breaking the Cost-Performance Ceiling" cannot have a region of its operating space where the proposed approach creates a *lower* ceiling than the baseline.

**What would move this to Accept:**
1. Present the full 8x8 budget sweep data (not just the favorable 3x point) in a table or figure.
2. Analyze the root cause of the 5-6x reversal (greedy algorithm pathology vs BookSim artifact vs fundamental limitation).
3. Qualify the 2.3x claim with its applicable range: "at moderate budgets (2-4x per pair), express links save 2-3x in link cost. At higher budgets, the greedy placement algorithm degrades and adjacent brute-force becomes competitive. An ILP formulation may extend the advantage."
4. Either soften the title or show that the reversal is an algorithm problem (not a fundamental express link limitation).

I want to emphasize: this is a good paper that has improved substantially over five iterations. The analytical contribution (Theta(K) phantom load, routing independence, workload sensitivity) is publishable on its own. The cost framing is the right framing. The 8x8 experiments were necessary and are valuable even when they reveal problems. But the paper's headline claim must be supported by the full data, not a selected subset. If the authors present the reversal honestly and qualify the claim, this is an accept from me. In its current form, the selective presentation is a concern.
