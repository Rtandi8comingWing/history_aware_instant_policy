"""
Continuous Pseudo-Demonstration Dataset using multiprocessing (bypasses GIL).
Much faster than threading version for CPU-intensive trimesh operations.
"""
import numpy as np
import queue
import time
import gc
import torch
import multiprocessing as mp
from torch.utils.data import Dataset

from ip.utils.shapenet_loader import ShapeNetLoader
from ip.utils.pseudo_demo_generator import PseudoDemoGenerator
from ip.utils.data_proc import sample_to_live, sample_to_cond_demo


def _worker_process(worker_id, shapenet_root, buffer_queue, stop_event, stats_queue,
                    num_demos_per_task, num_traj_wp, pred_horizon, num_context_demos):
    """Worker process that generates samples (runs in separate process, bypasses GIL)."""
    try:
        # Each process needs its own loader and generator
        shapenet_loader = ShapeNetLoader(shapenet_root, preload_size=0)
        generator = PseudoDemoGenerator()

        samples_generated = 0

        while not stop_event.is_set():
            try:
                # Sample objects
                objects = shapenet_loader.get_random_objects(n=2)

                # Generate multiple raw demonstrations
                raw_demos = []
                for _ in range(num_demos_per_task):
                    demo = generator.generate_pseudo_demonstration(objects)
                    raw_demos.append(demo)

                # Select one demo as "live", others as context
                live_idx = np.random.randint(0, len(raw_demos))

                # Live demo: use raw dense trajectory + subsample=True
                live_demo = sample_to_live(
                    raw_demos[live_idx],
                    pred_horizon=pred_horizon,
                    subsample=True
                )

                # Select context demos
                context_indices = [i for i in range(len(raw_demos)) if i != live_idx]
                if len(context_indices) >= num_context_demos:
                    context_indices = np.random.choice(context_indices, num_context_demos, replace=False)
                else:
                    context_indices = np.random.choice(context_indices, num_context_demos, replace=True)

                context_demos = [sample_to_cond_demo(raw_demos[i], num_traj_wp) for i in context_indices]

                # Create sample dict
                sample = {
                    'live_demo': live_demo,
                    'context_demos': context_demos
                }

                # Put in queue (with timeout to check stop_event)
                buffer_queue.put(sample, timeout=1.0)
                samples_generated += 1

                # Report stats periodically
                if samples_generated % 10 == 0:
                    stats_queue.put(('generated', worker_id, samples_generated))

                # Periodic GC
                if samples_generated % 50 == 0:
                    gc.collect()

            except queue.Full:
                time.sleep(0.1)
            except Exception as e:
                stats_queue.put(('error', worker_id, str(e)))
                time.sleep(0.1)

    except Exception as e:
        print(f"Worker {worker_id} crashed: {e}")
        import traceback
        traceback.print_exc()


