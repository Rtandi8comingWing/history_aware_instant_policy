"""
Track Builder: 从对象状态序列构建对象级历史点轨迹
将世界坐标系下的对象轨迹投影到当前 EE 坐标系

核心功能：
1. build_object_tracks_world: 从 objects_state_seq 构建原始轨迹
2. project_tracks_to_current_ee: 坐标变换到当前 EE frame
3. compute_track_age_seconds: 计算 track 年龄（秒）
"""
import numpy as np
from typing import List, Dict, Optional, Tuple


# 每个对象在局部坐标系下的 canonical 关键点（用于 track 可视化）
# 形状：[P, 3]，P=5 个点，均匀分布在立方体角点+中心
DEFAULT_CANONICAL_POINTS = np.array([
    [0.0, 0.0, 0.0],      # 中心
    [0.05, 0.0, 0.0],     # +x
    [-0.05, 0.0, 0.0],    # -x
    [0.0, 0.05, 0.0],     # +y
    [0.0, 0.0, 0.05],     # +z
], dtype=np.float32)


def build_object_tracks_world(
    objects_state_seq: List[Dict],
    points_per_obj: int = 5,
    n_max: int = 5,
    history_len: int = 16,
    canonical_points: Optional[np.ndarray] = None
) -> Dict[str, np.ndarray]:
    """
    从对象状态序列构建世界坐标系下的对象轨迹

    Args:
        objects_state_seq: List[Dict]，每帧的对象状态
            每个 Dict: {
                'object_poses': List[np.ndarray],  # [N, 4,4] 世界位姿
                'object_ids': List[int],           # 对象 ID
                'timestamp': float                 # 秒
            }
        points_per_obj: 每个对象的关键点数
        n_max: 最大对象数（padding 上限）
        history_len: 历史帧数
        canonical_points: [P,3] 对象局部关键点，默认用 DEFAULT_CANONICAL_POINTS

    Returns:
        tracks_world: [Nmax, H, P, 3] 世界坐标下的点轨迹
        track_valid: [Nmax] bool，有效对象 mask
        track_timestamps: [Nmax, H] 每帧的时间戳
    """
    if canonical_points is None:
        canonical_points = DEFAULT_CANONICAL_POINTS
    P = canonical_points.shape[0]

    num_frames = len(objects_state_seq)
    H = min(history_len, num_frames)  # 实际历史长度

    # 初始化输出
    tracks_world = np.zeros((n_max, history_len, P, 3), dtype=np.float32)
    track_valid = np.zeros(n_max, dtype=np.bool_)
    track_timestamps = np.full((n_max, history_len), -1.0, dtype=np.float32)

    # 获取本 episode 中的所有对象（假设全局 ID 在整个序列中一致）
    all_object_ids = set()
    for state in objects_state_seq:
        all_object_ids.update(state.get('object_ids', []))

    all_object_ids = sorted(list(all_object_ids))[:n_max]
    obj_id_to_idx = {oid: idx for idx, oid in enumerate(all_object_ids)}

    # 对每个对象构建轨迹
    for obj_idx, obj_id in enumerate(all_object_ids):
        # 收集该对象在每一帧的 canonical 点世界坐标
        obj_track = []

        # 从最新帧往回采样 history_len 帧
        frame_indices = list(range(num_frames - 1, -1, -1))[:history_len][::-1]  # 从旧到新
        for frame_idx in frame_indices:
            state = objects_state_seq[frame_idx]
            obj_poses = state.get('object_poses', [])
            frame_obj_ids = state.get('object_ids', [])

            if obj_id in frame_obj_ids:
                pose_idx = frame_obj_ids.index(obj_id)
                T_w_o = obj_poses[pose_idx]  # [4,4] world-to-object

                # 将 canonical 点变换到世界坐标
                # p_world = T_w_o @ [p_local, 1]
                local_hom = np.concatenate([canonical_points, np.ones((P, 1))], axis=1).T  # [4, P]
                world_hom = T_w_o @ local_hom  # [4, P]
                world_points = world_hom[:3, :].T  # [P, 3]
                obj_track.append(world_points)
            else:
                # 对象不在当前帧，用前一帧或 padding
                if len(obj_track) > 0:
                    obj_track.append(obj_track[-1].copy())
                else:
                    obj_track.append(np.zeros((P, 3), dtype=np.float32))

        # 存储（注意：已经是从旧到新排列）
        tracks_world[obj_idx, :H] = np.stack(obj_track[:history_len])
        track_valid[obj_idx] = True

        # 时间戳
        for i, frame_idx in enumerate(frame_indices[:history_len]):
            track_timestamps[obj_idx, i] = objects_state_seq[frame_idx].get('timestamp', 0.0)

    return {
        'tracks_world': tracks_world,      # [Nmax, H, P, 3]
        'track_valid': track_valid,        # [Nmax]
        'track_timestamps': track_timestamps,  # [Nmax, H]
    }


