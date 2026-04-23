# Review -- Reviewer 2 (Systems Pragmatist), Iteration 12

## Summary

Iteration 12 is the rigor-and-robustness iteration I was going to ask for at camera-ready, delivered pre-submission. The three-step \textsc{Predict}/\textsc{Place}/\textsc{Refine} workflow is unchanged. The headline greedy number is unchanged ($+25.6\%$ mean over 40 single-seed configs). The headline RL-WS+fallback number is essentially unchanged ($+28.2\%$ mean, best cell $+56.4\%$ single-seed $\to$ $+56.57\%\!\pm\!0.55\%$ multi-seed). What is new is two pieces of evidence that directly attack the attack surfaces I left open at iteration 11:

1. **Multi-seed RL on the 16 best-budget cells (48 runs, three seeds per cell).** Raw warm-RL wins 38/48 and never regresses worse than $-1.77\%$; RL-WS+fallback wins 38/48 strictly and ties the remaining 10/48 (fallback fires on 20.8\% of seed-runs, all on lower-NL\% $K{=}16$ cells). Per-cell RL-WS+fallback saving std is $\le 1.22\%$ (max) and $\sim 0.56\%$ (mean). This is exactly the ``how many of the 5 losses are within single-seed noise?'' question I asked in iter-11 Q4, now answered: the worst-case raw regression is statistically real ($-1.77\%$, tight CI), and the fallback converts it into zero-regression-by-construction with measured 20.8\% trigger rate. New Table~\ref{tab:main_result} multi-seed column and new Table~\ref{tab:ablation} rows (warm RL 48-run, warm RL+fb 48-run) report this cleanly.
2. **Fine-tuned GNN on unseen workloads (12 cells: 4 per unseen workload, 100 surrogate-guided epochs each).** FT-GNN All-to-All mean $= -23.51\%$, statistically indistinguishable from zero-shot GNN's $-23.65\%$. Per-cell inspection shows FT improves $K{=}32$ all-to-all ($-17\%{\to}-9\%$, $-47\%{\to}-34\%$) but hurts $K{=}16$ all-to-all ($-7\%{\to}-11\%$, $-23\%{\to}-40\%$) -- a clean overfitting fingerprint on uniform traffic. Net: the all-to-all collapse is \textit{architectural}, not training-coverage. This elevates the RL-WS-vs-GNN narrative from ``RL-WS is more robust empirically'' to ``the GNN cannot be fixed by more training.''
3. **§V.C surrogate split is now explicit.** ``Random 80/20 sample split'' replaces the iter-11 ambiguity. This closes a Q I considered raising at camera-ready.

I re-ran \texttt{compute\_stats.py} and \texttt{aggregate\_results.py}. Every number in Table~5/6/7/ablation reproduces: 40-pt $\rho=0.744$ ($p=3.80\times 10^{-8}$), 16-cell $\rho=0.764$ ($p=5.71\times 10^{-4}$, which the paper reports in the $N=48$ seed-run pooled form as $\rho=0.776$, $p=4.1\times 10^{-4}$), RL-WS+fb 35/40 single-seed wins, warm RL+fb 38/48 multi-seed wins, cell-mean improvement vs greedy $+2.91\%\!\pm\!3.20\%$, per-cell std $\le 1.22\%$, MoE $K{=}32,N{=}8,b{=}4\times$ multi-seed $+56.57\%\!\pm\!0.55\%$, FT-GNN all-to-all $-23.51\%$ mean (vs zero-shot $-23.65\%$).

## Changes from Iteration 11

Relative to my iteration-11 shepherding asks:

