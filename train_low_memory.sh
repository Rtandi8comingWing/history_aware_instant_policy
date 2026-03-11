#!/bin/bash
# Low memory training configuration for HA-IGD

python train_with_pseudo.py \
    --run_name=ha_igd_low_mem \
    --enable_track_nodes=1 \
    --batch_size=1 \
    --track_history_len=4 \
    --track_n_max=2 \
    --track_points_per_obj=3 \
    --num_generator_threads=1 \
    --buffer_size=20 \
    --num_demos=1 \
    --num_scenes_nodes=8 \
    --hidden_dim=512 \
    --local_nn_dim=256
