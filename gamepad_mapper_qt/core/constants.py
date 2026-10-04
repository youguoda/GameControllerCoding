# -*- coding: utf-8 -*-
"""常量定义"""

APP_NAME = "Gamepad Vibe Controller"
APP_VERSION = "2.0.0"
CONFIG_DIR = "config"

PROFILE_ORDER = [
    "cursor", "claude_code", "codex", "zcode", "dsh",
    "browser", "general",
]

# 特殊映射动作（非键盘）
MOUSE_LEFT = "@mouse:left"
MOUSE_RIGHT = "@mouse:right"
MOUSE_MIDDLE = "@mouse:middle"
WHEEL_UP = "@wheel:up"
WHEEL_DOWN = "@wheel:down"
VOICE_KEY = "ctrl_r"

# 全方案统一的鼠标层（左摇杆移动 / 右摇杆滚轮在引擎内；此处为 L3/R3）
UNIVERSAL_MOUSE_MAPPINGS = {
    10: MOUSE_LEFT,
    11: MOUSE_RIGHT,
}

DEFAULT_MOUSE_SENSITIVITY = 20.0
DEFAULT_STICK_DEADZONE = 0.15
DEFAULT_SCROLL_SENSITIVITY = 0.35
MOUSE_SENSITIVITY_MIN = 5.0
MOUSE_SENSITIVITY_MAX = 50.0
SCROLL_SENSITIVITY_MIN = 0.1
SCROLL_SENSITIVITY_MAX = 2.0
LT_LONG_PRESS_SEC = 0.4

DEFAULT_THRESHOLD = 0.5
