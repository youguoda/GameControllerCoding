# -*- coding: utf-8 -*-
"""键盘捕获 —— 组合键与左右修饰键判定

从旧 KeyBindDialog 原样抽出：绑定面板（以及将来任何宿主）把
QKeyEvent 转给 KeyCaptureEngine，拿到「捕获到了/预览中/不归我管」。

老约束一并带过来：实时捕获与目录浏览都要键盘焦点，必须显式切换，
否则在搜索框里打字会被当成要绑的键。
"""

import sys

from PyQt6.QtCore import Qt

# Qt key → pynput-style name
QT_KEY_MAP = {
    Qt.Key.Key_Space: "space",
    Qt.Key.Key_Return: "enter",
    Qt.Key.Key_Enter: "enter",
    Qt.Key.Key_Tab: "tab",
    Qt.Key.Key_Backspace: "backspace",
    Qt.Key.Key_Delete: "delete",
    Qt.Key.Key_Left: "left",
    Qt.Key.Key_Right: "right",
    Qt.Key.Key_Up: "up",
    Qt.Key.Key_Down: "down",
    Qt.Key.Key_F1: "f1", Qt.Key.Key_F2: "f2", Qt.Key.Key_F3: "f3",
    Qt.Key.Key_F4: "f4", Qt.Key.Key_F5: "f5", Qt.Key.Key_F6: "f6",
    Qt.Key.Key_F7: "f7", Qt.Key.Key_F8: "f8", Qt.Key.Key_F9: "f9",
    Qt.Key.Key_F10: "f10", Qt.Key.Key_F11: "f11", Qt.Key.Key_F12: "f12",
    Qt.Key.Key_BracketLeft: "[",
    Qt.Key.Key_BracketRight: "]",
    Qt.Key.Key_Semicolon: ";",
    Qt.Key.Key_Apostrophe: "'",
    Qt.Key.Key_Comma: ",",
    Qt.Key.Key_Period: ".",
    Qt.Key.Key_Slash: "/",
    Qt.Key.Key_Backslash: "\\",
    Qt.Key.Key_Minus: "-",
    Qt.Key.Key_Equal: "=",
    Qt.Key.Key_QuoteLeft: "`",
}

MODIFIER_KEYS = {
    Qt.Key.Key_Shift: "shift",
    Qt.Key.Key_Control: "ctrl",
    Qt.Key.Key_Alt: "alt",
    Qt.Key.Key_Meta: "cmd",
    Qt.Key.Key_Super_L: "cmd",
    Qt.Key.Key_Super_R: "cmd_r",
}

WIN_KEYS = (Qt.Key.Key_Meta, Qt.Key.Key_Super_L, Qt.Key.Key_Super_R)

# Windows virtual-key codes for left/right modifiers
WIN_VK_TO_MOD = {
    0x5B: "cmd_l",
    0x5C: "cmd_r",
    0xA2: "ctrl_l",
    0xA3: "ctrl_r",
    0xA0: "shift_l",
    0xA1: "shift_r",
    0xA4: "alt_l",
    0xA5: "alt_r",
}

# Windows scan codes (extended keys) — fallback when VK is generic
WIN_SCAN_TO_MOD = {
    29: "ctrl_l",
    285: "ctrl_r",
    42: "shift_l",
    54: "shift_r",
    56: "alt_l",
    312: "alt_r",
}

MODIFIER_ORDER = (
    "cmd_l", "cmd_r", "cmd", "win", "super",
    "ctrl_l", "ctrl_r", "ctrl",
    "shift_l", "shift_r", "shift",
    "alt_l", "alt_r", "alt",
)

DISPLAY_NAMES = {
    "cmd_l": "Win",
    "cmd_r": "Right Win",
    "cmd": "Win",
    "win": "Win",
    "super": "Win",
    "ctrl_l": "Left Ctrl",
    "ctrl_r": "Right Ctrl",
    "shift_l": "Left Shift",
    "shift_r": "Right Shift",
    "alt_l": "Left Alt",
    "alt_r": "Right Alt",
    "ctrl": "Ctrl",
    "shift": "Shift",
    "alt": "Alt",
}

# 多字符普通键的标题化写法 —— 不在目录里、捕获得到的组合键用
KEY_TITLE_NAMES = {
    "tab": "Tab",
    "escape": "Esc",
    "enter": "Enter",
    "home": "Home",
    "end": "End",
    "backspace": "Backspace",
    "delete": "Delete",
    "space": "Space",
    "page_up": "Page Up",
    "page_down": "Page Down",
    "insert": "Insert",
}


def format_display(combo: str) -> str:
    """pynput 组合键 → 人类可读（ctrl+shift+tab → Ctrl + Shift + Tab）"""
    def fmt(part: str) -> str:
        if part in DISPLAY_NAMES:
            return DISPLAY_NAMES[part]
        if part in ("cmd", "win", "super", "cmd_l", "cmd_r"):
            return "Win"
        if part in KEY_TITLE_NAMES:
            return KEY_TITLE_NAMES[part]
        return part.upper() if len(part) == 1 else part

    return " + ".join(fmt(part) for part in combo.split("+"))


def display_name_for_action(value: str) -> str:
    """绑定值 → 人类可读名

    目录里有的动作直接用目录的显示名（enter → Esc 左边的「Enter」、
    ctrl_l → 「左 Ctrl」），别把内部值原样摆给用户看。
    目录里没有的（实时捕获到的组合键）走 format_display。
    """
    from ui.widgets.key_catalog import CATALOG

    for _, entries in CATALOG:
        for label, action in entries:
            if action == value:
                if value.startswith("@") or "  " not in label:
                    return label
                # 「复制  Ctrl+C」这类双空格分隔的标签，右侧就是短名
                return label.split("  ", 1)[1]
    return format_display(value)


