"""
Pseudo-Demonstration Generator for Instant Policy
Based on paper Appendix D (Section on Data Generation)

Uses trimesh surface sampling instead of pyrender for headless compatibility.
"""
import numpy as np
import trimesh
from scipy.spatial.transform import Rotation as Rot
from scipy.interpolate import CubicSpline
from typing import List, Dict, Tuple, Optional
import random


class PseudoDemoGenerator:
    """Generate pseudo-demonstrations using ShapeNet objects."""

    def __init__(self, image_width=640, image_height=480):
        self.image_width = image_width
        self.image_height = image_height

        # Gripper model (Robotiq 2F-85)
        self.gripper_mesh = self._create_gripper_mesh()
        self.gripper_keypoints = self._create_gripper_keypoints()

        # Object tracking for attachment/detachment
        self.attached_object = None   # index into scene['objects']
        self.attachment_offset = None  # 4x4 offset in gripper frame

    def _create_gripper_mesh(self):
        palm = trimesh.creation.box(extents=[0.06, 0.04, 0.02])
        left_finger = trimesh.creation.box(extents=[0.01, 0.01, 0.08])
        left_finger.apply_translation([0.03, 0, 0.04])
        right_finger = trimesh.creation.box(extents=[0.01, 0.01, 0.08])
        right_finger.apply_translation([-0.03, 0, 0.04])
        return trimesh.util.concatenate([palm, left_finger, right_finger])

    def _create_gripper_keypoints(self):
        return np.array([
            [0.0,  0.0,  0.0],
            [0.04, 0.0,  0.0],
            [-0.04, 0.0, 0.0],
            [0.0,  0.0,  0.05],
            [0.02, 0.02, 0.0],
            [0.02, -0.02, 0.0],
        ])

    # ------------------------------------------------------------------
    # Scene: simple dict instead of pyrender.Scene
    # scene = {
    #   'objects': [ {'mesh': trimesh, 'pose': 4x4} , ... ],
    # }
    # ------------------------------------------------------------------

    def create_scene(self, objects: List[trimesh.Trimesh]) -> Dict:
        """Create a lightweight scene dict with object poses."""
        scene = {'objects': []}

        for i, obj in enumerate(objects):
            x = random.uniform(-0.3, 0.3)
            y = random.uniform(-0.3, 0.3)
            angle = random.uniform(0, 2 * np.pi)
            rot = Rot.from_euler('z', angle).as_matrix()
            pose = np.eye(4)
            pose[:3, :3] = rot
            pose[:3, 3] = [x, y, 0.0]
            scene['objects'].append({'mesh': obj, 'pose': pose.copy()})

        return scene

    def setup_cameras(self, scene: Dict):
        """Store camera poses in scene dict (kept for API compatibility)."""
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
            task_type = random.choice(['grasp', 'place', 'push', 'open', 'close'])

            if task_type == 'grasp':
                c = obj_center(random.randint(0, len(objects) - 1))
                waypoints += [c + [0, 0, 0.15], c + [0, 0, 0.02], c + [0, 0, 0.2]]

            elif task_type == 'place':
                c = obj_center(random.randint(0, len(objects) - 1))
                pick = c + [0, 0, 0.02]
                place = np.array([random.uniform(-0.3, 0.3), random.uniform(-0.3, 0.3), 0.15])
                waypoints += [pick, pick + [0, 0, 0.2], place, place - [0, 0, 0.1]]

            elif task_type == 'push':
                c = obj_center(random.randint(0, len(objects) - 1))
                d = np.array([random.uniform(-1, 1), random.uniform(-1, 1), 0])
                d /= np.linalg.norm(d) + 1e-6
                waypoints += [c + d * 0.1 + [0, 0, 0.05],
                               c + [0, 0, 0.02],
                               c - d * 0.15 + [0, 0, 0.02]]

            elif task_type == 'open':
                c = obj_center(random.randint(0, len(objects) - 1))
                approach = c + [0, 0, 0.02]
                d = np.array([random.uniform(-0.2, 0.2), random.uniform(-0.2, 0.2), 0])
                waypoints += [approach, approach + d * 0.5, approach + d]

            else:  # close
                c = obj_center(random.randint(0, len(objects) - 1))
                open_pos = c + [random.uniform(-0.15, 0.15), 0, 0.02]
                waypoints += [open_pos, open_pos * 0.5 + c * 0.5, c + [0, 0, 0.02]]
        else:
            for _ in range(num_waypoints):
                c = obj_center(random.randint(0, len(objects) - 1))
                offset = np.array([random.uniform(-0.1, 0.1),
                                   random.uniform(-0.1, 0.1),
                                   random.uniform(0.0, 0.2)])
                waypoints.append(c + offset)

        return waypoints

    def generate_trajectory(self, waypoints: List[np.ndarray],
                            scene: Dict,
                            objects: List[trimesh.Trimesh],
                            initial_pose: np.ndarray = None,
                            spacing_trans: float = 0.01,
                            spacing_rot: float = 3.0) -> Tuple[List[np.ndarray], List[int]]:
        if initial_pose is None:
            initial_pose = np.eye(4)
            initial_pose[:3, 3] = [random.uniform(-0.4, 0.4),
                                   random.uniform(-0.4, 0.4),
                                   random.uniform(0.3, 0.5)]
            initial_pose[:3, :3] = Rot.random().as_matrix()

        poses = [initial_pose.copy()]
        gripper_states = [1]

        self.attached_object = None
        self.attachment_offset = None

        grasp_waypoints = set(random.sample(range(len(waypoints)),
                                            k=random.randint(1, min(3, len(waypoints)))))
        interp_method = random.choice(['linear', 'cubic', 'slerp'])

        for i, waypoint in enumerate(waypoints):
            current_pos = poses[-1][:3, 3]
            target_pos = waypoint
            distance = np.linalg.norm(target_pos - current_pos)
            num_steps = max(1, int(distance / spacing_trans))

            if interp_method == 'cubic':
                positions = self._cubic_interpolate(current_pos, target_pos, num_steps, i, waypoints)
            else:
                positions = self._linear_interpolate(current_pos, target_pos, num_steps)

            current_rot = Rot.from_matrix(poses[-1][:3, :3])
            target_rot = self._compute_target_rotation(target_pos - current_pos)

            for step_idx, new_pos in enumerate(positions):
                alpha = (step_idx + 1) / len(positions)
                new_rot = Rot.from_quat(
                    self._slerp_quat(current_rot.as_quat(), target_rot.as_quat(), alpha)
                )
                new_pose = np.eye(4)
                new_pose[:3, :3] = new_rot.as_matrix()
                new_pose[:3, 3] = new_pos

                if i in grasp_waypoints and step_idx == len(positions) - 1:
                    new_state = 1 - gripper_states[-1]
                    if new_state == 0:
                        self._attach_closest_object(scene, new_pose)
                    else:
                        self._detach_object()
                    gripper_states.append(new_state)
                else:
                    gripper_states.append(gripper_states[-1])

                if self.attached_object is not None:
                    self._update_attached_object_pose(scene, new_pose)

                poses.append(new_pose)

        return poses, gripper_states

    def _linear_interpolate(self, start, end, num_steps):
        return [start * (1 - t) + end * t for t in np.linspace(0, 1, num_steps + 1)[1:]]

    def _cubic_interpolate(self, start, end, num_steps, current_idx, all_waypoints):
        points = [start]
        if current_idx > 0:
            points.insert(0, all_waypoints[current_idx - 1])
        else:
            points.insert(0, start - (end - start) * 0.5)
        points.append(end)
        if current_idx < len(all_waypoints) - 1:
            points.append(all_waypoints[current_idx + 1])
        else:
            points.append(end + (end - start) * 0.5)
        points = np.array(points)
        t = np.linspace(0, 1, len(points))
        t_new = np.linspace(0, 1, num_steps + 1)[1:]
        try:
            cs = CubicSpline(t, points, axis=0)
            return [cs(ti) for ti in t_new]
        except Exception:
            return self._linear_interpolate(start, end, num_steps)

    def _slerp_quat(self, q0, q1, t):
        q0 = q0 / np.linalg.norm(q0)
        q1 = q1 / np.linalg.norm(q1)
        dot = np.dot(q0, q1)
        if dot < 0.0:
            q1, dot = -q1, -dot
        dot = np.clip(dot, -1.0, 1.0)
        theta = np.arccos(dot)
        if theta < 1e-6:
            return q0 * (1 - t) + q1 * t
        sin_theta = np.sin(theta)
        return np.sin((1 - t) * theta) / sin_theta * q0 + np.sin(t * theta) / sin_theta * q1

    def _compute_target_rotation(self, direction):
        if np.linalg.norm(direction) < 1e-6:
            return Rot.identity()
        direction = direction / np.linalg.norm(direction)
        z_axis = direction
        x_axis = np.cross([0, 0, 1] if abs(z_axis[2]) < 0.9 else [1, 0, 0], z_axis)
        x_axis /= np.linalg.norm(x_axis)
        y_axis = np.cross(z_axis, x_axis)
        return Rot.from_matrix(np.column_stack([x_axis, y_axis, z_axis]))

    def _attach_closest_object(self, scene: Dict, gripper_pose: np.ndarray):
        gripper_pos = gripper_pose[:3, 3]
        best_idx, best_dist = None, float('inf')
        for i, obj in enumerate(scene['objects']):
            d = np.linalg.norm(gripper_pos - obj['pose'][:3, 3])
            if d < best_dist:
                best_dist, best_idx = d, i
        if best_idx is not None and best_dist < 0.1:
            self.attached_object = best_idx
            self.attachment_offset = np.linalg.inv(gripper_pose) @ scene['objects'][best_idx]['pose']

    def _detach_object(self):
        self.attached_object = None
        self.attachment_offset = None

    def _update_attached_object_pose(self, scene: Dict, gripper_pose: np.ndarray):
        if self.attached_object is not None and self.attachment_offset is not None:
            scene['objects'][self.attached_object]['pose'] = gripper_pose @ self.attachment_offset

    def render_observations(self, scene: Dict,
                            gripper_poses: List[np.ndarray],
                            target_points: int = 4096) -> List[np.ndarray]:
        """Generate point clouds via trimesh surface sampling (no OpenGL needed).
        Scene points are sampled once and reused across all poses for speed.
        """
        # Sample scene objects once (geometry doesn't change per frame)
        scene_pts_list = []
        for obj in scene['objects']:
            tm = obj['mesh'].copy()
            tm.apply_transform(obj['pose'])
            if len(tm.faces) == 0:
                continue
            pts, _ = trimesh.sample.sample_surface(tm, 1024)
            valid = (pts[:, 2] > 0.05) & (pts[:, 2] < 1.0)
            pts = pts[valid]
            dist = np.linalg.norm(pts - np.array([0, 0, 0.1]), axis=1)
            pts = pts[dist < 0.5]
            if len(pts) > 0:
                scene_pts_list.append(pts)

        scene_pts = np.concatenate(scene_pts_list, axis=0) if scene_pts_list else np.zeros((0, 3))

        point_clouds = []
        for pose in gripper_poses:
            # Sample gripper points for this pose
            g = self.gripper_mesh.copy()
            g.apply_transform(pose)
            all_pts = [scene_pts] if len(scene_pts) > 0 else []
            if len(g.faces) > 0:
                g_pts, _ = trimesh.sample.sample_surface(g, 256)
                all_pts.append(g_pts)

            combined = np.concatenate(all_pts, axis=0) if all_pts else np.random.randn(target_points, 3) * 0.05

            if len(combined) >= target_points:
                idx = np.random.choice(len(combined), target_points, replace=False)
            else:
                idx = np.random.choice(len(combined), target_points, replace=True)
            combined = combined[idx]

            # Transform to gripper frame
            gripper_inv = np.linalg.inv(pose)
            homog = np.concatenate([combined, np.ones((len(combined), 1))], axis=1)
            combined = (gripper_inv @ homog.T).T[:, :3]
            point_clouds.append(combined)

        return point_clouds

    def add_data_augmentation(self, poses, gripper_states, point_clouds):
        if random.random() < 0.3:
            for i in range(1, len(poses)):
                poses[i][:3, 3] += np.random.randn(3) * 0.005
                poses[i][:3, :3] = poses[i][:3, :3] @ Rot.from_euler(
                    'xyz', np.random.randn(3) * 5, degrees=True).as_matrix()
        if random.random() < 0.1:
            flip_idx = random.randint(0, len(gripper_states) - 1)
            gripper_states[flip_idx] = 1 - gripper_states[flip_idx]
        return poses, gripper_states, point_clouds

    def generate_pseudo_demonstration(self, objects: List[trimesh.Trimesh]) -> Dict:
        scene = self.create_scene(objects)
        self.setup_cameras(scene)
        waypoints = self.sample_waypoints(scene, objects)
        poses, gripper_states = self.generate_trajectory(waypoints, scene, objects)
        point_clouds = self.render_observations(scene, poses)
        del scene
        poses, gripper_states, point_clouds = self.add_data_augmentation(
            poses, gripper_states, point_clouds)
        return {
            'pcds': point_clouds,
            'T_w_es': poses,
            'grips': [float(s) for s in gripper_states]
        }
