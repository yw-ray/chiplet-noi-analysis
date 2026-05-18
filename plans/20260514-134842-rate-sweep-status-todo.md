# V3 Sweep + Rate Sweep Status & TODO

Date: 2026-05-14 13:48 KST

## Context

Paper: "Workload-Aware Multi-Workload Express Link Superset with Per-Workload Masking" (chiplet NoI).
Two parallel experiment tracks running:

1. **v3 sweep** (single-rate, broad WL coverage)
   - For each of 4 cells: 50 WL combos (C(6,2)+C(6,3)+C(6,4))
   - Per combo: backbone selection (Stage 1) + per-workload mask (Stage 2) + 5 baselines
   - Single injection rate = 0.005 (saturated regime, normalized to K16_N4 baseline)
2. **rate sweep** (latency-vs-rate curves, narrow combo coverage)
   - 4 cells × 2 representative combos × 7 rates × 6 alloc (ours + 5 baselines)
   - Used masked allocs from existing v3 / backup JSONs
   - Total ≈ 966 BookSim jobs

## Status (as of 2026-05-14 13:48)

### v3 sweep — saturated regime (rate=0.005)

| Cell | Combos Done | Active PID | Notes |
|---|---|---|---|
| K16_N4 | **50/50 ✓** | (already done 5/12) | preserved |
| K16_N8 | 2/50 | 1568720 (13.8h elapsed) | combo2 just done; slow at saturated regime |
| K32_N4 | 3/50 | 1568721 (1h27m elapsed) | combo4 in flight |
| K32_N8 | 0/50 | 1669888 (6.5min elapsed) | restarted after kill+revive; combo1 in flight |

JSON outputs (`results/ml_placement/`):
- `sweep_v3_isowire_seedinject_v3_K16_N4.json` (1.4MB, 50/50, low-rate originally — preserved)
- `sweep_v3_isowire_seedinject_v3_K16_N8.json` (55KB, 2/50)
- `sweep_v3_isowire_seedinject_v3_K32_N4.json` (124KB, 3/50)
- (`sweep_v3_isowire_seedinject_v3_K32_N8.json` — will be created when first combo done)
- `backup_lowload_v3/` — old low-rate partial results (K16_N8: 31, K32_N4: 40, K32_N8: 12 combos)

### Rate sweep — multi-rate single-combo

`results/ml_placement/rate_sweep_v3.json` — **946/966 (98%)**, last 20 jobs are K32_N8.

| Cell | Combos covered | Entries |
|---|---|---|
| K16_N4 | 3 (moe+ep, tree+unif, moe+unif+ep) | 294 ✓ |
| K16_N8 | 2 (moe+ep, hybr+fsdp) | 168 ✓ |
| K32_N4 | 3 (moe+unif, moe+unif+ep, tree+unif+ep) | 336 ✓ |
| K32_N8 | 2 (moe+ep, hybr+ep) | 116 (partial, 20 jobs remaining) |

Rates evaluated: `{0.001, 0.002, 0.003, 0.005, 0.008, 0.012, 0.018}`

## Key Findings (so far)

### Saturation knee comparison (K16_N4 moe+ep)

| Alloc | WL | Sat knee rate | Lat@knee |
|---|---|---|---|
| mesh | moe | 0.003 | 210 |
| mesh | ep | 0.002 | 198 |
| kite_l | moe | 0.005 | 205 |
| kite_l | ep | 0.005 | 391 |
| **ours** | **moe** | **0.008** | 367 |
| **ours** | **ep** | **0.005** | 260 |

→ **ours saturates at 2.7× higher rate than mesh for MoE** (textbook NoC latency-rate curve)

### K16_N4 single-rate sweep (50/50)

- 81% combo win rate (geomean vs best-of-5 baselines)
- 100% per-WL win vs kite_l on MoE/EP (25/25, 22/22)
- Headline: 2.05× speedup (moe+ep), 1.94× (moe+hybr)

### Mask saving by WL (133 mask events, partial data)

- **moe**: mean 21.9% saving (max 80.9%, 54% have >10%)
- **ep_all_to_all**: mean 19.9% (max 66.5%, 60% >10%)
- uniform_random: mean 6.4% (mostly 0)
- hybrid_tp_pp: mean 4.0%
- fsdp: mean 3.9%
- tree_allreduce: **0%** (never saves) — fail-safe property

