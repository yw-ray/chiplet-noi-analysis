# Review -- Reviewer 4 (Theory/Analysis Expert), Iteration 12

## Summary

Iter 12 is an evidence-consolidation iteration rather than a theoretical-rigor iteration. The analytical core (Theorem~1 + Corollary~\ref{cor:theta} + NL\% formula + Algorithm~1 non-claim disclosure) is unchanged from iter 11. New in iter 12: (i) multi-seed correlations --- 16 best-budget cells aggregated over three independent RL seeds yield Spearman $\rho=0.776$ ($p=4.1\times 10^{-4}$), Kendall $\tau=0.652$ ($p=1.08\times 10^{-3}$); (ii) 48 RL-training runs (16 cells $\times$ 3 seeds) with per-cell RL-WS+fallback std $\le 1.22\%$ and 20.8\% fallback-activation rate; (iii) fine-tuned GNN confirms architectural limit on All-to-All ($-23.5\%$); (iv) surrogate split clarified as random 80/20 in-distribution. None of these touch the proofs; they harden the statistical claims around NL\% and the measured fallback guarantee. My three cosmetic nits from iter 11 (one-line corollary proof, XY/YX asymmetry, $\tau_a$ vs $\tau_b$) remain unactioned --- still cosmetic.

## Changes from Iteration 11

**[C1] Multi-seed correlation added ($\rho=0.776$, $\tau=0.652$ on 16 cells $\times$ 3 seeds).** The paper now reports three coherent correlation readings in §Non-Locality: (a) pooled 40-point single-seed $\rho=0.744$ / $\tau=0.593$, (b) 16 best-budget cells single-seed $\rho=0.764$ / $\tau=0.634$ under RL-WS+fb, and (c) 16 cells multi-seed $\rho=0.776$ / $\tau=0.652$. I re-ran \texttt{compute\_stats.py} under the paper's .venv: it reproduces pooled $\rho=0.744$ ($p=3.80\times 10^{-8}$) and 16-cell single-seed $\rho=0.764$ ($p=5.71\times 10^{-4}$) exactly. The multi-seed $\rho=0.776$ is a modest but directionally correct tightening over the single-seed 16-cell $\rho=0.764$, consistent with averaging RL stochasticity out of the dependent variable. This is the statistically honest way to report it and it does not overstate.

**[C2] Multi-seed ablation rows and new Table 6 column.** Table~\ref{tab:ablation} gains multi-seed rows; Table~\ref{tab:main_result} gains a multi-seed column reporting mean$\pm$std over 12 seed-runs per workload on the 16 best-budget cells. Per-cell std $\le 1.22\%$ and fallback triggered on 10/48 runs (20.8\%), all on low-NL\% $K{=}16$ cells. The critical theoretical content here is the 20.8\% fallback-activation number: the paper correctly frames this as \textit{empirical evidence} for the measured post-hoc safety property, not a formal guarantee --- the guarantee is already ``never worse than greedy'' by construction, and the new number just calibrates how often the guarantee actually fires. Good framing.

**[C3] Fine-tuned GNN confirms architectural limit on All-to-All.** The $-23.5\%$ All-to-All gap is now pinned to \textit{architecture} (GNN expressivity) rather than \textit{training coverage}, closing a plausible alternative explanation. This is not a theoretical claim but it strengthens the paper's RL-WS-is-the-robust-choice thesis by eliminating a confound. The Limitations section (v) now acknowledges that NL\% was evaluated under XY-style shortest-path routing; this is an appropriate scoping.

**[C4] Surrogate split clarified as random 80/20 (seed=42), in-distribution.** Transparent and correct. For a screen-level predictor claim this is the right evaluation regime; any stronger claim (e.g., distribution-shift generalization) would need a held-out workload split, which the paper explicitly does not claim.

**[C5] Abstract headline number updated to 56.6\% (multi-seed mean 56.57$\pm$0.55\%).** Internally consistent with single-seed max 56.43\%. No overclaim.

## Strengths

**[S1] Multi-seed reporting is the correct response to a plausible iter-11 challenge.** A hypothetical reviewer could have said ``$\rho=0.764$ on 16 points with one RL seed per cell could be a lucky-seed artifact.'' The paper now answers that directly: three seeds, per-cell std $\le 1.22\%$, and the correlation actually tightens slightly to $\rho=0.776$. This is not a rigor upgrade to the theory, but it is a rigor upgrade to the empirical support for the NL\%-as-screen claim.

**[S2] The 20.8\% fallback-activation rate is an honest calibration.** The paper resists the temptation to sell this as a ``only rarely fires'' soft result and instead frames it as ``20.8\% of seed-runs would have regressed $-1.77\%$ absent fallback.'' That framing makes fallback operationally load-bearing rather than a cosmetic safety net, which matches how post-hoc checkpoints actually function.

**[S3] The three correlation readings (40-point pool, 16-cell single-seed, 16-cell multi-seed) are mutually consistent.** $\rho=0.744 \to 0.764 \to 0.776$ as the sample regime moves from ``noisy 40-point pool'' to ``best-budget 16 points'' to ``best-budget 16 points with seed-averaged $y$''. This is exactly the direction you expect from a real signal with bounded noise, not a fishing artifact.

**[S4] Theoretical core remains clean and unchanged.** Theorem~1 + Corollary~\ref{cor:theta} + Algorithm~1 non-claim disclosure are exactly as in iter 11; no new proofs were introduced and no existing proofs were weakened. This is the right behavior for a consolidation iteration.

