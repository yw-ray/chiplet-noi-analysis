# Review -- Reviewer 4 (Theory/Analysis Expert), Iteration 10

## Summary

The paper reframes express-link placement as a three-step Predict-Place-Refine pipeline anchored on a single static workload statistic, the non-locality fraction NL%. The theoretical core is unchanged from iteration 9: Theorem 1 states the flow-count formula under XY routing, from which center-link amplification Theta(K^{3/2}) follows. New relative to iteration 9: (i) a formal NL% formula with an explicit topology-dependence caveat; (ii) a measured post-hoc BookSim fallback guaranteeing L_RL-WS <= L_greedy^measured; (iii) three-axis novelty framing (Predictor / Warm-Start / Safety) with a direct PARL comparison; (iv) restated Spearman rho=0.744 pooled over 40 points (and rho=0.74/0.76 on 16 best-budget cells) with the ordering preserved under RL refinement.

## Changes from Iteration 9

**[C1] NL% now has a formal definition (resolves my W1/Q1).** Equation in Section "Non-Locality Analysis" defines NL%(T,G) as the symmetric volume-weighted share of demand between pairs at chiplet-graph hop >= 2. It is computed on the pre-routing demand matrix. The paper also explicitly notes NL% is "a static workload property relative to a chosen chiplet layout", which is the topology-dependence caveat I asked for. This is exactly the minimal formalization I requested.

**[C2] Measured fallback framing is now honest.** The text states the guarantee is "measured rather than surrogate-predicted": both greedy and RL candidates are simulated end-to-end and the minimum latency is kept. The inequality L_RL-WS = min(L_greedy^meas, L_RL^meas) <= L_greedy^meas is written out. I appreciate that the paper does not dress this up as a theorem -- it is a trivial consequence of selecting the min of two measured values, and the paper correctly presents it as an engineering safety property, not a theoretical contribution.

**[C3] Three-axis novelty framing and PARL comparison.** Table I (related work) places our method against Kite, Florets, and PARL along three axes: Predictor / Warm-start / Safety. PARL is cold-PPO with no predictor and no safety guarantee; our method differs on all three axes simultaneously. This is a cleaner positioning than iteration 9.

**[C4] Spearman reporting is more comprehensive but a touch quieter.** Pooled rho=0.744 (p=3.8e-8) over all 40 pairs, rho=0.744 under RL-WS+fallback, and rho=0.74/0.76 on 16 best-budget cells. The earlier iteration-9 "r=0.94" slice claim is gone. The pooled rho=0.744 is a strong and well-powered result on a 40-point sample, and I consider this an improvement in honesty even though the headline number is slightly lower.

**[C5] Theta(K^{3/2}) is now inside a Theorem environment.** Theorem 1 states the directed-flow count F_H(c), F_V(r) on an R x C grid under XY routing with uniform all-to-all. The Theta(K^{3/2}) bound follows one line later from alpha_max = R * ceil(C/2) * floor(C/2).

**[C6] Ablation counting fix (35/40 wins, was 32/40).** Table~\ref{tab:ablation} now reports 35/40 wins for Warm RL and Warm RL+fallback, consistent with the "5 remaining losses" sentence in the main-result subsection.

**[C7] Still not addressed (open from my iter-9 asks):** no approximation guarantee statement for Algorithm 1 (my W2); no formal deadlock-freedom argument (now listed as a limitation, which is the minimum acceptable).

## Strengths

**[S1] NL% formalization is crisp and theoretically clean.** The formula is symmetric (T[i,j]+T[j,i]), normalized by total demand, evaluated on the chiplet-graph hop metric, and computed before routing. This cleanly separates NL% from routing policy, which is the right choice for a predictor that is supposed to screen workloads *before* simulation. The topology-dependence caveat is explicit.

**[S2] Measured fallback is framed honestly.** The paper does not claim a theorem where there is none. "Measured rather than surrogate-predicted" is the correct phrase -- it addresses exactly the failure mode I worry about (surrogate error silently dominating selection). As a practitioner-facing safety argument this is sound.

**[S3] Theta(K^{3/2}) scaling remains the analytical anchor.** Theorem 1's flow-count formula is correct; the Theta(K^{3/2}) exponent follows directly by algebra on the square-grid product. I verified: for C=R=sqrt(K), R * ceil(C/2) * floor(C/2) = sqrt(K) * Theta(K) = Theta(K^{3/2}). Table II still validates this up to K=64.

