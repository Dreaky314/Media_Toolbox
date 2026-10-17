# -*- coding: utf-8 -*-
"""ffmpeg / ffprobe 定位、校验与媒体信息探测。"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from .config import app_dir, load_config, save_config


def _no_window_flags() -> int:
    return subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def _check_exe(path: str) -> bool:
    if not path:
        return False
    p = Path(path)
    if not p.is_file():
        return False
    if sys.platform == "win32" and p.suffix.lower() not in (".exe", ".bat", ".cmd"):
        return False
    return True


def _candidate_dirs() -> list[Path]:
    """按优先级给出可能存放 ffmpeg 的目录。"""
    base = app_dir()
    dirs = [
        base,
        base / "ffmpeg",
        base / "ffmpeg" / "bin",
        base / "bin",
        # 兼容原始项目结构：与本程序并列的 ts文件合并/ffmpeg/bin
        base.parent / "ts文件合并" / "ffmpeg" / "bin",
        base.parent / "ts文件合并",
        base.parent / "ffmpeg" / "bin",
    ]
    cfg = load_config()
    custom = cfg.get("ffmpeg_dir") or ""
    if custom:
        dirs.insert(0, Path(custom))
    # 去重并保持顺序
    seen, result = set(), []
    for d in dirs:
        key = str(d).lower()
        if key not in seen:
            seen.add(key)
            result.append(d)
    return result


def _find(name: str, same_dir_of: str = "") -> str:
    """在候选目录与系统 PATH 中查找可执行文件，找不到时返回裸名字。"""
    names = [f"{name}.exe", name] if sys.platform == "win32" else [name]

    if same_dir_of and _check_exe(same_dir_of):
        parent = Path(same_dir_of).parent
        for n in names:
            p = parent / n
            if p.is_file():
                return str(p)

    for d in _candidate_dirs():
        for n in names:
            p = d / n
            if p.is_file():
                return str(p)

    found = shutil.which(name)
    return found or name


def get_ffmpeg_path() -> str:
    """优先级：用户手选路径 → 候选目录 → 系统 PATH。"""
    cfg = load_config()
    user_path = cfg.get("ffmpeg_path") or ""
    if _check_exe(user_path):
        return user_path
    return _find("ffmpeg")


def get_ffprobe_path() -> str:
    cfg = load_config()
    user_path = cfg.get("ffmpeg_path") or ""
    return _find("ffprobe", same_dir_of=user_path if _check_exe(user_path) else "")


def set_ffmpeg_path(path: str) -> bool:
    cfg = load_config()
    if path:
        cfg["ffmpeg_path"] = path
    else:
        cfg.pop("ffmpeg_path", None)
    return save_config(cfg)


def test_ffmpeg(path: str | None = None) -> tuple[bool, str]:
    """执行 ffmpeg -version 验证可用性，返回 (是否可用, 说明)。"""
    exe = path or get_ffmpeg_path()
    try:
        r = subprocess.run(
            [exe, "-version"],
            capture_output=True, text=True, timeout=8,
            creationflags=_no_window_flags(),
        )
        if r.returncode == 0:
            first = (r.stdout or "").splitlines()
            return True, (first[0] if first else "ffmpeg 可用")
        return False, f"退出码 {r.returncode}"
    except FileNotFoundError:
        return False, "找不到该文件"
    except subprocess.TimeoutExpired:
        return False, "执行超时"
    except Exception as e:  # pragma: no cover - 平台差异
        return False, str(e)


_TIME_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")


def probe_duration(target: str, timeout: int = 60) -> float:
    """用 ffprobe 读取单个媒体文件的时长（秒）；失败返回 0。

    注意：ffprobe 对「MPEG-TS 的 concat 列表」恒返回 N/A，
    所以统计整段时长请用 total_duration()，不要传 .txt 列表。
    """
    if not target or not os.path.exists(target):
        return 0.0
    args = [
        get_ffprobe_path(), "-v", "error",
        "-i", target,
        "-show_entries", "format=duration",
        "-of", "csv=p=0",
    ]
    try:
        r = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout,
            creationflags=_no_window_flags(),
        )
        for line in (r.stdout or "").splitlines():
            value = line.strip().strip(",")
            try:
                seconds = float(value)
                if seconds > 0:
                    return seconds
            except ValueError:
                continue
    except Exception:
        pass
    return 0.0


# ffprobe 每次只接受一个输入，列表过长时逐个探测会很慢，
# 因此小列表精确探测（并行），大列表改为抽样估算。
EXACT_LIMIT = 80
PROBE_WORKERS = 8
SAMPLE_COUNT = 6


def total_duration(files: list, m3u8_seconds: float = 0.0,
                   exact_limit: int = EXACT_LIMIT,
                   workers: int = PROBE_WORKERS) -> tuple[float, str]:
    """估算一组分片的总时长。

    返回 (秒数, 方式)，方式取值：
        "m3u8"     直接来自 m3u8 的 #EXTINF 累加，最准
        "exact"    并行逐个探测后求和
        "estimate" 抽样若干分片取平均后乘以数量
        "unknown"  无法获知
    """
    files = [f for f in (files or []) if f and os.path.isfile(f)]
    if not files:
        return (float(m3u8_seconds or 0.0), "m3u8" if m3u8_seconds else "unknown")
    if m3u8_seconds and m3u8_seconds > 0:
        return (float(m3u8_seconds), "m3u8")

    if len(files) <= exact_limit:
        from concurrent.futures import ThreadPoolExecutor
        try:
            with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
                durations = list(pool.map(probe_duration, files))
            exact = sum(d for d in durations if d > 0)
            if exact > 0:
                return (exact, "exact")
        except Exception:
            pass

    # 抽样：取首尾若干个分片求平均（TS 分片时长通常很接近）
    indexes = []
    if len(files) <= SAMPLE_COUNT:
        indexes = list(range(len(files)))
    else:
        head = SAMPLE_COUNT // 2
        tail = SAMPLE_COUNT - head
        indexes = list(range(head)) + list(range(len(files) - tail, len(files)))
    samples = [probe_duration(files[i]) for i in dict.fromkeys(indexes)]
    samples = [s for s in samples if s > 0]
    if not samples:
        return (0.0, "unknown")
    average = sum(samples) / len(samples)
    return (average * len(files), "estimate")


DURATION_METHOD_TEXT = {
    "m3u8": "来自 m3u8",
    "exact": "精确读取",
    "estimate": "抽样估算",
    "unknown": "未知",
}


def format_duration(seconds: float) -> str:
    if not seconds or seconds <= 0:
        return "--:--:--"
    seconds = int(seconds)
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


def format_size(num_bytes: int) -> str:
    if not num_bytes:
        return "0 B"
    units = ("B", "KB", "MB", "GB", "TB")
    value = float(num_bytes)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"
