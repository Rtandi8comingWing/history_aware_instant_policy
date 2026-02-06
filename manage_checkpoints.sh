#!/bin/bash
# Checkpoint Management Utility
# 方便管理训练生成的 checkpoints

set -e

RUNS_DIR="./runs"

show_help() {
    cat << 'EOF'
╔════════════════════════════════════════════════════════════════════════════╗
║                                                                            ║
║                   Checkpoint 管理工具                                       ║
║                                                                            ║
╚════════════════════════════════════════════════════════════════════════════╝

用法:
  ./manage_checkpoints.sh <command> [options]

命令:

  list <run_name>              列出某次训练的所有 checkpoints
  prepare <run_name> <ckpt>    准备 checkpoint 用于推理
  clean <run_name> [keep_n]    清理旧 checkpoints，保留最近 N 个
  backup <run_name> <ckpt>     备份重要的 checkpoint
  compare <run_name>           对比所有 checkpoints 的性能
  info <run_name> <ckpt>       显示 checkpoint 详细信息

示例:

  # 列出所有 checkpoints
  ./manage_checkpoints.sh list my_train

  # 准备最佳模型用于推理
  ./manage_checkpoints.sh prepare my_train best.pt

  # 清理旧 checkpoints，保留最近 5 个
  ./manage_checkpoints.sh clean my_train 5

  # 备份最佳模型
  ./manage_checkpoints.sh backup my_train best.pt

EOF
}

