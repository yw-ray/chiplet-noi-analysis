"""Generate all paper figures consistently (Fig 3, 3b, 4, 5, 5b).

Uses unified color/marker/linestyle for the 4 placement methods across all figures.
"""
import json
from pathlib import Path
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import spearmanr, kendalltau

plt.rcParams.update({
    'font.size': 6,
    'axes.titlesize': 7,
    'axes.labelsize': 6,
    'xtick.labelsize': 5.5,
    'ytick.labelsize': 5.5,
    'legend.fontsize': 5.5,
    'font.family': 'serif',
})

R = Path('results/ml_placement')
FIG_DIR = Path('paper/figures')

METHOD_STYLE = {
    'adj_uniform': {'color': 'tab:gray', 'marker': 's', 'ls': '--', 'label': 'Adj Uniform'},
    'greedy':      {'color': 'tab:blue', 'marker': 'o', 'ls': '-',  'label': 'Greedy'},
    'fbfly':       {'color': 'tab:orange','marker': '^', 'ls': '-.', 'label': 'FBfly'},
    'rl_ws':       {'color': 'tab:red',  'marker': 'D', 'ls': '-',  'label': 'RL-WS (ours)'},
}

WL_ORDER = ['tree_allreduce', 'hybrid_tp_pp', 'uniform_random', 'moe']
WL_TITLE = {
    'tree_allreduce':  'Tree All-Reduce (NL 42%)',
    'hybrid_tp_pp':    'Hybrid TP+PP (NL 77%)',
    'uniform_random':  'Uniform Random (NL 89%)',
    'moe':             'MoE Skewed (NL 91%)',
}

# ----------- Data loading -----------
comp = json.load(open(R/'ml_comparison_fast.json'))     # adj/greedy/gnn/rl_agent
warm = json.load(open(R/'ml_comparison_warmstart.json')) # rl_warmstart (our main)
fbfly = json.load(open(R/'butterfly_baseline.json'))    # fbfly 3 cells K32N8
sweep = json.load(open(R/'rate_sweep.json'))            # 4 cells at K32N8 base rate
lam = json.load(open(R/'lambda_sensitivity.json'))

# Index warmstart by (wl, K, N, bpp)
warm_idx = {(r['workload'], r['K'], r['N'], r['budget_per_pair']): r for r in warm}
# Index comp by (wl, K, N, bpp)
comp_idx = {(r['workload'], r['K'], r['N'], r['budget_per_pair']): r for r in comp}

def get_latencies(wl, K, N, bpp):
    """Return dict of method -> latency for the cell if available."""
    out = {}
    c = comp_idx.get((wl, K, N, bpp))
    w = warm_idx.get((wl, K, N, bpp))
    if c:
        out['adj_uniform'] = c['adj_uniform']['latency']
        out['greedy'] = c['express_greedy']['latency']
    if w:
        out['rl_ws'] = w['rl_warmstart']['latency']
    # fbfly only at K32N8 from butterfly_baseline + rate_sweep
    if K == 32 and N == 8:
        # Prefer butterfly_baseline (exact iso-max_dist check)
        for fb in fbfly:
            if (fb['workload'], fb['K'], fb['N'], fb['budget_per_pair']) == (wl, K, N, bpp):
                out['fbfly'] = fb['L_fbfly']
                break
        # Fallback to rate_sweep rate 1x
        if 'fbfly' not in out:
            for rs in sweep:
                if (rs['workload'], rs['K'], rs['N'], rs['budget_per_pair']) == (wl, K, N, bpp):
                    out['fbfly'] = rs['fbfly']['latency'][0]
                    out['adj_uniform'] = rs['adj_uniform']['latency'][0]
                    out['greedy'] = rs['greedy']['latency'][0]
                    out['rl_ws'] = rs['rl_ws']['latency'][0]
                    break
    return out

