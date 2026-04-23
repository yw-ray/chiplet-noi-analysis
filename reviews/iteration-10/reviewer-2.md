# Review -- Reviewer 2 (Systems Pragmatist), Iteration 10

## Summary

This iteration reframes the work around a three-step design flow -- \textsc{Predict} (NL\%) $\to$ \textsc{Place} (greedy, Algorithm~1) $\to$ \textsc{Refine} (warm-start RL with post-hoc BookSim fallback). Across 40 BookSim configurations spanning four LLM workloads (Tree AR, Hybrid TP+PP, MoE Skewed, Uniform Rand.), two chiplet counts ($K\!\in\!\{16,32\}$), two per-chiplet mesh sizes ($N\!\in\!\{4,8\}$), and multiple link budgets ($b\!\in\!\{2\times,3\times,4\times,7\times\}$), greedy placement delivers a 25.6\% mean latency saving versus an adjacent-uniform no-express baseline and RL-WS lifts this to 28.2\%, best case 56.4\%. NL\% predicts saving with pooled Spearman $\rho=0.744$ ($p=3.8\times 10^{-8}$), stable under RL refinement. The post-hoc fallback makes $L_{\text{RL-WS}}\le L_{\text{greedy}}^{\text{measured}}$ by construction. On three unseen workloads (ring, pipeline, all-to-all), RL-WS wins 6/6 evaluated cells while a zero-shot GNN collapses on all-to-all ($-23.6\%$), arguing for RL-WS as the distribution-shift-robust option. PARL~\cite{parl} (Oct 2025) is added as the closest prior work with a clean three-axis (predictor / warm-start / safety) differentiation table.

## Changes from Iteration 9

Compared to my iteration 9 review, five changes directly address what a systems pragmatist cares about:

1. **Engineering story is now coherent end-to-end.** The new title and the \textsc{Predict}/\textsc{Place}/\textsc{Refine} structure map one-to-one onto contributions C1/C2/C3 and onto an actual design flow. In iteration 9 the paper read as "phantom load theorem + greedy placement + correlation"; in iteration 10 it reads as "here is a workflow a team can run." This is the single biggest non-numeric improvement.

2. **NL\% is now a formalized simulation-free predictor, not an observation.** Eq.~(7) defines NL\% on the pre-routing demand matrix with explicit hop-$\ge 2$ condition. The pooled correlation is restated with $n=40$, $\rho=0.744$, $p=3.8\times 10^{-8}$, and $\rho$ is shown to be stable under RL refinement ($\rho=0.744$ again). For a DATE audience this is more useful than the "best slice vs pooled" dance of iteration 9.

3. **Measured safety guarantee closes the fallback gap.** Eq.~(8) now states $L_{\text{RL-WS}}=\min(L_{\text{greedy}}^{\text{measured}}, L_{\text{RL}}^{\text{measured}})$ and the text is explicit that the guarantee is \textit{measured}, not surrogate-predicted. Table~6 (ablation) shows Warm RL + fallback at worst $+0.0\%$ over greedy, 35/40 strict wins. This is the crucial deployability claim and it is finally made cleanly.

4. **Distribution-shift robustness is quantified.** Section~6.4 adds an unseen-workload study (ring, pipeline, all-to-all) with a zero-shot GNN as a fast baseline. The GNN's $-23.6\%$ collapse on all-to-all plus RL-WS's 6/6 wins is the best evidence in the paper that RL-WS is \textit{the robust choice}, not the fastest choice. The paper also honestly admits the GNN beats RL-WS on ring (+14.7\% vs +11.5\%). For a pragmatist this even-handedness matters.

5. **Crossover regime at $b\!=\!2\times$ is explicitly acknowledged.** Fig.~3 (K32N8 budget sweep, 4-panel) and Table~6's "5 losses" discussion are now directly connected: the 5 losses \textit{are} the $b\!=\!2\times$ crossover cases. The paper no longer hides this behind best-budget selection.

Smaller but welcome fixes: Table~7 GNN Overall arithmetic corrected ($-0.6\%$), Warm RL win count corrected to 35/40, all RL figures in PDF, workload naming unified.

## Strengths

[S1] **Deployable workflow, not just a benchmark.** The \textsc{Predict}/\textsc{Place}/\textsc{Refine} triple lets a chip architect decide, per workload, how far down the stack to go. If NL\% $<40\%$, stop at \textsc{Predict}. If NL\% is moderate, use greedy (Algorithm~1) and ship. If NL\% $\ge 70$--$80\%$, spend the extra minutes on RL-WS. This is the first iteration where a real team could pick up Algorithm~1 and Section~5.3 and integrate them into a design flow.

