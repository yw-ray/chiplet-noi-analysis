# Review -- Reviewer 5 (Skeptic), Iteration 11

## Summary

Iteration 11 is a surgical patch pass on iter 10, not a methodological revision. The authors have addressed the two most acute *presentation* bugs I raised -- the §VI.D text/data mismatch and the statistical framing of Spearman $\rho$ over heavily tied NL\% tiers -- and have cleaned up a couple of numerical inconsistencies I let through in iter 10. The substantive criticisms, however, are largely unchanged: there is still no multi-seed variance, no PARL re-run, no fine-tuned GNN baseline, the surrogate is still trained on the same four workloads the paper evaluates, the "measured guarantee" is still the `min(a,b)` tautology, and the headline 56.4\% is still a single cell. The paper is more honest than iter 10 in how it *describes* what it did; it has not done more. On balance this earns a nudge upward but not enough to cross the Weak Accept line.

## Changes from Iteration 10

- **§VI.D text corrected.** The paper now reads: "$(K{=}16, N{=}4, b{=}4\times)$ and $(K{=}16, N{=}8, b{=}4\times)$" and adds the rationale "The RL-WS subset deliberately excludes the $b{=}2\times$ crossover regime, which is already covered by the fallback mechanism in the main result." I verified against `ml_generalization.json` -- RL-WS cells are exactly K16N4/K16N8 at b=4x. The text now matches the data.
- **Kendall $\tau$ added.** Paper §V.B and conclusion now report $\tau=0.593$ ($p=9.6\times 10^{-7}$) on the 40-point pool and $\tau=0.634$ on the 16 best-budget cells. I re-ran `scipy.stats.kendalltau` on the pooled cells and confirm these exactly. The authors also keep $\rho=0.744$ and explicitly say that $\tau$ is reported "to confirm that the monotone trend is not an artifact of tie-breaking."
- **Data cleanup.** L_adj=126.0 and L_RL-WS=54.9 for the MoE K32N8 b=4x cell are now exact (`ml_comparison_fast.json` shows 125.994; `ml_comparison_warmstart.json` shows 54.8939). The 16-cell RL+fb $\tau=0.634$ matches `scipy.stats.kendalltau` on best-budget cells.
- **New latency-sensitivity analytical bound** at $\lambda\in\{1.0,1.5,2.0\}$ for the MoE K32N8 b=4x cell, showing saving $\ge 50.1\%$ at $\lambda=2.0$. This is algebra on 8 cycles of added delay, not a BookSim re-run.
- **Multi-seed CI gap disclosed** honestly in §VII limitations ("All BookSim results are single-seed per configuration...").
- **Cold-RL repositioned** as "best-effort internal proxy for the cold-PPO regime that PARL inhabits", with an explicit acknowledgment that PARL is not reproduced.
- **Approximation-guarantee disclaimer** added for Algorithm 1.
- **Deadlock-freedom paragraph** added (not checked in detail).

## Strengths (genuine, limited)

**[S1] §VI.D factual mismatch is resolved.** iter-10 text said "$K{=}16, N{=}8$ at $b \in \{2\times, 4\times\}$" while the data had b=4x only and K both 16 and 4/8. iter 11 matches the data. Importantly, the authors now *state* that b=2x was deliberately excluded rather than leaving the reader to infer selection bias.

**[S2] $\tau$ addresses my tied-rank attack directly.** The paper now concedes the four-tier structure is a real concern and reports a tie-adjusted correlation ($\tau$). Numbers reproduce. The framing "to confirm that the monotone trend is not an artifact of tie-breaking" is exactly the concession I pushed for in iter 10.

**[S3] Numerical hygiene improved.** L_adj=126.0 and L_RL-WS=54.9 on the MoE K32N8 b=4x cell now reproduce bit-exactly from `compute_stats.py`. This fixes the iter-10 mismatch where narrative numbers drifted from the JSON.

**[S4] PARL and multi-seed gaps are now explicitly listed as limitations.** Honesty here is genuinely improved over iter 10: a future reviewer can quote the limitations verbatim rather than dig them out of my iter-10 review.

## Weaknesses (the substance)

**[W1] The §VI.D "fix" is a disclosure, not a fix.** The paper now says, with full candor, that b=2x is excluded from RL-WS generalization because "the unseen evaluation is thus scoped to the budget regime where express placement is active." Read carefully: this is the authors admitting on the record that they did not run their method in the budget regime they elsewhere identify as the most adversarial. Iter 10 hid this; iter 11 discloses it. Neither version *tests* it. For a paper whose headline safety claim is a fallback that kicks in precisely at b=2x, the refusal to run the unseen workloads at b=2x (where the fallback is most likely to be needed) is methodologically weak. "The fallback already covers it in the main result" is a deflection, not an experiment -- the main result's b=2x behavior is on training workloads.

