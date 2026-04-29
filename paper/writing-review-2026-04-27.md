# Writing Review — 2026-04-27

## Overall Assessment

The new "NL% as deployment classifier" framing is a clear improvement over the
previous v4 narrative. The paper now has a real, falsifiable thesis (NL% sharply
stratifies when learned placement is worth invoking) instead of the looser
"warm-start RL gives a Pareto improvement with safety guarantees" pitch. The
Predict / Place / Refine triptych is rhetorically strong and threads cleanly
from Abstract through §I contributions into §VI Main Result and the Conclusion.
FBfly as the strongest hand-engineered baseline gives the comparison real
teeth, and the per-cell MoE win (-83.2%) is a memorable headline number.

That said, the paper is not yet internally consistent. The pooled Spearman
value is reported as ρ=0.83 in Abstract/§I/Conclusion, ρ=0.825 in §IV body,
but ρ=0.74 in Fig. 4's caption — three different numbers for the same
correlation. The "Overall" row of Table 6 shows greedy = +24.8% mean saving,
but the Abstract, C3, and Conclusion all quote +25.6%. The Per-Cell Analysis
subsection drills down to three MoE cells but silently omits the fourth MoE
cell (K=16, N=4), even though Table 6 says MoE wins 4/4. The "deployment
classifier" framing in Abstract sounds slightly stronger than what §IV
actually shows: Abstract says "stays within simulation noise on the remaining 2"
while §VII Per-Cell Analysis admits "2 minor losses by ≤0.9 cycle" — these are
the same cells but the wording differs and the second framing is honest about
losses. Limitations does not mention the 1408-sample surrogate corpus or the
20% held-out validation — readers should be told the surrogate's training
distribution overlaps the eval set.

## Structure Issues

1. **§II "Background and Related Work" introduces FBfly but defers definition.**
   Line 65 calls FBfly "the strongest topology-aware baseline in our evaluation;
   it is workload-blind but exploits grid symmetry." But FBfly is not formally
   defined until Line 295 (§VI-A "Baseline definitions"), 230 lines later. A
   reader hitting Table 6 (Line 320) before reading §VI-A has only the §II
   one-line gloss. Move a 2-sentence definition of FBfly's row/column
   allocation rule into §II so Table 6 is self-contained.

2. **Per-Cell Analysis subsection arrives before Physical Overhead.** §VI-B
   (Per-Cell, Line 359) followed by §VI-C (Physical Overhead, Line 372) is
   awkward — Physical Overhead is essentially a methods footnote and should
   either come before the Main Result or be folded into Setup (§VI-A). As
   written, it interrupts the analytical thread and Discussion picks up cold.

3. **Fig. 3 "Cost-saving 4-panel" appears in §VI-A (Line 352) but is referenced
   only obliquely.** The figure is a `figure*` floated near the Main Result but
   is never named in the §VI-B Per-Cell Analysis discussion that would benefit
   from it. Either reference it explicitly in Per-Cell Analysis or move it
   adjacent to the corresponding text.

4. **§IV "Non-Locality Analysis" is one paragraph long.** Definition (Line 207)
   plus a single paragraph on empirical correlation (Line 213) is a thin
   section for a load-bearing concept. Given that NL% is the paper's title
   contribution, this should at minimum carry a small table of NL% values per
   workload (currently only available in Table 4 in §VI) and a sub-paragraph
   that previews the high-NL vs low-NL stratification.

5. **§VII Discussion is a wall of \textbf{}-headed paragraphs without
   subsection structure.** Six topics (workflow, design-time tradeoff, mesh
   vs switch, deadlock, λ sensitivity, limitations) are stacked with bold
   leads. λ sensitivity (Line 408) deserves its own subsection because it
   ships a non-trivial result + table; otherwise it reads as a footnote when
   it is actually a robustness result.

## Clarity Issues

1. **"Multi-warm-start" claim is ambiguous.** Line 254 says "16 independent
   training runs per cell: 8 seeded from the greedy allocation and 8 seeded
   from the FBfly allocation." Line 297 says "16 random seeds (8 greedy +
   8 FBfly)". Are these "seeds" in the random-seed sense or is each "seed"
   a complete independent training run? The cost analysis on Line 399
   ("1000 episodes × 16 warm-start seeds") implies the latter. State this
   once explicitly: "16 independent REINFORCE runs, each with a distinct
   random seed; 8 initialized from greedy, 8 from FBfly."

2. **"Top-3 surrogate-best" but selection over "≤48 candidates" is not
   reconciled.** Line 258: "16 × 3 = 48 surrogate-best candidates per cell."
   Line 260: "All 48 candidates plus the three baselines (adj-uniform,
   greedy, FBfly) are simulated in BookSim." Line 399: "≤48 candidates."
   Why "≤"? Are there cases where some seeds duplicate candidates? Add one
   sentence explaining the ≤ (probable cause: dedup of identical
   allocations across seeds).

