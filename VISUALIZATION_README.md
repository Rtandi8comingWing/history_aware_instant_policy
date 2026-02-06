# 伪数据可视化 - 快速开始

可视化生成的伪演示数据，直观了解数据质量和生成效果。

---

## 🎯 两种使用方式

### ⚡ 方式1：快速预览（推荐新手）

最快的方式，1-2分钟生成一个演示预览：

```bash
conda activate ip_env
python visualize_pseudo_data_simple.py
```

**输出**：`pseudo_demo_quick.png`（3个子图）

---

### 📊 方式2：详细分析（深入研究）

生成多个演示，包含动画帧和对比图：

```bash
# 基本用法（3个演示）
python visualize_pseudo_data.py

# 自定义参数
python visualize_pseudo_data.py \
    --num_demos 5 \
    --save_dir ./my_visualizations \
    --show_every_n 5
```

**输出**：保存在 `./visualizations/` 目录

---

## 📁 输出内容

### 简化版输出

```
pseudo_demo_quick.png
├─ 点云（中间帧）
├─ 轨迹（完整）
└─ 夹爪状态（时序）
```

### 完整版输出

```
visualizations/
├─ demo_0_overview.png          # 概览（4子图）
├─ demo_0_frame_0000.png        # 动画帧
├─ demo_0_frame_0010.png
├─ ...
├─ demo_1_overview.png
├─ demo_1_frame_*.png
└─ comparison.png               # 多演示对比
```

---

## 🎨 可视化内容

### 1. 点云（Point Cloud）
- 3D场景：物体+桌面+夹爪
- 颜色：根据高度着色
- 红色标记：夹爪位置

### 2. 轨迹（Trajectory）
- 蓝线：夹爪运动路径
- 绿点：夹爪开启
- 红点：夹爪关闭
- 黄色菱形：状态变化点

### 3. 夹爪状态（Gripper State）
- 时序图：显示开/闭状态变化
- 橙色虚线：状态变化时刻

### 4. 位置曲线（Position）
- X/Y/Z 坐标随时间变化

---

## ✅ 验证清单

使用可视化验证关键功能：

- [ ] **物体附加/分离**：夹爪关闭后物体跟随移动
- [ ] **插值策略多样性**：不同演示轨迹平滑度不同
- [ ] **任务类型**：识别 Grasp/Place/Push/Open/Close
- [ ] **夹爪网格**：点云中包含夹爪几何
- [ ] **数据增强**：30%有扰动，10%状态翻转

---

## 🎬 生成视频（可选）

将动画帧合成为视频：

```bash
cd visualizations

# 合成演示0的视频
ffmpeg -framerate 10 -pattern_type glob -i 'demo_0_frame_*.png' \
       -c:v libx264 -pix_fmt yuv420p demo_0.mp4

# 合成演示1的视频
ffmpeg -framerate 10 -pattern_type glob -i 'demo_1_frame_*.png' \
       -c:v libx264 -pix_fmt yuv420p demo_1.mp4
```

---

## 🐛 常见问题

### Q: 找不到 ShapeNet

```bash
# 检查路径
ls /media/tianyi/Tiantian/tianyiStudy/DataSets/ShapeNetCore.v2

# 或指定路径
python visualize_pseudo_data.py --shapenet_path /your/path
```

### Q: 可视化太慢

```bash
# 减少演示数量
python visualize_pseudo_data.py --num_demos 1

# 增加帧间隔
python visualize_pseudo_data.py --show_every_n 20

# 或使用简化版
python visualize_pseudo_data_simple.py
```

### Q: 内存不足

使用简化版或一次只生成一个演示：

```bash
python visualize_pseudo_data.py --num_demos 1
```

---

## 📚 详细文档

查看完整指南：

📖 **[docs/guides/VISUALIZATION_GUIDE.md](docs/guides/VISUALIZATION_GUIDE.md)**

包含：
- 详细使用说明
- 可视化内容解释
- 自定义可视化
- 分析技巧
- 故障排除

---

## 💡 使用建议

### 首次使用

1. 运行简化版，快速检查：
   ```bash
   python visualize_pseudo_data_simple.py
   ```

2. 如果效果OK，运行完整版：
   ```bash
   python visualize_pseudo_data.py --num_demos 3
   ```

### 训练前检查

1. 生成 10-20 个演示
2. 查看对比图，确保多样性
3. 验证物体附加/分离效果
4. 确认不同插值策略都有使用

---

## 🔗 相关文档

- **数据生成指南**：`docs/guides/PSEUDO_DATA_GENERATION_GUIDE.md`
- **相机配置分析**：`docs/analysis/CAMERA_AND_SAMPLING_ANALYSIS.md`
- **符合度分析**：`docs/analysis/DATA_GENERATION_COMPLIANCE.md`

---

**创建日期**: 2026-02-06  
**作者**: Cursor AI Agent
