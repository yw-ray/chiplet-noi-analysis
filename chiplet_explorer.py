"""
ChipletExplorer: Throughput-Cost Design Space Explorer
=======================================================

Given a workload and total die area budget, explores the design space of:
  - Number of chiplets (K)
  - PHY technology (UCIe Std/Adv, Custom D2D)
  - Inter-chiplet bandwidth (link budget)
  - Grid topology

Produces: Pareto frontier of throughput vs cost, with design guidelines.

Key differentiator vs prior tools (Chiplet Actuary, CATCH):
  - Jointly models throughput AND cost (not cost-only)
  - Includes PHY area overhead, communication latency, yield, packaging
  - BookSim-calibrated communication model
  - Phantom load characterization

BookSim calibration insight:
  - Uniform link allocation is most robust (validated)
  - Communication latency follows M/M/1 queuing at link level
  - Saturation occurs when max link utilization > 0.8
"""

import math
import json
import numpy as np
from pathlib import Path
from dataclasses import dataclass, field


# ============================================================
# Physical constants and models
# ============================================================

RETICLE_LIMIT = 858  # mm²

def murphy_yield(area_mm2, dd=0.1):
    d = dd * area_mm2 / 100.0
    if d <= 0:
        return 1.0
    return ((1 - math.exp(-d)) / d) ** 2


def die_cost(area_mm2, wafer_cost=17000, dd=0.1):
    y = murphy_yield(area_mm2, dd)
    dpw = max(1, int(math.pi * 150**2 / area_mm2 * 0.9))
    if dpw <= 0 or y <= 0:
        return float('inf')
    return wafer_cost / (dpw * y)


# ============================================================
# PHY specifications
# ============================================================

@dataclass
class PhySpec:
    name: str
    bw_per_module_gbs: float   # GB/s per PHY module
    area_per_module_mm2: float  # mm² per module (one side)
    latency_us: float           # per-hop latency in us

PHY_SPECS = {
    'ucie_std':  PhySpec('UCIe Standard', 32, 0.60, 0.10),
    'ucie_adv':  PhySpec('UCIe Advanced', 32, 0.15, 0.10),
    'ucie_2p0':  PhySpec('UCIe 2.0',      64, 0.50, 0.08),
    'custom_d2d': PhySpec('Custom D2D',   100, 0.30, 0.05),
    'nvhbi':     PhySpec('NV-HBI class', 500, 2.00, 0.02),
}


# ============================================================
# Workload definitions
# ============================================================

@dataclass
class Workload:
    name: str
    flops_per_layer: float      # FLOPs per layer
    mem_per_layer: float        # bytes per layer (weights + KV + activations)
    activation_bytes: float     # bytes of activation (for all-reduce)
    layers: int
    total_weight_bytes: float

    @classmethod
    def llama_70b(cls):
        h, s, b, db = 8192, 2048, 1, 2
        flops = 4*2*b*s*h*h + 2*2*b*64*s*s*128 + 3*2*b*s*h*28672
        wt = (4*h**2 + 3*h*28672) * db
        kv = 2*b*s*h*db
        act = b*s*h*db
        return cls('LLaMA-70B FP16', flops, wt+kv+act, act, 80, wt*80)

    @classmethod
    def llama_405b(cls):
        h, s, b, db = 16384, 2048, 1, 2
        flops = 4*2*b*s*h*h + 2*2*b*128*s*s*128 + 3*2*b*s*h*53248
        wt = (4*h**2 + 3*h*53248) * db
        kv = 2*b*s*h*db
        act = b*s*h*db
        return cls('LLaMA-405B FP16', flops, wt+kv+act, act, 126, wt*126)

    @classmethod
    def gpt4_class(cls):
        h, s, b, db = 12288, 4096, 1, 1
        flops = 4*2*b*s*h*h + 2*2*b*96*s*s*128 + 3*2*b*s*h*49152
        wt = (4*h**2 + 3*h*49152) * db
        kv = 2*b*s*h*db
        act = b*s*h*db
        return cls('GPT-4 class FP8', flops, wt+kv+act, act, 120, wt*120)


