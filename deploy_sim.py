from ip.models.diffusion import GraphDiffusion
from ip.configs.base_config import config as base_config
from sim_utils import rollout_model

import torch
import argparse
import pickle
import os



if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--model_path', type=str, default='./checkpoints',
                        help='Path to model checkpoint directory')
    parser.add_argument('--task_name', type=str, default='plate_out')
    parser.add_argument('--num_demos', type=int, default=2)
    parser.add_argument('--num_rollouts', type=int, default=10)
    parser.add_argument('--restrict_rot', type=int, default=1)
    parser.add_argument('--headless', type=int, default=1,
                        help='Run CoppeliaSim headless [0, 1]')
    
    args = parser.parse_args()
    restrict_rot = bool(args.restrict_rot)
    headless = bool(args.headless)
    task_name = args.task_name
    num_demos = args.num_demos
    num_rollouts = args.num_rollouts
    model_path = args.model_path
    ####################################################################################################################
    device = 'cuda' if torch.cuda.is_available() else 'cpu'

    # Load or create config
    config_path = f'{model_path}/config.pkl'
    if os.path.exists(config_path):
        config = pickle.load(open(config_path, 'rb'))
    else:
        print(f"Warning: config.pkl not found in {model_path}, using base config")
        config = base_config.copy()
    
    # Update config for inference
    config['device'] = device
    config['compile_models'] = False
    config['batch_size'] = 1
    config['num_demos'] = num_demos
    config['num_diffusion_iters_test'] = 4
    
    # Check if scene encoder exists, disable if not
    scene_encoder_path = f'{model_path}/scene_encoder.pt'
    if not os.path.exists(scene_encoder_path):
        print(f"Warning: scene_encoder.pt not found, disabling pre-trained encoder")
        print("For better performance, download weights using: cd ip && ./scripts/download_weights.sh")
        config['pre_trained_encoder'] = False

    model = GraphDiffusion.load_from_checkpoint(f'{model_path}/model.pt', 
                                                config=config,
                                                strict=False,
                                                map_location=device).to(device)

    model.model.reinit_graphs(1, num_demos=num_demos)
    model.eval()
    ####################################################################################################################
    sr = rollout_model(model, num_demos, task_name, num_rollouts=num_rollouts, execution_horizon=8,
                       num_traj_wp=config['traj_horizon'], restrict_rot=restrict_rot, headless=headless)
    print('Success rate:', sr)
