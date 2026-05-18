"""Fig 1 final: K X-axis, budget lines 1-6x, fixed rate=0.005.
Shows that even relaxing PHY cap (5x, 6x) doesn't help — adj-only hard floor.
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
EXTBUDGET_PATH = Path(__file__).parent / 'results' / 'cost_perf_K' / 'cost_perf_K_extbudget.json'

plt.rcParams.update({
    'font.size': 7, 'font.family': 'serif',
    'axes.labelsize': 7, 'axes.titlesize': 8,
    'legend.fontsize': 6.5, 'xtick.labelsize': 6.5, 'ytick.labelsize': 6.5,
    'figure.dpi': 150,
})

K_LIST = [4, 8, 16, 32, 64]
BUDGETS = [1, 2, 3, 4, 5, 6]
HEADLINE_RATE = 0.005
BUDGET_COLORS = {
    1: '#d62728', 2: '#ff7f0e', 3: '#1f77b4',
    4: '#2ca02c', 5: '#17becf', 6: '#9467bd',
}
BUDGET_MARKERS = {1: 'o', 2: 's', 3: '^', 4: 'v', 5: 'D', 6: 'P'}
BUDGET_LS = {1: '-', 2: '-', 3: '-', 4: '-', 5: '--', 6: ':'}


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
            for r in e['rates']:
                key = (K, e['budget_mult'], round(r['rate'], 5))
                if key not in out:
                    out[key] = (r['latency'], r['throughput'])
    if EXTBUDGET_PATH.exists():
        ext = json.loads(EXTBUDGET_PATH.read_text())
        for k, v in ext.items():
            key = (v['K'], v['budget_mult'], round(v['rate'], 5))
            out[key] = (v['latency'], v['throughput'])
    return out


def main():
    data = load_all()

    fig, ax = plt.subplots(figsize=(3.8, 2.8))
    for mult in BUDGETS:
        xs, ys = [], []
        for K in K_LIST:
            lat, _ = data.get((K, mult, round(HEADLINE_RATE, 5)), (None, None))
            if lat is not None:
                xs.append(K)
                ys.append(lat)
        if not ys:
            continue
        # Emphasize 4x (PHY cap) and 6x (relaxed cap)
        is_phy_cap = mult == 4
        is_relaxed = mult in (5, 6)
        lw = 2.2 if is_phy_cap else (1.6 if is_relaxed else 1.2)
        ms = 6 if is_phy_cap else (5 if is_relaxed else 4)
        ax.plot(xs, ys, marker=BUDGET_MARKERS[mult],
                color=BUDGET_COLORS[mult],
                linestyle=BUDGET_LS[mult],
                markersize=ms, linewidth=lw,
                label=f'{mult}$\\times$' + (' (PHY cap)' if is_phy_cap
                                            else ' (relaxed)' if is_relaxed else ''),
                zorder=5 if is_phy_cap else (4 if is_relaxed else 3),
                alpha=1.0 if (is_phy_cap or is_relaxed) else 0.7)

    ax.set_xscale('log', base=2)
    ax.set_yscale('log')
    ax.set_xticks(K_LIST)
    ax.set_xticklabels([str(k) for k in K_LIST])
    ax.set_xlabel('Number of chiplets (K)')
    ax.set_ylabel('Latency (cycles, log)')
    ax.set_title(f'Adj-only mesh: budget$\\geq$4$\\times$ saturates (rate={HEADLINE_RATE})')
    ax.grid(True, which='major', alpha=0.3, linewidth=0.4)
    ax.grid(True, which='minor', alpha=0.15, linewidth=0.3)
    ax.legend(loc='upper left', framealpha=0.95, ncol=2,
              title='Link budget (× per pair)', title_fontsize=6)

    v_4x_K64 = data.get((64, 4, round(HEADLINE_RATE, 5)), (None,))[0]
    v_6x_K64 = data.get((64, 6, round(HEADLINE_RATE, 5)), (None,))[0]
    if v_4x_K64 and v_6x_K64:
        ax.annotate(
            f'4$\\times$ = 5$\\times$ = 6$\\times$ = {v_4x_K64:.0f} cyc at K=64\n'
            f'Adding lanes/pair does not help.\n'
            f'Phantom load $+$ hop count $\\to$ hard floor.',
            xy=(64, v_6x_K64),
            xytext=(0.32, 0.62), textcoords='axes fraction',
            fontsize=6.5,
            arrowprops=dict(arrowstyle='->', color='#7a3', lw=1.0),
            color='#274', fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.3',
                      facecolor='#efe', edgecolor='#7a3', alpha=0.95))

    plt.tight_layout()
    out_png = FIGURES_DIR / 'fig_intro_motivation_final.png'
    out_pdf = FIGURES_DIR / 'fig_intro_motivation_final.pdf'
    fig.savefig(out_pdf, bbox_inches='tight')
    fig.savefig(out_png, bbox_inches='tight')
    plt.close()
    print(f'Saved: {out_png}')

    print(f'\nLatency table at rate={HEADLINE_RATE}:')
    print(f'{"K":<5} ' + ' '.join(f'{m}× lat' for m in BUDGETS))
    for K in K_LIST:
        row = []
        for m in BUDGETS:
            lat = data.get((K, m, round(HEADLINE_RATE, 5)), (None,))[0]
            row.append(f'{lat:>6.1f}' if lat else '   N/A')
        print(f'{K:<5} ' + ' '.join(row))


if __name__ == '__main__':
    main()
