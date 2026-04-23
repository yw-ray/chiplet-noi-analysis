# Review -- Reviewer 2 (Systems Pragmatist), Iteration 11

## Summary

This iteration is a targeted shepherding pass on top of the iteration-10 accept. The three-step \textsc{Predict}/\textsc{Place}/\textsc{Refine} workflow is unchanged; the numerical story is unchanged (40 configs; greedy $+25.6\%$ mean; RL-WS+fallback $+28.2\%$ mean, $+56.4\%$ best; pooled $\rho=0.744$, $p=3.8\times 10^{-8}$; unseen 6/6 for RL-WS, $-23.6\%$ GNN collapse on all-to-all). What changed is mostly rigor and disclosure: an explicit deadlock-freedom construction, an analytical $\lambda{=}2.0$ latency-sensitivity bound on the headline MoE $K{=}32,N{=}8,b{=}4\times$ cell, an approximation-guarantee disclaimer on Algorithm~1, a Corollary environment around $\Theta(K^{3/2})$, Kendall $\tau$ reported alongside Spearman $\rho$ (40-pt $\tau=0.593$; 16-cell RL-WS+fb $\tau=0.634$), a fix to the previously misstated unseen RL-WS subset, reframing of cold-RL as a PARL-cold-PPO internal proxy in Related Work, and an honest multi-seed CI limitation in Section~7. I re-ran \texttt{compute\_stats.py} and every number in Table~4, Table~5 (main result), Table~6 (ablation: warm $-3.6\%$ mean, worst $+1.7\%$; warm$+$fb worst $+0.0\%$, wins $35/40$), and Table~7 (generalization: $-0.6\%$ GNN, $+7.1\%$ RL-WS) reproduces to the reported precision.

## Changes from Iteration 10

Relative to my iteration-10 shepherding asks (W1 deadlock, W3 RL wall-clock, W6 absolute latency), this iteration:

1. **Addresses W1 cleanly.** §VII's new ``Deadlock freedom'' paragraph specifies per-dimension VC classes on the combined adjacent$+$express graph, notes that express links consume the VC subset of the dimension whose hop count they reduce, and argues the ordered channel-dependency graph remains acyclic. A Duato-style formal proof is honestly deferred, but the construction is concrete and matches BookSim's \texttt{anynet} capability. This is exactly the right depth for a DATE shepherding fix: not a handwave, but not an orthogonal theory contribution either.
2. **Addresses W6 partially, transparently.** §VII now quotes the concrete absolute latencies for the headline cell: $L_{\text{adj}}=126.0$, $L_{\text{RL-WS}}=54.9$ cycles at MoE $K{=}32,N{=}8,b{=}4\times$, and uses them to bound the $\lambda{=}2.0$ wire-delay-sensitivity saving at $\ge 50.1\%$. The reader can now calibrate saving percentages against an absolute anchor for at least one representative cell. A full absolute-latency table is still deferred, but the headline number is now anchored.
3. **Does not address W3 structurally.** No RL wall-clock table was added. This remains a gap -- but a smaller one than I assumed, because the \texttt{train\_time} field in \texttt{ml\_comparison\_warmstart.json} does capture it per-config. A reproducer can recover the numbers (spot-check: $K{=}16$ slices mean $\sim\!16$--$17$\,s, $K{=}32$ slices mean $\sim\!450$--$490$\,s, total $\sim\!132$\,min across 40 configs on the evaluation hardware). That the data exist but are not surfaced in the paper is a presentation choice, not a soundness problem. Camera-ready should add a one-row table.
4. **Adds disclosures I did not ask for but appreciate.** (a) Algorithm~1 approximation-guarantee disclaimer: the paper now explicitly says greedy is empirical-strong-starting-point, not a constant-factor approximation -- this removes an attack surface a hostile reviewer would exploit. (b) Kendall $\tau$ alongside Spearman $\rho$: the 40-pt $\tau=0.593$ confirms the rank correlation is not a tie-pattern artifact given our four-tier NL\% design. (c) Cold RL reframed as PARL-cold-PPO proxy: this neutralizes the ``why not reproduce PARL?'' concern by turning the ablation into a fair-proxy argument (cold worst $+11.3\%$ vs warm worst $+1.7\%$). (d) Multi-seed CI limitation stated honestly in §VII(ii): single-seed per configuration, $<1\%$ observed std, $\ge 3$-seed CIs flagged as future work.
5. **Fixes §VI.D data-consistency bug.** The iteration-10 text described the RL-WS unseen subset as ``$K{=}16,N{=}8$ at $b\in\{2\times,4\times\}$,'' which did not match the JSON. Iteration-11 states ``$(K{=}16,N{=}4,b{=}4\times)$ and $(K{=}16,N{=}8,b{=}4\times)$.'' I verified against \texttt{ml\_generalization.json}: the 2-cell RL-WS subset does not contain any $b{=}2\times$ cell. The corrected text also clarifies that the subset ``deliberately excludes the $b{=}2\times$ crossover regime,'' which is a reasonable scoping justification. This resolves my iteration-10 Q6.
6. **Corollary environment around $\Theta(K^{3/2})$.** Minor but welcome -- makes the phantom-load scaling a named citable result instead of inline prose. Good presentation hygiene for DATE.

