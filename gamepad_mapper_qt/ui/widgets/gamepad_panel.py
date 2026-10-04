# -*- coding: utf-8 -*-
"""可视化手柄面板

按 Xbox 手柄的真实布局绘制：非对称摇杆（左摇杆左上、D-Pad 左下、
ABXY 右上、右摇杆右下），扳机与肩键在顶边。
"""

import math
import time
from typing import List

from PyQt6.QtCore import Qt, QRectF, QPointF, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QRadialGradient, QLinearGradient,
    QFont, QPainterPath,
)
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame

from ui.styles.tokens import (
    ACCENT,
    BORDER_SOFT,
    CANVAS_BG,
    CANVAS_GATED_ALPHA,
    CANVAS_IDLE_ALPHA,
    TEXT_ON_ACCENT,
    TEXT_SUB,
    THEME,
    WARN,
)
from core.joystick_manager import PollResult
from core.button_map import IDX_LT, IDX_RT
# 扇形的几何常量从 slots 引入，不在这里再写一份 ——
# 绘制与命中检测一旦漂移，画出来的和点得到的就对不上。
from core.slots import (
    SLOTS,
    RESERVED,
    binding_kind,
    conflict_reason,
    hit_test,
    FRAME_RATIO,
    _DIR_ANGLE,
    _WEDGE_INNER,
    _WEDGE_OUTER,
    _WEDGE_SPAN,
)


