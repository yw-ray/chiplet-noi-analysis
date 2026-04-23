# Review -- Reviewer 5 (Skeptic), Iteration 10

## Summary

Iteration 10 is a full-scope rebrand: the paper is no longer "NL%-guided express link placement with a greedy algorithm" but "Predict, Place, Refine" where **Refine** is a new warm-started RL (RL-WS) pipeline with post-hoc BookSim fallback. The paper now claims (i) NL% predicts greedy saving with Spearman rho=0.744 across 40 configurations, (ii) RL-WS improves mean saving from 25.6% to 28.2%, (iii) RL-WS is "never worse than greedy by construction" due to the fallback, (iv) RL-WS generalizes 6/6 on unseen workloads while a zero-shot GNN collapses (-23.6%) on all-to-all. The numerical claims reproduce from `results/ml_placement/ml_comparison_{fast,warmstart,generalization}.json` via `compute_stats.py`. The framing changes are more honest than iter 9, but the newly added ML contribution drags the paper into a very different evaluation bar and, on closer inspection, opens more holes than it closes. I am upgrading from Borderline Reject to a hair above it, but I am not yet willing to recommend acceptance.

## Changes from Iteration 9

- **New contribution C3 (RL-WS).** Warm-start RL + post-hoc BookSim fallback. Previously the paper stopped at greedy.
- **Spearman rho "upgraded" from 0.94/0.93 (iter 9) to 0.744 (iter 10).** The authors now pool over all 40 configurations instead of the previous 5- or 16-cell selection. This is methodologically better but exposes that the earlier 0.94 number was driven by picking K32N8 only.
- **Best-case number changed: 52% -> 56.4%.** This is the RL-WS lift on a single configuration (MoE Skewed, K=32, N=8, 4x).
- **PARL (arXiv 2510.24113, Oct 2025) cited** as closest prior work; Table I compares along Predictor / Warm-start / Safety axes. PARL is not experimentally compared.
- **Table VII ("Warm RL + fallback") lists 35/40 wins** over greedy, fixing the iter-9 mislabeling.
- **Crossover at b=2x is now disclosed explicitly** in §VI.A: 5 pre-fallback losses all <=1.73%, all on Tree All-Reduce / Hybrid TP+PP at K=16.
- **Asymmetric generalization n disclosed**: GNN on 4 cells, RL-WS on 2 cells per unseen workload.

The iter-9 issues I raised (W1 workload scoping, W2 abstract "same link cost", W3 physical overhead mismatch, W4 traffic-proportional fallback contradiction, W5 no error bars on main-result table) are **only partially addressed**: Table VII has mean/worst/wins but still no std, and the physical overhead section is unchanged in structure.

## Strengths (genuine, limited)

**[S1] Numerical honesty improved.** The 25.6% greedy / 28.2% RL-WS+fb / 56.43% best / rho=0.744 / 35/40 wins / 6/6 gen numbers all reproduce bit-exactly from `compute_stats.py` on the shipped JSON. The Table VIII overall GNN sign error (+0.6% -> -0.6%) is fixed. The iter-9 inflated rho=0.94 has been replaced by the correctly-pooled rho=0.744.

**[S2] The post-hoc fallback gives a real, measurable guarantee.** `L_RL-WS = min(L_greedy^measured, L_RL^measured) <= L_greedy^measured` is trivially true but honestly disclosed. Prior learning-based NoI work (PARL) offers no such guarantee, so this is a genuine, if small, contribution.

**[S3] Negative result on the GNN (-23.6% on all-to-all) is kept in the paper.** Most authors would have dropped it. The fact that it stays gives the paper some credibility.

## Weaknesses (the bulk)

**[W1] The RL-WS "uplift" is 2.6 pp. Is the entire C3 contribution justified?**