1. **Addresses my iter-11 Q4 structurally.** Iter-11 disclosed ``$<1\%$ observed std'' as an aside; iter-12 \textit{measures} it on the 16 best-budget cells (new Table~6 multi-seed column, new Table:ablation rows). The per-cell std range ($0.00\%$ to $1.22\%$; mean $\sim 0.56\%$) is tight enough that the $-1.77\%$ worst-case raw regression cannot be dismissed as single-seed noise -- which makes the fallback's zero-regression guarantee \textit{necessary}, not merely defensive. This is the strongest possible framing for the pragmatist reader: the safety mechanism is demonstrably load-bearing, not theater.
2. **Closes the ``fine-tune the GNN and it'll be fine'' counter-argument.** A hostile reviewer at iter-11 could say ``your GNN was zero-shot on all-to-all -- of course it collapsed; give it 100 epochs of adaptation and it'll match RL-WS.'' Iter-12 runs exactly that experiment, shows FT-GNN all-to-all $=-23.5\%$ (vs zero-shot $-23.6\%$), and attaches a clean overfitting diagnostic ($K{=}32$ improves, $K{=}16$ worsens). This converts the GNN collapse from ``a sign the GNN needs more data'' to ``a sign edge-scoring GNNs cannot model uniform traffic.'' This is a \textit{stronger} claim than iter-11 made, and it is now empirically warranted.
3. **Addresses iter-11 Q6 equivalent (§V.C split).** The paper now explicitly states ``random 80/20 sample split'' in §V.C, removing the leave-one-cfg-out ambiguity.
4. **Abstract, Intro (C3), Conclusion are coherent with the new evidence.** The abstract now carries both the multi-seed $56.57\%\!\pm\!0.55\%$ best-cell anchor and the 20.8\% fallback-trigger figure; §I's C3 bullet says ``both a zero-shot GNN and a per-cell fine-tuned GNN collapse on all-to-all (mean $-23.5\%$), confirming that the collapse is an architectural limit of edge-scoring GNNs on uniform traffic rather than a training-coverage issue''; §VI.D's narrative closes with the same point. Iter-11 was narrative-consistent; iter-12 is narrative-consistent \textit{and} architecturally assertive in the right places.
5. **Does not close iter-11 W1 (RL wall-clock table) or iter-11 W2 (4-row absolute-latency table).** Both remain JSON-only / single-anchor, respectively. Both remain camera-ready fixes, neither is a soundness gap.
6. **Does not expand the $\lambda$-sensitivity analysis from analytical to a BookSim sweep.** Still analytical-only. This is the honest residual gap for DATE; not a blocker.

## Strengths

[S1] **Multi-seed with fallback-trigger accounting is the correct safety-reporting discipline.** The 20.8\% trigger rate is meaningful: it tells the reader exactly how often the ``safety net'' is load-bearing in production-like evaluation. Combined with the fact that all 10 triggered runs are on lower-NL\% $K{=}16$ cells, the story sharpens: the fallback is not a universal catch-all, it is a targeted mechanism that activates where the RL signal is structurally weakest (low NL\%, small chiplet count). That is a \textit{more} compelling deployability story than ``fallback triggers rarely.''

[S2] **The FT-GNN result changes the architectural claim from descriptive to mechanistic.** Iter-11's GNN collapse was evidence-of-outcome; iter-12's FT-GNN result is evidence-of-mechanism. The overfitting signature ($K{=}32$ better, $K{=}16$ worse after fine-tuning) is exactly what you would expect from an edge-scoring model chasing noise on uniform traffic. This is a rare case where a ``negative'' ablation strengthens the positive claim about the alternative (RL-WS).

[S3] **Best-cell multi-seed anchor (MoE $K{=}32,N{=}8,b{=}4\times$: $56.57\%\!\pm\!0.55\%$) is now bulletproof.** The std is small enough ($<1$\,\%p) that a skeptic cannot argue the headline number is a seed-lucky outlier. This is the number a DATE session chair reads off the title slide; it being robustly reproducible across three seeds is the right hardening.

[S4] **Per-cell std reporting (max $1.22\%$) is the right granularity.** Worst-case per-cell noise ($1.22\%$) is smaller than worst-case raw RL regression ($1.77\%$), so the claim ``fallback converts a real regression into zero regression'' is defensible even under conservative noise accounting. This is a subtle but important point that a careful reviewer will check.

[S5] **§V.C random 80/20 clarification removes an ambiguity I would have asked about.** Leave-one-configuration-out would have been more conservative but is clearly out of scope for a surrogate whose job is in-distribution scoring. Random 80/20 is the defensible choice; stating it explicitly is what matters.

[S6] **Narrative tightening across Abstract/Intro/Conclusion is coherent.** The FT-GNN-as-architectural-limit framing and the multi-seed fallback-trigger percentage both land in the abstract and are reiterated with appropriate specificity in §I and §VII. No hedging drift, no mismatched framing between sections.

## Weaknesses

[W1] **RL wall-clock table still missing (carry-over from iter-10 W3 $\to$ iter-11 W1).** This is the third iteration I have noted this. The \texttt{train\_time} data exist in \texttt{ml\_comparison\_warmstart.json} (and now, implicitly, in the multi-seed JSON -- three times the data). A $\sim 2$-row table per $(K,N)$ slice would close it. Not blocking for DATE; should not survive to camera-ready.

