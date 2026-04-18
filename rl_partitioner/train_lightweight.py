"""
Lightweight RL training without stable-baselines3 overhead.
Direct REINFORCE (policy gradient) with PyTorch.
"""

import sys
import json
import time
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


# ============================================================
# Simple GCN for pre-computed embeddings
# ============================================================

def compute_gnn_embeddings(G, embed_dim=16, epochs=300):
    node_feat = torch.FloatTensor(get_node_features(G))
    adj = torch.FloatTensor(get_edge_bandwidth_matrix(G))
    adj_norm = adj / (adj.max() + 1e-8)
    deg = adj_norm.sum(1, keepdim=True).clamp(min=1)
    adj_hat = adj_norm / deg  # row-normalized

    fc1 = nn.Linear(node_feat.shape[1], 32)
    fc2 = nn.Linear(32, embed_dim)
    opt = torch.optim.Adam(list(fc1.parameters()) + list(fc2.parameters()), lr=0.01)

    for _ in range(epochs):
        h = F.relu(fc1(adj_hat @ node_feat))
        emb = fc2(adj_hat @ h)
        recon = torch.sigmoid(emb @ emb.T)
        target = (adj_norm > 0).float()
        loss = F.binary_cross_entropy(recon, target)
        opt.zero_grad(); loss.backward(); opt.step()

    with torch.no_grad():
        h = F.relu(fc1(adj_hat @ node_feat))
        emb = fc2(adj_hat @ h)
    return emb.numpy()


# ============================================================
# Policy network
# ============================================================

class Policy(nn.Module):
    def __init__(self, obs_dim, n_actions, hidden=128):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(obs_dim, hidden), nn.ReLU(),
            nn.Linear(hidden, hidden), nn.ReLU(),
            nn.Linear(hidden, n_actions),
        )

    def forward(self, x):
        return F.softmax(self.net(x), dim=-1)


# ============================================================
# REINFORCE training
# ============================================================

def run_episode(env, policy, gnn_emb=None, deterministic=False):
    obs, _ = env.reset()
    if gnn_emb is not None and env.current_module < len(env.module_order):
        mod_id = env.module_order[env.current_module]
        obs = np.concatenate([obs, gnn_emb[mod_id]])

    log_probs = []
    rewards = []
    done = False

    while not done:
        obs_t = torch.FloatTensor(obs).unsqueeze(0)
        probs = policy(obs_t)

        if deterministic:
            action = probs.argmax(dim=-1).item()
        else:
            dist = torch.distributions.Categorical(probs)
            action = dist.sample().item()
            log_probs.append(dist.log_prob(torch.tensor(action)))

        obs, reward, done, _, info = env.step(action)
        if gnn_emb is not None and not done and env.current_module < len(env.module_order):
            mod_id = env.module_order[env.current_module]
            obs = np.concatenate([obs, gnn_emb[mod_id]])

        rewards.append(reward)

    return log_probs, rewards, info


def train_reinforce(env, policy, optimizer, n_episodes=2000, gnn_emb=None, gamma=0.99):
    reward_history = []
    best_reward = -np.inf
    best_info = None

    for ep in range(n_episodes):
        log_probs, rewards, info = run_episode(env, policy, gnn_emb)
        total_reward = sum(rewards)
        reward_history.append(total_reward)

        if total_reward > best_reward:
            best_reward = total_reward
            best_info = info

        # Compute returns
        returns = []
        G_t = 0
        for r in reversed(rewards):
            G_t = r + gamma * G_t
            returns.insert(0, G_t)
        returns = torch.FloatTensor(returns)
        returns = (returns - returns.mean()) / (returns.std() + 1e-8)

        # Policy gradient
        loss = 0
        for lp, ret in zip(log_probs, returns):
            loss -= lp * ret
        # Entropy bonus: use last observation's probs
        if log_probs:
            # Simple entropy approximation from last action distribution
            loss -= 0.01 * len(log_probs)

        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(policy.parameters(), 1.0)
        optimizer.step()

    return reward_history, best_info


def evaluate(env, policy, gnn_emb=None, n_episodes=30):
    results = []
    for _ in range(n_episodes):
        _, _, info = run_episode(env, policy, gnn_emb, deterministic=True)
        results.append(info)
    avg = {}
    for key in results[0]:
        vals = [r[key] for r in results if isinstance(r.get(key), (int, float))]
        if vals: avg[key] = np.mean(vals)
    return avg


