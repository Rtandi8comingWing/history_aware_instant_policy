# 伪数据可视化指南

本指南介绍如何可视化生成的伪演示数据，帮助理解数据生成的效果。

---

## 📋 目录

1. [快速开始](#快速开始)
2. [完整可视化](#完整可视化)
3. [可视化内容说明](#可视化内容说明)
4. [自定义可视化](#自定义可视化)
5. [故障排除](#故障排除)

---

## 🚀 快速开始

### 方法1：简化版（推荐新手）

最简单的方式，生成一个演示并快速查看：

```bash
# 在项目根目录运行
conda activate ip_env
python visualize_pseudo_data_simple.py
```

**输出**：
- 生成 `pseudo_demo_quick.png`
- 包含3个子图：点云、轨迹、夹爪状态

**时间**：约 1-2 分钟

---

### 方法2：完整版（详细分析）

生成多个演示，包含详细的可视化和动画帧：

```bash
# 基本用法（生成3个演示）
python visualize_pseudo_data.py

# 自定义参数
python visualize_pseudo_data.py \
    --num_demos 5 \
    --save_dir ./my_visualizations \
    --show_every_n 5
```

**参数说明**：
- `--num_demos`: 生成的演示数量（默认：3）
- `--save_dir`: 保存目录（默认：./visualizations）
- `--show_every_n`: 动画每N帧显示一次（默认：10）
- `--shapenet_path`: ShapeNet数据集路径

**输出**：
- `demo_*_overview.png`：每个演示的概览（4个子图）
- `demo_*_frame_*.png`：轨迹动画帧
- `comparison.png`：多演示对比图

**时间**：约 5-10 分钟（取决于演示数量）

---

## 🎨 可视化内容说明

### 1. 点云可视化

<img src="例子图：点云.png" width="400">

**显示内容**：
- 🔵 **点云**：场景中的3D点（物体+桌面）
  - 颜色：根据高度着色（viridis色图）
  - 密度：自动下采样到2000个点
- 🔴 **夹爪位置**：红色球标记
- 📐 **坐标系**：RGB箭头表示X/Y/Z轴

**理解要点**：
- 点云来自3个深度相机（front, left_shoulder, right_shoulder）
- 点云分割：只包含物体和桌面，去除背景
- 夹爪mesh也会被渲染到点云中

---

### 2. 轨迹可视化

<img src="例子图：轨迹.png" width="400">

**显示内容**：
- 🔵 **蓝色线**：夹爪中心的运动轨迹
- 🟢 **绿点**：夹爪开启状态的位置
- 🔴 **红点**：夹爪关闭状态的位置
- ⭐ **绿色星**：起点
- 🟧 **橙色方**：终点
- 💎 **黄色菱形**：夹爪状态变化点（抓取/释放）

**理解要点**：
- 轨迹是通过航点插值生成的
- 插值方法随机选择（Linear/Cubic/Slerp）
- 状态变化点是关键时刻（夹爪开/闭）

---

### 3. 夹爪状态时序图

<img src="例子图：状态.png" width="400">

**显示内容**：
- 🟢 **绿色区域**：夹爪开启（值=1.0）
- 🔴 **红色区域**：夹爪关闭（值=0.0）
- 🟠 **橙色虚线**：状态变化时刻

**理解要点**：
- 夹爪状态在1-3个随机航点改变
- 50%偏向采样会在任务关键点改变（如抓取时关闭）
- 数据增强会以10%概率翻转状态

---

### 4. 位置变化曲线

<img src="例子图：位置.png" width="400">

**显示内容**：
- 🔴 **红线**：X坐标
- 🟢 **绿线**：Y坐标
- 🔵 **蓝线**：Z坐标（高度）

**理解要点**：
- 平滑的曲线表示良好的插值
- 突变点可能是航点或数据增强扰动
- Z轴变化反映了接近、抓取、提升等动作

---

## 📊 完整可视化示例

### 概览图（Overview）

每个演示生成一个4格概览图：

```
┌─────────────┬─────────────┐
│  点云       │   轨迹      │
│  (中间帧)   │  (全轨迹)   │
├─────────────┼─────────────┤
│  夹爪状态   │  位置曲线   │
│  (时序)     │  (X/Y/Z)    │
└─────────────┴─────────────┘
```

### 动画帧（Animation Frames）

生成多帧图像，显示轨迹执行过程：

```
帧 0:    点云(初始) + 轨迹(起点)
帧 10:   点云 + 轨迹(进行中)
帧 20:   点云 + 轨迹(进行中)
...
帧 N:    点云(最终) + 轨迹(完整)
```

**生成视频**（可选）：
```bash
cd visualizations

# 演示 0
ffmpeg -framerate 10 -pattern_type glob -i 'demo_0_frame_*.png' \
       -c:v libx264 -pix_fmt yuv420p demo_0.mp4

# 演示 1
ffmpeg -framerate 10 -pattern_type glob -i 'demo_1_frame_*.png' \
       -c:v libx264 -pix_fmt yuv420p demo_1.mp4
```

### 对比图（Comparison）

横向对比多个演示：

```
演示0: [轨迹] [状态] [位置]
演示1: [轨迹] [状态] [位置]
演示2: [轨迹] [状态] [位置]
...
```

用于观察：
- 不同任务类型（Grasp/Place/Push/Open/Close）
- 不同插值策略（Linear/Cubic/Slerp）
- 轨迹多样性

---

## 🛠️ 自定义可视化

### 修改可视化脚本

编辑 `visualize_pseudo_data.py`：

```python
# 1. 调整图像分辨率
save_path = self.save_dir / f'demo_{demo_idx}_overview.png'
plt.savefig(save_path, dpi=150, bbox_inches='tight')  # 修改 dpi

# 2. 调整点云显示密度
if len(pcd) > 2000:  # 修改这个数字
    indices = np.random.choice(len(pcd), 2000, replace=False)

# 3. 调整坐标轴范围
ax.set_xlim([-0.5, 0.5])  # 修改范围
ax.set_ylim([-0.5, 0.5])
ax.set_zlim([0, 0.6])

# 4. 修改颜色方案
colors = ['green' if g > 0.5 else 'red' for g in grips]  # 自定义颜色
```

### 生成特定类型的演示

修改生成器以测试特定任务：

```python
from ip.utils.pseudo_demo_generator import PseudoDemoGenerator

generator = PseudoDemoGenerator()

# 强制使用特定任务类型（需要修改源码）
# 在 sample_waypoints() 中注释掉随机选择，固定为：
# task_type = 'grasp'  # 或 'place', 'push', 'open', 'close'

# 强制使用特定插值方法
# 在 generate_trajectory() 中：
# interp_method = 'cubic'  # 或 'linear', 'slerp'
```

---

## 📈 可视化分析技巧

### 1. 检查轨迹质量

**好的轨迹**：
- ✅ 平滑连续
- ✅ 夹爪状态在合理位置改变
- ✅ 轨迹长度适中（30-70帧）
- ✅ 覆盖工作空间的不同区域

**问题轨迹**：
- ❌ 突变或不连续
- ❌ 夹爪状态无意义的变化
- ❌ 过短或过长
- ❌ 集中在狭小区域

### 2. 检查点云质量

**好的点云**：
- ✅ 物体清晰可见
- ✅ 密度适中（1000-3000点）
- ✅ 包含桌面和物体
- ✅ 夹爪在合理位置

**问题点云**：
- ❌ 空白或噪声过多
- ❌ 物体不可见
- ❌ 点云过于稀疏或密集

### 3. 检查任务多样性

生成多个演示后，检查：
- 是否有不同的任务类型（Grasp/Place/Push等）
- 轨迹形状是否多样
- 起点和终点是否分布广泛
- 物体位置是否随机

---

## 🐛 故障排除

### 问题1：找不到 ShapeNet

**错误**：
```
❌ 加载 ShapeNet 失败: No such file or directory
```

**解决**：
```bash
# 检查路径
ls /media/tianyi/Tiantian/tianyiStudy/DataSets/ShapeNetCore.v2

# 或指定正确路径
python visualize_pseudo_data.py --shapenet_path /your/path/to/shapenet
```

---

### 问题2：点云为空

**错误**：
```
⚠️  点云为空
```

**原因**：
- 渲染失败
- 深度图无效
- 物体太远

**解决**：
1. 检查物体是否加载成功
2. 检查相机位置设置
3. 增加调试输出

---

### 问题3：可视化很慢

**原因**：
- 点云太密集
- 生成的帧太多

**解决**：
```bash
# 减少点云密度（修改代码）
if len(pcd) > 1000:  # 从2000改为1000
    ...

# 减少动画帧
python visualize_pseudo_data.py --show_every_n 20  # 增大这个值

# 减少演示数量
python visualize_pseudo_data.py --num_demos 1
```

---

### 问题4：内存不足

**错误**：
```
MemoryError: ...
```

**解决**：
```bash
# 一次只生成一个
python visualize_pseudo_data.py --num_demos 1

# 或使用简化版
python visualize_pseudo_data_simple.py
```

---

### 问题5：matplotlib 显示问题

**问题**：图形不显示或报错

**解决**：
```python
# 如果使用无头模式（服务器）
import matplotlib
matplotlib.use('Agg')  # 在 import pyplot 之前

# 或确保有GUI支持
export DISPLAY=:0  # Linux
```

---

## 📚 相关文档

- **数据生成实现**：`docs/analysis/DATA_GENERATION_COMPLIANCE.md`
- **相机配置**：`docs/analysis/CAMERA_AND_SAMPLING_ANALYSIS.md`
- **代码实现**：`ip/utils/pseudo_demo_generator.py`

---

## 💡 使用建议

### 调试数据生成

1. **首次使用**：运行简化版，快速检查
   ```bash
   python visualize_pseudo_data_simple.py
   ```

2. **详细分析**：生成少量演示，查看细节
   ```bash
   python visualize_pseudo_data.py --num_demos 3
   ```

3. **批量检查**：生成多个演示，检查多样性
   ```bash
   python visualize_pseudo_data.py --num_demos 10 --show_every_n 20
   ```

### 验证实现

使用可视化验证关键功能：

- [x] **物体附加/分离**：观察红点（关闭）后物体是否移动
- [x] **插值策略**：比较不同演示的轨迹平滑度
- [x] **任务类型**：识别Grasp/Place/Push等模式
- [x] **夹爪网格**：点云中是否包含夹爪几何

### 训练前检查

在开始训练前：

1. ✅ 生成10-20个演示
2. ✅ 检查轨迹质量和多样性
3. ✅ 确认点云质量
4. ✅ 验证夹爪状态合理
5. ✅ 查看对比图，确保没有重复模式

---

## 🎯 示例输出

### 命令行输出

```
================================================================================
🎨 伪演示数据可视化工具
================================================================================

📂 加载 ShapeNet 数据集: /path/to/ShapeNetCore.v2
✅ 成功加载 ShapeNet

🎭 初始化伪数据生成器...
✅ 生成器初始化完成

🎬 生成 3 个伪演示...

--- 生成演示 1/3 ---
  📦 物体1: 1234 顶点
  📦 物体2: 2345 顶点
  ✅ 生成完成:
     - 轨迹长度: 52 帧
     - 点云数: 52
     - 夹爪状态变化: 2 种

--- 生成演示 2/3 ---
  ...

🎨 开始可视化...

--- 可视化演示 1/3 ---

📊 演示 0 统计:
  - 总帧数: 52
  - 点云数量: 52
  - 夹爪状态变化: 2 种状态
  - 夹爪开启帧: 26.0 / 52
  - 夹爪关闭帧: 26 / 52

✅ 保存概览图: ./visualizations/demo_0_overview.png

🎬 生成动画帧...
  - 已生成 5/11 帧
✅ 完成！共生成 11 帧

================================================================================
✅ 可视化完成！
📁 结果保存在: ./visualizations
================================================================================

💡 查看结果:
   概览图: ./visualizations/demo_*_overview.png
   动画帧: ./visualizations/demo_*_frame_*.png
   对比图: ./visualizations/comparison.png

💡 生成视频（可选）:
   ffmpeg -framerate 10 -pattern_type glob -i './visualizations/demo_0_frame_*.png' \
          -c:v libx264 -pix_fmt yuv420p ./visualizations/demo_0.mp4
```

---

**最后更新**: 2026-02-06  
**作者**: Cursor AI Agent
