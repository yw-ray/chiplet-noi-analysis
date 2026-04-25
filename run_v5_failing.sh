#!/bin/bash
# Run v5 on the 4 cells where v4 lost to FBfly by +0.3-0.7 cycle
set -e
cd "$(dirname "$0")"
PY=".venv/bin/python3"
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1

# Main failing cells
nohup "$PY" -u run_rl_v5.py tree_allreduce 32 4 4 > v5_tree_allreduce_k32n4_b4.log 2>&1 &
nohup "$PY" -u run_rl_v5.py tree_allreduce 32 8 2 > v5_tree_allreduce_k32n8_b2.log 2>&1 &
# Generalization failing cells
nohup "$PY" -u run_rl_v5.py pipeline_parallel 16 4 4 > v5_pipeline_parallel_k16n4_b4.log 2>&1 &
nohup "$PY" -u run_rl_v5.py ring_allreduce 16 4 4 > v5_ring_allreduce_k16n4_b4.log 2>&1 &

echo "Launched $(jobs -r | wc -l) v5 failing cells"
wait
echo "All v5 done"
