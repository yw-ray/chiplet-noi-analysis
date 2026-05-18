"""Generate K16_N4-only rate curve figure for paper review.

Shows latency vs injection rate for 3 representative combos × multiple workloads.
Truncate at rate=0.008 (just past saturation knee) to avoid post-saturation noise.
Emphasize "ours" line for clarity.
"""

import json
import math
from pathlib import Path
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np

plt.rcParams.update({
    'font.size': 8,
    'axes.titlesize': 9,
    'axes.labelsize': 8,
    'xtick.labelsize': 7,
    'ytick.labelsize': 7,
    'legend.fontsize': 7.5,
    'font.family': 'serif',
})

DATA_PATH = Path("results/ml_placement/rate_sweep_v3.json")
OUT_PATH = Path("paper/figures/fig_k16n4_rate_curves")

# Show only useful operating range; cut off past-saturation noise
RATE_MIN = 0.001
RATE_MAX = 0.008

# K16_N4 combos and the WLs to plot per combo
COMBOS_WLS = [
    ('moe+ep_all_to_all',                       ['moe', 'ep_all_to_all']),
    ('moe+uniform_random+ep_all_to_all',        ['moe', 'ep_all_to_all', 'uniform_random']),
    ('tree_allreduce+uniform_random',           ['tree_allreduce', 'uniform_random']),
]

# baselines lighter & thinner; ours dark red bold
ALLOC_STYLES = {
    'baseline_mesh':   {'color': '#9E9E9E', 'lw': 0.9, 'ls': '-',  'label': 'mesh',   'marker': 's', 'zorder': 2},
    'baseline_kite_l': {'color': '#64B5F6', 'lw': 0.9, 'ls': '-',  'label': 'kite_l', 'marker': '^', 'zorder': 2},
    'baseline_kite_m': {'color': '#90CAF9', 'lw': 0.7, 'ls': ':',  'label': 'kite_m', 'marker': 'v', 'zorder': 1},
    'baseline_gia':    {'color': '#FFB74D', 'lw': 0.8, 'ls': '--', 'label': 'gia',    'marker': 'D', 'zorder': 2},
    'ours_mask':       {'color': '#C62828', 'lw': 2.2, 'ls': '-',  'label': 'ours',   'marker': 'o', 'zorder': 10},
}


def load_data():
    d = json.loads(DATA_PATH.read_text())
    grouped = defaultdict(dict)
    for key, v in d.items():
        cell, combo, alloc, wl, rate_str = key.split('|')
        rate = float(rate_str)
        grouped[(cell, combo, alloc, wl)][rate] = v.get('latency')
    return grouped


def get_curve(grouped, cell, combo, alloc, wl):
    if alloc == 'ours_mask':
        alloc_key = f'ours_mask_{wl}'
    else:
        alloc_key = alloc
    rdict = grouped.get((cell, combo, alloc_key, wl), {})
    if not rdict:
        return None, None
    rates = sorted(rdict.keys())
    lats = [rdict[r] for r in rates]
    return rates, lats


def main():
    grouped = load_data()
    cell = 'K16_N4'

    # 3 columns (one per combo), each with N panels (one per WL in combo)
    # Total panels = 2 + 3 + 2 = 7
    # Use a 3-row layout: row 0 (combo1 — 2 WLs), row 1 (combo2 — 3 WLs), row 2 (combo3 — 2 WLs)
    # Make this into a 3 row × 3 col grid; some cells empty

    fig, axes = plt.subplots(3, 3, figsize=(8.5, 7.5))

    wl_pretty = {'moe': 'MoE', 'ep_all_to_all': 'EP all-to-all',
                 'tree_allreduce': 'Tree all-reduce', 'uniform_random': 'Uniform',
                 'hybrid_tp_pp': 'Hybrid TP+PP', 'fsdp': 'FSDP'}

    for row_idx, (combo, wls) in enumerate(COMBOS_WLS):
        for col_idx in range(3):
            ax = axes[row_idx, col_idx]
            if col_idx >= len(wls):
                ax.axis('off')
                continue
            wl = wls[col_idx]

            # Track max latency to set Y limit per row
            max_lat = 0

            for alloc, style in ALLOC_STYLES.items():
                rates, lats = get_curve(grouped, cell, combo, alloc, wl)
                if rates is None: continue
                rl = [(r, l) for r, l in zip(rates, lats) if l is not None and RATE_MIN <= r <= RATE_MAX]
                if not rl: continue
                rs, ls = zip(*rl)
                max_lat = max(max_lat, max(ls))
                style_kwargs = {k: v for k, v in style.items() if k != 'marker'}
                ax.plot(rs, ls, **style_kwargs, marker=style['marker'], markersize=4)

            ax.set_xscale('log')
            ax.set_xlim(RATE_MIN * 0.9, RATE_MAX * 1.1)
            # Per-panel Y auto-scale with padding
            ax.set_ylim(0, max(80, max_lat * 1.08))
            ax.grid(True, which='major', alpha=0.4, linewidth=0.4)
            ax.grid(True, which='minor', alpha=0.2, linewidth=0.3)

            ax.set_title(wl_pretty[wl], fontsize=8.5, fontweight='bold')

            if row_idx == 2 or (row_idx == 0 and col_idx == len(wls) - 1) or (row_idx == 1 and col_idx == len(wls) - 1):
                ax.set_xlabel('Injection rate (packets/cycle)')
            if col_idx == 0:
                ax.set_ylabel(f'Latency (cycles)\n[{combo[:35]}]', fontsize=7)

    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', ncol=5,
               bbox_to_anchor=(0.5, 0.97), frameon=False)

    fig.suptitle(f'{cell}: Latency-vs-Rate, useful range r∈[{RATE_MIN}, {RATE_MAX}]\n'
                 f'ours wins on high-NL workloads (MoE, EP); marginal on Tree/Uniform',
                 y=1.0, fontsize=9)

    plt.tight_layout(rect=(0, 0, 1, 0.93))
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(f'{OUT_PATH}.pdf', dpi=300, bbox_inches='tight')
    plt.savefig(f'{OUT_PATH}.png', dpi=150, bbox_inches='tight')
    print(f"Saved: {OUT_PATH}.pdf, {OUT_PATH}.png")


if __name__ == '__main__':
    main()
