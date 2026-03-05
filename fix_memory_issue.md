# 内存不足问题解决方案

## 问题诊断

运行以下命令检查系统状态：

```bash
# 检查系统内存
free -h

# 检查 GPU 内存
nvidia-smi

# 检查是否有内存泄漏的进程
ps aux --sort=-%mem | head -20
```

## 解决方案

### 方案 1：减少内存使用（推荐）

修改训练参数，大幅减少内存占用：

```bash
python train_with_pseudo.py \
    --run_name=memory_optimized \
    --num_pseudo_samples=700000 \
    --buffer_size=100 \              # 从 1000 减少到 100
    --num_generator_threads=1 \      # 从 4 减少到 1
    --batch_size=1 \                 # 从 16 减少到 1
    --record=1
```

**说明**：
- `buffer_size=100`：减少预生成缓冲区，节省约 90% 内存
- `num_generator_threads=1`：只用 1 个生成线程，减少并发内存占用
- `batch_size=1`：最小批大小，减少 GPU 和系统内存占用

### 方案 2：使用交换空间（临时方案）

如果系统内存不足，可以增加交换空间：

```bash
# 创建 8GB 交换文件
sudo fallocate -l 8G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 验证
free -h
```

**警告**：使用交换空间会显著降低训练速度。

### 方案 3：分批训练

将大规模训练分成多个小批次：

```bash
# 第 1 批：训练 100K 样本
python train_with_pseudo.py \
    --run_name=batch_1 \
    --num_pseudo_samples=100000 \
    --buffer_size=100 \
    --num_generator_threads=1 \
    --batch_size=2 \
    --record=1

# 第 2 批：从检查点继续
python train_with_pseudo.py \
    --run_name=batch_2 \
    --fine_tune=1 \
    --model_path=./runs/batch_1 \
    --num_pseudo_samples=100000 \
    --buffer_size=100 \
    --num_generator_threads=1 \
    --batch_size=2 \
    --record=1

# 重复直到达到目标样本数
```

### 方案 4：修复内存泄漏（如果存在）

检查是否有内存泄漏：

```bash
# 监控内存使用
watch -n 1 'free -h && echo "---" && ps aux --sort=-%mem | head -5'
```

如果内存持续增长，可能需要修复代码中的内存泄漏。

## 推荐配置

根据你的系统内存选择配置：

### 8GB 系统内存
```bash
python train_with_pseudo.py \
    --num_pseudo_samples=700000 \
    --buffer_size=50 \
    --num_generator_threads=1 \
    --batch_size=1 \
    --record=1
```

### 16GB 系统内存
```bash
python train_with_pseudo.py \
    --num_pseudo_samples=700000 \
    --buffer_size=200 \
    --num_generator_threads=2 \
    --batch_size=2 \
    --record=1
```

### 32GB+ 系统内存
```bash
python train_with_pseudo.py \
    --num_pseudo_samples=700000 \
    --buffer_size=500 \
    --num_generator_threads=2 \
    --batch_size=4 \
    --record=1
```

## 监控训练

在另一个终端运行监控脚本：

```bash
# 监控系统内存
watch -n 1 'free -h'

# 监控 GPU 内存
watch -n 1 nvidia-smi

# 监控训练进度
./monitor_training.sh <run_name>
```

## 预防措施

1. **使用 screen 或 tmux**：防止 SSH 断开导致训练中断
2. **定期保存检查点**：设置 `--record=1` 并定期保存
3. **监控内存使用**：及时发现内存问题
4. **使用较小的缓冲区**：牺牲一些速度换取稳定性

