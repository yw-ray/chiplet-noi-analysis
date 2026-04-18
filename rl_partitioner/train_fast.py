"""
Fast training: MLP vs GNN-enhanced policy comparison.
Uses pre-computed GNN embeddings as features to avoid slow per-step GNN.
"""

import sys
import json
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from envs.chiplet_env import ChipletPartitionEnv
from envs.evaluator import evaluate_partition
from envs.netlist import (
    create_transformer_accelerator_netlist,
    get_node_features,
    get_edge_bandwidth_matrix,
    get_ground_truth_partition,
    netlist_summary,
)

from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback


# ============================================================
# GNN for pre-computing embeddings
# ============================================================

class SimpleGCN(nn.Module):
    """2-layer GCN to produce node embeddings."""
    def __init__(self, in_dim, hidden=64, out_dim=16):
        super().__init__()
        self.fc1 = nn.Linear(in_dim, hidden)
        self.fc2 = nn.Linear(hidden, out_dim)

    def forward(self, x, adj):
        # Symmetric normalization
        deg = adj.sum(dim=1, keepdim=True).clamp(min=1)
        adj_norm = adj / deg
        h = F.relu(self.fc1(adj_norm @ x))
        h = self.fc2(adj_norm @ h)
        return h


def compute_gnn_embeddings(G, n_random_inits=10):
    """
    Pre-compute GNN node embeddings.
    Train GNN to reconstruct adjacency (self-supervised).
    Return best embeddings.
    """
    node_feat = torch.FloatTensor(get_node_features(G))
    adj = torch.FloatTensor(get_edge_bandwidth_matrix(G))
    adj_norm = adj / (adj.max() + 1e-8)

    best_embeddings = None
    best_loss = float('inf')

    for _ in range(n_random_inits):
        model = SimpleGCN(node_feat.shape[1], hidden=32, out_dim=16)
        optimizer = torch.optim.Adam(model.parameters(), lr=0.01)

        for epoch in range(200):
            embeddings = model(node_feat, adj_norm)
            # Reconstruct adjacency from embeddings
            recon = torch.sigmoid(embeddings @ embeddings.T)
            target = (adj_norm > 0).float()
            loss = F.binary_cross_entropy(recon, target)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

        if loss.item() < best_loss:
            best_loss = loss.item()
            with torch.no_grad():
                best_embeddings = model(node_feat, adj_norm).numpy()

    return best_embeddings


# ============================================================
# Enhanced environment with GNN embeddings
# ============================================================

class EnhancedChipletEnv(ChipletPartitionEnv):
    """Env that includes pre-computed GNN embeddings in observations."""

    def __init__(self, gnn_embeddings=None, **kwargs):
        super().__init__(**kwargs)
        self.gnn_embeddings = gnn_embeddings

        if gnn_embeddings is not None:
            gnn_dim = gnn_embeddings.shape[1]
            self.obs_dim += gnn_dim  # current module's GNN embedding

            from gymnasium import spaces
            self.observation_space = spaces.Box(
                low=-np.inf, high=np.inf,
                shape=(self.obs_dim,), dtype=np.float32
            )

    def _get_obs(self):
        base_obs = super()._get_obs()
        if self.gnn_embeddings is not None and self.current_module < len(self.module_order):
            mod_id = self.module_order[self.current_module]
            gnn_feat = self.gnn_embeddings[mod_id]
            return np.concatenate([base_obs, gnn_feat])
        elif self.gnn_embeddings is not None:
            return np.concatenate([base_obs, np.zeros(self.gnn_embeddings.shape[1], dtype=np.float32)])
        return base_obs


# ============================================================
# Baselines
# ============================================================

def random_partition(G, k, rng=None):
    rng = rng or np.random.default_rng(42)
    return rng.integers(0, k, size=G.number_of_nodes())

def balanced_partition(G, k):
    return np.array([i % k for i in range(G.number_of_nodes())])

def greedy_bw_partition(G, k):
    N = G.number_of_nodes()
    bw = get_edge_bandwidth_matrix(G)
    assignment = np.full(N, -1, dtype=int)
    bw_sum = bw.sum(axis=1)
    order = list(np.argsort(-bw_sum))
    assignment[order[0]] = 0
    for idx in range(1, N):
        nid = order[idx]
        bw_to = np.zeros(k)
        count = np.zeros(k)
        for prev in range(idx):
            pnid = order[prev]
            cid = assignment[pnid]
            bw_to[cid] += bw[nid][pnid]
            count[cid] += 1
        avg = idx / k
        bonus = np.maximum(0, avg - count) * 10.0
        assignment[nid] = int(np.argmax(bw_to + bonus))
    return assignment

