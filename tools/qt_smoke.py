# -*- coding: utf-8 -*-
"""Qt 界面冒烟测试 / 截图验收。

    .venv\\Scripts\\python.exe tools\\qt_smoke.py
    .venv\\Scripts\\python.exe tools\\qt_smoke.py --shots

截图通过 QWidget.grab() 离屏渲染，不依赖窗口是否置顶。
数据造在 .selftest_tmp/ 下，不会碰真实媒体文件。
"""

import os
import shutil
import sys
import time

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)

os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")

from PySide6.QtCore import Qt, QTimer                      # noqa: E402
from PySide6.QtWidgets import QApplication                 # noqa: E402

TMP = os.path.join(PROJECT_DIR, ".selftest_tmp", "qt")
SHOTS = os.path.join(PROJECT_DIR, ".shots")

PASS, FAIL = [], []


def check(name, condition, detail=""):
    (PASS if condition else FAIL).append(name)
    print(f"  {'PASS' if condition else 'FAIL'}  {name}" + (f"  -> {detail}" if detail else ""))


def make_file(path, size=2048):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fp:
        fp.write(b"\0" * size)


def build_fixture():
    shutil.rmtree(TMP, ignore_errors=True)
    root = os.path.join(TMP, "孤独摇滚")
    for number, name in ((1, "EP01_[1080p][简繁].mkv"), (2, "第02话.mkv"),
                         (3, "Bangumi_03.mkv"), (10, "final_10.mkv"),
                         (11, "EP11.mkv"), (12, "EP12.mkv")):
        make_file(os.path.join(root, str(number), name), 1024 * (number + 1))
    make_file(os.path.join(root, "SP", "OVA.mkv"), 4096)
    make_file(os.path.join(root, "4", "readme.txt"), 64)
    out = os.path.join(TMP, "输出")
    os.makedirs(out, exist_ok=True)

    segs = os.path.join(TMP, "分片")
    for i in range(1, 25):
        make_file(os.path.join(segs, f"{i:04d}.ts"), 1024 * 512)
    return root, out, segs


def pump(app, ms=120):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def grab(widget, name):
    os.makedirs(SHOTS, exist_ok=True)
    path = os.path.join(SHOTS, name)
    pix = widget.grab()
    pix.save(path)
    return path, pix.width(), pix.height()



