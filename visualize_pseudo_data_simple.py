"""
简化版伪数据可视化 - 快速预览

快速生成和查看单个伪演示，适合快速测试。

使用方法：
    python visualize_pseudo_data_simple.py
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import sys
from pathlib import Path

# 配置字体
matplotlib.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'Liberation Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

# 添加项目路径
sys.path.append(str(Path(__file__).parent))

from ip.utils.pseudo_demo_generator import PseudoDemoGenerator
from ip.utils.shapenet_loader import ShapeNetLoader


def visualize_demo_quick(demo_data, save_path=None):
    """Quick visualization of one demo"""
    pcds = demo_data['pcds']
    poses = demo_data['T_w_es']
    grips = demo_data['grips']
    
    # Create figure
    fig = plt.figure(figsize=(16, 5))
    
    # 1. Point cloud (middle frame)
    ax1 = fig.add_subplot(1, 3, 1, projection='3d')
    mid_frame = len(pcds) // 2
    pcd = pcds[mid_frame]
    
    # Downsample
    if len(pcd) > 2000:
        indices = np.random.choice(len(pcd), 2000, replace=False)
        pcd = pcd[indices]
    
    ax1.scatter(pcd[:, 0], pcd[:, 1], pcd[:, 2], 
               c=pcd[:, 2], cmap='viridis', s=1, alpha=0.6)
    
    # Gripper position
    gripper_pos = poses[mid_frame][:3, 3]
    ax1.scatter(*gripper_pos, c='red', s=100, marker='o', label='Gripper')
    
    ax1.set_xlabel('X (m)')
    ax1.set_ylabel('Y (m)')
    ax1.set_zlabel('Z (m)')
    ax1.set_title(f'Point Cloud (Frame {mid_frame}/{len(pcds)})')
    ax1.legend()
    ax1.set_xlim([-0.5, 0.5])
    ax1.set_ylim([-0.5, 0.5])
    ax1.set_zlim([0, 0.6])
    
    # 2. Trajectory
    ax2 = fig.add_subplot(1, 3, 2, projection='3d')
    positions = np.array([pose[:3, 3] for pose in poses])
    colors = ['green' if g > 0.5 else 'red' for g in grips]
    
    ax2.plot(positions[:, 0], positions[:, 1], positions[:, 2], 
            'b-', alpha=0.3, linewidth=1)
    ax2.scatter(positions[:, 0], positions[:, 1], positions[:, 2],
               c=colors, s=20, alpha=0.6)
    ax2.scatter(*positions[0], c='lime', s=200, marker='*', label='Start')
    ax2.scatter(*positions[-1], c='orange', s=200, marker='s', label='End')
    
    ax2.set_xlabel('X (m)')
    ax2.set_ylabel('Y (m)')
    ax2.set_zlabel('Z (m)')
    ax2.set_title('Gripper Trajectory')
    ax2.legend()
    ax2.set_xlim([-0.5, 0.5])
    ax2.set_ylim([-0.5, 0.5])
    ax2.set_zlim([0, 0.6])
    
    # 3. Gripper state
    ax3 = fig.add_subplot(1, 3, 3)
    frames = range(len(grips))
    ax3.fill_between(frames, 0, grips, alpha=0.3, color='green', label='Open')
    ax3.fill_between(frames, grips, 1, alpha=0.3, color='red', label='Closed')
    ax3.plot(frames, grips, 'b-', linewidth=2)
    
    ax3.set_xlabel('Frame')
    ax3.set_ylabel('Gripper State (1=Open, 0=Closed)')
    ax3.set_title('Gripper State Timeline')
    ax3.set_ylim([-0.1, 1.1])
    ax3.grid(True, alpha=0.3)
    ax3.legend()
    
    plt.suptitle(f'Pseudo-Demo Data - {len(poses)} Frames', fontsize=14, fontweight='bold')
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"✅ 保存到: {save_path}")
    else:
        plt.show()
    
    plt.close()


def main():
    print("="*60)
    print("🎨 快速可视化伪演示数据")
    print("="*60)
    
    # 初始化
    shapenet_path = '/media/tianyi/Tiantian/tianyiStudy/DataSets/ShapeNetCore.v2'
    
    print(f"\n📂 加载 ShapeNet...")
    try:
        loader = ShapeNetLoader(shapenet_path)
        print(f"✅ 成功")
    except Exception as e:
        print(f"❌ 失败: {e}")
        return
    
    print(f"\n🎭 初始化生成器...")
    generator = PseudoDemoGenerator()
    print("✅ 完成")
    
    print(f"\n🎬 生成伪演示...")
    objects = loader.get_random_objects(n=2)
    demo_data = generator.generate_pseudo_demonstration(objects)
    
    print(f"\n📊 演示信息:")
    print(f"  - 轨迹长度: {len(demo_data['T_w_es'])} 帧")
    print(f"  - 点云数量: {len(demo_data['pcds'])}")
    print(f"  - 夹爪开启帧: {sum(demo_data['grips'])}")
    print(f"  - 夹爪关闭帧: {len(demo_data['grips']) - sum(demo_data['grips'])}")
    
    print(f"\n🎨 可视化...")
    visualize_demo_quick(demo_data, save_path='./pseudo_demo_quick.png')
    
    print("\n" + "="*60)
    print("✅ 完成！查看 pseudo_demo_quick.png")
    print("="*60)


if __name__ == '__main__':
    main()
