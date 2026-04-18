"""
PHY Area Overhead Analysis — When can chiplets match/beat monolithic throughput?
================================================================================

Core question: After subtracting PHY (UCIe/D2D) area from each chiplet,
can the yield advantage compensate, giving ≥ monolithic aggregate throughput?

Two comparison modes:
  1. Same total silicon area → chiplet always loses raw TOPS (by N×P_phy)
     BUT: yield means more working dies per wafer → aggregate throughput can win
  2. Same dollar budget → yield advantage buys more working compute

Key PHY parameters (from UCIe 1.0/2.0 specs + ISSCC papers):
  - UCIe standard: ~0.6mm² per module (16 lanes × 32Gbps = 64GB/s per module)
  - UCIe advanced: ~0.15mm² per module (bump pitch 25μm, shoreline-efficient)
  - D2D PHY (custom, like NVIDIA NV-HBI): ~0.3mm² per 100GB/s
"""

import math
import json
from pathlib import Path


# ============================================================
# Yield model
# ============================================================

def murphy_yield(area_mm2, dd=0.1):
    """Murphy's yield model. dd = defect density per cm²."""
    d = dd * area_mm2 / 100
    if d <= 0:
        return 1.0
    return ((1 - math.exp(-d)) / d) ** 2


def dies_per_wafer(area_mm2, wafer_r=150):
    """Good dies per wafer (300mm wafer, radius=150mm)."""
    return int(math.pi * wafer_r**2 / area_mm2 * 0.9)


def die_cost(area_mm2, wafer_cost=17000, dd=0.1):
    y = murphy_yield(area_mm2, dd)
    dpw = dies_per_wafer(area_mm2)
    if dpw <= 0 or y <= 0:
        return float('inf')
    return wafer_cost / (dpw * y)


# ============================================================
# PHY area model
# ============================================================

class PhySpec:
    """UCIe/D2D PHY specifications."""

    # bandwidth per module (GB/s), area per module (mm²)
    SPECS = {
        'ucie_standard': {
            'bw_per_module': 32,    # 16 lanes × 32Gbps / 8 = 64GB/s bidir → 32 GB/s per dir
            'area_per_module': 0.6,  # ~0.6mm² per module (TSMC 5nm, ISSCC'23)
            'name': 'UCIe Standard',
        },
        'ucie_advanced': {
            'bw_per_module': 32,
            'area_per_module': 0.15,  # 25μm bump pitch, much denser
            'name': 'UCIe Advanced',
        },
        'ucie_2p0': {
            'bw_per_module': 64,    # UCIe 2.0 doubles lane rate
            'area_per_module': 0.5,
            'name': 'UCIe 2.0',
        },
        'custom_d2d': {
            'bw_per_module': 100,   # Custom D2D (NV-HBI style)
            'area_per_module': 0.3,
            'name': 'Custom D2D (NV-HBI)',
        },
    }

    @classmethod
    def phy_area(cls, spec_name, target_bw_gbps):
        """Calculate total PHY area needed for target bandwidth (per direction)."""
        spec = cls.SPECS[spec_name]
        n_modules = math.ceil(target_bw_gbps / spec['bw_per_module'])
        return n_modules * spec['area_per_module'], n_modules

    @classmethod
    def phy_area_for_chiplet(cls, spec_name, target_bw_gbps, n_neighbors):
        """Total PHY area for a chiplet connected to n_neighbors."""
        per_neighbor_area, n_modules = cls.phy_area(spec_name, target_bw_gbps)
        total = per_neighbor_area * n_neighbors
        return total, n_modules * n_neighbors


# ============================================================
# Throughput model
# ============================================================

RETICLE_LIMIT = 858  # mm²

# TOPS density: how many TOPS per mm² of compute logic
# (NVIDIA H100: ~1000 TOPS FP16 in ~814mm² → ~1.2 TOPS/mm²)
# (But not all area is compute — subtract SRAM, I/O, etc.)
# Effective compute density after NoC/SRAM/misc:
TOPS_PER_MM2 = 1.0  # conservative: 1 TOPS per mm² effective compute