def spectral_partition(G, k):
    from sklearn.cluster import SpectralClustering
    bw = get_edge_bandwidth_matrix(G)
    return SpectralClustering(n_clusters=k, affinity='precomputed',
                              random_state=42).fit_predict(bw + 1e-6)


class RewardLogger(BaseCallback):
    def __init__(self):
        super().__init__()
        self.episode_rewards = []
        self.best_reward = -np.inf
    def _on_step(self):
        if self.model.ep_info_buffer:
            r = self.model.ep_info_buffer[-1]['r']
            self.episode_rewards.append(r)
            self.best_reward = max(self.best_reward, r)
        return True


def train_and_evaluate(env, name, total_timesteps=30000, n_eval=20):
    model = PPO("MlpPolicy", env, learning_rate=3e-4, n_steps=128,
                batch_size=64, n_epochs=5, gamma=0.99, ent_coef=0.03,
                verbose=0,
                policy_kwargs=dict(net_arch=dict(pi=[128, 64], vf=[128, 64])))
    cb = RewardLogger()
    model.learn(total_timesteps=total_timesteps, callback=cb)

    results = []
    for _ in range(n_eval):
        obs, _ = env.reset()
        done = False
        while not done:
            action, _ = model.predict(obs, deterministic=True)
            obs, _, done, _, info = env.step(action)
        results.append(info)

    avg = {}
    for key in results[0]:
        vals = [r[key] for r in results if isinstance(r.get(key), (int, float))]
        if vals:
            avg[key] = np.mean(vals)

    return avg, cb


def score(m, k):
    return 10.0 * (1 - m['comm_ratio']) * m['balance_score'] * (m['n_active_chiplets'] / k) + m['cost_score']


# ============================================================
# Main
# ============================================================

