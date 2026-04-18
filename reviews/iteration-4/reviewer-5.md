# Review -- Reviewer 5 (Skeptic), Iteration 4

## Summary

Fourth revision of a paper characterizing "phantom load" in chiplet mesh NoI. The paper provides closed-form amplification analysis (Theorem 1), routing-algorithm independence study, six LLM workload pattern analysis, five mitigation strategies, and BookSim cycle-accurate validation. Key changes from iteration 3: (1) Kite-like baseline now appears in the main BookSim dense-traffic table (Table VI), (2) the Table VII "Express (0 placed)" anomaly is now explained as non-uniform adjacent allocation causing router-level contention, (3) Guideline 3 physical overhead numbers are now consistent with Guideline 6, (4) abstract BW claim corrected, (5) AMD/NVIDIA commercial systems paragraph added.

## Assessment of Iteration-3 Blockers

### [BLOCKER 1] Kite-like baseline missing from main BookSim table (Table VI)

**RESOLVED.** This was my single most persistent complaint across iterations 2 and 3. The paper now includes Kite-like in Table VI (line 369):

```
K=16, L=72:
  Adj. Unif.  lat@0.01=54.3  lat@0.015=846  Peak Tput=0.0106
  Kite-like   lat@0.01=54.4  lat@0.015=846  Peak Tput=0.0104
  Express     lat@0.01=29.4  lat@0.015=37.6  Peak Tput=0.0200
```

This is a decisive result and actually *strengthens* the paper's argument far more than I anticipated. Kite-like (MinMax adjacent) is essentially identical to uniform at K=16: lat@0.01 of 54.4 vs 54.3, throughput of 0.0104 vs 0.0106. Both saturate catastrophically at rate 0.015 (latency 846 cycles). Express links, by contrast, maintain stable latency (37.6) at the same rate.

I had predicted based on the analytical model (rho_max 8.1 vs 6.6, a 1.2x gap) that the BookSim gap between Kite-like and Express would be small. I was wrong. The analytical model understates the gap. The reason is explained convincingly (line 375): "both adjacent uniform and Kite-like saturate identically at rate 0.01 -- confirming that even the optimal adjacent-only allocation cannot resolve phantom load, because the root cause (multi-hop routing) persists." The link-level analytical model captures the congestion ratio but misses the nonlinear saturation cliff that occurs when router buffers fill. At K=16, both adjacent strategies hit this cliff at virtually the same injection rate, while express links avoid it entirely by reducing hop count.

