# Checkpoint 管理指南

本文档详细说明了 Instant Policy 项目中 checkpoint 的保存、加载和管理逻辑。

---

## 📋 目录

- [保存逻辑](#保存逻辑)
- [训练方式对比](#训练方式对比)
- [加载和推理](#加载和推理)
- [文件结构](#文件结构)
- [最佳实践](#最佳实践)

---

## 🔄 保存逻辑

### 核心保存机制

Checkpoint 保存在 `ip/models/diffusion.py` 中实现：

```python
def save_model(self, path, save_compiled=False):
    """保存模型检查点"""
    self.trainer.save_checkpoint(path)
    
    if save_compiled:
        repair_checkpoint(path, save_path=path)
        if self.model.compiled_model is not None:
            path_compiled = path.replace('.pt', '_compiled.pt')
            self.trainer.save_checkpoint(path_compiled)
```

### 自动保存时机

#### 1. 定期保存（训练中）

```python
def on_train_batch_end(self, outputs, batch, batch_idx):
    """每 save_every 步保存一次"""
    if self.global_step % self.save_every == 0 and self.record:
        self.save_model(f'{self.save_dir}/{self.global_step}.pt', save_compiled=False)
```

**配置**：
- `save_every`: 默认 100,000 步保存一次
- 文件命名：`{save_dir}/{global_step}.pt`
- 例如：`./runs/my_train/100000.pt`, `./runs/my_train/200000.pt`

#### 2. 最佳模型保存（验证时）

```python
def on_validation_epoch_end(self):
    """验证后保存最佳模型"""
    if self.record:
        self.save_model(f'{self.save_dir}/best.pt')
```

**条件**：
- 仅当有验证集时触发
- 自动跟踪最低验证损失
- 文件：`{save_dir}/best.pt`

#### 3. 最终模型保存（训练结束）

```python
# ip/train.py
if record:
    model.save_model(f'{save_dir}/last.pt')
```

**文件**：`{save_dir}/last.pt`

---

## 📊 训练方式对比

### 方式 1: 使用预生成数据 (`ip/train.py`)

```bash
python ip/train.py \
    --run_name=my_train \
    --data_path_train=./data/pseudo_train \
    --data_path_val=./data/val \
    --record=1
```

**保存机制**：

| 时机 | 文件名 | 说明 |
|-----|--------|------|
| 每 100K 步 | `./runs/my_train/100000.pt` | 定期保存 |
| 验证后（最佳） | `./runs/my_train/best.pt` | 最佳验证损失 |
| 训练结束 | `./runs/my_train/last.pt` | 最终模型 |

**特点**：
- ✅ 保存逻辑与标准训练完全相同
- ✅ 支持断点续训（从任何 checkpoint 恢复）
- ✅ 自动跟踪最佳模型

---

### 方式 2: 连续生成数据 (`train_with_pseudo.py`)

```bash
python train_with_pseudo.py \
    --run_name=my_continuous_train \
    --num_pseudo_samples=700000 \
    --record=1
```

**保存机制**：

| 时机 | 文件名 | 说明 |
|-----|--------|------|
| 每 100K 步 | `./runs/my_continuous_train/100000.pt` | 定期保存 |
| 验证后（最佳） | `./runs/my_continuous_train/best.pt` | 最佳验证损失（如果有验证集） |
| 训练结束 | `./runs/my_continuous_train/final.pt` | 最终模型 |

**特点**：
- ✅ **保存逻辑完全相同** - 使用相同的 `save_model()` 方法
- ✅ 文件命名略有不同（`final.pt` vs `last.pt`）
- ✅ 与预生成数据训练的 checkpoint **格式完全兼容**

**重要**：连续生成和预生成数据的 checkpoint 格式完全相同，可以互相加载！

---

## 🎯 加载和推理

### 加载 Checkpoint

#### 方式 1: 仿真推理 (`deploy_sim.py`)

```bash
python deploy_sim.py \
    --model_path=./runs/my_train \
    --task_name=plate_out \
    --num_demos=2
```

**加载代码**：

```python
# 加载配置
if os.path.exists(f'{model_path}/config.pkl'):
    config = pickle.load(open(f'{model_path}/config.pkl', 'rb'))
else:
    config = base_config.copy()

# 更新推理配置
config['device'] = device
config['num_demos'] = num_demos
config['num_diffusion_iters_test'] = 4

# 加载模型
model = GraphDiffusion.load_from_checkpoint(
    f'{model_path}/model.pt',  # 默认加载 model.pt
    config=config,
    strict=False,
    map_location=device
).to(device)

model.eval()
```

**自动查找逻辑**：
1. 优先查找 `model.pt`（预训练权重）
2. 查找 `config.pkl`（保存的配置）
3. 查找 `scene_encoder.pt`（可选，预训练场景编码器）

#### 方式 2: 微调加载

```bash
python ip/train.py \
    --fine_tune=1 \
    --model_path=./runs/my_train \
    --model_name=best.pt \  # 或 last.pt, 100000.pt 等
    --data_path_train=./data/new_tasks
```

**加载代码**：

```python
if fine_tune:
    # 加载配置
    config = pickle.load(open(f'{model_path}/config.pkl', 'rb'))
    
    # 加载模型
    model = GraphDiffusion.load_from_checkpoint(
        f'{model_path}/{model_name}',
        config=config,
        strict=True,
        map_location=config['device']
    ).to(config['device'])
```

---

## 📁 文件结构

### 训练保存的完整结构

```
runs/my_train/
├── config.pkl              # 训练配置（必需）
├── 100000.pt               # 第 100K 步 checkpoint
├── 200000.pt               # 第 200K 步 checkpoint
├── 300000.pt               # 第 300K 步 checkpoint
├── best.pt                 # 最佳验证模型
└── last.pt / final.pt      # 最终模型
```

### Checkpoint 内容

每个 `.pt` 文件包含：

```python
checkpoint = {
    'state_dict': {
        'model.scene_encoder.xxx': ...,    # 场景编码器权重
        'model.local_encoder.xxx': ...,    # 局部编码器权重
        'model.cond_encoder.xxx': ...,     # 条件编码器权重
        'model.action_encoder.xxx': ...,   # 动作编码器权重
        'model.prediction_head.xxx': ...,  # 预测头权重
        # ... 所有模型参数
    },
    'optimizer_states': [...],              # 优化器状态
    'lr_schedulers': [...],                 # 学习率调度器
    'epoch': ...,                           # 训练轮数
    'global_step': ...,                     # 全局步数
    'pytorch-lightning_version': ...,       # Lightning 版本
    # ... 其他训练状态
}
```

---

## 🔧 配置参数

### 保存相关配置

在 `ip/configs/base_config.py`：

```python
config = {
    'record': False,              # 是否保存 checkpoint
    'save_dir': None,             # 保存目录
    'save_every': 100000,         # 每 N 步保存一次
    # ... 其他配置
}
```

### 修改保存频率

**方式 1: 修改配置文件**

```python
# ip/configs/base_config.py
config = {
    'save_every': 50000,  # 改为每 5 万步保存
}
```

**方式 2: 训练时动态修改**

```python
# ip/train.py
config['save_every'] = 50000  # 添加这行
model = GraphDiffusion(config).to(config['device'])
```

---

## 📊 保存策略对比

### 策略 1: 仅保存最佳和最终模型

```python
config['save_every'] = float('inf')  # 禁用定期保存
```

**优点**：
- ✅ 节省磁盘空间
- ✅ 适合磁盘空间有限的情况

**缺点**：
- ❌ 无法中途恢复训练
- ❌ 无法回溯到中间状态

---

### 策略 2: 频繁保存（推荐用于长时间训练）

```python
config['save_every'] = 50000  # 每 5 万步保存
```

**优点**：
- ✅ 可以随时恢复训练
- ✅ 可以比较不同阶段的模型
- ✅ 训练中断也不会丢失太多进度

**缺点**：
- ❌ 占用更多磁盘空间（每个 checkpoint ~900MB）

**存储需求估算**：
```
每个 checkpoint: ~900 MB
训练 2.5M 步，每 5 万步保存: 50 个 checkpoint
总空间需求: ~45 GB
```

---

### 策略 3: 稀疏保存 + 最佳模型（论文设置）

```python
config['save_every'] = 100000  # 每 10 万步保存
```

**优点**：
- ✅ 平衡存储和恢复能力
- ✅ 论文使用的设置

**存储需求**：
```
2.5M 步训练: 25 个 checkpoint
总空间: ~22.5 GB
```

---

## 🔄 断点续训

### 从 Checkpoint 恢复训练

```bash
python ip/train.py \
    --fine_tune=1 \
    --model_path=./runs/my_train \
    --model_name=200000.pt \
    --data_path_train=./data/train \
    --run_name=my_train_resumed \
    --record=1
```

**注意**：
- ✅ `global_step` 会从 checkpoint 继续
- ✅ 优化器状态被恢复
- ✅ 学习率调度器被恢复
- ⚠️ 新的保存会在新的 `save_dir`

---

## 🎯 最佳实践

### 1. 训练时的保存策略

**小规模测试**（< 100K 步）：
```python
config['save_every'] = 10000  # 每 1 万步保存
```

**中等规模**（100K - 500K 步）：
```python
config['save_every'] = 50000  # 每 5 万步保存
```

**大规模训练**（> 500K 步，论文规模）：
```python
config['save_every'] = 100000  # 每 10 万步保存
```

---

### 2. Checkpoint 选择指南

| 用途 | 推荐 Checkpoint | 说明 |
|-----|----------------|------|
| 最终部署 | `best.pt` | 验证集性能最佳 |
| 快速测试 | `last.pt` / `final.pt` | 最新的训练结果 |
| 分析训练过程 | `{step}.pt` | 特定步数的模型 |
| 微调 | `best.pt` 或 `{step}.pt` | 根据下游任务选择 |
| 对比实验 | 多个 `{step}.pt` | 比较不同训练阶段 |

---

### 3. 磁盘空间管理

**自动清理旧 Checkpoint**：

```bash
# 保留最近 5 个 checkpoint
cd ./runs/my_train
ls -t *.pt | grep -E '^[0-9]+\.pt$' | tail -n +6 | xargs rm -f
```

**压缩不常用的 Checkpoint**：

```bash
# 压缩早期 checkpoint
gzip 100000.pt 200000.pt
```

---

### 4. 备份策略

**重要 Checkpoint 备份**：

```bash
# 备份最佳模型
cp ./runs/my_train/best.pt ./backups/my_train_best_$(date +%Y%m%d).pt
cp ./runs/my_train/config.pkl ./backups/
```

**云端备份**：

```bash
# 上传到云存储
rclone copy ./runs/my_train/best.pt remote:backups/
```

---

## 🔍 故障排查

### Q1: Checkpoint 文件损坏？

**症状**：
```
RuntimeError: PytorchStreamReader failed reading file data/...
```

**解决**：
- 使用 `repair_checkpoint()` 修复（已内置）
- 从上一个 checkpoint 恢复

---

### Q2: 加载时配置不匹配？

**症状**：
```
RuntimeError: size mismatch for model.xxx
```

**解决**：
```python
# 使用 strict=False 加载
model = GraphDiffusion.load_from_checkpoint(
    checkpoint_path,
    config=config,
    strict=False  # 允许部分参数不匹配
)
```

---

### Q3: 内存不足无法加载？

**解决**：
```python
# 使用 CPU 加载后再移到 GPU
model = GraphDiffusion.load_from_checkpoint(
    checkpoint_path,
    config=config,
    map_location='cpu'  # 先加载到 CPU
)
model = model.to('cuda')  # 再移到 GPU
```

---

### Q4: 找不到 config.pkl？

**症状**：
```
FileNotFoundError: config.pkl not found
```

**解决**：
```python
# deploy_sim.py 已包含此逻辑
if os.path.exists(f'{model_path}/config.pkl'):
    config = pickle.load(open(f'{model_path}/config.pkl', 'rb'))
else:
    print("Warning: using base_config")
    config = base_config.copy()
```

---

## 📊 Checkpoint 对比表

### 连续生成 vs 预生成数据

| 特性 | 连续生成训练 | 预生成数据训练 |
|-----|------------|--------------|
| **保存逻辑** | ✅ 相同 | ✅ 相同 |
| **Checkpoint 格式** | ✅ 相同 | ✅ 相同 |
| **保存时机** | ✅ 相同 | ✅ 相同 |
| **配置文件** | ✅ config.pkl | ✅ config.pkl |
| **可互相加载** | ✅ 是 | ✅ 是 |
| **推理兼容性** | ✅ 完全兼容 | ✅ 完全兼容 |
| **微调兼容性** | ✅ 完全兼容 | ✅ 完全兼容 |

**结论**：两种训练方式的 checkpoint **完全相同**，可以互换使用！

---

## 🚀 完整示例

### 示例 1: 完整训练流程

```bash
# 1. 训练模型
python ip/train.py \
    --run_name=my_experiment \
    --data_path_train=./data/train \
    --data_path_val=./data/val \
    --record=1

# 生成的文件:
# ./runs/my_experiment/config.pkl
# ./runs/my_experiment/100000.pt
# ./runs/my_experiment/200000.pt
# ./runs/my_experiment/best.pt
# ./runs/my_experiment/last.pt

# 2. 推理测试
python deploy_sim.py \
    --model_path=./runs/my_experiment \
    --task_name=plate_out

# 3. 微调
python ip/train.py \
    --fine_tune=1 \
    --model_path=./runs/my_experiment \
    --model_name=best.pt \
    --data_path_train=./data/finetune \
    --run_name=my_experiment_finetuned
```

---

### 示例 2: 连续生成训练

```bash
# 1. 连续生成训练
python train_with_pseudo.py \
    --run_name=continuous_train \
    --num_pseudo_samples=700000 \
    --record=1

# 生成的文件（与预生成完全相同）:
# ./runs/continuous_train/config.pkl
# ./runs/continuous_train/100000.pt
# ./runs/continuous_train/200000.pt
# ./runs/continuous_train/best.pt
# ./runs/continuous_train/final.pt

# 2. 推理（完全相同的方式）
python deploy_sim.py \
    --model_path=./runs/continuous_train \
    --task_name=plate_out
```

---

## 📝 总结

### 关键要点

1. **保存逻辑统一**
   - ✅ 连续生成和预生成数据使用**完全相同**的保存逻辑
   - ✅ 都调用同一个 `save_model()` 方法
   - ✅ Checkpoint 格式完全兼容

2. **自动保存时机**
   - 每 `save_every` 步（默认 100K）
   - 验证后保存最佳模型（如果有验证集）
   - 训练结束保存最终模型

3. **文件结构**
   - `config.pkl` - 训练配置（必需）
   - `{step}.pt` - 定期保存的 checkpoint
   - `best.pt` - 最佳验证模型
   - `last.pt` / `final.pt` - 最终模型

4. **加载方式**
   - 推理：`deploy_sim.py --model_path=<dir>`
   - 微调：`ip/train.py --fine_tune=1 --model_path=<dir> --model_name=<file>.pt`
   - 使用 `GraphDiffusion.load_from_checkpoint()`

5. **推荐设置**
   - 测试：`save_every=10000`
   - 正常训练：`save_every=50000-100000`
   - 始终保存 `config.pkl`
   - 备份重要的 checkpoint

---

**相关文档**：
- [训练指南](README_SHAPENET_TRAINING.md)
- [部署指南](DEPLOYMENT_GUIDE.md)
- [训练修复说明](../updates/TRAINING_FIX.md)

---

**最后更新**: 2026-02-06  
**作者**: Cursor AI Agent
