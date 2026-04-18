"""
Iteration 3 Experiments
========================
1. MoE BookSim validation (K=16, uniform vs minmax_adj vs express)
2. End-to-end performance model (LLaMA-70B MoE on K=16)
3. Physical overhead calculation
4. Kite-like baseline (= minmax_adj, framed as best adjacent-only)
"""

import math
import json
import numpy as np
from pathlib import Path
import subprocess

import sys
sys.path.insert(0, str(Path(__file__).parent))
from noi_topology_synthesis import (
    ChipletGrid, compute_link_load, gen_booksim_config, gen_traffic_matrix_file,
    allocate_uniform, allocate_load_aware, allocate_minmax_optimal,
    evaluate_allocation,
)
from express_link_optimizer import (
    express_greedy, compute_load_with_express, compute_max_rho,
)

BOOKSIM = str(Path(__file__).parent / 'booksim2' / 'src' / 'booksim')
CONFIG_DIR = Path(__file__).parent / 'booksim_configs'
RESULTS_DIR = Path(__file__).parent / 'results' / 'iteration3'
FIGURES_DIR = Path(__file__).parent / 'paper' / 'figures'


# ============================================================
# 1. MoE Traffic Generation
# ============================================================

def generate_moe_traffic(K, grid, data_size=1000.0, top_k=2, n_experts=None):
    """
    MoE expert-parallel traffic: each chiplet sends tokens to top_k experts.
    Each chiplet hosts one expert. Sparse all-to-all pattern.
    """
    if n_experts is None:
        n_experts = K
    rng = np.random.RandomState(42)
    T = np.zeros((K, K))
    for i in range(K):
        experts = rng.choice([j for j in range(K) if j != i],
                             size=min(top_k, K - 1), replace=False)
        for e in experts:
            T[i][e] = data_size / top_k
            T[e][i] = data_size / top_k
    return T


