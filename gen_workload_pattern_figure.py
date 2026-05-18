"""Generate Fig: 4-workload chiplet connection patterns (K=16, 4x4 grid).

For each workload, shows chiplet grid positions with top traffic edges
drawn as arrows. Visualizes WHICH chiplets talk to WHICH at the physical
layout level.

Output:
  paper/figures/fig_workload_patterns.pdf
  paper/figures/fig_workload_patterns.png
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch, Rectangle

sys.path.insert(0, str(Path(__file__).parent))
from cost_perf_6panel_workload import (
    gen_moe, gen_hybrid_tp_pp, gen_tree_allreduce, gen_uniform_random,
    gen_ep_all_to_all, gen_fsdp,
)
from noi_topology_synthesis import ChipletGrid

# Paper-consistent rcParams (per CLAUDE.md figure rules)
plt.rcParams.update({
    'font.size': 6,
    'axes.titlesize': 7,
    'axes.labelsize': 6,
    'xtick.labelsize': 5.5,
    'ytick.labelsize': 5.5,
    'legend.fontsize': 5.5,
    'font.family': 'serif',
})

K = 16
R, C = 4, 4
grid = ChipletGrid(R, C)
adj_set = set(grid.get_adj_pairs())

WORKLOADS = [
    ('Tree All-Reduce', gen_tree_allreduce, 42),
    ('FSDP', gen_fsdp, 76),
    ('Hybrid TP+PP', gen_hybrid_tp_pp, 77),
    ('Uniform Random', gen_uniform_random, 89),
    ('MoE Expert (top-2)', gen_moe, 91),
    ('EP All-to-All', gen_ep_all_to_all, 92),
]


def chiplet_pos(idx):
    """Row-major mapping: chiplet idx → (col, row) in grid."""
    r, c = idx // C, idx % C
    return c, R - 1 - r  # flip Y so row 0 is at top


def draw_workload_panel(ax, name, traffic, nl_pct):
    # Determine top-K edges for visualization
    edges = []
    for i in range(K):
        for j in range(i + 1, K):
            if traffic[i][j] > 0:
                edges.append((i, j, traffic[i][j]))
    if not edges:
        return
    edges.sort(key=lambda e: -e[2])
    max_w = edges[0][2]

    # Threshold to show: keep top edges with weight >= 5% of max
    threshold = max_w * 0.05
    edges_to_draw = [e for e in edges if e[2] >= threshold]
    # Cap visualization at top-N for clarity
    edges_to_draw = edges_to_draw[:min(60, len(edges_to_draw))]

    # Compute per-chiplet incoming traffic for highlighting hotspots
    incoming = np.sum(traffic, axis=0)
    inc_norm = incoming / max(incoming.max(), 1e-9)

    # Draw chiplets as squares
    for k in range(K):
        x, y = chiplet_pos(k)
        # Color by incoming traffic intensity
        intensity = inc_norm[k]
        color = plt.cm.Reds(0.2 + 0.7 * intensity)
        rect = Rectangle((x - 0.32, y - 0.32), 0.64, 0.64,
                         facecolor=color, edgecolor='black', linewidth=0.4)
        ax.add_patch(rect)
        ax.text(x, y, str(k), ha='center', va='center',
                fontsize=4.5, color='black')

    # Draw edges with thickness proportional to weight
    for i, j, w in edges_to_draw:
        xi, yi = chiplet_pos(i)
        xj, yj = chiplet_pos(j)
        # Use distance to set curvature: short=straight, long=curved
        is_adj = (i, j) in adj_set or (j, i) in adj_set
        lw = 0.3 + 1.2 * (w / max_w)
        alpha = 0.3 + 0.6 * (w / max_w)
        color = '#2c5aa0' if is_adj else '#c84020'
        if is_adj:
            ax.plot([xi, xj], [yi, yj], color=color,
                    linewidth=lw, alpha=alpha, zorder=1)
        else:
            # curved arc for non-adjacent
            arc = FancyArrowPatch((xi, yi), (xj, yj),
                                  connectionstyle="arc3,rad=0.15",
                                  arrowstyle='-', color=color,
                                  linewidth=lw, alpha=alpha, zorder=1)
            ax.add_patch(arc)

    ax.set_xlim(-0.6, C - 1 + 0.6)
    ax.set_ylim(-0.6, R - 1 + 0.6)
    ax.set_aspect('equal')
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_title(f'{name} (NL={nl_pct}\\%)', pad=3)


def main():
    # 2x3 grid for 6 workloads
    fig, axes = plt.subplots(2, 3, figsize=(7.0, 4.0))
    for ax, (name, gen_fn, nl) in zip(axes.flat, WORKLOADS):
        traffic = gen_fn(K, grid)
        draw_workload_panel(ax, name, traffic, nl)

    # Shared legend at bottom
    from matplotlib.lines import Line2D
    legend_elems = [
        Line2D([0], [0], color='#2c5aa0', lw=1.2, label='adjacent traffic'),
        Line2D([0], [0], color='#c84020', lw=1.2, label='non-adjacent traffic'),
        Rectangle((0, 0), 1, 1, facecolor=plt.cm.Reds(0.2),
                  edgecolor='black', lw=0.4, label='low Rx'),
        Rectangle((0, 0), 1, 1, facecolor=plt.cm.Reds(0.9),
                  edgecolor='black', lw=0.4, label='high Rx (hotspot)'),
    ]
    fig.legend(handles=legend_elems, loc='lower center',
               ncol=4, frameon=False, bbox_to_anchor=(0.5, -0.04))

    plt.tight_layout(rect=(0, 0.05, 1, 1))
    out = Path('paper/figures/fig_workload_patterns')
    plt.savefig(f'{out}.pdf', dpi=300, bbox_inches='tight')
    plt.savefig(f'{out}.png', dpi=200, bbox_inches='tight')
    print(f"Saved: {out}.pdf, {out}.png")


if __name__ == '__main__':
    main()