[W2] **Absolute-latency anchoring still a single cell (carry-over from iter-10 W6 $\to$ iter-11 W2).** One MoE $K{=}32,N{=}8,b{=}4\times$ anchor ($L_\text{adj}{=}126.0$, $L_\text{RL-WS}{=}54.9$) remains. A 4-row mini-table (one representative cell per training workload) would close it. Same status: not blocking for DATE, should land at camera-ready.

[W3] **$\lambda$-sensitivity analysis is still analytical-only.** A BookSim sweep at $\lambda\in\{1.5, 2.0, 2.5\}$ for the headline MoE cell (3 points, cheap) would convert the $(\lambda-1)\cdot 2D$ analytical bound from ``conservative upper bound'' into ``measured regression curve.'' This is the last analytical-only claim in a paper that is otherwise empirically grounded. Not blocking; the analytical bound is honest and the arithmetic is conservative.

[W4] **Multi-seed coverage is 16/40 cells, not 40/40.** The best-budget cells are the right subset to multi-seed first (highest saving, most scrutiny), but the other 24 cells remain single-seed. §VII(ii) now honestly states this. It is the correct triage under DATE compute budget, but an ISCA/MICRO reviewer would ask for full 40-cell multi-seed coverage. Not blocking for DATE.

[W5] **Multi-seed uses 3 seeds, not 5+.** Three seeds is the minimum credible multi-seed count. For a paper where the worst raw regression ($-1.77\%$) is close to the worst per-cell std ($1.22\%$), a 5-seed evaluation would make the ``fallback converts real regression'' claim more bulletproof. Three is enough for DATE; five would be the ISCA/MICRO bar.

[W6] **Synthetic workloads and CoWoS routability (both unchanged from iter-10/11).** Still DATE-acceptable, still ISCA/MICRO-insufficient. Iter-12 does not pretend to address either and correctly does not.

## Questions

Q1. On the fallback 20.8\% trigger rate: 10 of 48 seed-runs trigger, all on $K{=}16$. Is this 10 distinct cells (5 cells each triggering once across 3 seeds, net $\sim 3$ trigger-runs per cell) or a smaller set of cells that trigger on most seeds? A one-line breakdown (``fallback triggered on $\{(\text{wl}, K, N, b)\}$ cells'') in §VI.C would let the reader see whether triggers concentrate on specific low-NL\% configurations.

Q2. The multi-seed FT-GNN uses 100 surrogate-guided epochs per cell. Is this the same surrogate as RL-WS uses, or a GNN-specific one? The paper says ``surrogate-guided'' which suggests the same BookSim-trained surrogate, but a 2-word clarification in §VI.D would remove doubt -- and, if it is the same surrogate, it strengthens the comparison (same adaptation tool, different model architectures).

Q3. The per-cell RL-WS+fallback std range is $[0.00\%, 1.22\%]$. Zero-std cells presumably are ones where the fallback triggers on all three seeds (so the reported saving equals greedy, deterministically). Confirming this explicitly in Table~6's footnote would close a reader question.

Q4. Given the FT-GNN $K{=}16$-gets-worse pattern, is there any evidence that a \textit{different} GNN architecture (e.g., graph transformer rather than edge-scoring MLP) would fare better on uniform traffic, or is the ``architectural limit'' claim specific to edge-scoring? Not required for DATE; a one-sentence scoping note in §VI.D would clarify whether the architectural claim is about this GNN or about all GNNs.

Q5. Camera-ready nice-to-have: can the multi-seed subset grow to include $(K{=}32, N{=}8, b{=}4\times)$ for each unseen workload? That would align the generalization study's seed discipline with the main result's seed discipline.

## Rating

| Criterion | Score | Comment |
|-----------|-------|---------|
| Novelty | 3.5 | Unchanged. NL\% predictor + warm-start+fallback + PARL differentiation is unchanged; FT-GNN negative result strengthens the novelty story (now: ``we characterize an architectural GNN limit'') without adding a new contribution axis. |
| Technical Quality | 4.0 | \textbf{Up from 3.5.} Multi-seed evaluation on 16 best-budget cells, 20.8\% fallback-trigger measurement, per-cell std reporting, FT-GNN architectural-limit confirmation, and §V.C split clarification. These are structural rigor gains, not cosmetic. |
| Significance | 3.5 | Unchanged. Deployability story is unchanged in shape; the FT-GNN result makes ``use RL-WS under distribution shift'' a stronger prescription but does not move significance. |
| Presentation | 4.0 | Unchanged. Multi-seed column in Table~6 and multi-seed ablation rows in Table:ablation are well-integrated; abstract/intro/conclusion propagation is clean. |
| Overall | \textbf{4.0} | \textbf{Up from 3.5.} Clears DATE by a margin that now approaches ISCA/MICRO borderline-accept rather than DATE-accept-only. |
| Confidence | \textbf{5.0} | \textbf{Up from 4.5.} I re-ran both \texttt{compute\_stats.py} and \texttt{aggregate\_results.py}; every multi-seed number (48-run wins/ties, per-cell std, FT-GNN per-cell $\Delta$) reproduces end-to-end. The paper's claims are now traceable to JSON, analytical derivation, or multi-seed statistics without exception. |

