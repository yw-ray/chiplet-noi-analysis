"""Generate current-paper concept figures.

The figures match the V2/V3 experiment framing:
  1. Detailed 2.5D chiplet NoI package schematic.
  2. Current topology baselines: Mesh, Kite-S/M/L, GIA, Ours.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.lines as mlines
import matplotlib.patches as patches
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch

from baselines import kite_alloc, mesh_alloc
from noi_topology_synthesis import ChipletGrid


ROOT = Path(__file__).parent
FIG_DIR = ROOT / "paper" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams.update(
    {
        "font.family": "DejaVu Serif",
        "font.size": 6.7,
        "axes.titlesize": 7.2,
        "figure.dpi": 180,
        "savefig.dpi": 300,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    }
)

NAVY = "#1f3552"
CHIP = "#e9f3ff"
CHIP2 = "#d7eaff"
HBM = "#f8e7c0"
PHY = "#26384f"
MESH = "#9aa2ad"
KITE_S = "#d38a25"
KITE_M = "#c4682d"
KITE_L = "#a24c26"
SUPERSET = "#b8bdc5"
MASK_MOE = "#2f7d32"
MASK_HYBRID = "#1764b3"
INTERPOSER = "#f1ddbb"
SUBSTRATE = "#d8d8d8"
METAL = "#b47b37"
TRAFFIC = "#b72222"


def link(ax, p0, p1, color, lw=1.0, alpha=1.0, curve=0.0, z=2, ls="-"):
    if curve:
        ax.add_patch(
            FancyArrowPatch(
                p0,
                p1,
                arrowstyle="-",
                connectionstyle=f"arc3,rad={curve}",
                color=color,
                linewidth=lw,
                alpha=alpha,
                linestyle=ls,
                zorder=z,
                shrinkA=1,
                shrinkB=1,
            )
        )
    else:
        ax.plot(
            [p0[0], p1[0]],
            [p0[1], p1[1]],
            color=color,
            linewidth=lw,
            alpha=alpha,
            linestyle=ls,
            zorder=z,
            solid_capstyle="round",
        )


def chip_box(ax, x, y, w, h, label, fc=CHIP, lw=0.8, fontsize=5.5):
    ax.add_patch(
        patches.FancyBboxPatch(
            (x - w / 2, y - h / 2),
            w,
            h,
            boxstyle="round,pad=0.012,rounding_size=0.025",
            facecolor=fc,
            edgecolor=NAVY,
            linewidth=lw,
            zorder=5,
        )
    )
    ax.text(x, y, label, ha="center", va="center", fontsize=fontsize, color="#111", zorder=6)


def grid_positions(rows=4, cols=4, dx=0.56, dy=0.50):
    return {r * cols + c: (c * dx, (rows - 1 - r) * dy) for r in range(rows) for c in range(cols)}


def manhattan(i, j, cols=4):
    r1, c1 = divmod(i, cols)
    r2, c2 = divmod(j, cols)
    return abs(r1 - r2) + abs(c1 - c2)


def curve_for_pair(i, j, cols=4):
    r1, c1 = divmod(i, cols)
    r2, c2 = divmod(j, cols)
    d = manhattan(i, j, cols)
    if r1 == r2:
        return -0.18 - 0.035 * max(0, d - 2)
    if c1 == c2:
        return 0.18 + 0.035 * max(0, d - 2)
    return 0.10 if (i + j) % 2 == 0 else -0.10


def draw_nodes_and_mesh(ax, pos, rows=4, cols=4, labels=False, node_radius=0.085):
    for idx, p in pos.items():
        r, c = divmod(idx, cols)
        if c + 1 < cols:
            link(ax, p, pos[idx + 1], MESH, lw=0.65, alpha=0.75, z=1)
        if r + 1 < rows:
            link(ax, p, pos[idx + cols], MESH, lw=0.65, alpha=0.75, z=1)
    for idx, (x, y) in pos.items():
        ax.add_patch(patches.Circle((x, y), node_radius, facecolor=CHIP, edgecolor=NAVY, linewidth=0.65, zorder=5))
        if labels:
            ax.text(x, y - 0.19, str(idx), ha="center", va="center", fontsize=4.4, zorder=6)


def draw_alloc(ax, alloc, pos, color, max_edges=18, inactive=False):
    # Draw non-adjacent pairs first; adjacent capacity is implicit in the mesh.
    pairs = [(p, n) for p, n in alloc.items() if manhattan(p[0], p[1]) > 1 and n > 0]
    pairs.sort(key=lambda item: (-manhattan(item[0][0], item[0][1]), item[0][0], item[0][1]))
    for (i, j), n in pairs[:max_edges]:
        lw = 1.15 + 0.22 * min(n, 4)
        link(
            ax,
            pos[i],
            pos[j],
            color,
            lw=lw,
            alpha=0.72 if inactive else 0.9,
            curve=curve_for_pair(i, j),
            z=3,
        )


def read_ours_example():
    path = ROOT / "results" / "ml_placement" / "sweep_v2_full_subsets.json"
    if not path.exists():
        return {}, {}, {}
    data = json.loads(path.read_text())
    subset = "moe+hybrid_tp_pp+uniform_random+all_to_all"
    if subset not in data:
        subset = next((k for k in data if k.count("+") == 3), next(iter(data)))
    cell = "K16_N4" if "K16_N4" in data[subset] else next(iter(data[subset]))
    bpp = "bpp2" if "bpp2" in data[subset][cell] else next(iter(data[subset][cell]))
    entry = data[subset][cell][bpp]

    def parse_alloc(raw):
        out = {}
        for k, v in raw.items():
            a, b = k.split("-")
            out[(int(a), int(b))] = int(v)
        return out

    superset = parse_alloc(entry.get("superset", {}))
    workloads = entry.get("workloads", {})
    masks = {w: parse_alloc(v.get("final_mask", {})) for w, v in workloads.items() if v.get("final_mask")}
    return superset, masks, {"subset": subset, "cell": cell, "bpp": bpp}


def make_chiplet_top_view():
    """Detailed top-view package schematic."""
    fig, ax = plt.subplots(figsize=(4.8, 3.75))
    ax.set_aspect("equal")
    ax.set_xlim(-1.05, 5.15)
    ax.set_ylim(-0.78, 4.35)
    ax.axis("off")
    ax.text(-0.98, 4.12, "Top view: 2.5D chiplet NoI on silicon interposer", fontsize=7.4, fontweight="bold")

    ax.add_patch(
        patches.FancyBboxPatch(
            (-0.48, -0.28),
            4.95,
            3.95,
            boxstyle="round,pad=0.02,rounding_size=0.06",
            facecolor="#fff7e8",
            edgecolor="#6a5435",
            linewidth=0.9,
            zorder=0,
        )
    )
    ax.add_patch(patches.Rectangle((-0.28, -0.08), 4.55, 3.55, fill=False, ec="#c7aa7a", lw=0.55, ls="--", zorder=0))
    ax.text(1.98, 3.43, "silicon interposer routing field", ha="center", fontsize=5.8, color="#6a5435")

    # HBM stacks with small TSV/bump arrays.
    for x, y in [(-0.04, 3.02), (4.02, 3.02), (-0.04, 0.23), (4.02, 0.23)]:
        chip_box(ax, x, y, 0.62, 0.48, "HBM", fc=HBM, fontsize=5.0)
        for rr in range(2):
            for cc in range(4):
                ax.add_patch(patches.Circle((x - 0.20 + cc * 0.13, y - 0.11 + rr * 0.19), 0.018, color="#7b6b52", zorder=7))

    pitch = 0.66
    x0, y0 = 0.78, 0.61
    coords = {}
    for r in range(4):
        for c in range(4):
            idx = r * 4 + c
            x = x0 + c * pitch
            y = y0 + (3 - r) * pitch
            coords[idx] = (x, y)

    for idx, p in coords.items():
        r, c = divmod(idx, 4)
        if c < 3:
            link(ax, p, coords[idx + 1], MESH, lw=1.15, alpha=0.65, z=1)
        if r < 3:
            link(ax, p, coords[idx + 4], MESH, lw=1.15, alpha=0.65, z=1)

    express_specs = [
        ((0, 3), MASK_HYBRID, 2.3, -0.20),
        ((2, 14), MASK_HYBRID, 2.25, 0.18),
        ((4, 10), MASK_MOE, 2.15, 0.07),
        ((1, 13), SUPERSET, 1.75, -0.16),
        ((8, 11), SUPERSET, 1.75, 0.18),
    ]
    for (a, b), color, lw, curve in express_specs:
        link(ax, coords[a], coords[b], color, lw=lw, alpha=0.88, curve=curve, z=3)

    for idx, (x, y) in coords.items():
        # Chiplet body.
        chip_box(ax, x, y, 0.45, 0.37, f"C{idx}", fc=CHIP2, fontsize=4.7)
        # Internal router / compute blocks: just enough detail to avoid a
        # generic square while staying legible at column width.
        ax.add_patch(patches.Rectangle((x - 0.16, y + 0.085), 0.075, 0.045, fc="#b9d4ee", ec="none", zorder=7))
        ax.add_patch(patches.Rectangle((x + 0.085, y + 0.085), 0.075, 0.045, fc="#b9d4ee", ec="none", zorder=7))
        ax.add_patch(patches.Circle((x, y - 0.075), 0.032, fc="#7aa6cf", ec="none", zorder=7))
        # D2D PHY slots on all edges.
        for k in range(4):
            ax.add_patch(patches.Rectangle((x - 0.165 + 0.092 * k, y - 0.235), 0.047, 0.028, color=PHY, zorder=7))
            ax.add_patch(patches.Rectangle((x - 0.165 + 0.092 * k, y + 0.207), 0.047, 0.028, color=PHY, zorder=7))
        for k in range(3):
            ax.add_patch(patches.Rectangle((x - 0.245, y - 0.105 + 0.085 * k), 0.028, 0.045, color=PHY, zorder=7))
            ax.add_patch(patches.Rectangle((x + 0.217, y - 0.105 + 0.085 * k), 0.028, 0.045, color=PHY, zorder=7))

    label_box = dict(boxstyle="round,pad=0.16,rounding_size=0.03", fc="white", ec="#d8d8d8", lw=0.5, alpha=0.97)
    ax.annotate("D2D beachfront\nPHY slots", xy=(coords[7][0] + 0.22, coords[7][1]), xytext=(4.52, 2.22),
                fontsize=5.1, ha="center", bbox=label_box, arrowprops=dict(arrowstyle="->", lw=0.55, color="#333"))
    ax.annotate("runtime-active\nmask links", xy=((coords[2][0] + coords[14][0]) / 2, 1.58), xytext=(4.48, 1.05),
                fontsize=5.1, color=MASK_HYBRID, ha="center", bbox=label_box,
                arrowprops=dict(arrowstyle="->", lw=0.65, color=MASK_HYBRID))
    ax.annotate("compute tile\n+ local router", xy=(coords[5][0], coords[5][1] + 0.08), xytext=(-0.47, 1.70),
                fontsize=5.0, ha="center", bbox=label_box, arrowprops=dict(arrowstyle="->", lw=0.5, color="#333"))
    ax.text(2.0, -0.43, "grey: mandatory adjacent mesh    blue/green: active links    light grey: inactive superset",
            ha="center", fontsize=4.9, color="#555")

    handles = [
        mlines.Line2D([], [], color=MESH, lw=1.5, label="adjacent mesh"),
        mlines.Line2D([], [], color=MASK_HYBRID, lw=2.0, label="active mask"),
        mlines.Line2D([], [], color=SUPERSET, lw=2.0, label="inactive superset"),
        patches.Patch(facecolor=PHY, label="D2D PHY"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=4, frameon=False, fontsize=5.7, bbox_to_anchor=(0.5, -0.015))
    fig.subplots_adjust(left=0.02, right=0.98, top=0.96, bottom=0.15)
    fig.savefig(FIG_DIR / "fig_chiplet_top_view.pdf", bbox_inches="tight")
    fig.savefig(FIG_DIR / "fig_chiplet_top_view.png", bbox_inches="tight")
    plt.close(fig)


def make_chiplet_side_view():
    """Detailed cross-section package schematic."""
    fig, ax = plt.subplots(figsize=(5.15, 2.95))
    ax.set_xlim(0, 10.2)
    ax.set_ylim(0, 5.65)
    ax.axis("off")
    ax.text(0.0, 5.42, "Side view: chiplets on a silicon interposer", fontsize=7.4, fontweight="bold")

    dies = [(0.95, "C0", CHIP2), (2.65, "C1", CHIP2), (4.35, "C2", CHIP2), (6.05, "C3", CHIP2), (8.25, "HBM", HBM)]
    for x, label, fc in dies:
        # Silicon die with a darker active layer strip.
        chip_box(ax, x, 4.58, 1.02, 0.58, label, fc=fc, fontsize=5.6)
        ax.add_patch(patches.Rectangle((x - 0.42, 4.30), 0.84, 0.055, fc="#91b8dc" if label != "HBM" else "#d1b36d", ec="none", zorder=6))
        # Micro-bumps.
        for k in range(6):
            ax.add_patch(patches.Circle((x - 0.38 + 0.15 * k, 4.05), 0.036, color="#555", zorder=7))
        ax.plot([x, x], [4.02, 3.38], color="#6c5a3b", lw=0.72)

    # Underfill between dies and interposer.
    ax.add_patch(patches.Rectangle((0.35, 3.52), 8.95, 0.18, facecolor="#f6f0e8", edgecolor="none", zorder=0))
    ax.text(9.55, 3.60, "underfill", fontsize=4.9, va="center", color="#777")

    ax.add_patch(patches.Rectangle((0.35, 1.55), 8.95, 1.95, facecolor=INTERPOSER, edgecolor="#4a3a25", lw=0.85))
    ax.text(4.82, 3.24, "silicon interposer", ha="center", fontsize=6.1)
    ax.text(9.55, 2.43, "few\nrouting\nlayers", ha="left", va="center", fontsize=5.0, color="#5b3f1e")
    metal_ys = [3.00, 2.54, 2.08, 1.72]
    for y in metal_ys:
        ax.plot([0.65, 9.0], [y, y], color=METAL, lw=0.95)
    ax.text(0.72, 1.80, "RDL/metal stack", fontsize=4.9, color="#5b3f1e")

    # Adjacent and express channels on different metal layers.
    link(ax, (0.95, 3.00), (2.65, 3.00), MESH, lw=2.05)
    link(ax, (2.65, 3.00), (4.35, 3.00), MESH, lw=2.05)
    link(ax, (0.95, 2.54), (6.05, 2.54), MASK_HYBRID, lw=2.45)
    # Via drops into the lower metal layer for express link.
    for x in [0.95, 6.05]:
        ax.plot([x, x], [3.00, 2.54], color=MASK_HYBRID, lw=0.75, ls=":")
        ax.add_patch(patches.Circle((x, 2.54), 0.036, fc=MASK_HYBRID, ec="none", zorder=7))
    ax.text(1.78, 3.13, "adjacent D2D", ha="center", fontsize=5.2, color="#666")
    ax.text(3.50, 2.26, "long express / reconfigurable channel", ha="center", fontsize=5.2, color=MASK_HYBRID)

    # TSV / C4 bumps down to substrate.
    for x in [0.85, 2.6, 4.3, 6.05, 8.25]:
        ax.plot([x, x], [1.55, 1.26], color="#6c5a3b", lw=0.75)
        ax.add_patch(patches.Circle((x, 1.25), 0.045, color="#555", zorder=7))

    ax.add_patch(patches.Rectangle((0.35, 0.50), 8.95, 0.65, facecolor=SUBSTRATE, edgecolor="#555", lw=0.75))
    for y in [0.68, 0.92]:
        ax.plot([0.62, 9.05], [y, y], color="#9b9b9b", lw=0.55, alpha=0.7)
    ax.text(4.82, 0.83, "package substrate", ha="center", va="center", fontsize=5.8)

    handles = [
        mlines.Line2D([], [], color=MESH, lw=1.7, label="adjacent link"),
        mlines.Line2D([], [], color=MASK_HYBRID, lw=2.1, label="express link"),
        mlines.Line2D([], [], color=METAL, lw=1.2, label="interposer metal"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False, fontsize=5.7, bbox_to_anchor=(0.5, -0.02))
    fig.subplots_adjust(left=0.03, right=0.98, top=0.94, bottom=0.17)
    fig.savefig(FIG_DIR / "fig_chiplet_side_view.pdf", bbox_inches="tight")
    fig.savefig(FIG_DIR / "fig_chiplet_side_view.png", bbox_inches="tight")
    plt.close(fig)


def make_chiplet_detail_figure():
    """Compatibility wrapper: create separate views and a small combined preview."""
    make_chiplet_top_view()
    make_chiplet_side_view()

    fig, axes = plt.subplots(1, 2, figsize=(7.25, 2.85))
    for ax, img_path, title in [
        (axes[0], FIG_DIR / "fig_chiplet_top_view.png", "(a) Top view"),
        (axes[1], FIG_DIR / "fig_chiplet_side_view.png", "(b) Side view"),
    ]:
        img = plt.imread(img_path)
        ax.imshow(img)
        ax.set_title(title, fontsize=7)
        ax.axis("off")
    fig.subplots_adjust(left=0.01, right=0.99, top=0.88, bottom=0.02, wspace=0.05)
    fig.savefig(FIG_DIR / "fig_chiplet_noi_detail.pdf", bbox_inches="tight")
    fig.savefig(FIG_DIR / "fig_chiplet_noi_detail.png", bbox_inches="tight")
    fig.savefig(FIG_DIR / "fig_noi_2p5d_overview.pdf", bbox_inches="tight")
    fig.savefig(FIG_DIR / "fig_noi_2p5d_overview.png", bbox_inches="tight")
    plt.close(fig)


def topology_panel(ax, title, alloc, color, note, max_edges=16):
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_xlim(-0.28, 1.95)
    ax.set_ylim(-0.35, 1.82)
    ax.set_title(title, fontsize=7.2, pad=1.5)
    pos = grid_positions(dx=0.45, dy=0.39)
    draw_nodes_and_mesh(ax, pos, node_radius=0.07)
    if alloc:
        draw_alloc(ax, alloc, pos, color, max_edges=max_edges)
    ax.text(0.68, -0.24, note, ha="center", fontsize=5.2, color="#333")


def make_current_topology_figure():
    grid = ChipletGrid(4, 4)
    budget = len(grid.get_adj_pairs()) * 2
    cap = 4
    allocs = {
        "Mesh": mesh_alloc(grid, budget, cap),
        "Kite-S": kite_alloc(grid, budget, cap, "small"),
        "Kite-M": kite_alloc(grid, budget, cap, "medium"),
        "Kite-L": kite_alloc(grid, budget, cap, "large"),
    }
    superset, masks, meta = read_ours_example()

    fig, axes = plt.subplots(2, 3, figsize=(7.25, 3.7))
    fig.text(0.015, 0.965, "Topology baselines used in the current multi-workload sweep", fontsize=8, fontweight="bold")
    topology_panel(axes[0, 0], "(a) Mesh", allocs["Mesh"], MESH, "adjacent capacity only", max_edges=0)
    topology_panel(axes[0, 1], "(b) Kite-S", allocs["Kite-S"], KITE_S, "distance-2 family", max_edges=14)
    topology_panel(axes[0, 2], "(c) Kite-M", allocs["Kite-M"], KITE_M, "distance-2/3 mixed", max_edges=14)
    topology_panel(axes[1, 0], "(d) Kite-L", allocs["Kite-L"], KITE_L, "distance-3 family", max_edges=14)

    # Ours as two explicit panels: design-time superset and runtime mask.
    ax = axes[1, 1]
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_xlim(-0.28, 1.95)
    ax.set_ylim(-0.35, 1.82)
    ax.set_title("(e) Ours: superset", fontsize=7.2, pad=1.5)
    pos = grid_positions(dx=0.45, dy=0.39)
    draw_nodes_and_mesh(ax, pos, node_radius=0.07)
    draw_alloc(ax, superset, pos, SUPERSET, max_edges=16, inactive=True)
    ax.text(0.68, -0.24, "joint RL over workload set", ha="center", fontsize=5.2, color="#333")

    ax = axes[1, 2]
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_xlim(-0.28, 1.95)
    ax.set_ylim(-0.35, 1.82)
    ax.set_title("(f) Ours: masks", fontsize=7.2, pad=1.5)
    draw_nodes_and_mesh(ax, pos, node_radius=0.07)
    draw_alloc(ax, superset, pos, SUPERSET, max_edges=16, inactive=True)
    # Overlay two masks if available.
    for workload, color in [("moe", MASK_MOE), ("hybrid_tp_pp", MASK_HYBRID)]:
        if workload in masks:
            draw_alloc(ax, masks[workload], pos, color, max_edges=9)
    ax.text(0.68, -0.24, "per-workload activation", ha="center", fontsize=5.2, color="#333")
    if meta:
        ax.text(1.93, 1.66, f"{meta['cell']} {meta['bpp']}", ha="right", fontsize=4.7, color="#555")

    handles = [
        mlines.Line2D([], [], color=MESH, lw=1.0, label="mandatory mesh"),
        mlines.Line2D([], [], color=KITE_S, lw=1.8, label="Kite static"),
        mlines.Line2D([], [], color=SUPERSET, lw=1.8, label="ours superset"),
        mlines.Line2D([], [], color=MASK_MOE, lw=1.8, label="MoE mask"),
        mlines.Line2D([], [], color=MASK_HYBRID, lw=1.8, label="Hybrid mask"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=5, frameon=False, fontsize=5.5, bbox_to_anchor=(0.5, -0.01))
    fig.subplots_adjust(left=0.03, right=0.99, top=0.89, bottom=0.16, wspace=0.18, hspace=0.38)
    fig.savefig(FIG_DIR / "fig_current_topology_baselines.pdf", bbox_inches="tight")
    fig.savefig(FIG_DIR / "fig_current_topology_baselines.png", bbox_inches="tight")
    # Backward-compatible names for the running server links.
    fig.savefig(FIG_DIR / "fig_topology_comparison.pdf", bbox_inches="tight")
    fig.savefig(FIG_DIR / "fig_topology_comparison.png", bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    make_chiplet_detail_figure()
    make_current_topology_figure()
    print(FIG_DIR / "fig_chiplet_noi_detail.pdf")
    print(FIG_DIR / "fig_current_topology_baselines.pdf")
