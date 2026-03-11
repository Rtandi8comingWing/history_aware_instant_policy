"""
Memory Task Generator: 生成需要历史记忆的任务模板

五类任务（对齐 History-Aware 论文五维）：
1. Counting - 重复操作 K 次后停止
2. Spatial Memorization - 记住初始位置映射
3. Task Stage Identification - 同一视觉状态不同动作
4. Pre-loaded Memory - 预载目标信息，执行时无提示
5. Continuous Memory - 长时间追踪 + 轻度遮挡

每个任务返回：
- pcds: world frame 点云（后续转 EE）
- T_w_es: EE 轨迹
- grips: 夹爪开合
- objects_state_seq: 每帧对象位姿（供 track_builder 使用）
- meta: 任务类型 + 决策点 + 评估标签
"""
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import random


@dataclass
class MemoryTaskMeta:
    """任务元数据（评估用，不进训练 loss）"""
    task_type: str  # counting/spatial/stage/preloaded/continuous
    decision_points: List[int]  # 需要模型做决策的关键帧索引
    decision_labels: List[int]  # 对应决策的正确动作标签
    memory_aspects: List[str]  # 涉及的记忆维度


class MemoryTaskGenerator:
    """
    记忆任务生成器

    Args:
        base_generator: 基础伪演示生成器（复用其物体和场景生成逻辑）
        control_hz: 控制频率 Hz
        track_refresh_hz: track 更新频率 Hz
    """

    def __init__(
        self,
        base_generator=None,
        control_hz: float = 15.0,
        track_refresh_hz: float = 3.0
    ):
        self.base_generator = base_generator
        self.control_hz = control_hz
        self.track_refresh_hz = track_refresh_hz
        self.dt = 1.0 / control_hz

    def sample_task_type(self, stage: int = 1) -> str:
        """
        按课程采样任务类型

        Args:
            stage: 1=基础, 2=中等, 3=高阶
        """
        # 简单实现：均匀采样
        task_types = ['counting', 'spatial', 'stage', 'preloaded', 'continuous']
        return random.choice(task_types)

    def generate_task(
        self,
        objects: List,
        task_type: Optional[str] = None,
        difficulty: int = 1
    ) -> Dict:
        """
        生成单个记忆任务

        Args:
            objects: ShapeNet 对象列表
            task_type: 任务类型，默认随机采样
            difficulty: 难度等级 1-3

        Returns:
            dict 含: pcds, T_w_es, grips, objects_state_seq, meta
        """
        if task_type is None:
            task_type = self.sample_task_type()

        if task_type == 'counting':
            return self._gen_counting_task(objects, difficulty)
        elif task_type == 'spatial':
            return self._gen_spatial_task(objects, difficulty)
        elif task_type == 'stage':
            return self._gen_stage_task(objects, difficulty)
        elif task_type == 'preloaded':
            return self._gen_preloaded_task(objects, difficulty)
        elif task_type == 'continuous':
            return self._gen_continuous_task(objects, difficulty)
        else:
            raise ValueError(f"Unknown task type: {task_type}")

    # ========================================================================
    # 任务模板实现
    # ========================================================================

    def _gen_counting_task(self, objects: List, difficulty: int) -> Dict:
        """
        Counting: 重复操作 K 次后停止

        例如：把两个物体各 press 3 次，然后返回
        """
        # 随机决定重复次数 K
        K = random.randint(2, 3 + difficulty)  # 2-5

        trajectory = []
        objects_state_seq = []
        timestamps = []
        decision_points = []
        decision_labels = []

        # 初始位置
        obj1_init = np.array([0.15, 0.0, 0.05])
        obj2_init = np.array([0.25, 0.0, 0.05])

        current_time = 0.0

        # 每次循环：下压 -> 抬起 -> 回到上方
        for rep in range(K):
            # 下压 phase
            start_pose = np.eye(4)
            start_pose[:3, 3] = obj1_init + np.array([0, 0, 0.1])
            mid_pose = np.eye(4)
            mid_pose[:3, 3] = obj1_init + np.array([0, 0, 0.0])  # 接触物体

            # 记录下压前的决策点
            decision_points.append(len(trajectory))
            decision_labels.append(0)  # 继续下压

            # 插入轨迹段
            seg_traj, seg_objs, seg_ts = self._interpolate_ee_trajectory(
                start_pose, mid_pose, num_steps=10
            )
            trajectory.extend(seg_traj)
            objects_state_seq.extend(seg_objs)
            timestamps.extend(seg_ts)

            # 抬起 phase
            up_pose = np.eye(4)
            up_pose[:3, 3] = obj1_init + np.array([0, 0, 0.15])

            seg_traj, seg_objs, seg_ts = self._interpolate_ee_trajectory(
                mid_pose, up_pose, num_steps=5
            )
            trajectory.extend(seg_traj)
            objects_state_seq.extend(seg_objs)
            timestamps.extend(seg_ts)

        # 最后回到安全位置（停止点）
        final_pose = np.eye(4)
        final_pose[:3, 3] = np.array([0.2, 0.2, 0.2])
        seg_traj, seg_objs, seg_ts = self._interpolate_ee_trajectory(
            trajectory[-1], final_pose, num_steps=15
        )
        trajectory.extend(seg_traj)
        objects_state_seq.extend(seg_objs)
        timestamps.extend(seg_ts)

        # 记录最终决策点（停止）
        decision_points.append(len(trajectory) - 1)
        decision_labels.append(1)  # 停止

        # 构建输出
        return self._build_output(
            trajectory, objects, objects_state_seq, timestamps,
            task_type='counting',
            decision_points=decision_points,
            decision_labels=decision_labels,
            memory_aspects=['counting']
        )

    def _gen_spatial_task(self, objects: List, difficulty: int) -> Dict:
        """
        Spatial Memorization: 记住初始位置，执行中交换，执行后放回原位

        例如：记住 A 在左、B 在右 -> 混合 -> A 放回左、B 放回右
        """
        trajectory = []
        objects_state_seq = []
        timestamps = []
        decision_points = []
        decision_labels = []

        # 初始位置
        A_init = np.array([0.15, -0.05, 0.05])
        B_init = np.array([0.15, 0.05, 0.05])

        current_time = 0.0

        # Phase 1: 移动到 A 和 B 上方
        for _ in range(5):
            p = np.array([0.15, 0.0, 0.15])
            trajectory.append(self._pose_to_mat(p))
            objects_state_seq.append(self._make_obj_state([A_init, B_init], current_time))
            timestamps.append(current_time)
            current_time += self.dt

        # Phase 2: 移动到 B（混淆）
        for _ in range(5):
            p = np.array([0.15, 0.05, 0.12])
            trajectory.append(self._pose_to_mat(p))
            objects_state_seq.append(self._make_obj_state([A_init, B_init], current_time))
            timestamps.append(current_time)
            current_time += self.dt

        # 决策点：需要记住要回到 A_init
        decision_points.append(len(trajectory) - 1)
        decision_labels.append(0)  # 记住 A 的目标位置

        # Phase 3: 抬起并移向 A 原位置
        for i in range(8):
            t = i / 7.0
            p = A_init + np.array([0, 0, 0.1 * (1 - t)])
            trajectory.append(self._pose_to_mat(p))
            objects_state_seq.append(self._make_obj_state([A_init, B_init], current_time))
            timestamps.append(current_time)
            current_time += self.dt

        # Phase 4: 下降到 A 原位置
        for _ in range(5):
            p = A_init + np.array([0, 0, 0.0])
            trajectory.append(self._pose_to_mat(p))
            objects_state_seq.append(self._make_obj_state([A_init, B_init], current_time))
            timestamps.append(current_time)
            current_time += self.dt

        # Phase 5: 回到安全位置
        final_pose = self._pose_to_mat(np.array([0.2, 0.2, 0.2]))
        seg_traj, seg_objs, seg_ts = self._interpolate_ee_trajectory(
            trajectory[-1], final_pose, num_steps=15
        )
        trajectory.extend(seg_traj)
        objects_state_seq.extend(seg_objs)
        timestamps.extend(seg_ts)

        return self._build_output(
            trajectory, objects, objects_state_seq, timestamps,
            task_type='spatial',
            decision_points=decision_points,
            decision_labels=decision_labels,
            memory_aspects=['spatial_memorization']
        )

    def _gen_stage_task(self, objects: List, difficulty: int) -> Dict:
        """
        Task Stage Identification: 同一视觉状态在不同阶段有不同含义

        例如：到达某位置 -> 第一次是抓取 -> 第二次是放置
        """
        trajectory = []
        objects_state_seq = []
        timestamps = []
        decision_points = []
        decision_labels = []

        target_pos = np.array([0.2, 0.0, 0.05])
        current_time = 0.0

        # Stage 1: 接近目标
        for _ in range(8):
            p = target_pos + np.array([0, 0, 0.1 - 0.01 * _])
            trajectory.append(self._pose_to_mat(p))
            objects_state_seq.append(self._make_obj_state([target_pos], current_time))
            timestamps.append(current_time)
            current_time += self.dt

        # 决策点 1: 到达目标位置（应该抓取）
        decision_points.append(len(trajectory) - 1)
        decision_labels.append(0)  # 抓取

        # Stage 1.5: 抓取并抬起
        for _ in range(5):
            p = target_pos + np.array([0, 0, 0.05])
            trajectory.append(self._pose_to_mat(p))
            objects_state_seq.append(self._make_obj_state([target_pos], current_time))
            timestamps.append(current_time)
            current_time += self.dt

        # Stage 2: 移动到另一位置（视觉状态可能相似）
        dest = np.array([0.3, 0.1, 0.15])
        for _ in range(10):
            t = _ / 9.0
            p = target_pos * (1 - t) + dest * t
            trajectory.append(self._pose_to_mat(p))
            objects_state_seq.append(self._make_obj_state([target_pos], current_time))
            timestamps.append(current_time)
            current_time += self.dt

        # 决策点 2: 再次到达某位置（应该放置）
        decision_points.append(len(trajectory) - 1)
        decision_labels.append(1)  # 放置

        # 放置
        for _ in range(5):
            p = dest - np.array([0, 0, 0.05 * _])
            trajectory.append(self._pose_to_mat(p))
            objects_state_seq.append(self._make_obj_state([target_pos], current_time))
            timestamps.append(current_time)
            current_time += self.dt

        # 返回
        final_pose = self._pose_to_mat(np.array([0.2, 0.2, 0.2]))
        seg_traj, seg_objs, seg_ts = self._interpolate_ee_trajectory(
            trajectory[-1], final_pose, num_steps=15
        )
        trajectory.extend(seg_traj)
        objects_state_seq.extend(seg_objs)
        timestamps.extend(seg_ts)

        return self._build_output(
            trajectory, objects, objects_state_seq, timestamps,
            task_type='stage',
            decision_points=decision_points,
            decision_labels=decision_labels,
            memory_aspects=['stage_identification']
        )

    def _gen_preloaded_task(self, objects: List, difficulty: int) -> Dict:
        """
        Pre-loaded Memory: 执行时才出现的目标，在 demo 中预加载

        例如：demo 展示了把红色方块放到碗里 -> 测试时让模型找碗
        """
        trajectory = []
        objects_state_seq = []
        timestamps = []
        decision_points = []
        decision_labels = []

        # 目标容器位置（测试时才知道）
        container_pos = np.array([0.25, 0.05, 0.03])
        object_pos = np.array([0.15, -0.05, 0.05])

        current_time = 0.0

        # 演示阶段：把对象移动到容器附近
        for i in range(15):
            t = i / 14.0
            p = object_pos * (1 - t) + (container_pos + np.array([0, 0, 0.1])) * t
            trajectory.append(self._pose_to_mat(p))
            objects_state_seq.append(self._make_obj_state([object_pos, container_pos], current_time))
            timestamps.append(current_time)
            current_time += self.dt

        # 决策点：需要"记得"目标是 container_pos
        decision_points.append(len(trajectory) - 1)
        decision_labels.append(0)  # 继续放入容器

        # 完成放置
        for i in range(5):
            p = container_pos + np.array([0, 0, 0.05 - 0.01 * i])
            trajectory.append(self._pose_to_mat(p))
            objects_state_seq.append(self._make_obj_state([object_pos, container_pos], current_time))
            timestamps.append(current_time)
            current_time += self.dt

        # 返回
        final_pose = self._pose_to_mat(np.array([0.2, 0.2, 0.2]))
        seg_traj, seg_objs, seg_ts = self._interpolate_ee_trajectory(
            trajectory[-1], final_pose, num_steps=15
        )
        trajectory.extend(seg_traj)
        objects_state_seq.extend(seg_objs)
        timestamps.extend(seg_ts)

        return self._build_output(
            trajectory, objects, objects_state_seq, timestamps,
            task_type='preloaded',
            decision_points=decision_points,
            decision_labels=decision_labels,
            memory_aspects=['preloaded_memory']
        )

    def _gen_continuous_task(self, objects: List, difficulty: int) -> Dict:
        """
        Continuous Memory: 长时间追踪 + 轻度遮挡

        例如：目标被另一个物体遮挡，需要持续追踪
        """
        trajectory = []
        objects_state_seq = []
        timestamps = []
        decision_points = []
        decision_labels = []

        # 目标物体和干扰物体
        target_pos = np.array([0.2, 0.0, 0.05])
        blocker_pos = np.array([0.2, 0.02, 0.05])  # 挡在前面

        current_time = 0.0

        # Phase 1: 接近目标
        for i in range(10):
            p = target_pos + np.array([0, 0, 0.15 - 0.015 * i])
            trajectory.append(self._pose_to_mat(p))
            objects_state_seq.append(self._make_obj_state([target_pos, blocker_pos], current_time))
            timestamps.append(current_time)
            current_time += self.dt

        # Phase 2: 遮挡（目标被挡住，但轨迹仍需延续）
        for i in range(10):
            p = blocker_pos + np.array([0, 0, 0.05])
            trajectory.append(self._pose_to_mat(p))
            # 目标位置不变，但被遮挡
            objects_state_seq.append(self._make_obj_state([target_pos, blocker_pos], current_time, occlusion=[True, False]))
            timestamps.append(current_time)
            current_time += self.dt

        # 决策点：需要记得目标实际位置
        decision_points.append(len(trajectory) - 1)
        decision_labels.append(0)  # 继续追踪

        # Phase 3: 绕过遮挡继续移动
        for i in range(10):
            t = i / 9.0
            p = blocker_pos + np.array([0, 0.05 * t, 0.05])
            trajectory.append(self._pose_to_mat(p))
            objects_state_seq.append(self._make_obj_state([target_pos, blocker_pos], current_time))
            timestamps.append(current_time)
            current_time += self.dt

        # 返回
        final_pose = self._pose_to_mat(np.array([0.2, 0.2, 0.2]))
        seg_traj, seg_objs, seg_ts = self._interpolate_ee_trajectory(
            trajectory[-1], final_pose, num_steps=15
        )
        trajectory.extend(seg_traj)
        objects_state_seq.extend(seg_objs)
        timestamps.extend(seg_ts)

        return self._build_output(
            trajectory, objects, objects_state_seq, timestamps,
            task_type='continuous',
            decision_points=decision_points,
            decision_labels=decision_labels,
            memory_aspects=['continuous_memory']
        )

    # ========================================================================
    # 辅助函数
    # ========================================================================

    def _pose_to_mat(self, position: np.ndarray) -> np.ndarray:
        """位置转 4x4 位姿矩阵"""
        T = np.eye(4)
        T[:3, 3] = position
        return T

    def _make_obj_state(
        self,
        obj_positions: List[np.ndarray],
        timestamp: float,
        occlusion: Optional[List[bool]] = None
    ) -> Dict:
        """构建单帧对象状态"""
        poses = []
        ids = []
        occ_list = occlusion if occlusion is not None else [False] * len(obj_positions)

        for i, pos in enumerate(obj_positions):
            T = np.eye(4)
            T[:3, 3] = pos
            poses.append(T)
            ids.append(i)

        return {
            'object_poses': poses,
            'object_ids': ids,
            'occlusion': occ_list,
            'timestamp': timestamp
        }

    def _interpolate_ee_trajectory(
        self,
        T_start: np.ndarray,
        T_end: np.ndarray,
        num_steps: int,
        grip_start: float = 1.0,
        grip_end: float = 1.0
    ) -> Tuple[List[np.ndarray], List[Dict], List[float]]:
        """简单线性插值 EE 轨迹"""
        trajectory = []
        objects_state_seq = []
        timestamps = []

        # 提取位置
        p_start = T_start[:3, 3]
        p_end = T_end[:3, 3]

        # 固定时间间隔
        dt = self.dt

        for i in range(num_steps):
            t = i / (num_steps - 1) if num_steps > 1 else 0.0
            p = p_start * (1 - t) + p_end * t

            T = np.eye(4)
            T[:3, 3] = p

            trajectory.append(T)
            # 暂时用静止对象状态
            objects_state_seq.append(self._make_obj_state([p], i * dt))
            timestamps.append(i * dt)

        return trajectory, objects_state_seq, timestamps

    def _build_output(
        self,
        trajectory: List[np.ndarray],
        objects: List,
        objects_state_seq: List[Dict],
        timestamps: List[float],
        task_type: str,
        decision_points: List[int],
        decision_labels: List[int],
        memory_aspects: List[str]
    ) -> Dict:
        """构建标准输出格式"""
        # 转换为 numpy
        T_w_es = np.stack(trajectory, axis=0).astype(np.float32)  # [T, 4,4]
        grips = np.ones(len(trajectory), dtype=np.float32)  # 默认张开

        # 简单点云生成（使用轨迹位置作为虚拟点云）
        pcds = []
        for i in range(len(trajectory)):
            p = trajectory[i][:3, 3]
            # 简单生成一些点
            pcd = p + np.random.randn(100, 3).astype(np.float32) * 0.01
            pcds.append(pcd)

        meta = MemoryTaskMeta(
            task_type=task_type,
            decision_points=decision_points,
            decision_labels=decision_labels,
            memory_aspects=memory_aspects
        )

        return {
            'pcds': pcds,
            'T_w_es': T_w_es,
            'grips': grips,
            'objects_state_seq': objects_state_seq,
            'meta': meta,
            'timestamps': timestamps
        }


# ============================================================================
# 测试
# ============================================================================
if __name__ == '__main__':
    random.seed(42)
    np.random.seed(42)

    generator = MemoryTaskGenerator()

    # 测试每种任务类型
    for task_type in ['counting', 'spatial', 'stage', 'preloaded', 'continuous']:
        print(f"\n=== Testing {task_type} ===")
        result = generator.generate_task(
            objects=[None, None],  # mock objects
            task_type=task_type,
            difficulty=1
        )
        print(f"Trajectory length: {len(result['T_w_es'])}")
        print(f"Decision points: {result['meta'].decision_points}")
        print(f"Memory aspects: {result['meta'].memory_aspects}")

    print("\n✓ memory_task_generator.py basic test passed")
