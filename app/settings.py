"""极简用户配置：目前只有 archive_dir 一个字段。"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _config_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) / "DesktopTodo" if appdata else Path.home() / ".desktop_todo"
    base.mkdir(parents=True, exist_ok=True)
    return base


DEFAULT_ARCHIVE_DIR: Path = _project_root() / "DoneList"
_CONFIG_PATH: Path = _config_dir() / "config.json"


class Settings:
    def __init__(self, path: Path = _CONFIG_PATH):
        self.path = path
        self._data: dict = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8")) or {}
            except (OSError, json.JSONDecodeError):
                self._data = {}

    def _save(self) -> None:
        try:
            self.path.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass

    @property
    def archive_dir(self) -> Path:
        raw = self._data.get("archive_dir")
        return Path(raw) if raw else DEFAULT_ARCHIVE_DIR

    @archive_dir.setter
    def archive_dir(self, value: Optional[Path]) -> None:
        if value is None or Path(value) == DEFAULT_ARCHIVE_DIR:
            self._data.pop("archive_dir", None)
        else:
            self._data["archive_dir"] = str(value)
        self._save()

    def reset_archive_dir(self) -> None:
        self.archive_dir = None


settings = Settings()
