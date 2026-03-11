import torch
import numpy as np

config = {
    'record': False,
    'save_dir': None,
    'scene_encoder_path': './checkpoints/scene_encoder.pt',
    'pre_trained_encoder': True,
    'freeze_encoder': True,
    'save_every': 5000,
    'compile_models': False,
    # Model config
    'local_num_freq': 10,
    'local_nn_dim': 512,
    'hidden_dim': 1024,
    'num_demos': 2,
    'randomise_num_demos': False,
    'num_demos_test': 2,
    'traj_horizon': 10,
    'device': 'cuda',
    'batch_size': 4,
    'batch_size_val': 1,
    'num_scenes_nodes': 16,
    'pre_horizon': 8,
    'pos_in_nodes': True,
    'num_layers': 2,

    # Diffusion config
    'lr': 1e-5,
    'weight_decay': 1e-2,
    'use_lr_scheduler': True,
    'num_warmup_steps': 1000,
    'num_diffusion_iters_train': 100,
    'num_diffusion_iters_test': 8,
    'num_iters': 50000000001,

    'test_every': 50000,
    'randomize_g_prob': 0.1,

    'min_actions': torch.tensor([-0.01] * 3 + [-np.deg2rad(3), -np.deg2rad(3), -np.deg2rad(3)], dtype=torch.float32),
    'max_actions': torch.tensor([0.01] * 3 + [np.deg2rad(3), np.deg2rad(3), np.deg2rad(3)], dtype=torch.float32),

    # =========================================================================
    # HA-IGD: History-Aware Instant Graph Diffusion Config
    # =========================================================================
    # Track nodes (memory) configuration
    'enable_track_nodes': False,          # 主开关：启用历史轨迹节点
    'track_n_max': 5,                    # 最大对象数
    'track_history_len': 16,              # 历史帧数
    'track_points_per_obj': 5,            # 每个对象的关键点数
    'track_hidden_dim': 512,              # Track encoder 输出维度
    'track_age_embed_dim': 32,            # Track age 编码维度
    'track_age_norm_max_sec': 2.0,        # Track age 归一化最大秒数

    # Soft membership (RBF overlap)
    'soft_membership_sigma': 0.05,       # RBF sigma for track-geo overlap

    # Asynchronous refresh (for deployment)
    'control_hz': 15.0,                  # 控制频率
    'track_refresh_hz': 3.0,              # Track 更新频率

    # Curriculum dropout
    'curriculum_dropout_start': 0.05,    # 起始 dropout 率
    'curriculum_dropout_end': 0.25,      # 最终 dropout 率
    'curriculum_dropout_warmup_steps': 50000,
    'curriculum_dropout_hold_steps': 200000,
    'track_modality_dropout_eval': 0.0,  # 评估时 dropout 率

    # Memory task training
    'memory_task_ratio': 0.3,             # 记忆任务采样比例
    'curriculum_stage_steps': (50000, 200000),  # 课程学习阶段

    # Graph topology (V0)
    'enable_track_track_edges': False,    # V0 关闭 track-track 边
    'enable_track_geo_edges': True,       # 启用 track-geo 边
    'enable_demo_current_track_edges': True,  # Demo-Current track 对齐边
    'enable_current_track_to_action_edges': True,  # Track -> 动作边
}
