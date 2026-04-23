# Review -- Reviewer 5 (Skeptic), Iteration 12

## Summary

Iteration 12 is the first iteration since iter 9 that delivers an *experimental* response to my attacks rather than a wording patch. Multi-seed RL-WS on 16 best-budget cells with 3 seeds each (48 runs), a matched fine-tuned GNN baseline on all 12 unseen configurations, and a multi-seed correlation ($\rho=0.776$) all reproduce bit-exactly from `ml_comparison_multiseed.json` and `ml_generalization_finetuned.json`. Importantly, the multi-seed data converts my iter-11 "fallback is tautological `min(a,b)`" attack into an empirical question: fallback now demonstrably fires on 10/48 runs (20.8\%) with raw regressions up to 1.77\%. I partially concede that attack -- the fallback is empirically load-bearing at 20.8\% fire rate, not just a mathematical shim. But the paper still gates me at Borderline Reject for DATE because (i) multi-seed was done on 16 cells, not all 40; (ii) PARL is still not re-run; (iii) the best-case 56.6\% is still one cell that is 92\% greedy attributable (RL adds 4.5\%p on that specific multi-seed cell); (iv) the per-workload multi-seed std column in Table VI is documented as "std over 12 seed-runs" but is in fact the *mean of per-cell 3-seed stds* (0.49 / 0.08 / 0.47 / 0.42 reproduce only under that interpretation; the genuine std over 12 values is 3.5--9.9\%). I flag (iv) as a factual error that must be corrected before camera-ready.

## Changes from Iteration 11 (experimental, verified)

- **Multi-seed RL-WS on 48 runs (16 best-budget cells × 3 seeds).** `ml_comparison_multiseed.json`. I re-ran `compute_stats.py` and `aggregate_results.py`: per-cell RL-WS+fb std is $\le 1.22\%$ (max), $0.56\%$ (mean). Raw wins/losses/ties $= 38/10/0$. Fallback fires on 10/48 (20.8\%). Worst pre-fallback regression is $+1.77\%$ latency. All four numbers match the paper's §VI.B / Table VIII claims.
- **Fine-tuned GNN on 12 unseen configs.** `ml_generalization_finetuned.json`. Per-workload means $+14.05 / +6.21 / -23.51$ (Ring / Pipeline / A2A); paper reports $+14.1 / +6.2 / -23.5$. Matches. Overall $-1.1\%$ / 8 wins matches.
- **Multi-seed Spearman on 16 cells with 3 seeds each.** $\rho=0.776$, $\tau=0.652$, $p=4.1\times 10^{-4}$ on the 16 cell-means. `scipy.stats.spearmanr` and `kendalltau` reproduce to three decimals (I got $\rho=0.776$, $p=4.08\times 10^{-4}$).
- **Table VIII expanded with multi-seed rows.** Warm RL (48 runs, 3 seeds): mean $-2.7\%$, worst $+1.8\%$, wins $38/48$. Warm RL + fallback: mean $-2.9\%$, worst $+0.0\%$, wins $38/48$. All reproduce.
- **Best-cell headline re-reported with std.** Abstract and Fig.~\ref{fig:ml_nonlocality} caption: $56.57\% \pm 0.55\%$ (MoE $K{=}32,N{=}8,b{=}4\times$, 3 seeds). I compute 55.80 / 56.97 / 56.94 across the three seeds; mean $=56.57$, population std $=0.548$. Matches (the paper uses population std; this is fine for a 3-seed report but should be stated).
- **Fine-tuning disclosure on GNN.** §VI.C now compares zero-shot and fine-tuned GNN side by side and explains that fine-tuning does not rescue the A2A collapse ($-23.6\% \to -23.5\%$ mean), converting my iter-11 W6 "GNN strawman" into an empirically supported architectural-limit claim. I concede this attack is now genuinely addressed.
- **Surrogate split disclosed.** §V.C now states "random 80/20, seed=42" and explicitly says the surrogate is an in-distribution reward model, not a held-out generalization predictor. Iter-11 Q5 partially addressed: the gap is disclosed, not closed.

## Strengths (genuine, upgraded)

