"""Generate Fig: latency vs injection rate, 4 cells × representative combos.

X axis: injection rate (log scale)
Y axis: latency (cycles)
Lines: mesh, kite_l, gia, ours_mask
"""

import json
import math
from pathlib import Path
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np

# Paper-consistent rcParams (per CLAUDE.md figure rules)
plt.rcParams.update({
    'font.size': 6,
    'axes.titlesize': 7,
    'axes.labelsize': 6,
    'xtick.labelsize': 5.5,
    'ytick.labelsize': 5.5,
    'legend.fontsize': 5.5,
    'font.family': 'serif',
})

DATA_PATH = Path("results/ml_placement/rate_sweep_v3.json")
OUT_PATH = Path("paper/figures/fig_rate_sweep")

RATES = [0.001, 0.002, 0.003, 0.005, 0.008, 0.012, 0.018]

# Cells and representative combos to show
# (cell, combo, [highlight_wl])
PANELS = [
    ('K16_N4', 'moe+ep_all_to_all', ['moe', 'ep_all_to_all']),
    ('K16_N8', 'moe+ep_all_to_all', ['moe', 'ep_all_to_all']),
    ('K32_N4', 'moe+uniform_random+ep_all_to_all', ['moe', 'ep_all_to_all']),
    ('K32_N8', 'moe+ep_all_to_all', ['moe', 'ep_all_to_all']),
]

# Allocations to show
ALLOC_STYLES = {
    'baseline_mesh':   {'color': '#888888', 'lw': 1.0, 'ls': '-',  'label': 'mesh',     'marker': 's'},
    'baseline_kite_l': {'color': '#2196F3', 'lw': 1.0, 'ls': '-',  'label': 'kite_l',   'marker': '^'},
    'baseline_kite_m': {'color': '#03A9F4', 'lw': 0.8, 'ls': '--', 'label': 'kite_m',   'marker': 'v'},
    'baseline_gia':    {'color': '#FF9800', 'lw': 1.0, 'ls': '-',  'label': 'gia',      'marker': 'D'},
    'ours_mask':       {'color': '#D32F2F', 'lw': 1.4, 'ls': '-',  'label': 'ours',     'marker': 'o'},
}


def load_data():
    d = json.loads(DATA_PATH.read_text())
    grouped = defaultdict(dict)  # (cell, combo, alloc, wl) -> {rate: lat}
    for key, v in d.items():
        cell, combo, alloc, wl, rate_str = key.split('|')
        rate = float(rate_str)
        grouped[(cell, combo, alloc, wl)][rate] = v.get('latency')
    return grouped


def get_curve(grouped, cell, combo, alloc, wl):
    """Return sorted (rates, lats) for a specific (cell, combo, alloc, wl)."""
    # ours_mask is per-WL: 'ours_mask_<wl>'
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

    # 4 cells × 2 WLs = 8 panels (2 rows × 4 cols)
    fig, axes = plt.subplots(2, 4, figsize=(7.2, 3.6))

    for col_idx, (cell, combo, wls) in enumerate(PANELS):
        for row_idx, wl in enumerate(wls):
            ax = axes[row_idx, col_idx]
            wl_short = {'moe': 'MoE', 'ep_all_to_all': 'EP',
                        'tree_allreduce': 'Tree', 'uniform_random': 'Uniform',
                        'hybrid_tp_pp': 'Hybrid', 'fsdp': 'FSDP'}.get(wl, wl)

            for alloc, style in ALLOC_STYLES.items():
                rates, lats = get_curve(grouped, cell, combo, alloc, wl)
                if rates is None: continue
                # Filter out None values
                rl_pairs = [(r, l) for r, l in zip(rates, lats) if l is not None]
                if not rl_pairs: continue
                rs, ls = zip(*rl_pairs)
                ax.plot(rs, ls, **{k: v for k, v in style.items() if k != 'marker'},
                        marker=style['marker'], markersize=2.5)

            ax.set_xscale('log')
            ax.set_xlim(8e-4, 2e-2)
            ax.set_ylim(0, 700)
            ax.grid(True, which='major', alpha=0.3, linewidth=0.3)
            ax.grid(True, which='minor', alpha=0.15, linewidth=0.2)

            if row_idx == 0:
                ax.set_title(f'{cell} • {wl_short}')
            else:
                ax.set_title(f'{wl_short}')

            if row_idx == 1:
                ax.set_xlabel('Injection rate')
            else:
                ax.set_xticklabels([])

            if col_idx == 0:
                ax.set_ylabel('Latency (cycles)')
            else:
                ax.set_yticklabels([])

    # Single legend at top
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', ncol=5,
               bbox_to_anchor=(0.5, 1.02), frameon=False)

    plt.tight_layout(rect=(0, 0, 1, 0.96))
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(f'{OUT_PATH}.pdf', dpi=300, bbox_inches='tight')
    plt.savefig(f'{OUT_PATH}.png', dpi=200, bbox_inches='tight')
    print(f"Saved: {OUT_PATH}.pdf, {OUT_PATH}.png")


if __name__ == '__main__':
    main()
