"""
Training script with continuous pseudo-demonstration generation
Based on Instant Policy paper training setup

Usage:
    # Train from scratch with continuous pseudo-data generation
    python train_with_pseudo.py --run_name=train_from_scratch --record=1
    
    # Fine-tune on real data
    python train_with_pseudo.py --run_name=finetune --fine_tune=1 \\
        --real_data_path=./data/rlbench --real_data_ratio=0.5
"""
import argparse
import os
import sys
from pathlib import Path

import lightning as L
import pickle
import torch

# Enable Tensor Cores on Ampere/Ada GPUs (RTX 3080Ti, 4090D, etc.)
torch.set_float32_matmul_precision('high')
from torch_geometric.data import DataLoader
from lightning.pytorch.callbacks import LearningRateMonitor
from lightning.pytorch.loggers import WandbLogger

# Add ip to path
sys.path.insert(0, str(Path(__file__).parent / 'ip'))

from ip.models.diffusion import GraphDiffusion
from ip.configs.base_config import config
from ip.utils.continuous_dataset import ContinuousPseudoDataset
from ip.utils.running_dataset import RunningDataset


def create_mixed_dataloader(continuous_dataset, real_data_path=None, 
                            batch_size=16, real_data_ratio=0.5):
    """
    Create a dataloader that mixes continuous pseudo-data with real data.
    
    Paper mentions fine-tuning with "50/50 mix of pseudo-demonstrations and new data"
    """
    if real_data_path and os.path.exists(real_data_path):
        print(f"Mixing pseudo-data with real data from {real_data_path}")
        print(f"Real data ratio: {real_data_ratio}")
        
        # Load real data
        real_dataset = RunningDataset(
            real_data_path, 
            len(os.listdir(real_data_path)),
            rand_g_prob=config['randomize_g_prob']
        )
        
        # Create mixed dataset
        from torch.utils.data import ConcatDataset, WeightedRandomSampler
        
        # Calculate sampling weights
        n_pseudo = len(continuous_dataset)
        n_real = len(real_dataset)
        
        pseudo_weight = (1 - real_data_ratio) / n_pseudo
        real_weight = real_data_ratio / n_real
        
        weights = [pseudo_weight] * n_pseudo + [real_weight] * n_real
        sampler = WeightedRandomSampler(weights, num_samples=n_pseudo, replacement=True)
        
        mixed_dataset = ConcatDataset([continuous_dataset, real_dataset])
        dataloader = DataLoader(
            mixed_dataset, 
            batch_size=batch_size,
            sampler=sampler,
            num_workers=0,  # Must be 0 for continuous generation
            pin_memory=True
        )
        
        return dataloader, real_dataset
    else:
        # Only pseudo-data
        print("Training with pseudo-data only")
        dataloader = DataLoader(
            continuous_dataset,
            batch_size=batch_size,
            shuffle=True,
            num_workers=0,  # Must be 0 for continuous generation
            pin_memory=True
        )
        return dataloader, None


