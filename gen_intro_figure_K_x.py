"""Fig 1: K on X-axis, budget as lines.

Shows: even 4x budget doesn't keep latency low as K grows.
"""

import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

FIGURES_DIR = Path(__file__).parent / 'paper' / 'figures'
RATESWEEP_PATH = Path(__file__).parent / 'results' / 'cost_perf_K' / 'cost_perf_K_ratesweep.json'
CPK_PATH = Path(__file__).parent / 'results' / 'cost_perf_K' / 'cost_perf_across_K.json'
K64_PATH = Path(__file__).parent / 'results' / 'cost_perf_K' / 'cost_perf_K64.json'

plt.rcParams.update({
    'font.size': 6, 'font.family': 'serif',
    'axes.labelsize': 6, 'axes.titlesize': 7,
    'legend.fontsize': 6, 'xtick.labelsize': 5.5, 'ytick.labelsize': 5.5,
    'figure.dpi': 150,
})

K_LIST = [4, 8, 16, 32, 64]
BUDGETS = [1, 2, 3, 4]
RATES_TO_SHOW = [0.003, 0.005]
BUDGET_COLORS = {1: '#d62728', 2: '#ff7f0e', 3: '#1f77b4', 4: '#2ca02c'}
BUDGET_MARKERS = {1: 'o', 2: 's', 3: '^', 4: 'v'}


def load_all():
    out = {}
    if RATESWEEP_PATH.exists():
        d = json.loads(RATESWEEP_PATH.read_text())
        for k, v in d.items():
            out[(v['K'], v['budget_mult'], round(v['rate'], 5))] = (
                v['latency'], v['throughput'])
    cpk = json.loads(CPK_PATH.read_text())
    if K64_PATH.exists():
        cpk['8x8'] = json.loads(K64_PATH.read_text())
    for gk, gd in cpk.items():
        K = gd['K']
        for e in gd['experiments']:
            if e['strategy'] != 'adj_uniform':
                continue
            mult = e['budget_mult']
            for r in e['rates']:
                key = (K, mult, round(r['rate'], 5))
                if key not in out:
                    out[key] = (r['latency'], r['throughput'])
    return out


def main():
    data = load_all()

    fig, axes = plt.subplots(1, len(RATES_TO_SHOW), figsize=(6.2, 2.7), sharey=False)
    if len(RATES_TO_SHOW) == 1:
        axes = [axes]

    for ax_idx, rate in enumerate(RATES_TO_SHOW):
        ax = axes[ax_idx]
        for mult in BUDGETS:
            xs, ys = [], []
            for K in K_LIST:
                lat, thr = data.get((K, mult, round(rate, 5)), (None, None))
                if lat is not None:
                    xs.append(K)
                    ys.append(lat)
            if not ys:
                continue
            ax.plot(xs, ys, marker=BUDGET_MARKERS[mult],
                    color=BUDGET_COLORS[mult], markersize=5,
                    linewidth=1.5 if mult == 4 else 1.2,
                    label=f'{mult}$\\times$ budget',
                    zorder=4 if mult == 4 else 3)

        ax.set_xscale('log', base=2)
        ax.set_yscale('log')
        ax.set_xticks(K_LIST)
        ax.set_xticklabels([str(k) for k in K_LIST])
        ax.set_xlabel('Number of chiplets (K)')
        if ax_idx == 0:
            ax.set_ylabel('Latency (cycles, log)')
        ax.set_title(f'Injection rate = {rate}')
        ax.grid(True, which='major', alpha=0.3, linewidth=0.4)
        ax.grid(True, which='minor', alpha=0.15, linewidth=0.3)
        ax.legend(loc='upper left', framealpha=0.95)

        # Annotate the 4x line at K=64 specifically
        v_4x_K4 = data.get((4, 4, round(rate, 5)), (None,))[0]
        v_4x_K64 = data.get((64, 4, round(rate, 5)), (None,))[0]
        if v_4x_K4 and v_4x_K64:
            ax.annotate(
                f'4$\\times$ budget: {v_4x_K4:.0f}$\\to${v_4x_K64:.0f} cyc\n'
                f'({v_4x_K64/v_4x_K4:.1f}$\\times$ worse despite 4$\\times$ links)',
                xy=(64, v_4x_K64),
                xytext=(0.55, 0.10), textcoords='axes fraction',
                fontsize=5.5,
                arrowprops=dict(arrowstyle='->', color='#2ca02c', lw=0.8),
                color='#2ca02c', fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.25',
                          facecolor='white', edgecolor='#2ca02c', alpha=0.92))

    fig.suptitle('Latency grows with K even at max budget — phantom load hard cap',
                 fontsize=7.5, y=1.02)
    plt.tight_layout()
    out_png = FIGURES_DIR / 'fig_intro_motivation_kX.png'
    out_pdf = FIGURES_DIR / 'fig_intro_motivation_kX.pdf'
    fig.savefig(out_pdf, bbox_inches='tight')
    fig.savefig(out_png, bbox_inches='tight')
    plt.close()
    print(f'Saved: {out_png}')

    # Print summary table
    print('\nLatency vs K and budget table:')
    for rate in RATES_TO_SHOW:
        print(f'\n--- rate={rate} ---')
        print(f'{"K":<5} ' + ' '.join(f'{m}x' for m in BUDGETS) +
              '   ratio(K_max/K_min @ 4x)')
        for K in K_LIST:
            row = []
            for m in BUDGETS:
                lat = data.get((K, m, round(rate, 5)), (None,))[0]
                row.append(f'{lat:>6.1f}' if lat else '   N/A')
            print(f'{K:<5} ' + ' '.join(row))


if __name__ == '__main__':
    main()
