# -*- coding: utf-8 -*-
"""程序入口

--minimized  启动后不显示窗口，直接进托盘（开机自启用这个）
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont

from ui.app_icon import make_gamepad_icon
from ui.main_window import MainWindow
from ui.win32_theme import DarkFrameFilter


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Gamepad Mapper")
    # 任务栏 / 窗口标题栏 / Alt+Tab 的图标 —— 和托盘同一枚手柄徽章
    app.setWindowIcon(make_gamepad_icon(False))
    # 系统画的标题栏/边框也跟主题色（QSS 够不到的地方）
    app.installEventFilter(DarkFrameFilter(app))
    app.setFont(QFont("Microsoft YaHei UI", 14))
    # 窗口收进托盘后不退出进程 —— 否则 hide() 会被当成最后一个窗口关闭
    app.setQuitOnLastWindowClosed(False)

    window = MainWindow()
    if "--minimized" in sys.argv:
        window.hide()
    else:
        window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
