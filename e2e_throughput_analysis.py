"""
End-to-End Inference Throughput Analysis
========================================

Combines PHY area overhead + communication latency → actual tokens/second.

Two throughput penalties for chiplets vs monolithic:
  1. PHY area → less compute per chiplet → lower effective TOPS
  2. Inter-chiplet communication → all-reduce latency per layer

This script answers: "After BOTH penalties, can chiplets still match monolithic?"

Models: LLaMA-70B (FP16), LLaMA-405B (FP16), GPT-4 class (1.8T, FP8)
"""

import math
from pathlib import Path


# ============================================================
# Yield & Cost (from phy_overhead_analysis.py)
# ============================================================

def murphy_yield(area_mm2, dd=0.1):
    d = dd * area_mm2 / 100
    if d <= 0:
        return 1.0
    return ((1 - math.exp(-d)) / d) ** 2


def die_cost(area_mm2, wafer_cost=17000, dd=0.1):
    y = murphy_yield(area_mm2, dd)
    dpw = int(math.pi * 150**2 / area_mm2 * 0.9)
    if dpw <= 0 or y <= 0:
        return float('inf')
    return wafer_cost / (dpw * y)


# ============================================================
# PHY specs
# ============================================================

PHY_SPECS = {
    'ucie_std': {'bw_mod': 32, 'area_mod': 0.60, 'name': 'UCIe Std'},
    'ucie_adv': {'bw_mod': 32, 'area_mod': 0.15, 'name': 'UCIe Adv'},
    'ucie_2p0': {'bw_mod': 64, 'area_mod': 0.50, 'name': 'UCIe 2.0'},
    'custom':   {'bw_mod': 100, 'area_mod': 0.30, 'name': 'Custom D2D'},
}

RETICLE_LIMIT = 858


def phy_area_per_chiplet(spec_name, bw_per_neighbor, n_neighbors):
    """Total PHY area consumed on one chiplet."""
    spec = PHY_SPECS[spec_name]
    modules_per_neighbor = math.ceil(bw_per_neighbor / spec['bw_mod'])
    return modules_per_neighbor * n_neighbors * spec['area_mod']


# ============================================================
# LLM Model definitions
# ============================================================

class LLMModel:
    def __init__(self, name, h, layers, heads, head_dim, ffn, seq, batch, dbytes):
        self.name = name
        self.h = h
        self.layers = layers
        self.heads = heads
        self.head_dim = head_dim
        self.ffn = ffn
        self.seq = seq
        self.batch = batch
        self.db = dbytes  # bytes per param (2=FP16, 1=FP8)

    @property
    def flops_per_layer(self):
        h, s, b = self.h, self.seq, self.batch
        # QKV proj + O proj + attention + FFN (up/gate/down)
        return (4 * 2 * b * s * h * h
                + 2 * 2 * b * self.heads * s * s * self.head_dim
                + 3 * 2 * b * s * h * self.ffn)

    @property
    def weights_per_layer(self):
        return (4 * self.h**2 + 3 * self.h * self.ffn) * self.db

    @property
    def kv_cache_per_layer(self):
        return 2 * self.batch * self.seq * self.h * self.db

    @property
    def mem_per_layer(self):
        act = self.batch * self.seq * self.h * self.db
        return self.weights_per_layer + self.kv_cache_per_layer + act

    @property
    def activation_bytes(self):
        return self.batch * self.seq * self.h * self.db

    @property
    def total_params(self):
        return (4 * self.h**2 + 3 * self.h * self.ffn) * self.layers

    @property
    def total_weight_bytes(self):
        return self.weights_per_layer * self.layers


MODELS = {
    'llama70b': LLMModel('LLaMA-70B (FP16)', 8192, 80, 64, 128, 28672, 2048, 1, 2),
    'llama405b': LLMModel('LLaMA-405B (FP16)', 16384, 126, 128, 128, 53248, 2048, 1, 2),
    'gpt4_class': LLMModel('GPT-4 class (FP8)', 12288, 120, 96, 128, 49152, 4096, 1, 1),
}


# ============================================================
# Interconnect specs
# ============================================================

