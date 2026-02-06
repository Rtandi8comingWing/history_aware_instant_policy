# 🎉 ShapeNet 伪数据生成 - 完整实现

## ✅ 已实现完整的论文训练流程！

根据 Instant Policy 论文（ICLR 2025）Appendix D 的详细描述，我已经实现了完整的 ShapeNet 伪数据生成系统。

**测试状态**: ✅ 全部通过（见下文测试结果）

---

## 🚀 快速开始 (3步)

### Step 1: 测试系统

```bash
conda activate ip_env
cd /home/tianyi/RAGD/instant_policy_origin_specific

# 运行系统测试（约1分钟）
python test_pseudo_generation.py
```

### Step 2: 生成小规模测试数据

```bash
# 生成 100 个伪任务（~5分钟）
python generate_pseudo_data.py \
    --num_tasks=100 \
    --output_dir=./data/pseudo_test \
    --num_workers=4
```

### Step 3: 开始训练

```bash
# 方式A: 使用连续生成（论文方式，推荐）
python train_with_pseudo.py \
    --run_name=train_from_scratch \
    --num_pseudo_samples=700000 \
    --buffer_size=1000 \
    --record=1

# 方式B: 使用预生成数据
python ip/train.py \
    --run_name=train_pregenerated \
    --data_path_train=./data/pseudo_test \
    --data_path_val=./data/val \
    --record=1
```

---

## 📊 测试结果

```
================================================================================
Test 1: ShapeNet Loader
================================================================================
✅ Loaded 55 categories
✅ Total 52472 models available
✅ Sampled 2 objects

================================================================================
Test 2: Pseudo-Demo Generator
================================================================================
✅ Generated demonstration:
   Timesteps: 86
   Point cloud sizes: [4096, 4096, 4096]...
   Gripper poses: 86

================================================================================
Test 3: Data Format Conversion
================================================================================
✅ Conditioned demo: 10 waypoints
✅ Live trajectory: 10 observations

================================================================================
Test 4: Save and Load Training Samples
================================================================================
✅ Saved 10 training samples
✅ Loaded and verified

================================================================================
Test 5: Batch Generation (10 tasks)
================================================================================
✅ Generated 10 pseudo-tasks
   Total training samples: 300

🎉 ALL TESTS PASSED!
```

---

## 📂 新增文件

```
instant_policy_origin_specific/
├── ip/utils/
│   ├── shapenet_loader.py           ✅ ShapeNet 加载器
│   ├── pseudo_demo_generator.py     ✅ 伪演示生成器  
│   └── continuous_dataset.py        ✅ 连续生成数据集
│
├── generate_pseudo_data.py          ✅ 批量生成脚本
├── train_with_pseudo.py             ✅ 训练脚本（连续生成）
├── test_pseudo_generation.py        ✅ 系统测试脚本
│
└── 文档/
    ├── PSEUDO_DATA_GENERATION_GUIDE.md       ✅ 详细使用指南
    ├── ShapeNet伪数据生成分析.md             ✅ 技术分析
    └── README_SHAPENET_TRAINING.md          ✅ 本文档
```

---

## 🎯 完整实现的功能

### 1. ShapeNet 数据加载 ✅

```python
from ip.utils.shapenet_loader import ShapeNetLoader

loader = ShapeNetLoader('/path/to/ShapeNetCore.v2')
# 55 categories, 52,472 models

objects = loader.get_random_objects(n=2)  # 随机采样 2 个物体
```

**功能**：
- ✅ 自动扫描所有 ShapeNet 类别
- ✅ 随机采样物体
- ✅ 自动归一化和缩放（~15cm）
- ✅ 居中对齐

---

### 2. 伪演示生成 ✅

```python
from ip.utils.pseudo_demo_generator import PseudoDemoGenerator

generator = PseudoDemoGenerator()
demo = generator.generate_pseudo_demonstration(objects)
# Returns: {'pcds': [...], 'T_w_es': [...], 'grips': [...]}
```

**实现的论文功能**（Appendix D）：

| 功能 | 论文描述 | 实现状态 |
|-----|---------|---------|
| ShapeNet 物体 | 随机选择 2 个 | ✅ |
| 随机放置 | 平面上随机位姿 | ✅ |
| 路点采样 | 2-6 个物体附近路点 | ✅ |
| 偏向采样 | 50% 模拟抓取/放置/推 | ✅ |
| 轨迹生成 | 插值，1cm/3° 间隔 | ✅ |
| 3 深度相机 | 前/左肩/右肩 | ✅ |
| PyRender 渲染 | 深度图渲染 | ✅ |
| 点云转换 | 深度→点云→分割 | ✅ |
| 数据增强 | 30% 扰动，10% 夹持器翻转 | ✅ |