3. **Table 6 column "vs FBfly" entries mix two scales.** "4/4, -63.1%" — the
   first is per-cell wins (count), the second is "per-workload mean latency
   reduction relative to FBfly" (percentage). The caption explains this, but
   the entries themselves look like a fraction. Consider splitting into two
   columns ("Wins" and "Δ vs FBfly") or annotating: "4/4 wins, -63.1% mean Δ".

4. **The "(2t)" / "(1t,1L)" / "(1L)" notation in Table 6 is undefined.**
   Reader has to guess "tie" / "loss". Add to caption: "t = tie within ±0.1
   cycle, L = loss by ≤0.9 cycle."

5. **"Pooled" Spearman in §IV is a weak choice of statistic.** Line 213 pools
   28 (workload, K, N, b) cells. But four of seven workloads each contribute
   four cells, so the points are not independent. Mention that the rank
   correlation is on per-cell observations (which are not iid) and that the
   primary message is the stratification, not the global ρ.

6. **Figure 4 caption mentions ρ=0.74 (Line 346)** while text mentions 0.83
   and 0.825. Either it is a stale leftover or it is a Pearson-vs-Spearman /
   subset-vs-pool difference; either way it must be reconciled.

7. **Limitations (vi) ends with "future work" three times.** ii, iv, vi all
   say "we treat X as future work" — pick one and vary the others ("we leave
   to" / "remains open" / "is outside scope").

## Logic Issues

1. **Greedy mean number disagrees: Table 6 Overall = +24.8%, Abstract +
   C3 + Conclusion = +25.6%.** Line 31 (Abstract): "exceeding both the
   workload-aware greedy heuristic (+25.6%)". Line 57 (C3): "35.6% mean...
   (versus 25.6% for greedy alone)". Line 338 (Table 6): "Overall ... +24.8%".
   Line 445 (Conclusion): "exceeding both greedy (25.6%)". Either Table 6
   needs to be recomputed or the three text mentions need to drop to 24.8%.

2. **"24/28 strict, 2 ties, 2 within noise" vs "24/28 strict, 2 ties, 2 minor
   losses".** Line 31 (Abstract): "ties on 2, and stays within simulation
   noise on the remaining 2". Line 370 (Per-Cell): "2 are ties within ±0.1
   cycle and 2 are minor losses by ≤0.9 cycle". A loss by 0.9 cycles is not
   the same as "within simulation noise" — a careful reviewer will read these
   as contradictory. Pick honest language: replace the Abstract phrase with
   "ties on 2 and loses by ≤0.9 cycle on 2".

3. **Spearman ρ value triple-discrepancy.** Line 31: ρ=0.83. Line 55: ρ=0.83.
   Line 214: ρ=0.825. Line 346 caption: ρ=0.74. Line 445: ρ=0.83. The 0.74
   in the figure caption is the most damaging because the figure is the
   evidence — readers will trust the figure and discount the text. Decide
   on one number and align all five sites.

4. **Per-Cell Analysis claims three cells "drive most of the −11.8% overall
   reduction"**, but only enumerates three of the four MoE cells (Line 363):
   K=32 N=8 (-83.2%), K=32 N=4 (-84.5%), K=16 N=8 (-72.6%). The fourth MoE
   cell (K=16, N=4) is silently omitted, even though MoE wins 4/4 in Table 6.
   Either include it for completeness or explain why it is excluded (e.g.
   "the fourth MoE cell K=16, N=4 also wins but with a smaller margin of
   X%"). As written, the omission looks selective.

5. **"NL% predicts saving with ρ=0.83" vs "the correlation is stable under
   method substitution".** Line 214: replacing RL-WS with greedy "yields a
   similar rank ordering". This argument cuts against the paper's other
   thesis: that NL% predicts the *RL-WS-over-FBfly margin*. If NL% predicts
   raw saving for any method, why is the deployment-classifier story
   specifically about RL vs FBfly? Be explicit: NL% predicts raw saving for
   any method (universal predictor), AND additionally, NL% predicts the
   FBfly→RL-WS uplift (deployment-classifier). These are two distinct
   correlations.

6. **§IV Line 214: "with a mean latency reduction of -19.0%"** for high-NL
   cells. §VII Conclusion Line 445: "with a mean reduction of -19.0% in
   latency". Where is this number computed in the paper? Table 6's
   per-workload "vs FBfly" column averaged across the four high-NL rows is
   (-63.1 -4.2 -3.9 -4.8)/4 = -19.0%. OK, this is correct, but please add
   a one-line breadcrumb in §VI-B: "Averaging the high-NL rows of the
   `vs FBfly` column in Table 6 gives the -19.0% number quoted in the
   Abstract."

7. **C2 (Line 56) claims FBfly "beats greedy on most high-NL cells",** but
   Table 6 row for MoE Skewed shows greedy = +61.0% and FBfly = +40.5% —
   greedy beats FBfly on the most extreme high-NL workload. The claim is
   only true for All-to-all, Uniform Random, and Hybrid TP+PP (3 of 4
   high-NL workloads). Soften to "beats greedy on near-uniform high-NL
   workloads" or "beats greedy on 3 of 4 high-NL workload rows".

8. **Limitations (ii) says "we do not report per-cell BookSim variance over
   independent end-to-end RL re-runs"** but the entire RL-WS pipeline
   already uses 16 seeds internally, with the BookSim-best of 48 selected.
   The variance the reviewer would want is the variance of *that selection
   process* — i.e., does running the 16-seed pipeline twice give the same
   final allocation? Be specific: "We run the 16-seed multi-warm-start
   pipeline once per cell and select the BookSim-best; we do not repeat
   the entire 16-seed pipeline multiple times to report variance over
   independent end-to-end re-runs."

## Line-by-line Suggestions

- **Line 29 (Abstract opener):** "We argue that a single static workload
  property---the *non-locality fraction* (NL\%, the share of traffic volume
  between non-adjacent chiplet pairs)---predicts both how much express links
  help a chiplet network-on-interposer (NoI) and when learned placement is
  worth invoking over a strong topology-aware heuristic."
  → Tighten: **"A single static workload statistic---the non-locality fraction
  (NL\%)---predicts both how much express links help a chiplet
  network-on-interposer (NoI) and when learned placement is worth invoking
  over a strong topology-aware heuristic."**
  The parenthetical definition is ~25 words and dilutes the thesis sentence;
  push the definition to the second sentence.

- **Line 31:** "exceeding both the workload-aware greedy heuristic (+25.6%)"
  → fix the number to match Table 6: **"exceeding both the workload-aware
  greedy heuristic (+24.8%) and a Flattened-Butterfly..."**

- **Line 31:** "ties on 2, and stays within simulation noise on the remaining 2"
  → **"ties on 2 and loses by ≤0.9 cycle on 2."**

- **Line 47:** "We prove that center links in a $K$-chiplet square grid carry
  $\Theta(K^{3/2})$ times more traffic than their direct demand."
  → "their direct demand" is fuzzy. Replace with: **"...carry traffic that
  scales as $\Theta(K^{3/2})$ relative to the direct chiplet-pair demand under
  uniform all-to-all routing."**

- **Line 49:** "Recent learning-based NoI synthesis~\cite{parl} trains
  reinforcement learning from scratch on a multi-objective interference score,
  but without a workload-level predictor for *when* learned placement actually
  beats a topology-aware regular allocator."
  → Drop "actually": **"...but without a workload-level predictor for when
  learned placement beats a topology-aware regular allocator."**

- **Line 56 (C2):** "FBfly is the strongest no-RL baseline in our evaluation,
  beating greedy on most high-NL cells precisely because regular row/column
  placement matches the symmetric phantom-load pattern."
  → Factually slightly off (greedy beats FBfly on MoE). Suggest:
  **"FBfly is the strongest workload-blind baseline in our evaluation: on
  near-uniform high-NL workloads (All-to-all, Uniform Random, Hybrid TP+PP)
  its row/column regularity matches the symmetric phantom-load pattern and
  beats greedy; on skewed high-NL workloads (MoE) workload-aware greedy is
  stronger, motivating the dual warm-start in C3."**
  This also pre-justifies dual warm-start.

- **Line 213 §IV:** "Pooling all 28 workload-configuration cells (7 workloads
  × {K=16,32} × {N=4,8}, primarily at b=4×), the Spearman rank correlation
  between NL\% and RL-WS saving versus adjacent-uniform is $\rho=0.825$"
  → Match the abstract: **$\rho=0.83$**, and add a parenthetical:
  **"(per-cell observations; not independent across the four (K,N,b) cells
  of each workload)."**