**[S4] Three-axis novelty framing clarifies contribution boundaries.** Placing the paper against PARL along orthogonal axes (predictor / warm-start / safety) is the right framing. A reviewer can now quickly see "what is new" without cross-referencing three prior papers.

**[S5] Pooled rho=0.744 on 40 points is a well-powered result.** At n=40 this corresponds to a p-value of 3.8e-8, which is overwhelmingly significant. The fact that the rank correlation is *stable* under RL refinement (rho=0.744 both before and after) is itself a nontrivial finding: RL does not reshuffle workloads in the benefit ranking, it shifts the whole curve up.

## Weaknesses

**[W1] Theorem 1 states the flow-count formula but not the Theta(K^{3/2}) scaling (MINOR).** The theorem body only provides F_H(c) and F_V(r). The Theta(K^{3/2}) conclusion is stated in equation (7) *outside* the theorem environment, with no explicit proof step. This is acceptable -- the algebra is one line -- but a theoretician would prefer either (a) folding the alpha_max = Theta(K^{3/2}) statement *into* the theorem as a corollary, or (b) adding a one-sentence proof note ("Substituting c=ceil(C/2)-1 into F_H and dividing by the 2R direct flows yields alpha_max = R * ceil(C/2) * floor(C/2) = Theta(K^{3/2}) for square grids.") As-is, a strict reading leaves the headline scaling claim formally unproven inside the theorem environment.

**[W2] Algorithm 1 approximation guarantee still missing (MODERATE, persists from iter 8/9).** The paper describes the greedy placement procedurally and acknowledges it is a "local optimum", but does not state that the underlying discrete optimization (minimizing rho_max under a budget and per-pair cap with express distance <= D) is known-hard, and does not cite a submodularity argument or a (1-1/e) style guarantee. For a paper whose *Place* step is 25.6% of the headline result, one sentence of the form "This problem is submodular under [assumption] / is NP-hard by reduction from X / admits no known constant-factor approximation, so we rely on greedy as a practical heuristic" would elevate the theoretical posture substantially. This was an iter-8 and iter-9 ask and is still unaddressed.

**[W3] Measured fallback is mathematically trivial (MINOR, but acceptable if framed as such).** The inequality L_RL-WS <= L_greedy^meas is literally just "min(a,b) <= a". The paper frames this as a safety mechanism rather than a theorem, which is the right call. However, a skeptical theory reviewer may still note that the 28.2% headline number partly reflects the *evaluator* (picking best of two) rather than the *refiner* (RL-WS). Table~\ref{tab:ablation} does disambiguate this (Warm RL alone -3.6%, Warm RL + fallback -3.7%), which I appreciate; the 0.1 percentage-point gap is honest. I would strengthen the narrative by saying explicitly that on the 40-config training set, fallback contributes only 0.1%p -- the gain is almost entirely from warm-start, not from the selection operator.

**[W4] NL% predictor is evaluated only against XY-style shortest-path routing (MINOR, acknowledged as a limitation).** The paper notes this in the Discussion. For a predictor that is supposed to be a simulation-free screen, a companion experiment with adaptive or Valiant routing would strengthen the generality claim -- NL% is defined on the chiplet-graph hop metric, which is routing-agnostic, but the *correlation* with saving was measured only under one routing family.

**[W5] Spearman rho dilution is worth a sentence of interpretation (MINOR).** Pooled rho=0.744 vs the iter-9 slice r=0.94 is a meaningful drop. The 40-point value is strictly more informative and less cherry-picked, but a reader cross-checking against iter 9 may wonder why the headline correlation went from 0.94 to 0.74. A single sentence ("Pooling dilutes the slice-level correlation because low-budget (2x) crossover cases reduce monotonicity; nonetheless rho=0.74 over 40 points is overwhelmingly significant.") would preempt that confusion.

**[W6] Table III routing-independence values still use "Max alpha" but differ from Table II (MINOR, known issue).** The paper now explicitly says Table III reports "simulator-measured directional link loads" not directly comparable to Table II's undirected closed-form values. Good. The XY vs YX asymmetry (111 vs 223 at 4x4) is still not explained -- in a square grid with uniform traffic, these should be identical by symmetry. I suspect a per-chiplet mesh effect or measurement convention, but the text does not say.

