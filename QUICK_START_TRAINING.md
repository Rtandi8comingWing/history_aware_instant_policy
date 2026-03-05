# 快速开始：train_with_pseudo.py 训练指南

## 🎯 一键启动

### 方式 1：使用便捷脚本（推荐）

```bash
# 小样本测试（10分钟，验证系统）
./train_pseudo_small.sh

# 中等规模训练（10-20小时，快速实验）
./train_pseudo_medium.sh

# 完整规模训练（5天，论文设置）
./train_pseudo_full.sh
```

### 方式 2：直接命令行

```bash
# 激活环境
conda activate ip_env

# 小样本测试
python train_with_pseudo.py \
    --run_name=test_small \
    --num_pseudo_samples=100 \
    --buffer_size=10 \
    --num_generator_threads=1 \
    --batch_size=2 \
    --record=0
```

---

## 📊 配置对比

| 配置 | 样本数 | 缓冲区 | 线程 | 批大小 | 用时 | 用途 |
|------|--------|--------|------|--------|------|------|
| **Small** | 100 | 10 | 1 | 2 | 10分钟 | 系统验证 |
| **Medium** | 10K | 500 | 2 | 4 | 10-20小时 | 快速实验 |
| **Full** | 700K | 1000 | 4 | 16 | 5天 | 生产训练 |

---

## ✅ 成功标志

训练正常运行时，你会看到：

```
================================================================================
Training Instant Policy with Continuous Pseudo-Data Generation
================================================================================
ShapeNet root: /media/tianyi/Tiantian/tianyiStudy/DataSets/ShapeNetCore.v2
Virtual dataset size: 100
Buffer size: 10
Generator threads: 1
Batch size: 2
Fine-tune: False
================================================================================

Creating new model...

Initializing continuous pseudo-data generation...
Initializing ShapeNet loader from /media/tianyi/Tiantian/tianyiStudy/DataSets/ShapeNetCore.v2...
ShapeNet Loader initialized with 55 categories
Loaded 55 categories, 52472 models
Starting 1 background generation threads...
Pre-generating 10 samples...
Initial buffer filled: 5 samples ready
Training with pseudo-data only
Loading validation data from ./data/val...

Setting up trainer...

================================================================================
Starting training...
Paper setup: 2.5M steps with ~700K unique pseudo-trajectories
Current setup: 50000000001 steps
================================================================================

Sanity Checking DataLoader 0: 100%|██████████| 2/2 [00:02<00:00,  0.95it/s]
Epoch 0:   2%|▏         | 1/50 [00:00<00:13,  3.51it/s, v_num=36]
Epoch 0:   4%|▍         | 2/50 [00:00<00:14,  3.33it/s, v_num=36]
...
Epoch 0: 100%|██████████| 50/50 [06:47<00:00,  0.12it/s, v_num=36, Train_Loss=1.020]
```

---

## 🔧 常用参数

### 必需参数

```bash
--run_name=<实验名称>          # 实验名称，用于保存
--num_pseudo_samples=<数量>    # 虚拟数据集大小
```

### 性能参数

```bash
--buffer_size=<大小>           # 预生成缓冲区大小（默认：1000）
--num_generator_threads=<数量> # 后台生成线程数（默认：4）
--batch_size=<大小>            # 批大小（默认：16）
```

### 保存参数

```bash
--record=1                     # 启用模型保存和日志
--save_path=./runs             # 保存路径
--use_wandb=1                  # 启用 Weights & Biases 日志
```

### 微调参数

```bash
--fine_tune=1                  # 从已有模型微调
--model_path=./checkpoints     # 预训练模型路径
--real_data_path=./data/real   # 真实数据路径
--real_data_ratio=0.5          # 真实数据比例（0.5 = 50/50）
```

---

## 💾 输出文件

### 训练时（record=1）

```
./runs/<run_name>/
├── config.pkl              # 训练配置
├── model_step_100000.pt    # 检查点（每10万步）
├── model_step_200000.pt
├── ...
└── final.pt                # 最终模型
```

### 训练后

```
================================================================================
Training Complete!
================================================================================
Pseudo-demos generated: 150
Generation errors: 0
================================================================================

Final model saved to: ./runs/<run_name>/final.pt
```

---

## 🐛 常见问题

### 1. CUDA out of memory

**症状**：`RuntimeError: CUDA out of memory`

**解决**：
```bash
python train_with_pseudo.py \
    --batch_size=1 \
    --num_generator_threads=1
```

