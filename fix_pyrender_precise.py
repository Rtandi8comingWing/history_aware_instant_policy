#!/usr/bin/env python3
"""
精确修复 PyRender 多线程问题 - 手动编辑版本
"""
import os

def main():
    file_path = "/root/instant_policy_new/ip/utils/pseudo_demo_generator_pyrender.py"

    print(f"读取文件: {file_path}")
    with open(file_path, 'r') as f:
        lines = f.readlines()

    # 备份
    backup_path = file_path + ".backup2"
    with open(backup_path, 'w') as f:
        f.writelines(lines)
    print(f"✓ 备份到: {backup_path}")

    # 读取原始文件重新开始
    original_path = file_path + ".backup"
    if os.path.exists(original_path):
        print(f"从原始备份恢复: {original_path}")
        with open(original_path, 'r') as f:
            lines = f.readlines()

    new_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # 1. 在 __init__ 方法的 print 语句后添加 renderer 初始化
        if '✓ PseudoDemoGeneratorPyrender:' in line and 'print(' in line:
            new_lines.append(line)
            # 添加空行和 renderer 初始化
            new_lines.append('\n')
            new_lines.append('        # 单实例复用渲染器，避免多线程 EGL Context 竞态\n')
            new_lines.append('        self.renderer = pyrender.OffscreenRenderer(\n')
            new_lines.append('            viewport_width=self.image_width,\n')
            new_lines.append('            viewport_height=self.image_height\n')
            new_lines.append('        )\n')
            new_lines.append('        print("✓ OffscreenRenderer 初始化完成（单实例复用模式）")\n')
            i += 1
            continue

        # 2. 移除 renderer = pyrender.OffscreenRenderer(...) 及其参数行
        if 'renderer = pyrender.OffscreenRenderer(' in line:
            new_lines.append('        # 使用单实例复用渲染器（已在 __init__ 中初始化）\n')
            # 跳过这一行和后续的参数行，直到找到闭合括号
            i += 1
            while i < len(lines) and ')' not in lines[i]:
                i += 1
            i += 1  # 跳过包含 ')' 的行
            continue

        # 3. 替换 renderer.render 为 self.renderer.render
        if 'color, depth = renderer.render(' in line:
            line = line.replace('renderer.render(', 'self.renderer.render(')

        # 4. 移除 renderer.delete()
        if 'renderer.delete()' in line:
            new_lines.append('        # 渲染器复用，不在此处删除（由 __del__ 统一管理）\n')
            i += 1
            continue

        new_lines.append(line)
        i += 1

    # 5. 在文件末尾添加 __del__ 方法（找到类的最后一个方法）
    # 从后往前找，找到最后一个有缩进的非空行
    insert_pos = len(new_lines)
    for j in range(len(new_lines) - 1, -1, -1):
        stripped = new_lines[j].strip()
        if stripped and new_lines[j].startswith('    '):  # 类方法级别的缩进
            insert_pos = j + 1
            break

    # 插入 __del__ 方法
    del_method = [
        '\n',
        '    def __del__(self):\n',
        '        """垃圾回收时安全释放渲染器"""\n',
        '        if hasattr(self, "renderer"):\n',
        '            try:\n',
        '                self.renderer.delete()\n',
        '                print("✓ OffscreenRenderer 已释放")\n',
        '            except Exception as e:\n',
        '                print(f"警告: 释放渲染器时出错: {e}")\n',
    ]

    new_lines = new_lines[:insert_pos] + del_method + new_lines[insert_pos:]

    # 写入修改后的文件
    with open(file_path, 'w') as f:
        f.writelines(new_lines)

    print(f"✓ 修复完成: {file_path}")
    print("\n修改内容:")
    print("  1. 在 __init__ 中添加 self.renderer 单实例")
    print("  2. 移除 _render_depth_pointcloud 中的局部 renderer 创建")
    print("  3. 替换 renderer.render 为 self.renderer.render")
    print("  4. 移除 renderer.delete() 调用")
    print("  5. 添加 __del__ 方法统一管理渲染器释放")

    # 验证语法
    print("\n验证 Python 语法...")
    import py_compile
    try:
        py_compile.compile(file_path, doraise=True)
        print("✓ 语法检查通过")
    except py_compile.PyCompileError as e:
        print(f"✗ 语法错误: {e}")
        return 1

    return 0

if __name__ == '__main__':
    import sys
    sys.exit(main())
