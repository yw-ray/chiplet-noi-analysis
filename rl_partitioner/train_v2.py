"""
Chiplet Partitioning v2: RL + Constraint Solver + Multi-Objective
=================================================================
Key improvements over v1:
  1. Spectral initialization → RL refinement (not from scratch)
  2. Constraint solver forces valid partitions (balance, capacity)
  3. Multi-objective: comm + balance + thermal + heterogeneous cost
  4. RL only needs to learn REFINEMENT, not full partition

Architecture:
  Spectral → initial partition → RL swaps modules between chiplets
  → constraint solver validates → evaluate multi-objective → reward
"""

import sys
import time
import json
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from envs.netlist import (
    create_transformer_accelerator_netlist,
    get_node_features,
    get_edge_bandwidth_matrix,
    get_ground_truth_partition,
    netlist_summary,
)
from envs.evaluator import evaluate_partition


# ============================================================
# Multi-objective evaluator (thermal + hetero cost)
# ============================================================

def multi_objective_score(G, assignment, num_chiplets, process_assignment=None):
    """
    Extended evaluation with thermal and heterogeneous process cost.
    Returns dict with individual scores and weighted total.
    """
    base = evaluate_partition(G, assignment, num_chiplets)

    # --- Thermal: power density per chiplet ---
    chiplet_power = np.array(base['chiplet_power'])
    chiplet_area = np.array(base['chiplet_areas'])
    power_density = np.where(chiplet_area > 0, chiplet_power / chiplet_area, 0)
    max_pd = np.max(power_density)
    thermal_score = max(0, 1.0 - max(0, max_pd - 0.8) / 0.4)  # penalty above 0.8 W/mm²

    # --- Heterogeneous process cost ---
    if process_assignment is None:
        # Auto-assign: chiplets with mostly I/O modules → 28nm, else → 5nm
        process_assignment = []
        for cid in range(num_chiplets):
            modules_in_chiplet = [n for n in G.nodes if assignment[n] == cid]
            io_ratio = sum(1 for n in modules_in_chiplet
                           if G.nodes[n]['preferred_process'] >= 28) / max(1, len(modules_in_chiplet))
            process_assignment.append(28 if io_ratio > 0.5 else 5)

    wafer_costs = {5: 17000, 7: 10000, 28: 3000}
    total_cost = 0
    for cid in range(num_chiplets):
        area = chiplet_area[cid]
        if area <= 0:
            continue
        pn = process_assignment[cid]
        wc = wafer_costs.get(pn, 17000)
        # Simplified yield model
        y = max(0.1, ((1 - np.exp(-0.001 * area)) / (0.001 * area + 1e-8)) ** 2)
        dpw = max(1, int(np.pi * 150**2 / area * 0.9))
        die_cost = wc / (dpw * y) + 10
        total_cost += die_cost

    # Process affinity: penalize compute on slow process
    process_affinity = 0
    for n in G.nodes:
        cid = assignment[n]
        pref = G.nodes[n]['preferred_process']
        if pref > 0 and process_assignment[cid] > pref:
            process_affinity += G.nodes[n]['compute']

    affinity_score = max(0, 1.0 - process_affinity / 50.0)

    # Hetero cost score (lower cost = better)
    mono_cost = sum(wafer_costs[5] / max(1, int(np.pi * 150**2 / (sum(chiplet_area)/num_chiplets) * 0.9) * 0.6) + 10
                    for _ in range(num_chiplets))
    cost_saving = max(0, 1.0 - total_cost / max(1, mono_cost))

    # --- Weighted multi-objective ---
    comm_score = 1.0 - base['comm_ratio']
    balance_score = base['balance_score']

    total = (4.0 * comm_score
             + 2.0 * balance_score
             + 2.0 * thermal_score
             + 1.5 * affinity_score
             + 1.0 * cost_saving)

    return {
        **base,
        'comm_score_v2': comm_score,
        'thermal_score': thermal_score,
        'affinity_score': affinity_score,
        'cost_saving': cost_saving,
        'hetero_cost': total_cost,
        'max_power_density_v2': max_pd,
        'process_assignment': process_assignment,
        'multi_obj_total': total,
    }


