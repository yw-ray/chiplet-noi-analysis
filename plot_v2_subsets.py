"""12-panel grouped bar chart for V2 subset sweep.

Layout:
  rows = 4 cells (K=16/32 × N=4/8)
  cols = 3 mix sizes (2-W, 3-W, 4-W)

Each panel:
  x-axis: wire-area (2 points per cell: bpp=2 super_wire, bpp=3 super_wire)
  y-axis: ours_mask latency (averaged over subsets at this mix size)
  bars per wire point: 4 workloads (grouped)
  legend: workloads (colors)
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


WORKLOADS = ['moe', 'hybrid_tp_pp', 'uniform_random', 'all_to_all']
WORKLOAD_LABELS = {
    'moe': 'MoE',
    'hybrid_tp_pp': 'Hybrid',
    'uniform_random': 'Uniform',
    'all_to_all': 'AllToAll',
}
COLORS = {
    'moe': 'tab:red',
    'hybrid_tp_pp': 'tab:blue',
    'uniform_random': 'tab:green',
    'all_to_all': 'tab:purple',
}
CELLS = ['K16_N4', 'K16_N8', 'K32_N4', 'K32_N8']
MIX_SIZES = [2, 3, 4]


def aggregate(data, cell, mix_size):
    """For (cell, mix_size), return per-bpp per-workload list of (wire, ours_mask_lat).

    Output:
      {bpp_key: {workload: (mean_wire, mean_lat)}}
    """
    accum = {}  # {bpp_key: {workload: list of (wire, lat)}}
    for subset_key, sd in data.items():
        subset = subset_key.split('+')
        if len(subset) != mix_size:
            continue
        cd = sd.get(cell, {})
        for bpp_key, bd in cd.items():
            wd = bd.get('workloads', {})
            super_wire = bd.get('super_wire', 0)
            for w in subset:
                wdat = wd.get(w)
                if not wdat:
                    continue
                lat = wdat.get('mask_lat')
                if lat is None:
                    continue
                accum.setdefault(bpp_key, {}).setdefault(w, []).append(
                    (super_wire, lat))
    out = {}
    for bpp_key, per_w in accum.items():
        out[bpp_key] = {}
        for w, samples in per_w.items():
            wires = [x[0] for x in samples]
            lats = [x[1] for x in samples]
            out[bpp_key][w] = (float(np.mean(wires)), float(np.mean(lats)))
    return out


def main():
    RD = Path(__file__).parent / 'results' / 'ml_placement'
    data = json.loads((RD / 'sweep_v2_full_subsets.json').read_text())

    fig, axes = plt.subplots(4, 3, figsize=(15, 16), squeeze=False)

    bar_width = 0.18

    for ci, cell in enumerate(CELLS):
        for mi, mix_size in enumerate(MIX_SIZES):
            ax = axes[ci, mi]
            agg = aggregate(data, cell, mix_size)
            if not agg:
                ax.text(0.5, 0.5, 'no data',
                        ha='center', va='center', transform=ax.transAxes)
                ax.set_title(f"{cell}, {mix_size}-W")
                continue

            bpp_keys = sorted(agg.keys(),
                              key=lambda k: int(k.replace('bpp', '')))
            x_centers = np.arange(len(bpp_keys))

            for wi, w in enumerate(WORKLOADS):
                ys = []
                xs = []
                for bi, bpp_key in enumerate(bpp_keys):
                    wd = agg[bpp_key].get(w)
                    if wd:
                        ys.append(wd[1])
                        xs.append(x_centers[bi] + (wi - 1.5) * bar_width)
                if xs:
                    ax.bar(xs, ys, bar_width,
                           color=COLORS[w], label=WORKLOAD_LABELS[w])

            xtick_labels = []
            for bpp_key in bpp_keys:
                wires = [agg[bpp_key][w][0] for w in WORKLOADS
                         if w in agg[bpp_key]]
                if wires:
                    xtick_labels.append(f"{np.mean(wires):.0f} mm²")
                else:
                    xtick_labels.append('—')
            ax.set_xticks(x_centers)
            ax.set_xticklabels(xtick_labels)
            ax.set_title(f"{cell}, {mix_size}-W mix")
            ax.set_xlabel('Wire-area')
            ax.set_ylabel('ours_mask latency (cycles)')
            ax.grid(True, axis='y', alpha=0.3)
            if ci == 0 and mi == 0:
                ax.legend(loc='best', fontsize=9)

    plt.tight_layout()
    out_pdf = (Path(__file__).parent / 'paper' / 'figures' /
               'fig_v2_subsets_bars.pdf')
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_pdf, dpi=150, bbox_inches='tight')
    fig.savefig(out_pdf.with_suffix('.png'), dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved: {out_pdf}")
    print(f"Saved: {out_pdf.with_suffix('.png')}")


if __name__ == '__main__':
    main()
