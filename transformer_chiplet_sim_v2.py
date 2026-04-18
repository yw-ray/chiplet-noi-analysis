"""
Transformer Chiplet Partitioning Analytical Simulator v2
========================================================
Fixed model with:
  1. Tensor parallelism (split each layer across chiplets)
  2. Pipeline parallelism (throughput with batching)
  3. Memory capacity constraint (model must fit)
  4. Fair cost comparison

Key insight: LLaMA-70B weights = 155 GB (FP16)
  → One chip with 96 GB HBM cannot hold it
  → Multi-chip is REQUIRED, not optional
  → Question becomes: monolithic multi-chip vs chiplet?
"""

import math
import json
from dataclasses import dataclass
from pathlib import Path


# ============================================================
# 1. Parameters
# ============================================================

@dataclass
class TransformerConfig:
    name: str = "LLaMA-70B"
    hidden_dim: int = 8192
    num_layers: int = 80
    num_heads: int = 64
    head_dim: int = 128
    ffn_dim: int = 28672
    seq_len: int = 2048
    batch_size: int = 1
    dtype_bytes: int = 2  # FP16

    @property
    def weight_per_layer_bytes(self):
        attn = 4 * self.hidden_dim * self.hidden_dim
        ffn = 3 * self.hidden_dim * self.ffn_dim
        return (attn + ffn) * self.dtype_bytes

    @property
    def total_weight_bytes(self):
        return self.weight_per_layer_bytes * self.num_layers

    @property
    def activation_bytes(self):
        return self.batch_size * self.seq_len * self.hidden_dim * self.dtype_bytes

    @property
    def kv_cache_per_layer_bytes(self):
        return 2 * self.batch_size * self.seq_len * self.hidden_dim * self.dtype_bytes

    @property
    def flops_per_layer(self):
        h, s, b = self.hidden_dim, self.seq_len, self.batch_size
        attn_proj = 4 * 2 * b * s * h * h
        qk = 2 * b * self.num_heads * s * s * self.head_dim
        sv = 2 * b * self.num_heads * s * s * self.head_dim
        ffn = 3 * 2 * b * s * h * self.ffn_dim
        return attn_proj + qk + sv + ffn

    @property
    def total_flops(self):
        return self.flops_per_layer * self.num_layers

    @property
    def memory_reads_per_layer_bytes(self):
        return self.weight_per_layer_bytes + self.kv_cache_per_layer_bytes + self.activation_bytes


@dataclass
class ChipConfig:
    """Configuration for a SINGLE chip/chiplet."""
    name: str = "Chip"
    compute_tops: float = 500       # TOPS per chip
    hbm_capacity_gb: float = 96     # GB HBM per chip
    hbm_bw_gbps: float = 2000      # GB/s HBM BW per chip
    sram_mb: float = 64
    die_area_mm2: float = 600
    process_nm: int = 5


@dataclass
class InterconnectConfig:
    """Interconnect parameters."""
    # Chip-to-chip (board level, e.g., NVLink)
    chip_to_chip_bw_gbps: float = 900     # NVLink 4.0: ~900 GB/s
    chip_to_chip_latency_us: float = 5.0   # ~5 us

    # Chiplet-to-chiplet (in-package, UCIe)
    ucie_bw_gbps: float = 256             # UCIe per link
    ucie_latency_us: float = 0.1          # ~100 ns

    # NoI
    noi_bw_gbps: float = 200
    noi_latency_us: float = 0.15


@dataclass
class CostConfig:
    wafer_cost_5nm: float = 17000
    wafer_cost_7nm: float = 10000
    wafer_diameter_mm: float = 300
    defect_density: float = 0.1
    packaging_base: float = 100        # base packaging cost
    packaging_per_chiplet: float = 50
    interposer_per_mm2: float = 0.5
    ucie_phy_area_mm2: float = 2.0
    noi_router_area_mm2: float = 1.5
    test_per_die: float = 10


# ============================================================
# 2. Yield & Cost
# ============================================================

def murphy_yield(area_mm2, defect_density=0.1):
    d = defect_density * area_mm2 / 100.0
    if d == 0:
        return 1.0
    return ((1 - math.exp(-d)) / d) ** 2