def main():
    parser = argparse.ArgumentParser(description='Train with continuous pseudo-data generation')
    
    # ShapeNet and pseudo-data settings
    parser.add_argument('--shapenet_root', type=str,
                       default='/media/tianyi/Tiantian/tianyiStudy/DataSets/ShapeNetCore.v2',
                       help='Path to ShapeNet dataset')
    parser.add_argument('--num_pseudo_samples', type=int, default=700000,
                       help='Virtual size of pseudo-dataset (paper uses ~700K)')
    parser.add_argument('--buffer_size', type=int, default=1000,
                       help='Size of pre-generation buffer')
    parser.add_argument('--num_generator_threads', type=int, default=4,
                       help='Number of background generation threads')
    parser.add_argument('--preload_size', type=int, default=0,
                       help='Number of meshes to preload into memory (0=on-demand, -1=all)')
    
    # Training settings
    parser.add_argument('--run_name', type=str, default='pseudo_train',
                       help='Name of the run')
    parser.add_argument('--record', type=int, default=0,
                       help='Whether to log and save models [0, 1]')
    parser.add_argument('--use_wandb', type=int, default=0,
                       help='Use Weights & Biases logging [0, 1]')
    parser.add_argument('--save_path', type=str, default='./runs',
                       help='Where to save models and logs')
    
    # Fine-tuning settings
    parser.add_argument('--resume_from', type=str, default=None,
                       help='Path to checkpoint to resume training from (restores optimizer state and step count)')
    parser.add_argument('--fine_tune', type=int, default=0,
                       help='Fine-tune from existing model [0, 1]')
    parser.add_argument('--model_path', type=str, default='./checkpoints',
                       help='Path to existing model for fine-tuning')
    parser.add_argument('--model_name', type=str, default='model.pt',
                       help='Model filename')
    
    # Real data mixing (for PD++ setup in paper)
    parser.add_argument('--real_data_path', type=str, default=None,
                       help='Path to real demonstration data (optional)')
    parser.add_argument('--real_data_ratio', type=float, default=0.5,
                       help='Ratio of real data in mixed training (0.5 = 50/50)')
    parser.add_argument('--data_path_val', type=str, default='./data/val',
                       help='Path to validation data')
    
    # Other settings
    parser.add_argument('--batch_size', type=int, default=16,
                       help='Batch size')
    parser.add_argument('--compile_models', type=int, default=0,
                       help='Compile models for faster training [0, 1]')

    # =========================================================================
    # HA-IGD: History-Aware parameters
    # =========================================================================
    parser.add_argument('--enable_track_nodes', type=int, default=0,
                       help='Enable track nodes for HA-IGD [0, 1]')
    parser.add_argument('--memory_task_ratio', type=float, default=0.3,
                       help='Ratio of memory tasks in training')
    parser.add_argument('--track_history_len', type=int, default=16,
                       help='History length for track encoding')
    parser.add_argument('--track_points_per_obj', type=int, default=5,
                       help='Number of points per object for track')
    parser.add_argument('--track_n_max', type=int, default=5,
                       help='Maximum number of tracked objects')
    parser.add_argument('--track_age_norm_max_sec', type=float, default=2.0,
                       help='Max seconds for track age normalization')
    parser.add_argument('--curriculum_dropout_start', type=float, default=0.05,
                       help='Initial dropout rate for track nodes')
    parser.add_argument('--curriculum_dropout_end', type=float, default=0.25,
                       help='Final dropout rate for track nodes')
    parser.add_argument('--soft_membership_sigma', type=float, default=0.05,
                       help='Sigma for RBF soft membership')
    parser.add_argument('--control_hz', type=float, default=15.0,
                       help='Control frequency Hz')
    parser.add_argument('--track_refresh_hz', type=float, default=3.0,
                       help='Track refresh frequency Hz')

    args = parser.parse_args()
    
    record = bool(args.record)
    use_wandb = bool(args.use_wandb)
    fine_tune = bool(args.fine_tune)
    compile_models = bool(args.compile_models)
    
    # Setup
    save_dir = f'{args.save_path}/{args.run_name}' if record else None
    if record and not os.path.exists(save_dir):
        os.makedirs(save_dir)
    
    print("=" * 80)
    print("Training Instant Policy with Continuous Pseudo-Data Generation")
    print("=" * 80)
    print(f"ShapeNet root: {args.shapenet_root}")
    print(f"Virtual dataset size: {args.num_pseudo_samples}")
    print(f"Buffer size: {args.buffer_size}")
    print(f"Generator threads: {args.num_generator_threads}")
    print(f"Batch size: {args.batch_size}")
    print(f"Fine-tune: {fine_tune}")
    if args.real_data_path:
        print(f"Real data: {args.real_data_path} (ratio: {args.real_data_ratio})")
    print("=" * 80)
    if args.num_generator_threads > 2:
        print("Tip: If the process is killed (OOM) or workers keep failing, try:")
        print("  --num_generator_threads=1 --buffer_size=500")
    
    # Create or load model
    if args.resume_from:
        print(f"\nResuming training from {args.resume_from}...")
        resume_dir = os.path.dirname(args.resume_from)
        config_loaded = pickle.load(open(f'{resume_dir}/config.pkl', 'rb'))
        config_loaded['save_dir'] = save_dir
        config_loaded['record'] = record
        config_loaded['batch_size'] = args.batch_size
        model = GraphDiffusion.load_from_checkpoint(
            args.resume_from,
            config=config_loaded,
            strict=True,
            map_location=config_loaded['device']
        ).to(config_loaded['device'])
        current_config = config_loaded
    elif fine_tune:
        print(f"\nLoading model from {args.model_path}/{args.model_name}...")
        config_loaded = pickle.load(open(f'{args.model_path}/config.pkl', 'rb'))
        config_loaded['compile_models'] = compile_models
        config_loaded['batch_size'] = args.batch_size
        config_loaded['save_dir'] = save_dir
        config_loaded['record'] = record

        model = GraphDiffusion.load_from_checkpoint(
            f'{args.model_path}/{args.model_name}',
            config=config_loaded,
            strict=False,
            map_location=config_loaded['device']
        ).to(config_loaded['device'])

        if compile_models:
            model.model.compile_models()

        current_config = config_loaded
    else:
        print("\nCreating new model...")
        config['save_dir'] = save_dir
        config['record'] = record
        config['batch_size'] = args.batch_size

        # Check if scene_encoder.pt exists, if not disable pre-trained encoder
        if not os.path.exists(config['scene_encoder_path']):
            print(f"Warning: scene_encoder.pt not found at {config['scene_encoder_path']}")
            print("Training from scratch without pre-trained scene encoder")
            config['pre_trained_encoder'] = False

        # =========================================================================
        # HA-IGD: Update config with command line arguments
        # =========================================================================
        config['enable_track_nodes'] = bool(args.enable_track_nodes)
        config['memory_task_ratio'] = args.memory_task_ratio
        config['track_history_len'] = args.track_history_len
        config['track_points_per_obj'] = args.track_points_per_obj
        config['track_n_max'] = args.track_n_max
        config['track_age_norm_max_sec'] = args.track_age_norm_max_sec
        config['curriculum_dropout_start'] = args.curriculum_dropout_start
        config['curriculum_dropout_end'] = args.curriculum_dropout_end
        config['soft_membership_sigma'] = args.soft_membership_sigma
        config['control_hz'] = args.control_hz
        config['track_refresh_hz'] = args.track_refresh_hz

        # Print HA-IGD config if enabled
        if config['enable_track_nodes']:
            print("\n" + "=" * 40)
            print("HA-IGD: History-Aware Mode Enabled")
            print("=" * 40)
            print(f"  Track nodes: {config['enable_track_nodes']}")
            print(f"  Memory task ratio: {config['memory_task_ratio']}")
            print(f"  Track history len: {config['track_history_len']}")
            print(f"  Track n_max: {config['track_n_max']}")
            print(f"  Curriculum dropout: {config['curriculum_dropout_start']} -> {config['curriculum_dropout_end']}")
            print("=" * 40)

        model = GraphDiffusion(config).to(config['device'])
        current_config = config
    
    # Create continuous pseudo-dataset
    print("\nInitializing continuous pseudo-data generation...")
    train_dataset = ContinuousPseudoDataset(
        shapenet_root=args.shapenet_root,
        num_virtual_samples=args.num_pseudo_samples,
        num_demos_per_task=5,
        num_traj_wp=current_config['traj_horizon'],
        pred_horizon=current_config['pre_horizon'],
        buffer_size=args.buffer_size,
        num_generator_threads=args.num_generator_threads,
        rand_g_prob=current_config['randomize_g_prob'],
        num_context_demos=current_config['num_demos'],
        preload_size=args.preload_size,
        # HA-IGD parameters
        enable_track_nodes=current_config.get('enable_track_nodes', False),
        memory_task_ratio=current_config.get('memory_task_ratio', 0.3),
        track_history_len=current_config.get('track_history_len', 16),
        track_points_per_obj=current_config.get('track_points_per_obj', 5),
        track_n_max=current_config.get('track_n_max', 5),
        track_age_norm_max_sec=current_config.get('track_age_norm_max_sec', 2.0),
        control_hz=current_config.get('control_hz', 15.0),
        track_refresh_hz=current_config.get('track_refresh_hz', 3.0),
    )
    
    # Create dataloader (possibly mixed with real data)
    train_dataloader, real_dataset = create_mixed_dataloader(
        train_dataset,
        real_data_path=args.real_data_path,
        batch_size=args.batch_size,
        real_data_ratio=args.real_data_ratio if args.real_data_path else 0.0
    )
    
    # Validation data (real data only)
    if args.data_path_val and os.path.exists(args.data_path_val):
        print(f"Loading validation data from {args.data_path_val}...")
        dset_val = RunningDataset(
            args.data_path_val,
            len(os.listdir(args.data_path_val)),
            rand_g_prob=0
        )
        dataloader_val = DataLoader(dset_val, batch_size=1, shuffle=False)
    else:
        print("⚠️  No validation data found, skipping validation")
        print("   Generate validation set: python generate_pseudo_data.py --val_tasks=10")
        print("   详见文档: docs/updates/VALIDATION_SET_UPDATE.md")
        dataloader_val = None
    
    # Setup logging
    logger = None
    if record:
        if use_wandb:
            logger = WandbLogger(
                project='Instant Policy',
                name=f'{args.run_name}',
                save_dir=save_dir,
                log_model=False
            )
        # Save config
        pickle.dump(current_config, open(f'{save_dir}/config.pkl', 'wb'))
    
    lr_monitor = LearningRateMonitor(logging_interval='step')
    
    # Create trainer
    print("\nSetting up trainer...")
    trainer = L.Trainer(
        enable_checkpointing=False,  # Manual checkpointing
        accelerator=current_config['device'],
        devices=1,
        max_steps=current_config['num_iters'],
        enable_progress_bar=True,
        precision='16-mixed',
        val_check_interval=20000 if dataloader_val else None,  # Skip validation if no val set
        num_sanity_val_steps=2 if dataloader_val else 0,
        check_val_every_n_epoch=None,
        logger=logger,
        log_every_n_steps=500,
        gradient_clip_val=1,
        gradient_clip_algorithm='norm',
        callbacks=[lr_monitor],
    )
    
    # Train
    print("\n" + "=" * 80)
    print("Starting training...")
    print(f"Paper setup: 2.5M steps with ~700K unique pseudo-trajectories")
    print(f"Current setup: {current_config['num_iters']} steps")
    print("=" * 80 + "\n")
    
    try:
        trainer.fit(
            model=model,
            train_dataloaders=train_dataloader,
            val_dataloaders=dataloader_val,
            ckpt_path=args.resume_from if args.resume_from else None
        )
    finally:
        # Always stop generation threads
        train_dataset.stop()
        
        # Print statistics
        stats = train_dataset.get_statistics()
        print("\n" + "=" * 80)
        print("Training Complete!")
        print("=" * 80)
        print(f"Pseudo-demos generated: {stats['samples_generated']}")
        print(f"Generation errors: {stats['generation_errors']}")
        if args.real_data_path and real_dataset:
            print(f"Real demos used: {len(real_dataset)}")
        print("=" * 80)
    
    # Save final model
    if record:
        final_path = f'{save_dir}/final.pt'
        model.save_model(final_path)
        print(f"\nFinal model saved to: {final_path}")


if __name__ == '__main__':
    main()