# ============================================================
# Swap-based RL environment (refinement, not from scratch)
# ============================================================

class SwapRefinementEnv:
    """
    RL environment for partition REFINEMENT via module swaps.

    Start from Spectral partition, then RL proposes swaps.
    Action: (module_id, target_chiplet) encoded as single int.
    """

    def __init__(self, G, num_chiplets, initial_partition, max_swaps=50):
        self.G = G
        self.K = num_chiplets
        self.N = G.number_of_nodes()
        self.initial_partition = initial_partition.copy()
        self.max_swaps = max_swaps

        self.node_features = get_node_features(G)
        self.bw_matrix = get_edge_bandwidth_matrix(G)

        # Action: which module to move to which chiplet
        # Encoded as: action = module_id * K + target_chiplet
        self.n_actions = self.N * self.K

        # Observation: per-chiplet stats + global metrics
        self.obs_dim = self.K * 5 + 3  # 5 stats per chiplet + 3 global

    def reset(self):
        self.assignment = self.initial_partition.copy()
        self.step_count = 0
        # Pre-compute cached metrics
        self._compute_cached_metrics()
        self.best_score = self._score()
        return self._get_obs()

    def _compute_cached_metrics(self):
        """Compute all metrics from scratch (called on reset)."""
        self._total_bw = 0.0
        self._inter_bw = 0.0
        for i in range(self.N):
            for j in range(i+1, self.N):
                bw = self.bw_matrix[i][j]
                if bw > 0:
                    self._total_bw += bw
                    if self.assignment[i] != self.assignment[j]:
                        self._inter_bw += bw

        self._chiplet_stats = np.zeros((self.K, 4))  # area, power, compute, count
        for n in range(self.N):
            cid = self.assignment[n]
            self._chiplet_stats[cid][0] += self.node_features[n][0]  # area
            self._chiplet_stats[cid][1] += self.node_features[n][1]  # power
            self._chiplet_stats[cid][2] += self.node_features[n][2]  # compute
            self._chiplet_stats[cid][3] += 1

    def _update_cached_on_swap(self, module_id, old_cid, new_cid):
        """Incrementally update cached metrics after a swap. O(N) instead of O(N²)."""
        # Update inter-chiplet BW
        for j in range(self.N):
            if j == module_id:
                continue
            bw = self.bw_matrix[module_id][j]
            if bw <= 0:
                continue
            j_cid = self.assignment[j]
            # Before swap: was module in old_cid
            was_inter = (old_cid != j_cid)
            # After swap: module now in new_cid
            is_inter = (new_cid != j_cid)
            if was_inter and not is_inter:
                self._inter_bw -= bw
            elif not was_inter and is_inter:
                self._inter_bw += bw

        # Update chiplet stats
        nf = self.node_features[module_id]
        for i in range(4):
            self._chiplet_stats[old_cid][i] -= nf[i] if i < 3 else 1
            self._chiplet_stats[new_cid][i] += nf[i] if i < 3 else 1

    def _score(self):
        cr = self._inter_bw / (self._total_bw + 1e-8)
        counts = self._chiplet_stats[:, 3]
        active_counts = counts[counts > 0]
        bal = 1.0 - np.std(active_counts) / (np.mean(active_counts) + 1e-8) if len(active_counts) > 1 else 0
        return 4.0 * (1 - cr) + 2.0 * max(0, bal) + 2.0

    def _get_obs(self):
        obs = np.zeros(self.obs_dim, dtype=np.float32)
        cr = self._inter_bw / (self._total_bw + 1e-8)
        for cid in range(self.K):
            obs[cid*5 + 0] = self._chiplet_stats[cid][0] / 50.0
            obs[cid*5 + 1] = self._chiplet_stats[cid][1] / 30.0
            obs[cid*5 + 2] = self._chiplet_stats[cid][2] / 50.0
            obs[cid*5 + 3] = self._chiplet_stats[cid][3] / self.N
            obs[cid*5 + 4] = cr  # global comm ratio as proxy

        counts = self._chiplet_stats[:, 3]
        obs[self.K*5 + 0] = cr
        obs[self.K*5 + 1] = np.std(counts) / (np.mean(counts) + 1e-8)
        obs[self.K*5 + 2] = self.step_count / self.max_swaps
        return obs

    def step(self, action):
        """Execute a swap."""
        module_id = action // self.K
        target_chiplet = action % self.K

        # Constraint solver: reject if it violates balance
        old_chiplet = self.assignment[module_id]
        if old_chiplet == target_chiplet:
            # No-op
            self.step_count += 1
            done = self.step_count >= self.max_swaps
            return self._get_obs(), -0.01, done  # small penalty for no-op

        # Check capacity
        max_cap = int(np.ceil(self.N / self.K * 1.5))
        min_cap = max(1, int(np.floor(self.N / self.K * 0.5)))
        count_target = np.sum(self.assignment == target_chiplet)
        count_source = np.sum(self.assignment == old_chiplet)

        if count_target >= max_cap or count_source <= min_cap:
            # Reject swap
            self.step_count += 1
            done = self.step_count >= self.max_swaps
            return self._get_obs(), -0.02, done

        # Execute swap with incremental update
        self._update_cached_on_swap(module_id, old_chiplet, target_chiplet)
        self.assignment[module_id] = target_chiplet

        new_score = self._score()
        improvement = new_score - self.best_score
        if new_score > self.best_score:
            self.best_score = new_score

        reward = improvement  # positive if improved, negative if worsened

        self.step_count += 1
        done = self.step_count >= self.max_swaps

        return self._get_obs(), reward, done

    def get_final_metrics(self):
        return multi_objective_score(self.G, self.assignment, self.K)


