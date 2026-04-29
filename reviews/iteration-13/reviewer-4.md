# Reviewer 4 (Theory / Analysis Expert) — Iteration 13

**Paper:** Predict, Place, Refine: Non-Locality-Guided Express Link Placement for LLM Chiplet Networks
**Track:** Architecture (DAC/DATE/ISCA/MICRO/HPCA)
**Reviewer focus:** rigor of analytical bounds, correctness of definitions, statistical validity, generalization claims.

---

## Summary

The paper contains three intertwined contributions: (i) a closed-form scaling result for "phantom load" amplification on a $K$-chiplet square grid under XY routing, claimed as $\Theta(K^{3/2})$ with a routing-algorithm independence argument; (ii) a definition of a static workload statistic (the non-locality fraction, NL%) and an empirical claim that NL% predicts express-link benefit (Spearman $\rho{=}0.83$ on 28 cells) and acts as a "deployment classifier" between RL-based placement (RL-WS) and a topology-aware heuristic (FBfly); (iii) a multi-warm-start REINFORCE method (RL-WS) trained against a 501-dim rate-aware MLP surrogate (Spearman $\rho{=}0.928$ on a 20% held-out split, 1408 samples), with 16 seeds × top-3 candidates per cell validated by BookSim and reported to attain a 35.6% mean latency saving versus an adjacent-uniform baseline and to strictly beat FBfly on 24/28 cells.

I focus on the analytical and statistical core. The closed-form Theorem 1 / Corollary 1 are essentially correct under the stated XY-uniform-all-to-all assumptions but are presented with several gaps that a reviewer in this slot will read as informality. The "routing algorithm independence" claim is overclaimed: the paper shows a property for three specific routing schemes, not independence in any algorithmic-class sense. NL%'s definition is well-formed but its "deployment classifier" status rests on a 28-point Spearman that is correlation-only and does not actually show layout-permutation stability or a calibrated decision threshold. The multi-warm-start RL is functionally an extensive search wrapped in a REINFORCE update; whether the policy gradient is actually doing work versus the BookSim top-$k$ argmax is not isolated.

The paper is technically interesting and the analytical core is largely defensible, but the *presentation* of the theory and the *statistical framing* of NL% are below the bar I expect for the architecture track of a top-tier venue. I lean toward weak reject in the current form, with a clear path to weak accept conditioned on the issues below being addressed.

---

## Strengths

- **S1. The scaling bound is real and clean.** The flow-counting derivation (lines 134–144) reduces to a standard combinatorial identity (number of source–destination pairs whose XY path crosses a given column boundary), and the resulting $\alpha_{\max} = R \cdot \lceil C/2 \rceil \cdot \lfloor C/2 \rfloor = \Theta(K^{3/2})$ for $R=C=\sqrt{K}$ is correct. The $4\times 4$ worked example ($\alpha=16$) and the scaling table (Table 2) are consistent.
- **S2. A genuinely useful design-time statistic.** Defining NL% on the *pre-routing* demand matrix (line 211) is the right call: it makes the statistic computable without simulation and decouples it from the placement method being evaluated. Showing that the rank correlation is method-stable (greedy vs. RL-WS produce the same NL%-ranking) is a non-trivial sanity check (line 214).
- **S3. The deployment-classifier framing is the right one.** Most prior NoI-RL work argues "RL is always better"; this paper instead identifies a regime (NL%≤50%) where the strongest non-RL heuristic (FBfly) is essentially optimal and RL is hard to justify. That is an unusually disciplined claim for the architecture-RL space.
- **S4. Post-hoc BookSim shortlist defends against surrogate error.** The final step (line 260) selects among 48 surrogate-shortlisted candidates by direct simulation, which is a clean way to guarantee that surrogate inaccuracy cannot produce a silent regression. This is a real strength relative to PARL-style cold-start RL with no measured gating.
- **S5. The wire-delay sensitivity sweep ($\lambda \in \{1,1.5,2\}$, Table 9) is exactly the right ablation.** Showing that the RL–greedy gap *grows* under heavier wire delay on high-NL workloads is a meaningful structural argument that the savings are not artifacts of an optimistic latency model.

---

## Weaknesses

### W1. Theorem 1 / Corollary 1 are stated, not proved.

The paper writes the formulas but never gives a proof. Specifically:

