# -*- coding: utf-8 -*-
"""m3u8 播放列表解析：提取分片路径、加密标记与总时长。"""

import os


class M3U8Error(Exception):
    """m3u8 解析相关错误。"""


def parse_m3u8(m3u8_path: str) -> dict:
    """解析 m3u8，返回分片列表等信息。

    返回字段：
        path / dir / segments / encrypted / is_master / has_endlist / duration
    """
    if not os.path.isfile(m3u8_path):
        raise M3U8Error(f"文件不存在：{m3u8_path}")

    with open(m3u8_path, "r", encoding="utf-8", errors="ignore") as fp:
        content = fp.read()

    if not content.lstrip("\ufeff \t\r\n").startswith("#EXTM3U"):
        raise M3U8Error("不是合法的 m3u8 文件（缺少 #EXTM3U 头）")

    segments: list[str] = []
    encrypted = False
    is_master = False
    has_endlist = False
    duration = 0.0
    pending_extinf = 0.0

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            upper = line.upper()
            if upper.startswith("#EXT-X-KEY") and "METHOD=NONE" not in upper:
                encrypted = True
            elif upper.startswith("#EXT-X-STREAM-INF"):
                is_master = True
            elif upper.startswith("#EXT-X-ENDLIST"):
                has_endlist = True
            elif upper.startswith("#EXTINF:"):
                try:
                    pending_extinf = float(line.split(":", 1)[1].split(",")[0])
                except ValueError:
                    pending_extinf = 0.0
            continue
        segments.append(line)
        duration += pending_extinf
        pending_extinf = 0.0

    return {
        "path": os.path.abspath(m3u8_path),
        "dir": os.path.dirname(os.path.abspath(m3u8_path)),
        "segments": segments,
        "encrypted": encrypted,
        "is_master": is_master,
        "has_endlist": has_endlist,
        "duration": duration,
    }


def resolve_segments(info: dict, must_exist: bool = True) -> list[str]:
    """把 m3u8 中的相对路径解析为绝对路径。

    must_exist=True 时，任何分片缺失都会抛出 M3U8Error。
    """
    base_dir = info["dir"]
    result: list[str] = []
    missing: list[str] = []

    for seg in info["segments"]:
        if seg.startswith(("http://", "https://")):
            result.append(seg)
            continue
        full = os.path.normpath(
            seg if os.path.isabs(seg) else os.path.join(base_dir, seg)
        )
        if not os.path.isfile(full):
            missing.append(full)
            if must_exist:
                raise M3U8Error(f"m3u8 引用的分片不存在：{full}")
        result.append(full)

    if not result:
        raise M3U8Error("m3u8 中没有解析到任何分片")
    return result


def missing_segments(info: dict) -> list[str]:
    """返回 m3u8 中缺失的本地分片列表（不抛异常）。"""
    base_dir = info["dir"]
    missing = []
    for seg in info["segments"]:
        if seg.startswith(("http://", "https://")):
            continue
        full = os.path.normpath(
            seg if os.path.isabs(seg) else os.path.join(base_dir, seg)
        )
        if not os.path.isfile(full):
            missing.append(full)
    return missing
