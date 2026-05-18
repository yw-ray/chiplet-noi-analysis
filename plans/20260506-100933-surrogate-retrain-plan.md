# V3.4 Plan: SurrogateV3 Retraining for Better OOD on Joint Multi-Workload

**Created**: 2026-05-06 10:09:33 KST
**Status**: Proposed (not started)
**Trigger**: User asked why "ours" loses on no-moe (dense-only) mixes such as
hyb+uni, hyb+a2a, uni+a2a, where Kite-L is near-optimal. Root cause analysis
shows the current rate-aware surrogate (`surrogate_predict_ra`) **does not see
the allocation pattern itself** — it consumes only aggregate features
(bpp, n_express_ratio, K, N, rate) plus per-pair traffic. Two allocations
with the same bpp but very different topologies (uniform spine vs. hub-spoke)
get the same prediction. This makes RL/MCTS unable to distinguish near-optimal
spine layouts from suboptimal hubs in dense symmetric workloads.

## Why this is the right fix

`SurrogateV3` already exists in `ml_express_warmstart.py`:

```python
class SurrogateV3(nn.Module):
    """v3 surrogate: [traffic_496, alloc_496, K/32, N/8, log_rate] = 995 dim."""
```

It accepts the *full allocation vector*, not just aggregate stats. But the
trained weights file (`results/ml_placement/surrogate_v3.pt`) does not exist.
The architecture is already wired up; we only need to train it.

## Data collection

Need (allocation, traffic, K, N, rate, lat) tuples from BookSim. Diversify
across:

- **Allocations**: random, greedy, kite_s/m/l, gia, mesh, RL outputs from
  current sweeps (~5 sources × varied wire budgets)
- **Workloads**: moe, hybrid_tp_pp, uniform_random, all_to_all, plus
  pipeline_parallel, ring_allreduce, tree_allreduce (low-NL regime so the
  surrogate learns the full distribution)
- **Cells**: K=16/32, N=4/8 (4 cells)
- **Wire budgets**: 60, 120, 240, 480, 520, 960, 1920, 2080, 4160 (8-9 W
  values)
- **Rate multipliers**: 1, 2, 3, 4

Target sample count: ~10,000 BookSim runs.

Cost: 10,000 × ~30s = ~83 h single-thread. Parallel 4-way: ~21 h. Acceptable.

Reuse existing data:

- All `sweep_v3_isowire_K*_N*.json` candidates × workload BookSim measurements
  are already collected. Each combo has 9 candidates × 4 workloads × measured
  latency. From 33 done combos that is ~1200 (alloc, traffic, lat) pairs
  available without any new BookSim runs.
- `sweep_v3_wire_scaling_K*_N*.json` adds another ~600 pairs.
- Pilot, retry, partial sweeps add ~500 more.
- Total free: ~2300 pairs — about 23% of the target.

So the new BookSim cost is closer to 7,500 runs ≈ 16 h parallel. ~1 day.

## Training

`SurrogateV3` is an MLP (995→512→512→256→64→1, ReLU + LayerNorm) outputting
log-latency. Train with:

- Loss: MSE on log(lat) (existing convention from V3 prediction code).
- Optimizer: Adam, lr=1e-4, weight_decay=1e-4.
- Train/val split: 90/10.
- Batch: 256, epochs: 100 with early stop on val MSE.
- Target val MSE on log(lat): < 0.05 (i.e. ~5% mean lat error).

Cost: ~1-3 hours on CPU (no GPU needed — small model).

## Validation against current data

Before re-running sweeps:

1. Load `surrogate_v3.pt`, run prediction on every (alloc, traffic) pair from
   `sweep_v3_isowire_K16_N4.json` candidate evaluation (those have measured
   `raw_per_wl`).
2. Compute prediction error vs measured BookSim. If mean abs % error <10%,
   surrogate quality is good. If >25%, retraining needed.
3. Specifically check error distribution by **workload**: dense-symmetric
   workloads (uni, a2a) vs asymmetric (moe). Current surrogate is weakest on
   uni/a2a — the new one should bring those into the same error band as moe.