# ============================================================
# Policy
# ============================================================

class SwapPolicy(nn.Module):
    def __init__(self, obs_dim, n_actions, hidden=64):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(obs_dim, hidden), nn.ReLU(),
            nn.Linear(hidden, n_actions),
        )

    def forward(self, x):
        logits = self.net(x)
        return F.softmax(logits, dim=-1)


# ============================================================
# Training
# ============================================================

def train_swap_rl(env, n_episodes=3000, lr=1e-3, gamma=0.99):
    policy = SwapPolicy(env.obs_dim, env.n_actions)
    optimizer = torch.optim.Adam(policy.parameters(), lr=lr)

    reward_history = []
    best_metrics = None
    best_total = -np.inf

    for ep in range(n_episodes):
        obs = env.reset()
        log_probs = []
        rewards = []
        done = False

        while not done:
            obs_t = torch.FloatTensor(obs).unsqueeze(0)
            probs = policy(obs_t).squeeze()
            dist = torch.distributions.Categorical(probs)
            action = dist.sample()
            log_probs.append(dist.log_prob(action))

            obs, reward, done = env.step(action.item())
            rewards.append(reward)

        total_reward = sum(rewards)
        reward_history.append(total_reward)

        metrics = env.get_final_metrics()
        if metrics['multi_obj_total'] > best_total:
            best_total = metrics['multi_obj_total']
            best_metrics = metrics

        # REINFORCE (vectorized)
        returns = []
        G_t = 0
        for r in reversed(rewards):
            G_t = r + gamma * G_t
            returns.insert(0, G_t)
        returns = torch.FloatTensor(returns)
        if len(returns) > 1:
            returns = (returns - returns.mean()) / (returns.std() + 1e-8)

        log_probs_t = torch.stack(log_probs)
        loss = -(log_probs_t * returns).sum()

        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(policy.parameters(), 1.0)
        optimizer.step()

    return reward_history, best_metrics, policy


# ============================================================
# Baselines
# ============================================================

def spectral_partition(G, k):
    from sklearn.cluster import SpectralClustering
    bw = get_edge_bandwidth_matrix(G)
    return SpectralClustering(n_clusters=k, affinity='precomputed',
                              random_state=42).fit_predict(bw + 1e-6)


def random_partition(G, k):
    return np.random.default_rng(42).integers(0, k, size=G.number_of_nodes())


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
        bonus = np.maximum(0, idx/k - count) * 10.0
        assignment[nid] = int(np.argmax(bw_to + bonus))
    return assignment


