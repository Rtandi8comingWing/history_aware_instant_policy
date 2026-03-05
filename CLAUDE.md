# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 提供在此代码库中工作的指导。

## 项目概述

**Instant Policy** - 基于图扩散的上下文模仿学习 (ICLR 2025)

这是一个研究实现，使用图扩散模型训练机器人操作策略。核心创新是使用 ShapeNet 物体生成的合成伪演示数据进行训练，在预训练阶段无需真实机器人数据。

## 核心架构

### 模型流程 (AGI - Action Graph Imitation)

1. **场景编码器** (`ip/models/scene_encoder.py`): 将点云编码为局部特征
2. **图表示** (`ip/models/graph_rep.py`): 构建包含场景节点和夹爪节点的异构图
3. **三阶段图 Transformer** (`ip/models/model.py`):
   - **局部编码器**: 处理单个演示
   - **条件编码器**: 聚合多个演示的上下文
   - **动作编码器**: 通过扩散去噪预测动作
4. **扩散模型** (`ip/models/diffusion.py`): DDIM 调度器用于动作生成

### 数据生成系统

项目实现了论文附录 D 的伪演示生成：

- **ShapeNet 加载器** (`ip/utils/shapenet_loader.py`): 加载 55 个类别，52K+ 3D 模型
- **伪演示生成器** (`ip/utils/pseudo_demo_generator.py`):
  - 采样 2-6 个航点，带偏置采样（50% 随机，50% 任务偏向）
  - 生成带物体附加模拟的轨迹
  - 使用 PyRender 渲染 3 个相机视角
  - 应用数据增强（30% 扰动，10% 夹爪翻转）
- **连续数据集** (`ip/utils/continuous_dataset.py`): 训练时后台生成

## 常用命令

### 环境设置

```bash
# 激活环境
conda activate ip_env
export PYOPENGL_PLATFORM=egl  # 无头渲染必需

# 以开发模式安装包
pip install -e .
```

### 训练

```bash
# 使用连续伪数据生成训练（推荐）
python train_with_pseudo.py \
    --run_name=experiment_name \
    --num_pseudo_samples=700000 \
    --buffer_size=1000 \
    --num_generator_threads=4 \
    --batch_size=16 \
    --record=1

# 使用预生成数据训练
python ip/train.py \
    --data_path_train=./data/train \
    --data_path_val=./data/val \
    --run_name=experiment_name \
    --record=1

# 在真实数据上微调（PD++ 设置）
python train_with_pseudo.py \
    --fine_tune=1 \
    --model_path=./checkpoints \
    --real_data_path=./data/rlbench \
    --real_data_ratio=0.5 \
    --record=1
```

### 数据生成

```bash
# 生成伪演示（批量模式）
python generate_pseudo_data.py \
    --num_tasks=100000 \
    --num_workers=8 \
    --output_dir=./data/train

# 快速测试生成
python test_pseudo_generation.py

# 可视化生成的数据
python visualize_pseudo_data_simple.py
python visualize_pseudo_data.py  # 完整可视化，包含动画
```

### 部署

```bash
# 在 RLBench 仿真中运行
python deploy_sim.py \
    --model_path=./checkpoints \
    --task_name=plate_out \
    --num_demos=2 \
    --num_rollouts=10

# 可用任务: plate_out, stack_blocks 等
```

### 测试

```bash
# 测试伪数据生成系统
python test_pseudo_generation.py

# 测试特定组件
python -c "from ip.utils.shapenet_loader import ShapeNetLoader; loader = ShapeNetLoader(); print(f'{loader.get_num_models()} models loaded')"
```

## 关键配置

### 基础配置 (`ip/configs/base_config.py`)

关键参数：
- `device`: 'cuda' 或 'cpu'
- `batch_size`: 4-16（根据 GPU 显存调整）
- `num_demos`: 2（上下文演示数量）
- `hidden_dim`: 1024（模型容量）
- `traj_horizon`: 10（轨迹长度）
- `pre_horizon`: 8（预测范围）
- `num_diffusion_iters_train`: 100（训练扩散步数）
- `num_diffusion_iters_test`: 8（推理扩散步数）

### 显存优化

对于有限的 GPU 显存（6-8GB）：
```python
config = {
    'batch_size': 1,
    'num_demos': 1,
    'hidden_dim': 512,
    'num_scenes_nodes': 8,
}
```
使用 `ip/train.py` 中的梯度累积（已设置为 8）。

## 重要实现细节

### 场景编码器处理

代码自动处理缺失的 `scene_encoder.pt`：
- 如果找到：加载预训练权重并可选冻结
- 如果缺失：从头训练（`train.py` 和 `train_with_pseudo.py` 都会处理）
- 位置：`./checkpoints/scene_encoder.pt`

### 数据格式

训练样本保存为单独的 `.pt` 文件：
```python
{
    'demos': [  # 上下文演示列表
        {
            'obs': List[torch.Tensor],      # 点云 (N, 3)
            'T_w_es': torch.Tensor,         # 夹爪位姿 (T, 4, 4)
            'grips': torch.Tensor,          # 夹爪状态 (T, 1)
        },
        ...
    ],
    'live': {  # 当前要预测的轨迹
        'obs': List[torch.Tensor],
        'T_w_es': torch.Tensor,
        'grips': torch.Tensor,
        'actions': torch.Tensor,            # 真实动作 (T, 4, 4)
        'grip_actions': torch.Tensor,       # 夹爪动作 (T, 1)
    }
}
```

