#!/bin/bash
set -e
cd "$(dirname "$0")"
PY=".venv/bin/python3"
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1

# Focus on 6 failing cells (same as SA)
for wl in tree_allreduce hybrid_tp_pp; do
    nohup "$PY" -u run_cem.py "$wl" 16 4 4 > cem_${wl}_k16n4_b4.log 2>&1 &
done
nohup "$PY" -u run_cem.py tree_allreduce 32 4 4 > cem_tree_allreduce_k32n4_b4.log 2>&1 &
nohup "$PY" -u run_cem.py tree_allreduce 32 8 2 > cem_tree_allreduce_k32n8_b2.log 2>&1 &
nohup "$PY" -u run_cem.py pipeline_parallel 16 4 4 > cem_pipeline_parallel_k16n4_b4.log 2>&1 &
nohup "$PY" -u run_cem.py ring_allreduce 16 4 4 > cem_ring_allreduce_k16n4_b4.log 2>&1 &

echo "Launched $(jobs -r | wc -l) CEM cells"
wait
echo "done"