class ContinuousPseudoDatasetMP(Dataset):
    """
    Dataset that generates pseudo-demonstrations on-the-fly using multiprocessing.
    Much faster than threading version due to bypassing Python GIL.
    """

    def __init__(self, shapenet_root, num_virtual_samples=700000,
                 num_demos_per_task=5, num_traj_wp=10, pred_horizon=8,
                 buffer_size=1000, num_generator_processes=8,
                 rand_g_prob=0.1, num_context_demos=2):
        """
        Args:
            shapenet_root: Path to ShapeNet dataset
            num_virtual_samples: Virtual dataset size
            num_demos_per_task: Number of demos per pseudo-task
            num_traj_wp: Trajectory waypoints
            pred_horizon: Prediction horizon
            buffer_size: Size of pre-generation buffer
            num_generator_processes: Number of background generation processes
            rand_g_prob: Probability to randomize gripper state
            num_context_demos: Fixed number of context demos
        """
        self.shapenet_root = shapenet_root
        self.num_virtual_samples = num_virtual_samples
        self.num_demos_per_task = num_demos_per_task
        self.num_traj_wp = num_traj_wp
        self.pred_horizon = pred_horizon
        self.rand_g_prob = rand_g_prob
        self.num_context_demos = num_context_demos

        # Initialize ShapeNet loader (main process only, for validation)
        print(f"Initializing ShapeNet loader from {shapenet_root}...")
        self.shapenet_loader = ShapeNetLoader(shapenet_root, preload_size=0)
        print(f"Loaded {self.shapenet_loader.get_num_categories()} categories, "
              f"{self.shapenet_loader.get_num_models()} models")
        print("Note: Using multiprocessing for data generation (bypasses GIL)")

        # Multiprocessing setup
        mp_ctx = mp.get_context('spawn')  # Use spawn to avoid fork issues
        self.buffer = mp_ctx.Queue(maxsize=buffer_size)
        self.stats_queue = mp_ctx.Queue()
        self.stop_event = mp_ctx.Event()
        self.buffer_size = buffer_size

        # Generation statistics
        self.samples_generated = 0
        self.generation_errors = 0
        self.worker_stats = {}

        # Start background generation processes
        self.generator_processes = []
        print(f"Starting {num_generator_processes} background generation processes...")
        for i in range(num_generator_processes):
            process = mp_ctx.Process(
                target=_worker_process,
                args=(i, shapenet_root, self.buffer, self.stop_event, self.stats_queue,
                      num_demos_per_task, num_traj_wp, pred_horizon, num_context_demos),
                daemon=True
            )
            process.start()
            self.generator_processes.append(process)

        # Wait for initial buffer
        min_start = min(buffer_size // 10, 20)
        print(f"Pre-generating {min_start} samples...")
        while self.buffer.qsize() < min_start:
            self._collect_stats()
            time.sleep(0.1)
        print(f"Initial buffer filled: {self.buffer.qsize()} samples ready")

    def _collect_stats(self):
        """Collect statistics from worker processes."""
        try:
            while not self.stats_queue.empty():
                msg_type, worker_id, data = self.stats_queue.get_nowait()
                if msg_type == 'generated':
                    self.worker_stats[worker_id] = data
                    self.samples_generated = sum(self.worker_stats.values())
                elif msg_type == 'error':
                    self.generation_errors += 1
                    if self.generation_errors <= 3:
                        print(f"Worker {worker_id} error: {data}")
        except queue.Empty:
            pass

    def __len__(self):
        return self.num_virtual_samples

    def __getitem__(self, idx):
        """Get one training sample from the buffer."""
        # Collect stats periodically
        if idx % 100 == 0:
            self._collect_stats()

        # Get sample from buffer
        try:
            sample = self.buffer.get(timeout=30)
        except queue.Empty:
            print("Warning: Buffer empty, waiting for generation...")
            sample = self.buffer.get(timeout=60)

        # Convert to torch_geometric Data object
        from torch_geometric.data import Data

        live_demo = sample['live_demo']
        context_demos = sample['context_demos']

        # Randomly select one timestep from live trajectory
        timestep_idx = np.random.randint(0, len(live_demo['obs']))

        # Combine demo point clouds
        joint_demo_pcd = []
        joint_demo_grasp = []
        batch_indices = []

        for demo_idx, demo in enumerate(context_demos):
            for t in range(len(demo['obs'])):
                joint_demo_pcd.append(torch.from_numpy(demo['obs'][t]).float())
                joint_demo_grasp.append(torch.from_numpy(demo['T_w_es'][t]).float())
                batch_indices.append(demo_idx)

        joint_demo_pcd = torch.cat(joint_demo_pcd, dim=0)
        joint_demo_grasp = torch.stack(joint_demo_grasp, dim=0)
        batch_indices = torch.tensor(batch_indices, dtype=torch.long)

        # Live observation
        live_obs = torch.from_numpy(live_demo['obs'][timestep_idx]).float()
        live_grasp = torch.from_numpy(live_demo['T_w_es'][timestep_idx]).float()

        # Actions (from current timestep onwards)
        # Note: live_demo['actions'] is a list of arrays, one per timestep
        actions = torch.from_numpy(live_demo['actions'][timestep_idx]).float()
        grip_actions = torch.tensor(live_demo['actions_grip'][timestep_idx], dtype=torch.float32)

        # Pad if necessary (actions is already [pred_horizon, 4, 4])
        if len(actions) < self.pred_horizon:
            pad_len = self.pred_horizon - len(actions)
            actions = torch.cat([actions, actions[-1:].repeat(pad_len, 1, 1)], dim=0)
            grip_actions = torch.cat([grip_actions, grip_actions[-1:].repeat(pad_len)], dim=0)

        # Randomize gripper state
        if np.random.rand() < self.rand_g_prob:
            grip_actions = torch.rand_like(grip_actions)

        return Data(
            demo_pcd=joint_demo_pcd,
            demo_grasp=joint_demo_grasp,
            demo_batch=batch_indices,
            live_obs=live_obs,
            live_grasp=live_grasp,
            actions=actions[:self.pred_horizon],
            actions_grip=grip_actions[:self.pred_horizon]
        )

    def stop(self):
        """Stop all generation processes."""
        print("Stopping generation processes...")
        self.stop_event.set()
        for process in self.generator_processes:
            process.join(timeout=2)
            if process.is_alive():
                process.terminate()
        self._collect_stats()

    def get_statistics(self):
        """Get generation statistics."""
        self._collect_stats()
        return {
            'samples_generated': self.samples_generated,
            'generation_errors': self.generation_errors,
            'buffer_size': self.buffer.qsize(),
            'worker_stats': self.worker_stats
        }

    def __del__(self):
        self.stop()
