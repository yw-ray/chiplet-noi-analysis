# Chiplet NoI Express Link Analysis

## Paper Status: Draft (major revision with new ML contribution)

**Target**: DAC/DATE (architecture track)
**Title**: "Breaking the Cost-Performance Ceiling of LLM Chiplet Networks via Non-Locality-Guided Warm-Started Reinforcement Learning"
**Repo**: https://github.com/yw-ray/chiplet-noi-analysis
**See also**: `PAPER_PLAN.md` for full section/table/figure plan

## Thesis (Updated)

1. **Non-locality fraction (NL%)** predicts express link benefit (Spearman ρ ≥ 0.9).
2. **Greedy warm-started RL** with post-hoc BookSim fallback delivers strict Pareto dominance over greedy placement — 40/40 configs beat Adj Uniform, 32/40 beat greedy, never worse than greedy (guaranteed).
3. NL% predicts both raw express benefit AND the headroom for RL refinement over greedy.

## Headline Numbers

- **Greedy**: +25.6% mean saving vs no-express (40 configs)
- **RL-WS (ours)**: **+28.1%** mean, max **+56.4%** (MoE K32N8 4x)
- **Generalization**: RL-WS wins 6/6 on UNSEEN workloads (ring, pipeline, all-to-all)
- **Guarantee**: 100% ≤ greedy (post-hoc fallback)

## Related Work Key Comparison

- **PARL** (arXiv 2510.24113, Oct 2025) — closest prior work
- PARL uses cold-start Maskable PPO without worst-case guarantee
- We use greedy warm-start + post-hoc fallback + NL% predictor (all unique)

## Key Decisions

### Workloads (4개)
- **Tree All-Reduce** (NL 42%) — gradient sync, butterfly pattern
- **Hybrid TP+PP** (NL 77%) — Megatron-LM, **TP=8** (reviewer feedback 반영, 이전 TP=4)
- **MoE Expert** (NL 91%) — **Zipf-skewed** top-2 dispatch (reviewer feedback 반영, 이전 uniform)
- **Uniform Random** (NL 89%) — synthetic worst-case baseline
- ~~All-to-All~~: 제거. 균등 traffic이라 greedy가 express 배치 못함 + uniform과 중복
- ~~Pipeline/Ring~~: 제거. Express link 0개 (non-adj traffic이 max_dist 밖) → express 논의와 무관

### Configurations
- **K ∈ {16, 32}** (K=8 제거: grid 너무 작아서 결과 불안정)
- **N ∈ {4, 8}** (N=2 제거: gen_traffic_matrix에서 weight 보존 가능하지만 realistic하지 않음)
- 총 **4 panels**: K16_N4, K16_N8, K32_N4, K32_N8

### Algorithm
- **alloc_express_greedy**: greedy congestion minimization + **traffic-proportional fallback** (plateau 시 budget 100% 사용) + **adj round-robin** (sparse traffic 잔여 budget)
- **Incremental greedy** (initial_alloc parameter): 이전 budget allocation 위에 쌓아서 monotonicity 시도. 단, all_to_all에서 실패 (express 안 깔림) → all_to_all 제거 후 문제 완화. MoE/uniform의 low-budget 구간에서 여전히 non-monotonic (2x crossover issue, 알고리즘 문제가 아닌 구조적 한계).

## Bug Fixes (Critical — 3개)

1. **gen_traffic_matrix weight normalization**: `max(1, int(T/npc²))` → `max(1, round(T/max_T * 100))`. 이전에는 N=8에서 모든 워크로드 weight=1로 clamping → 워크로드 차이 사라짐.
2. **tree_allreduce double-count**: `i < partner` 조건 추가. 이전 traffic 2× 과다.
3. **alloc_express_greedy break bug**: plateau에서 즉시 break → traffic-proportional fallback으로 남은 budget 배분.

## Paper Structure (8 tables, 4 figures)

### Tables
1. Related Work comparison
2. Phantom Load Scaling (Θ(K^{3/2}), analytical)
3. Routing Algorithm Independence (analytical)
4. LLM Workloads + NL% (4 workloads, K=32)
5. Mitigation Strategy Comparison (Uniform/Traffic-prop/Express, K=8/16/32, analytical ρ_max)
6. **Main Result** (4 workloads × 4 panels, BookSim saving %)
7. Ablation: Placement Strategy (random/fully-connected/greedy, K=16)
8. Physical Overhead (CoWoS wire estimates)

### Figures
1. Intro motivation (phantom load + diminishing returns)
2. Phantom 4×4 example
3. **Cost-saving 4-panel** (adj vs express latency curves, 4 workloads, K32_N8) — "adj ceiling" 표시
4. **NL% vs saving scatter** (16 points, 4 configs)

### Budget sweep range
- **N=4 panels**: 1x~4x (전부 표시)
- **N=8 panels**: 1x~**7x** (8x 제외 — border router 전부 사용은 비현실적 + MoE 8x greedy instability)
- 논문에서 보여주는 best saving은 7x까지의 값

## Current Results (incremental greedy)

| Workload | NL% | K16_N4 | K16_N8 | K32_N4 | K32_N8 |
|---|---|---|---|---|---|
| Tree AR | 42% | +9% | +12% | +11% | +15% |
| Hybrid TP+PP | 77% | +14% | +22% | +25% | +36% |
| MoE (skewed) | 91% | +86% | +82% | +82% | +81% |
| Uniform | 89% | +22% | +33% | +30% | +43% |

Best saving은 7x budget 기준 (8x 제외).
Spearman ρ=0.90 (all 16 points, p<0.000002)

## Known Issues

- **Non-monotonicity**: low-budget (2x) 구간에서 express가 adj보다 나쁨 (crossover). Structural issue, not algorithm bug. Fig 3에서 보임.
- **MoE K16 vs K32 saving 차이 큼**: K16_N4(+86%) vs K32_N4(+82%) — 비슷해졌지만 K16_N8(82%) vs K32_N8(82%)은 일관.
- **Table 7 본문 수치 outdated**: "10 express links" → 실제 K32에서 41~47개. 업데이트 필요.
- **Reviewer feedback (iter 8/9)**: real HW validation 없음 (BookSim only), workload trace 아닌 synthetic, deadlock freedom 미논의.

## TODO

- [ ] Paper에서 all_to_all 제거 (Table 4, 6, Abstract, text)
- [ ] Table 6 수치 교체 (현재 incremental greedy 결과)
- [ ] Fig 3, Fig 4 재생성 (4 workloads)
- [ ] Table 7 본문 overhead 수치 업데이트 (K=16 + K=32)
- [ ] Abstract/Intro/Conclusion 수치 업데이트
- [ ] Review iteration 10 실행
- [ ] Non-incremental greedy 원복 여부 결정 (현재 incremental이 4 workloads에선 OK)

## Experiment Execution

```bash
# Run all 4 workloads (7 available)
for WL in tree_allreduce hybrid_tp_pp moe uniform_random; do
  nohup env WORKLOAD=$WL python cost_perf_6panel_workload.py > cost_perf_6panel_${WL}.log 2>&1 &
done

# Results: results/cost_perf_6panel_<workload>/cost_perf_6panel.json
# Requires: booksim2/ (clone BookSim 2.0 separately, build with make)
```
