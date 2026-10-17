# -*- coding: utf-8 -*-
"""番剧整理：按集数号重命名子文件夹中的视频，并复制/移动到目标目录。

规则与原始脚本一致：
    - 只处理「以数字命名」的子文件夹（1 / 01 / 12 …）
    - 每个子文件夹取一个视频作为该集的正片
    - 重命名为补零后的集数号（如 01.mp4），位数按最大集数自动推导
"""

import os
import shutil
from dataclasses import dataclass, field

VIDEO_EXTS = {
    ".mp4", ".mkv", ".avi", ".rmvb", ".flv", ".wmv",
    ".mov", ".ts", ".m4v", ".webm", ".mpg", ".mpeg", ".3gp",
}

ACTION_COPY = "copy"
ACTION_MOVE = "move"
ACTION_RENAME = "rename"

ACTION_LABEL = {
    ACTION_COPY: "复制到目标目录",
    ACTION_MOVE: "移动到目标目录",
    ACTION_RENAME: "仅在原文件夹内重命名",
}

# 条目状态
ST_READY = "ready"
ST_NO_VIDEO = "no_video"
ST_EXISTS = "exists"
ST_CONFLICT = "conflict"
ST_SAME = "same"
ST_DONE = "done"
ST_ERROR = "error"

STATUS_TEXT = {
    ST_READY: "待处理",
    ST_NO_VIDEO: "未找到视频",
    ST_EXISTS: "目标已存在",
    ST_CONFLICT: "命名冲突",
    ST_SAME: "已是目标名",
    ST_DONE: "已完成",
    ST_ERROR: "失败",
}

STATUS_LEVEL = {
    ST_READY: "info",
    ST_NO_VIDEO: "muted",
    ST_EXISTS: "warn",
    ST_CONFLICT: "warn",
    ST_SAME: "muted",
    ST_DONE: "ok",
    ST_ERROR: "error",
}

IGNORED_DIR_NOTE = "非数字命名目录（已忽略）"


@dataclass
class Episode:
    number: int
    folder_name: str
    folder_path: str
    source: str = ""
    source_name: str = ""
    video_count: int = 0
    other_videos: list = field(default_factory=list)
    target: str = ""
    target_name: str = ""
    status: str = ST_READY
    note: str = ""
    size: int = 0

    @property
    def status_text(self) -> str:
        return STATUS_TEXT.get(self.status, self.status)

    @property
    def status_level(self) -> str:
        return STATUS_LEVEL.get(self.status, "info")


@dataclass
class ScanResult:
    root: str
    out_dir: str
    action: str
    width: int
    episodes: list
    ignored_dirs: list = field(default_factory=list)
    non_video_files: int = 0

    @property
    def ready(self) -> list:
        return [e for e in self.episodes if e.status == ST_READY]

    @property
    def problems(self) -> list:
        return [e for e in self.episodes
                if e.status in (ST_NO_VIDEO, ST_EXISTS, ST_CONFLICT, ST_ERROR)]

    @property
    def total_bytes(self) -> int:
        return sum(e.size for e in self.ready)


# ============================================================
# 扫描
# ============================================================
def clean_path(p: str) -> str:
    """去掉拖拽/粘贴路径时附带的首尾引号与空白。"""
    if not p:
        return ""
    return p.strip().strip('"').strip("'").strip()


def list_videos(folder: str) -> list[str]:
    """返回文件夹内的视频文件（自然排序）。"""
    result = []
    try:
        names = os.listdir(folder)
    except OSError:
        return result
    for name in names:
        path = os.path.join(folder, name)
        if os.path.isfile(path) and os.path.splitext(name)[1].lower() in VIDEO_EXTS:
            result.append(path)
    return sorted(result, key=_natural_key)


def _natural_key(path: str):
    import re
    parts = re.split(r"(\d+)", os.path.basename(path))
    return [int(t) if t.isdigit() else t.lower() for t in parts]


def compute_width(numbers: list[int], width_mode: str = "auto",
                  fixed_width: int = 2) -> int:
    if width_mode == "fixed":
        return max(1, int(fixed_width))
    if not numbers:
        return 2
    return max(2, len(str(max(numbers))))


