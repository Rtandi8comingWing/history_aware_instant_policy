#!/usr/bin/env python3
"""
Fix PyOpenGL EGL module to enable PyRender GPU rendering.
Run this on the remote server: python fix_egl_remote.py
"""
import os
import sys

def main():
    egl_module_path = "/root/miniconda3/envs/ip_env/lib/python3.10/site-packages/OpenGL/platform/egl.py"

    print(f"Fixing EGL module at: {egl_module_path}")

    # Check if file exists
    if not os.path.exists(egl_module_path):
        print(f"ERROR: File not found: {egl_module_path}")
        return 1

    # Read current content
    with open(egl_module_path, 'r') as f:
        content = f.read()

    # Check if already patched
    if 'ctypes.CDLL("/usr/lib/x86_64-linux-gnu/libEGL.so.1")' in content:
        print("✓ Already patched!")
        return 0

    # Create the fix code
    fix_lines = [
        '"""EGL platform implementation"""',
        'import ctypes',
        'import os',
        '',
        '# Force-load EGL library to work around PyOpenGL 3.1.0 bug',
        'try:',
        '    _egl_lib = ctypes.CDLL("/usr/lib/x86_64-linux-gnu/libEGL.so.1")',
        '    print("EGL library loaded successfully via ctypes")',
        'except Exception as e:',
        '    print(f"Warning: Could not pre-load EGL library: {e}")',
        '',
    ]
    fix_code = '\n'.join(fix_lines)

    # Find where to insert (after first docstring)
    if '"""' in content:
        # Split by docstring
        parts = content.split('"""', 2)
        if len(parts) >= 3:
            # Reconstruct: opening quote + docstring + closing quote + fix + rest
            new_content = parts[0] + '"""' + parts[1] + '"""' + '\n' + fix_code + '\n' + parts[2]
        else:
            # No proper docstring, just prepend
            new_content = fix_code + '\n' + content
    else:
        # No docstring at all, just prepend
        new_content = fix_code + '\n' + content

    # Backup original
    backup_path = egl_module_path + ".backup"
    if not os.path.exists(backup_path):
        with open(backup_path, 'w') as f:
            f.write(content)
        print(f"✓ Backup created: {backup_path}")

    # Write patched version
    with open(egl_module_path, 'w') as f:
        f.write(new_content)

    print(f"✓ Patched {egl_module_path}")
    print("\nTesting import...")

    # Test import
    try:
        # Clear module cache
        for mod in list(sys.modules.keys()):
            if 'OpenGL' in mod:
                del sys.modules[mod]

        from OpenGL.platform import egl
        print("✓ EGL module imports successfully")

        # Try to access EGL
        if hasattr(egl, 'EGL'):
            print("✓ EGL attribute exists")
        else:
            print("✗ EGL attribute still missing (but module loads)")

    except Exception as e:
        print(f"✗ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    print("\n" + "="*60)
    print("SUCCESS! EGL module patched.")
    print("You can now test PyRender with:")
    print("  python -c 'import pyrender; print(\"PyRender OK\")'")
    print("="*60)
    return 0

if __name__ == '__main__':
    sys.exit(main())