**[S1] Multi-seed experiment is the real thing, not a disclosure.** The 48 RL runs with three independent seeds per cell, with per-seed latencies reported and std computed, directly addresses my iter-11 Q1. This is the only kind of evidence that validates a $+2.6\%\mathrm{p}$ uplift claim. I checked that seeds 0/1/2 produce distinct allocations (differing `L_rl_raw` values within cells), not a re-seeded deterministic rerun, and the spread is genuine ($\sigma$ up to $1.22\%$ at MoE $K{=}32,N{=}8$). This crosses the "seed noise vs. real uplift" bar that I held the paper to at iter 11.

**[S2] Fine-tuned GNN is a matched-compute baseline.** The FT-GNN gets 100 surrogate-guided epochs per cell, which is the same per-cell adaptation budget as RL-WS. That it still loses $-23.5\%$ on all-to-all turns "GNN strawman" into "architectural limit". Per-cell inspection (K=16 $-7/-23 \to -11/-40$ vs K=32 $-17/-47 \to -9/-34$) is consistent with overfitting on low-signal cells and partial recovery on high-signal cells; the paper states this correctly.

**[S3] The fallback-is-tautological attack is empirically softened.** I said in iter 11 that "fallback fires so rarely ($5/40$) on warm RL that its mean-level benefit is statistical noise." Multi-seed reframes this: at 3 seeds per cell, fallback fires on $10/48 = 20.8\%$ of seed-runs, converting 10 regressions of up to $-1.77\%$ into 10 ties. That is load-bearing. I still hold that the mathematical guarantee ($L_{\text{RL-WS}} = \min(L_\text{greedy}, L_\text{RL}) \le L_\text{greedy}$ trivially) is tautological as an algorithmic novelty -- any A-or-B ensemble satisfies it. But the *empirical* claim that fallback meaningfully improves RL-WS has been upgraded from "2/40 mean-level pp" to "20.8\% of seed-runs rescued". **I concede this attack is now partially resolved.** The narrative should be: fallback is a trivial ensembling step whose empirical value becomes visible only under multi-seed evaluation. The paper nearly makes this point in §VI.B but does not quite separate "mathematical guarantee" from "empirical fallback rescue rate".

**[S4] Correlation claim survives multi-seed.** $\rho=0.776$ on 16 cells is slightly higher than the single-seed $\rho=0.764$; Kendall $\tau=0.652$ vs $0.634$. Seed averaging did not mask noise correlations; the NL\%-to-saving ordering is robust. This addresses my iter-11 W2 ("does NL\% ordering survive seed noise?") empirically.

## Weaknesses (the substance that remains)

**[W1] Multi-seed was done on 16/40 cells, not all 40.** Paper §VII (v) discloses this, but the Table VIII "Warm RL + fallback (40)" row remains single-seed, and the headline $+28.2\%$ overall mean in the abstract and Table VI is still the single-seed 40-config number. The 16-cell multi-seed evidence cannot retroactively validate the 24 single-seed cells at $b=2\times$, $b=3\times$, or at Hybrid TP+PP $N=4$ etc. A reviewer reading the abstract gets $28.2\%$ as the headline and does not know that 24 of the 40 cells underlying that number are still single-seed. Iter-11 Q1 was "multi-seed on a representative 10-config subset"; iter 12 gave me 16 configs but skipped the 24 low-budget / mid-tier cells. For DATE, this is defensible but not closed.

**[W2] PARL is still not re-run.** §II still positions PARL qualitatively, cold-RL is still the "best-effort internal proxy", and §VII (iii) moves the PARL reproduction to future work. My iter-11 Q4 explicitly asked for a stripped-down cold-PPO variant with PARL's reward on a 10-config subset. This iteration adds nothing here. The paper's third contribution pillar (C3, RL-WS with measured safety) is still not empirically compared to the closest prior work, and Table I's axis-based comparison is still the only direct contrast. For a DAC/DATE learning-based-topology paper, "we did not run the closest prior method but we compared axes" is the single largest remaining gap. A minimal response would have been: take PARL's public reward function (if available) or the paper's cold-PPO description and run it on 5 configs.