**[W2] $\tau=0.593$ does not rebut my tied-rank attack; it restates it.** Kendall $\tau$ on 40 points with 4 distinct NL\% tiers still measures, at its core, whether the four workload means rank correctly. $\tau=0.593$ with 10-fold replication per tier is not the same kind of evidence as $\tau=0.593$ on 40 independent workloads. The $p$-value is still driven by configuration replicates counted as independent observations, and no bootstrap over the 4 workload buckets has been reported. The authors' framing ("not an artifact of tie-breaking") is correct *as a narrow statistical claim* but does not address the underlying concern: the predictor has been validated on 4 workload points, not on 40.

A proper response would have been: (a) a non-parametric bootstrap resampling workloads, or (b) a leave-one-workload-out cross-validation of NL\%. Neither is in iter 11.

**[W3] RL-WS uplift is still +2.6 pp mean and +2.5\%\p "fallback-driven" is still cold-RL's story.** The overall table reproduces:

| Method | Mean saving | Worst vs greedy | Wins/40 |
|---|---|---|---|
| Greedy | +25.64\% | -- | -- |
| RL-WS raw | +28.14\% | -1.73\%\p | 35/40 |
| RL-WS + fb | +28.23\% | +0.00\%\p | 35/40 |

Fallback contributes 0.09\%\p to the RL-WS mean. This is identical to iter 10. The "fallback-driven safety" narrative in §VI.B ("2.3\%\p fallback-driven gain for cold, 0.1\%\p for warm") is correct but cuts the other way: **fallback is structural padding for cold RL, not a safety property of warm RL**. For warm RL, fallback fires so rarely (5/40 configs, each <1.73\% regression) that its mean-level benefit is statistical noise. The authors' own numbers say the "safety guarantee" is largely unneeded on warm RL -- which is either an argument for warm-start or an argument that the fallback is a superfluous wrapper, but not both simultaneously.

**[W4] "Never worse than greedy by construction" is still `min(a,b)`.** The abstract and conclusion retain this wording. I said in iter 10 that this is tautological; iter 11 changed nothing here. The mechanism is: simulate both candidates on BookSim, return whichever is lower. Every A-or-B ensemble trivially satisfies it. The novelty claim rests on the fact that PARL does not do this, which is true but is a statement about PARL's omission, not about a methodological contribution. The authors concede in §III that a PARL reproduction would require re-implementing its reward model, and they then sidestep the experiment. This is fine as a scoping decision; it is not fine as grounds for the "safety" contribution to be a named pillar (C3) of the paper.

**[W5] Surrogate training set = evaluation set, still.** iter 11 does not add a held-out-workload validation of the surrogate. I asked in iter-10 Q5; the response is absent. The 288 surrogate samples are still drawn from the same 4 workloads evaluated in Table VI, and per-configuration RL uses that surrogate to score candidate placements. For a paper whose thesis is "NL\% predicts and RL refines", this is a material gap: neither the predictor nor the refiner has been validated on workload distributions outside the 4-workload training family. The generalization experiment does not close it -- ring / pipeline / all-to-all are drawn from the same LLM-collective family, and RL-WS is retrained per configuration using a surrogate that is itself trained on the original 4.

**[W6] Zero-shot GNN is still a strawman.** iter 11 does not add a fine-tuned GNN. I flagged this in iter-10 W6 / Q3; the response is: "a fine-tuned GNN or a PARL re-implementation are complementary comparison points that we leave to future work." This converts the complaint from "the comparison is misleading" to "the authors acknowledge the comparison is limited", which is incrementally more honest but does not produce the missing experiment. The paper still headlines "RL-WS wins 6/6, zero-shot GNN collapses -23.6\% on all-to-all" as evidence of RL-WS's distribution-shift robustness. A matched-compute fine-tuned GNN might close most of that gap; we do not know.

**[W7] Best-case 56.4\% is still one cell, and the decomposition is still obscured.** The abstract says "RL-WS raises this to 28.2\% ... The best single configuration reaches 56.4\% latency reduction (MoE Skewed, $K$=32, $N$=8, 4$\times$ budget)." On that exact cell, greedy alone is 52.12\% (verified via `compute_stats.py`). RL-WS adds +4.31\%\p. The 56.4\% is a combination of the express topology change (captured by greedy) and the small RL refinement; juxtaposing "28.2\% RL-WS" with "56.4\% best" invites a reader to attribute the 56.4\% to RL-WS. iter 10 had this problem; iter 11 carries it unchanged.

