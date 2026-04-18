"""
Train RL agent for chiplet partitioning and compare with baselines.

Baselines:
  1. Random: random assignment
  2. Greedy-BW: assign to chiplet with most bandwidth to already-placed modules
  3. Balanced: round-robin assignment
  4. METIS-like: spectral clustering on bandwidth matrix

RL Agent: PPO from stable-baselines3
"""

import sys
import json
import numpy as np
import networkx as nx
from pathlib import Path

from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback

sys.path.insert(0, str(Path(__file__).parent))
from envs.chiplet_env import ChipletPartitionEnv
from envs.evaluator import evaluate_partition
from envs.netlist import (
    create_transformer_accelerator_netlist,
    get_edge_bandwidth_matrix,
    get_ground_truth_partition,
    netlist_summary,
)


# ============================================================
# Baselines
# ============================================================

def random_partition(G, num_chiplets, rng=None):
    rng = rng or np.random.default_rng(42)
    N = G.number_of_nodes()
    return rng.integers(0, num_chiplets, size=N)


def balanced_partition(G, num_chiplets):
    """Round-robin by node order."""
    N = G.number_of_nodes()
    return np.array([i % num_chiplets for i in range(N)])


def greedy_bw_partition(G, num_chiplets):
    """Greedy: assign each module to the chiplet with most bandwidth to its neighbors."""
    N = G.number_of_nodes()
    bw_matrix = get_edge_bandwidth_matrix(G)
    assignment = np.full(N, -1, dtype=int)

    # BFS order from highest-degree node
    bw_sum = bw_matrix.sum(axis=1)
    start = int(np.argmax(bw_sum))

    visited = set()
    queue = [start]
    order = []
    while queue:
        node = queue.pop(0)
        if node in visited:
            continue
        visited.add(node)
        order.append(node)
        neighbors = [(bw_matrix[node][n], n) for n in G.neighbors(node)
                     if n not in visited]
        neighbors.sort(reverse=True)
        queue.extend([n for _, n in neighbors])
    for n in range(N):
        if n not in visited:
            order.append(n)

    # Assign first node to chiplet 0
    assignment[order[0]] = 0

    for idx in range(1, N):
        nid = order[idx]
        # Calculate bandwidth to each chiplet
        bw_to_chiplet = np.zeros(num_chiplets)
        count_per_chiplet = np.zeros(num_chiplets)

        for prev_idx in range(idx):
            prev_nid = order[prev_idx]
            cid = assignment[prev_nid]
            bw_to_chiplet[cid] += bw_matrix[nid][prev_nid]
            count_per_chiplet[cid] += 1

        # Balance penalty: prefer chiplets with fewer modules
        avg_count = idx / num_chiplets
        balance_bonus = np.maximum(0, avg_count - count_per_chiplet) * 10.0

        score = bw_to_chiplet + balance_bonus
        assignment[nid] = int(np.argmax(score))

    return assignment


def spectral_partition(G, num_chiplets):
    """Spectral clustering on bandwidth-weighted adjacency."""
    try:
        from sklearn.cluster import SpectralClustering
    except ImportError:
        print("sklearn not available, falling back to balanced partition")
        return balanced_partition(G, num_chiplets)

    N = G.number_of_nodes()
    bw_matrix = get_edge_bandwidth_matrix(G)

    clustering = SpectralClustering(
        n_clusters=num_chiplets,
        affinity='precomputed',
        assign_labels='kmeans',
        random_state=42,
    )
    labels = clustering.fit_predict(bw_matrix + 1e-6)
    return labels


# ============================================================
# RL Agent
# ============================================================

class RewardLogger(BaseCallback):
    def __init__(self):
        super().__init__()
        self.episode_rewards = []
        self.best_reward = -np.inf

    def _on_step(self):
        if len(self.model.ep_info_buffer) > 0:
            latest = self.model.ep_info_buffer[-1]
            self.episode_rewards.append(latest['r'])
            if latest['r'] > self.best_reward:
                self.best_reward = latest['r']
        return True


def train_rl_agent(env, total_timesteps=50000, use_gnn=False):
    """Train PPO agent."""
    if use_gnn:
        from models.gnn_extractor import create_gnn_policy_kwargs
        policy_kwargs = create_gnn_policy_kwargs(env)
        policy = "MlpPolicy"  # SB3 uses MlpPolicy with custom extractor
    else:
        policy_kwargs = dict(
            net_arch=dict(pi=[128, 128], vf=[128, 128])
        )
        policy = "MlpPolicy"

    model = PPO(
        policy,
        env,
        learning_rate=3e-4,
        n_steps=256,
        batch_size=64,
        n_epochs=5,
        gamma=0.99,
        ent_coef=0.03,
        verbose=0,
        policy_kwargs=policy_kwargs,
    )

    callback = RewardLogger()
    model.learn(total_timesteps=total_timesteps, callback=callback)

    return model, callback


