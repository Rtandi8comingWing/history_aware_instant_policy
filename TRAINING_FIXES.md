# Training Fixes for train_with_pseudo.py

## 修复日期
2026-02-09

## 问题总结

在运行 `train_with_pseudo.py` 时遇到了两个关键问题，已全部修复并验证通过。

---

## 问题 1: PyRender 显示错误

### 错误信息
```
pyglet.display.xlib.NoSuchDisplayException: Cannot connect to "None"
Maximum number of clients reached
```

### 根本原因
PyRender 在无头环境（headless）下需要使用 EGL 平台进行渲染，但默认尝试连接 X11 显示服务器。

### 解决方案
在 `ip/utils/pseudo_demo_generator.py` 文件开头添加环境变量设置：

```python
import os
# Set EGL platform for headless rendering BEFORE importing pyrender
os.environ['PYOPENGL_PLATFORM'] = 'egl'

import numpy as np
import trimesh
import pyrender
...
```

**关键点**：必须在 `import pyrender` **之前**设置环境变量。

### 修改文件
- `ip/utils/pseudo_demo_generator.py` (第 10-12 行)

---

## 问题 2: 批处理维度不匹配

### 错误信息
```
RuntimeError: Sizes of tensors must match except in dimension 0.
Expected size 4 but got size 2 for tensor number 1 in the list.
```

### 根本原因
原代码中每个样本的上下文演示数量是随机的（2-4 个），导致批处理时不同样本的张量维度不一致，PyTorch Geometric 无法合并。

### 解决方案

#### 1. 修改 `ip/utils/continuous_dataset.py`

**添加 `num_context_demos` 参数**：

```python
def __init__(self,
             shapenet_root='/media/tianyi/Tiantian/tianyiStudy/DataSets/ShapeNetCore.v2',
             num_virtual_samples=700000,
             num_demos_per_task=5,
             num_traj_wp=10,
             pred_horizon=8,
             buffer_size=1000,
             num_generator_threads=4,
             rand_g_prob=0.0,
             num_context_demos=2):  # 新增参数
    ...
    self.num_context_demos = num_context_demos  # 保存固定数量
```

**修改上下文演示选择逻辑**（第 145-151 行）：

```python
# 原代码（随机数量）
num_context = np.random.randint(2, min(5, len(demos)))
context_indices = [i for i in range(len(demos)) if i != live_idx]
if len(context_indices) >= num_context:
    context_indices = np.random.choice(context_indices, num_context, replace=False)
context_demos = [demos[i] for i in context_indices[:num_context]]

# 修复后（固定数量）
context_indices = [i for i in range(len(demos)) if i != live_idx]
if len(context_indices) >= self.num_context_demos:
    context_indices = np.random.choice(context_indices, self.num_context_demos, replace=False)
else:
    # 如果不够，使用重复采样
    context_indices = np.random.choice(context_indices, self.num_context_demos, replace=True)
context_demos = [demos[i] for i in context_indices]
```

#### 2. 修改 `train_with_pseudo.py`

**传入固定的上下文演示数量**（第 197-209 行）：

```python
train_dataset = ContinuousPseudoDataset(
    shapenet_root=args.shapenet_root,
    num_virtual_samples=args.num_pseudo_samples,
    num_demos_per_task=5,
    num_traj_wp=current_config['traj_horizon'],
    pred_horizon=current_config['pre_horizon'],
    buffer_size=args.buffer_size,
    num_generator_threads=args.num_generator_threads,
    rand_g_prob=current_config['randomize_g_prob'],
    num_context_demos=current_config['num_demos']  # 使用配置中的固定值
)
```

### 修改文件
- `ip/utils/continuous_dataset.py` (第 24-50 行, 第 145-151 行)
- `train_with_pseudo.py` (第 197-209 行)

---

## 验证结果

### 测试配置
```bash
python train_with_pseudo.py \
    --run_name=test_small \
    --num_pseudo_samples=100 \
    --buffer_size=10 \
    --num_generator_threads=1 \
    --batch_size=2 \
    --record=0
```

### 成功指标
✅ ShapeNet 加载成功：55 类别，52,472 模型
✅ 后台生成线程启动成功
✅ 初始缓冲区填充成功（5/10 样本）
✅ 验证集加载成功
✅ 模型初始化成功（117M 参数）
✅ Sanity check 通过（2/2 验证样本）
✅ 训练循环正常运行
✅ Epoch 0 完成（50/50 批次，Train_Loss=1.020）
✅ Epoch 1 开始正常

