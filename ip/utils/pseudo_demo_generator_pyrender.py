"""
Pseudo-Demonstration Generator using PyRender for depth rendering.
Strictly follows paper Appendix D:
  "We record gripper poses and segmented point cloud observations
   using PyRender and three simulated depth cameras."
"""
import os
import numpy as np
from typing import List, Dict

# CRITICAL: Force EGL platform BEFORE importing PyRender
os.environ['PYOPENGL_PLATFORM'] = 'egl'
os.environ['DISPLAY'] = ''  # Clear DISPLAY to avoid X11 interference

# Import PyRender (will automatically use EGL platform from environment)
import pyrender

from ip.utils.pseudo_demo_generator import PseudoDemoGenerator


class PseudoDemoGeneratorPyrender(PseudoDemoGenerator):
    """
    Overrides render_observations() to use PyRender depth cameras
    instead of trimesh surface sampling.
    """

    def __init__(self, image_width=640, image_height=480):
        super().__init__(image_width, image_height)
        # Standard depth camera intrinsics
        self.fx = 525.0
        self.fy = 525.0
        self.cx = image_width / 2.0
        self.cy = image_height / 2.0

        print("✓ PseudoDemoGeneratorPyrender: Using EGL platform")

        # 单实例复用渲染器，避免多线程 EGL Context 竞态
        self.renderer = pyrender.OffscreenRenderer(
            viewport_width=self.image_width,
            viewport_height=self.image_height
        )
        print("✓ OffscreenRenderer 初始化完成（单实例复用模式）")

    def setup_cameras(self, scene: Dict):
        """3 fixed cameras: front, left_shoulder, right_shoulder."""
        scene['camera_poses'] = [
            self._lookat([0.0,  0.0,  0.8], [0.0, 0.0, 0.0]),
            self._lookat([-0.5, 0.3,  0.8], [0.0, 0.0, 0.0]),
            self._lookat([0.5, -0.3,  0.8], [0.0, 0.0, 0.0]),
        ]

    def _lookat(self, eye, target, up=None):
        """Camera-to-world matrix for pyrender (OpenGL: camera looks down -Z)."""
        if up is None:
            up = [0, 1, 0]
        eye = np.array(eye, dtype=float)
        target = np.array(target, dtype=float)
        up = np.array(up, dtype=float)
        forward = target - eye
        forward /= np.linalg.norm(forward)
        right = np.cross(forward, up)
        if np.linalg.norm(right) < 1e-6:
            up = np.array([1, 0, 0], dtype=float)
            right = np.cross(forward, up)
        right /= np.linalg.norm(right)
        up = np.cross(right, forward)
        pose = np.eye(4)
        pose[:3, 0] = right
        pose[:3, 1] = up
        pose[:3, 2] = -forward  # OpenGL convention
        pose[:3, 3] = eye
        return pose

    def render_observations(self, scene: Dict,
                            gripper_poses: List[np.ndarray],
                            target_points: int = 2048) -> List[np.ndarray]:
        """
        Render depth from 3 cameras per timestep, back-project to point cloud.
        Paper: spacing 1cm/3deg, 3 cameras, no wrist camera.
        """
        try:
            import pyrender
        except ImportError:
            raise ImportError(
                "pyrender not installed. Run: pip install pyrender\n"
                "Also set: export PYOPENGL_PLATFORM=egl"
            )

        point_clouds = []
        for gripper_pose in gripper_poses:
            all_pts = []
            for cam_pose in scene['camera_poses']:
                pts = self._render_depth_pointcloud(scene, gripper_pose, cam_pose)
                if len(pts) > 0:
                    all_pts.append(pts)

            combined = np.concatenate(all_pts, axis=0) if all_pts else np.zeros((target_points, 3))

            # Subsample to target_points
            if len(combined) >= target_points:
                idx = np.random.choice(len(combined), target_points, replace=False)
            else:
                idx = np.random.choice(len(combined), target_points, replace=True)
            combined = combined[idx]

            # Transform to gripper frame
            gripper_inv = np.linalg.inv(gripper_pose)
            homog = np.concatenate([combined, np.ones((len(combined), 1))], axis=1)
            combined = (gripper_inv @ homog.T).T[:, :3]
            point_clouds.append(combined)

        return point_clouds

    def _render_depth_pointcloud(self, scene: Dict, gripper_pose: np.ndarray,
                                 cam_pose: np.ndarray) -> np.ndarray:
        """Render one depth image and back-project to world-frame 3D points."""
        import pyrender

        pr_scene = pyrender.Scene(bg_color=[0, 0, 0, 0], ambient_light=[0.5, 0.5, 0.5])

        # Add scene objects
        for obj_info in scene['objects']:
            mesh = obj_info['mesh'].copy()
            mesh.apply_transform(obj_info['pose'])
            try:
                pr_scene.add(pyrender.Mesh.from_trimesh(mesh, smooth=False))
            except Exception:
                pass

        # # Add gripper
        # gripper = self.gripper_mesh.copy()
        # gripper.apply_transform(gripper_pose)
        # try:
        #     pr_scene.add(pyrender.Mesh.from_trimesh(gripper, smooth=False))
        # except Exception:
        #     pass

        # Add camera
        camera = pyrender.IntrinsicsCamera(
            fx=self.fx, fy=self.fy,
            cx=self.cx, cy=self.cy,
            znear=0.01, zfar=5.0
        )
        pr_scene.add(camera, pose=cam_pose)

        # Render depth only
        # 使用单实例复用渲染器（已在 __init__ 中初始化）
        try:
            depth = self.renderer.render(pr_scene, flags=pyrender.RenderFlags.DEPTH_ONLY)
        finally:
            # 渲染器复用，不在此处删除（由 __del__ 统一管理）
            pass

        # Back-project to camera-frame 3D
        valid = (depth > 0.01) & (depth < 3.0)
        v, u = np.where(valid)
        if len(v) == 0:
            return np.zeros((0, 3))
        z = depth[valid]
        x = (u - self.cx) * z / self.fx
        y = (v - self.cy) * z / self.fy
        pts_cam = np.stack([x, y, z], axis=1)

        # Transform to world frame
        homog = np.concatenate([pts_cam, np.ones((len(pts_cam), 1))], axis=1)
        return (cam_pose @ homog.T).T[:, :3]

    def __del__(self):
        """垃圾回收时安全释放渲染器"""
        if hasattr(self, "renderer"):
            try:
                self.renderer.delete()
                print("✓ OffscreenRenderer 已释放")
            except Exception as e:
                print(f"警告: 释放渲染器时出错: {e}")

