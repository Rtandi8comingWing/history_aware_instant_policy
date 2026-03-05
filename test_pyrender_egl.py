#!/usr/bin/env python3
"""
强制 PyRender 使用 EGL 平台的修复脚本
"""
import os
import sys

def main():
    print("修复 PyRender 平台选择...")

    # 1. 设置环境变量强制使用 EGL
    os.environ['PYOPENGL_PLATFORM'] = 'egl'
    os.environ['DISPLAY'] = ''  # 清空 DISPLAY 避免 X11 干扰

    # 2. 强制 PyRender 使用 EGL 平台
    try:
        import pyrender

        # 检查当前平台
        print(f"当前 PyRender 版本: {pyrender.__version__}")

        # 强制设置 EGL 平台
        from pyrender.platforms import egl_platform
        pyrender.platforms._platform = egl_platform.EGLPlatform()

        print("✓ 强制设置 PyRender 使用 EGL 平台")

        # 测试创建 OffscreenRenderer
        renderer = pyrender.OffscreenRenderer(640, 480)
        print("✓ PyRender OffscreenRenderer 创建成功")

        # 清理
        renderer.delete()
        print("✓ 测试完成")

        return True

    except Exception as e:
        print(f"✗ PyRender EGL 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = main()
    if success:
        print("\n" + "="*60)
        print("SUCCESS! PyRender EGL 配置成功")
        print("现在可以运行训练脚本了")
        print("="*60)
        sys.exit(0)
    else:
        print("\n" + "="*60)
        print("FAILED! 需要进一步调试")
        print("="*60)
        sys.exit(1)