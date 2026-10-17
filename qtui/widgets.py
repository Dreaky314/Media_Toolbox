# -*- coding: utf-8 -*-
"""Qt 复用控件：卡片、徽标、分段控件、统计块、矢量图标、日志台。"""

import os

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (QColor, QIcon, QPainter, QPainterPath, QPen,
                           QPixmap, QPolygonF)
from PySide6.QtWidgets import (QButtonGroup, QFrame, QHBoxLayout, QLabel,
                               QPlainTextEdit, QProgressBar, QPushButton,
                               QSizePolicy, QVBoxLayout, QWidget)

from . import theme


# ============================================================
# 矢量图标：直接画到 QPixmap，避免依赖图标字体
# ============================================================
def make_pixmap(name: str, color: str, size: int = 18) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    pen = QPen(QColor(color))
    pen.setWidthF(1.7)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(QColor(color))

    s = float(size)
    x, y = s * 0.12, s * 0.12
    w = s - 2 * x

    if name == "folder":
        path = QPainterPath()
        path.moveTo(x, y + w * 0.22)
        path.lineTo(x + w * 0.34, y + w * 0.22)
        path.lineTo(x + w * 0.46, y + w * 0.40)
        path.lineTo(x + w, y + w * 0.40)
        path.lineTo(x + w, y + w * 0.92)
        path.lineTo(x, y + w * 0.92)
        path.closeSubpath()
        p.drawPath(path)
    elif name == "merge":
        mid = x + w * 0.62
        cy = s / 2
        p.drawLine(QPointF(x, y + w * 0.08), QPointF(mid, cy))
        p.drawLine(QPointF(x, y + w * 0.92), QPointF(mid, cy))
        p.drawLine(QPointF(mid, cy), QPointF(x + w, cy))
    elif name == "settings":
        for ly, knob in ((y + w * 0.16, 0.62), (s / 2, 0.30), (y + w * 0.84, 0.72)):
            p.drawLine(QPointF(x, ly), QPointF(x + w, ly))
            kx = x + w * knob
            r = w * 0.13
            p.setBrush(QColor(theme.SURFACE))
            p.drawEllipse(QPointF(kx, ly), r, r)
            p.setBrush(QColor(color))
    elif name == "play":
        path = QPainterPath()
        path.moveTo(x + w * 0.10, y + w * 0.05)
        path.lineTo(x + w * 0.10, y + w * 0.95)
        path.lineTo(x + w * 0.95, s / 2)
        path.closeSubpath()
        p.drawPath(path)
    elif name == "stop":
        p.drawRoundedRect(QRectF(s * 0.26, s * 0.26, s * 0.48, s * 0.48), 2, 2)
    elif name == "trash":
        p.drawLine(QPointF(x + w * 0.05, y + w * 0.20), QPointF(x + w * 0.95, y + w * 0.20))
        p.drawLine(QPointF(s * 0.36, y + w * 0.05), QPointF(s * 0.64, y + w * 0.05))
        p.drawPolyline(QPolygonF([QPointF(x + w * 0.18, y + w * 0.20),
                                  QPointF(x + w * 0.25, y + w * 0.95),
                                  QPointF(x + w * 0.75, y + w * 0.95),
                                  QPointF(x + w * 0.82, y + w * 0.20)]))
    elif name == "up":
        cy = s / 2
        p.drawLine(QPointF(cy, y + w * 0.90), QPointF(cy, y + w * 0.10))
        p.drawPolyline(QPolygonF([QPointF(x + w * 0.22, cy * 0.85),
                                  QPointF(cy, y + w * 0.10),
                                  QPointF(x + w * 0.78, cy * 0.85)]))
    elif name == "down":
        cy = s / 2
        p.drawLine(QPointF(cy, y + w * 0.10), QPointF(cy, y + w * 0.90))
        p.drawPolyline(QPolygonF([QPointF(x + w * 0.22, s - cy * 0.85),
                                  QPointF(cy, y + w * 0.90),
                                  QPointF(x + w * 0.78, s - cy * 0.85)]))
    elif name == "plus":
        p.drawLine(QPointF(s / 2, y + w * 0.05), QPointF(s / 2, y + w * 0.95))
        p.drawLine(QPointF(x + w * 0.05, s / 2), QPointF(x + w * 0.95, s / 2))
    elif name == "refresh":
        p.drawArc(QRectF(x, y, w, w), 45 * 16, 280 * 16)
        p.drawPolyline(QPolygonF([QPointF(x + w * 0.80, y),
                                  QPointF(x + w, y + w * 0.05),
                                  QPointF(x + w * 0.86, y + w * 0.24)]))
    elif name == "file":
        p.drawRoundedRect(QRectF(x + w * 0.14, y, w * 0.72, w), 2, 2)
        p.drawLine(QPointF(s / 2, y + w * 0.24), QPointF(s / 2, y + w * 0.76))
    elif name == "terminal":
        cy = s / 2
        p.drawPolyline(QPolygonF([QPointF(x + w * 0.06, cy - w * 0.20),
                                  QPointF(cy * 0.86, cy + w * 0.06),
                                  QPointF(x + w * 0.06, cy + w * 0.34)]))
        p.drawLine(QPointF(cy * 1.10, cy + w * 0.34), QPointF(x + w * 0.96, cy + w * 0.34))
    elif name == "check":
        p.drawPolyline(QPolygonF([QPointF(x + w * 0.10, s * 0.52),
                                  QPointF(s * 0.42, s * 0.74),
                                  QPointF(x + w * 0.96, s * 0.24)]))
    elif name == "info":
        # 圆圈只描边，实心的话整块糊成一坨
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QRectF(x, y, w, w))
        p.setBrush(QColor(color))
        p.drawLine(QPointF(s / 2, s * 0.44), QPointF(s / 2, s * 0.76))
        p.drawLine(QPointF(s / 2, s * 0.26), QPointF(s / 2, s * 0.30))
    p.end()
    return pm


