# Reviewer 5 (Skeptic) — Iteration 15

**Paper**: "Predict, Place, Refine: Non-Locality-Guided Express Link Placement for LLM Chiplet Networks"
**Track**: Architecture (DAC/DATE-class)
**Calibration**: ISCA-class accept rate ~20%
**Prior decision (iter-14)**: Borderline / lean Weak Accept, 3.0/5

---

## Summary

The iter-15 revision is a smaller delta than iter-14 → it touches three things: (1) an expanded PARL contrast in §II reframed around three differentiation axes (predictor / multi-warm-start / safety) with citations to the paper's own ablation numbers (4/28 fallback, 17 greedy-warm + 11 FBfly-warm); (2) an expanded MoE Setup paragraph in §VI with Zipf $s{=}1.5$, top-2, $n_\text{seeds}{=}5$, plus DeepSeek-V3 / Mixtral / GShard citations; (3) a new wall-clock cost table (§VI.D Table 9) reporting per-cell ~15–45 min and full-sweep ~10–20 hr.

The two structural objections that survived iter-14 (W1', W2', W3', W4', W6' from my iter-14 review) have not been addressed by new experiments: there is still no held-out workload validation of the NL%≥77 / NL%≤50 cutoffs, no workload-aware FBfly variant, no 48-shot random-policy ablation, no ρ on non-MoE cells, and no multi-seed end-to-end variance study. The iter-15 changes are scoping / transparency improvements rather than evidence additions, and each one carries its own new-but-smaller skeptical hook.

What does change my read: the PARL contrast is now defensible as a *positioning* statement (it does not pretend to numerically beat PARL, only to differentiate along three axes the authors actually demonstrate empirically — fallback fires 4/28, both warm-start sources contribute 11+17). The MoE calibration is no longer hand-wavy ("Zipf-skewed top-2") — it is now a defined sampling procedure with $s{=}1.5$, $n_\text{seeds}{=}5$, and citations whose qualitative direction (production MoE has skewed expert popularity) is supported. The cost table is explicit about being design-time and amortized.

What does not change: the headline aggregate is still MoE-driven (Limitation (ii), §VI.E disclose this honestly), the deployment classifier is still curve-fit on 28 sampled points with a planted (50%, 77%) gap, and the largest single number — −83.2% on MoE Skewed K=32 N=8 — is still vs a workload-blind FBfly that nobody would deploy on a known skewed-MoE workload.

I will hold my vote at **3.0/5 (Borderline / lean Weak Accept)**. The iter-15 changes are real but do not close the structural objections; they make the paper harder to dismiss on transparency grounds while leaving the core empirical asks unanswered.

---

## Iter-14 Surviving Attacks: Status After Iter-15

| Attack (iter-14) | Status (iter-15) | Notes |
|---|---|---|
| W1' (post-hoc fitted NL%≥77 / NL%≤50 cutoffs) | **Not closed** | No held-out workload added. The (50%, 77%) sampling gap is still empty by design. |
| W2' (no workload-aware FBfly variant) | **Not closed** | The −83.2% MoE headline is still vs a workload-blind FBfly. |
| W3' (no 48-shot random-policy / perturbed-greedy ablation) | **Not closed** | Ablation §VI.C still reads on `min(greedy, FBfly)`, not on a search-only baseline. |
| W4' (Spearman ρ on non-MoE cells unreported) | **Not closed** | Pooled ρ=0.83 unchanged; non-MoE ρ still missing. |
| W5' (C1 vs Abstract low-NL framing inconsistency) | **Partial** | C1 line 55 still says "RL-WS matches within ±1 cycle" on low-NL; abstract says "8/12 strict beats with max −5.3%". Same inconsistency carried over. |
| W6' (deployment-classifier b-conditioning silence) | **Not closed** | No b-sweep of the classifier rule. §VI.A still acknowledges crossover at b=2× without quantifying classifier instability. |
| W7' (PARL only qualitative) | **Improved positioning, no new numbers** | iter-15 adds three differentiation axes with internal-ablation-supported numbers. PARL is still cited-only at the empirical level. |
| W8' (no multi-seed end-to-end variance) | **Not closed** | Limitation (v) still labels this future work. |

Net: 0 closed, 1 partial, 1 positioning improvement, 6 not closed. Iter-15 is a writing pass, not an experiment pass.

---

## Probes Requested by the Re-Review Task

### Probe 1: PARL contrast leans on OUR ablation numbers, not on PARL's

The §II revision adds a substantive paragraph (lines 70–71) framing PARL contrast along three axes:

- **(i) Workload predictor**: PARL has none; we have NL%.
- **(ii) Initialization**: PARL is cold-start PPO; we are dual-warm-start REINFORCE, with the 17 greedy-warm + 11 FBfly-warm split cited as evidence both sources matter.
- **(iii) Safety**: PARL has no post-hoc fallback; ours fires 4/28.

This positioning is internally consistent. It cites our own Table 8 ablation correctly. **But it remains a "what PARL does not do" argument, not a "PARL underperforms ours numerically on our 28 cells" argument.** A skeptical PC reviewer will read: "the authors are differentiating by enumerating axes their own design optimizes. PARL was published 6 months ago in Oct 2025 and the authors do not run it." The paragraph closes with: *"A direct end-to-end reproduction of PARL on our 28-cell benchmark would require porting its Interference-Score reward to BookSim and assembling a multi-tenant workload mix that fits its evaluation contract; we leave that to future work and position the design-space differences in Table 1."* This is a defensible scoping claim *if* the venue is DAC/DATE characterization-track. At ISCA/MICRO this would be a fatal Reviewer 2 hook: "the closest learned baseline is uncomparable by your own admission."

**Specifically**: claim (ii) is partly tautological. The 17/11 split tells us *that within our pipeline both warm-start sources contribute*, not *that warm-starting beats cold-start*. The iter-12 internal ablation ("cold-RL can regress versus a workload-aware greedy by >10% on adversarial cells") is referenced in the paragraph but not in the paper's tables — a skeptical reviewer will ask "where is the >10% regression number?" and find that it lives only in narrative. If the iter-12 cold-vs-warm comparison is real, it should be a row in Table 8.

Verdict: **the PARL contrast is rhetorically improved but remains numerically defenseless against "you described what PARL does not do, you did not show what PARL actually delivers".** This is the iter-13 W7' objection in slightly different clothing.

### Probe 2: Wall-clock numbers are claimed as estimates without timing methodology

§VI.D Table 9 is new. It reports:

- Surrogate v2 training: ~3 min total (one-time, amortized over 28 cells)
- RL training: 16 seeds × 1000 episodes (parallel), ~3–5 min
- BookSim selection: ≤48 RL candidates × 4 rates, ~10–40 min
- Baseline configs in BookSim: ~1–3 min
- **Total per-cell (parallelized, 8-core): ~15–45 min**
- **Total for full 28-cell sweep: ~10–20 hr**

The numbers are reasonable rough budgets. But:

1. **Methodology is not disclosed.** The table caption says "wall-clock per cell" but does not say what hardware was used, whether the ranges are min/max across 28 cells or 95th-percentile bounds, or whether they are measured on an actual run or estimated from individual-component timings. "Parallelized, 8-core" appears in a row label but the specific CPU model, BookSim build flags, and number of concurrent BookSim processes are not specified. A reviewer who tries to reproduce on the (open) repo will get a different number and have no rubric to judge whether their attempt matches.

2. **The ranges are wide.** "BookSim selection: $\sim$10–40 min" is a 4× spread; "Total per-cell: $\sim$15–45 min" is a 3× spread. For a paper that reports ρ=0.83 to 2-decimal precision and savings to 0.1% precision, the wall-clock table reads sloppily by comparison.

3. **The 10–20 hr total-sweep figure is not derivable from the per-cell range.** $28 \times 15$ min = 7 hr; $28 \times 45$ min = 21 hr; the lower bound of 10 hr is consistent with the upper but the table does not say whether cells run sequentially or in parallel across cells. If the 8-core parallelization is *within* a cell (parallel across the 16 RL seeds), then 28 cells × 15-45 min sequentially gives 7–21 hr — close to the stated 10–20 but not exactly. If it is *across* cells too, the total would be smaller.

4. **No comparison.** Table 9 reports cost in absolute terms but does not contrast to alternatives. PARL's wall-clock is unspecified (consistent with not running it), but greedy/FBfly are reported as <1s — fine. What is missing: how does this cost compare to a single training-run iteration of an LLM at this $K, N$? The "design-time" framing (§VI.D last paragraph) helps qualitatively, but a quantitative anchor (e.g., "0.001% of one pre-training run") would defang the obvious "is this practical?" question.

**Verdict**: the cost table is honest in framing (estimated, ranged, design-time, amortized) but is not a measured timing study. It reads as scoping disclosure rather than engineering evidence. For a characterization paper this is acceptable; for a "we built a system" claim it is thin.

### Probe 3: Zipf s=1.5 is well-cited but the actual production "concentration ratio" claim is not quantified

Line 280 (§VI Setup) says:

> *"This Zipf exponent is consistent with measured expert-popularity skew in production MoE language models — DeepSeek-V3 reports concentration ratios in the same regime, and Mixtral-8x7B shows comparable hot-expert dominance under top-2 routing."*

This is a step up from iter-14's "Zipf-skewed top-2" (which gave no $s$). Three concerns:

1. **No specific number from DeepSeek-V3.** The paper cites the V3 report~\cite{deepseekv3} but does not extract a number such as "the top-2 experts receive X% of dispatch in DeepSeek-V3, and our Zipf(1.5) places approximately 36% on the top-2 ranks at $K{=}32$ — same regime." The 36% figure for our model is in the paper (line 280: "Zipf(1.5) places approximately 36% of total dispatch on the top-2 ranks at $K{=}32$"), but DeepSeek-V3's measured value is not reported. A reviewer who reads the V3 technical report will find that V3's auxiliary-loss-free balancing is *designed to suppress* hot-expert dominance during training; the production-deployment concentration ratio depends on whether routing is taken pre- or post-balancing-loss adjustment. Without a specific DeepSeek-V3 number, "the same regime" is unfalsifiable.

2. **Mixtral-8x7B routing is reported in their paper, but not extracted here either.** Mixtral~\cite{mixtral} reports per-layer expert utilization that is closer to *near-uniform* in some layers (deliberate via load-balancing loss) and skewed in others. Our Zipf(1.5) reflects the more skewed end. Without saying which layers / which routing decisions match Zipf(1.5), the citation is decorative.

3. **GShard contrast (line 280)** — the claim that earlier MoE NoI studies that assumed uniform top-$k$ dispatch~\cite{gshard} "are dominated by load balancing rather than placement, and would conflate the two effects" is rhetorically useful but unsupported by reference to a specific NoI study that used uniform dispatch. GShard is the foundational MoE paper, not a NoI study; citing it as the prior assumption to dispute is mildly off-target. The right citation would be a chiplet NoI MoE evaluation that actually used uniform top-$k$ — does one exist?

**Verdict**: the Zipf calibration is now a *defined sampling procedure with $s$ and $n_\text{seeds}$ disclosed*, which closes the iter-14 procedural objection. But the connection to production MoE remains *qualitative* — citations support the *direction* of skew, not the specific magnitude of $s{=}1.5$. A reviewer who pushes here will find that DeepSeek-V3's deployment skew is engineered to be *less* than Zipf(1.5) by their own balancing-loss-free design. The MoE Skewed result therefore sits on a calibration that *production deployments actively try to avoid*. This does not invalidate the result (the workload is a *stress test*, and stress tests are useful), but it does undercut the framing that MoE Skewed represents a realistic production target.

The honest concession here would be: "Zipf(1.5) represents a deliberately-skewed stress regime; production MoE deployments typically operate under explicit balancing losses that suppress this skew, in which case the 91% NL workload would drift toward the Uniform Random regime where our gain over FBfly is +2.3% rather than +45.6%." This sentence is missing.

---

## Strengths Specific to Iter-15

- **PARL three-axis contrast (§II)** is cleaner than iter-14's prose. The three axes are individually defensible; the citation to our own ablation numbers (17/11 split, 4/28 fallback) gives the differentiation traction it lacked.
- **MoE calibration parameters (Zipf $s{=}1.5$, top-2, $n_\text{seeds}{=}5$)** are now disclosed — previously they were implicit. Reproducibility improved.
- **Wall-clock Table 9** is a non-trivial transparency win even though it is estimated. Most papers in this space do not report cost at all.
- **§VI.D last paragraph** explicitly acknowledges that the NL%-based classifier lets architects skip RL-WS on NL≤50% workloads, and that greedy/FBfly remain available as fast deterministic defaults. This conditional-cost framing is honest and matches the deployment-classifier thesis.

---

## Weaknesses Specific to Iter-15

### W1'' [MAJOR]. The PARL three-axis contrast is supported by *our own* ablation numbers, but the iter-12 cold-vs-warm regression evidence is narrative-only.

§II line 71 cites: *"our internal cold-vs-warm comparison (and the iter-12 ablation that informed our design) shows is unstable on structured workloads such as Tree All-Reduce: cold-RL can regress versus a workload-aware greedy by >10% on adversarial cells."* This is a strong empirical claim, but the >10% number does not appear in any table. If it is real, it deserves a row in Table 8 (e.g., "Cold-start REINFORCE, no warm-start: best/mean over 28 cells: −X% / −Y%"). As written, the strongest argument for warm-start over cold-start is anecdotal text. A reviewer will ask: "show the row."

Additional: the phrase "the iter-12 ablation that informed our design" should not appear in the camera-ready paper. "iter-12" is internal versioning; rephrase as "an ablation that informed our design" or — better — promote it to a numbered ablation row in Table 8. **Action**: remove the "iter-12" reference (line 71) regardless of whether the cold-RL row gets added.

### W2'' [MODERATE]. The Zipf(1.5) calibration's tension with production MoE balancing is undisclosed.

Production MoE deployments (DeepSeek-V3, Mixtral-8x7B) use auxiliary balancing losses or auxiliary-loss-free routing (V3) precisely to *prevent* Zipf-style hot-expert concentration during training and inference. Citing these systems as evidence that Zipf(1.5) is "in the same regime as production" inverts their stated design intent. The iter-15 §VI calibration paragraph would be sharpened by saying: "Zipf(1.5) represents a worst-case skew; production MoE explicitly suppresses skew via balancing losses, but residual hot-expert concentration in deployed systems remains the regime where express-link placement matters most." This re-frames the result as "stress test that exposes structural placement effects" rather than "matches production traffic."

### W3'' [MODERATE]. Table 9 wall-clock ranges have 3–4× spread without disclosed methodology.

For a reproducibility-conscious reader: which BookSim build (rate, packets-per-injection, simulation length), which CPU (and whether SMT was enabled), how many concurrent BookSim processes per node, and what determines the low end vs the high end of each range. The 10–20 hr total-sweep figure also needs explicit clarification: is this 28 cells run sequentially each consuming 15–45 min, or is it 28 cells run in parallel across 8 cores (in which case total = max-cell-time × ceil(28/parallelism))? Without this, the table reads as "rough order-of-magnitude budget" — which is what the caption says, but the precision of the bounds (10, 20, 15, 45) suggests measurement.

### W4'' [MODERATE]. The §II PARL paragraph (line 71) is now ~330 words long and dilutes the related work section.

The original §II was crisp; iter-15 adds substantial prose to PARL contrast at the expense of brevity. A revision that compresses (i)–(iii) into 2–3 sentences each and moves the cold-vs-warm narrative claim to a Table 8 row would read tighter and would force the empirical evidence into a table where it can be falsified. As written, the PARL paragraph reads like a defensive monologue.

### W5'' [MODERATE]. Conclusion's "deployment classifier" framing has not been b-conditioned.

The Conclusion still reads (line 532): *"compute NL\% first, fall back to FBfly when NL\% is low, and invoke RL-WS whenever NL\%$\ge$77\%"*. This is the headline deployment rule. §VI.A admits a crossover at $b{=}2\times$ and Limitation (ii)+(v) acknowledge that the headline is at $b{=}4\times$, but the Conclusion's classifier is not annotated with budget. An architect reading only the Conclusion will deploy RL-WS on a high-NL workload at $b{=}2\times$ and may observe a *regression* — exactly the regime §VI.A admits exists. **Specific fix**: add "(at $b\!\ge\!3\times$)" to the Conclusion's classifier rule, or annotate the abstract's deployment-classifier sentence (line 31) similarly. iter-14 W6' is unchanged.

### W6'' [MINOR]. C1 (line 55) vs Abstract (line 31) inconsistency carries over.

C1 still says "RL-WS matches within ±1 cycle" on low-NL; abstract says "8/12 strict beats with max −5.3% margin". Reconcile to the abstract's framing or qualify C1 to "RL-WS matches within ±1 cycle on 4/12 low-NL cells; on the remaining 8/12 it strictly beats FBfly by ≤5.3%". This was iter-14 W5'.

### W7'' [MINOR]. The §VI.B claim about routing-algorithm-independence-of-NL\%-as-predictor is not directly tested in iter-15 either.

Line 215: *"The correlation is stable under method substitution: replacing RL-WS with greedy yields a similar rank ordering, indicating that NL\% predicts the *raw express-link benefit* rather than a property of any specific placement method."* This is a useful claim. But the specific Spearman ρ for NL% vs greedy saving is not reported. Adding this single number (e.g., "ρ_greedy = 0.79, ρ_FBfly = 0.74, ρ_RL-WS = 0.83") would substantiate the "method-independence" claim quantitatively.

### W8'' [MINOR]. The cost table does not include the NL%-classifier-skip economy.

§VI.D last paragraph mentions that the deployment classifier saves RL-WS cost on NL≤50% cells, but the table itself does not quantify this. A row "Total cost on classifier-positive subset (16 high-NL cells)" would directly support the deployment-classifier framing. Currently the table reports the cost of running RL-WS on *every* cell, which the paper's own deployment rule says architects should *not* do.

---

## Questions for Authors (carry-over from iter-14, plus iter-15-specific)

1. (Carry-over from iter-14 Q1) **ρ on the 24 non-MoE cells.** Single number. Iter-15 did not add it.
2. (Carry-over from iter-14 Q2) **Workload-aware FBfly variant.** Iter-15 did not add it.
3. (Carry-over from iter-14 Q3) **48-shot greedy-with-tiebreaks ensemble baseline.** Iter-15 did not add it.
4. (Carry-over from iter-14 Q4) **Held-out workload validation of NL% cutoffs.** Iter-15 did not add it.
5. (Carry-over from iter-14 Q5) **Multi-seed end-to-end variance.** Iter-15 did not add it.
6. (Carry-over from iter-14 Q6) **b-conditioning of the deployment classifier.** Iter-15 did not add it.
7. (Carry-over from iter-14 Q7) **C1 vs abstract reconciliation.** Iter-15 did not reconcile.
8. **NEW (iter-15 Q8): Where is the "iter-12 cold-vs-warm regression >10%" row in Table 8?** The PARL contrast paragraph leans on this empirical claim; if it is real, it should be in the ablation table. If it is not real, the paragraph needs revision.
9. **NEW (iter-15 Q9): What is the measured (not estimated) wall-clock for at least one representative cell?** Run one full pipeline end-to-end on disclosed hardware and report the actual elapsed time. The Table 9 ranges are presented with quantitative precision (15–45, 10–20) but are described qualitatively as estimates; a single anchor measurement would calibrate the table.
10. **NEW (iter-15 Q10): What concentration ratio does DeepSeek-V3 actually report on top-2 dispatch under their auxiliary-loss-free routing, and what fraction of MoE production traffic is closer to Zipf(1.5) vs near-uniform?** A specific reference will either support or weaken the "in the same regime" framing. The honest answer ("our Zipf(1.5) is a stress test; production has lower skew due to balancing losses") would actually strengthen the paper's NL%-classifier framing — RL-WS demonstrates the *upper-bound* placement gain when skew is present.

---

## Detailed Comments (line references)

- **Line 31 (Abstract)**: still leads with the −83.2% best-cell number; workload-mean disclosure (−63.1% on MoE) is in Table 6, and the classifier rule in the abstract does not specify b. iter-14 L31 comment unchanged.
- **Line 55 (C1)**: "RL-WS matches within ±1 cycle" on low-NL still contradicts abstract's "8/12 strict beats with max −5.3%". iter-14 W11/W5' unchanged.
- **Line 71 (PARL contrast)**: remove "iter-12 ablation that informed our design"; either promote to Table 8 row or generalize to "an internal cold-vs-warm comparison".
- **Line 215 (NL% predictor)**: add ρ_greedy and ρ_FBfly alongside ρ_RL-WS = 0.83 to substantiate the "method-independence" claim.
- **Line 280 (Setup, MoE calibration)**: cite a *specific* concentration ratio from DeepSeek-V3 or Mixtral, or reframe as "stress-test calibration with $s{=}1.5$; production deployments typically operate at lower skew due to balancing losses."
- **Line 280 (GShard contrast)**: GShard is not a NoI study; cite an actual chiplet NoI study that assumed uniform top-$k$ dispatch, or remove the contrast.
- **Lines 411–439 (Table 9)**: disclose hardware (CPU model, core count, BookSim build flags, parallelism scope: within-cell vs across-cell). Add a row for cost on the classifier-positive subset (16 cells).
- **Line 441**: "$\sim$10–20 hr" — clarify whether this is sequential cells × per-cell or parallel-across-cells × max-per-cell.
- **Line 526 (Limitation (vi))**: PARL framing is unchanged from iter-14. Consider adding limitation (ix): "deployment classifier cutoffs (NL%≥77, NL%≤50) inspected post-hoc on the same 28 cells used for evaluation; held-out workload validation is future work." This was iter-14 L487 / W3 carry-over.
- **Line 532 (Conclusion classifier rule)**: annotate with "(at $b{\ge}3\times$)" to disclose budget conditioning.

---

## Ratings (iter-15 vs iter-14)

| Dimension | iter-13 | iter-14 | iter-15 | Change Driver |
|---|---|---|---|---|
| Novelty | 2 | 2 | **2** | No new technical content; PARL contrast is sharper but still positioning-only. |
| Technical Quality | 2 | 3 | **3** | No new experiments. iter-14 ablation set unchanged. The structural objections from iter-14 W1'–W6' all carry. |
| Significance | 2 | 2 | **2** | Same. Headline still MoE-driven, classifier still post-hoc, gap to baseline-tuning still open. |
| Presentation | 3 | 4 | **4** | PARL contrast clearer, MoE calibration disclosed, cost table added — but C1/abstract drift, b-conditioning silence, and "iter-12" residual all carry. Net unchanged. |
| Overall | 2 | 3 | **3** | Same as iter-14. Iter-15 is a writing pass, not an evidence pass. |
| Confidence | 4 | 4 | **4** | Same. |

---

## Decision

**Hold at Borderline (lean Weak Accept), 3.0/5.**

I do not raise. The iter-15 changes are genuine improvements in scoping and disclosure, but they do not respond to any of the six structural empirical asks I left open in iter-14. Specifically:

- ρ on non-MoE cells: still missing.
- Workload-aware FBfly: still missing.
- 48-shot random/perturbed-greedy ablation: still missing.
- Held-out workload validation of NL% cutoffs: still missing.
- Multi-seed end-to-end variance: still missing.
- b-conditioning of the classifier rule: still silent.

Each of these is roughly one day of work; none has been added. iter-15 instead invests in (1) PARL positioning (rhetorical), (2) MoE calibration disclosure (procedural), and (3) cost-table transparency (scoping). All three are improvements, but they sit *adjacent* to the surviving objections rather than answering them.

What would shift to clear Weak Accept (unchanged from iter-14):

1. ρ on non-MoE cells (single number, one paragraph).
2. Workload-aware FBfly variant (1 column in Table 6 + 1 paragraph).
3. 48-shot search-only ablation (1 row in Table 8).

What would additionally shift, given iter-15:

4. Promote the "iter-12 cold-vs-warm regression >10%" claim to an actual row in Table 8, and remove the "iter-12" string from the camera-ready.
5. Annotate the classifier rule with budget: "RL-WS at NL%≥77% \textit{and} $b{\ge}3\times$."
6. Quantify the DeepSeek-V3 concentration ratio with a specific number, or reframe Zipf(1.5) explicitly as a stress test.

What would not shift without more work (unchanged from iter-14):

- Held-out workload validation.
- Multi-seed end-to-end retraining variance.
- PARL reproduction.

The paper now reads as honestly-scoped DAC/DATE characterization. At ISCA/MICRO, the surviving structural objections remain venue-fatal (Reviewer 2: "MoE drives everything, FBfly is workload-blind, classifier is curve-fit on 28 sampled points with a planted gap, closest learned method not run by your own admission"). At DAC/DATE, those same objections become "limitations the authors disclosed and we will revisit at the next venue."

The integrity of disclosure is now high enough that an aggressive reviewer cannot win on overclaim grounds; they have to win on "is what you show enough?" That is the right question for this paper, and my answer remains: borderline.

**Final score: 3.0/5 (Borderline, leaning Weak Accept). Hold.**