## Strengths

[S1] **Shepherding asks were taken seriously, not cosmetically.** Three of my iteration-10 asks (deadlock paragraph, absolute latency anchoring, data-consistency fix) landed substantively. This matters because reviewers inevitably check whether iteration-over-iteration claims hold up; this one does.

[S2] **Kendall $\tau$ is the right tie-robustness evidence.** With four NL\% tiers (42/77/89/91) the 40-point dataset has heavy tie structure. Reporting both $\rho=0.744$ and $\tau=0.593$ for the 40-point pool, and $\rho=0.764$ / $\tau=0.634$ for the 16-cell subset, directly neutralizes the ``ranks are rigged by workload design'' counter-argument. This is a small but methodologically mature disclosure.

[S3] **Approximation-guarantee disclosure disarms a review trap.** Saying outright ``we do not claim any constant-factor approximation guarantee for Algorithm~\ref{alg:greedy_express}'' protects the paper against a theory-leaning committee member who would otherwise ask for an LP-relaxation argument. It is also honest: greedy is empirically strong here, not provably near-optimal.

[S4] **Deadlock-freedom paragraph is appropriate-depth for DATE.** It names the mechanism (per-dimension VC subset per express-link direction), states the acyclicity argument, and defers the formal proof with a clear scope demarcation. For DATE, this is the right trade: not a handwave, not a new contribution.

[S5] **$\lambda$-sensitivity bound is analytically conservative.** The $(\lambda-1)\cdot 2D$ upper bound on added express latency is worst-case per-packet, so the projected $\ge 50.1\%$ saving at $\lambda{=}2.0$ is a lower bound. A reviewer cannot accuse the paper of cherry-picking the $\lambda$-sensitivity argument -- the math is structurally pessimistic.

[S6] **Cold-RL-as-PARL-proxy framing closes the PARL-reproduction gap.** Iteration-10 relied on the Table~1 qualitative three-axis differentiation; iteration-11 adds a quantitative anchor (cold worst $+11.3\%$ vs warm worst $+1.7\%$) that is methodologically defensible as an internal proxy for cold-PPO-style synthesis. This is the right way to handle PARL without an end-to-end reimplementation.

## Weaknesses

[W1] **RL wall-clock table still missing, though data exist.** From the JSON, $K{=}32$ configs take $\sim\!7$--$16$ minutes each and $K{=}16$ configs take $\sim\!10$--$42$ seconds each; total across 40 configs is about 2.2 wall-clock hours. These numbers are deployability-positive and should appear as a small table rather than an in-text aside. This is my only carry-over from iteration 10 that was not addressed. Not blocking; camera-ready fix.

[W2] **Absolute-latency anchoring is still only one cell.** The MoE $K{=}32,N{=}8,b{=}4\times$ anchor is useful, but a reader looking at Tree AR ($+13.3\%$ mean) or Hybrid TP+PP ($+26.9\%$ mean) still cannot calibrate saving percentages to absolute cycles. A 4-row mini-table (one representative cell per workload) would close this completely. Not blocking; camera-ready fix.

