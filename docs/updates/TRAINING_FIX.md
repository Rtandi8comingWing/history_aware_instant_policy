# 训练脚本修复说明

## 问题描述

在使用 `ip/train.py` 或 `train_with_pseudo.py` 从头开始训练时，会遇到以下错误：

```
FileNotFoundError: [Errno 2] No such file or directory: './checkpoints/scene_encoder.pt'
```

## 原因分析

1. **配置默认值**: `ip/configs/base_config.py` 中默认设置：
   ```python
   'scene_encoder_path': './checkpoints/scene_encoder.pt',
   'pre_trained_encoder': True,
   ```

2. **文件不存在**: 您的检查点目录中只有 `model.pt`（包含完整模型权重），没有单独的 `scene_encoder.pt`

3. **模型初始化**: 在 `ip/models/model.py` 第 30-31 行，如果 `pre_trained_encoder=True`，会尝试加载 `scene_encoder.pt`：
   ```python
   if self.config['pre_trained_encoder']:
       self.scene_encoder.load_state_dict(torch.load(config['scene_encoder_path']))
   ```

## 解决方案

已修复 `ip/train.py` 和 `train_with_pseudo.py`，在创建新模型前自动检查文件：

```python
# Check if scene_encoder.pt exists, if not disable pre-trained encoder
if not os.path.exists(config['scene_encoder_path']):
    print(f"Warning: scene_encoder.pt not found at {config['scene_encoder_path']}")
    print("Training from scratch without pre-trained scene encoder")
    config['pre_trained_encoder'] = False
```

## 影响

- ✅ **从头训练**: 现在可以正常工作，scene encoder 从随机初始化开始
- ✅ **微调训练**: 不受影响，从 `model.pt` 加载完整权重（包括 scene encoder）
- ✅ **推理部署**: 之前已在 `deploy_sim.py` 中修复

## 训练方式对比

### 1. 从头训练（不使用预训练 scene encoder）

```bash
python ip/train.py \
    --run_name=train_from_scratch \
    --data_path_train=./data/pseudo_test \
    --data_path_val=./data/val \
    --record=1
```

**特点**:
- Scene encoder 从随机初始化开始
- 需要更多训练数据和时间
- 适合大规模训练（如使用 ShapeNet 伪数据）

### 2. 微调（使用预训练模型）

```bash
python ip/train.py \
    --fine_tune=1 \
    --model_path=./checkpoints \
    --model_name=model.pt \
    --data_path_train=./data/new_tasks \
    --run_name=finetune \
    --record=1
```

**特点**:
- 加载完整的预训练模型（包括 scene encoder）
- 训练更快，需要更少数据
- 适合在新任务上微调

### 3. 使用预训练 Scene Encoder（可选）

如果您有单独的 `scene_encoder.pt` 文件，可以：

```bash
# 1. 将文件放置在正确位置
cp /path/to/scene_encoder.pt ./checkpoints/

# 2. 正常训练
python ip/train.py \
    --run_name=train_with_pretrained_encoder \
    --data_path_train=./data/train \
    --record=1
```

**特点**:
- 使用预训练的 scene encoder
- 其他部分（graph transformer 等）从随机初始化
- 介于从头训练和完全微调之间

## 验证修复

### 测试从头训练

```bash
# 确保没有 scene_encoder.pt
ls -l ./checkpoints/scene_encoder.pt 2>&1

# 应该看到: No such file or directory

# 运行训练（应该成功）
python ip/train.py \
    --run_name=test_train \
    --data_path_train=./data/pseudo_test \
    --data_path_val=./data/val \
    --batch_size=8

# 应该看到:
# Warning: scene_encoder.pt not found at ./checkpoints/scene_encoder.pt
# Training from scratch without pre-trained scene encoder
```

### 测试 ShapeNet 伪数据训练

```bash
# 使用连续生成训练
python train_with_pseudo.py \
    --run_name=test_pseudo \
    --num_pseudo_samples=1000 \
    --batch_size=8

# 应该正常启动，不报错
```

## 注意事项

1. **性能影响**: 从头训练 scene encoder 可能需要：
   - 更多训练步数（论文使用 2.5M steps）
   - 更多训练数据（论文使用 ~700K 伪演示）

2. **推荐做法**:
   - **有大量数据**: 使用 ShapeNet 伪数据从头训练
   - **数据有限**: 使用预训练模型微调
   - **有预训练权重**: 放置 `scene_encoder.pt` 后训练

3. **兼容性**: 修复后的代码向后兼容，如果 `scene_encoder.pt` 存在，会正常加载

## 相关文件

- `ip/train.py` - 修复的主训练脚本
- `train_with_pseudo.py` - 修复的伪数据训练脚本
- `deploy_sim.py` - 已修复的推理脚本
- `ip/configs/base_config.py` - 默认配置
- `ip/models/model.py` - 模型定义

## 总结

✅ **问题已解决**: 所有训练脚本现在都能自动处理缺失的 `scene_encoder.pt`

✅ **自动降级**: 如果文件不存在，自动切换到从头训练模式

✅ **无需手动配置**: 不需要修改配置文件或代码

现在您可以：
- ✅ 使用预生成的伪数据训练
- ✅ 使用连续生成的伪数据训练  
- ✅ 微调预训练模型
- ✅ 从完全随机初始化开始训练
