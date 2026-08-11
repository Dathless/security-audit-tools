from __future__ import annotations

import secrets
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.yaml"


class AppSettings(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "info"
    local_token: str = ""
    require_local_token: bool = True
    allowed_origins: list[str] = Field(default_factory=lambda: ["http://127.0.0.1:5173"])


class DatabaseSettings(BaseModel):
    url: str = "sqlite:///./data/security_audit.db"


class ModuleSettings(BaseModel):
    enabled: bool = True
    schedule: Optional[str] = None
    extra: dict = Field(default_factory=dict)

    def get(self, key: str, default=None):
        return self.extra.get(key, default)

    @classmethod
    def from_config(cls, cfg: dict) -> "ModuleSettings":
        raw = dict(cfg or {})
        enabled = raw.pop("enabled", True)
        schedule = raw.pop("schedule", None)
        return cls(enabled=enabled, schedule=schedule, extra=raw)


class Settings(BaseModel):
    app: AppSettings = Field(default_factory=AppSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    modules: dict[str, ModuleSettings] = Field(default_factory=dict)


class Config:
    """Loads config.yaml once; exposes typed access and keeps module sections generic."""

    def __init__(self, path: Path = CONFIG_PATH) -> None:
        self.path = Path(path)
        self.raw: dict = {}
        if self.path.exists():
            with open(self.path, "r", encoding="utf-8") as fh:
                self.raw = yaml.safe_load(fh) or {}
        self.settings = Settings.model_validate(self.raw or {})

    @property
    def app(self) -> AppSettings:
        return self.settings.app

    @property
    def database(self) -> DatabaseSettings:
        return self.settings.database

    def module(self, module_id: str) -> ModuleSettings:
        m = self.settings.modules.get(module_id)
        if m is None:
            return ModuleSettings(enabled=False, schedule=None, extra={})
        return m

    def ensure_local_token(self) -> str:
        """Generates and persists a local token if none configured."""
        if self.settings.app.local_token:
            return self.settings.app.local_token
        token = secrets.token_urlsafe(32)
        self.settings.app.local_token = token
        self.raw.setdefault("app", {})["local_token"] = token
        self._persist()
        return token

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as fh:
            yaml.safe_dump(self.raw, fh, allow_unicode=True, sort_keys=False)


config = Config()