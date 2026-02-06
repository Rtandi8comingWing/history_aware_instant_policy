# Instant Policy - 项目总结

## 项目概述

基于论文 "Instant Policy: In-Context Imitation Learning via Graph Diffusion" 的实现，使用图扩散模型进行上下文模仿学习。

## 目录结构

```
instant_policy_origin_specific/
├── ip/                          # 核心代码包
│   ├── models/                  # 模型定义
│   │   ├── diffusion.py         # 图扩散模型
│   │   ├── model.py             # AGI 模型
│   │   ├── graph_transformer.py # 图Transformer
│   │   └── scene_encoder.py     # 场景编码器
│   ├── utils/                   # 工具函数
│   │   ├── pseudo_demo_generator.py  # 伪演示生成器
│   │   ├── shapenet_loader.py        # ShapeNet加载器
│   │   └── data_proc.py              # 数据处理
│   ├── configs/                 # 配置
│   │   └── base_config.py       # 基础配置
│   └── train.py                 # 训练脚本
├── docs/                        # 文档
│   ├── guides/                  # 使用指南
│   ├── references/              # 快速参考
│   ├── analysis/                # 分析文档
│   └── updates/                 # 更新记录
├── deploy_sim.py                # 仿真推理脚本
├── generate_pseudo_data.py      # 预生成伪数据脚本
├── train_with_pseudo.py         # 连续生成伪数据训练脚本
├── visualize_pseudo_data.py     # 数据可视化脚本
└── sim_utils.py                 # 仿真工具函数
```

## 核心功能

### 1. 数据生成
- **预生成模式**: `generate_pseudo_data.py` - 一次性生成固定数量的伪演示
- **连续生成模式**: `train_with_pseudo.py` - 训练时动态生成伪演示
- **可视化**: `visualize_pseudo_data.py` - 可视化生成的伪演示数据

### 2. 模型训练
- **基础训练**: `ip/train.py` - 使用预生成数据训练
- **连续训练**: `train_with_pseudo.py` - 动态生成数据边训练
- **支持特性**:
  - 混合精度训练 (FP16-mixed on GPU, FP32 on CPU)
  - 梯度累积
  - Checkpoint保存和恢复
  - WandB日志记录

### 3. 仿真推理
- **仿真脚本**: `deploy_sim.py` - 在RLBench环境中评估模型
- **支持任务**: plate_out, stack_blocks, etc.
- **灵活配置**: 支持自定义模型路径、演示数量等

## 数据生成细节（严格遵循论文附录D）

### 场景设置
- 从ShapeNet数据集中采样2个物体
- 随机放置在平面上
- 使用3个深度相机（无腕部相机）

### 轨迹生成
- 随机采样2-6个航点
- 使用多种插值策略：linear, cubic, slerp
- **物体附加策略**（严格实现）:
  - 夹爪状态改变时附加/分离最近物体
  - 附加物体跟随夹爪运动
  - 模拟真实的抓取/放置行为

### 偏置采样
- 50%随机轨迹
- 50%偏向常见任务：
  - grasp (抓取)
  - place (放置)
  - push (推动)
  - open (打开)
  - close (关闭)

### 数据增强
- 30%轨迹添加局部扰动（恢复行为）
- 10%数据点翻转夹爪状态（重新抓取行为）

## 配置说明

### 基础配置 (`ip/configs/base_config.py`)

```python
config = {
    'device': 'cuda',              # 'cuda' 或 'cpu'
    'batch_size': 16,              # 训练批大小
    'num_demos': 2,                # 上下文演示数量
    'hidden_dim': 1024,            # 隐藏层维度
    'num_scenes_nodes': 16,        # 场景节点数
    'traj_horizon': 10,            # 轨迹长度
    # ... 更多配置
}
```

### 显存优化配置（适用于6GB GPU）

```python
config = {
    'device': 'cuda',
    'batch_size': 1,               # 减小批大小
    'num_demos': 1,                # 减少演示数量
    'hidden_dim': 512,             # 减小隐藏层
    'num_scenes_nodes': 8,         # 减少节点数
    'traj_horizon': 8,             # 缩短轨迹
}
```

配合 `train.py` 中的梯度累积 (`accumulate_grad_batches=8`)，可在小显存GPU上训练。

## 环境设置

### 方式1：Conda（推荐）

```bash
conda env create -f environment.yml
conda activate ip_env
```

### 方式2：Pip

```bash
pip install -r requirements.txt
```

**注意**: PyTorch Geometric依赖复杂，推荐使用conda。

## 快速开始

### 1. 生成伪数据

```bash
python generate_pseudo_data.py \
    --output_dir=./data/train \
    --num_tasks=100 \
    --val_tasks=20 \
    --num_workers=8
```

### 2. 训练模型

```bash
python ip/train.py \
    --run_name=my_experiment \
    --data_path_train=./data/train \
    --data_path_val=./data/val \
    --record=1
```

### 3. 仿真推理

```bash
python deploy_sim.py \
    --model_path=./runs/my_experiment \
    --task_name=plate_out \
    --num_demos=2 \
    --num_rollouts=10
```

