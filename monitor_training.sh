#!/bin/bash
# 监控训练进度的实用脚本

if [ -z "$1" ]; then
    echo "用法: ./monitor_training.sh <run_name>"
    echo "示例: ./monitor_training.sh test_small"
    exit 1
fi

RUN_NAME=$1
LOG_DIR="./runs/$RUN_NAME"

echo "=========================================="
echo "监控训练: $RUN_NAME"
echo "=========================================="
echo ""

# 检查运行目录是否存在
if [ ! -d "$LOG_DIR" ]; then
    echo "⚠️  运行目录不存在: $LOG_DIR"
    echo "训练可能还未开始或使用了不同的 run_name"
    exit 1
fi

echo "📁 运行目录: $LOG_DIR"
echo ""

# 显示最新的检查点
echo "📦 检查点文件:"
ls -lh "$LOG_DIR"/*.pt 2>/dev/null | tail -5 || echo "  暂无检查点"
echo ""

# 显示配置
if [ -f "$LOG_DIR/config.pkl" ]; then
    echo "✅ 配置文件已保存"
else
    echo "⚠️  配置文件未找到"
fi
echo ""

# 显示 GPU 使用情况
echo "🖥️  GPU 状态:"
nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits | \
    awk -F',' '{printf "  GPU %s: %s\n  使用率: %s%%\n  显存: %s MB / %s MB\n\n", $1, $2, $3, $4, $5}'

echo ""
echo "=========================================="
echo "按 Ctrl+C 退出监控"
echo "=========================================="
echo ""

# 持续监控
while true; do
    clear
    echo "=========================================="
    echo "训练监控: $RUN_NAME"
    echo "时间: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "=========================================="
    echo ""

    # GPU 使用
    echo "🖥️  GPU 状态:"
    nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv,noheader,nounits | \
        awk -F',' '{printf "  使用率: %s%%  |  显存: %s/%s MB  |  温度: %s°C\n", $1, $2, $3, $4}'
    echo ""

    # 检查点数量
    CHECKPOINT_COUNT=$(ls "$LOG_DIR"/*.pt 2>/dev/null | wc -l)
    echo "📦 检查点数量: $CHECKPOINT_COUNT"

    # 最新检查点
    LATEST_CHECKPOINT=$(ls -t "$LOG_DIR"/*.pt 2>/dev/null | head -1)
    if [ -n "$LATEST_CHECKPOINT" ]; then
        echo "📝 最新检查点: $(basename $LATEST_CHECKPOINT)"
        echo "   大小: $(du -h $LATEST_CHECKPOINT | cut -f1)"
        echo "   时间: $(stat -c %y $LATEST_CHECKPOINT | cut -d'.' -f1)"
    fi

    echo ""
    echo "按 Ctrl+C 退出"

    sleep 5
done