### 验证集

验证数据是可选的但推荐使用：
- 生成方式：`python generate_pseudo_data.py --val_tasks=10`
- 如果未找到，训练会自动跳过验证
- 详见 `docs/updates/VALIDATION_SET_UPDATE.md`

### 连续生成 vs 批量生成

**连续生成** (`train_with_pseudo.py`)：
- 训练时在后台线程生成数据
- 内存高效（基于缓冲区）
- 符合论文方法
- DataLoader 必须使用 `num_workers=0`

**批量生成** (`generate_pseudo_data.py` + `ip/train.py`)：
- 训练前预生成所有数据
- 更易调试和检查
- 可跨运行重用数据
- 支持并行生成

## 项目结构

```
ip/
├── models/
│   ├── diffusion.py          # Lightning 模块，训练循环
│   ├── model.py              # AGI 模型（三阶段图 Transformer）
│   ├── graph_transformer.py  # 异构图 Transformer
│   ├── graph_rep.py          # 图构建逻辑
│   └── scene_encoder.py      # 点云编码器
├── utils/
│   ├── shapenet_loader.py           # ShapeNet 数据集接口
│   ├── pseudo_demo_generator.py     # 合成演示生成
│   ├── continuous_dataset.py        # 后台生成数据集
│   ├── running_dataset.py           # 标准数据集加载器
│   ├── data_proc.py                 # 数据格式转换
│   └── common_utils.py              # SE(3) 变换
├── configs/
│   └── base_config.py        # 超参数
└── train.py                  # 训练脚本（预生成数据）
```

## 常见问题

### CUDA 显存不足
- 减小 `batch_size` 至 1-2
- 减小 `num_demos` 至 1
- 减小 `hidden_dim` 至 512
- 使用梯度累积（已启用）
- 切换到 CPU：`config['device'] = 'cpu'`

### 生成进程被杀死（OOM）
使用 `train_with_pseudo.py` 时：
- 减小 `--num_generator_threads` 至 1-2
- 减小 `--buffer_size` 至 500
- 监控系统内存（不仅是 GPU）

### CPU 上的精度错误
已处理：训练在 CPU 上自动使用 FP32，在 GPU 上使用 FP16-mixed。

### ShapeNet 路径
默认：`/media/tianyi/Tiantian/tianyiStudy/DataSets/ShapeNetCore.v2`
在脚本中更新或传递 `--shapenet_root` 参数。

## 开发工作流

1. **测试系统**：`python test_pseudo_generation.py`
2. **快速训练测试**：`./quick_start_shapenet.sh`（选项 1）
3. **完整训练**：使用快速启动脚本的选项 2 或 3
4. **监控**：检查 `./runs/` 中的日志和检查点
5. **评估**：使用 `deploy_sim.py` 进行 RLBench 任务

## 论文合规性

实现严格遵循论文附录 D：
- ✅ ShapeNet 物体采样（每个场景 2 个物体）
- ✅ 航点采样（2-6 个航点，50% 偏置）
- ✅ 轨迹插值（1cm/3° 分辨率）
- ✅ 物体附加模拟
- ✅ 3 相机渲染（无腕部相机）
- ✅ 数据增强（30% 扰动 + 10% 翻转）
- ✅ ~700K 训练轨迹

详见 `docs/analysis/DATA_GENERATION_COMPLIANCE.md`。

## 文档

`docs/` 中的完整文档：
- **指南**：`docs/guides/README_SHAPENET_TRAINING.md`（主指南）
- **快速参考**：`docs/references/QUICK_SUMMARY.txt`
- **更新**：`docs/updates/`（错误修复和改进）
- **分析**：`docs/analysis/`（技术深入分析）

## 依赖

关键包：
- PyTorch 2.2.0 + CUDA
- PyTorch Geometric 2.5.0（图神经网络）
- PyTorch Lightning 2.4.0（训练框架）
- PyRender（3D 渲染）
- Trimesh（3D 模型处理）
- Open3D 0.18.0（点云处理）
- Diffusers（DDIM 调度器）

安装方式：`conda env create -f environment.yml` 或 `pip install -r requirements.txt`

## 模型检查点

`./checkpoints/` 或 `./runs/<run_name>/` 中的结构：
```
checkpoints/
├── model.pt           # 完整模型检查点（450MB）
├── scene_encoder.pt   # 预训练编码器（可选）
└── config.pkl         # 训练配置
```

加载模型：
```python
from ip.models.diffusion import GraphDiffusion
import pickle

config = pickle.load(open('checkpoints/config.pkl', 'rb'))
model = GraphDiffusion.load_from_checkpoint(
    'checkpoints/model.pt',
    config=config,
    map_location='cuda'
)
```

## 训练规模

论文设置：
- ~700K 唯一伪轨迹
- 2.5M 训练步数
- 高端 GPU 上约 5 天

实用建议：
- **快速测试**：1K 样本，约 5 分钟
- **小规模**：100K 样本，适合验证
- **完整规模**：700K 样本，生产训练

## 未来开发注意事项

- 模型使用包含场景节点和夹爪节点的异构图
- 边类型编码空间和时间关系
- 扩散在归一化的 SE(3) 动作空间中操作（6D：平移 + 角轴）
- 三阶段 Transformer 架构至关重要：局部 → 条件 → 动作
- 训练期间的连续生成符合论文但内存密集
- 预训练场景编码器改善收敛但非必需