Decision rule: proceed to sweep redo only if val MSE good AND per-workload
errors balanced.

## Re-run sweeps with new surrogate

Replace `surrogate_predict_ra` with `surrogate_predict_v3` in:

- `sweep_v3_isowire.py` (gen_candidates surrogate calls)
- `mcts_search.py` (`evaluate_state` calls surrogate_predict_ra; switch to v3)
- `run_rl_multi_workload.py` (surrogate_predict_ra in RL training loop)

Add a `SURROGATE_VARIANT` constant so the codebase can switch without code
edits.

Re-run all 4 cells × 11 subsets × 1 W (main sweep) + 4 cells × 6 W (wire
scaling). Total combos: 44 + 24 = 68.

Cost: K16 ~3 h/combo, K32 ~10 h/combo. 4-way parallel: ~3-4 days.

## Expected outcomes

If new surrogate is more accurate on dense workloads:

- **No-moe mixes (current weak point)**: ours should match Kite-L within 1-3%
  (currently +5-16%). Possibly small wins.
- **moe-included mixes**: continue dominating (current −20% to −58%); maybe
  marginal additional gains.
- **Wire scaling**: monotonic ours improvement across W; W=480 outlier
  removed.
- **MCTS selection rate**: probably increases — better surrogate → MCTS
  finds better trajectories more often.

If new surrogate is not significantly better (val error similar):

- The dense-symmetric "ceiling" is fundamental, not a surrogate issue.
- Document as paper limitation.

## Risk register

- **Data collection too expensive**: mitigate with reuse of existing 2300+
  pairs and parallelism.
- **Surrogate overfits to existing alloc distribution**: include random
  allocations to broaden coverage.
- **Retrained surrogate not better on dense workloads**: at that point fall
  back to BookSim-in-loop top-K verification (Plan C from previous round).
- **Sweep re-run too long**: prioritize K16 cells first, K32 N4, then K32_N8
  last.

## File deliverables

- `surrogate_train_v3.py` — new. Data collection + training script.
- `results/ml_placement/surrogate_v3_dataset.npz` — collected (alloc, traffic,
  lat) tuples.
- `results/ml_placement/surrogate_v3.pt` — trained weights.
- `surrogate_v3_validation.py` — new. Validates new surrogate against
  measured pairs from existing sweeps.
- Modifications to `mcts_search.py`, `run_rl_multi_workload.py`,
  `sweep_v3_isowire.py` to swap surrogate variant.
- `sweep_v3_isowire_v2.py` and `sweep_v3_wire_scaling_v2.py` (optional,
  separate output files to preserve current sweep results for ablation).

## Timeline

| Phase | Work | Time |
|---|---|---|
| 1 | Data collection (8k new BookSim runs) | ~1 day |
| 2 | Surrogate training + validation | ~3 h |
| 3 | If validation good: sweep re-run | ~3-4 days |
| 4 | If validation bad: fall back to Plan C (BookSim-in-loop top-K) | ~1-2 days |

Total: 4-6 days for end-to-end with successful surrogate.

## Decision criteria

After Phase 2 (validation):

- New surrogate val MSE on log(lat) < 0.05 AND per-workload errors balanced
  → proceed to sweep re-run.
- New surrogate not meaningfully better (val MSE ≥ current surrogate's MSE on
  the same eval set, or per-workload errors stay imbalanced) → switch to
  Plan C (BookSim-in-loop top-K).

## Migration from current sweep

Current cell0 K32_N8 sweep is still running and will not finish for ~5 days.
Two options:

1. **Let cell0 finish** with old surrogate, then re-run with new surrogate.
   Use both as ablation baseline ("v3.3 RA surrogate" vs "v3.4 V3 surrogate").
2. **Kill cell0**, immediately switch to surrogate retraining. Cell0 was the
   slowest anyway and gives the smallest paper-message contribution
   (only one extra cell).

Default: option 1. Cell0 result is "for free" since it is already running and
serves as baseline.