def _real_merge(app, window, seg_dir):
    """用真实 ffmpeg 走一遍「分片合并」页：开始 -> 进度 -> 完成 -> 按钮复位。"""
    import subprocess

    from core import ffmpeg as ff

    exe = ff.get_ffmpeg_path()
    available, _info = ff.test_ffmpeg(exe)
    if not available:
        print("  跳过：本机没有可用的 ffmpeg")
        return

    window.ffmpeg_ok = True
    window.ffmpeg_info = "测试用"

    real_dir = os.path.join(TMP, "真实分片")
    os.makedirs(real_dir, exist_ok=True)
    segs = []
    for i in range(1, 4):
        path = os.path.join(real_dir, f"{i}.ts")
        result = subprocess.run(
            [exe, "-y", "-f", "lavfi", "-i",
             "testsrc=size=160x120:rate=25:duration=1",
             "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
             "-f", "mpegts", path],
            capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        if result.returncode != 0:
            check("生成测试分片", False, (result.stderr or "")[-200:])
            return
        segs.append(path)
    check("生成 3 个测试分片", len(segs) == 3)

    window.show_page("merge")
    pump(app, 80)
    page = window.pages["merge"]
    output = os.path.join(TMP, "真实输出.mp4")
    page.files = segs
    page.edit_out.setText(output)
    page._refresh_list(reprobe=True)

    end = time.time() + 15
    while time.time() < end and page.total_seconds <= 0:
        pump(app, 60)
    check("读取到分片总时长", page.total_seconds > 0,
          f"{page.total_seconds:.2f}s")

    page.start()
    # 立即断言：3 个微型分片用 -c copy 几十毫秒就跑完了，
    # 等 pump 一轮再查的话按钮已经复位了
    check("开始后按钮状态正确",
          page.btn_stop.isEnabled() and not page.btn_start.isEnabled())
    pump(app, 120)

    end = time.time() + 90
    while time.time() < end:
        pump(app, 60)
        if not (page.runner and page.runner.is_running()):
            break
    pump(app, 600)

    check("合并输出已生成", os.path.isfile(output),
          ff.format_size(os.path.getsize(output)) if os.path.isfile(output) else "缺失")
    check("输出时长约 3s", abs(ff.probe_duration(output) - 3.0) < 0.8,
          f"{ff.probe_duration(output):.2f}s")
    check("进度走到 100%", page.action_bar.progress.value() == 1000,
          str(page.action_bar.progress.value()))
    check("按钮已复位",
          page.btn_start.isEnabled() and not page.btn_stop.isEnabled())
    check("日志里出现完成提示",
          "合并完成" in window.log_panel.view.toPlainText())


def main():
    from qtui.main_window import MainWindow

    print("=" * 62)
    print("Qt 界面冒烟测试")
    print("=" * 62)

    app = QApplication(sys.argv)
    from qtui import theme
    theme.init_fonts()
    app.setFont(theme.ui_font(10))

    window = MainWindow()
    window.resize(1200, 860)
    window.show()
    pump(app, 400)

    print("\n[1] 主窗口骨架")
    check("默认停在番剧整理页", window.current_page == "rename", window.current_page)
    check("侧边导航有三个入口", len(window.nav_buttons) == 3,
          str(list(window.nav_buttons)))
    check("页面栈数量正确", window.stack.count() == 3, str(window.stack.count()))
    check("页头标题正确", window.lbl_title.text() == "番剧整理",
          window.lbl_title.text())
    check("日志面板已创建", window.log_panel is not None)
    check("DPI 感知（devicePixelRatio）",
          app.primaryScreen().devicePixelRatio() > 0,
          str(app.primaryScreen().devicePixelRatio()))

    print("\n[2] 窗口/任务栏图标")
    icon = window.windowIcon()
    check("窗口设置了图标", not icon.isNull())
    sizes = sorted({(s.width(), s.height()) for s in icon.availableSizes()})
    check("图标是多尺寸且为正方形",
          bool(sizes) and all(w == h for w, h in sizes), str(sizes))
    check("图标包含 16/32/256 这三个关键尺寸",
          all((n, n) in sizes for n in (16, 32, 256)), str(sizes))

    print("\n[11] 页面切换")
    for key, title in (("merge", "分片合并"), ("settings", "设置"),
                       ("rename", "番剧整理")):
        window.show_page(key)
        pump(app, 80)
        check(f"切到 {title}", window.lbl_title.text() == title)
        check(f"{title} 已挂载", window.pages[key].isVisible())

    root, out, segs = build_fixture()

    print("\n[3] 番剧整理页")
    page = window.pages["rename"]
    page.edit_root.setText(root)
    page.edit_out.setText(out)
    page.scan()
    pump(app, 150)
    check("扫描出 7 个数字目录（含 1 个无视频）",
          len(page.result.episodes) == 7, str(len(page.result.episodes)))
    check("识别出无视频的那一集",
          any(e.status == "no_video" for e in page.result.episodes))
    check("忽略 SP 目录", page.result.ignored_dirs == ["SP"],
          str(page.result.ignored_dirs))
    check("表格行数与清单一致",
          page.table.rowCount() == len(page.result.episodes),
          str(page.table.rowCount()))
    check("统计块显示就绪集数", page.stat_chips["ready"].value.text() == "6",
          page.stat_chips["ready"].value.text())
    check("表头列数正确", page.table.columnCount() == 6)

    page.seg_action.set("rename")
    page._set_action("rename")
    pump(app, 60)
    check("仅重命名模式下目标目录被禁用", not page.edit_out.isEnabled())
    page._set_action("copy")
    pump(app, 60)
    check("复制模式下目标目录恢复可用", page.edit_out.isEnabled())

    print("\n[4] 分片合并页")
    window.show_page("merge")
    pump(app, 80)
    merge = window.pages["merge"]
    merge.files = []
    merge._refresh_list(reprobe=False)
    pump(app, 60)
    check("空列表提示正确", merge.lbl_summary.text() == "还没有添加分片",
          merge.lbl_summary.text())

    merge.files = sorted(os.path.join(segs, n) for n in os.listdir(segs))
    merge._refresh_list(reprobe=False)
    pump(app, 80)
    check("载入 24 个分片", merge.table.rowCount() == 24,
          str(merge.table.rowCount()))
    check("合计体积已统计", "合计" in merge.lbl_summary.text(),
          merge.lbl_summary.text())

    first = merge.files[0]
    merge.table.selectRow(0)
    merge.move_down()
    pump(app, 60)
    check("下移生效", merge.files[1] == first)
    merge.table.selectRow(1)
    merge.move_up()
    pump(app, 60)
    check("上移复原", merge.files[0] == first)

    merge.table.selectRow(0)
    before = len(merge.files)
    merge.remove_selected()
    pump(app, 60)
    check("删除选中生效", len(merge.files) == before - 1, str(len(merge.files)))
    merge.reverse_list()
    pump(app, 60)
    check("反转顺序生效", os.path.basename(merge.files[-1]) == "0002.ts",
          os.path.basename(merge.files[-1]))

    print("\n[5] 输出设置联动")
    merge.edit_out.setText(os.path.join(TMP, "输出", "第01集.mp4"))
    merge._on_format_change("mkv")
    pump(app, 60)
    check("切换格式同步改扩展名", merge.edit_out.text().endswith(".mkv"),
          merge.edit_out.text())
    merge._on_mode_change("bitrate")
    pump(app, 60)
    check("指定码率时显示码率输入框", merge.bitrate_box.isVisible())
    merge._on_mode_change("copy")
    pump(app, 60)
    check("直接拼接时隐藏码率输入框", not merge.bitrate_box.isVisible())

    print("\n[6] 命令构建（不执行）")
    merge.edit_out.setText(os.path.join(TMP, "输出", "第01集.mp4"))
    cmd, list_path = merge._build_cmd()
    check("命令含 concat", "concat" in cmd)
    check("命令以输出文件结尾", cmd[-1] == merge.edit_out.text(), cmd[-1])
    check("concat 列表已生成", os.path.isfile(list_path))
    try:
        os.remove(list_path)
    except OSError:
        pass

    print("\n[7] 设置页")
    window.show_page("settings")
    pump(app, 80)
    settings = window.pages["settings"]
    check("路径输入框可编辑", settings.edit_path.isEnabled())
    notices = []
    real_notify, real_confirm = window.notify, window.confirm
    window.notify = lambda t, m, level="info": notices.append((t, level))
    window.confirm = lambda *a, **k: True
    config_file = os.path.join(PROJECT_DIR, "config.json")
    backup = open(config_file, encoding="utf-8").read() if os.path.isfile(config_file) else None
    try:
        settings.edit_path.setText(r"Z:\不存在的\ffmpeg.exe")
        settings.save_path()
        pump(app, 60)
        check("非法路径被拒绝", notices and notices[-1][1] == "error",
              str(notices[-1] if notices else None))

        from core import ffmpeg as ff
        real = ff.get_ffmpeg_path()
        if os.path.isfile(real):
            settings.edit_path.setText(real)
            settings.save_path()
            pump(app, 60)
            import json
            cfg = json.load(open(config_file, encoding="utf-8"))
            check("ffmpeg 路径已写入 config.json",
                  cfg.get("ffmpeg_path") == real, str(cfg.get("ffmpeg_path")))
        else:
            print("  跳过：本机没有可用 ffmpeg 可执行文件")
        settings.auto_detect()
        pump(app, 60)
        import json
        cfg = json.load(open(config_file, encoding="utf-8")) if os.path.isfile(config_file) else {}
        check("自动检测会清除手动路径", not cfg.get("ffmpeg_path"))
        check("路径框已回填自动检测结果", bool(settings.edit_path.text()),
              settings.edit_path.text())
    finally:
        window.notify, window.confirm = real_notify, real_confirm
        if backup is None:
            if os.path.isfile(config_file):
                os.remove(config_file)
        else:
            open(config_file, "w", encoding="utf-8").write(backup)

    print("\n[8] 日志面板")
    window.log("这是一条普通日志", "info")
    window.log("这是一条成功日志", "ok")
    window.log("这是一条警告日志", "warn")
    window.log("这是一条错误日志", "error")
    pump(app, 80)
    content = window.log_panel.view.toPlainText()
    check("日志写入成功", "成功日志" in content)
    check("四种级别都有内容",
          all(k in content for k in ("普通日志", "成功日志", "警告日志", "错误日志")))
    window.log_panel.set_collapsed(True)
    pump(app, 60)
    check("日志面板可折叠", window.log_panel.collapsed is True)
    window.log_panel.set_collapsed(False)
    pump(app, 60)
    check("日志面板可展开", window.log_panel.collapsed is False)

    print("\n[9] 通过界面真的跑一次合并")
    _real_merge(app, window, segs)

    print("\n[10] 尺寸变化后布局仍然正确")
    for size in ((1000, 700), (1500, 950), (1100, 780)):
        window.resize(*size)
        pump(app, 150)
        ok = (window.stack.width() > 0 and window.stack.height() > 0
              and window.pages["rename"].table.width() > 100)
        check(f"缩放到 {size[0]}x{size[1]} 后布局正常", ok,
              f"stack={window.stack.width()}x{window.stack.height()}")

    # ---- 截图
    if "--shots" in sys.argv:
        print("\n[截图]")
        window.resize(1200, 860)
        window.show_page("rename")
        page.edit_root.setText(root)
        page.edit_out.setText(out)
        page.scan()
        pump(app, 300)
        window.log("示例模式：数据来自 .selftest_tmp/qt，不会动你的真实文件", "info_accent")
        window.log("番剧整理：已扫描 7 集，其中 1 集无视频、1 个非数字目录被忽略", "muted")
        window.log("分片合并：已载入 24 个分片，合计 12.0 MB，预计时长 00:24:00", "muted")
        window.log("ffmpeg 已就绪，可以直接开始合并", "ok")
        pump(app, 150)
        for key, name in (("rename", "qt-rename.png"), ("merge", "qt-merge.png"),
                          ("settings", "qt-settings.png")):
            window.show_page(key)
            pump(app, 250)
            path, w, h = grab(window, name)
            print(f"   {name}  {w}x{h}")
        window.show_page("rename")
        pump(app, 150)

    window.close()
    shutil.rmtree(TMP, ignore_errors=True)

    print("\n" + "=" * 62)
    print(f"通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
    if FAIL:
        print("失败项：" + "，".join(FAIL))
    print("=" * 62)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