### 训练性能
- **速度**：约 0.12 it/s（每批次 8 秒）
- **GPU 使用**：NVIDIA GeForce RTX 3060 Laptop GPU
- **精度**：16-bit Mixed Precision (AMP)
- **内存**：正常，无 OOM 错误

---

## 便捷启动脚本

已创建三个训练脚本，位于项目根目录：

### 1. 小样本测试（推荐首次运行）
```bash
./train_pseudo_small.sh
```
- 样本数：100
- 缓冲区：10
- 线程数：1
- 批大小：2
- 用时：约 10 分钟
- 用途：验证系统正常工作

### 2. 中等规模训练
```bash
./train_pseudo_medium.sh
```
- 样本数：10,000
- 缓冲区：500
- 线程数：2
- 批大小：4
- 用时：约 10-20 小时
- 用途：快速实验和验证

### 3. 完整规模训练（论文设置）
```bash
./train_pseudo_full.sh
```
- 样本数：700,000
- 缓冲区：1,000
- 线程数：4
- 批大小：16
- 用时：约 5 天（高端 GPU）
- 用途：生产训练

---

## 使用建议

### 首次运行
1. 先运行小样本测试确保系统正常：
   ```bash
   ./train_pseudo_small.sh
   ```

2. 如果成功，尝试中等规模训练：
   ```bash
   ./train_pseudo_medium.sh
   ```

3. 最后运行完整规模训练：
   ```bash
   ./train_pseudo_full.sh
   ```

### 内存优化

如果遇到 OOM（内存不足）错误：

**GPU 显存不足**：
```bash
python train_with_pseudo.py \
    --batch_size=1 \
    --num_generator_threads=1 \
    --buffer_size=100
```

**系统内存不足**：
```bash
python train_with_pseudo.py \
    --num_generator_threads=1 \
    --buffer_size=500
```

### 监控训练

**实时查看日志**：
```bash
tail -f ./runs/<run_name>/logs.txt
```

**检查 GPU 使用**：
```bash
watch -n 1 nvidia-smi
```

**查看生成统计**：
训练结束时会自动打印：
- 生成的伪演示数量
- 生成错误次数
- 缓冲区状态

---

## 技术细节

### 为什么固定上下文演示数量？

PyTorch Geometric 的批处理机制要求同一批次中的所有样本具有相同的张量维度。原代码中：

```python
# 每个样本的 demo_T_w_es 形状：(1, num_demos, traj_horizon, 4, 4)
# 如果 num_demos 不同，无法批处理
```

修复后，所有样本的 `num_demos` 固定为 `config['num_demos']`（默认 2），确保批处理兼容。

### 为什么在代码中设置 EGL？

虽然可以在命令行设置 `export PYOPENGL_PLATFORM=egl`，但在代码中设置更可靠：
1. 确保在 `import pyrender` 之前设置
2. 避免用户忘记设置环境变量
3. 跨平台兼容性更好

### 数据生成流程

```
ShapeNet 加载 → 后台线程生成 → 缓冲区队列 → DataLoader → 训练
     ↓              ↓                ↓            ↓          ↓
  52K 模型      多线程并行        预生成池      批处理     GPU 训练
```

---

## 已知限制

1. **DataLoader workers**：必须设置 `num_workers=0`，因为后台生成线程与 DataLoader 多进程不兼容。

2. **验证集**：需要预先生成验证数据，否则会跳过验证步骤。

3. **生成速度**：每个样本生成约需 1-2 秒（包括渲染），建议使用多线程加速。

4. **磁盘空间**：如果 `record=1`，检查点会占用约 500MB/保存。

---

## 故障排除

### 问题：生成线程持续报错
**解决**：检查 ShapeNet 路径是否正确，确保有读取权限。

### 问题：训练速度很慢
**解决**：增加 `--num_generator_threads`，确保缓冲区不为空。

### 问题：CUDA out of memory
**解决**：减小 `--batch_size` 或使用 CPU 训练（修改 `config['device'] = 'cpu'`）。

### 问题：验证集未找到
**解决**：这是正常的，训练会自动跳过验证。如需验证，运行：
```bash
python generate_pseudo_data.py --val_tasks=10
```

---

## 相关文件

- `ip/utils/pseudo_demo_generator.py` - 伪演示生成器（EGL 修复）
- `ip/utils/continuous_dataset.py` - 连续数据集（批处理修复）
- `train_with_pseudo.py` - 主训练脚本
- `ip/configs/base_config.py` - 配置文件

---

## 参考

- 论文：Instant Policy (ICLR 2025)
- 文档：`docs/guides/README_SHAPENET_TRAINING.md`
- 项目指南：`CLAUDE.md`
