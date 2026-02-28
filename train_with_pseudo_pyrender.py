"""
Training script with PyRender-based pseudo-demonstration generation.
Strictly follows paper Appendix D rendering pipeline.

Usage:
    export PYOPENGL_PLATFORM=egl
    python train_with_pseudo_pyrender.py --run_name=train_pyrender --record=1
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

sys.path.insert(0, str(Path(__file__).parent / 'ip'))

from ip.models.diffusion import GraphDiffusion
from ip.configs.base_config import config
from ip.utils.continuous_dataset_pyrender import ContinuousPseudoDatasetPyrender
from ip.utils.running_dataset import RunningDataset


def create_mixed_dataloader(continuous_dataset, real_data_path=None,
                            batch_size=16, real_data_ratio=0.5):
    if real_data_path and os.path.exists(real_data_path):
        print(f"Mixing pseudo-data with real data from {real_data_path}")
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
        dataloader = DataLoader(mixed_dataset, batch_size=batch_size,
                                sampler=sampler, num_workers=0, pin_memory=True)
        return dataloader, real_dataset
    else:
        print("Training with pseudo-data only (PyRender)")
        dataloader = DataLoader(continuous_dataset, batch_size=batch_size,
                                shuffle=True, num_workers=0, pin_memory=True)
        return dataloader, None


def main():
    parser = argparse.ArgumentParser(
        description='Train with PyRender-based pseudo-data generation (paper-accurate)')

    parser.add_argument('--shapenet_root', type=str,
                        default='/media/tianyi/Tiantian/tianyiStudy/DataSets/ShapeNetCore.v2')
    parser.add_argument('--num_pseudo_samples', type=int, default=700000)
    parser.add_argument('--buffer_size', type=int, default=1000)
    parser.add_argument('--num_generator_threads', type=int, default=4)
    parser.add_argument('--run_name', type=str, default='pseudo_train_pyrender')
    parser.add_argument('--record', type=int, default=0)
    parser.add_argument('--use_wandb', type=int, default=0)
    parser.add_argument('--save_path', type=str, default='./runs')
    parser.add_argument('--resume_from', type=str, default=None)
    parser.add_argument('--fine_tune', type=int, default=0)
    parser.add_argument('--model_path', type=str, default='./checkpoints')
    parser.add_argument('--model_name', type=str, default='model.pt')
    parser.add_argument('--real_data_path', type=str, default=None)
    parser.add_argument('--real_data_ratio', type=float, default=0.5)
    parser.add_argument('--data_path_val', type=str, default='./data/val')
    parser.add_argument('--batch_size', type=int, default=16)
    parser.add_argument('--compile_models', type=int, default=0)

    args = parser.parse_args()

    record = bool(args.record)
    fine_tune = bool(args.fine_tune)
    compile_models = bool(args.compile_models)

    save_dir = f'{args.save_path}/{args.run_name}' if record else None
    if record and not os.path.exists(save_dir):
        os.makedirs(save_dir)

    print("=" * 80)
    print("Training Instant Policy — PyRender pipeline (paper-accurate)")
    print("=" * 80)
    print(f"ShapeNet root:      {args.shapenet_root}")
    print(f"Virtual dataset:    {args.num_pseudo_samples}")
    print(f"Buffer size:        {args.buffer_size}")
    print(f"Generator threads:  {args.num_generator_threads}")
    print(f"Batch size:         {args.batch_size}")
    print("Rendering:          PyRender depth cameras (3 views, no wrist)")
    print("=" * 80)

    # Verify PYOPENGL_PLATFORM is set
    if os.environ.get('PYOPENGL_PLATFORM') != 'egl':
        print("WARNING: PYOPENGL_PLATFORM != egl. Headless rendering may fail.")
        print("  Run: export PYOPENGL_PLATFORM=egl")

    # Create or load model
    if args.resume_from:
        print(f"\nResuming from {args.resume_from}...")
        resume_dir = os.path.dirname(args.resume_from)
        config_loaded = pickle.load(open(f'{resume_dir}/config.pkl', 'rb'))
        config_loaded['save_dir'] = save_dir
        config_loaded['record'] = record
        config_loaded['batch_size'] = args.batch_size
        model = GraphDiffusion.load_from_checkpoint(
            args.resume_from, config=config_loaded, strict=True,
            map_location=config_loaded['device']
        ).to(config_loaded['device'])
        current_config = config_loaded
    elif fine_tune:
        print(f"\nFine-tuning from {args.model_path}/{args.model_name}...")
        config_loaded = pickle.load(open(f'{args.model_path}/config.pkl', 'rb'))
        config_loaded['compile_models'] = compile_models
        config_loaded['batch_size'] = args.batch_size
        config_loaded['save_dir'] = save_dir
        config_loaded['record'] = record
        model = GraphDiffusion.load_from_checkpoint(
            f'{args.model_path}/{args.model_name}', config=config_loaded,
            strict=False, map_location=config_loaded['device']
        ).to(config_loaded['device'])
        current_config = config_loaded
    else:
        print("\nCreating new model...")
        config['save_dir'] = save_dir
        config['record'] = record
        config['batch_size'] = args.batch_size
        if not os.path.exists(config['scene_encoder_path']):
            print(f"Warning: scene_encoder.pt not found, training without pre-trained encoder")
            config['pre_trained_encoder'] = False
        model = GraphDiffusion(config).to(config['device'])
        current_config = config

    # Create PyRender-based dataset
    print("\nInitializing PyRender pseudo-data generation...")
    train_dataset = ContinuousPseudoDatasetPyrender(
        shapenet_root=args.shapenet_root,
        num_virtual_samples=args.num_pseudo_samples,
        num_demos_per_task=5,
        num_traj_wp=current_config['traj_horizon'],
        pred_horizon=current_config['pre_horizon'],
        buffer_size=args.buffer_size,
        num_generator_threads=args.num_generator_threads,
        rand_g_prob=current_config['randomize_g_prob'],
        num_context_demos=current_config['num_demos']
    )

    train_dataloader, real_dataset = create_mixed_dataloader(
        train_dataset,
        real_data_path=args.real_data_path,
        batch_size=args.batch_size,
        real_data_ratio=args.real_data_ratio if args.real_data_path else 0.0
    )

    # Validation data
    if args.data_path_val and os.path.exists(args.data_path_val):
        print(f"Loading validation data from {args.data_path_val}...")
        dset_val = RunningDataset(args.data_path_val,
                                  len(os.listdir(args.data_path_val)), rand_g_prob=0)
        dataloader_val = DataLoader(dset_val, batch_size=1, shuffle=False)
    else:
        print("No validation data found, skipping validation")
        dataloader_val = None

    # Logging
    logger = None
    if record:
        if bool(args.use_wandb):
            logger = WandbLogger(project='Instant Policy',
                                 name=args.run_name, save_dir=save_dir, log_model=False)
        pickle.dump(current_config, open(f'{save_dir}/config.pkl', 'wb'))

    lr_monitor = LearningRateMonitor(logging_interval='step')

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

    print("\n" + "=" * 80)
    print("Starting training (PyRender pipeline)...")
    print(f"Steps: {current_config['num_iters']}")
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
        print(f"Pseudo-demos generated: {stats['samples_generated']}")
        print(f"Generation errors:      {stats['generation_errors']}")
        print("=" * 80)

    if record:
        final_path = f'{save_dir}/final.pt'
        model.save_model(final_path)
        print(f"Final model saved to: {final_path}")


if __name__ == '__main__':
    main()