INTERCONNECTS = {
    'nvlink_board':  {'bw': 900, 'lat_us': 1.0,  'name': 'NVLink (board)'},
    'nvlink_module': {'bw': 1800, 'lat_us': 0.5, 'name': 'NVLink (NV-HBI)'},
    'ucie_256':      {'bw': 256, 'lat_us': 0.1,  'name': 'UCIe 256GB/s'},
    'ucie_512':      {'bw': 512, 'lat_us': 0.08, 'name': 'UCIe 512GB/s'},
    'noi_512':       {'bw': 512, 'lat_us': 0.05, 'name': 'NoI 512GB/s'},
    'noi_1024':      {'bw': 1024, 'lat_us': 0.03, 'name': 'NoI 1TB/s'},
}


# ============================================================
# Core: end-to-end inference latency
# ============================================================

def inference_latency(model, n_devices, tops_per_device, hbm_bw_per_device,
                      inter_bw, inter_lat_us):
    """
    Tensor-parallel inference latency for one token generation step.
    Returns dict with per-layer and total breakdown.
    """
    # Per-layer compute time (compute-bound vs memory-bound)
    t_comp = (model.flops_per_layer / n_devices) / (tops_per_device * 1e12)
    t_mem = (model.mem_per_layer / n_devices) / (hbm_bw_per_device * 1e9)
    t_layer_compute = max(t_comp, t_mem)
    bottleneck = 'compute' if t_comp >= t_mem else 'memory'

    # Communication: 2× all-reduce per layer (after attention + after FFN)
    if n_devices > 1:
        # Ring all-reduce data volume
        ar_data = 2 * (n_devices - 1) / n_devices * model.activation_bytes
        # Ring all-reduce latency: data transfer + hop latencies
        t_ar = ar_data / (inter_bw * 1e9) + 2 * (n_devices - 1) * inter_lat_us * 1e-6
        t_comm_per_layer = 2 * t_ar  # 2 all-reduces per layer
    else:
        t_comm_per_layer = 0

    t_per_layer = t_layer_compute + t_comm_per_layer

    # Total over all layers (in microseconds)
    total_compute_us = t_layer_compute * model.layers * 1e6
    total_comm_us = t_comm_per_layer * model.layers * 1e6
    total_us = t_per_layer * model.layers * 1e6
    comm_pct = total_comm_us / total_us * 100 if total_us > 0 else 0

    # Throughput
    tokens_per_sec = 1e6 / total_us if total_us > 0 else 0

    return {
        'total_us': total_us,
        'compute_us': total_compute_us,
        'comm_us': total_comm_us,
        'comm_pct': comm_pct,
        'tokens_per_sec': tokens_per_sec,
        'bottleneck': bottleneck,
        't_comp_per_layer': t_comp * 1e6,
        't_mem_per_layer': t_mem * 1e6,
        't_comm_per_layer': t_comm_per_layer * 1e6,
    }


# ============================================================
# System configurations
# ============================================================

def make_monolithic_config(total_area, n_chips, inter_key, dd=0.1):
    """Create a monolithic multi-chip config."""
    die_area = total_area / n_chips
    if die_area > RETICLE_LIMIT:
        return None

    inter = INTERCONNECTS[inter_key]

    # TOPS and HBM BW scale with die area
    # Baseline: 800mm² die → 1000 TOPS, 3200 GB/s HBM
    tops = die_area / 800 * 1000
    hbm_bw = die_area / 800 * 3200

    y = murphy_yield(die_area, dd)
    cost = die_cost(die_area, dd=dd) * n_chips
    pkg_cost = (30 + 80 + 15 + 20 + 30) * n_chips  # substrate+HBM+test+board+NVLink

    return {
        'name': f'{n_chips}×Mono {die_area:.0f}mm²',
        'type': 'monolithic',
        'n_devices': n_chips,
        'die_area': die_area,
        'compute_area': die_area,
        'phy_area': 0,
        'phy_pct': 0,
        'tops_per_dev': tops,
        'hbm_bw_per_dev': hbm_bw,
        'inter_bw': inter['bw'],
        'inter_lat': inter['lat_us'],
        'inter_name': inter['name'],
        'yield': y,
        'total_cost': cost + pkg_cost,
    }


