# Review -- Reviewer 4 (Theory/Analysis Expert), Iteration 11

## Summary

Iteration 11 addresses the two presentation-level residuals I flagged in iter 10: (i) a disclosure sentence on Algorithm~1's non-approximation-guaranteed status, and (ii) a separate `Corollary` environment that lifts the $\Theta(K^{3/2})$ scaling out of a free-standing equation and into a labeled result with an explicit substitution. Both fixes are minimal and correctly done. Iter 11 also adds Kendall $\tau$ alongside Spearman $\rho$, a deadlock-freedom paragraph, a latency-sensitivity analytical bound, and several data-consistency corrections. No new theoretical claims are introduced; the paper's analytical core is the same as iter 10.

## Changes from Iteration 10

**[C1] Algorithm 1 approximation-guarantee disclosure added (resolves my iter-10 W2/Q2).** Section on the greedy baseline now ends with: "We do \textit{not} claim any constant-factor approximation guarantee for Algorithm~\ref{alg:greedy\_express} relative to the optimal topology; its role in the paper is as an empirically strong and reproducible starting point, which the warm-start RL stage ... refines further and the post-hoc fallback ... backs with a measured safety guarantee." This is exactly the declarative non-claim I asked for. It does not overstate (no submodularity argument it cannot back), does not understate (positions greedy as practically strong, not abandoned), and correctly offloads the rigor to the downstream RL+fallback safety property. This is the minimum acceptable theoretical hygiene and it is now in place.

**[C2] Corollary environment for $\Theta(K^{3/2})$ (resolves my iter-10 W1/Q1).** Theorem~1 now states the closed-form $\alpha_{\max} = R \cdot \lceil C/2 \rceil \cdot \lfloor C/2 \rfloor$ (general $R \times C$). A separate `Corollary~\ref{cor:theta}` then states $\alpha_{\max} = \sqrt{K} \cdot \lfloor K/4 \rfloor = \Theta(K^{3/2})$ for square grids. The substitution is correct: for $R = C = \sqrt{K}$, $\lceil C/2 \rceil \cdot \lfloor C/2 \rfloor = \lfloor C^2/4 \rfloor = \lfloor K/4 \rfloor$, so the corollary is a one-line algebraic consequence of the theorem. I spot-checked at $K \in \{4, 16, 64, 256\}$; the identity holds exactly. Table~\ref{tab:scaling} caption/example now reference `Corollary~\ref{cor:theta}` rather than a floating equation.

**[C3] Kendall $\tau$ reported alongside Spearman $\rho$.** 40-point pool: $\tau=0.593$ ($p=9.6 \times 10^{-7}$). 16 best-budget cells: $\tau=0.615$ (greedy), $\tau=0.634$ (RL-WS+fallback). The text justifies reporting both because the four training workloads cluster into four NL\% tiers, which creates a tie-breaking regime in $\rho$; $\tau$ confirms the monotone trend is not an artifact of rank-tie handling. This is good statistical hygiene and it preempts a plausible reviewer pushback. Both correlations agree on the ordering and are overwhelmingly significant.

**[C4] Deadlock-freedom paragraph added.** Listed as a limitation in iter 10; now an explicit paragraph. Still not a formal proof -- and I do not require one for an architecture-track paper -- but the paper now names the concern rather than silently leaving it.

**[C5] Latency-sensitivity analytical bound, data-consistency cleanup, generalization-subset fix, multi-seed CI disclosed as future work, PARL-cold-PPO reframing.** None of these change my theoretical assessment. The $L_{\text{adj}}=126.0$ / $\tau=0.634$ corrections are internal consistency cleanup; they do not affect any headline number.

## Strengths

**[S1] Both of my iter-10 explicit asks are now closed with minimal, correct changes.** The approximation-guarantee disclosure is phrased as a non-claim, not a false claim. The Corollary environment is a legitimate rigor upgrade: the scaling result now has a label, a name, and lives inside a numbered environment whose proof is a one-line algebra on the Theorem body. This is exactly the "presentation-level fix" I described in iter 10.

**[S2] Kendall $\tau$ as a ties-robust companion to $\rho$ is a thoughtful addition.** With only four NL\% tiers in the training workloads, the Spearman $\rho$ I relied on in iter 10 was vulnerable to a ties objection; reporting $\tau$ alongside closes that door. $\tau=0.593$ at $n=40$ with $p \approx 10^{-7}$ is itself an overwhelmingly significant result.

**[S3] The non-claim framing on Algorithm 1 is actually the right theoretical posture.** I want to flag this explicitly: claiming "we use greedy because we know it has no known constant-factor approximation, so we wrap it in a downstream safety argument" is a more defensible stance than claiming a submodularity result the authors cannot prove. The paper correctly does the former.

**[S4] Theorem 1 + Corollary~\ref{cor:theta} now forms a clean theoretical anchor.** The Theorem gives the general formula; the Corollary gives the headline scaling. This is the standard structural idiom for a closed-form result with a named consequence, and its absence was the only remaining rigor issue in iter 10.

## Weaknesses

