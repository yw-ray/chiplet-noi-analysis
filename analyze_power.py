"""Power analysis: superset vs masked vs kite_l via BookSim sim_power=1.

Reads existing sweep_v3_isowire_seedinject_K*.json results (no re-run needed).
For each completed combo, runs BookSim with sim_power=1 on:
  - superset topology (selected Stage 1 alloc)
  - per-workload masked topology (Stage 2 final_mask)
  - kite_l baseline

Output: results/ml_placement/power_analysis.json + printed table.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from noi_topology_synthesis import ChipletGrid
from cost_performance_experiment import (
    gen_anynet_config, gen_traffic_matrix, BOOKSIM,
)
from ml_express_warmstart import CONFIG_DIR, RESULTS_DIR, TOTAL_LOAD_BASE
from cost_perf_6panel_workload import WORKLOADS

TECHFILE = str(Path(__file__).parent / 'booksim2' / 'src' / 'power' / 'techfile.txt')

CELLS = {
    'K16_N4': (16, 4, 4, 4),
    'K16_N8': (16, 8, 4, 4),
    'K32_N4': (32, 4, 4, 8),
    'K32_N8': (32, 8, 4, 8),
}

POWER_OUT = RESULTS_DIR / 'power_analysis.json'


def str_alloc_to_dict(alloc_str):
    """Convert {'0-1': 3, ...} → {(0,1): 3, ...}"""
    return {tuple(int(x) for x in k.split('-')): v
            for k, v in alloc_str.items() if v > 0}


def run_booksim_power(label, alloc, K, N, R, C, w_name, rate_mult=2.0, timeout=600):
    """Run BookSim with sim_power=1 and return (latency, total_power)."""
    grid = ChipletGrid(R, C)
    traffic = WORKLOADS[w_name](K, grid)
    npc = N * N
    rate = (TOTAL_LOAD_BASE / (K * npc)) * rate_mult
    capped = {p: min(n, N) for p, n in alloc.items() if n > 0}

    cfg_name = f"pwr_{label}_{w_name}_K{K}N{N}"
    traf_file = f"traffic_pwr_{label}_{w_name}_K{K}N{N}.txt"
    gen_traffic_matrix(grid, traffic, npc, CONFIG_DIR / traf_file)
    gen_anynet_config(cfg_name, grid, capped, chip_n=N, outdir=CONFIG_DIR)

    cmd = [BOOKSIM, f'{cfg_name}.cfg',
           f'injection_rate={rate}',
           f'traffic=matrix({traf_file})',
           'sim_power=1',
           f'tech_file={TECHFILE}']
    try:
        result = subprocess.run(cmd, capture_output=True, text=True,
                                timeout=timeout, cwd=str(CONFIG_DIR))
        # Map BookSim power output labels → result keys
        POWER_LABELS = {
            '- Total Power:': 'total_power',
            '- Channel Wire Power:': 'channel_wire',
            '- Channel Clock Power:': 'channel_clock',
            '- Channel Retiming Power:': 'channel_retiming',
            '- Channel Leakage Power:': 'channel_leakage',
            '- Input Read Power:': 'input_read',
            '- Input Write Power:': 'input_write',
            '- Input Leakage Power:': 'input_leakage',
            '- Switch Power:': 'switch',
            '- Switch Control Power:': 'switch_control',
            '- Switch Leakage Power:': 'switch_leakage',
            '- Output DFF Power:': 'output_dff',
            '- Output Clk Power:': 'output_clk',
            '- Output Control Power:': 'output_control',
        }
        lat = None
        pwr = {k: None for k in POWER_LABELS.values()}
        for line in result.stdout.split('\n'):
            if 'Packet latency average' in line and '=' in line:
                parts = line.split()
                for i, p in enumerate(parts):
                    if p == '=' and i + 1 < len(parts):
                        try:
                            lat = float(parts[i + 1])
                        except ValueError:
                            pass
            for label, key in POWER_LABELS.items():
                if line.startswith(label):
                    try:
                        pwr[key] = float(line.split()[-1])
                    except ValueError:
                        pass
        return {
            'latency': lat,
            **pwr,
            'converged': lat is not None and pwr['total_power'] is not None,
        }
    except subprocess.TimeoutExpired:
        return {'latency': None, 'total_power': None, 'converged': False}
    except Exception as e:
        return {'latency': None, 'total_power': None, 'converged': False, 'error': str(e)}


def main():
    if POWER_OUT.exists():
        results = json.loads(POWER_OUT.read_text())
        print(f"Resuming from {POWER_OUT}")
    else:
        results = {}

    for fname in sorted(RESULTS_DIR.glob('sweep_v3_isowire_seedinject_K*.json')):
        sweep = json.loads(fname.read_text())
        cell_key = fname.stem.replace('sweep_v3_isowire_seedinject_', '')
        if cell_key not in CELLS:
            continue
        K, N, R, C = CELLS[cell_key]

        for subset_key, sv in sweep.items():
            cv = sv.get(cell_key, {})
            if not cv.get('stage2') or not cv.get('baselines_at_W'):
                continue

            wl_list = subset_key.split('+')
            combo_key = f'{cell_key}|{subset_key}'

            results.setdefault(combo_key, {})

            selected = cv['selected']
            superset_alloc = str_alloc_to_dict(
                cv['candidates'][selected]['alloc'])
            kite_l_alloc = str_alloc_to_dict(
                cv['baselines_at_W']['kite_l']['alloc'])

            for wl in wl_list:
                if wl not in cv['stage2']:
                    continue
                wl_entry = results[combo_key].get(wl, {})

                mask_alloc = str_alloc_to_dict(
                    cv['stage2'][wl]['final_mask'])

                # superset
                if 'superset' not in wl_entry:
                    print(f"  [{combo_key}|{wl}] superset ...", flush=True)
                    t0 = time.time()
                    r = run_booksim_power(
                        f'v3si_{cell_key}_{subset_key}_super',
                        superset_alloc, K, N, R, C, wl)
                    print(f"    → power={r.get('total_power')} lat={r.get('latency')} "
                          f"({time.time()-t0:.0f}s)", flush=True)
                    wl_entry['superset'] = r

                # masked
                if 'masked' not in wl_entry:
                    print(f"  [{combo_key}|{wl}] masked ...", flush=True)
                    t0 = time.time()
                    r = run_booksim_power(
                        f'v3si_{cell_key}_{subset_key}_mask_{wl[:4]}',
                        mask_alloc, K, N, R, C, wl)
                    print(f"    → power={r.get('total_power')} lat={r.get('latency')} "
                          f"({time.time()-t0:.0f}s)", flush=True)
                    wl_entry['masked'] = r

                # kite_l
                if 'kite_l' not in wl_entry:
                    print(f"  [{combo_key}|{wl}] kite_l ...", flush=True)
                    t0 = time.time()
                    r = run_booksim_power(
                        f'v3si_{cell_key}_{subset_key}_kitel',
                        kite_l_alloc, K, N, R, C, wl)
                    print(f"    → power={r.get('total_power')} lat={r.get('latency')} "
                          f"({time.time()-t0:.0f}s)", flush=True)
                    wl_entry['kite_l'] = r

                results[combo_key][wl] = wl_entry
                POWER_OUT.write_text(json.dumps(results, indent=2))

    # Print summary table
    W = 110
    print('\n' + '='*W)
    print(f'{"Combo":<40} {"WL":<8} {"Super(W)":>10} {"Mask(W)":>10} '
          f'{"Save%":>7} {"kite_l(W)":>10} {"CWire-S":>9} {"CWire-M":>9} {"Sw-S":>7} {"Sw-M":>7}')
    print('-'*W)
    for combo_key, combo_data in sorted(results.items()):
        for wl, wl_data in sorted(combo_data.items()):
            sp = wl_data.get('superset', {}).get('total_power')
            mp = wl_data.get('masked', {}).get('total_power')
            kp = wl_data.get('kite_l', {}).get('total_power')
            cw_sp = wl_data.get('superset', {}).get('channel_wire')
            cw_mp = wl_data.get('masked', {}).get('channel_wire')
            sw_sp = wl_data.get('superset', {}).get('switch')
            sw_mp = wl_data.get('masked', {}).get('switch')
            save = f'{(sp-mp)/sp*100:.1f}%' if sp and mp else 'N/A'
            fmt = lambda v: f'{v:.3f}' if v is not None else 'N/A'
            print(f'{combo_key:<40} {wl[:8]:<8} {fmt(sp):>10} {fmt(mp):>10} '
                  f'{save:>7} {fmt(kp):>10} {fmt(cw_sp):>9} {fmt(cw_mp):>9} '
                  f'{fmt(sw_sp):>7} {fmt(sw_mp):>7}')

    print(f'\nSaved: {POWER_OUT}')


if __name__ == '__main__':
    main()
