# -*- coding: utf-8 -*-
"""运行时路径解析

源码运行和 PyInstaller 打包后，`__file__` 的含义完全不同，所以所有
路径推导都必须走这里，不能各自 `os.path.dirname(__file__)`。

分两类，混淆它们会出真问题：

- **可写资源**（config/）—— 必须落在 exe 旁边（便携式），
  写进打包的临时解压目录会在退出时蒸发

（曾经还有第三类「只读资源 theme.qss」，样式改为运行时从
ui/styles/tokens.py 生成后就没了 —— 别为不存在的资源写路径逻辑。）
"""

import os
import sys


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def app_dir() -> str:
    """可写资源的根目录

    打包后 = exe 所在目录（便携：config/ 就在 exe 旁边）
    源码运行 = 项目根（gamepad_mapper_qt/）
    """
    if is_frozen():
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def launch_target() -> str:
    """开机自启要写进注册表的命令

    打包后就是 exe 自己；源码运行时用 pythonw + main.py，
    以免每次开机弹一个黑框。

    一律带 --minimized：开机时直接进托盘，不该弹出主窗口。
    """
    if is_frozen():
        return f'"{os.path.abspath(sys.executable)}" --minimized'

    main_py = os.path.join(app_dir(), "main.py")
    exe = sys.executable
    if exe.lower().endswith("python.exe"):
        pythonw = os.path.join(os.path.dirname(exe), "pythonw.exe")
        if os.path.isfile(pythonw):
            exe = pythonw
    return f'"{exe}" "{main_py}" --minimized'
