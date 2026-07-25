"""Pydantic schemas for web API endpoints (currently: settings)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class KimiSettings(BaseModel):
    """Kimi (LLM) related settings; secrets are masked in responses."""

    model_config = ConfigDict(extra="ignore")

    kimi_api_key: str = Field(default="", description="Masked placeholder when populated")
    kimi_base_url: str = ""
    kimi_model: str = ""
    learning_notification_enabled: bool = True


class ObsidianSettings(BaseModel):
    """Obsidian vault settings."""

    model_config = ConfigDict(extra="ignore")

    obsidian_vault_path: str = ""
    obsidian_archive_folder: str = ""


class WechatSettings(BaseModel):
    """WeChat push channel settings; secrets are masked."""

    model_config = ConfigDict(extra="ignore")

    wechat_appid: str = ""
    wechat_appsecret: str = Field(default="", description="Masked placeholder when populated")
    wechat_template_id: str = ""
    wechat_openid: str = ""
    wechat_to_user: str = ""
    wechat_account_id: str = ""
    wechat_bot_token: str = Field(default="", description="Masked placeholder when populated")
    wechat_context_token_file: str = ""
    wechat_send_script: str = ""


class FeishuSettings(BaseModel):
    """Feishu webhook settings; secrets are masked."""

    model_config = ConfigDict(extra="ignore")

    feishu_webhook_url: str = ""
    feishu_secret: str = Field(default="", description="Masked placeholder when populated")


class SettingsResponse(BaseModel):
    """Top-level envelope for GET /api/settings.

    Each section is a flat dict so the frontend can group edits by panel.
    """

    model_config = ConfigDict(extra="ignore")

    kimi: dict[str, Any] = Field(default_factory=dict)
    obsidian: dict[str, Any] = Field(default_factory=dict)
    wechat: dict[str, Any] = Field(default_factory=dict)
    feishu: dict[str, Any] = Field(default_factory=dict)


class SettingsUpdate(BaseModel):
    """Partial update for PATCH /api/settings.

    All fields optional. Secrets may be empty string — that signals "preserve
    existing value" so the UI can safely send back the masked placeholder
    after a round trip.
    """

    model_config = ConfigDict(extra="ignore")

    # Kimi
    kimi_api_key: str | None = None
    kimi_base_url: str | None = None
    kimi_model: str | None = None
    learning_notification_enabled: bool | None = None

    # Obsidian
    obsidian_vault_path: str | None = None
    obsidian_archive_folder: str | None = None

    # WeChat
    wechat_appid: str | None = None
    wechat_appsecret: str | None = None
    wechat_template_id: str | None = None
    wechat_openid: str | None = None
    wechat_to_user: str | None = None
    wechat_account_id: str | None = None
    wechat_bot_token: str | None = None
    wechat_context_token_file: str | None = None
    wechat_send_script: str | None = None

    # Feishu
    feishu_webhook_url: str | None = None
    feishu_secret: str | None = None