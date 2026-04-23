"""Generate fig_interposer_structure.pdf: physical structure + adj-only problem + express solution."""
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyArrowPatch, Rectangle, Circle

plt.rcParams.update({
    'font.size': 6, 'axes.titlesize': 7, 'axes.labelsize': 6,
    'xtick.labelsize': 5.5, 'ytick.labelsize': 5.5, 'legend.fontsize': 5.5,
    'figure.dpi': 150, 'savefig.dpi': 300,
    'font.family': 'sans-serif', 'font.sans-serif': ['DejaVu Sans'],
})

fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.3))

# ============ Panel (a): Cross-section of interposer ============
ax = axes[0]
ax.set_xlim(0, 10); ax.set_ylim(0, 7)
ax.set_aspect('equal')

# Chiplets on top
for i, x in enumerate([0.8, 4.2, 7.6]):
    r = Rectangle((x, 5.2), 1.8, 1.3, facecolor='#b0d4f1', edgecolor='black', linewidth=0.8)
    ax.add_patch(r)
    ax.text(x+0.9, 5.85, f'Chiplet {i}', ha='center', va='center', fontsize=5.5, fontweight='bold')
    # micro-bumps (small dots below each chiplet)
    for bx in range(6):
        ax.add_patch(Circle((x+0.2+bx*0.28, 5.15), 0.06, color='#555'))

# Interposer body
inter = Rectangle((0.2, 2.2), 9.6, 2.8, facecolor='#f4e5c8', edgecolor='black', linewidth=0.8)
ax.add_patch(inter)
ax.text(5.0, 4.65, 'Silicon interposer', ha='center', fontsize=6, style='italic')

# Metal layers inside interposer (3 layers)
colors = ['#d4943a', '#a67338', '#7a5628']
for i, (y, col, label) in enumerate(zip([4.2, 3.5, 2.8], colors,
                                          ['Metal 1 (signal)', 'Metal 2 (signal)', 'Metal 3 (PWR/GND)'])):
    ax.plot([0.4, 9.6], [y, y], color=col, linewidth=1.2)
    ax.text(9.7, y, label, fontsize=4.8, va='center', ha='left')

# Adj wires in metal layers (short horizontal wires)
ax.plot([2.0, 3.8], [4.2, 4.2], color='#1f77b4', linewidth=2.2)
ax.plot([5.4, 7.2], [4.2, 4.2], color='#1f77b4', linewidth=2.2)
ax.text(2.9, 4.35, 'adj', fontsize=4.5, color='#1f77b4', ha='center')
ax.text(6.3, 4.35, 'adj', fontsize=4.5, color='#1f77b4', ha='center')

# Express wire (longer, on different layer, with via jumps)
ax.plot([2.0, 3.0], [3.5, 3.5], color='#d62728', linewidth=2.2)
ax.plot([3.0, 3.0], [3.5, 4.2], color='#d62728', linewidth=1.5, linestyle=':')  # via
ax.plot([3.0, 7.0], [4.2, 4.2], color='#d62728', linewidth=2.2, alpha=0.0)  # hidden
ax.plot([3.1, 3.1], [3.5, 3.5], color='#d62728', linewidth=2.2)
ax.plot([3.05, 7.0], [3.5, 3.5], color='#d62728', linewidth=2.2)  # long express wire on metal 2
ax.plot([7.0, 8.4], [3.5, 3.5], color='#d62728', linewidth=2.2)
ax.text(4.8, 3.35, 'express (long, spans 2 hops)', fontsize=4.5, color='#d62728', ha='center')

# TSVs and substrate
for tx in [1.5, 3.5, 5.5, 7.5, 9.0]:
    ax.plot([tx, tx], [2.3, 2.2], color='black', linewidth=1)
    ax.add_patch(Circle((tx, 2.2), 0.1, color='black'))

sub = Rectangle((0.2, 0.7), 9.6, 1.3, facecolor='#dddddd', edgecolor='black', linewidth=0.8)
ax.add_patch(sub)
ax.text(5.0, 1.35, 'Package substrate (8--12 layers)', ha='center', fontsize=5.5)

# Labels
ax.text(0.5, 6.75, '(a) Cross-section: chiplets on interposer', fontsize=6.5, fontweight='bold')
ax.annotate('micro-bumps', xy=(1.3, 5.15), xytext=(0.5, 6.0),
            fontsize=4.5, arrowprops=dict(arrowstyle='->', lw=0.3))
ax.annotate('TSV', xy=(3.5, 2.2), xytext=(3.5, 0.3),
            fontsize=4.5, ha='center', arrowprops=dict(arrowstyle='->', lw=0.3))
ax.axis('off')

# ============ Panel (b): Top-down, adj-only, phantom load ============
ax = axes[1]
ax.set_xlim(-0.3, 4.3); ax.set_ylim(-0.3, 4.3)
ax.set_aspect('equal')

# 4x4 grid of chiplets
for r in range(4):
    for c in range(4):
        rect = Rectangle((c, r), 0.8, 0.8, facecolor='#e8f0f8',
                         edgecolor='black', linewidth=0.5)
        ax.add_patch(rect)
        ax.text(c+0.4, r+0.4, f'C{r*4+c}', ha='center', va='center', fontsize=4.8)

