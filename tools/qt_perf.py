# -*- coding: utf-8 -*-
"""实测 Qt 版窗口缩放的流畅度（与 Tkinter 版同样的测法，便于对比）。

Tkinter 版实测：番剧页 231 ms/步、合并页 142 ms/步、最大化 266 ms。
"""

import os
import sys
import time

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)

from PySide6.QtWidgets import QApplication          # noqa: E402

TMP = os.path.join(PROJECT_DIR, ".selftest_tmp", "qtperf")


def make_file(path, size=1024):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.isfile(path):
        with open(path, "wb") as fp:
            fp.write(b"\0" * size)


def build_fixture():
    root = os.path.join(TMP, "番剧")
    for n in (1, 2, 3, 10, 11, 12):
        make_file(os.path.join(root, str(n), f"EP{n:02d}.mkv"), 4096)
    segs = os.path.join(TMP, "分片")
    for i in range(1, 201):
        make_file(os.path.join(segs, f"{i:04d}.ts"), 1024 * 512)
    return root, segs


def main():
    from qtui.main_window import MainWindow
    from qtui import theme

    app = QApplication(sys.argv)
    theme.init_fonts()
    app.setFont(theme.ui_font(10))

    root, segs = build_fixture()

    window = MainWindow()
    window.resize(1200, 860)
    window.show()
    app.processEvents()
    time.sleep(0.4)
    app.processEvents()

    page = window.pages["rename"]
    page.edit_root.setText(root)
    page.edit_out.setText(os.path.join(TMP, "out"))
    os.makedirs(page.edit_out.text(), exist_ok=True)
    page.scan()
    app.processEvents()

    merge = window.pages["merge"]
    merge.files = sorted(os.path.join(segs, n) for n in os.listdir(segs))
    merge._refresh_list(reprobe=False)
    app.processEvents()

    def bench(label, steps=60):
        window.resize(1180, 860)
        for _ in range(6):
            app.processEvents()
            time.sleep(0.02)
        t0 = time.perf_counter()
        for i in range(steps):
            window.resize(1180 + (i % 20) * 12, 860)
            app.processEvents()
        dt = (time.perf_counter() - t0) / steps * 1000
        print(f"   {label:30s} {dt:6.1f} ms/步")
        return dt

    print("== Qt 版缩放（200 个分片 / 12 集）==")
    window.show_page("rename")
    app.processEvents()
    rename_ms = bench("番剧整理页")

    window.show_page("merge")
    app.processEvents()
    merge_ms = bench("分片合并页")

    print("\n== 最大化 / 还原 ==")
    window.resize(1180, 860)
    app.processEvents()
    time.sleep(0.2)
    t0 = time.perf_counter()
    window.showMaximized()
    app.processEvents()
    print(f"   showMaximized()                {(time.perf_counter()-t0)*1000:6.0f} ms")
    t0 = time.perf_counter()
    window.showNormal()
    app.processEvents()
    print(f"   showNormal()                   {(time.perf_counter()-t0)*1000:6.0f} ms")

    print("\n== 对比 Tkinter 版 ==")
    print(f"   番剧整理页    Tk 231 ms/步  ->  Qt {rename_ms:.1f} ms/步")
    print(f"   分片合并页    Tk 142 ms/步  ->  Qt {merge_ms:.1f} ms/步")
    print(f"   最大化        Tk 266 ms     ->  Qt 见上")

    window.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
