"""
Quick comparison script: original paper weights vs your trained weights.
Uses data/pseudo_test/ (5000 samples) - no RLBench needed.

Usage:
    python compare_models.py --num_samples=200
    python compare_models.py --num_samples=200 --user_ckpt=runs/my_experiment_5/50000.pt
"""
import sys, argparse, pickle, numpy as np, torch
sys.path.insert(0, '/home/tianyi/RAGD/instant_policy_origin_specific')

from ip.models.diffusion import GraphDiffusion
from ip.configs.base_config import config as base_config
from torch_geometric.data import DataLoader
from ip.utils.running_dataset import RunningDataset

def load_model(ckpt_path, config):
    config = config.copy()
    config['compile_models'] = False
    config['batch_size'] = 1
    config['num_diffusion_iters_test'] = 4
    model = GraphDiffusion.load_from_checkpoint(
        ckpt_path, config=config, strict=False,
        map_location=config['device']
    ).to(config['device'])
    model.model.reinit_graphs(1, num_demos=config['num_demos'])
    model.eval()
    return model

@torch.no_grad()
def evaluate(model, dataloader, num_samples, label):
    trans_errs, rot_errs, grip_errs = [], [], []
    device = next(model.parameters()).device

    for i, data in enumerate(dataloader):
        if i >= num_samples:
            break
        data = data.to(device)
        gt_actions = data.actions.clone()
        gt_grips = data.actions_grip.clone()

        with torch.autocast(dtype=torch.float32, device_type=device.type if hasattr(device, 'type') else 'cuda'):
            pred_actions, pred_grips = model.test_step(data, i)

        # Translation error (meters)
        trans = torch.norm(pred_actions[..., :3, 3] - gt_actions[..., :3, 3], dim=-1).mean().item()
        # Rotation error (degrees)
        R_err = pred_actions[..., :3, :3].transpose(-1, -2) @ gt_actions[..., :3, :3]
        trace = R_err.diagonal(dim1=-2, dim2=-1).sum(-1)
        angle = torch.acos(((trace - 1) / 2).clamp(-1, 1)) * 180 / np.pi
        rot = angle.mean().item()
        # Gripper error
        grip = (pred_grips.squeeze() - gt_grips.squeeze()).abs().mean().item()

        trans_errs.append(trans)
        rot_errs.append(rot)
        grip_errs.append(grip)

        if (i + 1) % 50 == 0:
            print(f"  [{label}] {i+1}/{num_samples} | "
                  f"trans={np.mean(trans_errs):.4f}m  rot={np.mean(rot_errs):.2f}°  grip={np.mean(grip_errs):.3f}")

    return {
        'trans_m': np.mean(trans_errs),
        'rot_deg': np.mean(rot_errs),
        'grip': np.mean(grip_errs),
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--num_samples', type=int, default=200)
    parser.add_argument('--orig_ckpt', type=str, default='./checkpoints/model.pt')
    parser.add_argument('--user_ckpt', type=str, default='./runs/my_experiment_5/model.pt')
    parser.add_argument('--data_path', type=str, default='./data/pseudo_test')
    args = parser.parse_args()

    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"Device: {device}")
    print(f"Evaluating on {args.num_samples} pseudo_test samples\n")

    # Dataset
    import os
    n = len(os.listdir(args.data_path))
    dataset = RunningDataset(args.data_path, n, rand_g_prob=0)
    dataloader = DataLoader(dataset, batch_size=1, shuffle=False, num_workers=0)

    results = {}

    # Original paper weights
    print(f"Loading original weights: {args.orig_ckpt}")
    orig_config = base_config.copy()
    orig_config['device'] = device
    orig_config['num_demos'] = 2
    orig_model = load_model(args.orig_ckpt, orig_config)
    print("Evaluating original model...")
    results['original'] = evaluate(orig_model, dataloader, args.num_samples, 'orig')
    del orig_model
    torch.cuda.empty_cache()

    # User's trained weights
    print(f"\nLoading your weights: {args.user_ckpt}")
    user_config = pickle.load(open('./runs/my_experiment_5/config.pkl', 'rb'))
    user_config['device'] = device
    user_model = load_model(args.user_ckpt, user_config)
    print("Evaluating your model...")
    results['yours'] = evaluate(user_model, dataloader, args.num_samples, 'yours')
    del user_model

    # Summary
    print("\n" + "=" * 55)
    print(f"{'Metric':<20} {'Original':>12} {'Yours':>12} {'Ratio':>8}")
    print("-" * 55)
    for metric, label in [('trans_m', 'Trans err (m)'), ('rot_deg', 'Rot err (deg)'), ('grip', 'Grip err')]:
        o = results['original'][metric]
        y = results['yours'][metric]
        ratio = y / o if o > 0 else float('inf')
        print(f"{label:<20} {o:>12.4f} {y:>12.4f} {ratio:>8.2f}x")
    print("=" * 55)
    print("\nInterpretation:")
    print("  Ratio ~1.0 = your model matches original")
    print("  Ratio  >2  = significant gap, needs more training")
    print("  Ratio  <1  = your model is better on pseudo data")

if __name__ == '__main__':
    main()
