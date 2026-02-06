# 验证集生成更新

## 更新概述

您提出了一个很好的建议！现在验证集会在数据准备阶段自动生成，而不是需要手动创建。

---

## ✅ 已更新的文件

### 1. `generate_pseudo_data.py` ⭐

**新增参数**:
```bash
--gen_val_set 1          # 是否生成验证集 [0, 1]，默认=1
--val_tasks 10           # 验证集任务数，默认=10
```

**新功能**:
- ✅ 自动生成训练集和验证集
- ✅ 验证集放在 `<output_dir>/../val/` 目录
- ✅ 默认生成 10 个验证任务（可配置）
- ✅ 生成完成后显示训练命令

### 2. `ip/train.py`

**更新**:
- ✅ 自动检测验证集是否存在
- ✅ 如果缺失，跳过验证并给出提示
- ✅ 训练器自动适配（有验证集才验证）

### 3. `train_with_pseudo.py`

**更新**:
- ✅ 自动检测验证集是否存在
- ✅ 如果缺失，跳过验证并给出提示
- ✅ 训练器自动适配（有验证集才验证）

---

## 🚀 使用方法

### 方法 1: 自动生成（推荐）⭐

```bash
# 生成训练集和验证集（一步完成）
python generate_pseudo_data.py \
    --num_tasks=100 \
    --output_dir=./data/pseudo_train \
    --gen_val_set=1 \
    --val_tasks=10
```

**输出**:
```
data/
├── pseudo_train/    (100 个任务的训练数据)
└── val/            (10 个任务的验证数据) ✅ 自动创建
```

**然后直接训练**:
```bash
python ip/train.py \
    --data_path_train=./data/pseudo_train \
    --data_path_val=./data/val \
    --record=1
```

---

### 方法 2: 只生成训练集

```bash
# 不生成验证集
python generate_pseudo_data.py \
    --num_tasks=100 \
    --output_dir=./data/pseudo_train \
    --gen_val_set=0
```

**训练时会自动跳过验证**:
```bash
python ip/train.py \
    --data_path_train=./data/pseudo_train \
    --record=1

# 输出:
# ⚠️  No validation data found, skipping validation
#    (You can generate validation set with: python generate_pseudo_data.py --val_tasks=10)
```

---

### 方法 3: 单独生成验证集

```bash
# 只生成验证集（如果之前忘记生成）
python generate_pseudo_data.py \
    --num_tasks=10 \
    --output_dir=./data/val
```

---

## 📊 完整示例

### 示例 1: 小规模测试

```bash
# 1. 生成数据（训练集 100 任务 + 验证集 10 任务）
python generate_pseudo_data.py \
    --num_tasks=100 \
    --val_tasks=10 \
    --output_dir=./data/test_train \
    --num_workers=4

# 2. 训练
python ip/train.py \
    --run_name=test_training \
    --data_path_train=./data/test_train \
    --data_path_val=./data/val \
    --batch_size=8 \
    --record=1
```

### 示例 2: 大规模训练

```bash
# 1. 生成大量数据
python generate_pseudo_data.py \
    --num_tasks=100000 \
    --val_tasks=100 \
    --output_dir=./data/pseudo_train \
    --num_workers=16

# 2. 训练
python ip/train.py \
    --run_name=full_train \
    --data_path_train=./data/pseudo_train \
    --data_path_val=./data/val \
    --batch_size=16 \
    --record=1
```

### 示例 3: 连续生成训练（无需预生成）

```bash
# 不需要预生成，训练时连续生成
python train_with_pseudo.py \
    --run_name=continuous_train \
    --num_pseudo_samples=10000 \
    --data_path_val=./data/val \
    --record=1

# 注意：验证集还是需要预先生成
```

---

## 🔍 验证集的重要性

### 为什么需要验证集？

1. **监控过拟合**: 查看训练损失 vs 验证损失
2. **早停**: 验证集性能不再提升时停止
3. **超参数调整**: 比较不同配置的泛化能力
4. **检查点选择**: 选择验证集性能最好的模型

### 验证集大小建议

| 训练集规模 | 验证集任务数 | 说明 |
|-----------|-------------|------|
| 100-1K 任务 | 10-20 | 快速测试 |
| 1K-10K 任务 | 50-100 | 中等规模 |
| 10K-100K 任务 | 100-500 | 大规模训练 |
| >100K 任务 | 500-1000 | 完整训练（论文规模） |

**经验法则**: 验证集约为训练集的 1-5%

---

## 🎯 默认行为

### 现在的默认行为（更新后）

```bash
# 默认会生成验证集
python generate_pseudo_data.py --num_tasks=100

# 等价于
python generate_pseudo_data.py \
    --num_tasks=100 \
    --gen_val_set=1 \
    --val_tasks=10
```

