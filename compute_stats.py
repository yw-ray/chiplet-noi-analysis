"""Compute Spearman rho and mean savings for the paper."""
import json
from scipy.stats import spearmanr, pearsonr

NL = {'tree_allreduce': 42, 'hybrid_tp_pp': 77, 'moe': 91, 'uniform_random': 89}

with open('results/ml_placement/ml_comparison_fast.json') as f:
    fast = json.load(f)
with open('results/ml_placement/ml_comparison_warmstart.json') as f:
    warm = json.load(f)
with open('results/ml_placement/ml_generalization.json') as f:
    gen = json.load(f)


def key(r):
    return (r['workload'], r['K'], r['N'], r['budget_per_pair'])


fast_by = {key(r): r for r in fast}
warm_by = {key(r): r for r in warm}

rows = []
missing = 0
for k, fr in fast_by.items():
    wr = warm_by.get(k)
    if not wr:
        missing += 1
        continue
    adj = fr['adj_uniform']['latency']
    g = fr['express_greedy']['latency']
    rl_cold = fr['rl_agent']['latency'] if fr.get('rl_agent') else None
    gnn = fr['gnn_agent']['latency'] if fr.get('gnn_agent') else None
    rl_warm = wr['rl_warmstart']['latency']
    saving_greedy = (adj - g) / adj * 100
    saving_rl_warm_raw = (adj - rl_warm) / adj * 100
    saving_rl_warm_fb = (adj - min(g, rl_warm)) / adj * 100
    saving_rl_cold_raw = (adj - rl_cold) / adj * 100 if rl_cold is not None else None
    saving_rl_cold_fb = (adj - min(g, rl_cold)) / adj * 100 if rl_cold is not None else None
    saving_gnn = (adj - gnn) / adj * 100 if gnn is not None else None
    rows.append({
        'workload': fr['workload'], 'K': fr['K'], 'N': fr['N'], 'b': fr['budget_per_pair'],
        'NL': NL[fr['workload']],
        'L_adj': adj, 'L_greedy': g, 'L_rl_cold': rl_cold, 'L_rl_warm': rl_warm, 'L_gnn': gnn,
        'save_greedy': saving_greedy,
        'save_rl_warm': saving_rl_warm_raw,
        'save_rl_warm_fb': saving_rl_warm_fb,
        'save_rl_cold': saving_rl_cold_raw,
        'save_rl_cold_fb': saving_rl_cold_fb,
        'save_gnn': saving_gnn,
    })

print(f'n_configs={len(rows)}, missing={missing}')
print()

# Per-workload mean savings
print('=== Per-Workload Mean Savings (vs adj_uniform) ===')
print(f'{"workload":<18} {"NL%":<5} {"greedy":<8} {"RL-WS":<8} {"RL-WS+fb":<10} {"GNN":<8}')
for wl in ['tree_allreduce', 'hybrid_tp_pp', 'uniform_random', 'moe']:
    rs = [r for r in rows if r['workload'] == wl]
    g_m = sum(r['save_greedy'] for r in rs) / len(rs)
    rw_m = sum(r['save_rl_warm'] for r in rs) / len(rs)
    rwfb_m = sum(r['save_rl_warm_fb'] for r in rs) / len(rs)
    gnn_vals = [r['save_gnn'] for r in rs if r['save_gnn'] is not None]
    gnn_m = sum(gnn_vals) / len(gnn_vals) if gnn_vals else float('nan')
    print(f'{wl:<18} {NL[wl]:<5} {g_m:+7.2f} {rw_m:+7.2f} {rwfb_m:+9.2f} {gnn_m:+7.2f}  (n={len(rs)}/gnn={len(gnn_vals)})')

def overall(k):
    vals = [r[k] for r in rows if r[k] is not None]
    return sum(vals) / len(vals) if vals else float('nan')
print(f'{"Overall":<18} {"--":<5} {overall("save_greedy"):+7.2f} {overall("save_rl_warm"):+7.2f} '
      f'{overall("save_rl_warm_fb"):+9.2f} {overall("save_gnn"):+7.2f}  (n={len(rows)})')
print()

# Best-budget cells (16: 4 wl x 2 K x 2 N)
print('=== Best-Budget Cells (n=16) ===')
best_cells = {}
for r in rows:
    cell = (r['workload'], r['K'], r['N'])
    if cell not in best_cells or r['save_greedy'] > best_cells[cell]['save_greedy']:
        best_cells[cell] = r
print(f'{"cell":<30} {"NL":<4} {"b":<3} {"greedy":<7} {"RL-WS+fb":<10}')
for cell, r in sorted(best_cells.items()):
    print(f'{str(cell):<30} {r["NL"]:<4} {r["b"]:<3} {r["save_greedy"]:+6.2f} {r["save_rl_warm_fb"]:+9.2f}')

# Spearman rho
nl_16 = [r['NL'] for r in best_cells.values()]
sv_g_16 = [r['save_greedy'] for r in best_cells.values()]
sv_rlfb_16 = [r['save_rl_warm_fb'] for r in best_cells.values()]
rho_g_16, p_g_16 = spearmanr(nl_16, sv_g_16)
rho_rl_16, p_rl_16 = spearmanr(nl_16, sv_rlfb_16)
print(f'\n16-cell Spearman rho (NL%, greedy saving)  = {rho_g_16:.3f}  p={p_g_16:.2e}')
print(f'16-cell Spearman rho (NL%, RL-WS+fb saving) = {rho_rl_16:.3f}  p={p_rl_16:.2e}')

