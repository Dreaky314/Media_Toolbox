# -*- coding: utf-8 -*-
"""番剧整理页（Qt）：扫描预览 + 重命名/复制/移动执行。"""

import os

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QFileDialog,
                               QGridLayout, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QScrollArea, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from core import osutil
from core import rename as core_rename
from core.ffmpeg import format_size

from . import theme, widgets
from .main_window import Page

ACTION_HINT = {
    core_rename.ACTION_COPY: "保留子文件夹里的原文件，并在目标目录留下整齐的一份",
    core_rename.ACTION_MOVE: "原位置的文件会被移走，最省磁盘空间",
    core_rename.ACTION_RENAME: "不产生新文件，只修改每个子文件夹内视频的名字",
}

STATUS_COLOR = {
    "info": theme.TEXT,
    "ok": theme.SUCCESS_TEXT,
    "warn": theme.WARN_TEXT,
    "error": theme.DANGER_TEXT,
    "muted": theme.TEXT_MUTED,
}


class _Events(QObject):
    step = Signal(object)
    error = Signal(object)
    done = Signal(object)


class RenamePage(Page):
    title = "番剧整理"
    subtitle = "把每集子文件夹里的视频按集数重命名，再复制或移动到番剧根目录"

    def __init__(self, window):
        super().__init__(window)
        self.result = None
        self.runner = None
        self._last_percent = 0.0

        self.events = _Events()
        self.events.step.connect(self._on_step)
        self.events.error.connect(self._on_error)
        self.events.done.connect(self._on_done)

        self._build()
        self._refresh_rules_state()

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
        body.setContentsMargins(20, 16, 20, 16)
        body.setSpacing(14)

        body.addWidget(self._build_source_card())
        body.addWidget(self._build_rules_card())
        body.addWidget(self._build_preview_card(), 1)
        scroll.setWidget(holder)
        outer.addWidget(scroll, 1)

        self.action_bar = widgets.ActionBar()
        self.btn_start = widgets.make_button("开始整理", "PrimaryButton", "play")
        self.btn_start.clicked.connect(self.start)
        self.btn_stop = widgets.make_button("停止", "SecondaryButton", "stop")
        self.btn_stop.clicked.connect(self.stop)
        self.btn_stop.setEnabled(False)
        self.action_bar.add_button(self.btn_start)
        self.action_bar.add_button(self.btn_stop)
        outer.addWidget(self.action_bar)

    # -------------------------------------------------- 目录
    def _build_source_card(self):
        card = widgets.Card("番剧根目录",
                            "每一集放在一个以数字命名的子文件夹里，例如 1 / 02 / 12",
                            icon="folder")
        row = card.add_row()
        self.edit_root = QLineEdit()
        self.edit_root.setPlaceholderText(r"例如 D:\Anime\某番剧")
        self.edit_root.setFont(theme.mono_font(10))
        self.edit_root.returnPressed.connect(self.scan)
        row.addWidget(self.edit_root, 1)
        btn_browse = widgets.make_button("浏览…", "SecondaryButton", "folder")
        btn_browse.clicked.connect(self.pick_root)
        row.addWidget(btn_browse)
        btn_scan = widgets.make_button("扫描", "SoftButton", "refresh")
        btn_scan.clicked.connect(self.scan)
        row.addWidget(btn_scan)
        return card

    # -------------------------------------------------- 规则
    def _build_rules_card(self):
        card = widgets.Card("整理规则", "改动前会先给出预览，确认无误再执行",
                            icon="settings")
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(14)
        grid.setColumnMinimumWidth(0, 72)
        grid.setColumnStretch(1, 1)

        # 集数位数 + 正片选择
        grid.addWidget(widgets.field_label("集数位数"), 0, 0, Qt.AlignTop)
        row0 = QHBoxLayout()
        row0.setSpacing(10)
        self.seg_width = widgets.Segmented(
            [("auto", "自动"), ("2", "固定 2 位"), ("3", "固定 3 位")], "auto")
        self.seg_width.changed.connect(lambda _v: self._refresh_rules_state())
        row0.addWidget(self.seg_width)
        row0.addSpacing(18)
        row0.addWidget(widgets.field_label("正片选择"))
        self.seg_pick = widgets.Segmented(
            [("first", "取第一个"), ("largest", "取体积最大的")], "first")
        row0.addWidget(self.seg_pick)
        row0.addStretch(1)
        grid.addLayout(row0, 0, 1)

        # 处理方式
        grid.addWidget(widgets.field_label("处理方式"), 1, 0, Qt.AlignTop)
        box1 = QVBoxLayout()
        box1.setSpacing(7)
        self.seg_action = widgets.Segmented(
            [(core_rename.ACTION_COPY, "复制到目标目录"),
             (core_rename.ACTION_MOVE, "移动到目标目录"),
             (core_rename.ACTION_RENAME, "仅重命名")],
            core_rename.ACTION_COPY)
        self.seg_action.changed.connect(self._set_action)
        holder1 = QHBoxLayout()
        holder1.addWidget(self.seg_action)
        holder1.addStretch(1)
        box1.addLayout(holder1)
        self.lbl_action_hint = widgets.hint(ACTION_HINT[core_rename.ACTION_COPY])
        box1.addWidget(self.lbl_action_hint)
        grid.addLayout(box1, 1, 1)

        # 目标目录
        grid.addWidget(widgets.field_label("目标目录"), 2, 0, Qt.AlignTop)
        box2 = QVBoxLayout()
        box2.setSpacing(6)
        row2 = QHBoxLayout()
        row2.setSpacing(10)
        self.edit_out = QLineEdit()
        self.edit_out.setFont(theme.mono_font(10))
        row2.addWidget(self.edit_out, 1)
        btn_out = widgets.make_button("浏览…", "SecondaryButton")
        btn_out.clicked.connect(self.pick_out)
        row2.addWidget(btn_out)
        box2.addLayout(row2)
        self.lbl_out_hint = widgets.hint("留空则输出到番剧根目录")
        box2.addWidget(self.lbl_out_hint)
        grid.addLayout(box2, 2, 1)

        card.add_layout(grid)
        card.body.addSpacing(4)

        # 同步重命名源文件
        self.chk_inplace = QCheckBox("同时把子文件夹里的源文件重命名为集数名")
        self.chk_inplace.setChecked(True)
        card.body.addWidget(self.chk_inplace)
        card.body.addWidget(widgets.hint(
            "开启后，1/EP01.mp4 会先改名为 1/01.mp4 再复制出去"))
        return card

    # -------------------------------------------------- 预览
    def _build_preview_card(self):
        card = widgets.Card("处理预览", "先扫描，确认清单后再执行", icon="file")
        self.badge_preview = widgets.Badge("未扫描", "muted", dot=True)
        if card.actions_widget is not None:
            card.actions.addWidget(self.badge_preview)

        stats = QHBoxLayout()
        stats.setSpacing(10)
        self.stat_chips = {}
        for key, label in (("episodes", "集数"), ("ready", "待处理"),
                           ("skip", "跳过"), ("size", "合计体积")):
            chip = widgets.StatChip(label)
            self.stat_chips[key] = chip
            stats.addWidget(chip)
        stats.addStretch(1)
        card.add_layout(stats)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["集数", "子文件夹", "源文件", "新文件名", "大小", "状态"])
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setDefaultSectionSize(30)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        for index, width in enumerate((64, 120, 260, 140, 90, 230)):
            self.table.setColumnWidth(index, width)
        self.table.setMinimumHeight(220)
        self.table.doubleClicked.connect(self._open_folder)
        card.add(self.table, 1)
        return card

    # -------------------------------------------------- 交互
    def pick_root(self):
        path = QFileDialog.getExistingDirectory(self, "选择番剧根目录")
        if path:
            self.edit_root.setText(path)
            self.scan()

    def pick_out(self):
        path = QFileDialog.getExistingDirectory(self, "选择目标目录")
        if path:
            self.edit_out.setText(path)

    def _set_action(self, value):
        # 也要同步分段控件，否则外部改值后界面与内部状态会不一致
        self.seg_action.set(value)
        self.lbl_action_hint.setText(ACTION_HINT.get(value, ""))
        self._refresh_rules_state()

    def _refresh_rules_state(self):
        action = self.seg_action.get()
        enabled = action in (core_rename.ACTION_COPY, core_rename.ACTION_MOVE)
        self.edit_out.setEnabled(enabled)
        self.lbl_out_hint.setText(
            "留空则输出到番剧根目录" if enabled else "仅重命名模式下不需要目标目录")

    def _open_folder(self, index):
        if not self.result:
            return
        try:
            episode = self.result.episodes[index.row()]
        except IndexError:
            return
        ok, detail = osutil.open_folder(episode.folder_path)
        if not ok:
            self.window.log(f"打开目录失败：{detail}", "error")

    # -------------------------------------------------- 扫描
    def scan(self):
        root = core_rename.clean_path(self.edit_root.text())
        if not root:
            self.window.notify("提示", "请先选择番剧根目录", "warn")
            return
        if not os.path.isdir(root):
            self.window.notify("目录不存在", f"找不到这个目录：\n{root}", "error")
            return

        width_value = self.seg_width.get()
        try:
            self.result = core_rename.scan(
                root,
                action=self.seg_action.get(),
                out_dir=core_rename.clean_path(self.edit_out.text()),
                width_mode="auto" if width_value == "auto" else "fixed",
                fixed_width=2 if width_value == "auto" else int(width_value),
                pick=self.seg_pick.get(),
                rename_in_place=self.chk_inplace.isChecked())
        except ValueError as e:
            self.result = None
            self.table.setRowCount(0)
            self._update_summary(None)
            self.window.notify("扫描失败", str(e), "error")
            self.window.log(f"[扫描失败] {e}", "error")
            return

        self._fill_table()
        self._update_summary(self.result)
        self.window.log(
            f"已扫描「{os.path.basename(self.result.root)}」："
            f"{len(self.result.episodes)} 个数字子文件夹，"
            f"就绪 {len(self.result.ready)} 集，补零位数 {self.result.width} 位", "ok")
        if self.result.ignored_dirs:
            self.window.log("忽略的非数字目录：" + "、".join(self.result.ignored_dirs),
                            "muted")

    def _fill_table(self):
        episodes = self.result.episodes
        self.table.setRowCount(len(episodes))
        for row, ep in enumerate(episodes):
            values = [
                str(ep.number),
                ep.folder_name,
                ep.source_name or "--",
                ep.target_name or "--",
                format_size(ep.size) if ep.size else "--",
                ep.status_text + (f"（{ep.note}）" if ep.note else ""),
            ]
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                if col == 0:
                    item.setTextAlignment(Qt.AlignCenter)
                elif col == 4:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                color = QColor(STATUS_COLOR.get(ep.status_level, theme.TEXT))
                if col == 5:
                    item.setForeground(color)
                elif ep.status_level in ("warn", "error", "muted"):
                    item.setForeground(QColor(STATUS_COLOR[ep.status_level]))
                self.table.setItem(row, col, item)

    def _update_summary(self, result):
        if result is None:
            for chip in self.stat_chips.values():
                chip.set_value("--")
            self.badge_preview.set_state("未扫描", "muted", dot=True)
            return
        ready = len(result.ready)
        self.stat_chips["episodes"].set_value(len(result.episodes))
        self.stat_chips["ready"].set_value(ready)
        self.stat_chips["skip"].set_value(len(result.episodes) - ready)
        self.stat_chips["size"].set_value(format_size(result.total_bytes))
        if ready == 0:
            self.badge_preview.set_state("无可处理项", "warn", dot=True)
        else:
            self.badge_preview.set_state(f"就绪 {ready} 集", "ok", dot=True)

    # -------------------------------------------------- 执行
    def start(self):
        if self.runner and self.runner.is_running():
            self.window.notify("提示", "已有任务在执行", "warn")
            return
        if self.result is None or not self.result.episodes:
            self.scan()
            if self.result is None:
                return
        if not self.result.ready:
            self.window.notify(
                "没有可处理的项",
                "当前清单里没有处于「待处理」状态的剧集。\n"
                "请检查子文件夹里是否有视频，或目标文件是否已存在。", "warn")
            return

        action = self.seg_action.get()
        message = (f"即将处理 {len(self.result.ready)} 集，"
                   f"{core_rename.ACTION_LABEL.get(action, action)}。\n"
                   f"补零位数：{self.result.width} 位\n"
                   f"目标目录：{self.result.out_dir}")
        if self.result.problems:
            message += (f"\n\n另有 {len(self.result.problems)} 项会被跳过"
                        f"（已存在的目标、命名冲突或无视频）。")
        if not self.window.confirm("确认执行", message):
            return

        self._last_percent = 0.0
        self.action_bar.set_progress(0)
        self.action_bar.set_status(f"0 / {len(self.result.ready)}", "info")
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.window.set_status("正在整理…", "info")
        self.window.log("-" * 64, "muted")
        self.window.log(f"开始整理：{core_rename.ACTION_LABEL.get(action)}"
                        f"（{len(self.result.ready)} 集）", "info_accent")

        self.runner = core_rename.OrganizeRunner(
            on_event=self._emit,
            on_done=lambda stats: self.events.done.emit(stats))
        self.runner.start(self.result, action=action,
                          rename_in_place=self.chk_inplace.isChecked())

    def stop(self):
        if self.runner and self.runner.is_running():
            self.runner.stop()
            self.window.log("已请求停止，正在收尾…", "warn")
            self.action_bar.set_status("正在停止…", "warn")

    def _emit(self, event):
        kind = event.get("type")
        if kind == "step":
            self.events.step.emit(event)
        elif kind == "error":
            self.events.error.emit(event)

    def _on_step(self, event):
        ep = event["episode"]
        done, total = event["index"], event["total"]
        self._last_percent = done / total if total else 0
        self.action_bar.set_progress(self._last_percent)
        self.action_bar.set_status(f"{done} / {total}", "info")
        self.window.log(f"[{done}/{total}] {ep.folder_name}/{ep.source_name}"
                        f"  ->  {ep.target_name}", "ok")

    def _on_error(self, event):
        ep = event.get("episode")
        name = ep.folder_name if ep else ""
        self.window.log(f"[失败] {name}：{event.get('message', '')}", "error")

    def _on_done(self, stats):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        ok = stats.get("ok", 0)
        failed = stats.get("failed", 0)
        if stats.get("stopped"):
            self.action_bar.set_progress(self._last_percent)
            self.action_bar.set_status(f"已停止，完成 {ok} 集", "warn")
            self.window.log(f"任务已停止：完成 {ok} 集，失败 {failed} 集", "warn")
        elif failed:
            self.action_bar.set_progress(1.0, theme.DANGER)
            self.action_bar.set_status(f"完成 {ok} 集，失败 {failed} 集", "error")
            self.window.log(f"整理结束：成功 {ok}，失败 {failed}", "error")
        else:
            self.action_bar.set_progress(1.0, theme.SUCCESS)
            self.action_bar.set_status(f"整理完成，共 {ok} 集", "ok")
            self.window.log(f"整理完成，共处理 {ok} 集", "ok")
        for line in stats.get("errors", []):
            self.window.log("  " + line, "error")
        self.scan()

    # --------------------------------------------------
    def on_show(self):
        if self.result is None and self.edit_root.text():
            self.scan()

    def shutdown(self):
        if self.runner and self.runner.is_running():
            self.runner.stop()
