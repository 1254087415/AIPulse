"""Tests for AppSettings load/save and public dict."""

import json
from pathlib import Path

import pytest

from aipulse.core.config import AppSettings, get_settings, reset_settings


@pytest.fixture
def settings(tmp_path: Path) -> AppSettings:
    reset_settings()
    return AppSettings(
        data_dir=tmp_path / "data",
        download_dir=tmp_path / "data" / "downloads",
        database_url=f"sqlite+aiosqlite:///{tmp_path}/aipulse.db",
    )


@pytest.mark.unit
def test_default_llm_settings(settings: AppSettings) -> None:
    assert settings.llm_base_url == "https://api.kimi.com/coding/v1"
    assert settings.llm_model == "kimi-for-coding"
    assert settings.llm_provider == "openai"


@pytest.mark.unit
def test_public_dict_masks_secrets(settings: AppSettings) -> None:
    settings = settings.update(llm_api_key="sk-secret-value")
    public = settings.to_public_dict()
    assert public["llm_api_key"] == "sk-s***alue"
    assert public["llm_base_url"] == "https://api.kimi.com/coding/v1"


@pytest.mark.unit
def test_save_persists_non_secret_overrides(settings: AppSettings) -> None:
    settings = settings.update(llm_model="kimi-latest")
    settings.save()
    persisted = json.loads(settings.settings_path.read_text(encoding="utf-8"))
    assert persisted["llm_model"] == "kimi-latest"
    assert "llm_api_key" not in persisted


@pytest.mark.unit
def test_update_returns_new_instance(settings: AppSettings) -> None:
    updated = settings.update(llm_model="kimi-latest")
    assert updated is not settings
    assert updated.llm_model == "kimi-latest"
    assert settings.llm_model == "kimi-for-coding"


@pytest.mark.unit
def test_validate_obsidian_vault_raises_when_missing(settings: AppSettings) -> None:
    settings = settings.update(obsidian_vault_path=Path("/nonexistent/vault"))
    with pytest.raises(FileNotFoundError):
        settings.validate_obsidian_vault()


@pytest.mark.unit
def test_get_settings_cached() -> None:
    reset_settings()
    first = get_settings()
    second = get_settings()
    assert first is second


@pytest.mark.unit
def test_wechat_bot_fields_and_secret_handling(tmp_path: Path) -> None:
    reset_settings()
    scripts_dir = tmp_path / "data" / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    send_script = scripts_dir / "send.sh"
    send_script.write_text("#!/usr/bin/env bash\necho ok\n")
    settings = AppSettings(
        data_dir=tmp_path / "data",
        download_dir=tmp_path / "data" / "downloads",
        database_url="mysql+aiomysql://user:pass@localhost:3306/aipulse",
        wechat_bot_token="secret-token",
        wechat_to_user="to-user",
        wechat_account_id="account-id",
        wechat_context_token_file="/tmp/token.json",
        wechat_send_script=str(send_script),
    )
    assert settings.database_url.startswith("mysql+aiomysql")
    assert settings.wechat_to_user == "to-user"
    assert settings.wechat_account_id == "account-id"
    assert settings.wechat_context_token_file == "/tmp/token.json"
    assert settings.wechat_send_script == str(send_script)
    public = settings.to_public_dict()
    assert "***" in public["wechat_bot_token"]
    assert "secret" not in public["wechat_bot_token"]
    updated = settings.update(wechat_bot_token="***")
    assert updated.wechat_bot_token.get_secret_value() == "secret-token"
