#!/bin/bash
# Run rate-aware RL on all 16 best-budget cells (4 workload × 4 K/N)
# for old vs new RL comparison at 4 injection rates.
set -e
cd "$(dirname "$0")"
PY=".venv/bin/python3"
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1

# Best bpp per K/N for each workload (from paper convention)
# K16N4: bpp=4 / K16N8: bpp=7 (or 4) / K32N4: bpp=4 / K32N8: bpp=4 (or 2 for tree)

# K16N4 b4
for wl in tree_allreduce hybrid_tp_pp uniform_random moe; do
    nohup "$PY" -u run_rate_aware_rl.py "$wl" 16 4 4 > "ra_${wl}_k16n4_b4.log" 2>&1 &
done
# K16N8 b4 (using bpp=4 for speed; bpp=7 can add later)
for wl in tree_allreduce hybrid_tp_pp moe; do
    nohup "$PY" -u run_rate_aware_rl.py "$wl" 16 8 4 > "ra_${wl}_k16n8_b4.log" 2>&1 &
done
# uniform K16N8 b4 already launched separately - skip duplicate

# K32N4 b4
for wl in tree_allreduce hybrid_tp_pp uniform_random moe; do
    nohup "$PY" -u run_rate_aware_rl.py "$wl" 32 4 4 > "ra_${wl}_k32n4_b4.log" 2>&1 &
done
# K32N8 b4 (tree uses b2, others b4)
nohup "$PY" -u run_rate_aware_rl.py tree_allreduce 32 8 2 > "ra_tree_allreduce_k32n8_b2.log" 2>&1 &
for wl in hybrid_tp_pp uniform_random moe; do
    nohup "$PY" -u run_rate_aware_rl.py "$wl" 32 8 4 > "ra_${wl}_k32n8_b4.log" 2>&1 &
done

echo "Launched $(jobs -r | wc -l) cells"
wait
echo "All cells finished"
