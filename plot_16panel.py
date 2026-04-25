"""16-panel figures (4 workload × 4 K/N grid) for bpp sweep, rate sweep, throughput."""
import json
from pathlib import Path
from collections import defaultdict
import matplotlib.pyplot as plt

plt.rcParams.update({
    'font.size': 5.5, 'axes.titlesize': 6.5, 'axes.labelsize': 5.5,
    'xtick.labelsize': 5, 'ytick.labelsize': 5,
    'legend.fontsize': 5, 'font.family': 'serif',
})

R = Path('results/ml_placement')
FIG_DIR = Path('paper/figures')

METHOD_STYLE = {
    'adj_uniform': dict(color='tab:gray', marker='s', ls='--', label='Adj Uniform'),
    'greedy':      dict(color='tab:blue', marker='o', ls='-',  label='Greedy'),
    'fbfly':       dict(color='tab:orange', marker='^', ls='-.', label='FBfly'),
    'rl_ws':       dict(color='tab:red',  marker='D', ls='-',  label='RL-WS (ours)'),
}
WL_ORDER = ['tree_allreduce', 'hybrid_tp_pp', 'uniform_random', 'moe']
WL_LABEL = {'tree_allreduce':'Tree AR', 'hybrid_tp_pp':'Hybrid', 'uniform_random':'Uniform', 'moe':'MoE'}
KN_ORDER = [(16,4), (16,8), (32,4), (32,8)]


def load_all():
    comp = json.load(open(R/'ml_comparison_fast.json'))
    warm = json.load(open(R/'ml_comparison_warmstart.json'))
    fb   = json.load(open(R/'butterfly_baseline.json'))
    sweep = json.load(open(R/'rate_sweep.json'))
    extra = []
    if (R/'bpp_extra.json').exists():
        extra = json.load(open(R/'bpp_extra.json'))
    return comp, warm, fb, sweep, extra


def build_bpp_cells():
    """Return dict (wl, K, N, bpp) -> {'adj':.., 'greedy':.., 'fbfly':.., 'rl_ws':..}."""
    comp, warm, fb, sweep, extra = load_all()
    cells = defaultdict(dict)

    for r in comp:
        k = (r['workload'], r['K'], r['N'], r['budget_per_pair'])
        cells[k]['adj_uniform'] = r['adj_uniform']['latency']
        cells[k]['greedy'] = r['express_greedy']['latency']
    for r in warm:
        k = (r['workload'], r['K'], r['N'], r['budget_per_pair'])
        cells[k]['rl_ws'] = r['rl_warmstart']['latency']
    for r in fb:
        k = (r['workload'], r['K'], r['N'], r['budget_per_pair'])
        cells[k]['fbfly'] = r['L_fbfly']
    # rate_sweep at rate 1x is base rate
    for r in sweep:
        k = (r['workload'], r['K'], r['N'], r['budget_per_pair'])
        for m in ['adj_uniform', 'greedy', 'fbfly', 'rl_ws']:
            cells[k].setdefault(m, r[m]['latency'][0])
    # bpp_extra adds 4 methods at base rate for K32
    for r in extra:
        k = (r['workload'], r['K'], r['N'], r['budget_per_pair'])
        cells[k]['adj_uniform'] = r['L_adj']
        cells[k]['greedy'] = r['L_greedy']
        cells[k]['fbfly'] = r['L_fbfly']
        cells[k]['rl_ws'] = r['L_rl_fb']
    return cells


def fig_bpp_sweep_16panel():
    cells = build_bpp_cells()
    fig, axes = plt.subplots(4, 4, figsize=(7.2, 7.5), sharex=False)
    for i, wl in enumerate(WL_ORDER):
        for j, (K, N) in enumerate(KN_ORDER):
            ax = axes[i][j]
            bpps_all = sorted(set(bpp for (w, k, n, bpp) in cells.keys() if (w, k, n) == (wl, K, N)))
            data = defaultdict(lambda: ([], []))
            for bpp in bpps_all:
                lats = cells.get((wl, K, N, bpp), {})
                for m in ['adj_uniform', 'greedy', 'fbfly', 'rl_ws']:
                    if m in lats:
                        data[m][0].append(bpp); data[m][1].append(lats[m])
            for m, (bp, lt) in data.items():
                s = METHOD_STYLE[m]
                ax.plot(bp, lt, color=s['color'], marker=s['marker'], linestyle=s['ls'],
                        label=s['label'], markersize=3, linewidth=0.9)
            ax.grid(True, alpha=0.3, linewidth=0.3)
            if i == 0:
                ax.set_title(f'K{K}N{N}')
            if j == 0:
                ax.set_ylabel(f'{WL_LABEL[wl]}\nLatency (cyc)')
            if i == 3:
                ax.set_xlabel(r'Budget per pair ($\times$)')
            ax.set_xticks(bpps_all)
    # Shared legend
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', ncol=4, bbox_to_anchor=(0.5, 1.005),
               frameon=True, fontsize=6)
    plt.tight_layout(rect=[0, 0, 1, 0.98])
    out_pdf = FIG_DIR/'fig_bpp_16panel.pdf'; out_png = FIG_DIR/'fig_bpp_16panel.png'
    plt.savefig(out_pdf, bbox_inches='tight', dpi=300)
    plt.savefig(out_png, bbox_inches='tight', dpi=150)
    plt.close()
    print(f'Saved: {out_pdf}')


