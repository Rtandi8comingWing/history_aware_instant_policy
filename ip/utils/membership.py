"""
Membership Calculator: 计算 Track <-> Geometry 节点的 Soft Overlap

实现 RBF 软重叠分数：
s_ij = exp(- ||p_i - q_j||^2 / (2 * sigma^2))

其中：
- p_i: 第 i 个 geometry 采样点
- q_j: 第 j 个 track 对象的末帧最近邻点
"""
import numpy as np
from typing import Optional


def rbf_soft_overlap(
    geo_points: np.ndarray,           # [M, 3]
    track_last_points: np.ndarray,    # [N, P, 3]
    sigma: float = 0.05
) -> np.ndarray:
    """
    计算 geometry 点到每个 track 对象末帧的 RBF 密度

    Args:
        geo_points: [M, 3] 几何采样点
        track_last_points: [N, P, 3] N 个对象，每个 P 个关键点的末帧位置
        sigma: RBF 带宽参数

    Returns:
        overlap_scores: [N, M]，每个对象-几何点对的分数 [0,1]
    """
    M = geo_points.shape[0]
    N = track_last_points.shape[0]

    # 对每个 track 对象，找到其末帧的点集
    # track_last_points 已经是 [N, P, 3]

    overlap_scores = np.zeros((N, M), dtype=np.float32)

    for n in range(N):
        obj_points = track_last_points[n]  # [P, 3]

        # 计算 geometry 点到该对象所有点的距离矩阵
        # dist[i, j] = ||geo_points[i] - obj_points[j]||
        # 使用广播: [M,1,3] - [1,P,3] -> [M,P]
        dist_matrix = np.linalg.norm(
            geo_points[:, None, :] - obj_points[None, :, :],
            axis=2
        )  # [M, P]

        # 取最近距离
        min_dist = dist_matrix.min(axis=1)  # [M]

        # RBF 核
        score = np.exp(- (min_dist ** 2) / (2 * sigma ** 2))

        overlap_scores[n] = score

    return overlap_scores


def rbf_soft_overlap_batch(
    geo_points_batch: np.ndarray,         # [B, M, 3]
    track_last_points_batch: np.ndarray,  # [B, N, P, 3]
    sigma: float = 0.05
) -> np.ndarray:
    """
    Batch 版本

    Returns:
        overlap_batch: [B, N, M]
    """
    B = geo_points_batch.shape[0]
    overlap_batch = np.zeros_like(geo_points_batch[:, None, :])

    for b in range(B):
        overlap_batch[b] = rbf_soft_overlap(
            geo_points_batch[b],
            track_last_points_batch[b],
            sigma=sigma
        )

    return overlap_batch


def compute_track_to_geo_edge_attr(
    geo_points: np.ndarray,           # [M, 3]
    track_points: np.ndarray,        # [N, P, 3] 或 [N, H, P, 3] 取末帧
    geo_pos_emb_dim: int = 64,
    sigma: float = 0.05,
    normalize: bool = True
) -> np.ndarray:
    """
    构建 Track -> Geometry 边的属性（含 soft overlap）

    Args:
        geo_points: [M, 3]
        track_points: [N, P, 3] 或 [N, H, P, 3]
        geo_pos_emb_dim: 位置编码维度（如果需要）
        sigma: RBF 参数
        normalize: 是否归一化到 [0,1]

    Returns:
        edge_attr: [E, D] 其中 E = N * M
    """
    # 取末帧
    if track_points.ndim == 3:
        track_last = track_points[:, :, :]  # [N, P, 3]
    else:
        track_last = track_points[:, -1, :, :]  # [N, P, 3]

    # 计算 overlap
    overlap = rbf_soft_overlap(geo_points, track_last, sigma)  # [N, M]

    if normalize:
        overlap = np.clip(overlap, 0, 1)

    # 构建边属性
    N, M = overlap.shape
    edge_attrs = []

    for n in range(N):
        for m in range(M):
            # 相对位置编码（简化版：直接用 overlap 作为特征）
            edge_attr = np.zeros(geo_pos_emb_dim + 1, dtype=np.float32)
            edge_attr[-1] = overlap[n, m]  # 最后一维是 overlap
            edge_attrs.append(edge_attr)

    return np.stack(edge_attrs, axis=0)


# ============================================================================
# 测试
# ============================================================================
if __name__ == '__main__':
    np.random.seed(42)

    # 模拟数据
    M = 16  # geometry nodes
    N = 3   # tracks
    P = 5   # points per object

    geo_points = np.random.randn(M, 3).astype(np.float32) * 0.1
    track_points = np.random.randn(N, P, 3).astype(np.float32) * 0.1

    # 计算 overlap
    overlap = rbf_soft_overlap(geo_points, track_points, sigma=0.05)

    print("geo_points shape:", geo_points.shape)
    print("track_points shape:", track_points.shape)
    print("overlap shape:", overlap.shape)
    print("overlap sample:\n", overlap[:2, :5])

    # 测试 edge attr
    edge_attr = compute_track_to_geo_edge_attr(geo_points, track_points)
    print("edge_attr shape:", edge_attr.shape)

    print("\n✓ membership.py basic test passed")
