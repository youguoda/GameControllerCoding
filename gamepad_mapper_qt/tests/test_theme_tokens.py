# -*- coding: utf-8 -*-
"""设计 token 的规格

样式表由 build_qss() 生成，Python 侧直接用常量 —— 两边来自同一份
token，这里守住「生成物完整、别名表完整」两条底线。
"""

from ui.styles import tokens


def test_build_qss_包含全部色值():
    qss = tokens.build_qss()
    for name, value in tokens.all_colors().items():
        # CANVAS_* 之类的画布专用色不进样式表，其余都必须出现在生成物里
        if name.startswith("CANVAS_"):
            continue
        assert value in qss, f"token {name} ({value}) 没有进入生成的样式表"


def test_build_qss_是稳定生成物():
    assert tokens.build_qss() == tokens.build_qss()


def test_旧THEME别名的键一个不少():
    """既有 ui 代码按这些键取色，漏一个就是运行时 KeyError"""
    required = {
        "bg", "panel", "card", "accent", "accent2", "danger", "warn",
        "success", "text", "subtext", "dim", "dark", "border", "hover",
    }
    assert required <= set(tokens.THEME)


def test_色值格式统一可解析():
    for name, value in tokens.all_colors().items():
        assert value.startswith("#") and len(value) in (7, 9), (
            f"{name} = {value} 不是 #RRGGBB / #RRGGBBAA 形式"
        )
