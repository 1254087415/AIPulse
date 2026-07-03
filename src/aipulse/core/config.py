"""Application configuration singleton."""

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

_SECRET_KEYS = {
    "llm_api_key",
    "feishu_secret",
    "wechat_appsecret",
}


class AppSettings(BaseSettings):
    """Global application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "sqlite+aiosqlite:///data/aipulse.db"

    # LLM
    llm_provider: str = "openai"
    llm_api_key: SecretStr = Field(default=SecretStr(""))
    llm_base_url: str = "https://api.kimi.com/coding/v1"
    llm_model: str = "kimi-for-coding"

    # Whisper
    whisper_model: str = "small"

    # Obsidian
    obsidian_vault_path: Path = Path.home() / "Documents" / "Obsidian Vault"
    obsidian_archive_folder: str = "AIPulse"

    # Feishu
    feishu_webhook_url: str = ""
    feishu_secret: SecretStr = Field(default=SecretStr(""))

    # WeChat
    wechat_appid: str = ""
    wechat_appsecret: SecretStr = Field(default=SecretStr(""))
    wechat_template_id: str = ""
    wechat_openid: str = ""

    # Data dirs
    data_dir: Path = Path("./data")
    download_dir: Path = Path("./data/downloads")

    # yt-dlp
    ytdlp_browser_cookies: str = "chrome"
    ytdlp_user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )

    # HTTP clients
    http_user_agent_mobile: str = (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
        "MicroMessenger/8.0.38(0x18002625) NetType/WIFI Language/zh_CN"
    )

    # Logging
    log_level: str = "INFO"

    def model_post_init(self, __context: Any) -> None:
        """Ensure data directories exist after initialization."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.download_dir.mkdir(parents=True, exist_ok=True)

    @property
    def settings_path(self) -> Path:
        """Path to the persisted settings JSON file."""
        return self.data_dir / "settings.json"

    def save(self) -> None:
        """Persist non-secret overrides to a JSON file under data/settings.json."""
        public = self.to_public_dict()
        # Only persist keys that are safe to write and may be changed at runtime.
        persist_keys = {
            "llm_provider",
            "llm_base_url",
            "llm_model",
            "whisper_model",
            "obsidian_vault_path",
            "obsidian_archive_folder",
            "feishu_webhook_url",
            "wechat_appid",
            "wechat_template_id",
            "wechat_openid",
            "data_dir",
            "download_dir",
            "log_level",
            "database_url",
            "ytdlp_browser_cookies",
            "ytdlp_user_agent",
            "http_user_agent_mobile",
        }
        payload = {key: public[key] for key in persist_keys if key in public}
        try:
            self.settings_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
        except OSError:
            logger.exception("Failed to save settings to %s", self.settings_path)
            raise

    def to_public_dict(self) -> dict[str, Any]:
        """Return a public-safe dict with secrets masked."""
        result: dict[str, Any] = {}
        for key, value in self.model_dump().items():
            if key in _SECRET_KEYS:
                result[key] = self._mask_secret(value)
            else:
                result[key] = value
        return result

    def update(self, **changes: Any) -> "AppSettings":
        """Return a new settings instance with the given changes applied."""
        current = self.model_dump()
        for key in _SECRET_KEYS:
            if key in changes and changes[key]:
                current[key] = changes[key]
            elif key not in changes:
                current[key] = self._get_secret_value(key)
        for key, value in changes.items():
            if key not in _SECRET_KEYS:
                current[key] = value
        # Ensure Path fields are converted back to Path objects.
        path_keys = {"data_dir", "download_dir", "obsidian_vault_path"}
        for key in path_keys:
            if key in current and not isinstance(current[key], Path):
                current[key] = Path(current[key])
        return AppSettings(**current)

    def validate_obsidian_vault(self) -> None:
        """Validate that the configured Obsidian vault path exists."""
        if not self.obsidian_vault_path.exists():
            raise FileNotFoundError(
                f"Obsidian vault path does not exist: {self.obsidian_vault_path}"
            )

    def _get_secret_value(self, key: str) -> str:
        value = getattr(self, key, None)
        if isinstance(value, SecretStr):
            return value.get_secret_value()
        return str(value) if value is not None else ""

    @staticmethod
    def _mask_secret(value: Any) -> str:
        raw = value.get_secret_value() if isinstance(value, SecretStr) else str(value)
        if not raw:
            return ""
        if len(raw) <= 8:
            return "***"
        return raw[:4] + "***" + raw[-4:]


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Return the cached global settings instance."""
    return AppSettings()


def reset_settings() -> None:
    """Clear the cached settings instance (useful in tests)."""
    get_settings.cache_clear()