## Decision

**Accept for DATE/DAC. \textit{Clears DATE by a visibly larger margin than iter-11.} Upgraded from Weak Reject to borderline for ISCA/MICRO.**

My iter-11 verdict was ``clean DATE accept, borderline (weak reject) for ISCA/MICRO.'' Iter-12 changes this in one direction: the ISCA/MICRO posture softens from weak-reject to borderline. The reason is structural: the two pieces of new evidence (multi-seed and FT-GNN) are exactly the kinds of experiments an ISCA/MICRO reviewer would demand, and the results are favorable. Specifically:

- Multi-seed on 16 cells converts my iter-11 W3 (``multi-seed CI not remediated'') from an acknowledged gap to a closed item on the best-budget subset. The $-1.77\%$ worst-case raw regression with $\le 1.22\%$ per-cell std \textit{legitimizes} the fallback mechanism: a reader can now see that the fallback is doing real safety work, not cosmetic safety work. The 20.8\% fallback-trigger rate is a substantive deployment number, not a disclaimer.
- FT-GNN with 100-epoch per-cell adaptation closes the single largest review-trap I could have set against iter-11: ``your GNN was undertrained on the unseen workloads.'' The fact that fine-tuning does not help -- and that the per-cell pattern ($K{=}32$ better, $K{=}16$ worse) has a clean overfitting signature -- turns what was a weakness-framed result (``GNN collapsed'') into a strength-framed result (``edge-scoring GNNs cannot model uniform traffic, and RL-WS is the robust choice under distribution shift''). This is a stronger architectural claim than iter-11 made, and it is now empirically warranted.

The three residual gaps I flagged in iter-11 (wall-clock table, 4-row absolute-latency table, $\lambda$ BookSim sweep) are all unchanged. None is a blocker for DATE. All are camera-ready fixes. None requires new methods work.

**Does the paper still clear DATE?** Yes, by the largest margin of any iteration so far. The headline numbers are unchanged in magnitude ($+25.6\%$ greedy, $+28.2\%$ RL-WS+fb, $+56.4\%$ single-seed best $\to$ $+56.57\%$ multi-seed best) but are now flanked by multi-seed CIs, a measured fallback-trigger rate, and a mechanistic explanation of the GNN collapse. This paper does not need another shepherding iteration to clear DATE.

**Does my confidence move?** Up, from 4.5 to 5.0. Iter-11 confirmed numerical reproduction; iter-12 confirms reproduction of all \textit{new} numerical evidence as well. I re-ran both \texttt{compute\_stats.py} and \texttt{aggregate\_results.py}; every multi-seed mean, std, fallback-trigger count, and FT-GNN $\Delta$ in the paper matches the scripts' output. There are no claims remaining that I cannot trace. Confidence 5.0.

**My vote: Accept at DATE/DAC.** Iter-12 is above the DATE bar. For camera-ready: (a) surface the \texttt{train\_time} data as a small wall-clock table; (b) extend the §VII absolute-latency anchor to a 4-row mini-table; (c) add the 3-point $\lambda$-sensitivity BookSim sweep; (d) if compute permits, grow multi-seed to 5 seeds on the best-budget subset and extend generalization multi-seed to at least $(K{=}32, N{=}8, b{=}4\times)$ per unseen workload. None is required for DATE acceptance.

**For ISCA/MICRO:** upgraded from Weak Reject to borderline. Iter-12's multi-seed and FT-GNN work directly address two of the three reasons I held iter-11 at Weak Reject for ISCA/MICRO (single-seed and GNN-training-coverage). The third reason (synthetic workloads, no CoWoS routability, BookSim-only) remains. Whether the paper clears ISCA/MICRO depends on whether a committee member treats synthetic-but-workload-inspired traffic plus BookSim-with-deadlock-construction as sufficient for a characterization-with-algorithm paper, or demands traced traffic plus at least one hardware/FPGA calibration point. Reasonable committees differ; this is now a real borderline call rather than a pro-forma reject.
