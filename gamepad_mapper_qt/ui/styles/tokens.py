# -*- coding: utf-8 -*-
"""设计 token —— 全应用唯一的颜色/字号/圆角来源

从前配色要在 theme.qss 和 constants.THEME 两处手工同步，改一处漏一处
就会出现「按钮变色了状态灯还认旧值」。现在样式表由 build_qss() 从这里
生成，Python 侧（画布/托盘/状态灯）直接 import 这里的常量，只剩一份事实。

基调是 Steam Deck 式的游戏工具风：深蓝黑底、品牌青色强调、
大圆角卡片、辉光与呼吸动效（动效在画布与窗口代码里，色值从这里取）。

本模块不依赖 Qt —— 纯数据，方便测试直接断言。
"""

# ---------- 颜色 ----------

BG = "#0b0b16"            # 窗口最底
SURFACE = "#141428"       # 顶栏 / 底栏 / 画布底
CARD = "#1d1d38"          # 卡片
CARD_INNER = "#16162b"    # 卡片内的输入框、列表行
HOVER = "#2c2c50"         # 悬停态
BORDER = "#3a3a66"        # 常规描边
BORDER_SOFT = "#2a2a4c"   # 弱描边（分隔线）

ACCENT = "#00e5b4"        # 品牌青（主强调）
ACCENT_BRIGHT = "#4dffd9" # 悬停 / 呼吸高光
ACCENT_DIM = "#00b394"    # 按下 / 弱强调
PURPLE = "#8b6cff"        # 副强调（渐变下沿）
DANGER = "#ff5c6c"        # 停止 / 危险
WARN = "#ffb84d"          # 未对准 / 冲突提醒
TEXT_ON_ACCENT = "#0b0b16"  # 强调色上面的文字

TEXT = "#f4f4fb"          # 主文字
TEXT_SUB = "#a6a6c6"      # 次级文字
TEXT_DIM = "#6b6b90"      # 弱化文字

# 画布专用的透明色（QSS 里写不了 rgba 语义的叠加层）
# 改绑恰恰发生在未运行时，停止态只轻压暗 —— 主提示交给右下角状态胶囊
CANVAS_BG = "#101022"
CANVAS_GRID_ALPHA = 10
CANVAS_IDLE_ALPHA = 70    # 未运行：轻压暗
CANVAS_GATED_ALPHA = 140  # 运行但门未对准：明显压暗（这时按了真没用）

# ---------- 字号 ----------

FONT_BASE = 14
FONT_SMALL = 12
FONT_SECTION = 16
FONT_TITLE = 24
FONT_PILL = 13
FONT_BIG_KEY = 28

# ---------- 圆角 ----------

RADIUS_CARD = 16
RADIUS_BTN = 10
RADIUS_INPUT = 8
RADIUS_BADGE = 6

FONT_FAMILY = '"Segoe UI", "Microsoft YaHei UI", sans-serif'


# ---------- 旧 THEME 字典（兼容别名） ----------
# 只剩 ui/ 层在用，作为渐进迁移的入口；新代码建议直接用上面的常量。

THEME = {
    "bg": BG,
    "panel": SURFACE,
    "card": CARD,
    "accent": ACCENT,
    "accent2": PURPLE,
    "danger": DANGER,
    "warn": WARN,
    "success": ACCENT,
    "text": TEXT,
    "subtext": TEXT_SUB,
    "dim": BORDER_SOFT,
    "dark": TEXT_ON_ACCENT,
    "border": BORDER,
    "hover": HOVER,
}