def scan(root: str, action: str = ACTION_COPY, out_dir: str = "",
         width_mode: str = "auto", fixed_width: int = 2,
         pick: str = "first", rename_in_place: bool = True) -> ScanResult:
    """扫描根目录，生成处理清单（不修改任何文件）。"""
    root = clean_path(root)
    if not root or not os.path.isdir(root):
        raise ValueError(f"目录不存在：{root or '（空）'}")

    out_dir = clean_path(out_dir) or root
    if action in (ACTION_COPY, ACTION_MOVE) and not os.path.isdir(out_dir):
        raise ValueError(f"目标目录不存在：{out_dir}")

    folders: list[tuple[int, str]] = []
    ignored: list[str] = []
    for name in sorted(os.listdir(root)):
        path = os.path.join(root, name)
        if not os.path.isdir(path):
            continue
        stripped = name.strip()
        if stripped.isdigit():
            folders.append((int(stripped), path))
        elif stripped:
            ignored.append(name)

    if not folders:
        raise ValueError("未找到以数字命名的子文件夹（例如 1 / 02 / 12）")

    # 同号目录（例如 1 与 01 并存）时，优先取名字更「干净」的那个，
    # 避免结果依赖 os.listdir 的列举顺序。
    folders.sort(key=lambda x: (x[0], len(os.path.basename(x[1]).strip())))
    width = compute_width([n for n, _ in folders], width_mode, fixed_width)

    episodes: list[Episode] = []
    for number, folder in folders:
        folder_name = os.path.basename(folder)
        videos = list_videos(folder)
        target_name = f"{number:0{width}d}"
        episode = Episode(
            number=number,
            folder_name=folder_name,
            folder_path=folder,
            video_count=len(videos),
        )

        if not videos:
            episode.status = ST_NO_VIDEO
            episode.note = "该子文件夹内没有可识别的视频文件"
            episode.target_name = target_name
            episodes.append(episode)
            continue

        if pick == "largest":
            videos_sorted = sorted(videos, key=_safe_size, reverse=True)
        else:
            videos_sorted = videos

        src = videos_sorted[0]
        episode.source = src
        episode.source_name = os.path.basename(src)
        episode.other_videos = [v for v in videos if v != src]
        episode.size = _safe_size(src)
        ext = os.path.splitext(src)[1].lower()
        episode.target_name = f"{target_name}{ext}"

        if action == ACTION_RENAME:
            target = os.path.join(folder, episode.target_name)
            episode.target = target
            if os.path.normcase(os.path.abspath(src)) == os.path.normcase(os.path.abspath(target)):
                episode.status = ST_SAME
                episode.note = "源文件名已经是目标名，无需处理"
            elif os.path.exists(target):
                episode.status = ST_EXISTS
                episode.note = "同目录下已存在同名文件，将跳过"
            if episode.other_videos:
                episode.note = (episode.note + "；" if episode.note else "") + \
                    f"该文件夹还有 {len(episode.other_videos)} 个视频未处理"
        else:
            target = os.path.join(out_dir, episode.target_name)
            episode.target = target
            if os.path.normcase(os.path.abspath(src)) == os.path.normcase(os.path.abspath(target)):
                episode.status = ST_SAME
                episode.note = "源文件已位于目标目录且名称正确，无需处理"
            elif os.path.exists(target):
                episode.status = ST_EXISTS
                episode.note = "目标目录已存在同名文件，将跳过"
            if episode.other_videos:
                episode.note = (episode.note + "；" if episode.note else "") + \
                    f"该文件夹还有 {len(episode.other_videos)} 个视频未处理"

        if rename_in_place and action in (ACTION_COPY, ACTION_MOVE) \
                and episode.status == ST_READY:
            inner = os.path.join(folder, episode.target_name)
            if os.path.normcase(os.path.abspath(src)) != os.path.normcase(os.path.abspath(inner)) \
                    and os.path.exists(inner):
                episode.status = ST_EXISTS
                episode.note = "子文件夹内已存在目标名文件，将跳过源文件重命名"

        episodes.append(episode)

    # 同一批次内目标重名（例如同时存在 1 和 01 两个文件夹）
    seen: dict[str, Episode] = {}
    for ep in episodes:
        key = os.path.normcase(os.path.abspath(ep.target))
        if not key:
            continue
        first = seen.get(key)
        if first is not None and ep.status == ST_READY:
            ep.status = ST_CONFLICT
            ep.note = f"与「{first.folder_name}」的目标重名，将跳过"
        else:
            seen.setdefault(key, ep)

    return ScanResult(
        root=root,
        out_dir=out_dir,
        action=action,
        width=width,
        episodes=episodes,
        ignored_dirs=ignored,
        non_video_files=0,
    )


