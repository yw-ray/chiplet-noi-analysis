"""
Phantom load on 4×4 grid — clean version.
(a) C0→C15 via XY routing: red arrows only
(b) Express link C0→C3: green arrow, remaining path in red
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

FIGURES_DIR = Path(__file__).parent / 'paper' / 'figures'


def draw_grid(ax, title):
    """Draw 4×4 chiplet grid, return positions."""
    ax.set_xlim(-0.4, 3.8)
    ax.set_ylim(-0.5, 3.6)
    ax.set_aspect('equal')
    ax.axis('off')
    ax.set_title(title, fontsize=7, pad=5)

    node_r = 0.15
    node_color = '#4A90D9'
    grid_color = '#DDDDDD'

    positions = {}
    for r in range(4):
        for c in range(4):
            cid = r * 4 + c
            x, y = c, 3 - r
            positions[cid] = (x, y)

    # Draw all adjacent links (gray)
    for r in range(4):
        for c in range(4):
            cid = r * 4 + c
            x, y = positions[cid]
            if c < 3:
                nx, ny = positions[cid + 1]
                ax.plot([x + node_r, nx - node_r], [y, ny],
                        color=grid_color, linewidth=3, zorder=1)
            if r < 3:
                nx, ny = positions[cid + 4]
                ax.plot([x, nx], [y - node_r, ny + node_r],
                        color=grid_color, linewidth=3, zorder=1)

    # Draw nodes
    for cid, (x, y) in positions.items():
        circle = plt.Circle((x, y), node_r, color=node_color, zorder=5)
        ax.add_patch(circle)
        ax.text(x, y, str(cid), ha='center', va='center', fontsize=5,
                color='white', fontweight='bold', zorder=6)

    return positions, node_r


def draw_arrow(ax, positions, node_r, a, b, color='#D62728', lw=1.5):
    """Draw arrow from node a to node b."""
    ax1, ay1 = positions[a]
    bx1, by1 = positions[b]
    dx = bx1 - ax1
    dy = by1 - ay1
    dist = np.sqrt(dx**2 + dy**2)
    ux, uy = dx / dist * (node_r + 0.03), dy / dist * (node_r + 0.03)
    ax.annotate('', xy=(bx1 - ux, by1 - uy),
                xytext=(ax1 + ux, ay1 + uy),
                arrowprops=dict(arrowstyle='->', color=color, lw=lw),
                zorder=4)


fig, axes = plt.subplots(1, 2, figsize=(3.5, 1.8))

# (a) Adjacent-only
pos, nr = draw_grid(axes[0], '(a) Adjacent: 6 hops')
for a, b in [(0, 1), (1, 2), (2, 3), (3, 7), (7, 11), (11, 15)]:
    draw_arrow(axes[0], pos, nr, a, b, color='#D62728', lw=1.5)

# (b) With express link C0→C3
pos, nr = draw_grid(axes[1], '(b) Express: 4 hops')

# Express link: green curved arrow C0→C3
ax1, ay1 = pos[0]
bx1, by1 = pos[3]
axes[1].annotate('', xy=(bx1, by1 + nr + 0.02),
                 xytext=(ax1, ay1 + nr + 0.02),
                 arrowprops=dict(arrowstyle='->', color='#2CA02C',
                                 lw=2.0, connectionstyle='arc3,rad=-0.25'),
                 zorder=4)

# Remaining path: red arrows C3→C7→C11→C15
for a, b in [(3, 7), (7, 11), (11, 15)]:
    draw_arrow(axes[1], pos, nr, a, b, color='#D62728', lw=1.5)

plt.tight_layout()
fig.savefig(FIGURES_DIR / 'fig_phantom_4x4.pdf', bbox_inches='tight')
fig.savefig(FIGURES_DIR / 'fig_phantom_4x4.png', bbox_inches='tight')
plt.close()
print("[OK] fig_phantom_4x4.pdf")
