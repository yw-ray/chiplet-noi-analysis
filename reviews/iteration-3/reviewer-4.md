# Review -- Reviewer 4 (Theory/Analysis Expert), Iteration 3

## Summary
This paper characterizes "phantom load" in 2D mesh chiplet Network-on-Interposer (NoI), provides closed-form flow-count expressions under XY routing with uniform all-to-all traffic, proves Theta(K) center-link amplification in square grids, demonstrates routing-algorithm independence across four algorithms, and evaluates workload sensitivity across six LLM communication patterns. The mitigation design space exploration compares five strategies, with express links providing 2.0--2.6x improvement for dense traffic and load-aware adjacent allocation shown sufficient for sparse MoE workloads. BookSim cycle-accurate simulation validates both the dense and sparse regimes.

## Response to Iteration-2 Concerns

**[W1] Proof sketch incomplete (F_H independence from r).** The revision now states Theorem 1 as "Under XY routing with uniform all-to-all traffic," which implicitly scopes the result. However, the proof sketch still does not explicitly explain *why* F_H(r,c) is independent of r. The text says "the source is at row r" but the formula uses R (total rows) rather than any function of r. The reason -- under XY routing, horizontal traversal occurs at the source row, so *every* row contributes the same number of flows crossing a given column boundary -- remains unstated. This is a minor expository issue, not a correctness issue. The computational validation for R,C <= 8 is sufficient to confirm correctness. **Partially addressed; acceptable for a conference paper.**

**[W2] Eq. 4 derivation not shown.** Still not shown explicitly: the step from F_H_max = 2R * ceil(C/2) * floor(C/2) to alpha_max = R * ceil(C/2) * floor(C/2) via division by 2 direct flows. The qualification that "2 direct flows" means one directed flow per direction under all-to-all traffic is still implicit. **Minor; does not affect the result's validity.**

**[W3] No closed-form for ECMP.** Not addressed in the revision. The paper still relies on empirical ECMP results (Table III). As noted previously, the ECMP closed form is derivable via binomial path-counting on a grid. This remains a missed opportunity to strengthen the routing-independence claim with theory. However, the empirical evidence across four routing algorithms is sufficient for a characterization paper. **Acknowledged as future work; acceptable.**

**[W4] No LP lower bound.** Not addressed directly. The greedy-vs-fully-connected comparison (Table VIII, greedy 15.3 vs fully-connected 39.0) serves as an empirical proxy. The fully-connected bound is loose (spreads budget across all O(K^2) pairs), so we still do not know greedy's proximity to optimal. However, the 2.5x advantage over fully-connected suggests greedy is reasonably effective. For a characterization paper (not an optimization paper), this is an acceptable resolution. **Acknowledged; acceptable given the paper's scope.**

**[W5] Theory-to-practice bridge.** Improved. The design guidelines section (Section VI) now provides seven actionable rules mapped to workload characteristics and grid sizes. Guideline 1 explicitly connects the closed-form amplification (Eqs. 2--3) to design decisions (alpha_max < 5 vs > 10 thresholds). Guideline 4 connects workload sparsity to strategy selection, validated by the MoE BookSim experiment. The connection between Theorem 1's center-link identification and greedy's placement behavior is now implicitly supported by the "6/7 top links target chiplet 13" observation. **Substantially addressed.**

## New Additions Evaluated

**MoE BookSim validation (Table IX).** This is a valuable addition. The finding that greedy places zero express links for MoE traffic -- confirming that express links are workload-dependent, not universally beneficial -- is a strong empirical result. The Kite-like baseline showing similar performance to uniform for MoE further validates that adjacent-only strategies are sufficient for sparse patterns. This directly addresses a concern from earlier iterations about the generality of express link recommendations.

**Kite-like (MinMax adjacent) baseline.** Including this as an upper bound on adjacent-only strategies is methodologically sound. It demonstrates that the limitation of adjacent-only approaches at K >= 16 is fundamental, not an artifact of suboptimal allocation. The comparison in Table IX (MoE) shows Kite-like performing comparably to uniform for sparse traffic, which is the expected behavior.

**Physical overhead quantification (Guideline 6).** The CoWoS-based quantification (56 mm^2, 15W for 10 express links) grounds the design recommendations in physical reality. The percentages (0.56% area, 2.1% TDP) are useful for practitioners. Minor concern: the 0.8 um wire pitch and UCIe Standard PHY assumptions should be cited more precisely (which CoWoS generation? which UCIe revision?).

**E2E model (Guideline 7 and Discussion).** The observation that batch-1 LLM decode has negligible communication (~0.1 us) versus memory access (~600 us) is important for setting realistic expectations. This prevents over-selling the phantom load mitigation. The identification of communication-heavy regimes (large-batch training, multi-query inference) as the target is well-motivated.

## Remaining Strengths

1. [S1] **Theorem 1 is correct and useful.** The closed-form F_H(r,c) = 2R(c+1)(C-c-1) is a clean, practically applicable result. The Theta(K) amplification bound for square grids is the paper's core theoretical contribution and it stands.

2. [S2] **Routing independence is convincingly demonstrated.** The four-algorithm comparison (XY, YX, ECMP, Valiant) at three grid sizes provides sufficient empirical evidence that phantom load is structural. The Valiant load-doubling observation is particularly insightful.