The paper's own Table VI reports greedy +25.6% and RL-WS+fb +28.2% -- a **+2.6 pp mean uplift** after adding a full RL training loop, a 288-sample surrogate, per-configuration REINFORCE with a few hundred episodes, and a post-hoc BookSim sweep. The surrogate itself costs 288 BookSim runs up front; RL adds tens to hundreds of seconds per configuration (the paper's own §VII); and the fallback re-runs BookSim on both candidates. For **2.6 pp** on average, and strictly smaller deltas on the workloads where greedy is already strong (e.g., MoE Skewed K32N8 moves from +52.1% to +56.4%, i.e., only +4.3 pp of absolute saving despite this being the headline 56.4% case).

An honest reading is: **greedy is the contribution; RL-WS is a cosmetic wrapper.** Every row of Table VI would still tell the same story if C3 were deleted. If the authors disagree, they need to argue that the 2.6 pp is statistically distinguishable from surrogate noise (they do not report std / CI) and that the deployment cost of RL is worth 2.6 pp vs a fast, deterministic baseline.

**[W2] The "measured guarantee" is `min(a, b)`.**

The authors call this a "strict Pareto-complement of greedy" and make it sound like a non-trivial safety property. It is `min(a, b)`. Every "A-or-B pick the better one" pipeline trivially satisfies it. The novelty of this mechanism relative to PARL is not that RL-WS is provably better -- it is that the authors double-simulated and kept the min. That is engineering hygiene, not a methodological contribution. The text "by construction" in the abstract oversells a tautology.

Worse, the fallback actively papers over the crossover: 5 of 40 configs regress pre-fallback (Table VI, confirmed from `ml_comparison_warmstart.json`: tree_allreduce K16N4 at b=2/3/4, hybrid_tp_pp K16N4 b=4, hybrid_tp_pp K16N8 b=7, all with +0.12% to +1.73% regressions). The fallback does not *fix* these -- it just reports greedy's latency and claims "no regression". The underlying RL policy is silently wrong on those 5 cells. This is not a solved problem; it is a masked one.

**[W3] The Spearman rho=0.744 at p<10^-7 is statistically misleading.**

There are exactly **four distinct NL% values** in the 40-point pool (42, 77, 89, 91), each replicated across 10 hardware-configuration cells per workload. Spearman on n=40 with heavy tied ranks effectively reduces to a rank test on 4 workload buckets. The p-value inflation comes from counting configuration replicates as independent observations, which they are not (same traffic matrix, same NL% by construction, only hardware knobs vary). The "real" Spearman signal is between 4 workload ranks and median savings; the 40-point version mostly measures whether each workload's 10-config median lies where NL% predicts. This is still a real ordering, but advertising `p < 10^{-7}` on 4 genuine NL% tiers is inflated.

The iter-9 paper claimed rho=0.90--0.93. iter-10 reports rho=0.744. The authors owe the reader a single sentence explaining *why* the number dropped. "We pooled all 40 points" is the true reason, and they should say so. A reader comparing to PARL or any future benchmark cannot tell from the current text whether 0.744 is a tightened analysis or a selection-different one.

**[W4] Surrogate training uses the same workloads as the 40-config evaluation.**

`ml_express_placement.py:collect_surrogate_data()` reads `results/cost_perf_6panel_{tree_allreduce,hybrid_tp_pp,moe,uniform_random}/cost_perf_6panel_incremental.json` -- i.e., the **exact four workloads** that show up in Table VI. The 288 training samples are random 80/20 split on *configurations from these four workloads*. The RL agent then uses this surrogate to score allocations during training, and the paper evaluates RL-WS on the same four workloads. This is not a held-out evaluation; it is training-set performance mediated by an MLP.

The authors' partial defense is the generalization experiment (§VI.D) on ring / pipeline / all-to-all, but (a) those workloads are still LLM collectives within the same family, and (b) RL-WS is re-trained per configuration on its own surrogate on those workloads too, so "generalization" here means "works when you retrain on the new distribution" -- a much weaker claim than zero-shot transfer.

For C1 (NL% as a simulation-free predictor), the same critique applies: the predictor is validated *on* the workloads used to tune the algorithms. There is no out-of-distribution validation of NL% itself.

**[W5] The generalization table is misleading in the paper text vs. the data.**

