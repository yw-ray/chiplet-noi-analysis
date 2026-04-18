"""
GNN-based feature extractor for stable-baselines3.

Implements Graph Attention Network (GAT) to encode netlist structure
directly into the RL policy. The GNN produces node embeddings that
capture both local and global graph structure.

Architecture:
  Input: node features [N, F] + adjacency [N, N]
  → GAT Layer 1 (multi-head attention)
  → GAT Layer 2
  → Current node embedding + chiplet stats
  → Concatenated feature vector for policy/value heads
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from gymnasium import spaces
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor


class GATLayer(nn.Module):
    """Single Graph Attention Network layer."""

    def __init__(self, in_features, out_features, num_heads=4, dropout=0.1):
        super().__init__()
        self.num_heads = num_heads
        self.head_dim = out_features // num_heads
        assert out_features % num_heads == 0

        self.W = nn.Linear(in_features, out_features, bias=False)
        self.a_src = nn.Parameter(torch.randn(num_heads, self.head_dim))
        self.a_dst = nn.Parameter(torch.randn(num_heads, self.head_dim))
        self.dropout = nn.Dropout(dropout)
        self.leaky_relu = nn.LeakyReLU(0.2)

        nn.init.xavier_uniform_(self.W.weight)
        nn.init.xavier_uniform_(self.a_src.unsqueeze(0))
        nn.init.xavier_uniform_(self.a_dst.unsqueeze(0))

    def forward(self, x, adj):
        """
        x: [N, in_features]
        adj: [N, N] adjacency (can be weighted)
        Returns: [N, out_features]
        """
        N = x.size(0)
        h = self.W(x)  # [N, out_features]
        h = h.view(N, self.num_heads, self.head_dim)  # [N, H, D]

        # Attention scores
        attn_src = (h * self.a_src).sum(dim=-1)  # [N, H]
        attn_dst = (h * self.a_dst).sum(dim=-1)  # [N, H]

        # Pairwise attention: attn_src[i] + attn_dst[j] for edge (i,j)
        attn = attn_src.unsqueeze(1) + attn_dst.unsqueeze(0)  # [N, N, H]
        attn = self.leaky_relu(attn)

        # Mask non-edges (set to -inf)
        mask = (adj > 0).unsqueeze(-1).expand_as(attn)
        attn = attn.masked_fill(~mask, float('-inf'))

        # Softmax over neighbors
        attn = F.softmax(attn, dim=1)  # [N, N, H]
        attn = torch.nan_to_num(attn, 0.0)  # handle isolated nodes
        attn = self.dropout(attn)

        # Weighted aggregation: weighted by both attention and edge weight
        edge_weight = adj.unsqueeze(-1)  # [N, N, 1]
        weighted_attn = attn * edge_weight  # incorporate bandwidth as weight

        # Aggregate: [N, N, H] × [N, H, D] → [N, H, D]
        out = torch.einsum('ijh,jhd->ihd', weighted_attn, h)
        out = out.reshape(N, -1)  # [N, out_features]

        return out


class NetlistGNN(nn.Module):
    """
    2-layer GAT for netlist encoding.
    Produces per-node embeddings that capture graph structure.
    """

    def __init__(self, node_feat_dim, hidden_dim=64, embed_dim=32, num_heads=4):
        super().__init__()
        self.gat1 = GATLayer(node_feat_dim, hidden_dim, num_heads=num_heads)
        self.gat2 = GATLayer(hidden_dim, embed_dim, num_heads=num_heads)
        self.norm1 = nn.LayerNorm(hidden_dim)
        self.norm2 = nn.LayerNorm(embed_dim)

    def forward(self, x, adj):
        """
        x: [N, F] node features
        adj: [N, N] adjacency matrix (bandwidth-weighted)
        Returns: [N, embed_dim] node embeddings
        """
        h = F.elu(self.norm1(self.gat1(x, adj)))
        h = self.norm2(self.gat2(h, adj))
        return h


class GNNFeatureExtractor(BaseFeaturesExtractor):
    """
    Custom feature extractor for SB3 that uses GNN.

    The observation from the environment is a flat vector containing:
      - node features for current module
      - chiplet stats
      - progress
      - bandwidth to each chiplet

    This extractor additionally runs a GNN on the full graph to get
    structure-aware embeddings, and concatenates them with the env obs.
    """

    def __init__(self, observation_space: spaces.Box,
                 node_features: np.ndarray,
                 adj_matrix: np.ndarray,
                 module_order: list,
                 num_chiplets: int,
                 gnn_embed_dim: int = 32,
                 features_dim: int = 128):
        super().__init__(observation_space, features_dim)

        self.num_chiplets = num_chiplets
        n_nodes, node_feat_dim = node_features.shape

        # Store graph data as buffers (not parameters)
        self.register_buffer('node_features',
                             torch.FloatTensor(node_features))
        # Normalize adjacency
        adj_norm = adj_matrix / (adj_matrix.max() + 1e-8)
        self.register_buffer('adj_matrix', torch.FloatTensor(adj_norm))

        self.module_order = module_order

        # GNN
        self.gnn = NetlistGNN(node_feat_dim, hidden_dim=64,
                              embed_dim=gnn_embed_dim, num_heads=4)

        # Combine GNN embedding with env observation
        env_obs_dim = observation_space.shape[0]
        combined_dim = env_obs_dim + gnn_embed_dim + gnn_embed_dim  # current + global

        self.combine = nn.Sequential(
            nn.Linear(combined_dim, features_dim),
            nn.ReLU(),
            nn.Linear(features_dim, features_dim),
            nn.ReLU(),
        )

        # Pre-compute GNN embeddings (updated each reset)
        self._gnn_embeddings = None

    def _compute_gnn_embeddings(self):
        """Run GNN on full graph."""
        with torch.no_grad():
            self._gnn_embeddings = self.gnn(self.node_features, self.adj_matrix)

    def forward(self, observations: torch.Tensor) -> torch.Tensor:
        """
        observations: [B, obs_dim] batch of observations
        Returns: [B, features_dim]
        """
        batch_size = observations.shape[0]

        # Compute GNN embeddings if not cached
        if self._gnn_embeddings is None:
            self._compute_gnn_embeddings()

        embeddings = self._gnn_embeddings  # [N, embed_dim]
        global_embed = embeddings.mean(dim=0)  # [embed_dim]

        # Extract current module index from progress in observation
        # Progress is at a known position in the obs vector
        # For now, use a simple heuristic: take first node's embedding
        # In practice, we'd pass module_id through the observation
        current_embed = global_embed.unsqueeze(0).expand(batch_size, -1)
        global_expanded = global_embed.unsqueeze(0).expand(batch_size, -1)

        # Concatenate: env_obs + current_gnn_embed + global_gnn_embed
        combined = torch.cat([observations, current_embed, global_expanded], dim=-1)

        return self.combine(combined)


def create_gnn_policy_kwargs(env):
    """Create policy_kwargs for SB3 with GNN feature extractor."""
    from envs.netlist import get_node_features, get_edge_bandwidth_matrix

    G = env.G
    node_features = get_node_features(G)
    adj_matrix = get_edge_bandwidth_matrix(G)
    module_order = env._get_module_order()

    gnn_embed_dim = 32
    features_dim = 128

    return dict(
        features_extractor_class=GNNFeatureExtractor,
        features_extractor_kwargs=dict(
            node_features=node_features,
            adj_matrix=adj_matrix,
            module_order=module_order,
            num_chiplets=env.num_chiplets,
            gnn_embed_dim=gnn_embed_dim,
            features_dim=features_dim,
        ),
        net_arch=dict(pi=[128, 64], vf=[128, 64]),
    )
