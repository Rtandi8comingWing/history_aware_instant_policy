"""
可视化伪演示数据

这个脚本生成并可视化训练用的伪数据，帮助理解数据生成的效果。

功能：
1. 生成伪演示数据
2. 可视化点云（3D）
3. 可视化夹爪轨迹
4. 显示夹爪开/闭状态
5. 显示任务类型和插值方法
6. 保存可视化结果

使用方法：
    python visualize_pseudo_data.py
    
    # 可选参数
    python visualize_pseudo_data.py --num_demos 5 --save_dir ./visualizations
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import argparse
import os
from pathlib import Path
import sys

# 配置中文字体
matplotlib.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'Liberation Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

# 添加项目路径
sys.path.append(str(Path(__file__).parent))

from ip.utils.pseudo_demo_generator import PseudoDemoGenerator
from ip.utils.shapenet_loader import ShapeNetLoader


class PseudoDataVisualizer:
    """可视化伪演示数据"""
    
    def __init__(self, save_dir='./visualizations'):
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"💾 可视化结果将保存到: {self.save_dir}")
        
    def visualize_single_demo(self, demo_data, demo_idx=0, show_every_n=5):
        """
        可视化单个演示
        
        Args:
            demo_data: 演示数据字典 {'pcds', 'T_w_es', 'grips'}
            demo_idx: 演示索引
            show_every_n: 每N帧显示一次（避免太密集）
        """
        pcds = demo_data['pcds']
        poses = demo_data['T_w_es']
        grips = demo_data['grips']
        
        num_frames = len(poses)
        print(f"\n📊 演示 {demo_idx} 统计:")
        print(f"  - 总帧数: {num_frames}")
        print(f"  - 点云数量: {len(pcds)}")
        print(f"  - 夹爪状态变化: {len(set(grips))} 种状态")
        print(f"  - 夹爪开启帧: {sum(grips)} / {len(grips)}")
        print(f"  - 夹爪关闭帧: {len(grips) - sum(grips)} / {len(grips)}")
        
        # 创建大图：2行2列
        fig = plt.figure(figsize=(16, 12))
        
        # 1. Point cloud visualization (middle frame)
        ax1 = fig.add_subplot(2, 2, 1, projection='3d')
        self._plot_pointcloud(ax1, pcds[len(pcds)//2], poses[len(poses)//2], 
                             title=f"Point Cloud (Frame {len(pcds)//2}/{num_frames})")
        
        # 2. Trajectory visualization
        ax2 = fig.add_subplot(2, 2, 2, projection='3d')
        self._plot_trajectory(ax2, poses, grips, title="Gripper Trajectory")
        
        # 3. Gripper state timeline
        ax3 = fig.add_subplot(2, 2, 3)
        self._plot_gripper_states(ax3, grips, title="Gripper State")
        
        # 4. Position curves
        ax4 = fig.add_subplot(2, 2, 4)
        self._plot_position_curves(ax4, poses, title="Position")
        
        plt.suptitle(f'Pseudo-Demo Visualization #{demo_idx}', fontsize=16, fontweight='bold')
        plt.tight_layout()
        
        # 保存
        save_path = self.save_dir / f'demo_{demo_idx}_overview.png'
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"✅ 保存概览图: {save_path}")
        plt.close()
        
        # 创建动画式的多帧可视化
        self._create_trajectory_animation(demo_data, demo_idx, show_every_n)
        
    def _plot_pointcloud(self, ax, pcd, pose, title="Point Cloud"):
        """Plot point cloud"""
        if len(pcd) == 0:
            print("Warning: Empty point cloud")
            return
            
        # Downsample for display
        if len(pcd) > 2000:
            indices = np.random.choice(len(pcd), 2000, replace=False)
            pcd = pcd[indices]
        
        # Plot point cloud
        ax.scatter(pcd[:, 0], pcd[:, 1], pcd[:, 2], 
                  c=pcd[:, 2], cmap='viridis', s=1, alpha=0.6)
        
        # Plot gripper position
        gripper_pos = pose[:3, 3]
        ax.scatter(*gripper_pos, c='red', s=100, marker='o', 
                  label='Gripper', edgecolors='black', linewidths=2)
        
        # Plot gripper frame
        scale = 0.1
        colors = ['r', 'g', 'b']
        labels = ['X', 'Y', 'Z']
        for i, (color, label) in enumerate(zip(colors, labels)):
            axis = pose[:3, i] * scale
            ax.quiver(*gripper_pos, *axis, color=color, arrow_length_ratio=0.3,
                     linewidth=2, alpha=0.8)
        
        ax.set_xlabel('X (m)')
        ax.set_ylabel('Y (m)')
        ax.set_zlabel('Z (m)')
        ax.set_title(title)
        ax.legend()
        
        # Set axis limits
        ax.set_xlim([-0.5, 0.5])
        ax.set_ylim([-0.5, 0.5])
        ax.set_zlim([0, 0.6])
        
    def _plot_trajectory(self, ax, poses, grips, title="Trajectory"):
        """Plot gripper trajectory"""
        positions = np.array([pose[:3, 3] for pose in poses])
        
        # Color by gripper state
        colors = ['green' if g > 0.5 else 'red' for g in grips]
        
        # Plot trajectory line
        ax.plot(positions[:, 0], positions[:, 1], positions[:, 2], 
               'b-', alpha=0.3, linewidth=1, label='Path')
        
        # Plot keypoints
        ax.scatter(positions[:, 0], positions[:, 1], positions[:, 2],
                  c=colors, s=20, alpha=0.6)
        
        # Mark start and end
        ax.scatter(*positions[0], c='lime', s=200, marker='*', 
                  edgecolors='black', linewidths=2, label='Start', zorder=5)
        ax.scatter(*positions[-1], c='orange', s=200, marker='s',
                  edgecolors='black', linewidths=2, label='End', zorder=5)
        
        # Mark state change points
        for i in range(1, len(grips)):
            if grips[i] != grips[i-1]:
                ax.scatter(*positions[i], c='yellow', s=100, marker='D',
                         edgecolors='black', linewidths=1.5, zorder=4)
        
        ax.set_xlabel('X (m)')
        ax.set_ylabel('Y (m)')
        ax.set_zlabel('Z (m)')
        ax.set_title(title)
        ax.legend()
        
        # Set axis limits
        ax.set_xlim([-0.5, 0.5])
        ax.set_ylim([-0.5, 0.5])
        ax.set_zlim([0, 0.6])
        
    def _plot_gripper_states(self, ax, grips, title="Gripper State"):
        """Plot gripper state timeline"""
        frames = range(len(grips))
        
        # Plot states
        ax.fill_between(frames, 0, grips, alpha=0.3, color='green', label='Open')
        ax.fill_between(frames, grips, 1, alpha=0.3, color='red', label='Closed')
        ax.plot(frames, grips, 'b-', linewidth=2)
        
        # Mark state changes
        for i in range(1, len(grips)):
            if grips[i] != grips[i-1]:
                ax.axvline(x=i, color='orange', linestyle='--', linewidth=1.5, alpha=0.7)
                state_text = 'Open' if grips[i] > 0.5 else 'Close'
                ax.text(i, 0.5, state_text, rotation=90, 
                       verticalalignment='center', fontsize=9)
        
        ax.set_xlabel('Frame')
        ax.set_ylabel('Gripper State (1=Open, 0=Closed)')
        ax.set_title(title)
        ax.set_ylim([-0.1, 1.1])
        ax.grid(True, alpha=0.3)
        ax.legend()
        
    def _plot_position_curves(self, ax, poses, title="Position"):
        """Plot position over time"""
        positions = np.array([pose[:3, 3] for pose in poses])
        frames = range(len(positions))
        
        ax.plot(frames, positions[:, 0], 'r-', label='X', linewidth=2)
        ax.plot(frames, positions[:, 1], 'g-', label='Y', linewidth=2)
        ax.plot(frames, positions[:, 2], 'b-', label='Z', linewidth=2)
        
        ax.set_xlabel('Frame')
        ax.set_ylabel('Position (m)')
        ax.set_title(title)
        ax.grid(True, alpha=0.3)
        ax.legend()
        
    def _create_trajectory_animation(self, demo_data, demo_idx, show_every_n):
        """创建轨迹动画（多帧图片）"""
        pcds = demo_data['pcds']
        poses = demo_data['T_w_es']
        grips = demo_data['grips']
        
        print(f"\n🎬 生成动画帧...")
        
        # 选择关键帧
        frame_indices = list(range(0, len(poses), show_every_n))
        if frame_indices[-1] != len(poses) - 1:
            frame_indices.append(len(poses) - 1)
        
        for idx, frame_idx in enumerate(frame_indices):
            fig = plt.figure(figsize=(14, 10))
            
            # Left: Point cloud
            ax1 = fig.add_subplot(1, 2, 1, projection='3d')
            self._plot_pointcloud(ax1, pcds[frame_idx], poses[frame_idx],
                                 title=f"Point Cloud (Frame {frame_idx}/{len(poses)})")
            
            # Right: Trajectory (up to current frame)
            ax2 = fig.add_subplot(1, 2, 2, projection='3d')
            current_poses = poses[:frame_idx+1]
            current_grips = grips[:frame_idx+1]
            self._plot_trajectory(ax2, current_poses, current_grips,
                                title=f"Trajectory Progress ({frame_idx}/{len(poses)})")
            
            # Add state info
            grip_state = "Open (1.0)" if grips[frame_idx] > 0.5 else "Closed (0.0)"
            fig.suptitle(f'Demo #{demo_idx} - Frame {frame_idx} - Gripper: {grip_state}',
                        fontsize=14, fontweight='bold')
            
            plt.tight_layout()
            
            # 保存
            save_path = self.save_dir / f'demo_{demo_idx}_frame_{frame_idx:04d}.png'
            plt.savefig(save_path, dpi=100)
            plt.close()
            
            if idx % 5 == 0:
                print(f"  - 已生成 {idx+1}/{len(frame_indices)} 帧")
        
        print(f"✅ 完成！共生成 {len(frame_indices)} 帧")
        
    def create_comparison_plot(self, all_demos):
        """Create comparison plot of multiple demos"""
        n_demos = len(all_demos)
        fig = plt.figure(figsize=(18, 4 * n_demos))
        
        for i, demo_data in enumerate(all_demos):
            poses = demo_data['T_w_es']
            grips = demo_data['grips']
            
            # Trajectory
            ax1 = fig.add_subplot(n_demos, 3, i*3 + 1, projection='3d')
            self._plot_trajectory(ax1, poses, grips, title=f"Demo {i} - Trajectory")
            
            # Gripper state
            ax2 = fig.add_subplot(n_demos, 3, i*3 + 2)
            self._plot_gripper_states(ax2, grips, title=f"Demo {i} - State")
            
            # Position curves
            ax3 = fig.add_subplot(n_demos, 3, i*3 + 3)
            self._plot_position_curves(ax3, poses, title=f"Demo {i} - Position")
        
        plt.suptitle('Multiple Demos Comparison', fontsize=16, fontweight='bold')
        plt.tight_layout()
        
        save_path = self.save_dir / 'comparison.png'
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"\n✅ 保存对比图: {save_path}")
        plt.close()


def main():
    parser = argparse.ArgumentParser(description='可视化伪演示数据')
    parser.add_argument('--num_demos', type=int, default=3,
                       help='生成的演示数量 (默认: 3)')
    parser.add_argument('--save_dir', type=str, default='./visualizations',
                       help='保存目录 (默认: ./visualizations)')
    parser.add_argument('--show_every_n', type=int, default=10,
                       help='动画每N帧显示一次 (默认: 10)')
    parser.add_argument('--shapenet_path', type=str, 
                       default='/media/tianyi/Tiantian/tianyiStudy/DataSets/ShapeNetCore.v2',
                       help='ShapeNet数据集路径')
    
    args = parser.parse_args()
    
    print("="*80)
    print("🎨 伪演示数据可视化工具")
    print("="*80)
    
    # 初始化
    print(f"\n📂 加载 ShapeNet 数据集: {args.shapenet_path}")
    try:
        loader = ShapeNetLoader(args.shapenet_path)
        print(f"✅ 成功加载 ShapeNet")
    except Exception as e:
        print(f"❌ 加载 ShapeNet 失败: {e}")
        print("💡 提示：请确保 ShapeNet 数据集路径正确")
        return
    
    print(f"\n🎭 初始化伪数据生成器...")
    generator = PseudoDemoGenerator()
    print("✅ 生成器初始化完成")
    
    print(f"\n🎬 生成 {args.num_demos} 个伪演示...")
    all_demos = []
    for i in range(args.num_demos):
        print(f"\n--- 生成演示 {i+1}/{args.num_demos} ---")
        
        # 随机采样物体
        objects = loader.get_random_objects(n=2)
        print(f"  📦 物体1: {len(objects[0].vertices)} 顶点")
        print(f"  📦 物体2: {len(objects[1].vertices)} 顶点")
        
        # 生成演示
        demo_data = generator.generate_pseudo_demonstration(objects)
        all_demos.append(demo_data)
        
        print(f"  ✅ 生成完成:")
        print(f"     - 轨迹长度: {len(demo_data['T_w_es'])} 帧")
        print(f"     - 点云数: {len(demo_data['pcds'])}")
        print(f"     - 夹爪状态变化: {len(set(demo_data['grips']))} 种")
    
    # 可视化
    print(f"\n🎨 开始可视化...")
    visualizer = PseudoDataVisualizer(save_dir=args.save_dir)
    
    for i, demo_data in enumerate(all_demos):
        print(f"\n--- 可视化演示 {i+1}/{args.num_demos} ---")
        visualizer.visualize_single_demo(demo_data, demo_idx=i, 
                                        show_every_n=args.show_every_n)
    
    # 创建对比图
    print(f"\n📊 创建多演示对比图...")
    visualizer.create_comparison_plot(all_demos)
    
    print("\n" + "="*80)
    print("✅ 可视化完成！")
    print(f"📁 结果保存在: {args.save_dir}")
    print("="*80)
    
    # 提供查看提示
    print(f"\n💡 查看结果:")
    print(f"   概览图: {args.save_dir}/demo_*_overview.png")
    print(f"   动画帧: {args.save_dir}/demo_*_frame_*.png")
    print(f"   对比图: {args.save_dir}/comparison.png")
    
    print(f"\n💡 生成视频（可选）:")
    print(f"   ffmpeg -framerate 10 -pattern_type glob -i '{args.save_dir}/demo_0_frame_*.png' \\")
    print(f"          -c:v libx264 -pix_fmt yuv420p {args.save_dir}/demo_0.mp4")


if __name__ == '__main__':
    main()