def project_tracks_to_current_ee(
    tracks_world: np.ndarray,      # [Nmax, H, P, 3]
    track_valid: np.ndarray,      # [Nmax]
    T_w_e_current: np.ndarray,    # [4,4] current EE pose (world frame)
    T_w_e_history: Optional[np.ndarray] = None  # [H, 4,4] 历史每一帧的 EE pose
) -> np.ndarray:
    """
    将世界坐标系下的轨迹投影到当前 EE 坐标系

    公式: p_ee = T_e_w @ p_world
    其中 T_e_w = inverse(T_w_e_current)

    Args:
        tracks_world: 世界坐标轨迹
        track_valid: 有效 mask
        T_w_e_current: 当前 EE 在世界中的位姿
        T_w_e_history: 可选的历史帧 EE pose，如果提供则每帧投影到对应帧的 EE frame

    Returns:
        tracks_ee: [Nmax, H, P, 3] 当前 EE frame 下的轨迹
    """
    Nmax, H, P, _ = tracks_world.shape
    T_e_w = np.linalg.inv(T_w_e_current)  # [4,4]

    # 如果提供了历史 EE pose，按每帧投影
    if T_w_e_history is not None:
        tracks_ee = np.zeros_like(tracks_world)
        for h in range(H):
            T_e_w_h = np.linalg.inv(T_w_e_history[h])
            # 对所有对象、所有点做变换
            for n in range(Nmax):
                if track_valid[n]:
                    pts = tracks_world[n, h]  # [P, 3]
                    pts_hom = np.concatenate([pts, np.ones((P, 1))], axis=1).T  # [4, P]
                    world_hom = T_w_e_history[h] @ pts_hom  # 先转到世界
                    ee_hom = T_e_w_h @ world_hom
                    tracks_ee[n, h] = ee_hom[:3, :].T
    else:
        # 统一投影到当前 EE frame
        tracks_ee = np.zeros_like(tracks_world)
        for n in range(Nmax):
            if track_valid[n]:
                for h in range(H):
                    pts = tracks_world[n, h]  # [P, 3]
                    pts_hom = np.concatenate([pts, np.ones((P, 1))], axis=1).T  # [4, P]
                    ee_hom = T_e_w @ pts_hom  # [4, P]
                    tracks_ee[n, h] = ee_hom[:3, :].T

    return tracks_ee


def compute_track_age_seconds(
    track_timestamps: np.ndarray,   # [Nmax, H]
    track_valid: np.ndarray,        # [Nmax]
    now_timestamp: float,
    norm_max_sec: float = 2.0
) -> np.ndarray:
    """
    计算每个 track 节点的最后更新年龄（秒）

    Args:
        track_timestamps: 每帧的时间戳
        track_valid: 有效 mask
        now_timestamp: 当前帧时间戳
        norm_max_sec: 归一化最大秒数

    Returns:
        track_age_sec: [Nmax, 1]，归一化到 [0,1]
    """
    Nmax = track_timestamps.shape[0]
    track_age_sec = np.zeros((Nmax, 1), dtype=np.float32)

    for n in range(Nmax):
        if track_valid[n]:
            # 找到最近一次有效更新的时间戳
            valid_ts = track_timestamps[n]
            valid_ts = valid_ts[valid_ts >= 0]
            if len(valid_ts) > 0:
                last_update_ts = valid_ts.max()
                age = now_timestamp - last_update_ts
                age = np.clip(age, 0, norm_max_sec)
                track_age_sec[n, 0] = age / norm_max_sec  # 归一化到 [0,1]
            else:
                track_age_sec[n, 0] = 1.0  # 最老
        else:
            track_age_sec[n, 0] = 1.0  # 无效对象视为最老

    return track_age_sec