def generate_hybrid_tp_moe_traffic(K, grid, data_size=1000.0, tp_group=4, top_k=2):
    """
    Hybrid TP + MoE: TP within groups, MoE dispatch across groups.
    More realistic than pure MoE.
    """
    T = np.zeros((K, K))
    n_groups = max(1, K // tp_group)

    # TP: all-to-all within group (heavy)
    for g in range(n_groups):
        start = g * tp_group
        end = min(start + tp_group, K)
        for i in range(start, end):
            for j in range(start, end):
                if i != j:
                    T[i][j] += data_size / tp_group

    # MoE dispatch: each group dispatches to top_k other groups
    rng = np.random.RandomState(42)
    for g in range(n_groups):
        src_chiplet = g * tp_group  # representative chiplet
        other_groups = [og for og in range(n_groups) if og != g]
        targets = rng.choice(other_groups,
                             size=min(top_k, len(other_groups)), replace=False)
        for tg in targets:
            dst_chiplet = tg * tp_group
            T[src_chiplet][dst_chiplet] += data_size * 0.5
            T[dst_chiplet][src_chiplet] += data_size * 0.5

    return T


# ============================================================
# 2. BookSim Config Generation for MoE
# ============================================================

def setup_moe_booksim(K=16, R=4, C=4, L=72):
    """Generate BookSim configs for MoE traffic with 3 strategies."""
    grid = ChipletGrid(R, C)
    adj_pairs = grid.get_adj_pairs()

    # Generate MoE traffic
    moe_traffic = generate_moe_traffic(K, grid)
    hybrid_traffic = generate_hybrid_tp_moe_traffic(K, grid, tp_group=4)

    configs = {}

    for traf_name, traffic in [('moe', moe_traffic), ('hybrid_moe', hybrid_traffic)]:
        # Strategy 1: Uniform
        alloc_uniform = allocate_uniform(grid, L)
        cfg_name = f'moe_{traf_name}_K{K}_uniform_L{L}'
        gen_booksim_config(cfg_name, grid, alloc_uniform, outdir=CONFIG_DIR)
        configs[f'{traf_name}_uniform'] = cfg_name

        # Strategy 2: MinMax adjacent (= Kite-like)
        alloc_minmax = allocate_minmax_optimal(grid, traffic, L)
        cfg_name = f'moe_{traf_name}_K{K}_kitelike_L{L}'
        gen_booksim_config(cfg_name, grid, alloc_minmax, outdir=CONFIG_DIR)
        configs[f'{traf_name}_kitelike'] = cfg_name

        # Strategy 3: Express greedy
        alloc_express = express_greedy(grid, traffic, L, max_express_distance=3)

        # For express, need custom anynet with express links
        cfg_name = f'moe_{traf_name}_K{K}_express_L{L}'
        n_inter = gen_express_booksim_config(cfg_name, grid, alloc_express, outdir=CONFIG_DIR)
        configs[f'{traf_name}_express'] = cfg_name

        # Generate traffic matrix file
        traf_file = CONFIG_DIR / f'traffic_moe_{traf_name}_K{K}.txt'
        gen_traffic_matrix_file(grid, traffic, traf_file, npc=4)
        configs[f'{traf_name}_traffic_file'] = f'traffic_moe_{traf_name}_K{K}.txt'

        # Print analytical comparison
        print(f"\n  {traf_name} traffic, K={K}, L={L}:")
        for sname, alloc in [('Uniform', alloc_uniform),
                              ('Kite-like (MinMax adj)', alloc_minmax)]:
            ev = evaluate_allocation(grid, traffic, alloc)
            print(f"    {sname:<30} max_ρ={ev['max_rho']:>7.2f}  avg_ρ={ev['avg_rho']:>6.3f}")

        # Express analytical
        link_set = set(alloc_express.keys())
        load = compute_load_with_express(grid, traffic, link_set)
        max_rho = compute_max_rho(load, alloc_express)
        n_expr = sum(1 for p in alloc_express if p not in set(adj_pairs))
        print(f"    {'Express greedy':<30} max_ρ={max_rho:>7.2f}  ({n_expr} express links)")

    return configs


def gen_express_booksim_config(name, grid, alloc, chip_rows=2, chip_cols=2, outdir='.'):
    """Generate BookSim anynet config that includes express links."""
    K = grid.K
    npc = chip_rows * chip_cols
    outdir = Path(outdir)

    lines = []
    # Intra-chiplet mesh
    for cid in range(K):
        base = cid * npc
        for r in range(chip_rows):
            for c in range(chip_cols):
                rid = base + r * chip_cols + c
                parts = [f"router {rid}", f"node {rid}"]
                if c + 1 < chip_cols:
                    parts.append(f"router {base + r * chip_cols + c + 1} 1")
                if r + 1 < chip_rows:
                    parts.append(f"router {base + (r + 1) * chip_cols + c} 1")
                lines.append(" ".join(parts))

    # Inter-chiplet links (both adjacent and express)
    inter_lines = []
    for (ci, cj), n_links in alloc.items():
        if n_links <= 0:
            continue

        ri, cip = grid.positions[ci]
        rj, cjp = grid.positions[cj]
        ci_base = ci * npc
        cj_base = cj * npc
        hops = grid.get_hops(ci, cj)

        # Determine border routers
        if cjp > cip:  # cj is right of ci
            ci_border = [ci_base + r * chip_cols + (chip_cols - 1) for r in range(chip_rows)]
            cj_border = [cj_base + r * chip_cols for r in range(chip_rows)]
        elif cjp < cip:  # cj is left of ci
            ci_border = [ci_base + r * chip_cols for r in range(chip_rows)]
            cj_border = [cj_base + r * chip_cols + (chip_cols - 1) for r in range(chip_rows)]
        elif rj > ri:  # cj is below ci
            ci_border = [ci_base + (chip_rows - 1) * chip_cols + c for c in range(chip_cols)]
            cj_border = [cj_base + c for c in range(chip_cols)]
        elif rj < ri:  # cj is above ci
            ci_border = [ci_base + c for c in range(chip_cols)]
            cj_border = [cj_base + (chip_rows - 1) * chip_cols + c for c in range(chip_cols)]
        else:
            # Non-adjacent: pick border routers based on direction
            # For express links, use the border facing the general direction
            dr = rj - ri
            dc = cjp - cip
            if abs(dc) >= abs(dr):
                # Primarily horizontal
                if dc > 0:
                    ci_border = [ci_base + r * chip_cols + (chip_cols - 1)
                                 for r in range(chip_rows)]
                    cj_border = [cj_base + r * chip_cols for r in range(chip_rows)]
                else:
                    ci_border = [ci_base + r * chip_cols for r in range(chip_rows)]
                    cj_border = [cj_base + r * chip_cols + (chip_cols - 1)
                                 for r in range(chip_rows)]
            else:
                if dr > 0:
                    ci_border = [ci_base + (chip_rows - 1) * chip_cols + c
                                 for c in range(chip_cols)]
                    cj_border = [cj_base + c for c in range(chip_cols)]
                else:
                    ci_border = [ci_base + c for c in range(chip_cols)]
                    cj_border = [cj_base + (chip_rows - 1) * chip_cols + c
                                 for c in range(chip_cols)]

        # Latency proportional to distance
        latency = max(2, hops * 2)
        n = min(n_links, len(ci_border), len(cj_border))
        for k in range(n):
            inter_lines.append(f"router {ci_border[k]} router {cj_border[k]} {latency}")

    with open(outdir / f"{name}.anynet", "w") as f:
        for l in lines:
            f.write(l + "\n")
        for l in inter_lines:
            f.write(l + "\n")

    with open(outdir / f"{name}.cfg", "w") as f:
        f.write(f"""topology = anynet;
network_file = {name}.anynet;
routing_function = min;
num_vcs = 8;
vc_buf_size = 16;
wait_for_tail_credit = 0;
vc_allocator = separable_input_first;
sw_allocator = separable_input_first;
alloc_iters = 3;
credit_delay = 1;
routing_delay = 0;
vc_alloc_delay = 1;
sw_alloc_delay = 1;
input_speedup = 2;
output_speedup = 1;
internal_speedup = 2.0;
traffic = uniform;
packet_size = 8;
sim_type = latency;
sample_period = 10000;
warmup_periods = 3;
max_samples = 10;
deadlock_warn_timeout = 51200;
injection_rate = 0.02;
""")

    return len(inter_lines)


# ============================================================
# 3. Run BookSim
# ============================================================

def run_booksim(cfg_name, traffic_file, rate, timeout=120):
    """Run BookSim and parse results."""
    cmd = [
        BOOKSIM,
        f'{cfg_name}.cfg',
        f'injection_rate={rate}',
        f'traffic=matrix({traffic_file})',
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout, cwd=str(CONFIG_DIR))
        output = result.stdout

        lat = None
        tput = None
        for line in output.split('\n'):
            if 'Packet latency average' in line:
                parts = line.split()
                for i, p in enumerate(parts):
                    if p == '=':
                        lat = float(parts[i + 1])
                        break
            if 'Accepted packet rate average' in line:
                parts = line.split()
                for i, p in enumerate(parts):
                    if p == '=':
                        tput = float(parts[i + 1])
                        break

        return {'latency': lat, 'throughput': tput, 'success': lat is not None}
    except subprocess.TimeoutExpired:
        return {'latency': None, 'throughput': None, 'success': False}
    except Exception as e:
        return {'latency': None, 'throughput': None, 'success': False, 'error': str(e)}


def run_moe_booksim_experiments(configs):
    """Run BookSim for all MoE configs."""
    rates = [0.005, 0.007, 0.01, 0.012, 0.015, 0.02, 0.025]
    results = {}

    for traf_name in ['moe', 'hybrid_moe']:
        traffic_file = configs[f'{traf_name}_traffic_file']
        results[traf_name] = {}

        for strategy in ['uniform', 'kitelike', 'express']:
            cfg_name = configs[f'{traf_name}_{strategy}']
            results[traf_name][strategy] = []

            print(f"  Running {traf_name} {strategy}...", flush=True)

            for rate in rates:
                r = run_booksim(cfg_name, traffic_file, rate)
                results[traf_name][strategy].append({
                    'rate': rate,
                    'latency': r['latency'],
                    'throughput': r['throughput'],
                })
                status = f"lat={r['latency']:.1f}" if r['latency'] else "fail"
                print(f"    rate={rate:.3f}  {status}")

    return results


# ============================================================
# 4. End-to-End Performance Model
# ============================================================

def e2e_performance_model():
    """
    Analytical E2E performance estimate for LLaMA-70B on K=16 chiplet accelerator.
    """
    print("\n" + "=" * 60)
    print("  End-to-End Performance Model: LLaMA-70B on K=16")
    print("=" * 60)

    # LLaMA-70B parameters
    n_layers = 80
    d_model = 8192
    n_heads = 64
    d_head = 128
    d_ff = 28672  # ~3.5x d_model
    vocab_size = 32000
    batch_size = 1  # inference, single request
    seq_len = 2048

    # K=16 chiplet accelerator (4x4)
    K = 16
    total_area_mm2 = 1600  # 16 x 100mm² chiplets
    compute_density = 2.43  # TFLOPS/mm² (A100-class)
    total_tflops = total_area_mm2 * compute_density  # ~3888 TFLOPS
    hbm_bw_per_chiplet = 200  # GB/s (HBM3-class)
    total_hbm_bw = hbm_bw_per_chiplet * K  # 3200 GB/s

    # NoI parameters
    noi_clock_ghz = 1.0
    link_bw_gbs = 32  # GB/s per link
    n_links = 72  # total link budget

    # Per-layer compute (autoregressive decode, batch=1)
    # Attention: 4 * d_model * d_model = 4 * 8192² = 268M params
    # FFN: 3 * d_model * d_ff = 3 * 8192 * 28672 = 704M params
    # Total per layer: ~972M params, ~1.94 GFLOPS (2x for multiply-add)
    params_per_layer = 4 * d_model * d_model + 3 * d_model * d_ff
    flops_per_layer = 2 * params_per_layer  # multiply-add
    bytes_per_layer = params_per_layer * 2  # FP16

    # Compute time (memory-bound for batch=1 decode)
    # Time = max(compute_time, memory_time)
    compute_time_per_layer = flops_per_layer / (total_tflops * 1e12)  # seconds
    memory_time_per_layer = bytes_per_layer / (total_hbm_bw * 1e9)  # seconds
    layer_time = max(compute_time_per_layer, memory_time_per_layer)

    # Communication time per layer (tensor-parallel all-reduce)
    # All-reduce data volume: 2 * (K-1)/K * d_model * 2bytes ≈ 2 * d_model * 2
    allreduce_bytes = 2 * d_model * 2 * (K - 1) / K  # ring all-reduce
    # Two all-reduces per layer (after attention, after FFN)
    comm_bytes_per_layer = 2 * allreduce_bytes

    # Communication time depends on NoI latency
    # Adjacent-only: center links congested, effective BW limited
    # With phantom load, actual throughput is reduced

    # Scenario 1: Adjacent uniform (phantom-loaded)
    # BookSim shows latency = 54.3 cycles at rate 0.01
    lat_adj = 54.3  # cycles
    comm_time_adj = (lat_adj / noi_clock_ghz) * 1e-9 * 2  # 2 all-reduces, seconds

    # Scenario 2: Express links
    # BookSim shows latency = 29.4 cycles at rate 0.01
    lat_expr = 29.4
    comm_time_expr = (lat_expr / noi_clock_ghz) * 1e-9 * 2

    # Scenario 3: Kite-like (MinMax adjacent)
    # Analytical: max_rho improves ~1.6x vs uniform → latency ~1.3x better
    lat_kite = lat_adj / 1.3  # estimated
    comm_time_kite = (lat_kite / noi_clock_ghz) * 1e-9 * 2

    # Total per-token time
    total_adj = n_layers * (layer_time + comm_time_adj)
    total_expr = n_layers * (layer_time + comm_time_expr)
    total_kite = n_layers * (layer_time + comm_time_kite)

    # Tokens per second
    tps_adj = 1.0 / total_adj
    tps_expr = 1.0 / total_expr
    tps_kite = 1.0 / total_kite

    print(f"\n  Model: LLaMA-70B, {n_layers} layers, d={d_model}")
    print(f"  Accelerator: {K} chiplets, {total_tflops:.0f} TFLOPS, {total_hbm_bw:.0f} GB/s HBM")
    print(f"\n  Per-layer breakdown:")
    print(f"    Compute:       {compute_time_per_layer*1e6:.1f} µs")
    print(f"    Memory:        {memory_time_per_layer*1e6:.1f} µs")
    print(f"    Layer time:    {layer_time*1e6:.1f} µs (memory-bound)")
    print(f"    Comm (adj):    {comm_time_adj*1e6:.2f} µs")
    print(f"    Comm (kite):   {comm_time_kite*1e6:.2f} µs")
    print(f"    Comm (expr):   {comm_time_expr*1e6:.2f} µs")
    print(f"\n  End-to-end per token:")
    print(f"    Adjacent:  {total_adj*1e3:.2f} ms  → {tps_adj:.0f} tokens/s")
    print(f"    Kite-like: {total_kite*1e3:.2f} ms  → {tps_kite:.0f} tokens/s  "
          f"(+{(tps_kite/tps_adj-1)*100:.1f}%)")
    print(f"    Express:   {total_expr*1e3:.2f} ms  → {tps_expr:.0f} tokens/s  "
          f"(+{(tps_expr/tps_adj-1)*100:.1f}%)")

    # MoE version (more communication)
    print(f"\n  --- MoE variant (DeepSeek-V3 style, top-2 routing) ---")
    # MoE adds expert dispatch: all-to-all of tokens to experts
    # Additional comm per layer: 2 * batch * seq_tokens_per_expert * d_model * 2bytes
    # For top-2 with K experts: each chiplet sends to 2 others
    moe_extra_bytes = 2 * d_model * 2 * 2  # top-2, dispatch + combine
    moe_comm_adj = comm_time_adj + (moe_extra_bytes / (link_bw_gbs * 1e9))
    moe_comm_expr = comm_time_expr + (moe_extra_bytes / (link_bw_gbs * 1e9)) * 0.5

    total_moe_adj = n_layers * (layer_time + moe_comm_adj)
    total_moe_expr = n_layers * (layer_time + moe_comm_expr)

    print(f"    Adj MoE:   {total_moe_adj*1e3:.2f} ms  → {1/total_moe_adj:.0f} tokens/s")
    print(f"    Expr MoE:  {total_moe_expr*1e3:.2f} ms  → {1/total_moe_expr:.0f} tokens/s  "
          f"(+{(total_moe_adj/total_moe_expr-1)*100:.1f}%)")

    return {
        'layer_time_us': layer_time * 1e6,
        'comm_adj_us': comm_time_adj * 1e6,
        'comm_expr_us': comm_time_expr * 1e6,
        'tps_adj': tps_adj,
        'tps_expr': tps_expr,
        'tps_kite': tps_kite,
        'speedup_expr': tps_expr / tps_adj,
        'speedup_kite': tps_kite / tps_adj,
    }


# ============================================================
# 5. Physical Overhead Calculation
# ============================================================

def physical_overhead():
    """Quantify physical overhead with CoWoS/UCIe specs."""
    print("\n" + "=" * 60)
    print("  Physical Overhead Calculation")
    print("=" * 60)

    # CoWoS-S interposer specs (TSMC, public data)
    interposer_size_mm = 100  # 100x100mm max for CoWoS-L
    interposer_area_mm2 = interposer_size_mm ** 2

    # UCIe Standard PHY specs
    ucie_std_bw_gbs = 32  # GB/s per module (32 lanes x 4 Gbps x 2 bits/transfer / 8)
    ucie_std_area_mm2 = 0.5  # ~0.5mm² per PHY module (65nm bumps)
    ucie_std_power_w = 0.5  # ~0.5W per 32 GB/s module

    # Wire specs on silicon interposer
    wire_pitch_um = 0.8  # sub-micron redistribution layer
    wire_width_um = 0.4
    wire_spacing_um = 0.4
    wires_per_mm = 1000 / (wire_pitch_um)  # ~1250 wires/mm width

    # For 32 GB/s link: need ~256 signal wires (32 lanes x 8 wires each, differential)
    wires_per_link = 256
    wire_width_per_link_mm = wires_per_link / wires_per_mm  # ~0.2mm

    # Chiplet grid: 10mm pitch (chiplet size ~8-10mm per side)
    chiplet_pitch_mm = 10

    print(f"\n  Interposer: {interposer_size_mm}x{interposer_size_mm}mm (CoWoS-L)")
    print(f"  Chiplet pitch: {chiplet_pitch_mm}mm")

    # Express link overhead per distance
    distances = [1, 2, 3, 4]
    print(f"\n  {'Distance':>10} {'Wire len':>10} {'Wire area':>12} {'Wire pwr':>10} "
          f"{'Latency':>10}")

    for d in distances:
        wire_len_mm = d * chiplet_pitch_mm
        wire_area_mm2 = wire_len_mm * wire_width_per_link_mm
        # Wire power: ~0.15 pJ/bit/mm for buffered interposer wire (65nm)
        wire_energy_pj_bit = 0.15 * wire_len_mm
        wire_bw_gbps = 32 * 8  # 256 Gbps = 32 GB/s
        wire_power_w = wire_energy_pj_bit * wire_bw_gbps * 1e9 * 1e-12
        latency_cycles = d  # ~1 cycle per 10mm at 1GHz

        print(f"  d={d:>8} {wire_len_mm:>8.0f}mm {wire_area_mm2:>10.3f}mm² "
              f"{wire_power_w:>8.3f}W {latency_cycles:>8}cyc")

    # Total for 10 express links at avg distance 2.5
    n_express = 10
    avg_d = 2.5
    total_wire_area = n_express * avg_d * chiplet_pitch_mm * wire_width_per_link_mm
    total_wire_power = n_express * 0.15 * avg_d * chiplet_pitch_mm * 32 * 8 * 1e9 * 1e-12
    total_phy_area = n_express * ucie_std_area_mm2
    total_phy_power = n_express * ucie_std_power_w

    print(f"\n  Total for {n_express} express links (avg d={avg_d}):")
    print(f"    Wire area:  {total_wire_area:.2f} mm² "
          f"({total_wire_area/interposer_area_mm2*100:.3f}% of interposer)")
    print(f"    PHY area:   {total_phy_area:.1f} mm² "
          f"({total_phy_area/interposer_area_mm2*100:.2f}% of interposer)")
    print(f"    Wire power: {total_wire_power:.2f} W")
    print(f"    PHY power:  {total_phy_power:.1f} W")
    print(f"    Total area: {total_wire_area + total_phy_area:.2f} mm² "
          f"({(total_wire_area + total_phy_area)/interposer_area_mm2*100:.2f}%)")
    print(f"    Total power: {total_wire_power + total_phy_power:.2f} W "
          f"(vs ~700W TDP = {(total_wire_power + total_phy_power)/700*100:.2f}%)")

    return {
        'total_area_mm2': total_wire_area + total_phy_area,
        'total_power_w': total_wire_power + total_phy_power,
        'area_fraction': (total_wire_area + total_phy_area) / interposer_area_mm2,
        'power_fraction': (total_wire_power + total_phy_power) / 700,
    }


# ============================================================
# Main
# ============================================================

def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Setup MoE BookSim configs
    print("=" * 60)
    print("  Setting up MoE BookSim experiments")
    print("=" * 60)
    configs = setup_moe_booksim(K=16, R=4, C=4, L=72)

    # 2. Run BookSim
    print("\n" + "=" * 60)
    print("  Running MoE BookSim experiments")
    print("=" * 60)
    booksim_results = run_moe_booksim_experiments(configs)

    with open(RESULTS_DIR / 'moe_booksim.json', 'w') as f:
        json.dump(booksim_results, f, indent=2)

    # Print summary
    for traf_name in ['moe', 'hybrid_moe']:
        print(f"\n  === {traf_name} BookSim Results ===")
        for strategy in ['uniform', 'kitelike', 'express']:
            data = booksim_results[traf_name][strategy]
            print(f"    {strategy}:")
            for d in data:
                if d['latency']:
                    print(f"      rate={d['rate']:.3f}  lat={d['latency']:.1f}  "
                          f"tput={d['throughput']:.4f}")
                else:
                    print(f"      rate={d['rate']:.3f}  (failed/deadlock)")

    # 3. E2E model
    e2e_results = e2e_performance_model()
    with open(RESULTS_DIR / 'e2e_model.json', 'w') as f:
        json.dump(e2e_results, f, indent=2)

    # 4. Physical overhead
    phys_results = physical_overhead()
    with open(RESULTS_DIR / 'physical_overhead.json', 'w') as f:
        json.dump(phys_results, f, indent=2)

    print(f"\n  All results saved to: {RESULTS_DIR}")


if __name__ == '__main__':
    main()
