"""Introduction Figure v6: K in {4, 8, 16, 32, 64} only.
(a) Center-link amplification: closed-form + BookSim-measured latency overlay.
(b) Adjacent-link budget sweep: speedup vs 1x budget across K.
"""

import json
import math
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

FIGURES_DIR = Path(__file__).parent / 'paper' / 'figures'
CPK_PATH = Path(__file__).parent / 'results' / 'cost_perf_K' / 'cost_perf_across_K.json'
K64_PATH = Path(__file__).parent / 'results' / 'cost_perf_K' / 'cost_perf_K64.json'

plt.rcParams.update({
    'font.size': 6, 'font.family': 'serif',
    'axes.labelsize': 6, 'axes.titlesize': 7,
    'legend.fontsize': 5.5, 'xtick.labelsize': 5.5, 'ytick.labelsize': 5.5,
    'figure.dpi': 150,
})

bbox_white = dict(boxstyle='round,pad=0.2', facecolor='white', edgecolor='none', alpha=0.85)

K_LIST = [4, 8, 16, 32, 64]
GRIDS = {4: (2, 2), 8: (2, 4), 16: (4, 4), 32: (4, 8), 64: (8, 8)}


def closed_form_alpha(K):
    R, C = GRIDS[K]
    max_h = R * ((C + 1) // 2) * (C // 2)
    max_v = C * ((R + 1) // 2) * (R // 2)
    return max(max_h, max_v)


def load_booksim_data():
    """Latency at rate=0.005 across (K, budget_mult) for adj_uniform."""
    d = json.loads(CPK_PATH.read_text())
    if K64_PATH.exists():
        d64 = json.loads(K64_PATH.read_text())
        d['8x8'] = d64
    out = {}
    for grid_key, gd in d.items():
        K = gd['K']
        for e in gd['experiments']:
            if e['strategy'] != 'adj_uniform':
                continue
            mult = e['budget_mult']
            for r in e['rates']:
                if abs(r['rate'] - 0.005) < 1e-9:
                    out[(K, mult)] = r['latency']
    return out


def main():
    lat = load_booksim_data()
    print('Loaded BookSim data points:', sorted(lat.keys()))

    fig, axes = plt.subplots(2, 1, figsize=(3.5, 3.8))

    # ---- Panel (a): BookSim-measured phantom load impact ----
    ax = axes[0]
    booksim_lats_1x = [lat.get((K, 1)) for K in K_LIST]
    valid_idx = [i for i, v in enumerate(booksim_lats_1x) if v is not None]
    bs_x = [K_LIST[i] for i in valid_idx]
    bs_y = [booksim_lats_1x[i] for i in valid_idx]

    ax.plot(bs_x, bs_y, 'o-', color='#d62728', markersize=6,
            linewidth=1.8, zorder=3)
    ax.fill_between(bs_x, [bs_y[0]] * len(bs_x), bs_y,
                    alpha=0.10, color='#d62728')

    ax.set_xlabel('Number of chiplets (K)')
    ax.set_ylabel('Latency at 1$\\times$ budget (cycles)')
    ax.set_xscale('log', base=2)
    ax.set_yscale('log')
    ax.set_xticks(K_LIST)
    ax.set_xticklabels([str(k) for k in K_LIST])
    ax.set_title('(a) BookSim-measured phantom load (adj-only mesh)')
    ax.grid(True, which='major', alpha=0.3, linewidth=0.4)
    ax.grid(True, which='minor', alpha=0.15, linewidth=0.3)

    for K, l in zip(bs_x, bs_y):
        ax.annotate(f'{l:.0f}', xy=(K, l), xytext=(4, 6),
                    textcoords='offset points', fontsize=5.5,
                    color='#d62728', fontweight='bold')

    if len(bs_y) >= 2:
        amp_factor = bs_y[-1] / bs_y[0]
        ax.text(0.05, 0.85,
                f'K={bs_x[0]}$\\to${bs_x[-1]}: {amp_factor:.1f}$\\times$ latency',
                transform=ax.transAxes, fontsize=5.5,
                color='#d62728', fontweight='bold', bbox=bbox_white)

    # ---- Panel (b): Budget sweep speedup ----
    ax = axes[1]
    colors = {4: '#2ca02c', 8: '#1f77b4', 16: '#ff7f0e', 32: '#d62728', 64: '#8c564b'}
    markers = {4: 'v', 8: '^', 16: 's', 32: 'o', 64: 'D'}

    budgets = [1, 2, 3, 4]
    K_speedups = {}
    for K in K_LIST:
        lats = [lat.get((K, m)) for m in budgets]
        if lats[0] is None or any(l is None for l in lats):
            print(f'K={K}: missing BookSim data, skip')
            continue
        K_speedups[K] = [lats[0] / l for l in lats]
        ax.plot(budgets, K_speedups[K], marker=markers[K], color=colors[K],
                markersize=5 if K in (16, 32, 64) else 4,
                linewidth=1.8 if K in (16, 32, 64) else 1.3,
                label=f'K={K}', alpha=0.95, zorder=3)

    ideal = budgets
    ax.plot(budgets, ideal, '--', color='gray', linewidth=1.0, alpha=0.5, label='Ideal (linear)')

    ax.set_xlabel('Link budget (× per adjacent pair)')
    ax.set_ylabel('Speedup vs 1$\\times$')
    ax.set_xticks(budgets)
    ax.set_xticklabels([f'{b}$\\times$' for b in budgets])
    ax.set_title('(b) Adjacent links alone: diminishing returns')
    ax.legend(loc='upper left', ncol=2, framealpha=0.92)
    ax.grid(True, alpha=0.3, linewidth=0.4)
    ax.set_ylim(0.8, 4.5)

    if 16 in K_speedups:
        ax.annotate(
            f'K=16: 4$\\times$ budget\n$\\to$ {K_speedups[16][3]:.2f}$\\times$ only',
            xy=(3.9, K_speedups[16][3]), fontsize=5.5,
            ha='right', va='top', xytext=(3.85, 3.7),
            arrowprops=dict(arrowstyle='->', color='#ff7f0e', lw=0.8),
            color='#ff7f0e', fontweight='bold', bbox=bbox_white)

    plt.tight_layout()
    out_pdf = FIGURES_DIR / 'fig_intro_motivation_v6.pdf'
    out_png = FIGURES_DIR / 'fig_intro_motivation_v6.png'
    fig.savefig(out_pdf, bbox_inches='tight')
    fig.savefig(out_png, bbox_inches='tight')
    plt.close()
    print(f'Saved: {out_pdf}')
    print(f'Saved: {out_png}')


if __name__ == '__main__':
    main()
