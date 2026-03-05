#!/bin/bash
# 检查系统资源是否足够训练

echo "=========================================="
echo "系统资源检查"
echo "=========================================="
echo ""

# 检查系统内存
TOTAL_MEM=$(free -g | grep Mem | awk '{print $2}')
AVAIL_MEM=$(free -g | grep Mem | awk '{print $7}')

echo "💾 系统内存:"
echo "  总内存: ${TOTAL_MEM} GB"
echo "  可用内存: ${AVAIL_MEM} GB"
echo ""

# 推荐配置
if [ $TOTAL_MEM -lt 16 ]; then
    echo "⚠️  内存较少（< 16GB），推荐使用极简配置:"
    echo "  buffer_size=100"
    echo "  num_generator_threads=1"
    echo "  batch_size=2"
    echo ""
    echo "  运行命令:"
    echo "  python train_with_pseudo.py --buffer_size=100 --num_generator_threads=1 --batch_size=2"
elif [ $TOTAL_MEM -lt 32 ]; then
    echo "✅ 内存适中（16-32GB），推荐使用优化配置:"
    echo "  buffer_size=200"
    echo "  num_generator_threads=1"
    echo "  batch_size=4"
    echo ""
    echo "  运行命令:"
    echo "  ./train_pseudo_memory_optimized.sh"
else
    echo "✅ 内存充足（>= 32GB），可以使用标准配置:"
    echo "  buffer_size=500-1000"
    echo "  num_generator_threads=2-4"
    echo "  batch_size=8-16"
    echo ""
    echo "  运行命令:"
    echo "  ./train_pseudo_full.sh"
fi

echo ""
echo "=========================================="
echo "💿 磁盘空间:"
df -h . | tail -1 | awk '{printf "  可用空间: %s / %s (%s 已使用)\n", $4, $2, $5}'
echo ""

# 检查 swap
SWAP_TOTAL=$(free -g | grep Swap | awk '{print $2}')
echo "🔄 Swap 空间:"
if [ $SWAP_TOTAL -eq 0 ]; then
    echo "  ⚠️  未配置 swap，建议添加 swap 以避免 OOM"
    echo ""
    echo "  添加 swap 命令:"
    echo "  sudo fallocate -l 16G /swapfile"
    echo "  sudo chmod 600 /swapfile"
    echo "  sudo mkswap /swapfile"
    echo "  sudo swapon /swapfile"
else
    echo "  ✅ Swap: ${SWAP_TOTAL} GB"
fi

echo ""
echo "=========================================="
echo "🖥️  GPU 信息:"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader | \
    awk -F',' '{printf "  GPU: %s\n  显存: %s\n", $1, $2}'

echo ""
echo "=========================================="
echo ""
echo "建议："
echo "1. 先运行小样本测试验证配置"
echo "2. 使用 ./monitor_memory.sh 监控内存使用"
echo "3. 如果出现 OOM，减小 buffer_size 和 num_generator_threads"
echo ""
