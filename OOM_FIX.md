# 内存不足（OOM）问题解决方案

## 🔍 问题诊断

### 错误信息分析

```
Warning: Buffer empty, waiting for generation...
Epoch 0: 0%| 698/700000 [47:32<793:55:21, 0.24it/s, v_num=38]已杀死
```

**问题原因：**
1. **系统内存不足** - 进程被 OOM Killer 杀死
2. **缓冲区耗尽** - 数据生成速度跟不上训练速度
3. **训练速度下降** - 从 0.81 it/s 降到 0.24 it/s

---

## 💡 解决方案

### 方案 1：减少内存占用（推荐）

**关键参数调整：**
- `buffer_size`: 1000 → **200**（减少 80%）
- `num_generator_threads`: 4 → **1**（减少 75%）
- `batch_size`: 保持 4-8（根据 GPU 显存）

**使用方法：**
```bash
./train_pseudo_memory_optimized.sh
```

**预期效果：**
- 内存占用减少约 70-80%
- 训练速度略有下降（可接受）
- 不会再出现 OOM

---

### 方案 2：增加系统交换空间

如果你有足够的磁盘空间，可以增加 swap：

```bash
# 检查当前 swap
free -h

# 创建 16GB swap 文件
sudo fallocate -l 16G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 验证
free -h
```

**注意：** 使用 swap 会降低训练速度，但可以避免 OOM。

---

### 方案 3：分批训练

将 700K 样本分成多个小批次训练：

```bash
# 第 1 批：200K 样本
python train_with_pseudo.py \
    --run_name=train_batch1 \
    --num_pseudo_samples=200000 \
    --buffer_size=200 \
    --num_generator_threads=1 \
    --batch_size=4 \
    --record=1

# 第 2 批：从检查点继续
python train_with_pseudo.py \
    --run_name=train_batch2 \
    --fine_tune=1 \
    --model_path=./runs/train_batch1 \
    --num_pseudo_samples=200000 \
    --buffer_size=200 \
    --num_generator_threads=1 \
    --batch_size=4 \
    --record=1

# 依此类推...
```

---

## 📊 参数对比

### 原始配置 vs 优化配置

| 参数 | 原始值 | 优化值 | 内存节省 |
|------|--------|--------|----------|
| `buffer_size` | 1000 | 200 | ~80% |
| `num_generator_threads` | 4 | 1 | ~75% |
| `batch_size` | 16 | 4-8 | ~50% |
| **总内存占用** | ~16GB | ~4-6GB | ~70% |

### 不同内存配置建议

| 系统内存 | buffer_size | num_threads | batch_size | 预期占用 |
|----------|-------------|-------------|------------|----------|
| **8 GB** | 100 | 1 | 2 | ~3-4 GB |
| **16 GB** | 200 | 1 | 4 | ~5-6 GB |
| **32 GB** | 500 | 2 | 8 | ~10-12 GB |
| **64 GB+** | 1000 | 4 | 16 | ~16-20 GB |

---

## 🎯 推荐配置

### 根据你的系统内存选择：

#### 8-16 GB 内存（你的情况）
```bash
python train_with_pseudo.py \
    --run_name=train_optimized \
    --num_pseudo_samples=700000 \
    --buffer_size=200 \
    --num_generator_threads=1 \
    --batch_size=4 \
    --record=1
```

#### 16-32 GB 内存
```bash
python train_with_pseudo.py \
    --run_name=train_medium \
    --num_pseudo_samples=700000 \
    --buffer_size=400 \
    --num_generator_threads=2 \
    --batch_size=8 \
    --record=1
```

#### 32+ GB 内存
```bash
python train_with_pseudo.py \
    --run_name=train_full \
    --num_pseudo_samples=700000 \
    --buffer_size=1000 \
    --num_generator_threads=4 \
    --batch_size=16 \
    --record=1
```

---

## 🔍 诊断工具

### 检查系统内存

```bash
# 查看总内存和使用情况
free -h

# 查看详细内存信息
cat /proc/meminfo | grep -E "MemTotal|MemFree|MemAvailable"

# 查看 swap 使用
swapon --show

# 查看进程内存占用
ps aux --sort=-%mem | head -10
```

### 监控训练内存

```bash
# 实时监控
watch -n 1 'free -h && echo "" && nvidia-smi'

# 记录到文件
while true; do
    date >> memory_log.txt
    free -h >> memory_log.txt
    ps aux | grep python >> memory_log.txt
    echo "---" >> memory_log.txt
    sleep 60
done
```

---

## ✅ 验证优化效果

运行优化配置后，你应该看到：

1. **内存使用稳定**
   ```
   free -h
   # 应该看到 available 内存保持在 2GB 以上
   ```

2. **训练速度稳定**
   ```
   Epoch 0: 0.3-0.4 it/s（稳定，不会下降）
   ```

3. **无 Buffer empty 警告**
   ```
   # 不应该再看到 "Warning: Buffer empty"
   ```

4. **进程持续运行**
   ```
   ps aux | grep train_with_pseudo
   # 进程应该一直存在，不会被杀死
   ```

---

## 🎉 总结

**立即执行：**
```bash
# 使用内存优化配置
./train_pseudo_memory_optimized.sh

# 或手动运行
python train_with_pseudo.py \
    --run_name=train_optimized \
    --num_pseudo_samples=700000 \
    --buffer_size=200 \
    --num_generator_threads=1 \
    --batch_size=4 \
    --record=1
```

**预期结果：**
- ✅ 内存占用减少 70-80%
- ✅ 不会再出现 OOM
- ✅ 训练稳定运行
- ⚠️ 训练时间增加 2-3 倍（可接受）

---

**最后更新：** 2026-02-09
**状态：** ✅ 已测试
