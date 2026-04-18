"""
Transformer Chiplet Partitioning Analytical Simulator
=====================================================
Compares monolithic vs layer-pipeline chiplet architectures
for LLM inference acceleration.

Partitioning strategies:
  - Monolithic: single die, all layers
  - 2-chiplet:  layers split into 2 pipeline stages
  - 4-chiplet:  layers split into 4 pipeline stages
  - 4-chiplet + NoI: with network-on-interposer optimization
"""

import math
import json
from dataclasses import dataclass, field
from pathlib import Path


# ============================================================
# 1. Model & Hardware Parameters
# ============================================================

@dataclass
class TransformerConfig:
    """Transformer model configuration (LLaMA-70B-like)."""
    name: str = "LLaMA-70B"
    hidden_dim: int = 8192
    num_layers: int = 80
    num_heads: int = 64
    head_dim: int = 128          # hidden_dim / num_heads
    ffn_dim: int = 28672         # ~3.5x hidden_dim
    vocab_size: int = 32000
    seq_len: int = 2048
    batch_size: int = 1
    dtype_bytes: int = 2         # FP16

    @property
    def weight_per_layer_bytes(self):
        """Weight memory per transformer layer."""
        # Attention: W_Q, W_K, W_V, W_O = 4 * (h * h)
        attn = 4 * self.hidden_dim * self.hidden_dim
        # FFN: W_up, W_down, W_gate (LLaMA uses gated FFN)
        ffn = 3 * self.hidden_dim * self.ffn_dim
        return (attn + ffn) * self.dtype_bytes

    @property
    def total_weight_bytes(self):
        return self.weight_per_layer_bytes * self.num_layers

    @property
    def activation_bytes(self):
        """Activation tensor size passed between layers."""
        return self.batch_size * self.seq_len * self.hidden_dim * self.dtype_bytes

    @property
    def kv_cache_per_layer_bytes(self):
        """KV cache size per layer."""
        # K and V each: batch * seq_len * hidden_dim
        return 2 * self.batch_size * self.seq_len * self.hidden_dim * self.dtype_bytes

    @property
    def flops_per_layer(self):
        """FLOPs per transformer layer (forward pass)."""
        h = self.hidden_dim
        s = self.seq_len
        b = self.batch_size

        # Attention: Q,K,V projections + QK^T + Score*V + Output projection
        attn_proj = 4 * 2 * b * s * h * h        # 4 linear layers
        qk_matmul = 2 * b * self.num_heads * s * s * self.head_dim
        sv_matmul = 2 * b * self.num_heads * s * s * self.head_dim

        # FFN: up + gate + down (gated FFN)
        ffn = 3 * 2 * b * s * h * self.ffn_dim

        return attn_proj + qk_matmul + sv_matmul + ffn

    @property
    def total_flops(self):
        return self.flops_per_layer * self.num_layers

    @property
    def memory_reads_per_layer_bytes(self):
        """Bytes read from memory per layer (weights + KV cache + activation)."""
        return (self.weight_per_layer_bytes
                + self.kv_cache_per_layer_bytes
                + self.activation_bytes)


@dataclass
class HardwareConfig:
    """Hardware configuration for a single chiplet or monolithic die."""
    name: str = "AI Accelerator"
    compute_tops: float = 500       # TOPS (FP16) total chip
    hbm_bw_gbps: float = 2000      # GB/s HBM bandwidth total
    sram_mb: float = 64             # MB on-chip SRAM total
    ucie_bw_gbps: float = 256      # GB/s per UCIe link
    noi_bw_gbps: float = 200       # GB/s NoI effective bandwidth (after routing overhead)
    clock_ghz: float = 1.5
    die_area_mm2: float = 600      # total die area for monolithic
    process_nm: int = 5
    hbm_stacks: int = 4


