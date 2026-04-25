#!/bin/bash
set -e
cd "$(dirname "$0")"
PY=".venv/bin/python3"
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1

nohup "$PY" -u run_rl_v5_alt.py tree_allreduce 32 4 4 > v5alt_tree_allreduce_k32n4_b4.log 2>&1 &
nohup "$PY" -u run_rl_v5_alt.py tree_allreduce 32 8 2 > v5alt_tree_allreduce_k32n8_b2.log 2>&1 &
nohup "$PY" -u run_rl_v5_alt.py pipeline_parallel 16 4 4 > v5alt_pipeline_parallel_k16n4_b4.log 2>&1 &
nohup "$PY" -u run_rl_v5_alt.py ring_allreduce 16 4 4 > v5alt_ring_allreduce_k16n4_b4.log 2>&1 &

echo "Launched $(jobs -r | wc -l) v5-alt cells"
wait
echo "done"