[W3] **Multi-seed CI limitation is now disclosed but not remediated.** §VII(ii) honestly admits single-seed per configuration with $<1\%$ observed std. That is enough for DATE acceptance, but a hostile ISCA-style reviewer would still ask: given that RL-WS wins 35/40 and the 5 losses are all within 1.73\%, how many of those 5 are within the single-seed noise band? Without multi-seed runs the answer is ``probably most, but we did not verify.'' The fallback makes this a moot point for deployment, which is the correct pragmatist response, but the sentence-level framing in §VI.C could acknowledge this more explicitly.

[W4] **§VI.D RL-WS subset is now correct but still small.** The corrected subset is $(K{=}16,N{=}4,b{=}4\times)$ and $(K{=}16,N{=}8,b{=}4\times)$. Both cells are at $b{=}4\times$, both at $K{=}16$. This is honest about scope and I accept the exclusion of $b{=}2\times$ (fallback territory), but the $6/6$ headline is over 6 cells all at the same budget level and the same chiplet count. I would like the camera-ready to add at least $(K{=}32, N{=}8, b{=}4\times)$ for each unseen workload if compute allows; this would take the subset to 9 cells and -- more importantly -- to two distinct $K$ values.

[W5] **Physical overhead and CoWoS routability are unchanged from iteration 10.** Table~8 still gives back-of-envelope per-link wire cost without interposer routability analysis (my iteration-10 W2). Still not disqualifying, still the obvious camera-ready improvement target for CoWoS-literate readers.

[W6] **Synthetic workloads, still.** Unchanged from iteration 10 (my W5 then). DATE-acceptable; ISCA/MICRO-insufficient. Iteration-11 does nothing new here, and correctly does not pretend to.

## Questions

Q1. For the deadlock-freedom construction in §VII: is each express link assigned to a \textit{single} VC subset (the dimension whose hop count it reduces), or does it alternate based on routing direction? The paragraph reads as single-subset but BookSim's \texttt{anynet} in principle supports both; please clarify for the camera-ready.

Q2. The $\lambda{=}2.0$ sensitivity bound uses $(\lambda{-}1)\cdot 2D = 8$ cycles per express hop. Is this upper bound per express-link usage, or per packet traversing any number of express hops? For a packet that uses two express hops the bound would double. The math in §VII reads as per-hop; please confirm.

Q3. The RL-WS \texttt{train\_time} data in \texttt{ml\_comparison\_warmstart.json} range from $\sim\!10$\,s ($K{=}16$) to $\sim\!16$\,min ($K{=}32$). Do these include the 288-sample BookSim surrogate amortization, or is the surrogate trained once per $(K,N)$ slice and reused? Answer matters for the deployability claim.

Q4. On the 5 warm-RL losses that fallback zeros out (mean $+0.9\%$, worst $+1.73\%$): given the $<1\%$ single-seed std mentioned in §VII(ii), are these losses within single-seed noise? A 2-line footnote to §VI.C would close this.

Q5. For the corrected unseen subset at two $N$ values and only $K{=}16$: do you have any $K{=}32$ unseen-workload data lying around that could be promoted to a ``full'' unseen table in the camera-ready, or is $K{=}32$ unseen RL-WS out of compute budget?

## Rating

| Criterion | Score | Comment |
|-----------|-------|---------|
| Novelty | 3.5 | Unchanged from iteration 10. NL\% predictor + warm-start+fallback + PARL differentiation is a coherent contribution triangle. |
| Technical Quality | 3.5 | Up from 3.5 (held). Kendall $\tau$ disclosure, approximation-guarantee disclaimer, deadlock construction, and $\lambda$-sensitivity bound are all incremental-but-real rigor gains. I re-verified the full numerical chain via \texttt{compute\_stats.py}. |
| Significance | 3.5 | Unchanged. Three-step workflow + measured safety is the deployability story, not the silicon-proximity story. DATE/DAC fit. |
| Presentation | 4.0 | Unchanged. Corollary environment and the §VII ordering (deadlock $\to$ sensitivity $\to$ limitations) are small but positive. |
| Overall | 3.5 | Held from iteration 10 at ``clean DATE/DAC accept.'' |
| Confidence | 4.5 | Up from 4.0. I ran \texttt{compute\_stats.py} and verified the 40-config Spearman, Kendall, ablation, and generalization numbers end-to-end; I also spot-verified the unseen JSON subset against the §VI.D text. Familiarity with the paper is now high and I am confident nothing material is hiding. |

