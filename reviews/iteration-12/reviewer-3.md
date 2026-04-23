# Review -- Reviewer 3 (ML/Application Expert), Iteration 12

## Summary

Iteration 12 is the first iteration since I picked up this paper that delivers new experimental data rather than reframing. The authors executed the two experimental asks I flagged as most tractable in iter-11 (multi-seed CIs and a fine-tuned GNN row) and wove both into Abstract, Intro, Table~\ref{tab:main_result}, Table~\ref{tab:ablation}, Table~\ref{tab:generalization}, Fig.~\ref{fig:rho_nl_saving}, Limitations, and Conclusion. Three asks remain undelivered: the surrogate calibration plot, a direct PARL experimental reproduction, and an end-to-end Amdahl bracket. The $80/20$ surrogate split is now disclosed as in-distribution refinement rather than held-out generalization---a scoping clarification rather than a calibration fix.

My verification reruns (`compute_stats.py`, `aggregate_results.py`) match every headline number in the manuscript: greedy $+25.64\%$, RL-WS+fb $+28.23\%$, pooled-40 $\rho=0.744$, 16-cell best-budget multi-seed mean cell-improvement $+2.91\% \pm 3.20\%$ with per-cell std $\le 1.22\%$, FT-GNN all-to-all $-23.51\%$ vs ZS $-23.65\%$, RL-WS generalization 6/6 wins. Multi-seed fallback activates on 10/48 runs (20.8\%), all on $K{=}16$ Tree/Hybrid cells; the claim ``worst-case raw-RL regression $-1.77\%$'' reproduces exactly.

## Changes from Iteration 11

**Newly executed (W1, W4 closed or materially tightened):**
- **Multi-seed evaluation on 16 best-budget cells (48 RL-training runs).** Table~\ref{tab:main_result} gains a ``RL-WS+fb (3 seeds, best-b)'' column with per-workload mean $\pm$ std; Table~\ref{tab:ablation} gains two new rows (``Warm RL 48 runs, 3 seeds'' and ``Warm RL + fallback 48 runs, 3 seeds'') at $-2.7\%/-2.9\%$ vs-greedy; Fig.~\ref{fig:rho_nl_saving} overlays 16 large squares with $\pm 1\sigma$ error bars on the 40-point scatter; the pooled best-budget correlation is reported as $\rho=0.776$ ($p=4.1\times 10^{-4}$) on multi-seed-averaged cells. The key variance numbers---per-cell std $\le 1.22\%$ (max), $0.56\%$ (mean)---are supported by my rerun.
- **Fine-tuned GNN column in Table~\ref{tab:generalization} (12 configs).** FT-GNN all-to-all $-23.5\%$ vs zero-shot $-23.6\%$; Ring and Pipeline essentially unchanged or slightly worse. Paper correctly reads this as architectural rather than training-coverage driven. The per-cell breakdown in §V.D (FT helps $K{=}32$ A2A, hurts $K{=}16$ A2A as overfitting on a small per-cell signal) is a stronger reading than a flat ``FT doesn't help.''

**Newly disclosed (not executed):**
- **Surrogate train/val split clarified** in §V.C: ``random 80/20 split (seed=42)... well-matched reward model for in-distribution refinement rather than a held-out generalization predictor.'' This converts an implicit assumption into an explicit scoping choice. It does \emph{not} replace the calibration plot I asked for in iter-10 and iter-11.

**Unchanged gaps:**
- **No surrogate calibration figure or table.** The 288-sample corpus MAE/max-error breakdown is still not shown. The iter-10 concrete miscalibration (tree-K16N8-$2\times$: 37.7 predicted vs 53.1 measured) is not addressed.
- **No direct PARL reproduction.** Cold-RL-as-proxy framing carried forward from iter-11; Limitations item (iii) explicitly labels PARL reproduction as future work.
- **No end-to-end Amdahl paragraph.** Discussion remains NoI-only.
- **Multi-seed coverage is $16/40$ cells, not $40/40$.** Limitations item (ii) acknowledges this.

## Strengths

**[S1] Multi-seed execution, though partial, is not cosmetic.** Three concrete facts emerge that were genuinely unavailable in iter-11: (a) per-cell RL-WS+fb std $\le 1.22\%$, which makes the $+2.6$--$2.9\,\%p$ RL-WS-over-greedy uplift mechanically credible, not just asserted; (b) raw-RL loses on 10/48 seed-runs (20.8\%) with worst regression $-1.77\%$, which quantifies the exact probability mass the fallback is insuring against; (c) the fallback triggers \emph{only} on lower-NL\% $K{=}16$ Tree/Hybrid cells, meaning the safety mechanism is load-bearing precisely in the regime where the surrogate is least well-calibrated. The third fact is, in my view, the strongest ML result added in this iteration: it converts ``fallback is there for correctness'' into ``fallback is doing measurable work on a characterizable subset.''

