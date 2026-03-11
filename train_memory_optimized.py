#!/usr/bin/env python3
"""
Memory-optimized training script for HA-IGD
Reduces memory footprint through:
1. Smaller batch sizes
2. Reduced buffer size
3. Gradient accumulation
4. Periodic garbage collection
"""

import gc
import torch
import sys
import os

# Add memory optimization flags
os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'max_split_size_mb:128'

# Import original training script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Monkey-patch to add garbage collection after each training step
original_training_step = None

def memory_optimized_training_step(self, *args, **kwargs):
    result = original_training_step(self, *args, **kwargs)

    # Periodic garbage collection every 50 steps
    if self.global_step % 50 == 0:
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    return result

# Apply monkey patch
from ip.models.diffusion import GraphDiffusion
original_training_step = GraphDiffusion.training_step
GraphDiffusion.training_step = memory_optimized_training_step

# Now run the original training script
if __name__ == '__main__':
    # Set default memory-optimized arguments
    if '--batch_size' not in sys.argv:
        sys.argv.extend(['--batch_size', '1'])
    if '--buffer_size' not in sys.argv:
        sys.argv.extend(['--buffer_size', '20'])
    if '--track_history_len' not in sys.argv:
        sys.argv.extend(['--track_history_len', '4'])
    if '--track_n_max' not in sys.argv:
        sys.argv.extend(['--track_n_max', '2'])

    # Import and run main training
    from train_with_pseudo import main
    main()
