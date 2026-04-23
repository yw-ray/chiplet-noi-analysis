# Review -- Reviewer 3 (ML/Application Expert), Iteration 11

## Summary

Iteration 11 is a textual/positioning revision rather than a new-experiments revision. The authors restate the cold-RL variant as an "internal proxy for PARL's cold-PPO regime," add a Kendall $\tau=0.593$ alongside Spearman $\rho$, promote the $\Theta(K^{3/2})$ claim to a corollary, disclose Algorithm 1's approximation status, add an explicit deadlock-freedom paragraph, correct the generalization text to match the data (RL-WS on $(K{=}16, N{=}4, 4\times)$ and $(K{=}16, N{=}8, 4\times)$, excluding the $b{=}2\times$ crossover), and add an explicit "single-seed; $\ge 3$ seeds planned" limitation. Headline numbers are unchanged: greedy $+25.6\%$, RL-WS+fallback $+28.2\%$, best 56.4\% on MoE Skewed K32N8 $4\times$. None of my iter-10 experimental asks---multi-seed RL CIs, surrogate calibration plot, fine-tuned GNN row, direct PARL reproduction, end-to-end Amdahl framing---are delivered as new data; they are all deferred to future work or addressed by reframing.

## Changes from Iteration 10

**Disclosed as limitations (but not experimentally addressed):**
- **Multi-seed CIs**: Now stated in the Limitations paragraph that "all BookSim results are single-seed per configuration... future work should include $\ge 3$ seeds per configuration with formal CIs." This turns my iter-10 W1 from a silent gap into an acknowledged gap, but does not change any table.
- **Fine-tuned GNN / PARL reproduction**: Limitations paragraph now explicitly states "a fine-tuned GNN or a PARL re-implementation are complementary comparison points that we leave to future work." This converts W3 and W4 from omissions into scoped-out future work.

**Reframing (not new experiments):**
- **Cold RL as PARL proxy**: Related Work now positions the cold-start RL ablation as an "internal proxy for the cold-PPO regime that PARL inhabits," contrasting cold worst-case $+11.3\%$ vs warm $+1.7\%$ (pre-fallback). This is a defensible rhetorical move, but it is not a PARL reproduction---the comparison is to the authors' own cold implementation, not to maskable PPO with PARL's reward and interference evaluator.
- **Generalization text corrected**: The iter-10 text contradicted the data by referring to $b \in \{2\times, 4\times\}$; iter-11 correctly states "$(K{=}16, N{=}4, b{=}4\times)$ and $(K{=}16, N{=}8, b{=}4\times)$" and adds that the RL-WS subset "deliberately excludes the $b{=}2\times$ crossover regime." The subset-mismatch concern (W5) is now at least transparent, though still not apples-to-apples.

**Added rigor:**
- **Kendall $\tau=0.593$** alongside Spearman $\rho=0.744$ (pooled, all 40 points). Also $\tau=0.596$ for RL-WS and $\tau=0.615$/$0.634$ for the 16-cell best-budget subsets. This is a substantive add: ties-robust correlation holds, so the NL\%-ordering claim is not an artifact of rank ties across four distinct workload tiers.
- **Corollary 1** for the $\Theta(K^{3/2})$ scaling, with the 16$\times$ example on a 4$\times$4 grid validated against Table 2.
- **Algorithm 1 approximation-guarantee disclosure** (submodular-adjacent framing; best-effort, no formal bound).
- **Deadlock-freedom paragraph** (VC-dimension assignment argument; explicitly marks Duato-style formal proof as out of scope).
- **Latency-sensitivity analytical bound** added (not re-verified).

**What did not change:**
- **No multi-seed RL results.** Every RL-WS number in Tables 6--8 is still single-seed.
- **No surrogate calibration table/plot.** The 29\% tree-K16N8-$2\times$ miscalibration I flagged in iter 10 (predicted 37.7 vs measured 53.1) is neither shown nor discussed; this regime is exactly where RL-WS "wins by fallback" rather than by RL.
- **No fine-tuned GNN row.** The "RL-WS is robust under distribution shift" claim still relies on a zero-shot GNN comparison.
- **No direct PARL experimental comparison.** The cold-RL "proxy" framing is the substitute.
- **No end-to-end Amdahl / iteration-time framing.** My iter-9 W3 is still un-addressed, now for a third iteration.

## Strengths

**[S1] Kendall $\tau$ is a load-bearing add, not cosmetic.** Because the four training workloads occupy four distinct NL\% tiers (42/77/89/91), the pooled Spearman $\rho$ was at risk of being inflated by between-tier separation with heavy within-tier ties. Adding $\tau=0.593$ at $p<10^{-6}$ (40 points) converts what was a suggestive correlation into a ties-robust monotone statement. This is a cheap but meaningful rigor upgrade.

