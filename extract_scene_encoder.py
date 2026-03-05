#!/usr/bin/env python
"""Extract scene_encoder weights from model.pt"""
import torch
import os

print("="*60)
print("Extracting scene_encoder from model.pt")
print("="*60)

# 加载完整模型
checkpoint = torch.load('./checkpoints/model.pt', map_location='cpu')
state_dict = checkpoint['state_dict']
print(f"\n✓ Loaded checkpoint with {len(state_dict)} total parameters")

# 提取 scene_encoder 权重，正确处理键名
scene_encoder_state = {}
for key, value in state_dict.items():
    if 'scene_encoder' in key:
        # 移除 'model.scene_encoder.' 前缀
        new_key = key.replace('model.scene_encoder.', '')
        scene_encoder_state[new_key] = value

print(f"✓ Extracted {len(scene_encoder_state)} scene_encoder parameters")
print("\nSample keys (first 3):")
for i, key in enumerate(list(scene_encoder_state.keys())[:3]):
    print(f"  {i+1}. {key}")

# 保存
output_path = './checkpoints/scene_encoder.pt'
torch.save(scene_encoder_state, output_path)
print(f"\n✓ Saved to: {output_path}")
print(f"  File size: {os.path.getsize(output_path) / 1024 / 1024:.2f} MB")

# 验证可以加载到 SceneEncoder 模型
print("\n" + "="*60)
print("Verifying extraction")
print("="*60)

from ip.models.scene_encoder import SceneEncoder

model = SceneEncoder(num_freqs=10, embd_dim=512)
try:
    model.load_state_dict(scene_encoder_state)
    print("✅ SUCCESS: Weights load correctly into SceneEncoder")
    
    # 测试前向传播
    dummy_pcd = torch.randn(1, 2048, 3)
    with torch.no_grad():
        output = model(dummy_pcd)
    print(f"✅ Forward pass successful")
    print(f"   Input shape: {dummy_pcd.shape}")
    print(f"   Output shape: {output.shape}")
    
except Exception as e:
    print(f"❌ ERROR: {e}")
    print("\nDebugging info:")
    print("Expected keys in model:", list(model.state_dict().keys())[:3])
    print("Got keys:", list(scene_encoder_state.keys())[:3])

print("\n" + "="*60)
print("✅ Extraction complete!")
print("="*60)
