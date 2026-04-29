#!/bin/bash
# Adj-only RL on 4 high-NL cells at K=32 N=8 b=4×
set -e
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1

cd /home/youngwoo.jeong/grepo/research/projects/chiplet-noi-analysis

VENV=/home/youngwoo.jeong/grepo/research/projects/chiplet-noi-analysis/.venv/bin/python3

for WL in moe hybrid_tp_pp uniform_random all_to_all; do
    echo "=== $WL K=32 N=8 b=4× ==="
    $VENV run_rl_adj_only.py $WL 32 8 4 2>&1
done

echo "=== ALL DONE ==="