def dies_per_wafer(area_mm2, wafer_d=300):
    return int(math.pi * (wafer_d / 2) ** 2 / area_mm2 * 0.9)


def chip_cost(area_mm2, wafer_cost, defect_density=0.1):
    y = murphy_yield(area_mm2, defect_density)
    dpw = dies_per_wafer(area_mm2)
    return wafer_cost / (dpw * y) + 10  # +$10 test


# ============================================================
# 3. Simulation Configs
# ============================================================

@dataclass
class SimResult:
    name: str
    description: str
    num_devices: int          # total chips or chiplets
    num_packages: int         # how many physical packages
    chiplets_per_package: int
    # Parallelism
    parallelism_type: str     # "none", "tensor", "pipeline", "tensor+pipeline"
    # Latency
    compute_latency_us: float
    comm_latency_us: float
    total_latency_us: float
    # Memory
    fits_in_memory: bool
    total_hbm_gb: float
    weight_gb: float
    # Cost
    die_area_mm2: float
    yield_pct: float
    single_die_cost: float
    total_system_cost: float
    # Efficiency
    perf_per_dollar: float    # tokens/s per $
    perf_vs_baseline: float   # relative to monolithic ideal


def simulate(model: TransformerConfig, config: dict) -> SimResult:
    """
    Generic simulation for any configuration.

    config keys:
      name, description, parallelism, num_chips, chiplets_per_chip,
      chip_area, chip_tops, chip_hbm_gb, chip_hbm_bw,
      inter_chip_bw (board level), inter_chiplet_bw (in-package),
      wafer_cost
    """
    c = config
    num_chips = c['num_chips']
    cppc = c.get('chiplets_per_chip', 1)
    total_devices = num_chips * cppc
    parallelism = c['parallelism']

    chip_area = c['chip_area']
    chip_tops = c['chip_tops']
    chip_hbm_gb = c['chip_hbm_gb']
    chip_hbm_bw = c['chip_hbm_bw']

    total_hbm = chip_hbm_gb * num_chips * cppc
    total_tops = chip_tops * num_chips * cppc
    fits = total_hbm >= model.total_weight_bytes / 1e9

    # --- Latency model ---
    if parallelism == "none":
        # Single chip, all layers sequential
        t_compute = model.total_flops / (chip_tops * 1e12)
        t_memory = (model.memory_reads_per_layer_bytes * model.num_layers) / (chip_hbm_bw * 1e9)
        t_layer = max(t_compute, t_memory)
        t_comm = 0

    elif parallelism == "tensor":
        # Tensor parallelism: each layer split across N devices
        # Each device computes 1/N of each GEMM
        # All-reduce after each layer (2 all-reduces per layer: attn + ffn)
        n = total_devices
        per_device_tops = chip_tops  # each device has full chip compute
        per_device_hbm_bw = chip_hbm_bw

        # Compute: each device does 1/N of the FLOPs per layer
        t_compute_per_layer = (model.flops_per_layer / n) / (per_device_tops * 1e12)

        # Memory: each device reads 1/N of weights
        t_memory_per_layer = (model.memory_reads_per_layer_bytes / n) / (per_device_hbm_bw * 1e9)

        t_per_layer = max(t_compute_per_layer, t_memory_per_layer)
        t_layer = t_per_layer * model.num_layers

        # Communication: 2 all-reduce per layer (ring all-reduce)
        # All-reduce data = 2 * activation_bytes * (n-1)/n per all-reduce
        inter_bw = c.get('inter_chiplet_bw', c.get('inter_chip_bw', 256))
        allreduce_bytes = 2 * model.activation_bytes * (n - 1) / n
        allreduce_per_layer = 2  # one for attn output, one for ffn output
        t_comm_per_layer = allreduce_per_layer * allreduce_bytes / (inter_bw * 1e9)
        # Add fixed latency per communication
        comm_latency_fixed = c.get('comm_latency_us', 0.1) * 1e-6
        t_comm_per_layer += allreduce_per_layer * comm_latency_fixed

        t_comm = t_comm_per_layer * model.num_layers
        t_compute = t_layer

    elif parallelism == "pipeline":
        # Pipeline: each device handles L/N layers
        # For single token: must traverse all stages sequentially
        # But each device has full compute for its layers
        n = total_devices
        layers_per_device = model.num_layers // n
        per_device_tops = chip_tops
        per_device_hbm_bw = chip_hbm_bw

        t_compute_per_layer = model.flops_per_layer / (per_device_tops * 1e12)
        t_memory_per_layer = model.memory_reads_per_layer_bytes / (per_device_hbm_bw * 1e9)
        t_per_layer = max(t_compute_per_layer, t_memory_per_layer)

        # Each stage takes: layers_per_device * t_per_layer
        t_stage = layers_per_device * t_per_layer
        # Total: all stages sequential
        t_layer = t_stage * n  # = total_layers * t_per_layer (same as monolithic!)

        # Communication: activation transfer between stages (n-1 transfers)
        inter_bw = c.get('inter_chiplet_bw', c.get('inter_chip_bw', 256))
        t_transfer = model.activation_bytes / (inter_bw * 1e9)
        comm_latency_fixed = c.get('comm_latency_us', 0.1) * 1e-6
        t_comm = (n - 1) * (t_transfer + comm_latency_fixed)
        t_compute = t_layer

    else:
        raise ValueError(f"Unknown parallelism: {parallelism}")

    total_latency = t_compute + t_comm

    # --- Cost model ---
    y = murphy_yield(chip_area, 0.1)
    wafer_cost = c.get('wafer_cost', 17000)
    die_cost = chip_cost(chip_area, wafer_cost)
    total_die_cost = die_cost * total_devices

    # Packaging & interposer
    pkg_cost = 100  # base
    if cppc > 1:
        interposer_area = chip_area * cppc * 1.3
        pkg_cost += interposer_area * 0.5  # interposer
        pkg_cost += cppc * 50  # per-chiplet packaging
    total_pkg_cost = pkg_cost * num_chips
    total_system_cost = total_die_cost + total_pkg_cost

    throughput = 1.0 / total_latency if total_latency > 0 else 0
    ppd = throughput / total_system_cost if total_system_cost > 0 else 0

    # Baseline: ideal monolithic (compute only, no comm)
    t_baseline = max(
        model.total_flops / (chip_tops * 1e12),
        (model.memory_reads_per_layer_bytes * model.num_layers) / (chip_hbm_bw * 1e9)
    )
    perf_vs_base = t_baseline / total_latency if total_latency > 0 else 0

    return SimResult(
        name=c['name'],
        description=c['description'],
        num_devices=total_devices,
        num_packages=num_chips,
        chiplets_per_package=cppc,
        parallelism_type=parallelism,
        compute_latency_us=t_compute * 1e6,
        comm_latency_us=t_comm * 1e6,
        total_latency_us=total_latency * 1e6,
        fits_in_memory=fits,
        total_hbm_gb=total_hbm,
        weight_gb=model.total_weight_bytes / 1e9,
        die_area_mm2=chip_area,
        yield_pct=y * 100,
        single_die_cost=die_cost,
        total_system_cost=total_system_cost,
        perf_per_dollar=ppd,
        perf_vs_baseline=perf_vs_base,
    )