def make_icon(name: str, color: str, size: int = 18) -> QIcon:
    return QIcon(make_pixmap(name, color, size))


def icon_label(name: str, color: str = theme.TEXT_MUTED, size: int = 16) -> QLabel:
    lab = QLabel()
    lab.setPixmap(make_pixmap(name, color, size))
    lab.setFixedSize(size, size)
    lab.setAttribute(Qt.WA_TranslucentBackground, True)
    return lab


# ============================================================
# 卡片
# ============================================================
class Card(QFrame):
    """圆角白卡片，内容加到 .body 布局里。"""

    def __init__(self, title="", subtitle="", icon=None, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(0)

        self._outer = outer
        self.actions_widget = None
        if title:
            self._build_header(title, subtitle, icon)

        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(10)
        outer.addLayout(self.body)

    def _build_header(self, title, subtitle, icon):
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(10)

        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(3)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(8)
        if icon:
            title_row.addWidget(icon_label(icon, theme.TEXT_MUTED, 16))
        lab = QLabel(title)
        lab.setObjectName("CardTitle")
        title_row.addWidget(lab)
        title_row.addStretch(1)
        left.addLayout(title_row)

        if subtitle:
            sub = QLabel(subtitle)
            sub.setObjectName("CardSubtitle")
            sub.setWordWrap(True)
            left.addWidget(sub)

        rl.addLayout(left, 1)

        self.actions_widget = QWidget()
        self.actions = QHBoxLayout(self.actions_widget)
        self.actions.setContentsMargins(0, 0, 0, 0)
        self.actions.setSpacing(6)
        rl.addWidget(self.actions_widget, 0, Qt.AlignTop)

        self._outer.addWidget(row)
        self._outer.addSpacing(14)

    def add(self, widget, stretch=0):
        self.body.addWidget(widget, stretch)
        return widget

    def add_layout(self, layout, stretch=0):
        self.body.addLayout(layout, stretch)
        return layout

    def add_row(self, spacing=10):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(spacing)
        self.body.addLayout(row)
        return row


# ============================================================
# 徽标
# ============================================================
class Badge(QLabel):
    def __init__(self, text="", level="muted", dot=False, parent=None):
        super().__init__(parent)
        self.setObjectName("Badge")
        self.setAlignment(Qt.AlignCenter)
        self.setFixedHeight(22)
        self.set_level(level)
        self.set_text(text, dot)

    def set_level(self, level: str):
        self._level = level
        bg, fg = theme.BADGE_LEVELS.get(level, theme.BADGE_LEVELS["muted"])
        self.setStyleSheet(f"background: {bg}; color: {fg}; border-radius: 11px;"
                           f" padding: 3px 10px; font-size: 9pt;")

    def set_text(self, text: str, dot=False):
        self.setText(("●  " if dot else "") + text)

    def set_state(self, text=None, level=None, dot=False):
        if level is not None:
            self.set_level(level)
        if text is not None:
            self.set_text(text, dot)


# ============================================================
# 分段控件
# ============================================================
class Segmented(QFrame):
    """少量互斥选项的分段选择器。"""

    changed = Signal(str)

    def __init__(self, options, value=None, parent=None, min_width=0):
        super().__init__(parent)
        self.setObjectName("Segmented")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(4)

        self._value = value if value is not None else (options[0][0] if options else None)
        self._buttons = {}
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        for key, label in options:
            btn = QPushButton(label)
            btn.setObjectName("SegButton")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setChecked(key == self._value)
            if min_width:
                btn.setMinimumWidth(min_width)
            btn.clicked.connect(lambda _c, k=key: self._on_click(k))
            self._group.addButton(btn)
            self._buttons[key] = btn
            lay.addWidget(btn)

    def _on_click(self, key):
        if key == self._value:
            return
        self._value = key
        self.changed.emit(key)

    def get(self):
        return self._value

    def set(self, value, emit=False):
        if value == self._value:
            return
        self._value = value
        btn = self._buttons.get(value)
        if btn is not None:
            btn.setChecked(True)
        if emit:
            self.changed.emit(value)


# ============================================================
# 统计块
# ============================================================
class StatChip(QFrame):
    def __init__(self, label, parent=None):
        super().__init__(parent)
        self.setObjectName("StatChip")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 8, 14, 8)
        lay.setSpacing(1)
        self.value = QLabel("--")
        self.value.setObjectName("StatValue")
        self.caption = QLabel(label)
        self.caption.setObjectName("StatLabel")
        lay.addWidget(self.value)
        lay.addWidget(self.caption)

    def set_value(self, text):
        self.value.setText(str(text))