**[W1] Corollary~\ref{cor:theta} is stated without an explicit one-line proof note (VERY MINOR).** The corollary follows by substituting $R=C=\sqrt{K}$ into $R \cdot \lceil C/2 \rceil \cdot \lfloor C/2 \rfloor$, and using $\lceil C/2 \rceil \cdot \lfloor C/2 \rfloor = \lfloor C^2/4 \rfloor = \lfloor K/4 \rfloor$. The algebra is trivial, but a strict theoretician would prefer a "Proof. Substitute $R=C=\sqrt{K}$; the identity $\lceil C/2 \rceil \lfloor C/2 \rfloor = \lfloor K/4 \rfloor$ gives the claim." inline after the corollary. Not blocking.

**[W2] Spearman dilution interpretation sentence I suggested in iter-10 W5 is not added.** This is cosmetic; the new $\tau$ reporting actually makes this concern less important, because $\tau=0.593$ on 40 points is its own rigorous answer to "why did the iter-9 slice $r=0.94$ go to $\rho=0.744$".

**[W3] Table III XY/YX asymmetry (iter-10 W6/Q5) is still not explained in the text.** Minor, and the caption already says the values are simulator-measured directional loads not comparable to Table II. I would still appreciate a one-sentence note on the asymmetry on a square grid under uniform traffic.

**[W4] No new theoretical content beyond presentation fixes.** This is not really a weakness -- it is by design for iter 11 -- but I want to note that iter 11 moves the rigor bar by polishing existing claims rather than adding new ones. The theoretical core is Theorem 1 + Corollary + NL\% formula, unchanged since iter 10.

## Questions

**[Q1]** Would you add a one-sentence proof note under Corollary~\ref{cor:theta} -- literally "Proof. Substitute $R=C=\sqrt{K}$; $\lceil C/2 \rceil \lfloor C/2 \rfloor = \lfloor K/4 \rfloor$." -- to make the corollary fully self-contained? This is the only remaining purely-theoretical nit.

**[Q2]** (Carrying over from iter 10.) On a square $4 \times 4$ grid under uniform traffic, why does Table III show XY at Max $\alpha = 111$ and YX at Max $\alpha = 223$? A one-line explanation in the caption would preempt a pedantic reviewer challenge.

**[Q3]** Is the Kendall $\tau$ computed with the tie-corrected $\tau_b$ estimator or the raw $\tau_a$? At $n=40$ with visible NL\% tier clustering, this matters for the reported $p$-value. If $\tau_b$, the existing number is correct; if $\tau_a$, the $p$-value is conservative.

## Rating

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Novelty | 3.5/5 | Unchanged from iter 10. NL\% formalization, three-axis novelty framing, measured fallback -- the novelty picture is stable. |
| Technical Quality | 4.5/5 | Up from 4.0. Corollary~\ref{cor:theta} closes the scaling-claim gap. Algorithm 1 now has an explicit non-claim on approximation. Kendall $\tau$ alongside Spearman $\rho$ is good statistical hygiene. |
| Significance | 3.5/5 | Unchanged. Findings are actionable, +2.6\,\%p over a strong greedy baseline is modest but defensible. |
| Presentation | 4.5/5 | Up from 4.0. The Theorem/Corollary split is now standard-idiomatic. The approximation-guarantee disclosure is phrased correctly. Data-consistency cleanup (L\_adj, $\tau$ values, generalization subset) is all in the right direction. |
| Overall | 4.0/5 | Up from 3.7. Both iter-10 residuals are cleanly resolved. Only cosmetic nits remain. |
| Confidence | 5/5 | I re-verified: (a) the Corollary substitution at $K \in \{4, 16, 64, 256\}$; (b) the approximation-guarantee disclosure phrasing does not overclaim; (c) Kendall $\tau$ values are internally consistent with the reported Spearman $\rho$ ordering. |

## Decision

**Accept.**

Iter 11 delivers exactly the two fixes I conditioned my iter-10 vote on: Algorithm~1 now carries a correctly-phrased non-claim on approximation guarantees, and the $\Theta(K^{3/2})$ scaling is now a named Corollary of Theorem~1 with an exact substitution (verified at $K \in \{4, 16, 64, 256\}$). The approximation-guarantee disclosure is phrased as a non-claim rather than a false claim, which is the right theoretical posture. The Corollary statement is rigorous: the identity $\lceil C/2 \rceil \lfloor C/2 \rfloor = \lfloor C^2/4 \rfloor = \lfloor K/4 \rfloor$ under $R=C=\sqrt{K}$ makes the scaling result a one-line algebraic consequence of the theorem body. Adding Kendall $\tau$ alongside Spearman $\rho$ preempts the tie-breaking objection on a 4-tier NL\% sample.

The remaining nits (one-line proof note under the corollary, XY/YX asymmetry explanation, whether $\tau$ is $\tau_a$ or $\tau_b$) are cosmetic and easily addressed at camera-ready. They do not affect correctness.

For a DATE/DAC architecture-track submission, I now recommend **Accept**. The characterization (phantom load + $\Theta(K^{3/2})$ Corollary), the predictor (NL\% with $\rho=0.744$ / $\tau=0.593$ on 40 points), and the placement pipeline (greedy + warm-start RL + measured post-hoc fallback) now clear the bar on theoretical rigor, statistical reporting, and algorithmic hygiene.