def _safe_size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


# ============================================================
# 执行
# ============================================================
def execute(result: ScanResult, action: str = "", rename_in_place: bool = True,
            on_event=None, should_stop=None) -> dict:
    """执行清单，逐条回调进度。

    on_event(event: dict) 中的 event:
        {"type": "start"|"step"|"done"|"error"|"finish", ...}
    """
    action = action or result.action
    emit = on_event or (lambda event: None)

    targets = result.ready
    total = len(targets)
    stats = {"total": total, "ok": 0, "failed": 0, "skipped": 0,
             "stopped": False, "errors": []}

    emit({"type": "start", "total": total})

    for index, ep in enumerate(targets, start=1):
        if should_stop and should_stop():
            stats["stopped"] = True
            break
        try:
            source = ep.source
            if action == ACTION_RENAME:
                _rename(source, ep.target)
                ep.status = ST_DONE
                ep.note = ""
            else:
                if rename_in_place:
                    inner = os.path.join(ep.folder_path, ep.target_name)
                    if os.path.normcase(os.path.abspath(source)) != \
                            os.path.normcase(os.path.abspath(inner)):
                        if not os.path.exists(inner):
                            _rename(source, inner)
                            source = inner
                            ep.note = "源文件已在子文件夹内重命名"
                        else:
                            source = inner if os.path.exists(inner) else source
                if action == ACTION_MOVE:
                    _move(source, ep.target)
                else:
                    _copy(source, ep.target)
                ep.status = ST_DONE
            stats["ok"] += 1
            emit({"type": "step", "index": index, "total": total,
                  "episode": ep, "ok": True})
        except Exception as e:
            ep.status = ST_ERROR
            ep.note = str(e)
            stats["failed"] += 1
            stats["errors"].append(f"{ep.folder_name}：{e}")
            emit({"type": "error", "index": index, "total": total,
                  "episode": ep, "message": str(e)})

    emit({"type": "finish", "stats": stats})
    return stats


def _rename(src: str, dst: str):
    if os.path.normcase(os.path.abspath(src)) == os.path.normcase(os.path.abspath(dst)):
        return
    if os.path.exists(dst):
        raise FileExistsError(f"目标已存在：{dst}")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    os.rename(src, dst)


def _copy(src: str, dst: str, chunk: int = 1024 * 1024, progress=None):
    """分块复制，便于展示进度并支持中断。"""
    if os.path.exists(dst):
        raise FileExistsError(f"目标已存在：{dst}")
    size = _safe_size(src)
    copied = 0
    with open(src, "rb") as fi, open(dst, "wb") as fo:
        while True:
            buf = fi.read(chunk)
            if not buf:
                break
            fo.write(buf)
            copied += len(buf)
            if progress:
                progress(copied, size)
    try:
        shutil.copystat(src, dst)
    except OSError:
        pass
    return copied


def _move(src: str, dst: str):
    if os.path.exists(dst):
        raise FileExistsError(f"目标已存在：{dst}")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.move(src, dst)


# ============================================================
# 与 Tkinter 解耦的线程执行器
# ============================================================
class OrganizeRunner:
    """在后台线程执行整理任务，通过回调汇报进度。"""

    def __init__(self, on_event=None, on_done=None):
        import threading
        self._threading = threading
        self.on_event = on_event or (lambda event: None)
        self.on_done = on_done or (lambda stats: None)
        self._thread = None
        self._stop = False
        self.stats = {}

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, result: ScanResult, action: str = "",
              rename_in_place: bool = True):
        if self.is_running():
            raise RuntimeError("已有任务正在执行")
        self._stop = False
        self._thread = self._threading.Thread(
            target=self._run, args=(result, action, rename_in_place), daemon=True)
        self._thread.start()

    def stop(self):
        self._stop = True

    def _run(self, result, action, rename_in_place):
        try:
            self.stats = execute(
                result, action=action, rename_in_place=rename_in_place,
                on_event=self.on_event, should_stop=lambda: self._stop)
        except Exception as e:  # pragma: no cover
            self.stats = {"total": 0, "ok": 0, "failed": 1, "skipped": 0,
                          "stopped": False, "errors": [str(e)]}
            self.on_event({"type": "error", "message": str(e)})
        finally:
            self.on_done(self.stats)