class GamepadCanvas(QWidget):
    """自定义绘制手柄状态；同时是绑定的编辑面 —— 点哪个键就绑哪个"""

    slot_clicked = pyqtSignal(int)       # 可绑定的槽位被点击
    slot_refused = pyqtSignal(int)       # 保留槽位被点击，附带说明

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hover: int | None = None
        self._bindings: dict = {}
        self.setMouseTracking(True)
        self._pressed: List[bool] = [False] * len(SLOTS)
        self._left_stick = (0.0, 0.0)
        self._right_stick = (0.0, 0.0)
        self._lt = 0.0
        self._rt = 0.0
        self._liveness = "idle"    # active / gated / idle
        self._selected: int | None = None
        self.setMinimumSize(420, 300)

        # 呼吸动效的驱动：只在需要时（有选中槽位 / 映射运行中）刷新重绘，
        # 空闲时彻底停掉，不为好看白烧 GPU
        self._breath_timer = QTimer(self)
        self._breath_timer.setInterval(33)
        self._breath_timer.timeout.connect(self.update)
        self._ensure_breath()

    def _ensure_breath(self) -> None:
        should_run = self._selected is not None or self._liveness in ("active", "gated")
        if should_run and not self._breath_timer.isActive():
            self._breath_timer.start()
        elif not should_run and self._breath_timer.isActive():
            self._breath_timer.stop()

    def _breath(self) -> float:
        """0..1 的呼吸相位，正弦缓动"""
        return 0.5 + 0.5 * math.sin(time.monotonic() * 2.0)

    def update_state(self, result: PollResult):
        self._pressed = list(result.pressed)
        self._left_stick = result.left_stick
        self._right_stick = result.right_stick
        self._lt = result.lt_value
        self._rt = result.rt_value
        self.update()

    def set_bindings(self, mappings: dict):
        """当前方案的绑定，用来在图上标出哪些键已经绑了"""
        if mappings != self._bindings:
            self._bindings = dict(mappings)
            self.update()

    # ---------- 交互 ----------

    def mouseMoveEvent(self, event):
        pos = event.position()
        hit = hit_test(pos.x(), pos.y(), self.width(), self.height())
        if hit != self._hover:
            self._hover = hit
            self.setCursor(Qt.CursorShape.PointingHandCursor if hit is not None
                           else Qt.CursorShape.ArrowCursor)
            self.update()

    def leaveEvent(self, _event):
        if self._hover is not None:
            self._hover = None
            self.update()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position()
        hit = hit_test(pos.x(), pos.y(), self.width(), self.height())
        if hit is None:
            return
        if binding_kind(hit) == RESERVED:
            self.slot_refused.emit(hit)
        else:
            self.slot_clicked.emit(hit)

    def set_liveness(self, state: str):
        """三态亮度：active 全亮 / gated 运行但门未对准(明显压暗) / idle 未运行(轻压暗)

        改绑发生在未运行时，所以 idle 只轻压 —— 「按了没用」主要由
        右下角状态胶囊说话；gated 才是真正该收手的信号。
        """
        if state != self._liveness:
            self._liveness = state
            self._ensure_breath()
            self.update()

    def set_selected(self, slot):
        """选中槽位（与右侧绑定面板同步）—— 画呼吸光圈"""
        if slot != self._selected:
            self._selected = slot
            self._ensure_breath()
            self.update()

    # ---------- 绘制 ----------

    @staticmethod
    def _glow(painter, cx, cy, r, color: QColor, strength=170):
        """外扩辉光，近似 bloom —— Qt 没有廉价的模糊，用径向渐变代替"""
        g = QRadialGradient(cx, cy, r)
        c = QColor(color)
        c.setAlpha(strength)
        g.setColorAt(0.0, c)
        mid = QColor(color); mid.setAlpha(int(strength * 0.35))
        g.setColorAt(0.55, mid)
        end = QColor(color); end.setAlpha(0)
        g.setColorAt(1.0, end)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(g))
        painter.drawEllipse(QPointF(cx, cy), r, r)

    def _draw_grid(self, painter, w, h):
        """背景细网格，衬科技感"""
        step = w * 0.038
        pen = QPen(QColor(255, 255, 255, 8), 1)
        painter.setPen(pen)
        x = 0.0
        while x < w:
            painter.drawLine(QPointF(x, 0), QPointF(x, h))
            x += step
        y = 0.0
        while y < h:
            painter.drawLine(QPointF(0, y), QPointF(w, y))
            y += step

    def _frame_rect(self):
        """手柄画在一个固定宽高比的内接矩形里

        否则 x 用宽度、y 用高度各自缩放，窗口一变形 ABXY 的菱形、
        D-Pad 的十字、摇杆的扇形就全被拉扁。
        """
        w, h = self.width(), self.height()
        # 留一点边距，否则握把会贴着画布底边被裁掉
        aw, ah = w * 0.96, h * 0.96
        ratio = FRAME_RATIO
        if aw / ah > ratio:
            fw = ah * ratio
            fh = ah
        else:
            fw = aw
            fh = aw / ratio
        return (w - fw) / 2, (h - fh) / 2, fw, fh

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(CANVAS_BG))
        self._draw_grid(painter, self.width(), self.height())

        ox, oy, fw, fh = self._frame_rect()
        painter.translate(ox, oy)

        self._draw_body(painter, fw, fh)
        for slot in SLOTS:
            self._draw_slot(painter, slot, fw, fh)
            self._draw_overlay(painter, slot, fw)

        painter.resetTransform()
        alpha = {"gated": CANVAS_GATED_ALPHA, "idle": CANVAS_IDLE_ALPHA}.get(
            self._liveness, 0
        )
        if alpha:
            painter.fillRect(self.rect(), QColor(11, 11, 22, alpha))
        self._draw_status_chip(painter)
        painter.end()

    def _draw_body(self, painter, w, h):
        """Xbox 手柄轮廓：中央机身 + 两侧下垂握把"""
        # 全部按宽度缩放，与槽位坐标同一套基准
        def P(x, y):
            return w * x, w * y

        def 圆(x, y, r):
            p = QPainterPath()
            p.addEllipse(QPointF(*P(x, y)), w * r, w * r)
            return p

        def 胶囊(x1, y1, x2, y2, r):
            """两端点之间的胶囊 —— 两个圆加中间的矩形"""
            p = 圆(x1, y1, r).united(圆(x2, y2, r))
            ax, ay = P(x1, y1)
            bx, by = P(x2, y2)
            dx, dy = bx - ax, by - ay
            ln = max((dx * dx + dy * dy) ** 0.5, 1e-6)
            nx, ny = -dy / ln * w * r, dx / ln * w * r
            body = QPainterPath()
            body.moveTo(ax + nx, ay + ny)
            body.lineTo(bx + nx, by + ny)
            body.lineTo(bx - nx, by - ny)
            body.lineTo(ax - nx, ay - ny)
            body.closeSubpath()
            return p.united(body)

        # 轮廓 = 中央机身 ∪ 两侧护翼 ∪ 两条斜向握把
        core = QPainterPath()
        core.addRoundedRect(QRectF(*P(0.19, 0.145), w * 0.62, w * 0.245),
                            w * 0.09, w * 0.09)
        path = core
        path = path.united(圆(0.275, 0.300, 0.182))     # 左护翼（罩住左摇杆与 D-Pad）
        path = path.united(圆(0.700, 0.300, 0.182))     # 右护翼（罩住 ABXY 与右摇杆）
        path = path.united(胶囊(0.222, 0.330, 0.150, 0.585, 0.098))   # 左握把
        path = path.united(胶囊(0.752, 0.330, 0.824, 0.585, 0.098))   # 右握把
        path = path.simplified()

        grad = QLinearGradient(0, w * 0.08, 0, w * 0.70)
        grad.setColorAt(0.0, QColor("#232342"))
        grad.setColorAt(0.5, QColor("#1a1a30"))
        grad.setColorAt(1.0, QColor("#111124"))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(path)

        # 边缘光：上沿青、下沿紫，做出体积与科技味；
        # 映射运行中随呼吸微微脉动 —— 「活着」的感觉不用看状态栏就知道
        rim = QLinearGradient(0, w * 0.08, 0, w * 0.70)
        rim.setColorAt(0.0, QColor(0, 240, 195, 255))
        rim.setColorAt(0.42, QColor(120, 140, 210, 130))
        rim.setColorAt(1.0, QColor(150, 110, 255, 235))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        # 先描一道粗而透明的做外辉光，再描一道细而实的做硬边
        pulse = 0.55 + 0.45 * self._breath() if self._liveness == "active" else 1.0
        halo = QLinearGradient(0, w * 0.08, 0, w * 0.70)
        halo.setColorAt(0.0, QColor(0, 240, 195, int(60 * pulse)))
        halo.setColorAt(1.0, QColor(150, 110, 255, int(55 * pulse)))
        painter.setPen(QPen(QBrush(halo), max(4.0, w * 0.010)))
        painter.drawPath(path)
        painter.setPen(QPen(QBrush(rim), max(1.6, w * 0.0032)))
        painter.drawPath(path)

        # 中央凹面高光，让机身有体积
        inner = QRadialGradient(w * 0.5, w * 0.30, w * 0.32)
        inner.setColorAt(0.0, QColor(255, 255, 255, 16))
        inner.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(inner))
        painter.drawPath(path)

    def _draw_slot(self, painter, slot, w, h):
        px, py, pr = slot.panel
        # x / y / 半径全部按宽度缩放：圆才是圆，菱形与十字才不走形。
        # 画框高度固定为宽度的 1/1.42，所以 py 的取值上限是 0.704。
        cx, cy, r = w * px, w * py, w * pr
        pressed = self._pressed[slot.index] if slot.index < len(self._pressed) else False
        kind = slot.render

        if self._hover == slot.index:
            hl = QColor(255, 255, 255, 40)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(hl))
            painter.drawEllipse(QPointF(cx, cy), r * 1.75, r * 1.75)

        if kind == "button":
            self._draw_round_button(painter, cx, cy, r, slot, pressed)
        elif kind == "bumper":
            self._draw_bumper(painter, cx, cy, r, slot, pressed)
        elif kind == "trigger":
            value = self._lt if slot.index == IDX_LT else self._rt
            self._draw_trigger(painter, cx, cy, r, slot, value)
        elif kind == "stick":
            offset = self._left_stick if slot.index == 10 else self._right_stick
            self._draw_stick(painter, cx, cy, r, slot, offset, pressed)
        elif kind == "stick_dir":
            self._draw_wedge(painter, cx, cy, r, slot, pressed)
        elif kind == "dpad":
            self._draw_dpad_petal(painter, cx, cy, r, slot, pressed)

    def _draw_overlay(self, painter, slot, w):
        """叠加层：选中呼吸圈、已绑定的标记、悬停高亮、保留槽位的禁用叉"""
        px, py, pr = slot.panel
        cx, cy, r = w * px, w * py, w * pr
        kind = binding_kind(slot.index)

        # 各形状的半宽/半高不同：肩键是扁矩形，用 r 同时做横纵偏移会把标记甩到外面
        hw, hh = {
            "bumper": (r, r * 0.34),
            "trigger": (r * 0.72, r * 0.62),
            "dpad": (r * 0.92, r * 0.92),
        }.get(slot.render, (r, r))

        if self._selected == slot.index and kind != RESERVED:
            breath = self._breath()
            ring = QColor(ACCENT)
            ring.setAlpha(int(130 + 110 * breath))
            self._glow(painter, cx, cy, max(hw, hh) * 2.4, ring,
                       int(36 + 36 * breath))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(ring, max(2.0, r * 0.09)))
            pad = max(hw, hh) * 0.34
            painter.drawRoundedRect(
                QRectF(cx - hw - pad, cy - hh - pad, (hw + pad) * 2, (hh + pad) * 2),
                hh + pad, hh + pad)

        if kind == RESERVED:
            # 保留槽位：斜杠，表示点了也绑不上
            painter.setPen(QPen(QColor(255, 255, 255, 70), max(1.2, r * 0.10)))
            painter.drawLine(QPointF(cx - hw * 0.5, cy + hh * 0.5),
                             QPointF(cx + hw * 0.5, cy - hh * 0.5))
        elif slot.index in self._bindings:
            # 已绑定：右上角一个实心小点
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(THEME["accent"])))
            painter.drawEllipse(QPointF(cx + hw * 0.82, cy - hh * 0.82),
                                r * 0.20, r * 0.20)

        if self._hover == slot.index:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            hl = QColor("#ff5c5c") if kind == RESERVED else QColor(255, 255, 255, 235)
            painter.setPen(QPen(hl, max(1.6, r * 0.12)))
            pad = r * 0.22
            painter.drawRoundedRect(
                QRectF(cx - hw - pad, cy - hh - pad, (hw + pad) * 2, (hh + pad) * 2),
                hh + pad, hh + pad)

    def _draw_round_button(self, painter, cx, cy, r, slot, pressed):
        color = QColor(slot.color)
        if pressed:
            self._glow(painter, cx, cy, r * 2.4, color, 150)
            grad = QRadialGradient(cx, cy - r * 0.3, r * 1.5)
            grad.setColorAt(0.0, color.lighter(190))
            grad.setColorAt(0.6, color)
            grad.setColorAt(1.0, color.darker(120))
            painter.setBrush(QBrush(grad))
            painter.setPen(QPen(QColor(255, 255, 255, 220), max(1.5, r * 0.10)))
        else:
            # 霓虹描边：暗玻璃底 + 细亮环，而不是实心暗块
            painter.setBrush(QBrush(QColor(12, 12, 26, 210)))
            ring = QColor(color); ring.setAlpha(215)
            painter.setPen(QPen(ring, max(1.2, r * 0.11)))
        painter.drawEllipse(QPointF(cx, cy), r, r)
        if not pressed:      # 内层细环，小键在霓虹风里才不寡淡
            painter.setBrush(Qt.BrushStyle.NoBrush)
            faint = QColor(color); faint.setAlpha(70)
            painter.setPen(QPen(faint, 1))
            painter.drawEllipse(QPointF(cx, cy), r * 0.66, r * 0.66)

        label = slot.name.split()[-1]
        font_px = int(r * 0.95)
        if font_px < 9:          # 放不下就不写，免得截断成「3ack」
            return
        painter.setPen(QPen(QColor("#0b0b18") if pressed else QColor(slot.color).lighter(125)))
        painter.setFont(QFont("Segoe UI", font_px, QFont.Weight.Bold))
        painter.drawText(QRectF(cx - r * 1.6, cy - r, r * 3.2, r * 2),
                         Qt.AlignmentFlag.AlignCenter, label)

    def _draw_bumper(self, painter, cx, cy, r, slot, pressed):
        color = QColor(slot.color)
        rect = QRectF(cx - r, cy - r * 0.34, r * 2, r * 0.68)
        if pressed:
            self._glow(painter, cx, cy, r * 1.9, color, 140)
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(QColor(255, 255, 255, 220), 2))
        else:
            painter.setBrush(QBrush(QColor(12, 12, 26, 210)))
            ring = QColor(color); ring.setAlpha(195)
            painter.setPen(QPen(ring, max(1.2, r * 0.055)))
        painter.drawRoundedRect(rect, r * 0.34, r * 0.34)
        painter.setPen(QPen(QColor("#0b0b18") if pressed else color.lighter(125)))
        painter.setFont(QFont("Segoe UI", max(8, int(r * 0.36)), QFont.Weight.Bold))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, slot.name)

    def _draw_trigger(self, painter, cx, cy, r, slot, value):
        color = QColor(slot.color)
        rect = QRectF(cx - r * 0.72, cy - r * 0.62, r * 1.44, r * 1.24)
        if value > 0.5:
            self._glow(painter, cx, cy, r * 1.9, color, 130)
        painter.setBrush(QBrush(QColor(12, 12, 26, 210)))
        ring = QColor(color); ring.setAlpha(150)
        painter.setPen(QPen(ring, max(1.1, r * 0.055)))
        painter.drawRoundedRect(rect, r * 0.36, r * 0.36)

        v = max(0.0, min(1.0, value))
        if v > 0.01:
            fill = QRectF(rect.left(), rect.bottom() - rect.height() * v,
                          rect.width(), rect.height() * v)
            painter.setBrush(QBrush(color if v > 0.5 else color.darker(125)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(fill, r * 0.3, r * 0.3)

        painter.setPen(QPen(QColor("#0b0b18") if v > 0.5 else color.lighter(120)))
        painter.setFont(QFont("Segoe UI", max(8, int(r * 0.40)), QFont.Weight.Bold))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, slot.name)

    def _draw_stick(self, painter, cx, cy, r, slot, offset, pressed):
        # 底座：暗井 + 双层霓虹环
        painter.setBrush(QBrush(QColor(9, 9, 20, 235)))
        painter.setPen(QPen(QColor(0, 212, 170, 90), max(1.2, r * 0.055)))
        painter.drawEllipse(QPointF(cx, cy), r, r)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(124, 92, 255, 70), 1))
        painter.drawEllipse(QPointF(cx, cy), r * 0.82, r * 0.82)

        # 摇杆帽随输入偏移
        sx = cx + offset[0] * r * 0.30
        sy = cy + offset[1] * r * 0.30
        cap = r * 0.62
        if pressed:
            self._glow(painter, sx, sy, cap * 2.6, QColor(THEME["accent"]), 165)
        grad = QRadialGradient(sx, sy - cap * 0.45, cap * 1.9)
        if pressed:
            grad.setColorAt(0.0, QColor(THEME["accent"]).lighter(165))
            grad.setColorAt(1.0, QColor(THEME["accent"]).darker(160))
        else:
            grad.setColorAt(0.0, QColor("#3d3d63"))
            grad.setColorAt(1.0, QColor("#191932"))
        painter.setBrush(QBrush(grad))
        painter.setPen(QPen(QColor(255, 255, 255, 210) if pressed
                            else QColor(0, 212, 170, 120), max(1.2, cap * 0.10)))
        painter.drawEllipse(QPointF(sx, sy), cap, cap)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(255, 255, 255, 40), 1))
        painter.drawEllipse(QPointF(sx, sy), cap * 0.55, cap * 0.55)

    def _draw_wedge(self, painter, cx, cy, r, slot, pressed):
        """摇杆四周的方向热区，扇形"""
        angle = _DIR_ANGLE[slot.name.split()[-1]]
        outer = QRectF(cx - r * _WEDGE_OUTER, cy - r * _WEDGE_OUTER,
                       r * _WEDGE_OUTER * 2, r * _WEDGE_OUTER * 2)
        inner = QRectF(cx - r * _WEDGE_INNER, cy - r * _WEDGE_INNER,
                       r * _WEDGE_INNER * 2, r * _WEDGE_INNER * 2)
        path = QPainterPath()
        path.arcMoveTo(outer, angle - _WEDGE_SPAN / 2)
        path.arcTo(outer, angle - _WEDGE_SPAN / 2, _WEDGE_SPAN)
        path.arcTo(inner, angle + _WEDGE_SPAN / 2, -_WEDGE_SPAN)
        path.closeSubpath()

        if pressed:
            acc = QColor(THEME["accent"])
            self._glow(painter, cx, cy, r * _WEDGE_OUTER * 1.35, acc, 110)
            painter.setBrush(QBrush(acc))
            painter.setPen(QPen(QColor(255, 255, 255, 200), 1))
        else:
            painter.setBrush(QBrush(QColor(0, 212, 170, 20)))
            painter.setPen(QPen(QColor(0, 212, 170, 60), 1))
        painter.drawPath(path)

    def _draw_dpad_petal(self, painter, cx, cy, r, slot, pressed):
        rect = QRectF(cx - r * 0.92, cy - r * 0.92, r * 1.84, r * 1.84)
        color = QColor(slot.color)
        if pressed:
            self._glow(painter, cx, cy, r * 2.2, color, 150)
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(QColor(255, 255, 255, 215), max(1.4, r * 0.10)))
        else:
            painter.setBrush(QBrush(QColor(12, 12, 26, 210)))
            ring = QColor(color); ring.setAlpha(150)
            painter.setPen(QPen(ring, max(1.1, r * 0.09)))
        painter.drawRoundedRect(rect, r * 0.26, r * 0.26)

        # 方向箭头
        d = slot.name.split()[-1]
        a = r * 0.34
        tri = QPainterPath()
        if d == "Up":
            tri.moveTo(cx, cy - a); tri.lineTo(cx - a, cy + a * 0.7); tri.lineTo(cx + a, cy + a * 0.7)
        elif d == "Down":
            tri.moveTo(cx, cy + a); tri.lineTo(cx - a, cy - a * 0.7); tri.lineTo(cx + a, cy - a * 0.7)
        elif d == "Left":
            tri.moveTo(cx - a, cy); tri.lineTo(cx + a * 0.7, cy - a); tri.lineTo(cx + a * 0.7, cy + a)
        else:
            tri.moveTo(cx + a, cy); tri.lineTo(cx - a * 0.7, cy - a); tri.lineTo(cx - a * 0.7, cy + a)
        tri.closeSubpath()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#0b0b18") if pressed else color.lighter(115)))
        painter.drawPath(tri)

    def _draw_status_chip(self, painter):
        """右下角状态胶囊 —— 画布自己回答「现在按手柄有没有用」"""
        text, bg, fg = {
            "active": ("映射中 · 门开", QColor(ACCENT), QColor(TEXT_ON_ACCENT)),
            "gated": ("映射中 · 门未对准", QColor(WARN), QColor(TEXT_ON_ACCENT)),
            "idle": ("已停止", QColor(BORDER_SOFT), QColor(TEXT_SUB)),
        }[self._liveness]

        font = QFont("Segoe UI", 12, QFont.Weight.Bold)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        pad_x, pad_y = 14, 7
        chip_w = metrics.horizontalAdvance(text) + pad_x * 2
        chip_h = metrics.height() + pad_y * 2
        x = self.width() - chip_w - 14
        y = self.height() - chip_h - 12

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(bg))
        painter.drawRoundedRect(QRectF(x, y, chip_w, chip_h), chip_h / 2, chip_h / 2)
        painter.setPen(QPen(fg))
        painter.drawText(QRectF(x, y, chip_w, chip_h),
                         Qt.AlignmentFlag.AlignCenter, text)


class GamepadPanel(QFrame):
    """手柄可视化面板容器"""

    slot_clicked = pyqtSignal(int)
    slot_refused = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("手柄状态")
        title.setObjectName("sectionLabel")
        layout.addWidget(title)

        self._canvas = GamepadCanvas()
        self._canvas.slot_clicked.connect(self.slot_clicked.emit)
        self._canvas.slot_refused.connect(self.slot_refused.emit)
        layout.addWidget(self._canvas, stretch=1)

        self._info = QLabel("未连接")
        self._info.setObjectName("infoLabel")
        self._info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._info)

    def set_bindings(self, mappings):
        self._canvas.set_bindings(mappings)

    def update_state(self, result: PollResult):
        self._canvas.update_state(result)

    def set_liveness(self, state: str):
        self._canvas.set_liveness(state)

    def set_selected(self, slot):
        self._canvas.set_selected(slot)

    def set_info(self, text: str, connected: bool):
        self._info.setText(text)
        color = THEME["accent"] if connected else THEME["warn"]
        self._info.setStyleSheet(f"color: {color}; font-size: 15px; font-weight: 600;")