**[S2] Generalization-text correction matters.** The iter-10 text literally contradicted the JSON (it said $b \in \{2\times, 4\times\}$ when the data show both cells at $b=4\times$). Correcting this, and explicitly justifying exclusion of the $b=2\times$ crossover as "already covered by the fallback mechanism," is the right disclosure. An unfixed contradiction between text and data would have been a fatal credibility issue at any venue.

**[S3] Explicit limitations paragraph is properly scoped.** Iter-11's limitations paragraph (i--v) names all five residual gaps---synthetic workloads, single-seed, zero-shot-only GNN, linear wire-delay model, XY-only NL\% evaluation---in one place. For DATE this is exactly the right posture: the authors are not pretending the paper is ML-systems-complete.

**[S4] Cold-RL-as-PARL-proxy framing is defensible \emph{rhetoric}, even without a reproduction.** Given that PARL's maskable PPO and interference evaluator would require non-trivial re-implementation on BookSim traces, the cold-start RL comparison on the same benchmark does carry some information about how warm-start changes the RL regime. The $+11.3\%$ vs $+1.7\%$ (vs $+0.0\%$ after fallback) worst-case contrast is clean. It is not a substitute for PARL itself, but it is the strongest internal proxy available and is now positioned honestly rather than implicitly.

**[S5] Corollary + Algorithm-1 disclosure improve theoretical framing.** Promoting the $K^{3/2}$ scaling to a named corollary and explicitly marking Algorithm 1 as a best-effort heuristic without a formal approximation bound are small but honest presentational upgrades. The deadlock-freedom paragraph, while not a formal proof, is more than most learned-placement papers offer.

## Weaknesses

**[W1] The core ML-rigor gap is now documented but not closed.** Disclosing "single-seed; $\ge 3$ seeds planned" in the Limitations paragraph converts W1 from a silent gap into an acknowledged gap. For an architecture-track venue this is a meaningful posture change, but it does not change the fact that the headline $+28.2\%$ mean, the $+2.6\%$p RL-WS-over-greedy uplift, and the 35/40 win count are all single-seed single-run numbers. An adversarial reviewer can still ask: if re-running with a different seed swings the mean by $\pm 1\%$p, is the $+2.6$p uplift meaningful? The Limitations paragraph says "future work"; it does not say "we checked three seeds on a subset and variance was $<X$\%p." Even a 3-seed sanity check on the 4--6 headline cells would have closed this much more firmly than a future-work note. For DATE this is survivable; for MLSys/NeurIPS-Systems it would not be.

**[W2] Surrogate calibration is still un-shown.** My iter-10 concrete example---tree K16N8 at $b{=}2\times$: surrogate predicted 37.7, measured 53.1 ($\sim$29\% underestimate)---is not discussed, plotted, or tabulated anywhere in iter-11. The JSON still contains this gap. The "RL-WS $\ge$ greedy by construction" guarantee is real because fallback is measured, but whether the RL portion of RL-WS is contributing on top of greedy depends on whether the surrogate is within tolerance of the measured landscape the policy searches over. Without calibration, "RL refinement" at low-budget tree-like cells is plausibly search-over-surrogate-noise rescued by fallback. An appendix calibration plot---held-out MAE, scatter of predicted vs measured across the 288 corpus samples---was cheap to produce and would have resolved this cleanly.

**[W3] PARL framing is now explicit about the substitution, which is good, but the substitution still has real limits.** Iter-11 is honest: cold RL is "a best-effort internal proxy for the cold-PPO regime that PARL inhabits." But the three differentiators the paper claims over PARL (predictor / warm-start / measured fallback) are not tested against PARL's actual policy architecture, reward shaping, or interference evaluator. Cold REINFORCE on our benchmark is not cold maskable-PPO on PARL's benchmark. A careful reviewer can accept the rhetorical framing but will still discount the "warm beats PARL" story from "proven" to "plausible." For DATE I will accept this; for an ML-systems venue I would not.

**[W4] Zero-shot GNN is still a strawman, and the Limitations paragraph acknowledges this rather than fixing it.** "A fine-tuned GNN... is a complementary comparison point we leave to future work" is the right disclosure, but it weakens the headline "RL-WS is the robust choice under distribution shift" claim to "RL-WS outperforms a deliberately-unadapted GNN under distribution shift." That is a narrower, though still defensible, claim. The Table 8 narrative would be cleaner if this weakening were folded into the main text as well, not only in Limitations.

**[W5] Subset-matched generalization comparison is now transparent but not fixed.** The RL-WS 2-cell subset vs GNN 4-cell subset mismatch is now openly acknowledged ($b=4\times$ only for RL-WS, exclusion justified). But Table 8 still does not present a 2-cell GNN row alongside the 2-cell RL-WS row, which would have fully resolved the apples-to-apples concern. Producing that row requires no new experiments---it is a subselection of the existing GNN runs. I would have expected this in iter 11.

