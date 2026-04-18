# Review -- Reviewer 1 (Architecture Expert), Iteration 6

## Summary
This paper identifies "phantom load" -- multi-hop routing traffic on intermediate chiplet links -- as a fundamental cost problem in chiplet Networks-on-Interposer (NoI). The closed-form analysis proves center-link amplification grows as Theta(K) for K-chiplet grids under XY routing, and this result is shown to persist across four routing algorithms and six LLM communication patterns. The proposed solution, workload-aware greedy placement of express links (direct non-adjacent connections), achieves the same latency target as adjacent-only topologies using 2.3x fewer inter-chiplet links on realistic 8x8 internal meshes. The paper validates across three mesh sizes, confirms workload-awareness (greedy places zero express links for sparse MoE traffic), and provides seven design guidelines for chiplet NoI architects.

## Assessment of Iteration-5 Concerns

**[W1] Kite-like baseline underspecified for 8x8 mesh.** PARTIALLY ADDRESSED. Section 5.3 now provides specific numerical comparison: "latency 54.3 vs. 54.4 at rate 0.01, both saturating at rate 0.015 (latency >800)." This is precisely the kind of number I asked for -- it proves quantitatively that Kite-like optimization saturates identically to uniform. However, this data is for the 2x2 internal mesh (L=72), not for the 8x8 mesh. My iteration-5 request was specifically for the 8x8 mesh result, since the paper's strongest claim is the 2.3x cost advantage at 8x8. The 2x2 number is helpful (it was missing entirely in iteration 5), but the gap remains: we do not see the Kite-like latency at 168 adjacent links on 8x8 mesh. That said, this is a minor concern -- the analytical argument that Kite-like is the best adjacent-only allocation is sound, and Table V already shows that 168 adjacent links are needed on 8x8 mesh. The numerical comparison on 2x2 is sufficient to establish the pattern.

**[W2] Ablation in wrong metric.** NOT ADDRESSED. Table VI still reports rho_max (congestion) values: random 85.4, uniform 62.8, fully-connected 39.0, greedy 15.3. The paper's core thesis is now framed in cost terms (links needed for target latency), but the ablation reports a different metric. I raised this specifically because iteration 4's MoE anomaly demonstrated that link-level congestion does not always predict cycle-accurate latency. However, for the ablation's purpose -- showing that placement strategy matters and random is worse than uniform -- the rho_max metric is directionally correct even if it is not the paper's primary currency. Downgrading from concern to minor issue.

**[W3] Differential BW decay lacks mesh size.** NOT ADDRESSED. Section IV still states "With 75% BW decay per hop distance, express still provides 1.8--2.2x improvement; at 50% decay, 1.6--1.8x" without specifying the internal mesh configuration. Since the paper now emphasizes that results must hold at realistic mesh sizes (the entire reframing hinges on the 8x8 result), leaving this unspecified is an inconsistency. However, the differential BW result is a robustness check, not a core claim, so the impact on the paper's main argument is limited.

**[W4] Routing table lacks mesh size.** ADDRESSED. Table III caption now reads "Load Imbalance Across Routing Algorithms (2x2 Mesh)." This clarifies that the routing independence results are from the 2x2 internal mesh. The analytical closed-form (Theorem 1, Eq. 2-3) is mesh-independent by construction, and the table serves as computational validation of the analytical result, so specifying 2x2 is appropriate.

**[Minor 1] Table II analytical vs. BookSim.** Implicitly clarified by the routing table caption specifying "2x2 Mesh" -- this indicates it is a simulation result, not purely analytical. Still, an explicit note would be cleaner.

**[Minor 2] BW improvement metric ambiguity.** NOT ADDRESSED. "1.8--2.2x improvement" in Section IV still does not specify improvement in latency, congestion, or link cost.

**[Minor 3] Abstract mesh size specification.** NOT ADDRESSED. The abstract still claims "2.3x fewer inter-chiplet links" without noting this is for 8x8 internal mesh. However, the abstract now adds "validated in BookSim cycle-accurate simulation across 2x2, 4x4, and 8x8 internal mesh configurations," which gives the reader context that multiple configurations were tested. This is an acceptable alternative to specifying the exact mesh for the 2.3x claim.

## New Content Assessment