@dataclass
class CostConfig:
    """Manufacturing cost parameters."""
    wafer_cost_5nm: float = 17000   # $ per wafer
    wafer_cost_28nm: float = 3000
    wafer_diameter_mm: float = 300
    defect_density: float = 0.1     # defects per cm^2
    packaging_cost_per_chiplet: float = 50  # $
    interposer_cost_per_mm2: float = 0.5    # $
    ucie_phy_area_mm2: float = 2.0  # per link
    noi_router_area_mm2: float = 1.5
    test_cost_per_die: float = 10   # $


# ============================================================
# 2. Compute & Latency Models
# ============================================================

def compute_time_s(flops, compute_tops):
    """Time to execute given FLOPs on given compute."""
    return flops / (compute_tops * 1e12)


def memory_time_s(bytes_to_transfer, bw_gbps):
    """Time to transfer data over a given bandwidth."""
    return bytes_to_transfer / (bw_gbps * 1e9)


def layer_latency_s(model: TransformerConfig, hw: HardwareConfig,
                    num_chiplets: int = 1):
    """
    Latency for one transformer layer on one chiplet.
    The chiplet has (1/num_chiplets) of total compute and HBM BW.
    """
    # Each chiplet gets proportional resources
    chiplet_tops = hw.compute_tops / num_chiplets
    chiplet_hbm_bw = hw.hbm_bw_gbps / num_chiplets

    t_compute = compute_time_s(model.flops_per_layer, chiplet_tops)
    t_memory = memory_time_s(model.memory_reads_per_layer_bytes, chiplet_hbm_bw)

    # Roofline: max of compute and memory time
    return max(t_compute, t_memory)


# ============================================================
# 3. Partitioning Strategies
# ============================================================

@dataclass
class SimResult:
    """Simulation result for one configuration."""
    name: str
    num_chiplets: int
    layers_per_chiplet: int
    # Latency
    layer_latency_us: float
    inter_die_latency_us: float
    pipeline_bubble_us: float
    total_latency_us: float
    # Throughput
    throughput_tokens_per_s: float
    # Memory
    weight_per_chiplet_gb: float
    kv_cache_per_chiplet_gb: float
    # Cost
    die_area_mm2: float
    yield_pct: float
    die_cost: float
    total_cost: float
    # Efficiency
    tops_per_dollar: float
    # Bandwidth
    inter_die_data_gb: float
    inter_die_bw_required_gbps: float


def die_yield(area_mm2: float, defect_density: float = 0.1) -> float:
    """Murphy's yield model."""
    area_cm2 = area_mm2 / 100.0
    d = defect_density * area_cm2
    if d == 0:
        return 1.0
    return ((1 - math.exp(-d)) / d) ** 2


def dies_per_wafer(die_area_mm2: float, wafer_diameter_mm: float = 300) -> int:
    """Estimate number of dies per wafer."""
    wafer_area = math.pi * (wafer_diameter_mm / 2) ** 2
    return int(wafer_area / die_area_mm2 * 0.9)  # 90% utilization


def simulate_monolithic(model: TransformerConfig, hw: HardwareConfig,
                        cost: CostConfig) -> SimResult:
    """Simulate monolithic (single die) architecture."""
    t_layer = layer_latency_s(model, hw, num_chiplets=1)
    t_total = t_layer * model.num_layers

    # Cost
    y = die_yield(hw.die_area_mm2, cost.defect_density)
    dpw = dies_per_wafer(hw.die_area_mm2)
    die_cost = cost.wafer_cost_5nm / (dpw * y) + cost.test_cost_per_die
    total_cost = die_cost

    return SimResult(
        name="Monolithic",
        num_chiplets=1,
        layers_per_chiplet=model.num_layers,
        layer_latency_us=t_layer * 1e6,
        inter_die_latency_us=0,
        pipeline_bubble_us=0,
        total_latency_us=t_total * 1e6,
        throughput_tokens_per_s=1.0 / t_total,
        weight_per_chiplet_gb=model.total_weight_bytes / 1e9,
        kv_cache_per_chiplet_gb=(model.kv_cache_per_layer_bytes * model.num_layers) / 1e9,
        die_area_mm2=hw.die_area_mm2,
        yield_pct=y * 100,
        die_cost=die_cost,
        total_cost=total_cost,
        tops_per_dollar=hw.compute_tops / total_cost,
        inter_die_data_gb=0,
        inter_die_bw_required_gbps=0,
    )