**[W3] Best-case 56.6\% is still a one-cell headline.** On MoE $K{=}32,N{=}8,b{=}4\times$, the 3-seed mean is $56.57\%\pm 0.55\%$. On the same cell, greedy alone is $52.12\%$; RL-WS adds $+4.45\%\mathrm{p}$. The abstract juxtaposes "RL-WS raises this to 28.2\%" with "best reaches 56.6\%" without the decomposition. A reader naturally imputes the $56.6\%$ to RL-WS, but the honest split is "greedy topology delivers $52.1\%$; RL-WS refines by $4.5\%\mathrm{p}$". The paper makes the correct statement in §VI.B ("RL-WS adds +4.3\%p over greedy on this cell") but the abstract framing remains misleading. Iter-11 W7 is unchanged at iter 12.

**[W4] Table VI "mean ± std over 12 seed-runs" is incorrectly described.** I recomputed the std over 12 seed-runs per workload from `ml_comparison_multiseed.json` and `ml_comparison_fast.json`'s $L_\text{adj}$ values and got:
- Tree AR: mean $13.67\%$, std (n=12) $=3.73\%$ -- paper says $0.49\%$
- Hybrid TP+PP: mean $34.14\%$, std $=9.91\%$ -- paper says $0.08\%$
- Uniform Rand: mean $36.68\%$, std $=8.76\%$ -- paper says $0.47\%$
- MoE: mean $45.86\%$, std $=8.69\%$ -- paper says $0.42\%$

The paper's numbers in Table VI reproduce only if one computes *the mean of the per-cell 3-seed stds* (i.e., for each of the 4 cells per workload, compute 3-seed std, then average those 4 stds). I verified: mean-of-cell-stds $=0.49 / 0.08 / 0.47 / 0.42$. Matches exactly. So the number itself is fine; the *caption* misdescribes what it is. "std over 12 seed-runs" is $\ge 3.7\%$ for every workload because the 12 runs span 4 cells with widely different savings. The correct caption is "mean of per-cell 3-seed population std (4 cells per workload)" or equivalently "within-cell seed variability averaged over the 4 cells". This is a factual error that must be fixed. It is not load-bearing for the scientific claim (the within-cell std is what matters for "seeds are stable"), but it is a numerical inconsistency that a careful reviewer will flag.

**[W5] The per-workload multi-seed column's narrative is also inflated.** Paper Table VI reports $+45.86\%$ multi-seed mean on MoE versus $+40.0\%$ single-seed mean. This is because the multi-seed column is computed on *4 best-budget cells per workload*, whereas the single-seed column uses *all 10 cells per workload* (which includes low-budget cells at $b=2\times$ where express placement does not help). Different denominators. The paper's single-seed "Overall +28.2\%" and multi-seed "Overall +32.59\%" are therefore not a like-for-like multi-seed confirmation of the headline number; they are the same data averaged over different subsets. This is stated in the caption ("16 best-budget cells") but the $\Delta$ column in Table VI is $+2.6\%\mathrm{p}$ (single-seed vs greedy), not "multi-seed vs single-seed". A reader may infer that multi-seed averaging boosts the mean from $+28.2\%$ to $+32.6\%$; it does not -- the boost is from restricting to best-budget cells.

**[W6] Fine-tuned GNN is single-seed per config.** §VI.C reports $-23.51\%$ mean on A2A FT-GNN but does not say how many seeds. Checking `ml_generalization_finetuned.json`: there is one entry per config, no seed field. So the FT-GNN result is a single random init. For an architectural-limit claim, a single-seed FT-GNN with 100 epochs per cell is borderline evidence -- on a low-signal workload like A2A, a different initialization could plausibly reach the $-15\%$ range rather than the $-23.5\%$ range. Iter-11 W6 said "a matched-compute fine-tuned GNN might close most of that gap". The FT-GNN's single-seed result shows that one particular init does not close the gap. A 3-seed FT-GNN on A2A would make the architectural-limit claim robust; one seed is suggestive.

**[W7] Surrogate hold-out still deferred.** Iter-11 Q5 asked for a leave-one-workload-out surrogate MSE. Iter 12 discloses that the split is random 80/20 and names the gap as "in-distribution refinement, not held-out generalization"; this is better than iter 11 but does not produce the experiment. The fine-tuned GNN result partially substitutes: FT-GNN uses the same surrogate and still wins on Ring/Pipeline and loses on A2A, suggesting the surrogate itself generalizes to Ring/Pipeline but is not the bottleneck on A2A. This is circumstantial evidence, not a hold-out validation.

