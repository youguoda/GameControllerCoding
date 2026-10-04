# -*- coding: utf-8 -*-
"""绑定面板的行为规格

覆盖点：三态提示落到面板横幅、保留槽位禁编辑、目录选键确认落信号、
清除落信号、运行中提示条。
"""

import pytest

from PyQt6.QtWidgets import QApplication

from core.slots import SLOTS


@pytest.fixture(scope="session")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def panel(qt_app):
    from ui.widgets.binding_panel import BindingPanel

    p = BindingPanel()
    yield p


def _tree_item(panel, prefix: str):
    tree = panel._tree
    for i in range(tree.topLevelItemCount()):
        branch = tree.topLevelItem(i)
        for j in range(branch.childCount()):
            child = branch.child(j)
            if child.text(0).startswith(prefix):
                return child
    raise AssertionError(f"目录里找不到 {prefix}")


def test_默认是引导页(panel):
    assert panel.current_slot is None
    assert panel._pages.currentIndex() == 0


def test_选中保留槽位禁止编辑并说明原因(panel):
    panel.select_slot(6)      # LT

    assert panel._confirm_btn.isEnabled() is False
    assert panel._clear_btn.isEnabled() is False
    assert not panel._search.isEnabled()
    assert "LT" in panel._banner_text.text()
    assert not panel._banner.isHidden()


def test_选中冲突槽位可编辑但提示注意(panel):
    panel.select_slot(10)     # L3，统一鼠标层

    assert panel._search.isEnabled()
    assert "注意" in panel._banner_text.text()
    assert panel._confirm_btn.isEnabled() is False   # 还没选键


def test_空闲可选槽位不挂横幅(panel):
    panel.select_slot(0)      # A，自由
    assert panel._banner.isHidden()


def test_目录选键后确认发信号(qt_app, panel):
    committed = []
    panel.bind_committed.connect(lambda s, k: committed.append((s, k)))

    panel.select_slot(0)
    panel._tree.setCurrentItem(_tree_item(panel, "复制"))

    assert panel._confirm_btn.isEnabled()
    panel._on_confirm()

    assert committed == [(0, "ctrl+c")]
    # 确认后面板停在原槽位、展示新绑定，方便连续调整多个键
    assert panel.current_slot == 0
    assert panel._confirm_btn.isEnabled() is False   # 捕获已复位


def test_清除发信号(qt_app, panel):
    cleared = []
    panel.bind_cleared.connect(lambda s: cleared.append(s))

    panel.set_mappings({0: "y"})
    panel.select_slot(0)
    assert panel._clear_btn.isEnabled()

    panel._on_clear()

    assert cleared == [0]


def test_选中槽位显示现值(qt_app, panel):
    panel.set_mappings({2: "ctrl+shift+tab"})
    panel.select_slot(2)
    assert "Ctrl + Shift + Tab" in panel._key_display.text()


def test_运行中提示即时生效(qt_app, panel):
    panel.select_slot(0)
    panel.set_live_hint(True)
    assert "即时生效" in panel._banner_text.text()

    panel.set_live_hint(False)
    assert panel._banner.isHidden()
