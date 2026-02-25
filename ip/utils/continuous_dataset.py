"""
Continuous Pseudo-Demonstration Dataset
Generates data on-the-fly during training (paper mentions continuous generation)
"""
import torch
import numpy as np
from torch.utils.data import Dataset
import queue
import threading
import time
import gc
from ip.utils.shapenet_loader import ShapeNetLoader
from ip.utils.pseudo_demo_generator import PseudoDemoGenerator
from ip.utils.data_proc import sample_to_cond_demo, sample_to_live


class ContinuousPseudoDataset(Dataset):
    """
    Dataset that continuously generates pseudo-demonstrations during training.
    
    Paper (Section 4): "pseudo-demonstrations that are continuously generated 
    in parallel, which is roughly equivalent to using 700K unique trajectories"
    """
    
    def __init__(self,
                 shapenet_root='/media/tianyi/Tiantian/tianyiStudy/DataSets/ShapeNetCore.v2',
                 num_virtual_samples=700000,
                 num_demos_per_task=3,
                 num_traj_wp=10,
                 pred_horizon=8,
                 buffer_size=1000,
                 num_generator_threads=4,
                 rand_g_prob=0.0,
                 num_context_demos=2):
        """
        Args:
            shapenet_root: Path to ShapeNet dataset
            num_virtual_samples: Virtual dataset size (paper uses ~700K)
            num_demos_per_task: Number of demos for each pseudo-task
            num_traj_wp: Trajectory waypoints
            pred_horizon: Prediction horizon
            buffer_size: Size of pre-generation buffer
            num_generator_threads: Number of background generation threads
            rand_g_prob: Probability to randomize gripper state (0.1 in paper)
            num_context_demos: Fixed number of context demos (for batching)
        """
        self.shapenet_root = shapenet_root
        self.num_virtual_samples = num_virtual_samples
        self.num_demos_per_task = num_demos_per_task
        self.num_traj_wp = num_traj_wp
        self.pred_horizon = pred_horizon
        self.rand_g_prob = rand_g_prob
        self.num_context_demos = num_context_demos
        
        # Initialize ShapeNet loader
        print(f"Initializing ShapeNet loader from {shapenet_root}...")
        self.shapenet_loader = ShapeNetLoader(shapenet_root)
        print(f"Loaded {self.shapenet_loader.get_num_categories()} categories, "
              f"{self.shapenet_loader.get_num_models()} models")
        
        # Buffer for pre-generated samples
        self.buffer = queue.Queue(maxsize=buffer_size)
        self.buffer_size = buffer_size
        
        # Generation statistics
        self.samples_generated = 0
        self.generation_errors = 0
        self._last_error_msg = None
        self._error_print_lock = threading.Lock()
        
        # Start background generation threads
        self.stop_generation = threading.Event()
        self.generator_threads = []
        
        print(f"Starting {num_generator_threads} background generation threads...")
        for i in range(num_generator_threads):
            thread = threading.Thread(
                target=self._generation_worker,
                args=(i,),
                daemon=True
            )
            thread.start()
            self.generator_threads.append(thread)
        
        # Wait for a small initial buffer before starting training
        min_start = min(buffer_size // 10, 20)
        print(f"Pre-generating {min_start} samples...")
        while self.buffer.qsize() < min_start:
            time.sleep(0.1)
        print(f"Initial buffer filled: {self.buffer.qsize()} samples ready")
    
    def _generation_worker(self, worker_id):
        """Background thread that continuously generates samples."""
        generator = PseudoDemoGenerator()
        
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
                        print(f"\n[Worker {worker_id}] Generation error #{self.generation_errors}: {err_msg}")
                        if self.generation_errors <= 2:
                            traceback.print_exc()
                        self._last_error_msg = err_msg
                    elif self.generation_errors % 100 == 0:
                        print(f"Worker {worker_id} generation error count: {self.generation_errors} (last: {err_msg[:80]}...)")
                time.sleep(0.1)
    
    def _generate_one_sample(self, generator):
        """Generate one training sample."""
        # Sample objects for this pseudo-task
        objects = self.shapenet_loader.get_random_objects(n=2)
        
        # Generate multiple demonstrations
        demos = []
        for _ in range(self.num_demos_per_task):
            demo = generator.generate_pseudo_demonstration(objects)
            cond_demo = sample_to_cond_demo(demo, self.num_traj_wp)
            demos.append(cond_demo)
        
        # Select one demo as "live", others as context
        live_idx = np.random.randint(0, len(demos))
        
        # Convert live demo
        live_demo_dict = {
            'pcds': demos[live_idx]['obs'],
            'T_w_es': demos[live_idx]['T_w_es'],
            'grips': demos[live_idx]['grips']
        }
        live_demo = sample_to_live(
            live_demo_dict,
            pred_horizon=self.pred_horizon,
            subsample=False
        )
        
        # Select context demos (fixed number for batching)
        context_indices = [i for i in range(len(demos)) if i != live_idx]
        if len(context_indices) >= self.num_context_demos:
            context_indices = np.random.choice(context_indices, self.num_context_demos, replace=False)
        else:
            # If not enough demos, sample with replacement
            context_indices = np.random.choice(context_indices, self.num_context_demos, replace=True)
        context_demos = [demos[i] for i in context_indices]
        
        # Randomly select one timestep from live trajectory
        timestep_idx = np.random.randint(0, len(live_demo['obs']))
        
        # Create torch_geometric Data object
        from torch_geometric.data import Data
        
        # Combine demo point clouds
        joint_demo_pcd = []
        joint_demo_grasp = []
        batch_indices = []
        
        num_demos = len(context_demos)
        for n, demo in enumerate(context_demos):
            for i, obs in enumerate(demo['obs']):
                joint_demo_pcd.append(obs)
                joint_demo_grasp.append(demo['grips'][i])
                batch_indices.append(np.zeros(len(obs)) + i + n * self.num_traj_wp)
        
        joint_demo_pcd = np.concatenate(joint_demo_pcd)
        joint_demo_grasp = (np.array(joint_demo_grasp) - 0.5) * 2  # Convert to [-1, 1]
        batch_indices = np.concatenate(batch_indices)
        
        # Current observation
        current_obs = live_demo['obs'][timestep_idx]
        current_grip = live_demo['grips'][timestep_idx]
        current_T_w_e = live_demo['T_w_es'][timestep_idx]
        
        # Actions
        actions = live_demo['actions'][timestep_idx]
        actions_grip = live_demo['actions_grip'][timestep_idx]
        
        # Create data object
        data = Data(
            pos_demos=torch.tensor(joint_demo_pcd, dtype=torch.float32),
            graps_demos=torch.tensor(joint_demo_grasp, dtype=torch.float32).view(
                num_demos, self.num_traj_wp, 1).unsqueeze(0),
            batch_demos=torch.tensor(batch_indices, dtype=torch.int64),
            pos_obs=torch.tensor(current_obs, dtype=torch.float32),
            batch_pos_obs=torch.tensor(np.zeros(len(current_obs)), dtype=torch.int64),
            current_grip=torch.tensor((current_grip - 0.5) * 2, dtype=torch.float32).unsqueeze(0),
            demo_T_w_es=torch.tensor(
                np.stack([demo['T_w_es'] for demo in context_demos]),
                dtype=torch.float32
            ).unsqueeze(0),
            T_w_e=torch.tensor(current_T_w_e, dtype=torch.float32).unsqueeze(0),
            actions=torch.tensor(actions, dtype=torch.float32).unsqueeze(0),
            actions_grip=torch.tensor((np.array(actions_grip) - 0.5) * 2, 
                                     dtype=torch.float32).unsqueeze(0),
        )
        
        # Random gripper flip (10% probability, paper mentions this)
        if np.random.uniform() < self.rand_g_prob:
            data.current_grip *= -1
        
        return data
    
    def __len__(self):
        """Return virtual dataset size."""
        return self.num_virtual_samples
    
    def __getitem__(self, idx):
        """Get a sample from the buffer."""
        try:
            # Get from buffer (blocks if empty)
            sample = self.buffer.get(timeout=10.0)
            return sample
        except queue.Empty:
            print("Warning: Buffer empty, waiting for generation...")
            time.sleep(1.0)
            return self.buffer.get(timeout=10.0)
    
    def get_statistics(self):
        """Get generation statistics."""
        return {
            'samples_generated': self.samples_generated,
            'generation_errors': self.generation_errors,
            'buffer_size': self.buffer.qsize(),
            'buffer_max': self.buffer_size
        }
    
    def stop(self):
        """Stop background generation threads."""
        print("Stopping generation threads...")
        self.stop_generation.set()
        for thread in self.generator_threads:
            thread.join(timeout=2.0)
        print("Generation threads stopped")
    
    def __del__(self):
        """Cleanup."""
        self.stop()


if __name__ == '__main__':
    # Test the dataset
    print("Testing ContinuousPseudoDataset...")
    
    dataset = ContinuousPseudoDataset(
        num_virtual_samples=1000,
        buffer_size=10,
        num_generator_threads=2
    )
    
    print("\nFetching samples...")
    for i in range(5):
        sample = dataset[i]
        print(f"Sample {i}:")
        print(f"  Demo point cloud: {sample.pos_demos.shape}")
        print(f"  Current obs: {sample.pos_obs.shape}")
        print(f"  Actions: {sample.actions.shape}")
        print(f"  Gripper states: {sample.actions_grip.shape}")
    
    stats = dataset.get_statistics()
    print(f"\nStatistics: {stats}")
    
    dataset.stop()
    print("Test complete!")