def simulate_chiplet_pipeline(model: TransformerConfig, hw: HardwareConfig,
                              cost: CostConfig, num_chiplets: int,
                              use_noi: bool = False) -> SimResult:
    """
    Simulate layer-pipeline chiplet architecture.
    Layers are evenly split across chiplets.
    """
    layers_per_chiplet = model.num_layers // num_chiplets
    chiplet_area = hw.die_area_mm2 / num_chiplets

    # Add UCIe PHY area overhead
    links_per_chiplet = 2 if num_chiplets > 2 else 1  # neighbors
    phy_overhead = links_per_chiplet * cost.ucie_phy_area_mm2
    noi_overhead = cost.noi_router_area_mm2 if use_noi else 0
    effective_compute_area = chiplet_area - phy_overhead - noi_overhead

    # Compute reduction due to area overhead
    area_ratio = effective_compute_area / chiplet_area
    effective_tops = hw.compute_tops * area_ratio

    # Per-chiplet latency for its layers
    chiplet_tops = effective_tops / num_chiplets
    chiplet_hbm_bw = hw.hbm_bw_gbps / num_chiplets

    t_compute_per_layer = compute_time_s(model.flops_per_layer, chiplet_tops)
    t_memory_per_layer = memory_time_s(
        model.memory_reads_per_layer_bytes, chiplet_hbm_bw)
    t_layer = max(t_compute_per_layer, t_memory_per_layer)

    t_chiplet_compute = t_layer * layers_per_chiplet

    # Inter-die communication: activation tensor transfer
    activation_bytes = model.activation_bytes
    inter_die_bw = hw.noi_bw_gbps if use_noi else hw.ucie_bw_gbps
    t_inter_die = memory_time_s(activation_bytes, inter_die_bw)

    # Pipeline model
    # First token: must traverse all chiplets sequentially
    # Pipeline bubble = (num_chiplets - 1) * t_chiplet_compute
    t_first_token = num_chiplets * t_chiplet_compute + (num_chiplets - 1) * t_inter_die

    # For autoregressive inference, each token goes through all stages
    # Pipeline doesn't help much for single-token generation
    # But for prefill (processing prompt), pipeline helps
    t_total = t_first_token  # single token inference

    # Pipeline bubble analysis for prefill (batch processing)
    t_bubble = (num_chiplets - 1) * t_chiplet_compute
    total_inter_die_data = activation_bytes * (num_chiplets - 1)

    # Cost model
    y = die_yield(chiplet_area, cost.defect_density)
    dpw = dies_per_wafer(chiplet_area)
    die_cost = cost.wafer_cost_5nm / (dpw * y) + cost.test_cost_per_die
    total_die_cost = die_cost * num_chiplets

    # Interposer cost
    interposer_area = hw.die_area_mm2 * 1.3  # interposer is ~30% larger
    interposer_cost = interposer_area * cost.interposer_cost_per_mm2

    # Packaging
    pkg_cost = cost.packaging_cost_per_chiplet * num_chiplets

    total_cost = total_die_cost + interposer_cost + pkg_cost

    name = f"{num_chiplets}-Chiplet Pipeline"
    if use_noi:
        name += " + NoI"

    return SimResult(
        name=name,
        num_chiplets=num_chiplets,
        layers_per_chiplet=layers_per_chiplet,
        layer_latency_us=t_layer * 1e6,
        inter_die_latency_us=t_inter_die * 1e6 * (num_chiplets - 1),
        pipeline_bubble_us=t_bubble * 1e6,
        total_latency_us=t_total * 1e6,
        throughput_tokens_per_s=1.0 / t_total,
        weight_per_chiplet_gb=(model.weight_per_layer_bytes * layers_per_chiplet) / 1e9,
        kv_cache_per_chiplet_gb=(model.kv_cache_per_layer_bytes * layers_per_chiplet) / 1e9,
        die_area_mm2=chiplet_area,
        yield_pct=y * 100,
        die_cost=die_cost,
        total_cost=total_cost,
        tops_per_dollar=effective_tops / total_cost,
        inter_die_data_gb=total_inter_die_data / 1e9,
        inter_die_bw_required_gbps=activation_bytes / t_chiplet_compute / 1e9,
    )