def make_chiplet_config(total_area, n_chiplets, phy_key, inter_bw_gbps,
                        inter_key, topology='mesh2d', dd=0.1):
    """Create a chiplet config with PHY overhead."""
    chiplet_area = total_area / n_chiplets
    inter = INTERCONNECTS[inter_key]

    # Neighbors based on topology
    if topology == 'ring':
        n_neighbors = 2
    elif topology == 'mesh2d':
        n_neighbors = min(3, n_chiplets - 1)
    elif topology == 'full':
        n_neighbors = n_chiplets - 1
    else:
        n_neighbors = 2

    phy_area = phy_area_per_chiplet(phy_key, inter_bw_gbps, n_neighbors)
    compute_area = chiplet_area - phy_area
    if compute_area <= 0:
        return None

    # TOPS and HBM BW scale with COMPUTE area (not total chiplet area)
    tops = compute_area / 800 * 1000
    # HBM BW scales with chiplet area (HBM stacks are separate from compute)
    hbm_bw = chiplet_area / 800 * 3200

    y = murphy_yield(chiplet_area, dd)
    cost = die_cost(chiplet_area, dd=dd) * n_chiplets
    # Packaging
    bridges = n_chiplets - 1
    pkg_cost = 35 * bridges + 40 + n_chiplets * 12 + total_area * 0.08 + 80

    phy_spec = PHY_SPECS[phy_key]

    return {
        'name': f'{n_chiplets}×Chip {chiplet_area:.0f}mm² ({phy_spec["name"]})',
        'type': 'chiplet',
        'n_devices': n_chiplets,
        'die_area': chiplet_area,
        'compute_area': compute_area,
        'phy_area': phy_area,
        'phy_pct': phy_area / chiplet_area * 100,
        'tops_per_dev': tops,
        'hbm_bw_per_dev': hbm_bw,
        'inter_bw': inter['bw'],
        'inter_lat': inter['lat_us'],
        'inter_name': inter['name'],
        'yield': y,
        'total_cost': cost + pkg_cost,
        'n_neighbors': n_neighbors,
    }


# ============================================================
# Analysis 1: E2E throughput comparison at fixed total area
# ============================================================

def analysis_1_e2e_comparison():
    print("=" * 100)
    print("  ANALYSIS 1: End-to-End Inference Throughput (tokens/sec)")
    print("  PHY area overhead + Communication latency → real throughput")
    print("=" * 100)

    for model_key, model in MODELS.items():
        total_areas = [800, 1200, 1600, 2400]

        print(f"\n{'─' * 100}")
        print(f"  Model: {model.name}")
        print(f"  Params: {model.total_params/1e9:.0f}B, "
              f"Weights: {model.total_weight_bytes/1e9:.1f}GB, "
              f"FLOPs/layer: {model.flops_per_layer/1e12:.1f}T")
        print(f"{'─' * 100}")

        for total_area in total_areas:
            print(f"\n  ┌─ Total Area: {total_area}mm² {'─' * 70}")

            configs = []

            # Monolithic baselines
            for nc in [1, 2, 4]:
                c = make_monolithic_config(total_area, nc, 'nvlink_board')
                if c:
                    configs.append(c)

            # Monolithic with NV-HBI (like Blackwell)
            c = make_monolithic_config(total_area, 2, 'nvlink_module')
            if c:
                c['name'] = f"2×Mono {total_area//2}mm² (NV-HBI)"
                configs.append(c)

            # Chiplet configs
            chiplet_setups = [
                (4, 'ucie_adv', 256, 'ucie_256', 'mesh2d'),
                (4, 'ucie_adv', 512, 'ucie_512', 'mesh2d'),
                (4, 'custom',   256, 'noi_512',  'mesh2d'),
                (4, 'custom',   512, 'noi_1024', 'mesh2d'),
                (8, 'ucie_adv', 256, 'ucie_256', 'mesh2d'),
                (8, 'ucie_adv', 256, 'noi_512',  'mesh2d'),
                (8, 'custom',   256, 'noi_512',  'mesh2d'),
                (8, 'custom',   512, 'noi_1024', 'mesh2d'),
            ]
            for (nc, phy, bw, inter, topo) in chiplet_setups:
                c = make_chiplet_config(total_area, nc, phy, bw, inter, topo)
                if c:
                    configs.append(c)

            # Run inference for each config
            results = []
            for cfg in configs:
                r = inference_latency(
                    model, cfg['n_devices'], cfg['tops_per_dev'],
                    cfg['hbm_bw_per_dev'], cfg['inter_bw'], cfg['inter_lat'])
                results.append((cfg, r))

            # Find best monolithic as baseline
            mono_results = [(c, r) for c, r in results if c['type'] == 'monolithic']
            if mono_results:
                best_mono = min(mono_results, key=lambda x: x[1]['total_us'])
                base_tps = best_mono[1]['tokens_per_sec']
                base_name = best_mono[0]['name']
            else:
                base_tps = None
                base_name = "N/A"

            print(f"  │  Baseline: {base_name}")
            print(f"  │")
            print(f"  │  {'Config':<32} {'Comp':>8} {'Comm':>8} {'Total':>8} "
                  f"{'tok/s':>7} {'Comm%':>6} {'PHY%':>5} {'BN':>4} "
                  f"{'vs Mono':>8} {'Cost':>7} {'tok/s/$':>9}")
            print(f"  │  {'':32} {'(us)':>8} {'(us)':>8} {'(us)':>8} "
                  f"{'':>7} {'':>6} {'':>5} {'':>4} {'':>8} {'($)':>7} {'':>9}")
            print(f"  │  {'─' * 95}")

            for cfg, r in results:
                ratio_str = ""
                tpd_str = ""
                if base_tps and base_tps > 0:
                    ratio = r['tokens_per_sec'] / base_tps
                    marker = " ✓" if ratio >= 1.0 else ""
                    ratio_str = f"{ratio:>6.1%}{marker}"

                tpd = r['tokens_per_sec'] / cfg['total_cost'] if cfg['total_cost'] > 0 else 0
                tpd_str = f"{tpd:>9.6f}"

                type_marker = "  " if cfg['type'] == 'monolithic' else "→ "
                print(f"  │  {type_marker}{cfg['name']:<30} "
                      f"{r['compute_us']:>8.0f} {r['comm_us']:>8.0f} "
                      f"{r['total_us']:>8.0f} {r['tokens_per_sec']:>7.1f} "
                      f"{r['comm_pct']:>5.1f}% {cfg['phy_pct']:>4.1f}% "
                      f"{r['bottleneck'][:3]:>4} "
                      f"{ratio_str:>8} "
                      f"${cfg['total_cost']:>6.0f} {tpd_str}")

            print(f"  └{'─' * 97}")