def build_demo_tracks(
    demo_objects_state_seq: List[List[Dict]],  # [D, T, state_dict]
    demo_T_w_e: np.ndarray,  # [D, T, 4,4]
    points_per_obj: int = 5,
    n_max: int = 5,
    history_len: int = 16
) -> Dict[str, np.ndarray]:
    """
    为多个 demo 构建轨迹序列

    Args:
        demo_objects_state_seq: [D, T] List of state dicts
        demo_T_w_e: [D, T, 4,4] 每个 demo 每帧的 EE pose
        其他参数同 build_object_tracks_world

    Returns:
        demo_tracks_ee: [D, T, Nmax, H, P, 3]
        demo_track_valid: [D, T, Nmax]
        demo_track_age_sec: [D, T, Nmax, 1]
    """
    D = len(demo_objects_state_seq)
    T = len(demo_objects_state_seq[0])

    demo_tracks_ee = np.zeros((D, T, n_max, history_len, points_per_obj, 3), dtype=np.float32)
    demo_track_valid = np.zeros((D, T, n_max), dtype=np.bool_)
    demo_track_age_sec = np.zeros((D, T, n_max, 1), dtype=np.float32)

    for d in range(D):
        # 对 demo 中的每个时间切片，视为一个"当前帧"
        # 历史从该帧往前追溯
        for t in range(T):
            # 构建从 t 往前 history_len 帧的对象状态子序列
            start_idx = max(0, t - history_len + 1)
            sub_seq = demo_objects_state_seq[d][start_idx:t+1]

            # 如果不足 history_len，左侧 padding
            if len(sub_seq) < history_len:
                # 复制第一帧来 padding
                first_state = demo_objects_state_seq[d][0].copy()
                first_state['timestamp'] = demo_objects_state_seq[d][0].get('timestamp', 0.0)
                sub_seq = [first_state] * (history_len - len(sub_seq)) + sub_seq

            # 当前 EE pose
            T_w_e_current = demo_T_w_e[d, t]

            # 构建世界轨迹
            world_result = build_object_tracks_world(
                sub_seq,
                points_per_obj=points_per_obj,
                n_max=n_max,
                history_len=history_len
            )

            # 投影到当前 EE frame
            tracks_ee = project_tracks_to_current_ee(
                world_result['tracks_world'],
                world_result['track_valid'],
                T_w_e_current
            )

            # 计算 age
            now_ts = sub_seq[-1].get('timestamp', 0.0)
            track_age = compute_track_age_seconds(
                world_result['track_timestamps'],
                world_result['track_valid'],
                now_ts
            )

            demo_tracks_ee[d, t] = tracks_ee
            demo_track_valid[d, t] = world_result['track_valid']
            demo_track_age_sec[d, t, :, 0] = track_age[:, 0]

    return {
        'demo_tracks_ee': demo_tracks_ee,
        'demo_track_valid': demo_track_valid,
        'demo_track_age_sec': demo_track_age_sec
    }


# ============================================================================
# 简单测试
# ============================================================================
if __name__ == '__main__':
    # 模拟数据测试
    np.random.seed(42)

    # 模拟 2 个对象在 20 帧中的运动
    num_frames = 20
    objects_state_seq = []

    for i in range(num_frames):
        # 两个物体做简单直线运动
        obj1_pose = np.eye(4)
        obj1_pose[:3, 3] = [0.1 + i * 0.01, 0.0, 0.05]  # 平移

        obj2_pose = np.eye(4)
        obj2_pose[:3, 3] = [0.2, 0.1 + i * 0.005, 0.05]

        state = {
            'object_poses': [obj1_pose, obj2_pose],
            'object_ids': [0, 1],
            'timestamp': i * 0.1  # 10Hz 采样
        }
        objects_state_seq.append(state)

    # 当前 EE pose
    T_w_e_current = np.eye(4)
    T_w_e_current[:3, 3] = [0.0, 0.0, 0.2]

    # 构建轨迹
    result = build_object_tracks_world(
        objects_state_seq,
        points_per_obj=5,
        n_max=5,
        history_len=16
    )

    print("tracks_world shape:", result['tracks_world'].shape)
    print("track_valid:", result['track_valid'])
    print("track_timestamps (last obj):", result['track_timestamps'][1])

    # 投影到 EE frame
    tracks_ee = project_tracks_to_current_ee(
        result['tracks_world'],
        result['track_valid'],
        T_w_e_current
    )
    print("tracks_ee shape:", tracks_ee.shape)

    # 计算 age
    now_ts = objects_state_seq[-1]['timestamp']
    age = compute_track_age_seconds(
        result['track_timestamps'],
        result['track_valid'],
        now_ts
    )
    print("track_age (normalized):", age)

    print("\n✓ track_builder.py basic test passed")