def fig_rate_sweep_16panel():
    """Rate sweep at all 4 K/N. Requires rate_sweep.json to cover 16 cells."""
    sweep = json.load(open(R/'rate_sweep.json'))
    by_cell = {(r['workload'], r['K'], r['N']): r for r in sweep}
    fig, axes = plt.subplots(4, 4, figsize=(7.2, 7.5))
    for i, wl in enumerate(WL_ORDER):
        for j, (K, N) in enumerate(KN_ORDER):
            ax = axes[i][j]
            r = by_cell.get((wl, K, N))
            if r is None:
                ax.text(0.5, 0.5, 'no data', ha='center', va='center',
                        transform=ax.transAxes, fontsize=6, color='gray')
                ax.set_xticks([]); ax.set_yticks([])
            else:
                rates_mult = [1, 2, 3, 4]
                for m in ['adj_uniform', 'greedy', 'fbfly', 'rl_ws']:
                    lat = r[m]['latency']
                    s = METHOD_STYLE[m]
                    ax.plot(rates_mult, lat, color=s['color'], marker=s['marker'], linestyle=s['ls'],
                            label=s['label'], markersize=2.5, linewidth=0.9)
                ax.set_xticks(rates_mult)
                # log Y only when range is wide (e.g., saturating cells)
                lats_all = [v for m in ['adj_uniform','greedy','fbfly','rl_ws'] for v in r[m]['latency']]
                if max(lats_all) / min(lats_all) > 3:
                    ax.set_yscale('log')
            ax.grid(True, alpha=0.3, linewidth=0.3)
            if i == 0:
                ax.set_title(f'K{K}N{N}')
            if j == 0:
                ax.set_ylabel(f'{WL_LABEL[wl]}\nLatency (cyc)')
            if i == 3:
                ax.set_xlabel(r'Rate ($\times$ base)')
    handles, labels = None, None
    for ax_row in axes:
        for ax in ax_row:
            h, l = ax.get_legend_handles_labels()
            if h:
                handles, labels = h, l
                break
        if handles: break
    if handles:
        fig.legend(handles, labels, loc='upper center', ncol=4, bbox_to_anchor=(0.5, 1.005),
                   frameon=True, fontsize=6)
    plt.tight_layout(rect=[0, 0, 1, 0.98])
    out_pdf = FIG_DIR/'fig_rate_16panel.pdf'; out_png = FIG_DIR/'fig_rate_16panel.png'
    plt.savefig(out_pdf, bbox_inches='tight', dpi=300)
    plt.savefig(out_png, bbox_inches='tight', dpi=150)
    plt.close()
    print(f'Saved: {out_pdf}')


def fig_throughput_16panel():
    sweep = json.load(open(R/'rate_sweep.json'))
    by_cell = {(r['workload'], r['K'], r['N']): r for r in sweep}
    fig, axes = plt.subplots(4, 4, figsize=(7.2, 7.5))
    for i, wl in enumerate(WL_ORDER):
        for j, (K, N) in enumerate(KN_ORDER):
            ax = axes[i][j]
            r = by_cell.get((wl, K, N))
            if r is None:
                ax.text(0.5, 0.5, 'no data', ha='center', va='center',
                        transform=ax.transAxes, fontsize=6, color='gray')
                ax.set_xticks([]); ax.set_yticks([])
            else:
                rates = r['rates']
                rates_mult = [1, 2, 3, 4]
                for m in ['adj_uniform', 'greedy', 'fbfly', 'rl_ws']:
                    tps = r[m]['throughput']
                    ratios = [100*t/x for t, x in zip(tps, rates)]
                    s = METHOD_STYLE[m]
                    ax.plot(rates_mult, ratios, color=s['color'], marker=s['marker'], linestyle=s['ls'],
                            label=s['label'], markersize=2.5, linewidth=0.9)
                ax.set_xticks(rates_mult)
                ax.set_ylim(70, 105)
            ax.grid(True, alpha=0.3, linewidth=0.3)
            if i == 0:
                ax.set_title(f'K{K}N{N}')
            if j == 0:
                ax.set_ylabel(f'{WL_LABEL[wl]}\nDelivered / Offered (%)')
            if i == 3:
                ax.set_xlabel(r'Rate ($\times$ base)')
    handles, labels = axes[-1][-1].get_legend_handles_labels()
    if handles:
        fig.legend(handles, labels, loc='upper center', ncol=4, bbox_to_anchor=(0.5, 1.005),
                   frameon=True, fontsize=6)
    plt.tight_layout(rect=[0, 0, 1, 0.98])
    out_pdf = FIG_DIR/'fig_throughput_16panel.pdf'; out_png = FIG_DIR/'fig_throughput_16panel.png'
    plt.savefig(out_pdf, bbox_inches='tight', dpi=300)
    plt.savefig(out_png, bbox_inches='tight', dpi=150)
    plt.close()
    print(f'Saved: {out_pdf}')


if __name__ == '__main__':
    fig_bpp_sweep_16panel()
    fig_rate_sweep_16panel()
    fig_throughput_16panel()