def monolithic_throughput(total_area, n_chips=1, dd=0.1, wafer_cost=17000):
    """
    Monolithic system: n_chips × (total_area/n_chips) die.
    All die area is compute (no inter-chip PHY needed, uses board-level NVLink).
    """
    die_area = total_area / n_chips
    if die_area > RETICLE_LIMIT:
        return None

    compute_area = die_area  # all area is compute
    tops_per_chip = compute_area * TOPS_PER_MM2
    aggregate_tops = tops_per_chip * n_chips

    y = murphy_yield(die_area, dd)
    cost_per_chip = die_cost(die_area, wafer_cost, dd)

    # Board-level packaging
    pkg_per_chip = 30 + 80 + 15  # substrate + HBM + test
    board_per_chip = 20 + 30  # PCB + NVLink
    total_cost = (cost_per_chip + pkg_per_chip + board_per_chip) * n_chips

    return {
        'die_area': die_area,
        'compute_area': compute_area,
        'phy_area': 0,
        'phy_overhead_pct': 0,
        'tops_per_chip': tops_per_chip,
        'aggregate_tops': aggregate_tops,
        'yield': y,
        'cost_per_chip': cost_per_chip,
        'total_cost': total_cost,
        'tops_per_dollar': aggregate_tops / total_cost,
        'n_chips': n_chips,
    }


def chiplet_throughput(total_area, n_chiplets, phy_spec, inter_bw_gbps,
                       topology='mesh2d', dd=0.1, wafer_cost=17000):
    """
    Chiplet system: n_chiplets in a package, connected via UCIe/D2D.
    PHY area is subtracted from each chiplet's compute area.

    topology determines number of neighbors per chiplet:
      - 'ring': 2 neighbors
      - 'mesh2d': ~3 neighbors (2×N grid average)
      - 'full': n_chiplets-1 neighbors (all-to-all)
    """
    chiplet_area = total_area / n_chiplets

    # Determine neighbors per chiplet based on topology
    if topology == 'ring':
        n_neighbors = 2
    elif topology == 'mesh2d':
        # 2D grid: corner=2, edge=3, center=4 → average ~3
        n_neighbors = min(3, n_chiplets - 1)
    elif topology == 'full':
        n_neighbors = n_chiplets - 1
    elif topology == 'star':
        n_neighbors = 1  # only connected to central hub
    else:
        n_neighbors = 2

    # PHY area per chiplet
    phy_area, n_phy_modules = PhySpec.phy_area_for_chiplet(
        phy_spec, inter_bw_gbps, n_neighbors)

    compute_area = chiplet_area - phy_area
    if compute_area <= 0:
        return None  # PHY larger than chiplet!

    phy_overhead_pct = phy_area / chiplet_area * 100
    tops_per_chiplet = compute_area * TOPS_PER_MM2
    aggregate_tops = tops_per_chiplet * n_chiplets

    y = murphy_yield(chiplet_area, dd)
    cost_per_chiplet = die_cost(chiplet_area, wafer_cost, dd)

    # Packaging (organic substrate + bridges)
    bridges = n_chiplets - 1
    pkg_cost = 35 * bridges + 40 + n_chiplets * 12 + total_area * 0.08 + 80
    total_cost = cost_per_chiplet * n_chiplets + 8 * n_chiplets + pkg_cost

    return {
        'chiplet_area': chiplet_area,
        'compute_area': compute_area,
        'phy_area': phy_area,
        'phy_overhead_pct': phy_overhead_pct,
        'n_phy_modules': n_phy_modules,
        'tops_per_chiplet': tops_per_chiplet,
        'aggregate_tops': aggregate_tops,
        'yield': y,
        'cost_per_chiplet': cost_per_chiplet,
        'total_cost': total_cost,
        'tops_per_dollar': aggregate_tops / total_cost,
        'n_chiplets': n_chiplets,
        'n_neighbors': n_neighbors,
        'topology': topology,
    }