### 训练脚本的默认行为

```bash
# 如果验证集存在 → 使用验证
# 如果验证集不存在 → 跳过验证（不报错）
python ip/train.py \
    --data_path_train=./data/train \
    --data_path_val=./data/val
```

---

## 📝 输出示例

### 生成数据时的输出

```
================================================================================
Pseudo-Demonstration Generation for Instant Policy
================================================================================
ShapeNet root: /media/tianyi/Tiantian/tianyiStudy/DataSets/ShapeNetCore.v2
Output directory: ./data/pseudo_train
Number of pseudo-tasks: 100
Demos per task: 5
Trajectory waypoints: 10
Prediction horizon: 8
Parallel workers: 4
Validation set: ./data/val (10 tasks)     ✅ 新增显示
================================================================================

Initializing ShapeNet loader...
Loaded 55 categories with 52472 models

Generating 100 pseudo-tasks using 4 workers...
Workers: 100%|██████████████████████████| 4/4

================================================================================
Training Set Generation Complete!
================================================================================
Total pseudo-tasks generated: 100
Total training samples: 3000
Time elapsed: 120.5s (2.0 minutes)
Average time per task: 1.21s
Samples saved in: ./data/pseudo_train
================================================================================

================================================================================
Generating Validation Set...                    ✅ 新增部分
================================================================================
Generating 10 validation tasks...
Val tasks: 100%|████████████████████████| 10/10
✅ Validation set created: ./data/val
   Tasks: 10, Samples: 300
================================================================================

================================================================================
All Data Generated Successfully!
================================================================================
Training set: ./data/pseudo_train (3000 samples)
Validation set: ./data/val (300 samples)        ✅ 新增显示

You can now train with:
  python ip/train.py --data_path_train=./data/pseudo_train --data_path_val=./data/val --record=1
================================================================================
```

### 训练时的输出（无验证集）

```
Warning: scene_encoder.pt not found at ./checkpoints/scene_encoder.pt
Training from scratch without pre-trained scene encoder
⚠️  No validation data found, skipping validation
   (You can generate validation set with: python generate_pseudo_data.py --val_tasks=10)

(训练正常进行，只是跳过验证步骤)
```

---

## 🆚 对比

### 之前（手动创建）❌

```bash
# 1. 生成训练集
python generate_pseudo_data.py --num_tasks=100 --output_dir=./data/train

# 2. 手动复制创建验证集
mkdir -p ./data/val
cp ./data/train/data_{0..9}.pt ./data/val/

# 3. 训练
python ip/train.py --data_path_train=./data/train --data_path_val=./data/val
```

### 现在（自动生成）✅

```bash
# 1. 一步生成训练集和验证集
python generate_pseudo_data.py --num_tasks=100

# 2. 直接训练
python ip/train.py --data_path_train=./data/pseudo_train --data_path_val=./data/val
```

**节省步骤**: 从 3 步 → 2 步  
**减少错误**: 不会忘记创建验证集  
**更合理**: 验证集是独立生成的，不是训练集的子集

---

## 💡 最佳实践

### 1. 始终使用验证集

```bash
# ✅ 推荐
python generate_pseudo_data.py --num_tasks=1000 --val_tasks=50

# ❌ 不推荐（除非快速测试）
python generate_pseudo_data.py --num_tasks=1000 --gen_val_set=0
```

### 2. 验证集应该独立

- ✅ 生成脚本会创建独立的验证任务
- ❌ 不要从训练集中抽取验证集
- 原因：验证集应该测试泛化能力，而不是记忆能力

### 3. 验证集不要太小

```bash
# ❌ 太小（不稳定）
--val_tasks=5

# ✅ 合适
--val_tasks=10-50  # 小规模训练
--val_tasks=100+   # 大规模训练
```

---

## 🎉 总结

### 主要改进

1. ✅ **自动化**: 验证集自动生成，无需手动操作
2. ✅ **智能**: 训练脚本自动检测，缺失时跳过而不报错
3. ✅ **灵活**: 可以选择生成或不生成验证集
4. ✅ **完整**: 生成完成后显示完整的训练命令

### 向后兼容

- ✅ 默认行为生成验证集（更好的默认值）
- ✅ 可以禁用验证集生成（`--gen_val_set=0`）
- ✅ 训练脚本可以处理缺失验证集的情况

### 现在您可以

```bash
# 一个命令搞定数据生成
python generate_pseudo_data.py --num_tasks=100

# 直接开始训练
python ip/train.py \
    --data_path_train=./data/pseudo_train \
    --data_path_val=./data/val \
    --record=1
```

**更简单、更可靠、更符合最佳实践！** 🚀
