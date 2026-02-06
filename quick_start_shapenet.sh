#!/bin/bash
# Quick Start Script for ShapeNet Pseudo-Data Training
# Instant Policy - ICLR 2025

set -e

echo "================================================================================"
echo "Instant Policy - ShapeNet Pseudo-Data Training Quick Start"
echo "================================================================================"
echo ""

# Configuration
SHAPENET_ROOT="/media/tianyi/Tiantian/tianyiStudy/DataSets/ShapeNetCore.v2"
CONDA_ENV="ip_env"

# Activate conda environment
echo "Step 1: Activating conda environment '$CONDA_ENV'..."
source ~/miniconda3/etc/profile.d/conda.sh
conda activate $CONDA_ENV
export PYOPENGL_PLATFORM=egl

echo "✅ Environment activated"
echo ""

# Test system
echo "Step 2: Testing pseudo-data generation system..."
python test_pseudo_generation.py
if [ $? -eq 0 ]; then
    echo "✅ System test passed"
else
    echo "❌ System test failed!"
    exit 1
fi
echo ""

# Ask user for training mode
echo "================================================================================"
echo "Choose training mode:"
echo "================================================================================"
echo "  1) Quick test (1K samples, ~5 minutes)"
echo "  2) Small scale (100K samples, good for testing)"
echo "  3) Full scale (700K samples, paper setting, ~5 days)"
echo "  4) Generate data only (batch generation)"
echo ""
read -p "Enter choice [1-4]: " choice
echo ""

case $choice in
    1)
        echo "Starting quick test training..."
        python train_with_pseudo.py \
            --shapenet_root=$SHAPENET_ROOT \
            --run_name=quick_test \
            --num_pseudo_samples=1000 \
            --buffer_size=100 \
            --num_generator_threads=2 \
            --batch_size=8
        ;;
    2)
        echo "Starting small scale training..."
        python train_with_pseudo.py \
            --shapenet_root=$SHAPENET_ROOT \
            --run_name=small_scale \
            --num_pseudo_samples=100000 \
            --buffer_size=1000 \
            --num_generator_threads=4 \
            --batch_size=16 \
            --record=1
        ;;
    3)
        echo "Starting full scale training (paper setting)..."
        python train_with_pseudo.py \
            --shapenet_root=$SHAPENET_ROOT \
            --run_name=full_scale \
            --num_pseudo_samples=700000 \
            --buffer_size=2000 \
            --num_generator_threads=8 \
            --batch_size=16 \
            --record=1 \
            --use_wandb=1
        ;;
    4)
        read -p "How many tasks to generate? [1000]: " num_tasks
        num_tasks=${num_tasks:-1000}
        read -p "Number of workers? [4]: " num_workers
        num_workers=${num_workers:-4}
        
        echo "Generating $num_tasks tasks with $num_workers workers..."
        python generate_pseudo_data.py \
            --shapenet_root=$SHAPENET_ROOT \
            --num_tasks=$num_tasks \
            --num_workers=$num_workers \
            --output_dir=./data/pseudo_train
        
        echo ""
        echo "✅ Data generation complete!"
        echo "   Output: ./data/pseudo_train/"
        echo ""
        echo "To train with this data:"
        echo "  python ip/train.py --data_path_train=./data/pseudo_train --record=1"
        ;;
    *)
        echo "Invalid choice!"
        exit 1
        ;;
esac

echo ""
echo "================================================================================"
echo "✅ Done!"
echo "================================================================================"
echo ""
echo "📚 查看完整文档："
echo "   主文档: docs/guides/README_SHAPENET_TRAINING.md"
echo "   快速参考: docs/references/QUICK_SUMMARY.txt"
echo "   文档中心: docs/README.md"
