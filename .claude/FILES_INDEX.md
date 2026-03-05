# .claude/ 目录文件索引

本目录包含 Claude Code 的所有配置和文档文件。

## 📁 文件列表

### 核心配置文件

#### `preferences.md` ⭐ 最重要
**用途：** Claude Code 的主要配置文件  
**内容：** 语言偏好、文档格式、项目背景  
**何时使用：** `/init` 命令自动读取  
**优先级：** 最高  

**快速查看：**
```bash
cat .claude/preferences.md
```

---

#### `CLAUDE.md.template`
**用途：** CLAUDE.md 的模板文件  
**内容：** 标准章节结构、双语格式示例  
**何时使用：** `/init` 命令参考此模板  
**优先级：** 参考  

**快速查看：**
```bash
cat .claude/CLAUDE.md.template
```

---

### 管理工具

#### `manage-language.sh` ⭐ 核心工具
**用途：** 语言配置管理脚本  
**功能：**
- 查看配置状态 (`status`)
- 切换语言模式 (`set-chinese`, `set-english`, `set-bilingual`)
- 测试配置 (`test`)
- 备份恢复 (`backup`, `restore`)
- 显示帮助 (`help`)

**使用示例：**
```bash
# 查看状态
./.claude/manage-language.sh status

# 切换到双语
./.claude/manage-language.sh set-bilingual

# 测试配置
./.claude/manage-language.sh test
```

---

### 文档文件

#### `HOW_TO_USE.md` ⭐ 完整指南
**用途：** 详细的使用指南  
**内容：**
- 快速开始
- 完整工作流程
- 语言模式对比
- 故障排除
- 最佳实践
- 高级用法

**适合：** 首次使用或需要详细说明时阅读

**快速查看：**
```bash
less .claude/HOW_TO_USE.md
```

---

#### `QUICK_REFERENCE.txt` ⭐ 快速参考
**用途：** 快速参考卡片  
**内容：**
- 核心命令速查
- 配置文件位置
- 语言模式说明
- 故障排除快速指南

**适合：** 日常使用时快速查阅

**快速查看：**
```bash
cat .claude/QUICK_REFERENCE.txt
```

---

#### `README.md`
**用途：** .claude 目录说明  
**内容：**
- 文件说明
- 如何修改语言偏好
- 配置优先级
- 常见问题
- 维护建议

**适合：** 了解 .claude 目录的整体结构

**快速查看：**
```bash
cat .claude/README.md
```

---

#### `SUMMARY.md` ⭐ 完整总结
**用途：** 配置系统的完整总结  
**内容：**
- 配置完成状态
- 已创建文件列表
- 配置功能说明
- 快速使用指南
- 当前配置详情
- 工作原理
- 验证清单

**适合：** 了解整个配置系统的全貌

**快速查看：**
```bash
less .claude/SUMMARY.md
```

---

#### `FILES_INDEX.md`
**用途：** 本文件，文件索引  
**内容：** 所有文件的说明和使用方法

---

## 🎯 快速导航

### 我想...

**查看当前配置状态**
```bash
./.claude/manage-language.sh status
```

**切换语言模式**
```bash
./.claude/manage-language.sh set-bilingual  # 双语
./.claude/manage-language.sh set-chinese    # 中文
./.claude/manage-language.sh set-english    # 英文
```

**测试配置是否正确**
```bash
./.claude/manage-language.sh test
```

**查看快速参考**
```bash
cat .claude/QUICK_REFERENCE.txt
```

**查看完整使用指南**
```bash
less .claude/HOW_TO_USE.md
```

**查看配置总结**
```bash
less .claude/SUMMARY.md
```

**备份 CLAUDE.md**
```bash
./.claude/manage-language.sh backup
```

**恢复 CLAUDE.md**
```bash
./.claude/manage-language.sh restore
```

---

## 📊 文件大小和行数

| 文件 | 大小 | 行数 | 类型 |
|------|------|------|------|
| `preferences.md` | 4KB | 30 | 配置 |
| `CLAUDE.md.template` | 4KB | 54 | 模板 |
| `manage-language.sh` | 12KB | 298 | 脚本 |
| `HOW_TO_USE.md` | 8KB | 416 | 文档 |
| `QUICK_REFERENCE.txt` | 8KB | 129 | 文档 |
| `README.md` | 4KB | 152 | 文档 |
| `SUMMARY.md` | 16KB | 500+ | 文档 |
| `FILES_INDEX.md` | 本文件 | - | 索引 |

**总计：** 8 个文件，约 56KB

---

## 🔄 文件关系图

```
.claude/
│
├── preferences.md ──────────┐
│   (主配置)                  │
│                            │
├── CLAUDE.md.template ──────┤
│   (模板参考)                │
│                            ├──→ /init 命令读取
├── manage-language.sh ──────┤    生成 CLAUDE.md
│   (管理工具)                │
│                            │
└── 文档文件 ────────────────┘
    ├── HOW_TO_USE.md (完整指南)
    ├── QUICK_REFERENCE.txt (快速参考)
    ├── README.md (目录说明)
    ├── SUMMARY.md (完整总结)
    └── FILES_INDEX.md (本文件)
```

---

## 🎨 使用场景

### 场景 1：首次了解配置系统
**推荐阅读顺序：**
1. `QUICK_REFERENCE.txt` - 快速了解
2. `SUMMARY.md` - 完整概览
3. `HOW_TO_USE.md` - 详细指南

### 场景 2：日常使用
**常用命令：**
```bash
./.claude/manage-language.sh status  # 查看状态
./.claude/manage-language.sh test    # 测试配置
cat .claude/QUICK_REFERENCE.txt      # 查看参考
```

### 场景 3：切换语言模式
**操作步骤：**
1. 查看 `HOW_TO_USE.md` 中的"切换语言模式"章节
2. 运行 `manage-language.sh set-<mode>`
3. 删除旧 CLAUDE.md 并运行 `/init`

### 场景 4：故障排除
**查看：**
- `QUICK_REFERENCE.txt` - 快速故障排除
- `HOW_TO_USE.md` - 详细故障排除
- `SUMMARY.md` - 故障排除章节

---

## 💡 提示

- 所有文档都支持中英双语
- 使用 `less` 命令查看长文档（支持翻页）
- 使用 `cat` 命令查看短文档（直接显示）
- 管理脚本支持彩色输出，便于阅读

---

## 🔗 相关文件

### 项目根目录

- `../CLAUDE.md` - 当前的项目指导文件
- `../.cursorrules` - AI 助手通用配置
- `../README.md` - 项目说明（包含语言偏好）
- `../.gitignore` - Git 忽略规则（已添加备份文件）

---

## 📝 维护说明

### 添加新文件时

1. 在本文件中添加说明
2. 更新 `SUMMARY.md` 中的文件列表
3. 如果是配置文件，更新 `README.md`

### 修改配置时

1. 修改 `preferences.md`
2. 运行 `manage-language.sh test` 验证
3. 更新相关文档

### 更新文档时

1. 保持中英双语格式
2. 更新"最后更新"日期
3. 提交到 Git

---

**最后更新：** 2026-02-08  
**维护者：** Claude Code  
**版本：** 1.0
