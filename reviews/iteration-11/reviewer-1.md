# Review -- Reviewer 1 (Architecture Expert), Iteration 11

## Summary

Iteration 11 targets three of the specific gaps I flagged in iteration 10: the latency-model sensitivity question, surrogate training provenance, and several housekeeping items (Kendall $\tau$, Corollary framing, deadlock sketch, approximation-guarantee disclosure, multi-seed scoping, and consistency of the headline latency pair $L_\text{adj}{=}126.0$, $L_\text{RL-WS}{=}54.9$). The submission now presents the three-step Predict--Place--Refine story with cleaner analytical scaffolding: $\Theta(K^{3/2})$ is stated as Corollary~1 after Theorem~1; the NL\%-versus-saving claim is supported by both Spearman $\rho=0.744$ and Kendall $\tau=0.593$ over 40 points; the ablation honestly admits single-seed main results with $<1\%$ exploratory std; cold RL is explicitly reframed as a PARL-like cold-PPO proxy with worst $+11.3\%$ vs warm's $+1.7\%$ (fallback: $+0.0\%$); and the Discussion now contains a back-of-envelope bound that at $\lambda{=}2.0$ per-hop express latency, MoE K32N8 $b{=}4\times$ saving still projects $\ge 50.1\%$ using measured $L_\text{adj}{=}126.0$, $L_\text{RL-WS}{=}54.9$. The paper is noticeably tighter. But one of my three iter-10 asks (latency sensitivity as a table) has been answered only analytically, one (surrogate split) has not actually been stated in §V.C as requested, and the switch-topology gap is unchanged.

## Changes from Iteration 10

**Fixed:**
- **[W-detail iter 10: $\Theta(K^{3/2})$ scaling framing]** Now stated as Corollary~1 following Theorem~1, removing the floating-in-text presentation. Minor but correct.
- **[W-detail iter 10: approximation-guarantee claim]** §V.B now explicitly says "We do \textit{not} claim any constant-factor approximation guarantee for Algorithm~1." Good. This removes a latent reviewer complaint.
- **[W-detail iter 10: $\tau$ alongside $\rho$]** The paper now reports $\tau=0.593$ (40 pts) and $\tau=0.634$ (16-cell RL+fb). For a 40-point sample with four NL\% tiers, $\tau$ is the more honest statistic, and its agreement with $\rho$ (both in the 0.6--0.74 band) materially strengthens the predictor claim. This is the correct fix to my iter-10 W6.
- **[W-detail iter 10: multi-seed honesty]** Limitations (ii) now explicitly states single-seed main results, exploratory-run std $<1\%$, and $\ge 3$ seeds as future work. That is the right level of disclosure for a DATE paper and converts a likely reviewer strike into a scoped limitation.
- **[W-detail iter 10: cold RL framing]** Related Work now frames the cold RL variant as the PARL-like cold-PPO proxy. This is a legitimate rhetorical move given the per-configuration training cost of a faithful PARL re-implementation, and the $+11.3\%$ vs $+1.7\%$ worst-case contrast is a strong empirical argument for warm-starting.
- **[W-detail iter 10: deadlock freedom]** §VII now gives a two-VC ordered-channel sketch (express links stay in the dimension-consistent VC subset; no cycle in the channel-dependency graph). Not a formal Duato proof, but adequate for a conference bar.
- **[Data consistency cleanup]** The headline pair is now internally consistent: $L_\text{adj}{=}126.0$, $L_\text{RL-WS}{=}54.9$, saving $=56.4\%$, 16-cell RL+fb $\tau=0.634$. Prior iterations carried a $134.9/60.9$ pair that didn't reproduce the $56.4\%$ figure cleanly. The fix is small but the kind of thing PC members actually check.
- **[§VI.D data text fix]** The unseen-workload subset is now stated as $(K{=}16, N{=}4, b{=}4\times)$ and $(K{=}16, N{=}8, b{=}4\times)$, which matches the 2-cell-per-workload count in Table~VIII. Prior text had a cell mislabel.