### 2. 系统内存不足（OOM）

**症状**：进程被 killed

**解决**：
```bash
python train_with_pseudo.py \
    --num_generator_threads=1 \
    --buffer_size=500
```

### 3. 生成速度慢

**症状**：缓冲区经常为空

**解决**：
```bash
python train_with_pseudo.py \
    --num_generator_threads=4 \
    --buffer_size=1000
```

### 4. 验证集未找到

**症状**：`⚠️  No validation data found, skipping validation`

**解决**：这是正常的，训练会自动跳过验证。如需验证：
```bash
python generate_pseudo_data.py --val_tasks=10
```

---

## 📈 监控训练

### 实时查看进度

```bash
# 方式 1：直接运行（推荐）
python train_with_pseudo.py --run_name=test

# 方式 2：后台运行 + 日志
nohup python train_with_pseudo.py --run_name=test > train.log 2>&1 &
tail -f train.log

# 方式 3：使用 screen
screen -S training
python train_with_pseudo.py --run_name=test
# Ctrl+A+D 分离，screen -r training 重新连接
```

### 查看 GPU 使用

```bash
watch -n 1 nvidia-smi
```

### 查看训练指标

训练过程中会显示：
- **Train_Loss**：训练损失
- **it/s**：迭代速度（批次/秒）
- **v_num**：验证编号

---

## 🎓 进阶用法

### 1. 从检查点恢复训练

```bash
python train_with_pseudo.py \
    --fine_tune=1 \
    --model_path=./runs/previous_run \
    --model_name=model_step_100000.pt \
    --run_name=resume_training
```

### 2. 混合真实数据训练（PD++）

```bash
python train_with_pseudo.py \
    --run_name=pd_plus_plus \
    --fine_tune=1 \
    --model_path=./checkpoints \
    --real_data_path=./data/rlbench \
    --real_data_ratio=0.5 \
    --num_pseudo_samples=100000
```

### 3. 自定义配置

编辑 `ip/configs/base_config.py`：

```python
config = {
    'batch_size': 4,           # 批大小
    'num_demos': 2,            # 上下文演示数量
    'hidden_dim': 1024,        # 模型隐藏维度
    'traj_horizon': 10,        # 轨迹长度
    'pre_horizon': 8,          # 预测范围
    'lr': 1e-5,                # 学习率
    'num_diffusion_iters_train': 100,  # 训练扩散步数
    'num_diffusion_iters_test': 8,     # 推理扩散步数
}
```

---

## 📚 相关文档

- **修复说明**：`TRAINING_FIXES.md` - 详细的问题修复记录
- **完整指南**：`docs/guides/README_SHAPENET_TRAINING.md`
- **项目说明**：`CLAUDE.md`
- **快速参考**：`docs/references/QUICK_SUMMARY.txt`

---

## 🚀 推荐工作流

### 首次使用

```bash
# 1. 测试系统（10分钟）
./train_pseudo_small.sh

# 2. 如果成功，运行中等规模（10-20小时）
./train_pseudo_medium.sh

# 3. 最后运行完整训练（5天）
./train_pseudo_full.sh
```

### 日常实验

```bash
# 快速验证想法
python train_with_pseudo.py \
    --run_name=experiment_$(date +%Y%m%d_%H%M%S) \
    --num_pseudo_samples=1000 \
    --buffer_size=100 \
    --num_generator_threads=2 \
    --batch_size=4 \
    --record=1
```

### 生产训练

```bash
# 使用 screen 或 tmux 运行长时间训练
screen -S production_training
./train_pseudo_full.sh
# Ctrl+A+D 分离
```

---

## ✨ 提示

1. **首次运行**：建议先用 `train_pseudo_small.sh` 验证系统正常
2. **GPU 显存**：如果显存不足，减小 `batch_size` 和 `num_generator_threads`
3. **系统内存**：如果系统内存不足，减小 `buffer_size` 和 `num_generator_threads`
4. **训练速度**：增加 `num_generator_threads` 可以加速数据生成
5. **保存空间**：如果磁盘空间有限，设置 `--record=0` 跳过保存

---

## 📞 获取帮助

如果遇到问题：

1. 查看 `TRAINING_FIXES.md` 了解已知问题和解决方案
2. 检查 `docs/guides/README_SHAPENET_TRAINING.md` 获取详细指南
3. 查看训练日志中的错误信息
4. 确保 ShapeNet 数据集路径正确

---

**祝训练顺利！🎉**
