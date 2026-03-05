"""
Offline pseudo-demonstration generation using PyRender depth rendering.

This mirrors generate_pseudo_data.py but uses PseudoDemoGeneratorPyrender
so output remains fully compatible with ip/train.py via save_sample.

Usage example:
    PYOPENGL_PLATFORM=egl DISPLAY= python generate_pseudo_data_pyrender.py \
        --output_dir ./data/pseudo_train_pyrender --num_tasks 100 --num_workers 1
"""
import argparse
import os
import sys
import time
from pathlib import Path

import multiprocessing as mp
import numpy as np
from tqdm import tqdm

# Add ip to path
sys.path.insert(0, str(Path(__file__).parent / 'ip'))

from ip.utils.shapenet_loader import ShapeNetLoader
from ip.utils.pseudo_demo_generator_pyrender import PseudoDemoGeneratorPyrender
from ip.utils.data_proc import sample_to_cond_demo, sample_to_live, save_sample


def _ensure_egl_env():
    """Ensure headless EGL rendering environment."""
    current_platform = os.environ.get('PYOPENGL_PLATFORM', '').lower()
    if current_platform and current_platform != 'egl':
        raise RuntimeError(
            f"PYOPENGL_PLATFORM must be 'egl' for PyRender offline rendering, got '{current_platform}'."
        )

    os.environ['PYOPENGL_PLATFORM'] = 'egl'
    os.environ['DISPLAY'] = ''


def generate_one_pseudo_task(task_id, shapenet_loader, output_dir, num_demos_per_task=5,
                             num_traj_wp=10, pred_horizon=8):
    """Generate one pseudo-task and save all produced training samples."""
    generator = PseudoDemoGeneratorPyrender()

    # Keep paper-aligned setup: 2 ShapeNet objects per task.
    objects = shapenet_loader.get_random_objects(n=2)

    samples_generated = 0
    demos = []

    for demo_idx in range(num_demos_per_task):
        try:
            demo = generator.generate_pseudo_demonstration(objects)
            cond_demo = sample_to_cond_demo(demo, num_traj_wp)
            demos.append(cond_demo)
        except Exception as e:
            print(f"Failed to generate demo {demo_idx} for task {task_id}: {e}")
            continue

    if len(demos) < 2:
        return 0

    for i in range(len(demos)):
        try:
            live_demo = sample_to_live(
                {
                    'pcds': demos[i]['obs'],
                    'T_w_es': demos[i]['T_w_es'],
                    'grips': demos[i]['grips'],
                },
                pred_horizon=pred_horizon,
                subsample=False,
            )

            # Match existing offline generation behavior: fixed 2 context demos.
            num_context = 2
            context_indices = [j for j in range(len(demos)) if j != i]

            if len(context_indices) >= num_context:
                context_indices = np.random.choice(context_indices, num_context, replace=False).tolist()
            else:
                while len(context_indices) < num_context:
                    context_indices.append(context_indices[len(context_indices) % len(context_indices)])

            context_demos = [demos[j] for j in context_indices[:num_context]]

            full_sample = {
                'demos': context_demos,
                'live': live_demo,
            }

            offset = task_id * 1000 + i * 100
            save_sample(full_sample, save_dir=output_dir, offset=offset, scene_encoder=None)
            samples_generated += len(live_demo['obs'])

        except Exception as e:
            print(f"Failed to create training sample {i} for task {task_id}: {e}")
            continue

    return samples_generated


def generate_worker(args):
    """Worker function for parallel generation."""
    task_range, shapenet_root, output_dir, num_demos_per_task, num_traj_wp, pred_horizon = args

    _ensure_egl_env()
    loader = ShapeNetLoader(shapenet_root)

    total_samples = 0
    for task_id in task_range:
        n_samples = generate_one_pseudo_task(
            task_id,
            loader,
            output_dir,
            num_demos_per_task,
            num_traj_wp,
            pred_horizon,
        )
        total_samples += n_samples

    return total_samples