**Partially addressed (and my iter-10 ask):**
- **[Q2 iter 10 = W1 iter 10: latency-model sensitivity]** §VII now contains an analytical bound: at $\lambda{=}2.0$, the extra delay per express hop is at most $2D=8$ cycles, giving RL-WS $\le 62.9$ cycles and projected saving $\ge 50.1\%$ for MoE K32N8 $b{=}4\times$. At $\lambda{=}1.5$, $\ge 53.3\%$. This is \textit{one} cell, not a table, and it is an upper bound on latency (i.e., lower bound on saving) rather than a measured re-simulation. For the headline MoE cell the bound is loose enough that the qualitative conclusion ("express saving survives a $2\times$ pessimistic wire model") is defensible. But the iter-10 concern was that the $2$--$4\,\%\text{p}$ RL-WS-over-greedy gap could be erased by a perturbation; the new bound addresses only the adj-vs-express gap on the \textit{best} cell, not the RL-WS-vs-greedy gap on the \textit{worst} cells (Tree AR $K{=}16$, Hybrid TP+PP $K{=}16$, where $\Delta$ is 1--2\,\%p and $L_\text{adj}$ is smaller so the absolute $(\lambda{-}1)\cdot 2D$ penalty is a bigger fraction). This is a partial answer, not a full one. In rebuttal I would accept it; the camera-ready should carry a proper per-cell table.

**Not addressed:**
- **[Q1 iter 10 = W5 iter 10: surrogate training split]** I asked for a one-sentence clarification in §V.C stating which 288 BookSim samples trained the surrogate and whether they overlap with the 40 evaluation configurations. §V.C still says only "trained on 288 BookSim samples" with no split description. The post-hoc fallback protects final numbers, but the \textit{magnitude} of the claimed warm-start uplift (the $-3.6\%$ mean-vs-greedy in Table~VII) is only meaningful if the surrogate was not fit on its evaluation set. This was a two-sentence ask and it did not land.
- **[W2 iter 9/10: switch-based topology comparison]** Unchanged across three iterations. No paragraph in Discussion scopes "mesh+express wins when \ldots vs a central switch." The paper frames express links as "topological rather than allocation-level" but never engages with the alternative topology. An architecture reviewer on the PC will continue to ask this question; the paper still has no answer.
- **[W4 iter 10: GNN vs RL-WS on matched cells]** The Table~VIII comparison is still asymmetric (GNN on 4 cells, RL-WS on 2 cells). The $6/6$ vs $8/12$ headline is still not a like-for-like comparison. This was never committed in the author response and remains a legitimate weakness.

## Strengths

**[S1] Honesty about single-seed and surrogate-guided RL.** The explicit "$<1\%$ exploratory std, single-seed main result, $\ge 3$ seeds future work" statement and the retention of cold RL results as a PARL-proxy worst-case are the right rhetorical choices for this paper and directly address two of my iter-10 concerns.

**[S2] Kendall $\tau$ corroborates the NL\% story.** The agreement of $\rho$ and $\tau$ across 40-point and 16-cell views ($\rho\in\{0.744, 0.764\}$, $\tau\in\{0.593, 0.634\}$) converts the predictor claim from "one correlation metric" to "two rank-correlation metrics with a consistent ordering." This is a cheap but real improvement to the central empirical claim.

**[S3] Measured fallback narrative is sharper than in iter 10.** The reframed Related Work table (Predictor/Warm-Start/Safety) plus the approximation-guarantee disclosure in §V.B plus the deadlock sketch in §VII collectively make the "greedy is the safe default, RL-WS is the safe refinement" story much harder to attack. Architecture PCs like papers that admit what they do \textit{not} prove.

**[S4] Headline numbers still reproduce.** Running \verb|python3 compute_stats.py| on the released JSON produces mean greedy $25.64\%$, mean RL-WS+fb $28.23\%$, best $56.43\%$, wins $35/40$, worst raw regression $1.73\%$. The analytical bound in the Discussion uses $L_\text{adj}{=}126.0$ and $L_\text{RL-WS}{=}54.9$, which now match the rest of the paper and give $56.4\%$ exactly. Consistency is still one of this submission's strongest assets.

## Weaknesses

**[W1] Latency-sensitivity evidence remains analytical and single-cell (was iter-10 W1).** The new bound in §VII is on the \textit{best} cell (MoE K32N8 $b{=}4\times$, saving $56.4\%$), not on the cells where the paper's claim is actually vulnerable. The cells most at risk under a latency multiplier are low-NL\% cells where $\Delta_{\text{RL-WS vs Greedy}}$ is 1--2\,\%p and $L_\text{adj}$ is smaller (so an added $(\lambda{-}1)\cdot 2D$ is a larger fraction of the improvement). A 4-row table covering $\{$Tree AR K16N8 $4\times$, Hybrid TP+PP K16N8 $4\times$, MoE K32N8 $4\times$, Uniform K32N8 $4\times$$\}$ at $\lambda\in\{1.0, 1.5, 2.0\}$ would take one BookSim night and would fully close this. The qualitative claim survives a rebuttal; for camera-ready the full table is non-negotiable.

