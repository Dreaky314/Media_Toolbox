# -*- coding: utf-8 -*-
"""TS 分片合并：文件收集、命令构建、带进度的后台执行器。"""

import os
import re
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from .ffmpeg import get_ffmpeg_path


def _creationflags() -> int:
    return subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


# ============================================================
# 文件收集
# ============================================================
def natural_key(path: str):
    """自然排序：让 2.ts 排在 10.ts 前面。"""
    parts = re.split(r"(\d+)", os.path.basename(path))
    return [int(t) if t.isdigit() else t.lower() for t in parts]


def list_ts_files(directory: str, recursive: bool = False) -> list[str]:
    """列出目录中的 .ts 分片并按自然顺序排列。"""
    if not os.path.isdir(directory):
        return []
    if recursive:
        files = [
            os.path.join(root, name)
            for root, _dirs, names in os.walk(directory)
            for name in names
            if name.lower().endswith(".ts")
        ]
    else:
        files = [
            os.path.join(directory, name)
            for name in os.listdir(directory)
            if name.lower().endswith(".ts")
        ]
    return sorted(files, key=natural_key)


def total_size(files: list[str]) -> int:
    size = 0
    for f in files:
        try:
            size += os.path.getsize(f)
        except OSError:
            pass
    return size


# ============================================================
# 命令构建
# ============================================================
def _default_list_path() -> str:
    """挑一个可写的目录放 concat 列表。

    优先系统临时目录；被安全策略挡住时退回程序目录下的 temp/，
    再不行就用当前工作目录，保证合并不因为一个中转文件而失败。
    """
    candidates = []
    try:
        candidates.append(tempfile.gettempdir())
    except Exception:
        pass
    candidates.append(str(Path(__file__).resolve().parent.parent / "temp"))
    candidates.append(os.getcwd())

    for directory in candidates:
        try:
            os.makedirs(directory, exist_ok=True)
            handle, path = tempfile.mkstemp(prefix="mediakit_concat_",
                                            suffix=".txt", dir=directory)
            os.close(handle)
            return path
        except Exception:
            continue
    raise OSError("找不到可写的目录来存放合并列表文件")


def build_concat_list(files: list[str], list_path: str | None = None) -> str:
    """写出 ffmpeg concat 列表文件，返回其路径。"""
    if list_path is None:
        list_path = _default_list_path()
    with open(list_path, "w", encoding="utf-8") as fp:
        for f in files:
            safe = os.path.abspath(f).replace("\\", "/").replace("'", "'\\''")
            fp.write(f"file '{safe}'\n")
    return list_path


MODE_COPY = "copy"
MODE_CRF = "crf"
MODE_BITRATE = "bitrate"


def build_ffmpeg_cmd(
    files: list[str],
    output: str,
    mode: str = MODE_COPY,
    crf: int = 18,
    video_bitrate: str = "8M",
    audio_bitrate: str = "192k",
    list_path: str | None = None,
    ffmpeg_path: str | None = None,
) -> tuple[list[str], str]:
    """拼装 ffmpeg 命令，返回 (命令列表, concat 列表文件路径)。

    mode:
      "copy"    直接复制码流，速度最快、画质无损
      "crf"     质量优先重编码，CRF 越小越清晰
      "bitrate" 固定码率重编码
    """
    if not files:
        raise ValueError("分片列表为空，请先添加 .ts 文件")
    missing = [f for f in files if not os.path.isfile(f)]
    if missing:
        raise ValueError(f"文件不存在：{missing[0]}")
    if not output or not output.strip():
        raise ValueError("请先指定输出文件路径")

    output = output.strip()
    out_dir = os.path.dirname(os.path.abspath(output))
    if out_dir and not os.path.isdir(out_dir):
        raise ValueError(f"输出目录不存在：{out_dir}")

    real_list = build_concat_list(files, list_path)

    cmd = [
        ffmpeg_path or get_ffmpeg_path(),
        "-y",
        "-f", "concat", "-safe", "0",
        "-i", real_list,
    ]

    if mode == MODE_COPY:
        cmd += ["-c", "copy"]
    elif mode == MODE_CRF:
        cmd += [
            "-c:v", "libx264",
            "-crf", str(crf),
            "-preset", "medium",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", audio_bitrate,
        ]
    elif mode == MODE_BITRATE:
        cmd += [
            "-c:v", "libx264",
            "-b:v", video_bitrate,
            "-maxrate", video_bitrate,
            "-bufsize", video_bitrate,
            "-preset", "medium",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", audio_bitrate,
        ]
    else:
        raise ValueError(f"未知的编码模式：{mode}")

    if output.lower().endswith(".mp4"):
        # aac_adtstoasc 让 TS 中的 AAC 能正常放进 mp4；队列放大避免长列表下 mux 阻塞
        cmd += ["-bsf:a", "aac_adtstoasc", "-movflags", "+faststart",
                "-max_muxing_queue_size", "1024"]

    cmd += [output]
    return cmd, real_list