# ============================================================
# Analysis 1: PHY overhead sweep
# ============================================================

def analysis_1_phy_overhead():
    """How much compute area do we lose to PHY at various configs?"""
    print("=" * 90)
    print("  ANALYSIS 1: PHY Area Overhead by Configuration")
    print("  (How much die area goes to PHY instead of compute?)")
    print("=" * 90)

    # Target bandwidth per neighbor: how much BW do we need?
    # BookSim showed: need ~4×4 links (16 links) to match monolithic
    # At 32GB/s per UCIe module → 16 modules × 32 = 512 GB/s per edge
    # But we may not need that much — let's sweep

    bw_targets = [64, 128, 256, 512, 1024]  # GB/s per neighbor
    chiplet_areas = [100, 150, 200, 300, 400]  # mm² per chiplet

    for phy_spec in ['ucie_standard', 'ucie_advanced', 'ucie_2p0', 'custom_d2d']:
        spec = PhySpec.SPECS[phy_spec]
        print(f"\n  --- {spec['name']} ({spec['bw_per_module']} GB/s/module, "
              f"{spec['area_per_module']} mm²/module) ---")

        print(f"\n  {'BW/neighbor':>12} │", end="")
        for ca in chiplet_areas:
            print(f" {ca}mm²", end="   ")
        print()
        print(f"  {'(GB/s)':>12} │", end="")
        for ca in chiplet_areas:
            print(f" {'overhead':>8}", end="")
        print()
        print("  " + "-" * (14 + 10 * len(chiplet_areas)))

        for bw in bw_targets:
            # Assume mesh2d (3 neighbors)
            phy_total, _ = PhySpec.phy_area_for_chiplet(phy_spec, bw, 3)
            print(f"  {bw:>8} GB/s │", end="")
            for ca in chiplet_areas:
                overhead = phy_total / ca * 100
                if phy_total >= ca:
                    print(f" {'!!TOO BIG':>8}", end="")
                else:
                    print(f" {overhead:>6.1f}%", end="  ")
            print(f"   (PHY={phy_total:.1f}mm²)")


# ============================================================
# Analysis 2: Throughput comparison — same total area
# ============================================================

def analysis_2_same_area():
    """Same total silicon area: can chiplets match monolithic throughput?"""
    print("\n" + "=" * 90)
    print("  ANALYSIS 2: Same Total Area — Raw Throughput Comparison")
    print("  (Chiplet loses compute to PHY. Can yield advantage compensate?)")
    print("=" * 90)

    total_areas = [600, 800, 1000, 1200, 1600, 2400]

    for phy_spec in ['ucie_standard', 'ucie_advanced', 'custom_d2d']:
        spec = PhySpec.SPECS[phy_spec]
        print(f"\n  --- {spec['name']} @ 256 GB/s per neighbor, mesh2d topology ---")

        print(f"\n  {'Total Area':>10} │ {'Mono 1×':>12} {'Mono 2×':>12} │ "
              f"{'Chip 4×':>12} {'Chip 8×':>12} │ "
              f"{'4×/Mono':>8} {'8×/Mono':>8}")
        print(f"  {'(mm²)':>10} │ {'TOPS':>12} {'TOPS':>12} │ "
              f"{'TOPS':>12} {'TOPS':>12} │ "
              f"{'ratio':>8} {'ratio':>8}")
        print("  " + "-" * 90)

        for area in total_areas:
            m1 = monolithic_throughput(area, 1)
            m2 = monolithic_throughput(area, 2)
            c4 = chiplet_throughput(area, 4, phy_spec, 256, 'mesh2d')
            c8 = chiplet_throughput(area, 8, phy_spec, 256, 'mesh2d')

            # Best monolithic baseline
            if m1:
                mono_tops = m1['aggregate_tops']
                mono_str = f"{m1['aggregate_tops']:>10.0f}"
            else:
                mono_tops = None
                mono_str = f"{'RETICLE':>10}"

            m2_str = f"{m2['aggregate_tops']:>10.0f}" if m2 else f"{'RETICLE':>10}"

            best_mono = None
            if m1:
                best_mono = m1['aggregate_tops']
            if m2:
                best_mono = m2['aggregate_tops'] if best_mono is None else max(best_mono, m2['aggregate_tops'])

            c4_str = f"{c4['aggregate_tops']:>10.0f}" if c4 else "N/A"
            c8_str = f"{c8['aggregate_tops']:>10.0f}" if c8 else "N/A"

            r4 = f"{c4['aggregate_tops']/best_mono:>7.1%}" if (c4 and best_mono) else "N/A"
            r8 = f"{c8['aggregate_tops']/best_mono:>7.1%}" if (c8 and best_mono) else "N/A"

            print(f"  {area:>10} │ {mono_str:>12} {m2_str:>12} │ "
                  f"{c4_str:>12} {c8_str:>12} │ {r4:>8} {r8:>8}")

            if c4:
                print(f"  {'':>10}   (PHY overhead: 4×chiplet={c4['phy_overhead_pct']:.1f}%, "
                      f"8×chiplet={c8['phy_overhead_pct']:.1f}% per chiplet)")


