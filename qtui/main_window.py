# -*- coding: utf-8 -*-
"""主窗口：侧边导航 + 页头 + 页面栈 + 共用日志面板。"""

import os
import sys
import threading

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel,
                               QMainWindow, QMessageBox, QStackedWidget,
                               QVBoxLayout, QWidget)

from core import config as app_config
from core import ffmpeg as ff

from . import theme, widgets


class Bridge(QObject):
    """把工作线程的回调安全地转成 UI 线程的信号。"""

    ffmpeg_ready = Signal(bool, str, str)
    generic = Signal(object)


class Page(QWidget):
    """页面基类。"""

    title = ""
    subtitle = ""

    def __init__(self, window):
        super().__init__()
        self.window = window
        self.setObjectName("PageBody")

    def header_actions(self):
        """可选：返回要放到页头右侧的控件列表。"""
        return []

    def on_show(self):
        pass

    def on_ffmpeg_changed(self, ok, path, info):
        pass

    def shutdown(self):
        pass


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{app_config.APP_NAME} · 番剧整理 + TS 分片合并")
        self.setStyleSheet(theme.build_qss())

        self.ffmpeg_ok = False
        self.ffmpeg_path = ""
        self.ffmpeg_info = "尚未检测"
        self.pages = {}
        self._page_keys = []
        self.current_page = None

        self.bridge = Bridge()
        self.bridge.ffmpeg_ready.connect(self._apply_ffmpeg)

        self._build()
        self._build_pages()
        self._apply_icon()
        self.show_page("rename")
        self._place_window()

        QTimer.singleShot(80, self.detect_ffmpeg)

    # ------------------------------------------------------------ 图标
    def _apply_icon(self):
        """窗口/任务栏图标。

        必须显式设在窗口上：只设 QApplication 时，Qt 不会把图标回填进
        已有窗口的 windowIcon()，打包后路径又变了，结果就是图标直接没有。
        """
        path = app_config.resource_path("assets", "app.ico")
        if path is None:
            return
        icon = QIcon(str(path))
        if icon.isNull():
            return
        self.setWindowIcon(icon)
        QApplication.setWindowIcon(icon)

    # ------------------------------------------------------------ 布局
    def _build(self):
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        outer.addWidget(self._build_sidebar())

        right = QWidget()
        right.setObjectName("Root")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)

        rl.addWidget(self._build_header())
        rl.addWidget(widgets.divider())

        self.stack = QStackedWidget()
        self.stack.setObjectName("ContentArea")
        rl.addWidget(self.stack, 1)

        self.log_panel = widgets.LogPanel()
        self.log_panel.clear_requested.connect(self.log_panel.clear)
        self.log_panel.toggle_requested.connect(
            lambda: self.log_panel.set_collapsed(not self.log_panel.collapsed))
        rl.addWidget(self.log_panel)

        outer.addWidget(right, 1)

    def _build_sidebar(self):
        side = QFrame()
        side.setObjectName("Sidebar")
        side.setFixedWidth(theme.SIDEBAR_WIDTH)
        lay = QVBoxLayout(side)
        lay.setContentsMargins(12, 0, 12, 16)
        lay.setSpacing(0)

        # ---- 品牌
        brand = QFrame()
        brand.setObjectName("SidebarBrand")
        brand.setFixedHeight(88)
        bl = QHBoxLayout(brand)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(10)

        # 品牌区：只有 logo 和名字，整体居中（不显示版本号）
        bl.addStretch(1)
        mark = QLabel()
        mark.setFixedSize(38, 38)
        mark.setPixmap(widgets.make_brand_mark(38))
        bl.addWidget(mark, 0, Qt.AlignVCenter)
        name = QLabel(app_config.APP_NAME)
        name.setObjectName("BrandName")
        bl.addWidget(name, 0, Qt.AlignVCenter)
        bl.addStretch(1)
        lay.addWidget(brand)

        # ---- 导航
        sec1 = QLabel("功能")
        sec1.setObjectName("NavSection")
        sec1.setContentsMargins(10, 12, 0, 6)
        lay.addWidget(sec1)

        self.nav_buttons = {}
        for key, label, icon in (("rename", "番剧整理", "folder"),
                                 ("merge", "分片合并", "merge")):
            lay.addWidget(self._make_nav(key, label, icon))

        sec2 = QLabel("其它")
        sec2.setObjectName("NavSection")
        sec2.setContentsMargins(10, 16, 0, 6)
        lay.addWidget(sec2)
        lay.addWidget(self._make_nav("settings", "设置", "settings"))

        lay.addStretch(1)

        # ---- 底部状态
        self.chip = widgets.StatusChip()
        self.chip.clicked.connect(lambda: self.show_page("settings"))
        lay.addWidget(self.chip)

        return side

    def _make_nav(self, key, label, icon):
        btn = widgets.NavButton(key, label, icon)
        btn.clicked.connect(lambda: self.show_page(key))
        self.nav_buttons[key] = btn
        return btn

    def _build_header(self):
        header = QFrame()
        header.setObjectName("HeaderBar")
        header.setFixedHeight(theme.HEADER_HEIGHT)
        lay = QHBoxLayout(header)
        lay.setContentsMargins(24, 0, 24, 0)
        lay.setSpacing(12)

        box = QVBoxLayout()
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(2)
        self.lbl_title = widgets.page_title("")
        self.lbl_subtitle = widgets.page_subtitle("")
        box.addWidget(self.lbl_title)
        box.addWidget(self.lbl_subtitle)
        lay.addLayout(box)
        lay.addStretch(1)

        self.header_actions = QWidget()
        self.header_actions_layout = QHBoxLayout(self.header_actions)
        self.header_actions_layout.setContentsMargins(0, 0, 0, 0)
        self.header_actions_layout.setSpacing(8)
        lay.addWidget(self.header_actions)

        return header

    def _place_window(self):
        screen = QApplication.primaryScreen().availableGeometry()
        width = min(1200, max(900, screen.width() - 60))
        height = min(880, max(620, screen.height() - 80))
        self.resize(width, height)
        self.setMinimumSize(min(1040, width), min(680, height))
        self.move(screen.x() + (screen.width() - width) // 2,
                  screen.y() + max(0, (screen.height() - height) // 3))

    # ------------------------------------------------------------ 页面
    def _build_pages(self):
        from .page_rename import RenamePage
        from .page_merge import MergePage
        from .page_settings import SettingsPage

        for key, cls in (("rename", RenamePage), ("merge", MergePage),
                         ("settings", SettingsPage)):
            page = cls(self)
            self.pages[key] = page
            self.stack.addWidget(page)
            self._page_keys.append(key)

    def show_page(self, key):
        if key not in self.pages:
            return
        page = self.pages[key]
        self.stack.setCurrentWidget(page)
        self.current_page = key

        for nav_key, btn in self.nav_buttons.items():
            btn.setChecked(nav_key == key)

        self.lbl_title.setText(page.title)
        self.lbl_subtitle.setText(page.subtitle)

        while self.header_actions_layout.count():
            item = self.header_actions_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        for w in page.header_actions():
            self.header_actions_layout.addWidget(w)

        page.on_show()

    # ------------------------------------------------------------ ffmpeg
    def detect_ffmpeg(self):
        path = ff.get_ffmpeg_path()
        self.ffmpeg_path = path
        self.chip.set_state("muted", "正在检测 ffmpeg…", os.path.basename(path))

        def worker():
            ok, info = ff.test_ffmpeg(path)
            self.bridge.ffmpeg_ready.emit(ok, path, info)

        threading.Thread(target=worker, daemon=True).start()

    def _apply_ffmpeg(self, ok, path, info):
        self.ffmpeg_ok = ok
        self.ffmpeg_path = path
        self.ffmpeg_info = info
        if ok:
            version = info.split(" Copyright")[0].replace("ffmpeg version ", "")
            self.chip.set_state("ok", "ffmpeg 已就绪", version[:32])
            self.set_status("ffmpeg 可用", "ok")
        else:
            self.chip.set_state("error", "ffmpeg 不可用", info[:32])
            self.set_status(f"ffmpeg 不可用：{info}", "error")
        for page in self.pages.values():
            try:
                page.on_ffmpeg_changed(ok, path, info)
            except Exception:
                pass

    # ------------------------------------------------------------ 通用
    def log(self, message: str, level: str = "info"):
        self.log_panel.log(message, level)

    def set_status(self, text: str, level: str = "muted"):
        self.log_panel.set_level(level, text)

    def notify(self, title: str, message: str, level: str = "info"):
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setText(message)
        box.setIcon({"error": QMessageBox.Critical,
                     "warn": QMessageBox.Warning}.get(level, QMessageBox.Information))
        box.setStandardButtons(QMessageBox.Ok)
        box.exec()

    def confirm(self, title: str, message: str) -> bool:
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setText(message)
        box.setIcon(QMessageBox.Question)
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.setDefaultButton(QMessageBox.No)
        return box.exec() == QMessageBox.Yes

    # ------------------------------------------------------------ 生命周期
    def closeEvent(self, event):
        for page in self.pages.values():
            try:
                page.shutdown()
            except Exception:
                pass
        super().closeEvent(event)


def run():
    app = QApplication(sys.argv)
    theme.init_fonts()
    app.setApplicationName(f"{app_config.APP_NAME}")
    app.setFont(theme.ui_font(10))
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "com.mediatoolkit.dsh")
        except Exception:
            pass
    icon_path = app_config.resource_path("assets", "app.ico")
    if icon_path is not None:
        icon = QIcon(str(icon_path))
        if not icon.isNull():
            app.setWindowIcon(icon)
    window = MainWindow()
    window.show()
    return app.exec()
