# Review -- Reviewer 5 (Skeptic), Iteration 3

## Summary
Third revision of a paper characterizing "phantom load" in chiplet mesh NoI with closed-form amplification analysis, routing-algorithm independence study, six LLM workload patterns, five mitigation strategies, and BookSim cycle-accurate validation. Key changes from iteration 2: toned-down abstract leading with characterization, MoE BookSim validation showing zero express-link benefit (honest negative), Kite-like baseline (MinMax adj) in BookSim evaluation, physical overhead with CoWoS specs (0.56% area, 2.1% TDP), E2E analysis showing ~0% speedup for batch-1 inference, and seven design guidelines including when express links do NOT help. The conclusion now explicitly states "express links are not universally beneficial."

## Assessment of Iteration-2 Concerns

### [W1] 90% throughput claim still driven by baseline saturation
**ADDRESSED.** The abstract no longer leads with the 90% hero number. It now opens with the characterization ("We identify and characterize the phantom load problem... phantom load amplification grows quadratically with grid size") and defers the BookSim numbers to a subordinate position ("validated by BookSim (46% latency reduction at K=16)"). The 90% throughput figure now appears only in the BookSim results section (line 351) and the conclusion, not the abstract. This is a significant improvement in framing. The saturation explanation ("Note on link budget saturation") remains, which is fine -- it is honest rather than hidden.

**Verdict: Fixed.** The framing is now appropriate.

### [W2] Abstract still leads with K=16 hero result
**MOSTLY ADDRESSED.** The abstract now leads with the characterization story: quadratic scaling, routing-algorithm independence, workload sensitivity. The K=16 BookSim result appears as validation of the broader analytical findings, not the headline claim. The abstract now also mentions the negative result: "For sparse workloads like MoE, load-aware adjacent allocation is sufficient." This is much more balanced than iterations 1 and 2.

However, the abstract still does not mention the K=8 result at all. Given that K=8 is the current commercial reality (MI300X), a single clause like "improvements are modest at K=8" would complete the honest picture.

**Verdict: Mostly fixed.** The abstract is now defensible, though adding a K=8 note would be ideal.

### [W4] No quantitative Kite/Florets comparison
**SUBSTANTIALLY ADDRESSED.** This was my biggest complaint in iteration 2. The paper now includes:
1. A "Kite-like" baseline (MinMax adjacent allocation) in the BookSim MoE evaluation (Table IX, line 411): Kite-like shows lat@0.01=34.2, tput=0.0212 vs. Uniform at 33.4/0.0229 for MoE traffic.
2. The Discussion (line 450) explicitly explains the Kite relationship: "Our MinMax adjacent strategy approximates this approach -- it finds the optimal link allocation among adjacent pairs."
3. Most importantly, the Kite-like baseline is present in the MoE table, showing that for sparse MoE traffic, Kite-like is actually *worse* than uniform (tput 0.0212 vs 0.0229), presumably because MinMax over-optimizes for a congestion pattern that does not match MoE's sparse structure.

**However**, I notice a significant omission: the Kite-like baseline does NOT appear in the main BookSim results table (Table VI, line 358). For the dense traffic case at K=16 where the paper claims 2.0x improvement from express links, we still do not know how Kite-like (MinMax adj) performs in BookSim. The analytical model (Table V) showed MinMax adj rho_max=8.1 vs Express 6.6 at K=16 (3x budget) -- only a 1.2x gap. If this 1.2x gap holds in BookSim, then the practical benefit of express over the best adjacent strategy shrinks from the claimed 2x to a modest 1.2x. The paper conveniently tests Kite-like only in the MoE scenario where it looks bad, not in the dense-traffic scenario where the comparison is most critical.

**Verdict: Partially fixed.** The Kite-like baseline is present but strategically placed only in the MoE table. The critical comparison -- Kite-like vs Express for dense traffic in BookSim -- is still missing.

### [W5] Synthetic netlists with limited parameter sensitivity
**PARTIALLY ADDRESSED.** The Limitations section (line 456) is now more explicit: "Traffic matrices are parameterized, not from production RTL. BookSim uses uniform-size chiplets." The workload sensitivity (Section III-D, six patterns) provides broader coverage. The xcr sensitivity mention (line 422: "for dense traffic xcr 0.1--0.6, express maintains 3.8--4.5x rho_max advantage") gives some parameter sensitivity.

