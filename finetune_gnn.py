"""Fine-tune the pretrained GNN on each unseen workload config before evaluation."""
import json
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
import torch.optim as optim

import ml_generalization as mg
from ml_generalization import (
    ChipletGrid, WORKLOADS, build_graph_data, gnn_allocate,
    run_booksim, gen_traffic_matrix, gen_anynet_config, alloc_express_greedy,
    TOTAL_LOAD_BASE, CONFIG_DIR, DEVICE, RESULTS_DIR,
    SurrogateModel, GNNPlacementModel,
)


OUT_FILE = RESULTS_DIR / 'ml_generalization_finetuned.json'
FINETUNE_EPOCHS = 100
FINETUNE_LR = 5e-4


def finetune_gnn_for_config(pretrained_state, surrogate, wl, K, N, R, C, bpp):
    """Clone pretrained GNN, fine-tune on this workload for FINETUNE_EPOCHS."""
    model = GNNPlacementModel(node_dim=4, hidden=64, n_layers=3).to(DEVICE)
    model.load_state_dict(pretrained_state)
    model.train()
    optimizer = optim.Adam(model.parameters(), lr=FINETUNE_LR)

    grid = ChipletGrid(R, C)
    traffic = WORKLOADS[wl](K, grid)
    adj_pairs = grid.get_adj_pairs()
    budget = int(len(adj_pairs) * bpp)
    adj_set = set(adj_pairs)
    all_pairs = [(i, j) for i in range(K) for j in range(i+1, K)]

    node_features, adj, edge_features, pair_indices = build_graph_data(grid, traffic, K)
    node_features = node_features.to(DEVICE); adj = adj.to(DEVICE)
    edge_features = edge_features.to(DEVICE); pair_indices = pair_indices.to(DEVICE)

    t_max = traffic.max()
    traffic_norm = traffic / t_max if t_max > 0 else traffic
    traffic_flat = traffic_norm[np.triu_indices(K, k=1)]
    padded = list(traffic_flat) + [0.0] * (496 - len(traffic_flat))

    adj_indices = [i for i, p in enumerate(all_pairs) if p in adj_set]
    non_adj_indices = [i for i, p in enumerate(all_pairs) if p not in adj_set]

    for ep in range(FINETUNE_EPOCHS):
        scores = model(node_features, adj, edge_features, pair_indices)
        probs = F.softmax(scores, dim=0)
        express_frac = (probs[non_adj_indices].sum() if non_adj_indices
                        else torch.tensor(0.0, device=DEVICE))
        features = padded + [bpp/8.0, express_frac.item(), K/32.0, N/8.0]
        x = torch.tensor([features], dtype=torch.float32, device=DEVICE)
        pred_lat = surrogate(x)
        # Encourage diverse scores (entropy reg) + minimize latency
        entropy = -(probs * torch.log(probs + 1e-9)).sum()
        loss = pred_lat - 0.01 * entropy
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

    model.eval()
    return model


def main():
    print('=== Fine-Tuned GNN on Unseen Workloads ===', flush=True)

    surrogate = SurrogateModel(input_dim=500).to(DEVICE)
    surrogate.load_state_dict(torch.load(RESULTS_DIR / 'surrogate_model.pt', map_location=DEVICE))
    surrogate.eval()

    pretrained_state = torch.load(RESULTS_DIR / 'gnn_model.pt', map_location=DEVICE)
    print('  Loaded pretrained GNN state', flush=True)

    unseen = ['ring_allreduce', 'pipeline_parallel', 'all_to_all']
    configs = []
    for wl in unseen:
        configs.append((wl, 16, 4, 4, 4, 4))
        configs.append((wl, 16, 8, 4, 4, 4))
        configs.append((wl, 32, 4, 4, 8, 4))
        configs.append((wl, 32, 8, 4, 8, 4))

    existing = []
    if OUT_FILE.exists():
        existing = json.load(open(OUT_FILE))
    done = {(r['workload'], r['K'], r['N'], r['budget_per_pair']) for r in existing}
    out = list(existing)

    for idx, (wl, K, N, R, C, bpp) in enumerate(configs):
        key = (wl, K, N, bpp)
        if key in done:
            print(f'[{idx+1}/{len(configs)}] SKIP {wl} K{K}N{N} b{bpp}x', flush=True)
            continue

        print(f'\n[{idx+1}/{len(configs)}] {wl} K{K}N{N} b{bpp}x (FT GNN)', flush=True)
        try:
            grid = ChipletGrid(R, C)
            traffic = WORKLOADS[wl](K, grid)
            adj_pairs = grid.get_adj_pairs()
            adj_set = set(adj_pairs)
            budget = int(len(adj_pairs) * bpp)
            npc = N * N
            base_rate = TOTAL_LOAD_BASE / (K * npc)
            label = f'K{K}_N{N}_bpp{bpp}'
            traf_file = f'traffic_ft_{wl}_{label}.txt'
            gen_traffic_matrix(grid, traffic, npc, CONFIG_DIR / traf_file)

            # Greedy baseline
            max_dist = max(2, min(3, max(R, C) - 1))
            greedy_alloc = alloc_express_greedy(grid, traffic, budget, max_dist=max_dist)
            greedy_capped = {p: min(n, N) for p, n in greedy_alloc.items()}
            cfg_g = f'ft_{wl}_{label}_greedy'
            gen_anynet_config(cfg_g, grid, greedy_capped, chip_n=N, outdir=CONFIG_DIR)
            L_g = mg.run_booksim(cfg_g, traf_file, base_rate, timeout=300)['latency']
            print(f'    Greedy: {L_g}', flush=True)

            # Fine-tuned GNN
            t0 = time.time()
            ft_model = finetune_gnn_for_config(pretrained_state, surrogate, wl, K, N, R, C, bpp)
            ft_train_time = time.time() - t0
            ft_alloc = gnn_allocate(ft_model, grid, traffic, K, N, budget)
            ft_capped = {p: min(n, N) for p, n in ft_alloc.items()}
            cfg_ft = f'ft_{wl}_{label}_gnnft'
            gen_anynet_config(cfg_ft, grid, ft_capped, chip_n=N, outdir=CONFIG_DIR)
            L_ft = mg.run_booksim(cfg_ft, traf_file, base_rate, timeout=300)['latency']
            print(f'    FT-GNN: {L_ft}  (train_time={ft_train_time:.1f}s)', flush=True)

            out.append({
                'workload': wl, 'K': K, 'N': N, 'budget_per_pair': bpp,
                'L_greedy': L_g, 'L_gnn_ft': L_ft, 'ft_train_time': ft_train_time,
            })
            with open(OUT_FILE, 'w') as f:
                json.dump(out, f, indent=2)
        except Exception as e:
            print(f'    ERROR: {e}', flush=True)

    print(f'\nDone. Wrote {OUT_FILE}', flush=True)


if __name__ == '__main__':
    main()
