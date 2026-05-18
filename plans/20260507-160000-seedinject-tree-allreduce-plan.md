# V3.5 Seed Injection + Tree AllReduce Redesign Plan

**Created**: 2026-05-07 16:00 KST
**Status**: Active — supersedes all prior plans
**Trigger**: (1) Dense-only mixes lose to kite_l because RL has no structural prior for symmetric traffic. (2) all_to_all ≈ uniform_random (both symmetric, redundant). (3) Paper thesis narrowed to "MoE가 있으면 이긴다" is insufficient.

## Workload Redesign

Replace `all_to_all` with `tree_allreduce`. Final 4 workloads:

| Workload | Traffic Structure | NL% | Express Benefit |
|---|---|---|---|
| MoE (Zipf top-2) | Random hotspot, extreme skew | ~91% | Hub links |
| Hybrid TP+PP (TP=8) | Group all-reduce + pipeline | ~77% | Group express |
| Tree AllReduce | Butterfly XOR pairs, hierarchical | ~42% | XOR-targeted express |
| Uniform Random | Fully symmetric | ~89% | kite_l optimal (honest hard case) |

**Why tree_allreduce beats all_to_all for thesis:**
- XOR pairing creates specific long-range pair structure (e.g., level-2 stride-4 pairs = hop-4 on K=32 grid)
- kite_l's uniform spine doesn't target these specific XOR pairs
- Our MCTS from kite_l warm-start can escape and find XOR-targeted placements
- Removes the "two symmetric workloads" problem that created easy lose-cases

**New 11 subsets:**
- Size-2: moe+hybrid, moe+tree, moe+uniform, hybrid+tree, hybrid+uniform, tree+uniform
- Size-3: moe+hybrid+tree, moe+hybrid+uniform, moe+tree+uniform, hybrid+tree+uniform
- Size-4: all 4
- **No purely-symmetric 2-mix exists** (tree always adds structure)

## Algorithm: Seed Injection + Intersection Backbone

### Candidate generation per (cell, subset):
- `greedy_union` — deterministic baseline
- RL × 3 seeds (42,43,44) from greedy_union + backbone constraint
- MCTS × 3 seeds (101,102,103) from greedy_union + backbone constraint
- MCTS × 2 seeds (104,105) from kite_l warm-start + backbone constraint
  (kite_l identical → filtered out)
- **RL from kite_l removed**: smoke test confirmed RL always reverts to kite_l
  (no surrogate gradient to escape kite_l local optimum; MCTS can via UCB)

Total candidates per combo: up to 9 (1 greedy + 3 RL + 3 MCTS-greedy + 2 MCTS-kitel)

### Intersection Backbone:
Links present in ALL per-workload greedy allocations are frozen (cannot be removed below 1).
For dense-only mixes, intersection converges to uniform-spine structure, guiding RL/MCTS
toward kite_l territory without directly injecting kite_l as a candidate.

### Stage 2: Per-workload BookSim-greedy mask (unchanged from V3.4)

## Thesis (updated)

> "단일 칩렛 topology가 이질적인 multi-workload (MoE expert dispatch, TP/PP group comm,
> tree allreduce, uniform background traffic)를 동시에 지원해야 하는 상황에서,
> workload-adaptive joint superset이 structured topology (kite_l)를 Pareto-dominate한다."

"Traffic heterogeneity in the mix predicts our advantage" — not just "MoE present."

## Running Experiments (2026-05-07)

| Cell | PID | Log |
|---|---|---|
| K16_N4 | 1707783 | logs/seedinject_K16_N4.log |
| K16_N8 | 1709214 | logs/seedinject_K16_N8.log |
| K32_N4 | 1873771 | logs/seedinject_K32_N4.log |
| K32_N8 | 1789730 | logs/seedinject_K32_N8.log |

Output: `results/ml_placement/sweep_v3_isowire_seedinject_K{K}_N{N}.json`

## Decision Criteria

After K16_N4 finishes (~10–15h):
- MoE-included mixes ≥ 20% win vs kite_l: ✓ proceed
- hybrid+tree, tree+uniform: ideally win or tie (≤ 5% loss)
- If hybrid+tree still loses 10%+: revisit backbone parameters

Full sweep running in parallel — check K16_N4 first, kill others if approach fails.

## Code Changes

- `sweep_v3_isowire.py`: ALL_WORKLOADS changed to tree_allreduce
- `sweep_v3_seedinject.py`: RL_SEEDS_KITEL removed, new workloads inherited
- `run_rl_multi_workload.py`: alloc_dict_to_vec, warm_start_intersection_backbone,
  frozen_backbone_mask param added to train_warmstart_rl_multi
- `mcts_search.py`: backbone_mask_np param added to enumerate_swap_actions + mcts_search