# ============================================================
# 4. Define Configurations
# ============================================================

def get_configs():
    """Define all comparison configurations."""
    configs = []

    # --- A. Ideal Monolithic (hypothetical, unlimited memory) ---
    configs.append({
        'name': 'A. Monolithic 1x',
        'description': '1x 600mm2, 500 TOPS, 96GB HBM (model does NOT fit)',
        'parallelism': 'none',
        'num_chips': 1, 'chiplets_per_chip': 1,
        'chip_area': 600, 'chip_tops': 500,
        'chip_hbm_gb': 96, 'chip_hbm_bw': 2000,
        'wafer_cost': 17000,
    })

    # --- B. 2x Monolithic (tensor parallel, board-level NVLink) ---
    configs.append({
        'name': 'B. Mono 2x TP',
        'description': '2x 600mm2 chips, tensor parallel, NVLink',
        'parallelism': 'tensor',
        'num_chips': 2, 'chiplets_per_chip': 1,
        'chip_area': 600, 'chip_tops': 500,
        'chip_hbm_gb': 96, 'chip_hbm_bw': 2000,
        'inter_chip_bw': 900, 'comm_latency_us': 1.0,
        'wafer_cost': 17000,
    })

    # --- C. 4x Monolithic (tensor parallel, board-level) ---
    configs.append({
        'name': 'C. Mono 4x TP',
        'description': '4x 600mm2 chips, tensor parallel, NVLink',
        'parallelism': 'tensor',
        'num_chips': 4, 'chiplets_per_chip': 1,
        'chip_area': 600, 'chip_tops': 500,
        'chip_hbm_gb': 96, 'chip_hbm_bw': 2000,
        'inter_chip_bw': 900, 'comm_latency_us': 1.0,
        'wafer_cost': 17000,
    })

    # --- D. 2-chiplet per package, 1 package (tensor, UCIe) ---
    configs.append({
        'name': 'D. 2-Chiplet TP',
        'description': '1 pkg, 2x 300mm2 chiplets, tensor parallel, UCIe',
        'parallelism': 'tensor',
        'num_chips': 1, 'chiplets_per_chip': 2,
        'chip_area': 300, 'chip_tops': 250,
        'chip_hbm_gb': 48, 'chip_hbm_bw': 1000,
        'inter_chiplet_bw': 256, 'comm_latency_us': 0.1,
        'wafer_cost': 17000,
    })

    # --- E. 4-chiplet per package, 1 package (tensor, UCIe) ---
    configs.append({
        'name': 'E. 4-Chiplet TP',
        'description': '1 pkg, 4x 150mm2 chiplets, tensor parallel, UCIe',
        'parallelism': 'tensor',
        'num_chips': 1, 'chiplets_per_chip': 4,
        'chip_area': 150, 'chip_tops': 125,
        'chip_hbm_gb': 48, 'chip_hbm_bw': 500,
        'inter_chiplet_bw': 256, 'comm_latency_us': 0.1,
        'wafer_cost': 17000,
    })

    # --- F. 4-chiplet + NoI (tensor, higher effective BW) ---
    configs.append({
        'name': 'F. 4-Chiplet+NoI',
        'description': '1 pkg, 4x 150mm2, tensor parallel, NoI network',
        'parallelism': 'tensor',
        'num_chips': 1, 'chiplets_per_chip': 4,
        'chip_area': 150, 'chip_tops': 125,
        'chip_hbm_gb': 48, 'chip_hbm_bw': 500,
        'inter_chiplet_bw': 512, 'comm_latency_us': 0.05,  # NoI: better BW, lower latency
        'wafer_cost': 17000,
    })

    # --- G. Pipeline comparison: 4-chiplet pipeline ---
    configs.append({
        'name': 'G. 4-Chip Pipe',
        'description': '1 pkg, 4x 150mm2 chiplets, pipeline parallel, UCIe',
        'parallelism': 'pipeline',
        'num_chips': 1, 'chiplets_per_chip': 4,
        'chip_area': 150, 'chip_tops': 125,
        'chip_hbm_gb': 48, 'chip_hbm_bw': 500,
        'inter_chiplet_bw': 256, 'comm_latency_us': 0.1,
        'wafer_cost': 17000,
    })

    # --- H. Heterogeneous: compute chiplet (5nm) + memory chiplet (28nm) ---
    # 2 compute chiplets (5nm, high TOPS) + 2 memory chiplets (28nm, cheap)
    # Using tensor parallelism on compute, memory chiplets serve weights
    # Simplified: model as 4-chiplet tensor with mixed cost
    configs.append({
        'name': 'H. Hetero 2+2',
        'description': '2x compute(5nm) + 2x memory(28nm), tensor parallel',
        'parallelism': 'tensor',
        'num_chips': 1, 'chiplets_per_chip': 4,
        'chip_area': 150, 'chip_tops': 125,  # average
        'chip_hbm_gb': 48, 'chip_hbm_bw': 500,
        'inter_chiplet_bw': 256, 'comm_latency_us': 0.1,
        'wafer_cost': 10000,  # blended: 2x 5nm ($17k) + 2x 28nm ($3k) ≈ avg $10k
        'wafer_cost_note': 'blended 5nm+28nm',
    })

    return configs