1. **Flow count derivation is not shown.** The expressions $F_H(c) = 2R(c{+}1)(C{-}c{-}1)$ and $F_V(r) = 2C(r{+}1)(R{-}r{-}1)$ require an explicit argument that the number of (source, destination) pairs whose XY shortest path crosses the boundary between column $c$ and column $c{+}1$ equals $R \cdot (c{+}1) \cdot R \cdot (C{-}c{-}1)$ before doubling for the two directions. The factor of 2 (two directions) is hand-waved. A two-line derivation would close this.
2. **"Each adjacent pair contributes exactly 2 direct flows" (line 140) is not a self-contained statement** — under the all-to-all assumption it is true (one flow each way), but the paper states the corollary as if this holds in general. Make this explicit.
3. **The $\Theta(\cdot)$ claim conflates max amplification with average amplification.** Corollary 1 covers $\alpha_{\max}$ only. The text on line 47 ("center-link amplification grows super-linearly") is fine, but the abstract and intro repeatedly use $\Theta(K^{3/2})$ as if it described the *typical* link, not the worst link. This is technically a max-load result. State both, or restrict the language.
4. **Edge cases.** What if $C$ is even vs. odd, or $R\ne C$? The formula $\alpha_{\max}=R \cdot \lceil C/2\rceil \cdot \lfloor C/2 \rfloor$ is fine for the maximizer at $c=\lfloor C/2\rfloor - 1$, but the paper does not say which boundary attains the max for non-square grids. Spell it out.
5. **No statement about uniqueness or symmetry assumptions.** XY routing is *deterministic*; YX gives the symmetric statement on vertical boundaries. The claim implicitly assumes a single deterministic shortest-path policy (no ties broken adversarially).

These are easy fixes, but in their absence the theorem reads as *a numerical observation in theorem environment*, not a proved result.

### W2. "Routing Algorithm Independence" is overclaimed.

Section 3.4 (lines 173–199) is titled "Routing Algorithm Independence" but only shows numerical results for three specific routings (XY/YX, ECMP, Valiant) on two grids. This is *not* a routing-independence theorem; it is an empirical observation. The conclusion "Phantom load is therefore a structural consequence of multi-hop adjacency, not an artifact of one routing algorithm" (line 199) is the *interpretation* the authors want, but it does not follow from three rows of a table.

A real independence statement would be of the form: "For any oblivious routing $R$ on a square grid with uniform all-to-all traffic, there exists a link with load $\Omega(K^{3/2})$." This is in fact true (Valiant gives a lower bound; the bisection-bandwidth argument gives an analogous bound for *any* deadlock-free routing on a 2D mesh) and should be stated and cited, not replaced by a 4-row table.

I strongly recommend: (a) rename the subsection to "Routing Algorithm Sensitivity" or "Empirical Robustness Across Routings", or (b) prove a one-paragraph bisection-bandwidth lower bound that applies to *any* routing.

### W3. NL% definition is layout-dependent and the paper does not characterize this dependency.

Line 205 defines NL% on $(T, G)$, where $G$ is the chiplet graph. This means NL% is *not* a property of the workload alone — it depends on which chiplets you place where on the interposer.

Concretely:
- Permuting the chiplet-to-grid assignment $\pi$ changes the hop distance $\mathrm{hop}_G(i,j)$ for many pairs and therefore changes NL%.
- An adversarial permutation can drive NL% from low to high without changing the workload.
- The paper never says how the chiplet-to-grid mapping was chosen for the 28 cells. Was it canonical? Random? Optimized?

This matters because the headline claim — "NL% predicts express-link benefit" — is only meaningful if the mapping is fixed by some independent criterion (e.g., the "natural" canonical assignment used by all baselines including FBfly). If the mapping is implicitly co-optimized with the placement, the predictor leaks information.

A paragraph on layout invariance is essential. At minimum: state that all methods see the same chiplet→grid mapping; show that NL% is stable under a few random relabelings (or report its variance under permutation).

### W4. The Spearman $\rho{=}0.83$ on 28 points needs more careful reporting.

- 28 is small. The reported $p=6.8\times 10^{-8}$ is the asymptotic two-tailed p-value of Spearman's $\rho$, which is fine but should be stated as such; consider an exact permutation p-value or a Fisher-z bootstrap CI for $\rho$.
- The 28 cells are *not* independent: 7 workloads × 4 (K,N) configurations. Many cells share the same NL% (one per workload at fixed K=32 — Table 5 reports a single NL% per workload). If multiple cells have identical NL% values, Spearman's tie correction matters. State the number of distinct NL% values used and how ties were handled.
- The abstract reports $\rho=0.83$, the body reports $\rho=0.825$ (line 214), the figure caption reports $\rho=0.74$ (line 346). These are inconsistent — please reconcile. The body and figure cannot disagree.
- The "rank correlation is stable under method substitution" sentence (line 214) needs the actual greedy-NL% Spearman number reported, not just asserted.