# 40-point pooled
nl_40 = [r['NL'] for r in rows]
sv_g_40 = [r['save_greedy'] for r in rows]
sv_rlfb_40 = [r['save_rl_warm_fb'] for r in rows]
rho_g_40, p_g_40 = spearmanr(nl_40, sv_g_40)
rho_rl_40, p_rl_40 = spearmanr(nl_40, sv_rlfb_40)
print(f'\n40-point Spearman rho (NL%, greedy saving)  = {rho_g_40:.3f}  p={p_g_40:.2e}')
print(f'40-point Spearman rho (NL%, RL-WS+fb saving) = {rho_rl_40:.3f}  p={p_rl_40:.2e}')

# Ablation: RL-WS vs greedy (positive = improvement)
print('\n=== Ablation vs Greedy ===')
imp_warm_raw = [(r['L_greedy'] - r['L_rl_warm']) / r['L_greedy'] * 100 for r in rows]
imp_warm_fb = [(r['L_greedy'] - min(r['L_greedy'], r['L_rl_warm'])) / r['L_greedy'] * 100 for r in rows]
cold_rows = [r for r in rows if r['L_rl_cold'] is not None]
imp_cold_raw = [(r['L_greedy'] - r['L_rl_cold']) / r['L_greedy'] * 100 for r in cold_rows]
imp_cold_fb = [(r['L_greedy'] - min(r['L_greedy'], r['L_rl_cold'])) / r['L_greedy'] * 100 for r in cold_rows]
print(f'Warm RL raw  : mean={sum(imp_warm_raw)/len(imp_warm_raw):+.2f}%  worst(min)={min(imp_warm_raw):+.2f}%  wins={sum(1 for x in imp_warm_raw if x>0)}/{len(imp_warm_raw)}')
print(f'Warm RL + fb : mean={sum(imp_warm_fb)/len(imp_warm_fb):+.2f}%   worst(min)={min(imp_warm_fb):+.2f}%   wins={sum(1 for x in imp_warm_fb if x>0)}/{len(imp_warm_fb)}')
if imp_cold_raw:
    print(f'Cold RL raw  : mean={sum(imp_cold_raw)/len(imp_cold_raw):+.2f}%  worst(min)={min(imp_cold_raw):+.2f}%  wins={sum(1 for x in imp_cold_raw if x>0)}/{len(imp_cold_raw)}')
    print(f'Cold RL + fb : mean={sum(imp_cold_fb)/len(imp_cold_fb):+.2f}%   worst(min)={min(imp_cold_fb):+.2f}%   wins={sum(1 for x in imp_cold_fb if x>0)}/{len(imp_cold_fb)}')
else:
    print('Cold RL: no data')

# Best single config
best = max(rows, key=lambda r: r['save_rl_warm_fb'])
print(f'\nBest RL-WS+fb: {best["workload"]} K{best["K"]} N{best["N"]} b{best["b"]}: saving={best["save_rl_warm_fb"]:.2f}% (greedy={best["save_greedy"]:.2f}%)')
best_g = max(rows, key=lambda r: r['save_greedy'])
print(f'Best greedy  : {best_g["workload"]} K{best_g["K"]} N{best_g["N"]} b{best_g["b"]}: saving={best_g["save_greedy"]:.2f}%')

# Generalization stats
print('\n=== Generalization (Unseen) ===')
from collections import defaultdict
by_wl = defaultdict(list)
for r in gen:
    by_wl[r['workload']].append(r)
print(f'{"workload":<20} {"n":<3} {"GNN vs greedy":<15} {"RL-WS vs greedy":<15}')
gnn_all = []
rl_all = []
for wl, rs in by_wl.items():
    gnn_imps = [(r['express_greedy']['latency'] - r['gnn_agent']['latency']) / r['express_greedy']['latency'] * 100
                for r in rs if r.get('gnn_agent')]
    rl_imps = [(r['express_greedy']['latency'] - r['rl_warmstart']['latency']) / r['express_greedy']['latency'] * 100
               for r in rs if r.get('rl_warmstart')]
    gnn_all.extend(gnn_imps)
    rl_all.extend(rl_imps)
    gnn_wins = sum(1 for x in gnn_imps if x > 0)
    rl_wins = sum(1 for x in rl_imps if x > 0)
    gnn_m = sum(gnn_imps)/len(gnn_imps) if gnn_imps else float('nan')
    rl_m = sum(rl_imps)/len(rl_imps) if rl_imps else float('nan')
    print(f'{wl:<20} {len(rs):<3} {gnn_m:+.1f}% ({gnn_wins}/{len(gnn_imps)})  {rl_m:+.1f}% ({rl_wins}/{len(rl_imps)})')
print(f'{"Overall":<20} {len(gen):<3} {sum(gnn_all)/len(gnn_all):+.1f}% ({sum(1 for x in gnn_all if x>0)}/{len(gnn_all)})  {sum(rl_all)/len(rl_all):+.1f}% ({sum(1 for x in rl_all if x>0)}/{len(rl_all)})')