# ============================================================
# 侧边栏
# ============================================================
class NavButton(QPushButton):
    def __init__(self, key, label, icon, parent=None):
        super().__init__("  " + label, parent)
        self.setObjectName("NavButton")
        self.key = key
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setIcon(make_icon(icon, theme.SIDEBAR_TEXT, 18))
        self.setIconSize(self.iconSize().expandedTo(self.iconSize()))
        self.setMinimumHeight(40)


class StatusChip(QFrame):
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("StatusChip")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(54)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(10)

        self.dot = QLabel("●")
        self.dot.setObjectName("ChipDot")
        self.dot.setStyleSheet(f"color: {theme.CONSOLE_MUTED}; font-size: 11pt;")
        lay.addWidget(self.dot, 0, Qt.AlignVCenter)

        box = QVBoxLayout()
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(1)
        self.title = QLabel("ffmpeg 未检测")
        self.title.setObjectName("ChipTitle")
        self.sub = QLabel("点击前往设置")
        self.sub.setObjectName("ChipSub")
        box.addWidget(self.title)
        box.addWidget(self.sub)
        lay.addLayout(box, 1)

    def set_state(self, level, title, sub=""):
        colors = {"ok": theme.SUCCESS, "warn": theme.WARN,
                  "error": theme.DANGER, "muted": theme.CONSOLE_MUTED}
        self.dot.setStyleSheet(
            f"color: {colors.get(level, theme.CONSOLE_MUTED)}; font-size: 11pt;")
        self.title.setText(title)
        self.sub.setText(sub)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


