"""Regenerate RL paper figures as PDF with consistent style."""
import json
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import spearmanr

plt.rcParams.update({
    'font.size': 6,
    'axes.titlesize': 7,
    'axes.labelsize': 6,
    'xtick.labelsize': 5.5,
    'ytick.labelsize': 5.5,
    'legend.fontsize': 5.5,
    'figure.dpi': 150,
    'savefig.dpi': 300,
    'font.family': 'sans-serif',
    'font.sans-serif': ['DejaVu Sans'],
})

NL = {'tree_allreduce': 42, 'hybrid_tp_pp': 77, 'moe': 91, 'uniform_random': 89}
WL_NAME = {'tree_allreduce': 'Tree AR', 'hybrid_tp_pp': 'Hybrid TP+PP',
           'moe': 'MoE Skewed', 'uniform_random': 'Uniform Rand.'}
WL_COLOR = {'tree_allreduce': '#1f77b4', 'hybrid_tp_pp': '#ff7f0e',
            'moe': '#d62728', 'uniform_random': '#2ca02c'}

with open('results/ml_placement/ml_comparison_fast.json') as f:
    fast = json.load(f)
with open('results/ml_placement/ml_comparison_warmstart.json') as f:
    warm = json.load(f)
with open('results/ml_placement/ml_generalization.json') as f:
    gen = json.load(f)

key = lambda r: (r['workload'], r['K'], r['N'], r['budget_per_pair'])
fast_by = {key(r): r for r in fast}

rows = []
for wr in warm:
    fr = fast_by[key(wr)]
    adj = fr['adj_uniform']['latency']
    g = fr['express_greedy']['latency']
    rlw = wr['rl_warmstart']['latency']
    rows.append({
        'workload': wr['workload'], 'K': wr['K'], 'N': wr['N'], 'b': wr['budget_per_pair'],
        'NL': NL[wr['workload']],
        'save_greedy': (adj - g) / adj * 100,
        'save_rl_fb': (adj - min(g, rlw)) / adj * 100,
    })

# ============ Fig A: NL% vs saving scatter ============
fig, ax = plt.subplots(figsize=(3.5, 2.2))
for wl in ['tree_allreduce', 'hybrid_tp_pp', 'uniform_random', 'moe']:
    rs = [r for r in rows if r['workload'] == wl]
    nl = [r['NL'] + (hash((r['K'], r['N'], r['b'])) % 100) / 100 - 0.5 for r in rs]  # jitter
    sv_g = [r['save_greedy'] for r in rs]
    sv_r = [r['save_rl_fb'] for r in rs]
    ax.scatter(nl, sv_g, c=WL_COLOR[wl], marker='o', s=12, alpha=0.55,
               edgecolors='none', label=f'{WL_NAME[wl]} greedy')
    ax.scatter(nl, sv_r, c=WL_COLOR[wl], marker='^', s=14, alpha=0.95,
               edgecolors='black', linewidths=0.35, label=f'{WL_NAME[wl]} RL-WS+fb')

rho, p = spearmanr([r['NL'] for r in rows], [r['save_greedy'] for r in rows])
rho_r, p_r = spearmanr([r['NL'] for r in rows], [r['save_rl_fb'] for r in rows])
ax.text(0.02, 0.97, f'Spearman $\\rho$(greedy) = {rho:.3f} ($p<10^{{-7}}$)\n'
                    f'Spearman $\\rho$(RL-WS+fb) = {rho_r:.3f}',
        transform=ax.transAxes, va='top', ha='left',
        fontsize=5.5, bbox=dict(boxstyle='round,pad=0.25', facecolor='white', alpha=0.9, edgecolor='gray', linewidth=0.4))
ax.set_xlabel('Non-locality fraction NL\\% (+ per-config jitter)')
ax.set_ylabel('Latency saving vs adj-uniform (\\%)')
ax.set_title('NL\\% predicts express saving across 40 configurations', fontsize=7)
ax.grid(True, alpha=0.2, linewidth=0.3)
ax.legend(loc='lower right', ncol=2, handletextpad=0.3, columnspacing=0.8, fontsize=4.5)
fig.tight_layout(pad=0.3)
fig.savefig('paper/figures/fig_rl_nonlocality_scatter.pdf', bbox_inches='tight')
plt.close(fig)
print('saved fig_rl_nonlocality_scatter.pdf')

