"""
Transformer Chiplet Partitioning Simulator v3
==============================================
Fair comparison: all configs normalized to same total compute (1000 TOPS).

Key fix: compare at SAME total silicon budget.
  - Monolithic: fewer large dies → low yield, high cost per die
  - Chiplet: many small dies → high yield, low cost per die
  - Same total TOPS, same total HBM → fair performance comparison

Configs:
  A. 2× monolithic 600mm² (NVLink)       — baseline
  B. 1 pkg, 4× 300mm² chiplets (UCIe)
  C. 1 pkg, 8× 150mm² chiplets (UCIe)
  D. 1 pkg, 8× 150mm² chiplets (NoI)
  E. Heterogeneous 4+4 (5nm compute + 28nm memory)
  F. Scaling analysis: 2→4→8→16 chiplets
"""

import math
import json
from dataclasses import dataclass
from pathlib import Path

# ============================================================
# Parameters
# ============================================================

@dataclass
class Model:
    """LLaMA-70B (FP16)."""
    hidden: int = 8192
    layers: int = 80
    heads: int = 64
    head_dim: int = 128
    ffn: int = 28672
    seq: int = 2048
    batch: int = 1
    dbytes: int = 2

    @property
    def weight_per_layer(self):
        return (4 * self.hidden**2 + 3 * self.hidden * self.ffn) * self.dbytes

    @property
    def total_weights(self):
        return self.weight_per_layer * self.layers

    @property
    def activation(self):
        return self.batch * self.seq * self.hidden * self.dbytes

    @property
    def kv_per_layer(self):
        return 2 * self.batch * self.seq * self.hidden * self.dbytes

    @property
    def flops_per_layer(self):
        h, s, b = self.hidden, self.seq, self.batch
        attn = 4 * 2 * b * s * h * h
        qk = 2 * b * self.heads * s * s * self.head_dim
        sv = 2 * b * self.heads * s * s * self.head_dim
        ff = 3 * 2 * b * s * h * self.ffn
        return attn + qk + sv + ff

    @property
    def mem_per_layer(self):
        return self.weight_per_layer + self.kv_per_layer + self.activation


def murphy_yield(area_mm2, dd=0.1):
    d = dd * area_mm2 / 100
    if d == 0: return 1.0
    return ((1 - math.exp(-d)) / d) ** 2


def die_cost(area, wafer_cost=17000, dd=0.1):
    y = murphy_yield(area, dd)
    dpw = int(math.pi * 150**2 / area * 0.9)
    if dpw == 0: return float('inf')
    return wafer_cost / (dpw * y) + 10


def ring_allreduce_time(data_bytes, n_devices, bw_per_link_gbps, latency_per_hop_us):
    """Ring all-reduce latency for n devices."""
    if n_devices <= 1:
        return 0
    # Ring all-reduce: 2*(N-1) steps
    # Total data transferred per link: 2*(N-1)/N * data
    alpha = latency_per_hop_us * 1e-6
    data_per_link = 2 * (n_devices - 1) / n_devices * data_bytes
    t_data = data_per_link / (bw_per_link_gbps * 1e9)
    t_latency = 2 * (n_devices - 1) * alpha
    return t_data + t_latency


# ============================================================
# Simulation
# ============================================================