# ============================================================
# 4. Run Simulations
# ============================================================

def run_all_simulations():
    model = TransformerConfig()
    hw = HardwareConfig()
    cost = CostConfig()

    print("=" * 70)
    print("Transformer Chiplet Partitioning Analysis")
    print("=" * 70)

    # Model summary
    print(f"\n--- Model: {model.name} ---")
    print(f"  Layers: {model.num_layers}")
    print(f"  Hidden dim: {model.hidden_dim}")
    print(f"  FFN dim: {model.ffn_dim}")
    print(f"  Seq length: {model.seq_len}")
    print(f"  Total weights: {model.total_weight_bytes / 1e9:.1f} GB")
    print(f"  FLOPs/layer: {model.flops_per_layer / 1e9:.1f} GFLOPs")
    print(f"  Total FLOPs: {model.total_flops / 1e12:.1f} TFLOPs")
    print(f"  Activation size (inter-layer): {model.activation_bytes / 1e6:.1f} MB")
    print(f"  KV Cache/layer: {model.kv_cache_per_layer_bytes / 1e6:.1f} MB")
    print(f"  Weight/layer: {model.weight_per_layer_bytes / 1e6:.1f} MB")
    print(f"  Memory reads/layer: {model.memory_reads_per_layer_bytes / 1e6:.1f} MB")

    # Hardware summary
    print(f"\n--- Hardware: {hw.name} ---")
    print(f"  Total compute: {hw.compute_tops} TOPS (FP16)")
    print(f"  HBM bandwidth: {hw.hbm_bw_gbps} GB/s")
    print(f"  On-chip SRAM: {hw.sram_mb} MB")
    print(f"  UCIe bandwidth: {hw.ucie_bw_gbps} GB/s/link")
    print(f"  Die area (monolithic): {hw.die_area_mm2} mm^2")

    # Roofline analysis
    arithmetic_intensity = model.flops_per_layer / model.memory_reads_per_layer_bytes
    ridge_point = hw.compute_tops * 1e12 / (hw.hbm_bw_gbps * 1e9)
    print(f"\n--- Roofline Analysis ---")
    print(f"  Arithmetic Intensity: {arithmetic_intensity:.1f} FLOPs/byte")
    print(f"  Ridge Point: {ridge_point:.1f} FLOPs/byte")
    if arithmetic_intensity < ridge_point:
        print(f"  >> MEMORY-BOUND (AI < Ridge Point)")
    else:
        print(f"  >> COMPUTE-BOUND (AI > Ridge Point)")

    # Run simulations
    results = []

    # 1. Monolithic
    results.append(simulate_monolithic(model, hw, cost))

    # 2. Chiplet variants
    for n in [2, 4, 8]:
        results.append(simulate_chiplet_pipeline(model, hw, cost, n, use_noi=False))

    # 3. Chiplet + NoI variants
    for n in [4, 8]:
        results.append(simulate_chiplet_pipeline(model, hw, cost, n, use_noi=True))

    # Print results table
    print("\n" + "=" * 70)
    print("RESULTS COMPARISON")
    print("=" * 70)

    # Header
    print(f"\n{'Config':<28} {'Latency':>10} {'Perf vs':>8} {'Die':>8} "
          f"{'Yield':>7} {'Total':>8} {'TOPS/$':>8} {'Inter-die':>10}")
    print(f"{'':28} {'(us)':>10} {'Mono':>8} {'(mm2)':>8} "
          f"{'(%)':>7} {'Cost($)':>8} {'':>8} {'Data(MB)':>10}")
    print("-" * 98)

    mono_latency = results[0].total_latency_us

    for r in results:
        perf_ratio = mono_latency / r.total_latency_us
        print(f"{r.name:<28} {r.total_latency_us:>10.1f} {perf_ratio:>8.2f}x "
              f"{r.die_area_mm2:>8.1f} {r.yield_pct:>6.1f}% "
              f"${r.total_cost:>7.1f} {r.tops_per_dollar:>8.2f} "
              f"{r.inter_die_data_gb * 1000:>9.1f}")

    # Detailed breakdown
    print("\n" + "=" * 70)
    print("DETAILED LATENCY BREAKDOWN")
    print("=" * 70)

    print(f"\n{'Config':<28} {'Compute':>10} {'Inter-die':>10} {'Bubble':>10} "
          f"{'Total':>10} {'Bottleneck':>12}")
    print(f"{'':28} {'(us)':>10} {'(us)':>10} {'(us)':>10} "
          f"{'(us)':>10} {'':>12}")
    print("-" * 80)

    for r in results:
        compute_us = r.layer_latency_us * r.layers_per_chiplet * r.num_chiplets
        bottleneck = "Memory" if r.layer_latency_us > 0 else "N/A"
        print(f"{r.name:<28} {compute_us:>10.1f} {r.inter_die_latency_us:>10.2f} "
              f"{r.pipeline_bubble_us:>10.1f} {r.total_latency_us:>10.1f} "
              f"{bottleneck:>12}")

    # Cost-performance analysis
    print("\n" + "=" * 70)
    print("COST-PERFORMANCE ANALYSIS")
    print("=" * 70)

    mono_cost = results[0].total_cost
    mono_perf = results[0].throughput_tokens_per_s

    print(f"\n{'Config':<28} {'Cost':>8} {'Cost':>8} {'Perf':>8} "
          f"{'Perf':>8} {'Perf/$':>10} {'Perf/$':>8}")
    print(f"{'':28} {'($)':>8} {'vs Mono':>8} {'(tok/s)':>8} "
          f"{'vs Mono':>8} {'(tok/s/$)':>10} {'vs Mono':>8}")
    print("-" * 86)

    for r in results:
        cost_ratio = r.total_cost / mono_cost
        perf_ratio = r.throughput_tokens_per_s / mono_perf
        perf_per_dollar = r.throughput_tokens_per_s / r.total_cost
        mono_ppd = mono_perf / mono_cost
        ppd_ratio = perf_per_dollar / mono_ppd

        print(f"{r.name:<28} ${r.total_cost:>7.1f} {cost_ratio:>7.2f}x "
              f"{r.throughput_tokens_per_s:>8.1f} {perf_ratio:>7.2f}x "
              f"{perf_per_dollar:>10.3f} {ppd_ratio:>7.2f}x")

    # Save results as JSON
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)

    results_data = []
    for r in results:
        results_data.append({
            "name": r.name,
            "num_chiplets": r.num_chiplets,
            "layers_per_chiplet": r.layers_per_chiplet,
            "total_latency_us": r.total_latency_us,
            "throughput_tokens_per_s": r.throughput_tokens_per_s,
            "die_area_mm2": r.die_area_mm2,
            "yield_pct": r.yield_pct,
            "total_cost": r.total_cost,
            "tops_per_dollar": r.tops_per_dollar,
            "inter_die_data_mb": r.inter_die_data_gb * 1000,
            "inter_die_bw_required_gbps": r.inter_die_bw_required_gbps,
            "weight_per_chiplet_gb": r.weight_per_chiplet_gb,
            "kv_cache_per_chiplet_gb": r.kv_cache_per_chiplet_gb,
        })

    with open(results_dir / "simulation_results.json", "w") as f:
        json.dump(results_data, f, indent=2)
    print(f"\nResults saved to {results_dir / 'simulation_results.json'}")

    return results


