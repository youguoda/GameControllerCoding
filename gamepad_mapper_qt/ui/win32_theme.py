# -*- coding: utf-8 -*-
"""Windows 深色标题栏与主题色窗口边框

QSS 只画得到客户区 —— 系统绘制的标题栏和窗口边框在深色应用上
会突兀地保持白色。通过 DwmSetWindowAttribute 修正：

- Win10 1809+：DWMWA_USE_IMMERSIVE_DARK_MODE 整体切深色标题栏
- Win11 22000+：还能把标题栏底色 / 标题文字 / 边框线刷成主题色

所有调用失败都静默跳过 —— 老系统上顶多维持系统默认外观，不能崩。
"""

import ctypes
import sys

from PyQt6.QtCore import QEvent, QObject

from ui.styles.tokens import ACCENT_DIM, SURFACE, TEXT

_DWMWA_USE_IMMERSIVE_DARK_MODE = 20
# 34/35/36 只在 Win11 22000+ 生效，传给更老的系统只会返回错误码，无副作用
_DWMWA_BORDER_COLOR = 34
_DWMWA_CAPTION_COLOR = 35
_DWMWA_TEXT_COLOR = 36


def _colorref(hex_color: str) -> int:
    """#RRGGBB → COLORREF（Windows 的 0x00BBGGRR，字节序是反的）"""
    value = hex_color.lstrip("#")
    red, green, blue = (int(value[i:i + 2], 16) for i in (0, 2, 4))
    return red | (green << 8) | (blue << 16)


def apply_dark_frame(widget, border_color: str = ACCENT_DIM) -> None:
    """把一个顶层窗口的标题栏/边框刷成主题色"""
    if sys.platform != "win32":
        return
    try:
        dwm = ctypes.windll.dwmapi
        hwnd = int(widget.winId())

        enabled = ctypes.c_int(1)
        for attr in (_DWMWA_USE_IMMERSIVE_DARK_MODE, 19):
            # 20 是现代值，部分老 Win10 只认 19；返回 0 表示该属性被接受
            if dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(enabled), 4) == 0:
                break

        for attr, color in (
            (_DWMWA_CAPTION_COLOR, SURFACE),
            (_DWMWA_TEXT_COLOR, TEXT),
            (_DWMWA_BORDER_COLOR, border_color),
        ):
            value = ctypes.c_int(_colorref(color))
            dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(value), 4)
    except Exception:
        pass


class DarkFrameFilter(QObject):
    """给每个顶层窗口应用深色标题栏 —— 包括 QMessageBox 这类临时对话框

    装在 QApplication 上，Show 事件时刷一遍；重复 Show（隐藏再显示）
    重复刷也无害，DWM 调用是幂等的。
    """

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.Type.Show:
            try:
                is_window = getattr(obj, "isWindow", None)
                if callable(is_window) and is_window():
                    apply_dark_frame(obj)
            except Exception:
                pass
        return False