# ======================================================================
# Fig 3 — Cost-saving vs budget (bpp sweep at K=32, N=8)
# ======================================================================
print("Generating Fig 3: bpp sweep at K32N8...")
fig, axes = plt.subplots(1, 4, figsize=(7.2, 1.8), sharey=False)
for ax, wl in zip(axes, WL_ORDER):
    # Collect data at K=32 N=8 for all available bpp
    bpps = []
    data_by_method = defaultdict(lambda: ([], []))  # method -> (bpps, lat)
    for bpp in [2, 4]:  # K=32 has bpp 2, 4
        lats = get_latencies(wl, 32, 8, bpp)
        for m, v in lats.items():
            data_by_method[m][0].append(bpp)
            data_by_method[m][1].append(v)
    for m, (bp, lat) in data_by_method.items():
        s = METHOD_STYLE[m]
        ax.plot(bp, lat, color=s['color'], marker=s['marker'], linestyle=s['ls'],
                label=s['label'], markersize=3.5, linewidth=1.0)
    ax.set_title(WL_TITLE[wl])
    ax.set_xlabel(r'Budget per pair (bpp, $\times$)')
    ax.set_xticks([2, 4])
    ax.grid(True, alpha=0.3, linewidth=0.3)
    ax.set_ylabel('Latency (cycles)')
axes[0].legend(loc='upper right', frameon=True, handlelength=2.0,
               borderpad=0.3, labelspacing=0.25)
plt.tight_layout(w_pad=0.3)
plt.savefig(FIG_DIR/'fig_bpp_sweep.pdf', bbox_inches='tight', dpi=300)
plt.savefig(FIG_DIR/'fig_bpp_sweep.png', bbox_inches='tight', dpi=150)
plt.close()

# ======================================================================
# Fig 3b — K·N scaling of saving% (at best bpp for each cell)
# ======================================================================
print("Generating Fig 3b: K/N scaling...")
KN_ORDER = [(16,4), (16,8), (32,4), (32,8)]
KN_LABEL = [f'K{k}N{n}' for k,n in KN_ORDER]

fig, axes = plt.subplots(1, 4, figsize=(7.2, 1.8), sharey=False)
for ax, wl in zip(axes, WL_ORDER):
    # For each K/N, find the BEST bpp for RL-WS (max saving)
    for m in ['greedy', 'fbfly', 'rl_ws']:
        xs, ys = [], []
        for i, (K, N) in enumerate(KN_ORDER):
            # Pick best bpp (highest bpp available)
            bpps_avail = [bpp for bpp in [2,3,4,7] if (wl, K, N, bpp) in comp_idx]
            if not bpps_avail:
                continue
            bpp = max(bpps_avail)
            lats = get_latencies(wl, K, N, bpp)
            if 'adj_uniform' not in lats or m not in lats:
                continue
            sv = (lats['adj_uniform'] - lats[m]) / lats['adj_uniform'] * 100
            xs.append(i)
            ys.append(sv)
        s = METHOD_STYLE[m]
        ax.plot(xs, ys, color=s['color'], marker=s['marker'], linestyle=s['ls'],
                label=s['label'], markersize=3.8, linewidth=1.0)
    ax.set_title(WL_TITLE[wl])
    ax.set_xticks(range(4))
    ax.set_xticklabels(KN_LABEL, rotation=30, ha='right')
    ax.set_xlabel('Chiplet grid (K, N)')
    ax.set_ylabel('Saving vs Adj (%)')
    ax.grid(True, alpha=0.3, linewidth=0.3)
    ax.axhline(0, color='black', linewidth=0.4, alpha=0.5)
axes[0].legend(loc='upper left', frameon=True, handlelength=2.0,
               borderpad=0.3, labelspacing=0.25)
plt.tight_layout(w_pad=0.3)
plt.savefig(FIG_DIR/'fig_kn_scaling.pdf', bbox_inches='tight', dpi=300)
plt.savefig(FIG_DIR/'fig_kn_scaling.png', bbox_inches='tight', dpi=150)
plt.close()

