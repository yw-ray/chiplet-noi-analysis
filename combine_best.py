"""Combine best candidates from ALL methods (v4, v5, v5alt, GA, SA) per cell.

For each cell, pick the candidate with lowest max-latency-across-rates.
This is the 'meta-best' across all search methods.

Saves to results/ml_placement/meta_best.json with breakdown by winning method.
"""
import json
from pathlib import Path
from collections import Counter

R = Path('results/ml_placement')
files = {
    'v4': 'rl_v4.json',
    'v5': 'rl_v5.json',
    'v5alt': 'rl_v5_alt.json',
    'ga': 'rl_ga.json',
    'sa': 'rl_sa.json',
}

# Load all available files
data = {}
for tag, fn in files.items():
    p = R / fn
    if p.exists():
        data[tag] = json.load(open(p))

# Index by (wl, K, N, bpp)
indexed = {tag: {(r['workload'], r['K'], r['N'], r['budget_per_pair']): r
                  for r in d} for tag, d in data.items()}

# Collect all unique cells
all_keys = set()
for idx in indexed.values():
    all_keys.update(idx.keys())

results = []
print(f"{'Cell':<32s}  {'greedy':>7s} {'FBfly':>7s}  " +
      "  ".join(f"{t:>7s}" for t in data.keys()) +
      f"  {'meta_best':>9s}  {'chosen':>8s}")

for key in sorted(all_keys):
    wl, K, N, bpp = key
    cell = f"{wl:14s} K{K}N{N} b{bpp}x"
    # Baselines from any available result
    g = fb = None
    method_vals = {}
    for tag, idx in indexed.items():
        if key in idx:
            r = idx[key]
            if g is None:
                g = max(r['greedy']['latency'])
                fb = max(r['fbfly']['latency'])
            # Get this method's ours_* value
            ours_key = f'ours_{tag}' if tag != 'v5alt' else 'ours_v5alt'
            if ours_key in r:
                method_vals[tag] = max(r[ours_key]['latency'])

    # Meta-best: min across all methods + baselines
    all_options = {'greedy': g, 'fbfly': fb, **method_vals}
    chosen = min(all_options.keys(), key=lambda k: all_options[k])
    meta_best = all_options[chosen]

    row = f"{cell:<32s}  {g:7.1f} {fb:7.1f}  " + "  ".join(
        f"{method_vals.get(t, None):7.1f}" if method_vals.get(t) is not None else '    N/A' for t in data.keys()
    )
    fb_win = '✅' if meta_best <= fb + 0.01 else '❌'
    print(f"{row}  {meta_best:9.1f}  {chosen:>8s} {fb_win}")

    results.append({
        'workload': wl, 'K': K, 'N': N, 'budget_per_pair': bpp,
        'greedy': g, 'fbfly': fb, **method_vals,
        'meta_best': meta_best, 'chosen_method': chosen,
    })

# Summary
chose = Counter(r['chosen_method'] for r in results)
print()
print(f"Chosen method distribution: {dict(chose)}")
fb_wins = sum(1 for r in results if r['meta_best'] <= r['fbfly'] + 0.01)
print(f"meta_best ≤ FBfly: {fb_wins}/{len(results)}")

# Save
with open(R / 'meta_best.json', 'w') as f:
    json.dump(results, f, indent=2)
print(f"\nSaved to {R / 'meta_best.json'}")
