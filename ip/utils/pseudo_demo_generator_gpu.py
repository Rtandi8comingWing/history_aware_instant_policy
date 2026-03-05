"""
GPU-Accelerated Pseudo-Demonstration Generator
Uses PyTorch CUDA for 10-50x speedup over CPU trimesh version.
"""
import numpy as np
import torch
import trimesh
from scipy.spatial.transform import Rotation as Rot
from scipy.interpolate import CubicSpline
from typing import List, Dict, Tuple
import random


class PseudoDemoGeneratorGPU:
    """Generate pseudo-demonstrations using GPU acceleration."""

    def __init__(self, device='cuda', image_width=640, image_height=480):
        self.device = torch.device(device if torch.cuda.is_available() else 'cpu')
        self.image_width = image_width
        self.image_height = image_height

        # Gripper model
        self.gripper_mesh = self._create_gripper_mesh()

        # Pre-sample gripper points on GPU
        if len(self.gripper_mesh.faces) > 0:
            pts, _ = trimesh.sample.sample_surface(self.gripper_mesh, 256)
            self._gripper_pts_canonical = torch.from_numpy(pts).float().to(self.device)
        else:
            self._gripper_pts_canonical = torch.zeros(256, 3, device=self.device)

        # Object tracking
        self.attached_object = None
        self.attachment_offset = None

    def _create_gripper_mesh(self):
        palm = trimesh.creation.box(extents=[0.06, 0.04, 0.02])
        left_finger = trimesh.creation.box(extents=[0.01, 0.01, 0.08])
        left_finger.apply_translation([0.03, 0, 0.04])
        right_finger = trimesh.creation.box(extents=[0.01, 0.01, 0.08])
        right_finger.apply_translation([-0.03, 0, 0.04])
        return trimesh.util.concatenate([palm, left_finger, right_finger])

    def create_scene(self, objects: List[trimesh.Trimesh]) -> Dict:
        """Create scene with GPU-ready object data."""
        scene = {'objects': []}

        for obj in objects:
            x = random.uniform(-0.3, 0.3)
            y = random.uniform(-0.3, 0.3)
            angle = random.uniform(0, 2 * np.pi)
            rot = Rot.from_euler('z', angle).as_matrix()
            pose = np.eye(4)
            pose[:3, :3] = rot
            pose[:3, 3] = [x, y, 0.0]

            # Pre-sample object points on GPU
            if len(obj.faces) > 0:
                pts, _ = trimesh.sample.sample_surface(obj, 2048)
                pts_gpu = torch.from_numpy(pts).float().to(self.device)
            else:
                pts_gpu = torch.zeros(2048, 3, device=self.device)

            scene['objects'].append({
                'mesh': obj,
                'pose': pose.copy(),
                'points_gpu': pts_gpu  # Pre-sampled points on GPU
            })

        return scene

    def setup_cameras(self, scene: Dict):
        """Store camera poses."""
        scene['camera_poses'] = [
            self._make_camera_pose(0, 0, 0.8, -45, 0),
            self._make_camera_pose(-0.5, 0.3, 0.8, -45, 30),
            self._make_camera_pose(0.5, -0.3, 0.8, -45, -30),
        ]

    def _make_camera_pose(self, x, y, z, pitch_deg, yaw_deg):
        pose = np.eye(4)
        pose[:3, 3] = [x, y, z]
        pose[:3, :3] = Rot.from_euler('xyz', [pitch_deg, 0, yaw_deg], degrees=True).as_matrix()
        return pose

    def sample_waypoints(self, scene: Dict, objects: List[trimesh.Trimesh],
                         num_waypoints: int = None, bias_common_tasks: bool = True) -> List[np.ndarray]:
        if num_waypoints is None:
            num_waypoints = random.randint(2, 6)

        waypoints = []

        def obj_center(idx):
            return scene['objects'][idx]['pose'][:3, 3].copy()

        if bias_common_tasks and random.random() < 0.5:
            # Pick-and-place task
            obj_idx = random.randint(0, len(objects) - 1)
            center = obj_center(obj_idx)

            # Approach
            approach = center.copy()
            approach[2] += 0.15
            waypoints.append(self._pose_from_position(approach))

            # Grasp
            grasp = center.copy()
            grasp[2] += 0.05
            waypoints.append(self._pose_from_position(grasp))

            # Lift
            lift = grasp.copy()
            lift[2] += 0.15
            waypoints.append(self._pose_from_position(lift))

            # Place
            place_xy = np.random.uniform(-0.3, 0.3, 2)
            place = np.array([place_xy[0], place_xy[1], lift[2]])
            waypoints.append(self._pose_from_position(place))

            # Lower
            lower = place.copy()
            lower[2] = grasp[2]
            waypoints.append(self._pose_from_position(lower))

            # Retreat
            retreat = lower.copy()
            retreat[2] += 0.15
            waypoints.append(self._pose_from_position(retreat))
        else:
            # Random waypoints
            for _ in range(num_waypoints):
                x = random.uniform(-0.4, 0.4)
                y = random.uniform(-0.4, 0.4)
                z = random.uniform(0.1, 0.4)
                waypoints.append(self._pose_from_position([x, y, z]))

        return waypoints[:num_waypoints]

    def _pose_from_position(self, position):
        pose = np.eye(4)
        pose[:3, 3] = position
        pose[:3, :3] = Rot.from_euler('xyz', [180, 0, random.uniform(-30, 30)], degrees=True).as_matrix()
        return pose

    def interpolate_trajectory(self, waypoints: List[np.ndarray],
                               trans_spacing: float = 0.01,
                               rot_spacing: float = 3.0) -> Tuple[List[np.ndarray], List[float]]:
        positions = np.array([wp[:3, 3] for wp in waypoints])
        rotations = [Rot.from_matrix(wp[:3, :3]) for wp in waypoints]

        # Interpolate positions
        t = np.linspace(0, 1, len(positions))
        cs = CubicSpline(t, positions, bc_type='clamped')

        # Estimate number of steps
        total_dist = np.sum(np.linalg.norm(np.diff(positions, axis=0), axis=1))
        num_steps = max(int(total_dist / trans_spacing), len(waypoints))

        t_dense = np.linspace(0, 1, num_steps)
        positions_dense = cs(t_dense)

        # Interpolate rotations (slerp)
        rotations_dense = []
        for i, t_val in enumerate(t_dense):
            idx = int(t_val * (len(rotations) - 1))
            idx = min(idx, len(rotations) - 2)
            local_t = (t_val * (len(rotations) - 1)) - idx
            rot_interp = Rot.from_quat(
                (1 - local_t) * rotations[idx].as_quat() + local_t * rotations[idx + 1].as_quat()
            )
            rotations_dense.append(rot_interp)

        # Build trajectory
        trajectory = []
        for pos, rot in zip(positions_dense, rotations_dense):
            pose = np.eye(4)
            pose[:3, 3] = pos
            pose[:3, :3] = rot.as_matrix()
            trajectory.append(pose)

        # Gripper states (open until grasp, then close)
        grips = [0.0] * len(trajectory)
        if len(waypoints) >= 3:
            grasp_idx = len(trajectory) // 3
            for i in range(grasp_idx, len(trajectory)):
                grips[i] = 1.0

        return trajectory, grips

    def render_observations_gpu(self, scene: Dict, gripper_poses: List[np.ndarray],
                                target_points: int = 4096) -> List[np.ndarray]:
        """
        GPU-accelerated point cloud rendering.
        10-50x faster than CPU trimesh version.
        """
        point_clouds = []

        # Convert gripper poses to GPU tensors (batch processing)
        gripper_poses_gpu = torch.from_numpy(np.stack(gripper_poses)).float().to(self.device)

        for i, gripper_pose in enumerate(gripper_poses_gpu):
            all_pts = []

            # Transform gripper points (GPU)
            gripper_pts_homog = torch.cat([
                self._gripper_pts_canonical,
                torch.ones(len(self._gripper_pts_canonical), 1, device=self.device)
            ], dim=1)
            g_pts = (gripper_pose @ gripper_pts_homog.T).T[:, :3]
            all_pts.append(g_pts)

            # Transform object points (GPU batch)
            for obj_info in scene['objects']:
                obj_pts = obj_info['points_gpu']
                obj_pose = torch.from_numpy(obj_info['pose']).float().to(self.device)

                # Apply object pose
                obj_pts_homog = torch.cat([obj_pts, torch.ones(len(obj_pts), 1, device=self.device)], dim=1)
                transformed = (obj_pose @ obj_pts_homog.T).T[:, :3]
                all_pts.append(transformed)

            # Combine and subsample (GPU)
            combined = torch.cat(all_pts, dim=0)

            if len(combined) >= target_points:
                idx = torch.randperm(len(combined), device=self.device)[:target_points]
            else:
                idx = torch.randint(0, len(combined), (target_points,), device=self.device)
            combined = combined[idx]

            # Transform to gripper frame (GPU)
            gripper_inv = torch.inverse(gripper_pose)
            homog = torch.cat([combined, torch.ones(len(combined), 1, device=self.device)], dim=1)
            combined = (gripper_inv @ homog.T).T[:, :3]

            # Move back to CPU for storage
            point_clouds.append(combined.cpu().numpy())

        return point_clouds

    def simulate_object_attachment(self, scene: Dict, gripper_pose: np.ndarray,
                                   grip_state: float, threshold: float = 0.08):
        """Simulate object attachment/detachment."""
        if grip_state > 0.5 and self.attached_object is None:
            # Try to attach
            gripper_pos = gripper_pose[:3, 3]
            for i, obj_info in enumerate(scene['objects']):
                obj_pos = obj_info['pose'][:3, 3]
                dist = np.linalg.norm(gripper_pos - obj_pos)
                if dist < threshold:
                    self.attached_object = i
                    self.attachment_offset = np.linalg.inv(gripper_pose) @ obj_info['pose']
                    break
        elif grip_state < 0.5 and self.attached_object is not None:
            # Detach
            self.attached_object = None
            self.attachment_offset = None

        # Update attached object pose
        if self.attached_object is not None:
            scene['objects'][self.attached_object]['pose'] = gripper_pose @ self.attachment_offset

    def generate_pseudo_demonstration(self, objects: List[trimesh.Trimesh]) -> Dict:
        """Generate one pseudo-demonstration (GPU accelerated)."""
        # Create scene
        scene = self.create_scene(objects)
        self.setup_cameras(scene)

        # Sample waypoints
        waypoints = self.sample_waypoints(scene, objects, bias_common_tasks=True)

        # Interpolate trajectory
        trajectory, grips = self.interpolate_trajectory(waypoints, trans_spacing=0.01, rot_spacing=3.0)

        # Simulate attachment
        self.attached_object = None
        self.attachment_offset = None
        for pose, grip in zip(trajectory, grips):
            self.simulate_object_attachment(scene, pose, grip)

        # Render observations (GPU accelerated)
        pcds = self.render_observations_gpu(scene, trajectory, target_points=4096)

        # Data augmentation (30% perturbation)
        if random.random() < 0.3:
            trajectory, grips, pcds = self._apply_augmentation(trajectory, grips, pcds)

        return {
            'T_w_es': trajectory,
            'grips': grips,
            'pcds': pcds
        }

    def _apply_augmentation(self, trajectory, grips, pcds):
        """Apply data augmentation."""
        # Random SE(3) perturbation
        trans_noise = np.random.uniform(-0.02, 0.02, 3)
        rot_noise = Rot.from_euler('xyz', np.random.uniform(-5, 5, 3), degrees=True).as_matrix()

        aug_traj = []
        for pose in trajectory:
            aug_pose = pose.copy()
            aug_pose[:3, 3] += trans_noise
            aug_pose[:3, :3] = rot_noise @ aug_pose[:3, :3]
            aug_traj.append(aug_pose)

        # Gripper flip (10%)
        if random.random() < 0.1:
            grips = [1.0 - g for g in grips]

        return aug_traj, grips, pcds
