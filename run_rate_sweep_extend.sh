#!/bin/bash
# Launch rate_sweep for missing K/N combinations (K16N4, K16N8, K32N4)
# Uses best bpp per cell to match existing K32N8 runs.
set -e
cd "$(dirname "$0")"

PY=".venv/bin/python3"

# K16N4: bpp=4 (max for N=4)
for wl in tree_allreduce hybrid_tp_pp uniform_random moe; do
    nohup "$PY" -u rate_sweep_cell.py "$wl" 16 4 4 > "rate_${wl}_k16n4_b4.log" 2>&1 &
done

# K16N8: bpp=4 (midpoint; bpp=7 takes too long in some configs)
for wl in tree_allreduce hybrid_tp_pp uniform_random moe; do
    nohup "$PY" -u rate_sweep_cell.py "$wl" 16 8 4 > "rate_${wl}_k16n8_b4.log" 2>&1 &
done

# K32N4: bpp=4
for wl in tree_allreduce hybrid_tp_pp uniform_random moe; do
    nohup "$PY" -u rate_sweep_cell.py "$wl" 32 4 4 > "rate_${wl}_k32n4_b4.log" 2>&1 &
done

echo "Launched $(jobs -r | wc -l) rate-sweep cells"
wait
echo "All rate-sweep cells finished"