**[W8] Latency-sensitivity is algebra, not experiment.** The new $\lambda$-sensitivity paragraph shows that on the *single* headline cell, an analytical upper bound on added delay gives saving $\ge 50.1\%$ at $\lambda=2.0$. This is a reassuring back-of-envelope result for that cell, but:
- It applies to one of 40 cells; other cells (especially low-NL\% Tree All-Reduce at $K=16$) may be much more sensitive to $\lambda$.
- The bound is analytical ($2D=8$ cycles added per express hop), not measured. A full BookSim re-evaluation at $\lambda=2.0$ is what I asked for in iter 10; what iter 11 delivers is an algebra exercise on a best-case cell.
- The authors explicitly say "a full BookSim re-evaluation ... is a camera-ready exercise rather than a blocker." This is a scoping statement, not an experiment. An architecture reviewer reading "express benefit depends on wire-delay scaling" will want the full table, not a single analytically bounded cell.

**[W9] Multi-seed CI is deferred, not performed.** iter 11 disclosed (good) that all results are single-seed and claims "we observed small latency noise in exploratory runs (standard deviation $<1\%$ at saturation)." No location in the paper actually reports that standard deviation, and the "exploratory runs" are not quantified (how many? which configs?). A 2.6\%\p mean uplift with 1\% per-cell noise across 40 configs is plausibly significant by t-test, but no t-test is shown. Disclosing a limitation is not the same as addressing it. I asked in iter-10 Q1; iter 11 converts "missing" to "acknowledged missing".

**[W10] Cold-RL as PARL proxy is a soft comparison.** §III now says cold RL is a "best-effort internal proxy for the cold-PPO regime that PARL inhabits". This is fair as a descriptive statement. But cold RL in this paper is *the authors' own method with warm-start turned off*, trained on 24 configurations. PARL uses a different state space (interference score, multi-objective), a different architecture (maskable PPO with safety masks), and a different training regime. Calling one a "proxy" for the other does useful triage work but does not substitute for running PARL. The axis-based Table I comparison remains the only formal comparison; I raised this in iter-10 W7, and iter 11 does not advance it.

## Questions (pointed, mostly repeated)

**Q1 (iter 10, unaddressed).** What is the std over seeds of the 28.2\% RL-WS mean, computed on at least 3 seeds per configuration on a representative 10-config subset? A 1\% per-cell CI on 40 configs would not validate a 2.6\%\p uplift as statistically distinct from seed noise; you need actual numbers.

**Q2 (iter 10, addressed by disclosure only).** Why not run RL-WS at b=2x on the unseen workloads? The fallback's worst-case behavior on distribution-shifted, low-budget traffic is precisely the adversarial regime that would stress-test the safety claim. "Scoped to the regime where express placement is active" is a definitional move; I want an experimental move.

**Q3 (iter 10, unaddressed).** Is there a fine-tuned GNN number for the 40-config benchmark and the generalization set, trained on the same 288-sample surrogate dataset? Even a best-effort result would sharpen the "RL-WS is the robust choice" claim from axis-argument to empirical one.

**Q4 (iter 10, softened).** The PARL comparison is now explicitly "future work." Is there a reason a stripped-down PARL variant (cold-PPO on the same reward as your own RL) cannot be run on a 10-config subset to provide *any* empirical data point? The cold-RL ablation is not quite the same experiment: it uses your state space and reward, not PARL's.

**Q5 (iter 10, unaddressed).** Hold-out-workload surrogate validation: if the surrogate is trained on tree / hybrid / uniform only and tested on MoE (or any workload-wise leave-one-out), what is its MSE, and does RL-WS still beat greedy on the held-out workload? This is the out-of-distribution test that would convert the generalization experiment from "different traffic matrix, same workload family" to "different workload family".

**Q6 (iter 10, partially addressed).** Can you report a non-parametric bootstrap of $\rho$ or $\tau$ that resamples over the 4 workload buckets (rather than over 40 configuration replicates)? $n=4$ will yield wide CIs, but it will also tell the reader honestly how much of the correlation is driven by the *predictor* versus the *replicate count*.

