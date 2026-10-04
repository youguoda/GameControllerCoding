# -*- coding: utf-8 -*-
"""顶栏状态胶囊 —— 连接状态与门控状态的小容器

替代从前「圆点 + 文字」的裸组合：胶囊底色随状态变色，
一眼分得出「好的绿色、要紧的橙色、无关的灰色」。
"""

from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel

from ui.styles.tokens import ACCENT, TEXT_DIM, WARN


_TONE_DOT_COLOR = {
    "ok": ACCENT,
    "warn": WARN,
    "off": TEXT_DIM,
}


class StatusPill(QFrame):
    def __init__(self, text: str = "…", tone: str = "off", parent=None):
        super().__init__(parent)
        self.setObjectName("pillFrame")
        self._tone = tone

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 5, 12, 5)
        layout.setSpacing(7)

        self._dot = QLabel("●")
        self._dot.setObjectName("pillDot")
        layout.addWidget(self._dot)

        self._text = QLabel(text)
        self._text.setObjectName("pillText")
        layout.addWidget(self._text)

        self.set_state(text, tone)

    def set_state(self, text: str, tone: str) -> None:
        if text != self._text.text() or tone != self._tone:
            self._tone = tone
            self._text.setText(text)
            self._dot.setStyleSheet(f"color: {_TONE_DOT_COLOR.get(tone, TEXT_DIM)};")
            self.setProperty("tone", tone)
            self.style().unpolish(self)
            self.style().polish(self)
