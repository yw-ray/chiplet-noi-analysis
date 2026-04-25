#!/bin/bash
# Run v4 method on 3 UNSEEN workloads at 4 K/N = 12 cells
# For generalization / zero-shot claim
set -e
cd "$(dirname "$0")"
PY=".venv/bin/python3"
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1

# Unseen workloads: ring_allreduce, pipeline_parallel, all_to_all
# Same K/N × bpp scheme as main v4 batch
for wl in ring_allreduce pipeline_parallel all_to_all; do
    nohup "$PY" -u run_rl_v4.py "$wl" 16 4 4 > "v4g_${wl}_k16n4_b4.log" 2>&1 &
    nohup "$PY" -u run_rl_v4.py "$wl" 16 8 4 > "v4g_${wl}_k16n8_b4.log" 2>&1 &
    nohup "$PY" -u run_rl_v4.py "$wl" 32 4 4 > "v4g_${wl}_k32n4_b4.log" 2>&1 &
    nohup "$PY" -u run_rl_v4.py "$wl" 32 8 4 > "v4g_${wl}_k32n8_b4.log" 2>&1 &
done

echo "Launched $(jobs -r | wc -l) v4-generalization cells"
wait
echo "All done"
