#!/bin/bash
# Quick start script for training with pseudo-data generation (small sample)
# This script runs a minimal training test to verify the system works

echo "=========================================="
echo "Training Instant Policy with Pseudo-Data"
echo "Small Sample Test (100 samples)"
echo "=========================================="

# Activate environment
source ~/miniconda3/etc/profile.d/conda.sh
conda activate ip_env

# Set EGL platform for headless rendering (already set in code, but just in case)
export PYOPENGL_PLATFORM=egl

# Run training with minimal configuration
python train_with_pseudo.py \
    --run_name=test_small \
    --num_pseudo_samples=100 \
    --buffer_size=10 \
    --num_generator_threads=1 \
    --batch_size=2 \
    --record=0

echo ""
echo "=========================================="
echo "Training test completed!"
echo "=========================================="