## Decision

**Accept for DATE/DAC. Borderline for ISCA/MICRO (Weak Reject), unchanged.**

Iteration 11 is the shepherding-pass iteration I asked for. The three substantive gaps I flagged in iteration 10 are now addressed as follows: W1 (deadlock) is \textit{closed} via the per-dimension VC construction in §VII; W6 (absolute latency) is \textit{partially closed} via the MoE $K{=}32,N{=}8,b{=}4\times$ anchor cell in §VII; W3 (RL wall-clock table) is \textit{not closed} in the paper but the underlying data exist and are recoverable. Of these three, only W3 is a genuine carry-over, and it is a camera-ready fix rather than a soundness gap.

The data-consistency fix in §VI.D is the single most important change in this iteration from a reviewing-integrity perspective: the iteration-10 text misdescribed the unseen RL-WS subset as spanning $b\in\{2\times,4\times\}$ when the data actually has both cells at $b{=}4\times$. Catching and correcting this without waiting for the committee to notice is credibility-positive; it is also the kind of error that a low-effort iteration would have ignored. The new phrasing -- ``deliberately excludes the $b{=}2\times$ crossover regime, which is already covered by the fallback mechanism in the main result'' -- is a legitimate scoping justification and I accept it.

The three-axis disclosure trio (approximation-guarantee disclaimer on Algorithm~1, Kendall $\tau$ alongside Spearman $\rho$, multi-seed CI limitation) is the right defensive posture for a DATE/DAC submission: it concedes the attack surfaces that a hostile committee member would find and turns them into stated scope rather than discovered weaknesses. Combined with the cold-RL-as-PARL-cold-PPO-proxy reframing, the paper's defensive posture is noticeably stronger than iteration 10's.

**Does the paper still clear DATE?** Yes. It clears DATE by a slightly larger margin than iteration 10 because (i) the two structurally hard asks -- deadlock freedom and absolute-latency anchoring -- were taken on substantively rather than deflected, and (ii) the methodological disclosures (Kendall $\tau$, approximation-guarantee disclaimer, multi-seed CI limitation) remove review-trap surfaces without weakening any claim. The headline numbers reproduce from the committed stats script, the unseen subset description now matches the JSON, and the deadlock/sensitivity paragraphs are concrete rather than handwaved.

**Does my confidence go up or hold?** Up, from 4.0 to 4.5. Iteration-10's 4.0 reflected familiarity with the literature and methodology; iteration-11's 4.5 reflects that \textit{and} a direct numerical re-verification via \texttt{compute\_stats.py} plus a JSON spot-check of the corrected §VI.D subset. There are no remaining claims in the paper that I cannot trace to a JSON file or a closed-form derivation.

**My vote: Accept at DATE/DAC.** No further shepherding required to clear the bar. For camera-ready, three nice-to-haves (not blockers): (a) a 1-row RL wall-clock table per $(K,N)$ slice surfaced from the existing \texttt{train\_time} JSON field; (b) a 4-row absolute-latency table (one representative cell per training workload) to extend the §VII anchor; (c) if compute permits, at least one $K{=}32$ unseen-workload cell added to §VI.D so the generalization study spans two $K$ values. None require new methods work.

**For ISCA/MICRO**: unchanged (Weak Reject). Iteration-11's improvements are disclosure and rigor, not new evidence. BookSim-only, synthetic-workload, single-seed per configuration, and no CoWoS routability analysis remain. The paper is now a very clean DATE paper; promoting it to ISCA/MICRO would require at least one traced workload and either multi-seed CIs or hardware/FPGA validation.