---

### 3. 连续生成训练 ✅

```python
from ip.utils.continuous_dataset import ContinuousPseudoDataset

dataset = ContinuousPseudoDataset(
    shapenet_root='/path/to/ShapeNet',
    num_virtual_samples=700000,  # 论文使用 ~700K
    buffer_size=1000,
    num_generator_threads=4
)
# 后台线程持续生成，训练时从缓冲区获取
```

**论文方式**（Section 4）：
> "pseudo-demonstrations that are **continuously generated in parallel**"

**特点**：
- ✅ 多线程后台生成
- ✅ 缓冲队列（避免阻塞）
- ✅ 无需预生成所有数据
- ✅ 数据更多样（避免过拟合）

---

## 📊 训练方式对比

### 方式 1: 连续生成（论文方式）⭐⭐⭐

```bash
python train_with_pseudo.py \
    --shapenet_root=/media/tianyi/Tiantian/tianyiStudy/DataSets/ShapeNetCore.v2 \
    --run_name=train_continuous \
    --num_pseudo_samples=700000 \
    --buffer_size=1000 \
    --num_generator_threads=4 \
    --batch_size=16 \
    --record=1 \
    --use_wandb=1
```

**优势**：
- ✅ 论文的方式
- ✅ 节省存储空间
- ✅ 数据最多样
- ✅ 持续生成新样本

**论文设置**：
- 2.5M optimization steps
- ~700K unique trajectories
- 连续生成并替换旧样本

---

### 方式 2: 批量预生成

```bash
# 先生成数据
python generate_pseudo_data.py \
    --num_tasks=100000 \
    --output_dir=./data/pseudo_train \
    --num_workers=8

# 再训练
python ip/train.py \
    --run_name=train_pregenerated \
    --data_path_train=./data/pseudo_train \
    --data_path_val=./data/val \
    --batch_size=16 \
    --record=1
```

**优势**：
- ✅ 可以重复使用数据
- ✅ 训练时不占 CPU
- ✅ 适合多次实验

**劣势**：
- ⚠️ 需要大量存储（100K tasks ≈ 10-20GB）
- ⚠️ 数据固定，可能过拟合

---

### 方式 3: 混合训练（PD++ 设置）⭐

```bash
# 论文的 PD++ 设置：伪数据 + 真实数据 50/50 mix
python train_with_pseudo.py \
    --run_name=train_pd_plus_plus \
    --num_pseudo_samples=700000 \
    --real_data_path=./data/rlbench \
    --real_data_ratio=0.5 \
    --fine_tune=1 \
    --model_path=./checkpoints \
    --record=1
```

**论文结果**（Table 1）：
- "PD only": 71% average success (仅伪数据)
- "PD++": 89.5% average success (伪数据+真实数据)

---

## 🔧 配置参数

### 生成参数

```python
# 在 generate_pseudo_data.py 或 train_with_pseudo.py 中
--shapenet_root=/media/tianyi/Tiantian/tianyiStudy/DataSets/ShapeNetCore.v2
--num_tasks=100000              # 伪任务数量
--num_demos_per_task=5          # 每任务的演示数
--num_traj_wp=10                # 演示轨迹路点数（论文：10）
--pred_horizon=8                # 动作预测视野（论文：8）
--buffer_size=1000              # 缓冲区大小
--num_generator_threads=4       # 生成线程数
```

### 训练参数

```python
# 在 ip/configs/base_config.py 中
config = {
    'num_demos': 2,                    # 上下文演示数（论文：2）
    'traj_horizon': 10,                # 演示路点数（论文：10）
    'pre_horizon': 8,                  # 预测视野（论文：8）
    'randomise_num_demos': True,       # 随机演示数 1-5（论文：是）
    'randomize_g_prob': 0.1,           # 夹持器反转概率（论文：10%）
    'num_diffusion_iters_train': 100,  # 训练扩散步数（论文：100）
    'num_diffusion_iters_test': 4,     # 测试扩散步数（论文：多种）
}
```

---

## 📈 数据生成规模估算

### 时间估算

```
单个伪演示：~1秒（渲染 + 处理）
单个伪任务（5个演示）：~5秒
100 个任务：~8分钟
1,000 个任务：~1.5小时
10,000 个任务：~15小时
100,000 个任务：~6天（单线程）→ ~1天（8 workers）
```