**F_H row-independence explanation (Theorem 1).** Good addition. "F_H is independent of row position because XY routing performs all horizontal movement at the source row, so every row contributes equally to horizontal link load" is a concise and correct explanation for why the formula depends only on column position. This addresses a potential reader confusion about why a 2D formula has only 1D dependence.

**Net PHY saving calculation (Section V-G).** Strong addition. "72 express links replace 168 adjacent links, saving ~96 PHY modules (~48 mm^2 PHY area)" transforms the physical overhead discussion from a cost justification into a net savings argument. This is the right framing for a cost-focused paper: express links are not an overhead to tolerate but an investment that pays back through total link reduction.

**Greedy suboptimality acknowledgment (Limitations).** Appropriate. "The greedy algorithm shows suboptimal behavior at very high budgets (>=5x per pair) on 8x8 meshes; ILP formulation could improve this" is an honest limitation disclosure that also points toward future work. This does not undermine the core contribution because the paper's main results operate at more moderate budget levels.

**BookSim store-and-forward caveat.** Good addition. "BookSim models internal mesh as store-and-forward routers, not the high-speed crossbars used in real chiplets; absolute latencies for 8x8 are thus inflated, though relative comparisons remain valid." This preempts a potential reviewer objection about the absolute latency numbers for 8x8 mesh being unrealistically high.

**Full-length restoration.** The paper now reads as a complete characterization study. Restoring Table IV (mitigation comparison), Table VI (ablation), sensitivity analysis paragraphs, and the MoE validation section gives the paper the depth expected at a top-tier venue. The iter-5 version, while cleaner, was too lean for a conference paper that claims breadth across routing algorithms, workloads, mesh sizes, and mitigation strategies. This version strikes the right balance.

## Strengths

1. [S1] **The cost-performance framework is now the paper's backbone.** Every major result is presented in terms of "links needed for target latency": Table V (cost to achieve target latency across mesh sizes), Fig. 3 (latency vs. total link count), and the central 2.3x claim. This consistency makes the paper's contribution clear and directly usable by practitioners.

2. [S2] **The 8x8 internal mesh result remains the definitive empirical contribution.** The 2.3x cost advantage at border=8/edge, where adjacent links have ample capacity, is now presented alongside the full spectrum (1.0x at 2x2, 2.0x at 4x4, 2.3x at 8x8). The monotonic increase with mesh size is both counterintuitive and important: more border capacity does not help adjacent-only topologies because the bottleneck is topological (phantom load), not capacity-related.

3. [S3] **Counter-intuitive results are preserved and well-presented.** Traffic-proportional allocation being 1.5x worse than uniform (Table IV), Kite-like saturating identically to uniform at K=16 (Section 5.3 with specific numbers), and express links being useless for MoE (Section 5.5) -- these three results collectively demonstrate that the paper provides genuine insight rather than an obvious optimization.

4. [S4] **The analytical framework is now tighter.** The F_H row-independence explanation in Theorem 1, the explicit connection between alpha_max and cost provisioning (end of Section 3.2), and the scaling table (Table I) validated for all R,C <= 8 give the analytical contribution a level of rigor appropriate for a characterization paper.

5. [S5] **Completeness of the design space exploration.** Five mitigation strategies (Table IV), four routing algorithms (Table III), six LLM workloads (Table II), three internal mesh sizes (Table V), and placement ablation (Table VI) -- the paper covers the design space thoroughly without feeling bloated. Each table answers a distinct question.

6. [S6] **Honest limitation disclosure.** The greedy suboptimality at high budgets, BookSim's store-and-forward assumption, parameterized traffic matrices, and XY/uniform assumption in closed-form are all acknowledged. The paper does not overclaim.

## Weaknesses

1. [W1] **Kite-like comparison is still missing for 8x8 mesh.** Section 5.3 provides the 54.3 vs. 54.4 comparison for 2x2 mesh at L=72, which is helpful. But the paper's headline claim is at 8x8 mesh where 168 adjacent links are needed. Does Kite-like achieve any improvement over uniform at 8x8? If Kite-like and uniform are equally poor at 8x8 (as expected from the analytical argument), stating this explicitly with a number would be the final nail in the adjacent-only coffin. This is a missed opportunity rather than a flaw -- the analytical argument is sufficient, but the empirical confirmation would be stronger.

