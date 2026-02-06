# Instant Policy - 仿真推理部署指南

## 项目状态 ✅

该项目已经过完整分析和修复，**可以正常运行仿真推理**。

## 环境信息

- **Conda 环境**: `ip_env`
- **Python**: 3.10
- **CUDA**: 支持（可选，CPU也可运行）
- **关键依赖**: PyTorch 2.2.0, PyG, RLBench, Lightning

## 文件修改说明

已修复以下文件以确保正常运行：

### 1. `deploy_sim.py`
- ✅ 修复了导入语句：`from instant_policy` → `from ip.models.diffusion`
- ✅ 添加了配置文件加载逻辑（支持 config.pkl 或使用默认配置）
- ✅ 添加了scene_encoder.pt缺失检测和自动降级处理
- ✅ 正确初始化模型以进行推理

### 2. `sim_utils.py`
- ✅ 修复了导入语句：使用 `ip.utils.*` 替代 `instant_policy` 和 `utils`
- ✅ 修复了模型调用API：使用 `model.test_step()` 而不是不存在的 `predict_actions()`
- ✅ 添加了场景编码处理逻辑
- ✅ 添加了必要的 torch 导入

## 快速开始

### 基本用法

```bash
# 激活环境
conda activate ip_env

# 运行仿真推理
cd /home/tianyi/RAGD/instant_policy_origin_specific
python deploy_sim.py --task_name=plate_out --num_demos=2 --num_rollouts=10
```

### 参数说明

- `--task_name`: RLBench任务名称（默认: `plate_out`）
  - 可选任务见 `sim_utils.py` 中的 `TASK_NAMES` 字典
  - 例如: `open_box`, `close_box`, `phone_on_base`, `toilet_seat_down` 等
  
- `--num_demos`: 演示数量（默认: 2）
  - 推荐值: 1-5
  
- `--num_rollouts`: 评估次数（默认: 10）
  - 用于计算成功率
  
- `--restrict_rot`: 是否限制旋转范围（默认: 1）
  - 1 = 启用限制（推荐）
  - 0 = 不限制

### 示例命令

```bash
# 1. 快速测试（1次评估）
python deploy_sim.py --task_name=plate_out --num_demos=2 --num_rollouts=1

# 2. 完整评估（10次）
python deploy_sim.py --task_name=plate_out --num_demos=2 --num_rollouts=10

# 3. 不同任务测试
python deploy_sim.py --task_name=open_box --num_demos=3 --num_rollouts=5

# 4. 更多演示
python deploy_sim.py --task_name=toilet_seat_down --num_demos=4 --num_rollouts=10
```

## 模型权重

### 当前状态
- ✅ `checkpoints/model.pt` (450MB) - 主模型权重（已存在）
- ⚠️ `checkpoints/scene_encoder.pt` - 场景编码器（缺失，但已自动处理）
- ⚠️ `checkpoints/config.pkl` - 配置文件（缺失，使用默认配置）

### 性能说明
当前配置使用**未预训练的场景编码器**，这可能会影响性能。如需最佳性能，请下载完整权重：

```bash
cd ip
./scripts/download_weights.sh
```

这将从Google Drive下载完整的预训练权重。

## 测试结果

✅ **测试通过**（2026-02-06）

```
任务: plate_out (从彩色碗架上取盘子)
演示数量: 2
评估次数: 1
结果: 成功率 100%

输出样例:
DEBUG: actions shape: (8, 4, 4)
DEBUG: Action[0] trans: [-0.00396911 -0.00336481  0.00859544], mag: 0.010047
DEBUG: Action[1] trans: [-0.00798344 -0.00684901  0.0171558 ], mag: 0.020124
DEBUG: Action[2] trans: [-0.01193011 -0.01046544  0.02538092], mag: 0.029934
Success rate: 1.0
```

## 支持的任务列表

从 `sim_utils.py` 中可以看到支持的任务：