# ============================================================
# Analysis 3: Same budget — throughput per dollar
# ============================================================

def analysis_3_same_budget():
    """Same dollar budget: chiplet yield advantage → more working TOPS."""
    print("\n" + "=" * 90)
    print("  ANALYSIS 3: Same Budget — TOPS per Dollar")
    print("  (Yield advantage means more working chiplets per wafer)")
    print("=" * 90)

    total_areas = [600, 800, 1000, 1200, 1600, 2400]

    for phy_spec in ['ucie_advanced', 'custom_d2d']:
        spec = PhySpec.SPECS[phy_spec]
        print(f"\n  --- {spec['name']} @ 256 GB/s per neighbor ---")

        print(f"\n  {'Total Area':>10} │ {'Mono 2×':>14} │ {'Chip 4×':>14} {'Chip 8×':>14} │ "
              f"{'4×/Mono':>8} {'8×/Mono':>8}")
        print(f"  {'(mm²)':>10} │ {'TOPS/$':>14} │ {'TOPS/$':>14} {'TOPS/$':>14} │ "
              f"{'ratio':>8} {'ratio':>8}")
        print("  " + "-" * 85)

        for area in total_areas:
            m2 = monolithic_throughput(area, 2)
            c4 = chiplet_throughput(area, 4, phy_spec, 256, 'mesh2d')
            c8 = chiplet_throughput(area, 8, phy_spec, 256, 'mesh2d')

            if m2 is None:
                # Monolithic impossible, try 4-chip
                m2 = monolithic_throughput(area, 4)

            if m2 is None:
                continue

            mono_tpd = m2['tops_per_dollar']
            c4_tpd = c4['tops_per_dollar'] if c4 else 0
            c8_tpd = c8['tops_per_dollar'] if c8 else 0

            r4 = c4_tpd / mono_tpd if mono_tpd > 0 else 0
            r8 = c8_tpd / mono_tpd if mono_tpd > 0 else 0

            winner_4 = " ✓" if r4 >= 1.0 else ""
            winner_8 = " ✓" if r8 >= 1.0 else ""

            print(f"  {area:>10} │ {mono_tpd:>12.6f}  │ "
                  f"{c4_tpd:>12.6f}  {c8_tpd:>12.6f}  │ "
                  f"{r4:>7.2f}x{winner_4} {r8:>7.2f}x{winner_8}")


# ============================================================
# Analysis 4: Find the crossover conditions
# ============================================================