But the underlying issue remains: we do not know the netlist generation parameters, how many module configurations were tested, or how the spectral clustering partition quality affects results. The reproducibility gap persists.

**Verdict: Partially fixed.** Honest acknowledgment, but no new data.

### [NC4] MinMax adjacent not tested in BookSim
**PARTIALLY ADDRESSED but with a twist.** MinMax adjacent (Kite-like) is now in BookSim -- but only for MoE traffic (Table IX). For the main dense-traffic results (Table VI), it is still absent. See [W4] above. This is the single most important missing comparison in the paper. If the authors are confident express links significantly beat MinMax adj in BookSim, they should show it. If the gap is small, they should be honest about it.

**Verdict: Partially fixed.** The omission of Kite-like from Table VI is suspicious.

## Assessment of New Content

### MoE BookSim Validation (Table IX) -- Honest Negative Result
This is the single best addition in the revision. The finding that express greedy places ZERO express links for MoE traffic -- and that all strategies perform similarly for sparse patterns -- is a mature, honest result that significantly strengthens the paper's credibility. It shows the framework can identify when its own proposed solution does not work. The "Express (0 placed)" row at lat@0.01=36.2, tput=0.0150 is interesting: the express algorithm, by placing zero express links, actually has *worse* throughput than uniform (0.0229). This deserves explanation -- if zero express links are placed, why is performance different from uniform? Is this a routing artifact? A link allocation difference?

**Concern (NEW): Express (0 placed) worse than Uniform for MoE.** Table IX shows Express at lat@0.01=36.2, tput=0.0150 versus Uniform at 33.4/0.0229. If the greedy algorithm places zero express links, the topology should be identical to some adjacent-only configuration. The 34% throughput gap (0.0150 vs 0.0229) is large. Something is wrong -- either the "0 express placed" configuration is not equivalent to uniform (perhaps the remaining budget is allocated differently), or there is a bug. The paper should explain this discrepancy.

### Kite-like Baseline in MoE Table
See [W4] above. The Kite-like result for MoE (lat@0.01=34.2, tput=0.0212) is interesting but the absence of Kite-like from the main table is a glaring omission.

### Physical Overhead (Guideline 6)
The CoWoS specification numbers (0.56% area at 56 mm^2, 2.1% TDP at 15W) are a meaningful addition. The honesty is appreciated -- "modest but non-negligible" is the right framing. However:
- **0.56% area**: For 10 express links at average distance 2.5 on a 100x100 mm^2 interposer. The calculation is not shown. At 0.8 um wire pitch with UCIe Standard PHY, what width and how many wires per link? This should be a footnote at minimum.
- **2.1% TDP**: 15W for 10 express links on a 700W TDP budget. This seems reasonable but the per-link power breakdown is not given. UCIe Standard PHY power is ~0.5 pJ/bit; at what bandwidth does 15W emerge?
- **The TDP number is higher than previously claimed** (iteration 2 said "<0.1% TDP"). This correction is honest and important. It means express links have a real power cost that should be weighed against the throughput benefit, especially for edge or power-constrained deployments.

### E2E Analysis (Guideline 7 and Discussion)
The E2E analysis showing ~0% speedup for batch-1 inference is another honest, credibility-building result. The numbers are straightforward: 0.1 us communication vs. 600 us memory access means NoI optimization is irrelevant for batch-1. The paper correctly identifies the communication-heavy regimes (large-batch training, multi-query inference, MoE dispatch) where phantom load matters.

**Concern:** The paper claims "communication can reach 10--30% of total time" for these regimes but does not provide supporting numbers. A simple roofline-style analysis (e.g., for batch-256 with all-reduce every N layers) would substantiate this claim. Without it, the 10-30% range is hand-waved.

### Design Guidelines (Section VI)
The seven guidelines are well-structured and actionable. Highlights:
- **Guideline 2** ("Never use traffic-proportional allocation") is a strong, falsifiable recommendation backed by data.
- **Guideline 4** ("Match strategy to workload sparsity") with the MoE negative result is the paper's best practical contribution.
- **Guideline 7** ("NoI is not the bottleneck for single-token inference") is refreshingly honest.

**Concern:** Guideline 3 says "Add 3--4 express links for K>=16. This captures 60% of total improvement at minimal physical overhead (<0.5% interposer area, <0.1% TDP for 10 express links)." But Guideline 6 says "10 express links require ~56 mm^2 (0.56% area) and ~15W (2.1% TDP)." These numbers contradict: Guideline 3 says <0.5% area and <0.1% TDP; Guideline 6 says 0.56% and 2.1%. This is a copy-paste error from the previous revision -- the old numbers were not updated everywhere. This needs to be fixed.

