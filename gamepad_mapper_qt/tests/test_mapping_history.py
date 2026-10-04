# -*- coding: utf-8 -*-
"""撤销栈的规格"""

from core.mapping_history import MappingHistory


def test_空栈不可撤销():
    h = MappingHistory()
    assert h.can_undo is False
    assert h.undo() is None


def test_撤销还原变更前状态():
    """push 存的是变更前快照，undo 按 LIFO 还原最近一次变更的「之前」"""
    h = MappingHistory()
    h.push({0: "a"})
    h.push({0: "b", 1: "c"})

    assert h.undo() == {0: "b", 1: "c"}
    assert h.undo() == {0: "a"}
    assert h.can_undo is False


def test_快照是拷贝_入栈后的改动不影响():
    h = MappingHistory()
    current = {0: "a"}
    h.push(current)
    current[0] = "zzz"

    assert h.undo() == {0: "a"}


def test_栈深有上限_最早的被挤掉():
    h = MappingHistory(capacity=3)
    for i in range(5):
        h.push({0: str(i)})

    assert h.undo() == {0: "4"}
    assert h.undo() == {0: "3"}
    assert h.undo() == {0: "2"}
    assert h.can_undo is False


def test_clear():
    h = MappingHistory()
    h.push({0: "a"})
    h.clear()

    assert h.can_undo is False