**Q7 (iter 10, superseded by the b=2x scoping disclosure).** On the 5 regression configs pre-fallback, does RL-WS's policy converge to greedy asymptotically, or does it actively prefer a worse allocation? If the latter, the surrogate is mis-specified in that regime, and more training time would not help.

**Q8 (iter 10, unaddressed).** What are the 24 configurations used for cold RL? Reporting Warm RL restricted to those same 24 configurations would make the comparison apples-to-apples.

**Q9 (iter 9, persistently unaddressed).** Algorithm 1 falls back to traffic-proportional allocation, but Table 5 (mitigation) shows traffic-proportional is 1.5--2.3x worse than uniform. Why?

**Q10 (new, iter 11).** The $\lambda$-sensitivity paragraph reports saving $\ge 50.1\%$ at $\lambda=2.0$ on the MoE K32N8 b=4x cell. What is the analytical bound on the 5 pre-fallback regression cells (Tree All-Reduce and Hybrid TP+PP at $K=16$, various b)? If saving becomes negative on those cells under mild $\lambda$ scaling, the conclusion "express saving remains dominant even under a 2x pessimistic wire-delay assumption" is cell-specific rather than regime-specific.

## Rating

| Metric | Score | Comment |
|--------|-------|---------|
| Novelty | 2.5/5 | NL\% as predictor modestly novel; RL-WS + `min(a,b)` fallback still engineering hygiene. No change from iter 10. |
| Technical Quality | 3.0/5 | §VI.D fix and $\tau$ addition remove specific iter-10 errors. Single-seed, no PARL, no fine-tuned GNN, same-workload surrogate, b=2x unseen-skip all persist. Net change ~0. |
| Significance | 2.5/5 | RL-WS uplift still +2.6 pp mean; best-case 56.4\% still one cell and greedy-dominated on that cell. No change. |
| Presentation | 3.8/5 | +0.3: the §VI.D correction and $\tau$ addition remove two framing traps that were actively misleading in iter 10. Limitations section is now honest. The "never worse by construction" wording in the abstract remains an overclaim. |
| Overall | 2.8/5 | +0.1 over iter 10. Honesty improved at the margin; no new experiments. |
| Confidence | 4.0/5 | Same. All numerical claims verified via `compute_stats.py` and direct JSON inspection. |

## Decision

**Borderline Reject (held).**

iter 11 delivers exactly what I asked for on the two specific factual errors I flagged (§VI.D text, $\tau$), and the authors deserve credit for that. But the core iter-10 structural concerns were not about wording -- they were about missing experiments:

- no PARL re-run (even a partial one on a subset),
- no fine-tuned GNN baseline matched to RL-WS's training compute,
- no multi-seed variance on the RL-WS main result,
- no held-out workload for the surrogate,
- no b=2x evaluation on unseen workloads.

iter 11 converts each of these from "undisclosed gap" to "explicitly acknowledged future work." That is better science. It is not a different conclusion: the paper has the same evidence base as iter 10, and the RL-WS contribution still rests on a 2.6\%\p mean uplift with an `min(a,b)` safety wrapper, trained on the same four workloads it evaluates, not compared to the cited prior work, with single-seed results on a 40-config grid.

**Does the paper clear the DATE bar?** Not yet, but closer in spirit than iter 10. I would upgrade to **Weak Accept** if any *one* of Q1 (multi-seed CI showing the 2.6 pp uplift survives), Q3 (fine-tuned GNN baseline), or Q4 (PARL or PARL-equivalent cold-PPO on at least a subset) is addressed with an actual experiment. Disclosure-only patches are not enough for a method-contribution paper whose named third pillar is a learning algorithm. At the current evidence level, the phantom-load analysis + NL\% predictor + greedy placement (the iter-9 scope) would be a Weak Accept; the added RL-WS + fallback apparatus raises the evaluation bar in ways the paper's experiments do not yet meet.

---

**Under-100 verdict.** Borderline Reject (held). Overall 2.8/5, Confidence 4/5. §VI.D fix and Kendall $\tau$ land; L_adj=126.0 / L_RL-WS=54.9 / $\tau=0.593, 0.634$ reproduce. But no new experiments: no PARL re-run, no fine-tuned GNN, no multi-seed CI, no held-out-workload surrogate test, no b=2x on unseen. RL-WS uplift still +2.6\%\p mean; best-case 56.4\% still one cell (+4.3\%\p over greedy); "never worse by construction" still tautological. Honesty improved; evidence unchanged. **DATE: reject at current evidence; Weak Accept if any one of Q1/Q3/Q4 is addressed experimentally before camera-ready.**
