"""Helpers to project AppSettings into the grouped SettingsResponse shape.

Secrets are always masked in the response. Updates preserve existing secrets
when the incoming value is empty or already-masked (UI round-trip safe).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aipulse.core.config import AppSettings

# Field groups keyed by section name. Order is the order in the response.
_SECTIONS: dict[str, tuple[str, ...]] = {
    "llm": (
        "llm_api_key",
        "llm_base_url",
        "llm_model",
        "learning_notification_enabled",
    ),
    "obsidian": ("obsidian_vault_path", "obsidian_archive_folder"),
    "wechat": (
        "wechat_appid",
        "wechat_appsecret",
        "wechat_template_id",
        "wechat_openid",
        "wechat_to_user",
        "wechat_account_id",
        "wechat_bot_token",
        "wechat_context_token_file",
        "wechat_send_script",
    ),
    "feishu": ("feishu_webhook_url", "feishu_secret"),
}


def build_settings_response(settings: AppSettings) -> dict[str, Any]:
    """Return a {section: {field: value_or_masked}} dict."""
    public = settings.to_public_dict()
    grouped: dict[str, Any] = {}
    for section, fields in _SECTIONS.items():
        bucket: dict[str, Any] = {}
        for field in fields:
            if field in public:
                bucket[field] = _serialise(public[field])
        grouped[section] = bucket
    return grouped


def update_settings(settings: AppSettings, changes: dict[str, Any]) -> AppSettings:
    """Apply changes to a settings instance, preserving empty/masked secrets.

    Delegates to AppSettings.update() which already implements the secret
    preservation contract; we just want a single chokepoint for tests and
    any future validation.
    """
    # Coerce path fields back to Path before delegating.
    for path_field in ("obsidian_vault_path",):
        if path_field in changes and isinstance(changes[path_field], str):
            changes[path_field] = Path(changes[path_field])
    return settings.update(**changes)


def _serialise(value: Any) -> Any:
    """Make Path / SecretStr / etc. JSON-friendly."""
    if isinstance(value, Path):
        return str(value)
    return value