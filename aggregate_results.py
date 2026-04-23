"""Aggregate multi-seed and fine-tune results into paper-ready tables."""
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

RESULTS_DIR = Path('results/ml_placement')
NL = {'tree_allreduce': 42, 'hybrid_tp_pp': 77, 'moe': 91, 'uniform_random': 89}


def aggregate_multiseed():
    """Compute per-config mean ± std over seeds + ablation stats."""
    f = RESULTS_DIR / 'ml_comparison_multiseed.json'
    if not f.exists():
        print(f'[skip multiseed] {f} missing')
        return
    rows = json.load(open(f))
    by_cfg = defaultdict(list)
    for r in rows:
        k = (r['workload'], r['K'], r['N'], r['budget_per_pair'])
        by_cfg[k].append(r)

    print(f'\n=== Multi-seed: {len(rows)} runs, {len(by_cfg)} cells ===')

    # Load fast.json for adj_uniform baseline to compute savings
    with open(RESULTS_DIR / 'ml_comparison_fast.json') as fp:
        fast = json.load(fp)
    fast_by = {(r['workload'], r['K'], r['N'], r['budget_per_pair']): r for r in fast}

    print(f'\n{"Cell":<40}{"n":<3}{"greedy_sv":<12}{"rl_raw_sv":<16}{"rl_fb_sv":<16}{"imp_raw":<16}{"imp_fb":<12}')
    rows_out = []
    for cfg, seed_rows in sorted(by_cfg.items()):
        fr = fast_by.get(cfg)
        if not fr:
            continue
        adj = fr['adj_uniform']['latency']

        g_lat = [r['L_greedy'] for r in seed_rows if r.get('L_greedy')]
        rr = [r['L_rl_raw'] for r in seed_rows if r.get('L_rl_raw')]
        rf = [r['L_rl_fb'] for r in seed_rows if r.get('L_rl_fb')]
        g_m = np.mean(g_lat) if g_lat else float('nan')
        rr_m = np.mean(rr) if rr else float('nan')
        rr_s = np.std(rr) if rr else float('nan')
        rf_m = np.mean(rf) if rf else float('nan')
        rf_s = np.std(rf) if rf else float('nan')

        sv_g = (adj - g_m) / adj * 100 if g_lat else float('nan')
        sv_rr_m = (adj - rr_m) / adj * 100 if rr else float('nan')
        sv_rr_s = rr_s / adj * 100
        sv_rf_m = (adj - rf_m) / adj * 100 if rf else float('nan')
        sv_rf_s = rf_s / adj * 100
        imp_raw_m = (g_m - rr_m) / g_m * 100 if g_lat and rr else float('nan')
        imp_raw_s = rr_s / g_m * 100 if g_lat and rr else float('nan')
        imp_fb_m = (g_m - rf_m) / g_m * 100 if g_lat and rf else float('nan')
        imp_fb_s = rf_s / g_m * 100 if g_lat and rf else float('nan')
        print(f'{str(cfg):<40}{len(seed_rows):<3}{sv_g:>+7.2f}%    {sv_rr_m:>+7.2f}±{sv_rr_s:4.2f}%   {sv_rf_m:>+7.2f}±{sv_rf_s:4.2f}%   {imp_raw_m:>+6.2f}±{imp_raw_s:4.2f}%   {imp_fb_m:>+6.2f}±{imp_fb_s:4.2f}%')

        rows_out.append({
            'cfg': cfg, 'NL': NL[cfg[0]],
            'sv_g': sv_g, 'sv_rr_m': sv_rr_m, 'sv_rr_s': sv_rr_s,
            'sv_rf_m': sv_rf_m, 'sv_rf_s': sv_rf_s,
            'imp_raw_m': imp_raw_m, 'imp_raw_s': imp_raw_s,
            'imp_fb_m': imp_fb_m, 'imp_fb_s': imp_fb_s,
        })

    # Overall mean (across cells) ± std (of per-cell means)
    if rows_out:
        imp_raw_cellmeans = [r['imp_raw_m'] for r in rows_out if not np.isnan(r['imp_raw_m'])]
        imp_fb_cellmeans = [r['imp_fb_m'] for r in rows_out if not np.isnan(r['imp_fb_m'])]
        print(f'\nOverall cell-mean imp_raw: {np.mean(imp_raw_cellmeans):+.2f} ± {np.std(imp_raw_cellmeans):.2f}%')
        print(f'Overall cell-mean imp_fb:  {np.mean(imp_fb_cellmeans):+.2f} ± {np.std(imp_fb_cellmeans):.2f}%')


def aggregate_finetune():
    f = RESULTS_DIR / 'ml_generalization_finetuned.json'
    if not f.exists():
        print(f'\n[skip ft-gnn] {f} missing')
        return
    rows = json.load(open(f))
    print(f'\n=== Fine-tuned GNN: {len(rows)} configs ===')

    # Load original generalization results for zero-shot GNN baseline
    with open(RESULTS_DIR / 'ml_generalization.json') as fp:
        gen = json.load(fp)
    gen_by = {(r['workload'], r['K'], r['N'], r['budget_per_pair']): r for r in gen}

    by_wl = defaultdict(list)
    for r in rows:
        key = (r['workload'], r['K'], r['N'], r['budget_per_pair'])
        base = gen_by.get(key)
        if not base:
            continue
        L_g = r['L_greedy']
        L_ft = r['L_gnn_ft']
        L_zs = base.get('gnn_agent', {}).get('latency')
        ft_imp = (L_g - L_ft) / L_g * 100 if L_g and L_ft else float('nan')
        zs_imp = (L_g - L_zs) / L_g * 100 if L_g and L_zs else float('nan')
        by_wl[r['workload']].append({'cfg': key, 'ft_imp': ft_imp, 'zs_imp': zs_imp})

    print(f'\n{"Workload":<20}{"cfg":<20}{"GNN-ZS":<12}{"GNN-FT":<12}{"Δ":<8}')
    summary = defaultdict(list)
    for wl, items in sorted(by_wl.items()):
        for it in items:
            print(f'{wl:<20}{str(it["cfg"][1:]):<20}{it["zs_imp"]:>+7.2f}%   {it["ft_imp"]:>+7.2f}%   {it["ft_imp"]-it["zs_imp"]:>+6.2f}%')
            summary[wl].append(it)

    print(f'\n{"Workload":<20}{"n":<4}{"GNN-ZS mean":<18}{"GNN-FT mean":<18}{"ZS wins":<10}{"FT wins":<10}')
    for wl, items in summary.items():
        n = len(items)
        zs_m = np.mean([x['zs_imp'] for x in items])
        ft_m = np.mean([x['ft_imp'] for x in items])
        zs_w = sum(1 for x in items if x['zs_imp'] > 0)
        ft_w = sum(1 for x in items if x['ft_imp'] > 0)
        print(f'{wl:<20}{n:<4}{zs_m:>+7.2f}%          {ft_m:>+7.2f}%          {zs_w}/{n}        {ft_w}/{n}')


if __name__ == '__main__':
    aggregate_multiseed()
    aggregate_finetune()
