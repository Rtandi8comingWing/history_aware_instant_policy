"""
Continuous Pseudo-Demonstration Dataset with GPU Acceleration
Uses GPU for mesh sampling and point cloud processing - 10-50x faster than CPU version.
"""
import numpy as np
import queue
import time
import gc
import threading
import torch
from torch.utils.data import Dataset

from ip.utils.shapenet_loader import ShapeNetLoader
from ip.utils.pseudo_demo_generator_gpu import PseudoDemoGeneratorGPU
from ip.utils.data_proc import sample_to_live, sample_to_cond_demo


class ContinuousPseudoDatasetGPU(Dataset):
    """
    Dataset that generates pseudo-demonstrations on-the-fly using GPU acceleration.
    Much faster than CPU version due to GPU-accelerated mesh sampling and point cloud processing.
    """

    def __init__(self, shapenet_root, num_virtual_samples=700000,
                 num_demos_per_task=5, num_traj_wp=10, pred_horizon=8,
                 buffer_size=1000, num_generator_threads=4,
                 rand_g_prob=0.1, num_context_demos=2, device='cuda'):
        """
        Args:
            shapenet_root: Path to ShapeNet dataset
            num_virtual_samples: Virtual dataset size
            num_demos_per_task: Number of demos per pseudo-task
            num_traj_wp: Trajectory waypoints
            pred_horizon: Prediction horizon
            buffer_size: Size of pre-generation buffer
            num_generator_threads: Number of background generation threads (fewer needed with GPU)
            rand_g_prob: Probability to randomize gripper state
            num_context_demos: Fixed number of context demos
            device: GPU device ('cuda' or 'cuda:0')
        """
        self.shapenet_root = shapenet_root
        self.num_virtual_samples = num_virtual_samples
        self.num_demos_per_task = num_demos_per_task
        self.num_traj_wp = num_traj_wp
        self.pred_horizon = pred_horizon
        self.rand_g_prob = rand_g_prob
        self.num_context_demos = num_context_demos
        self.device = device

        # Initialize ShapeNet loader (skip preloading for faster startup)
        print(f"Initializing ShapeNet loader from {shapenet_root}...")
        self.shapenet_loader = ShapeNetLoader(shapenet_root, preload_size=0)
        print(f"Loaded {self.shapenet_loader.get_num_categories()} categories, "
              f"{self.shapenet_loader.get_num_models()} models")
        print(f"Note: Using GPU acceleration on {device} for 10-50x speedup")

        # Buffer for pre-generated samples
        self.buffer = queue.Queue(maxsize=buffer_size)
        self.buffer_size = buffer_size

        # Generation statistics
        self.samples_generated = 0
        self.generation_errors = 0
        self._last_error_msg = None
        self._error_print_lock = threading.Lock()

        # Start background generation threads (fewer needed with GPU)
        self.stop_generation = threading.Event()
        self.generator_threads = []

        print(f"Starting {num_generator_threads} background GPU generation threads...")
        for i in range(num_generator_threads):
            thread = threading.Thread(
                target=self._generation_worker,
                args=(i,),
                daemon=True
            )
            thread.start()
            self.generator_threads.append(thread)

        # Wait for initial buffer
        min_start = min(buffer_size // 10, 20)
        print(f"Pre-generating {min_start} samples...")
        while self.buffer.qsize() < min_start:
            time.sleep(0.1)
        print(f"Initial buffer filled: {self.buffer.qsize()} samples ready")

    def _generation_worker(self, worker_id):
        """Background thread that continuously generates samples using GPU."""
        # Each thread gets its own GPU generator
        generator = PseudoDemoGeneratorGPU(device=self.device)

        while not self.stop_generation.is_set():
            try:
                # Generate one pseudo-task
                sample = self._generate_one_sample(generator)

                # Add to buffer (blocks if buffer is full)
                self.buffer.put(sample, timeout=1.0)
                self.samples_generated += 1

                # Periodic GC to prevent memory accumulation
                if self.samples_generated % 50 == 0:
                    gc.collect()
                    torch.cuda.empty_cache()

            except queue.Full:
                # Buffer is full, wait a bit
                time.sleep(0.1)
            except Exception as e:
                import traceback
                self.generation_errors += 1
                err_msg = str(e)
                with self._error_print_lock:
                    # Print actual error on first occurrence or when it changes
                    if self._last_error_msg != err_msg or self.generation_errors <= 3:
                        print(f"\n[GPU Worker {worker_id}] Generation error #{self.generation_errors}: {err_msg}")
                        if self.generation_errors <= 2:
                            traceback.print_exc()
                        self._last_error_msg = err_msg
                    elif self.generation_errors % 100 == 0:
                        print(f"GPU Worker {worker_id} error count: {self.generation_errors} (last: {err_msg[:80]}...)")
                time.sleep(0.1)

    def _generate_one_sample(self, generator):
        """Generate one training sample using GPU."""
        # Sample objects for this pseudo-task
        objects = self.shapenet_loader.get_random_objects(n=2)

        # Generate multiple raw demonstrations (dense trajectory, 1cm spacing)
        raw_demos = []
        for _ in range(self.num_demos_per_task):
            demo = generator.generate_pseudo_demonstration(objects)
            raw_demos.append(demo)

        # Select one demo as "live", others as context
        live_idx = np.random.randint(0, len(raw_demos))

        # Live demo: use raw dense trajectory + subsample=True (1cm spacing)
        # This ensures actions stay within normalizer range (±0.01m/step)
        live_demo = sample_to_live(
            raw_demos[live_idx],
            pred_horizon=self.pred_horizon,
            subsample=True
        )

        # Select context demos (fixed number for batching)
        context_indices = [i for i in range(len(raw_demos)) if i != live_idx]
        if len(context_indices) >= self.num_context_demos:
            context_indices = np.random.choice(context_indices, self.num_context_demos, replace=False)
        else:
            # If not enough demos, sample with replacement
            context_indices = np.random.choice(context_indices, self.num_context_demos, replace=True)

        # Context demos: compress to num_traj_wp waypoints for fixed-size batching
        context_demos = [sample_to_cond_demo(raw_demos[i], self.num_traj_wp) for i in context_indices]

        # Randomly select one timestep from live trajectory
        timestep_idx = np.random.randint(0, len(live_demo['obs']))

        # Create torch_geometric Data object
        from torch_geometric.data import Data

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
        # Each array is [pred_horizon, 4, 4]
        actions = torch.from_numpy(live_demo['actions'][timestep_idx]).float()
        grip_actions = torch.tensor(live_demo['actions_grip'][timestep_idx], dtype=torch.float32)

        # Pad if necessary
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

    def __len__(self):
        return self.num_virtual_samples

    def __getitem__(self, idx):
        """Get one training sample from the buffer."""
        # Get sample from buffer
        try:
            sample = self.buffer.get(timeout=30)
        except queue.Empty:
            print("Warning: Buffer empty, waiting for GPU generation...")
            sample = self.buffer.get(timeout=60)

        return sample

    def stop(self):
        """Stop all generation threads."""
        print("Stopping GPU generation threads...")
        self.stop_generation.set()
        for thread in self.generator_threads:
            thread.join(timeout=2)

    def get_statistics(self):
        """Get generation statistics."""
        return {
            'samples_generated': self.samples_generated,
            'generation_errors': self.generation_errors,
            'buffer_size': self.buffer.qsize()
        }

    def __del__(self):
        self.stop()
