# -*- coding: utf-8 -*-
"""按键捕获状态机的规格

引擎不持 UI，测试直接喂 QKeyEvent —— 实时捕获这条链路第一次有了
直接覆盖（此前 KeyBindDialog 的捕获逻辑零测试）。
"""

import pytest

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QApplication

from ui.widgets.key_capture import (
    KeyCaptureEngine,
    display_name_for_action,
    format_display,
)


@pytest.fixture(scope="session")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


def _press(key, text="", mods=Qt.KeyboardModifier.NoModifier):
    return QKeyEvent(QEvent.Type.KeyPress, key, mods, text)


def _release(key, text="", mods=Qt.KeyboardModifier.NoModifier):
    return QKeyEvent(QEvent.Type.KeyRelease, key, mods, text)


def test_未开启时事件一律忽略():
    engine = KeyCaptureEngine()
    assert engine.press(_press(Qt.Key.Key_X, "x")) == "ignored"


def test_普通字母捕获(qt_app):
    engine = KeyCaptureEngine()
    engine.begin()
    assert engine.press(_press(Qt.Key.Key_X, "x")) == "captured"
    assert engine.captured == "x"


def test_组合键捕获(qt_app):
    engine = KeyCaptureEngine()
    engine.begin()
    combo_event = _press(
        Qt.Key.Key_C, "c", Qt.KeyboardModifier.ControlModifier
    )
    assert engine.press(combo_event) == "captured"
    assert engine.captured == "ctrl+c"


def test_符号键绑定符号本身(qt_app):
    """Shift+9 得到 ( 时，绑 ( 而不是 shift+9"""
    engine = KeyCaptureEngine()
    engine.begin()
    event = _press(Qt.Key.Key_9, "(", Qt.KeyboardModifier.ShiftModifier)
    assert engine.press(event) == "captured"
    assert engine.captured == "("


def test_修饰键先预览松开成键(qt_app):
    engine = KeyCaptureEngine()
    engine.begin()

    assert engine.press(_press(Qt.Key.Key_Shift)) == "preview"
    assert engine.captured is None
    assert "Shift" in engine.preview_text

    assert engine.release(_release(Qt.Key.Key_Shift)) == "captured"
    assert engine.captured == "shift"


def test_end_之后复位():
    engine = KeyCaptureEngine()
    engine.begin()
    engine.press(_press(Qt.Key.Key_X, "x"))
    engine.end()
    assert engine.capturing is False
    assert engine.captured is None


def test_reset_清空捕获但保持模式():
    engine = KeyCaptureEngine()
    engine.begin()
    engine.press(_press(Qt.Key.Key_X, "x"))
    engine.reset()
    assert engine.capturing is True
    assert engine.captured is None


# ---------- 显示名 ----------

def test_format_display_组合键():
    assert format_display("ctrl+shift+tab") == "Ctrl + Shift + Tab"
    assert format_display("x") == "X"


def test_display_name_目录内动作用目录名():
    assert display_name_for_action("enter") == "Enter"
    assert display_name_for_action("page_up") == "Page Up"
    assert display_name_for_action("ctrl_l") == "左 Ctrl"
    assert display_name_for_action("space") == "空格"


def test_display_name_鼠标哨兵不露内部值():
    assert display_name_for_action("@mouse:left") == "鼠标左键"
    assert display_name_for_action("@wheel:up") == "滚轮上滚"


def test_display_name_目录外的组合键走格式化():
    assert display_name_for_action("ctrl+alt+p") == "Ctrl + Alt + P"
