# ShapeNet 伪数据生成使用指南

## 🎉 已实现功能

根据论文 Appendix D 的详细描述，我已经实现了完整的 ShapeNet 伪数据生成系统！

## 📂 新增文件

```
instant_policy_origin_specific/
├── ip/utils/
│   ├── shapenet_loader.py           # ShapeNet 数据集加载器
│   ├── pseudo_demo_generator.py     # 伪演示生成器
│   └── continuous_dataset.py        # 训练时连续生成数据集
├── generate_pseudo_data.py          # 批量生成伪数据
└── train_with_pseudo.py             # 使用伪数据训练
```

## 🚀 快速开始

### 方式 1: 批量预生成数据（推荐用于测试）

```bash
# 生成 1000 个伪任务（测试用）
python generate_pseudo_data.py \
    --shapenet_root=/media/tianyi/Tiantian/tianyiStudy/DataSets/ShapeNetCore.v2 \
    --output_dir=./data/pseudo_train \
    --num_tasks=1000 \
    --num_workers=4

# 生成大量数据（接近论文规模）
python generate_pseudo_data.py \
    --shapenet_root=/media/tianyi/Tiantian/tianyiStudy/DataSets/ShapeNetCore.v2 \
    --output_dir=./data/pseudo_train \
    --num_tasks=100000 \
    --num_workers=8
```

### 方式 2: 训练时连续生成（论文方式）⭐

```bash
# 从头训练（仅伪数据）
python train_with_pseudo.py \
    --shapenet_root=/media/tianyi/Tiantian/tianyiStudy/DataSets/ShapeNetCore.v2 \
    --run_name=train_from_scratch \
    --num_pseudo_samples=700000 \
    --buffer_size=1000 \
    --num_generator_threads=4 \
    --batch_size=16 \
    --record=1

# 微调（伪数据 + 真实数据，论文的 PD++ 设置）
python train_with_pseudo.py \
    --shapenet_root=/media/tianyi/Tiantian/tianyiStudy/DataSets/ShapeNetCore.v2 \
    --run_name=finetune_with_real \
    --fine_tune=1 \
    --model_path=./checkpoints \
    --real_data_path=./data/rlbench \
    --real_data_ratio=0.5 \
    --num_pseudo_samples=700000 \
    --batch_size=16 \
    --record=1
```

## 📊 实现细节

### 1. ShapeNet 数据加载 (`shapenet_loader.py`)

```python
from ip.utils.shapenet_loader import ShapeNetLoader

# 初始化加载器
loader = ShapeNetLoader(
    shapenet_root='/media/tianyi/Tiantian/tianyiStudy/DataSets/ShapeNetCore.v2'
)

# 随机采样物体
objects = loader.get_random_objects(n=2)  # 采样 2 个物体
```

**功能**：
- ✅ 加载所有 ShapeNet 类别
- ✅ 随机采样物体
- ✅ 自动归一化和缩放
- ✅ 缓存机制

### 2. 伪演示生成器 (`pseudo_demo_generator.py`)

```python
from ip.utils.pseudo_demo_generator import PseudoDemoGenerator

generator = PseudoDemoGenerator()

# 生成一个伪演示
demo = generator.generate_pseudo_demonstration(objects)
# 返回: {'pcds': [...], 'T_w_es': [...], 'grips': [...]}
```

**实现的功能**（论文 Appendix D）：
- ✅ 场景构建（物体随机放置）
- ✅ 3 个虚拟深度相机
- ✅ 路点采样（2-6 个路点）
- ✅ 偏向采样（50% 概率，模拟常见任务如抓取、放置、推）
- ✅ 轨迹生成（插值）
- ✅ PyRender 渲染点云
- ✅ 数据增强（30% 添加扰动，10% 翻转夹持器）

### 3. 连续数据集 (`continuous_dataset.py`)

```python
from ip.utils.continuous_dataset import ContinuousPseudoDataset

# 创建连续生成数据集
dataset = ContinuousPseudoDataset(
    shapenet_root='/path/to/ShapeNet',
    num_virtual_samples=700000,
    buffer_size=1000,
    num_generator_threads=4
)

# 后台线程持续生成数据
sample = dataset[0]  # 从缓冲区获取
```

**特点**：
- ✅ 后台多线程持续生成
- ✅ 缓冲队列预生成
- ✅ 无需预先生成所有数据
- ✅ 论文中的连续生成方式

## 🔧 参数说明

### 生成参数

| 参数 | 默认值 | 说明 | 论文值 |
|-----|-------|------|--------|
| `num_pseudo_samples` | 700000 | 虚拟数据集大小 | ~700K |
| `num_demos_per_task` | 5 | 每个伪任务的演示数 | - |
| `num_traj_wp` | 10 | 演示轨迹的路点数 | 10 |
| `pred_horizon` | 8 | 动作预测视野 | 8 |
| `buffer_size` | 1000 | 预生成缓冲区大小 | - |
| `num_generator_threads` | 4 | 后台生成线程数 | - |

### 场景参数（内置）

| 参数 | 值 | 说明 |
|-----|---|------|
| `num_objects` | 2 | 每个场景的物体数 |
| `num_waypoints` | 2-6 | 随机选择 |
| `num_cameras` | 3 | 深度相机数 |
| `spacing_trans` | 0.01m | 轨迹平移间隔（1cm） |
| `spacing_rot` | 3° | 轨迹旋转间隔 |

## 📝 生成流程

