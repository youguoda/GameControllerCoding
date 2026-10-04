# -*- coding: utf-8 -*-
"""绑定变更的轻量撤销栈

只记「整张映射表的前一状态」，不记滑杆类连续值 —— 拖一次滑杆几十次
变更，进栈毫无意义。撤销直接把快照整表还原，不做字段级 diff。

栈不跨方案：切换方案时清空，否则会把上一个方案的键位还原到当前方案。
"""

from typing import Dict, List, Optional

_MAX_HISTORY = 20


class MappingHistory:
    def __init__(self, capacity: int = _MAX_HISTORY) -> None:
        self._capacity = capacity
        self._stack: List[Dict[int, str]] = []

    def push(self, mappings: Dict[int, str]) -> None:
        """变更发生前调用：把变更前的状态存起来"""
        self._stack.append(dict(mappings))
        if len(self._stack) > self._capacity:
            self._stack.pop(0)

    def undo(self) -> Optional[Dict[int, str]]:
        """弹出最近一次变更前的状态；栈空返回 None"""
        if not self._stack:
            return None
        return self._stack.pop()

    def clear(self) -> None:
        self._stack.clear()

    @property
    def can_undo(self) -> bool:
        return bool(self._stack)