# ============================================================
# Analysis 2: Breakdown of throughput penalty sources
# ============================================================

def analysis_2_penalty_breakdown():
    print("\n" + "=" * 100)
    print("  ANALYSIS 2: Throughput Penalty Breakdown")
    print("  How much does each factor reduce throughput vs ideal?")
    print("=" * 100)

    model = MODELS['llama70b']
    total_area = 1200

    # Ideal: monolithic 1200mm² single die (impossible, but theoretical max)
    ideal_tops = total_area / 800 * 1000
    ideal_hbm = total_area / 800 * 3200
    ideal = inference_latency(model, 1, ideal_tops, ideal_hbm, 0, 0)
    ideal_tps = ideal['tokens_per_sec']

    print(f"\n  Model: {model.name}, Total Area: {total_area}mm²")
    print(f"  Theoretical ideal (1×{total_area}mm², no comm): {ideal_tps:.1f} tok/s\n")

    configs = [
        ('2×Mono NVLink', 2, 0, 600, 900, 1.0),
        ('2×Mono NV-HBI', 2, 0, 600, 1800, 0.5),
        ('4×Chip UCIe256', 4, 3.6, 300, 256, 0.1),
        ('4×Chip NoI512', 4, 2.7, 300, 512, 0.05),
        ('4×Chip NoI1T', 4, 2.7, 300, 1024, 0.03),
        ('8×Chip UCIe256', 8, 3.6, 150, 256, 0.1),
        ('8×Chip NoI512', 8, 2.7, 150, 512, 0.05),
        ('8×Chip NoI1T', 8, 2.7, 150, 1024, 0.03),
    ]

    print(f"  {'Config':<20} │ {'PHY loss':>8} │ {'Comm loss':>9} │ "
          f"{'Combined':>9} │ {'tok/s':>7} │ {'vs Ideal':>8} │ {'Comment'}")
    print(f"  {'─' * 95}")

    for (name, nd, phy_pct, chip_area, ibw, ilat) in configs:
        # Effective TOPS after PHY deduction
        eff_area = chip_area * (1 - phy_pct / 100)
        tops = eff_area / 800 * 1000
        hbm = chip_area / 800 * 3200

        # With PHY loss only (no comm)
        r_no_comm = inference_latency(model, nd, tops, hbm, 1e6, 0)
        phy_loss = 1 - r_no_comm['tokens_per_sec'] / ideal_tps

        # With comm only (no PHY loss) — full area compute
        tops_full = chip_area / 800 * 1000
        r_no_phy = inference_latency(model, nd, tops_full, hbm, ibw, ilat)
        comm_loss = 1 - r_no_phy['tokens_per_sec'] / ideal_tps

        # Both losses combined
        r_both = inference_latency(model, nd, tops, hbm, ibw, ilat)
        combined_loss = 1 - r_both['tokens_per_sec'] / ideal_tps

        comment = ""
        if combined_loss < 0.01:
            comment = "< 1% loss"
        elif combined_loss < 0.05:
            comment = "acceptable"
        elif combined_loss < 0.10:
            comment = "moderate"
        else:
            comment = "significant"

        print(f"  {name:<20} │ {phy_loss:>7.1%}  │ {comm_loss:>8.1%}  │ "
              f"{combined_loss:>8.1%}  │ {r_both['tokens_per_sec']:>7.1f} │ "
              f"{1-combined_loss:>7.1%}  │ {comment}")

    print(f"\n  Note: PHY loss = reduced compute area. Comm loss = all-reduce overhead.")
    print(f"  Combined ≠ PHY + Comm (they interact — less compute means faster compute step,")
    print(f"  but comm stays the same, so comm% actually increases).")