# ============================================================
# 日志台
# ============================================================
class LogPanel(QFrame):
    toggle_requested = Signal()
    clear_requested = Signal()

    COLORS = {
        "info": theme.CONSOLE_TEXT,
        "muted": theme.CONSOLE_MUTED,
        "ok": theme.CONSOLE_OK,
        "warn": theme.CONSOLE_WARN,
        "error": theme.CONSOLE_ERR,
        "info_accent": theme.CONSOLE_INFO,
    }

    def __init__(self, height=theme.CONSOLE_HEIGHT, parent=None):
        super().__init__(parent)
        self.setObjectName("LogPanel")
        self._height = height
        self._collapsed = False
        self.setFixedHeight(height)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ---- 标题栏
        header = QFrame()
        header.setObjectName("LogHeader")
        header.setFixedHeight(theme.CONSOLE_HEADER)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(14, 0, 10, 0)
        hl.setSpacing(10)

        hl.addWidget(icon_label("terminal", theme.CONSOLE_MUTED, 15))
        title = QLabel("运行日志")
        title.setObjectName("LogTitle")
        hl.addWidget(title)

        self.status = QLabel("就绪")
        self.status.setObjectName("LogStatus")
        hl.addWidget(self.status)
        hl.addStretch(1)

        self.btn_toggle = QPushButton("收起")
        self.btn_toggle.setObjectName("ConsoleButton")
        self.btn_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_toggle.clicked.connect(self.toggle_requested.emit)
        hl.addWidget(self.btn_toggle)

        btn_clear = QPushButton("清空")
        btn_clear.setObjectName("ConsoleButton")
        btn_clear.setCursor(Qt.PointingHandCursor)
        btn_clear.clicked.connect(self.clear_requested.emit)
        hl.addWidget(btn_clear)

        outer.addWidget(header)

        sep = QFrame()
        sep.setObjectName("LogSep")
        sep.setFixedHeight(1)
        outer.addWidget(sep)

        self.view = QPlainTextEdit()
        self.view.setObjectName("LogView")
        self.view.setReadOnly(True)
        self.view.setFrameStyle(QFrame.NoFrame)
        self.view.setFont(theme.mono_font(9))
        self.view.setMaximumBlockCount(5000)
        outer.addWidget(self.view, 1)

        self.set_level("muted", "就绪")

    # --------------------------------------------------
    def log(self, message: str, level: str = "info"):
        color = self.COLORS.get(level, self.COLORS["info"])
        escaped = (message.replace("&", "&amp;").replace("<", "&lt;")
                   .replace(">", "&gt;").replace(" ", "&nbsp;"))
        self.view.appendHtml(f'<span style="color:{color};">{escaped}</span>')
        bar = self.view.verticalScrollBar()
        bar.setValue(bar.maximum())

    def clear(self):
        self.view.clear()

    def set_level(self, level: str, text: str):
        colors = {"muted": theme.CONSOLE_MUTED, "ok": theme.CONSOLE_OK,
                  "warn": theme.CONSOLE_WARN, "error": theme.CONSOLE_ERR,
                  "info": theme.CONSOLE_INFO}
        self.status.setText(text)
        self.status.setStyleSheet(
            f"color: {colors.get(level, theme.CONSOLE_MUTED)}; font-size: 9pt;")

    def set_collapsed(self, collapsed: bool):
        self._collapsed = collapsed
        self.setFixedHeight(theme.CONSOLE_HEADER if collapsed else self._height)
        self.view.setVisible(not collapsed)
        self.btn_toggle.setText("展开" if collapsed else "收起")

    @property
    def collapsed(self):
        return self._collapsed


