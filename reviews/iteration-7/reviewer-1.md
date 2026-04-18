# Review -- Reviewer 1 (Architecture Expert), Iteration 7

## Summary
This paper identifies "phantom load" -- multi-hop routing traffic on intermediate chiplet links -- as a fundamental cost problem in chiplet Networks-on-Interposer (NoI). The closed-form analysis proves center-link amplification grows as Theta(K) for K-chiplet grids under XY routing, and this persists across four routing algorithms and six LLM communication patterns. The proposed solution, workload-aware greedy placement of express links, achieves the same latency target as adjacent-only topologies using up to 2.3x fewer inter-chiplet links on realistic 8x8 internal meshes. The paper validates across three mesh sizes, confirms workload-awareness (greedy places zero express links for sparse MoE traffic), and provides seven design guidelines.

## Editorial Fix Verification

**[Fix 1] "72 express links" -> "72 total links (including express)" / "72 total links (including ~19 express)".**
CORRECT. Two instances updated:
- Introduction (line 41): "only 72 total links (including express) suffice when they bypass the phantom load." This correctly distinguishes the 72 total links from the express subset, eliminating the misleading implication that all 72 are express links.
- Physical Overhead (line 346): "72 total links (including ~19 express) replace 168 adjacent-only links, saving ~96 PHY modules (~48 mm^2 PHY area)." The ~19 express count is consistent with the greedy algorithm placing a modest number of express links (cf. sensitivity analysis: "first 3--4 express links capture 60% of total improvement"). The remaining ~53 links are adjacent links with load-aware allocation. This is internally consistent and resolves the ambiguity I noted in iteration 6 about the composition of the 72-link budget.

**[Fix 2] Abstract "2.3x" -> "up to 2.3x".**
CORRECT. Abstract (line 28): "up to 2.3$\times$ fewer inter-chiplet links." This qualifier is appropriate because the 2.3x figure is specifically for the 8x8 internal mesh; the 4x4 mesh achieves 2.0x and the 2x2 mesh achieves only 1.0x (Table V). "Up to" accurately signals that 2.3x is the best case, not the universal case. This is a standard and appropriate qualifier.

**[Fix 3] Greedy suboptimality caveat in Section 5.2.**
CORRECT. Line 305: "The advantage is strongest at 2--4x budget per adjacent pair; at higher budgets (>=5x), the greedy algorithm's suboptimal placement can reduce the advantage (see Limitations)." This addition is well-placed -- it appears directly after the 2.3x claim for 8x8 mesh, providing immediate context rather than making the reader wait until the Limitations section. The cross-reference to Limitations is appropriate. The sentence correctly scopes the claim without undermining it: the 2--4x budget range is the practically relevant regime for most designs, and the greedy suboptimality at >=5x is acknowledged as a known limitation (with ILP as the suggested remedy in Limitations).

## Assessment

All three fixes are editorial in nature and correctly executed. No new technical content was added, and no existing content was altered beyond these three targeted changes. Each fix addresses a real (if minor) precision issue:
- Fix 1 eliminates a factual ambiguity about link composition.
- Fix 2 adds a standard qualifier to prevent overclaiming in the abstract.
- Fix 3 scopes the cost advantage claim to its strongest regime and acknowledges the known limitation inline.

No new issues introduced. The fixes do not create any inconsistencies with the rest of the paper.

## Residual Items from Iteration 6

For completeness, the three weaknesses I noted in iteration 6 remain:
- [W1] Kite-like comparison still missing for 8x8 mesh (opportunity, not flaw).
- [W2] Differential BW decay results still lack mesh size and metric specification.
- [W3] Ablation table still reports rho_max instead of link cost metric.

These are all minor presentation issues that I already downgraded in iteration 6. They do not affect the core claims. None of the three editorial fixes in this iteration were intended to address these items, and that is fine -- they are camera-ready polish items.

## Rating

- Novelty: 3.5/5
- Technical Quality: 4.5/5
- Significance: 4/5
- Presentation: 4/5
- Overall: 4.0/5 (Accept)
- Confidence: 5/5

## Score Justification vs Iteration 6

**All scores unchanged.** The three editorial fixes are precision improvements to existing text. They do not alter the paper's technical contributions, experimental scope, or overall presentation quality. The paper was at Accept in iteration 6 and remains so.

**Confidence increased from 4 to 5.** After seven iterations, I have thoroughly examined every claim, table, figure reference, and limitation in this paper. I am confident that the scores reflect the paper's quality and that no further iteration will change the assessment.

## Decision

**Accept** -- The paper is ready for submission. The three editorial fixes in this iteration are all correct and improve precision without introducing new issues. The paper presents: (1) a rigorous analytical framework for phantom load (Theta(K) scaling), (2) comprehensive validation across routing algorithms, workloads, and mesh sizes, (3) a definitive cost-performance result (up to 2.3x on 8x8 mesh), (4) validated negative results (MoE, traffic-proportional), and (5) honest limitations. No further revision is needed. The residual items (W1-W3 from iteration 6) are camera-ready polish and do not warrant another iteration.