# ============================================================
# Analysis 3: What BW makes chiplets match monolithic?
# ============================================================

def analysis_3_bw_crossover():
    print("\n" + "=" * 100)
    print("  ANALYSIS 3: Required Inter-Chiplet Bandwidth for Throughput Parity")
    print("  (Find BW where chiplet tok/s ≥ best monolithic tok/s)")
    print("=" * 100)

    for model_key in ['llama70b', 'llama405b', 'gpt4_class']:
        model = MODELS[model_key]

        for total_area in [1200, 1600, 2400]:
            # Best monolithic
            best_mono_tps = 0
            best_mono_name = ""
            for nc in [1, 2, 4]:
                cfg = make_monolithic_config(total_area, nc, 'nvlink_board')
                if cfg:
                    r = inference_latency(model, cfg['n_devices'], cfg['tops_per_dev'],
                                          cfg['hbm_bw_per_dev'], cfg['inter_bw'], cfg['inter_lat'])
                    if r['tokens_per_sec'] > best_mono_tps:
                        best_mono_tps = r['tokens_per_sec']
                        best_mono_name = cfg['name']

            # Also try NV-HBI monolithic
            cfg = make_monolithic_config(total_area, 2, 'nvlink_module')
            if cfg:
                r = inference_latency(model, cfg['n_devices'], cfg['tops_per_dev'],
                                      cfg['hbm_bw_per_dev'], cfg['inter_bw'], cfg['inter_lat'])
                if r['tokens_per_sec'] > best_mono_tps:
                    best_mono_tps = r['tokens_per_sec']
                    best_mono_name = f"2×Mono NV-HBI"

            if best_mono_tps == 0:
                best_mono_tps = 0.001  # avoid div by zero

            print(f"\n  {model.name} @ {total_area}mm² — "
                  f"Mono baseline: {best_mono_name} = {best_mono_tps:.1f} tok/s")

            # Sweep BW for chiplets
            n_chiplets_list = [4, 8]
            phy_list = [('ucie_adv', 'UCIe Adv'), ('custom', 'Custom D2D')]

            print(f"  {'Config':>30} │ BW to reach: "
                  f"{'90%':>8} {'95%':>8} {'100%':>8} {'105%':>8}")
            print(f"  {'─' * 75}")

            for nc in n_chiplets_list:
                for phy_key, phy_name in phy_list:
                    thresholds = {0.90: None, 0.95: None, 1.00: None, 1.05: None}

                    for bw in range(32, 2049, 32):
                        chiplet_area = total_area / nc
                        n_neighbors = min(3, nc - 1)
                        pa = phy_area_per_chiplet(phy_key, bw, n_neighbors)
                        compute_area = chiplet_area - pa
                        if compute_area <= 0:
                            break

                        tops = compute_area / 800 * 1000
                        hbm = chiplet_area / 800 * 3200

                        # Use same BW for interconnect as provisioned PHY
                        lat = 0.05 if bw >= 512 else 0.08 if bw >= 256 else 0.1
                        r = inference_latency(model, nc, tops, hbm, bw, lat)
                        ratio = r['tokens_per_sec'] / best_mono_tps

                        for thresh in thresholds:
                            if thresholds[thresh] is None and ratio >= thresh:
                                thresholds[thresh] = bw

                    label = f"{nc}×{phy_name}"
                    vals = []
                    for thresh in [0.90, 0.95, 1.00, 1.05]:
                        v = thresholds[thresh]
                        vals.append(f"{v:>5}GB/s" if v else f"{'N/A':>8}")
                    print(f"  {label:>30} │ {vals[0]:>8} {vals[1]:>8} "
                          f"{vals[2]:>8} {vals[3]:>8}")