2. [W2] **Differential bandwidth decay results (Section IV) still lack mesh size and metric specification.** The "1.8--2.2x improvement" at 75% BW decay and "1.6--1.8x" at 50% are stated without specifying (a) which internal mesh size, and (b) improvement in which metric (latency, rho_max, or link cost). For a paper that has carefully specified mesh sizes in every other table caption, this omission stands out. This is minor because BW decay is a robustness check, not a core result.

3. [W3] **Ablation table reports rho_max instead of the paper's core cost metric.** Table VI shows congestion values but the paper's thesis is about link cost. This creates a minor disconnect. Converting to "links needed for target latency" format would align with the rest of the paper. However, rho_max is a reasonable proxy for the ablation's purpose (demonstrating that placement strategy matters), so this is a presentation issue rather than a technical one.

## Questions for Authors

1. [Q1] What is the Kite-like (MinMax) latency for K=16 with 8x8 internal mesh at 168 links? If it matches uniform (as expected), stating the specific number would complete the argument. If it does not match (i.e., Kite-like achieves some improvement at 8x8), that would be an interesting nuance worth discussing.

2. [Q2] For the BW decay analysis in Section IV: what internal mesh size was used, and is "1.8--2.2x improvement" in rho_max or latency?

## Minor Issues

- Section IV BW decay: specify mesh size and metric.
- Table VI: consider adding a column for BookSim latency at a reference injection rate to complement rho_max.
- The abstract now mentions "2x2, 4x4, and 8x8 internal mesh configurations" which provides sufficient context for the 2.3x claim. No change needed.

## Rating

- Novelty: 3.5/5
- Technical Quality: 4.5/5
- Significance: 4/5
- Presentation: 4/5
- Overall: 4.0/5 (Accept)
- Confidence: 4/5

## Score Justification vs Iteration 5

**Novelty unchanged at 3.5.** No new conceptual contributions in iteration 6. The additions (F_H explanation, net PHY saving, greedy suboptimality caveat, BookSim store-and-forward note) are refinements of existing content.

**Technical quality unchanged at 4.5.** The 8x8 result -- the single most important technical contribution -- was already present in iteration 5. The Kite-like numbers for 2x2 mesh (54.3 vs. 54.4) are a welcome addition that was missing in iteration 5, though the 8x8 Kite-like number is still absent. The F_H row-independence explanation and greedy suboptimality acknowledgment strengthen the analytical presentation. The BookSim store-and-forward caveat is good practice. Overall, the technical substance is solid and no new concerns have emerged.

**Significance unchanged at 4.** The full-length restoration gives the paper the depth expected of a characterization study, but does not change the fundamental contribution. The net PHY saving calculation (96 modules saved) is a nice addition that strengthens the cost argument, but the 2.3x cost advantage was already the core claim.

**Presentation unchanged at 4.** The full-length version is better suited for a conference paper than the lean iteration-5 version. The restored tables (mitigation comparison, ablation, workload sensitivity) give the reader the complete picture without feeling padded. However, the two residual issues -- BW decay lacking mesh size/metric, and ablation reporting rho_max instead of link cost -- prevent a score increase. These are minor and do not impair readability, but they are inconsistencies in an otherwise carefully constructed paper.

**Overall unchanged at 4.0.** The paper was at Accept in iteration 5 and remains so. Iteration 6 is a merger of iteration-5's cost-efficiency thesis with iteration-4's full content, and the combination works well. The paper is now a complete, well-argued characterization study with a clear thesis (phantom load creates a 2-3x cost ceiling), a definitive empirical result (2.3x on 8x8 mesh), validated edge cases (MoE, BW decay, grid shape), and honest limitations. The remaining weaknesses (W1-W3) are minor presentation issues that do not affect the core claims or their validity.

## Decision

**Accept** -- This iteration successfully merges the cost-efficiency framing of iteration 5 with the full content depth of iteration 4. The result is a complete characterization paper with: (1) rigorous analytical foundations (Theta(K) scaling with F_H row-independence explanation), (2) comprehensive design space exploration (five strategies, four routing algorithms, six workloads, three mesh sizes), (3) a definitive cost-performance result (2.3x on 8x8 mesh), (4) validated negative results (MoE, traffic-proportional), and (5) honest limitations (greedy suboptimality, BookSim modeling). The residual weaknesses are presentation inconsistencies (BW decay mesh size, ablation metric) rather than technical gaps. The paper is ready for DATE publication. No further iteration is needed -- the remaining items are camera-ready polish, not substantive revisions.
