#!/bin/bash
# Full-scale training with pseudo-data generation
# Paper setup: ~700K samples (production training)

echo "=========================================="
echo "Training Instant Policy with Pseudo-Data"
echo "Full Scale (700K samples - Paper Setup)"
echo "=========================================="
echo "WARNING: This will take several days on high-end GPU"
echo "Press Ctrl+C within 5 seconds to cancel..."
sleep 5

# Activate environment
source ~/miniconda3/etc/profile.d/conda.sh
conda activate ip_env

# Set EGL platform for headless rendering
export PYOPENGL_PLATFORM=egl

# Run training with full configuration
python train_with_pseudo.py \
    --run_name=train_full_$(date +%Y%m%d_%H%M%S) \
    --num_pseudo_samples=700000 \
    --buffer_size=1000 \
    --num_generator_threads=4 \
    --batch_size=16 \
    --record=1 \
    --save_path=./runs \
    --use_wandb=0

echo ""
echo "=========================================="
echo "Training completed!"
echo "Check ./runs/ for results"
echo "=========================================="