# ============================================================
# Baselines
# ============================================================

def random_partition(G, k):
    return np.random.default_rng(42).integers(0, k, size=G.number_of_nodes())

def balanced_partition(G, k):
    return np.array([i % k for i in range(G.number_of_nodes())])

def greedy_bw_partition(G, k):
    N = G.number_of_nodes()
    bw = get_edge_bandwidth_matrix(G)
    assignment = np.full(N, -1, dtype=int)
    order = list(np.argsort(-bw.sum(axis=1)))
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
        bonus = np.maximum(0, idx / k - count) * 10.0
        assignment[nid] = int(np.argmax(bw_to + bonus))
    return assignment

def spectral_partition(G, k):
    from sklearn.cluster import SpectralClustering
    bw = get_edge_bandwidth_matrix(G)
    return SpectralClustering(n_clusters=k, affinity='precomputed',
                              random_state=42).fit_predict(bw + 1e-6)


def score_metrics(m, k):
    if m['n_active_chiplets'] < k:
        return -5.0 + m['n_active_chiplets']
    comm_q = 1.0 - m['comm_ratio']
    return 5.0 * comm_q + 3.0 * m['balance_score'] + m['cost_score']


# ============================================================
# Main
# ============================================================

def main():
    k = 4
    n_episodes = 5000
    G = create_transformer_accelerator_netlist()

    print("=" * 70)
    print("  Chiplet Partitioning: MLP vs GNN-Enhanced REINFORCE")
    print("=" * 70)
    print(f"\n{netlist_summary(G)}")

    # --- Baselines ---
    print("\n--- Baselines ---")
    all_scores = {}
    baselines = {
        'Random': random_partition(G, k),
        'Balanced': balanced_partition(G, k),
        'Greedy-BW': greedy_bw_partition(G, k),
        'Spectral': spectral_partition(G, k),
        'Ground Truth': get_ground_truth_partition(G),
    }
    for name, asgn in baselines.items():
        m = evaluate_partition(G, asgn, k)
        s = score_metrics(m, k)
        all_scores[name] = {'comm': m['comm_ratio'], 'bal': m['balance_score'],
                            'util': m['n_active_chiplets'], 'score': s}
        print(f"  {name:<15} comm={m['comm_ratio']*100:>5.1f}%  bal={m['balance_score']:.3f}  score={s:.2f}")

    # --- RL+MLP ---
    print(f"\n--- RL+MLP ({n_episodes} episodes) ---")
    env_mlp = ChipletPartitionEnv(num_chiplets=k)
    obs_dim = env_mlp.observation_space.shape[0]
    policy_mlp = Policy(obs_dim, k)
    opt_mlp = torch.optim.Adam(policy_mlp.parameters(), lr=1e-3)

    t0 = time.time()
    hist_mlp, _ = train_reinforce(env_mlp, policy_mlp, opt_mlp, n_episodes)
    t_mlp = time.time() - t0
    print(f"  Training time: {t_mlp:.1f}s")

    avg_mlp = evaluate(env_mlp, policy_mlp)
    s_mlp = score_metrics(avg_mlp, k)
    all_scores['RL+MLP'] = {'comm': avg_mlp['comm_ratio'], 'bal': avg_mlp['balance_score'],
                            'util': avg_mlp['n_active_chiplets'], 'score': s_mlp}
    print(f"  RL+MLP         comm={avg_mlp['comm_ratio']*100:>5.1f}%  bal={avg_mlp['balance_score']:.3f}  score={s_mlp:.2f}")

    # --- GNN embeddings ---
    print("\n--- Computing GNN embeddings ---")
    gnn_emb = compute_gnn_embeddings(G, embed_dim=16)
    print(f"  Shape: {gnn_emb.shape}")

    # --- RL+GNN ---
    print(f"\n--- RL+GNN ({n_episodes} episodes) ---")
    env_gnn = ChipletPartitionEnv(num_chiplets=k)
    # obs_dim must match: base env obs + gnn embedding
    base_obs_dim = env_gnn.observation_space.shape[0]
    gnn_dim = gnn_emb.shape[1]
    obs_dim_gnn = base_obs_dim + gnn_dim
    policy_gnn = Policy(obs_dim_gnn, k)
    opt_gnn = torch.optim.Adam(policy_gnn.parameters(), lr=1e-3)

    # Override env observation_space for entropy calculation
    env_gnn._gnn_obs_dim = obs_dim_gnn

    t0 = time.time()
    hist_gnn, _ = train_reinforce(env_gnn, policy_gnn, opt_gnn, n_episodes, gnn_emb=gnn_emb)
    t_gnn = time.time() - t0
    print(f"  Training time: {t_gnn:.1f}s")

    avg_gnn = evaluate(env_gnn, policy_gnn, gnn_emb)
    s_gnn = score_metrics(avg_gnn, k)
    all_scores['RL+GNN'] = {'comm': avg_gnn['comm_ratio'], 'bal': avg_gnn['balance_score'],
                            'util': avg_gnn['n_active_chiplets'], 'score': s_gnn}
    print(f"  RL+GNN         comm={avg_gnn['comm_ratio']*100:>5.1f}%  bal={avg_gnn['balance_score']:.3f}  score={s_gnn:.2f}")

    # --- Final ---
    print("\n" + "=" * 70)
    print("  FINAL RANKING")
    print("=" * 70)

    sorted_r = sorted(all_scores.items(), key=lambda x: x[1]['score'], reverse=True)
    best = sorted_r[0][1]['score']

    print(f"\n{'Rank':>4} {'Method':<15} {'Comm':>8} {'Balance':>8} {'Util':>5} {'Score':>8} {'vs Best':>8}")
    print("-" * 60)
    for rank, (name, d) in enumerate(sorted_r, 1):
        marker = " ★" if rank == 1 else ""
        print(f"{rank:>4} {name:<15} {d['comm']*100:>7.1f}% {d['bal']:>8.3f} "
              f"{d['util']:>4.1f} {d['score']:>8.2f} {d['score']/best*100:>7.1f}%{marker}")

    # --- Plot ---
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(1, 3, figsize=(18, 5))
        fig.suptitle('Chiplet Partitioning: REINFORCE MLP vs GNN', fontsize=13, fontweight='bold')

        # Training curves
        ax = axes[0]
        w = 50
        if len(hist_mlp) > w:
            sm = np.convolve(hist_mlp, np.ones(w)/w, 'valid')
            ax.plot(sm, label='RL+MLP', color='#2196F3', linewidth=2)
        if len(hist_gnn) > w:
            sm = np.convolve(hist_gnn, np.ones(w)/w, 'valid')
            ax.plot(sm, label='RL+GNN', color='#FF9800', linewidth=2)
        ax.set_xlabel('Episode'); ax.set_ylabel('Episode Reward')
        ax.set_title('Training Curves'); ax.legend(); ax.grid(True, alpha=0.3)

        # Bar comparison
        ax = axes[1]
        names = [n for n, _ in sorted_r]
        scores = [d['score'] for _, d in sorted_r]
        colors = ['#FF9800' if 'GNN' in n else '#2196F3' if 'MLP' in n else '#66BB6A' for n in names]
        bars = ax.barh(range(len(names)), scores, color=colors)
        ax.set_yticks(range(len(names))); ax.set_yticklabels(names)
        ax.set_xlabel('Score'); ax.set_title('Partition Quality')
        for b, v in zip(bars, scores):
            ax.text(v+0.05, b.get_y()+b.get_height()/2, f'{v:.2f}', va='center', fontsize=9)

        # Scatter
        ax = axes[2]
        for name, d in all_scores.items():
            c = '#FF9800' if 'GNN' in name else '#2196F3' if 'MLP' in name else '#66BB6A'
            s = 200 if 'RL' in name or 'Ground' in name else 100
            ax.scatter(d['comm']*100, d['bal'], s=s, c=c, edgecolors='black', linewidth=0.5, zorder=5)
            ax.annotate(name, (d['comm']*100, d['bal']), fontsize=7, xytext=(5,5), textcoords='offset points')
        ax.set_xlabel('Inter-Chiplet Comm (%)'); ax.set_ylabel('Balance')
        ax.set_title('Comm vs Balance (bottom-right=best)'); ax.grid(True, alpha=0.3)

        plt.tight_layout()
        out = Path(__file__).parent / "results" / "mlp_vs_gnn.png"
        plt.savefig(out, dpi=150, bbox_inches='tight')
        print(f"\nPlot: {out}")
        plt.close()
    except Exception as e:
        print(f"Plot error: {e}")


if __name__ == "__main__":
    main()