# ============================================================
# 5. Run & Print
# ============================================================

def run_all():
    model = TransformerConfig()
    configs = get_configs()

    print("=" * 80)
    print("  Transformer Chiplet Partitioning Analysis v2")
    print("  Model: LLaMA-70B (FP16) | Autoregressive Inference | batch=1")
    print("=" * 80)

    print(f"\n  Weights:       {model.total_weight_bytes / 1e9:.1f} GB")
    print(f"  FLOPs/token:   {model.total_flops / 1e12:.1f} TFLOPs")
    print(f"  Activation:    {model.activation_bytes / 1e6:.1f} MB (inter-layer)")
    print(f"  KV Cache:      {model.kv_cache_per_layer_bytes * model.num_layers / 1e9:.1f} GB (total)")

    results = []
    for c in configs:
        results.append(simulate(model, c))

    # --- Main comparison table ---
    print("\n" + "=" * 80)
    print("  MAIN RESULTS")
    print("=" * 80)

    print(f"\n{'Config':<22} {'Type':<8} {'#Dev':>4} {'HBM':>6} {'Fits?':>5} "
          f"{'Latency':>10} {'Comm%':>6} {'Yield':>6} {'Cost':>8} {'Perf/$':>9}")
    print(f"{'':22} {'':8} {'':4} {'(GB)':>6} {'':5} "
          f"{'(us)':>10} {'':>6} {'(%)':>6} {'($)':>8} {'(tok/s/$)':>9}")
    print("-" * 95)

    for r in results:
        mem_flag = "OK" if r.fits_in_memory else "NO!"
        comm_pct = r.comm_latency_us / r.total_latency_us * 100 if r.total_latency_us > 0 else 0
        print(f"{r.name:<22} {r.parallelism_type:<8} {r.num_devices:>4} "
              f"{r.total_hbm_gb:>6.0f} {mem_flag:>5} "
              f"{r.total_latency_us:>10.0f} {comm_pct:>5.1f}% "
              f"{r.yield_pct:>5.1f}% ${r.total_system_cost:>7.0f} "
              f"{r.perf_per_dollar:>9.6f}")

    # --- Latency breakdown ---
    print("\n" + "=" * 80)
    print("  LATENCY BREAKDOWN")
    print("=" * 80)

    print(f"\n{'Config':<22} {'Compute':>10} {'Comm':>10} {'Total':>10} {'vs Ideal':>9}")
    print(f"{'':22} {'(us)':>10} {'(us)':>10} {'(us)':>10} {'1-chip':>9}")
    print("-" * 65)

    baseline_lat = results[0].total_latency_us
    for r in results:
        ratio = r.total_latency_us / baseline_lat if baseline_lat > 0 else 0
        speedup = baseline_lat / r.total_latency_us if r.total_latency_us > 0 else 0
        print(f"{r.name:<22} {r.compute_latency_us:>10.0f} {r.comm_latency_us:>10.1f} "
              f"{r.total_latency_us:>10.0f} {speedup:>8.2f}x")

    # --- Cost breakdown ---
    print("\n" + "=" * 80)
    print("  COST-PERFORMANCE ANALYSIS")
    print("=" * 80)

    # Only compare configs that fit in memory
    valid = [r for r in results if r.fits_in_memory]
    if valid:
        best_cost = min(r.total_system_cost for r in valid)
        best_perf = min(r.total_latency_us for r in valid)

        print(f"\n  (Only showing configs where model fits in memory)")
        print(f"\n{'Config':<22} {'Cost':>8} {'vs Best':>8} {'Latency':>10} "
              f"{'vs Best':>8} {'Perf/$':>12} {'vs Best':>8}")
        print("-" * 78)

        best_ppd = max(r.perf_per_dollar for r in valid)
        for r in valid:
            cost_r = r.total_system_cost / best_cost
            perf_r = best_perf / r.total_latency_us if r.total_latency_us > 0 else 0
            ppd_r = r.perf_per_dollar / best_ppd if best_ppd > 0 else 0
            print(f"{r.name:<22} ${r.total_system_cost:>7.0f} {cost_r:>7.2f}x "
                  f"{r.total_latency_us:>10.0f} {perf_r:>7.2f}x "
                  f"{r.perf_per_dollar:>12.6f} {ppd_r:>7.2f}x")

    # --- Key takeaways ---
    print("\n" + "=" * 80)
    print("  KEY TAKEAWAYS")
    print("=" * 80)

    mono_1x = results[0]
    print(f"\n  1. Memory constraint: LLaMA-70B needs {mono_1x.weight_gb:.0f} GB, "
          f"single chip has {mono_1x.total_hbm_gb:.0f} GB")
    print(f"     → Single monolithic chip CANNOT run this model")
    print(f"     → Multi-chip/chiplet is REQUIRED")

    if len(results) >= 6:
        mono_2x = results[1]
        chip_4x = results[4]  # E. 4-Chiplet TP
        chip_noi = results[5]  # F. 4-Chiplet+NoI

        print(f"\n  2. Tensor parallel comparison (same total resources):")
        print(f"     Mono 2x NVLink: {mono_2x.total_latency_us:.0f} us, "
              f"${mono_2x.total_system_cost:.0f}")
        print(f"     4-Chiplet UCIe:  {chip_4x.total_latency_us:.0f} us, "
              f"${chip_4x.total_system_cost:.0f}")
        print(f"     4-Chiplet+NoI:   {chip_noi.total_latency_us:.0f} us, "
              f"${chip_noi.total_system_cost:.0f}")

        if chip_4x.total_system_cost < mono_2x.total_system_cost:
            saving = (1 - chip_4x.total_system_cost / mono_2x.total_system_cost) * 100
            print(f"     → Chiplet saves {saving:.0f}% cost")

        lat_diff = (chip_4x.total_latency_us - mono_2x.total_latency_us) / mono_2x.total_latency_us * 100
        print(f"     → Chiplet latency difference: {lat_diff:+.1f}%")

        if chip_noi.total_latency_us < chip_4x.total_latency_us:
            noi_gain = (1 - chip_noi.total_latency_us / chip_4x.total_latency_us) * 100
            print(f"     → NoI improves latency by {noi_gain:.1f}% over plain UCIe")

    # --- Save results ---
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)

    data = []
    for r in results:
        data.append({
            'name': r.name,
            'description': r.description,
            'parallelism': r.parallelism_type,
            'num_devices': r.num_devices,
            'total_hbm_gb': r.total_hbm_gb,
            'fits_in_memory': r.fits_in_memory,
            'compute_latency_us': r.compute_latency_us,
            'comm_latency_us': r.comm_latency_us,
            'total_latency_us': r.total_latency_us,
            'die_area_mm2': r.die_area_mm2,
            'yield_pct': r.yield_pct,
            'total_cost': r.total_system_cost,
            'perf_per_dollar': r.perf_per_dollar,
        })

    with open(results_dir / "sim_v2_results.json", "w") as f:
        json.dump(data, f, indent=2)

    return results


