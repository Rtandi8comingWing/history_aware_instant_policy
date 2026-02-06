# 数据准备指南

## 训练数据结构

训练 Instant Policy 需要以下数据集：

```
data/
├── train/          # 训练集（主数据）
├── val/            # 验证集（用于监控训练）
└── test/           # 测试集（可选，用于评估）
```

---

## 🚀 快速设置

### 方式 1: 使用测试生成的数据（已完成）✅

```bash
# 训练集
data/pseudo_test/       # ~100 样本

# 验证集（已自动创建）
data/val/               # 10 样本
```

**立即可用**：
```bash
python ip/train.py \
    --run_name=train_test \
    --data_path_train=./data/pseudo_test \
    --data_path_val=./data/val \
    --batch_size=8 \
    --record=1
```

---

### 方式 2: 使用 ShapeNet 伪数据（推荐）

#### 2a. 批量预生成

```bash
# 1. 生成训练数据（100K 任务，~30GB）
python generate_pseudo_data.py \
    --num_tasks=100000 \
    --output_dir=./data/pseudo_train \
    --num_workers=8

# 2. 生成验证数据（1K 任务，~300MB）
python generate_pseudo_data.py \
    --num_tasks=1000 \
    --output_dir=./data/pseudo_val \
    --num_workers=4

# 3. 训练
python ip/train.py \
    --run_name=train_shapenet \
    --data_path_train=./data/pseudo_train \
    --data_path_val=./data/pseudo_val \
    --batch_size=16 \
    --record=1
```

#### 2b. 连续生成（论文方式）

```bash
# 训练时动态生成数据，无需预生成
python train_with_pseudo.py \
    --run_name=train_continuous \
    --num_pseudo_samples=700000 \
    --buffer_size=1000 \
    --num_generator_threads=4 \
    --batch_size=16 \
    --record=1

# 需要单独准备验证集（小规模即可）
python generate_pseudo_data.py \
    --num_tasks=1000 \
    --output_dir=./data/pseudo_val \
    --num_workers=4
```

---

## 📊 数据集大小建议

### 测试/调试

| 用途 | 训练集 | 验证集 | 说明 |
|-----|-------|-------|------|
| 快速测试 | 100 样本 | 10 样本 | 验证代码运行 |
| 小规模实验 | 1K 任务 | 100 任务 | 初步验证想法 |

### 正式训练

| 用途 | 训练集 | 验证集 | 说明 |
|-----|-------|-------|------|
| 小规模 | 10K 任务 | 1K 任务 | 有限资源 |
| 中规模 | 50K 任务 | 2K 任务 | 平衡性能 |
| 完整训练 | 100K+ 任务 | 5K 任务 | 论文设置 |

**论文设置**：~700K 独特轨迹（连续生成）

---

## 🔧 数据格式

### 样本结构

每个 `.pt` 文件包含一个训练样本：

```python
import torch

data = torch.load('data/train/data_0.pt')

# 数据结构
data.pos_demos           # torch.Size([N, 3]) - 演示点云
data.graps_demos         # torch.Size([1, num_demos, T, 1]) - 演示夹持器状态
data.batch_demos         # torch.Size([N]) - 点云批次索引
data.pos_obs             # torch.Size([M, 3]) - 当前观察点云
data.batch_pos_obs       # torch.Size([M]) - 观察批次索引
data.current_grip        # torch.Size([1]) - 当前夹持器状态
data.demo_T_w_es         # torch.Size([1, num_demos, T, 4, 4]) - 演示姿态
data.T_w_e               # torch.Size([1, 4, 4]) - 当前姿态
data.actions             # torch.Size([1, H, 4, 4]) - 动作序列
data.actions_grip        # torch.Size([1, H]) - 夹持器动作序列
```

---

## 📂 数据管理技巧

### 1. 创建符号链接（节省空间）

```bash
# 如果有多个实验需要相同的验证集
ln -s /path/to/shared/val ./data/val
```

### 2. 清理旧数据

```bash
# 删除测试数据
rm -rf ./data/test_pseudo ./data/test_pseudo_batch

# 只保留需要的
ls ./data/
# pseudo_test/  - 训练用
# val/          - 验证用
```

### 3. 检查数据完整性

```bash
# 统计样本数量
echo "训练集: $(ls ./data/pseudo_test/*.pt | wc -l) 样本"
echo "验证集: $(ls ./data/val/*.pt | wc -l) 样本"

# 验证数据可读性
python -c "
import torch
import glob

for f in glob.glob('./data/val/*.pt')[:3]:
    data = torch.load(f)
    print(f'{f}: pos_obs={data.pos_obs.shape}, actions={data.actions.shape}')
"
```

---

## ⚠️ 常见问题

### Q1: 验证集应该多大？

**A**: 
- **最小**：10 样本（仅检查代码运行）
- **推荐**：100-1000 样本（可靠监控）
- **理想**：1000-5000 样本（完整评估）