# Adj links (gray)
for r in range(4):
    for c in range(4):
        if c < 3:
            ax.plot([c+0.8, c+1], [r+0.4, r+0.4], color='#888', linewidth=0.6)
        if r < 3:
            ax.plot([c+0.4, c+0.4], [r+0.8, r+1], color='#888', linewidth=0.6)

# Phantom load path: C0 → C15 via multi-hop (highlighted)
path_x = [0.4, 0.4, 0.4, 0.4, 1.4, 2.4, 3.4]
path_y = [0.4, 1.4, 2.4, 3.4, 3.4, 3.4, 3.4]
for i in range(len(path_x)-1):
    ax.plot([path_x[i], path_x[i+1]], [path_y[i], path_y[i+1]],
            color='#d62728', linewidth=2.5, alpha=0.7,
            solid_capstyle='round')

# Annotations
ax.add_patch(Circle((0.4, 0.4), 0.15, facecolor='#d62728', edgecolor='black', linewidth=0.5))
ax.add_patch(Circle((3.4, 3.4), 0.15, facecolor='#d62728', edgecolor='black', linewidth=0.5))
ax.text(0.4, 0.4, 'S', ha='center', va='center', fontsize=5, color='white', fontweight='bold')
ax.text(3.4, 3.4, 'D', ha='center', va='center', fontsize=5, color='white', fontweight='bold')
ax.annotate('6 hops', xy=(1.9, 3.6), xytext=(2.2, 4.2), fontsize=5, color='#d62728',
            arrowprops=dict(arrowstyle='->', lw=0.4, color='#d62728'))
ax.text(2.0, -0.2, 'Every intermediate link carries transit traffic (phantom load)',
        ha='center', fontsize=4.8, color='#d62728', style='italic')

ax.text(-0.3, 4.5, '(b) Adjacent-only NoI: multi-hop bottleneck', fontsize=6.5, fontweight='bold')
ax.axis('off')

# ============ Panel (c): Top-down, with express link ============
ax = axes[2]
ax.set_xlim(-0.3, 4.3); ax.set_ylim(-0.3, 4.3)
ax.set_aspect('equal')

# 4x4 grid
for r in range(4):
    for c in range(4):
        rect = Rectangle((c, r), 0.8, 0.8, facecolor='#e8f0f8',
                         edgecolor='black', linewidth=0.5)
        ax.add_patch(rect)
        ax.text(c+0.4, r+0.4, f'C{r*4+c}', ha='center', va='center', fontsize=4.8)

# Adj links
for r in range(4):
    for c in range(4):
        if c < 3:
            ax.plot([c+0.8, c+1], [r+0.4, r+0.4], color='#888', linewidth=0.6)
        if r < 3:
            ax.plot([c+0.4, c+0.4], [r+0.8, r+1], color='#888', linewidth=0.6)

# Express link C0 --> C3 (distance 3, horizontal)
ax.plot([0.5, 3.3], [0.25, 0.25], color='#2ca02c', linewidth=2.5,
        solid_capstyle='round')
ax.text(1.9, 0.0, 'express (d=3)', ha='center', fontsize=5, color='#2ca02c', fontweight='bold')

# New path C0 → express to C3 → C15 via 3 hops
# C0 -> (express) C3 -> C7 -> C11 -> C15
path_x2 = [0.4, 3.4, 3.4, 3.4]
path_y2 = [0.4, 0.4, 1.4, 3.4]
for i in range(len(path_x2)-1):
    if i == 0:
        # express jump
        ax.plot([path_x2[i], path_x2[i+1]], [path_y2[i], path_y2[i+1]],
                color='#2ca02c', linewidth=2.5, alpha=0.9)
    else:
        ax.plot([path_x2[i], path_x2[i+1]], [path_y2[i], path_y2[i+1]],
                color='#ff7f0e', linewidth=2.0, alpha=0.7)

# S, D markers
ax.add_patch(Circle((0.4, 0.4), 0.15, facecolor='#d62728', edgecolor='black', linewidth=0.5))
ax.add_patch(Circle((3.4, 3.4), 0.15, facecolor='#d62728', edgecolor='black', linewidth=0.5))
ax.text(0.4, 0.4, 'S', ha='center', va='center', fontsize=5, color='white', fontweight='bold')
ax.text(3.4, 3.4, 'D', ha='center', va='center', fontsize=5, color='white', fontweight='bold')
ax.annotate('1 express\n+ 3 adj hops', xy=(2.8, 1.8), xytext=(1.5, 2.8), fontsize=5, color='#2ca02c',
            arrowprops=dict(arrowstyle='->', lw=0.4, color='#2ca02c'))

ax.text(2.0, -0.2, 'Express link bypasses 3 intermediate links',
        ha='center', fontsize=4.8, color='#2ca02c', style='italic')
ax.text(-0.3, 4.5, '(c) With one express link: fewer hops, less phantom load',
        fontsize=6.5, fontweight='bold')
ax.axis('off')

fig.tight_layout(pad=0.5)
fig.savefig('paper/figures/fig_interposer_structure.pdf', bbox_inches='tight')
plt.close(fig)
print('saved fig_interposer_structure.pdf')
