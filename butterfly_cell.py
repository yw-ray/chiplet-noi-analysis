"""Run a single butterfly baseline cell (for parallel execution)."""
import json
import sys
import time
from pathlib import Path

from butterfly_baseline import run_one

RESULTS_DIR = Path('results/ml_placement')
OUT_FILE = RESULTS_DIR / 'butterfly_baseline.json'


def main():
    wl = sys.argv[1]
    K = int(sys.argv[2])
    N = int(sys.argv[3])
    bpp = int(sys.argv[4])

    print(f'>>> {wl} K{K}N{N} b{bpp}x (single cell)', flush=True)
    t0 = time.time()
    res = run_one(wl, K, N, bpp)
    dt = time.time() - t0
    res.update({'workload': wl, 'K': K, 'N': N, 'budget_per_pair': bpp, 'run_time': dt})

    # Atomic append to json
    existing = []
    if OUT_FILE.exists():
        existing = json.load(open(OUT_FILE))
    existing = [r for r in existing if (r['workload'], r['K'], r['N'], r['budget_per_pair'])
                 != (wl, K, N, bpp)]
    existing.append(res)
    with open(OUT_FILE, 'w') as f:
        json.dump(existing, f, indent=2)

    L_adj = res['L_adj']; L_g = res['L_greedy']; L_fb = res['L_fbfly']
    sv_g = (L_adj - L_g) / L_adj * 100 if L_adj and L_g else None
    sv_fb = (L_adj - L_fb) / L_adj * 100 if L_adj and L_fb else None
    print(f'    L_adj={L_adj} L_greedy={L_g} L_fbfly={L_fb}', flush=True)
    print(f'    greedy_sv={sv_g:+.2f}%  fbfly_sv={sv_fb:+.2f}%  ({dt:.0f}s)', flush=True)


if __name__ == '__main__':
    main()
