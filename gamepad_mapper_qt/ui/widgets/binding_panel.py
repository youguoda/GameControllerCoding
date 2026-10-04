# -*- coding: utf-8 -*-
"""绑定面板 —— 选中槽位后就地编辑，替代旧的全屏模态弹窗

三态提示的主展示位也在这里：可绑定 / 冲突（能绑但有代价）/ 保留
（点不开绑，说明被什么占用）。状态栏不再承担解释职责。
"""

from typing import Dict, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QStackedWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from core.slots import CONFLICT, FREE, RESERVED, SLOTS, binding_kind, conflict_reason
from ui.widgets.key_capture import (
    KeyCaptureEngine,
    display_name_for_action,
)
from ui.widgets.key_catalog import CATALOG


def _repolish(widget: QWidget) -> None:
    """动态属性（tone/empty）改过后让 QSS 重新生效"""
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class BindingPanel(QFrame):
    """上下文绑定编辑器

    信号：
      bind_committed(slot, combo) —— 确认绑定
      bind_cleared(slot)          —— 清除该槽位
    MainWindow 负责落到 ActiveProfile / 引擎；面板自己不碰配置。
    """

    bind_committed = pyqtSignal(int, str)
    bind_cleared = pyqtSignal(int)
    selection_changed = pyqtSignal(object)   # int 槽位或 None，画布/列表跟着同步

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("panelFrame")
        self.setMinimumHeight(340)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._slot: Optional[int] = None
        self._mappings: Dict[int, str] = {}
        self._live_hint = False
        self._capture = KeyCaptureEngine()

        self._setup_ui()
        self._show_guide()

    # ---------- UI ----------

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(10)

        self._pages = QStackedWidget(self)
        root.addWidget(self._pages, stretch=1)
        self._pages.addWidget(self._build_guide_page())
        self._pages.addWidget(self._build_editor_page())

    def _build_guide_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 24, 4, 24)
        layout.setSpacing(12)

        title = QLabel("按键绑定")
        title.setObjectName("sectionLabel")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(title)

        hint = QLabel("点左边手柄图上的按键开始绑定\n或点下方列表里的「绑定」")
        hint.setObjectName("hintLabel")
        hint.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(hint)
        layout.addStretch()
        return page

    def _build_editor_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(10)
        self._slot_name = QLabel()
        self._slot_name.setObjectName("panelSlotName")
        header.addWidget(self._slot_name)
        self._badge = QLabel()
        self._badge.setObjectName("slotBadge")
        header.addWidget(self._badge)
        header.addStretch()
        layout.addLayout(header)

        self._banner = QFrame()
        self._banner.setObjectName("warnBanner")
        banner_layout = QHBoxLayout(self._banner)
        banner_layout.setContentsMargins(10, 6, 10, 6)
        self._banner_text = QLabel()
        self._banner_text.setObjectName("warnBannerText")
        self._banner_text.setWordWrap(True)
        banner_layout.addWidget(self._banner_text)
        layout.addWidget(self._banner)

        key_row = QHBoxLayout()
        key_row.setSpacing(10)
        self._key_display = QLabel("未绑定")
        self._key_display.setObjectName("currentKey")
        self._key_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        key_row.addWidget(self._key_display, stretch=1)

        self._clear_btn = QPushButton("清除")
        self._clear_btn.setObjectName("clearBtn")
        self._clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_btn.clicked.connect(self._on_clear)
        key_row.addWidget(self._clear_btn)
        layout.addLayout(key_row)

        self._search = QLineEdit()
        self._search.setPlaceholderText("搜索动作，如 复制 / ctrl / F5 / 滚轮")
        self._search.setObjectName("searchBox")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._filter_tree)
        layout.addWidget(self._search)

        self._tree = QTreeWidget()
        self._tree.setObjectName("catalogTree")
        self._tree.setHeaderHidden(True)
        self._tree.setMinimumHeight(120)
        self._build_tree()
        self._tree.itemSelectionChanged.connect(self._on_tree_selection)
        layout.addWidget(self._tree, stretch=1)

        bottom = QHBoxLayout()
        bottom.setSpacing(10)
        self._capture_btn = QPushButton("⌨  直接按键捕获")
        self._capture_btn.setObjectName("ghostBtn")
        self._capture_btn.setCheckable(True)
        self._capture_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._capture_btn.toggled.connect(self._on_capture_toggled)
        bottom.addWidget(self._capture_btn)
        bottom.addStretch()

        collapse_btn = QPushButton("收起")
        collapse_btn.setObjectName("dialogBtn")
        collapse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        collapse_btn.clicked.connect(lambda: self.select_slot(None))
        bottom.addWidget(collapse_btn)

        self._confirm_btn = QPushButton("确认")
        self._confirm_btn.setObjectName("dialogBtnPrimary")
        self._confirm_btn.setEnabled(False)
        self._confirm_btn.clicked.connect(self._on_confirm)
        bottom.addWidget(self._confirm_btn)
        layout.addLayout(bottom)
        return page

    def _build_tree(self) -> None:
        for category, entries in CATALOG:
            branch = QTreeWidgetItem(self._tree, [category])
            branch.setFlags(Qt.ItemFlag.ItemIsEnabled)      # 分类本身不可选中
            for label, value in entries:
                child = QTreeWidgetItem(branch, [label])
                child.setData(0, Qt.ItemDataRole.UserRole, value)
        self._tree.expandItem(self._tree.topLevelItem(0))

    # ---------- 对外接口 ----------

    def select_slot(self, slot) -> None:
        """选中一个槽位进入编辑；None 回到引导页"""
        self._slot = slot
        self._capture.end()
        self._capture_btn.blockSignals(True)
        self._capture_btn.setChecked(False)
        self._capture_btn.blockSignals(False)
        self._search.clear()
        if slot is None:
            self._show_guide()
        else:
            self._pages.setCurrentIndex(1)
            self._refresh_slot_view()
        self.selection_changed.emit(slot)

    def set_mappings(self, mappings: Dict[int, str]) -> None:
        """当前方案的绑定，用来显示选中槽位的现值"""
        self._mappings = dict(mappings)
        if self._slot is not None:
            self._refresh_slot_view()

    def set_live_hint(self, on: bool) -> None:
        """映射运行中时提示「改动即时生效」"""
        if on != self._live_hint:
            self._live_hint = on
            self._refresh_slot_view()

    @property
    def current_slot(self) -> Optional[int]:
        return self._slot

    # ---------- 键盘事件（转给捕获引擎） ----------

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            if self._capture.capturing:
                self._on_capture_toggled(False)
                self._capture_btn.setChecked(False)
            else:
                self.select_slot(None)
            return
        outcome = self._capture.press(event)
        if outcome == "ignored":
            super().keyPressEvent(event)
            return
        self._refresh_key_display()
        self._confirm_btn.setEnabled(self._capture.captured is not None)

    def keyReleaseEvent(self, event):
        outcome = self._capture.release(event)
        if outcome == "ignored":
            super().keyReleaseEvent(event)
            return
        self._refresh_key_display()
        self._confirm_btn.setEnabled(self._capture.captured is not None)

    # ---------- 内部刷新 ----------

    def _show_guide(self) -> None:
        self._pages.setCurrentIndex(0)

    def _refresh_slot_view(self) -> None:
        if self._slot is None:
            return
        slot = SLOTS[self._slot]
        kind = binding_kind(self._slot)
        self._slot_name.setText(slot.name)

        badge = {
            FREE: ("可绑定", "ok"),
            CONFLICT: ("⚠ 有冲突", "warn"),
            RESERVED: ("已占用", "mute"),
        }[kind]
        self._set_badge(*badge)

        editable = kind != RESERVED
        for w in (self._search, self._tree, self._capture_btn):
            w.setEnabled(editable)
        self._confirm_btn.setEnabled(False)
        self._clear_btn.setEnabled(
            editable and self._slot in self._mappings
        )

        self._refresh_banner(kind)
        self._refresh_key_display()

    def _refresh_banner(self, kind: str) -> None:
        if kind == RESERVED:
            self._set_banner(conflict_reason(self._slot), "warn")
        elif kind == CONFLICT:
            self._set_banner(f"注意：{conflict_reason(self._slot)}", "warn")
        elif self._live_hint:
            self._set_banner("映射运行中 —— 现在改绑会即时生效", "info")
        else:
            self._set_banner(None)

    def _refresh_key_display(self) -> None:
        if self._capture.captured:
            self._key_display.setText(display_name_for_action(self._capture.captured))
            self._key_display.setProperty("empty", "false")
        elif self._capture.capturing:
            self._key_display.setText("按下你想绑定的键…")
            self._key_display.setProperty("empty", "false")
        else:
            current = self._mappings.get(self._slot) if self._slot is not None else None
            self._key_display.setText(
                display_name_for_action(current) if current else "未绑定"
            )
            self._key_display.setProperty("empty", "true" if not current else "false")
        _repolish(self._key_display)

    def _set_badge(self, text: str, tone: str) -> None:
        self._badge.setText(text)
        self._badge.setProperty("tone", tone)
        _repolish(self._badge)

    def _set_banner(self, text: Optional[str], tone: str = "warn") -> None:
        if text is None:
            self._banner.hide()
            return
        self._banner_text.setText(text)
        self._banner.setProperty("tone", tone)
        _repolish(self._banner)
        self._banner.show()

    # ---------- 交互 ----------

    def _on_capture_toggled(self, on: bool) -> None:
        """捕获与浏览列表抢键盘焦点，必须显式切换（老约束）"""
        if on:
            self._tree.clearSelection()
            self._capture.begin()
            self.setFocus()
        else:
            self._capture.end()
        self._refresh_key_display()
        self._confirm_btn.setEnabled(self._capture.captured is not None)

    def _on_tree_selection(self) -> None:
        items = self._tree.selectedItems()
        if not items:
            return
        value = items[0].data(0, Qt.ItemDataRole.UserRole)
        if not value:
            return
        # 从列表挑了键就退出捕获模式，两条路别同时抢焦点
        if self._capture.capturing:
            self._on_capture_toggled(False)
            self._capture_btn.setChecked(False)
        self._capture.captured = value
        self._refresh_key_display()
        self._confirm_btn.setEnabled(True)

    def _filter_tree(self, keyword: str) -> None:
        word = keyword.strip().lower()
        for i in range(self._tree.topLevelItemCount()):
            branch = self._tree.topLevelItem(i)
            hits = 0
            for j in range(branch.childCount()):
                child = branch.child(j)
                value = child.data(0, Qt.ItemDataRole.UserRole) or ""
                matched = not word or word in child.text(0).lower() or word in value.lower()
                child.setHidden(not matched)
                hits += int(matched)
            branch.setHidden(hits == 0)
            if word:
                branch.setExpanded(hits > 0)

    def _on_confirm(self) -> None:
        if self._slot is None or not self._capture.captured:
            return
        if binding_kind(self._slot) == RESERVED:
            return
        combo = self._capture.captured
        self.bind_committed.emit(self._slot, combo)
        # 停在当前槽位展示新绑定，连续调整多个键时不用重新点
        self._capture.reset()
        self._refresh_slot_view()

    def _on_clear(self) -> None:
        if self._slot is None:
            return
        if binding_kind(self._slot) == RESERVED:
            return
        self.bind_cleared.emit(self._slot)
        self._capture.reset()
        self._refresh_slot_view()