[S2] **The fallback is actually deployable, not paper-grade.** Running both candidates in BookSim and keeping the lower-latency one is a cheap operation (two cycle-accurate runs) at design time. There is no online/runtime fallback logic to build into the NoI hardware; the guarantee is a build-time artifact. That is the right place for it.

[S3] **Ablation is now honest about where the gains come from.** Table~6 cleanly separates warm-start's contribution (mean $-1.3\%\to -3.6\%$; worst $+11.3\%\to +1.7\%$) from fallback's contribution ($+1.7\%\to +0.0\%$). This is exactly the decomposition a program committee asks for: warm-start does the heavy lifting, fallback is the insurance.

[S4] **Distribution-shift story is even-handed.** The paper does not claim RL-WS dominates GNN per cell; it claims RL-WS degrades gracefully while GNN does not. On ring the GNN is actually better. This honesty is credibility-positive at DATE/DAC and matches how a real team would deploy: GNN for screening, RL-WS for the hard workloads. Section~6.4 essentially hands readers a deployment recipe.

[S5] **Crossover at $b\!=\!2\times$ is now a feature, not a bug.** Iteration 9 left me wondering whether low-budget losses were being quietly filtered. Iteration 10 puts them in Fig.~3, ties them to the 5-loss ablation column, and explains them as adjacent-capacity starvation. A pragmatist wants to know exactly \textit{when} the method fails; this paper now tells them.

[S6] **PARL comparison is the right framing.** Adding PARL~\cite{parl} (arXiv 2510.24113) as the closest prior work and spelling out the three-axis differentiation (predictor / warm-start / safety) in Table~1 is exactly what a DATE reviewer wants. Without this, the learning-based placement story would have felt crowded.

## Weaknesses

[W1] **Deadlock freedom still unaddressed beyond a one-line limitation.** Section~7 admits "we do not provide a formal deadlock-freedom proof for the combined adjacent/express routing policy." For a DATE/DAC audience this is important but not disqualifying: express links on a 2D mesh with Dijkstra shortest-path routing are known to risk deadlock without virtual-channel ordering. A paragraph stating (a) which VC scheme BookSim uses in the experiments and (b) that production deployment would require a VC turn-restriction argument (e.g., Duato-style) would neutralize this concern. Right now the paper punts.

[W2] **Physical overhead table is CoWoS-class but not CoWoS-specific.** Table~7 is unchanged from iteration 9 and is still back-of-envelope. For a DATE venue the reader wants to know: does a $d\!=\!4$ express link (40\,mm, 8.2\,mm$^2$) actually route on a realistic CoWoS-S / CoWoS-L interposer given adjacent-link PHY keepouts? The paper does not engage with interposer routability. This does not block acceptance but it is the obvious weakness a CoWoS-literate reviewer will flag.

[W3] **Per-configuration RL cost is hand-waved.** Section~7 says "RL-WS takes tens to hundreds of seconds per configuration" but there is no table of wall-clock numbers. A practitioner needs to know: is this CPU or GPU? Per-workload training amortization? For the 40-config evaluation, is total RL cost in the minutes or the hours? Currently this is missing and the "per-configuration training cost" explanation for why Cold RL is only 24 configs reads as an excuse rather than a budget.

[W4] **Unseen-workload study is asymmetric.** GNN is evaluated on 4 cells per unseen workload; RL-WS on 2 cells per unseen workload. Section~6.4 is upfront about this (good), but the $6/6$ headline number is over only 6 cells. The paper should at minimum report whether the extra 6 cells that would complete the parity (the other 2 per unseen workload) can be extrapolated, or run them. As stated, a hostile reviewer can note that RL-WS's 6/6 is half the sample size of the GNN's 8/12.

[W5] **Synthetic workloads, still.** No change from iteration 9: traffic matrices are workload-\textit{inspired} but not traced from a real Megatron/DeepSpeed run. Section~7 acknowledges this. For DATE this is acceptable; for a camera-ready I would still push for at least one traced workload even if it is small-scale (e.g., traced LLaMA-7B TP=4 on 16 simulated chiplets), because the NL\% predictor's credibility scales with traced evidence.

[W6] **No absolute latency numbers.** Iteration 9 Q1 was about this and it is still unanswered. Saving percentages are reported throughout, but the reader cannot tell whether the adjacent-uniform baseline at K=32,N=8,max-rate is 200, 500, or 2000 cycles. A single row in Table~5 or Fig.~3 caption giving absolute baseline latency would close this.

[W7] **NL\% threshold rules in Section~7 are informal.** The discussion recommends "NL\% $<40\%$: don't use express; $70$--$80\%$: use RL-WS." These thresholds are reasonable given the 40-point dataset but are not formally validated (no held-out threshold calibration). A reader shipping Algorithm~1 would want to know how robust these thresholds are to workload shift.

## Questions

