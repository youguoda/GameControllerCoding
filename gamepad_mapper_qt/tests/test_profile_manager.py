# -*- coding: utf-8 -*-
"""方案管理的规格：新建 / 重命名 / 门控进程编辑 / 删除

走 MainWindow.ui_* 窄接口（与 ProfileManagerDialog 同一路径），
断言落盘效果 —— 配置目录已由 conftest 隔离到临时目录。
"""

import os

from core import config_store as cs


def _disk_profile(profile_id: str):
    return cs.load_profile(profile_id)


# ---------- 新建 ----------

def test_新建方案_写盘并进入下拉(主窗口):
    ok, err = 主窗口.ui_create_profile("my_game", "我的游戏")

    assert ok, err
    assert "my_game" in 主窗口._profile_ids
    assert os.path.isfile(os.path.join(cs._profiles_dir(), "my_game.json"))
    texts = [主窗口._profile_combo.itemText(i) for i in range(主窗口._profile_combo.count())]
    assert "我的游戏" in texts


def test_新建方案_拒绝空标识(主窗口):
    ok, err = 主窗口.ui_create_profile("  ", "x")
    assert not ok
    assert "标识" in err


def test_新建方案_拒绝非法字符(主窗口):
    ok, err = 主窗口.ui_create_profile("bad name!", "x")
    assert not ok
    assert "标识" in err


def test_新建方案_拒绝重复(主窗口):
    ok, err = 主窗口.ui_create_profile("cursor", "x")
    assert not ok
    assert "已存在" in err


# ---------- 重命名 ----------

def test_重命名当前方案_走_ActiveProfile_并落盘(主窗口):
    current = 主窗口._active.profile.id

    ok, err = 主窗口.ui_rename_profile(current, "新名字")

    assert ok, err
    assert 主窗口._profile_combo.currentText() == "新名字"
    assert _disk_profile(current).display_name == "新名字"


def test_重命名拒绝空名(主窗口):
    ok, err = 主窗口.ui_rename_profile("cursor", "  ")
    assert not ok
    assert "显示名" in err


# ---------- 门控进程 ----------

def test_编辑当前方案门控_引擎与磁盘同步(主窗口):
    current = 主窗口._active.profile.id

    ok, err = 主窗口.ui_set_profile_processes(current, [" Foo.exe ", "", "bar.exe"])

    assert ok, err
    assert 主窗口._engine._process_names == ["Foo.exe", "bar.exe"]
    assert _disk_profile(current).process_names == ["Foo.exe", "bar.exe"]


def test_编辑非当前方案门控_只落盘(主窗口):
    other = next(p for p in 主窗口._profile_ids if p != 主窗口._active.profile.id)
    before = list(主窗口._engine._process_names)

    ok, err = 主窗口.ui_set_profile_processes(other, ["Other.exe"])

    assert ok, err
    assert _disk_profile(other).process_names == ["Other.exe"]
    assert 主窗口._engine._process_names == before, "不该影响当前引擎"


def test_下拉框tooltip_显示门控目标(主窗口):
    combo = 主窗口._profile_combo
    tooltips = [
        combo.itemData(i, __import__("PyQt6.QtCore", fromlist=["Qt"]).Qt.ItemDataRole.ToolTipRole)
        for i in range(combo.count())
    ]
    assert all(t and t.startswith("门控:") for t in tooltips)


# ---------- 删除 ----------

def test_删除非当前方案(主窗口):
    other = next(p for p in 主窗口._profile_ids if p != 主窗口._active.profile.id)

    ok, err = 主窗口.ui_delete_profile(other)

    assert ok, err
    assert other not in 主窗口._profile_ids
    assert not os.path.isfile(os.path.join(cs._profiles_dir(), f"{other}.json"))


def test_删除当前方案_先切换再删(主窗口):
    current = 主窗口._active.profile.id

    ok, err = 主窗口.ui_delete_profile(current)

    assert ok, err
    assert 主窗口._active.profile.id != current
    assert current not in 主窗口._profile_ids


def test_至少保留一个方案(主窗口, monkeypatch):
    only = 主窗口._active.profile.id
    monkeypatch.setattr(主窗口, "_profile_ids", [only])

    ok, err = 主窗口.ui_delete_profile(only)

    assert not ok
    assert "至少" in err


# ---------- 概览 ----------

def test_ui_profile_brief_字段齐全(主窗口):
    briefs = 主窗口.ui_profile_brief()

    assert briefs, "默认方案一个不少"
    for pid, display, processes, bound, is_active in briefs:
        assert isinstance(pid, str) and pid
        assert isinstance(display, str)
        assert isinstance(processes, list)
        assert isinstance(bound, int)
        assert isinstance(is_active, bool)
    assert sum(1 for b in briefs if b[4]) == 1, "有且只有一个是当前方案"
