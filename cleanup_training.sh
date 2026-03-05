#!/bin/bash
# 清理训练文件的实用脚本

echo "=========================================="
echo "清理训练文件"
echo "=========================================="
echo ""

# 显示当前磁盘使用
echo "📊 当前磁盘使用:"
du -sh ./runs 2>/dev/null || echo "  ./runs 目录不存在"
echo ""

# 列出所有运行
echo "📁 现有的训练运行:"
if [ -d "./runs" ]; then
    ls -lh ./runs/ | grep "^d" | awk '{print "  " $9 " (" $5 ")"}'
else
    echo "  无"
fi
echo ""

# 询问是否清理
read -p "是否要清理旧的训练文件？(y/N): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "选择清理选项:"
    echo "1. 删除所有训练运行"
    echo "2. 删除特定运行"
    echo "3. 只删除中间检查点（保留 final.pt）"
    echo "4. 取消"
    echo ""
    read -p "请选择 (1-4): " -n 1 -r
    echo ""

    case $REPLY in
        1)
            echo "⚠️  警告：这将删除 ./runs 目录下的所有内容！"
            read -p "确认删除？(yes/N): " CONFIRM
            if [ "$CONFIRM" = "yes" ]; then
                rm -rf ./runs/*
                echo "✅ 已删除所有训练运行"
            else
                echo "❌ 已取消"
            fi
            ;;
        2)
            echo "可用的运行:"
            ls -1 ./runs/ 2>/dev/null | nl
            echo ""
            read -p "输入要删除的运行名称: " RUN_NAME
            if [ -d "./runs/$RUN_NAME" ]; then
                rm -rf "./runs/$RUN_NAME"
                echo "✅ 已删除运行: $RUN_NAME"
            else
                echo "❌ 运行不存在: $RUN_NAME"
            fi
            ;;
        3)
            echo "清理中间检查点..."
            find ./runs -name "model_step_*.pt" -delete
            echo "✅ 已删除中间检查点（保留 final.pt）"
            ;;
        4)
            echo "❌ 已取消"
            ;;
        *)
            echo "❌ 无效选项"
            ;;
    esac
else
    echo "❌ 已取消"
fi

echo ""
echo "=========================================="
echo "清理完成"
echo "=========================================="