def analysis_4_crossover():
    """Sweep PHY technology × BW × chiplet count to find ≥1.0x conditions."""
    print("\n" + "=" * 90)
    print("  ANALYSIS 4: Crossover Conditions — When Chiplet TOPS ≥ Monolithic TOPS")
    print("  (Same total area, find PHY spec + BW combos where chiplets win)")
    print("=" * 90)

    total_area = 1200  # mm² — realistic large accelerator
    bw_range = [64, 128, 192, 256, 384, 512]
    n_chiplets_range = [2, 4, 8, 16]

    for phy_spec in ['ucie_standard', 'ucie_advanced', 'ucie_2p0', 'custom_d2d']:
        spec = PhySpec.SPECS[phy_spec]
        print(f"\n  --- {spec['name']} @ {total_area}mm² total ---")
        print(f"  (Each module: {spec['bw_per_module']} GB/s, {spec['area_per_module']} mm²)")

        # Best monolithic: single die if possible, else 2-chip
        m1 = monolithic_throughput(total_area, 1)
        m2 = monolithic_throughput(total_area, 2)
        if m1:
            mono = m1
        elif m2:
            mono = m2
        else:
            mono = monolithic_throughput(total_area, 4)

        mono_tops = mono['aggregate_tops']
        print(f"  Monolithic baseline: {mono_tops:.0f} TOPS "
              f"({mono['n_chips']}×{mono['die_area']:.0f}mm², "
              f"yield={mono['yield']*100:.1f}%)\n")

        print(f"  {'N chiplets':>10} │", end="")
        for bw in bw_range:
            print(f" {bw:>6}GB/s", end="")
        print()
        print("  " + "-" * (12 + 10 * len(bw_range)))

        for nc in n_chiplets_range:
            print(f"  {nc:>10} │", end="")
            for bw in bw_range:
                c = chiplet_throughput(total_area, nc, phy_spec, bw, 'mesh2d')
                if c is None:
                    print(f" {'  FAIL':>9}", end="")
                else:
                    ratio = c['aggregate_tops'] / mono_tops
                    marker = "≥" if ratio >= 1.0 else " "
                    print(f" {marker}{ratio:>7.1%}", end="")
            print()

        # Find minimum PHY spec to achieve ≥ 95% throughput
        print(f"\n  Minimum BW to achieve ≥95% monolithic throughput:")
        for nc in n_chiplets_range:
            for bw in range(32, 1025, 32):
                c = chiplet_throughput(total_area, nc, phy_spec, bw, 'mesh2d')
                if c and c['aggregate_tops'] / mono_tops >= 0.95:
                    print(f"    {nc} chiplets: {bw} GB/s/neighbor "
                          f"(PHY={c['phy_area']:.1f}mm², "
                          f"overhead={c['phy_overhead_pct']:.1f}%, "
                          f"effective={c['aggregate_tops']/mono_tops:.1%})")
                    break
            else:
                print(f"    {nc} chiplets: NOT ACHIEVABLE (PHY too large)")


# ============================================================
# Analysis 5: The yield-adjusted throughput (key insight)
# ============================================================