验证集太小：可能不能准确反映性能  
验证集太大：验证时间过长

### Q2: 可以用训练集作为验证集吗？

**A**: 不推荐，但用于快速测试可以：

```bash
python ip/train.py \
    --data_path_train=./data/pseudo_test \
    --data_path_val=./data/pseudo_test \  # 同一个
    --batch_size=8
```

**问题**：会导致过拟合的假象。

### Q3: 如何从大数据集中采样验证集？

**A**: 
```bash
# 从训练集中随机采样 1000 个作为验证集
mkdir -p ./data/val
ls ./data/pseudo_train/*.pt | shuf | head -1000 | xargs -I {} cp {} ./data/val/

# 或者使用 Python
python << 'EOF'
import random
import shutil
import glob
import os

train_files = glob.glob('./data/pseudo_train/*.pt')
val_files = random.sample(train_files, min(1000, len(train_files)))

os.makedirs('./data/val', exist_ok=True)
for f in val_files:
    shutil.copy(f, './data/val/')
print(f"Created validation set with {len(val_files)} samples")
EOF
```

### Q4: 需要专门的测试集吗？

**A**: 取决于需求：

- **训练和调参**：训练集 + 验证集 足够
- **论文评估**：需要独立的测试集
- **RLBench 评估**：使用实际 RLBench 环境测试（`deploy_sim.py`）

---

## 🎯 不同场景的数据准备

### 场景 1: 快速原型（5分钟设置）

```bash
# 使用已有的测试数据
python ip/train.py \
    --data_path_train=./data/pseudo_test \
    --data_path_val=./data/val \
    --batch_size=8
```

**优点**：立即开始  
**缺点**：数据量小，性能有限

---

### 场景 2: 中规模实验（1-2小时设置）

```bash
# 生成 10K 训练 + 1K 验证
python generate_pseudo_data.py --num_tasks=10000 --output_dir=./data/train --num_workers=8
python generate_pseudo_data.py --num_tasks=1000 --output_dir=./data/val --num_workers=4

python ip/train.py \
    --data_path_train=./data/train \
    --data_path_val=./data/val \
    --batch_size=16 \
    --record=1
```

**优点**：合理的数据量  
**缺点**：需要等待生成

---

### 场景 3: 完整训练（论文设置，1-2天设置）

```bash
# 方式 A: 大规模预生成
python generate_pseudo_data.py --num_tasks=100000 --output_dir=./data/train --num_workers=16
python generate_pseudo_data.py --num_tasks=5000 --output_dir=./data/val --num_workers=8

python ip/train.py \
    --data_path_train=./data/train \
    --data_path_val=./data/val \
    --batch_size=16 \
    --record=1 \
    --use_wandb=1

# 方式 B: 连续生成（推荐）
python generate_pseudo_data.py --num_tasks=5000 --output_dir=./data/val --num_workers=8

python train_with_pseudo.py \
    --num_pseudo_samples=700000 \
    --buffer_size=2000 \
    --num_generator_threads=8 \
    --data_path_val=./data/val \
    --batch_size=16 \
    --record=1 \
    --use_wandb=1
```

**优点**：论文级别性能  
**缺点**：训练时间长（~5天）

---

### 场景 4: 真实数据微调

```bash
# 1. 收集您自己的演示数据（RLBench/真实机器人）
# 2. 转换为正确格式（参考 ip/prepare_data.py）
# 3. 微调

python ip/train.py \
    --fine_tune=1 \
    --model_path=./checkpoints \
    --model_name=model.pt \
    --data_path_train=./data/my_robot_demos \
    --data_path_val=./data/my_robot_val \
    --batch_size=8 \
    --run_name=finetune_my_robot \
    --record=1
```

---

## 📋 检查清单

在开始训练前确认：

- [ ] 训练集存在且包含 .pt 文件
- [ ] 验证集存在且包含 .pt 文件
- [ ] 至少 10 个验证样本
- [ ] 数据文件可以正常加载
- [ ] 有足够的磁盘空间（~300MB/1K 任务）

快速验证命令：

```bash
# 检查数据
ls ./data/pseudo_test/*.pt | wc -l  # 训练集大小
ls ./data/val/*.pt | wc -l          # 验证集大小

# 验证加载
python -c "import torch; d=torch.load('./data/val/data_0.pt'); print('OK:', d.actions.shape)"
```

---

## 🎉 现在可以训练了！

您的数据已准备好：

```bash
python ip/train.py \
    --run_name=my_first_train \
    --data_path_train=./data/pseudo_test \
    --data_path_val=./data/val \
    --batch_size=8 \
    --record=1
```

**预期输出**：
```
Warning: scene_encoder.pt not found at ./checkpoints/scene_encoder.pt
Training from scratch without pre-trained scene encoder
[开始训练...]
```

祝训练顺利！🚀