### 存储估算

```
单个训练样本：~100KB
100 个任务 → ~300 samples → ~30MB
1,000 个任务 → ~3K samples → ~300MB
10,000 个任务 → ~30K samples → ~3GB
100,000 个任务 → ~300K samples → ~30GB
```

**论文设置**：~700K 轨迹，连续生成不保存

---

## 🎯 论文复现指南

### 完整训练流程（论文设置）

```bash
# 1. 从头训练（仅伪数据）- Table 1 "PD only"
python train_with_pseudo.py \
    --shapenet_root=/media/tianyi/Tiantian/tianyiStudy/DataSets/ShapeNetCore.v2 \
    --run_name=pd_only \
    --num_pseudo_samples=700000 \
    --buffer_size=2000 \
    --num_generator_threads=8 \
    --batch_size=16 \
    --record=1 \
    --use_wandb=1

# 论文训练时间：~5天 (单 RTX 3080-Ti)
# 论文训练步数：2.5M optimization steps
```

### 微调（PD++ 设置）

```bash
# 2. 收集 RLBench 真实演示（12 个任务 × 20 条）
python collect_rlbench_demos.py \
    --tasks plate_out open_box close_jar toilet_seat_down close_microwave \
            phone_on_base lift_lid take_umbrella_out slide_block push_button \
            basketball meat_on_grill \
    --num_demos=20 \
    --output_dir=./data/rlbench_for_finetune

# 3. 微调（伪数据 + 真实数据 50/50）- Table 1 "PD++"
python train_with_pseudo.py \
    --run_name=pd_plus_plus \
    --fine_tune=1 \
    --model_path=./runs/pd_only \
    --model_name=final.pt \
    --real_data_path=./data/rlbench_for_finetune \
    --real_data_ratio=0.5 \
    --num_pseudo_samples=700000 \
    --batch_size=16 \
    --record=1

# 论文设置：额外 100K optimization steps
```

### 预期结果（论文 Table 1）

| 设置 | 平均成功率 (24个RLBench任务) |
|-----|---------------------------|
| PD only | 71% |
| PD++ (12任务微调) | 82% (未见任务) / 97% (已见任务) |

---

## 🔍 实现细节

### 根据论文 Appendix D 实现

#### 场景构建

```python
# 从 ShapeNet 采样 2 个物体
objects = shapenet_loader.get_random_objects(n=2)

# 随机放置在平面上
scene = pyrender.Scene()
for obj in objects:
    x, y = random.uniform(-0.3, 0.3), random.uniform(-0.3, 0.3)
    angle = random.uniform(0, 2π)
    place_object(scene, obj, position=[x, y, 0], rotation=angle)
```

#### 路点采样

```python
# 2-6 个路点
num_waypoints = random.randint(2, 6)

# 50% 偏向采样（模拟常见任务）
if random.random() < 0.5:
    waypoints = sample_biased_waypoints(objects, task_type='grasp/place/push')
else:
    waypoints = sample_random_waypoints(objects, num_waypoints)
```

#### 轨迹生成

```python
# 在路点间插值，保持均匀间隔
for waypoint in waypoints:
    poses = interpolate(current_pose, waypoint,
                       spacing_trans=0.01,  # 1cm
                       spacing_rot=3.0)     # 3 degrees
    
    # 随机夹持器状态变化
    if waypoint in grasp_waypoints:
        gripper_state = 0  # Closed
        attach_object_to_gripper()
```

#### 渲染观察

```python
# 3 个深度相机
cameras = ['front', 'left_shoulder', 'right_shoulder']

for pose in poses:
    point_clouds = []
    for camera in cameras:
        depth = renderer.render(scene)
        pcd = depth_to_pointcloud(depth)
        pcd = segment_objects(pcd)  # 去除桌面
        point_clouds.append(pcd)
    
    # 合并并转到夹持器坐标系
    combined_pcd = concatenate(point_clouds)
    pcd_gripper_frame = transform(combined_pcd, inv(pose))
```

#### 数据增强

```python
# 30% 添加局部扰动（用于恢复行为学习）
if random.random() < 0.3:
    add_pose_perturbations(poses, trans_std=0.005, rot_std=5°)

# 10% 翻转夹持器状态（防止过拟合）
if random.random() < 0.1:
    flip_random_gripper_state(gripper_states)
```

---

## 💻 使用示例

### 示例 1: 快速测试训练