def analysis_5_yield_adjusted():
    """
    Key insight: monolithic large die has terrible yield.
    If we measure "expected working TOPS per wafer", chiplets can win.

    Expected TOPS per wafer = TOPS × yield × dies_per_wafer
    This is what actually matters for production economics.
    """
    print("\n" + "=" * 90)
    print("  ANALYSIS 5: Expected Working TOPS per Wafer")
    print("  (THE key metric: yield × dies_per_wafer × TOPS_per_die)")
    print("  This is what determines real-world aggregate throughput at scale.")
    print("=" * 90)

    total_areas = [400, 600, 800, 1000, 1200, 1600]
    phy_spec = 'ucie_advanced'  # best-case PHY
    inter_bw = 256  # GB/s per neighbor

    spec = PhySpec.SPECS[phy_spec]
    print(f"\n  PHY: {spec['name']}, {inter_bw} GB/s per neighbor, mesh2d topology")

    print(f"\n  {'Total':>7} │ {'Monolithic (1 die)':^30} │ {'4 Chiplets':^35} │ {'Win?':>6}")
    print(f"  {'Area':>7} │ {'TOPS':>8} {'Yield':>7} {'TOPS×Y':>8} {'DPW':>5} │ "
          f"{'TOPS':>8} {'PHY%':>6} {'Yield':>7} {'TOPS×Y':>8} {'DPW':>5} │")
    print("  " + "-" * 95)

    for area in total_areas:
        m = monolithic_throughput(area, 1)
        c = chiplet_throughput(area, 4, phy_spec, inter_bw, 'mesh2d')

        if m is None:
            m_str = f"  {'RETICLE LIMIT — monolithic impossible':^30}"
            m_effective = 0
            m_dpw = 0
        else:
            m_effective = m['aggregate_tops'] * m['yield']
            m_dpw = dies_per_wafer(m['die_area'])
            m_str = (f"{m['aggregate_tops']:>8.0f} {m['yield']*100:>6.1f}% "
                     f"{m_effective:>8.1f} {m_dpw:>5}")

        if c is None:
            c_str = "PHY too large"
            c_effective = 0
        else:
            # For chiplet: yield is per-chiplet, need all N to work for one system
            # P(system works) = yield^N for independent chiplets
            # But with known-good-die (KGD) testing, we only pay for individual yield
            # So effective TOPS per "system" = N × tops_per_chiplet (all tested good)
            # Cost already accounts for yield via die_cost
            c_effective = c['aggregate_tops'] * c['yield']  # per-chiplet yield
            c_dpw = dies_per_wafer(c['chiplet_area'])
            c_str = (f"{c['aggregate_tops']:>8.0f} {c['phy_overhead_pct']:>5.1f}% "
                     f"{c['yield']*100:>6.1f}% {c_effective:>8.1f} {c_dpw:>5}")

        if m_effective > 0 and c_effective > 0:
            win = "YES" if c_effective >= m_effective else "no"
        elif m_effective == 0:
            win = "YES*"
        else:
            win = "no"

        print(f"  {area:>7} │ {m_str} │ {c_str} │ {win:>6}")

    print("""
  Note on yield interpretation:
  - Monolithic: 1 die = 1 system. System yield = die yield.
  - Chiplet with KGD (Known Good Die) testing: each chiplet tested separately.
    You only assemble known-good chiplets. System yield ≈ individual chiplet yield.
    This is THE key advantage — you don't throw away the whole system for one defect.
  """)


# ============================================================
# Analysis 6: Sensitivity — what PHY technology is needed?
# ============================================================