# ======================================================================
# Fig 4 — NL% vs saving% scatter (40 config predictor validity)
# ======================================================================
print("Generating Fig 4: NL% scatter...")
NL_PCT = {
    'tree_allreduce': 42,
    'hybrid_tp_pp': 77,
    'uniform_random': 89,
    'moe': 91,
}
WL_COLOR = {
    'tree_allreduce': 'tab:green',
    'hybrid_tp_pp': 'tab:purple',
    'uniform_random': 'tab:brown',
    'moe': 'tab:red',
}

fig, ax = plt.subplots(1, 1, figsize=(3.5, 2.5))
xs, ys = [], []
for wl in WL_ORDER:
    xw, yw = [], []
    for r in comp:
        if r['workload'] != wl:
            continue
        w = warm_idx.get((r['workload'], r['K'], r['N'], r['budget_per_pair']))
        if not w:
            continue
        L_adj = r['adj_uniform']['latency']
        L_rl = w['rl_warmstart']['latency']
        sv = (L_adj - L_rl)/L_adj*100
        xw.append(NL_PCT[wl] + np.random.uniform(-1.5, 1.5))  # jitter for visibility
        yw.append(sv)
        xs.append(NL_PCT[wl]); ys.append(sv)
    ax.scatter(xw, yw, color=WL_COLOR[wl], label=WL_TITLE[wl].split(' (')[0],
               s=20, alpha=0.7, edgecolors='black', linewidth=0.3)
rho, _ = spearmanr(xs, ys)
tau, _ = kendalltau(xs, ys)
ax.set_xlabel('Non-Locality fraction (NL %)')
ax.set_ylabel('RL-WS Saving vs Adj (%)')
ax.set_title(f'NL% predictor (Spearman ρ={rho:.3f}, Kendall τ={tau:.3f}, n={len(xs)})')
ax.grid(True, alpha=0.3, linewidth=0.3)
ax.legend(loc='lower right', frameon=True, fontsize=5.5, labelspacing=0.25)
plt.tight_layout()
plt.savefig(FIG_DIR/'fig_nl_scatter.pdf', bbox_inches='tight', dpi=300)
plt.savefig(FIG_DIR/'fig_nl_scatter.png', bbox_inches='tight', dpi=150)
plt.close()

# ======================================================================
# Fig 5b — MoE delivered-throughput ratio vs rate (only meaningful panel)
# ======================================================================
print("Generating Fig 5b: MoE throughput ratio...")
moe_cell = next(r for r in sweep if r['workload'] == 'moe')
rates = moe_cell['rates']
rates_mult = [1, 2, 3, 4]

fig, ax = plt.subplots(1, 1, figsize=(3.5, 2.0))
for m in ['adj_uniform', 'greedy', 'fbfly', 'rl_ws']:
    tps = moe_cell[m]['throughput']
    ratio = [tp/rt*100 for tp, rt in zip(tps, rates)]
    s = METHOD_STYLE[m]
    ax.plot(rates_mult, ratio, color=s['color'], marker=s['marker'], linestyle=s['ls'],
            label=s['label'], markersize=4, linewidth=1.0)
ax.set_xlabel(r'Injection rate ($\times$ base)')
ax.set_ylabel('Delivered / Offered (%)')
ax.set_title('MoE Skewed — Throughput efficiency (K32N8 b4x)')
ax.set_xticks(rates_mult)
ax.set_ylim(70, 102)
ax.grid(True, alpha=0.3, linewidth=0.3)
ax.legend(loc='lower left', frameon=True, fontsize=5.5, labelspacing=0.25)
plt.tight_layout()
plt.savefig(FIG_DIR/'fig_moe_throughput.pdf', bbox_inches='tight', dpi=300)
plt.savefig(FIG_DIR/'fig_moe_throughput.png', bbox_inches='tight', dpi=150)
plt.close()

print("\nAll figures generated:")
for f in sorted(FIG_DIR.glob('fig_*.png')):
    print(f"  {f}")
