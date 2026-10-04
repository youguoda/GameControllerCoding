# -*- coding: utf-8 -*-
"""路径解析的规格

打包后这几条全都会变，而源码运行时永远看不出问题 ——
所以必须把「冻结」状态模拟出来测，否则只有装到别人机器上才发现。
"""

import os
import sys

import pytest

from core import paths


@pytest.fixture
def 假装已打包(monkeypatch, tmp_path):
    exe = tmp_path / "GamepadVibeController.exe"
    exe.write_bytes(b"")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    return tmp_path


def test_源码运行时可写目录是项目根():
    assert os.path.isfile(os.path.join(paths.app_dir(), "main.py"))


def test_打包后可写目录是_exe_所在目录(假装已打包):
    """便携式：config/ 必须在 exe 旁边，不能进临时解压目录"""
    assert paths.app_dir() == str(假装已打包)


def test_打包后配置目录跟着走(假装已打包, monkeypatch):
    from core import config_store as cs
    assert cs._profiles_dir().startswith(str(假装已打包))
    assert cs._app_state_path().startswith(str(假装已打包))


def test_打包后自启命令就是_exe_本身(假装已打包):
    """不能再拼 python.exe + main.py —— 打包后两者都不存在"""
    命令 = paths.launch_target()
    assert os.path.abspath(sys.executable) in 命令
    assert "main.py" not in 命令
    assert "python" not in 命令.lower()


def test_自启命令一律带_minimized():
    """开机时该直接进托盘，不该弹出主窗口"""
    assert "--minimized" in paths.launch_target()


def test_源码运行时自启命令用_pythonw_避免黑框():
    命令 = paths.launch_target()
    assert "main.py" in 命令
    if sys.executable.lower().endswith("python.exe"):
        pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if os.path.isfile(pythonw):
            assert "pythonw" in 命令.lower()