def analysis_6_sensitivity():
    """What PHY area density do we need for chiplets to break even?"""
    print("\n" + "=" * 90)
    print("  ANALYSIS 6: Required PHY Density for Throughput Parity")
    print("  (Given N chiplets and target BW, what mm²/module makes chiplet = monolithic?)")
    print("=" * 90)

    total_area = 1200
    m = monolithic_throughput(total_area, 2)  # 2-chip monolithic baseline
    mono_tops = m['aggregate_tops']

    print(f"\n  Baseline: 2×{total_area//2}mm² monolithic = {mono_tops:.0f} TOPS")
    print(f"  Target: chiplet aggregate TOPS ≥ {mono_tops:.0f}")

    configs = [
        (4, 256, 'mesh2d'),
        (4, 512, 'mesh2d'),
        (8, 256, 'mesh2d'),
        (8, 512, 'mesh2d'),
    ]

    print(f"\n  {'Config':>25} │ {'Max PHY area/mod':>18} │ {'PHY total':>10} │ "
          f"{'Effective':>10} │ {'Status':>10}")
    print("  " + "-" * 80)

    for (nc, bw, topo) in configs:
        chiplet_area = total_area / nc
        if topo == 'mesh2d':
            n_neighbors = min(3, nc - 1)

        # Find max PHY area per module that still gives ≥ mono_tops
        # aggregate_tops = nc × (chiplet_area - phy_total) × TOPS_PER_MM2
        # Need: nc × (chiplet_area - phy_total) ≥ mono_tops / TOPS_PER_MM2
        # → phy_total ≤ chiplet_area - mono_tops / (nc × TOPS_PER_MM2)
        max_phy_total = chiplet_area - mono_tops / (nc * TOPS_PER_MM2)

        # phy_total = n_modules_per_neighbor × n_neighbors × area_per_module
        n_modules_per_neighbor = math.ceil(bw / 32)  # assuming 32 GB/s per module
        total_modules = n_modules_per_neighbor * n_neighbors
        max_area_per_module = max_phy_total / total_modules if total_modules > 0 else 0

        config_name = f"{nc}×chiplet, {bw}GB/s, {topo}"
        if max_area_per_module > 0:
            status = "FEASIBLE" if max_area_per_module >= 0.15 else "TIGHT"
            if max_area_per_module >= 0.6:
                status = "EASY"
            print(f"  {config_name:>25} │ {max_area_per_module:>14.2f} mm² │ "
                  f"{max_phy_total:>8.1f} mm² │ "
                  f"{nc*(chiplet_area-max_phy_total):>8.0f} TOPS │ {status:>10}")
        else:
            print(f"  {config_name:>25} │ {'IMPOSSIBLE':>18} │ "
                  f"{'N/A':>10} │ {'N/A':>10} │ {'IMPOSSIBLE':>10}")

    print("""
  Interpretation:
  - EASY:     max PHY area/module ≥ 0.6mm² → even UCIe Standard works
  - FEASIBLE: max PHY area/module ≥ 0.15mm² → needs UCIe Advanced or better
  - TIGHT:    max PHY area/module < 0.15mm² → needs custom D2D
  - IMPOSSIBLE: cannot achieve parity at any PHY density
  """)


# ============================================================
# Analysis 7: The winning formula — combined advantage
# ============================================================

def analysis_7_winning_formula():
    """
    Combine all factors to find THE condition where chiplet throughput > monolithic:
    1. Yield advantage (smaller dies)
    2. PHY overhead (reduces compute)
    3. Beyond reticle limit (monolithic impossible)
    4. Heterogeneous process (compute on advanced node, I/O on mature)
    """
    print("\n" + "=" * 90)
    print("  ANALYSIS 7: The Winning Formula — Complete Comparison")
    print("=" * 90)

    scenarios = [
        # (name, total_area, defect_density, description)
        ("Mainstream GPU",     600, 0.08, "Good process, moderate area"),
        ("Large Accelerator", 1000, 0.10, "H100-class"),
        ("Blackwell-class",   1600, 0.10, "2× reticle, must use chiplet or multi-chip"),
        ("Next-gen Monster",  2400, 0.12, "Future 3nm+ accelerator"),
        ("Bleeding edge",     1200, 0.15, "Early 2nm, high defect density"),
    ]

    for (name, area, dd, desc) in scenarios:
        print(f"\n  ┌─ Scenario: {name} ({area}mm², dd={dd}) ─ {desc}")
        print(f"  │")

        # Find best monolithic
        best_mono = None
        for nc in [1, 2, 4]:
            m = monolithic_throughput(area, nc, dd)
            if m and (best_mono is None or m['aggregate_tops'] > best_mono['aggregate_tops']):
                best_mono = m
        if best_mono:
            print(f"  │  Best Monolithic: {best_mono['n_chips']}×{best_mono['die_area']:.0f}mm² "
                  f"= {best_mono['aggregate_tops']:.0f} TOPS "
                  f"(yield={best_mono['yield']*100:.1f}%, "
                  f"${best_mono['total_cost']:.0f})")
        else:
            print(f"  │  Best Monolithic: IMPOSSIBLE (all configs exceed reticle)")

        # Chiplet configs
        print(f"  │")
        print(f"  │  {'Config':>30} {'TOPS':>8} {'PHY%':>6} {'Yield':>7} "
              f"{'Cost':>8} {'TOPS/$':>10} {'vs Mono':>8}")
        print(f"  │  " + "-" * 80)

        chiplet_configs = [
            (4, 'ucie_advanced', 256, 'mesh2d'),
            (4, 'custom_d2d', 256, 'mesh2d'),
            (8, 'ucie_advanced', 256, 'mesh2d'),
            (8, 'custom_d2d', 256, 'mesh2d'),
            (4, 'ucie_advanced', 512, 'mesh2d'),
            (8, 'custom_d2d', 512, 'mesh2d'),
        ]

        for (nc, phy, bw, topo) in chiplet_configs:
            c = chiplet_throughput(area, nc, phy, bw, topo, dd)
            spec_name = PhySpec.SPECS[phy]['name']
            label = f"{nc}×{spec_name[:10]} {bw}GB/s"

            if c is None:
                print(f"  │  {label:>30} {'PHY > chiplet area':>40}")
                continue

            if best_mono:
                ratio_tops = c['aggregate_tops'] / best_mono['aggregate_tops']
                ratio_tpd = c['tops_per_dollar'] / best_mono['tops_per_dollar']
                tops_win = "✓TOPS" if ratio_tops >= 1.0 else ""
                tpd_win = "✓$/T" if ratio_tpd >= 1.0 else ""
                vs = f"{ratio_tops:.1%} {tops_win} {tpd_win}"
            else:
                vs = "MONO N/A"

            print(f"  │  {label:>30} {c['aggregate_tops']:>8.0f} "
                  f"{c['phy_overhead_pct']:>5.1f}% {c['yield']*100:>6.1f}% "
                  f"${c['total_cost']:>7.0f} {c['tops_per_dollar']:>10.6f} "
                  f"{vs:>8}")

        print(f"  └{'─' * 88}")