3. [S3] **Counter-intuitive results are the paper's practical value.** Traffic-proportional allocation being 1.5x worse than uniform, and express links being unhelpful for MoE, are both non-obvious findings that will save chiplet designers from costly mistakes.

4. [S4] **Workload-dependent design guidelines are actionable.** The seven guidelines in Section VI, particularly the K <= 8 vs K >= 16 threshold and the dense-vs-sparse strategy selection, are directly usable by practitioners.

5. [S5] **BookSim validation covers both positive and negative cases.** Showing both where express links help (dense traffic, 46% latency reduction) and where they do not (MoE, zero express links placed) is more convincing than showing only positive results.

## Remaining Weaknesses

1. [W1] **The ECMP closed form remains a gap.** The paper claims phantom load is "routing-algorithm-independent" but proves it only for XY routing. The ECMP and Valiant evidence is empirical. For a theory-focused characterization paper, this is the most notable missing piece. However, the empirical evidence at multiple grid sizes is sufficiently convincing for practical purposes. This is a clear direction for a journal extension.

2. [W2] **No formal optimality bound for greedy.** The comparison against fully-connected (2.5x better) is a loose proxy. Without an LP relaxation lower bound, we cannot state whether greedy captures 60% or 95% of the optimal improvement. For the paper's scope as a characterization (not optimization) paper, this is acceptable. The greedy algorithm is positioned as a practical tool, not an algorithmic contribution.

3. [W3] **The Leighton-Rao MCF connection is still under-cited.** The bibliography includes [14] (mcf_theory) but the Related Work section does not reference it in the main text. A single sentence acknowledging that phantom load is the chiplet-NoI manifestation of multicommodity flow congestion, with a citation to [14], would strengthen the theoretical positioning. The Discussion mentions this connection but Related Work does not.

4. [W4] **Table III YX anomaly unexplained.** YX routing shows exactly 2x the XY values across all metrics for every grid size. This systematic doubling is suspicious and deserves a one-sentence explanation. If it is because YX loads vertical links first (which are fewer in a 2x4 grid, or longer-dimension links carry proportionally more traffic), stating this would remove ambiguity. As-is, a reader might question whether the YX implementation is correct.

## Minor Issues

- Guideline 6: "0.56% of 100x100 mm^2" -- specify whether this is CoWoS-L or CoWoS-S and which technology node, since wire pitch and PHY area vary significantly.
- The MoE BookSim table (Table IX) shows "Express (0 placed)" performing worse than Uniform (lat@0.01: 36.2 vs 33.4). If greedy placed zero express links, the resulting topology should be identical to some adjacent allocation. Clarify what adjacent allocation the "Express (0 placed)" row uses -- is it load-aware adjacent? If so, it should match or beat uniform, and the discrepancy needs explanation.
- Algorithm 1: The re-routing step (Dijkstra) after each addition makes the algorithm O(|C| * L * K^2 log K). For K=32, this is feasible (86s reported) but the complexity should be stated.

## Questions for Authors

1. [Q1] In Table IX, "Express (0 placed)" has higher latency than Uniform despite the greedy algorithm choosing not to place express links. Does this mean the adjacent allocation within the greedy framework differs from uniform? If greedy simply defaults to uniform when no express links are placed, the numbers should match.

2. [Q2] The 3-4 express links capturing 60% of improvement (Guideline 3) -- is this a general result or specific to the K=16, L=72 configuration? Does this diminishing-returns curve shift for different grid sizes?

## Rating

- Novelty: 3/5 (unchanged: the closed-form theorem and routing independence are genuine but the underlying theory is standard MCF analysis applied to a specific domain)
- Technical Quality: 3.5/5 (unchanged: correct analysis, thorough empirical evaluation, proof exposition still has minor gaps)
- Significance: 4/5 (up from 3.5: the MoE BookSim validation, physical overhead quantification, and E2E model collectively make the guidelines significantly more actionable)
- Presentation: 4/5 (unchanged: well-written, clear tables, seven design guidelines are well-organized)
- Overall: 3.5/5 (unchanged numerically, but confidence in the result is higher)
- Confidence: 5/5 (up from 4: three iterations have fully clarified the paper's scope and contributions)

## Decision

**Weak Accept.** The iteration-3 revision addresses my remaining concerns adequately for a conference paper. The MoE BookSim validation (zero express links placed for sparse traffic) and the E2E application model (communication negligible for batch-1 inference) demonstrate intellectual honesty and practical maturity that were missing in earlier iterations. The physical overhead quantification with CoWoS specs grounds the recommendations in reality.

The theoretical gaps identified in iteration 2 -- no ECMP closed form, no LP lower bound, incomplete proof exposition -- remain. However, I now view these as journal-extension material rather than conference-blocking deficiencies. The paper's contribution is clear: it is the first systematic characterization of phantom load in chiplet NoI, with a correct Theta(K) scaling result, routing-algorithm independence demonstrated across four algorithms, workload sensitivity across six patterns, and actionable design guidelines validated by cycle-accurate simulation. The counter-intuitive findings (traffic-proportional is worse; express links hurt for MoE) have genuine practical value.

**What would elevate to Accept:** (1) A one-sentence explanation in the proof sketch for why F_H is independent of r; (2) cite Leighton-Rao [14] in Related Work, not just the bibliography; (3) explain the Table IX "Express (0 placed)" latency discrepancy. These are all minor fixes achievable in camera-ready.