Paper §VI.D line 387: "K=16, N=8 at b in {2x, 4x}". The actual RL-WS cells in `ml_generalization.json` are **(K=16,N=4,b=4x) and (K=16,N=8,b=4x)** -- different (K,N), same b=4x. There are **no b=2x** generalization cells for RL-WS. Given that b=2x is precisely the crossover regime where RL regresses on the training workloads, running RL-WS generalization only at b=4x avoids the most adversarial budget regime. This is a paper-text-vs-data inconsistency that must be corrected; it is either a description error or a selection bias (or both), and in its current form it misrepresents what was actually run.

Additionally, RL-WS "wins 6/6" on cells where b=4x and K=16. GNN "wins 8/12" on cells covering both K=16 and K=32. These are fundamentally different denominators, and comparing them head-to-head ("RL-WS wins 6/6 while GNN only 8/12") is apples-to-oranges. If RL-WS were run at K=32 on all-to-all -- the adversarial cell -- it might also fail; we simply do not know.

**[W6] Zero-shot GNN is a strawman.**

The GNN is pre-trained on a separate NoI-synthesis dataset (line 295) and evaluated without fine-tuning. The paper presents its collapse on all-to-all (-23.6%) as evidence for RL-WS's robustness. But the proper comparison is a GNN fine-tuned on the 288 surrogate samples, or a GNN with the same per-configuration retraining budget as RL-WS. Training on one distribution and testing on another is the textbook definition of a setup that should fail; RL-WS "winning" under this contrast is nearly guaranteed.

A stronger baseline -- a fine-tuned GNN matched to RL-WS's training compute -- might very plausibly beat RL-WS on the same 6 cells. Without that comparison, the robustness narrative is empirically unsupported.

**[W7] PARL is cited but not experimentally compared.**

Table I lists PARL along Predictor / Warm-start / Safety axes and declares each "No / Cold PPO / None". PARL is not re-run on the 40-config benchmark nor on the generalization set. The text in §III ("PARL does not... does not... offers no...") is a paper-axes argument, not an empirical one. For an architecture venue reviewing a work whose main selling point is an ML method, the absence of an empirical head-to-head with the closest cited prior work is a serious gap. At minimum, the authors should reproduce or approximate PARL's objective under their own setup.

**[W8] Best-case 56.4% is one cell.**

The abstract headlines "best single configuration reaches 56.4%" (MoE Skewed K=32 N=8 b=4x). This is one cell of a 40-cell grid. The greedy alone achieves 52.1% on the same cell, so the RL-WS contribution on this particular cell is **+4.3 pp**, not 56.4%. The abstract's rhetorical structure invites the reader to associate 56.4% with RL-WS, when the large number is really attributable to the greedy-express topology change. Keeping the "best single" number is fine; juxtaposing it directly after "RL-WS raises this to 28.2%" without clarifying the decomposition is not.

**[W9] No error bars on Table VI.**

My iter-9 W5 remains un-addressed. RL is stochastic; the REINFORCE loop uses a small number of episodes per configuration; the surrogate's val MSE is not reported. Without at least mean +/- std over multiple seeds, the +2.6 pp mean uplift is not distinguishable from seed noise. Table VII reports worst case but not std.

**[W10] Cold-RL comparison is run on a different subset (24 vs 40).**

§VI.B, Table VII: "Cold RL (24 cfgs)" vs "Warm RL (40 cfgs)". The 24-config subset is not specified, and any comparison of mean / worst / wins between different subsets is methodologically unsafe. If cold RL is too expensive for 40 configs, then (a) this is a cost-asymmetric comparison (warm starts are cheaper per config than cold starts at the same episode budget, precisely because they start near a good solution), and (b) the "wins 13/24 vs 35/40" line is a ratio comparison over different denominators.

## Questions (pointed)

**Q1.** What is the std over seeds for the RL-WS mean saving of 28.2%? If you run the same pipeline with 5 random seeds, what is the 95% CI on 28.2%?

**Q2.** Why is the generalization subset of RL-WS cells (K16N4 b=4x, K16N8 b=4x) different from what the paper text describes (K=16 N=8 at b in {2x,4x})? Which is the authoritative set? If b=2x was not run for RL-WS generalization, why not?

