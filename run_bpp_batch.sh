#!/bin/bash
# Launch 20 bpp cells in parallel (K32N4 bpp=3, K32N8 bpp=3,5,6,7 for 4 workloads)
set -e
cd "$(dirname "$0")"

PY=".venv/bin/python3"

# K32N4: add bpp=3 for all 4 workloads (bpp max=4)
for wl in tree_allreduce hybrid_tp_pp uniform_random moe; do
    nohup "$PY" -u bpp_cell.py "$wl" 32 4 3 > "bpp_${wl}_k32n4_b3.log" 2>&1 &
done

# K32N8: add bpp=3,5,6,7 for all 4 workloads (bpp max=7)
for wl in tree_allreduce hybrid_tp_pp uniform_random moe; do
    for bpp in 3 5 6 7; do
        nohup "$PY" -u bpp_cell.py "$wl" 32 8 "$bpp" > "bpp_${wl}_k32n8_b${bpp}.log" 2>&1 &
    done
done

echo "Launched $(jobs -r | wc -l) parallel bpp cells"
wait
echo "All bpp cells finished"
