#!/bin/bash
# Run 16 cells with v4 (10-seed multi-warm-start + top-3 + entropy + 500 episodes)
set -e
cd "$(dirname "$0")"
PY=".venv/bin/python3"
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1

for wl in tree_allreduce hybrid_tp_pp uniform_random moe; do
    nohup "$PY" -u run_rl_v4.py "$wl" 16 4 4 > "v4_${wl}_k16n4_b4.log" 2>&1 &
done
for wl in tree_allreduce hybrid_tp_pp uniform_random moe; do
    nohup "$PY" -u run_rl_v4.py "$wl" 16 8 4 > "v4_${wl}_k16n8_b4.log" 2>&1 &
done
for wl in tree_allreduce hybrid_tp_pp uniform_random moe; do
    nohup "$PY" -u run_rl_v4.py "$wl" 32 4 4 > "v4_${wl}_k32n4_b4.log" 2>&1 &
done
nohup "$PY" -u run_rl_v4.py tree_allreduce 32 8 2 > "v4_tree_allreduce_k32n8_b2.log" 2>&1 &
for wl in hybrid_tp_pp uniform_random moe; do
    nohup "$PY" -u run_rl_v4.py "$wl" 32 8 4 > "v4_${wl}_k32n8_b4.log" 2>&1 &
done

echo "Launched $(jobs -r | wc -l) v4 cells"
wait
echo "All v4 cells finished"
