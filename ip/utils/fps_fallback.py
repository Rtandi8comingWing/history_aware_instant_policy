"""
Simple FPS (Farthest Point Sampling) fallback implementation
当 torch-cluster 不可用时使用
"""
import torch


def fps_fallback(pos, batch, ratio=0.5, random_start=True):
    """
    简单的 FPS 实现，当 torch-cluster 不可用时使用

    Args:
        pos: [N, 3] 点坐标
        batch: [N] batch 索引
        ratio: 采样比例
        random_start: 是否随机起始点

    Returns:
        idx: 采样点的索引
    """
    device = pos.device
    batch_size = batch.max().item() + 1

    all_indices = []

    for b in range(batch_size):
        mask = batch == b
        batch_pos = pos[mask]
        n_points = batch_pos.shape[0]
        n_sample = max(1, int(n_points * ratio))

        if n_sample >= n_points:
            # 如果采样数量大于等于总点数，返回所有点
            batch_indices = torch.where(mask)[0]
        else:
            # 简单的均匀采样作为FPS的近似
            step = n_points // n_sample
            if random_start:
                start = torch.randint(0, step, (1,)).item()
            else:
                start = 0

            sample_indices = torch.arange(start, n_points, step, device=device)[:n_sample]
            batch_indices = torch.where(mask)[0][sample_indices]

        all_indices.append(batch_indices)

    return torch.cat(all_indices)


def nearest_fallback(x, y, batch_x, batch_y):
    """
    简单的最近邻实现

    Args:
        x: [N, 3] 查询点
        y: [M, 3] 目标点
        batch_x: [N] 查询点batch索引
        batch_y: [M] 目标点batch索引

    Returns:
        idx: [N] 每个查询点对应的最近目标点索引
    """
    device = x.device
    batch_size = batch_x.max().item() + 1

    all_indices = []

    for b in range(batch_size):
        mask_x = batch_x == b
        mask_y = batch_y == b

        batch_x_pos = x[mask_x]  # [Nx, 3]
        batch_y_pos = y[mask_y]  # [Ny, 3]

        if batch_y_pos.shape[0] == 0:
            # 如果没有目标点，使用0索引
            batch_indices = torch.zeros(batch_x_pos.shape[0], dtype=torch.long, device=device)
        else:
            # 计算距离矩阵 [Nx, Ny]
            dist = torch.cdist(batch_x_pos, batch_y_pos)
            # 找到最近点索引
            nearest_idx = dist.argmin(dim=1)  # [Nx]
            # 转换为全局索引
            y_global_indices = torch.where(mask_y)[0]
            batch_indices = y_global_indices[nearest_idx]

        all_indices.append(batch_indices)

    return torch.cat(all_indices)