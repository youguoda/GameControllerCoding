# -*- coding: utf-8 -*-
"""绑定列表

只列出**当前已绑定**的槽位（通常 9-11 行），而不是全部 24 行。
从前 24 行里超过一半是绑不了或不该绑的（LT/RT/Start 绑了不生效、
摇杆方向和鼠标层抢），要在一个半数是噪音的滚动列表里找目标。

新的绑定入口是手柄图 —— 点图上的键即可。这里是结果视图与快速清除。
勾选「显示未绑定」可以看到其余可绑槽位，主要为了摇杆方向那种图上不好点的。
"""

from typing import Dict, List

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QPushButton, QWidget,
    QHBoxLayout, QHeaderView, QAbstractItemView,
)

from ui.styles.tokens import THEME
from core.slots import SLOTS, CONFLICT, RESERVED, binding_kind, conflict_reason

_ROW_HEIGHT = 40
_BTN_HEIGHT = 28


class MappingTable(QTableWidget):
    """已绑定槽位的列表；行数随绑定变化"""

    bind_requested = pyqtSignal(int)
    row_selected = pyqtSignal(int)
    mapping_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mappings: Dict[int, str] = {}
        self._row_slots: List[int] = []      # 行号 → 槽位号，行不再等于槽位
        self._highlight_slot: int | None = None
        self._show_unbound = False
        self._setup_table()
        self._rebuild()

    def _setup_table(self):
        self.setColumnCount(3)
        self.setHorizontalHeaderLabels(["手柄键", "键盘键", "操作"])
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setShowGrid(False)

        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(0, 200)
        self.setColumnWidth(2, 176)

        self.cellDoubleClicked.connect(self._on_double_click)
        self.cellClicked.connect(self._on_row_click)

    # ---------- 行的构建 ----------

    def _visible_slots(self) -> List[int]:
        """要显示哪些槽位：默认只有已绑定的；勾选后加上其余可绑的"""
        bound = [s.index for s in SLOTS if s.index in self._mappings]
        if not self._show_unbound:
            return bound
        rest = [
            s.index for s in SLOTS
            if s.index not in self._mappings and binding_kind(s.index) != RESERVED
        ]
        return bound + rest

    def _rebuild(self):
        self._row_slots = self._visible_slots()
        self.setRowCount(len(self._row_slots))

        row_font = QFont("Segoe UI", 14)
        row_font.setWeight(QFont.Weight.DemiBold)

        for row, slot_index in enumerate(self._row_slots):
            slot = SLOTS[slot_index]
            kind = binding_kind(slot_index)
            mark = " ⚠" if kind == CONFLICT else ""

            name_item = QTableWidgetItem(f"● {slot.name}{mark}")
            name_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            name_item.setForeground(QColor(slot.color))
            name_item.setFont(row_font)
            if kind == CONFLICT:
                name_item.setToolTip(conflict_reason(slot_index))
            self.setItem(row, 0, name_item)

            key = self._mappings.get(slot_index, "")
            key_item = QTableWidgetItem(key if key else "—")
            key_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            key_item.setForeground(QColor(THEME["accent"] if key else THEME["subtext"]))
            key_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            key_item.setFont(row_font)
            self.setItem(row, 1, key_item)

            self.setCellWidget(row, 2, self._make_buttons(slot_index, bool(key)))
            self.setRowHeight(row, _ROW_HEIGHT)

        self._apply_highlight()

    def _make_buttons(self, slot_index: int, bound: bool) -> QWidget:
        holder = QWidget()
        layout = QHBoxLayout(holder)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(6)

        bind_btn = QPushButton("改绑" if bound else "绑定")
        bind_btn.setObjectName("bindBtn")
        bind_btn.setFixedHeight(_BTN_HEIGHT)
        bind_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        bind_btn.clicked.connect(lambda _, s=slot_index: self.bind_requested.emit(s))
        layout.addWidget(bind_btn)

        if bound:
            clear_btn = QPushButton("清除")
            clear_btn.setObjectName("clearBtn")
            clear_btn.setFixedHeight(_BTN_HEIGHT)
            clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            clear_btn.clicked.connect(lambda _, s=slot_index: self._clear_slot(s))
            layout.addWidget(clear_btn)
        return holder

    # ---------- 对外接口（保持槽位号语义，不是行号） ----------

    def set_show_unbound(self, show: bool):
        if show != self._show_unbound:
            self._show_unbound = show
            self._rebuild()

    def set_mapping(self, button_index: int, key_name: str):
        self._mappings[button_index] = key_name
        self._rebuild()
        self.mapping_changed.emit()

    def clear_slot(self, button_index: int):
        """清除单个槽位（面板的清除按钮走这里）"""
        if button_index in self._mappings:
            self._mappings.pop(button_index)
            self._rebuild()
            self.mapping_changed.emit()

    def select_slot(self, button_index: int):
        """面板/画布选中某槽位时，让表里对应行可见且选中"""
        if button_index in self._row_slots:
            row = self._row_slots.index(button_index)
            self.selectRow(row)
            self.scrollToItem(self.item(row, 0))

    def load_mappings(self, mappings: Dict[int, str]):
        self._mappings = dict(mappings)
        self._rebuild()

    def get_mappings(self) -> Dict[int, str]:
        return dict(self._mappings)

    def clear_all(self):
        self._mappings.clear()
        self._rebuild()
        self.mapping_changed.emit()

    def highlight_button(self, button_index: int | None):
        """按下手柄时高亮对应行；该槽位不在当前视图里就什么都不做"""
        self._highlight_slot = button_index
        self._apply_highlight()

    def clear_highlight_if(self, button_index: int):
        if self._highlight_slot == button_index:
            self.highlight_button(None)

    # ---------- 内部 ----------

    def _clear_slot(self, slot_index: int):
        self.clear_slot(slot_index)

    def _on_row_click(self, row: int, _col: int):
        if 0 <= row < len(self._row_slots):
            self.row_selected.emit(self._row_slots[row])

    def _on_double_click(self, row: int, _col: int):
        if 0 <= row < len(self._row_slots):
            self.bind_requested.emit(self._row_slots[row])

    def _apply_highlight(self):
        for row in range(self.rowCount()):
            bg = QColor(THEME["hover"]) if (
                self._highlight_slot is not None
                and row < len(self._row_slots)
                and self._row_slots[row] == self._highlight_slot
            ) else QColor(THEME["card"])
            for col in range(3):
                item = self.item(row, col)
                if item:
                    item.setBackground(bg)
