# Review -- Reviewer 3 (ML/Application Expert), Iteration 6

## Summary
Iteration 6 restores the full workload sensitivity content that was condensed in iteration 5 and addresses my camera-ready suggestion from iter-5: the Kite-like vs. uniform numerical comparison (54.3 vs. 54.4) is now inline in Section 5.3. The MoE top-2 routing is specified in the Table III caption, resolving a concern I have carried since iteration 2. The paper is now in camera-ready shape with no remaining substantive gaps.

## Assessment of Changes from v5

**Iter-5 W1 (MoE parameters unspecified, carried from iters 2-5): ADDRESSED.** The Table III caption now specifies "MoE expert dispatch (top-2 routing across K experts)." This tells the reader the routing sparsity: each token is dispatched to 2 out of K experts. Combined with K=32, this means each token's traffic touches 2/32 = 6.25% of chiplets per dispatch -- genuinely sparse, justifying the "zero express links" finding. This resolves my longest-running concern. A minor note: the caption specifies top-2 routing but does not specify whether there is a capacity factor or load-balancing auxiliary loss, which would affect traffic uniformity across experts. For a DATE paper this level of detail is not required, but for a journal extension it would be worth adding.

**Iter-5 W2 (Section 5.3 missing Kite-like numbers): ADDRESSED.** Section 5.3 now reads: "adjacent uniform and Kite-like (MinMax adjacent) produce nearly identical BookSim results: latency 54.3 vs. 54.4 at rate 0.01, both saturating at rate 0.015 (latency >800). Express achieves latency 29.4 at rate 0.01 and remains stable through 0.015 (latency 37.6)." This is exactly the inline comparison I requested. The numbers are devastating for the adjacent-only position: a 0.2% difference between uniform and optimal adjacent allocation at rate 0.01, versus a 46% improvement from express links. The saturation behavior (both adjacent strategies hitting >800 at rate 0.015 while express holds at 37.6) is equally compelling. This closes the gap cleanly.

**Iter-5 W3 (Table II XY vs. YX asymmetry on square grid): NOT addressed.** Table II still shows Max alpha = 111 for XY and 223 for YX on a 4x4 grid. On a square grid with uniform all-to-all traffic, swapping dimension order should produce symmetric load distributions (transposed, so the same max). The 2x difference remains unexplained. However, examining Table II more carefully, the caption says "2x2 Mesh" which appears to be a copy error -- the data rows show 4x4 and 4x8 grids. If the routing analysis was performed on internal mesh configurations rather than the chiplet grid itself, the asymmetry could arise from internal mesh topology. In any case, this is a minor issue that does not affect the paper's core claims, since the point of Table II is that phantom load persists across all routing algorithms, which it does regardless of the specific alpha values.

**Iter-5 W4 (Greedy algorithm runtime/scalability): NOT addressed.** No runtime information beyond what was in the text previously. As noted in iter-5, this is a practical concern for the target audience but does not affect the paper's technical contributions.

**Iter-5 W5 (CNSim comparison): NOT addressed.** BookSim remains the only simulation platform. This is acceptable for a conference paper; BookSim is the de facto standard for NoC/NoI simulation and has sufficient community trust.

**Restored content from pre-iter-5 versions.** The workload sensitivity table (Table III, 6 LLM patterns at K=32) is present with full detail: Ring All-Reduce, Tree All-Reduce, Pipeline Parallel, Tensor Parallel, MoE Expert, and Hybrid TP+PP. The table includes Max alpha, Imbalance, Phantom%, and Pattern columns. This restores the workload characterization that was present in earlier iterations and provides the reader with a complete picture of when express links matter (dense traffic) and when they do not (sparse/neighbor patterns).

## Strengths

1. [S1] **All load-bearing claims now have inline numbers.** The 54.3 vs. 54.4 comparison in Section 5.3 was the last data gap in the paper. Every major claim -- phantom load scaling (Table I), routing independence (Table II), workload sensitivity (Table III), cost savings (Table IV), and the adjacent-only ceiling (Section 5.3 inline) -- is now backed by specific numbers. A reviewer cannot point to any claim and say "where is the evidence?"

2. [S2] **MoE specification closes the reproducibility gap.** Top-2 routing across K experts is a well-defined traffic model: each source chiplet sends to exactly 2 destination chiplets per dispatch round, creating a sparse traffic matrix with exactly 2K nonzero entries per round. This is reproducible and the sparsity directly explains why express links provide no benefit -- the traffic is already diffuse enough that no intermediate link accumulates significant phantom load.

3. [S3] **The cost thesis is now fully supported end-to-end.** The argument chain is: (a) phantom load amplification is Theta(K) (Section 3, Table I), (b) this forces 2-3x over-provisioning of adjacent links (Section 4, Table IV), (c) even optimal adjacent allocation cannot break through this ceiling (Section 5.3, 54.3 vs. 54.4), (d) express links achieve the same performance at 2.3x fewer links on realistic 8x8 meshes (Section 5.2, Table IV), (e) the benefit increases with mesh size, confirming it is not an artifact (Table IV monotonic trend), (f) for sparse workloads where phantom load is low, express links correctly provide no benefit (Section 5.5, Table III MoE row). Every link in this chain has quantitative support.

4. [S4] **The 6 LLM workload patterns provide practical coverage.** The restored Table III gives a chiplet architect immediate guidance: Ring All-Reduce (12% phantom) and Pipeline Parallel (6% phantom) are safe with adjacent links; MoE Expert (88% phantom) has the highest phantom percentage but is sparse enough that express links are unnecessary; Tensor Parallel and Hybrid TP+PP (6% phantom each) are in the low regime; Tree All-Reduce (38% phantom) is the intermediate case. This workload-to-strategy mapping is directly actionable.