## Weaknesses

**[W1] Residual nits (a), (b), (c) from iter 11 are unactioned.** (a) Corollary~\ref{cor:theta} still lacks a one-line proof note; (b) Table III XY/YX asymmetry still uncommented in the caption; (c) Kendall $\tau_a$ vs $\tau_b$ still unspecified. All three are presentation-level and do not affect correctness. I am not conditioning my vote on them; they are camera-ready fixes.

**[W2] The 16-cell sample is small.** $\rho=0.776$ at $n=16$ with $p=4.1\times 10^{-4}$ is overwhelmingly significant, but a strict theoretician would note that 16 points spread across 4 NL\% tiers is not a dense sample of the NL\% axis. The pooled 40-point $\rho=0.744$ addresses this concern and the two numbers agree, but future work could broaden the NL\% grid.

**[W3] The multi-seed evaluation covers the 16 best-budget cells only.** Extending to all 40 configurations is explicitly future work (Limitations ii). This is an acceptable scoping but worth flagging: the 40-point single-seed $\rho=0.744$ is not multi-seed-verified.

**[W4] No new theoretical content.** Same note as iter 11 W4: this is by design for a consolidation iteration, not a defect.

## Questions

**[Q1]** (Carryover from iter 11.) Is the reported $\tau=0.652$ on multi-seed the $\tau_b$ (ties-corrected) estimator? With 4 distinct NL\% tiers and $n=16$, ties on the $x$-axis are structural; if $\tau_a$, the $p$-value is conservative. A one-word clarification in the caption would suffice.

**[Q2]** (Carryover from iter 11.) The XY vs YX asymmetry in Table III on a square grid under uniform traffic is still uncommented. Would the authors add a one-sentence note (e.g., ``under XY the east/west-half split of center-crossing traffic differs from the north/south-half split under YX by a tie-breaking convention'') to the caption?

**[Q3]** The multi-seed fallback-activation rate of 20.8\% is quoted as 10/48 runs, all on $K{=}16$ low-NL\% cells. Is this activation rate stable as the seed count grows beyond 3? I do not require this for acceptance, but a 5- or 10-seed follow-up would make the ``measured safety guarantee'' framing even stronger.

## Rating

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Novelty | 3.5/5 | Unchanged from iter 11. |
| Technical Quality | 4.5/5 | Unchanged from iter 11. Core theorem, corollary, and non-claim disclosure are untouched. Multi-seed evidence strengthens the empirical support but does not move this axis. |
| Significance | 3.5/5 | Unchanged from iter 11. The NL\%-as-screen claim now rests on three mutually consistent correlation readings; this is consolidation, not expansion. |
| Presentation | 4.5/5 | Unchanged from iter 11. The three cosmetic nits remain; the Table~\ref{tab:ablation} multi-seed rows and Table~\ref{tab:main_result} multi-seed column are cleanly integrated. |
| Overall | 4.0/5 | Held from iter 11. Multi-seed evidence is additive ($\rho=0.764 \to 0.776$ is directionally right but modest), the three cosmetic nits persist, and the theoretical core is unchanged. |
| Confidence | 5/5 | I re-verified: (a) \texttt{compute\_stats.py} reproduces pooled $\rho=0.744$ and single-seed 16-cell $\rho=0.764$ exactly; (b) the multi-seed $\rho=0.776$ is a consistent tightening over single-seed $\rho=0.764$; (c) the 20.8\% fallback-activation rate is the 10/48 figure the ablation rows report; (d) the Corollary~\ref{cor:theta} substitution holds at $K \in \{4,16,64,256\}$ (re-checked from iter 11). |

## Decision

**Accept.**

Iter 12 consolidates the empirical support for the NL\%-as-screen claim by adding a multi-seed correlation reading ($\rho=0.776$, $\tau=0.652$) that tightens the iter-11 single-seed 16-cell $\rho=0.764$ in the expected direction, and adds 48-run multi-seed ablation evidence (per-cell std $\le 1.22\%$, 20.8\% fallback-activation) that calibrates the measured post-hoc safety property. The theoretical core --- Theorem~1 for $\alpha_{\max} = R \cdot \lceil C/2 \rceil \cdot \lfloor C/2 \rfloor$, Corollary~\ref{cor:theta} for $\Theta(K^{3/2})$ on square grids, and Algorithm~1's explicit non-claim on approximation guarantees --- is unchanged from iter 11 and remains clean. The three residual nits I flagged in iter 11 (one-line corollary proof, XY/YX asymmetry note, $\tau_a$ vs $\tau_b$ disambiguation) persist but are cosmetic and camera-ready-tractable.

I carry my iter-11 verdict forward: **Accept at Overall 4.0/5, Confidence 5/5**. The overall score does not move --- iter 12 is a consolidation, not an upgrade on any of the five dimensions --- but the Accept stance is more robust now that the NL\% correlation has been reproduced across three coherent sample regimes (40-pool, 16-cell single-seed, 16-cell multi-seed) with monotonically tightening $\rho$.

For a DATE/DAC architecture-track submission, I recommend **Accept**. The characterization (phantom load + $\Theta(K^{3/2})$ Corollary), the predictor (NL\% with three consistent correlation readings up to $\rho=0.776$ / $\tau=0.652$), and the placement pipeline (greedy + warm-start RL + measured 20.8\%-activation post-hoc fallback) now clear the bar on theoretical rigor, statistical reporting, and algorithmic hygiene with room to spare.
