# -*- coding: utf-8 -*-
"""Qt 界面的设计令牌与全局样式表。

和 Tkinter 版本保持同一套视觉语言（浅色内容区 + 深色侧边栏与日志台），
但不再需要手工补偿 DPI：Qt 自己按 devicePixelRatio 缩放，
圆角、描边、文字都是矢量抗锯齿绘制。
"""

import os

from PySide6.QtGui import QColor, QFont, QFontDatabase

ASSETS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")


def asset_path(name: str) -> str:
    """资源文件的绝对路径（QSS 里用 url() 引用时必须是正斜杠路径）。"""
    p = os.path.join(ASSETS_DIR, name)
    return p.replace("\\", "/") if os.path.isfile(p) else ""

# ---------------------------------------------------------------- 颜色
BG = "#F4F6FA"
SURFACE = "#FFFFFF"
SURFACE_2 = "#F7F9FC"
SURFACE_3 = "#EDF1F8"
SURFACE_4 = "#E3E9F4"
BORDER = "#DDE3EE"
BORDER_2 = "#C9D2E2"

TEXT = "#151A23"
TEXT_SUB = "#5B6474"
TEXT_MUTED = "#98A1B0"
TEXT_ON = "#FFFFFF"

PRIMARY = "#3D6DF6"
PRIMARY_HOVER = "#2F5DE4"
PRIMARY_ACTIVE = "#2850C8"
PRIMARY_SOFT = "#ECF1FE"
PRIMARY_TEXT = "#2A56D6"

SUCCESS = "#12A150"
SUCCESS_SOFT = "#E6F6EE"
SUCCESS_TEXT = "#0C7C3D"
WARN = "#C27A08"
WARN_SOFT = "#FDF4E4"
WARN_TEXT = "#9A6106"
DANGER = "#DC3B41"
DANGER_HOVER = "#C93038"
DANGER_SOFT = "#FDEDEE"
DANGER_TEXT = "#B3282F"

SIDEBAR = "#151A24"
SIDEBAR_TOP = "#1B2130"
SIDEBAR_HOVER = "#222A3A"
SIDEBAR_ACTIVE = "#273047"
SIDEBAR_TEXT = "#8C95A8"
SIDEBAR_TEXT_ON = "#FFFFFF"
SIDEBAR_LABEL = "#5A6478"

CONSOLE_BG = "#11151E"
CONSOLE_TOOLBAR = "#171C27"
CONSOLE_BORDER = "#242C3C"
CONSOLE_TEXT = "#C4CAD6"
CONSOLE_MUTED = "#69728A"
CONSOLE_OK = "#4ADE80"
CONSOLE_WARN = "#FBBF24"
CONSOLE_ERR = "#F87171"
CONSOLE_INFO = "#7DA9FF"
CONSOLE_TIME = "#4A536B"

SCROLL_THUMB = "#C2CAD9"
SCROLL_THUMB_HOVER = "#AEB7C9"

BADGE_LEVELS = {
    "info": (PRIMARY_SOFT, PRIMARY_TEXT),
    "ok": (SUCCESS_SOFT, SUCCESS_TEXT),
    "success": (SUCCESS_SOFT, SUCCESS_TEXT),
    "warn": (WARN_SOFT, WARN_TEXT),
    "error": (DANGER_SOFT, DANGER_TEXT),
    "danger": (DANGER_SOFT, DANGER_TEXT),
    "muted": (SURFACE_3, TEXT_SUB),
    "neutral": (SURFACE_3, TEXT_SUB),
}

# ---------------------------------------------------------------- 尺寸（逻辑像素）
SIDEBAR_WIDTH = 208
HEADER_HEIGHT = 68
CONSOLE_HEIGHT = 168
CONSOLE_HEADER = 38
RADIUS_CARD = 14
RADIUS_BTN = 8

_UI_CANDIDATES = (
    "Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", "HarmonyOS Sans SC",
    "Source Han Sans SC", "Noto Sans CJK SC", "Segoe UI",
)
_MONO_CANDIDATES = (
    "Cascadia Mono", "Consolas", "JetBrains Mono", "DejaVu Sans Mono", "Courier New",
)

ui_family = "Microsoft YaHei UI"
mono_family = "Consolas"


def init_fonts():
    """挑系统里真实存在的字体。"""
    global ui_family, mono_family
    families = set(QFontDatabase.families())
    for name in _UI_CANDIDATES:
        if name in families:
            ui_family = name
            break
    for name in _MONO_CANDIDATES:
        if name in families:
            mono_family = name
            break
    return ui_family, mono_family


def ui_font(size=10, weight=QFont.Weight.Normal):
    f = QFont(ui_family)
    f.setPointSizeF(size)
    f.setWeight(weight)
    return f


def mono_font(size=9):
    f = QFont(mono_family)
    f.setPointSizeF(size)
    f.setStyleHint(QFont.StyleHint.Monospace)
    return f