Q1. What VC configuration did BookSim use for the combined adjacent/express routing? If VCs were used to avoid deadlock in simulation, the paper should state so; if not, why did simulations not deadlock on the express-augmented topology?

Q2. What is the wall-clock cost of RL-WS per configuration on the hardware you used? And does the per-configuration cost include the 288-sample BookSim surrogate training amortization, or is that a one-time offline cost?

Q3. Is the 288-sample BookSim surrogate reused across all 40 main-result configurations, or is a new surrogate trained per $(K,N)$ slice? This matters for deployment: a one-shot surrogate dramatically lowers amortized cost.

Q4. Table~7 wire-area numbers are linear in $d$. On a real CoWoS-L reticle, $d\!=\!4$ express links may have to route around the PHY keepouts of all intermediate dies; is that accounted for, or is 40\,mm the point-to-point Manhattan length only?

Q5. On the 5 losses where Warm RL is worse than greedy before fallback (all at low-NL\%, $K\!=\!16$): are these consistent across random seeds, or is the loss stochastic? If stochastic, a cheap multi-seed RL-WS would close the 5 losses without needing fallback at all.

Q6. For the unseen-workload study, are the 2 RL-WS cells per workload at $b\!=\!2\times$ and $b\!=\!4\times$ i.e., spanning the crossover? If so, the 6/6 headline is more meaningful. If both are at high budget, the comparison is weaker than it reads.

## Rating

| Criterion | Score | Comment |
|-----------|-------|---------|
| Novelty | 3.5 | NL\% as a simulation-free predictor is a genuinely new and useful contribution. Warm-start RL + post-hoc fallback is not individually novel, but the combination with the predictor and the three-axis differentiation from PARL is novel enough for DATE/DAC. |
| Technical Quality | 3.5 | Measured fallback guarantee, corrected ablation counts, and pooled Spearman with $n=40$ are all solid. BookSim-only and synthetic workloads remain. |
| Significance | 3.5 | Up from 3.0. The three-step workflow and measured safety push this over the line for a practitioner audience at DATE/DAC. Still simulation-only for top-tier. |
| Presentation | 4.0 | Up from 3.5. The \textsc{Predict}/\textsc{Place}/\textsc{Refine} framing is clean; Fig.~3 (crossover visible) and Table~6 (decomposition of warm-start vs fallback) are pedagogically excellent. |
| Overall | 3.5 | Up from 3.0. The paper clears the DATE/DAC bar. |
| Confidence | 4.0 | Familiar with chiplet NoI literature, BookSim methodology, and learned topology synthesis. |

## Decision

**Accept for DATE/DAC. Borderline for ISCA/MICRO (Weak Reject).**

Iteration 10 moves the paper from "solid DATE/DAC accept" to "clean DATE/DAC accept." The three changes that matter most to a systems pragmatist all landed:

1. **Engineering story coherence.** The \textsc{Predict}/\textsc{Place}/\textsc{Refine} reframing turns a collection of contributions into a design flow. A real team can pick up Algorithm~1 and Section~5.3 and use them next quarter.
2. **Measured safety guarantee.** Eq.~(8) and Table~6's worst-case $+0.0\%$ column mean RL-WS is a \textit{safe} drop-in replacement for greedy, not a risky one. This is the single most important deployability property and it is finally air-tight.
3. **Distribution-shift robustness via RL-WS vs GNN.** The asymmetric-but-honest unseen-workload study (RL-WS 6/6 vs GNN $-23.6\%$ on all-to-all) is exactly the kind of evidence a DATE audience wants: not "our method is always best," but "our method degrades gracefully while the alternative does not."

**Does the paper clear the DATE acceptance bar?** Yes, clearly. The combination of (i) a formally stated predictor with $p<10^{-7}$ on 40 points, (ii) a deployable measured-fallback guarantee, (iii) a credible PARL differentiation, and (iv) honest acknowledgement of the $b\!=\!2\times$ crossover regime puts this above the practical-contribution bar DATE applies. The remaining limitations (no deadlock proof, no CoWoS routability analysis, no traced workloads, no absolute latency numbers) are all important but all fall into the "shepherding / camera-ready" bucket rather than the "major revision" bucket.

**For ISCA/MICRO**: still not there. BookSim-only evaluation with synthetic traffic, no hardware or FPGA validation, no comparison against production alternatives (wider UCIe links, hierarchical ring, NVSwitch-class full connectivity), and no deadlock-freedom argument keep this below the top-tier architecture bar. The iteration 10 improvements are real but they improve deployability, not silicon-proximity.

My vote: **Accept at DATE/DAC with minor shepherding** to resolve W1 (deadlock statement), W3 (RL wall-clock table), and W6 (absolute baseline latency). None of these requires new experiments.