def main():
    parser = argparse.ArgumentParser(description='Generate PyRender pseudo-demonstrations for offline training')
    parser.add_argument('--shapenet_root', type=str,
                        default='/media/tianyi/Tiantian/tianyiStudy/DataSets/ShapeNetCore.v2',
                        help='Path to ShapeNet dataset')
    parser.add_argument('--output_dir', type=str, default='./data/pseudo_train_pyrender',
                        help='Output directory for generated data')
    parser.add_argument('--num_tasks', type=int, default=100000,
                        help='Number of pseudo-tasks to generate')
    parser.add_argument('--num_demos_per_task', type=int, default=5,
                        help='Number of demonstrations per pseudo-task')
    parser.add_argument('--num_traj_wp', type=int, default=10,
                        help='Number of waypoints in demonstration trajectories')
    parser.add_argument('--pred_horizon', type=int, default=8,
                        help='Prediction horizon for actions')
    parser.add_argument('--num_workers', type=int, default=4,
                        help='Number of parallel workers')
    parser.add_argument('--gen_val_set', type=int, default=1,
                        help='Generate validation set [0, 1]')
    parser.add_argument('--val_tasks', type=int, default=10,
                        help='Number of validation tasks to generate')

    args = parser.parse_args()

    _ensure_egl_env()

    os.makedirs(args.output_dir, exist_ok=True)

    gen_val = bool(args.gen_val_set)
    if gen_val:
        val_dir = os.path.join(os.path.dirname(args.output_dir), 'val')
        os.makedirs(val_dir, exist_ok=True)

    print("=" * 80)
    print("PyRender Offline Pseudo-Demonstration Generation")
    print("=" * 80)
    print(f"ShapeNet root: {args.shapenet_root}")
    print(f"Output directory: {args.output_dir}")
    print(f"Number of pseudo-tasks: {args.num_tasks}")
    print(f"Demos per task: {args.num_demos_per_task}")
    print(f"Trajectory waypoints: {args.num_traj_wp}")
    print(f"Prediction horizon: {args.pred_horizon}")
    print(f"Parallel workers: {args.num_workers}")
    print(f"PYOPENGL_PLATFORM: {os.environ.get('PYOPENGL_PLATFORM')}")
    print(f"DISPLAY: '{os.environ.get('DISPLAY', '')}'")
    if gen_val:
        print(f"Validation set: {val_dir} ({args.val_tasks} tasks)")
    print("=" * 80)

    print("\nInitializing ShapeNet loader...")
    loader = ShapeNetLoader(args.shapenet_root)
    print(f"Loaded {loader.get_num_categories()} categories with {loader.get_num_models()} models")

    print(f"\nGenerating {args.num_tasks} pseudo-tasks using {args.num_workers} workers...")

    tasks_per_worker = args.num_tasks // args.num_workers
    task_ranges = [
        range(i * tasks_per_worker, (i + 1) * tasks_per_worker)
        for i in range(args.num_workers)
    ]

    if args.num_tasks % args.num_workers != 0:
        task_ranges[-1] = range((args.num_workers - 1) * tasks_per_worker, args.num_tasks)

    worker_args = [
        (
            task_range,
            args.shapenet_root,
            args.output_dir,
            args.num_demos_per_task,
            args.num_traj_wp,
            args.pred_horizon,
        )
        for task_range in task_ranges
    ]

    start_time = time.time()

    if args.num_workers > 1:
        with mp.Pool(args.num_workers) as pool:
            results = list(tqdm(
                pool.imap(generate_worker, worker_args),
                total=len(worker_args),
                desc="Workers",
            ))
        total_samples = sum(results)
    else:
        total_samples = 0
        for task_id in tqdm(range(args.num_tasks), desc="Generating"):
            n_samples = generate_one_pseudo_task(
                task_id,
                loader,
                args.output_dir,
                args.num_demos_per_task,
                args.num_traj_wp,
                args.pred_horizon,
            )
            total_samples += n_samples

    elapsed = time.time() - start_time

    print("\n" + "=" * 80)
    print("Training Set Generation Complete!")
    print("=" * 80)
    print(f"Total pseudo-tasks generated: {args.num_tasks}")
    print(f"Total training samples: {total_samples}")
    print(f"Time elapsed: {elapsed:.1f}s ({elapsed/60:.1f} minutes)")
    print(f"Average time per task: {elapsed/args.num_tasks:.2f}s")
    print(f"Samples saved in: {args.output_dir}")
    print("=" * 80)

    if gen_val:
        print("\n" + "=" * 80)
        print("Generating Validation Set...")
        print("=" * 80)

        val_samples = 0
        print(f"Generating {args.val_tasks} validation tasks...")
        for task_id in tqdm(range(args.val_tasks), desc="Val tasks"):
            n_samples = generate_one_pseudo_task(
                task_id,
                loader,
                val_dir,
                args.num_demos_per_task,
                args.num_traj_wp,
                args.pred_horizon,
            )
            val_samples += n_samples

        print(f"✅ Validation set created: {val_dir}")
        print(f"   Tasks: {args.val_tasks}, Samples: {val_samples}")
        print("=" * 80)

    print("\n" + "=" * 80)
    print("All Data Generated Successfully!")
    print("=" * 80)
    print(f"Training set: {args.output_dir} ({total_samples} samples)")
    if gen_val:
        print(f"Validation set: {val_dir} ({val_samples} samples)")
    print("\nYou can now train with:")
    if gen_val:
        print(f"  python ip/train.py --data_path_train={args.output_dir} --data_path_val={val_dir} --record=1")
    else:
        print(f"  python ip/train.py --data_path_train={args.output_dir} --record=1")
    print("=" * 80)


if __name__ == '__main__':
    main()