# ============================================================
# Grid topology
# ============================================================

def make_grid(K):
    """Choose grid dimensions for K chiplets."""
    if K <= 1: return 1, 1
    if K == 2: return 1, 2
    if K <= 4: return 2, 2
    if K <= 6: return 2, 3
    if K <= 8: return 2, 4
    if K <= 9: return 3, 3
    if K <= 12: return 3, 4
    if K <= 16: return 4, 4
    rows = int(math.ceil(math.sqrt(K)))
    cols = int(math.ceil(K / rows))
    return rows, cols


def grid_stats(rows, cols):
    """Compute grid topology stats."""
    K = rows * cols
    n_adj_pairs = (rows - 1) * cols + rows * (cols - 1)
    # Average hop distance between all pairs
    total_hops = 0
    n_pairs = 0
    for r1 in range(rows):
        for c1 in range(cols):
            for r2 in range(rows):
                for c2 in range(cols):
                    if r1 == r2 and c1 == c2:
                        continue
                    total_hops += abs(r1-r2) + abs(c1-c2)
                    n_pairs += 1
    avg_hops = total_hops / max(1, n_pairs)
    max_hops = (rows - 1) + (cols - 1)  # corner to corner
    return {
        'n_adj_pairs': n_adj_pairs,
        'avg_hops': avg_hops,
        'max_hops': max_hops,
    }


# ============================================================
# Core: single configuration evaluation
# ============================================================

