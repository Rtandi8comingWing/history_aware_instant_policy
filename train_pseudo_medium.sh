#!/bin/bash
# Medium-scale training with pseudo-data generation
# Suitable for validation and testing (10K samples)

echo "=========================================="
echo "Training Instant Policy with Pseudo-Data"
echo "Medium Scale (10K samples)"
echo "=========================================="

# Activate environment
source ~/miniconda3/etc/profile.d/conda.sh
conda activate ip_env

# Set EGL platform for headless rendering
export PYOPENGL_PLATFORM=egl

# Run training with medium configuration
python train_with_pseudo.py \
    --run_name=train_medium \
    --num_pseudo_samples=10000 \
    --buffer_size=500 \
    --num_generator_threads=2 \
    --batch_size=4 \
    --record=1 \
    --save_path=./runs

echo ""
echo "=========================================="
echo "Training completed!"
echo "Check ./runs/train_medium for results"
echo "=========================================="