def evaluate_rl_agent(model, env, n_episodes=20):
    """Evaluate trained RL agent."""
    results = []
    for _ in range(n_episodes):
        obs, _ = env.reset()
        done = False
        while not done:
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, done, truncated, info = env.step(action)
        results.append(info)
    return results


# ============================================================
# Main
# ============================================================

def main():
    num_chiplets = 4

    print("=" * 70)
    print("  Chiplet Partitioning: RL vs Baselines")
    print("=" * 70)

    # Create netlist
    G = create_transformer_accelerator_netlist(
        num_tensor_cores=16,
        num_sram_banks=8,
        num_hbm_ctrl=4,
    )
    print(f"\n{netlist_summary(G)}")
    print(f"\n  Partitioning into {num_chiplets} chiplets...")

    # ================================================================
    # Baselines
    # ================================================================
    print("\n" + "=" * 70)
    print("  BASELINES")
    print("=" * 70)

    baselines = {
        'Random': random_partition(G, num_chiplets),
        'Balanced (RR)': balanced_partition(G, num_chiplets),
        'Greedy-BW': greedy_bw_partition(G, num_chiplets),
        'Spectral': spectral_partition(G, num_chiplets),
        'Ground Truth': get_ground_truth_partition(G),
    }

    baseline_results = {}
    for name, assignment in baselines.items():
        metrics = evaluate_partition(G, assignment, num_chiplets)
        baseline_results[name] = metrics

    # Print baseline comparison
    print(f"\n{'Method':<18} {'Comm%':>6} {'Balance':>8} {'Cost($)':>8} "
          f"{'Thermal':>8} {'Total':>8}")
    print("-" * 60)

    for name, m in baseline_results.items():
        comm_q = 1.0 - m['comm_ratio']
        bal_q = m['balance_score']
        util = m['n_active_chiplets'] / num_chiplets
        total = 10.0 * comm_q * bal_q * util + m['cost_score']
        print(f"{name:<18} {m['comm_ratio']*100:>5.1f}% {m['balance_score']:>8.3f} "
              f"${m['total_cost']:>7.0f} {m['thermal_score']:>8.3f} {total:>8.3f}")

    # ================================================================
    # RL Training
    # ================================================================
    print("\n" + "=" * 70)
    print("  RL TRAINING (PPO)")
    print("=" * 70)

    env = ChipletPartitionEnv(num_chiplets=num_chiplets)

    # --- MLP Agent ---
    print("\n  Training PPO+MLP agent (100K timesteps)...")
    model_mlp, cb_mlp = train_rl_agent(env, total_timesteps=100000, use_gnn=False)
    print(f"  MLP done. Best reward: {cb_mlp.best_reward:.3f}")

    # --- GNN Agent ---
    print("  Training PPO+GNN agent (100K timesteps)...")
    model_gnn, cb_gnn = train_rl_agent(env, total_timesteps=100000, use_gnn=True)
    print(f"  GNN done. Best reward: {cb_gnn.best_reward:.3f}")

    # Evaluate both
    print("  Evaluating agents (20 episodes each)...")

    def avg_metrics(results_list):
        avg = {}
        for key in results_list[0]:
            vals = [r[key] for r in results_list if isinstance(r.get(key), (int, float))]
            if vals:
                avg[key] = np.mean(vals)
        return avg

    mlp_results = evaluate_rl_agent(model_mlp, env, n_episodes=20)
    gnn_results = evaluate_rl_agent(model_gnn, env, n_episodes=20)
    avg_mlp = avg_metrics(mlp_results)
    avg_gnn = avg_metrics(gnn_results)

    for label, avg_rl, cb in [("MLP", avg_mlp, cb_mlp), ("GNN", avg_gnn, cb_gnn)]:
        comm_q = 1.0 - avg_rl['comm_ratio']
        bal_q = avg_rl['balance_score']
        util = avg_rl['n_active_chiplets'] / num_chiplets
        total_rl = 10.0 * comm_q * bal_q * util + avg_rl['cost_score']
        print(f"\n  RL+{label} (avg 20 episodes):")
        print(f"    Comm ratio:    {avg_rl['comm_ratio']*100:.1f}%")
        print(f"    Balance:       {avg_rl['balance_score']:.3f}")
        print(f"    Utilization:   {avg_rl['n_active_chiplets']:.1f}/{num_chiplets}")
        print(f"    Cost:          ${avg_rl['total_cost']:.0f}")
        print(f"    Total score:   {total_rl:.3f}")

    callback = cb_gnn  # for plotting

    # ================================================================
    # Final comparison
    # ================================================================
    print("\n" + "=" * 70)
    print("  FINAL COMPARISON")
    print("=" * 70)

    all_methods = {}
    for name, m in baseline_results.items():
        comm_q = 1.0 - m['comm_ratio']
        bal_q = m['balance_score']
        util = m['n_active_chiplets'] / num_chiplets
        total = 10.0 * comm_q * bal_q * util + m['cost_score']
        all_methods[name] = {
            'comm_ratio': m['comm_ratio'],
            'balance': m['balance_score'],
            'cost': m['total_cost'],
            'total': total,
            'areas': m['chiplet_areas'],
        }

    for label, avg_rl in [('RL+MLP', avg_mlp), ('RL+GNN', avg_gnn)]:
        comm_q = 1.0 - avg_rl['comm_ratio']
        bal_q = avg_rl['balance_score']
        util = avg_rl['n_active_chiplets'] / num_chiplets
        total_score = 10.0 * comm_q * bal_q * util + avg_rl['cost_score']
        all_methods[label] = {
            'comm_ratio': avg_rl['comm_ratio'],
            'balance': avg_rl['balance_score'],
            'cost': avg_rl['total_cost'],
            'total': total_score,
            'areas': avg_rl.get('chiplet_areas', []),
        }

    # Sort by total score
    sorted_methods = sorted(all_methods.items(), key=lambda x: x[1]['total'], reverse=True)

    best_score = sorted_methods[0][1]['total']
    print(f"\n{'Rank':>4} {'Method':<18} {'Inter-Chip':>10} {'Balance':>8} "
          f"{'Cost($)':>8} {'Score':>8} {'vs Best':>8}")
    print("-" * 68)

    for rank, (name, m) in enumerate(sorted_methods, 1):
        vs_best = m['total'] / best_score * 100
        marker = " ★" if rank == 1 else ""
        print(f"{rank:>4} {name:<18} {m['comm_ratio']*100:>9.1f}% {m['balance']:>8.3f} "
              f"${m['cost']:>7.0f} {m['total']:>8.3f} {vs_best:>7.1f}%{marker}")

    # ================================================================
    # Save results
    # ================================================================
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)

    save_data = {
        'num_modules': G.number_of_nodes(),
        'num_chiplets': num_chiplets,
        'methods': {name: {k: v if not isinstance(v, np.ndarray) else v.tolist()
                           for k, v in m.items()}
                    for name, m in all_methods.items()},
    }
    with open(results_dir / "partition_comparison.json", "w") as f:
        json.dump(save_data, f, indent=2, default=str)

    print(f"\nResults saved to {results_dir / 'partition_comparison.json'}")

    # Training curve
    if callback.episode_rewards:
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt

            fig, axes = plt.subplots(1, 2, figsize=(14, 5))
            fig.suptitle('RL Chiplet Partitioning: Training & Comparison',
                         fontsize=13, fontweight='bold')

            # Training curve
            ax = axes[0]
            rewards = callback.episode_rewards
            window = min(50, len(rewards) // 4 + 1)
            if len(rewards) > window:
                smoothed = np.convolve(rewards, np.ones(window)/window, mode='valid')
                ax.plot(smoothed, color='#2196F3', linewidth=2)
            ax.plot(rewards, alpha=0.2, color='#2196F3')
            ax.set_xlabel('Episode')
            ax.set_ylabel('Episode Reward')
            ax.set_title('RL Training Curve')
            ax.grid(True, alpha=0.3)

            # Comparison bar
            ax = axes[1]
            names = [n for n, _ in sorted_methods]
            scores = [m['total'] for _, m in sorted_methods]
            colors = ['#FF9800' if n == 'RL (PPO)' else '#2196F3' for n in names]
            bars = ax.barh(range(len(names)), scores, color=colors)
            ax.set_yticks(range(len(names)))
            ax.set_yticklabels(names)
            ax.set_xlabel('Total Score (higher = better)')
            ax.set_title('Partitioning Quality Comparison')
            for b, v in zip(bars, scores):
                ax.text(v + 0.05, b.get_y() + b.get_height()/2,
                        f'{v:.2f}', va='center', fontsize=9)
            ax.grid(True, alpha=0.3, axis='x')

            plt.tight_layout()
            plt.savefig(results_dir / "rl_vs_baselines.png", dpi=150,
                        bbox_inches='tight')
            print(f"Plot saved to {results_dir / 'rl_vs_baselines.png'}")
            plt.close()
        except Exception as e:
            print(f"Plotting failed: {e}")


if __name__ == "__main__":
    main()