### W5. Surrogate v2 generalization claim is not properly validated.

The surrogate is trained on 1408 BookSim samples spanning all 28 cells (line 256: "samples that span all evaluated $(\text{workload}, K, N, b)$ cells"). This is the key issue: if the train/val split is *random within* the 1408 samples, then every $(\text{workload}, K, N, b)$ cell appears in both train and val, and the held-out $\rho{=}0.928$ measures *within-cell* generalization to *unseen allocations* in cells the model has already seen.

That is a much weaker claim than cross-cell generalization. For this paper's framing — "a single learned model handles multi-rate evaluation" (line 256) — the authors should additionally report:
- **Leave-one-cell-out CV**: train on 27 cells, evaluate on the held-out cell. Repeat 28 times. This is the relevant metric for whether the surrogate generalizes to *new* configurations.
- **Leave-one-workload-out CV**: even stronger; train on 6 workloads and evaluate on the 7th.

Without these, the $\rho{=}0.928$ is mostly a memorization signal and the surrogate's role in the system is poorly characterized.

### W6. Multi-warm-start RL is functionally extensive search, not principled RL.

The pipeline runs 16 seeds × top-3 surrogate-best candidates per seed = 48 candidates per cell, all of which are then BookSim-simulated and the argmin is taken. This is *enumerate-then-validate*. Two questions the paper does not answer:

1. **Ablation: is REINFORCE doing anything?** Replace REINFORCE rollouts with random swap-walks of the same length (matched compute) and report final BookSim latency. If random walks plus surrogate-shortlisting plus BookSim argmin do nearly as well, the policy-gradient component is not contributing, and the method should be re-described as a guided random-search method (which is fine — but it should be honest).
2. **Ablation: number of warm-start seeds.** What is the saving curve as the number of seeds drops from 16 to 8 to 4 to 1? At 1 seed, you have either greedy-only-warm or FBfly-only-warm. Showing the marginal value of multi-warm-start is the natural ablation; without it, the "16 seeds" looks like an arbitrary compute budget.

The post-hoc BookSim shortlist is genuinely defensive (see S4), but it makes "RL" effectively a candidate-generation distribution. The paper should commit to that framing or do the ablations to show otherwise.

### W7. The deployment-classifier threshold has a gap (50–77%).

Line 31 ("on the 16 high-NL cells (NL≥77%)") and line 318 ("when NL%≥77%") set the high-NL threshold at 77%, while the low-NL threshold is 50%. The 50–77% range contains *no* evaluated workloads (Table 5 shows a gap: the highest low-NL is Tree at 42%, the lowest high-NL is Hybrid TP+PP at 77%). The paper therefore cannot empirically distinguish between

- "RL-WS is essential at NL%≥77%" and
- "RL-WS is essential at NL%≥50%".

The "deployment classifier" claim is sharp on the data the paper has, but the threshold is undetermined: 50%, 65%, and 77% are all consistent with the evidence. The paper should either (a) construct a synthetic mid-NL workload (e.g., interpolate between Tree and Hybrid TP+PP) and report where the FBfly-vs-RL-WS gap opens, or (b) explicitly state that the threshold is "somewhere in (50%, 77%)" and flag this as a limitation. The current Discussion (line 397) reads as if 77% is the established cutoff, which is not supported.

### W8. The "guarantee" language is gone but the residual claim still needs a guard.

Compared to prior iterations, the post-hoc fallback has been removed, so RL-WS is not formally guaranteed to be ≤ greedy. Yet line 247 still says greedy is a "starting point, which the multi-warm-start RL refinement … extends further by also seeding from FBfly and selecting the BookSim-best of the resulting candidates", and the paper has 4 cells where RL-WS is worse than FBfly (line 370: "2 ties within ±0.1 cycle and 2 minor losses by ≤0.9 cycle").

Two cells lose to FBfly. The paper should: (a) report whether RL-WS is *also* worse than greedy on those cells (since BookSim selection is over all 48 candidates plus baselines, RL-WS should never be worse than greedy *if greedy is in the candidate set*). If greedy and FBfly are in the candidate set, the BookSim argmin trivially dominates them. The "minor losses by ≤0.9 cycle" suggests they are not in the set, which contradicts the natural reading of line 260. Clarify.

