"""Extract (alloc, traffic, K, N, rate=4, lat) tuples from all existing
sweep JSONs and save to a single npz file as the seed dataset for
SurrogateV3 training.

Sources searched:
  results/ml_placement/sweep_v3_isowire_K*_N*.json     (main sweep)
  results/ml_placement/sweep_v3_wire_scaling_K*_N*.json (wire scaling)
  results/ml_placement/pilot_booksim_select.json        (pilot)
  results/ml_placement/sweep_v2_full_subsets.json       (partial v2)
  results/ml_placement/sweep_v2_extra_baselines.json    (kite_s/m, gia)

Output: results/ml_placement/surrogate_v3_seed_data.npz
  arrays: alloc_flat (N×496), traffic_flat (N×496), K (N,), N_chips (N,),
          rate_mult (N,), lat (N,)
"""

import json
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from noi_topology_synthesis import ChipletGrid
from cost_perf_6panel_workload import WORKLOADS


N_PAIRS_MAX = 496  # K=32 → 32*31/2 = 496


def all_pairs_for(K):
    return [(i, j) for i in range(K) for j in range(i + 1, K)]


def build_alloc_flat(alloc_dict, all_pairs):
    """alloc_dict: {'i-j': count} or {(i,j): count}. Output: float[496]."""
    out = np.zeros(N_PAIRS_MAX, dtype=np.float32)
    for k, v in alloc_dict.items():
        if isinstance(k, str):
            i, j = (int(x) for x in k.split('-'))
        else:
            i, j = k
        if (i, j) in all_pairs:
            idx = all_pairs.index((i, j))
            out[idx] = v
    return out


def build_traffic_flat(workload_name, K, grid):
    traffic = WORKLOADS[workload_name](K, grid)
    t_max = traffic.max()
    if t_max > 0:
        traffic_norm = traffic / t_max
    else:
        traffic_norm = traffic
    triu = np.triu_indices(K, k=1)
    flat = traffic_norm[triu].astype(np.float32)
    out = np.zeros(N_PAIRS_MAX, dtype=np.float32)
    out[: len(flat)] = flat
    return out


def grid_for(K):
    if K == 16:
        return ChipletGrid(4, 4)
    if K == 32:
        return ChipletGrid(4, 8)
    raise ValueError(f"unknown K={K}")


def n_for(K, N):
    return N * N  # cores per chip


def add_pair(records, alloc_dict, K, N_chips, workload, lat,
             rate_mult=4.0):
    """Append one training tuple to `records` (in-place)."""
    if lat is None or lat <= 0:
        return False
    grid = grid_for(K)
    pairs = all_pairs_for(K)
    pair_index = {p: i for i, p in enumerate(pairs)}

    alloc_flat = np.zeros(N_PAIRS_MAX, dtype=np.float32)
    for k, v in alloc_dict.items():
        if isinstance(k, str):
            i, j = (int(x) for x in k.split('-'))
        else:
            i, j = k
        p = (min(i, j), max(i, j))
        if p in pair_index:
            alloc_flat[pair_index[p]] = v / N_chips  # normalize by per-pair cap N

    traffic_flat = build_traffic_flat(workload, K, grid)

    records['alloc'].append(alloc_flat)
    records['traffic'].append(traffic_flat)
    records['K'].append(K)
    records['N'].append(N_chips)
    records['rate'].append(rate_mult)
    records['lat'].append(lat)
    return True


def extract_v3_isowire(path, records):
    """sweep_v3_isowire_K*_N*.json → records.

    Per (subset, cell): each candidate gives (alloc, raw_per_wl).
    Also each baseline at_W gives (alloc, lat dict).
    Stage-2 final mask gives one more (alloc, lat) per workload.
    """
    if not os.path.exists(path):
        return 0
    d = json.load(open(path))
    n_added = 0
    for subset_key, by_cell in d.items():
        for cell_key, combo in by_cell.items():
            if not combo or not combo.get('candidates'):
                continue
            K = int(cell_key.split('_')[0][1:])
            N = int(cell_key.split('_')[1][1:])
            for cname, cand in combo['candidates'].items():
                alloc_dict = cand.get('alloc', {})
                per_wl = cand.get('raw_per_wl', {})
                for w, lat in per_wl.items():
                    if add_pair(records, alloc_dict, K, N, w, lat):
                        n_added += 1
            if combo.get('baselines_at_W'):
                for bname, b in combo['baselines_at_W'].items():
                    alloc_dict = b.get('alloc', {})
                    lat_per_wl = b.get('lat', {})
                    for w, lat in lat_per_wl.items():
                        if add_pair(records, alloc_dict, K, N, w, lat):
                            n_added += 1
            if combo.get('stage2'):
                for w, info in combo['stage2'].items():
                    alloc_dict = info.get('final_mask', {})
                    lat = info.get('mask_lat')
                    if add_pair(records, alloc_dict, K, N, w, lat):
                        n_added += 1
    return n_added


