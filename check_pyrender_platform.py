#!/usr/bin/env python3
"""
检查 PyRender 平台模块的正确导入方式
"""
import os
os.environ['PYOPENGL_PLATFORM'] = 'egl'

try:
    import pyrender
    print(f"PyRender 版本: {pyrender.__version__}")
    print(f"PyRender 路径: {pyrender.__file__}")

    # 检查 platforms 模块
    print("\n检查 platforms 模块:")
    import pyrender.platforms
    print(f"platforms 路径: {pyrender.platforms.__file__}")
    print(f"platforms 内容: {dir(pyrender.platforms)}")

    # 尝试不同的导入方式
    print("\n尝试导入 EGL 平台:")

    # 方式 1: 直接从 platforms 导入
    try:
        from pyrender.platforms.egl_platform import EGLPlatform
        print("✓ 方式 1 成功: from pyrender.platforms.egl_platform import EGLPlatform")
    except ImportError as e:
        print(f"✗ 方式 1 失败: {e}")

    # 方式 2: 通过 platforms 模块访问
    try:
        egl_platform = pyrender.platforms.egl_platform
        print("✓ 方式 2 成功: pyrender.platforms.egl_platform")
        print(f"  内容: {dir(egl_platform)}")
    except AttributeError as e:
        print(f"✗ 方式 2 失败: {e}")

    # 方式 3: 检查 _platform 属性
    try:
        print(f"\n当前平台: {pyrender.platforms._platform}")
        print(f"平台类型: {type(pyrender.platforms._platform)}")
    except AttributeError as e:
        print(f"✗ 无法访问 _platform: {e}")

    # 方式 4: 列出 platforms 目录的文件
    import os
    platforms_dir = os.path.dirname(pyrender.platforms.__file__)
    print(f"\nplatforms 目录文件:")
    for f in os.listdir(platforms_dir):
        if f.endswith('.py'):
            print(f"  {f}")

    # 方式 5: 尝试创建 OffscreenRenderer（会自动选择平台）
    print("\n尝试创建 OffscreenRenderer:")
    try:
        renderer = pyrender.OffscreenRenderer(640, 480)
        print("✓ OffscreenRenderer 创建成功")
        print(f"  使用的平台: {type(renderer._platform)}")
        renderer.delete()
    except Exception as e:
        print(f"✗ OffscreenRenderer 创建失败: {e}")
        import traceback
        traceback.print_exc()

except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()
