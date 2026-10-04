# -*- coding: utf-8 -*-
"""当前生效的方案

拥有方案对象、统一鼠标层的合并与剥离、以及落盘时机。
"""

from typing import Callable, Dict, Optional

from core.config_store import (
    ConfigNotSavable,
    HarnessProfile,
    effective_mappings,
    load_profile,
    save_profile,
)
from core.constants import UNIVERSAL_MOUSE_MAPPINGS


class ActiveProfile:
    """全应用唯一持有「当前方案」的地方

    任何变更立即落盘，调用方不需要知道 save 的存在。
    落盘失败（文件损坏）走 on_save_failed 回调，对调用方永不抛 ——
    否则每个 setter 的调用点都得处理一个它没请求的操作的失败模式。
    """

    def __init__(
        self,
        profile_id: str,
        on_save_failed: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._on_save_failed = on_save_failed
        self._reported: set[str] = set()
        self._load(profile_id)

    def _load(self, profile_id: str) -> None:
        profile = load_profile(profile_id)
        if profile is None:
            profile = HarnessProfile(id=profile_id, display_name=profile_id)
        self._profile = profile

    # ---------- 只读 ----------

    @property
    def mappings(self) -> Dict[int, str]:
        """已合并统一鼠标层的映射"""
        return effective_mappings(self._profile)

    @property
    def profile(self) -> HarnessProfile:
        """其余字段的只读访问（process_names / display_name / 灵敏度…）"""
        return self._profile

    @property
    def savable(self) -> bool:
        return self._profile.savable

    # ---------- 变更（自动落盘，永不抛） ----------

    def switch_to(self, profile_id: str) -> None:
        """切到另一个方案

        不需要先保存旧方案 —— 每次变更都已经立即落盘了。
        """
        self._load(profile_id)

    def set_threshold(self, value: float) -> None:
        self._profile.threshold = value
        self._persist()

    def set_mouse_sensitivity(self, value: float) -> None:
        self._profile.mouse_sensitivity = value
        self._persist()

    def set_scroll_sensitivity(self, value: float) -> None:
        self._profile.scroll_sensitivity = value
        self._persist()

    def set_mappings(self, mappings: Dict[int, str]) -> None:
        self._profile.mappings = self._strip_universal_mouse(mappings)
        self._persist()

    def set_display_name(self, value: str) -> None:
        self._profile.display_name = value
        self._persist()

    def set_process_names(self, names) -> None:
        self._profile.process_names = list(names)
        self._persist()

    def _strip_universal_mouse(self, mappings: Dict[int, str]) -> Dict[int, str]:
        """与统一层取值相同的项不写盘，免得每个方案重复一遍

        这是 effective_mappings 的逆操作 —— 两者必须待在一起，
        分开放会让「合并再剥离等于原样」这个不变式无人负责。
        """
        if not self._profile.universal_mouse:
            return dict(mappings)
        return {
            slot: action
            for slot, action in mappings.items()
            if UNIVERSAL_MOUSE_MAPPINGS.get(slot) != action
        }

    def _persist(self) -> None:
        try:
            save_profile(self._profile)
        except ConfigNotSavable as exc:
            self._report_failure(str(exc))

    def _report_failure(self, message: str) -> None:
        """同一个原因只报一次 —— 拖一次滑块会触发几十次保存"""
        if message in self._reported:
            return
        self._reported.add(message)
        if self._on_save_failed:
            self._on_save_failed(message)
