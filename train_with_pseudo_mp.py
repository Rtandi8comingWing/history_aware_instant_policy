"""
Training script with multiprocessing-based pseudo-demonstration generation.
Much faster than threading version due to bypassing Python GIL.

Usage:
    python train_with_pseudo_mp.py --run_name=train_mp --record=1
"""
import argparse
import os
import sys
from pathlib import Path

import lightning as L
import pickle
import torch
from torch_geometric.data import DataLoader
from lightning.pytorch.callbacks import LearningRateMonitor
from lightning.pytorch.loggers import WandbLogger

# Add ip to path
sys.path.insert(0, str(Path(__file__).parent / 'ip'))

from ip.models.diffusion import GraphDiffusion
from ip.configs.base_config import config
from ip.utils.continuous_dataset_mp import ContinuousPseudoDatasetMP
from ip.utils.running_dataset import RunningDataset


def create_mixed_dataloader(continuous_dataset, real_data_path=None,
                            batch_size=16, real_data_ratio=0.5):
    """Create a dataloader that mixes continuous pseudo-data with real data."""
    if real_data_path and os.path.exists(real_data_path):
        print(f"Mixing pseudo-data with real data from {real_data_path}")
        print(f"Real data ratio: {real_data_ratio}")

        real_dataset = RunningDataset(
            real_data_path,
            len(os.listdir(real_data_path)),
            rand_g_prob=config['randomize_g_prob']
        )

        from torch.utils.data import ConcatDataset, WeightedRandomSampler

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
        print("Training with pseudo-data only (multiprocessing)")
        dataloader = DataLoader(
            continuous_dataset,
            batch_size=batch_size,
            shuffle=True,
            num_workers=0,  # Must be 0 for continuous generation
            pin_memory=True
        )
        return dataloader, None


def main():
    parser = argparse.ArgumentParser(description='Train with multiprocessing pseudo-data generation')

    # ShapeNet and pseudo-data settings
    parser.add_argument('--shapenet_root', type=str,
                       default='/media/tianyi/Tiantian/tianyiStudy/DataSets/ShapeNetCore.v2',
                       help='Path to ShapeNet dataset')
    parser.add_argument('--num_pseudo_samples', type=int, default=700000,
                       help='Virtual size of pseudo-dataset')
    parser.add_argument('--buffer_size', type=int, default=1000,
                       help='Size of pre-generation buffer')
    parser.add_argument('--num_generator_processes', type=int, default=8,
                       help='Number of background generation processes')

    # Training settings
    parser.add_argument('--run_name', type=str, default='pseudo_train_mp',
                       help='Name of the run')
    parser.add_argument('--record', type=int, default=0,
                       help='Whether to log and save models [0, 1]')
    parser.add_argument('--use_wandb', type=int, default=0,
                       help='Use Weights & Biases logging [0, 1]')
    parser.add_argument('--save_path', type=str, default='./runs',
                       help='Where to save models and logs')

    # Fine-tuning settings
    parser.add_argument('--resume_from', type=str, default=None,
                       help='Path to checkpoint to resume from')
    parser.add_argument('--fine_tune', type=int, default=0,
                       help='Fine-tune from existing model [0, 1]')
    parser.add_argument('--model_path', type=str, default='./checkpoints',
                       help='Path to existing model for fine-tuning')
    parser.add_argument('--model_name', type=str, default='model.pt',
                       help='Model filename')

    # Real data mixing
    parser.add_argument('--real_data_path', type=str, default=None,
                       help='Path to real demonstration data (optional)')
    parser.add_argument('--real_data_ratio', type=float, default=0.5,
                       help='Ratio of real data in mixed training')
    parser.add_argument('--data_path_val', type=str, default='./data/val',
                       help='Path to validation data')

    # Other settings
    parser.add_argument('--batch_size', type=int, default=16,
                       help='Batch size')
    parser.add_argument('--compile_models', type=int, default=0,
                       help='Compile models for faster training [0, 1]')

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
    print("Training Instant Policy with Multiprocessing Pseudo-Data Generation")
    print("=" * 80)
    print(f"ShapeNet root: {args.shapenet_root}")
    print(f"Virtual dataset size: {args.num_pseudo_samples}")
    print(f"Buffer size: {args.buffer_size}")
    print(f"Generator processes: {args.num_generator_processes}")
    print(f"Batch size: {args.batch_size}")
    print(f"Fine-tune: {fine_tune}")
    if args.real_data_path:
        print(f"Real data: {args.real_data_path} (ratio: {args.real_data_ratio})")
    print("=" * 80)
    print("Note: Using multiprocessing (bypasses GIL) for much faster generation")

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

        if not os.path.exists(config['scene_encoder_path']):
            print(f"Warning: scene_encoder.pt not found at {config['scene_encoder_path']}")
            print("Training from scratch without pre-trained scene encoder")
            config['pre_trained_encoder'] = False

        model = GraphDiffusion(config).to(config['device'])
        current_config = config

    # Create continuous pseudo-dataset with multiprocessing
    print("\nInitializing multiprocessing pseudo-data generation...")
    train_dataset = ContinuousPseudoDatasetMP(
        shapenet_root=args.shapenet_root,
        num_virtual_samples=args.num_pseudo_samples,
        num_demos_per_task=5,
        num_traj_wp=current_config['traj_horizon'],
        pred_horizon=current_config['pre_horizon'],
        buffer_size=args.buffer_size,
        num_generator_processes=args.num_generator_processes,
        rand_g_prob=current_config['randomize_g_prob'],
        num_context_demos=current_config['num_demos']
    )

    # Create dataloader
    train_dataloader, real_dataset = create_mixed_dataloader(
        train_dataset,
        real_data_path=args.real_data_path,
        batch_size=args.batch_size,
        real_data_ratio=args.real_data_ratio if args.real_data_path else 0.0
    )

    # Validation data
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
        pickle.dump(current_config, open(f'{save_dir}/config.pkl', 'wb'))

    lr_monitor = LearningRateMonitor(logging_interval='step')

    # Create trainer
    print("\nSetting up trainer...")
    trainer = L.Trainer(
        enable_checkpointing=False,
        accelerator=current_config['device'],
        devices=1,
        max_steps=current_config['num_iters'],
        enable_progress_bar=True,
        precision='16-mixed',
        val_check_interval=20000 if dataloader_val else None,
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
        train_dataset.stop()

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
