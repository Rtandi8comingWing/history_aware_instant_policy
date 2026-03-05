#!/bin/bash
# 一键验证脚本 - 快速测试所有修复是否生效

echo "=========================================="
echo "验证 train_with_pseudo.py 修复"
echo "=========================================="
echo ""

# 检查修改的文件
echo "1. 检查修改的文件..."
echo ""

echo "✓ 检查 EGL 平台设置..."
if grep -q "PYOPENGL_PLATFORM.*egl" ip/utils/pseudo_demo_generator.py; then
    echo "  ✅ ip/utils/pseudo_demo_generator.py - EGL 设置已添加"
else
    echo "  ❌ ip/utils/pseudo_demo_generator.py - EGL 设置缺失"
fi

echo ""
echo "✓ 检查批处理修复..."
if grep -q "num_context_demos" ip/utils/continuous_dataset.py; then
    echo "  ✅ ip/utils/continuous_dataset.py - 批处理修复已添加"
else
    echo "  ❌ ip/utils/continuous_dataset.py - 批处理修复缺失"
fi

echo ""
echo "✓ 检查训练脚本更新..."
if grep -q "num_context_demos=current_config" train_with_pseudo.py; then
    echo "  ✅ train_with_pseudo.py - 参数传递已更新"
else
    echo "  ❌ train_with_pseudo.py - 参数传递缺失"
fi

echo ""
echo "=========================================="
echo "2. 检查启动脚本..."
echo ""

for script in train_pseudo_small.sh train_pseudo_medium.sh train_pseudo_full.sh; do
    if [ -x "$script" ]; then
        echo "  ✅ $script - 可执行"
    else
        echo "  ❌ $script - 不可执行或不存在"
    fi
done

echo ""
echo "=========================================="
echo "3. 检查文档..."
echo ""

for doc in TRAINING_FIXES.md QUICK_START_TRAINING.md TRAINING_SUCCESS_REPORT.md README_TRAINING.md; do
    if [ -f "$doc" ]; then
        echo "  ✅ $doc - 已创建"
    else
        echo "  ❌ $doc - 缺失"
    fi
done

echo ""
echo "=========================================="
echo "4. 环境检查..."
echo ""

# 检查 conda 环境
if conda env list | grep -q "ip_env"; then
    echo "  ✅ Conda 环境 'ip_env' 存在"
else
    echo "  ⚠️  Conda 环境 'ip_env' 未找到"
fi

# 检查 ShapeNet 路径
SHAPENET_PATH="/media/tianyi/Tiantian/tianyiStudy/DataSets/ShapeNetCore.v2"
if [ -d "$SHAPENET_PATH" ]; then
    echo "  ✅ ShapeNet 数据集路径存在"
else
    echo "  ⚠️  ShapeNet 数据集路径不存在: $SHAPENET_PATH"
fi

echo ""
echo "=========================================="
echo "验证完成！"
echo "=========================================="
echo ""
echo "下一步："
echo "1. 运行小样本测试："
echo "   ./train_pseudo_small.sh"
echo ""
echo "2. 如果成功，运行中等规模训练："
echo "   ./train_pseudo_medium.sh"
echo ""
echo "3. 查看详细文档："
echo "   cat README_TRAINING.md"
echo ""
