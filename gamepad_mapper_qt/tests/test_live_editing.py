# -*- coding: utf-8 -*-
"""窗口级的交互增强规格：运行中改绑 / 撤销 / 物理即选 / 死功能接线

qt_app / 主窗口 fixture 在 tests/conftest.py，配置目录已隔离到临时目录。
"""

import pytest


# ---------- 运行中即时改绑 ----------

def test_运行中可以改绑_不再拦截(主窗口):
    主窗口._engine.start_mapping()

    主窗口._on_bind_committed(0, "ctrl+alt+p")

    assert 主窗口._active.mappings[0] == "ctrl+alt+p"
    assert 主窗口._engine.is_active


def test_运行中改绑先释放受影响槽位(主窗口):
    released = []
    主窗口._engine.release_slots = lambda slots: released.extend(slots)

    主窗口._on_bind_committed(0, "k")

    assert 0 in released


def test_清除全部不需要先停止(主窗口, monkeypatch):
    主窗口._engine.start_mapping()
    monkeypatch.setattr(
        "ui.main_window.QMessageBox.question",
        lambda *a, **k: __import__("PyQt6.QtWidgets", fromlist=["QMessageBox"]).QMessageBox.StandardButton.Yes,
    )

    主窗口._clear_all_mappings()

    assert 主窗口._active.mappings.get(0) is None
    assert 主窗口._engine.is_active


# ---------- 撤销 ----------

def test_撤销恢复上一个绑定(主窗口):
    before = dict(主窗口._active.mappings)

    主窗口._on_bind_committed(0, "k")
    assert 主窗口._active.mappings[0] == "k"
    assert 主窗口._undo_btn.isEnabled()

    主窗口._undo_mapping_change()

    assert 主窗口._active.mappings == before
    assert not 主窗口._undo_btn.isEnabled()


def test_连续改绑逐层撤销(主窗口):
    主窗口._on_bind_committed(0, "k")
    主窗口._on_bind_committed(0, "l")

    主窗口._undo_mapping_change()
    assert 主窗口._active.mappings[0] == "k"
    主窗口._undo_mapping_change()
    assert 主窗口._active.mappings.get(0) is None or 主窗口._active.mappings[0] != "k"


def test_撤销栈不跨方案(主窗口):
    主窗口._on_bind_committed(0, "k")
    assert 主窗口._undo_btn.isEnabled()

    other = [pid for pid in 主窗口._profile_ids if pid != 主窗口._active.profile.id][0]
    主窗口._apply_profile(other)

    assert not 主窗口._undo_btn.isEnabled()


# ---------- 实体按键即点即亮 ----------

def test_物理即选_编辑态跟随(主窗口):
    主窗口._binding_panel.select_slot(0)

    主窗口._follow_physical_press(2)       # X

    assert 主窗口._binding_panel.current_slot == 2


def test_物理即选_引导态不跟随(主窗口):
    主窗口._binding_panel.select_slot(None)

    主窗口._follow_physical_press(2)

    assert 主窗口._binding_panel.current_slot is None


def test_物理即选_保留槽位不跟随(主窗口):
    主窗口._binding_panel.select_slot(0)

    主窗口._follow_physical_press(7)       # RT，保留槽位

    assert 主窗口._binding_panel.current_slot == 0


def test_物理即选_运行中不跟随(主窗口):
    主窗口._engine.start_mapping()
    主窗口._binding_panel.select_slot(0)

    主窗口._follow_physical_press(2)

    assert 主窗口._binding_panel.current_slot == 0


# ---------- 死功能接线 ----------

def test_映射启停联动窗口边框与图标(主窗口, monkeypatch):
    from ui.styles.tokens import ACCENT, ACCENT_DIM

    borders = []
    monkeypatch.setattr(
        "ui.main_window.apply_dark_frame",
        lambda w, border_color: borders.append(border_color),
    )

    主窗口._on_engine_state(True)
    主窗口._on_engine_state(False)

    assert borders == [ACCENT, ACCENT_DIM]


def test_图上已绑定角标有数据源(主窗口):
    assert 主窗口._gamepad_panel._canvas._bindings, "方案加载后画布应拿到绑定表"


def test_三态亮度接线(主窗口):
    主窗口._engine.start_mapping()
    主窗口._on_engine_state(True)
    expected = "active" if 主窗口._gate_open else "gated"
    assert 主窗口._gamepad_panel._canvas._liveness == expected

    主窗口._engine.stop_mapping()
    主窗口._on_engine_state(False)
    assert 主窗口._gamepad_panel._canvas._liveness == "idle"


def test_自动映射勾选框随连接态禁用(主窗口):
    主窗口._refresh_joystick()

    assert 主窗口._status_bar._auto_map_checkbox.isEnabled() == (
        主窗口._joystick.connected
    )
