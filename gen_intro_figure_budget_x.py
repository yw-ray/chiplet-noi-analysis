"""Fig 1 with budget on X-axis, rate as legend lines.
5 panels per K, each shows lat vs budget for different rates.
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
    'legend.fontsize': 5.5, 'xtick.labelsize': 5.5, 'ytick.labelsize': 5.5,
    'figure.dpi': 150,
})

K_LIST = [4, 8, 16, 32, 64]
RATES = [0.001, 0.002, 0.003, 0.005, 0.008, 0.012]
RATE_COLORS = {
    0.001: '#2ca02c', 0.002: '#1f77b4', 0.003: '#9467bd',
    0.005: '#ff7f0e', 0.008: '#d62728', 0.012: '#8c564b',
}
RATE_MARKERS = {0.001: 'v', 0.002: '^', 0.003: 'o',
                0.005: 's', 0.008: 'D', 0.012: 'P'}
BUDGETS = [1, 2, 3, 4]


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
    print(f'Loaded {len(data)} points')

    fig, axes = plt.subplots(1, 5, figsize=(11.0, 2.6), sharey=True)

    for idx, K in enumerate(K_LIST):
        ax = axes[idx]
        for rate in RATES:
            ys = []
            xs = []
            for mult in BUDGETS:
                lat, thr = data.get((K, mult, round(rate, 5)), (None, None))
                if lat is not None:
                    xs.append(mult)
                    ys.append(lat)
            if not ys:
                continue
            ax.plot(xs, ys, marker=RATE_MARKERS[rate],
                    color=RATE_COLORS[rate], markersize=4,
                    linewidth=1.3, label=f'r={rate}',
                    zorder=3)

        ax.set_yscale('log')
        ax.set_xticks(BUDGETS)
        ax.set_xticklabels([f'{b}$\\times$' for b in BUDGETS])
        ax.set_xlim(0.7, 4.3)
        ax.set_title(f'K = {K}')
        ax.grid(True, which='major', alpha=0.3, linewidth=0.4)
        ax.grid(True, which='minor', alpha=0.15, linewidth=0.3)
        ax.set_xlabel('Link budget')
        if idx == 0:
            ax.set_ylabel('Latency (cycles, log)')
            ax.legend(loc='upper right', framealpha=0.95, ncol=2, fontsize=5)

    fig.suptitle('Latency vs budget per K — '
                 'higher rate diverges sooner as K grows (phantom load)',
                 fontsize=7.5, y=1.02)
    plt.tight_layout()
    out_png = FIGURES_DIR / 'fig_intro_motivation_budgetX.png'
    out_pdf = FIGURES_DIR / 'fig_intro_motivation_budgetX.pdf'
    fig.savefig(out_pdf, bbox_inches='tight')
    fig.savefig(out_png, bbox_inches='tight')
    plt.close()
    print(f'Saved: {out_png}')


if __name__ == '__main__':
    main()