## New Concerns (Iteration 3)

### [NC1] Table IX Express (0 placed) throughput anomaly
As noted above, Express with 0 placed links shows 0.0150 throughput versus Uniform's 0.0229 for MoE traffic -- a 34% degradation despite supposedly identical topology. This is either a bug or an unexplained difference in how remaining link budget is allocated. If the greedy algorithm places 0 express links but distributes the link budget differently from uniform (e.g., load-aware among adjacent pairs), then the label "Express (0 placed)" is misleading -- it is really "Load-aware adjacent allocation" and should be labeled as such. If it IS uniform with zero express links, the throughput gap is a validation issue.

### [NC2] Guideline 3 vs Guideline 6 contradiction
Guideline 3: "<0.5% interposer area, <0.1% TDP for 10 express links"
Guideline 6: "56 mm^2 (0.56% area) and ~15W (2.1% TDP)"
These cannot both be correct. The Guideline 6 numbers appear to be the revised ones based on CoWoS specs. Guideline 3 appears to still contain the old under-estimates from iteration 2. This must be fixed.

### [NC3] Missing Kite-like in main BookSim table remains the elephant in the room
The single most informative datapoint for this paper would be: at K=16 with dense traffic and L=72, what is the BookSim throughput and latency of Kite-like (MinMax adj)? The analytical model predicts a 1.2x gap between MinMax adj (rho_max=8.1) and Express (rho_max=6.6). If BookSim confirms this small gap, then the practical motivation for express links weakens significantly -- you get 80% of the benefit from just doing smart adjacent allocation (which Kite already proposes). If BookSim shows a larger gap, then express links are justified. Either way, this datapoint is essential.

### [NC4] Hybrid TP+MoE row in Table IX lacks Express comparison
Table IX includes Hybrid TP+MoE traffic but only shows Uniform and Kite-like, not Express. This is an odd omission -- the hybrid pattern mixes dense (TP) and sparse (MoE) traffic, which is exactly the scenario where the express/adjacent trade-off is most nuanced. Why was Express not tested for this workload?

## Has the Paper Become More Honest?

Yes, substantially. The progression across three iterations is clear:
- **Iteration 1**: Overclaimed "90% throughput improvement" as headline, no negative results, no caveats.
- **Iteration 2**: Added averages, acknowledged K=8 weakness, but abstract still oversold.
- **Iteration 3**: Abstract leads with characterization, MoE negative result is prominently featured, E2E analysis honestly shows ~0% speedup for batch-1, conclusion says "not universally beneficial," physical overhead is higher than originally claimed and honestly reported.

The new negative results (MoE showing zero express benefit, E2E showing ~0% speedup for batch-1) **strengthen** the paper because they demonstrate intellectual maturity and a framework that produces discriminating results rather than uniformly positive ones. A paper that says "our technique works for X but not for Y, and here is why" is more trustworthy than one that claims universal benefit.

## Do the Negative Results Weaken the Paper?

This is the critical question. On one hand, the negative results narrow the paper's impact claim -- express links only help for dense traffic at K>=16, which is a forward-looking regime, not today's production systems. On the other hand:
1. The characterization (phantom load definition, closed-form analysis, routing independence, workload ranking) stands independently of the mitigation results.
2. The negative results THEMSELVES are contributions (practitioners should know that traffic-proportional is bad, MoE does not benefit from express links, batch-1 inference does not benefit from NoI optimization).
3. The seven design guidelines are more credible BECAUSE they include "when NOT to" recommendations.

So: the negative results weaken the *hero number* story but strengthen the *characterization paper* story. Since the paper has correctly pivoted to be a characterization paper, this is the right trade-off.

## Strengths (Retained and New)

1. [S1] **Honest self-assessment (new).** The paper now contains three explicit negative results: MoE zero express benefit, ~0% E2E speedup for batch-1, and traffic-proportional being worse than uniform. This level of honesty is rare and strengthens credibility.
2. [S2] **MoE BookSim validation (new).** Confirming analytically predicted negative results in cycle-accurate simulation is a strong methodological choice.
3. [S3] **Design guidelines are actionable (new).** Seven guidelines with clear conditions and thresholds (K<=8 vs K>=16, dense vs sparse). Guideline 4 (match strategy to workload) is the paper's most practical contribution.
4. [S4] **Closed-form analysis remains the anchor.** Theorem 1 with computational validation up to R,C<=8 is rigorous. The Theta(K) scaling result is clean.
5. [S5] **Counter-intuitive result on traffic-proportional allocation.** Still the paper's most memorable finding.
6. [S6] **Physical overhead is now honest.** CoWoS-based numbers (0.56% area, 2.1% TDP) are higher than originally claimed, which builds trust.