def build_qss() -> str:
    """从 token 生成全应用样式表

    替代旧的静态 theme.qss：token 改了，样式自动跟着变，
    不再有「第二份事实」。
    """
    return f"""
* {{
    font-family: {FONT_FAMILY};
    font-size: {FONT_BASE}px;
}}

QMainWindow, QWidget#centralWidget {{
    background-color: {BG};
    color: {TEXT};
}}

QLabel {{
    color: {TEXT};
    background: transparent;
    font-size: {FONT_BASE}px;
}}

QLabel#titleLabel {{
    font-size: {FONT_TITLE}px;
    font-weight: 700;
    color: {ACCENT};
}}

QLabel#subtitleLabel {{
    font-size: {FONT_BASE}px;
    color: {TEXT_SUB};
}}

QLabel#sectionLabel {{
    font-size: {FONT_SECTION}px;
    font-weight: 600;
    color: {TEXT};
}}

QLabel#fieldLabel {{
    font-size: {FONT_BASE}px;
    font-weight: 600;
    color: {TEXT_SUB};
}}

QLabel#statusDot {{
    font-size: 18px;
}}

QLabel#statusText {{
    font-size: 15px;
    color: {TEXT};
}}

QLabel#hintLabel {{
    font-size: {FONT_SMALL + 1}px;
    color: {TEXT_DIM};
}}

QLabel#infoLabel {{
    font-size: {FONT_BASE}px;
    color: {TEXT_SUB};
}}

QLabel#sliderLabel {{
    font-size: {FONT_BASE}px;
    font-weight: 600;
    color: {TEXT_SUB};
    min-width: 96px;
}}

QLabel#sliderValue {{
    font-size: 15px;
    font-weight: 700;
    color: {ACCENT};
    min-width: 44px;
}}

QLabel#metaLabel {{
    font-size: {FONT_SMALL + 1}px;
    color: {TEXT_SUB};
}}

QFrame#cardFrame, QFrame#panelFrame {{
    background-color: {CARD};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_CARD}px;
}}

QFrame#headerFrame {{
    background-color: {SURFACE};
    border-bottom: 1px solid {BORDER_SOFT};
}}

QFrame#footerFrame {{
    background-color: {SURFACE};
    border-top: 1px solid {BORDER_SOFT};
}}

/* ---------- 顶栏状态胶囊 ---------- */

QFrame#pillFrame {{
    border-radius: 13px;
    padding: 4px 12px;
}}
QFrame#pillFrame[tone="ok"] {{
    background-color: rgba(0, 229, 180, 26);
    border: 1px solid {ACCENT_DIM};
}}
QFrame#pillFrame[tone="warn"] {{
    background-color: rgba(255, 184, 77, 26);
    border: 1px solid {WARN};
}}
QFrame#pillFrame[tone="off"] {{
    background-color: {CARD_INNER};
    border: 1px solid {BORDER_SOFT};
}}

QLabel#pillDot {{
    font-size: 13px;
}}
QLabel#pillText {{
    font-size: {FONT_PILL}px;
    font-weight: 600;
    color: {TEXT};
}}

/* ---------- 按钮 ---------- */

QPushButton {{
    background-color: {HOVER};
    color: {TEXT};
    border: none;
    border-radius: {RADIUS_BTN}px;
    padding: 10px 18px;
    font-size: {FONT_BASE}px;
    font-weight: 600;
    min-height: 20px;
}}

QPushButton:hover {{
    background-color: {BORDER};
}}

QPushButton:pressed {{
    background-color: {CARD};
}}

QPushButton:disabled {{
    background-color: {CARD_INNER};
    color: {TEXT_DIM};
}}

QPushButton#refreshBtn {{
    background-color: {HOVER};
    border: 1px solid {BORDER};
    padding: 10px 20px;
    font-size: {FONT_BASE}px;
}}

QPushButton#refreshBtn:hover {{
    border-color: {ACCENT};
    color: {ACCENT};
}}

QPushButton#iconBtn {{
    background-color: transparent;
    border: 1px solid {BORDER};
    border-radius: {RADIUS_BTN}px;
    padding: 6px 12px;
    font-size: 16px;
    color: {TEXT_SUB};
}}
QPushButton#iconBtn:hover {{
    border-color: {ACCENT};
    color: {ACCENT};
}}

QPushButton#startBtn {{
    background-color: {ACCENT};
    color: {TEXT_ON_ACCENT};
    font-size: 17px;
    font-weight: 700;
    padding: 12px 32px;
    border-radius: 12px;
    min-width: 150px;
    min-height: 26px;
}}

QPushButton#startBtn:hover {{
    background-color: {ACCENT_BRIGHT};
}}

QPushButton#startBtn[running="true"] {{
    background-color: {DANGER};
    color: {TEXT};
}}
QPushButton#startBtn[running="true"]:hover {{
    background-color: #ff7d8a;
}}

QPushButton#bindBtn {{
    background-color: transparent;
    color: {ACCENT};
    border: 1px solid {ACCENT};
    padding: 6px 14px;
    font-size: {FONT_SMALL + 1}px;
    border-radius: 8px;
    min-width: 52px;
}}

QPushButton#bindBtn:hover {{
    background-color: {ACCENT};
    color: {TEXT_ON_ACCENT};
}}

QPushButton#clearBtn {{
    background-color: transparent;
    color: {WARN};
    border: 1px solid {WARN};
    padding: 6px 14px;
    font-size: {FONT_SMALL + 1}px;
    border-radius: 8px;
    min-width: 52px;
}}

QPushButton#clearBtn:hover {{
    background-color: {WARN};
    color: {TEXT_ON_ACCENT};
}}

QPushButton#ghostBtn {{
    background-color: transparent;
    color: {TEXT_SUB};
    border: 1px solid {BORDER_SOFT};
    padding: 6px 14px;
    font-size: {FONT_SMALL + 1}px;
    border-radius: 8px;
}}
QPushButton#ghostBtn:hover {{
    border-color: {ACCENT};
    color: {ACCENT};
}}
QPushButton#ghostBtn:disabled {{
    color: {TEXT_DIM};
    border-color: {BORDER_SOFT};
}}

QTableWidget QPushButton#bindBtn,
QTableWidget QPushButton#clearBtn {{
    padding: 0 10px;
    font-size: {FONT_SMALL}px;
    min-width: 46px;
    max-width: 68px;
    min-height: 0;
    max-height: 28px;
    border-radius: 6px;
}}

QPushButton#dialogBtn {{
    font-size: 15px;
    padding: 10px 24px;
    min-width: 88px;
}}

QPushButton#dialogBtnPrimary {{
    background-color: {ACCENT};
    color: {TEXT_ON_ACCENT};
    font-size: 15px;
    font-weight: 700;
    padding: 10px 24px;
    min-width: 88px;
}}

QPushButton#dialogBtnPrimary:hover {{
    background-color: {ACCENT_BRIGHT};
}}

QPushButton#dialogBtnPrimary:disabled {{
    background-color: {HOVER};
    color: {TEXT_DIM};
}}

/* ---------- 复选框 ---------- */

QCheckBox#optionCheck {{
    color: {TEXT};
    font-size: {FONT_BASE}px;
    font-weight: 600;
    spacing: 8px;
}}

QCheckBox#optionCheck::indicator {{
    width: 20px;
    height: 20px;
    border-radius: 5px;
    border: 2px solid {BORDER};
    background: {CARD};
}}

QCheckBox#optionCheck::indicator:hover {{
    border-color: {ACCENT};
}}

QCheckBox#optionCheck::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}

QCheckBox#optionCheck:disabled {{
    color: {TEXT_DIM};
}}

/* ---------- 下拉框 ---------- */

QComboBox {{
    background-color: {CARD};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_BTN}px;
    padding: 8px 14px;
    font-size: 15px;
    font-weight: 600;
    min-width: 180px;
    min-height: 24px;
}}

QComboBox:hover {{
    border-color: {ACCENT};
}}

QComboBox::drop-down {{
    border: none;
    width: 28px;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 7px solid {TEXT_SUB};
    margin-right: 10px;
}}

QComboBox QAbstractItemView {{
    background-color: {CARD};
    color: {TEXT};
    border: 1px solid {BORDER};
    selection-background-color: {HOVER};
    selection-color: {ACCENT};
    font-size: 15px;
    padding: 4px;
    outline: none;
}}

/* ---------- 表格与列表 ---------- */

QTableWidget {{
    background-color: {CARD};
    alternate-background-color: {CARD_INNER};
    color: {TEXT};
    gridline-color: {BORDER_SOFT};
    border: none;
    border-radius: {RADIUS_BTN}px;
    selection-background-color: {HOVER};
    selection-color: {ACCENT};
    outline: none;
    font-size: {FONT_BASE}px;
}}

QTableWidget::item {{
    padding: 6px 12px;
    border: none;
}}

QTableWidget::item:hover {{
    background-color: {HOVER};
}}

QHeaderView::section {{
    background-color: {SURFACE};
    color: {TEXT_SUB};
    padding: 10px;
    border: none;
    border-bottom: 2px solid {BORDER};
    font-weight: 700;
    font-size: {FONT_BASE}px;
}}

QListWidget#profileList {{
    background-color: {CARD_INNER};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_BTN}px;
    color: {TEXT};
    font-size: 15px;
    outline: none;
}}
QListWidget#profileList::item {{
    padding: 10px 14px;
    border-radius: {RADIUS_BADGE + 2}px;
}}
QListWidget#profileList::item:selected {{
    background-color: {HOVER};
    color: {ACCENT};
}}
QListWidget#profileList::item:hover {{
    background-color: {HOVER};
}}

/* ---------- 滚动条 / 滑杆 ---------- */

QScrollBar:vertical {{
    background: {SURFACE};
    width: 12px;
    border-radius: 6px;
    margin: 2px;
}}

QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 6px;
    min-height: 32px;
}}

QScrollBar::handle:vertical:hover {{
    background: {ACCENT};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background: {SURFACE};
    height: 12px;
    border-radius: 6px;
    margin: 2px;
}}

QScrollBar::handle:horizontal {{
    background: {BORDER};
    border-radius: 6px;
    min-width: 32px;
}}

QScrollBar::handle:horizontal:hover {{
    background: {ACCENT};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

QSlider::groove:horizontal {{
    height: 8px;
    background: {BORDER_SOFT};
    border-radius: 4px;
}}

QSlider::handle:horizontal {{
    width: 22px;
    height: 22px;
    margin: -7px 0;
    background: {ACCENT};
    border-radius: 11px;
}}

QSlider::handle:horizontal:hover {{
    background: {ACCENT_BRIGHT};
}}

QSlider::sub-page:horizontal {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {ACCENT_DIM}, stop:1 {PURPLE});
    border-radius: 4px;
}}

/* ---------- 对话框 ---------- */

QDialog {{
    background-color: {BG};
}}

QMessageBox {{
    background-color: {SURFACE};
}}

QMessageBox QLabel {{
    font-size: 15px;
    color: {TEXT};
    min-width: 320px;
}}

QMessageBox QPushButton {{
    font-size: {FONT_BASE}px;
    min-width: 80px;
}}

QLabel#dialogTitle {{
    font-size: 22px;
    font-weight: 700;
    color: {ACCENT};
}}

QLabel#dialogHint {{
    color: {TEXT_SUB};
    font-size: 15px;
}}

/* ---------- 绑定面板 ---------- */

QLabel#panelSlotName {{
    font-size: 20px;
    font-weight: 700;
    color: {TEXT};
}}

QLabel#slotBadge {{
    font-size: {FONT_SMALL + 1}px;
    font-weight: 600;
    border-radius: {RADIUS_BADGE}px;
    padding: 3px 10px;
}}
QLabel#slotBadge[tone="ok"] {{
    color: {ACCENT};
    background-color: rgba(0, 229, 180, 30);
}}
QLabel#slotBadge[tone="warn"] {{
    color: {WARN};
    background-color: rgba(255, 184, 77, 30);
}}
QLabel#slotBadge[tone="mute"] {{
    color: {TEXT_DIM};
    background-color: {CARD_INNER};
}}

QLabel#currentKey {{
    font-size: {FONT_BIG_KEY}px;
    font-weight: 700;
    color: {TEXT};
    background-color: {CARD_INNER};
    border: 2px solid {ACCENT};
    border-radius: 12px;
    padding: 14px 24px;
}}
QLabel#currentKey[empty="true"] {{
    color: {TEXT_DIM};
    border-color: {BORDER_SOFT};
}}

QFrame#warnBanner {{
    border-radius: {RADIUS_BADGE + 2}px;
    padding: 8px 12px;
}}
QFrame#warnBanner[tone="warn"] {{
    background-color: rgba(255, 184, 77, 24);
    border: 1px solid {WARN};
}}
QFrame#warnBanner[tone="info"] {{
    background-color: rgba(0, 229, 180, 22);
    border: 1px solid {ACCENT_DIM};
}}

QLabel#warnBannerText {{
    font-size: {FONT_SMALL + 1}px;
    color: {TEXT};
    background: transparent;
}}
QFrame#warnBanner[tone="warn"] QLabel#warnBannerText {{
    color: {WARN};
}}

/* ---------- 输入与目录（面板 / 对话框共用） ---------- */

QLineEdit#searchBox, QLineEdit#inputLine {{
    background-color: {CARD_INNER};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_INPUT}px;
    padding: 8px 12px;
    color: {TEXT};
    font-size: {FONT_BASE}px;
    selection-background-color: {ACCENT_DIM};
}}
QLineEdit#searchBox:focus, QLineEdit#inputLine:focus {{
    border-color: {ACCENT};
}}

QTreeWidget#catalogTree {{
    background-color: {CARD_INNER};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_BTN}px;
    color: {TEXT_SUB};
    font-size: {FONT_BASE}px;
    outline: none;
}}
QTreeWidget#catalogTree::item {{
    padding: 5px 4px;
}}
QTreeWidget#catalogTree::item:selected {{
    background-color: {ACCENT};
    color: {TEXT_ON_ACCENT};
    border-radius: 4px;
}}
QTreeWidget#catalogTree::item:hover {{
    background-color: {HOVER};
}}
"""


def all_colors() -> dict:
    """供测试断言的 (token 名 → 色值) 总表"""
    return {
        name: value
        for name, value in globals().items()
        if name.isupper() and isinstance(value, str) and value.startswith("#")
    }
