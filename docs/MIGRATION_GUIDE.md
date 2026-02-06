# 文档迁移说明

## 📋 概述

所有文档已从项目根目录迁移到 `docs/` 目录，并按类型分类整理。

**迁移日期**: 2026-02-06

---

## 🔄 文档迁移对照表

### 使用指南 (guides/)

| 原位置 | 新位置 |
|--------|--------|
| `README_SHAPENET_TRAINING.md` | `docs/guides/README_SHAPENET_TRAINING.md` |
| `PSEUDO_DATA_GENERATION_GUIDE.md` | `docs/guides/PSEUDO_DATA_GENERATION_GUIDE.md` |
| `DEPLOYMENT_GUIDE.md` | `docs/guides/DEPLOYMENT_GUIDE.md` |
| `DATA_PREPARATION_GUIDE.md` | `docs/guides/DATA_PREPARATION_GUIDE.md` |

### 技术分析 (analysis/)

| 原位置 | 新位置 |
|--------|--------|
| `ShapeNet伪数据生成分析.md` | `docs/analysis/ShapeNet伪数据生成分析.md` |
| `分析报告.md` | `docs/analysis/分析报告.md` |
| `数据生成策略分析.md` | `docs/analysis/数据生成策略分析.md` |
| `训练数据来源分析-更新版.md` | `docs/analysis/训练数据来源分析-更新版.md` |

### 更新说明 (updates/)

| 原位置 | 新位置 |
|--------|--------|
| `TRAINING_FIX.md` | `docs/updates/TRAINING_FIX.md` |
| `VALIDATION_SET_UPDATE.md` | `docs/updates/VALIDATION_SET_UPDATE.md` |
| `PROJECT_UPDATE_SHAPENET.md` | `docs/updates/PROJECT_UPDATE_SHAPENET.md` |
| `更正说明.md` | `docs/updates/更正说明.md` |

### 快速参考 (references/)

| 原位置 | 新位置 |
|--------|--------|
| `QUICK_SUMMARY.txt` | `docs/references/QUICK_SUMMARY.txt` |
| `FILES_CREATED.txt` | `docs/references/FILES_CREATED.txt` |
| `数据生成策略-快速参考.md` | `docs/references/数据生成策略-快速参考.md` |
| `伪数据生成策略总结.txt` | `docs/references/伪数据生成策略总结.txt` |
| `核心发现-ShapeNet代码缺失.txt` | `docs/references/核心发现-ShapeNet代码缺失.txt` |

### 项目总结 (summary/)

| 原位置 | 新位置 |
|--------|--------|
| `SUMMARY_SHAPENET_IMPLEMENTATION.md` | `docs/summary/SUMMARY_SHAPENET_IMPLEMENTATION.md` |

---

## 📝 新增文件

### 文档索引

- `docs/README.md` - 文档中心主页，提供所有文档的导航
- `docs/.doc_structure` - 文档结构和分类规则说明

### 项目主页

- `README.md` - 项目主README（已完全重写）

---

## 🔗 引用更新

以下文件中的文档引用已更新：

1. **quick_start_shapenet.sh**
   - 添加了文档链接提示

2. **generate_pseudo_data.py**
   - 输出中添加文档引用

3. **test_pseudo_generation.py**
   - 成功提示中添加文档链接

4. **ip/train.py**
   - 验证集缺失提示中更新文档路径

5. **train_with_pseudo.py**
   - 验证集缺失提示中更新文档路径

---

## 💡 如何查找文档

### 方法 1: 使用文档索引

```bash
# 查看文档中心
cat docs/README.md
```

### 方法 2: 按类型浏览

```bash
# 使用指南
ls docs/guides/

# 技术分析
ls docs/analysis/

# 更新说明
ls docs/updates/

# 快速参考
ls docs/references/

# 项目总结
ls docs/summary/
```

### 方法 3: 搜索文档

```bash
# 按文件名搜索
find docs/ -name "*training*"

# 按内容搜索
grep -r "ShapeNet" docs/
```

---

## 📚 快速访问常用文档

```bash
# 主文档
cat docs/guides/README_SHAPENET_TRAINING.md

# 快速参考
cat docs/references/QUICK_SUMMARY.txt

# 最新更新
ls -lt docs/updates/
```

---

## 🎯 新文档创建指南

创建新文档时，请遵循以下规则：

1. **确定文档类型**，选择合适的目录
2. **遵循命名规范**（见 `docs/.doc_structure`）
3. **更新文档索引**（在 `docs/README.md` 中添加链接）
4. **更新统计信息**（如果需要）

详细规则请查看: `docs/.doc_structure`

---

## ✅ 迁移完成检查清单

- ✅ 所有文档已移动到 `docs/` 目录
- ✅ 文档已按类型分类
- ✅ 创建了文档索引 (`docs/README.md`)
- ✅ 更新了项目主页 (`README.md`)
- ✅ 更新了脚本中的文档引用
- ✅ 创建了分类规则说明 (`docs/.doc_structure`)
- ✅ 根目录保持简洁（仅 `README.md`）
- ✅ 创建了本迁移指南

---

## 📞 问题排查

### Q: 找不到某个文档？

**A**: 使用上面的对照表查找新位置，或搜索：
```bash
find docs/ -name "原文件名"
```

### Q: 脚本引用的文档路径错误？

**A**: 所有主要脚本已更新。如果发现问题，请检查：
- `quick_start_shapenet.sh`
- `generate_pseudo_data.py`
- `test_pseudo_generation.py`
- `ip/train.py`
- `train_with_pseudo.py`

### Q: 如何恢复旧的文档结构？

**A**: 不建议恢复。新结构更清晰。如果确实需要，可以使用 git 回退：
```bash
git log --all -- "*.md" "*.txt"  # 查看文档历史
```

---

**迁移完成**: ✅  
**状态**: 生产就绪  
**维护者**: Cursor AI Agent