## Questions

**[Q1]** Can you fold the Theta(K^{3/2}) bound directly into Theorem 1 as part (c) or a corollary, with the one-line substitution proof? Keeping the scaling claim outside the theorem environment undermines the rigor gained by introducing the environment in the first place.

**[Q2]** (Re-asking from iter 9.) Can you add a single sentence classifying Algorithm 1's underlying problem -- hardness, submodularity, or the absence of known approximation ratio? Even a declarative statement ("We treat this as a heuristic; we know of no constant-factor approximation for minimizing rho_max under the per-pair cap and max-distance constraints") is fine.

**[Q3]** Why is the warm-start RL alone contributing essentially all the ablation gain (-3.6% vs -3.7% with fallback), yet the narrative still emphasizes fallback as central? Would you agree that the main scientific claim is "warm-start RL refinement works" and that fallback is a *safety wrapper* that becomes meaningful only on out-of-distribution or low-budget cells?

**[Q4]** Is NL% equivalent to "expected number of multi-hop destinations weighted by demand volume, normalized"? The formula as written is a volume fraction, not an expectation -- but architects may read it either way. A one-line operational description ("NL% is the demand-weighted probability that a random byte enters a non-adjacent routing path") might help.

**[Q5]** In Table III, why do XY and YX give asymmetric Max alpha on a square 4x4 grid under uniform traffic? A symmetry argument would predict identical values.

## Rating

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Novelty | 3.5/5 | NL% as a formally-defined simulation-free predictor is a genuine contribution. The three-axis differentiation from PARL is clean. Warm-start + measured fallback is sound engineering rather than deep theory. |
| Technical Quality | 4.0/5 | NL% formula is rigorous, Theta(K^{3/2}) scaling is correct, Theorem 1 is well-stated (modulo W1), statistical reporting on 40 points is honest. Algorithm 1 approximation gap and missing deadlock argument persist. |
| Significance | 3.5/5 | Phantom load and NL%-predictability are real, actionable findings. RL-WS delivers +2.6%p over a strong deterministic baseline, which is modest but defensible. |
| Presentation | 4.0/5 | NL% formula, Theorem environment, measured-fallback inequality, and PARL comparison table all read cleanly. Iter-10 framing (Predict-Place-Refine) is a genuine structural improvement. |
| Overall | 3.7/5 | Iter-10 addresses my primary iter-9 ask (NL% formalization) and adds measured-fallback framing and the three-axis positioning. The Algorithm 1 approximation gap remains, but for a characterization+placement paper this is a moderate rather than blocking issue. |
| Confidence | 5/5 | I re-verified the Theorem 1 algebra to Theta(K^{3/2}), checked the NL% formula, and confirmed ablation arithmetic (35/40 wins, Warm RL -3.6% -> -3.7% with fallback = 0.1%p fallback contribution). |

## Decision

**Weak Accept.**

Iter 10 crosses the line from Borderline Accept to Weak Accept for me. The iter-9 blocking ask -- a formal NL% definition with topology-dependence -- is cleanly resolved, and the new iter-10 contributions (three-axis novelty framing, measured fallback inequality, Theorem environment for Theta(K^{3/2}), PARL positioning) each add non-trivial rigor. Pooled Spearman rho=0.744 over 40 points, with the ordering preserved under RL refinement, is a credible predictor-validation result.

Two residual concerns keep me from an unqualified Accept. First, Algorithm 1 still has no approximation statement, which is a carryover from iter 8 and iter 9 -- one sentence would resolve this. Second, the Theta(K^{3/2}) scaling claim lives just outside the Theorem environment; folding it in as a corollary with a one-line substitution proof would complete the theoretical polish. Both are presentation-level fixes rather than new science.

For a DATE/DAC architecture-track submission whose claimed contributions are a characterization result (phantom load + Theta(K^{3/2})), a workload predictor (NL%), and an RL refinement with a measured safety wrapper, the paper now clears the acceptance bar. I recommend **Weak Accept** and would raise to **Accept** if the authors fold Theta(K^{3/2}) into Theorem 1 as a corollary and add one sentence on Algorithm 1's heuristic status.