### W9. Big-O wire/area model is suspiciously linear.

Table 8 uses a strictly linear scaling: 10/20/30/40 mm wire length for $d=1/2/3/4$, with proportional area and power. On a real silicon interposer, longer wires need (i) repeaters (super-linear power), (ii) wider tracks for IR-drop and crosstalk, and (iii) layer transitions through vias. The paper acknowledges this is "CoWoS-class estimates" but the "comparative" defense (line 374) is too weak: the $d=4$ cost model is what determines whether RL-WS's preference for distance-4 expresses on MoE Skewed is realistic. State the assumption that wire RC is ignored, or cite a specific physical model (e.g., from Florets or a CoWoS PDK reference).

### W10. Notation and terminology bugs.

- Line 47: "At $K{=}32$, this amplification reaches 64×" — Table 2 shows 64 at 4×8 (which is K=32) and 128 at 8×8 (K=64). The intro number is fine but the abstract claim "$\Theta(K^{3/2})$" is most prominently illustrated at K=64 (128×), not K=32 (64×). A more compact way to write this: "the worst-link amplification at $K{=}64$ reaches $128\times$, scaling as $K^{3/2}$."
- Line 31 abstract says "Spearman $\rho=0.83$"; line 214 body says "$\rho=0.825$"; figure caption (line 346) says "$\rho=0.74$". As noted in W4, these must be reconciled.
- Line 156: "Imbalance" column in Table 1 — what does 1.3 vs 2.7 mean? max/avg ratio? max/min? Define.
- Line 175: "directional link loads" vs "undirected closed-form" — the *nominal* mismatch is fine, but "Imbalance" of 18.7 in Table 3 is suspiciously high for a standard ECMP run. Sanity-check: under ECMP on a 4×8 mesh with uniform all-to-all, what does a textbook bisection argument predict?

---

## Questions for the Authors

1. **Theorem 1 proof.** Please provide the two-line combinatorial derivation of $F_H(c) = 2R(c{+}1)(C{-}c{-}1)$. Specifically: (a) why is the count of (s,d) pairs with XY paths crossing the c|c+1 boundary exactly $R(c{+}1) \cdot R(C{-}c{-}1)$? (b) is the factor of 2 the two traffic directions or the two endpoints' bidirectional flows?

2. **Routing independence.** Can you state and prove (or cite) a routing-class independence result, e.g., "for any oblivious deadlock-free routing on a $\sqrt{K}\times\sqrt{K}$ mesh under uniform all-to-all, some link carries $\Omega(K^{3/2})$ traffic"? The bisection-bandwidth argument should give exactly this.

3. **NL% layout permutation.** For each of the 28 cells, was the chiplet-to-grid mapping fixed canonically, or chosen per workload? What is $\mathrm{Var}_\pi[\mathrm{NL\%}(T, G_\pi)]$ for a Hybrid TP+PP workload over random permutations $\pi$?

4. **Spearman value reconciliation.** The abstract says 0.83, body says 0.825, figure caption says 0.74. Which is the correct value, and on which subset of cells?

5. **Surrogate generalization.** Was the 80/20 train/val split done *across all 1408 samples uniformly*, or *across cells*? Please report leave-one-cell-out validation $\rho$.

6. **REINFORCE ablation.** What is the BookSim-best latency over 48 candidates if you replace REINFORCE rollouts with random swap-walks of equivalent length? If equal or close, the claim shifts from "RL refinement" to "guided random search with BookSim validation" — both are valid but should be stated.

7. **Deployment threshold.** Where empirically does the high-vs-low-NL deployment threshold actually fall? Can you produce a synthetic mid-NL (e.g., 60%) workload and report whether RL-WS strictly beats FBfly there?

8. **Greedy in candidate set.** Is the greedy allocation always included as a candidate in the final BookSim selection (line 260)? If yes, RL-WS should never be worse than greedy. If no, please state.

9. **"Independent" routing claim.** Lines 173–199 should either be retitled to "Sensitivity" or augmented with a routing-class lower bound.

10. **All-to-all and Tree at K=32 N=8 b=2x.** The smallest cell is reported at $b=2\times$ (line 271). Why this choice? It introduces a budget-confound for Tree's "minor losses".

---

## Missing References

The paper would benefit from referencing the following analytical and architectural works:

- **Bisection bandwidth lower bounds for mesh networks.** Leiserson's *Fat-Trees* (TC '85) and Dally & Towles, *Principles and Practices of Interconnection Networks* (Ch. 3) give the canonical bisection-based $\Omega(K^{3/2})$ bound for 2D mesh worst-case load. Citing Dally–Towles makes the routing-independence claim trivial to state correctly.
- **Concentrated/express NoCs in monolithic context.** Beyond *Express Virtual Channels* and *cmesh*, the paper omits Kim et al., *Flattened Butterfly* (ISCA '07), which is the topology FBfly is named after, and Kim et al., *MECS* (HPCA '09). Citing these makes the FBfly baseline nameable.
- **Surrogate-assisted topology search.** Lin et al. *Optimizing Network-on-Chip with NoC Generators* and Krishnan et al. *Interconnect-Aware Area and Performance Estimation for Chiplet Architectures* (DAC '21) are precedents for surrogate-driven NoI design.
- **Off-policy / warm-started RL for combinatorial optimization.** Bello et al. *Neural Combinatorial Optimization with RL* (ICLR-W '17), Khalil et al. *Learning Combinatorial Optimization Algorithms over Graphs* (NeurIPS '17), and especially Mazyavkina et al., *RL for Combinatorial Optimization* (Comput. OR '21) provide the methodological context for RL-WS — the paper currently treats REINFORCE as a method without situating it.
- **Spearman small-sample statistics.** Note Hollander & Wolfe, *Nonparametric Statistical Methods* on tied-rank correction; and bootstrap CIs from Efron & Tibshirani.

---

## Detailed Comments (line-by-line)

- **Line 29 (abstract).** "We argue that a single static workload property … predicts both how much express links help … and when learned placement is worth invoking." This is a strong, specific thesis. Good. But the second clause ("when learned placement is worth invoking") only holds if the deployment threshold is established empirically; see W7.
- **Line 31 (abstract).** $\rho=0.83$. Reconcile with body (0.825) and figure caption (0.74).
- **Line 47.** "Adjacent links yield diminishing returns" — supported by Fig 1(b), but the figure caption is on line 43, not described in body. Add one sentence in §3 referencing how Fig 1(b) was generated (which workload, which K).
- **Lines 133–149.** The Theorem-Corollary block needs proofs in an appendix or a 5-line in-text derivation. As stated, it is informal. See W1.
- **Line 142.** $\alpha_{\max} = R\cdot\lceil C/2\rceil\cdot\lfloor C/2\rfloor$. State explicitly which boundary attains the max for non-square $R\ne C$.
- **Line 151.** "amplification is $\alpha = 32/2 = 16\times$". The "/2" assumes each adjacent pair has 2 direct flows under uniform all-to-all. State this as the normalization rule.
- **Line 156, Table 1 caption.** Define "Imbalance".
- **Line 175.** "directional link loads … not directly comparable to the undirected closed-form". OK, but Table 1 gives 16 at 4×4 (undirected) and Table 3 gives 111 at 4×4-XY (directional) — the factor of ~7 between them deserves a one-sentence reconciliation.
- **Line 199.** "Phantom load is therefore a structural consequence" — replace "therefore" with "consistent with this" until W2 is addressed.
- **Lines 205–211.** Define NL% as $\mathrm{NL\%}(T, G)$, but throughout the paper "NL%" is used as if it were a property of the workload alone. State the layout dependency explicitly here.
- **Line 211.** "static workload property *relative to a chosen chiplet layout*" — please *bold* "relative to a chosen chiplet layout" because much of the paper's later language elides this.
- **Line 214.** "Spearman rank correlation … is $\rho=0.825$ ($p=6.8\times 10^{-8}$)". Report Fisher-z 95% CI; report number of distinct NL% values; state tie-correction handling. See W4.
- **Line 247.** "We do *not* claim any constant-factor approximation guarantee". Good.
- **Line 256.** "Spearman $\rho{=}0.928$ on a held-out 20% validation split" — clarify split design (W5).
- **Line 258.** "weighted across the four training rates with weights $\{1{:}1, 2{:}1, 3{:}1, 4{:}2\}$" — these weights are arbitrary. Provide a one-line ablation (uniform vs current).
- **Line 270.** "primarily at $b{=}4\times$" — but Tree $K{=}32, N{=}8$ is at $b{=}2\times$. This means one cell uses a different budget. Either footnote *why* (line 271) or move the budget exception to a footnote so it does not look like cherry-picking.
- **Line 309.** "We keep $2\times$ in the evaluation because it is the canonical starting point". Good — this is the right disclosure of crossover behavior. But please also cite which prior work uses $2\times$ as the canonical start.
- **Line 327, Table 7.** Greedy column shows +24.8% overall, body abstract says +25.6%. These are different by 0.8pp. Reconcile.
- **Line 338.** "Overall +35.6% … 24/28 (2t), $-11.8\%$" — $-11.8$pp is dominated by the three MoE cells (line 363–367). State the median or the 25–75 IQR alongside the mean.
- **Line 346, Fig caption.** "Pooled Spearman $\rho=0.74$". Disagrees with body 0.825 and abstract 0.83. Hard to dismiss as rounding. Please fix.
- **Line 405.** Deadlock-freedom argument is informal. "A formal Duato-style proof is outside the scope" is fine, but the constructive VC assignment ("express link at horizontal distance $d$ travels in the $X$-VC subset") deserves one diagram or one paragraph more — it is the *only* deadlock-related content in the paper.
- **Line 408, Table 9.** Lambda sensitivity is well-designed. The text says RL-WS uplift "*grows*" with $\lambda$ on Uniform (+3.1pp → +5.8pp); Table 9 row 3 reads $+43.77/+46.90$, $+40.07/+43.95$, $+36.47/+42.25$. The deltas are 3.13, 3.88, 5.78 — yes, monotone increasing. But for MoE Skewed (row 4): 4.37, 3.03, 4.91 — *not* monotone. Soften "grows" to "is preserved or grows" or report the actual monotonicity.
- **Line 439, limitation (ii).** "We do not report per-cell BookSim variance over independent end-to-end RL re-runs". This is a real gap. Please report on at least one representative cell (MoE $K{=}32, N{=}8, b{=}4\times$), since the headline 83.2% number depends on it.
- **Line 445.** "$-19.0\%$ in latency" — confirm whether this is mean-of-percentages or percentage-of-means; these differ.

---

## Rating

| Axis | Score (1–5) |
|---|---|
| Novelty | 3 |
| Technical Quality | 2 |
| Significance | 4 |
| Presentation | 3 |
| **Overall** | **2.5** |
| Confidence | 4 |

**Notes on scoring:**
- *Novelty (3):* NL% as a deployment classifier is a genuinely new framing. Multi-warm-start + post-hoc BookSim selection is incremental. The $\Theta(K^{3/2})$ result is correct but is a reformulation of bisection-bandwidth-style reasoning.
- *Technical Quality (2):* The analytical content is presented informally (W1, W2). The statistical framing of NL% has methodological gaps (W3, W4, W5). The RL is under-ablated (W6). The Spearman value is internally inconsistent across abstract/body/figure (W4, line-level note on 346).
- *Significance (4):* If the deployment-classifier story holds up under W3/W4/W7, this is a useful design-time tool that LLM accelerator architects would actually use. The MoE 83% reduction is large enough to matter operationally.
- *Presentation (3):* Generally readable, but the Theorem block and the routing-independence section are presented with overconfident language. Multiple internal numerical inconsistencies (Spearman values, greedy mean, Tree budget exception).
- *Confidence (4):* I am confident in the analytical and statistical assessment. I have not re-run the BookSim experiments; I take the experimental numbers at face value modulo the internal inconsistencies flagged.

---

## Decision

**Weak Reject (2.5/5).**

The thesis is well-chosen and the analytical core, *once formalized*, would be defensible. But in the present form: (i) Theorem 1 is asserted without proof; (ii) "routing-algorithm independence" is overclaimed; (iii) NL%'s layout dependency is unaddressed; (iv) the Spearman value is internally inconsistent across three places in the paper; (v) the surrogate's cross-cell generalization is not actually tested; (vi) the RL component is under-ablated against random search.

I would move to **Weak Accept** with high confidence if the authors:

1. Provide a 5-line proof of Theorem 1 and either prove or cite a routing-class lower bound for §3.4.
2. Report NL% variance under random chiplet-to-grid permutation, and clarify the canonical mapping.
3. Reconcile the three Spearman values (0.83 / 0.825 / 0.74) — likely a single arithmetic fix.
4. Report leave-one-cell-out surrogate validation (or at least leave-one-workload-out).
5. Add a random-swap-walk ablation against REINFORCE at matched compute.
6. Either construct a mid-NL workload (around 60%) or explicitly state the deployment threshold as "in (50%, 77%) — undetermined within this evaluation".

None of these require new BookSim runs at scale; (1)(2)(3)(6) are textual or one-off computations, (4)(5) are bounded re-trainings on existing data.