# ============================================================
# Main
# ============================================================

def main():
    K = 4
    G = create_transformer_accelerator_netlist()

    print("=" * 75)
    print("  Chiplet Partitioning v2: Spectral Init + RL Refinement")
    print("  Multi-Objective: Comm + Balance + Thermal + Hetero Cost")
    print("=" * 75)
    print(f"\n{netlist_summary(G)}")

    # --- Baselines with multi-objective score ---
    print("\n--- Multi-Objective Baselines ---")
    baselines = {
        'Random': random_partition(G, K),
        'Greedy-BW': greedy_bw_partition(G, K),
        'Spectral': spectral_partition(G, K),
        'Ground Truth': get_ground_truth_partition(G),
    }

    all_results = {}
    print(f"\n{'Method':<18} {'Comm':>6} {'Bal':>6} {'Therm':>6} {'Affin':>6} "
          f"{'Cost$':>6} {'TOTAL':>7}")
    print("-" * 60)

    for name, asgn in baselines.items():
        m = multi_objective_score(G, asgn, K)
        all_results[name] = m
        print(f"{name:<18} {m['comm_score_v2']:>5.2f} {m['balance_score']:>5.2f} "
              f"{m['thermal_score']:>5.2f} {m['affinity_score']:>5.2f} "
              f"${m['hetero_cost']:>4.0f} {m['multi_obj_total']:>7.2f}")

    # --- RL Refinement from Spectral ---
    print(f"\n--- RL Refinement (Spectral init, 3000 swap episodes) ---")

    spectral_init = spectral_partition(G, K)
    env = SwapRefinementEnv(G, K, spectral_init, max_swaps=20)

    t0 = time.time()
    history, best_rl, policy = train_swap_rl(env, n_episodes=1000, lr=3e-3)
    t_train = time.time() - t0
    print(f"  Training time: {t_train:.0f}s")

    all_results['RL+Spectral'] = best_rl

    # Evaluate deterministic
    eval_results = []
    for _ in range(30):
        obs = env.reset()
        done = False
        while not done:
            with torch.no_grad():
                probs = policy(torch.FloatTensor(obs).unsqueeze(0)).squeeze()
            action = probs.argmax().item()
            obs, _, done = env.step(action)
        eval_results.append(env.get_final_metrics())

    avg_rl = {}
    for key in eval_results[0]:
        vals = [r[key] for r in eval_results if isinstance(r.get(key), (int, float))]
        if vals:
            avg_rl[key] = np.mean(vals)
    all_results['RL+Spectral(avg)'] = avg_rl

    # --- Final comparison ---
    print(f"\n{'='*75}")
    print("  FINAL MULTI-OBJECTIVE RANKING")
    print(f"{'='*75}")
    print(f"  Score = 4×Comm + 2×Balance + 2×Thermal + 1.5×Affinity + 1×CostSaving")

    print(f"\n{'Rank':>4} {'Method':<20} {'Comm':>6} {'Bal':>6} {'Therm':>6} "
          f"{'Affin':>6} {'TOTAL':>7} {'vs Best':>8}")
    print("-" * 70)

    sorted_r = sorted(all_results.items(), key=lambda x: x[1].get('multi_obj_total', 0),
                       reverse=True)
    best = sorted_r[0][1]['multi_obj_total']

    for rank, (name, m) in enumerate(sorted_r, 1):
        total = m.get('multi_obj_total', 0)
        marker = " ★" if rank == 1 else ""
        print(f"{rank:>4} {name:<20} {m.get('comm_score_v2',0):>5.2f} "
              f"{m.get('balance_score',0):>5.2f} {m.get('thermal_score',0):>5.2f} "
              f"{m.get('affinity_score',0):>5.2f} {total:>7.2f} "
              f"{total/best*100:>7.1f}%{marker}")

    # Check if RL beat Spectral
    spectral_score = all_results['Spectral']['multi_obj_total']
    rl_best_score = best_rl['multi_obj_total']
    rl_avg_score = avg_rl.get('multi_obj_total', 0)

    print(f"\n  Key comparison:")
    print(f"    Spectral:        {spectral_score:.2f}")
    print(f"    RL+Spectral best:{rl_best_score:.2f} ({(rl_best_score/spectral_score-1)*100:+.1f}%)")
    print(f"    RL+Spectral avg: {rl_avg_score:.2f} ({(rl_avg_score/spectral_score-1)*100:+.1f}%)")

    if rl_best_score > spectral_score:
        print(f"\n  ★ RL BEATS SPECTRAL by {(rl_best_score/spectral_score-1)*100:.1f}% (best)")
    if rl_avg_score > spectral_score:
        print(f"  ★ RL BEATS SPECTRAL by {(rl_avg_score/spectral_score-1)*100:.1f}% (avg)")

    # --- Plot ---
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(1, 3, figsize=(20, 6))
        fig.suptitle('Chiplet Partitioning v2: Multi-Objective RL Refinement',
                     fontsize=14, fontweight='bold')

        # Training curve
        ax = axes[0]
        w = 50
        if len(history) > w:
            sm = np.convolve(history, np.ones(w)/w, 'valid')
            ax.plot(sm, color='#FF9800', linewidth=2)
        ax.plot(history, alpha=0.15, color='#FF9800')
        ax.set_xlabel('Episode'); ax.set_ylabel('Episode Reward (improvement)')
        ax.set_title('RL Refinement Training Curve')
        ax.grid(True, alpha=0.3)
        ax.axhline(y=0, color='gray', linestyle='--', alpha=0.5)

        # Multi-objective bar
        ax = axes[1]
        show = ['Random', 'Greedy-BW', 'Spectral', 'Ground Truth', 'RL+Spectral(avg)']
        show_data = [(n, all_results[n]) for n in show if n in all_results]

        names = [n for n, _ in show_data]
        totals = [d['multi_obj_total'] for _, d in show_data]
        colors = ['#FF9800' if 'RL' in n else '#4CAF50' if 'Ground' in n else '#2196F3' for n in names]
        bars = ax.barh(range(len(names)), totals, color=colors)
        ax.set_yticks(range(len(names))); ax.set_yticklabels(names, fontsize=9)
        ax.set_xlabel('Multi-Objective Score'); ax.set_title('Partition Quality')
        for b, v in zip(bars, totals):
            ax.text(v+0.02, b.get_y()+b.get_height()/2, f'{v:.2f}', va='center', fontsize=9)
        ax.grid(True, alpha=0.3, axis='x')

        # Radar chart (multi-objective breakdown)
        ax = axes[2]
        categories = ['Comm', 'Balance', 'Thermal', 'Affinity']
        show_radar = ['Spectral', 'RL+Spectral(avg)', 'Ground Truth']
        angles = np.linspace(0, 2*np.pi, len(categories), endpoint=False).tolist()
        angles += angles[:1]

        for name in show_radar:
            if name not in all_results:
                continue
            m = all_results[name]
            values = [m.get('comm_score_v2', 0), m.get('balance_score', 0),
                      m.get('thermal_score', 0), m.get('affinity_score', 0)]
            values += values[:1]
            color = '#FF9800' if 'RL' in name else '#4CAF50' if 'Ground' in name else '#2196F3'
            ax.plot(angles, values, 'o-', label=name, linewidth=2, color=color)
            ax.fill(angles, values, alpha=0.1, color=color)

        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories, fontsize=9)
        ax.set_ylim(0, 1.1)
        ax.set_title('Multi-Objective Breakdown')
        ax.legend(fontsize=8, loc='lower right')
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        out = Path(__file__).parent / "results" / "v2_multi_objective.png"
        plt.savefig(out, dpi=150, bbox_inches='tight')
        print(f"\nPlot: {out}")
        plt.close()
    except Exception as e:
        print(f"Plot error: {e}")

    # Save
    save = {name: {k: v for k, v in m.items() if isinstance(v, (int, float, str, list))}
            for name, m in all_results.items()}
    out_json = Path(__file__).parent / "results" / "v2_results.json"
    with open(out_json, 'w') as f:
        json.dump(save, f, indent=2, default=str)
    print(f"Results: {out_json}")


if __name__ == "__main__":
    main()
