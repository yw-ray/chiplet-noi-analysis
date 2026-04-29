"""Explanatory figure: Flattened Butterfly on a 4x4 chiplet grid.

Two panels: (a) Pure Flattened Butterfly: row + column all-to-all.
            (b) Our FBfly-style allocator: row/col with max_dist=3, iso-budget.
"""
import matplotlib.pyplot as plt
import matplotlib as mpl
import matplotlib.patches as mp
import numpy as np

mpl.rcParams.update({
    'font.size': 7, 'axes.titlesize': 8, 'axes.labelsize': 7,
    'xtick.labelsize': 6, 'ytick.labelsize': 6,
    'lines.linewidth': 1.2,
})

R, C = 4, 4

def draw_grid(ax, R=4, C=4, title=''):
    ax.set_xlim(-0.6, C - 0.4)
    ax.set_ylim(-0.6, R - 0.4)
    ax.set_aspect('equal')
    ax.set_title(title)
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    # chiplets
    for r in range(R):
        for c in range(C):
            idx = r * C + c
            ax.add_patch(mp.FancyBboxPatch(
                (c - 0.18, r - 0.18), 0.36, 0.36,
                boxstyle="round,pad=0.02",
                fc='#FFE4B5', ec='black', linewidth=0.6, zorder=3))
            ax.text(c, r, f'{idx}', ha='center', va='center',
                    fontsize=6, zorder=4, fontweight='bold')

def coord(idx, C=4):
    return (idx % C, idx // C)

def draw_link(ax, i, j, color, lw, alpha=0.7, curve=0.0, zorder=1):
    (x1, y1) = coord(i); (x2, y2) = coord(j)
    if curve == 0:
        ax.plot([x1, x2], [y1, y2], color=color, lw=lw, alpha=alpha, zorder=zorder)
    else:
        from matplotlib.patches import FancyArrowPatch
        arr = FancyArrowPatch((x1, y1), (x2, y2),
                              connectionstyle=f"arc3,rad={curve}",
                              arrowstyle='-', color=color, lw=lw,
                              alpha=alpha, zorder=zorder)
        ax.add_patch(arr)

def hop_dist(i, j, C=4):
    (x1, y1) = coord(i, C); (x2, y2) = coord(j, C)
    return abs(x1 - x2) + abs(y1 - y2)

# --- Panel (a): Pure Flattened Butterfly (row+col all-to-all, no distance cap) ---
fig, axes = plt.subplots(1, 2, figsize=(7, 3.4))
ax = axes[0]
draw_grid(ax, R, C, '(a) Pure Flattened Butterfly\n(row+col all-to-all, any distance)')

# Adjacent mesh (gray base)
for r in range(R):
    for c in range(C):
        idx = r * C + c
        if c + 1 < C:
            draw_link(ax, idx, idx + 1, '#999999', 0.6, alpha=0.5, zorder=1)
        if r + 1 < R:
            draw_link(ax, idx, idx + C, '#999999', 0.6, alpha=0.5, zorder=1)

# Row all-to-all (blue) — every same-row pair, any distance
for r in range(R):
    chiplets = [r * C + c for c in range(C)]
    for i in range(len(chiplets)):
        for j in range(i + 1, len(chiplets)):
            a, b = chiplets[i], chiplets[j]
            d = hop_dist(a, b, C)
            if d >= 2:
                curve = 0.0 if d == 2 else (-0.25 if d == 3 else -0.4)
                draw_link(ax, a, b, '#1f77b4', 1.0, alpha=0.7, curve=curve, zorder=2)

# Column all-to-all (green)
for c in range(C):
    chiplets = [r * C + c for r in range(R)]
    for i in range(len(chiplets)):
        for j in range(i + 1, len(chiplets)):
            a, b = chiplets[i], chiplets[j]
            d = hop_dist(a, b, C)
            if d >= 2:
                curve = 0.0 if d == 2 else (0.25 if d == 3 else 0.4)
                draw_link(ax, a, b, '#2ca02c', 1.0, alpha=0.7, curve=curve, zorder=2)

# --- Panel (b): Our FBfly-style allocator (max_dist=3, iso-budget) ---
ax = axes[1]
draw_grid(ax, R, C, '(b) Our "FBfly-style" allocator\n(row+col, max_dist=3, iso-budget)')

# Adjacent mesh
for r in range(R):
    for c in range(C):
        idx = r * C + c
        if c + 1 < C:
            draw_link(ax, idx, idx + 1, '#999999', 0.6, alpha=0.5, zorder=1)
        if r + 1 < R:
            draw_link(ax, idx, idx + C, '#999999', 0.6, alpha=0.5, zorder=1)

# Row pairs but only 2 <= hop <= 3 (distance 3 is max in 4x4)
for r in range(R):
    chiplets = [r * C + c for c in range(C)]
    for i in range(len(chiplets)):
        for j in range(i + 1, len(chiplets)):
            a, b = chiplets[i], chiplets[j]
            d = hop_dist(a, b, C)
            if 2 <= d <= 3:
                curve = 0.0 if d == 2 else -0.25
                draw_link(ax, a, b, '#1f77b4', 1.0, alpha=0.7, curve=curve, zorder=2)

# Column pairs but only 2 <= hop <= 3
for c in range(C):
    chiplets = [r * C + c for r in range(R)]
    for i in range(len(chiplets)):
        for j in range(i + 1, len(chiplets)):
            a, b = chiplets[i], chiplets[j]
            d = hop_dist(a, b, C)
            if 2 <= d <= 3:
                curve = 0.0 if d == 2 else 0.25
                draw_link(ax, a, b, '#2ca02c', 1.0, alpha=0.7, curve=curve, zorder=2)

# Legend on whole figure
import matplotlib.lines as mlines
legend_handles = [
    mlines.Line2D([], [], color='#999999', lw=0.8, alpha=0.7, label='Mesh adj. links'),
    mlines.Line2D([], [], color='#1f77b4', lw=1.2, alpha=0.7, label='Row express links'),
    mlines.Line2D([], [], color='#2ca02c', lw=1.2, alpha=0.7, label='Column express links'),
]
fig.legend(handles=legend_handles, loc='lower center', ncol=3,
           bbox_to_anchor=(0.5, -0.02), frameon=False)

plt.tight_layout()
plt.subplots_adjust(bottom=0.12)
plt.savefig('/tmp/fbfly_explain.png', dpi=200, bbox_inches='tight')
plt.savefig('/tmp/fbfly_explain.pdf', dpi=300, bbox_inches='tight')
print('Saved /tmp/fbfly_explain.{png,pdf}')