### 4. 可视化数据

```bash
# 简单可视化
python visualize_pseudo_data_simple.py

# 完整可视化（包括动画帧）
python visualize_pseudo_data.py
```

## 常见问题解决

### 1. CUDA Out of Memory

**症状**: `torch.cuda.OutOfMemoryError`

**解决方案**:
- 减小 `batch_size` (推荐: 1-2)
- 减小 `num_demos` (推荐: 1)
- 减小 `hidden_dim` (推荐: 512)
- 减小 `num_scenes_nodes` (推荐: 8)
- 使用梯度累积
- 或切换到CPU训练 (`device='cpu'`)

### 2. 数据形状不匹配

**症状**: `RuntimeError: Sizes of tensors must match`

**原因**: `num_demos` 数量不一致

**解决方案**:
1. 检查 `base_config.py` 中的 `num_demos`
2. 确保数据生成时使用了固定的 `num_context`
3. 重新生成数据

### 3. 环境包冲突

**症状**: 修改配置不生效，或加载错误目录的代码

**解决方案**:
```bash
# 卸载旧包
conda run -n ip_env pip uninstall instant_policy -y

# 确认当前使用正确目录
python -c "import ip; print(ip.__file__)"
```

### 4. CPU训练时出现GPU错误

**原因**: `precision='16-mixed'` 不支持CPU

**解决方案**: 已在 `train.py` 中自动处理，根据device选择precision。

## 重要修复记录

### 1. 环境配置问题（已解决）
- **问题**: conda环境中安装了指向错误目录的包
- **影响**: 配置修改不生效，训练和仿真使用错误代码
- **解决**: 卸载旧包，确保加载正确目录

### 2. 精度配置问题（已解决）
- **问题**: CPU训练时强制使用16-mixed精度
- **解决**: 自动根据device选择precision

### 3. 参数传递问题（已解决）
- **问题**: argparse默认值覆盖配置文件
- **解决**: 将默认值改为None，只在明确提供时覆盖

### 4. 模型路径问题（已解决）
- **问题**: deploy_sim.py不支持自定义model_path
- **解决**: 添加--model_path参数

### 5. 数据生成完全符合论文（已实现）
- **实现**: 严格按照附录D实现所有细节
- **包括**: 物体附加策略、偏置采样、数据增强等

## 文档资源

### 使用指南
- `docs/guides/CHECKPOINT_MANAGEMENT.md` - Checkpoint管理完整指南
- `docs/guides/VISUALIZATION_GUIDE.md` - 数据可视化指南
- `VISUALIZATION_README.md` - 可视化快速开始

### 快速参考
- `docs/references/CHECKPOINT_QUICK_REFERENCE.txt` - Checkpoint快速参考
- `docs/references/CAMERA_SAMPLING_QUICK_REFERENCE.txt` - 相机和采样配置
- `docs/references/FULL_COMPLIANCE_SUMMARY.txt` - 论文合规性总结

### 分析文档
- `docs/analysis/DATA_GENERATION_COMPLIANCE.md` - 数据生成合规性分析
- `docs/analysis/CAMERA_AND_SAMPLING_ANALYSIS.md` - 相机和采样策略分析

### 更新记录
- `docs/updates/FULL_COMPLIANCE_UPDATE.md` - 完全合规性更新详情
- `docs/updates/VALIDATION_SET_UPDATE.md` - 验证集更新

## 关键脚本

### Checkpoint管理
```bash
./manage_checkpoints.sh [command] [options]
# 命令: list, info, copy, compare, cleanup
```

### 快速启动
```bash
./quick_start_shapenet.sh
# 自动下载ShapeNet、生成数据、开始训练
```

## 性能建议

### GPU训练（推荐）
- **最低要求**: 6GB VRAM (需要大幅优化配置)
- **推荐配置**: 12GB+ VRAM (可使用原始配置)
- **最佳体验**: 24GB+ VRAM (A100, RTX 3090等)

### CPU训练
- **优点**: 内存充足，稳定
- **缺点**: 速度慢约100倍
- **适用**: 验证代码、小规模实验

### 云GPU选择
- **经济型**: T4, P100 (12-16GB)
- **高性能**: V100, A100 (16-40GB)
- **性价比**: RTX 3090, RTX 4090 (24GB)

## 依赖关键版本

- Python: 3.10+
- PyTorch: 2.2.0
- PyTorch Geometric: 2.5.0
- PyTorch Lightning: 2.4.0
- NumPy: 1.26.4
- Open3D: 0.18.0

## 引用

如果使用本项目，请引用原始论文：

```bibtex
@article{instant_policy_2024,
  title={Instant Policy: In-Context Imitation Learning via Graph Diffusion},
  author={...},
  journal={...},
  year={2024}
}
```

## 许可证

请参考原始论文和代码的许可证。

## 联系与支持

- 问题反馈: 通过GitHub Issues
- 文档: `docs/` 目录
- 论文: `10684_Instant_Policy_In_Contex.pdf`

---

**最后更新**: 2026-02-07  
**项目状态**: ✅ 生产就绪
**环境状态**: ✅ 已修复所有已知问题