| 任务名称 | 描述 | RLBench类 |
|---------|------|-----------|
| `lift_lid` | 打开锅盖 | TakeLidOffSaucepan |
| `phone_on_base` | 将电话放在底座上 | PhoneOnBase |
| `open_box` | 打开盒子 | OpenBox |
| `slide_block` | 滑动方块到目标 | SlideBlockToTarget |
| `close_box` | 关闭盒子 | CloseBox |
| `basketball` | 篮球投篮 | BasketballInHoop |
| `buzz` | Beat the Buzz | BeatTheBuzz |
| `close_microwave` | 关闭微波炉 | CloseMicrowave |
| `plate_out` | 从碗架取盘子 | TakePlateOffColoredDishRack |
| `toilet_seat_down` | 放下马桶座圈 | ToiletSeatDown |
| `toilet_seat_up` | 抬起马桶座圈 | ToiletSeatUp |
| `toilet_roll_off` | 取下卷纸 | TakeToiletRollOffStand |
| `open_microwave` | 打开微波炉 | OpenMicrowave |
| `lamp_on` | 打开台灯 | LampOn |
| `umbrella_out` | 从伞架取雨伞 | TakeUmbrellaOutOfUmbrellaStand |
| `push_button` | 按按钮 | PushButton |
| `put_rubbish` | 扔垃圾 | PutRubbishInBin |

## 故障排除

### 1. 模型加载失败
**问题**: `FileNotFoundError: scene_encoder.pt`
**解决**: 脚本会自动检测并禁用预训练编码器，不需要手动处理

### 2. CUDA内存不足
**解决方案**: 
- 减少 `num_demos` 参数
- 或在 CPU 上运行（自动检测）

### 3. RLBench环境启动失败
**解决方案**:
- 确保已正确安装RLBench
- 检查CoppeliaSim是否正常工作
- 尝试使用 `headless=True` 模式

### 4. 导入错误
**检查环境**:
```bash
conda activate ip_env
python -c "import ip; import rlbench; print('OK')"
```

## 性能优化建议

1. **下载完整权重**: 运行 `cd ip && ./scripts/download_weights.sh`
2. **启用模型编译**: 在代码中设置 `config['compile_models'] = True`（需要PyTorch 2.0+）
3. **调整扩散步数**: 减少 `num_diffusion_iters_test` 可以加速推理（可能影响精度）
4. **使用GPU**: 确保CUDA可用以获得最佳性能

## 项目结构

```
instant_policy_origin_specific/
├── checkpoints/           # 模型权重目录
│   └── model.pt          # 主模型（450MB）
├── ip/                   # 核心包
│   ├── configs/          # 配置文件
│   ├── models/           # 模型定义
│   └── utils/            # 工具函数
├── deploy_sim.py         # 仿真推理主脚本 ✅ 已修复
├── sim_utils.py          # 仿真工具函数 ✅ 已修复
└── environment.yml       # Conda环境配置
```

## 技术细节

### 模型架构
- **主模型**: GraphDiffusion（基于图扩散的策略网络）
- **场景编码器**: SceneEncoder（点云编码）
- **图表示**: 使用PyTorch Geometric进行图神经网络处理
- **动作预测**: 8步预测视野（可配置）

### 推理流程
1. 收集演示（live demos from RLBench）
2. 将演示转换为条件输入
3. 对每个时间步：
   - 获取当前观察（点云、夹持器状态）
   - 编码演示和实时场景
   - 通过扩散模型预测动作序列
   - 执行动作直到任务完成或超时

## 参考资料

- 项目主页: https://www.robot-learning.uk/instant-policy
- 原始仓库: https://github.com/vv19/instant_policy
- RLBench: https://github.com/stepjam/RLBench

## 版本信息

- 修复日期: 2026-02-06
- 测试环境: Ubuntu 22.04, CUDA 11.8, Python 3.10
- 状态: ✅ 可运行