### N=4 vs N=8 mechanism difference

- **N=4 (latency-bound)**: ours shifts saturation knee 2-3× higher → throughput improvement
- **N=8 (throughput-bound)**: ours gives 6× lower zero-load latency but similar saturation rate → latency improvement

### K32_N8 = worst-case cell

- baselines saturated even at rate=0.001 (kite_m moe@0.001 = 314 cycles)
- "Next-gen chiplet" motivation: framework value most visible here

## Critical Bugs Fixed Today

1. **rate_sweep traffic file race condition**: workers writing same traffic file for different rates → corrupted data. Fixed by including rate in filename.
2. **rate_sweep `imap_unordered` ordering bug**: results getting matched to wrong job keys. Fixed by passing key in worker payload.
3. (Earlier) Server reboot killed all sweeps mid-run; backups in `backup_lowload_v3/`.

## TODO

### Immediate (next 1-3 hours)

- [ ] Wait for rate sweep completion (last 20 K32_N8 jobs, ~5-30 min)
- [ ] Sanity check completed rate sweep JSON (monotonicity per (alloc, wl) curve)
- [ ] Generate paper Figure: latency-vs-rate curves
  - 4 panels (one per cell)
  - X: injection rate (log scale 0.001-0.018)
  - Y: latency (linear, 0-500)
  - Lines: mesh, kite_l, gia, **ours_mask**
  - Annotations: saturation knee, X× throughput improvement

### Short-term (today/tomorrow)

- [ ] Let v3 sweep continue → K32_N4 should reach 5-10/50 in a few hours
- [ ] Generate paper Table: per-WL mask saving stats (mean/median/max by WL)
- [ ] Generate paper Table: per-cell win rate vs baselines
- [ ] Re-examine current Fig 1 (intro_motivation) — orthogonal to rate curve, both needed
- [ ] Update paper text: clarify N=4 vs N=8 mechanism difference (throughput shift vs latency reduction)
- [ ] Address "scope" honestly: K16_N4 strong, K16_N8 marginal, K32_N4 mixed, K32_N8 forward-looking

### Medium-term (this week)

- [ ] Generate per-WL mask saving figure (NL% scatter vs saving%)
- [ ] EDP analysis (`analyze_power_v2.py`) — power × latency main metric
- [ ] Decide which K16_N4 50/50 to report: low-rate (current JSON, 5/12) or saturated (would require re-run)
- [ ] V3 sweep partial reporting strategy: K32_N4 ~10/50 by end of run, K16_N8/K32_N8 even less
- [ ] Wire-area + cycle cost table (per cell × stage)

### Open questions / decisions

- **Single-rate evaluation** (currently 0.005 saturated for v3 sweep): is this the right operating point? Rate sweep shows behavior varies. Consider reporting at 2-3 representative rates.
- **K32_N8 v3 sweep**: 50/50 unrealistic given pace (1 combo / many hours at saturated). Plan for partial (5-10 combos) + footnote.
- **Backup low-rate JSONs**: include partial low-rate data in paper as "low-injection regime baseline" or discard?
- **K=32 mesh strength**: mesh in K32_N4 has 208 adj links → competitive on some workloads. Honest reporting needed.

## File Index

- `sweep_v3_seedinject.py` — v3 sweep driver (cell index arg: 0=K32_N8, 1=K16_N8, 2=K32_N4, 3=K16_N4)
- `sweep_v3_isowire.py` — cell + workload config (CELLS list, SUBSETS)
- `sweep_v2_mask_greedy.py` — Stage 2 mask greedy (run_booksim_alloc has saturated rate=0.005 hardcoded)
- `rate_sweep_v3.py` — multi-rate evaluation driver
- `cost_perf_6panel_workload.py` — workload definitions (6 WLs incl. ep_all_to_all, fsdp)
- `noi_topology_synthesis.py` — BookSim runner + traffic matrix gen
- `backup_lowload_v3/` — pre-reboot data (low-rate, mixed completion)

## Process Management Notes

- 3 v3 sweep PIDs + 1 rate_sweep + 6 workers ≈ 10 Python processes
- BookSim children: 12-20 active depending on phase
- System load 22-30 (64-core system, safe)
- Each PID alive can be killed/restarted; v3 sweep supports resume from JSON
- If user wants to free resources: kill K32_N8 v3 sweep (slowest, lowest yield); K16_N8 also slow