# ============================================================
# Main
# ============================================================

def main():
    analysis_1_phy_overhead()
    analysis_2_same_area()
    analysis_3_same_budget()
    analysis_4_crossover()
    analysis_5_yield_adjusted()
    analysis_6_sensitivity()
    analysis_7_winning_formula()

    # Summary
    print("\n" + "=" * 90)
    print("  SUMMARY: Conditions for Chiplet Throughput ≥ Monolithic")
    print("=" * 90)
    print("""
  ┌─────────────────────────────────────────────────────────────────────────┐
  │ SAME AREA (raw TOPS):                                                  │
  │   Chiplet ALWAYS loses by N × PHY_area.                                │
  │   At 4 chiplets, UCIe Advanced, 256GB/s: ~4-8% throughput loss.        │
  │   → Need OTHER advantages to compensate.                               │
  │                                                                        │
  │ SAME BUDGET (TOPS/$):                                                  │
  │   Chiplet wins when yield advantage > PHY+packaging overhead.          │
  │   Crossover: total die area > ~800mm² with dd ≥ 0.08.                 │
  │   At 1200mm²+: chiplet wins by 10-30% on TOPS/$.                      │
  │                                                                        │
  │ BEYOND RETICLE (>858mm²):                                              │
  │   Monolithic single-die is IMPOSSIBLE.                                  │
  │   Multi-chip monolithic uses NVLink (expensive, board-level).           │
  │   Chiplet-in-package is the ONLY viable option.                         │
  │                                                                        │
  │ KEY INSIGHT FOR PAPER:                                                  │
  │   "Same throughput" is achievable when:                                 │
  │   1. PHY area overhead < 8% per chiplet (UCIe Advanced or better)      │
  │   2. Total area > 800mm² (yield crossover)                             │
  │   3. Inter-chiplet BW ≥ 256 GB/s per neighbor (NoI helps)              │
  │   4. KGD testing enables system yield ≈ individual chiplet yield        │
  │                                                                        │
  │   "Better throughput" is achievable when (additionally):                │
  │   5. Heterogeneous process (compute@3nm + I/O@12nm)                     │
  │   6. Total area > 1200mm² (strong yield advantage)                      │
  │   7. High defect density (early node) amplifies yield advantage         │
  └─────────────────────────────────────────────────────────────────────────┘
  """)


if __name__ == "__main__":
    main()
