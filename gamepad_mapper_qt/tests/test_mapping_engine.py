# -*- coding: utf-8 -*-
"""MappingEngine.consume 的行为规格

这些是 characterization test：锁定既有行为，防止回归。
用假的键盘/鼠标即可，不需要手柄、不需要 QApplication。
"""

import pytest

from core.constants import MOUSE_LEFT, MOUSE_RIGHT, VOICE_KEY
from core.gamepad_input import InputFrame
from core.mapping_engine import MappingEngine


class 假键盘:
    def __init__(self):
        self.日志 = []

    def press(self, key):
        self.日志.append(("press", key))

    def release(self, key):
        self.日志.append(("release", key))

    def release_all(self):
        self.日志.append(("release_all",))


class 假鼠标:
    def __init__(self):
        self.日志 = []

    def left_down(self):
        self.日志.append(("left_down",))

    def left_up(self):
        self.日志.append(("left_up",))

    def right_down(self):
        self.日志.append(("right_down",))

    def right_up(self):
        self.日志.append(("right_up",))

    def move(self, dx, dy, sensitivity):
        self.日志.append(("move", dx, dy))

    def wheel(self, delta):
        self.日志.append(("wheel", delta))


@pytest.fixture
def 引擎():
    """已启动映射的引擎 + 它的假输出"""
    kb, ms = 假键盘(), 假鼠标()
    eng = MappingEngine(kb, ms)
    eng.set_mouse_settings(sensitivity=20.0, deadzone=0.15, scroll_sensitivity=0.35)
    eng.start_mapping()
    kb.日志.clear()
    ms.日志.clear()
    return eng, kb, ms


def _帧(**kw) -> InputFrame:
    kw.setdefault("connected", True)
    return InputFrame(**kw)


# ---------- 按键映射 ----------

def test_按下发_press_松开发_release(引擎):
    eng, kb, _ = 引擎
    eng.set_mappings({0: "y"})

    eng.consume(_帧(just_pressed=frozenset({0})))
    eng.consume(_帧(just_released=frozenset({0})))

    assert kb.日志 == [("press", "y"), ("release", "y")]


def test_未映射的槽位什么都不发(引擎):
    eng, kb, ms = 引擎
    eng.set_mappings({0: "y"})

    eng.consume(_帧(just_pressed=frozenset({1, 2, 3})))

    assert kb.日志 == []
    assert ms.日志 == []


def test_保留槽位_LT_RT_不走通用映射(引擎):
    eng, kb, _ = 引擎
    # 即便 profile 里给 6/7 配了映射，也不该发出来
    eng.set_mappings({6: "a", 7: "b"})

    eng.consume(_帧(just_pressed=frozenset({6, 7})))

    assert kb.日志 == []


def test_组合键原样交给键盘层(引擎):
    eng, kb, _ = 引擎
    eng.set_mappings({12: "ctrl+shift+tab"})

    eng.consume(_帧(just_pressed=frozenset({12})))

    assert kb.日志 == [("press", "ctrl+shift+tab")]


# ---------- 鼠标哨兵动作 ----------

def test_L3_R3_哨兵动作变成鼠标按键(引擎):
    eng, kb, ms = 引擎
    eng.set_mappings({10: MOUSE_LEFT, 11: MOUSE_RIGHT})

    eng.consume(_帧(just_pressed=frozenset({10, 11})))
    eng.consume(_帧(just_released=frozenset({10, 11})))

    assert ("left_down",) in ms.日志
    assert ("right_down",) in ms.日志
    assert ("left_up",) in ms.日志
    assert ("right_up",) in ms.日志
    assert kb.日志 == []


# ---------- 前台闸门 ----------

def test_闸门关闭时不发任何按键(引擎):
    eng, kb, ms = 引擎
    eng.set_mappings({0: "y"})
    eng.set_gate_checker(lambda: False)

    eng.consume(_帧(just_pressed=frozenset({0}), left_stick=(0.9, 0.9)))

    assert ("press", "y") not in kb.日志
    assert not any(项[0] == "move" for 项 in ms.日志)


def test_闸门关闭时释放全部输出(引擎):
    eng, kb, ms = 引擎
    eng.set_gate_checker(lambda: False)

    eng.consume(_帧())

    assert ("release_all",) in kb.日志
    assert ("left_up",) in ms.日志
    assert ("right_up",) in ms.日志


def test_未启动映射时什么都不做(引擎):
    eng, kb, ms = 引擎
    eng.set_mappings({0: "y"})
    eng.stop_mapping()
    kb.日志.clear()
    ms.日志.clear()

    eng.consume(_帧(just_pressed=frozenset({0})))

    assert kb.日志 == []
    assert ms.日志 == []


def test_手柄断开时什么都不做(引擎):
    eng, kb, ms = 引擎
    eng.set_mappings({0: "y"})

    eng.consume(_帧(connected=False, just_pressed=frozenset({0})))

    assert kb.日志 == []
    assert ms.日志 == []


# ---------- RT 语音 ----------

def test_RT_按住发语音键_松开释放(引擎):
    eng, kb, _ = 引擎

    eng.consume(_帧(rt_value=0.8))
    按住后 = list(kb.日志)
    eng.consume(_帧(rt_value=0.1))

    assert 按住后 == [("press", VOICE_KEY)]
    assert kb.日志[-1] == ("release", VOICE_KEY)


