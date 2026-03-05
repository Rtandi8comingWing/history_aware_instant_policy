#!/bin/bash
# 内存优化版训练脚本

echo "启动内存优化训练..."

python train_with_pseudo.py \
    --run_name=train_memory_optimized \
    --num_pseudo_samples=700000 \
    --buffer_size=200 \
    --num_generator_threads=1 \
    --batch_size=4 \
    --record=1

echo "训练完成！"
