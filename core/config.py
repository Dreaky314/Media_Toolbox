# -*- coding: utf-8 -*-
"""程序目录定位与配置文件读写。"""

import json
import sys
from pathlib import Path

APP_NAME = "影音工具箱"
APP_VERSION = "1.0.0"


def app_dir() -> Path:
    """程序真正所在目录（开发环境为源码目录，打包后为 exe 所在目录）。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def config_path() -> Path:
    return app_dir() / "config.json"


def resource_path(*parts) -> Path | None:
    """定位随程序发布的资源（图标等），找不到返回 None。

    开发环境：项目目录下；
    PyInstaller onefile：解压目录 sys._MEIPASS；
    PyInstaller onedir：exe 同级的 _internal 目录（--add-data 会落到这里）。
    """
    bases = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        bases.append(Path(meipass))
    base = app_dir()
    bases.extend([base, base / "_internal"])
    for candidate_base in bases:
        candidate = candidate_base.joinpath(*parts)
        if candidate.exists():
            return candidate
    return None


def load_config() -> dict:
    path = config_path()
    if not path.is_file():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def save_config(cfg: dict) -> bool:
    try:
        with open(config_path(), "w", encoding="utf-8") as fp:
            json.dump(cfg, fp, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


def update_config(**kwargs) -> dict:
    cfg = load_config()
    cfg.update(kwargs)
    save_config(cfg)
    return cfg