# ============================================================
# 5. Visualization
# ============================================================

def plot_results(results: list[SimResult]):
    """Generate comparison plots."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not available, skipping plots.")
        return

    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    fig.suptitle('Transformer Chiplet Partitioning Analysis (LLaMA-70B, FP16 Inference)',
                 fontsize=14, fontweight='bold')

    names = [r.name for r in results]
    colors = ['#2196F3', '#4CAF50', '#FF9800', '#F44336',
              '#9C27B0', '#00BCD4', '#795548']

    # 1. Total Latency
    ax = axes[0][0]
    latencies = [r.total_latency_us for r in results]
    bars = ax.bar(range(len(results)), latencies, color=colors[:len(results)])
    ax.set_ylabel('Latency (us)')
    ax.set_title('Inference Latency (lower is better)')
    ax.set_xticks(range(len(results)))
    ax.set_xticklabels(names, rotation=30, ha='right', fontsize=8)
    for bar, val in zip(bars, latencies):
        ax.text(bar.get_x() + bar.get_width()/2., bar.get_height(),
                f'{val:.0f}', ha='center', va='bottom', fontsize=8)

    # 2. Manufacturing Cost
    ax = axes[0][1]
    costs = [r.total_cost for r in results]
    bars = ax.bar(range(len(results)), costs, color=colors[:len(results)])
    ax.set_ylabel('Cost ($)')
    ax.set_title('Total Manufacturing Cost (lower is better)')
    ax.set_xticks(range(len(results)))
    ax.set_xticklabels(names, rotation=30, ha='right', fontsize=8)
    for bar, val in zip(bars, costs):
        ax.text(bar.get_x() + bar.get_width()/2., bar.get_height(),
                f'${val:.0f}', ha='center', va='bottom', fontsize=8)

    # 3. Yield
    ax = axes[0][2]
    yields = [r.yield_pct for r in results]
    bars = ax.bar(range(len(results)), yields, color=colors[:len(results)])
    ax.set_ylabel('Yield (%)')
    ax.set_title('Manufacturing Yield (higher is better)')
    ax.set_xticks(range(len(results)))
    ax.set_xticklabels(names, rotation=30, ha='right', fontsize=8)
    ax.set_ylim(0, 100)
    for bar, val in zip(bars, yields):
        ax.text(bar.get_x() + bar.get_width()/2., bar.get_height(),
                f'{val:.1f}%', ha='center', va='bottom', fontsize=8)

    # 4. Performance/Cost (TOPS/$)
    ax = axes[1][0]
    tpd = [r.tops_per_dollar for r in results]
    bars = ax.bar(range(len(results)), tpd, color=colors[:len(results)])
    ax.set_ylabel('TOPS/$')
    ax.set_title('Compute Efficiency (higher is better)')
    ax.set_xticks(range(len(results)))
    ax.set_xticklabels(names, rotation=30, ha='right', fontsize=8)
    for bar, val in zip(bars, tpd):
        ax.text(bar.get_x() + bar.get_width()/2., bar.get_height(),
                f'{val:.2f}', ha='center', va='bottom', fontsize=8)

    # 5. Inter-die Communication
    ax = axes[1][1]
    inter_die = [r.inter_die_data_gb * 1000 for r in results]  # MB
    bars = ax.bar(range(len(results)), inter_die, color=colors[:len(results)])
    ax.set_ylabel('Inter-die Data (MB)')
    ax.set_title('Inter-die Communication (lower is better)')
    ax.set_xticks(range(len(results)))
    ax.set_xticklabels(names, rotation=30, ha='right', fontsize=8)
    for bar, val in zip(bars, inter_die):
        ax.text(bar.get_x() + bar.get_width()/2., bar.get_height(),
                f'{val:.0f}', ha='center', va='bottom', fontsize=8)

    # 6. Latency Breakdown (stacked bar)
    ax = axes[1][2]
    compute = []
    inter_die_lat = []
    for r in results:
        c = r.layer_latency_us * r.layers_per_chiplet * r.num_chiplets
        compute.append(c)
        inter_die_lat.append(r.inter_die_latency_us)

    x = range(len(results))
    ax.bar(x, compute, label='Compute', color='#2196F3')
    ax.bar(x, inter_die_lat, bottom=compute, label='Inter-die', color='#F44336')
    ax.set_ylabel('Latency (us)')
    ax.set_title('Latency Breakdown')
    ax.set_xticks(range(len(results)))
    ax.set_xticklabels(names, rotation=30, ha='right', fontsize=8)
    ax.legend()

    plt.tight_layout()
    output_path = Path(__file__).parent / "results" / "chiplet_comparison.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"Plot saved to {output_path}")
    plt.close()


# ============================================================
# 6. Sensitivity Analysis
# ============================================================

def sensitivity_analysis():
    """Analyze how results change with different parameters."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not available, skipping sensitivity analysis.")
        return

    cost = CostConfig()

    # Sweep die area to show yield advantage
    areas = list(range(50, 850, 50))
    yields_mono = [die_yield(a) * 100 for a in areas]
    yields_2chip = [die_yield(a / 2) * 100 for a in areas]
    yields_4chip = [die_yield(a / 4) * 100 for a in areas]
    yields_8chip = [die_yield(a / 8) * 100 for a in areas]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle('Sensitivity Analysis', fontsize=14, fontweight='bold')

    ax = axes[0]
    ax.plot(areas, yields_mono, 'o-', label='Monolithic', linewidth=2)
    ax.plot(areas, yields_2chip, 's-', label='2-Chiplet', linewidth=2)
    ax.plot(areas, yields_4chip, '^-', label='4-Chiplet', linewidth=2)
    ax.plot(areas, yields_8chip, 'D-', label='8-Chiplet', linewidth=2)
    ax.set_xlabel('Total Die Area (mm^2)')
    ax.set_ylabel('Yield (%)')
    ax.set_title('Yield vs Total Die Area')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.axvline(x=600, color='gray', linestyle='--', alpha=0.5, label='Our design (600mm^2)')

    # Sweep UCIe bandwidth to show communication bottleneck
    bws = [32, 64, 128, 256, 512, 1024]
    model = TransformerConfig()
    hw = HardwareConfig()

    latencies_4chip = []
    for bw in bws:
        hw_temp = HardwareConfig(ucie_bw_gbps=bw)
        r = simulate_chiplet_pipeline(model, hw_temp, cost, 4, use_noi=False)
        latencies_4chip.append(r.total_latency_us)

    mono_lat = simulate_monolithic(model, hw, cost).total_latency_us

    ax = axes[1]
    ax.semilogx(bws, latencies_4chip, 'o-', label='4-Chiplet Pipeline', linewidth=2)
    ax.axhline(y=mono_lat, color='red', linestyle='--', label='Monolithic baseline')
    ax.set_xlabel('UCIe Bandwidth (GB/s)')
    ax.set_ylabel('Latency (us)')
    ax.set_title('4-Chiplet Latency vs UCIe Bandwidth')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_xticks(bws)
    ax.set_xticklabels([str(b) for b in bws])

    plt.tight_layout()
    output_path = Path(__file__).parent / "results" / "sensitivity_analysis.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"Sensitivity plot saved to {output_path}")
    plt.close()


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    results = run_all_simulations()
    plot_results(results)
    sensitivity_analysis()