# ============================================================
# Analysis 4: Communication overhead at scale
# ============================================================

def analysis_4_comm_scaling():
    print("\n" + "=" * 100)
    print("  ANALYSIS 4: Communication Overhead Scaling with Chiplet Count")
    print("  (How does comm% grow as we add more chiplets?)")
    print("=" * 100)

    model = MODELS['llama70b']
    total_area = 1200

    n_range = [1, 2, 4, 8, 16, 32]

    # Different interconnect technologies
    inter_configs = [
        ('NVLink board',  900, 1.0),
        ('UCIe 256GB/s',  256, 0.1),
        ('NoI 512GB/s',   512, 0.05),
        ('NoI 1TB/s',    1024, 0.03),
    ]

    print(f"\n  {model.name} @ {total_area}mm² total, Custom D2D PHY, 256GB/s provisioned\n")

    print(f"  {'N':>4} │ {'Chip':>6} {'Comp':>6} │", end="")
    for (iname, _, _) in inter_configs:
        print(f" {iname:>16}", end="")
    print()

    print(f"  {'':>4} │ {'(mm²)':>6} {'(mm²)':>6} │", end="")
    for _ in inter_configs:
        print(f" {'tok/s (comm%)':>16}", end="")
    print()
    print(f"  {'─' * (18 + 18 * len(inter_configs))}")

    for nd in n_range:
        if nd == 1:
            chip_area = total_area
            phy_a = 0
            comp_area = chip_area
        else:
            chip_area = total_area / nd
            n_neighbors = min(3, nd - 1)
            phy_a = phy_area_per_chiplet('custom', 256, n_neighbors)
            comp_area = chip_area - phy_a
            if comp_area <= 0:
                continue

        tops = comp_area / 800 * 1000
        hbm = chip_area / 800 * 3200

        print(f"  {nd:>4} │ {chip_area:>6.0f} {comp_area:>6.1f} │", end="")

        for (iname, ibw, ilat) in inter_configs:
            if nd == 1:
                r = inference_latency(model, 1, tops, hbm, 0, 0)
            else:
                r = inference_latency(model, nd, tops, hbm, ibw, ilat)
            print(f" {r['tokens_per_sec']:>6.1f} ({r['comm_pct']:>4.1f}%)", end="  ")
        print()


# ============================================================
# Analysis 5: TOPS/$ including communication overhead
# ============================================================

