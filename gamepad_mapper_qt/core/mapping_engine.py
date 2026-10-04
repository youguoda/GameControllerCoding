# -*- coding: utf-8 -*-
"""映射引擎 — 消费输入帧，产生键盘/鼠标输出（闸门 / 语音 / 鼠标）"""

from typing import Callable, Dict, Optional

from PyQt6.QtCore import QObject, pyqtSignal

from core.button_map import IDX_LT, IDX_RT
from core.constants import (
    MOUSE_LEFT,
    MOUSE_MIDDLE,
    MOUSE_RIGHT,
    VOICE_KEY,
    WHEEL_DOWN,
    WHEEL_UP,
)
from core.gamepad_input import InputFrame
from core.keyboard_output import KeyboardOutput
from core.mouse_output import MouseOutput

# 引擎不处理的保留槽位：LT 归 MainWindow（聚焦/切方案），RT 恒为语音键
_RESERVED_SLOTS = (IDX_LT, IDX_RT)


class MappingEngine(QObject):
    """把 InputFrame 翻译成键盘与鼠标输出

    不再自己轮询，也不再是线程 —— 由主循环每帧调用 consume()。
    """

    state_changed = pyqtSignal(bool)
    error_occurred = pyqtSignal(str)
    gate_changed = pyqtSignal(bool, str)

    def __init__(
        self,
        keyboard: KeyboardOutput,
        mouse: MouseOutput,
        parent=None,
    ):
        super().__init__(parent)
        self._keyboard = keyboard
        self._mouse = mouse
        self._mappings: Dict[int, str] = {}
        self._active = False
        self._gate_checker: Optional[Callable[[], bool]] = None
        self._process_names: list[str] = []
        self._mouse_sensitivity = 12.0
        self._stick_deadzone = 0.15
        self._scroll_sensitivity = 1.0
        self._rt_voice_held = False
        self._last_gate_open = True
        self._last_gate_label = ""
        self._reported_actions: set[str] = set()

    def set_mappings(self, mappings: Dict[int, str]) -> None:
        self._mappings = dict(mappings)
        # 改了绑定就重新给每个动作一次上报机会
        self._reported_actions.clear()

    def release_slots(self, slots) -> None:
        """改绑前释放这些槽位正按住的输出，防止旧键卡死

        典型场景：按住 A（ctrl+enter）时把 A 改绑成别的 —— 之后的
        松开事件读的是新映射表，旧组合键永远等不到 release。
        改绑前对旧映射放一次手。运行中改绑能成立，靠的就是这个。
        """
        for slot in slots:
            try:
                self._release_slot(slot)
            except Exception as exc:
                self._report_failure(self._mappings.get(slot, f"槽位 {slot}"), exc)

    def set_gate_checker(self, checker: Optional[Callable[[], bool]]) -> None:
        self._gate_checker = checker

    def set_process_names(self, names: list[str]) -> None:
        self._process_names = list(names)

    def set_mouse_settings(
        self,
        sensitivity: float,
        deadzone: float,
        scroll_sensitivity: float,
    ) -> None:
        self._mouse_sensitivity = sensitivity
        self._stick_deadzone = deadzone
        self._scroll_sensitivity = scroll_sensitivity

    def start_mapping(self) -> None:
        if self._active:
            return
        self._active = True
        self._rt_voice_held = False
        self.state_changed.emit(True)

    def stop_mapping(self) -> None:
        self._active = False
        self._release_all_output()
        self.state_changed.emit(False)

    @property
    def is_active(self) -> bool:
        return self._active

    def _is_gate_open(self) -> bool:
        if self._gate_checker:
            return self._gate_checker()
        return True

    def _emit_gate_state(self, open_: bool) -> None:
        label = ", ".join(self._process_names[:2]) if self._process_names else "任意"
        if open_ != self._last_gate_open or label != self._last_gate_label:
            self._last_gate_open = open_
            self._last_gate_label = label
            self.gate_changed.emit(open_, label)

    def _release_rt_voice(self) -> None:
        if self._rt_voice_held:
            self._keyboard.release(VOICE_KEY)
            self._rt_voice_held = False

    def _release_all_output(self) -> None:
        """释放全部输出。这是清理动作，被 stop_mapping / closeEvent 调用 ——
        那些路径没有 try/except，所以失败必须在这里就地上报，不能往外抛。
        """
        try:
            self._release_rt_voice()
            self._keyboard.release_all()
        except Exception as exc:
            self._report_failure("释放按键", exc)
        self._mouse.left_up()
        self._mouse.right_up()

    def consume(self, frame: InputFrame) -> None:
        """处理一帧输入。由主循环调用，不自己计时。"""
        if not self._active or not frame.connected:
            return

        try:
            self._consume(frame)
        except Exception as exc:
            self.error_occurred.emit(str(exc))

    def _consume(self, frame: InputFrame) -> None:
        gate_open = self._is_gate_open()
        self._emit_gate_state(gate_open)

        if not gate_open:
            self._release_all_output()
            return

        # 逐槽位捕获：一个键发不出去，不该让同一帧的其他键跟着失效
        for slot in frame.just_pressed:
            self._try_slot(slot, self._press_slot)
        for slot in frame.just_released:
            self._try_slot(slot, self._release_slot)

        self._handle_voice(frame.rt_value)
        self._handle_mouse(frame)

    def _try_slot(self, slot: int, action_fn) -> None:
        try:
            action_fn(slot)
        except Exception as exc:
            self._report_failure(self._mappings.get(slot, f"槽位 {slot}"), exc)

    def _report_failure(self, action: str, exc: Exception) -> None:
        """同一个动作只上报一次，否则按住无效键会 60Hz 刷屏"""
        if action in self._reported_actions:
            return
        self._reported_actions.add(action)
        self.error_occurred.emit(f"按键「{action}」发送失败: {exc}")

    def _press_slot(self, slot: int) -> None:
        if slot in _RESERVED_SLOTS:
            return
        action = self._mappings.get(slot)
        if not action:
            return
        if action == MOUSE_LEFT:
            self._mouse.left_down()
        elif action == MOUSE_RIGHT:
            self._mouse.right_down()
        elif action == MOUSE_MIDDLE:
            self._mouse.middle_down()
        elif action == WHEEL_UP:
            self._mouse.wheel(1.0)      # 滚轮没有「按住」，按下滚一格
        elif action == WHEEL_DOWN:
            self._mouse.wheel(-1.0)
        else:
            self._keyboard.press(action)

    def _release_slot(self, slot: int) -> None:
        if slot in _RESERVED_SLOTS:
            return
        action = self._mappings.get(slot)
        if not action:
            return
        if action == MOUSE_LEFT:
            self._mouse.left_up()
        elif action == MOUSE_RIGHT:
            self._mouse.right_up()
        elif action == MOUSE_MIDDLE:
            self._mouse.middle_up()
        elif action in (WHEEL_UP, WHEEL_DOWN):
            return                       # 按下时已经滚过，松开无事可做
        else:
            self._keyboard.release(action)

    def _handle_voice(self, rt_value: float) -> None:
        rt_pressed = rt_value > 0.5
        if rt_pressed and not self._rt_voice_held:
            self._keyboard.press(VOICE_KEY)
            self._rt_voice_held = True
        elif not rt_pressed and self._rt_voice_held:
            self._keyboard.release(VOICE_KEY)
            self._rt_voice_held = False

    def _handle_mouse(self, frame: InputFrame) -> None:
        dz = self._stick_deadzone

        lx, ly = frame.left_stick
        if abs(lx) > dz or abs(ly) > dz:
            self._mouse.move(lx, ly, self._mouse_sensitivity)

        _, ry = frame.right_stick
        if ry < -dz:
            self._mouse.wheel(self._scroll_sensitivity)
        elif ry > dz:
            self._mouse.wheel(-self._scroll_sensitivity)

    def terminate_engine(self) -> None:
        self._active = False
        self._release_all_output()