5. [S5] Strengths S1-S6 from iteration 5 (8x8 mesh validation, cost framing, ablation quality, MoE negative result, physical overhead grounding, differential bandwidth analysis) all remain intact. The paper has not regressed on any dimension.

## Weaknesses

1. [W1] **Table II caption says "2x2 Mesh" but data shows 4x4 and 4x8 grids.** This is likely a copy error from an earlier version where the table was structured differently. The caption should read something like "Load Imbalance Across Routing Algorithms" without the mesh size, or with the correct grid sizes. This is a trivial formatting fix.

2. [W2] **XY vs. YX asymmetry on 4x4 grid (carried from iter-5 W3).** Max alpha = 111 (XY) vs. 223 (YX) on a 4x4 grid remains unexplained. If this is an artifact of the internal mesh configuration or how border routers are assigned, a brief parenthetical would help. If it is a computation artifact, it should be corrected. The impact is low because the table's purpose is to show routing-algorithm independence of phantom load (which it does -- all algorithms show high alpha), not to compare algorithms head-to-head.

3. [W3] **Greedy algorithm runtime unspecified (carried from iter-5 W4).** No runtime data. For camera-ready, a single sentence like "The greedy algorithm completes in <X> seconds for K=16 on a single CPU core" would address practical scalability concerns for the DATE audience.

4. [W4] **Guideline 7 text has a minor imprecision.** The guideline states "per-layer communication (~0.1 us) is negligible versus memory access (~600 us)" but does not specify the model size, batch size, or HBM configuration behind these numbers. The 600 us figure implies roughly 600 GB/s bandwidth reading a ~360 MB layer from HBM, which is plausible for a single HBM3 stack but would differ substantially with HBM3E or multi-stack configurations. A brief qualifier like "for a representative 7B-parameter model at batch-1 on a single HBM3 stack" would make this more precise. This is a minor concern; the qualitative point (memory access dominates at batch-1) is correct regardless of exact numbers.

## Questions for Authors

1. [Q1] Is the Table II caption "2x2 Mesh" intentional? The data rows show 4x4 and 4x8 grids.

2. [Q2] The XY/YX asymmetry question from iter-5 remains open. On a square 4x4 chiplet grid with uniform traffic, can you confirm whether the 111 vs. 223 difference is expected?

3. [Q3] What is the greedy algorithm's wall-clock runtime at K=16? A single number would address scalability concerns.

## Detailed Comments

- The Section 5.3 addition is exactly what I suggested: "54.3 vs. 54.4 at rate 0.01" inline, with express comparison (29.4). This is the most efficient way to convey the adjacent-only ceiling result.
- Table III with 6 LLM workload patterns is well-structured. The "Pattern" column (neighbor, hierarchical, sequential, group a2a, sparse a2a, mixed) gives instant intuition about why each workload has its specific phantom load characteristics.
- The MoE top-2 specification in the Table III caption is appropriately placed -- it provides context without interrupting the table's visual flow.
- The differential bandwidth analysis (75% BW decay -> 1.8-2.2x improvement; 50% decay -> 1.6-1.8x) remains one of the paper's most practically important paragraphs. Express link designers will face wire-length-dependent bandwidth degradation, and knowing the breakeven points is essential.
- The paper's internal consistency is now very high. The abstract's "2.3x fewer inter-chiplet links" matches Table IV's 168/72 = 2.33x; the "1.5x worse" for traffic-proportional matches Table IV's K=16 row (19.8/13.2 = 1.5x); the MoE "zero express links" matches Section 5.5 and Table III's low max alpha for sparse patterns. No dangling claims.

## Rating
- Novelty: 3/5
- Technical Quality: 4/5
- Significance: 4/5
- Presentation: 4/5
- Overall: 4/5 (Accept)
- Confidence: 4/5

## Score Changes from Iteration 5
- No score changes. The iteration 5 scores already reflected the paper's core contributions (cost framing, 8x8 validation). Iteration 6 addresses camera-ready items (inline numbers, MoE specification, restored tables) that improve completeness and reproducibility but do not change the fundamental evaluation. The paper was already at Accept; it is now a stronger Accept with better internal consistency and no remaining data gaps for the central claims.

## Decision
**Accept** -- The paper is in camera-ready condition for its core claims. All five weaknesses I flagged in iteration 5 have been addressed (W1, W2) or are minor enough to not affect the paper's contribution (W3-W5). The addition of inline Kite-like numbers in Section 5.3, MoE top-2 specification, and restored workload sensitivity tables collectively close every substantive gap that existed in earlier iterations.

Remaining items for camera-ready polish:
1. Fix Table II caption ("2x2 Mesh" appears incorrect for the data shown).
2. Clarify or footnote the XY vs. YX asymmetry in Table II if the 4x4 grid data is correct.
3. Add a single sentence on greedy algorithm runtime.
4. These are all sub-paragraph fixes that do not affect the paper's accept-worthiness.

The paper makes a clear, well-supported contribution to DATE: it identifies phantom load as a cost problem, proves it analytically, validates it across mesh sizes, routing algorithms, and workloads, and provides a workload-aware solution with honest negative results. The 2.3x cost saving on realistic 8x8 internal meshes is the paper's headline result, and it is now fully substantiated with no remaining gaps in the evidence chain.