**[W8] Latency-sensitivity is still analytical, still one cell.** Iter-11 W8 unchanged. The $\lambda\in\{1.0,1.5,2.0\}$ argument is still algebra on the MoE $K{=}32,N{=}8,b{=}4\times$ cell only. Iter-11 Q10 (what happens to Tree All-Reduce at low $b$ under $\lambda=2.0$?) is unanswered.

**[W9] "Never worse than greedy by construction" in Abstract and §VI.A is still the $\min$ tautology.** Empirically (S3) this operator turns out to be load-bearing at 20.8\% fire rate, which is non-trivial and worth reporting. But the *construction* guarantee is still A-or-B ensembling. The paper could responsibly write: "RL-WS is never worse than greedy *because* we measure both and keep the lower; empirically, this measured minimum rescues 20.8\% of seed-runs". That would convert a tautology-plus-data into an honest claim. The abstract still reads as if the construction itself is the contribution.

**[W10] Approximation guarantee of greedy, raised in iter-9 Q9 ($\rho$-proportional is 1.5--2.3x worse than uniform), is still unexplained.** The fallback in Algorithm 1 distributes remaining budget *proportional to traffic*, but Table V shows traffic-proportional is uniformly worse than uniform. The fallback therefore degrades to a worse-than-uniform allocation in the "no single link strictly improves" regime. The paper does not address this contradiction. Unchanged from iter 9 / iter 10 / iter 11.

## Questions (pointed)

**Q1 (iter 11, partially addressed).** The 16 best-budget cells are exactly the cells where greedy already performs best. The 24 skipped cells include all $b=2\times$ entries, where iter-12's own multi-seed data shows raw RL-WS regresses on 10/48 runs on $b\in\{4\times,7\times\}$ -- i.e., even the best-budget regime has a 20.8\% seed-regression rate. What is the seed-regression rate at $b=2\times$? My prior, given Fig.~\ref{fig:cost_saving_4panel}, is that it is materially higher. A 3-seed run on 6--10 representative $b=2\times$ cells would close this.

**Q2 (iter 11, carried).** Rerun RL-WS at $b=2\times$ on at least one unseen workload (Ring or Pipeline), so the fallback claim is tested outside the regime where express placement is guaranteed active.

**Q3 (iter 11, partially addressed by FT-GNN).** Is the FT-GNN single-seed? If so, report 3-seed FT-GNN on A2A at least, to make the architectural-limit claim as robust as the RL-WS claim.

**Q4 (iter 11, unchanged).** PARL on $\ge 5$ configs, with its own reward or a cold-PPO variant using our state/action space, is still missing. Is there a principled reason a 5-config PARL run is infeasible in the rebuttal window? At camera-ready, this is the single remaining experiment that would flip my vote.

**Q5 (iter 11, disclosed but not run).** Leave-one-workload-out surrogate validation.

**Q6 (iter 11, ties-bootstrap).** Nonparametric bootstrap of $\rho$ resampling *over 4 workload buckets* (not 40 replicates). The iter-11 version of this attack still applies to the multi-seed $\rho=0.776$: 4 distinct NL\% tiers, 4 cells per tier, 3 seeds per cell $= 48$ correlated observations. A bootstrap over the 4 tiers would yield a CI that honestly reflects the $n_{\text{effective}} \approx 4$ ceiling.

**Q7 (new, iter 12).** Please correct the Table VI caption. "mean ± std over 12 seed-runs per workload" is not what is reported. The reported std is the mean of per-cell 3-seed population stds across 4 best-budget cells. The distinction matters because std-over-12-runs is 3.7--9.9\% (genuine), and the 0.08--0.49\% numbers are within-cell seed stability, not across-cell stability. Both are valid to report; the caption should match the computation.

**Q8 (new, iter 12).** The multi-seed overall mean in Table VI is $+32.59\%$ on 16 best-budget cells, not a multi-seed confirmation of the single-seed $+28.2\%$. Please clarify that the abstract's $+28.2\%$ headline is still single-seed on all 40 configs and that the multi-seed column is a best-budget-subset lower-variance check, not a reaffirmation of the main number.

**Q9 (iter 9, persistent).** Why is Algorithm 1's traffic-proportional fallback compatible with Table V's finding that traffic-proportional is worse than uniform?