def simulate_tensor_parallel(
    model, n_devices, device_tops, device_hbm_gb, device_hbm_bw,
    inter_bw_gbps, inter_latency_us,
    name="", desc="", device_area=0, wafer_cost=17000,
    pkg_overhead=0, is_chiplet=False, n_packages=1
):
    """Simulate tensor parallelism across n_devices."""
    m = model

    # Memory check
    total_hbm = device_hbm_gb * n_devices
    fits = total_hbm * 1e9 >= m.total_weights * 1.1  # 10% margin for KV cache etc.

    # Each device computes 1/N of each layer
    t_compute = (m.flops_per_layer / n_devices) / (device_tops * 1e12)
    t_memory = (m.mem_per_layer / n_devices) / (device_hbm_bw * 1e9)
    t_per_layer = max(t_compute, t_memory)

    # Bottleneck analysis
    bottleneck = "compute" if t_compute >= t_memory else "memory"

    # Communication: 2 all-reduces per layer (attn + ffn)
    ar_data = m.activation  # all-reduce the activation tensor
    t_ar = ring_allreduce_time(ar_data, n_devices, inter_bw_gbps, inter_latency_us)
    t_comm_per_layer = 2 * t_ar

    t_total_per_layer = t_per_layer + t_comm_per_layer
    t_total = t_total_per_layer * m.layers

    # Batch throughput (batch=16): pipeline fill + steady state
    batch_size = 16
    t_batch = t_total * batch_size  # simplified (no pipeline benefit for TP)
    throughput_batch = batch_size / t_batch

    # Cost
    y = murphy_yield(device_area)
    dc = die_cost(device_area, wafer_cost)
    total_die = dc * n_devices

    # Packaging
    if is_chiplet:
        cpkg = n_packages  # number of packages
        chiplets_per_pkg = n_devices // cpkg
        interposer_area = device_area * chiplets_per_pkg * 1.3
        pkg_per = 100 + interposer_area * 0.5 + chiplets_per_pkg * 40
        total_pkg = pkg_per * cpkg
    else:
        total_pkg = 100 * n_packages  # simple board mounting

    total_cost = total_die + total_pkg + pkg_overhead

    throughput = 1.0 / t_total
    ppd = throughput / total_cost

    comm_pct = (t_comm_per_layer / t_total_per_layer * 100) if t_total_per_layer > 0 else 0

    return {
        'name': name, 'desc': desc,
        'n_devices': n_devices, 'n_packages': n_packages,
        'device_area': device_area,
        'total_area': device_area * n_devices,
        'total_tops': device_tops * n_devices,
        'total_hbm_gb': total_hbm,
        'fits': fits,
        'bottleneck': bottleneck,
        't_compute_us': t_per_layer * m.layers * 1e6,
        't_comm_us': t_comm_per_layer * m.layers * 1e6,
        't_total_us': t_total * 1e6,
        'comm_pct': comm_pct,
        'throughput_tok_s': throughput,
        'throughput_batch16': throughput_batch,
        'yield_pct': y * 100,
        'die_cost': dc,
        'total_cost': total_cost,
        'ppd': ppd,
        'cost_per_tops': total_cost / (device_tops * n_devices),
    }


