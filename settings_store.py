"""用户设置持久化 — 纯函数模块，无外部依赖。

设置文件默认位于 %APPDATA%\\ModeCalc\\settings.json；
可用环境变量 MODECALC_SETTINGS_DIR 覆盖目录（测试/便携用途）。
"""

import json
import os
import sys
from pathlib import Path

from runtime_paths import settings_path

SETTINGS_VERSION = 2


def default_settings_path() -> Path:
    """返回设置文件路径。"""
    return settings_path()


def load_settings(path: str | os.PathLike | None = None) -> dict:
    """读取设置；文件不存在、损坏或不是 JSON 对象时返回空 dict。"""
    p = Path(path) if path else default_settings_path()
    if path is None and sys.platform == "darwin" and not os.environ.get("MODECALC_SETTINGS_DIR"):
        # Copy a valid legacy Mac file once; never overwrite the new location
        # or remove the user's original file if migration fails.
        legacy = Path.home() / "ModeCalc" / "settings.json"
        if not p.exists() and legacy != p:
            try:
                old = json.loads(legacy.read_text(encoding="utf-8"))
                if isinstance(old, dict):
                    save_settings(old, p)
                    return old
            except (OSError, ValueError):
                pass
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_settings(settings: dict, path: str | os.PathLike | None = None) -> bool:
    """原子写入设置；失败返回 False，不抛异常。"""
    p = Path(path) if path else default_settings_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".tmp")
        tmp.write_text(
            json.dumps(settings, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(tmp, p)
        return True
    except OSError:
        return False


def load_parents(path: str | os.PathLike | None = None) -> list[str] | None:
    """读取上次勾选的母音阶；无记录或格式非法时返回 None。"""
    parents = load_settings(path).get("parents")
    if isinstance(parents, list) and all(isinstance(p, str) for p in parents):
        return parents
    return None


def save_parents(parents, path: str | os.PathLike | None = None) -> bool:
    """保存母音阶勾选，保留文件中的其他字段。"""
    data = load_settings(path)
    data["version"] = SETTINGS_VERSION
    data["parents"] = list(parents)
    return save_settings(data, path)


def load_scale_library(path: str | os.PathLike | None = None) -> dict:
    """读取用户音阶库状态；无记录或格式非法时返回空 dict。"""
    value = load_settings(path).get("scale_library")
    return value if isinstance(value, dict) else {}


def save_scale_library(state: dict, path: str | os.PathLike | None = None) -> bool:
    """保存音阶库状态，保留文件中的其他字段。"""
    data = load_settings(path)
    data["version"] = SETTINGS_VERSION
    data["scale_library"] = state
    return save_settings(data, path)
