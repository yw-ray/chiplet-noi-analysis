"""Generate 12 wire-Pareto graphs (4 cells x 3 mix sizes).

x = wire-mm² (Ours superset wire-area at each bpp)
y = avg latency over all C(4, k) mixes of size k
5 lines per graph: mesh, kite_s, kite_m, kite_l, ours
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


CELLS = ['K16_N4', 'K16_N8', 'K32_N4', 'K32_N8']
MIX_SIZES = [2, 3, 4]
METHODS = ['mesh', 'kite_s', 'kite_m', 'kite_l', 'ours']
COLORS = {'mesh': 'gray', 'kite_s': 'tab:blue', 'kite_m': 'tab:cyan',
          'kite_l': 'tab:green', 'ours': 'tab:red'}
MARKERS = {'mesh': 'o', 'kite_s': 's', 'kite_m': 'D',
           'kite_l': '^', 'ours': '*'}


def main():
    RD = Path(__file__).parent / 'results' / 'ml_placement'
    data = json.loads((RD / 'sweep_v2_pareto_full.json').read_text())

    fig, axes = plt.subplots(4, 3, figsize=(15, 16), squeeze=False)

    for ci, cell in enumerate(CELLS):
        cell_data = data.get(cell, {})
        for mi, mix_size in enumerate(MIX_SIZES):
            ax = axes[ci, mi]
            if not cell_data:
                ax.text(0.5, 0.5, f"{cell} no data",
                        ha='center', va='center', transform=ax.transAxes)
                continue

            for method in METHODS:
                xs, ys = [], []
                for bpp_key in sorted(cell_data.keys(),
                                       key=lambda k: int(k.replace('bpp', ''))):
                    bpp_data = cell_data[bpp_key]
                    raw = bpp_data.get('raw', {})
                    method_workloads = raw.get(method, {})
                    mix_avgs = bpp_data.get('mix_avgs', {}).get(str(mix_size), {})
                    if not mix_avgs:
                        continue
                    method_lats = []
                    for combo, row in mix_avgs.items():
                        if row.get(method) is not None:
                            method_lats.append(row[method])
                    if method_lats:
                        wire = bpp_data.get('super_wire', 0)
                        xs.append(wire)
                        ys.append(np.mean(method_lats))
                if xs:
                    pts = sorted(zip(xs, ys))
                    xs, ys = zip(*pts)
                    ax.plot(xs, ys,
                            marker=MARKERS[method],
                            color=COLORS[method],
                            label=method,
                            linewidth=1.5,
                            markersize=8 if method == 'ours' else 6)

            ax.set_title(f"{cell}, mix size = {mix_size}", fontsize=11)
            ax.set_xlabel('Wire-area (mm²)')
            ax.set_ylabel('Avg latency (cycles)')
            ax.grid(True, alpha=0.3)
            if ci == 0 and mi == 0:
                ax.legend(loc='best', fontsize=9)

    plt.tight_layout()
    out_pdf = Path(__file__).parent / 'paper' / 'figures' / 'fig_v2_wire_pareto.pdf'
    out_png = out_pdf.with_suffix('.png')
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_pdf, dpi=150, bbox_inches='tight')
    fig.savefig(out_png, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved: {out_pdf}")
    print(f"Saved: {out_png}")


if __name__ == '__main__':
    main()
