#!/bin/bash
# Expand SA + CEM to all 28 cells (b=4×). Skip already-done cells.
set -e
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
cd /home/youngwoo.jeong/grepo/research/projects/chiplet-noi-analysis

VENV=.venv/bin/python3

# 28 cells: 7 workloads × {K=16,32} × {N=4,8} × b=4×
WORKLOADS=(moe hybrid_tp_pp uniform_random all_to_all tree_allreduce ring_allreduce pipeline_parallel)

for K in 16 32; do
  for N in 4 8; do
    for WL in "${WORKLOADS[@]}"; do
      # SA
      echo "=== SA $WL K$K N$N b4 ==="
      $VENV run_sa.py "$WL" "$K" "$N" 4 2>&1 | tail -5
      # CEM
      echo "=== CEM $WL K$K N$N b4 ==="
      $VENV run_cem.py "$WL" "$K" "$N" 4 2>&1 | tail -5
    done
  done
done

echo "=== ALL DONE ==="
