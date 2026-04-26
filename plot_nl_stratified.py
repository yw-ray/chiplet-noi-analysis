"""Generate fig_rl_nonlocality_scatter.pdf from v5_full data.

Shows NL%-stratified comparison: greedy vs FBfly vs RL-WS across 28 cells.
"""
import json
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib as mpl

mpl.rcParams.update({
    'font.size': 6, 'axes.titlesize': 7, 'axes.labelsize': 6,
    'xtick.labelsize': 5.5, 'ytick.labelsize': 5.5, 'legend.fontsize': 5.5,
    'lines.linewidth': 0.8, 'lines.markersize': 4,
})

R = Path('results/ml_placement')
v5 = json.load(open(R / 'rl_v5.json'))

NL = {'moe': 91, 'all_to_all': 90, 'uniform_random': 89, 'hybrid_tp_pp': 77,
      'tree_allreduce': 42, 'ring_allreduce': 13, 'pipeline_parallel': 10}

rows = []
for r in v5:
    if not r.get('ours_v5'):
        continue
    wl = r['workload']
    K, N, bpp = r['K'], r['N'], r['budget_per_pair']
    adj = max(r['adj_uniform']['latency'])
    g = max(r['greedy']['latency'])
    fb = max(r['fbfly']['latency'])
    ours = max(r['ours_v5']['latency'])
    rows.append({
        'wl': wl, 'NL%': NL[wl], 'K': K, 'N': N, 'bpp': bpp,
        's_g': (adj - g) / adj * 100,
        's_fb': (adj - fb) / adj * 100,
        's_v5': (adj - ours) / adj * 100,
    })

fig, ax = plt.subplots(1, 1, figsize=(3.5, 2.6))
xs_g = [r['NL%'] for r in rows]; ys_g = [r['s_g'] for r in rows]
xs_fb = [r['NL%'] for r in rows]; ys_fb = [r['s_fb'] for r in rows]
xs_v5 = [r['NL%'] for r in rows]; ys_v5 = [r['s_v5'] for r in rows]

ax.scatter(xs_g, ys_g, marker='o', s=22, c='#1f77b4', alpha=0.65, label='Greedy', edgecolors='none')
ax.scatter(xs_fb, ys_fb, marker='s', s=22, c='#2ca02c', alpha=0.65, label='FBfly', edgecolors='none')
ax.scatter(xs_v5, ys_v5, marker='D', s=22, c='#d62728', alpha=0.85, label='RL-WS', edgecolors='black', linewidths=0.4)

# Stratification line
ax.axvline(x=63, color='gray', linestyle='--', linewidth=0.5, alpha=0.6)
ax.text(30, 95, 'Low-NL\n(FBfly ≈ RL-WS)', fontsize=5, ha='center', color='gray')
ax.text(85, 95, 'High-NL\n(RL-WS strict beat)', fontsize=5, ha='center', color='gray')

ax.set_xlabel('Non-Locality Fraction NL\\% (at K=32)')
ax.set_ylabel('Saving vs Adj-Uniform (\\%)')
ax.set_title('NL\\% predicts when learned placement is essential')
ax.legend(loc='lower right', frameon=False)
ax.grid(True, alpha=0.3, linewidth=0.3)
ax.set_xlim(0, 100)
ax.set_ylim(-5, 100)

plt.tight_layout()
plt.savefig('paper/figures/fig_rl_nonlocality_scatter.pdf', dpi=300, bbox_inches='tight')
plt.savefig('paper/figures/fig_rl_nonlocality_scatter.png', dpi=200, bbox_inches='tight')
print(f'Saved fig_rl_nonlocality_scatter.{{pdf,png}} ({len(rows)} cells)')