```
1. ShapeNet 物体采样
   └─> 随机选择 2 个物体

2. 场景构建
   └─> 在平面上随机放置物体
   └─> 添加 3 个相机

3. 路点采样
   └─> 50% 偏向采样（grasp/place/push）
   └─> 50% 完全随机
   └─> 2-6 个路点

4. 轨迹生成
   └─> 在路点间插值
   └─> 均匀间隔：1cm, 3°
   └─> 随机夹持器开合

5. 渲染观察
   └─> 3 个相机渲染深度图
   └─> 转换为点云
   └─> 简单分割（去除桌面）
   └─> 转到夹持器坐标系

6. 数据增强
   └─> 30% 添加局部扰动
   └─> 10% 翻转夹持器状态

7. 保存/缓冲
   └─> 转换为训练格式
   └─> 保存或加入缓冲队列
```

## 🧪 测试生成

```bash
# 测试 ShapeNet 加载器
python -m ip.utils.shapenet_loader

# 测试伪演示生成
python -m ip.utils.pseudo_demo_generator

# 测试连续数据集
python -m ip.utils.continuous_dataset
```

## 📈 训练对比

### 论文设置

```
训练数据：~700K 伪演示（连续生成）
训练步数：2.5M optimization steps
微调（PD++）：
  - 伪数据 + 12个RLBench任务（各20条）
  - 50/50 混合
  - 额外 100K steps
```

### 您的设置

```bash
# 仅伪数据（PD only）
python train_with_pseudo.py \
    --run_name=pd_only \
    --num_pseudo_samples=700000

# 伪数据 + 真实数据（PD++）
python train_with_pseudo.py \
    --run_name=pd_plus \
    --num_pseudo_samples=700000 \
    --real_data_path=./data/rlbench \
    --real_data_ratio=0.5  # 50/50 mix
```

## ⚡ 性能优化

### 1. 并行生成

```bash
# 增加生成线程（如果CPU核心足够）
python train_with_pseudo.py \
    --num_generator_threads=8 \
    --buffer_size=2000
```

### 2. 预生成 vs 连续生成

**预生成优势**：
- ✅ 可以重复使用
- ✅ 训练时不占CPU

**连续生成优势**（论文方式）：
- ✅ 不需要大量存储空间
- ✅ 数据更多样（每次都是新的）
- ✅ 避免过拟合

### 3. 批量预生成大数据集

```bash
# 生成 10 万个任务（可能需要数天）
python generate_pseudo_data.py \
    --num_tasks=100000 \
    --num_workers=16 \
    --output_dir=/path/to/large/storage
```

## 🔍 验证生成的数据

```python
import torch
from ip.utils.data_proc import *

# 加载一个样本
data = torch.load('./data/pseudo_train/data_0.pt')

print(f"Demo point clouds: {data.pos_demos.shape}")
print(f"Current obs: {data.pos_obs.shape}")
print(f"Actions: {data.actions.shape}")
print(f"Gripper actions: {data.actions_grip.shape}")

# 可视化（可选）
import open3d as o3d
pcd = o3d.geometry.PointCloud()
pcd.points = o3d.utility.Vector3dVector(data.pos_obs.numpy())
o3d.visualization.draw_geometries([pcd])
```

## 📊 数据量估算

### 存储需求

```
每个样本：~100KB（取决于点云密度）
1000 个样本：~100MB
10000 个样本：~1GB
100000 个样本：~10GB
```

### 生成时间

```
单个样本：~0.5-2秒（取决于渲染复杂度）
1000 个样本：~15-30分钟
10000 个样本：~3-5小时
100000 个样本：~2-3天（16 workers）
```

**推荐**：使用连续生成方式，无需预生成所有数据！

## 🆚 与论文的对比

| 特性 | 论文 | 实现状态 |
|-----|------|---------|
| ShapeNet 物体 | ✅ | ✅ 完整实现 |
| 随机路点采样 | ✅ | ✅ 完整实现 |
| 偏向采样 | ✅ | ✅ 完整实现 |
| 3 个深度相机 | ✅ | ✅ 完整实现 |
| PyRender 渲染 | ✅ | ✅ 完整实现 |
| 数据增强 | ✅ | ✅ 完整实现 |
| 连续生成 | ✅ | ✅ 完整实现 |
| 训练集成 | ✅ | ✅ 完整实现 |

## 🐛 常见问题

### Q1: PyRender 初始化失败

```bash
# 安装依赖
conda install -c conda-forge pyrender
pip install pyrender trimesh

# 如果还有问题，需要设置 DISPLAY
export PYOPENGL_PLATFORM=egl  # 或 osmesa
```

### Q2: ShapeNet 路径错误

```python
# 检查路径
import os
assert os.path.exists('/media/tianyi/Tiantian/tianyiStudy/DataSets/ShapeNetCore.v2')
```

### Q3: 内存不足

```bash
# 减少缓冲区大小和线程数
python train_with_pseudo.py \
    --buffer_size=100 \
    --num_generator_threads=2
```

### Q4: 生成速度慢

- 减少渲染分辨率（在 `pseudo_demo_generator.py` 中修改）
- 增加生成线程数
- 使用预生成方式

## 📚 下一步

1. **测试生成**：
   ```bash
   python -m ip.utils.pseudo_demo_generator
   ```

2. **小规模训练**：
   ```bash
   python train_with_pseudo.py --num_pseudo_samples=10000
   ```

3. **完整训练**：
   ```bash
   python train_with_pseudo.py --num_pseudo_samples=700000 --record=1
   ```

4. **微调**：
   ```bash
   python train_with_pseudo.py --fine_tune=1 --real_data_path=./data/rlbench
   ```

## 🎯 总结

您现在拥有完整的 ShapeNet 伪数据生成系统，可以：

- ✅ 按照论文方式生成无限伪数据
- ✅ 训练时连续生成（论文方式）
- ✅ 批量预生成大数据集
- ✅ 混合真实数据微调
- ✅ 完全复现论文的训练流程

**开始训练吧！** 🚀
