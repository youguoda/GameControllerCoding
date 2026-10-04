# -*- coding: utf-8 -*-
"""配置与 Harness Profile 持久化"""

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from core import paths
from core.constants import (
    CONFIG_DIR,
    DEFAULT_MOUSE_SENSITIVITY,
    DEFAULT_SCROLL_SENSITIVITY,
    DEFAULT_STICK_DEADZONE,
    DEFAULT_THRESHOLD,
    PROFILE_ORDER,
    UNIVERSAL_MOUSE_MAPPINGS,
)

PROFILES_DIR = "profiles"
APP_STATE_FILE = "app_state.json"


class ConfigNotSavable(Exception):
    """配置来自一个读不了的文件，写回去会毁掉用户原本的内容"""


@dataclass
class AppState:
    active_profile: str = PROFILE_ORDER[0]
    launch_at_startup: bool = False
    auto_start_mapping: bool = False
    # 与 HarnessProfile.savable 同义：读不了的文件不许写回去
    savable: bool = True


@dataclass
class HarnessProfile:
    id: str
    display_name: str
    process_names: List[str] = field(default_factory=list)
    mappings: Dict[int, str] = field(default_factory=dict)
    threshold: float = DEFAULT_THRESHOLD
    mouse_sensitivity: float = DEFAULT_MOUSE_SENSITIVITY
    stick_deadzone: float = DEFAULT_STICK_DEADZONE
    scroll_sensitivity: float = DEFAULT_SCROLL_SENSITIVITY
    universal_mouse: bool = True
    # 从损坏/读不了的文件加载出来的是 False —— save_profile 会拒绝覆盖它
    savable: bool = True


def effective_mappings(profile: HarnessProfile) -> Dict[int, str]:
    """合并统一鼠标层与方案专属按键（方案可覆盖鼠标层）"""
    if not profile.universal_mouse:
        return dict(profile.mappings)
    merged = dict(UNIVERSAL_MOUSE_MAPPINGS)
    merged.update(profile.mappings)
    return merged


def _base_dir() -> str:
    # 走 paths：打包后必须是 exe 所在目录，否则配置写进临时解压目录、退出即失
    return paths.app_dir()


def _profiles_dir() -> str:
    return os.path.join(_base_dir(), CONFIG_DIR, PROFILES_DIR)


def _app_state_path() -> str:
    return os.path.join(_base_dir(), CONFIG_DIR, APP_STATE_FILE)


def list_profile_ids() -> List[str]:
    directory = _profiles_dir()
    if not os.path.isdir(directory):
        return list(PROFILE_ORDER)
    on_disk = {
        name[:-5]
        for name in os.listdir(directory)
        if name.endswith(".json")
    }
    ordered = [pid for pid in PROFILE_ORDER if pid in on_disk]
    extra = sorted(on_disk - set(ordered))
    return ordered + extra or list(PROFILE_ORDER)


def load_profile(profile_id: str) -> Optional[HarnessProfile]:
    path = os.path.join(_profiles_dir(), f"{profile_id}.json")
    if not os.path.isfile(path):
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        # 文件在但读不了 —— 和「不存在」是两回事。标记为不可保存，
        # 免得后续任何一次保存把用户的配置覆盖成空。
        return HarnessProfile(id=profile_id, display_name=profile_id, savable=False)

    mappings: Dict[int, str] = {}
    raw = data.get("mappings", {})
    for key, value in raw.items():
        if value and value != "-":
            mappings[int(key)] = str(value)

    return HarnessProfile(
        id=data.get("id", profile_id),
        display_name=data.get("display_name", profile_id),
        process_names=list(data.get("process_names", [])),
        mappings=mappings,
        threshold=float(data.get("threshold", DEFAULT_THRESHOLD)),
        mouse_sensitivity=float(
            data.get("mouse_sensitivity", DEFAULT_MOUSE_SENSITIVITY)
        ),
        stick_deadzone=float(data.get("stick_deadzone", DEFAULT_STICK_DEADZONE)),
        scroll_sensitivity=float(
            data.get("scroll_sensitivity", DEFAULT_SCROLL_SENSITIVITY)
        ),
        universal_mouse=bool(data.get("universal_mouse", True)),
    )


def save_profile(profile: HarnessProfile) -> None:
    if not profile.savable:
        raise ConfigNotSavable(
            f"方案「{profile.id}」的文件读取失败，已停止写入以免覆盖原有配置"
        )

    directory = _profiles_dir()
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, f"{profile.id}.json")

    data = {
        "id": profile.id,
        "display_name": profile.display_name,
        "process_names": profile.process_names,
        "mappings": {str(k): v for k, v in sorted(profile.mappings.items())},
        "threshold": profile.threshold,
        "mouse_sensitivity": profile.mouse_sensitivity,
        "stick_deadzone": profile.stick_deadzone,
        "scroll_sensitivity": profile.scroll_sensitivity,
        "universal_mouse": profile.universal_mouse,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def delete_profile(profile_id: str) -> bool:
    """删除方案文件；文件本来就不存在时返回 False

    只管删文件。删的是当前激活方案时的切换逻辑归 MainWindow。
    """
    path = os.path.join(_profiles_dir(), f"{profile_id}.json")
    if not os.path.isfile(path):
        return False
    os.remove(path)
    return True


def load_app_state() -> AppState:
    path = _app_state_path()
    if not os.path.isfile(path):
        return AppState()

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return AppState(savable=False)

    return AppState(
        active_profile=data.get("active_profile", PROFILE_ORDER[0]),
        launch_at_startup=bool(data.get("launch_at_startup", False)),
        auto_start_mapping=bool(data.get("auto_start_mapping", False)),
    )


def save_app_state(state: AppState) -> None:
    if not state.savable:
        raise ConfigNotSavable(
            "app_state.json 读取失败，已停止写入以免覆盖原有设置"
        )

    path = _app_state_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = {
        "active_profile": state.active_profile,
        "launch_at_startup": state.launch_at_startup,
        "auto_start_mapping": state.auto_start_mapping,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_active_profile_id() -> str:
    return load_app_state().active_profile


def save_active_profile_id(profile_id: str) -> None:
    state = load_app_state()
    state.active_profile = profile_id
    save_app_state(state)