**[W2] Surrogate training split still undocumented (was iter-10 W5, Q1).** The text in §V.C is unchanged on this point. This is the single easiest fix in the entire paper and it did not land this round, so I am forced to treat it as a persisting concern. A one-sentence addition of the form "The 288 training samples are drawn from \{workload/config-list\}, disjoint from the 40 evaluation configurations at the (workload, K, N, budget) level" would resolve this.

**[W3] Switch-based topology comparison still absent (unchanged since iter 9).** I have asked for a single paragraph three times. The paper's "express links are a topological fix" framing now sits right next to a missing discussion of the other topological fix that PC members will name (NVSwitch / crossbar / fat tree). The paper would benefit from one paragraph in Discussion bounding "mesh+express dominates when per-link PHY area is the binding cost vs central-switch area", even without new experiments.

**[W4] Matched-cell GNN/RL-WS comparison still missing (unchanged since iter 10).** Table~VIII reads asymmetrically; the natural one-line fix is a footnote giving the GNN's improvement restricted to the 2-cell subset used for RL-WS on each unseen workload.

**[W5] RL-WS mean-uplift over greedy is still quantitatively modest (unchanged).** $+2.6\,\%\text{p}$ mean, dominated by a single +56.4\% cell; the Discussion now does commit to "RL-WS when NL\% leaves meaningful headroom" as the operating rule, which is better than iter 10, but a reader can still ask whether the engineering complexity is worth 2.6\,\%p. This is a "I would accept the answer the paper now gives" weakness, not a deal-breaker.

## Questions

1. **Surrogate split (third ask).** Please add one sentence in §V.C stating the (workload, K, N, budget) set used to generate the 288 BookSim surrogate-training samples and whether it is disjoint from the 40 evaluation configurations. If it \textit{is} disjoint, this resolves my W2 directly; if not, the warm-start mean-uplift should be reframed as "surrogate fit plus search" rather than pure optimization uplift.

2. **Latency-sensitivity table for camera-ready.** Please commit in rebuttal to publishing a per-cell RL-WS saving table at $\lambda\in\{1.0, 1.5, 2.0\}$ on the 4-cell set above, so the $2\,\%\text{p}$ headroom is not vulnerable to a single latency-model perturbation. The current analytical bound is acceptable for a rebuttal but not for camera-ready.

3. **Switch alternative scoping.** One paragraph in Discussion bounding when mesh+express wins vs a central switch. No new experiments needed.

## Rating

- Novelty: 3.5/5 (unchanged; warm-start + measured fallback is a genuine contribution, and the PARL-proxy framing is fairer than in iter 10)
- Technical Quality: 3/5 (unchanged; the analytical bound partially closes W1-iter10, but the surrogate split is still undocumented after an explicit iter-10 ask, which is a methodology transparency issue)
- Significance: 3.5/5 (unchanged; modest 2.6\,\%p RL uplift, but the fallback guarantee and NL\%-predictor-of-headroom are genuinely practitioner-useful)
- Presentation: 4/5 (up from 4 in iter 10's rating, now a full 4; Corollary/Theorem framing, $\tau$ alongside $\rho$, data consistency cleanup, explicit no-approx-guarantee disclosure)
- Overall: 3.5/5 (unchanged at Borderline)
- Confidence: 4/5 (unchanged)

## Decision

**Borderline.** Iteration 11 is a strictly better paper than iteration 10: the Kendall $\tau$ addition, the Corollary framing, the approximation-guarantee disclosure, the deadlock sketch, the multi-seed honesty, the $L_\text{adj}/L_\text{RL-WS}$ consistency cleanup, and the PARL-proxy reframing are each small moves, but together they close about half of the "architecture PC will reject this" surface area that iter 10 carried. The remaining concerns are, unfortunately, the two specific iter-10 asks I flagged for the rebuttal: the latency-sensitivity question now has an analytical \textit{partial} answer (single-cell, best-case, upper-bounded) rather than the BookSim table I asked for, and the surrogate training split is still not stated in §V.C despite being a two-sentence fix. Neither is fatal on its own. If the rebuttal (a) commits to a per-cell $\lambda\in\{1.0,1.5,2.0\}$ table in camera-ready on at least 4 cells covering both low- and high-NL\% workloads, and (b) states the 288-sample surrogate split in §V.C, I would move to Weak Accept. Without both of these in the rebuttal, I stay at Borderline. **DATE bar verdict:** clears the DATE bar \textit{if} both rebuttal items land; otherwise it sits just below, in the same band as iter 10.