# ============================================================
# 后台执行器
# ============================================================
_TIME_RE = re.compile(r"time=\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_SPEED_RE = re.compile(r"speed=\s*([\d.]+)\s*x")
_STATS_HINT = ("frame=", "bitrate=", "speed=", "size=")
_ERROR_HINT = ("error", "failed", "invalid", "no such file", "not found", "unable to")


class MergerRunner:
    """在后台线程里跑 ffmpeg，通过回调把日志与进度抛给界面。

    回调：
        on_log(line, is_error)
        on_progress(seconds, percent, speed)   percent 为 0~1，未知时为 -1
        on_done(success, message)
    """

    def __init__(self, on_log=None, on_progress=None, on_done=None):
        self.on_log = on_log or (lambda line, is_error: None)
        self.on_progress = on_progress or (lambda seconds, percent, speed: None)
        self.on_done = on_done or (lambda success, message: None)
        self.duration = 0.0
        self._process: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self._cancelled = False

    # -------------------------------------------------- 状态
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # -------------------------------------------------- 生命周期
    def start(self, cmd: list[str], cleanup_path: str | None = None,
              duration: float = 0.0):
        if self.is_running():
            raise RuntimeError("已有任务正在执行")
        self.duration = float(duration or 0.0)
        self._cancelled = False
        self._thread = threading.Thread(
            target=self._run, args=(cmd, cleanup_path), daemon=True)
        self._thread.start()

    def stop(self):
        self._cancelled = True
        proc = self._process
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass

    # -------------------------------------------------- 内部
    def _run(self, cmd: list[str], cleanup_path: str | None):
        success, message = False, ""
        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                encoding="utf-8",
                errors="ignore",
                creationflags=_creationflags(),
            )
            assert self._process.stdout is not None
            # 文本模式下 \r 与 \n 都会被识别为换行，
            # 于是 ffmpeg 就地刷新的统计行也能逐行读到。
            for raw in self._process.stdout:
                line = raw.strip()
                if not line:
                    continue
                if self._handle_stats(line):
                    continue
                low = line.lower()
                self.on_log(line, any(k in low for k in _ERROR_HINT))

            code = self._process.wait()
            if self._cancelled:
                message = "任务已被手动停止"
            else:
                success = (code == 0)
                message = "合并完成" if success else f"ffmpeg 退出码 {code}"
        except FileNotFoundError:
            exe = cmd[0] if cmd else "ffmpeg"
            message = f"找不到 ffmpeg：{exe}"
        except Exception as e:  # pragma: no cover - 平台差异
            message = f"异常：{e}"
        finally:
            if cleanup_path:
                try:
                    if os.path.exists(cleanup_path):
                        os.remove(cleanup_path)
                except OSError:
                    pass
            self._process = None
            self.on_done(success, message)

    def _handle_stats(self, line: str) -> bool:
        """识别 ffmpeg 的统计行，转成进度回调。返回 True 表示已消费该行。"""
        if not all(hint in line for hint in ("time=",)) or \
                not any(h in line for h in _STATS_HINT):
            return False
        m = _TIME_RE.search(line)
        if not m:
            return False
        seconds = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
        percent = -1.0
        if self.duration > 0:
            percent = max(0.0, min(1.0, seconds / self.duration))
        speed_m = _SPEED_RE.search(line)
        speed = float(speed_m.group(1)) if speed_m else 0.0
        self.on_progress(seconds, percent, speed)
        return True
