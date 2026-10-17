# -*- coding: utf-8 -*-
"""分片合并页（Qt）：分片列表管理 + 输出设置 + 带进度的 ffmpeg 执行。"""

import os
import shlex
import threading

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QFileDialog, QGridLayout,
                               QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                               QTableWidget, QTableWidgetItem, QVBoxLayout,
                               QWidget)

from core import config as app_config
from core import ffmpeg as ff
from core import merge as core_merge
from core import m3u8 as core_m3u8

from . import theme, widgets
from .main_window import Page

FORMATS = [("mp4", "MP4"), ("ts", "TS"), ("mkv", "MKV")]
MODES = [("copy", "直接拼接"), ("crf", "高质量重编码"), ("bitrate", "指定码率")]

MODE_HINT = {
    "copy": "直接复制码流，速度最快、画质无损；要求所有分片来自同一路流。",
    "crf": "重新编码以获得更好的兼容性，CRF 18 接近无损，但耗时会明显变长。",
    "bitrate": "重新编码并固定码率上限，适合需要控制文件体积的场景。",
}


class _Events(QObject):
    log = Signal(str, bool)
    progress = Signal(object, float, float)
    done = Signal(bool, str)
    duration = Signal(object, float, str)


class MergePage(Page):
    title = "分片合并"
    subtitle = "把 .ts 分片按顺序拼接为一个视频文件，支持从 m3u8 列表导入"

    def __init__(self, window):
        super().__init__(window)
        self.files = []
        self.runner = None
        self._m3u8_duration = 0.0
        self.total_seconds = 0.0
        self.duration_method = "unknown"
        self._probe_token = 0
        self._last_percent = 0.0
        self._last_dir = ""

        self.events = _Events()
        self.events.log.connect(self._on_log)
        self.events.progress.connect(self._on_progress)
        self.events.done.connect(self._on_done)
        self.events.duration.connect(self._on_duration)

        self._build()

    # ------------------------------------------------------------
    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        body = QWidget()
        body.setObjectName("PageBody")
        lay = QVBoxLayout(body)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(14)

        lay.addWidget(self._build_output_card())
        lay.addWidget(self._build_list_card(), 1)
        outer.addWidget(body, 1)

        self.action_bar = widgets.ActionBar()
        self.btn_start = widgets.make_button("开始合并", "PrimaryButton", "play")
        self.btn_start.clicked.connect(self.start)
        self.btn_stop = widgets.make_button("停止", "SecondaryButton", "stop")
        self.btn_stop.clicked.connect(self.stop)
        self.btn_stop.setEnabled(False)
        btn_cmd = widgets.make_button("查看命令", "GhostButton")
        btn_cmd.clicked.connect(self.show_command)
        for b in (self.btn_start, self.btn_stop, btn_cmd):
            self.action_bar.add_button(b)
        outer.addWidget(self.action_bar)

    # -------------------------------------------------- 输出设置
    def _build_output_card(self):
        card = widgets.Card("输出设置", icon="settings")
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(14)
        grid.setColumnMinimumWidth(0, 72)
        grid.setColumnStretch(1, 1)

        grid.addWidget(widgets.field_label("输出文件"), 0, 0)
        row0 = QHBoxLayout()
        row0.setSpacing(10)
        self.edit_out = QLineEdit()
        self.edit_out.setFont(theme.mono_font(10))
        row0.addWidget(self.edit_out, 1)
        btn_save = widgets.make_button("另存为…", "SecondaryButton")
        btn_save.clicked.connect(self.pick_output)
        row0.addWidget(btn_save)
        grid.addLayout(row0, 0, 1)

        grid.addWidget(widgets.field_label("输出格式"), 1, 0)
        row1 = QHBoxLayout()
        row1.setSpacing(10)
        self.seg_fmt = widgets.Segmented(FORMATS, "mp4")
        self.seg_fmt.changed.connect(self._on_format_change)
        row1.addWidget(self.seg_fmt)
        row1.addSpacing(20)
        row1.addWidget(widgets.field_label("编码方式"))
        self.seg_mode = widgets.Segmented(MODES, "copy")
        self.seg_mode.changed.connect(self._on_mode_change)
        row1.addWidget(self.seg_mode)

        self.bitrate_box = QWidget()
        bl = QHBoxLayout(self.bitrate_box)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(8)
        bl.addWidget(widgets.field_label("码率"))
        self.edit_bitrate = QLineEdit("8M")
        self.edit_bitrate.setFixedWidth(90)
        bl.addWidget(self.edit_bitrate)
        bl.addWidget(widgets.hint("如 4M / 2000k"))
        row1.addWidget(self.bitrate_box)
        row1.addStretch(1)
        grid.addLayout(row1, 1, 1)

        card.add_layout(grid)
        card.body.addSpacing(2)
        self.lbl_mode_hint = widgets.hint(MODE_HINT["copy"])
        card.body.addWidget(self.lbl_mode_hint)
        self._on_mode_change("copy")
        return card

    # -------------------------------------------------- 分片列表
    def _build_list_card(self):
        card = widgets.Card("待合并分片", "顺序即拼接顺序，可用「上移 / 下移」调整",
                            icon="merge")
        if card.actions_widget is not None:
            for text, icon, kind, slot in (
                ("清空", "trash", "GhostButton", self.clear_list),
                ("添加目录", "folder", "SecondaryButton", self.add_dir),
                ("添加文件", "plus", "SecondaryButton", self.add_files),
                ("从 m3u8 导入", "file", "SoftButton", self.import_m3u8),
            ):
                btn = widgets.make_button(text, kind, icon)
                btn.setMinimumHeight(30)
                btn.clicked.connect(slot)
                card.actions.addWidget(btn)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["序号", "文件名", "大小", "所在目录"])
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setDefaultSectionSize(30)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Fixed)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        for index, width in enumerate((64, 260, 100, 340)):
            self.table.setColumnWidth(index, width)
        self.table.setMinimumHeight(150)
        card.add(self.table, 1)

        footer = QHBoxLayout()
        footer.setSpacing(4)
        for text, icon, slot in (("上移", "up", self.move_up),
                                 ("下移", "down", self.move_down),
                                 ("删除选中", "trash", self.remove_selected),
                                 ("反转顺序", "refresh", self.reverse_list)):
            btn = widgets.make_button(text, "GhostButton", icon)
            btn.setMinimumHeight(30)
            btn.clicked.connect(slot)
            footer.addWidget(btn)
        footer.addStretch(1)
        self.lbl_duration = QLabel("")
        self.lbl_duration.setObjectName("Hint")
        self.lbl_summary = QLabel("还没有添加分片")
        self.lbl_summary.setObjectName("Hint")
        footer.addWidget(self.lbl_duration)
        footer.addSpacing(14)
        footer.addWidget(self.lbl_summary)
        card.add_layout(footer)
        return card

    # -------------------------------------------------- 列表操作
    def add_files(self):
        paths, _f = QFileDialog.getOpenFileNames(
            self, "选择 TS 分片", self._last_dir, "TS 分片 (*.ts);;所有文件 (*)")
        if not paths:
            return
        self._last_dir = os.path.dirname(paths[0])
        added = 0
        for path in paths:
            path = os.path.normpath(path)
            if path not in self.files:
                self.files.append(path)
                added += 1
        if not added:
            self.window.log("所选文件已经在列表里，未重复添加", "warn")
        self._refresh_list(reprobe=True)

    def add_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "选择包含 TS 的目录",
                                                     self._last_dir)
        if not directory:
            return
        self._last_dir = directory
        found = core_merge.list_ts_files(directory)
        recursive = False
        if not found:
            found = core_merge.list_ts_files(directory, recursive=True)
            recursive = bool(found)
        if not found:
            self.window.notify("没有找到分片", "该目录下没有 .ts 文件", "warn")
            return
        added = 0
        for path in found:
            if path not in self.files:
                self.files.append(path)
                added += 1
        self.window.log(f"从「{os.path.basename(directory)}」添加 {added} 个分片"
                        + ("（含子目录）" if recursive else ""), "ok")
        self._refresh_list(reprobe=True)

    def import_m3u8(self):
        path, _f = QFileDialog.getOpenFileName(
            self, "选择本地 m3u8 文件", self._last_dir,
            "M3U8 播放列表 (*.m3u8);;所有文件 (*)")
        if not path:
            return
        try:
            info = core_m3u8.parse_m3u8(path)
        except core_m3u8.M3U8Error as e:
            self.window.notify("解析失败", str(e), "error")
            return
        if info["is_master"]:
            self.window.notify("这是主列表",
                               "该 m3u8 是多码率主列表，它引用的是子 m3u8 而不是分片。\n"
                               "请选择具体的子 m3u8 文件。", "warn")
            return

        self.window.log("-" * 64, "muted")
        self.window.log(f"导入 m3u8：{path}", "info_accent")
        if info["encrypted"]:
            self.window.log("检测到加密标签 #EXT-X-KEY，本工具不解密，合并可能失败", "warn")
        if not info["has_endlist"]:
            self.window.log("列表里没有 #EXT-X-ENDLIST，可能是直播列表，内容可能不完整", "warn")

        missing = core_m3u8.missing_segments(info)
        if missing and not self.window.confirm(
                "有分片缺失",
                f"有 {len(missing)} 个分片在本地找不到，例如：\n{missing[0]}\n\n"
                f"是否仍然导入现有的分片？"):
            return
        if missing:
            self.window.log(f"有 {len(missing)} 个分片缺失，仍按现有分片导入", "warn")

        self.files = list(core_m3u8.resolve_segments(info, must_exist=False))
        self._m3u8_duration = float(info.get("duration") or 0.0)
        self._last_dir = info["dir"]
        base = os.path.splitext(os.path.basename(path))[0]
        self.edit_out.setText(os.path.join(info["dir"], f"{base}.{self.seg_fmt.get()}"))
        self._refresh_list(reprobe=False)
        self.window.log(f"共导入 {len(self.files)} 个分片，"
                        f"总时长约 {ff.format_duration(self._m3u8_duration)}", "ok")
        self._probe_duration()

    def remove_selected(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        if not rows:
            self.window.log("请先在列表里选中要删除的行", "warn")
            return
        for row in rows:
            if 0 <= row < len(self.files):
                self.files.pop(row)
        self._m3u8_duration = 0.0
        self._refresh_list(reprobe=True)

    def clear_list(self):
        if not self.files:
            return
        self.files = []
        self._m3u8_duration = 0.0
        self.edit_out.setText("")
        self._refresh_list(reprobe=True)
        self.window.log("已清空分片列表", "muted")

    def reverse_list(self):
        if len(self.files) < 2:
            return
        self.files.reverse()
        self._refresh_list(reprobe=False)
        self.window.log("已反转分片顺序", "muted")

    def _selected_rows(self):
        return sorted({i.row() for i in self.table.selectedIndexes()})

    def move_up(self):
        rows = self._selected_rows()
        if not rows or rows[0] == 0:
            return
        for row in rows:
            if row > 0:
                self.files[row - 1], self.files[row] = self.files[row], self.files[row - 1]
        self._refresh_list(reprobe=False)
        self._reselect([max(0, r - 1) for r in rows])

    def move_down(self):
        rows = self._selected_rows()
        last = len(self.files) - 1
        if not rows or rows[-1] >= last:
            return
        for row in reversed(rows):
            if row < last:
                self.files[row + 1], self.files[row] = self.files[row], self.files[row + 1]
        self._refresh_list(reprobe=False)
        self._reselect([min(last, r + 1) for r in rows])

    def _reselect(self, rows):
        self.table.clearSelection()
        for row in rows:
            if 0 <= row < self.table.rowCount():
                self.table.selectRow(row)
                self.table.scrollToItem(self.table.item(row, 0))

    # -------------------------------------------------- 刷新
    def _refresh_list(self, reprobe=True):
        self.table.setRowCount(len(self.files))
        total = 0
        missing = 0
        for row, path in enumerate(self.files):
            try:
                size = os.path.getsize(path)
            except OSError:
                size = 0
                missing += 1
            total += size
            values = (str(row + 1), os.path.basename(path),
                      ff.format_size(size), os.path.dirname(path))
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                if col == 0:
                    item.setTextAlignment(Qt.AlignCenter)
                elif col == 2:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if missing and not os.path.isfile(path):
                    item.setForeground(theme.color(theme.DANGER_TEXT))
                self.table.setItem(row, col, item)

        if not self.files:
            self.lbl_summary.setText("还没有添加分片")
            self.lbl_duration.setText("")
        else:
            text = f"共 {len(self.files)} 个分片 · 合计 {ff.format_size(total)}"
            if missing:
                text += f" · {missing} 个文件缺失"
            self.lbl_summary.setText(text)

        if reprobe:
            self._m3u8_duration = 0.0
            self._probe_duration()
        self._auto_output_name()

    def _auto_output_name(self):
        if self.files and not self.edit_out.text().strip():
            fmt = self.seg_fmt.get()
            self.edit_out.setText(
                os.path.join(os.path.dirname(self.files[0]), f"merged.{fmt}"))

    def _on_format_change(self, value):
        out = self.edit_out.text().strip()
        if out:
            base, _ext = os.path.splitext(out)
            self.edit_out.setText(f"{base}.{value}")

    def _on_mode_change(self, value):
        self.lbl_mode_hint.setText(MODE_HINT.get(value, ""))
        self.bitrate_box.setVisible(value == "bitrate")

    def pick_output(self):
        fmt = self.seg_fmt.get()
        path, _f = QFileDialog.getSaveFileName(
            self, "保存为", self.edit_out.text() or self._last_dir,
            f"{fmt.upper()} (*.{fmt});;所有文件 (*)")
        if not path:
            return
        self.edit_out.setText(path)
        ext = os.path.splitext(path)[1].lstrip(".").lower()
        if ext in ("mp4", "ts", "mkv"):
            self.seg_fmt.set(ext)

    # -------------------------------------------------- 时长探测
    def _probe_duration(self):
        if not self.files:
            self.total_seconds = 0.0
            self.duration_method = "unknown"
            self.lbl_duration.setText("")
            return
        self._probe_token += 1
        token = self._probe_token
        files = list(self.files)
        seconds = self._m3u8_duration
        self.lbl_duration.setText("正在读取时长…")

        def worker():
            try:
                total, method = ff.total_duration(files, m3u8_seconds=seconds)
            except Exception:
                total, method = 0.0, "unknown"
            self.events.duration.emit(token, total, method)

        threading.Thread(target=worker, daemon=True).start()

    def _on_duration(self, token, total, method):
        if token != self._probe_token:
            return
        self.total_seconds = total
        self.duration_method = method
        if total <= 0:
            self.lbl_duration.setText("时长未知")
        else:
            self.lbl_duration.setText(
                f"预计时长 {ff.format_duration(total)}"
                f"（{ff.DURATION_METHOD_TEXT.get(method, method)}）")

    # -------------------------------------------------- 执行
    def _collect_settings(self):
        mode = self.seg_mode.get()
        kwargs = {"mode": mode}
        if mode == "crf":
            kwargs["crf"] = 18
            kwargs["audio_bitrate"] = "192k"
        elif mode == "bitrate":
            kwargs["video_bitrate"] = self.edit_bitrate.text().strip() or "8M"
            kwargs["audio_bitrate"] = "192k"
        return kwargs

    def _build_cmd(self, list_path=None):
        return core_merge.build_ffmpeg_cmd(
            self.files, self.edit_out.text().strip(),
            list_path=list_path, **self._collect_settings())

    def start(self):
        if self.runner and self.runner.is_running():
            self.window.notify("提示", "已有任务在执行", "warn")
            return
        if not self.window.ffmpeg_ok:
            if self.window.confirm("ffmpeg 不可用",
                                   f"当前 ffmpeg 无法执行：\n{self.window.ffmpeg_info}\n\n"
                                   f"是否现在去设置它的路径？"):
                self.window.show_page("settings")
            return
        if not self.files:
            self.window.notify("还没有分片", "请先添加 .ts 文件，或从 m3u8 导入", "warn")
            return
        try:
            cmd, list_path = self._build_cmd()
        except ValueError as e:
            self.window.notify("无法开始", str(e), "error")
            return

        output = self.edit_out.text().strip()
        if os.path.exists(output) and not self.window.confirm(
                "文件已存在", f"{output}\n\n该文件已存在，合并会覆盖它，是否继续？"):
            try:
                os.remove(list_path)
            except OSError:
                pass
            return

        if self.total_seconds <= 0:
            self.window.set_status("正在读取分片时长…", "info")
            self.total_seconds, self.duration_method = ff.total_duration(
                self.files, m3u8_seconds=self._m3u8_duration)

        self.window.log("-" * 64, "muted")
        self.window.log(f"使用 ffmpeg：{cmd[0]}", "muted")
        self.window.log(" ".join(shlex.quote(p) for p in cmd), "muted")
        self.window.log(f"开始合并 {len(self.files)} 个分片 -> "
                        f"{os.path.basename(output)}", "info_accent")

        self._last_percent = 0.0
        self.action_bar.set_progress(0 if self.total_seconds > 0 else -1)
        self.action_bar.set_status("0%", "info")
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.window.set_status("正在合并…", "info")

        self.runner = core_merge.MergerRunner(
            on_log=lambda line, err: self.events.log.emit(line, err),
            on_progress=lambda sec, pct, spd: self.events.progress.emit(sec, pct, spd),
            on_done=lambda ok, msg: self.events.done.emit(ok, msg))
        self.runner.start(cmd, cleanup_path=list_path, duration=self.total_seconds)

    def stop(self):
        if self.runner and self.runner.is_running():
            self.window.log("正在停止 ffmpeg…", "warn")
            self.runner.stop()
            self.action_bar.set_status("正在停止…", "warn")

    def show_command(self):
        if not self.files:
            self.window.notify("还没有分片", "请先添加分片再查看命令", "warn")
            return
        try:
            cmd, list_path = self._build_cmd()
        except ValueError as e:
            self.window.notify("无法生成命令", str(e), "error")
            return
        try:
            os.remove(list_path)
        except OSError:
            pass
        self.window.notify("ffmpeg 命令", " ".join(shlex.quote(p) for p in cmd))

    def _on_log(self, line, is_error):
        self.window.log(line, "error" if is_error else "muted")

    def _on_progress(self, seconds, percent, speed):
        if percent is not None and percent >= 0:
            self._last_percent = percent
            self.action_bar.set_progress(percent)
            text = f"{percent * 100:.0f}%  ·  {ff.format_duration(seconds)}"
        else:
            self.action_bar.set_progress(-1)
            text = ff.format_duration(seconds)
        if speed:
            text += f"  ·  {speed:.1f}x"
        self.action_bar.set_status(text, "info")

    def _on_done(self, ok, message):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        output = self.edit_out.text().strip()
        if ok:
            size = os.path.getsize(output) if os.path.isfile(output) else 0
            self.action_bar.set_progress(1.0, theme.SUCCESS)
            self.action_bar.set_status("100%", "ok")
            self.window.set_status(f"合并完成 · {ff.format_size(size)}", "ok")
            self.window.log(f"合并完成：{output}", "ok")
            self.window.log(f"输出体积 {ff.format_size(size)}，"
                            f"时长 {ff.format_duration(ff.probe_duration(output))}", "ok")
            self.total_seconds, self.duration_method = ff.total_duration(
                self.files, m3u8_seconds=self._m3u8_duration)
        else:
            stopped = "停止" in message
            self.action_bar.set_progress(0, theme.DANGER)
            self.action_bar.set_status(message, "warn" if stopped else "error")
            self.window.log(message, "warn" if stopped else "error")

    # --------------------------------------------------
    def shutdown(self):
        if self.runner and self.runner.is_running():
            self.runner.stop()
