"""Application configuration singleton."""

import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

_SECRET_KEYS = {
    "llm_api_key",
    "kimi_api_key",
    "feishu_secret",
    "wechat_appsecret",
    "wechat_bot_token",
    "aipulse_api_token",
}


class AppSettings(BaseSettings):
    """Global application settings loaded from environment variables.

    Load order (later wins):
      1. Built-in defaults declared on the model.
      2. ``.env`` file in the working directory.
      3. ``data/settings.json`` produced by ``AppSettings.save()`` so the
         UI's PATCH /api/settings call persists across restarts.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/aipulse.db"
    auto_create_tables: bool = False

    # LLM
    llm_provider: str = "openai"
    llm_api_key: SecretStr = Field(default=SecretStr(""))
    llm_base_url: str = "https://api.kimi.com/coding/v1"
    llm_model: str = "kimi-for-coding"

    # v0.3 — Kimi specific (independent config; used by follow + learning phase)
    # NOTE: kimi_* defaults are aligned with the Kimi coding endpoint per
    # v0.3 spec §5.3 (kimi-for-coding + api.kimi.com/coding/v1). If the user
    # later decides to keep llm_* as the canonical Kimi path instead, this
    # block can be reverted.
    kimi_api_key: SecretStr = Field(default=SecretStr(""))
    kimi_base_url: str = "https://api.kimi.com/coding/v1"
    kimi_model: str = "kimi-for-coding"
    learning_notification_enabled: bool = True

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
    wechat_bot_token: SecretStr = Field(default=SecretStr(""))
    wechat_to_user: str = Field(default="")
    wechat_account_id: str = Field(default="")
    wechat_context_token_file: str = Field(default="")
    wechat_send_script: str = Field(default="")

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

    # API auth
    aipulse_api_token: SecretStr = Field(default=SecretStr(""))

    def model_post_init(self, __context: Any) -> None:
        """Ensure data directories exist after initialization."""
        # Guard against recursive re-entry: Pydantic-settings sometimes
        # re-invokes ``__init__``/``model_post_init`` while resolving
        # source values, which would otherwise attempt to merge persisted
        # JSON state into an already-merging instance and blow the stack.
        if getattr(self, "_aipulse_post_init_done", False):
            return
        object.__setattr__(self, "_aipulse_post_init_done", True)

        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.scripts_dir.mkdir(parents=True, exist_ok=True)

        # Reload from the persisted JSON if it exists, so changes made via
        # PATCH /api/settings survive process restarts.
        persisted = self._load_persisted()
        if persisted:
            try:
                # Re-construct via model_validate so Pydantic re-runs the field
                # validators and converts Path / SecretStr etc. correctly.
                merged = self.model_validate({**self.model_dump(), **persisted})
                object.__setattr__(self, "__dict__", merged.__dict__)
            except Exception:  # noqa: BLE001 — defensive: never block init
                logger.exception("Failed to merge persisted settings")

    def _load_persisted(self) -> dict[str, Any]:
        """Read data/settings.json if present and return only known keys."""
        path = self.settings_path
        if not path.exists():
            return {}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.exception("Failed to read persisted settings at %s", path)
            return {}
        if not isinstance(raw, dict):
            return {}
        # Drop unknown keys so we don't re-introduce removed fields.
        valid = set(self.model_dump().keys())
        return {k: v for k, v in raw.items() if k in valid}

    @property
    def scripts_dir(self) -> Path:
        """Directory where external push scripts must reside."""
        return self.data_dir / "scripts"

    @property
    def settings_path(self) -> Path:
        """Path to the persisted settings JSON file."""
        return self.data_dir / "settings.json"

    @staticmethod
    def validate_script_path(path: str | Path, data_dir: Path) -> Path:
        """Validate that an external script path is safe to execute.

        Raises:
            ValueError: If the path is empty, contains traversal or shell
                metacharacters, is not a regular file, or is outside the
                configured ``data_dir/scripts`` directory.
        """
        if not path:
            raise ValueError("script path is empty")
        raw = str(path).strip()
        if not raw:
            raise ValueError("script path is empty")
        if ".." in raw or re.search(r"[;|&$\\`\n\r]", raw):
            raise ValueError(f"script path contains unsafe characters: {raw}")
        resolved = Path(raw).expanduser().resolve()
        scripts_dir = (data_dir / "scripts").resolve()
        if not resolved.is_relative_to(scripts_dir):
            raise ValueError(
                f"script must be located under {scripts_dir}: {resolved}"
            )
        if not resolved.is_file():
            raise ValueError(f"script is not a regular file: {resolved}")
        return resolved

    def save(self) -> None:
        """Persist runtime overrides to a JSON file under data/settings.json.

        Non-secret overrides and non-empty secret values are written so they
        survive process restarts. Empty secret values are skipped so a PATCH
        with no secret field does not overwrite a previously persisted value
        (CLAUDE.md: 保存时必须保留原有 secrets).
        """
        full = self.to_client_dict()
        # Only persist keys that may be changed at runtime.
        persist_keys = {
            "llm_provider",
            "llm_base_url",
            "llm_model",
            "kimi_base_url",
            "kimi_model",
            "learning_notification_enabled",
            "whisper_model",
            "obsidian_vault_path",
            "obsidian_archive_folder",
            "feishu_webhook_url",
            "wechat_appid",
            "wechat_template_id",
            "wechat_openid",
            "wechat_to_user",
            "wechat_account_id",
            "wechat_context_token_file",
            "wechat_send_script",
            "data_dir",
            "download_dir",
            "log_level",
            "database_url",
            "ytdlp_browser_cookies",
            "ytdlp_user_agent",
            "http_user_agent_mobile",
        }
        payload = {key: full[key] for key in persist_keys if key in full}
        # Secrets: persist only when the user explicitly set a non-empty value
        # via PATCH /api/settings. Empty secrets are omitted so .env remains
        # the source of truth for unset secrets and a partial PATCH cannot
        # silently clear a previously persisted secret.
        for key in _SECRET_KEYS:
            value = full.get(key)
            if value:
                payload[key] = value
        try:
            self.settings_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
        except OSError:
            logger.exception("Failed to save settings to %s", self.settings_path)
            raise

    def to_public_dict(self) -> dict[str, Any]:
        """Return a public-safe dict with secrets masked (for logs)."""
        result: dict[str, Any] = {}
        for key, value in self.model_dump().items():
            if key in _SECRET_KEYS:
                result[key] = self._mask_secret(value)
            else:
                result[key] = value
        return result

    def to_client_dict(self) -> dict[str, Any]:
        """Return a plain dict with real secret values for the UI."""
        result: dict[str, Any] = {}
        for key, value in self.model_dump().items():
            if key in _SECRET_KEYS and isinstance(value, SecretStr):
                result[key] = value.get_secret_value()
            else:
                result[key] = value
        return result

    def update(self, **changes: Any) -> "AppSettings":
        """Apply changes in place and return self.

        Mutating the existing instance avoids re-running ``model_post_init``
        on the new instance (which would re-merge persisted values from
        ``data/settings.json`` and silently overwrite any caller-provided
        changes that conflict with on-disk state).
        """
        # Validate security-sensitive paths before mutating.
        new_script = changes.get("wechat_send_script")
        if new_script:
            self.validate_script_path(new_script, self.data_dir)

        for key in _SECRET_KEYS:
            if key in changes:
                new_value = changes[key]
                if new_value and not self._is_masked_secret(new_value):
                    self._set_secret_value(key, str(new_value))
                # else: preserve existing secret when value is empty/masked/missing
        for key, value in changes.items():
            if key not in _SECRET_KEYS:
                if key in {"data_dir", "download_dir", "obsidian_vault_path"}:
                    object.__setattr__(self, key, Path(value) if value else Path("."))
                else:
                    object.__setattr__(self, key, value)
        return self

    def _set_secret_value(self, key: str, value: str) -> None:
        """Replace the SecretStr field on a frozen model without re-validation."""
        current = getattr(self, key, None)
        if isinstance(current, SecretStr):
            current = SecretStr(value)
            object.__setattr__(self, key, current)
        else:
            object.__setattr__(self, key, SecretStr(value))

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

    @staticmethod
    def _is_masked_secret(value: Any) -> bool:
        """Return True if value looks like a masked secret returned to the UI."""
        return "***" in str(value)


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Return the cached global settings instance."""
    return AppSettings()


def reset_settings() -> None:
    """Clear the cached settings instance (useful in tests)."""
    get_settings.cache_clear()