**[S2] The fine-tuned GNN experiment is the honest way to run this comparison.** FT-GNN matching ZS-GNN at $-23.5\%$ on all-to-all kills the natural referee question (``maybe the GNN just needs per-cell adaptation''). The per-cell breakdown showing FT helps $K{=}32$ A2A but hurts $K{=}16$ A2A---consistent with overfitting on a small uniform-traffic gradient---is a stronger, more falsifiable reading than a flat ``architectural limit'' claim. This turns Table~\ref{tab:generalization} from a two-method contrast into a three-method contrast that controls for the adaptation-access confound.

**[S3] Abstract and Conclusion were updated in step with the experiments.** Iter-11's single-seed headline is now ``$56.57\%\!\pm\!0.55\%$ multi-seed mean'' on the best cell, ``48 RL-training runs, three seeds per cell,'' ``20.8\% fallback activation rate.'' For DATE this is important: an architecture-track reader should not have to dig into the ablation to discover that the headline cell is multi-seed.

**[S4] The surrogate-split disclosure, while not the calibration plot I asked for, is the right scoping move.** Calling the 80/20 split ``a well-matched reward model for in-distribution refinement rather than a held-out generalization predictor'' narrows the surrogate claim from something that would fail out-of-distribution scrutiny to something that is self-consistent with what the RL policy is actually doing (searching within a configuration, guided by a reward model trained on that configuration). It also pre-empts the obvious reviewer question of ``why don't you leave-one-cell-out?''

**[S5] The fallback-activation characterization is quantitatively honest.** The manuscript does not round up to ``fallback triggers rarely''; it states 20.8\%, it enumerates the subset ($K{=}16$ Tree and Hybrid at $b{=}4\times/b{=}7\times$), and it frames fallback as converting a 20.8\% regression probability into a zero-regression guarantee. This is the right tone for the ML-systems subcommunity that will read this paper most skeptically.

## Weaknesses

**[W1] 16/40 multi-seed coverage is a half-close of the ask, not a full close.** The headline table (Table~\ref{tab:main_result}) still uses 40 single-seed cells for the main ``Greedy / RL-WS+fb / $\Delta$'' columns, with the multi-seed column appended alongside. The multi-seed 16-cell subset is the best-budget selection, which is deliberately favorable---the regimes where RL-WS helps most are exactly the regimes where variance should also be easiest to control. The remaining 24 cells (non-best budgets, including the $b{=}2\times$ crossover region where iter-10 flagged surrogate miscalibration) are still single-seed. For DATE I will accept this as ``enough to verify the headline''; I would not accept it for MLSys.

**[W2] Surrogate calibration remains un-shown for a third consecutive iteration.** The 80/20-split disclosure addresses \emph{what} the surrogate is for, but not \emph{how well} it approximates BookSim on the configurations the policy actually searches. The miscalibration I flagged in iter-10 (tree-K16N8-$2\times$: 37.7 predicted vs 53.1 measured, $\sim 29\%$) is in the exact subset where the iter-12 multi-seed data now show the fallback fires most often. The two observations are consistent---fallback is doing the work because the surrogate is locally poor---but the paper does not connect them. A one-figure appendix calibration plot (held-out MAE, predicted-vs-measured scatter on the 288-sample corpus) would upgrade that connection from implication to evidence. This is still cheap and still absent.

**[W3] PARL reproduction is now pinned as future work and will stay there.** Limitations item (iii) is honest, and I accepted this posture in iter-11. With multi-seed in, it is clearer that the cold-RL-as-proxy framing is carrying weight the proxy should not carry: the $+11.3\%$ cold worst-case vs $+1.7\%$ warm worst-case contrast is now reported on single-seed cold-RL data (24 configs) against multi-seed warm-RL data (16 configs). A 3-seed cold-RL rerun on the same 24 configs would at least make the cold-vs-warm contrast seed-comparable.

**[W4] No end-to-end framing, three iterations in.** This has now been my W6 in iter-10, W6 in iter-11, and W4 in iter-12. Even a single paragraph in the Discussion---``If NoI accounts for $\alpha \in [0.15, 0.40]$ of MoE K32N8 iteration time, the $56.6\%$ NoI-latency reduction corresponds to $8.5\%$--$22.6\%$ wall-clock speedup''---would ground the significance claim for the ML-systems reader. The multi-seed execution shows the authors are willing to do non-trivial compute; refusing to write the Amdahl paragraph now reads less like triage and more like deliberate avoidance. I cannot insist on a \emph{number}, but I can insist on a \emph{bracket}.

**[W5] FT-GNN per-cell reading is slightly overreaching.} The paper interprets FT helping on $K{=}32$ A2A and hurting on $K{=}16$ A2A as overfitting on a small signal. This is plausible, but the actual mean numbers---$K{=}32$: $(-17\%, -47\%) \to (-9\%, -34\%)$; $K{=}16$: $(-7\%, -23\%) \to (-11\%, -40\%)$---show a $K{=}16$ $N{=}8$ drop from $-23.4\%$ to $-39.8\%$, which is a huge single-cell swing. With only 4 FT-GNN all-to-all cells total, I would soften ``overfitting on the small per-cell signal'' to ``consistent with high-variance fine-tuning on a small per-cell sample'' and move the architectural-limit claim to rest primarily on the ZS-vs-FT \emph{mean} equality, not on the per-cell pattern. This is a writing tweak, not a new experiment.