- **Line 214:** "with a mean latency reduction of $-19.0\%$ (16/16 wins)"
  → Add traceability: **"...with a mean latency reduction of $-19.0\%$
  averaged over the four high-NL rows of Table~\ref{tab:main_result}'s
  `vs FBfly` column (16/16 cells strictly win)."**

- **Line 256 §V-C "Rate-aware surrogate":** "trained on 1408 BookSim
  samples that span all evaluated $(\text{workload}, K, N, b)$ cells."
  → Reviewers will spot this as a generalization concern.
  Add: **"The surrogate's training corpus and the evaluation grid overlap
  by construction (the surrogate is fit per task, not transferred across
  workloads); the role of the surrogate is to amortize REINFORCE rollout
  cost, not to demonstrate cross-workload generalization."**

- **Line 297 §VI-A:** "16 random seeds (8 greedy-warm-start + 8 FBfly-warm-start)"
  → The phrase "random seeds" is misleading because the warm-start type is
  deterministic (greedy vs FBfly), not seeded. Replace with:
  **"16 independent REINFORCE runs (each with a distinct random seed): 8
  initialized from greedy, 8 from FBfly."**

- **Line 309 §VI-A "Low-budget regime":** "we observe a *crossover*: below
  roughly 3×, express placement may tie or slightly trail adjacent-uniform"
  → This is a claim about the b=2× behavior but the only b=2× cell in the
  main result is Tree (K=32, N=8). Be specific: **"we observe a crossover
  on the b=2× Tree K=32, N=8 cell, where express placement trails adjacent-
  uniform; we keep this cell in the evaluation..."**

