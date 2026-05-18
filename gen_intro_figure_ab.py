"""Generate two Fig 1 variants for honest phantom-load comparison.

Option A: latency speedup at fixed LOW rate (all K non-saturated) — fair latency comparison.
Option B: saturation-rate speedup — max sustainable rate ratio.

Both reuse the same panel (a) showing BookSim latency at 1x budget (phantom impact).
Panel (b) differs by metric.
"""

import json
from pathlib import Path
from collections import defaultdict

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
bbox_white = dict(boxstyle='round,pad=0.2', facecolor='white', edgecolor='none', alpha=0.85)

K_LIST = [4, 8, 16, 32, 64]
COLORS = {4: '#2ca02c', 8: '#1f77b4', 16: '#ff7f0e', 32: '#d62728', 64: '#8c564b'}
MARKERS = {4: 'v', 8: '^', 16: 's', 32: 'o', 64: 'D'}


def load_all():
    """Returns dict[(K, mult, rate)] -> (latency, throughput)."""
    out = {}
    if RATESWEEP_PATH.exists():
        d = json.loads(RATESWEEP_PATH.read_text())
        for k, v in d.items():
            out[(v['K'], v['budget_mult'], round(v['rate'], 5))] = (
                v['latency'], v['throughput'])
    # Merge legacy rate=0.005, 0.01, 0.015
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


def get_latency(data, K, mult, rate):
    return data.get((K, mult, round(rate, 5)), (None, None))[0]


def find_saturation_rate(data, K, mult, target_acc_pct=0.9):
    """Max rate where accepted/offered >= target_acc_pct (default 90%)."""
    rates_here = sorted({r for (kk, mm, r) in data if kk == K and mm == mult})
    sat = None
    for r in rates_here:
        lat, thr = data.get((K, mult, round(r, 5)), (None, None))
        if thr is None:
            continue
        acc_pct = thr / r if r > 0 else 0
        if acc_pct >= target_acc_pct:
            sat = r
        else:
            break
    return sat


def draw_panel_a(ax, data):
    """Panel (a) — common: BookSim latency at 1x budget rate=0.005."""
    lats = [get_latency(data, K, 1, 0.005) for K in K_LIST]
    valid = [(K, l) for K, l in zip(K_LIST, lats) if l]
    if not valid:
        return
    xs, ys = zip(*valid)
    ax.plot(xs, ys, 'o-', color='#d62728', markersize=6, linewidth=1.8, zorder=3)
    ax.fill_between(xs, [ys[0]] * len(xs), ys, alpha=0.10, color='#d62728')
    ax.set_xlabel('Number of chiplets (K)')
    ax.set_ylabel('Latency at 1$\\times$ budget (cycles)')
    ax.set_xscale('log', base=2)
    ax.set_yscale('log')
    ax.set_xticks(K_LIST)
    ax.set_xticklabels([str(k) for k in K_LIST])
    ax.set_title('(a) BookSim-measured phantom load (adj-only, rate=0.005)')
    ax.grid(True, which='major', alpha=0.3, linewidth=0.4)
    ax.grid(True, which='minor', alpha=0.15, linewidth=0.3)
    for K, l in zip(xs, ys):
        ax.annotate(f'{l:.0f}', xy=(K, l), xytext=(4, 6),
                    textcoords='offset points', fontsize=5.5,
                    color='#d62728', fontweight='bold')