# ============================================================
# 6. Visualization
# ============================================================

def plot_results(results):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("matplotlib not available, skipping plots.")
        return

    # Filter to memory-valid configs
    valid = [r for r in results if r.fits_in_memory]
    names = [r.name for r in valid]

    fig, axes = plt.subplots(2, 3, figsize=(20, 11))
    fig.suptitle('Transformer Chiplet Analysis v2: LLaMA-70B FP16 Inference\n'
                 '(Only configs where 155 GB model fits in memory)',
                 fontsize=13, fontweight='bold')

    colors = {'Mono': '#2196F3', 'Chiplet': '#4CAF50', 'NoI': '#FF9800',
              'Pipe': '#F44336', 'Hetero': '#9C27B0'}

    def get_color(name):
        if 'NoI' in name: return colors['NoI']
        if 'Hetero' in name: return colors['Hetero']
        if 'Pipe' in name: return colors['Pipe']
        if 'Chiplet' in name: return colors['Chiplet']
        return colors['Mono']

    bar_colors = [get_color(r.name) for r in valid]

    # 1. Latency comparison
    ax = axes[0][0]
    lats = [r.total_latency_us for r in valid]
    bars = ax.bar(range(len(valid)), lats, color=bar_colors)
    ax.set_ylabel('Latency (us)')
    ax.set_title('Inference Latency (lower = better)')
    ax.set_xticks(range(len(valid)))
    ax.set_xticklabels(names, rotation=35, ha='right', fontsize=7)
    for b, v in zip(bars, lats):
        ax.text(b.get_x() + b.get_width()/2, b.get_height(),
                f'{v:.0f}', ha='center', va='bottom', fontsize=7)

    # 2. Latency breakdown (stacked)
    ax = axes[0][1]
    comp = [r.compute_latency_us for r in valid]
    comm = [r.comm_latency_us for r in valid]
    x = range(len(valid))
    ax.bar(x, comp, label='Compute', color='#2196F3')
    ax.bar(x, comm, bottom=comp, label='Communication', color='#F44336')
    ax.set_ylabel('Latency (us)')
    ax.set_title('Latency Breakdown')
    ax.set_xticks(range(len(valid)))
    ax.set_xticklabels(names, rotation=35, ha='right', fontsize=7)
    ax.legend(fontsize=8)

    # 3. Total system cost
    ax = axes[0][2]
    costs = [r.total_system_cost for r in valid]
    bars = ax.bar(range(len(valid)), costs, color=bar_colors)
    ax.set_ylabel('Cost ($)')
    ax.set_title('Total System Cost (lower = better)')
    ax.set_xticks(range(len(valid)))
    ax.set_xticklabels(names, rotation=35, ha='right', fontsize=7)
    for b, v in zip(bars, costs):
        ax.text(b.get_x() + b.get_width()/2, b.get_height(),
                f'${v:.0f}', ha='center', va='bottom', fontsize=7)

    # 4. Yield
    ax = axes[1][0]
    yields = [r.yield_pct for r in valid]
    bars = ax.bar(range(len(valid)), yields, color=bar_colors)
    ax.set_ylabel('Yield (%)')
    ax.set_title('Manufacturing Yield (higher = better)')
    ax.set_xticks(range(len(valid)))
    ax.set_xticklabels(names, rotation=35, ha='right', fontsize=7)
    ax.set_ylim(0, 100)
    for b, v in zip(bars, yields):
        ax.text(b.get_x() + b.get_width()/2, b.get_height(),
                f'{v:.1f}%', ha='center', va='bottom', fontsize=7)

    # 5. Performance per dollar
    ax = axes[1][1]
    ppd = [r.perf_per_dollar * 1e6 for r in valid]  # scale for readability
    bars = ax.bar(range(len(valid)), ppd, color=bar_colors)
    ax.set_ylabel('Perf/$ (x10^-6 tok/s/$)')
    ax.set_title('Performance per Dollar (higher = better)')
    ax.set_xticks(range(len(valid)))
    ax.set_xticklabels(names, rotation=35, ha='right', fontsize=7)
    for b, v in zip(bars, ppd):
        ax.text(b.get_x() + b.get_width()/2, b.get_height(),
                f'{v:.2f}', ha='center', va='bottom', fontsize=7)

    # 6. Communication overhead %
    ax = axes[1][2]
    comm_pct = [r.comm_latency_us / r.total_latency_us * 100
                if r.total_latency_us > 0 else 0 for r in valid]
    bars = ax.bar(range(len(valid)), comm_pct, color=bar_colors)
    ax.set_ylabel('Communication Overhead (%)')
    ax.set_title('Comm Overhead (lower = better)')
    ax.set_xticks(range(len(valid)))
    ax.set_xticklabels(names, rotation=35, ha='right', fontsize=7)
    for b, v in zip(bars, comm_pct):
        ax.text(b.get_x() + b.get_width()/2, b.get_height(),
                f'{v:.1f}%', ha='center', va='bottom', fontsize=7)

    plt.tight_layout()
    out = Path(__file__).parent / "results" / "chiplet_analysis_v2.png"
    plt.savefig(out, dpi=150, bbox_inches='tight')
    print(f"\nPlot saved to {out}")
    plt.close()


if __name__ == "__main__":
    results = run_all()
    plot_results(results)