## Weaknesses (Summary)

1. [W1] **Kite-like baseline missing from main BookSim table (Table VI).** This is the single most important missing experiment. Kite-like appears only in the MoE table where it looks bad, not in the dense-traffic table where the comparison is most critical. The analytical model predicts only a 1.2x gap between MinMax adj and Express -- if this holds in BookSim, the practical case for express links is much weaker than presented. **(Not fixed from iteration 2, partially addressed only for MoE.)**
2. [W2] **Table IX Express (0 placed) throughput anomaly.** Express with 0 placed links shows 34% worse throughput than Uniform for MoE traffic. This is unexplained and either represents a bug or a misleading label. **(New concern.)**
3. [W3] **Guideline 3 vs Guideline 6 physical overhead contradiction.** One says <0.5% area / <0.1% TDP; the other says 0.56% area / 2.1% TDP. Copy-paste error from previous revision. **(New concern, easy fix.)**
4. [W4] **"10-30% communication time" for high-communication regimes is unsubstantiated.** No roofline or back-of-envelope calculation provided to support when phantom load mitigation matters in E2E terms. **(Carried from iteration 2.)**
5. [W5] **Netlist generation still underspecified.** Spectral clustering parameters, module configurations, and sensitivity to these choices remain unexplored. **(Carried from iteration 2, partially addressed by honesty in Limitations.)**

## Questions for Authors

1. [Q1] Table IX: Why does "Express (0 placed)" show throughput 0.0150 versus Uniform's 0.0229 for MoE traffic? If zero express links are placed, how does the topology differ from uniform? Is the remaining budget allocated differently?
2. [Q2] Guideline 3 says "<0.5% area, <0.1% TDP" but Guideline 6 says "0.56% area, 2.1% TDP." Which is correct?
3. [Q3] Why is Kite-like not included in the main BookSim table (Table VI) for dense traffic? This is the most important baseline comparison -- the analytical model predicts only 1.2x gap between MinMax adj and Express.
4. [Q4] For the E2E analysis: at what batch size does communication time cross 10% of total? A simple calculation would significantly strengthen Guideline 7.

## Rating

- Novelty: 3.0/5 (unchanged; the characterization contribution is clear but the mitigation story is less novel given express channels are known)
- Technical Quality: 3.5/5 (up from 3.0; MoE validation and honest negatives improve methodology, but Table IX anomaly and missing Kite-like in Table VI are concerns)
- Significance: 3.0/5 (unchanged; K>=16 forward-looking regime limits near-term impact, but guidelines are practically useful)
- Presentation: 4.0/5 (up from 3.5; much more balanced framing, honest negatives, well-structured guidelines)
- Overall: 3.5/5 (up from 3.0)
- Confidence: 4/5

## Decision

**Weak Accept.** The paper has improved significantly across three iterations. The pivot to a characterization paper with honest negative results was the right strategic choice. The MoE zero-benefit result, the ~0% E2E speedup admission, and the "express links are not universally beneficial" conclusion demonstrate intellectual maturity. The closed-form analysis, routing-algorithm independence, and counter-intuitive traffic-proportional result are genuine contributions.

However, two issues prevent a strong accept:

1. **The missing Kite-like baseline in Table VI is the remaining elephant.** The analytical model predicts express beats MinMax adj by only 1.2x for dense traffic. If BookSim confirms this, the practical case for express links weakens from "2x improvement" to "1.2x improvement over the best adjacent strategy, which Kite already proposes." The paper should either (a) run this experiment and show the result, or (b) honestly state the expected gap and argue why even 1.2x matters at K>=16 scale.

2. **The Table IX Express throughput anomaly needs explanation.** A 34% throughput gap between "0 express placed" and Uniform is too large to ignore.

If these two items are addressed (even as brief clarifications), this is a solid accept for DATE. The characterization contribution -- phantom load definition, closed-form scaling, workload vulnerability ranking, and actionable guidelines with explicit negative cases -- is a useful addition to the chiplet design literature.