def gen_option_a(data):
    """Option A: latency speedup at fixed low rate where all K non-saturated."""
    # Pick the lowest rate present in data
    candidate_rates = [0.001, 0.002, 0.003]
    chosen_rate = None
    for r in candidate_rates:
        # All (K, 1x) must have lat at this rate
        if all(get_latency(data, K, 1, r) is not None for K in K_LIST):
            chosen_rate = r
            break
    if chosen_rate is None:
        print('Option A: no rate available for all K — need ratesweep data')
        return False

    fig, axes = plt.subplots(2, 1, figsize=(3.5, 3.8))
    draw_panel_a(axes[0], data)

    ax = axes[1]
    budgets = [1, 2, 3, 4]
    K_speedups = {}
    for K in K_LIST:
        lats = [get_latency(data, K, m, chosen_rate) for m in budgets]
        if any(l is None for l in lats):
            print(f'  K={K}: missing lat at rate={chosen_rate} — skip')
            continue
        K_speedups[K] = [lats[0] / l for l in lats]
        ax.plot(budgets, K_speedups[K], marker=MARKERS[K], color=COLORS[K],
                markersize=5 if K in (16, 32, 64) else 4,
                linewidth=1.8 if K in (16, 32, 64) else 1.3,
                label=f'K={K}', alpha=0.95, zorder=3)

    ax.plot(budgets, budgets, '--', color='gray', linewidth=1.0, alpha=0.5,
            label='Ideal (linear)')

    ax.set_xlabel('Link budget (× per adjacent pair)')
    ax.set_ylabel(f'Speedup vs 1$\\times$ at rate={chosen_rate:.3f}')
    ax.set_xticks(budgets)
    ax.set_xticklabels([f'{b}$\\times$' for b in budgets])
    ax.set_title(f'(b-A) Fair latency speedup at low rate ({chosen_rate}) — no saturation')
    ax.legend(loc='upper left', ncol=2, framealpha=0.92)
    ax.grid(True, alpha=0.3, linewidth=0.4)
    ax.set_ylim(0.85, 4.5)

    plt.tight_layout()
    pdf = FIGURES_DIR / 'fig_intro_motivation_optA.pdf'
    png = FIGURES_DIR / 'fig_intro_motivation_optA.png'
    fig.savefig(pdf, bbox_inches='tight')
    fig.savefig(png, bbox_inches='tight')
    plt.close()
    print(f'Saved Option A: {png}')
    print(f'  used rate={chosen_rate}')
    for K, sp in K_speedups.items():
        print(f'  K={K}: {[f"{s:.2f}x" for s in sp]}')
    return True


def gen_option_b(data):
    """Option B: saturation rate speedup."""
    fig, axes = plt.subplots(2, 1, figsize=(3.5, 3.8))
    draw_panel_a(axes[0], data)

    ax = axes[1]
    budgets = [1, 2, 3, 4]
    K_sat_speedups = {}
    K_sat_rates = {}
    for K in K_LIST:
        sat_rates = [find_saturation_rate(data, K, m) for m in budgets]
        K_sat_rates[K] = sat_rates
        if sat_rates[0] is None or any(s is None for s in sat_rates):
            print(f'  K={K}: incomplete sat data {sat_rates} — partial plot')
            continue
        sp = [s / sat_rates[0] for s in sat_rates]
        K_sat_speedups[K] = sp
        ax.plot(budgets, sp, marker=MARKERS[K], color=COLORS[K],
                markersize=5 if K in (16, 32, 64) else 4,
                linewidth=1.8 if K in (16, 32, 64) else 1.3,
                label=f'K={K}', alpha=0.95, zorder=3)

    ax.plot(budgets, budgets, '--', color='gray', linewidth=1.0, alpha=0.5,
            label='Ideal (linear)')
    ax.set_xlabel('Link budget (× per adjacent pair)')
    ax.set_ylabel('Sat-rate speedup vs 1$\\times$')
    ax.set_xticks(budgets)
    ax.set_xticklabels([f'{b}$\\times$' for b in budgets])
    ax.set_title('(b-B) Saturation-rate speedup (max rate at $\\geq$90% accept)')
    ax.legend(loc='upper left', ncol=2, framealpha=0.92)
    ax.grid(True, alpha=0.3, linewidth=0.4)
    ax.set_ylim(0.85, 4.5)

    plt.tight_layout()
    pdf = FIGURES_DIR / 'fig_intro_motivation_optB.pdf'
    png = FIGURES_DIR / 'fig_intro_motivation_optB.png'
    fig.savefig(pdf, bbox_inches='tight')
    fig.savefig(png, bbox_inches='tight')
    plt.close()
    print(f'Saved Option B: {png}')
    for K, sp in K_sat_speedups.items():
        rates_str = [f'{r:.4f}' if r else 'None' for r in K_sat_rates[K]]
        print(f'  K={K}: sat_rates={rates_str} speedup={[f"{s:.2f}x" for s in sp]}')


def main():
    data = load_all()
    print(f'Loaded {len(data)} (K, mult, rate) points')
    print('Rates per (K=64, m=1):',
          sorted({r for (k, m, r) in data if k == 64 and m == 1}))
    print()
    print('=== Option A ===')
    gen_option_a(data)
    print()
    print('=== Option B ===')
    gen_option_b(data)


if __name__ == '__main__':
    main()
