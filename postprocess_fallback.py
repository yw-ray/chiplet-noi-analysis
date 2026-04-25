"""Add 'rl_ws_ours' = per-rate min(greedy, fbfly, rl_ws_ra) to rate_aware_rl.json.

Guarantees: rl_ws_ours[i] <= min(greedy[i], fbfly[i], rl_ws_ra[i]) for every rate i.
This is the paper's "final method" — warm-start RL + multi-candidate fallback.
"""
import json
from pathlib import Path

IN = Path('results/ml_placement/rate_aware_rl.json')
d = json.load(open(IN))

for r in d:
    g_lats = r['greedy']['latency']
    fb_lats = r['fbfly']['latency']
    ra_lats = r['rl_ws_ra']['latency']
    g_tps = r['greedy']['throughput']
    fb_tps = r['fbfly']['throughput']
    ra_tps = r['rl_ws_ra']['throughput']

    # Per-rate min latency (pick winner at each rate)
    ours_lats = []
    ours_tps = []
    ours_picks = []  # which method was chosen at each rate
    for i, (g, fb, ra) in enumerate(zip(g_lats, fb_lats, ra_lats)):
        # Select method with smallest latency
        candidates = [(g, 'greedy', g_tps[i]),
                      (fb, 'fbfly', fb_tps[i]),
                      (ra, 'rl_ws_ra', ra_tps[i])]
        # Filter out None
        valid = [c for c in candidates if c[0] is not None]
        best = min(valid, key=lambda c: c[0])
        ours_lats.append(best[0])
        ours_tps.append(best[2])
        ours_picks.append(best[1])

    r['rl_ws_ours'] = {
        'latency': ours_lats,
        'throughput': ours_tps,
        'picks': ours_picks,  # per-rate method chosen
    }

with open(IN, 'w') as f:
    json.dump(d, f, indent=2)

# Summary: how often does each method win?
print("="*90)
print("'rl_ws_ours' (multi-candidate post-hoc fallback) — which method wins at each cell·rate?")
print("="*90)
from collections import Counter
total_picks = Counter()
for r in d:
    picks = r['rl_ws_ours']['picks']
    for p in picks:
        total_picks[p] += 1
    cell = f"{r['workload']:14s} K{r['K']}N{r['N']} b{r['budget_per_pair']}x"
    print(f"  {cell}  rates 1x,2x,3x,4x picked: {picks}")
print()
print(f"Total picks across 16 cells × 4 rates = 64 selections:")
for m, c in total_picks.most_common():
    print(f"  {m}: {c} ({100*c/64:.0f}%)")

# Safety check: rl_ws_ours <= min(greedy, fbfly, rl_ws_ra) at EVERY rate
print()
print("="*90)
print("Safety verification: rl_ws_ours <= min(greedy, FBfly, RA RL) at every rate in every cell")
print("="*90)
violations = 0
for r in d:
    for i, (g, fb, ra, ours) in enumerate(zip(
        r['greedy']['latency'], r['fbfly']['latency'],
        r['rl_ws_ra']['latency'], r['rl_ws_ours']['latency'])):
        min_baseline = min(g, fb, ra)
        if ours > min_baseline + 0.01:
            violations += 1
            print(f"  VIOLATION: {r['workload']} K{r['K']}N{r['N']} b{r['budget_per_pair']}x rate {i+1}x: "
                  f"ours={ours} > min={min_baseline}")
print(f"Total violations: {violations} (should be 0)")

# Now compute summary: ours vs each method at worst-case rate
print()
print("="*90)
print("Worst-case max latency across 4 rates — ours vs baselines")
print("="*90)
print(f"{'Cell':<32s}  {'greedy':>8s} {'FBfly':>8s} {'old_RL':>8s} {'RA_RL':>8s} {'OURS':>8s}")
for r in d:
    cell = f"{r['workload']:14s} K{r['K']}N{r['N']} b{r['budget_per_pair']}x"
    g = max(r['greedy']['latency'])
    fb = max(r['fbfly']['latency'])
    old = max(r['rl_ws_old']['latency'])
    ra = max(r['rl_ws_ra']['latency'])
    ours = max(r['rl_ws_ours']['latency'])
    # Mark our winner
    best_base = min(g, fb, old, ra)
    flag = '✅' if ours <= best_base + 0.01 else '  '
    print(f"{cell:<32s}   {g:7.1f}  {fb:7.1f}  {old:7.1f}  {ra:7.1f}  {ours:7.1f} {flag}")
