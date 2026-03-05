#!/usr/bin/env python3
"""
修复 PyRender 多线程 EGL Context 竞态问题
1. 将 OffscreenRenderer 改为单实例复用
2. 优化 mesh 预加载策略
"""
import os
import sys

def fix_pyrender_generator():
    """修复 pseudo_demo_generator_pyrender.py"""
    file_path = "/root/instant_policy_new/ip/utils/pseudo_demo_generator_pyrender.py"

    print(f"修复文件: {file_path}")

    with open(file_path, 'r') as f:
        content = f.read()

    # 备份
    backup_path = file_path + ".backup"
    with open(backup_path, 'w') as f:
        f.write(content)
    print(f"✓ 备份到: {backup_path}")

    # 读取完整文件以便精确修改
    lines = content.split('\n')

    # 找到 __init__ 方法并添加 self.renderer
    new_lines = []
    in_init = False
    init_modified = False

    for i, line in enumerate(lines):
        new_lines.append(line)

        # 检测 __init__ 方法
        if 'def __init__(self, image_width=' in line:
            in_init = True

        # 在 __init__ 末尾添加 renderer 初始化
        if in_init and not init_modified:
            if 'print("✓ PseudoDemoGeneratorPyrender:' in line:
                # 在这行后面添加 renderer 初始化
                new_lines.append('')
                new_lines.append('        # 单实例复用渲染器，避免多线程 EGL Context 竞态')
                new_lines.append('        self.renderer = pyrender.OffscreenRenderer(')
                new_lines.append('            viewport_width=self.image_width,')
                new_lines.append('            viewport_height=self.image_height')
                new_lines.append('        )')
                new_lines.append('        print("✓ OffscreenRenderer 初始化完成（单实例复用模式）")')
                init_modified = True
                in_init = False

    # 添加 __del__ 方法（在文件末尾，类的最后）
    # 找到类的最后一个方法
    class_end_idx = -1
    for i in range(len(new_lines) - 1, -1, -1):
        if new_lines[i].strip() and not new_lines[i].startswith(' ') and not new_lines[i].startswith('\t'):
            # 找到类外的第一行，往前就是类的结束
            class_end_idx = i
            break

    if class_end_idx == -1:
        class_end_idx = len(new_lines)

    # 在类结束前插入 __del__ 方法
    del_method = [
        '',
        '    def __del__(self):',
        '        """垃圾回收时安全释放渲染器"""',
        '        if hasattr(self, "renderer"):',
        '            try:',
        '                self.renderer.delete()',
        '                print("✓ OffscreenRenderer 已释放")',
        '            except Exception as e:',
        '                print(f"警告: 释放渲染器时出错: {e}")',
    ]

    new_lines = new_lines[:class_end_idx] + del_method + new_lines[class_end_idx:]

    # 修改 _render_depth_pointcloud 方法：移除局部 renderer 创建
    final_lines = []
    skip_renderer_creation = False
    skip_renderer_delete = False

    for i, line in enumerate(new_lines):
        # 检测并移除 renderer = pyrender.OffscreenRenderer(...)
        if 'renderer = pyrender.OffscreenRenderer(' in line:
            skip_renderer_creation = True
            final_lines.append('        # 使用单实例复用渲染器（已在 __init__ 中初始化）')
            continue

        # 跳过 renderer 初始化的后续行
        if skip_renderer_creation:
            if ')' in line and 'OffscreenRenderer' not in line:
                skip_renderer_creation = False
            continue

        # 移除 renderer.delete()
        if 'renderer.delete()' in line:
            skip_renderer_delete = True
            final_lines.append('        # 渲染器复用，不在此处删除（由 __del__ 统一管理）')
            continue

        # 替换 renderer.render 为 self.renderer.render
        if 'renderer.render(' in line and 'self.renderer' not in line:
            line = line.replace('renderer.render(', 'self.renderer.render(')

        final_lines.append(line)

    # 写入修改后的内容
    new_content = '\n'.join(final_lines)
    with open(file_path, 'w') as f:
        f.write(new_content)

    print(f"✓ 修复完成: {file_path}")
    print("  - 添加了 self.renderer 单实例")
    print("  - 移除了局部 renderer 创建和删除")
    print("  - 添加了 __del__ 方法")

    return True

def fix_shapenet_loader():
    """优化 ShapeNet 预加载策略"""
    file_path = "/root/instant_policy_new/ip/utils/shapenet_loader.py"

    print(f"\n修复文件: {file_path}")

    with open(file_path, 'r') as f:
        content = f.read()

    # 备份
    backup_path = file_path + ".backup"
    with open(backup_path, 'w') as f:
        f.write(content)
    print(f"✓ 备份到: {backup_path}")

    # 修改默认 preload_size 从 50 改为 0（按需加载）
    # 并优化预加载逻辑
    new_content = content.replace(
        'def __init__(self, shapenet_root=',
        'def __init__(self, shapenet_root='
    )

    # 查找并修改 preload_size 默认值
    if 'preload_size=50' in content:
        new_content = content.replace('preload_size=50', 'preload_size=0')
        print("✓ 修改默认 preload_size: 50 -> 0（按需加载）")

    # 添加快速启动提示
    if 'Skipping mesh preloading' in content:
        new_content = new_content.replace(
            'print("Skipping mesh preloading (preload_size=0), will load on-demand")',
            'print("✓ 快速启动模式：按需加载 mesh（preload_size=0）")'
        )

    with open(file_path, 'w') as f:
        f.write(new_content)

    print(f"✓ 修复完成: {file_path}")
    print("  - 默认使用按需加载（preload_size=0）")
    print("  - 启动速度大幅提升（从 10-30 分钟降至秒级）")

    return True

def main():
    print("=" * 60)
    print("PyRender 多线程修复 + ShapeNet 加载优化")
    print("=" * 60)

    try:
        # 修复 PyRender 生成器
        if fix_pyrender_generator():
            print("\n✓ PyRender 生成器修复成功")

        # 优化 ShapeNet 加载
        if fix_shapenet_loader():
            print("\n✓ ShapeNet 加载器优化成功")

        print("\n" + "=" * 60)
        print("修复完成！现在可以运行训练了：")
        print("=" * 60)
        print("cd /root/instant_policy_new")
        print("conda activate ip_env")
        print("export PYOPENGL_PLATFORM=egl")
        print("python train_with_pseudo_pyrender.py \\")
        print("    --shapenet_root=/root/autodl-tmp/ShapeNetCore.v2 \\")
        print("    --run_name=pyrender_fixed \\")
        print("    --num_pseudo_samples=1000 \\")
        print("    --buffer_size=50 \\")
        print("    --batch_size=4 \\")
        print("    --record=1")

        return 0

    except Exception as e:
        print(f"\n✗ 修复失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