def extract_wire_scaling(path, records):
    """sweep_v3_wire_scaling_K*_N*.json: same schema but at top-level by W."""
    if not os.path.exists(path):
        return 0
    d = json.load(open(path))
    K = N = None
    if 'K16_N4' in path:
        K, N = 16, 4
    elif 'K16_N8' in path:
        K, N = 16, 8
    elif 'K32_N4' in path:
        K, N = 32, 4
    elif 'K32_N8' in path:
        K, N = 32, 8
    else:
        return 0
    n_added = 0
    for W_key, combo in d.items():
        if not combo or not combo.get('candidates'):
            continue
        for cname, cand in combo['candidates'].items():
            alloc_dict = cand.get('alloc', {})
            per_wl = cand.get('raw_per_wl', {})
            for w, lat in per_wl.items():
                if add_pair(records, alloc_dict, K, N, w, lat):
                    n_added += 1
        if combo.get('baselines_at_W'):
            for bname, b in combo['baselines_at_W'].items():
                alloc_dict = b.get('alloc', {})
                lat_per_wl = b.get('lat', {})
                for w, lat in lat_per_wl.items():
                    if add_pair(records, alloc_dict, K, N, w, lat):
                        n_added += 1
        if combo.get('stage2'):
            for w, info in combo['stage2'].items():
                alloc_dict = info.get('final_mask', {})
                lat = info.get('mask_lat')
                if add_pair(records, alloc_dict, K, N, w, lat):
                    n_added += 1
    return n_added


def extract_pilot(path, records):
    if not os.path.exists(path):
        return 0
    d = json.load(open(path))
    n_added = 0
    for cell_tag, info in d.items():
        if not info or not info.get('candidates'):
            continue
        cell = info.get('cell', {})
        K = cell.get('K')
        N = cell.get('N')
        if K is None or N is None:
            continue
        for cname, cand in info['candidates'].items():
            alloc_dict = cand.get('alloc', {})
            per_wl = cand.get('raw_per_wl', {})
            for w, lat in per_wl.items():
                if add_pair(records, alloc_dict, K, N, w, lat):
                    n_added += 1
        if info.get('stage2'):
            for w, s2 in info['stage2'].items():
                alloc_dict = s2.get('final_mask', {})
                lat = s2.get('mask_lat')
                if add_pair(records, alloc_dict, K, N, w, lat):
                    n_added += 1
                # mesh and kite_l from stage2
                for k_alt in ('mesh_lat', 'kite_l_lat'):
                    if s2.get(k_alt) is not None:
                        # alloc not stored separately for these; skip
                        pass
    return n_added


def extract_v2_full(path, records):
    if not os.path.exists(path):
        return 0
    d = json.load(open(path))
    n_added = 0
    for subset_key, by_cell in d.items():
        for cell_key, by_bpp in by_cell.items():
            for bpp_key, combo in by_bpp.items():
                if not combo:
                    continue
                K = int(cell_key.split('_')[0][1:])
                N = int(cell_key.split('_')[1][1:])
                # superset
                superset = combo.get('superset', {})
                workloads = combo.get('workloads', {})
                for w, info in workloads.items():
                    raw_lat = info.get('raw_lat')
                    if raw_lat:
                        if add_pair(records, superset, K, N, w, raw_lat):
                            n_added += 1
                    final_mask = info.get('final_mask', {})
                    mask_lat = info.get('mask_lat')
                    if mask_lat:
                        if add_pair(records, final_mask, K, N, w, mask_lat):
                            n_added += 1
    return n_added


def main():
    records = {'alloc': [], 'traffic': [], 'K': [], 'N': [], 'rate': [],
               'lat': []}
    base = Path('results/ml_placement')

    counts = {}
    for K in [16, 32]:
        for N in [4, 8]:
            f = base / f'sweep_v3_isowire_K{K}_N{N}.json'
            n = extract_v3_isowire(str(f), records)
            counts[f'isowire_K{K}_N{N}'] = n
            f2 = base / f'sweep_v3_wire_scaling_K{K}_N{N}.json'
            n2 = extract_wire_scaling(str(f2), records)
            counts[f'wirescaling_K{K}_N{N}'] = n2

    f = base / 'pilot_booksim_select.json'
    counts['pilot'] = extract_pilot(str(f), records)

    f = base / 'sweep_v2_full_subsets.json'
    counts['v2_full'] = extract_v2_full(str(f), records)

    print('=== Extraction counts ===')
    for k, v in counts.items():
        print(f'  {k}: {v} pairs')
    total = sum(counts.values())
    print(f'  Total: {total} pairs')

    # Also dedup near-identical (same alloc + traffic + K + N)
    alloc_arr = np.stack(records['alloc'])
    traffic_arr = np.stack(records['traffic'])
    K_arr = np.array(records['K'], dtype=np.int32)
    N_arr = np.array(records['N'], dtype=np.int32)
    rate_arr = np.array(records['rate'], dtype=np.float32)
    lat_arr = np.array(records['lat'], dtype=np.float32)

    print(f'\nFinal: {len(lat_arr)} pairs')
    print(f'  K=16: {(K_arr == 16).sum()}, K=32: {(K_arr == 32).sum()}')
    print(f'  N=4: {(N_arr == 4).sum()}, N=8: {(N_arr == 8).sum()}')
    print(f'  Lat range: {lat_arr.min():.1f} - {lat_arr.max():.1f}')

    out_path = base / 'surrogate_v3_seed_data.npz'
    np.savez_compressed(
        out_path,
        alloc=alloc_arr, traffic=traffic_arr,
        K=K_arr, N=N_arr, rate=rate_arr, lat=lat_arr,
    )
    print(f'\nSaved: {out_path} ({out_path.stat().st_size / 1024:.0f} KB)')


if __name__ == '__main__':
    main()
