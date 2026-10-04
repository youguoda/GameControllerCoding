# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置（onedir）

onedir 而非 onefile：onefile 每次启动都要把 PyQt6 解压到临时目录，
开机自启时这个延迟很明显。

config/ **不打进包里** —— 它是可写的，由 paths.app_dir() 定位到
exe 旁边。首次运行若没有 config/，程序会用默认值重建。
如果要连默认方案一起分发，把 config/ 手动拷到 dist 目录即可。
"""

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    # 样式由 ui/styles/tokens.py 在运行时生成，没有只读资源要打进来
    datas=[],
    hiddenimports=['pygame', 'pynput', 'pynput.keyboard._win32', 'pynput.mouse._win32'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 用不到的大件，砍掉能明显减小体积
        'tkinter', 'unittest', 'pydoc_data',
        'PyQt6.QtWebEngineCore', 'PyQt6.QtWebEngineWidgets',
        'PyQt6.QtMultimedia', 'PyQt6.QtQuick', 'PyQt6.QtQml', 'PyQt6.Qt3D',
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='GamepadVibeController',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # 无控制台窗口，否则开机自启会闪黑框
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='GamepadVibeController',
)
