#!/bin/bash
# 超低内存配置（适用于 8GB 内存系统）

echo "=========================================="
echo "启动超低内存训练配置"
echo "=========================================="
echo ""
echo "配置:"
echo "  buffer_size: 50"
echo "  num_generator_threads: 1"
echo "  batch_size: 1"
echo "  预期内存占用: ~2-3 GB"
echo ""
echo "⚠️  注意: 训练速度会较慢，但不会 OOM"
echo ""

python train_with_pseudo.py \
    --run_name=train_ultra_low_mem \
    --num_pseudo_samples=700000 \
    --buffer_size=50 \
    --num_generator_threads=1 \
    --batch_size=1 \
    --record=1

echo ""
echo "训练完成！"
