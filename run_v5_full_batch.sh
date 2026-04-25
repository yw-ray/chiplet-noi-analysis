#!/bin/bash
# v5 algorithm on ALL 28 cells (16 main + 12 generalization)
set -e
cd "$(dirname "$0")"
PY=".venv/bin/python3"
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1

# Main 16 cells (skip ones already in rl_v5.json)
for wl in tree_allreduce hybrid_tp_pp uniform_random moe; do
    nohup "$PY" -u run_rl_v5.py "$wl" 16 4 4 > v5full_${wl}_k16n4_b4.log 2>&1 &
    nohup "$PY" -u run_rl_v5.py "$wl" 16 8 4 > v5full_${wl}_k16n8_b4.log 2>&1 &
    nohup "$PY" -u run_rl_v5.py "$wl" 32 4 4 > v5full_${wl}_k32n4_b4.log 2>&1 &
done
nohup "$PY" -u run_rl_v5.py tree_allreduce 32 8 2 > v5full_tree_allreduce_k32n8_b2.log 2>&1 &
for wl in hybrid_tp_pp uniform_random moe; do
    nohup "$PY" -u run_rl_v5.py "$wl" 32 8 4 > v5full_${wl}_k32n8_b4.log 2>&1 &
done

# Generalization 12 cells
for wl in ring_allreduce pipeline_parallel all_to_all; do
    nohup "$PY" -u run_rl_v5.py "$wl" 16 4 4 > v5full_${wl}_k16n4_b4.log 2>&1 &
    nohup "$PY" -u run_rl_v5.py "$wl" 16 8 4 > v5full_${wl}_k16n8_b4.log 2>&1 &
    nohup "$PY" -u run_rl_v5.py "$wl" 32 4 4 > v5full_${wl}_k32n4_b4.log 2>&1 &
    nohup "$PY" -u run_rl_v5.py "$wl" 32 8 4 > v5full_${wl}_k32n8_b4.log 2>&1 &
done

echo "Launched $(jobs -r | wc -l) v5_full cells"
wait
echo "All v5_full cells finished"
