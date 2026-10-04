# -*- coding: utf-8 -*-
"""系统托盘

隐藏启动必须配托盘 —— 否则窗口一藏就再也叫不回来，
只能去任务管理器杀进程。
"""

from PyQt6.QtCore import pyqtSignal, QObject
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon

from core.constants import APP_NAME
from ui.app_icon import make_gamepad_icon


class Tray(QObject):
    """托盘图标与右键菜单

    只发信号，不直接操作窗口 —— 让 MainWindow 决定怎么响应。
    """

    show_requested = pyqtSignal()
    toggle_mapping_requested = pyqtSignal()
    quit_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._icon = QSystemTrayIcon(make_gamepad_icon(False), parent)
        self._icon.setToolTip(APP_NAME)

        menu = QMenu()
        show_action = QAction("显示主窗口", menu)
        show_action.triggered.connect(self.show_requested)
        menu.addAction(show_action)

        self._toggle_action = QAction("启动映射", menu)
        self._toggle_action.triggered.connect(self.toggle_mapping_requested)
        menu.addAction(self._toggle_action)

        menu.addSeparator()
        quit_action = QAction("退出", menu)
        quit_action.triggered.connect(self.quit_requested)
        menu.addAction(quit_action)

        self._icon.setContextMenu(menu)
        self._icon.activated.connect(self._on_activated)
        self._menu = menu

    def _on_activated(self, reason):
        if reason in (
            QSystemTrayIcon.ActivationReason.DoubleClick,
            QSystemTrayIcon.ActivationReason.Trigger,
        ):
            self.show_requested.emit()

    def show(self):
        self._icon.show()

    def hide(self):
        self._icon.hide()

    def set_running(self, running: bool):
        """映射启停时更新图标与菜单文字"""
        self._icon.setIcon(make_gamepad_icon(running))
        self._toggle_action.setText("停止映射" if running else "启动映射")
        self._icon.setToolTip(f"{APP_NAME} — {'映射中' if running else '已停止'}")

    def notify(self, message: str):
        if self._icon.supportsMessages():
            self._icon.showMessage(APP_NAME, message, make_gamepad_icon(False), 3000)