- **Line 346 (Fig. 4 caption):** "Pooled Spearman $\rho(\mathrm{NL\%},
  \text{RL-WS saving})=0.74$."
  → Reconcile with text: **"Pooled Spearman $\rho=0.83$ (see §IV)."**

- **Line 363 (Per-Cell):** Three MoE cells are listed.
  → Add the fourth: **"\item \textbf{MoE Skewed, $K{=}16$, $N{=}4$,
  $b{=}4\times$}: X.X vs Y.Y cycles ($-Z\%$). Smaller absolute margin
  because per-pair cap is tighter."** (Insert real numbers from results.)

- **Line 370:** "stochasticity of REINFORCE+surrogate"
  → "stochasticity" is informal here. **"variance of the REINFORCE policy
  + surrogate selection pipeline"**.

- **Line 397 Discussion opener:** "If NL\%≤50\%, express links are unlikely
  to pay off relative to a topology-aware regular allocator (FBfly)"
  → This contradicts Table 6: Ring AllReduce (NL=13%) shows RL-WS = +22.8%
  saving, FBfly = +20.3% — both clearly pay off. The honest claim is that
  *the FBfly→RL-WS gap* is small at low NL%, not that express links don't
  help. Replace with: **"If NL\%≤50\%, the FBfly-vs-RL-WS gap is within
  simulation noise and a topology-aware regular allocator captures most of
  the available saving; learned-placement effort is hard to justify."**

- **Line 439 (Limitations) ii:** Rewrite per Logic Issue #8.

- **Line 445 (Conclusion):** "exceeding both greedy (25.6\%) and FBfly (27.1\%)"
  → Match Table 6: **"exceeding both greedy (24.8\%) and FBfly (27.1\%)"**.

- **Bibliography:** entries `modular_routing` (Line 464), `chiplet_actuary`
  (470), `catch` (473), `cpelide` (476), `cnsim` (480) are never cited in
  the body. Either cite them or remove them.

## Strengths

1. **The "Predict / Place / Refine" triptych is rhetorically excellent.**
   It maps cleanly onto C1/C2/C3 and gives reviewers a single mental model
   to retain. The Conclusion (Line 445) ends with an actionable workflow,
   which is rare in architecture papers.

2. **NL% as a "deployment classifier" is a strong contribution framing.**
   It is more falsifiable than "predictor" (which is just correlation) and
   it gives the paper a non-trivial recommendation (don't run RL when
   NL%≤50%) that is operationally useful.

3. **The MoE K=32, N=8 headline (-83.2% latency vs FBfly, 67.8 vs 402.8
   cycles)** is a memorable win that anchors the abstract and figures.
   The drill-down in §VI-B Per-Cell Analysis correctly identifies the
   mechanism (FBfly under-provisions skewed pairs).

4. **FBfly as the strongest deterministic baseline gives the comparison
   real teeth.** Without FBfly, "RL beats greedy" would be a weak claim;
   with FBfly, "RL beats both regular topology-aware allocation AND
   workload-aware greedy" is a real result.

5. **§VII λ sensitivity (Table 8) is exactly the right kind of robustness
   check.** The result that the RL uplift *grows* under higher λ on
   high-NL workloads (Line 408) is rhetorically stronger than the safer
   "savings persist" framing. Good move.

6. **Limitations are concrete and honest** (synthetic workloads, no
   adaptive routing, no SPICE-level wire model, 2.5D scope). Limitation
   (iii) on PARL is appropriately humble — explicit acknowledgment that
   PARL targets a different problem rather than a hand-wave.

7. **§III Phantom Load Analysis closed-form bound + empirical Table 3
   (routing-algorithm independence)** is a nice rigor anchor that grounds
   the rest of the paper. The point that "phantom load is a structural
   consequence of multi-hop adjacency, not an artifact of one routing
   algorithm" (Line 199) is well-defended.
