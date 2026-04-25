#!/bin/bash
# Run 16 cells with multi-seed rate-weighted RL v3
set -e
cd "$(dirname "$0")"
PY=".venv/bin/python3"
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1

# K16N4 b4
for wl in tree_allreduce hybrid_tp_pp uniform_random moe; do
    nohup "$PY" -u run_rl_v3.py "$wl" 16 4 4 > "v3_${wl}_k16n4_b4.log" 2>&1 &
done
# K16N8 b4
for wl in tree_allreduce hybrid_tp_pp uniform_random moe; do
    nohup "$PY" -u run_rl_v3.py "$wl" 16 8 4 > "v3_${wl}_k16n8_b4.log" 2>&1 &
done
# K32N4 b4
for wl in tree_allreduce hybrid_tp_pp uniform_random moe; do
    nohup "$PY" -u run_rl_v3.py "$wl" 32 4 4 > "v3_${wl}_k32n4_b4.log" 2>&1 &
done
# K32N8 (tree b2, others b4)
nohup "$PY" -u run_rl_v3.py tree_allreduce 32 8 2 > "v3_tree_allreduce_k32n8_b2.log" 2>&1 &
for wl in hybrid_tp_pp uniform_random moe; do
    nohup "$PY" -u run_rl_v3.py "$wl" 32 8 4 > "v3_${wl}_k32n8_b4.log" 2>&1 &
done

echo "Launched $(jobs -r | wc -l) cells (v3: 5-seed rate-weighted)"
wait
echo "All v3 cells finished"
