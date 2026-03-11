"""
Continuous Pseudo-Demonstration Dataset
Generates data on-the-fly during training (paper mentions continuous generation)

V1 Extension: 添加历史轨迹 (Track) 支持，用于 HA-IGD 融合训练
"""
import torch
import numpy as np
from torch.utils.data import Dataset
import queue
import threading
import time
import gc
import random
from ip.utils.shapenet_loader import ShapeNetLoader
from ip.utils.pseudo_demo_generator import PseudoDemoGenerator
from ip.utils.data_proc import sample_to_cond_demo, sample_to_live
from ip.utils.track_builder import build_object_tracks_world, project_tracks_to_current_ee, compute_track_age_seconds
from ip.utils.memory_task_generator import MemoryTaskGenerator


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
                 num_context_demos=2,
                 # HA-IGD track parameters
                 enable_track_nodes=False,
                 memory_task_ratio=0.3,
                 track_history_len=16,
                 track_points_per_obj=5,
                 track_n_max=5,
                 track_age_norm_max_sec=2.0,
                 control_hz=15.0,
                 track_refresh_hz=3.0,
                 curriculum_stage_steps=(50000, 200000)):
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
            enable_track_nodes: 是否启用历史轨迹节点 (HA-IGD)
            memory_task_ratio: 记忆任务采样比例
            track_history_len: 轨迹历史帧数
            track_points_per_obj: 每个对象的关键点数
            track_n_max: 最大对象数
            track_age_norm_max_sec: track age 归一化最大秒数
            control_hz: 控制频率
            track_refresh_hz: track 更新频率
            curriculum_stage_steps: 课程学习阶段步数 (warmup, mid)
        """
        self.shapenet_root = shapenet_root
        self.num_virtual_samples = num_virtual_samples
        self.num_demos_per_task = num_demos_per_task
        self.num_traj_wp = num_traj_wp
        self.pred_horizon = pred_horizon
        self.rand_g_prob = rand_g_prob
        self.num_context_demos = num_context_demos

        # HA-IGD track parameters
        self.enable_track_nodes = enable_track_nodes
        self.memory_task_ratio = memory_task_ratio
        self.track_history_len = track_history_len
        self.track_points_per_obj = track_points_per_obj
        self.track_n_max = track_n_max
        self.track_age_norm_max_sec = track_age_norm_max_sec
        self.control_hz = control_hz
        self.track_refresh_hz = track_refresh_hz
        self.curriculum_stage_steps = curriculum_stage_steps

        # Global step counter for curriculum scheduling
        self._global_step = 0
        
        # Initialize ShapeNet loader (fast startup mode)
        print(f"Initializing ShapeNet loader from {shapenet_root}...")
        self.shapenet_loader = ShapeNetLoader(shapenet_root, preload_size=0)
        print(f"Loaded {self.shapenet_loader.get_num_categories()} categories, "
              f"{self.shapenet_loader.get_num_models()} models")
        print(f"Note: Using on-demand mesh loading for fast startup.")

        # Initialize memory task generator (HA-IGD)
        if self.enable_track_nodes:
            print(f"Initializing MemoryTaskGenerator (ratio={memory_task_ratio})...")
            self.memory_task_generator = MemoryTaskGenerator(
                control_hz=self.control_hz,
                track_refresh_hz=self.track_refresh_hz
            )
        else:
            self.memory_task_generator = None
        
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

    def _current_memory_ratio(self) -> float:
        """
        根据训练步数返回当前 memory task 采样比例
        课程学习策略：
        - warmup 阶段 (0 ~ 50k): 10%
        - mid 阶段 (50k ~ 200k): 30%
        - late 阶段 (200k+): 50%
        """
        step = self._global_step
        warmup_end, mid_end = self.curriculum_stage_steps

        if step < warmup_end:
            return 0.1
        elif step < mid_end:
            # 线性插值 10% -> 30%
            ratio = 0.1 + (0.3 - 0.1) * (step - warmup_end) / (mid_end - warmup_end)
            return ratio
        else:
            # 线性插值 30% -> 50%
            ratio = 0.3 + (0.5 - 0.3) * min((step - mid_end) / 100000, 1.0)
            return min(ratio, 0.5)
    
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
        # Update global step for curriculum scheduling
        self._global_step += 1

        # Decide whether to generate memory task or base pseudo task
        use_memory_task = (
            self.enable_track_nodes and
            self.memory_task_generator is not None and
            np.random.uniform() < self._current_memory_ratio()
        )

        if use_memory_task:
            # Generate memory task (HA-IGD)
            data = self._generate_memory_sample()
        else:
            # Generate base pseudo task (original IP)
            data = self._generate_base_sample(generator)

        # Random gripper flip (10% probability, paper mentions this)
        if np.random.uniform() < self.rand_g_prob:
            data.current_grip *= -1

        return data

    def _generate_base_sample(self, generator):
        """Generate base pseudo sample (original IP pipeline)"""
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
        live_demo = sample_to_live(
            raw_demos[live_idx],
            pred_horizon=self.pred_horizon,
            subsample=True
        )

        # Select context demos
        context_indices = [i for i in range(len(raw_demos)) if i != live_idx]
        if len(context_indices) >= self.num_context_demos:
            context_indices = np.random.choice(context_indices, self.num_context_demos, replace=False)
        else:
            context_indices = np.random.choice(context_indices, self.num_context_demos, replace=True)
        context_demos = [sample_to_cond_demo(raw_demos[i], self.num_traj_wp) for i in context_indices]

        # Randomly select one timestep from live trajectory
        timestep_idx = np.random.randint(0, len(live_demo['obs']))

        # Build Data object (without tracks for base mode)
        data = self._build_data_object(
            context_demos=context_demos,
            live_demo=live_demo,
            timestep_idx=timestep_idx,
            generate_tracks=False
        )

        return data

    def _generate_memory_sample(self):
        """Generate memory task sample (HA-IGD)"""
        # Sample objects
        objects = self.shapenet_loader.get_random_objects(n=2)

        # Use memory task generator
        memory_task = self.memory_task_generator.generate_task(
            objects=objects,
            task_type=None,  # random
            difficulty=1
        )

        # Extract components
        T_w_es = memory_task['T_w_es']  # [T, 4,4]
        timestamps = memory_task.get('timestamps', np.arange(len(T_w_es)) * (1.0 / self.control_hz))
        objects_state_seq = memory_task.get('objects_state_seq', [{}] * len(T_w_es))

        # Sample timestep
        timestep_idx = np.random.randint(0, len(T_w_es))

        # Build pseudo demo structure (single demo case)
        demo_data = {
            'obs': memory_task['pcds'],
            'grips': memory_task['grips'],
            'T_w_es': T_w_es,
            'objects_state_seq': objects_state_seq
        }

        # Split into context and live
        # Need to sample/fit to fixed length num_traj_wp
        mid = len(T_w_es) // 2

        # Sample context demo to fixed length
        context_traj = demo_data['obs'][:mid]
        context_grips = demo_data['grips'][:mid]
        context_T_w_es = demo_data['T_w_es'][:mid]
        context_obj_seq = demo_data['objects_state_seq'][:mid]

        # Resample to num_traj_wp
        if len(context_traj) >= self.num_traj_wp:
            # Uniformly sample num_traj_wp indices
            indices = np.linspace(0, len(context_traj) - 1, self.num_traj_wp, dtype=int)
            context_obs = [context_traj[i] for i in indices]
            context_grips_sampled = context_grips[indices]
            context_T_w_es_sampled = context_T_w_es[indices]
            context_obj_seq_sampled = [context_obj_seq[i] for i in indices]
        else:
            # Pad with first frame
            context_obs = list(context_traj)
            context_grips_sampled = list(context_grips)
            context_T_w_es_sampled = list(context_T_w_es)
            context_obj_seq_sampled = list(context_obj_seq)
            while len(context_obs) < self.num_traj_wp:
                context_obs.append(context_obs[0])
                context_grips_sampled = np.concatenate([context_grips_sampled, [context_grips_sampled[0]]])
                context_T_w_es_sampled = np.concatenate([context_T_w_es_sampled, context_T_w_es_sampled[0:1]], axis=0)
                context_obj_seq_sampled.append(context_obj_seq_sampled[0])

        context_demo = {
            'obs': context_obs,
            'grips': context_grips_sampled,
            'T_w_es': context_T_w_es_sampled,
            'objects_state_seq': context_obj_seq_sampled
        }

        # Live demo - ensure we have enough frames
        live_traj = demo_data['obs'][mid:]
        live_grips = demo_data['grips'][mid:]
        live_T_w_es = demo_data['T_w_es'][mid:]
        live_obj_seq = demo_data['objects_state_seq'][mid:]

        # Resample to fixed length
        if len(live_traj) >= self.pred_horizon:
            indices = np.linspace(0, len(live_traj) - 1, max(self.pred_horizon, 2), dtype=int)
            live_obs = [live_traj[i] for i in indices]
            live_grips_sampled = live_grips[indices]
            live_T_w_es_sampled = live_T_w_es[indices]
            live_obj_seq_sampled = [live_obj_seq[i] for i in indices]
        else:
            # Pad
            live_obs = list(live_traj)
            live_grips_sampled = list(live_grips)
            live_T_w_es_sampled = list(live_T_w_es)
            live_obj_seq_sampled = list(live_obj_seq)
            while len(live_obs) < self.pred_horizon:
                live_obs.append(live_obs[0])
                live_grips_sampled = np.concatenate([live_grips_sampled, [live_grips_sampled[0]]])
                live_T_w_es_sampled = np.concatenate([live_T_w_es_sampled, live_T_w_es_sampled[0:1]], axis=0)
                live_obj_seq_sampled.append(live_obj_seq_sampled[0])

        # Build live demo action sequences (matching sample_to_live format: [T, pred_horizon, 4, 4])
        # For each timestep, compute relative actions to future timesteps
        live_actions = []
        live_actions_grip = []
        T = len(live_T_w_es_sampled)
        for i in range(T):
            actions_i = []
            actions_grip_i = []
            for j in range(1, self.pred_horizon + 1):
                if i + j < T:
                    # Relative transformation from timestep i to i+j
                    actions_i.append(np.linalg.inv(live_T_w_es_sampled[i]) @ live_T_w_es_sampled[i + j])
                    actions_grip_i.append(live_grips_sampled[i + j])
                else:
                    # Pad with identity if not enough future frames
                    actions_i.append(np.eye(4))
                    actions_grip_i.append(live_grips_sampled[-1])
            live_actions.append(np.array(actions_i))
            live_actions_grip.append(actions_grip_i)

        live_demo = {
            'obs': live_obs,
            'grips': live_grips_sampled,
            'T_w_es': live_T_w_es_sampled,
            'objects_state_seq': live_obj_seq_sampled,
            'actions': live_actions,  # List of [pred_horizon, 4, 4] arrays
            'actions_grip': live_actions_grip  # List of [pred_horizon] lists
        }

        # Adjust timestep_idx to be within live range
        actual_timestep_idx = min(timestep_idx - mid, len(live_demo['obs']) - 1)
        actual_timestep_idx = max(0, actual_timestep_idx)

        # Replicate context demo to match num_context_demos (for consistent batch shape)
        # Use deep copy to avoid reference issues
        import copy
        context_demos_list = [copy.deepcopy(context_demo) for _ in range(self.num_context_demos)]
        context_obj_seq_list = [copy.deepcopy(context_demo['objects_state_seq']) for _ in range(self.num_context_demos)]

        # Build Data object with tracks
        data = self._build_data_object(
            context_demos=context_demos_list,
            live_demo=live_demo,
            timestep_idx=actual_timestep_idx,
            generate_tracks=True,
            live_objects_state_seq=live_demo['objects_state_seq'],
            context_objects_state_seq=context_obj_seq_list
        )

        # Add memory task metadata (for evaluation only)
        data.task_type = memory_task['meta'].task_type
        data.decision_points = memory_task['meta'].decision_points
        data.decision_labels = memory_task['meta'].decision_labels
        data.memory_aspects = memory_task['meta'].memory_aspects

        return data

    def _build_data_object(self, context_demos, live_demo, timestep_idx, generate_tracks=False,
                           live_objects_state_seq=None, context_objects_state_seq=None):
        """Build torch_geometric Data object, optionally with track information"""
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

        # Actions - now matches sample_to_live format: [pred_horizon, 4, 4]
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

        # Generate track information if enabled
        if generate_tracks:
            data = self._add_track_information(data, live_demo, context_demos,
                                               timestep_idx, live_objects_state_seq,
                                               context_objects_state_seq)
        else:
            # Add empty track fields to maintain consistent data structure
            data = self._add_empty_track_fields(data, num_demos)

        return data

    def _add_track_information(self, data, live_demo, context_demos, timestep_idx,
                               live_objects_state_seq=None, context_objects_state_seq=None):
        """Add track information to Data object"""
        # Get current timestep's EE pose
        T_w_e_current = live_demo['T_w_es'][timestep_idx]

        # Build live track (current observation's history)
        if live_objects_state_seq is not None:
            # Use provided object states
            live_obj_seq = live_objects_state_seq
        else:
            # Create dummy object states from EE trajectory
            live_obj_seq = self._create_dummy_object_states(live_demo['T_w_es'])

        # Build world tracks
        track_result = build_object_tracks_world(
            live_obj_seq,
            points_per_obj=self.track_points_per_obj,
            n_max=self.track_n_max,
            history_len=self.track_history_len
        )

        # Project to current EE frame
        current_track_ee = project_tracks_to_current_ee(
            track_result['tracks_world'],
            track_result['track_valid'],
            T_w_e_current
        )

        # Ensure shape matches expected dimensions
        expected_shape = (self.track_n_max, self.track_history_len, self.track_points_per_obj, 3)
        if current_track_ee.shape != expected_shape:
            # Resize if needed (truncate or pad)
            resized = np.zeros(expected_shape, dtype=np.float32)
            min_n = min(current_track_ee.shape[0], expected_shape[0])
            min_h = min(current_track_ee.shape[1], expected_shape[1])
            min_p = min(current_track_ee.shape[2], expected_shape[2])
            resized[:min_n, :min_h, :min_p, :] = current_track_ee[:min_n, :min_h, :min_p, :]
            current_track_ee = resized

        # Compute track age
        now_ts = live_obj_seq[-1].get('timestamp', 0.0) if live_obj_seq else 0.0
        current_track_age = compute_track_age_seconds(
            track_result['track_timestamps'],
            track_result['track_valid'],
            now_ts,
            norm_max_sec=self.track_age_norm_max_sec
        )

        # Build demo tracks with fixed T dimension (padding)
        D = len(context_demos)
        max_demo_T = 15  # Fixed T dimension to avoid collate issues

        demo_track_seq = np.zeros((D, max_demo_T, self.track_n_max,
                                   self.track_history_len, self.track_points_per_obj, 3), dtype=np.float32)
        demo_track_valid = np.zeros((D, max_demo_T, self.track_n_max), dtype=np.bool_)
        demo_track_age = np.zeros((D, max_demo_T, self.track_n_max, 1), dtype=np.float32)

        for d in range(D):
            demo = context_demos[d]
            demo_obj_seq = demo.get('objects_state_seq', self._create_dummy_object_states(demo['T_w_es']))

            actual_T = min(len(demo['T_w_es']), max_demo_T)
            for t in range(actual_T):
                # Get object states up to this timestep
                sub_seq = demo_obj_seq[:t+1]
                if len(sub_seq) < self.track_history_len:
                    # Pad
                    first_state = demo_obj_seq[0].copy() if demo_obj_seq else {'timestamp': 0.0}
                    sub_seq = [first_state] * (self.track_history_len - len(sub_seq)) + sub_seq

                # Build and project tracks
                demo_track_result = build_object_tracks_world(
                    sub_seq,
                    points_per_obj=self.track_points_per_obj,
                    n_max=self.track_n_max,
                    history_len=self.track_history_len
                )

                T_w_e_t = demo['T_w_es'][t]
                demo_track_ee = project_tracks_to_current_ee(
                    demo_track_result['tracks_world'],
                    demo_track_result['track_valid'],
                    T_w_e_t
                )

                # Ensure shape matches expected dimensions
                # demo_track_ee shape: [Nmax, H, P, 3]
                # Expected: [track_n_max, track_history_len, track_points_per_obj, 3]
                expected_shape = (self.track_n_max, self.track_history_len, self.track_points_per_obj, 3)
                if demo_track_ee.shape != expected_shape:
                    # Resize if needed (truncate or pad)
                    resized = np.zeros(expected_shape, dtype=np.float32)
                    min_n = min(demo_track_ee.shape[0], expected_shape[0])
                    min_h = min(demo_track_ee.shape[1], expected_shape[1])
                    min_p = min(demo_track_ee.shape[2], expected_shape[2])
                    resized[:min_n, :min_h, :min_p, :] = demo_track_ee[:min_n, :min_h, :min_p, :]
                    demo_track_ee = resized

                demo_track_seq[d, t] = demo_track_ee
                demo_track_valid[d, t] = demo_track_result['track_valid']

                # Compute age
                ts = sub_seq[-1].get('timestamp', 0.0) if sub_seq else 0.0
                age = compute_track_age_seconds(
                    demo_track_result['track_timestamps'],
                    demo_track_result['track_valid'],
                    ts,
                    norm_max_sec=self.track_age_norm_max_sec
                )
                demo_track_age[d, t, :, 0] = age[:, 0]

        # Add to data object
        data.current_track_seq = torch.from_numpy(current_track_ee).float().unsqueeze(0)  # [1, Nmax, H, P, 3]
        data.current_track_valid = torch.from_numpy(track_result['track_valid']).bool().unsqueeze(0)  # [1, Nmax]
        data.current_track_age_sec = torch.from_numpy(current_track_age).float().unsqueeze(0)  # [1, Nmax, 1]

        data.demo_track_seq = torch.from_numpy(demo_track_seq).float().unsqueeze(0)  # [1, D, max_demo_T, Nmax, H, P, 3]
        data.demo_track_valid = torch.from_numpy(demo_track_valid).bool().unsqueeze(0)  # [1, D, max_demo_T, Nmax]
        data.demo_track_age_sec = torch.from_numpy(demo_track_age).float().unsqueeze(0)  # [1, D, max_demo_T, Nmax, 1]

        # Add config info
        data.track_n_max = self.track_n_max
        data.track_history_len = self.track_history_len
        data.track_points_per_obj = self.track_points_per_obj

        return data

    def _add_empty_track_fields(self, data, num_demos):
        """Add empty track fields to maintain consistent data structure across batch"""
        max_demo_T = 15  # Fixed T dimension matching _add_track_information

        # Current track (empty) - add batch dimension
        data.current_track_seq = torch.zeros(
            (1, self.track_n_max, self.track_history_len, self.track_points_per_obj, 3),
            dtype=torch.float32
        )
        data.current_track_valid = torch.zeros((1, self.track_n_max), dtype=torch.bool)
        data.current_track_age_sec = torch.zeros((1, self.track_n_max, 1), dtype=torch.float32)

        # Demo tracks (empty) - add batch dimension with fixed T
        data.demo_track_seq = torch.zeros(
            (1, num_demos, max_demo_T, self.track_n_max,
             self.track_history_len, self.track_points_per_obj, 3),
            dtype=torch.float32
        )
        data.demo_track_valid = torch.zeros(
            (1, num_demos, max_demo_T, self.track_n_max),
            dtype=torch.bool
        )
        data.demo_track_age_sec = torch.zeros(
            (1, num_demos, max_demo_T, self.track_n_max, 1),
            dtype=torch.float32
        )

        # Add config info
        data.track_n_max = self.track_n_max
        data.track_history_len = self.track_history_len
        data.track_points_per_obj = self.track_points_per_obj

        # Add default memory task attributes (for consistent batch structure)
        data.task_type = "none"
        data.decision_points = []
        data.decision_labels = []
        data.memory_aspects = {}

        return data

    def _create_dummy_object_states(self, T_w_es):
        """Create dummy object states from EE trajectory (for base pseudo data)"""
        dt = 1.0 / self.control_hz
        obj_states = []
        for i, T in enumerate(T_w_es):
            # Use EE position as a "dummy object" at offset
            obj_pos = T[:3, 3] + np.array([0.05, 0.0, 0.0])
            obj_pose = np.eye(4)
            obj_pose[:3, 3] = obj_pos

            obj_states.append({
                'object_poses': [obj_pose],
                'object_ids': [0],
                'timestamp': i * dt
            })
        return obj_states
    
    def __len__(self):
        """Return virtual dataset size."""
        return self.num_virtual_samples
    
    def __getitem__(self, idx):
        """Get a sample from the buffer."""
        while True:
            try:
                return self.buffer.get(timeout=5.0)
            except queue.Empty:
                if self.stop_generation.is_set():
                    raise RuntimeError("Generation stopped and buffer is empty")
                print("Warning: Buffer empty, waiting for generation...")
    
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
