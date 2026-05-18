"""Generate noise-free comparison figures for K16_N4:

(C) Throughput plot: accepted_rate vs offered_rate.
    - At saturation, accepted plateaus → noise-free metric.
    - X = offered injection rate, Y = accepted packet rate
    - Higher Y plateau = better.

(E) Max sustainable rate table: max rate where latency < N × zero-load.
    - Single number per (cell, combo, alloc, wl).
    - N=3 threshold (typical NoC convention).
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
OUT_DIR = Path("paper/figures")

LAT_THRESHOLD_MUL = 3.0  # rate is "sustainable" if latency < 3× zero-load
CANON_RATES = [0.001, 0.002, 0.003, 0.005, 0.008, 0.012, 0.018]

COMBOS_WLS = [
    ('moe+ep_all_to_all',                       ['moe', 'ep_all_to_all']),
    ('moe+uniform_random+ep_all_to_all',        ['moe', 'ep_all_to_all', 'uniform_random']),
    ('tree_allreduce+uniform_random',           ['tree_allreduce', 'uniform_random']),
]

ALLOC_STYLES = {
    'baseline_mesh':   {'color': '#9E9E9E', 'lw': 0.9, 'ls': '-',  'label': 'mesh',   'marker': 's', 'zorder': 2},
    'baseline_kite_l': {'color': '#64B5F6', 'lw': 0.9, 'ls': '-',  'label': 'kite_l', 'marker': '^', 'zorder': 2},
    'baseline_gia':    {'color': '#FFB74D', 'lw': 0.8, 'ls': '--', 'label': 'gia',    'marker': 'D', 'zorder': 2},
    'ours_mask':       {'color': '#C62828', 'lw': 2.2, 'ls': '-',  'label': 'ours',   'marker': 'o', 'zorder': 10},
}

WL_PRETTY = {'moe': 'MoE', 'ep_all_to_all': 'EP all-to-all',
             'tree_allreduce': 'Tree all-reduce', 'uniform_random': 'Uniform',
             'hybrid_tp_pp': 'Hybrid TP+PP', 'fsdp': 'FSDP'}


def load():
    d = json.loads(DATA_PATH.read_text())
    # {(cell, combo, alloc, wl): {rate: (lat, thr)}}
    grouped = defaultdict(dict)
    for key, v in d.items():
        cell, combo, alloc, wl, rate_str = key.split('|')
        rate = float(rate_str)
        grouped[(cell, combo, alloc, wl)][rate] = (v.get('latency'), v.get('throughput'))
    return grouped


def get_curve(grouped, cell, combo, alloc, wl, metric='throughput'):
    if alloc == 'ours_mask':
        alloc_key = f'ours_mask_{wl}'
    else:
        alloc_key = alloc
    rdict = grouped.get((cell, combo, alloc_key, wl), {})
    rs, vs = [], []
    for r in sorted(rdict.keys()):
        lat, thr = rdict[r]
        if metric == 'throughput' and thr is not None:
            rs.append(r); vs.append(thr)
        elif metric == 'latency' and lat is not None:
            rs.append(r); vs.append(lat)
    return rs, vs


def gen_throughput_figure():
    grouped = load()
    cell = 'K16_N4'

    fig, axes = plt.subplots(3, 3, figsize=(8.5, 7.5))

    for row_idx, (combo, wls) in enumerate(COMBOS_WLS):
        for col_idx in range(3):
            ax = axes[row_idx, col_idx]
            if col_idx >= len(wls):
                ax.axis('off')
                continue
            wl = wls[col_idx]

            # Plot offered_rate diagonal (y=x) reference
            offered = np.array(CANON_RATES)
            ax.plot(offered, offered, color='#222', ls=':', lw=0.8, label='ideal (y=x)', zorder=1)

            for alloc, style in ALLOC_STYLES.items():
                rates, thrs = get_curve(grouped, cell, combo, alloc, wl, metric='throughput')
                if not rates: continue
                style_kwargs = {k: v for k, v in style.items() if k != 'marker'}
                ax.plot(rates, thrs, **style_kwargs, marker=style['marker'], markersize=4)

            ax.set_xscale('log')
            ax.set_xlim(8e-4, 2e-2)
            ax.set_ylim(0, 0.02)
            ax.grid(True, which='major', alpha=0.4, linewidth=0.4)
            ax.set_title(WL_PRETTY[wl], fontsize=8.5, fontweight='bold')

            if row_idx == 2 or (row_idx == 0 and col_idx == len(wls) - 1) or (row_idx == 1 and col_idx == len(wls) - 1):
                ax.set_xlabel('Offered rate')
            if col_idx == 0:
                ax.set_ylabel(f'Accepted rate\n[{combo[:35]}]', fontsize=7)

    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', ncol=5,
               bbox_to_anchor=(0.5, 0.97), frameon=False)
    fig.suptitle(f'{cell}: Throughput plot (accepted vs offered rate)\n'
                 'plateau = max sustainable throughput; ours plateau higher → more throughput',
                 y=1.0, fontsize=9)
    plt.tight_layout(rect=(0, 0, 1, 0.93))
    out = OUT_DIR / 'fig_k16n4_throughput'
    plt.savefig(f'{out}.pdf', dpi=300, bbox_inches='tight')
    plt.savefig(f'{out}.png', dpi=150, bbox_inches='tight')
    print(f"Saved: {out}.png")
    plt.close()


def compute_max_sustainable_rate(grouped):
    """For each (cell, combo, alloc, wl), find max rate where lat < 3× zero-load."""
    results = []
    for (cell, combo, alloc, wl), rdict in sorted(grouped.items()):
        rates = sorted(rdict.keys())
        if not rates: continue
        zero_load = rdict[rates[0]][0]  # latency at min rate
        if zero_load is None: continue
        threshold = LAT_THRESHOLD_MUL * zero_load
        max_sustain = None
        for r in rates:
            lat = rdict[r][0]
            if lat is None: continue
            if lat <= threshold:
                max_sustain = r
            else:
                break
        results.append({
            'cell': cell, 'combo': combo, 'alloc': alloc, 'wl': wl,
            'zero_load': zero_load, 'threshold': threshold,
            'max_sustainable': max_sustain,
        })
    return results


def gen_sustained_rate_figure():
    grouped = load()
    results = compute_max_sustainable_rate(grouped)
    # Group by (cell, combo, wl) → {alloc: max_rate}
    grouped_results = defaultdict(dict)
    for r in results:
        grouped_results[(r['cell'], r['combo'], r['wl'])][r['alloc']] = r['max_sustainable']

    # Plot K16_N4 sustained rate bar chart
    cell = 'K16_N4'
    bar_data = []
    for combo, wls in COMBOS_WLS:
        for wl in wls:
            key = (cell, combo, wl)
            d = grouped_results.get(key, {})
            bar_data.append({
                'combo': combo, 'wl': wl,
                'mesh': d.get('baseline_mesh'),
                'kite_l': d.get('baseline_kite_l'),
                'kite_m': d.get('baseline_kite_m'),
                'gia': d.get('baseline_gia'),
                'ours': d.get(f'ours_mask_{wl}'),
            })

    fig, ax = plt.subplots(figsize=(9, 4.5))
    n = len(bar_data)
    labels = [f"{WL_PRETTY[d['wl']]}\n({d['combo'][:20]})" for d in bar_data]
    x = np.arange(n)
    width = 0.15

    allocs_order = [('mesh', '#9E9E9E'), ('kite_l', '#64B5F6'),
                    ('kite_m', '#90CAF9'), ('gia', '#FFB74D'), ('ours', '#C62828')]
    for i, (name, color) in enumerate(allocs_order):
        vals = [d.get(name) for d in bar_data]
        vals_plot = [v if v else 0 for v in vals]
        ax.bar(x + (i - 2) * width, vals_plot, width, label=name, color=color,
               edgecolor='black' if name == 'ours' else None, linewidth=0.8)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha='right', fontsize=7)
    ax.set_ylabel(f'Max sustainable injection rate\n(lat < {LAT_THRESHOLD_MUL}× zero-load)')
    ax.set_title(f'{cell}: Max sustainable rate by allocation\n'
                 'higher = better (delays saturation, allows more traffic)',
                 fontsize=10)
    ax.legend(loc='upper right', ncol=5, fontsize=7)
    ax.grid(True, axis='y', alpha=0.4)
    plt.tight_layout()
    out = OUT_DIR / 'fig_k16n4_sustained_rate'
    plt.savefig(f'{out}.pdf', dpi=300, bbox_inches='tight')
    plt.savefig(f'{out}.png', dpi=150, bbox_inches='tight')
    print(f"Saved: {out}.png")
    plt.close()


def print_sustained_table():
    grouped = load()
    results = compute_max_sustainable_rate(grouped)
    print(f"\n=== Max sustainable rate (lat < {LAT_THRESHOLD_MUL}× zero-load) ===")
    print(f"{'cell|combo':<55} {'wl':<14} {'alloc':<22} {'zero':<6} {'thr':<6} {'sat rate':<10}")
    print("-"*120)
    for r in results:
        if r['cell'] != 'K16_N4': continue
        key = f"{r['cell']}|{r['combo'][:40]}"
        print(f"{key:<55} {r['wl']:<14} {r['alloc']:<22} {r['zero_load']:>5.1f}  {r['threshold']:>5.1f}  {r['max_sustainable']}")


if __name__ == '__main__':
    gen_throughput_figure()
    gen_sustained_rate_figure()
    print_sustained_table()
