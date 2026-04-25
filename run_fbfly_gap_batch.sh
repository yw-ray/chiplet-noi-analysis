#!/bin/bash
# Fill FBfly measurements at all K/N × bpp gaps
set -e
cd "$(dirname "$0")"
PY=".venv/bin/python3"
export OMP_NUM_THREADS=1

# K16N4 × bpp {2,3,4} × 4 workloads = 12
for wl in tree_allreduce hybrid_tp_pp uniform_random moe; do
    for bpp in 2 3 4; do
        nohup "$PY" -u fbfly_gap_cell.py "$wl" 16 4 "$bpp" > "fbg_${wl}_k16n4_b${bpp}.log" 2>&1 &
    done
done
# K16N8 × bpp {2,4,7} × 4 = 12
for wl in tree_allreduce hybrid_tp_pp uniform_random moe; do
    for bpp in 2 4 7; do
        nohup "$PY" -u fbfly_gap_cell.py "$wl" 16 8 "$bpp" > "fbg_${wl}_k16n8_b${bpp}.log" 2>&1 &
    done
done
# K32N4 × bpp {2,4} × 4 = 8
for wl in tree_allreduce hybrid_tp_pp uniform_random moe; do
    for bpp in 2 4; do
        nohup "$PY" -u fbfly_gap_cell.py "$wl" 32 4 "$bpp" > "fbg_${wl}_k32n4_b${bpp}.log" 2>&1 &
    done
done

echo "Launched $(jobs -r | wc -l) FBfly gap cells"
wait
echo "Done"
