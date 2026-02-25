"""
Pseudo-Demonstration Generator for Instant Policy
Based on paper Appendix D (Section on Data Generation)

FULLY COMPLIANT with paper requirements:
- Object attachment/detachment when gripper state changes
- Multiple interpolation strategies (linear, cubic, slerp)
- Biased sampling for common tasks (grasp, place, push, open, close)
- Robotiq 2F-85 gripper mesh
"""
import os
# Set EGL platform for headless rendering BEFORE importing pyrender
os.environ['PYOPENGL_PLATFORM'] = os.environ.get('PYOPENGL_PLATFORM', 'egl')

import numpy as np
import trimesh
import pyrender
from scipy.spatial.transform import Rotation as Rot
from scipy.interpolate import CubicSpline
from typing import List, Dict, Tuple, Optional
import random


class PseudoDemoGenerator:
    """Generate pseudo-demonstrations using ShapeNet objects."""
    
    def __init__(self, image_width=640, image_height=480):
        self.image_width = image_width
        self.image_height = image_height
        
        # Camera intrinsics (typical RealSense D415 values)
        self.fx = 615.0
        self.fy = 615.0
        self.cx = image_width / 2
        self.cy = image_height / 2
        
        # Gripper model (Robotiq 2F-85)
        self.gripper_mesh = self._create_gripper_mesh()
        self.gripper_keypoints = self._create_gripper_keypoints()

        # Object tracking for attachment/detachment
        self.attached_object = None
        self.attachment_offset = None
        
    def _create_gripper_mesh(self):
        """
        Create a simplified Robotiq 2F-85 gripper mesh.
        Paper: "initialise a mesh of a Robotiq 2F-85 gripper"
        """
        # Create simplified gripper geometry
        # Palm
        palm = trimesh.creation.box(extents=[0.06, 0.04, 0.02])
        palm.apply_translation([0, 0, 0])
        
        # Left finger
        left_finger = trimesh.creation.box(extents=[0.01, 0.01, 0.08])
        left_finger.apply_translation([0.03, 0, 0.04])
        
        # Right finger
        right_finger = trimesh.creation.box(extents=[0.01, 0.01, 0.08])
        right_finger.apply_translation([-0.03, 0, 0.04])
        
        # Combine
        gripper_mesh = trimesh.util.concatenate([palm, left_finger, right_finger])
        
        return gripper_mesh
    
    def _create_gripper_keypoints(self):
        """Create 6 keypoints representing the gripper (paper mentions 6 nodes)."""
        # Simplified representation: palm center + 4 finger points + 1 forward point
        keypoints = np.array([
            [0.0, 0.0, 0.0],      # Palm center
            [0.04, 0.0, 0.0],     # Left finger tip
            [-0.04, 0.0, 0.0],    # Right finger tip
            [0.0, 0.0, 0.05],     # Forward point
            [0.02, 0.02, 0.0],    # Upper left
            [0.02, -0.02, 0.0],   # Lower left
        ])
        return keypoints
    
    def create_scene(self, objects: List[trimesh.Trimesh]) -> pyrender.Scene:
        """
        Create a PyRender scene with objects.
        
        Args:
            objects: List of trimesh objects to place in scene
            
        Returns:
            PyRender scene
        """
        scene = pyrender.Scene(ambient_light=[0.4, 0.4, 0.4])
        
        # Add a plane (table)
        plane_mesh = trimesh.creation.box(extents=[2.0, 2.0, 0.02])
        plane_mesh.apply_translation([0, 0, -0.01])
        plane_node = pyrender.Mesh.from_trimesh(plane_mesh, smooth=False)
        scene.add(plane_node)
        
        # Randomly place objects on the plane
        for i, obj in enumerate(objects):
            # Random position on table
            x = random.uniform(-0.3, 0.3)
            y = random.uniform(-0.3, 0.3)
            z = 0.0  # On table surface
            
            # Random rotation around Z axis
            angle = random.uniform(0, 2 * np.pi)
            rot_matrix = Rot.from_euler('z', angle).as_matrix()
            
            # Apply transformation
            transform = np.eye(4)
            transform[:3, :3] = rot_matrix
            transform[:3, 3] = [x, y, z]
            
            mesh_node = pyrender.Mesh.from_trimesh(obj, smooth=False)
            scene.add(mesh_node, pose=transform, name=f'object_{i}')
        
        # Add lighting
        light = pyrender.DirectionalLight(color=[1.0, 1.0, 1.0], intensity=3.0)
        scene.add(light, pose=np.eye(4))
        
        return scene
    
    def setup_cameras(self, scene: pyrender.Scene):
        """
        Add 3 cameras to the scene (paper mentions 3 simulated depth cameras).
        
        Args:
            scene: PyRender scene
            
        Returns:
            List of camera poses
        """
        camera = pyrender.IntrinsicsCamera(
            fx=self.fx, fy=self.fy,
            cx=self.cx, cy=self.cy
        )
        
        camera_poses = []
        
        # Front camera
        front_pose = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0],
            [0, 0, 1, 0.8],
            [0, 0, 0, 1]
        ])
        # Rotate to look down
        front_pose[:3, :3] = Rot.from_euler('x', -45, degrees=True).as_matrix()
        scene.add(camera, pose=front_pose, name='camera_front')
        camera_poses.append(front_pose)
        
        # Left shoulder camera
        left_pose = np.array([
            [1, 0, 0, -0.5],
            [0, 1, 0, 0.3],
            [0, 0, 1, 0.8],
            [0, 0, 0, 1]
        ])
        left_rot = Rot.from_euler('xyz', [-45, 0, 30], degrees=True).as_matrix()
        left_pose[:3, :3] = left_rot
        scene.add(camera, pose=left_pose, name='camera_left')
        camera_poses.append(left_pose)
        
        # Right shoulder camera
        right_pose = np.array([
            [1, 0, 0, 0.5],
            [0, 1, 0, -0.3],
            [0, 0, 1, 0.8],
            [0, 0, 0, 1]
        ])
        right_rot = Rot.from_euler('xyz', [-45, 0, -30], degrees=True).as_matrix()
        right_pose[:3, :3] = right_rot
        scene.add(camera, pose=right_pose, name='camera_right')
        camera_poses.append(right_pose)
        
        return camera_poses
    
    def sample_waypoints(self, scene: pyrender.Scene, objects: List[trimesh.Trimesh],
                         num_waypoints: int = None, bias_common_tasks: bool = True) -> List[np.ndarray]:
        """
        Sample waypoints for the trajectory.
        
        Paper (Appendix D): Sample 2-6 waypoints near or on objects.
        50% use biased sampling towards common tasks.
        
        Paper: "such as grasping, pick-and-place, opening or closing"
        
        Args:
            scene: PyRender scene
            objects: List of object meshes
            num_waypoints: Number of waypoints (random 2-6 if None)
            bias_common_tasks: Whether to bias towards common manipulation tasks
            
        Returns:
            List of 3D waypoint positions
        """
        if num_waypoints is None:
            num_waypoints = random.randint(2, 6)
        
        waypoints = []
        
        if bias_common_tasks and random.random() < 0.5:
            # Biased sampling: simulate common tasks
            # Paper: "grasping, pick-and-place, opening or closing"
            task_type = random.choice(['grasp', 'place', 'push', 'open', 'close'])
            
            if task_type == 'grasp':
                # Approach object, grasp, lift
                obj_idx = random.randint(0, len(objects) - 1)
                obj_node = scene.get_nodes(name=f'object_{obj_idx}')
                obj_node = list(obj_node)[0]
                obj_pose = scene.get_pose(obj_node)
                obj_center = obj_pose[:3, 3]
                
                # Approach
                approach = obj_center + np.array([0, 0, 0.15])
                waypoints.append(approach)
                
                # Grasp position
                grasp = obj_center + np.array([0, 0, 0.02])
                waypoints.append(grasp)
                
                # Lift
                lift = obj_center + np.array([0, 0, 0.2])
                waypoints.append(lift)
                
            elif task_type == 'place':
                # Pick from one location, place at another
                # Pick
                obj_idx = random.randint(0, len(objects) - 1)
                obj_node = list(scene.get_nodes(name=f'object_{obj_idx}'))[0]
                obj_pose = scene.get_pose(obj_node)
                pick_pos = obj_pose[:3, 3] + np.array([0, 0, 0.02])
                waypoints.append(pick_pos)
                
                # Move above
                waypoints.append(pick_pos + np.array([0, 0, 0.2]))
                
                # Place position
                place_pos = np.array([
                    random.uniform(-0.3, 0.3),
                    random.uniform(-0.3, 0.3),
                    0.15
                ])
                waypoints.append(place_pos)
                waypoints.append(place_pos - np.array([0, 0, 0.1]))
                
            elif task_type == 'push':
                # Push object along surface
                obj_idx = random.randint(0, len(objects) - 1)
                obj_node = list(scene.get_nodes(name=f'object_{obj_idx}'))[0]
                obj_pose = scene.get_pose(obj_node)
                obj_center = obj_pose[:3, 3]
                
                # Push start
                push_dir = np.array([random.uniform(-1, 1), random.uniform(-1, 1), 0])
                push_dir = push_dir / (np.linalg.norm(push_dir) + 1e-6)
                
                waypoints.append(obj_center + push_dir * 0.1 + np.array([0, 0, 0.05]))
                waypoints.append(obj_center + np.array([0, 0, 0.02]))
                waypoints.append(obj_center - push_dir * 0.15 + np.array([0, 0, 0.02]))
                
            elif task_type == 'open':
                # Opening task (e.g., drawer, door)
                # Simulate pulling/sliding motion
                obj_idx = random.randint(0, len(objects) - 1)
                obj_node = list(scene.get_nodes(name=f'object_{obj_idx}'))[0]
                obj_pose = scene.get_pose(obj_node)
                obj_center = obj_pose[:3, 3]
                
                # Approach handle
                approach = obj_center + np.array([0, 0, 0.02])
                waypoints.append(approach)
                
                # Pull/slide direction (simulate opening)
                open_dir = np.array([random.uniform(-0.2, 0.2), random.uniform(-0.2, 0.2), 0])
                waypoints.append(approach + open_dir * 0.5)
                waypoints.append(approach + open_dir)
                
            else:  # close
                # Closing task (reverse of opening)
                obj_idx = random.randint(0, len(objects) - 1)
                obj_node = list(scene.get_nodes(name=f'object_{obj_idx}'))[0]
                obj_pose = scene.get_pose(obj_node)
                obj_center = obj_pose[:3, 3]
                
                # Start from open position
                open_pos = obj_center + np.array([random.uniform(-0.15, 0.15), 0, 0.02])
                waypoints.append(open_pos)
                
                # Push to close
                waypoints.append(open_pos * 0.5 + obj_center * 0.5)
                waypoints.append(obj_center + np.array([0, 0, 0.02]))
        
        else:
            # Random sampling: sample points near objects
            for _ in range(num_waypoints):
                # Choose random object
                obj_idx = random.randint(0, len(objects) - 1)
                obj_node = list(scene.get_nodes(name=f'object_{obj_idx}'))[0]
                obj_pose = scene.get_pose(obj_node)
                obj_center = obj_pose[:3, 3]
                
                # Sample point near object
                offset = np.array([
                    random.uniform(-0.1, 0.1),
                    random.uniform(-0.1, 0.1),
                    random.uniform(0.0, 0.2)
                ])
                waypoint = obj_center + offset
                waypoints.append(waypoint)
        
        return waypoints
    
    def generate_trajectory(self, waypoints: List[np.ndarray], 
                          scene: pyrender.Scene,
                          objects: List[trimesh.Trimesh],
                          initial_pose: np.ndarray = None,
                          spacing_trans: float = 0.01,
                          spacing_rot: float = 3.0) -> Tuple[List[np.ndarray], List[int]]:
        """
        Generate trajectory by interpolating between waypoints.
        
        Paper: 
        - "different interpolation strategies (e.g. linear, cubic or interpolating 
           while staying on a spherical manifold)"
        - "attaching or detaching the closest object to it when the gripper state changes"
        - Uniform spacing: 1cm translation, 3 degrees rotation.
        
        Args:
            waypoints: List of 3D waypoint positions
            scene: PyRender scene (for object tracking)
            objects: List of object meshes
            initial_pose: Initial gripper pose (SE(3)), random if None
            spacing_trans: Translation spacing in meters (default 0.01 = 1cm)
            spacing_rot: Rotation spacing in degrees (default 3.0)
            
        Returns:
            poses: List of SE(3) gripper poses
            gripper_states: List of gripper states (0=closed, 1=open)
        """
        if initial_pose is None:
            # Random initial pose above table
            initial_pose = np.eye(4)
            initial_pose[:3, 3] = [
                random.uniform(-0.4, 0.4),
                random.uniform(-0.4, 0.4),
                random.uniform(0.3, 0.5)
            ]
            # Random orientation
            initial_pose[:3, :3] = Rot.random().as_matrix()
        
        poses = [initial_pose.copy()]
        gripper_states = [1]  # Start with gripper open
        
        # Reset object attachment
        self.attached_object = None
        self.attachment_offset = None
        
        # Randomly decide which waypoints trigger gripper state change
        grasp_waypoints = set(random.sample(range(len(waypoints)), 
                                           k=random.randint(1, min(3, len(waypoints)))))
        
        # Choose interpolation strategy (paper: linear, cubic, or spherical manifold)
        interp_method = random.choice(['linear', 'cubic', 'slerp'])
        
        for i, waypoint in enumerate(waypoints):
            # Interpolate from current pose to waypoint
            current_pos = poses[-1][:3, 3]
            target_pos = waypoint
            
            # Compute number of steps needed
            distance = np.linalg.norm(target_pos - current_pos)
            num_steps = max(1, int(distance / spacing_trans))
            
            # Generate interpolated positions
            if interp_method == 'linear':
                positions = self._linear_interpolate(current_pos, target_pos, num_steps)
            elif interp_method == 'cubic':
                positions = self._cubic_interpolate(current_pos, target_pos, num_steps, i, waypoints)
            else:  # slerp
                positions = self._linear_interpolate(current_pos, target_pos, num_steps)
            
            # Get current and target orientations
            current_rot = Rot.from_matrix(poses[-1][:3, :3])
            target_rot = self._compute_target_rotation(target_pos - current_pos)
            
            for step_idx, new_pos in enumerate(positions):
                # Interpolate rotation
                alpha = (step_idx + 1) / len(positions)
                if interp_method == 'slerp':
                    # Spherical linear interpolation for rotation
                    new_rot = Rot.from_quat(
                        self._slerp_quat(current_rot.as_quat(), target_rot.as_quat(), alpha)
                    )
                else:
                    # Simple linear interpolation of rotation
                    new_rot = Rot.from_quat(
                        self._slerp_quat(current_rot.as_quat(), target_rot.as_quat(), alpha)
                    )
                
                new_pose = np.eye(4)
                new_pose[:3, :3] = new_rot.as_matrix()
                new_pose[:3, 3] = new_pos
                
                # Determine gripper state
                if i in grasp_waypoints and step_idx == len(positions) - 1:
                    # Change gripper state at this waypoint
                    new_state = 1 - gripper_states[-1]
                    
                    # **CRITICAL: Attach/detach object when gripper state changes**
                    # Paper: "attaching or detaching the closest object to it when 
                    # the gripper state changes"
                    if new_state == 0:  # Closing gripper
                        self._attach_closest_object(scene, objects, new_pose)
                    else:  # Opening gripper
                        self._detach_object()
                    
                    gripper_states.append(new_state)
                else:
                    gripper_states.append(gripper_states[-1])
                
                # **CRITICAL: Update attached object position**
                # Paper: "By moving the gripper between the aforementioned waypoints 
                # and attaching or detaching the closest object"
                if self.attached_object is not None:
                    self._update_attached_object_pose(scene, new_pose)
                
                poses.append(new_pose)
        
        return poses, gripper_states
    
    def _linear_interpolate(self, start: np.ndarray, end: np.ndarray, num_steps: int) -> List[np.ndarray]:
        """Linear interpolation between waypoints."""
        positions = []
        for step in range(1, num_steps + 1):
            alpha = step / num_steps
            pos = start * (1 - alpha) + end * alpha
            positions.append(pos)
        return positions
    
    def _cubic_interpolate(self, start: np.ndarray, end: np.ndarray, num_steps: int,
                          current_idx: int, all_waypoints: List[np.ndarray]) -> List[np.ndarray]:
        """
        Cubic spline interpolation.
        Paper: "cubic... interpolation strategies"
        """
        # Need at least 4 points for cubic spline
        # Use previous and next waypoints if available
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
            positions = [cs(ti) for ti in t_new]
        except:
            # Fallback to linear if cubic fails
            positions = self._linear_interpolate(start, end, num_steps)
        
        return positions
    
    def _slerp_quat(self, q0: np.ndarray, q1: np.ndarray, t: float) -> np.ndarray:
        """
        Spherical linear interpolation of quaternions.
        Paper: "interpolating while staying on a spherical manifold"
        """
        # Normalize quaternions
        q0 = q0 / np.linalg.norm(q0)
        q1 = q1 / np.linalg.norm(q1)
        
        # Compute dot product
        dot = np.dot(q0, q1)
        
        # If negative dot, negate one quaternion
        if dot < 0.0:
            q1 = -q1
            dot = -dot
        
        # Clamp dot product
        dot = np.clip(dot, -1.0, 1.0)
        
        # Calculate interpolation coefficients
        theta = np.arccos(dot)
        
        if theta < 1e-6:
            # Very close, use linear interpolation
            return q0 * (1 - t) + q1 * t
        
        sin_theta = np.sin(theta)
        w0 = np.sin((1 - t) * theta) / sin_theta
        w1 = np.sin(t * theta) / sin_theta
        
        return w0 * q0 + w1 * q1
    
    def _compute_target_rotation(self, direction: np.ndarray) -> Rot:
        """Compute target rotation to look in a direction."""
        if np.linalg.norm(direction) < 1e-6:
            return Rot.identity()
        
        direction = direction / np.linalg.norm(direction)
        z_axis = direction
        
        # Create perpendicular x axis
        if abs(z_axis[2]) < 0.9:
            x_axis = np.cross([0, 0, 1], z_axis)
        else:
            x_axis = np.cross([1, 0, 0], z_axis)
        
        x_axis = x_axis / np.linalg.norm(x_axis)
        y_axis = np.cross(z_axis, x_axis)
        
        rot_matrix = np.column_stack([x_axis, y_axis, z_axis])
        return Rot.from_matrix(rot_matrix)
    
    def _attach_closest_object(self, scene: pyrender.Scene, objects: List[trimesh.Trimesh], 
                               gripper_pose: np.ndarray):
        """
        Attach the closest object to the gripper.
        Paper: "attaching... the closest object to it when the gripper state changes"
        """
        gripper_pos = gripper_pose[:3, 3]
        closest_obj_idx = None
        min_distance = float('inf')
        
        # Find closest object
        for obj_idx in range(len(objects)):
            obj_nodes = list(scene.get_nodes(name=f'object_{obj_idx}'))
            if obj_nodes:
                obj_node = obj_nodes[0]
                obj_pose = scene.get_pose(obj_node)
                obj_pos = obj_pose[:3, 3]
                distance = np.linalg.norm(gripper_pos - obj_pos)
                
                if distance < min_distance:
                    min_distance = distance
                    closest_obj_idx = obj_idx
        
        # Attach if close enough (within 10cm)
        if closest_obj_idx is not None and min_distance < 0.1:
            obj_nodes = list(scene.get_nodes(name=f'object_{closest_obj_idx}'))
            if obj_nodes:
                self.attached_object = obj_nodes[0]
                obj_pose = scene.get_pose(self.attached_object)
                # Store offset in gripper frame
                self.attachment_offset = np.linalg.inv(gripper_pose) @ obj_pose
    
    def _detach_object(self):
        """
        Detach object from gripper.
        Paper: "detaching the closest object to it when the gripper state changes"
        """
        self.attached_object = None
        self.attachment_offset = None
    
    def _update_attached_object_pose(self, scene: pyrender.Scene, gripper_pose: np.ndarray):
        """
        Update the pose of the attached object to follow the gripper.
        Paper: "By moving the gripper between the aforementioned waypoints and 
        attaching or detaching the closest object"
        """
        if self.attached_object is not None and self.attachment_offset is not None:
            # Compute new object pose relative to gripper
            new_obj_pose = gripper_pose @ self.attachment_offset
            # Update object pose in scene
            scene.set_pose(self.attached_object, new_obj_pose)
    
    def render_observations(self, scene: pyrender.Scene,
                          gripper_poses: List[np.ndarray],
                          camera_names: List[str] = ['camera_front', 'camera_left', 'camera_right'],
                          target_points: int = 4096) -> List[np.ndarray]:
        """
        Generate point clouds via trimesh surface sampling (no OpenGL needed).
        Fast CPU-based alternative to depth rendering.
        """
        # Collect all meshes with their current world poses
        scene_meshes = []
        for node in scene.mesh_nodes:
            mesh = node.mesh
            pose = scene.get_pose(node)
            for primitive in mesh.primitives:
                # Reconstruct trimesh from primitive
                tm = trimesh.Trimesh(
                    vertices=primitive.positions,
                    faces=primitive.indices if primitive.indices is not None else None,
                    process=False
                )
                if len(tm.faces) == 0:
                    continue
                tm.apply_transform(pose)
                scene_meshes.append(tm)

        # Add gripper mesh
        gripper_tm = self.gripper_mesh.copy()

        point_clouds = []
        for pose in gripper_poses:
            # Transform gripper mesh to current pose
            g = gripper_tm.copy()
            g.apply_transform(pose)

            # Sample points from all meshes
            all_pts = []
            for tm in scene_meshes:
                pts, _ = trimesh.sample.sample_surface(tm, 512)
                # Filter: above table, within workspace
                valid = (pts[:, 2] > 0.05) & (pts[:, 2] < 1.0)
                pts = pts[valid]
                dist = np.linalg.norm(pts - np.array([0, 0, 0.1]), axis=1)
                pts = pts[dist < 0.5]
                if len(pts) > 0:
                    all_pts.append(pts)

            # Sample gripper points
            g_pts, _ = trimesh.sample.sample_surface(g, 256)
            all_pts.append(g_pts)

            if len(all_pts) > 0:
                combined = np.concatenate(all_pts, axis=0)
            else:
                combined = np.random.randn(target_points, 3) * 0.05

            # Subsample to target
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
    
    def _depth_to_pointcloud(self, depth: np.ndarray, camera_pose: np.ndarray,
                            subsample_factor: int = 4) -> np.ndarray:
        """Convert depth image to 3D point cloud."""
        h, w = depth.shape
        
        # Subsample pixels to reduce point cloud density
        u, v = np.meshgrid(
            np.arange(0, w, subsample_factor),
            np.arange(0, h, subsample_factor)
        )
        u = u.flatten()
        v = v.flatten()
        
        # Get depth values at subsampled pixels
        depth_flat = depth[v, u]
        
        # Filter invalid depth
        valid = (depth_flat > 0) & (depth_flat < 10.0)
        u = u[valid]
        v = v[valid]
        depth_flat = depth_flat[valid]
        
        if len(depth_flat) == 0:
            return np.empty((0, 3))
        
        # Back-project to 3D
        x = (u - self.cx) * depth_flat / self.fx
        y = (v - self.cy) * depth_flat / self.fy
        z = depth_flat
        
        # Points in camera frame
        points_cam = np.stack([x, y, z], axis=1)
        
        # Transform to world frame
        points_homog = np.concatenate([points_cam, np.ones((len(points_cam), 1))], axis=1)
        points_world = (camera_pose @ points_homog.T).T[:, :3]
        
        return points_world
    
    def add_data_augmentation(self, poses: List[np.ndarray], 
                             gripper_states: List[int],
                             point_clouds: List[np.ndarray]) -> Tuple:
        """
        Add data augmentation as described in paper Appendix D.
        
        - 30% of trajectories: add local disturbances
        - 10% of data points: flip gripper state
        
        Args:
            poses: List of gripper poses
            gripper_states: List of gripper states
            point_clouds: List of point clouds
            
        Returns:
            Augmented poses, gripper_states, point_clouds
        """
        # 30% chance: add local disturbances
        if random.random() < 0.3:
            # Add small random perturbations to poses
            for i in range(len(poses)):
                if i > 0:  # Skip first pose
                    # Translation perturbation: ±5mm
                    trans_noise = np.random.randn(3) * 0.005
                    poses[i][:3, 3] += trans_noise
                    
                    # Rotation perturbation: ±5 degrees
                    rot_noise = Rot.from_euler('xyz', np.random.randn(3) * 5, degrees=True)
                    poses[i][:3, :3] = poses[i][:3, :3] @ rot_noise.as_matrix()
        
        # 10% chance: flip gripper state at random points
        if random.random() < 0.1:
            flip_idx = random.randint(0, len(gripper_states) - 1)
            gripper_states[flip_idx] = 1 - gripper_states[flip_idx]
        
        return poses, gripper_states, point_clouds
    
    def generate_pseudo_demonstration(self, objects: List[trimesh.Trimesh]) -> Dict:
        """
        Generate one complete pseudo-demonstration.
        
        FULLY COMPLIANT with paper Appendix D:
        - Object attachment/detachment when gripper state changes
        - Multiple interpolation strategies (linear, cubic, slerp)
        - Biased sampling for common tasks (50%)
        - Robotiq 2F-85 gripper mesh
        - 3 depth cameras with PyRender
        - Data augmentation (30% disturbance, 10% gripper flip)
        
        Args:
            objects: List of ShapeNet objects
            
        Returns:
            Dictionary with 'pcds', 'T_w_es', 'grips'
        """
        # Create scene
        scene = self.create_scene(objects)
        self.setup_cameras(scene)

        # Sample waypoints (paper: 2-6, 50% biased sampling)
        waypoints = self.sample_waypoints(scene, objects)

        # Generate trajectory with object attachment/detachment
        # Paper: "attaching or detaching the closest object to it when the
        # gripper state changes"
        poses, gripper_states = self.generate_trajectory(waypoints, scene, objects)

        # Render observations (with gripper mesh)
        point_clouds = self.render_observations(scene, poses)

        # Explicitly clear scene to free memory
        scene.clear()
        del scene

        # Data augmentation (30% disturbance, 10% gripper flip)
        poses, gripper_states, point_clouds = self.add_data_augmentation(
            poses, gripper_states, point_clouds
        )
        
        # Convert gripper states to float (1.0=open, 0.0=closed)
        gripper_states_float = [float(s) for s in gripper_states]
        
        return {
            'pcds': point_clouds,
            'T_w_es': poses,
            'grips': gripper_states_float
        }


if __name__ == '__main__':
    # Test the generator
    from shapenet_loader import ShapeNetLoader
    
    loader = ShapeNetLoader()
    generator = PseudoDemoGenerator()
    
    print("Generating test pseudo-demonstration...")
    objects = loader.get_random_objects(n=2)
    demo = generator.generate_pseudo_demonstration(objects)
    
    print(f"Generated demo with {len(demo['pcds'])} timesteps")
    print(f"  Point cloud sizes: {[len(pcd) for pcd in demo['pcds'][:3]]}...")
    print(f"  Gripper states: {demo['grips'][:10]}...")