# ============================================================
# 小工具
# ============================================================
def divider(bg=theme.BORDER, height=1) -> QFrame:
    line = QFrame()
    line.setFixedHeight(height)
    line.setStyleSheet(f"background: {bg}; border: none;")
    return line


def page_title(text):
    lab = QLabel(text)
    lab.setObjectName("PageTitle")
    return lab


def page_subtitle(text):
    lab = QLabel(text)
    lab.setObjectName("PageSubtitle")
    return lab


def field_label(text, width=None):
    lab = QLabel(text)
    lab.setObjectName("FieldLabel")
    if width:
        lab.setFixedWidth(width)
    return lab


def hint(text):
    lab = QLabel(text)
    lab.setObjectName("Hint")
    lab.setWordWrap(True)
    return lab


def make_brand_mark(size: int = 38) -> QPixmap:
    """左上角品牌方块：蓝色圆角 + 播放三角。"""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(theme.PRIMARY))
    p.drawRoundedRect(QRectF(0, 0, size, size), size * 0.29, size * 0.29)
    p.setBrush(QColor("#FFFFFF"))
    cx, cy, r = size / 2.0, size / 2.0, size * 0.21
    path = QPainterPath()
    path.moveTo(cx - r * 0.55, cy - r)
    path.lineTo(cx - r * 0.55, cy + r)
    path.lineTo(cx + r, cy)
    path.closeSubpath()
    p.drawPath(path)
    p.end()
    return pm


def make_button(text, kind="SecondaryButton", icon=None, icon_color=None):
    btn = QPushButton(text)
    btn.setObjectName(kind)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setMinimumHeight(34)
    if icon:
        color = icon_color or (theme.TEXT_ON if kind in ("PrimaryButton", "DangerButton")
                               else theme.TEXT_SUB)
        btn.setIcon(make_icon(icon, color, 16))
        btn.setIconSize(btn.iconSize())
    return btn


# ============================================================
# 底部操作条
# ============================================================
class ActionBar(QFrame):
    """页面底部的操作条：左边按钮、右边进度与状态。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ActionBar")
        self.setFixedHeight(64)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 0, 20, 0)
        lay.setSpacing(10)

        self.buttons = QHBoxLayout()
        self.buttons.setContentsMargins(0, 0, 0, 0)
        self.buttons.setSpacing(10)
        lay.addLayout(self.buttons)
        lay.addStretch(1)

        self.progress = QProgressBar()
        self.progress.setFixedHeight(8)
        self.progress.setTextVisible(False)
        self.progress.setMinimumWidth(260)
        lay.addWidget(self.progress, 3)

        self.status = QLabel("尚未开始")
        self.status.setObjectName("ActionStatus")
        self.status.setMinimumWidth(140)
        self.status.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay.addWidget(self.status)

    def add_button(self, widget):
        self.buttons.addWidget(widget)
        return widget

    def set_status(self, text, level="muted"):
        colors = {"muted": theme.TEXT_MUTED, "ok": theme.SUCCESS_TEXT,
                  "warn": theme.WARN_TEXT, "error": theme.DANGER_TEXT,
                  "info": theme.PRIMARY_TEXT}
        self.status.setText(text)
        self.status.setStyleSheet(
            f"color: {colors.get(level, theme.TEXT_MUTED)}; font-size: 9pt;")

    def set_progress(self, percent, color=None):
        if percent is None or percent < 0:
            self.progress.setRange(0, 0)          # 不确定态
            return
        self.progress.setRange(0, 1000)
        self.progress.setValue(int(percent * 1000))
        if color:
            self.progress.setStyleSheet(
                f"QProgressBar::chunk {{ background: {color}; border-radius: 4px; }}")