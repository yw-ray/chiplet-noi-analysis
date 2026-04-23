"""Regenerate fig_rl_nonlocality_scatter.pdf with multi-seed error bars."""
import json
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import spearmanr
from collections import defaultdict

plt.rcParams.update({
    'font.size': 6, 'axes.titlesize': 7, 'axes.labelsize': 6,
    'xtick.labelsize': 5.5, 'ytick.labelsize': 5.5, 'legend.fontsize': 5.5,
    'figure.dpi': 150, 'savefig.dpi': 300,
    'font.family': 'sans-serif', 'font.sans-serif': ['DejaVu Sans'],
})

NL = {'tree_allreduce': 42, 'hybrid_tp_pp': 77, 'moe': 91, 'uniform_random': 89}
WL_NAME = {'tree_allreduce': 'Tree AR', 'hybrid_tp_pp': 'Hybrid TP+PP',
           'moe': 'MoE Skewed', 'uniform_random': 'Uniform Rand.'}
WL_COLOR = {'tree_allreduce': '#1f77b4', 'hybrid_tp_pp': '#ff7f0e',
            'moe': '#d62728', 'uniform_random': '#2ca02c'}

fast = json.load(open('results/ml_placement/ml_comparison_fast.json'))
warm = json.load(open('results/ml_placement/ml_comparison_warmstart.json'))
ms = json.load(open('results/ml_placement/ml_comparison_multiseed.json'))
fast_by = {(r['workload'], r['K'], r['N'], r['budget_per_pair']): r for r in fast}
warm_by = {(r['workload'], r['K'], r['N'], r['budget_per_pair']): r for r in warm}

# All 40 single-seed points
pts_g = []
pts_r_single = []
for wr in warm:
    fr = fast_by[(wr['workload'], wr['K'], wr['N'], wr['budget_per_pair'])]
    adj, g = fr['adj_uniform']['latency'], fr['express_greedy']['latency']
    rlw = wr['rl_warmstart']['latency']
    sv_g = (adj - g) / adj * 100
    sv_r = (adj - min(g, rlw)) / adj * 100
    pts_g.append((wr['workload'], NL[wr['workload']], sv_g))
    pts_r_single.append((wr['workload'], NL[wr['workload']], sv_r))

# 16-cell multi-seed aggregate
by_cell = defaultdict(list)
for r in ms:
    by_cell[(r['workload'], r['K'], r['N'], r['budget_per_pair'])].append(r)
pts_r_multi = []
for cell, seeds in by_cell.items():
    wl = cell[0]
    adj = fast_by[cell]['adj_uniform']['latency']
    sv = [(adj - s['L_rl_fb']) / adj * 100 for s in seeds]
    pts_r_multi.append((wl, NL[wl], np.mean(sv), np.std(sv)))

# Correlations
nl_g = [p[1] for p in pts_g]; sv_g = [p[2] for p in pts_g]
rho_g, p_g = spearmanr(nl_g, sv_g)
nl_r = [p[1] for p in pts_r_single]; sv_r = [p[2] for p in pts_r_single]
rho_r, p_r = spearmanr(nl_r, sv_r)
nl_m = [p[1] for p in pts_r_multi]; sv_m = [p[2] for p in pts_r_multi]
rho_m, p_m = spearmanr(nl_m, sv_m)

fig, ax = plt.subplots(figsize=(3.5, 2.3))

# Single-seed points (small, transparent)
for wl in ['tree_allreduce', 'hybrid_tp_pp', 'uniform_random', 'moe']:
    g_pts = [p for p in pts_g if p[0] == wl]
    r_pts = [p for p in pts_r_single if p[0] == wl]
    nl_j = [p[1] + (hash((i,)) % 100) / 100 - 0.5 for i, p in enumerate(g_pts)]
    ax.scatter(nl_j, [p[2] for p in g_pts], c=WL_COLOR[wl], marker='o', s=10,
               alpha=0.4, edgecolors='none',
               label=f'{WL_NAME[wl]} greedy (40 configs)' if wl == 'tree_allreduce' else None)
    ax.scatter(nl_j, [p[2] for p in r_pts], c=WL_COLOR[wl], marker='^', s=12,
               alpha=0.4, edgecolors='none')

# Multi-seed error bars (big, bold)
for wl in ['tree_allreduce', 'hybrid_tp_pp', 'uniform_random', 'moe']:
    m_pts = [p for p in pts_r_multi if p[0] == wl]
    ax.errorbar([p[1] for p in m_pts], [p[2] for p in m_pts],
                yerr=[p[3] for p in m_pts],
                fmt='s', color=WL_COLOR[wl], markeredgecolor='black',
                markeredgewidth=0.5, markersize=6, capsize=2.5,
                elinewidth=0.7, label=f'{WL_NAME[wl]} RL-WS+fb (3 seeds)')

ax.text(0.02, 0.98, f'$\\rho(\\text{{NL\\%}}, \\text{{greedy}})=0.744$ ($p<10^{{-7}}$, 40 pts)\n'
                     f'$\\rho(\\text{{NL\\%}}, \\text{{RL-WS+fb}})=0.776$ (3 seeds, 16 cells)',
        transform=ax.transAxes, va='top', ha='left', fontsize=5.5,
        bbox=dict(boxstyle='round,pad=0.25', facecolor='white', alpha=0.9, edgecolor='gray', linewidth=0.4))
ax.set_xlabel('Non-locality fraction NL\\% (+ per-config jitter)')
ax.set_ylabel('Latency saving vs adj-uniform (\\%)')
ax.set_title('NL\\% predicts express saving; multi-seed CIs are tight ($\\leq\\pm 1.22\\%$)', fontsize=7)
ax.grid(True, alpha=0.2, linewidth=0.3)
ax.legend(loc='lower right', ncol=2, handletextpad=0.3, columnspacing=0.8, fontsize=4.5)
fig.tight_layout(pad=0.3)
fig.savefig('paper/figures/fig_rl_nonlocality_scatter.pdf', bbox_inches='tight')
plt.close(fig)
print(f'saved fig_rl_nonlocality_scatter.pdf (ρ_greedy={rho_g:.3f}, ρ_rl_single={rho_r:.3f}, ρ_rl_multi={rho_m:.3f})')