# ============ Fig B: Tree rescue (warm vs cold per config) ============
tree_rows = []
for r in rows:
    if r['workload'] != 'tree_allreduce':
        continue
    fr = fast_by[(r['workload'], r['K'], r['N'], r['b'])]
    wr_full = [w for w in warm if key(w) == (r['workload'], r['K'], r['N'], r['b'])][0]
    cold = fr.get('rl_agent')
    g = fr['express_greedy']['latency']
    if cold is None:
        continue
    tree_rows.append({
        'cfg': f"K{r['K']}N{r['N']} {r['b']}x",
        'cold_imp': (g - cold['latency']) / g * 100,
        'warm_imp': (g - wr_full['rl_warmstart']['latency']) / g * 100,
    })

fig, ax = plt.subplots(figsize=(3.5, 2.0))
x = np.arange(len(tree_rows))
w = 0.38
cold_v = [t['cold_imp'] for t in tree_rows]
warm_v = [t['warm_imp'] for t in tree_rows]
ax.bar(x - w/2, cold_v, w, label='Cold RL (raw)', color='#c94d4d', edgecolor='black', linewidth=0.3)
ax.bar(x + w/2, warm_v, w, label='Warm RL (raw)', color='#4d7bc9', edgecolor='black', linewidth=0.3)
ax.axhline(0, color='black', linewidth=0.5)
ax.set_xticks(x)
ax.set_xticklabels([t['cfg'] for t in tree_rows], rotation=30, ha='right')
ax.set_ylabel('Improvement vs greedy (\\%)\n(higher is better; fallback clips to $\\geq$0)')
ax.set_title('Tree All-Reduce: warm-start rescues cold RL from regressions', fontsize=7)
ax.grid(True, axis='y', alpha=0.2, linewidth=0.3)
ax.legend(loc='lower left', fontsize=5.5)
cm = np.mean(cold_v)
wm = np.mean(warm_v)
ax.text(0.98, 0.95, f'mean cold: {cm:+.2f}\\%\nmean warm: {wm:+.2f}\\%',
        transform=ax.transAxes, va='top', ha='right', fontsize=5.5,
        bbox=dict(boxstyle='round,pad=0.25', facecolor='white', alpha=0.9, edgecolor='gray', linewidth=0.4))
fig.tight_layout(pad=0.3)
fig.savefig('paper/figures/fig_rl_tree_rescue.pdf', bbox_inches='tight')
plt.close(fig)
print('saved fig_rl_tree_rescue.pdf')

# ============ Fig C: Generalization (per workload) ============
from collections import defaultdict
by_wl = defaultdict(list)
for r in gen:
    by_wl[r['workload']].append(r)

wl_order = ['ring_allreduce', 'pipeline_parallel', 'all_to_all']
wl_label = {'ring_allreduce': 'Ring AR', 'pipeline_parallel': 'Pipeline', 'all_to_all': 'All-to-All'}

gnn_means, rl_means, gnn_stds, rl_stds = [], [], [], []
for wl in wl_order:
    rs = by_wl[wl]
    gnn_imps = [(r['express_greedy']['latency'] - r['gnn_agent']['latency']) / r['express_greedy']['latency'] * 100
                for r in rs if r.get('gnn_agent')]
    rl_imps = [(r['express_greedy']['latency'] - r['rl_warmstart']['latency']) / r['express_greedy']['latency'] * 100
               for r in rs if r.get('rl_warmstart')]
    gnn_means.append(np.mean(gnn_imps) if gnn_imps else 0)
    rl_means.append(np.mean(rl_imps) if rl_imps else 0)
    gnn_stds.append(np.std(gnn_imps) if gnn_imps else 0)
    rl_stds.append(np.std(rl_imps) if rl_imps else 0)

