# -*- coding: utf-8 -*-
"""设置对话框 —— 每方案调优参数（滑杆）与关于信息

滑杆不再常驻底栏：它们是「调一次用很久」的参数，收进设置后
底栏从 168px 减到 64px，画面留给手柄和绑定。

信号直连 MainWindow 的既有处理器，改动即时落盘、即时生效
（和滑杆在底栏时同一个链路）。
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QSlider, QVBoxLayout,
)

from core.constants import (
    APP_NAME,
    APP_VERSION,
    MOUSE_SENSITIVITY_MAX,
    MOUSE_SENSITIVITY_MIN,
    SCROLL_SENSITIVITY_MAX,
    SCROLL_SENSITIVITY_MIN,
)


class SettingsDialog(QDialog):
    threshold_changed = pyqtSignal(float)
    mouse_sensitivity_changed = pyqtSignal(float)
    scroll_sensitivity_changed = pyqtSignal(float)

    def __init__(
        self,
        threshold: float,
        mouse_sensitivity: float,
        scroll_sensitivity: float,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setFixedWidth(460)
        self._setup_ui(threshold, mouse_sensitivity, scroll_sensitivity)

    def _slider_row(self, label: str, value: float, lo: int, hi: int, scale: float):
        """返回 (整行布局, 滑杆, 数值标签) —— 布局必须被调用方 addLayout"""
        row = QVBoxLayout()
        row.setSpacing(4)

        caption = QHBoxLayout()
        text = QLabel(label)
        text.setObjectName("sliderLabel")
        value_label = QLabel(f"{value:.1f}")
        value_label.setObjectName("sliderValue")
        caption.addWidget(text)
        caption.addStretch()
        caption.addWidget(value_label)
        row.addLayout(caption)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(lo, hi)
        slider.setValue(int(value * scale))
        row.addWidget(slider)
        return row, slider, value_label

    def _setup_ui(self, threshold, mouse_sensitivity, scroll_sensitivity):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(14)

        title = QLabel("摇杆调优（按方案分别保存）")
        title.setObjectName("dialogTitle")
        root.addWidget(title)

        row, self._threshold_slider, self._threshold_value = self._slider_row(
            "摇杆阈值（多大偏移算触发）", threshold, 10, 90, 100.0
        )
        self._threshold_slider.valueChanged.connect(self._on_threshold)
        root.addLayout(row)

        row, self._mouse_slider, self._mouse_value = self._slider_row(
            "左摇杆鼠标灵敏度", mouse_sensitivity,
            int(MOUSE_SENSITIVITY_MIN), int(MOUSE_SENSITIVITY_MAX), 1.0,
        )
        self._mouse_slider.valueChanged.connect(self._on_mouse)
        root.addLayout(row)

        row, self._scroll_slider, self._scroll_value = self._slider_row(
            "右摇杆滚轮灵敏度", scroll_sensitivity,
            int(SCROLL_SENSITIVITY_MIN * 10), int(SCROLL_SENSITIVITY_MAX * 10), 10.0,
        )
        self._scroll_slider.valueChanged.connect(self._on_scroll)
        root.addLayout(row)

        root.addStretch()

        about = QLabel(
            f"{APP_NAME}  v{APP_VERSION}\n"
            "手柄 → 键鼠映射 · 按前台进程门控 · 统一鼠标层"
        )
        about.setObjectName("hintLabel")
        root.addWidget(about)

    def _on_threshold(self, value: int) -> None:
        thr = value / 100.0
        self._threshold_value.setText(f"{thr:.1f}")
        self.threshold_changed.emit(thr)

    def _on_mouse(self, value: int) -> None:
        self._mouse_value.setText(f"{value:.0f}")
        self.mouse_sensitivity_changed.emit(float(value))

    def _on_scroll(self, value: int) -> None:
        scroll = value / 10.0
        self._scroll_value.setText(f"{scroll:.1f}")
        self.scroll_sensitivity_changed.emit(scroll)
