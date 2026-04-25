#!/bin/bash
set -e
cd "$(dirname "$0")"
PY=".venv/bin/python3"
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1

# Focus on 4 failing cells (tree K16N4, hybrid K16N4, tree K32N4, tree K32N8 b2, pipeline K16N4, ring K16N4)
# + verification on other cells
for wl in tree_allreduce hybrid_tp_pp; do
    nohup "$PY" -u run_sa.py "$wl" 16 4 4 > sa_${wl}_k16n4_b4.log 2>&1 &
done
nohup "$PY" -u run_sa.py tree_allreduce 32 4 4 > sa_tree_allreduce_k32n4_b4.log 2>&1 &
nohup "$PY" -u run_sa.py tree_allreduce 32 8 2 > sa_tree_allreduce_k32n8_b2.log 2>&1 &
nohup "$PY" -u run_sa.py pipeline_parallel 16 4 4 > sa_pipeline_parallel_k16n4_b4.log 2>&1 &
nohup "$PY" -u run_sa.py ring_allreduce 16 4 4 > sa_ring_allreduce_k16n4_b4.log 2>&1 &

echo "Launched $(jobs -r | wc -l) SA cells"
wait
echo "done"
