"""Fig 1 with full latency-vs-rate curves per K (Dally-style).

5 panels (K=4,8,16,32,64), each with 4 lines (budget 1x..4x).
X = injection rate (log), Y = latency.
Shows: budget shifts saturation knee, but phantom puts hard cap.
"""

import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

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
    print(f'Loaded {len(data)} points')

    # 5 panels in 1 row
    fig, axes = plt.subplots(1, 5, figsize=(10.0, 2.5), sharey=True)

    for idx, K in enumerate(K_LIST):
        ax = axes[idx]
        for mult in [1, 2, 3, 4]:
            rates_lats = []
            for (kk, mm, r), (lat, thr) in data.items():
                if kk == K and mm == mult and lat is not None:
                    rates_lats.append((r, lat, thr))
            rates_lats.sort()
            if not rates_lats:
                continue
            rs = [x[0] for x in rates_lats]
            ls = [x[1] for x in rates_lats]
            # only plot up to r=0.012
            keep = [(r, l) for r, l in zip(rs, ls) if r <= 0.0125]
            if not keep:
                continue
            rs, ls = zip(*keep)
            ax.plot(rs, ls, marker=BUDGET_MARKERS[mult],
                    color=BUDGET_COLORS[mult], markersize=3.5,
                    linewidth=1.3, label=f'{mult}$\\times$ budget',
                    zorder=3)

        ax.set_xscale('log')
        ax.set_yscale('log')
        ax.set_xlim(0.0008, 0.013)
        ax.set_xticks([0.001, 0.003, 0.01])
        ax.set_xticklabels(['0.001', '0.003', '0.01'])
        ax.set_title(f'K = {K}')
        ax.grid(True, which='major', alpha=0.3, linewidth=0.4)
        ax.grid(True, which='minor', alpha=0.15, linewidth=0.3)
        if idx == 0:
            ax.set_ylabel('Latency (cycles, log)')
            ax.legend(loc='upper left', framealpha=0.95)
        ax.set_xlabel('Injection rate (pkt/cyc)')

    fig.suptitle('Adjacent-only mesh: latency vs rate across K and budget — '
                 'phantom load shifts saturation knee left as K grows',
                 fontsize=7.5, y=1.02)
    plt.tight_layout()
    out_png = FIGURES_DIR / 'fig_intro_motivation_curves.png'
    out_pdf = FIGURES_DIR / 'fig_intro_motivation_curves.pdf'
    fig.savefig(out_pdf, bbox_inches='tight')
    fig.savefig(out_png, bbox_inches='tight')
    plt.close()
    print(f'Saved: {out_png}')

    # Also: bar chart of saturation rate (where >=90% acc)
    fig2, ax2 = plt.subplots(figsize=(4.0, 2.5))
    K_pos = np.arange(len(K_LIST))
    width = 0.18

    sat_rates_table = {}
    for mult in [1, 2, 3, 4]:
        sat_rates = []
        for K in K_LIST:
            rates_here = sorted({r for (kk, mm, r) in data
                                 if kk == K and mm == mult})
            sat = None
            for r in rates_here:
                lat, thr = data.get((K, mult, round(r, 5)), (None, None))
                if thr is None:
                    continue
                acc = thr / r if r > 0 else 0
                if acc >= 0.9:
                    sat = r
                else:
                    break
            sat_rates.append(sat if sat else 0)
        sat_rates_table[mult] = sat_rates
        ax2.bar(K_pos + (mult - 2.5) * width, sat_rates, width,
                color=BUDGET_COLORS[mult], label=f'{mult}$\\times$',
                edgecolor='black' if mult == 4 else None, linewidth=0.5)

    ax2.set_xticks(K_pos)
    ax2.set_xticklabels([f'K={k}' for k in K_LIST])
    ax2.set_ylabel('Saturation rate (acc $\\geq$ 90%)')
    ax2.set_title('Max sustainable injection rate vs K and budget')
    ax2.legend(loc='upper right', ncol=4, fontsize=5.5, framealpha=0.95)
    ax2.grid(True, axis='y', alpha=0.3, linewidth=0.4)
    plt.tight_layout()
    out2_png = FIGURES_DIR / 'fig_intro_motivation_satbars.png'
    out2_pdf = FIGURES_DIR / 'fig_intro_motivation_satbars.pdf'
    fig2.savefig(out2_pdf, bbox_inches='tight')
    fig2.savefig(out2_png, bbox_inches='tight')
    plt.close()
    print(f'Saved: {out2_png}')

    print('\nSat rates table:')
    print(f'{"K":<5} {"1x":<8} {"2x":<8} {"3x":<8} {"4x":<8}')
    for i, K in enumerate(K_LIST):
        print(f'{K:<5} {sat_rates_table[1][i]:<8} {sat_rates_table[2][i]:<8} '
              f'{sat_rates_table[3][i]:<8} {sat_rates_table[4][i]:<8}')


if __name__ == '__main__':
    main()
