"""
Phantom load explanation figure — 1D example, clear and simple.
(a) Adjacent-only: C0→C3 creates phantom load on intermediate links
(b) With express link: direct connection, intermediate links freed
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path

FIGURES_DIR = Path(__file__).parent / 'paper' / 'figures'

fig, axes = plt.subplots(2, 1, figsize=(3.5, 2.4))

node_color = '#4A90D9'
node_r = 0.18
positions = [0.5, 1.5, 2.5, 3.5]
labels = ['C0', 'C1', 'C2', 'C3']

for ax_idx, ax in enumerate(axes):
    ax.set_xlim(-0.1, 4.5)
    ax.set_ylim(-0.5, 0.8)
    ax.set_aspect('equal')
    ax.axis('off')

    # Draw adjacent links (gray base)
    for i in range(3):
        ax.plot([positions[i] + node_r, positions[i + 1] - node_r],
                [0, 0], color='#CCCCCC', linewidth=4, zorder=1)

    # Draw nodes
    for i, (x, label) in enumerate(zip(positions, labels)):
        circle = plt.Circle((x, 0), node_r, color=node_color, zorder=5)
        ax.add_patch(circle)
        ax.text(x, 0, label, ha='center', va='center', fontsize=6,
                color='white', fontweight='bold', zorder=6)

    if ax_idx == 0:
        # (a) Adjacent-only: phantom load
        ax.set_title('(a) Adjacent-only: C0→C3 = 3 hops', fontsize=7, pad=3)

        # Traffic path: C0 → C1 → C2 → C3
        arrow_y = 0.15
        for i in range(3):
            color = '#D62728' if i > 0 else '#D62728'
            ax.annotate('', xy=(positions[i + 1] - node_r - 0.05, arrow_y),
                        xytext=(positions[i] + node_r + 0.05, arrow_y),
                        arrowprops=dict(arrowstyle='->', color=color,
                                        lw=1.8))

        # Label phantom load
        ax.text(1.5, -0.35, 'phantom', fontsize=5.5, ha='center',
                color='#D62728', style='italic')
        ax.text(2.5, -0.35, 'phantom', fontsize=5.5, ha='center',
                color='#D62728', style='italic')

        # Highlight phantom links
        ax.plot([positions[1] + node_r, positions[2] - node_r],
                [0, 0], color='#D62728', linewidth=4, zorder=2, alpha=0.4)
        ax.plot([positions[2] + node_r, positions[3] - node_r],
                [0, 0], color='#D62728', linewidth=4, zorder=2, alpha=0.4)

    else:
        # (b) With express link
        ax.set_title('(b) With express link: C0→C3 = 1 hop', fontsize=7, pad=3)

        # Express link arc
        from matplotlib.patches import FancyArrowPatch
        import matplotlib.patches as mpatches

        # Draw express link as curved arrow
        ax.annotate('', xy=(positions[3] - node_r, 0.12),
                    xytext=(positions[0] + node_r, 0.12),
                    arrowprops=dict(arrowstyle='->', color='#2CA02C',
                                    lw=2.0,
                                    connectionstyle='arc3,rad=-0.3'))

        ax.text(2.0, 0.62, 'express', fontsize=5.5, ha='center',
                color='#2CA02C', fontweight='bold')

        # Freed links
        ax.text(1.5, -0.35, 'freed', fontsize=5.5, ha='center',
                color='#2CA02C', style='italic')
        ax.text(2.5, -0.35, 'freed', fontsize=5.5, ha='center',
                color='#2CA02C', style='italic')

        # Green highlight on freed links
        ax.plot([positions[1] + node_r, positions[2] - node_r],
                [0, 0], color='#2CA02C', linewidth=4, zorder=2, alpha=0.3)
        ax.plot([positions[2] + node_r, positions[3] - node_r],
                [0, 0], color='#2CA02C', linewidth=4, zorder=2, alpha=0.3)

plt.tight_layout()
fig.savefig(FIGURES_DIR / 'fig_phantom_explain.pdf', bbox_inches='tight')
fig.savefig(FIGURES_DIR / 'fig_phantom_explain.png', bbox_inches='tight')
plt.close()
print("[OK] fig_phantom_explain.pdf")
