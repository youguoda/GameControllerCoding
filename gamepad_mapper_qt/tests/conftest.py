# -*- coding: utf-8 -*-
"""共享 fixture：Qt 会话与配置隔离的主窗口

主窗口构造/交互测试共用。隔离手法与 test_widgets_construct 一致：
配置目录 monkeypatch 到临时目录 —— ActiveProfile 任何变更立即落盘，
直接跑在真实 config/ 上会改写用户的方案（已经因此丢过一次数据）。
"""

import shutil

import pytest

from core import config_store as cs


@pytest.fixture(scope="session")
def qt_app():
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def 主窗口(qt_app, tmp_path, monkeypatch):
    shutil.copytree("config/profiles", tmp_path / "profiles")
    monkeypatch.setattr(cs, "_profiles_dir", lambda: str(tmp_path / "profiles"))
    monkeypatch.setattr(cs, "_app_state_path", lambda: str(tmp_path / "app_state.json"))

    from ui.main_window import MainWindow

    w = MainWindow()
    yield w
    w.close()