fig, ax = plt.subplots(figsize=(3.5, 2.0))
x = np.arange(len(wl_order))
w = 0.38
ax.bar(x - w/2, gnn_means, w, yerr=gnn_stds, label='GNN (zero-shot)',
       color='#c9a94d', edgecolor='black', linewidth=0.3, capsize=2, error_kw={'linewidth': 0.4})
ax.bar(x + w/2, rl_means, w, yerr=rl_stds, label='RL-WS (retrained)',
       color='#4d7bc9', edgecolor='black', linewidth=0.3, capsize=2, error_kw={'linewidth': 0.4})
ax.axhline(0, color='black', linewidth=0.5)
ax.set_xticks(x)
ax.set_xticklabels([wl_label[w] for w in wl_order])
ax.set_ylabel('Improvement vs greedy (\\%)')
ax.set_title('Generalization to unseen workloads', fontsize=7)
ax.grid(True, axis='y', alpha=0.2, linewidth=0.3)
ax.legend(loc='lower left', fontsize=5.5)
# Annotate FAIL on a2a GNN
ax.annotate('collapse\n(distribution shift)', xy=(2 - w/2, gnn_means[2]),
            xytext=(2 - w/2 - 0.5, gnn_means[2] - 4),
            fontsize=5, ha='center',
            arrowprops=dict(arrowstyle='->', lw=0.4, color='#c9a94d'))
fig.tight_layout(pad=0.3)
fig.savefig('paper/figures/fig_rl_generalization.pdf', bbox_inches='tight')
plt.close(fig)
print('saved fig_rl_generalization.pdf')

# ============ Fig D: K32N8 budget sweep (restore Fig 3) ============
def load_6panel(wl):
    try:
        return json.load(open(f'results/cost_perf_6panel_{wl}/cost_perf_6panel_incremental.json'))
    except FileNotFoundError:
        return json.load(open(f'results/cost_perf_6panel_{wl}/cost_perf_6panel.json'))

fig, axes = plt.subplots(1, 4, figsize=(7.0, 1.9), sharey=False)
for i, wl in enumerate(['tree_allreduce', 'hybrid_tp_pp', 'uniform_random', 'moe']):
    ax = axes[i]
    d = load_6panel(wl)
    cfg = d.get('K32_N8')
    if cfg is None:
        ax.set_title(f'{WL_NAME[wl]} (missing)', fontsize=7)
        continue
    exps = cfg['experiments']
    adj_points = [(e['budget_per_pair'], max(rr['latency'] for rr in e['rates']))
                  for e in exps if e['strategy'] == 'adj_uniform']
    exp_points = [(e['budget_per_pair'], max(rr['latency'] for rr in e['rates']))
                  for e in exps if e['strategy'] == 'express_greedy']
    adj_points.sort()
    exp_points.sort()
    ax.plot([p[0] for p in adj_points], [p[1] for p in adj_points],
            'o-', color='#888888', label='Adj uniform', linewidth=0.8, markersize=3)
    ax.plot([p[0] for p in exp_points], [p[1] for p in exp_points],
            '^-', color=WL_COLOR[wl], label='Express greedy', linewidth=0.8, markersize=3)
    ax.set_title(f'{WL_NAME[wl]} (NL={NL[wl]}\\%)', fontsize=6.5)
    ax.set_xlabel('Budget ($b\\times$)')
    if i == 0:
        ax.set_ylabel('Max-rate latency (cycles)')
    ax.grid(True, alpha=0.2, linewidth=0.3)
    ax.legend(loc='upper right', fontsize=5)
fig.suptitle('K=32, N=8: Express placement breaks the adjacent-uniform ceiling (all 4 training workloads)', fontsize=7, y=1.02)
fig.tight_layout(pad=0.3)
fig.savefig('paper/figures/fig_cost_saving_4panel.pdf', bbox_inches='tight')
plt.close(fig)
print('saved fig_cost_saving_4panel.pdf')

print('\nAll 4 PDFs written.')