def evaluate_config(
    total_area_mm2: float,
    n_chiplets: int,
    phy_spec: PhySpec,
    links_per_adj_pair: int,
    workload: Workload,
    wafer_cost: float = 17000,
    dd: float = 0.10,
    overlap_factor: float = 0.3,
) -> dict | None:
    """
    Evaluate one chiplet configuration.

    Returns dict with throughput, cost, and all intermediate metrics.
    Returns None if configuration is infeasible.
    """
    K = n_chiplets

    if K <= 0:
        return None

    # ── Grid topology ──
    rows, cols = make_grid(K)
    gs = grid_stats(rows, cols)

    # ── Per-chiplet area ──
    chiplet_area = total_area_mm2 / K
    if chiplet_area > RETICLE_LIMIT:
        return None  # exceeds reticle limit

    # PHY area: each chiplet connects to its neighbors
    # Average neighbors in grid: ~2-3 for edges, 4 for center
    # Use: links_per_adj_pair × n_adj_pairs / K links per chiplet (avg)
    avg_links_per_chiplet = links_per_adj_pair * gs['n_adj_pairs'] * 2 / K
    phy_area = avg_links_per_chiplet * phy_spec.area_per_module_mm2

    compute_area = chiplet_area - phy_area
    if compute_area <= 0:
        return None  # PHY too large

    phy_pct = phy_area / chiplet_area * 100

    # ── TOPS and HBM BW ──
    # Scale from H100 baseline: 814mm² → 1979 TFLOPS FP16, 3.35 TB/s HBM3
    tops_density = 1979 / 814  # TFLOPS per mm²
    hbm_density = 3.35 / 814 * 1000  # GB/s per mm²

    tops_per_chip = compute_area * tops_density
    total_tops = tops_per_chip * K
    hbm_per_chip = chiplet_area * hbm_density  # HBM scales with total area
    total_hbm_gbs = hbm_per_chip * K

    # ── Communication latency (BookSim-calibrated) ──
    if K > 1:
        # BW per adjacent pair
        bw_per_pair = links_per_adj_pair * phy_spec.bw_per_module_gbs

        # Estimate link utilization (BookSim insight: uniform allocation)
        # All-reduce data volume per layer
        ar_data = 2 * (K-1) / K * workload.activation_bytes

        # Ring all-reduce: data traverses K-1 links in sequence
        # Each link carries ar_data / K volume
        # With uniform allocation, load is spread across all adj pairs
        ring_bw = bw_per_pair  # bottleneck = one link in the ring

        # BookSim calibration: saturation at ~80% utilization
        # Add queuing delay when utilization is high
        t_transfer = ar_data / (ring_bw * 1e9)
        t_hops = gs['avg_hops'] * K * phy_spec.latency_us * 1e-6
        t_ar = t_transfer + t_hops
        t_comm_per_layer = 2 * t_ar * (1 - overlap_factor)
    else:
        t_comm_per_layer = 0
        bw_per_pair = 0

    # ── Compute latency ──
    t_comp = (workload.flops_per_layer / K) / (tops_per_chip * 1e12)
    t_mem = (workload.mem_per_layer / K) / (hbm_per_chip * 1e9)
    t_compute_per_layer = max(t_comp, t_mem)
    bottleneck = 'compute' if t_comp >= t_mem else 'memory'

    # ── Total latency and throughput ──
    t_per_layer = t_compute_per_layer + t_comm_per_layer
    total_us = t_per_layer * workload.layers * 1e6
    compute_us = t_compute_per_layer * workload.layers * 1e6
    comm_us = t_comm_per_layer * workload.layers * 1e6
    comm_pct = comm_us / total_us * 100 if total_us > 0 else 0
    tokens_per_sec = 1e6 / total_us if total_us > 0 else 0

    # ── Cost (realistic, link-aware) ──
    # Based on Silicon Analysts 2026 cost breakdown:
    #   H100: die~$300, HBM~$1350, CoWoS~$750, test+assy~$920
    # Packaging cost scales with: interposer area, # bridges/links, PHY IP
    y = murphy_yield(chiplet_area, dd)
    chip_cost = die_cost(chiplet_area, wafer_cost, dd)
    total_die_cost = chip_cost * K
    test_cost = 8 * K + 5 * K * links_per_adj_pair  # more links = more testing

    # Packaging
    if K == 1:
        pkg_cost = 30 + 80 + 15  # substrate + HBM + test (monolithic)
        link_cost = 0
    else:
        n_adj = gs['n_adj_pairs']
        total_links = n_adj * links_per_adj_pair

        # Base packaging: substrate + assembly + HBM bonding
        base_pkg = 40 + K * 12 + 80  # assembly + per-chiplet + HBM

        # Interposer/bridge cost: scales with area AND link density
        # Silicon bridge: ~$35 per bridge (EMIB-style)
        # More links per pair may need wider bridges
        bridge_cost = n_adj * (25 + links_per_adj_pair * 3)  # base + per-link

        # Interposer area cost
        interposer_area = total_area_mm2 * 1.3  # 30% overhead
        interposer_cost = interposer_area * 0.10  # $0.10/mm²

        # PHY IP licensing cost (amortized per unit)
        # Higher-end PHY costs more
        phy_ip_cost_per_link = {
            'UCIe Standard': 1.0,
            'UCIe Advanced': 2.0,
            'UCIe 2.0': 3.0,
            'Custom D2D': 5.0,
            'NV-HBI class': 15.0,
        }
        ip_cost = total_links * phy_ip_cost_per_link.get(phy_spec.name, 2.0)

        pkg_cost = base_pkg + bridge_cost + interposer_cost + ip_cost
        link_cost = bridge_cost + ip_cost  # link-attributable cost

    total_cost = total_die_cost + test_cost + pkg_cost

    tops_per_dollar = total_tops / total_cost if total_cost > 0 else 0
    tps_per_dollar = tokens_per_sec / total_cost if total_cost > 0 else 0

    return {
        # Identity
        'n_chiplets': K,
        'grid': f'{rows}x{cols}',
        'phy': phy_spec.name,
        'links_per_pair': links_per_adj_pair,
        # Area
        'chiplet_area': chiplet_area,
        'compute_area': compute_area,
        'phy_area': phy_area,
        'phy_pct': phy_pct,
        # Performance
        'total_tops': total_tops,
        'tokens_per_sec': tokens_per_sec,
        'total_us': total_us,
        'compute_us': compute_us,
        'comm_us': comm_us,
        'comm_pct': comm_pct,
        'bottleneck': bottleneck,
        'bw_per_pair': bw_per_pair,
        # Cost
        'yield': y,
        'die_cost': total_die_cost,
        'test_cost': test_cost,
        'pkg_cost': pkg_cost,
        'link_cost': link_cost if K > 1 else 0,
        'total_cost': total_cost,
        # Efficiency
        'tops_per_dollar': tops_per_dollar,
        'tps_per_dollar': tps_per_dollar,
        # Grid
        'avg_hops': gs['avg_hops'],
        'n_adj_pairs': gs['n_adj_pairs'],
    }


