# -*- coding: utf-8 -*-
"""影音工具箱 —— Qt 版入口。

    .venv\\Scripts\\python.exe app_qt.py

界面层是 PySide6，逻辑层 core/ 与 Tkinter 版本完全共用。
"""

import os
import sys

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)


def main():
    try:
        from qtui.main_window import run
    except ImportError as e:
        sys.stderr.write(
            "缺少 PySide6，请先安装依赖：\n"
            "    .venv\\Scripts\\python.exe -m pip install PySide6\n"
            f"\n原始错误：{e}\n")
        return 2
    return run()


if __name__ == "__main__":
    sys.exit(main())
