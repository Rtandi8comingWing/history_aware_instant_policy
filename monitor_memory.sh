#!/bin/bash
# 实时监控训练内存使用

echo "=========================================="
echo "训练内存监控"
echo "=========================================="
echo ""
echo "按 Ctrl+C 退出"
echo ""

while true; do
    clear
    echo "=========================================="
    echo "时间: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "=========================================="
    echo ""
    
    # 系统内存
    echo "📊 系统内存:"
    free -h | grep -E "Mem|Swap"
    echo ""
    
    # GPU 内存
    echo "🖥️  GPU 状态:"
    nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits | \
        awk -F',' '{printf "  显存: %s/%s MB  |  使用率: %s%%\n", $1, $2, $3}'
    echo ""
    
    # Python 进程
    echo "🐍 Python 进程:"
    ps aux | grep -E "python.*train_with_pseudo" | grep -v grep | \
        awk '{printf "  PID: %s  |  CPU: %s%%  |  MEM: %s%%  |  时间: %s\n", $2, $3, $4, $10}'
    
    if [ -z "$(ps aux | grep -E 'python.*train_with_pseudo' | grep -v grep)" ]; then
        echo "  ⚠️  未检测到训练进程"
    fi
    
    echo ""
    echo "=========================================="
    
    sleep 2
done