**[W6] End-to-end ML impact is now three iterations un-addressed.** This is the concern I raised in iter 9, reiterated in iter 10, and it does not appear in iter 11 at all---not in Limitations, not in Discussion, not in the Predict--Place--Refine workflow summary. The headline "$+56.4\%$ latency reduction" on MoE Skewed K32N8 $4\times$ is NoI-only; with compute-communication overlap, a realistic MoE training run may see a much smaller fraction as wall-clock speedup. Even a one-paragraph Amdahl bracket ("assuming 20--40\% of iteration time is NoI-bound, this corresponds to 11--22\% iteration-time speedup") would ground the ML-significance claim for the intended audience. This is a one-paragraph fix that persists as an unforced omission.

**[W7] Single-seed BookSim noise claim ("$<1\%$ at saturation") is unverified and load-bearing.** The Limitations paragraph asserts "standard deviation $<1\%$ at saturation" from exploratory runs. This single number is now carrying the weight of the entire single-seed defense, and no table, appendix, or even a parenthetical ($n$=?, across which configurations?) is provided. Under 1\% at saturation says nothing about variance below saturation, where most RL-WS-vs-greedy differences are contested.

## Questions

1. **Seed variance sanity.** Even a 3-seed spot-check on the four headline cells (MoE Skewed K32N8 $4\times$, Hybrid K32N8 $4\times$, Uniform K32N8 $4\times$, Tree K16N8 $2\times$) would convert the single-seed claim from asserted to minimally verified. Is this feasible before camera-ready?

2. **Surrogate calibration table.** Can you add an appendix table with held-out MAE and max error for the 3-layer MLP surrogate across the 288-sample corpus, broken down by workload and $(K,N,b)$? This is the smallest add that would close my W2.

3. **Subset-matched GNN row.** Can Table 8 include a 2-cell GNN row on the same $(K=16, N=4, b=4\times)$ and $(K=16, N=8, b=4\times)$ subset used by RL-WS? No new experiments are required; it is a subselection of existing data.

4. **End-to-end bracket.** Can you add one paragraph to the Discussion with an Amdahl-style bracket for the 56.4\% headline cell? Even a rough "10--40\% of iteration time is NoI-bound" bracket would anchor the significance claim.

5. **Cold-RL-as-PARL-proxy caveat.** Can the Related Work make explicit that the cold-RL proxy uses REINFORCE, not maskable PPO, and does not share PARL's multi-objective reward? This would tighten the rhetorical framing.

6. **BookSim noise verification.** Can the "$<1\%$ at saturation" claim in Limitations be supported by a one-sentence methodology note ($n$=?, which configs)?

## Rating

- Novelty: 3.5/5 (unchanged from iter-10; three-step framing and measured fallback remain the distinctive pieces; corollary and deadlock paragraph are presentational refinements)
- Technical Quality: 3/5 (unchanged; Kendall $\tau$ adds rigor, but single-seed and surrogate-calibration gaps persist; PARL direct comparison remains future work)
- Significance: 3/5 (unchanged; end-to-end impact gap un-addressed for the third iteration in a row)
- Presentation: 4/5 (unchanged; limitations paragraph is now properly scoped, generalization text-vs-data contradiction fixed)
- Overall: 3/5
- Confidence: 4/5

## Decision

**Borderline (hold)** -- Iter 11 is a good presentational cleanup: the generalization text-vs-data contradiction is fixed, the Kendall $\tau$ is a real rigor add, the Limitations paragraph is honestly scoped, and the cold-RL-as-PARL-proxy framing is a defensible rhetorical substitute for a full PARL reproduction. But none of my five iter-10 experimental asks (multi-seed CIs, surrogate calibration plot, fine-tuned GNN row, direct PARL reproduction, end-to-end Amdahl paragraph) translated into new data. They are now, at best, acknowledged in a Limitations paragraph.

**Does "disclose as future work" suffice for DATE?** On a strict reading, I hold at Borderline. Two of the five asks---subset-matched GNN row (W5) and end-to-end Amdahl paragraph (W6)---required no new simulations and were cheap wins; their absence in iter 11 reads as avoidance rather than effortful triage. The multi-seed gap (W1) and surrogate calibration (W2) are the only genuinely expensive asks, and those are the ones I will accept as future work for a DATE architecture-track submission. A 3-seed sanity check on 4 headline cells and an appendix calibration table would have pushed me to Weak Accept; instead, I stay at Borderline.

**Is the ML rigor sufficient for DATE specifically?** Yes, narrowly. DATE is an architecture-track venue and the $\Theta(K^{3/2})$ phantom-load analysis, workload-aware greedy, NL\% predictor, and measured-fallback safety mechanism form a publishable architectural core. The RL-WS contribution is the part that will draw methodology scrutiny, and for DATE I can accept it on the Limitations disclosure alone---I would not at MLSys or NeurIPS-Systems. I land on the same **Borderline** position as iter 10, and I would not fight either acceptance or rejection for DATE. If the PC treats Borderline as soft-accept, I concur; as soft-reject, I concur. Overall 3/5, Confidence 4/5.