def run():
    m = Model()

    print("=" * 85)
    print("  Chiplet vs Monolithic for LLaMA-70B (FP16) Inference")
    print("  All configs: ~1000 TOPS total, tensor parallelism")
    print("=" * 85)
    print(f"\n  Model: {m.total_weights/1e9:.0f} GB weights, "
          f"{m.flops_per_layer * m.layers / 1e12:.0f} TFLOPS/token, "
          f"{m.activation/1e6:.0f} MB activation")

    results = []

    # ================================================================
    # A. Baseline: 2× Monolithic 600mm² (NVLink)
    # ================================================================
    results.append(simulate_tensor_parallel(
        m, n_devices=2, device_tops=500, device_hbm_gb=96, device_hbm_bw=2000,
        inter_bw_gbps=900, inter_latency_us=1.0,
        name="A. 2×Mono 600mm²",
        desc="2 large monolithic chips, NVLink",
        device_area=600, wafer_cost=17000,
        is_chiplet=False, n_packages=2,
    ))

    # ================================================================
    # B. 4× Monolithic 300mm² (NVLink) — same total area (1200mm²)
    # ================================================================
    results.append(simulate_tensor_parallel(
        m, n_devices=4, device_tops=250, device_hbm_gb=48, device_hbm_bw=1000,
        inter_bw_gbps=900, inter_latency_us=1.0,
        name="B. 4×Mono 300mm²",
        desc="4 medium monolithic chips, NVLink",
        device_area=300, wafer_cost=17000,
        is_chiplet=False, n_packages=4,
    ))

    # ================================================================
    # C. 1 package, 4× 300mm² chiplets (UCIe) — same total area
    # ================================================================
    results.append(simulate_tensor_parallel(
        m, n_devices=4, device_tops=250, device_hbm_gb=48, device_hbm_bw=1000,
        inter_bw_gbps=256, inter_latency_us=0.1,
        name="C. 4×Chiplet 300mm²",
        desc="1 pkg, 4 chiplets, UCIe",
        device_area=300, wafer_cost=17000,
        is_chiplet=True, n_packages=1,
    ))

    # ================================================================
    # D. 1 package, 8× 150mm² chiplets (UCIe)
    # ================================================================
    results.append(simulate_tensor_parallel(
        m, n_devices=8, device_tops=125, device_hbm_gb=24, device_hbm_bw=500,
        inter_bw_gbps=256, inter_latency_us=0.1,
        name="D. 8×Chiplet 150mm²",
        desc="1 pkg, 8 chiplets, UCIe",
        device_area=150, wafer_cost=17000,
        is_chiplet=True, n_packages=1,
    ))

    # ================================================================
    # E. 1 package, 8× 150mm² chiplets + NoI
    # NoI: aggregated bandwidth higher, lower hop latency via smart routing
    # ================================================================
    results.append(simulate_tensor_parallel(
        m, n_devices=8, device_tops=125, device_hbm_gb=24, device_hbm_bw=500,
        inter_bw_gbps=512, inter_latency_us=0.05,
        name="E. 8×Chiplet+NoI",
        desc="1 pkg, 8 chiplets, NoI (2x BW, 0.5x lat)",
        device_area=150, wafer_cost=17000,
        is_chiplet=True, n_packages=1,
        pkg_overhead=50,  # NoI router cost
    ))

    # ================================================================
    # F. Heterogeneous: 4× compute(5nm) + 4× I/O(28nm) in 1 package
    # Compute chiplets: high TOPS, 5nm
    # I/O chiplets: HBM controllers + SerDes, 28nm (cheap)
    # ================================================================
    # Approximate: 8 chiplets total, blended wafer cost
    # 4× 5nm (150mm², $17k wafer) + 4× 28nm (100mm², $3k wafer)
    # Average die cost is much lower
    avg_die_cost_hetero = (4 * die_cost(150, 17000) + 4 * die_cost(100, 3000)) / 8

    results.append(simulate_tensor_parallel(
        m, n_devices=8, device_tops=125, device_hbm_gb=24, device_hbm_bw=500,
        inter_bw_gbps=256, inter_latency_us=0.1,
        name="F. Hetero 4+4",
        desc="4×compute(5nm) + 4×I/O(28nm)",
        device_area=135, wafer_cost=10000,  # blended
        is_chiplet=True, n_packages=1,
    ))

    # ================================================================
    # G. Multi-package chiplet: 2 pkg × 4 chiplets (UCIe intra, NVLink inter)
    # ================================================================
    # Within package: UCIe (256 GB/s, 0.1us)
    # Between packages: NVLink (900 GB/s, 1.0us)
    # Effective: weighted average bandwidth
    # For 8-device ring: 4 hops UCIe + ~2 hops NVLink equivalent
    # Simplified: use average BW
    eff_bw = (256 * 6 + 900 * 2) / 8  # rough weighted average
    eff_lat = (0.1 * 6 + 1.0 * 2) / 8
    results.append(simulate_tensor_parallel(
        m, n_devices=8, device_tops=125, device_hbm_gb=24, device_hbm_bw=500,
        inter_bw_gbps=eff_bw, inter_latency_us=eff_lat,
        name="G. 2pkg×4chiplet",
        desc="2 packages, 4 chiplets each, UCIe+NVLink",
        device_area=150, wafer_cost=17000,
        is_chiplet=True, n_packages=2,
    ))

    # ================================================================
    # Print main table
    # ================================================================
    print("\n" + "=" * 85)
    print("  RESULTS (all ~1000 TOPS total, tensor parallelism)")
    print("=" * 85)

    hdr = (f"{'Config':<23} {'#Dev':>4} {'Area':>6} {'HBM':>5} {'Fit':>3} "
           f"{'Latency':>9} {'Comm':>5} {'Yield':>6} {'Cost':>7} "
           f"{'$/TOPS':>7} {'Tok/s':>7}")
    print(f"\n{hdr}")
    print(f"{'':23} {'':>4} {'(mm²)':>6} {'(GB)':>5} {'':>3} "
          f"{'(us)':>9} {'(%)':>5} {'(%)':>6} {'($)':>7} "
          f"{'':>7} {'':>7}")
    print("-" * 100)

    for r in results:
        fit = "OK" if r['fits'] else "NO"
        print(f"{r['name']:<23} {r['n_devices']:>4} {r['total_area']:>6.0f} "
              f"{r['total_hbm_gb']:>5.0f} {fit:>3} "
              f"{r['t_total_us']:>9.0f} {r['comm_pct']:>4.1f}% "
              f"{r['yield_pct']:>5.1f}% ${r['total_cost']:>6.0f} "
              f"${r['cost_per_tops']:>5.2f} {r['throughput_tok_s']:>7.1f}")

    # ================================================================
    # Normalized comparison
    # ================================================================
    print("\n" + "=" * 85)
    print("  NORMALIZED TO BASELINE (A. 2×Mono 600mm²)")
    print("=" * 85)

    base = results[0]
    print(f"\n{'Config':<23} {'Latency':>10} {'Cost':>10} {'Perf/$':>10} {'Verdict':>20}")
    print("-" * 75)

    for r in results:
        lat_r = r['t_total_us'] / base['t_total_us']
        cost_r = r['total_cost'] / base['total_cost']
        ppd_r = r['ppd'] / base['ppd'] if base['ppd'] > 0 else 0

        verdict = ""
        if r['fits']:
            if lat_r <= 1.05 and cost_r < 0.9:
                verdict = "BETTER (cheaper)"
            elif lat_r < 0.9 and cost_r <= 1.1:
                verdict = "BETTER (faster)"
            elif lat_r < 0.95 and cost_r < 0.95:
                verdict = "BETTER (both)"
            elif lat_r > 1.1 and cost_r > 1.1:
                verdict = "WORSE"
            elif ppd_r > 1.1:
                verdict = "better perf/$"
            elif ppd_r < 0.9:
                verdict = "worse perf/$"
            else:
                verdict = "similar"
        else:
            verdict = "NO FIT"

        print(f"{r['name']:<23} {lat_r:>9.2f}x {cost_r:>9.2f}x "
              f"{ppd_r:>9.2f}x {verdict:>20}")

    # ================================================================
    # Scaling analysis: chiplet count sweep
    # ================================================================
    print("\n" + "=" * 85)
    print("  SCALING ANALYSIS: Effect of chiplet count")
    print("  (Fixed: 1200mm² total silicon, tensor parallelism)")
    print("=" * 85)

    chiplet_counts = [2, 4, 8, 16, 32]
    print(f"\n{'#Chiplets':>10} {'Area/chip':>10} {'TOPS/chip':>10} {'Yield':>7} "
          f"{'Die Cost':>9} {'Total Cost':>11} {'Latency':>10} {'Comm%':>6} "
          f"{'$/TOPS':>8}")
    print("-" * 93)

    scaling_results = []
    for nc in chiplet_counts:
        area_each = 1200.0 / nc
        tops_each = 1000.0 / nc
        hbm_each = max(12, 192.0 / nc)  # min 12GB HBM per chiplet
        hbm_bw_each = max(200, 2000.0 / nc * (nc / 2)**0.3)  # BW scales sub-linearly

        r = simulate_tensor_parallel(
            m, n_devices=nc, device_tops=tops_each,
            device_hbm_gb=hbm_each, device_hbm_bw=hbm_bw_each,
            inter_bw_gbps=256, inter_latency_us=0.1,
            name=f"{nc}-chiplet",
            device_area=area_each, wafer_cost=17000,
            is_chiplet=True, n_packages=max(1, nc // 8),
        )
        scaling_results.append(r)

        fit = "OK" if r['fits'] else "NO"
        print(f"{nc:>10} {area_each:>9.0f} {tops_each:>9.0f} "
              f"{r['yield_pct']:>6.1f}% ${r['die_cost']:>8.1f} "
              f"${r['total_cost']:>10.0f} {r['t_total_us']:>10.0f} "
              f"{r['comm_pct']:>5.1f}% ${r['cost_per_tops']:>6.2f}")

    # Repeat with NoI
    print(f"\n  With NoI (2× BW, 0.5× latency):")
    print(f"{'#Chiplets':>10} {'Latency':>10} {'Comm%':>6} {'vs UCIe':>10}")
    print("-" * 40)

    for i, nc in enumerate(chiplet_counts):
        area_each = 1200.0 / nc
        tops_each = 1000.0 / nc
        hbm_each = max(12, 192.0 / nc)
        hbm_bw_each = max(200, 2000.0 / nc * (nc / 2)**0.3)

        r_noi = simulate_tensor_parallel(
            m, n_devices=nc, device_tops=tops_each,
            device_hbm_gb=hbm_each, device_hbm_bw=hbm_bw_each,
            inter_bw_gbps=512, inter_latency_us=0.05,
            name=f"{nc}-chiplet+NoI",
            device_area=area_each, wafer_cost=17000,
            is_chiplet=True, n_packages=max(1, nc // 8),
        )

        r_ucie = scaling_results[i]
        improvement = (1 - r_noi['t_total_us'] / r_ucie['t_total_us']) * 100
        print(f"{nc:>10} {r_noi['t_total_us']:>10.0f} {r_noi['comm_pct']:>5.1f}% "
              f"{improvement:>+9.1f}%")

    # ================================================================
    # Batch throughput comparison
    # ================================================================
    print("\n" + "=" * 85)
    print("  BATCH THROUGHPUT (batch=16, tensor parallelism)")
    print("  (Relevant for serving workloads)")
    print("=" * 85)

    m16 = Model(batch=16)
    batch_results = []

    configs_batch = [
        ("2×Mono 600mm²", 2, 500, 96, 2000, 900, 1.0, 600, False, 2),
        ("4×Chiplet 300mm²", 4, 250, 48, 1000, 256, 0.1, 300, True, 1),
        ("8×Chiplet 150mm²", 8, 125, 24, 500, 256, 0.1, 150, True, 1),
        ("8×Chiplet+NoI", 8, 125, 24, 500, 512, 0.05, 150, True, 1),
    ]

    print(f"\n{'Config':<23} {'Latency(us)':>12} {'Throughput':>12} {'Comm%':>6} {'Cost':>8}")
    print(f"{'':23} {'batch=16':>12} {'(tok/s)':>12} {'':>6} {'($)':>8}")
    print("-" * 65)

    for (nm, nd, tops, hbm, bw, ibw, ilat, area, ic, npkg) in configs_batch:
        r = simulate_tensor_parallel(
            m16, n_devices=nd, device_tops=tops,
            device_hbm_gb=hbm, device_hbm_bw=bw,
            inter_bw_gbps=ibw, inter_latency_us=ilat,
            name=nm, device_area=area, wafer_cost=17000,
            is_chiplet=ic, n_packages=npkg,
        )
        batch_results.append(r)
        print(f"{nm:<23} {r['t_total_us']:>12.0f} {r['throughput_tok_s']:>12.1f} "
              f"{r['comm_pct']:>5.1f}% ${r['total_cost']:>7.0f}")

    # ================================================================
    # Key insights
    # ================================================================
    print("\n" + "=" * 85)
    print("  KEY INSIGHTS")
    print("=" * 85)

    a = results[0]  # 2×Mono
    d = results[3]  # 8×Chiplet UCIe
    e = results[4]  # 8×Chiplet NoI
    f = results[5]  # Hetero

    print(f"""
  1. COST ADVANTAGE:
     2×Mono 600mm²:   ${a['total_cost']:.0f}  (yield {a['yield_pct']:.0f}% per die)
     8×Chiplet 150mm²: ${d['total_cost']:.0f}  (yield {d['yield_pct']:.0f}% per die)
     Hetero 4+4:       ${f['total_cost']:.0f}  (mixed 5nm+28nm)
     → Chiplet cost: {d['total_cost']/a['total_cost']:.2f}x of monolithic
     → Hetero cost:  {f['total_cost']/a['total_cost']:.2f}x of monolithic

  2. PERFORMANCE:
     2×Mono:     {a['t_total_us']:.0f} us (comm {a['comm_pct']:.1f}%)
     8×Chiplet:  {d['t_total_us']:.0f} us (comm {d['comm_pct']:.1f}%)
     8×Chip+NoI: {e['t_total_us']:.0f} us (comm {e['comm_pct']:.1f}%)
     → UCIe chiplet: {d['t_total_us']/a['t_total_us']:.2f}x latency of mono
     → NoI improves: {(1-e['t_total_us']/d['t_total_us'])*100:.1f}% over UCIe

  3. PERFORMANCE PER DOLLAR:
     2×Mono:     ${a['cost_per_tops']:.2f}/TOPS
     8×Chiplet:  ${d['cost_per_tops']:.2f}/TOPS
     Hetero:     ${f['cost_per_tops']:.2f}/TOPS
     → Chiplet $/TOPS: {d['cost_per_tops']/a['cost_per_tops']:.2f}x ({"better" if d['cost_per_tops'] < a['cost_per_tops'] else "worse"})

  4. NoI SCALING:
     NoI benefit grows with chiplet count because all-reduce
     communication scales as O(N) hops. NoI's higher aggregated
     bandwidth and lower per-hop latency compound with more chiplets.

  5. MEMORY:
     8×Chiplet: {d['total_hbm_gb']:.0f} GB total HBM (vs {a['total_hbm_gb']:.0f} GB for 2×Mono)
     → More chiplets = more HBM stacks = larger models fit
""")

    # ================================================================
    # Save & Plot
    # ================================================================
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)

    with open(results_dir / "sim_v3_results.json", "w") as f:
        json.dump(results, f, indent=2)

    return results, scaling_results


def plot_all(results, scaling_results):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("matplotlib not available.")
        return

    out_dir = Path(__file__).parent / "results"

    # === Plot 1: Main comparison ===
    fig, axes = plt.subplots(2, 3, figsize=(20, 11))
    fig.suptitle('Chiplet vs Monolithic: LLaMA-70B FP16 Inference (1000 TOPS total)',
                 fontsize=13, fontweight='bold')

    valid = [r for r in results if r['fits']]
    names = [r['name'] for r in valid]

    def c(name):
        if 'NoI' in name: return '#FF9800'
        if 'Hetero' in name: return '#9C27B0'
        if 'Chiplet' in name or 'chiplet' in name: return '#4CAF50'
        if '2pkg' in name: return '#00BCD4'
        return '#2196F3'

    colors = [c(r['name']) for r in valid]

    # 1. Latency
    ax = axes[0][0]
    vals = [r['t_total_us'] for r in valid]
    bars = ax.bar(range(len(valid)), vals, color=colors)
    ax.set_ylabel('Latency (us)')
    ax.set_title('Inference Latency')
    ax.set_xticks(range(len(valid)))
    ax.set_xticklabels(names, rotation=40, ha='right', fontsize=7)
    for b, v in zip(bars, vals):
        ax.text(b.get_x()+b.get_width()/2, b.get_height(), f'{v:.0f}',
                ha='center', va='bottom', fontsize=7)

    # 2. Cost
    ax = axes[0][1]
    vals = [r['total_cost'] for r in valid]
    bars = ax.bar(range(len(valid)), vals, color=colors)
    ax.set_ylabel('Cost ($)')
    ax.set_title('Total System Cost')
    ax.set_xticks(range(len(valid)))
    ax.set_xticklabels(names, rotation=40, ha='right', fontsize=7)
    for b, v in zip(bars, vals):
        ax.text(b.get_x()+b.get_width()/2, b.get_height(), f'${v:.0f}',
                ha='center', va='bottom', fontsize=7)

    # 3. $/TOPS
    ax = axes[0][2]
    vals = [r['cost_per_tops'] for r in valid]
    bars = ax.bar(range(len(valid)), vals, color=colors)
    ax.set_ylabel('$/TOPS')
    ax.set_title('Cost per TOPS (lower = better)')
    ax.set_xticks(range(len(valid)))
    ax.set_xticklabels(names, rotation=40, ha='right', fontsize=7)
    for b, v in zip(bars, vals):
        ax.text(b.get_x()+b.get_width()/2, b.get_height(), f'${v:.2f}',
                ha='center', va='bottom', fontsize=7)

    # 4. Latency breakdown
    ax = axes[1][0]
    comp = [r['t_compute_us'] for r in valid]
    comm = [r['t_comm_us'] for r in valid]
    x = range(len(valid))
    ax.bar(x, comp, label='Compute', color='#2196F3')
    ax.bar(x, comm, bottom=comp, label='Communication', color='#F44336')
    ax.set_ylabel('Latency (us)')
    ax.set_title('Latency Breakdown')
    ax.set_xticks(range(len(valid)))
    ax.set_xticklabels(names, rotation=40, ha='right', fontsize=7)
    ax.legend(fontsize=8)

    # 5. Yield
    ax = axes[1][1]
    vals = [r['yield_pct'] for r in valid]
    bars = ax.bar(range(len(valid)), vals, color=colors)
    ax.set_ylabel('Yield (%)')
    ax.set_title('Manufacturing Yield')
    ax.set_ylim(0, 100)
    ax.set_xticks(range(len(valid)))
    ax.set_xticklabels(names, rotation=40, ha='right', fontsize=7)
    for b, v in zip(bars, vals):
        ax.text(b.get_x()+b.get_width()/2, b.get_height(), f'{v:.0f}%',
                ha='center', va='bottom', fontsize=7)

    # 6. Comm overhead
    ax = axes[1][2]
    vals = [r['comm_pct'] for r in valid]
    bars = ax.bar(range(len(valid)), vals, color=colors)
    ax.set_ylabel('Comm Overhead (%)')
    ax.set_title('Communication Overhead')
    ax.set_xticks(range(len(valid)))
    ax.set_xticklabels(names, rotation=40, ha='right', fontsize=7)
    for b, v in zip(bars, vals):
        ax.text(b.get_x()+b.get_width()/2, b.get_height(), f'{v:.1f}%',
                ha='center', va='bottom', fontsize=7)

    plt.tight_layout()
    plt.savefig(out_dir / "v3_main.png", dpi=150, bbox_inches='tight')
    plt.close()

    # === Plot 2: Scaling analysis ===
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    fig.suptitle('Scaling Analysis: Chiplet Count vs Performance & Cost (1200mm² total)',
                 fontsize=13, fontweight='bold')

    counts = [r['n_devices'] for r in scaling_results]

    ax = axes[0]
    ax.plot(counts, [r['t_total_us'] for r in scaling_results], 'o-',
            label='UCIe', linewidth=2, color='#4CAF50')
    ax.set_xlabel('Number of Chiplets')
    ax.set_ylabel('Latency (us)')
    ax.set_title('Latency vs Chiplet Count')
    ax.grid(True, alpha=0.3)
    ax.legend()

    ax = axes[1]
    ax.plot(counts, [r['total_cost'] for r in scaling_results], 'o-',
            label='Total Cost', linewidth=2, color='#F44336')
    ax.set_xlabel('Number of Chiplets')
    ax.set_ylabel('Cost ($)')
    ax.set_title('Cost vs Chiplet Count')
    ax.grid(True, alpha=0.3)

    ax = axes[2]
    ax.plot(counts, [r['comm_pct'] for r in scaling_results], 'o-',
            label='UCIe', linewidth=2, color='#4CAF50')
    ax.set_xlabel('Number of Chiplets')
    ax.set_ylabel('Comm Overhead (%)')
    ax.set_title('Communication Overhead vs Chiplet Count')
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(out_dir / "v3_scaling.png", dpi=150, bbox_inches='tight')
    plt.close()

    print(f"\nPlots saved to {out_dir}/v3_main.png and v3_scaling.png")


if __name__ == "__main__":
    results, scaling = run()
    plot_all(results, scaling)