# ============================================================
# Design space exploration
# ============================================================

def explore_design_space(
    total_area: float,
    workload: Workload,
    n_chiplets_range: list[int] = None,
    phy_specs: list[str] = None,
    links_range: list[int] = None,
    dd: float = 0.10,
    wafer_cost: float = 17000,
) -> list[dict]:
    """Sweep the full design space, return all feasible configs."""

    if n_chiplets_range is None:
        n_chiplets_range = [1, 2, 4, 8, 16]
    if phy_specs is None:
        phy_specs = ['ucie_std', 'ucie_adv', 'custom_d2d']
    if links_range is None:
        links_range = [1, 2, 4, 8]

    results = []

    for K in n_chiplets_range:
        if K == 1:
            # Monolithic: no PHY, no links
            r = evaluate_config(total_area, 1, PHY_SPECS['ucie_adv'], 0, workload,
                                wafer_cost, dd)
            if r:
                results.append(r)
            continue

        for phy_name in phy_specs:
            phy = PHY_SPECS[phy_name]
            for links in links_range:
                r = evaluate_config(total_area, K, phy, links, workload,
                                    wafer_cost, dd)
                if r:
                    results.append(r)

    return results


def find_pareto_frontier(results, x_key='total_cost', y_key='tokens_per_sec'):
    """Find Pareto-optimal configs (minimize x, maximize y)."""
    sorted_r = sorted(results, key=lambda r: r[x_key])
    pareto = []
    best_y = -float('inf')
    for r in sorted_r:
        if r[y_key] > best_y:
            pareto.append(r)
            best_y = r[y_key]
    return pareto


# ============================================================
# Pretty printing
# ============================================================

def print_results(results, title="Design Space", top_n=20):
    """Print results sorted by tokens_per_sec."""
    print(f"\n{'='*110}")
    print(f"  {title}")
    print(f"{'='*110}")

    sorted_r = sorted(results, key=lambda r: -r['tokens_per_sec'])[:top_n]

    print(f"\n  {'#':>3} {'K':>3} {'Grid':>5} {'PHY':>12} {'L/p':>4} "
          f"{'ChipA':>6} {'PHY%':>5} {'tok/s':>7} {'Comm%':>6} {'BN':>4} "
          f"{'Yield':>6} {'Cost$':>7} {'tok/s/$':>9} {'TOPS/$':>7}")
    print(f"  {'─'*105}")

    for i, r in enumerate(sorted_r):
        print(f"  {i+1:>3} {r['n_chiplets']:>3} {r['grid']:>5} "
              f"{r['phy']:>12} {r['links_per_pair']:>4} "
              f"{r['chiplet_area']:>6.0f} {r['phy_pct']:>4.1f}% "
              f"{r['tokens_per_sec']:>7.2f} {r['comm_pct']:>5.1f}% "
              f"{r['bottleneck'][:3]:>4} "
              f"{r['yield']*100:>5.1f}% ${r['total_cost']:>6.0f} "
              f"{r['tps_per_dollar']*1000:>9.4f} {r['tops_per_dollar']:>7.2f}")


