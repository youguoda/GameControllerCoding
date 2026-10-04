# -*- coding: utf-8 -*-
"""底部控制条 —— 启停映射、常用开关、状态一行带过

从前的 3 个滑杆收进了设置对话框（ui/widgets/settings_dialog.py）：
调优参数不常动，不值得常驻 100px 高度。这里只留高频操作。
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
)


class StatusBar(QFrame):
    """底部控制条"""

    start_stop_clicked = pyqtSignal()
    settings_clicked = pyqtSignal()
    launch_at_startup_changed = pyqtSignal(bool)
    auto_start_mapping_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("footerFrame")
        self.setFixedHeight(64)
        self._setup_ui()

    def _setup_ui(self):
        row = QHBoxLayout(self)
        row.setContentsMargins(24, 12, 24, 12)
        row.setSpacing(16)

        self._start_btn = QPushButton("▶  启动映射")
        self._start_btn.setObjectName("startBtn")
        self._start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._start_btn.clicked.connect(self.start_stop_clicked.emit)
        row.addWidget(self._start_btn)

        self._launch_checkbox = QCheckBox("开机自启动")
        self._launch_checkbox.setObjectName("optionCheck")
        self._launch_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self._launch_checkbox.toggled.connect(self.launch_at_startup_changed.emit)
        row.addWidget(self._launch_checkbox)

        self._auto_map_checkbox = QCheckBox("启动后自动开始映射")
        self._auto_map_checkbox.setObjectName("optionCheck")
        self._auto_map_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self._auto_map_checkbox.toggled.connect(self.auto_start_mapping_changed.emit)
        row.addWidget(self._auto_map_checkbox)

        row.addStretch()

        self._status_label = QLabel("状态: 就绪")
        self._status_label.setObjectName("statusText")
        row.addWidget(self._status_label)

        hint = QLabel("F9 切换映射")
        hint.setObjectName("hintLabel")
        row.addWidget(hint)

        settings_btn = QPushButton("⚙ 设置")
        settings_btn.setObjectName("iconBtn")
        settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_btn.setToolTip("摇杆灵敏度（按方案保存）")
        settings_btn.clicked.connect(self.settings_clicked.emit)
        row.addWidget(settings_btn)

    # ---------- 对外接口 ----------

    def set_running(self, running: bool):
        if running:
            self._start_btn.setText("■  停止映射")
            self._start_btn.setProperty("running", True)
        else:
            self._start_btn.setText("▶  启动映射")
            self._start_btn.setProperty("running", False)
        self._start_btn.style().unpolish(self._start_btn)
        self._start_btn.style().polish(self._start_btn)

    def set_status(self, text: str):
        self._status_label.setText(f"状态: {text}")

    def set_launch_at_startup(self, enabled: bool) -> None:
        self._launch_checkbox.blockSignals(True)
        self._launch_checkbox.setChecked(enabled)
        self._launch_checkbox.blockSignals(False)

    def set_auto_start_mapping(self, enabled: bool) -> None:
        self._auto_map_checkbox.blockSignals(True)
        self._auto_map_checkbox.setChecked(enabled)
        self._auto_map_checkbox.blockSignals(False)

    def set_auto_start_mapping_enabled(self, enabled: bool) -> None:
        self._auto_map_checkbox.setEnabled(enabled)