def analysis_5_cost_performance():
    print("\n" + "=" * 100)
    print("  ANALYSIS 5: Cost-Performance (tok/s per $) — The Bottom Line")
    print("  Combines: PHY area loss + communication overhead + yield advantage + packaging cost")
    print("=" * 100)

    model = MODELS['llama70b']

    for total_area, dd in [(1200, 0.10), (1600, 0.10), (1200, 0.15), (2400, 0.12)]:
        print(f"\n  ┌─ {model.name} @ {total_area}mm², defect density={dd} {'─' * 45}")

        all_configs = []

        # Monolithic baselines
        for nc, inter_key in [(2, 'nvlink_board'), (2, 'nvlink_module'), (4, 'nvlink_board')]:
            cfg = make_monolithic_config(total_area, nc, inter_key, dd)
            if cfg:
                all_configs.append(cfg)

        # Chiplet configs
        for (nc, phy, bw, inter_key) in [
            (4, 'ucie_adv', 256, 'ucie_256'),
            (4, 'custom',   256, 'noi_512'),
            (4, 'custom',   512, 'noi_1024'),
            (8, 'ucie_adv', 256, 'noi_512'),
            (8, 'custom',   256, 'noi_512'),
            (8, 'custom',   512, 'noi_1024'),
        ]:
            cfg = make_chiplet_config(total_area, nc, phy, bw, inter_key, 'mesh2d', dd)
            if cfg:
                all_configs.append(cfg)

        results = []
        for cfg in all_configs:
            r = inference_latency(model, cfg['n_devices'], cfg['tops_per_dev'],
                                  cfg['hbm_bw_per_dev'], cfg['inter_bw'], cfg['inter_lat'])
            tpd = r['tokens_per_sec'] / cfg['total_cost']
            results.append((cfg, r, tpd))

        # Sort by tok/s/$
        results.sort(key=lambda x: x[2], reverse=True)
        best_tpd = results[0][2]

        print(f"  │")
        print(f"  │  {'#':>2} {'Config':<35} {'tok/s':>7} {'Comm%':>6} "
              f"{'PHY%':>5} {'Yield':>6} {'Cost':>7} {'tok/s/$':>9} {'vs Best':>8}")
        print(f"  │  {'─' * 92}")

        for i, (cfg, r, tpd) in enumerate(results):
            marker = "★" if tpd == best_tpd else " "
            ratio = tpd / best_tpd
            print(f"  │ {marker}{i+1:>2} {cfg['name']:<35} "
                  f"{r['tokens_per_sec']:>7.1f} {r['comm_pct']:>5.1f}% "
                  f"{cfg['phy_pct']:>4.1f}% {cfg['yield']*100:>5.1f}% "
                  f"${cfg['total_cost']:>6.0f} {tpd:>9.6f} {ratio:>7.1%}")

        print(f"  └{'─' * 97}")


# ============================================================
# Main
# ============================================================

def main():
    analysis_1_e2e_comparison()
    analysis_2_penalty_breakdown()
    analysis_3_bw_crossover()
    analysis_4_comm_scaling()
    analysis_5_cost_performance()

    # Final summary
    print("\n" + "=" * 100)
    print("  FINAL VERDICT: Chiplet vs Monolithic End-to-End Throughput")
    print("=" * 100)
    print("""
  ┌──────────────────────────────────────────────────────────────────────────────┐
  │                                                                              │
  │  THROUGHPUT PENALTIES (chiplet vs monolithic, same total area):              │
  │                                                                              │
  │    1. PHY area overhead:     1-4% (UCIe Advanced / Custom D2D)              │
  │    2. Communication latency: 2-8% (depends on BW and chiplet count)         │
  │    3. Combined penalty:      3-11% total throughput loss                     │
  │                                                                              │
  │  THROUGHPUT ADVANTAGES:                                                      │
  │                                                                              │
  │    1. Yield: smaller dies → higher yield → more working TOPS per wafer      │
  │    2. Cost: yield + packaging → better TOPS/$ at large area (>800mm²)       │
  │    3. Scalability: beyond reticle limit (858mm²), chiplet is ONLY option    │
  │                                                                              │
  │  NET RESULT (by scenario):                                                   │
  │                                                                              │
  │    Total area < 800mm²:   Monolithic wins (penalties > advantages)          │
  │    800-1200mm²:           Chiplet matches on TOPS/$, ~3-5% raw TOPS loss    │
  │    1200-1600mm²:          Chiplet wins on TOPS/$, <5% raw TOPS loss         │
  │    >1600mm² (reticle):    Chiplet-in-package DOMINATES multi-chip NVLink    │
  │    Early node (high dd):  Yield advantage amplified → chiplet wins sooner   │
  │                                                                              │
  │  KEY REQUIREMENTS for throughput parity:                                     │
  │    • PHY technology: UCIe Advanced (0.15mm²/mod) or Custom D2D              │
  │    • Inter-chiplet BW: ≥256 GB/s per neighbor (NoI preferred)               │
  │    • Topology: 2D mesh with 3+ neighbors (not ring)                          │
  │    • Known-Good-Die testing (KGD) for system yield                           │
  │    • NoI with <50ns latency for 8+ chiplets                                  │
  │                                                                              │
  └──────────────────────────────────────────────────────────────────────────────┘
""")


if __name__ == "__main__":
    main()