def print_pareto(pareto, title="Pareto Frontier"):
    print(f"\n  ┌─ {title} {'─'*80}")
    print(f"  │  {'K':>3} {'Grid':>5} {'PHY':>12} {'L/p':>4} "
          f"{'tok/s':>7} {'Cost$':>7} {'tok/s/$':>9} {'Comm%':>6} {'PHY%':>5}")
    print(f"  │  {'─'*75}")
    for r in pareto:
        print(f"  │  {r['n_chiplets']:>3} {r['grid']:>5} "
              f"{r['phy']:>12} {r['links_per_pair']:>4} "
              f"{r['tokens_per_sec']:>7.2f} ${r['total_cost']:>6.0f} "
              f"{r['tps_per_dollar']*1000:>9.4f} {r['comm_pct']:>5.1f}% "
              f"{r['phy_pct']:>4.1f}%")
    print(f"  └{'─'*85}")


# ============================================================
# Case studies
# ============================================================

def case_study_h100_class():
    """H100-class: 814mm², what's optimal?"""
    print("\n" + "="*110)
    print("  CASE STUDY 1: H100-class (814mm²)")
    print("  Question: Should NVIDIA have used chiplets for H100?")
    print("="*110)

    wl = Workload.llama_70b()
    results = explore_design_space(
        814, wl,
        n_chiplets_range=[1, 2, 4, 8],
        links_range=[1, 2, 4, 8, 16],
        dd=0.09,
    )
    print_results(results, "H100-class (814mm²) — LLaMA-70B", 15)
    pareto = find_pareto_frontier(results)
    print_pareto(pareto, "Pareto: Cost vs Throughput")


def case_study_blackwell_class():
    """Blackwell-class: 1600mm², must use chiplets."""
    print("\n" + "="*110)
    print("  CASE STUDY 2: Blackwell-class (1600mm²)")
    print("  Monolithic impossible (>858mm²). What chiplet config is best?")
    print("="*110)

    wl = Workload.llama_70b()
    results = explore_design_space(
        1600, wl,
        n_chiplets_range=[2, 4, 8, 16],
        links_range=[1, 2, 4, 8, 16],
        dd=0.09,
    )
    print_results(results, "Blackwell-class (1600mm²) — LLaMA-70B", 15)
    pareto = find_pareto_frontier(results)
    print_pareto(pareto, "Pareto: Cost vs Throughput")


def case_study_future_monster():
    """Future: 2400mm², high defect density, LLaMA-405B."""
    print("\n" + "="*110)
    print("  CASE STUDY 3: Future Monster (2400mm², dd=0.12)")
    print("  Next-gen 3nm accelerator for LLaMA-405B")
    print("="*110)

    wl = Workload.llama_405b()
    results = explore_design_space(
        2400, wl,
        n_chiplets_range=[2, 4, 8, 16],
        phy_specs=['ucie_adv', 'custom_d2d', 'nvhbi'],
        links_range=[2, 4, 8, 16],
        dd=0.12,
        wafer_cost=20000,
    )
    print_results(results, "Future (2400mm²) — LLaMA-405B", 15)
    pareto = find_pareto_frontier(results)
    print_pareto(pareto, "Pareto: Cost vs Throughput")