**[W6] ``RL-WS wins 6/6'' on unseen workloads is still on the 2-cell subset, and the FT-GNN columns cover 4 cells.** Iter-11 W5 asked for a subset-matched GNN row. Iter-12 added the FT-GNN column but kept the 4-cell GNN rows vs 2-cell RL-WS rows. Table~\ref{tab:generalization} would be cleaner as either ``both methods on the same 2 cells'' or ``both methods on the same 4 cells.'' This is a reselection of existing runs, not new experiments, and is now the last remaining apples-to-apples gap in the generalization story.

## Questions

1. **Multi-seed for the remaining 24 cells.** Is a 3-seed sanity run on the 24 non-best-budget cells (or at least the $b{=}2\times$ crossover cells) feasible for the camera-ready? The iter-12 multi-seed fallback-activation pattern suggests these are exactly the regimes where single-seed noise could be largest.

2. **Cold-RL multi-seed.** Can the 24-config cold-RL evaluation be re-run at 3 seeds so the cold-vs-warm worst-case contrast is seed-matched? The current $+11.3\%$ cold worst vs $+1.7\%$ warm worst comparison mixes single-seed (cold) with effectively single-seed (warm 40-config) and three-seed (warm 16-best). A seed-matched version would tighten the ablation.

3. **Surrogate calibration appendix.** Even without a figure, can you add a single table with held-out MAE and max error of the 3-layer MLP across the 288-sample corpus, broken down by workload and $(K,N,b)$ tier? This is the minimum evidence that the surrogate the policy is optimizing is a good proxy for BookSim.

4. **Amdahl bracket.** Will a single paragraph with a $[\alpha_\text{low}, \alpha_\text{high}]$ bracket on the $56.6\%$ headline cell appear in the camera-ready?

5. **Subset-matched generalization.** Will Table~\ref{tab:generalization} be updated so GNN (ZS), GNN (FT), and RL-WS all report on the same configuration set (either 2 cells or 4 cells per unseen workload)?

6. **Fallback-activation correlation.** The 10 fallback activations are on Tree and Hybrid $K{=}16$ cells. Can you confirm whether these are also the cells with the worst surrogate MAE? If so, this would be the cleanest possible connection between W2 (calibration) and the fallback-activation subset.

## Rating

- Novelty: 3.5/5 (unchanged; three-step framing and measured fallback are still the distinctive pieces)
- Technical Quality: 3.5/5 (up from 3/5 in iter-11; multi-seed on 16 best-budget cells and FT-GNN row are both non-trivial additions; surrogate calibration gap and partial multi-seed coverage hold this short of 4/5)
- Significance: 3/5 (unchanged; end-to-end Amdahl bracket un-addressed for the third iteration)
- Presentation: 4/5 (unchanged; Abstract/Conclusion correctly updated in step with experiments; multi-seed column is well-integrated into existing tables rather than bolted on)
- Overall: 3.5/5 (up from 3/5)
- Confidence: 4/5

## Decision

**Borderline leaning Weak Accept (soft-accept)** -- Iter-12 moves me off the hard borderline I held in iter-10 and iter-11. Two of my five iter-10 experimental asks have been executed in a way I can verify by rerun, and the core ML-rigor concern (is the $+2.6$--$2.9\,\%p$ RL-WS-over-greedy uplift an artifact of single-seed noise?) is materially answered by per-cell std $\le 1.22\%$. The fine-tuned GNN result is the right experiment to have run; its outcome (FT does not rescue all-to-all) strengthens rather than weakens the paper's robustness-under-distribution-shift story, because the ``architectural limit'' claim is now defended against the obvious adaptation-access objection.

**The DATE bar.** DATE is an architecture-track venue, not an ML-systems venue, and the submission's center of gravity remains the $\Theta(K^{3/2})$ phantom-load analysis, workload-aware greedy allocator, NL\% predictor, and measured-fallback safety mechanism. Iter-12 adds enough ML rigor on top---multi-seed variance on the headline cells, FT-GNN control, explicit surrogate scoping---that I can defend this as publishable at DATE. The three remaining gaps (calibration plot, PARL reproduction, Amdahl bracket) are each a one-iteration ask, and none of them changes the architectural core. If the PC treats Borderline as soft-accept, I now \emph{concur} rather than \emph{not fighting either direction}. If the PC treats Borderline as soft-reject, I would fight for acceptance, noting that the multi-seed and FT-GNN additions close the two most load-bearing ML-rigor concerns raised across iterations 9--11. I land at Overall 3.5/5, Confidence 4/5.
