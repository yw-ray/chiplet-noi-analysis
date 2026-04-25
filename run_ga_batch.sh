#!/bin/bash
set -e
cd "$(dirname "$0")"
PY=".venv/bin/python3"
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1

# 16 main cells
for wl in tree_allreduce hybrid_tp_pp uniform_random moe; do
    nohup "$PY" -u run_ga.py "$wl" 16 4 4 > ga_${wl}_k16n4_b4.log 2>&1 &
    nohup "$PY" -u run_ga.py "$wl" 16 8 4 > ga_${wl}_k16n8_b4.log 2>&1 &
    nohup "$PY" -u run_ga.py "$wl" 32 4 4 > ga_${wl}_k32n4_b4.log 2>&1 &
done
nohup "$PY" -u run_ga.py tree_allreduce 32 8 2 > ga_tree_allreduce_k32n8_b2.log 2>&1 &
for wl in hybrid_tp_pp uniform_random moe; do
    nohup "$PY" -u run_ga.py "$wl" 32 8 4 > ga_${wl}_k32n8_b4.log 2>&1 &
done
# 12 generalization cells
for wl in ring_allreduce pipeline_parallel all_to_all; do
    nohup "$PY" -u run_ga.py "$wl" 16 4 4 > ga_${wl}_k16n4_b4.log 2>&1 &
    nohup "$PY" -u run_ga.py "$wl" 16 8 4 > ga_${wl}_k16n8_b4.log 2>&1 &
    nohup "$PY" -u run_ga.py "$wl" 32 4 4 > ga_${wl}_k32n4_b4.log 2>&1 &
    nohup "$PY" -u run_ga.py "$wl" 32 8 4 > ga_${wl}_k32n8_b4.log 2>&1 &
done

echo "Launched $(jobs -r | wc -l) GA cells"
wait
echo "All done"