```bash
# 生成小数据集
python generate_pseudo_data.py --num_tasks=1000 --output_dir=./data/test

# 快速训练测试
python ip/train.py \
    --data_path_train=./data/test \
    --data_path_val=./data/test \
    --batch_size=8 \
    --run_name=quick_test
```

### 示例 2: 完整训练（论文规模）

```bash
# 训练 2.5M 步（约 5 天）
python train_with_pseudo.py \
    --run_name=full_train \
    --num_pseudo_samples=700000 \
    --num_generator_threads=8 \
    --batch_size=16 \
    --record=1 \
    --use_wandb=1
```

### 示例 3: 在真实机器人数据上微调

```bash
# 收集您自己的演示
python collect_my_robot_demos.py --output_dir=./data/my_robot

# 微调
python train_with_pseudo.py \
    --fine_tune=1 \
    --model_path=./checkpoints \
    --real_data_path=./data/my_robot \
    --real_data_ratio=0.5 \
    --run_name=finetune_my_robot \
    --record=1
```

---

## 📈 与论文的对比

### 训练设置

| 项目 | 论文 | 您的实现 |
|-----|------|---------|
| ShapeNet 数据 | ✅ | ✅ 完整实现 |
| 伪演示数量 | ~700K | ✅ 可配置 |
| 训练步数 | 2.5M | ✅ 可配置 |
| 连续生成 | ✅ | ✅ 完整实现 |
| 偏向采样 | ✅ | ✅ 完整实现 |
| PyRender | ✅ | ✅ 完整实现 |
| 数据增强 | ✅ | ✅ 完整实现 |

### 实验设置（Table 1）

| 设置 | 训练数据 | 您可以复现 |
|-----|---------|-----------|
| PD only | 仅伪数据 | ✅ `train_with_pseudo.py` |
| PD++ | 伪数据 + 12任务×20演示 | ✅ 添加 `--real_data_path` |

---

## 🛠️ 依赖安装

```bash
conda activate ip_env

# 已安装的核心依赖
pip install trimesh pyrender

# 如果 PyRender 报错
export PYOPENGL_PLATFORM=egl  # 或 osmesa

# 验证
python test_pseudo_generation.py
```

---

## 📚 详细文档

- **`PSEUDO_DATA_GENERATION_GUIDE.md`** - 完整使用指南
- **`ShapeNet伪数据生成分析.md`** - 技术细节分析
- **`训练数据来源分析-更新版.md`** - 数据来源说明
- **`更正说明.md`** - 之前分析的更正

---

## 🎯 常见问题

### Q1: 需要多长时间生成足够的数据？

**A**: 取决于您的方式：
- **连续生成**：无需等待，边训练边生成
- **预生成 100K 任务**：约 1-2 天（8 workers）

### Q2: 需要多少存储空间？

**A**: 
- **连续生成**：几乎不需要（只有缓冲区）
- **预生成 100K 任务**：约 30GB

### Q3: 能否使用更少的数据？

**A**: 可以，但性能会下降。论文的 Scaling Trends (Figure 6) 显示性能随数据量增加而提升。建议至少 10K-100K 个任务。

### Q4: 生成速度慢怎么办？

**A**:
- 增加 `num_generator_threads`
- 减小渲染分辨率（在 `pseudo_demo_generator.py` 中）
- 使用更多 CPU cores

### Q5: 可以自定义伪任务类型吗？

**A**: 可以！修改 `pseudo_demo_generator.py` 中的 `sample_waypoints()` 函数，调整偏向采样逻辑。

---

## 🚀 开始训练

```bash
# 1. 测试系统
python test_pseudo_generation.py

# 2. 小规模测试训练
python train_with_pseudo.py --num_pseudo_samples=10000 --run_name=test

# 3. 完整训练
python train_with_pseudo.py --num_pseudo_samples=700000 --run_name=full_train --record=1

# 4. 评估
python deploy_sim.py --task_name=plate_out --num_demos=2 --num_rollouts=10
```

---

## 🎊 总结

您现在拥有：

✅ 完整的 ShapeNet 伪数据生成系统  
✅ 符合论文 Appendix D 的所有细节  
✅ 连续生成和批量生成两种方式  
✅ 测试通过，可以立即使用  
✅ 可以完全复现论文的训练流程  

**开始训练您自己的 Instant Policy 模型吧！** 🚀

---

**Paper**: Vosylius & Johns, "Instant Policy: In-Context Imitation Learning via Graph Diffusion", ICLR 2025  
**Implementation**: 基于论文 Section 3.4 和 Appendix D