**Q10 (iter 11 Q10, unchanged).** Analytical $\lambda$-sensitivity on at least the 5 pre-fallback regression cells, not just the headline cell.

## Rating

| Metric | Score | Comment |
|--------|-------|---------|
| Novelty | 2.5/5 | Unchanged. NL\% predictor and min-ensemble RL are both modest novelty; warm-start + measured fallback is honest hygiene. Multi-seed and FT-GNN are hygiene upgrades, not novelty. |
| Technical Quality | 3.3/5 | **+0.3 over iter 11.** Multi-seed (48 runs, $\sigma \le 1.22\%$) and matched fine-tuned GNN (same surrogate, same epochs) are the iter-11 asks I said would move me. Table VI caption error (W4) and single-seed FT-GNN (W6) keep this below 3.5. |
| Significance | 2.8/5 | **+0.3 over iter 11.** The fallback's 20.8\% empirical fire rate (W3-softened) elevates the "measured safety" claim from tautological to operationally useful. Still limited by best-case-1-cell framing (W3 carried) and PARL not run. |
| Presentation | 3.5/5 | **−0.3 vs iter 11** due to the Table VI caption mismatch (W4). When corrected, this returns to 3.8. |
| Overall | 3.0/5 | **+0.2 over iter 11.** Multi-seed was the single largest iter-11 gap; it is now filled on the best-budget subset. PARL, full-40-multi-seed, and best-case-decomposition remain. |
| Confidence | 4.0/5 | Unchanged. All multi-seed / FT-GNN / correlation / ablation / best-cell numbers reproduced from raw JSON via `compute_stats.py` and `aggregate_results.py`. The Table VI std is the only place where the narrative and the numbers disagree. |

## Decision

**Borderline (leaning Weak Accept), 3.0/5.**

I am moving off Borderline Reject for the first time since iter 9. Iter 12 delivered on two of the three gating asks I listed at iter-11 (Q1 multi-seed CI, Q3 fine-tuned GNN); Q4 (PARL re-run) remains open but is now the *only* remaining iter-11 ask. The multi-seed data, in particular, forces me to empirically concede that the min-ensemble fallback is load-bearing (20.8\% fire rate, 10 regressions rescued), not merely tautological -- this was the single attack I was most confident about at iter 11, and I now partially withdraw it.

**Does the paper clear the DATE bar?**

- **DATE Weak Accept if:** Either (a) a partial PARL or cold-PPO-with-PARL-reward experiment on $\ge 5$ configs, or (b) multi-seed extended to all 40 configs (not just the best-budget 16), plus correction of the Table VI caption error. Either one converts this from 3.0 to 3.3-3.5.
- **DATE Borderline Reject if:** No further experiments are added and the Table VI error is not corrected. The paper would then still be at iter-11's "honest but limited" evidence level plus the new multi-seed slice, which is borderline for DATE's architecture track.
- **Hard DATE verdict at current evidence:** **Weak Accept** contingent on fixing W4 (Table VI caption) in revision. The experimental content now justifies the C3 pillar, which iter-11 did not. The remaining gaps (PARL, full-40-multi-seed, best-case decomposition, $\lambda$-sensitivity scope) are camera-ready work that can be staged.

I would upgrade to **Accept** if (a) + (b) above are both delivered at camera-ready. Without at least one, I would hold at Borderline Reject. The paper has improved materially at iter 12; it is within reach of the DATE bar for the first time.

---

**Under-100 verdict.** Borderline Weak Accept, first move off Reject since iter 9. Overall 3.0/5, Confidence 4/5. Multi-seed 48 runs (38/10/0, $\sigma\le 1.22\%$, fallback fires 20.8\% -- empirically load-bearing, iter-11 W3 partially conceded) and matched FT-GNN ($-23.5\%$ A2A, architectural-limit claim supported) reproduce. $\rho=0.776,\tau=0.652$ reproduce. **But:** multi-seed is 16/40 cells (best-budget only); PARL still not re-run; best-case $56.6\%$ still one cell ($52.1\%$ greedy attributable, $+4.5\%\mathrm{p}$ RL); **Table VI caption "std over 12 seed-runs" is factually wrong -- reported values are mean of per-cell 3-seed stds (must fix)**. **DATE: Weak Accept contingent on Table VI fix; Accept if PARL or full-40-multi-seed is added at camera-ready.**