def query_held_modifiers_win32() -> list[str]:
    import ctypes

    user32 = ctypes.windll.user32
    held = []
    for vk, name in WIN_VK_TO_MOD.items():
        if user32.GetAsyncKeyState(vk) & 0x8000:
            held.append(name)
    return held


class KeyCaptureEngine:
    """捕获状态机 —— 不持 UI，宿主把键盘事件转进来

    press/release 返回 'captured' / 'preview' / 'ignored'：
    captured 表示捕获到一个完整组合键（engine.captured 就绪），
    preview 表示只按了修饰键（用 engine.preview_text 刷新提示），
    ignored 表示本轮不归捕获管（宿主走自己的键盘处理）。
    """

    def __init__(self) -> None:
        self.capturing = False
        self.captured: str | None = None
        self.preview_text: str = ""
        self._pending_modifier: str | None = None

    def begin(self) -> None:
        self.capturing = True
        self.reset()

    def end(self) -> None:
        self.capturing = False
        self.reset()

    def reset(self) -> None:
        self.captured = None
        self.preview_text = ""
        self._pending_modifier = None

    def press(self, event) -> str:
        if not self.capturing:
            return "ignored"

        if event.key() in MODIFIER_KEYS or event.key() in WIN_KEYS:
            self._pending_modifier = self._modifier_from_event(event)
            mods = self.active_modifiers(event)
            if mods:
                self.preview_text = (
                    " + ".join(format_display(m) for m in mods) + " + …"
                )
            elif self._pending_modifier:
                self.preview_text = (
                    format_display(self._pending_modifier) + " + …"
                )
            return "preview"

        combo = self.combo_for_event(event)
        if combo:
            self.captured = combo
            self.preview_text = ""
            return "captured"
        return "ignored"

    def release(self, event) -> str:
        if not self.capturing or self.captured:
            return "ignored"

        if event.key() not in MODIFIER_KEYS and event.key() not in WIN_KEYS:
            return "ignored"

        mod = self._pending_modifier or self._modifier_from_event(event)
        if not mod and event.key() in WIN_KEYS:
            mod = "cmd"
        if not mod:
            return "ignored"

        self.captured = mod
        self.preview_text = ""
        self._pending_modifier = None
        return "captured"

    # ---------- 事件 → 组合键 ----------

    def _modifier_from_event(self, event) -> str | None:
        if event.key() not in MODIFIER_KEYS and event.key() not in WIN_KEYS:
            return None

        if sys.platform == "win32":
            held = query_held_modifiers_win32()
            if len(held) == 1:
                return held[0]
            if len(held) > 1:
                for probe in (
                    WIN_VK_TO_MOD.get(event.nativeVirtualKey()),
                    WIN_SCAN_TO_MOD.get(event.nativeScanCode()),
                ):
                    if probe and probe in held:
                        return probe

            if event.key() == Qt.Key.Key_Super_R:
                return "cmd_r"
            if event.key() in (Qt.Key.Key_Meta, Qt.Key.Key_Super_L):
                return "cmd_l"

            scan_mod = WIN_SCAN_TO_MOD.get(event.nativeScanCode())
            if scan_mod:
                return scan_mod

        specific = WIN_VK_TO_MOD.get(event.nativeVirtualKey())
        if specific:
            return specific
        if event.key() in WIN_KEYS:
            return "cmd"
        return MODIFIER_KEYS.get(event.key())

    def active_modifiers(self, event) -> list[str]:
        if sys.platform == "win32":
            held = query_held_modifiers_win32()
            if held:
                return [m for m in MODIFIER_ORDER if m in held]

        mods = event.modifiers()
        result = []
        if mods & Qt.KeyboardModifier.MetaModifier:
            if sys.platform == "win32":
                held = query_held_modifiers_win32()
                win_mods = [m for m in ("cmd_l", "cmd_r") if m in held]
                if win_mods:
                    result.extend(win_mods)
                else:
                    result.append("cmd")
            else:
                result.append("cmd")
        if mods & Qt.KeyboardModifier.ControlModifier:
            result.append("ctrl")
        if mods & Qt.KeyboardModifier.ShiftModifier:
            result.append("shift")
        if mods & Qt.KeyboardModifier.AltModifier:
            result.append("alt")
        return result

    def _resolve_main_key(self, event) -> str | None:
        key = event.key()
        if key in QT_KEY_MAP:
            return QT_KEY_MAP[key]
        if Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
            return chr(key).lower()
        if Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
            return chr(key)
        text = event.text()
        if text and text.isprintable() and len(text) == 1:
            return text
        return None

    def _symbol_from_event(self, event) -> str | None:
        """Shift+9 等得到 ( ) [ ] { } 时，绑定该符号本身，而不是 shift+数字。"""
        text = event.text()
        if not text or len(text) != 1 or not text.isprintable():
            return None
        if text.isalnum() or text.isspace():
            return None
        mods = self.active_modifiers(event)
        if any(m.startswith("ctrl") or m.startswith("alt") for m in mods):
            return None
        return text

    def combo_for_event(self, event) -> str | None:
        symbol = self._symbol_from_event(event)
        if symbol:
            return symbol

        main = self._resolve_main_key(event)
        if not main:
            return None

        mods = self.active_modifiers(event)
        parts = [m for m in MODIFIER_ORDER if m in mods]
        # 输出统一用 cmd，pynput 在 Windows 上更稳定
        parts = ["cmd" if p in ("cmd_l", "cmd_r", "win", "super") else p for p in parts]
        seen: set[str] = set()
        deduped: list[str] = []
        for part in parts:
            if part not in seen:
                seen.add(part)
                deduped.append(part)
        parts = deduped
        parts.append(main)
        return "+".join(parts)