def color(name: str) -> QColor:
    return QColor(name)


# ---------------------------------------------------------------- 样式表
def build_qss() -> str:
    _check = asset_path("check.svg")
    _check_image = f'image: url("{_check}");' if _check else ""
    return f"""
/* ---------- 基础 ---------- */
QWidget {{
    color: {TEXT};
    font-family: "{ui_family}";
    font-size: 10pt;
}}
#Root, #ContentArea, #HeaderBar, #PageBody {{ background: {BG}; }}

/* 滚动条：细、无边框、无箭头 */
QScrollBar:vertical {{
    background: transparent; width: 10px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {SCROLL_THUMB}; border-radius: 5px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {SCROLL_THUMB_HOVER}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 0; }}
QScrollBar::handle:horizontal {{
    background: {SCROLL_THUMB}; border-radius: 5px; min-width: 30px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ---------- 侧边栏 ---------- */
#Sidebar, #SidebarBrand, #NavBox, #SidebarTail {{ background: {SIDEBAR}; }}
#BrandName {{ color: {SIDEBAR_TEXT_ON}; font-size: 11pt; font-weight: 600; }}
#BrandVer {{ color: {SIDEBAR_TEXT}; font-size: 8pt; }}
#NavSection {{ color: {SIDEBAR_LABEL}; font-size: 8pt; font-weight: 600; }}

#NavButton {{
    background: transparent; color: {SIDEBAR_TEXT};
    border: none; border-radius: 10px;
    padding: 10px 12px; text-align: left; font-size: 10pt;
}}
#NavButton:hover {{ background: {SIDEBAR_HOVER}; color: {SIDEBAR_TEXT_ON}; }}
#NavButton:checked {{
    background: {SIDEBAR_ACTIVE}; color: {SIDEBAR_TEXT_ON}; font-weight: 600;
}}

#StatusChip {{ background: {SIDEBAR_TOP}; border: none; border-radius: 10px; }}
#StatusChip:hover {{ background: {SIDEBAR_HOVER}; }}
#StatusChip[level="ok"] #ChipDot {{ color: {SUCCESS}; }}
#ChipTitle {{ color: {SIDEBAR_TEXT_ON}; font-size: 9pt; font-weight: 600; }}
#ChipSub {{ color: {SIDEBAR_TEXT}; font-size: 8pt; }}
#ChipFoot {{ color: #4C5568; font-size: 8pt; }}

/* ---------- 页头 ---------- */
#PageTitle {{ font-size: 15pt; font-weight: 600; }}
#PageSubtitle {{ color: {TEXT_MUTED}; font-size: 9pt; }}
#HeaderLine {{ background: {BORDER}; }}

/* ---------- 卡片 ---------- */
#Card {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_CARD}px;
}}
#CardTitle {{ font-size: 11pt; font-weight: 600; }}
#CardSubtitle {{ color: {TEXT_MUTED}; font-size: 9pt; }}
#SectionLabel {{ color: {TEXT_MUTED}; font-size: 9pt; font-weight: 600; }}
#FieldLabel {{ color: {TEXT_SUB}; font-size: 10pt; }}
#Hint {{ color: {TEXT_MUTED}; font-size: 9pt; }}
#DividerLine {{ background: {BORDER}; }}

/* ---------- 按钮 ---------- */
#PrimaryButton {{
    background: {PRIMARY}; color: {TEXT_ON}; border: none;
    border-radius: {RADIUS_BTN}px; padding: 8px 16px; font-weight: 600;
}}
#PrimaryButton:hover {{ background: {PRIMARY_HOVER}; }}
#PrimaryButton:pressed {{ background: {PRIMARY_ACTIVE}; }}
#PrimaryButton:disabled {{ background: #BFC9E6; color: #FFFFFF; }}

#SecondaryButton {{
    background: {SURFACE}; color: {TEXT};
    border: 1px solid {BORDER_2}; border-radius: {RADIUS_BTN}px;
    padding: 8px 16px;
}}
#SecondaryButton:hover {{ background: {SURFACE_3}; }}
#SecondaryButton:pressed {{ background: {SURFACE_4}; }}
#SecondaryButton:disabled {{ background: {SURFACE_2}; color: {TEXT_MUTED}; }}

#SoftButton {{
    background: {PRIMARY_SOFT}; color: {PRIMARY_TEXT}; border: none;
    border-radius: {RADIUS_BTN}px; padding: 8px 16px; font-weight: 600;
}}
#SoftButton:hover {{ background: #DFE8FD; }}

#GhostButton {{
    background: transparent; color: {TEXT_SUB}; border: none;
    border-radius: {RADIUS_BTN}px; padding: 8px 14px;
}}
#GhostButton:hover {{ background: {SURFACE_3}; }}
#GhostButton:disabled {{ color: #C3C9D6; }}

#DangerButton {{
    background: {DANGER}; color: {TEXT_ON}; border: none;
    border-radius: {RADIUS_BTN}px; padding: 8px 16px; font-weight: 600;
}}
#DangerButton:hover {{ background: {DANGER_HOVER}; }}

#ConsoleButton {{
    background: transparent; color: {CONSOLE_MUTED}; border: none;
    border-radius: 7px; padding: 6px 12px;
}}
#ConsoleButton:hover {{ background: {CONSOLE_BORDER}; color: {CONSOLE_TEXT}; }}

/* ---------- 输入 ---------- */
QLineEdit, QSpinBox, QComboBox {{
    background: {SURFACE_2}; color: {TEXT};
    border: 1px solid {BORDER}; border-radius: 9px;
    padding: 7px 12px; selection-background-color: {PRIMARY_SOFT};
    selection-color: {TEXT};
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border: 1px solid {PRIMARY}; background: {SURFACE};
}}
QLineEdit[readOnly="true"] {{ color: {TEXT_SUB}; }}
QLineEdit:disabled {{ color: {TEXT_MUTED}; background: {SURFACE_2}; }}

/* ---------- 分段控件 ---------- */
#Segmented {{
    background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 9px;
}}
#SegButton {{
    background: transparent; color: {TEXT_SUB}; border: none;
    border-radius: 7px; padding: 6px 16px; font-size: 10pt;
}}
#SegButton:hover {{ color: {TEXT}; }}
#SegButton:checked {{
    background: {PRIMARY}; color: {TEXT_ON}; font-weight: 600;
}}

/* ---------- 统计块 ---------- */
#StatChip {{ background: {SURFACE_2}; border: none; border-radius: 10px; }}
#StatValue {{ font-size: 13pt; font-weight: 600; }}
#StatLabel {{ color: {TEXT_MUTED}; font-size: 8pt; }}

/* ---------- 复选框 ---------- */
QCheckBox {{ color: {TEXT}; spacing: 9px; }}
QCheckBox::indicator {{
    width: 17px; height: 17px; border-radius: 5px;
    border: 1px solid {BORDER_2}; background: {SURFACE};
}}
QCheckBox::indicator:hover {{ border-color: {PRIMARY}; }}
QCheckBox::indicator:checked {{
    background: {PRIMARY}; border-color: {PRIMARY};
    {_check_image}
}}
#CheckHint {{ color: {TEXT_MUTED}; font-size: 9pt; }}

/* ---------- 表格 ---------- */
QTableWidget {{
    background: {SURFACE}; border: none; outline: none;
    gridline-color: transparent; selection-background-color: {PRIMARY_SOFT};
    selection-color: {PRIMARY_TEXT};
}}
QTableWidget::item {{
    padding: 4px 8px; border-bottom: 1px solid #EFF2F8;
}}
QTableWidget::item:selected {{ background: {PRIMARY_SOFT}; color: {PRIMARY_TEXT}; }}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{
    background: {SURFACE_2}; color: {TEXT_SUB};
    border: none; border-bottom: 1px solid {BORDER};
    padding: 7px 8px; font-weight: 600;
}}
QTableCornerButton::section {{ background: {SURFACE_2}; border: none; }}

/* ---------- 进度条 ---------- */
QProgressBar {{
    background: {SURFACE_4}; border: none; border-radius: 4px;
    height: 8px; text-align: center; color: transparent;
}}
QProgressBar::chunk {{ background: {PRIMARY}; border-radius: 4px; }}

/* ---------- 日志台 ---------- */
#LogPanel {{ background: {CONSOLE_BG}; }}
#LogHeader {{ background: {CONSOLE_TOOLBAR}; }}
#LogTitle {{ color: {CONSOLE_TEXT}; font-size: 9pt; font-weight: 600; }}
#LogStatus {{ color: {CONSOLE_MUTED}; font-size: 9pt; }}
#LogView {{
    background: {CONSOLE_BG}; color: {CONSOLE_TEXT};
    border: none; padding: 8px 12px;
}}
#LogSep {{ background: {CONSOLE_BORDER}; }}

/* ---------- 底部操作条 ---------- */
#ActionBar {{ background: {SURFACE}; border-top: 1px solid {BORDER}; }}
#ActionStatus {{ color: {TEXT_MUTED}; font-size: 9pt; }}

/* ---------- 状态徽标 ---------- */
#Badge {{ border-radius: 11px; padding: 3px 10px; font-size: 9pt; }}

/* ---------- 对话框 ---------- */
QDialog {{ background: {BG}; }}
QMessageBox {{ background: {BG}; }}
QMessageBox QLabel {{ color: {TEXT}; }}

/* ---------- 提示气泡 ---------- */
QToolTip {{
    background: #1B2130; color: #FFFFFF;
    border: none; padding: 5px 8px; border-radius: 6px;
}}
"""
