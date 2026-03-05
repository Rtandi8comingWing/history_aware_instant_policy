#!/bin/bash
# 一键启动训练的便捷脚本

echo "=========================================="
echo "Instant Policy 训练启动器"
echo "=========================================="
echo ""
echo "请选择训练规模："
echo ""
echo "1. 小样本测试（100 样本，10 分钟）"
echo "   - 用途：验证系统正常工作"
echo "   - 配置：batch_size=2, threads=1"
echo ""
echo "2. 中等规模训练（10K 样本，10-20 小时）"
echo "   - 用途：快速实验和验证"
echo "   - 配置：batch_size=4, threads=2"
echo ""
echo "3. 完整规模训练（700K 样本，5 天）"
echo "   - 用途：论文复现和生产训练"
echo "   - 配置：batch_size=16, threads=4"
echo ""
echo "4. 自定义配置"
echo ""
echo "5. 退出"
echo ""

read -p "请选择 (1-5): " choice

case $choice in
    1)
        echo ""
        echo "启动小样本测试..."
        ./train_pseudo_small.sh
        ;;
    2)
        echo ""
        echo "启动中等规模训练..."
        ./train_pseudo_medium.sh
        ;;
    3)
        echo ""
        echo "⚠️  警告：完整规模训练需要约 5 天时间"
        read -p "确认启动？(y/N): " confirm
        if [[ $confirm =~ ^[Yy]$ ]]; then
            echo ""
            echo "启动完整规模训练..."
            ./train_pseudo_full.sh
        else
            echo "已取消"
        fi
        ;;
    4)
        echo ""
        echo "自定义配置训练"
        read -p "实验名称: " run_name
        read -p "样本数量: " num_samples
        read -p "批大小: " batch_size
        read -p "生成线程数: " num_threads
        read -p "是否保存模型 (0/1): " record

        echo ""
        echo "启动训练..."
        conda activate ip_env
        export PYOPENGL_PLATFORM=egl

        python train_with_pseudo.py \
            --run_name=$run_name \
            --num_pseudo_samples=$num_samples \
            --batch_size=$batch_size \
            --num_generator_threads=$num_threads \
            --buffer_size=$((num_samples / 10)) \
            --record=$record
        ;;
    5)
        echo "退出"
        exit 0
        ;;
    *)
        echo "无效选项"
        exit 1
        ;;
esac