list_checkpoints() {
    local run_name=$1
    local run_dir="$RUNS_DIR/$run_name"
    
    if [ ! -d "$run_dir" ]; then
        echo "❌ 训练目录不存在: $run_dir"
        exit 1
    fi
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Checkpoints in: $run_dir"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # List all .pt files
    if ls "$run_dir"/*.pt 1> /dev/null 2>&1; then
        echo "文件名              大小        修改时间"
        echo "───────────────────────────────────────────────────────────────────"
        ls -lh "$run_dir"/*.pt | awk '{printf "%-20s %-10s %s %s %s\n", $9, $5, $6, $7, $8}' | sed "s|$run_dir/||g"
        echo ""
        echo "总计: $(ls "$run_dir"/*.pt | wc -l) 个 checkpoints"
        
        # Show config.pkl if exists
        if [ -f "$run_dir/config.pkl" ]; then
            echo "✅ config.pkl 存在"
        else
            echo "⚠️  config.pkl 缺失（推理需要）"
        fi
    else
        echo "❌ 未找到任何 checkpoint"
    fi
    echo ""
}

prepare_for_inference() {
    local run_name=$1
    local ckpt_name=$2
    local run_dir="$RUNS_DIR/$run_name"
    
    if [ ! -f "$run_dir/$ckpt_name" ]; then
        echo "❌ Checkpoint 不存在: $run_dir/$ckpt_name"
        exit 1
    fi
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "准备 checkpoint 用于推理"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # Copy to model.pt
    echo "1. 复制 $ckpt_name 为 model.pt..."
    cp "$run_dir/$ckpt_name" "$run_dir/model.pt"
    echo "   ✅ 已复制"
    
    # Check config.pkl
    echo ""
    echo "2. 检查配置文件..."
    if [ -f "$run_dir/config.pkl" ]; then
        echo "   ✅ config.pkl 存在"
    else
        echo "   ⚠️  config.pkl 缺失"
        echo "   推理时将使用默认配置"
    fi
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "✅ 准备完成！"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "现在可以运行推理:"
    echo "  python deploy_sim.py --model_path=$run_dir --task_name=plate_out"
    echo ""
}

clean_old_checkpoints() {
    local run_name=$1
    local keep_n=${2:-3}  # 默认保留 3 个
    local run_dir="$RUNS_DIR/$run_name"
    
    if [ ! -d "$run_dir" ]; then
        echo "❌ 训练目录不存在: $run_dir"
        exit 1
    fi
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "清理旧 checkpoints"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "保留最近 $keep_n 个定期 checkpoint"
    echo "保留 best.pt 和 last.pt/final.pt"
    echo ""
    
    # Get numbered checkpoints only (exclude best.pt, last.pt, final.pt, model.pt)
    cd "$run_dir"
    numbered_ckpts=$(ls -t *.pt 2>/dev/null | grep -E '^[0-9]+\.pt$' || true)
    
    if [ -z "$numbered_ckpts" ]; then
        echo "✅ 没有需要清理的 checkpoints"
        return
    fi
    
    total=$(echo "$numbered_ckpts" | wc -l)
    echo "找到 $total 个定期 checkpoints"
    
    if [ $total -le $keep_n ]; then
        echo "✅ 数量不超过 $keep_n，无需清理"
        return
    fi
    
    to_delete=$(echo "$numbered_ckpts" | tail -n +$((keep_n + 1)))
    delete_count=$(echo "$to_delete" | wc -l)
    
    echo ""
    echo "将删除 $delete_count 个旧 checkpoints:"
    echo "$to_delete"
    echo ""
    
    read -p "确认删除？[y/N] " confirm
    if [[ $confirm =~ ^[Yy]$ ]]; then
        echo "$to_delete" | xargs rm -f
        echo "✅ 已删除 $delete_count 个旧 checkpoints"
        
        # Calculate freed space
        freed_space=$(echo "$delete_count * 900" | bc)
        echo "💾 释放约 ${freed_space} MB 磁盘空间"
    else
        echo "❌ 取消删除"
    fi
    
    cd - > /dev/null
    echo ""
}

backup_checkpoint() {
    local run_name=$1
    local ckpt_name=$2
    local run_dir="$RUNS_DIR/$run_name"
    local backup_dir="./backups"
    
    if [ ! -f "$run_dir/$ckpt_name" ]; then
        echo "❌ Checkpoint 不存在: $run_dir/$ckpt_name"
        exit 1
    fi
    
    mkdir -p "$backup_dir"
    
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_name="${run_name}_${ckpt_name%.pt}_${timestamp}.pt"
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "备份 checkpoint"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "源文件: $run_dir/$ckpt_name"
    echo "备份到: $backup_dir/$backup_name"
    echo ""
    
    cp "$run_dir/$ckpt_name" "$backup_dir/$backup_name"
    
    # Also backup config.pkl
    if [ -f "$run_dir/config.pkl" ]; then
        cp "$run_dir/config.pkl" "$backup_dir/${run_name}_config_${timestamp}.pkl"
        echo "✅ 已备份 checkpoint 和配置文件"
    else
        echo "✅ 已备份 checkpoint"
        echo "⚠️  config.pkl 不存在，未备份配置"
    fi
    
    echo ""
}

show_checkpoint_info() {
    local run_name=$1
    local ckpt_name=$2
    local run_dir="$RUNS_DIR/$run_name"
    local ckpt_path="$run_dir/$ckpt_name"
    
    if [ ! -f "$ckpt_path" ]; then
        echo "❌ Checkpoint 不存在: $ckpt_path"
        exit 1
    fi
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Checkpoint 信息"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "文件: $ckpt_path"
    echo ""
    
    # File info
    ls -lh "$ckpt_path" | awk '{print "大小: " $5 "\n修改时间: " $6 " " $7 " " $8}'
    echo ""
    
    # Try to extract info using Python
    python << PYEOF
import torch
import sys

try:
    ckpt = torch.load('$ckpt_path', map_location='cpu')
    
    if 'global_step' in ckpt:
        print(f"训练步数: {ckpt['global_step']:,}")
    if 'epoch' in ckpt:
        print(f"训练轮数: {ckpt['epoch']}")
    if 'state_dict' in ckpt:
        num_params = sum(p.numel() for p in ckpt['state_dict'].values())
        print(f"参数数量: {num_params:,}")
    
    print("\n包含的组件:")
    if 'state_dict' in ckpt:
        print("  ✅ 模型权重 (state_dict)")
    if 'optimizer_states' in ckpt:
        print("  ✅ 优化器状态")
    if 'lr_schedulers' in ckpt:
        print("  ✅ 学习率调度器")
    
except Exception as e:
    print(f"⚠️  无法读取详细信息: {e}")
    sys.exit(0)
PYEOF
    
    echo ""
}

# Main
case "$1" in
    list)
        if [ -z "$2" ]; then
            echo "用法: ./manage_checkpoints.sh list <run_name>"
            exit 1
        fi
        list_checkpoints "$2"
        ;;
    prepare)
        if [ -z "$2" ] || [ -z "$3" ]; then
            echo "用法: ./manage_checkpoints.sh prepare <run_name> <checkpoint>"
            exit 1
        fi
        prepare_for_inference "$2" "$3"
        ;;
    clean)
        if [ -z "$2" ]; then
            echo "用法: ./manage_checkpoints.sh clean <run_name> [keep_n]"
            exit 1
        fi
        clean_old_checkpoints "$2" "${3:-3}"
        ;;
    backup)
        if [ -z "$2" ] || [ -z "$3" ]; then
            echo "用法: ./manage_checkpoints.sh backup <run_name> <checkpoint>"
            exit 1
        fi
        backup_checkpoint "$2" "$3"
        ;;
    info)
        if [ -z "$2" ] || [ -z "$3" ]; then
            echo "用法: ./manage_checkpoints.sh info <run_name> <checkpoint>"
            exit 1
        fi
        show_checkpoint_info "$2" "$3"
        ;;
    compare)
        echo "⚠️  compare 功能待实现"
        echo "请手动运行推理对比不同 checkpoints"
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        show_help
        exit 1
        ;;
esac