def main():
    k = 4
    G = create_transformer_accelerator_netlist()
    print("=" * 70)
    print("  Chiplet Partitioning: MLP vs GNN-Enhanced RL")
    print("=" * 70)
    print(f"\n{netlist_summary(G)}")
    print(f"\n  Partitioning into {k} chiplets...")

    # Baselines
    print("\n--- Baselines ---")
    baselines = {
        'Random': random_partition(G, k),
        'Balanced': balanced_partition(G, k),
        'Greedy-BW': greedy_bw_partition(G, k),
        'Spectral': spectral_partition(G, k),
        'Ground Truth': get_ground_truth_partition(G),
    }

    all_results = {}
    for name, assignment in baselines.items():
        m = evaluate_partition(G, assignment, k)
        s = score(m, k)
        all_results[name] = {'m': m, 's': s}
        print(f"  {name:<15} comm={m['comm_ratio']*100:>5.1f}%  bal={m['balance_score']:.3f}  "
              f"util={m['n_active_chiplets']}/{k}  score={s:.2f}")

    # RL + MLP
    print("\n--- RL+MLP (30K steps) ---")
    env_mlp = ChipletPartitionEnv(num_chiplets=k)
    avg_mlp, cb_mlp = train_and_evaluate(env_mlp, "MLP", total_timesteps=30000)
    s_mlp = score(avg_mlp, k)
    print(f"  RL+MLP         comm={avg_mlp['comm_ratio']*100:>5.1f}%  bal={avg_mlp['balance_score']:.3f}  "
          f"util={avg_mlp['n_active_chiplets']:.1f}/{k}  score={s_mlp:.2f}")
    all_results['RL+MLP'] = {'m': avg_mlp, 's': s_mlp}

    # Pre-compute GNN embeddings
    print("\n--- Computing GNN embeddings ---")
    gnn_emb = compute_gnn_embeddings(G)
    print(f"  GNN embeddings: shape {gnn_emb.shape}")

    # RL + GNN embeddings
    print("\n--- RL+GNN (30K steps) ---")
    env_gnn = EnhancedChipletEnv(gnn_embeddings=gnn_emb, num_chiplets=k)
    avg_gnn, cb_gnn = train_and_evaluate(env_gnn, "GNN", total_timesteps=30000)
    s_gnn = score(avg_gnn, k)
    print(f"  RL+GNN         comm={avg_gnn['comm_ratio']*100:>5.1f}%  bal={avg_gnn['balance_score']:.3f}  "
          f"util={avg_gnn['n_active_chiplets']:.1f}/{k}  score={s_gnn:.2f}")
    all_results['RL+GNN'] = {'m': avg_gnn, 's': s_gnn}

    # Final comparison
    print("\n" + "=" * 70)
    print("  FINAL RANKING")
    print("=" * 70)

    sorted_r = sorted(all_results.items(), key=lambda x: x[1]['s'], reverse=True)
    best = sorted_r[0][1]['s']

    print(f"\n{'Rank':>4} {'Method':<15} {'Inter-Chip':>10} {'Balance':>8} {'Util':>5} {'Score':>8} {'vs Best':>8}")
    print("-" * 62)
    for rank, (name, data) in enumerate(sorted_r, 1):
        m = data['m']
        marker = " ★" if rank == 1 else ""
        print(f"{rank:>4} {name:<15} {m['comm_ratio']*100:>9.1f}% {m['balance_score']:>8.3f} "
              f"{m['n_active_chiplets']:>4.1f} {data['s']:>8.2f} {data['s']/best*100:>7.1f}%{marker}")

    # Plot
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(1, 3, figsize=(18, 5))
        fig.suptitle('Chiplet Partitioning: RL+MLP vs RL+GNN vs Baselines',
                     fontsize=13, fontweight='bold')

        # Training curves
        ax = axes[0]
        if cb_mlp.episode_rewards:
            w = min(20, len(cb_mlp.episode_rewards)//4+1)
            sm = np.convolve(cb_mlp.episode_rewards, np.ones(w)/w, 'valid')
            ax.plot(sm, label='RL+MLP', color='#2196F3', linewidth=2)
        if cb_gnn.episode_rewards:
            w = min(20, len(cb_gnn.episode_rewards)//4+1)
            sm = np.convolve(cb_gnn.episode_rewards, np.ones(w)/w, 'valid')
            ax.plot(sm, label='RL+GNN', color='#FF9800', linewidth=2)
        ax.set_xlabel('Episode'); ax.set_ylabel('Reward')
        ax.set_title('Training Curves'); ax.legend(); ax.grid(True, alpha=0.3)

        # Score comparison
        ax = axes[1]
        names = [n for n, _ in sorted_r]
        scores = [d['s'] for _, d in sorted_r]
        colors = ['#FF9800' if 'GNN' in n else '#2196F3' if 'MLP' in n else '#66BB6A' for n in names]
        bars = ax.barh(range(len(names)), scores, color=colors)
        ax.set_yticks(range(len(names))); ax.set_yticklabels(names)
        ax.set_xlabel('Score'); ax.set_title('Partition Quality')
        for b, v in zip(bars, scores):
            ax.text(v+0.05, b.get_y()+b.get_height()/2, f'{v:.2f}', va='center', fontsize=9)
        ax.grid(True, alpha=0.3, axis='x')

        # Comm vs Balance scatter
        ax = axes[2]
        for name, data in all_results.items():
            m = data['m']
            c = '#FF9800' if 'GNN' in name else '#2196F3' if 'MLP' in name else '#66BB6A'
            s = 200 if 'RL' in name or 'Ground' in name else 100
            ax.scatter(m['comm_ratio']*100, m['balance_score'], s=s, c=c,
                       edgecolors='black', linewidth=0.5, zorder=5)
            ax.annotate(name, (m['comm_ratio']*100, m['balance_score']),
                        fontsize=7, xytext=(5, 5), textcoords='offset points')
        ax.set_xlabel('Inter-Chiplet Comm (%)'); ax.set_ylabel('Balance Score')
        ax.set_title('Communication vs Balance\n(bottom-right = best)')
        ax.grid(True, alpha=0.3)
        ax.axvline(x=10, color='red', linestyle=':', alpha=0.3)
        ax.axhline(y=0.9, color='red', linestyle=':', alpha=0.3)

        plt.tight_layout()
        out = Path(__file__).parent / "results" / "mlp_vs_gnn.png"
        plt.savefig(out, dpi=150, bbox_inches='tight')
        print(f"\nPlot: {out}")
        plt.close()
    except Exception as e:
        print(f"Plot error: {e}")


if __name__ == "__main__":
    main()