This is actually the most important datapoint in the paper. It definitively shows that adjacent-only optimization (Kite's approach) is fundamentally limited for K>=16 dense traffic -- not merely incrementally worse, but *identically* saturated. The gap between Kite-like and Express is not 1.2x but closer to 2x in throughput, and the latency gap at 0.015 injection is 22x (37.6 vs 846). This validates the paper's central thesis that topology intervention (express links) is qualitatively different from capacity redistribution.

**Verdict: Fully resolved.** The result is stronger than what I expected and eliminates my main concern. The paper should arguably highlight this finding more prominently -- the identical saturation of uniform and Kite-like is a striking result.

### [BLOCKER 2] Table VII "Express (0 placed)" anomaly

**RESOLVED.** The paper now explains (line 400): "Express (0 placed) shows slightly higher latency than uniform despite placing zero express links: this is because the greedy algorithm produces a non-uniform adjacent allocation (concentrating links on analytically high-load pairs), which can create router-level contention not captured by the link-level analytical model."

This is a satisfactory explanation. The greedy algorithm, by distributing adjacent-link budget non-uniformly based on link-level load analysis, inadvertently creates router-level hotspots that the link-level model does not capture. The MoE traffic pattern, being sparse and unpredictable, does not benefit from this concentration -- it actually suffers from it. The paper correctly identifies this as "a known gap between link-level and router-level modeling in BookSim."

The label "Express (0 placed)" is now understandable: it means "the greedy express algorithm was run, it chose to place zero express links, but it did distribute adjacent budget non-uniformly." It is not identical to "Uniform" because the adjacent allocation differs. The throughput gap (0.0150 vs 0.0229) is now explained rather than mysterious.

One minor observation: this result actually serves as additional evidence that for MoE traffic, *uniform allocation is the best strategy*. The paper could note this more explicitly -- even analytically-optimized adjacent allocation (Kite-like at 0.0212) and greedy-optimized allocation (0.0150) both underperform simple uniform (0.0229) for MoE. This reinforces Guideline 4's recommendation.

**Verdict: Resolved.** The explanation is physically plausible and internally consistent.

## Assessment of Other Iteration-3 Concerns

### [W3] Guideline 3 vs Guideline 6 physical overhead contradiction

**FIXED.** Guideline 3 (line 437) now reads: "Physical overhead for 10 express links: ~0.6% interposer area and ~2% TDP (see Guideline 6)." This is consistent with Guideline 6's numbers (0.56% area, 2.1% TDP). The old under-estimates (<0.5% area, <0.1% TDP) are eliminated.

**Verdict: Fixed.** No inconsistency remains.

### [W4] "10-30% communication time" unsubstantiated

**NOT ADDRESSED.** Line 455 still states: "communication can reach 10--30% of total time" for large-batch training, multi-query inference, and MoE dispatch without providing a supporting calculation. This is a minor concern -- the claim is qualitatively plausible, but a single back-of-envelope number (e.g., "for batch-256 all-reduce on K=16 with HBM bandwidth B and ring size K, communication fraction = ...") would make it rigorous. As-is, this remains hand-waved.

**Verdict: Not fixed, but downgraded to minor.** The qualitative argument is sound even without the exact number. The claim does not affect the paper's core contributions.

### [W5] Netlist generation underspecified

**NOT ADDRESSED.** The Limitations section (line 459) still honestly acknowledges "Traffic matrices are parameterized, not from production RTL" and "BookSim uses uniform-size chiplets." No new data on parameter sensitivity of the spectral clustering partitioner, module configurations, or how many random seeds were tested for netlist generation.

**Verdict: Not fixed, acknowledged in Limitations.** This is acceptable for a DATE paper. The analytical results (Theorem 1, routing independence, workload ranking) do not depend on the netlist generator. Only the absolute values in the BookSim tables depend on it, and the relative comparisons (uniform vs express, MoE vs dense) should be robust to reasonable parameter variation.

### AMD/NVIDIA commercial systems paragraph

**GOOD ADDITION.** The new Discussion paragraph (line 451) places the work in context of real products: MI300X (K=8, manageable regime), B200 (K=2, trivial), with the forward-looking prediction for K>=16. The mention that MI300X uses "effectively a fully-connected topology at small K" through Infinity Fabric is a nice touch that shows awareness of industrial practice. This addresses the earlier concern about disconnect from commercial reality.

## Remaining Concerns

### [RC1] Express vs Kite-like gap in analytical model vs BookSim (observation, not a blocker)

The analytical model predicted rho_max 8.1 (MinMax adj) vs 6.6 (Express) at K=16 -- a 1.2x gap. BookSim shows Kite-like and Uniform saturating identically, with Express providing ~2x throughput. The paper should briefly comment on this model-vs-simulation discrepancy. A single sentence like "The analytical model, being link-level, underestimates the saturation cliff that cycle-accurate simulation reveals" would suffice. The paper partially does this at line 375, but could be more explicit about the quantitative discrepancy.

### [RC2] Hybrid TP+MoE still lacks Express comparison in Table VII

Table VII (line 415-416) shows Hybrid TP+MoE with Uniform and Kite-like (both identical: lat=25.5, tput=0.0250) but not Express. This was flagged as [NC4] in iteration 3 and remains unaddressed. The hybrid case is the most practically relevant scenario (real LLM systems combine TP and MoE), so knowing whether express links help here would be valuable.

However, given that the hybrid traffic is apparently so light that both Uniform and Kite-like achieve identical performance at the tested injection rates, it is likely that the network is far from saturation and express links would show no measurable benefit. This makes the omission less problematic -- the result would likely be "all strategies identical for hybrid at this injection rate."

**Severity: Minor.** Not a blocker, but noting the omission for completeness.

### [RC3] Analytical model gap deserves a sentence in Limitations

The paper uses two levels of modeling: link-level analytical (rho_max) and cycle-accurate BookSim. The Kite-like result reveals that link-level rho_max is a poor predictor of absolute performance at saturation -- rho_max 8.1 vs 6.6 (1.2x) translates to identical throughput in BookSim. This is a methodological observation that deserves acknowledgment. The link-level model remains useful for *ranking* strategies (it correctly predicts Express > MinMax > Uniform) but not for *quantifying* the gap.

## New Strengths (Iteration 4)

1. **[S-new] Kite-like identical-saturation result is the paper's strongest finding.** The fact that optimal adjacent allocation (Kite-like) saturates at the exact same rate as naive uniform (0.0104 vs 0.0106 throughput, latency 846 vs 846 at rate 0.015) is a powerful, clean result. It proves that capacity redistribution among adjacent links is *futile* at K=16 for dense traffic -- only topology change (hop reduction) helps. This is the paper's sharpest contribution and should be positioned as such.

## Strengths (Consolidated)

1. [S1] **Kite-like vs Express BookSim result (new).** The identical saturation of adjacent strategies at K=16 is the most compelling evidence in the paper. It transforms the argument from "express is incrementally better" to "adjacent-only is fundamentally limited."
2. [S2] **Honest negative results (retained).** MoE zero express benefit, batch-1 near-zero E2E speedup, and traffic-proportional being worse than uniform. The paper is now genuinely balanced.
3. [S3] **Closed-form analysis (retained).** Theorem 1 with Theta(K) scaling and computational validation up to R,C<=8 is rigorous and elegant.
4. [S4] **Actionable guidelines (retained, improved).** Seven guidelines with consistent numbers (Guideline 3/6 contradiction fixed), clear workload conditions, and explicit negative recommendations.
5. [S5] **Counter-intuitive traffic-proportional result (retained).** Remains the paper's most memorable and practically useful finding.
6. [S6] **Commercial systems context (new).** AMD MI300X and NVIDIA B200 discussion grounds the work in industrial reality.

## Weaknesses (Consolidated)

1. [W1] **"10-30% communication time" still unsubstantiated.** No back-of-envelope calculation for when NoI becomes the bottleneck. Minor -- does not affect core contributions.
2. [W2] **Netlist generation underspecified.** Spectral clustering parameters and module configurations not detailed. Acknowledged in Limitations. Acceptable for DATE.
3. [W3] **Analytical model vs BookSim gap not explicitly discussed.** Link-level rho_max predicts 1.2x gap, BookSim shows identical saturation. The paper should note this discrepancy and explain that the analytical model correctly ranks strategies but underestimates the saturation cliff. Currently partially addressed but could be more explicit.
4. [W4] **Hybrid TP+MoE missing Express comparison.** Minor -- likely would show no difference at tested injection rates.

## Questions for Authors

1. [Q1] The Kite-like result shows identical saturation to Uniform at K=16. Does this hold at K=32? If MinMax adjacent is also identical to Uniform at K=32, the case for express links at scale becomes even stronger.
2. [Q2] For the "10-30% communication time" claim: what is the batch size threshold where communication crosses 10% of total time? Even a single data point would suffice.
3. [Q3] Have you tested express link placement with router-aware cost functions (accounting for buffer pressure) rather than link-level rho_max? Given the gap between analytical and BookSim results, a router-aware placement might further improve greedy express performance.

## Rating

- Novelty: 3.5/5 (up from 3.0; the Kite-like identical-saturation finding is a genuinely novel and significant observation that strengthens the characterization contribution)
- Technical Quality: 4.0/5 (up from 3.5; both blockers resolved, Kite-like BookSim result is the definitive experiment, Express-0-placed anomaly explained)
- Significance: 3.5/5 (up from 3.0; the Kite-like result elevates the paper from "incremental optimization paper" to "fundamentally new insight about adjacent-only limitations")
- Presentation: 4.0/5 (unchanged; well-structured, honest, consistent numbers)
- Overall: 3.75/5 (up from 3.5)
- Confidence: 4/5

## Decision

**Accept.** Both of my iteration-3 blockers are resolved, and the resolutions are substantive rather than cosmetic:

1. The Kite-like result in Table VI is the paper's strongest single datapoint. It shows that even optimal adjacent allocation (approximating Kite) provides *zero* improvement over naive uniform at K=16 -- both saturate at the same rate, both hit latency 846 at rate 0.015. This is a qualitatively stronger finding than I expected. My iteration-3 concern that "the practical case for express links is much weaker than presented" was based on the analytical model predicting a 1.2x gap. BookSim shows the gap is actually *larger* than claimed analytically -- express achieves 2x throughput while Kite-like provides nothing. The paper's thesis is validated more strongly than the authors' own analytical model predicted.

2. The Express (0 placed) anomaly is explained as non-uniform adjacent allocation causing router contention. This is physically plausible, internally consistent, and honestly reported as a modeling gap. The explanation also reinforces that uniform allocation is optimal for MoE traffic -- an additional practical insight.

The remaining weaknesses are all minor: the "10-30% communication time" hand-wave, underspecified netlists, and missing Hybrid Express comparison. None of these undermine the paper's core contributions. The characterization (phantom load definition, Theta(K) scaling, routing independence, workload vulnerability ranking) is rigorous and novel. The Kite-like saturation result transforms the mitigation contribution from "express links are incrementally better" to "adjacent-only strategies are fundamentally limited at K>=16" -- a much stronger and more publishable claim. The seven design guidelines are actionable and credible, bolstered by explicit negative results.

For a DATE paper, this is solid work. The combination of closed-form analysis, multi-dimensional characterization (routing, workload, mitigation), cycle-accurate validation with both positive and negative results, and practical design guidelines meets the bar. I recommend acceptance.
