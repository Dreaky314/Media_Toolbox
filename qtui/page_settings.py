# -*- coding: utf-8 -*-
"""设置页（Qt）：ffmpeg 路径与运行环境。"""

import os

from PySide6.QtWidgets import (QFileDialog, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QScrollArea, QVBoxLayout, QWidget)

from core import config as app_config
from core import ffmpeg as ff
from core.rename import clean_path

from . import theme, widgets
from .main_window import Page


class SettingsPage(Page):
    title = "设置"
    subtitle = "ffmpeg 是分片合并的必需依赖，这里可以指定它的位置"

    def __init__(self, window):
        super().__init__(window)
        self._build()
        self.refresh_display()

    # ------------------------------------------------------------
    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet(f"QScrollArea {{ background: {theme.BG}; border: none; }}")

        holder = QWidget()
        holder.setObjectName("PageBody")
        body = QVBoxLayout(holder)
        body.setContentsMargins(20, 16, 20, 20)
        body.setSpacing(14)
        body.addWidget(self._build_ffmpeg_card())
        body.addWidget(self._build_about_card())
        body.addStretch(1)
        scroll.setWidget(holder)
        outer.addWidget(scroll, 1)

    def _build_ffmpeg_card(self):
        card = widgets.Card("ffmpeg 位置", "合并分片时调用的可执行文件",
                            icon="terminal")
        self.badge = widgets.Badge("检测中…", "muted", dot=True)
        if card.actions_widget is not None:
            card.actions.addWidget(self.badge)

        self.edit_path = QLineEdit()
        self.edit_path.setFont(theme.mono_font(10))
        self.edit_path.returnPressed.connect(self.save_path)
        card.add(self.edit_path)

        row = QHBoxLayout()
        row.setSpacing(10)
        btn_save = widgets.make_button("保存路径", "PrimaryButton", "check")
        btn_save.clicked.connect(self.save_path)
        btn_browse = widgets.make_button("浏览…", "SecondaryButton", "folder")
        btn_browse.clicked.connect(self.pick)
        btn_auto = widgets.make_button("自动检测", "SecondaryButton", "refresh")
        btn_auto.clicked.connect(self.auto_detect)
        btn_test = widgets.make_button("测试可用性", "SecondaryButton", "info")
        btn_test.clicked.connect(self.test)
        for b in (btn_save, btn_browse, btn_auto, btn_test):
            row.addWidget(b)
        row.addStretch(1)
        card.add_layout(row)

        card.body.addSpacing(4)
        card.body.addWidget(widgets.divider())
        card.body.addSpacing(10)

        self.lbl_version = QLabel("尚未检测")
        self.lbl_version.setFont(theme.mono_font(9))
        self.lbl_version.setStyleSheet(f"color: {theme.TEXT_SUB};")
        self.lbl_version.setWordWrap(True)
        card.add(self.lbl_version)

        card.add(widgets.hint(
            "可以直接把 ffmpeg.exe 的完整路径粘贴到上面的输入框，再点「保存路径」；"
            "没有配置时会按下面的顺序自动查找。\n"
            "查找顺序：手动指定 → 程序目录的 ffmpeg/bin → 与本程序并列的"
            " ts文件合并/ffmpeg/bin → 系统 PATH。只想做番剧整理的话可以不配 ffmpeg。"))
        return card

    def _build_about_card(self):
        card = widgets.Card("关于", icon="info")
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        grid.setColumnMinimumWidth(0, 72)
        grid.setColumnStretch(1, 1)

        rows = [
            ("名称", f"{app_config.APP_NAME} v{app_config.APP_VERSION}"),
            ("功能", "番剧整理（按集数重命名并归档） + TS 分片合并（ffmpeg 无损拼接）"),
            ("界面", "PySide6 / Qt"),
            ("程序目录", str(app_config.app_dir())),
            ("配置文件", str(app_config.config_path())),
        ]
        for index, (key, value) in enumerate(rows):
            grid.addWidget(widgets.field_label(key), index, 0)
            lab = QLabel(value)
            lab.setWordWrap(True)
            grid.addWidget(lab, index, 1)
        card.add_layout(grid)
        return card

    # ------------------------------------------------------------
    def pick(self):
        path, _f = QFileDialog.getOpenFileName(
            self, "选择 ffmpeg 可执行文件", "",
            "可执行文件 (*.exe);;所有文件 (*)" if os.name == "nt" else "所有文件 (*)")
        if path:
            self._apply_path(path)

    def save_path(self):
        path = clean_path(self.edit_path.text())
        if not path:
            self.window.notify("路径为空",
                               "请填写 ffmpeg 可执行文件的完整路径，\n"
                               r"例如 D:\ffmpeg\bin\ffmpeg.exe", "warn")
            return
        if not os.path.isfile(path):
            self.window.notify("文件不存在", f"找不到这个文件：\n{path}", "error")
            self.window.log(f"保存失败，文件不存在：{path}", "error")
            return
        self._apply_path(path)

    def _apply_path(self, path):
        ok, info = ff.test_ffmpeg(path)
        if not ok and not self.window.confirm(
                "测试失败", f"这个文件似乎不是可用的 ffmpeg：\n{info}\n\n仍然保存吗？"):
            return
        if ff.set_ffmpeg_path(path):
            self.edit_path.setText(path)
            self.window.log(f"已保存 ffmpeg 路径：{path}", "ok")
            self.window.log(f"  写入 {app_config.config_path()}", "muted")
            self.window.notify("已保存",
                               f"ffmpeg 路径已写入配置文件：\n"
                               f"{app_config.config_path()}")
        else:
            self.window.notify("保存失败", "配置文件不可写，请检查程序目录权限。", "error")
            return
        self.window.detect_ffmpeg()

    def auto_detect(self):
        ff.set_ffmpeg_path("")
        path = ff.get_ffmpeg_path()
        self.edit_path.setText(path)
        self.window.log(f"已清除手动路径，恢复自动检测，当前解析到：{path}", "info")
        self.window.detect_ffmpeg()

    def test(self):
        path = clean_path(self.edit_path.text())
        ok, info = ff.test_ffmpeg(path)
        if ok:
            self.window.notify("测试通过", f"ffmpeg 可用：\n{info}")
            self.window.log(f"ffmpeg 测试通过：{info}", "ok")
        else:
            self.window.notify("测试失败", f"ffmpeg 不可用：\n{info}", "error")
            self.window.log(f"ffmpeg 测试失败：{info}", "error")

    # ------------------------------------------------------------
    def refresh_display(self):
        self.edit_path.setText(ff.get_ffmpeg_path())

    def on_show(self):
        self.refresh_display()
        self.on_ffmpeg_changed(self.window.ffmpeg_ok, self.window.ffmpeg_path,
                               self.window.ffmpeg_info)

    def on_ffmpeg_changed(self, ok, path, info):
        if path:
            self.edit_path.setText(path)
        if ok:
            self.badge.set_state("可用", "ok", dot=True)
            self.lbl_version.setText(info)
        else:
            self.badge.set_state("不可用", "error", dot=True)
            self.lbl_version.setText(f"当前不可用：{info}")
