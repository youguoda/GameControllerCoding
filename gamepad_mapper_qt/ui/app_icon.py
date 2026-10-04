# -*- coding: utf-8 -*-
"""应用图标 —— 代码绘制的手柄徽章，托盘与顶栏 logo 共用

保持零图片资源：画出来的是同一个形状，跑在托盘和窗口标题旁才不会
出现两个不像同一个应用的手柄。
"""

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QIcon, QPainter, QPixmap, QPen

from ui.styles.tokens import ACCENT, SURFACE, TEXT_DIM

_ICON_RUNNING = QColor(ACCENT)
_ICON_IDLE = QColor(TEXT_DIM)


def make_gamepad_pixmap(running: bool, size: int = 64) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    try:
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        s = size / 64.0
        body = QColor(_ICON_RUNNING) if running else QColor(_ICON_IDLE)
        p.setBrush(QBrush(body))
        p.setPen(QPen(QColor(0, 0, 0, 90), 2 * s))
        # 机身
        p.drawRoundedRect(QRectF(8 * s, 20 * s, 48 * s, 26 * s), 12 * s, 12 * s)
        # 两侧握把
        p.drawEllipse(QRectF(6 * s, 28 * s, 22 * s, 26 * s))
        p.drawEllipse(QRectF(36 * s, 28 * s, 22 * s, 26 * s))
        # 中间挖空一点，让轮廓在小尺寸下能分辨
        p.setBrush(QBrush(QColor(SURFACE)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(20 * s, 30 * s, 10 * s, 10 * s))
        p.drawEllipse(QRectF(34 * s, 30 * s, 10 * s, 10 * s))
    finally:
        # 中途抛异常时也必须收笔，否则 pixmap 被 GC 时
        # Qt 会报「Cannot destroy paint device that is being painted」并直接中止
        p.end()
    return pm


def make_gamepad_icon(running: bool, size: int = 64) -> QIcon:
    return QIcon(make_gamepad_pixmap(running, size))
