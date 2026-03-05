#!/usr/bin/env python3
"""
诊断 EGL 库符号和函数可用性
"""
import ctypes
import os
import subprocess

def main():
    print("=" * 60)
    print("EGL 库符号诊断")
    print("=" * 60)

    # 1. 检查可用的 EGL 库
    egl_paths = [
        "/usr/lib/x86_64-linux-gnu/libEGL.so.1",
        "/usr/lib/x86_64-linux-gnu/libEGL_nvidia.so.580.76.05",
        "/usr/lib/x86_64-linux-gnu/libEGL_mesa.so.0",
        "/usr/lib/x86_64-linux-gnu/libEGL.so",
    ]

    working_libs = []
    for path in egl_paths:
        if os.path.exists(path):
            print(f"✓ 找到 EGL 库: {path}")
            try:
                lib = ctypes.CDLL(path)
                working_libs.append((path, lib))
                print(f"  ✓ 可以加载")
            except Exception as e:
                print(f"  ✗ 加载失败: {e}")
        else:
            print(f"✗ 不存在: {path}")

    print()

    # 2. 检查每个库的符号
    required_symbols = [
        'eglGetCurrentContext',
        'eglGetCurrentDisplay',
        'eglGetCurrentSurface',
        'eglInitialize',
        'eglTerminate',
        'eglCreateContext',
        'eglMakeCurrent',
        'eglSwapBuffers'
    ]

    for path, lib in working_libs:
        print(f"检查库 {path} 的符号:")
        available_symbols = []
        missing_symbols = []

        for symbol in required_symbols:
            try:
                func = getattr(lib, symbol)
                available_symbols.append(symbol)
                print(f"  ✓ {symbol}")
            except AttributeError:
                missing_symbols.append(symbol)
                print(f"  ✗ {symbol}")

        print(f"  可用符号: {len(available_symbols)}/{len(required_symbols)}")
        print()

    # 3. 使用 nm 命令检查符号表
    print("使用 nm 检查符号表:")
    for path, _ in working_libs:
        try:
            result = subprocess.run(['nm', '-D', path],
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                symbols = result.stdout
                egl_symbols = [line for line in symbols.split('\n')
                             if 'egl' in line.lower()]
                print(f"\n{path} 中的 EGL 符号 (前10个):")
                for symbol in egl_symbols[:10]:
                    print(f"  {symbol}")

                # 检查特定符号
                if 'eglGetCurrentContext' in symbols:
                    print("  ✓ 找到 eglGetCurrentContext")
                else:
                    print("  ✗ 未找到 eglGetCurrentContext")
            else:
                print(f"  nm 命令失败: {result.stderr}")
        except Exception as e:
            print(f"  nm 检查失败: {e}")

    # 4. 检查 NVIDIA EGL 扩展
    print("\n" + "=" * 60)
    print("NVIDIA EGL 扩展检查")
    print("=" * 60)

    nvidia_egl_paths = [
        "/usr/lib/x86_64-linux-gnu/libEGL_nvidia.so.580.76.05",
        "/usr/lib/x86_64-linux-gnu/libEGL_nvidia.so.0",
    ]

    for path in nvidia_egl_paths:
        if os.path.exists(path):
            print(f"✓ NVIDIA EGL: {path}")
            try:
                lib = ctypes.CDLL(path)
                # 尝试 NVIDIA 特定的函数
                nvidia_symbols = [
                    'eglGetCurrentContext',
                    'eglQueryDevicesEXT',
                    'eglGetPlatformDisplayEXT'
                ]
                for symbol in nvidia_symbols:
                    try:
                        func = getattr(lib, symbol)
                        print(f"  ✓ {symbol}")
                    except AttributeError:
                        print(f"  ✗ {symbol}")
            except Exception as e:
                print(f"  加载失败: {e}")

    # 5. 推荐解决方案
    print("\n" + "=" * 60)
    print("推荐解决方案")
    print("=" * 60)

    # 找到最好的 EGL 库
    best_lib = None
    best_score = 0

    for path, lib in working_libs:
        score = 0
        for symbol in required_symbols:
            try:
                getattr(lib, symbol)
                score += 1
            except AttributeError:
                pass

        print(f"{path}: {score}/{len(required_symbols)} 符号可用")
        if score > best_score:
            best_score = score
            best_lib = path

    if best_lib:
        print(f"\n推荐使用: {best_lib}")
        print("修复方案:")
        print(f'1. 在代码中使用: ctypes.CDLL("{best_lib}")')
        print("2. 或者考虑使用 OSMesa 后端 (CPU 渲染)")
        print("3. 或者回到优化的 CPU 数据生成版本")
    else:
        print("\n✗ 没有找到完全兼容的 EGL 库")
        print("建议使用 OSMesa 后端或 CPU 版本")

if __name__ == '__main__':
    main()