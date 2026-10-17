# -*- coding: utf-8 -*-
"""与系统外壳交互的小工具。

不用 os.startfile 作为唯一手段：它在部分环境（受限会话、被安全策略拦截）下会抛
PermissionError，调用方又常常把异常吞掉，表现就是「点了按钮没反应」。
这里改成多级回退，并把失败原因返回给界面显示。
"""

import os
import subprocess
import sys


def _popen(args) -> bool:
    """启动外部 Shell 程序。

    这里有两个坑，都不能踩：

    * **不能给 explorer.exe 传 CREATE_NO_WINDOW**。那样 explorer 会在初始化阶段
      直接失败，弹「explorer.exe - Application Error，应用程序无法正常启动
      (0xc0000142)」（STATUS_DLL_INIT_FAILED）。CREATE_NO_WINDOW 只适合 ffmpeg
      这类控制台程序。
    * **不能让子进程继承父进程的 stdio**，否则调用方的管道会一直被占着，
      PowerShell 之类的宿主会以为命令还没结束。
    """
    try:
        subprocess.Popen(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        return True
    except Exception:
        return False


def open_folder(path: str) -> tuple[bool, str]:
    """在文件管理器里打开目录，返回 (是否成功, 说明)。"""
    # 注意：normpath("") 会变成 "."，所以必须先判空再规范化
    path = (path or "").strip()
    if not path:
        return False, "路径为空"
    path = os.path.normpath(path)
    if not os.path.isdir(path):
        return False, f"目录不存在：{path}"

    if sys.platform == "win32":
        # explorer 最可靠，且在受限会话里也能用
        if _popen(["explorer", path]):
            return True, path
        try:
            os.startfile(path)  # noqa: S606
            return True, path
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"

    if sys.platform == "darwin":
        if _popen(["open", path]):
            return True, path
        return False, "无法调用 open"

    if _popen(["xdg-open", path]):
        return True, path
    return False, "无法调用 xdg-open"


def reveal_path(path: str) -> tuple[bool, str]:
    """打开目录并在文件管理器里选中该文件；文件不存在时退化为打开所在目录。"""
    path = (path or "").strip()
    if not path:
        return False, "路径为空"
    path = os.path.normpath(path)
    if not os.path.exists(path):
        return open_folder(os.path.dirname(path))

    if sys.platform == "win32":
        # explorer 要求开关和路径是同一个参数、逗号后不能有空格
        if _popen(["explorer", "/select," + path]):
            return True, path
    return open_folder(os.path.dirname(path))