**Q3.** Did you evaluate a *fine-tuned* GNN (on the same 288 surrogate samples) as a baseline? The zero-shot vs RL-WS comparison is asymmetric in training data; please close that gap before claiming "RL-WS is the robust choice under distribution shift."

**Q4.** PARL is the closest cited prior work but is not re-run. Is there a reason the 40-config benchmark cannot be run with PARL's cold-start PPO (perhaps limited to a subset matching their original setup)? Without this, the C3 "safety" claim remains rhetorical rather than empirical.

**Q5.** The surrogate is trained on configurations sampled from the same 4 training workloads used in Table VI. What is the surrogate's validation MSE, and what happens if you hold out an entire workload (e.g., train on tree/hybrid/uniform only, test on moe)?

**Q6.** Does NL%=0.744 replicate under a non-parametric bootstrap over the 4 workload buckets (n=4), or only over the 40 configs with heavy ties? Please report both.

**Q7.** The crossover regime at b=2x affects 5 configs. The fallback makes RL-WS identical to greedy on those cells. Does the method offer *any* benefit over greedy when the budget is tight? If not, the "Refine" step is effectively inactive precisely when budget pressure is highest -- which is the regime architects care about most.

**Q8.** Table VII shows Cold RL on 24 cfgs and Warm RL on 40. What are the 24 cfgs? Please report Warm RL restricted to the same 24 cfgs so the means and win rates are comparable.

**Q9.** (From iter 9, still unanswered.) Algorithm 1 falls back to traffic-proportional allocation, but Table 5 (mitigation) shows traffic-proportional is 1.5--2.3x *worse* than uniform. Why is it the fallback strategy?

## Rating

| Metric | Score | Comment |
|--------|-------|---------|
| Novelty | 2.5/5 | NL% as predictor is modestly novel; warm-start + min-fallback is engineering hygiene, not a contribution |
| Technical Quality | 3.0/5 | Numbers reproduce; statistical framing of rho p-values is inflated; no seed variance; no PARL head-to-head; generalization subset mismatches paper text |
| Significance | 2.5/5 | Phantom load analysis useful; RL-WS's 2.6 pp uplift is too small to drive a new headline |
| Presentation | 3.5/5 | Predict-Place-Refine is a clean frame; best-case 56.4% framing conflates greedy and RL gains; §VI.D factual mismatch |
| Overall | 2.7/5 | |
| Confidence | 4.0/5 | |

## Decision

**Borderline Reject (unchanged).**

The iter-10 revision makes real progress on honesty (correct rho, correct wins, correct signs, fallback disclosure) but also substantially expands the claim surface with an RL methodology that, under close inspection, adds only **+2.6 pp mean** on top of a strong greedy baseline, trained on the same workloads it evaluates, compared against a deliberately weakened zero-shot GNN, not compared against the closest prior work (PARL) at all, and whose "safety guarantee" is `min(a,b)`. The best-case 56.4% headline is dominated by the greedy topology change, not by RL.

For DATE/DAC:
- If this were still a "phantom load + NL% + greedy express placement" paper (the iter 9 scope), I would be closer to Weak Accept on the strength of the phantom load analysis and the empirically grounded NL% predictor.
- Expanding the scope to *also* own an RL methodology raises the bar. The paper now competes with learning-based NoI synthesis work (PARL, GNN NoI synthesis) on their turf and loses on the most important axes: no empirical comparison to PARL, no held-out workload test for the surrogate, no seed variance, weakened-baseline GNN, generalization run on the less-adversarial budget regime.

**Does the paper clear the DATE bar?** Not yet. The phantom load analysis + NL% predictor would, in a tighter scope. The RL-WS contribution in its current form does not; it should either be tightened (proper baselines: fine-tuned GNN, PARL, seed variance, held-out workloads) or demoted from "Refine" as a named contribution to an appendix-level ablation. I would move to Weak Accept if Q1--Q5 are addressed convincingly (in particular: seed variance showing the 2.6 pp uplift survives, a fine-tuned GNN baseline, and either a PARL re-run or a frank acknowledgment that the comparison is axes-only). Absent those, the paper remains at Borderline Reject.
