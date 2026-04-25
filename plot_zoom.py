"""Re-plot Fig 3 / Fig 3b with tighter Y-axis for visibility."""
import json
from pathlib import Path
from collections import defaultdict
import matplotlib.pyplot as plt

plt.rcParams.update({
    'font.size': 6, 'axes.titlesize': 7, 'axes.labelsize': 6,
    'xtick.labelsize': 5.5, 'ytick.labelsize': 5.5,
    'legend.fontsize': 5.5, 'font.family': 'serif',
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
WL_TITLE = {
    'tree_allreduce':  'Tree All-Reduce (NL 42%)',
    'hybrid_tp_pp':    'Hybrid TP+PP (NL 77%)',
    'uniform_random':  'Uniform Random (NL 89%)',
    'moe':             'MoE Skewed (NL 91%)',
}

comp = json.load(open(R/'ml_comparison_fast.json'))
warm = json.load(open(R/'ml_comparison_warmstart.json'))
fbfly = json.load(open(R/'butterfly_baseline.json'))
sweep = json.load(open(R/'rate_sweep.json'))

comp_idx = {(r['workload'], r['K'], r['N'], r['budget_per_pair']): r for r in comp}
warm_idx = {(r['workload'], r['K'], r['N'], r['budget_per_pair']): r for r in warm}

def get_lats(wl, K, N, bpp):
    out = {}
    c = comp_idx.get((wl, K, N, bpp))
    w = warm_idx.get((wl, K, N, bpp))
    if c:
        out['adj_uniform'] = c['adj_uniform']['latency']
        out['greedy'] = c['express_greedy']['latency']
    if w:
        out['rl_ws'] = w['rl_warmstart']['latency']
    if K == 32 and N == 8:
        for fb in fbfly:
            if (fb['workload'], fb['K'], fb['N'], fb['budget_per_pair']) == (wl, K, N, bpp):
                out['fbfly'] = fb['L_fbfly']; break
        if 'fbfly' not in out:
            for rs in sweep:
                if (rs['workload'], rs['K'], rs['N'], rs['budget_per_pair']) == (wl, K, N, bpp):
                    out['fbfly'] = rs['fbfly']['latency'][0]
                    out['adj_uniform'] = rs['adj_uniform']['latency'][0]
                    out['greedy'] = rs['greedy']['latency'][0]
                    out['rl_ws'] = rs['rl_ws']['latency'][0]; break
    return out

# =====================================================================
# Fig 3 v2 — Drop adj, focus on greedy/FBfly/RL-WS at K=32 N=8
# =====================================================================
print("Generating Fig 3 v2: express methods only, tight Y...")
fig, axes = plt.subplots(1, 4, figsize=(7.2, 1.8))
for ax, wl in zip(axes, WL_ORDER):
    data = defaultdict(lambda: ([], []))
    for bpp in [2, 4]:
        lats = get_lats(wl, 32, 8, bpp)
        for m in ['greedy', 'fbfly', 'rl_ws']:
            if m in lats:
                data[m][0].append(bpp); data[m][1].append(lats[m])
    for m, (bp, lt) in data.items():
        s = METHOD_STYLE[m]
        ax.plot(bp, lt, color=s['color'], marker=s['marker'], linestyle=s['ls'],
                label=s['label'], markersize=4, linewidth=1.1)
    # Tight Y per panel
    all_v = [v for _, (_, ys) in data.items() for v in ys]
    lo, hi = min(all_v), max(all_v)
    pad = (hi - lo) * 0.15
    ax.set_ylim(lo - pad, hi + pad)
    ax.set_title(WL_TITLE[wl])
    ax.set_xlabel(r'Budget per pair ($\times$)')
    ax.set_xticks([2, 4])
    ax.grid(True, alpha=0.3, linewidth=0.3)
    ax.set_ylabel('Latency (cycles)')
    # Annotate adj reference at top
    adj_val = get_lats(wl, 32, 8, 4).get('adj_uniform')
    if adj_val:
        ax.text(0.98, 0.95, f'adj={adj_val:.0f}', transform=ax.transAxes,
                ha='right', va='top', fontsize=5, color='gray',
                bbox=dict(facecolor='white', edgecolor='gray', boxstyle='round,pad=0.2', linewidth=0.3))
axes[0].legend(loc='lower left', frameon=True, handlelength=2.0,
               borderpad=0.3, labelspacing=0.25)
plt.tight_layout(w_pad=0.3)
plt.savefig(FIG_DIR/'fig_bpp_sweep_v2.pdf', bbox_inches='tight', dpi=300)
plt.savefig(FIG_DIR/'fig_bpp_sweep_v2.png', bbox_inches='tight', dpi=150)
plt.close()

# =====================================================================
# Fig 3 v3 — Use K16N8 (3-point curve) as the main panel
# =====================================================================
print("Generating Fig 3 v3: K16N8 3-point curves (with bpp=7)...")
fig, axes = plt.subplots(1, 4, figsize=(7.2, 1.8))
for ax, wl in zip(axes, WL_ORDER):
    data = defaultdict(lambda: ([], []))
    for bpp in [2, 4, 7]:
        lats = get_lats(wl, 16, 8, bpp)
        for m in ['greedy', 'rl_ws']:  # FBfly not measured at K16N8
            if m in lats:
                data[m][0].append(bpp); data[m][1].append(lats[m])
    for m, (bp, lt) in data.items():
        s = METHOD_STYLE[m]
        ax.plot(bp, lt, color=s['color'], marker=s['marker'], linestyle=s['ls'],
                label=s['label'], markersize=4, linewidth=1.1)
    all_v = [v for _, (_, ys) in data.items() for v in ys]
    if all_v:
        lo, hi = min(all_v), max(all_v)
        pad = (hi - lo) * 0.15
        ax.set_ylim(lo - pad, hi + pad)
    ax.set_title(f'{WL_TITLE[wl]}  [K16N8]')
    ax.set_xlabel(r'Budget per pair ($\times$)')
    ax.set_xticks([2, 4, 7])
    ax.grid(True, alpha=0.3, linewidth=0.3)
    ax.set_ylabel('Latency (cycles)')
    adj_val = get_lats(wl, 16, 8, 4).get('adj_uniform')
    if adj_val:
        ax.text(0.98, 0.95, f'adj={adj_val:.0f}', transform=ax.transAxes,
                ha='right', va='top', fontsize=5, color='gray',
                bbox=dict(facecolor='white', edgecolor='gray', boxstyle='round,pad=0.2', linewidth=0.3))
axes[0].legend(loc='upper right', frameon=True, handlelength=2.0,
               borderpad=0.3, labelspacing=0.25)
plt.tight_layout(w_pad=0.3)
plt.savefig(FIG_DIR/'fig_bpp_sweep_k16n8.pdf', bbox_inches='tight', dpi=300)
plt.savefig(FIG_DIR/'fig_bpp_sweep_k16n8.png', bbox_inches='tight', dpi=150)
plt.close()

# =====================================================================
# Fig 3b v2 — K/N scaling, tighter Y per panel
# =====================================================================
print("Generating Fig 3b v2: tighter Y-range...")
KN_ORDER = [(16,4), (16,8), (32,4), (32,8)]
KN_LABEL = [f'K{k}N{n}' for k,n in KN_ORDER]

fig, axes = plt.subplots(1, 4, figsize=(7.2, 1.9))
for ax, wl in zip(axes, WL_ORDER):
    method_data = {}
    for m in ['greedy', 'fbfly', 'rl_ws']:
        xs, ys = [], []
        for i, (K, N) in enumerate(KN_ORDER):
            bpps_avail = [bpp for bpp in [2,3,4,7] if (wl, K, N, bpp) in comp_idx]
            if not bpps_avail:
                continue
            bpp = max(bpps_avail)
            lats = get_lats(wl, K, N, bpp)
            if 'adj_uniform' not in lats or m not in lats:
                continue
            sv = (lats['adj_uniform'] - lats[m]) / lats['adj_uniform'] * 100
            xs.append(i); ys.append(sv)
        method_data[m] = (xs, ys)
        s = METHOD_STYLE[m]
        ax.plot(xs, ys, color=s['color'], marker=s['marker'], linestyle=s['ls'],
                label=s['label'], markersize=4.5, linewidth=1.1)
    # tight Y per panel (only greedy/RL which have full 4 points)
    all_v = [v for _, (_, ys) in method_data.items() for v in ys]
    if all_v:
        lo, hi = min(all_v), max(all_v)
        pad = (hi - lo) * 0.18
        ax.set_ylim(lo - pad, hi + pad)
    ax.set_title(WL_TITLE[wl])
    ax.set_xticks(range(4))
    ax.set_xticklabels(KN_LABEL, rotation=30, ha='right')
    ax.set_xlabel('Chiplet grid')
    ax.set_ylabel('Saving vs Adj (%)')
    ax.grid(True, alpha=0.3, linewidth=0.3)
axes[0].legend(loc='upper left', frameon=True, handlelength=2.0,
               borderpad=0.3, labelspacing=0.25)
plt.tight_layout(w_pad=0.3)
plt.savefig(FIG_DIR/'fig_kn_scaling_v2.pdf', bbox_inches='tight', dpi=300)
plt.savefig(FIG_DIR/'fig_kn_scaling_v2.png', bbox_inches='tight', dpi=150)
plt.close()

print("Done.")