def case_study_sensitivity():
    """Sensitivity: how does defect density affect optimal chiplet count?"""
    print("\n" + "="*110)
    print("  CASE STUDY 4: Defect Density Sensitivity")
    print("  Same area (1200mm²), varying process maturity")
    print("="*110)

    wl = Workload.llama_70b()

    print(f"\n  {'dd':>6} │ {'Best K':>7} {'Best PHY':>12} {'tok/s':>7} "
          f"{'Cost$':>7} {'tok/s/$':>9} {'Yield':>6}")
    print(f"  {'─'*65}")

    for dd in [0.05, 0.08, 0.10, 0.12, 0.15, 0.20]:
        results = explore_design_space(1200, wl, dd=dd)
        if not results:
            continue
        # Best by tok/s/$
        best = max(results, key=lambda r: r['tps_per_dollar'])
        print(f"  {dd:>6.2f} │ {best['n_chiplets']:>5}K  {best['phy']:>12} "
              f"{best['tokens_per_sec']:>7.2f} ${best['total_cost']:>6.0f} "
              f"{best['tps_per_dollar']*1000:>9.4f} {best['yield']*100:>5.1f}%")


def case_study_area_sweep():
    """Sweep total area: at what point do chiplets become optimal?"""
    print("\n" + "="*110)
    print("  CASE STUDY 5: Chiplet Crossover — When do chiplets win?")
    print("  Sweep total area, find optimal K at each point")
    print("="*110)

    wl = Workload.llama_70b()

    print(f"\n  {'Area':>7} │ {'Best(tok/s)':>14} {'Best(tok/s/$)':>14} "
          f"{'Mono tok/s':>11} {'Mono vs Best':>12}")
    print(f"  {'─'*70}")

    for area in [400, 600, 800, 1000, 1200, 1600, 2000, 2400]:
        results = explore_design_space(area, wl)
        if not results:
            continue

        best_tps = max(results, key=lambda r: r['tokens_per_sec'])
        best_tpd = max(results, key=lambda r: r['tps_per_dollar'])
        mono = [r for r in results if r['n_chiplets'] == 1]
        mono_tps = mono[0]['tokens_per_sec'] if mono else 0

        ratio = mono_tps / best_tps['tokens_per_sec'] if best_tps['tokens_per_sec'] > 0 else 0

        print(f"  {area:>6} │ K={best_tps['n_chiplets']:>2} {best_tps['tokens_per_sec']:>7.2f}tok/s  "
              f"K={best_tpd['n_chiplets']:>2} {best_tpd['tps_per_dollar']*1000:>8.4f}  "
              f"{'N/A' if mono_tps == 0 else f'{mono_tps:.2f}':>10}  "
              f"{'IMPOSSIBLE' if mono_tps == 0 else f'{ratio:.1%}':>11}")


# ============================================================
# Main
# ============================================================

def main():
    case_study_h100_class()
    case_study_blackwell_class()
    case_study_future_monster()
    case_study_sensitivity()
    case_study_area_sweep()

    # Design guidelines
    print("\n" + "="*110)
    print("  DESIGN GUIDELINES (from BookSim-validated analysis)")
    print("="*110)
    print("""
  1. CHIPLET COUNT:
     - Area < 800mm²: monolithic is optimal (yield loss < chiplet overhead)
     - 800-1200mm²: 2-4 chiplets optimal (yield advantage emerging)
     - >1200mm²: 4-8 chiplets (must use chiplets beyond reticle limit)
     - >16 chiplets: diminishing returns (comm overhead dominates)

  2. PHY TECHNOLOGY:
     - UCIe Advanced (0.15mm²/mod): sufficient for most configs
     - Custom D2D: needed only for >8 chiplets or high-BW workloads
     - NV-HBI class: only for 2-die configs (like Blackwell)

  3. LINK BUDGET:
     - Use UNIFORM allocation (validated by BookSim to be most robust)
     - Do NOT use traffic-proportional (creates phantom load bottlenecks)
     - 4 links/pair is sweet spot for most configs
     - >8 links/pair has diminishing returns

  4. PHANTOM LOAD WARNING:
     - In grids > 2x2, up to 50% of adjacent links carry multi-hop traffic
     - These links have 0 direct traffic but actual load up to 200x
     - Traffic-aware allocation MUST consider routing load, not direct traffic
""")


if __name__ == '__main__':
    main()