def test_RT_持续按住不重复发键(引擎):
    eng, kb, _ = 引擎

    eng.consume(_帧(rt_value=0.8))
    eng.consume(_帧(rt_value=0.9))
    eng.consume(_帧(rt_value=0.7))

    assert kb.日志 == [("press", VOICE_KEY)]


# ---------- 摇杆 ----------

def test_左摇杆超出死区才移动鼠标(引擎):
    eng, _, ms = 引擎

    eng.consume(_帧(left_stick=(0.05, 0.05)))   # 死区内
    死区内 = list(ms.日志)
    eng.consume(_帧(left_stick=(0.5, -0.3)))    # 死区外

    assert 死区内 == []
    assert ("move", 0.5, -0.3) in ms.日志


def test_右摇杆上下对应滚轮正负(引擎):
    eng, _, ms = 引擎

    eng.consume(_帧(right_stick=(0.0, -0.8)))   # 上
    向上 = list(ms.日志)
    ms.日志.clear()
    eng.consume(_帧(right_stick=(0.0, 0.8)))    # 下

    assert 向上 == [("wheel", 0.35)]
    assert ms.日志 == [("wheel", -0.35)]


# ---------- 失败上报 ----------

class 会坏的键盘(假键盘):
    def __init__(self, 坏键):
        super().__init__()
        self.坏键 = 坏键

    def press(self, key):
        if key == self.坏键:
            raise ValueError(f"发不出 {key}")
        super().press(key)


def test_单个坏键不影响同一帧的其他键():
    kb, ms = 会坏的键盘(坏键="foobar"), 假鼠标()
    eng = MappingEngine(kb, ms)
    eng.start_mapping()
    eng.set_mappings({0: "foobar", 1: "y"})

    eng.consume(_帧(just_pressed=frozenset({0, 1})))

    assert ("press", "y") in kb.日志


def test_同一个坏键只上报一次():
    kb, ms = 会坏的键盘(坏键="foobar"), 假鼠标()
    eng = MappingEngine(kb, ms)
    eng.start_mapping()
    eng.set_mappings({0: "foobar"})

    错误 = []
    eng.error_occurred.connect(错误.append)

    for _ in range(5):
        eng.consume(_帧(just_pressed=frozenset({0})))
        eng.consume(_帧(just_released=frozenset({0})))

    assert len(错误) == 1
    assert "foobar" in 错误[0]


# ---------- 扩展的鼠标动作 ----------

class 假鼠标2(假鼠标):
    def middle_down(self):
        self.日志.append(("middle_down",))

    def middle_up(self):
        self.日志.append(("middle_up",))


def _带中键的引擎():
    kb, ms = 假键盘(), 假鼠标2()
    eng = MappingEngine(kb, ms)
    eng.set_mouse_settings(20.0, 0.15, 0.35)
    eng.start_mapping()
    kb.日志.clear(); ms.日志.clear()
    return eng, kb, ms


def test_中键哨兵按下抬起():
    from core.constants import MOUSE_MIDDLE
    eng, kb, ms = _带中键的引擎()
    eng.set_mappings({0: MOUSE_MIDDLE})

    eng.consume(_帧(just_pressed=frozenset({0})))
    eng.consume(_帧(just_released=frozenset({0})))

    assert ms.日志 == [("middle_down",), ("middle_up",)]
    assert kb.日志 == []


def test_滚轮哨兵按下时滚一格_松开不动():
    """滚轮没有「按住」的概念，按下滚一格即可"""
    from core.constants import WHEEL_UP, WHEEL_DOWN
    eng, kb, ms = _带中键的引擎()
    eng.set_mappings({0: WHEEL_UP, 1: WHEEL_DOWN})

    eng.consume(_帧(just_pressed=frozenset({0, 1})))
    按下后 = list(ms.日志)
    ms.日志.clear()
    eng.consume(_帧(just_released=frozenset({0, 1})))

    assert ("wheel", 1.0) in 按下后
    assert ("wheel", -1.0) in 按下后
    assert ms.日志 == [], "松开滚轮不该再滚"


# ---------- 运行中改绑的防卡死释放 ----------

def test_release_slots_释放正按住的输出(引擎):
    eng, kb, _ = 引擎
    eng.set_mappings({0: "y"})
    eng.consume(_帧(just_pressed=frozenset({0})))
    kb.日志.clear()

    eng.release_slots([0])

    assert kb.日志 == [("release", "y")]


def test_release_slots_未绑定的槽位无事发生(引擎):
    eng, kb, _ = 引擎
    eng.set_mappings({})

    eng.release_slots([3])

    assert kb.日志 == []


def test_release_slots_保留槽位跳过(引擎):
    eng, kb, _ = 引擎
    eng.set_mappings({6: "a", 7: "b"})     # 引擎本就不处理 LT/RT

    eng.release_slots([6, 7, 0])

    assert kb.日志 == []


def test_release_slots_单键失败就地上报不外抛(引擎):
    eng, kb, _ = 引擎
    eng.set_mappings({0: "y", 1: "u"})

    def 炸(key):
        raise RuntimeError("boom")

    kb.release = 炸
    错误 = []
    eng.error_occurred.connect(lambda msg: 错误.append(msg))

    eng.release_slots([0, 1])              # 第一个槽位失败不该拖垮第二个

    # 两个槽位是不同动作，各自上报一次；关键是循环没被异常打断
    assert len(错误) == 2
