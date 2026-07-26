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
    assert settings.llm_base_url == "https://api.minimaxi.com/v1"
    assert settings.llm_model == "MiniMax-M2.5"
    assert settings.llm_provider == "openai"


@pytest.mark.unit
def test_public_dict_masks_secrets(settings: AppSettings) -> None:
    settings = settings.update(llm_api_key="sk-secret-value")
    public = settings.to_public_dict()
    assert public["llm_api_key"] == "sk-s***alue"
    assert public["llm_base_url"] == "https://api.minimaxi.com/v1"


@pytest.mark.unit
def test_save_persists_non_secret_overrides(settings: AppSettings) -> None:
    settings = settings.update(
        llm_model="MiniMax-Text-01", llm_api_key="sk-secret-value"
    )
    settings.save()
    persisted = json.loads(settings.settings_path.read_text(encoding="utf-8"))
    assert persisted["llm_model"] == "MiniMax-Text-01"


@pytest.mark.unit
def test_save_persists_non_empty_secrets(settings: AppSettings) -> None:
    """PATCH /api/settings writes non-empty secrets to settings.json so they
    survive process restarts (CLAUDE.md: 必须保留 secrets).

    Empty secrets are skipped so a PATCH with no secret does not overwrite
    a previously persisted value with an empty string. Non-empty secrets are
    masked on disk (first4***last4) so a leaked settings.json cannot leak
    credentials (E6 spec §9.5 follow-up) — the real secret stays in memory
    via ``to_client_dict()``.
    """
    settings = settings.update(
        llm_api_key="sk-persist-llm-1234567890",
        wechat_appsecret="wechat-persist-1234567890",
        feishu_secret="feishu-persist-1234567890",
    )
    settings.save()
    persisted = json.loads(settings.settings_path.read_text(encoding="utf-8"))
    # Real values never written to disk; only masked previews survive.
    assert persisted["llm_api_key"] == "sk-p***7890"
    assert persisted["wechat_appsecret"] == "wech***7890"
    assert persisted["feishu_secret"] == "feis***7890"


@pytest.mark.unit
def test_save_skips_empty_secrets(settings: AppSettings) -> None:
    """An empty secret must not overwrite a previously persisted value.
    This is the in-memory guard against accidental clearing on partial PATCH.
    """
    settings = settings.update(llm_api_key="sk-keep-me-9999888877776666")
    settings.save()
    # Now simulate a PATCH that only updates a non-secret field; the
    # update() call returns self without touching the secret (which is
    # preserved in memory); save() must therefore NOT write an empty
    # llm_api_key into the JSON.
    settings = settings.update(llm_model="MiniMax-Text-01")
    settings.save()
    persisted = json.loads(settings.settings_path.read_text(encoding="utf-8"))
    assert persisted["llm_model"] == "MiniMax-Text-01"
    # Secret field omitted entirely when no new non-empty value is set.
    assert "llm_api_key" not in persisted or persisted["llm_api_key"] != ""


@pytest.mark.unit
def test_loaded_settings_use_persisted_secret(tmp_path: Path) -> None:
    """Verify the E6 on-disk secret contract: real values never survive a
    process restart, but a masked preview is persisted so the UI can show
    "secret is set" without leaking the credential.

    Pre-E6 behaviour (real secret round-tripped via settings.json) was
    retired in favour of leaking nothing on disk (spec §9.5 / E6 follow-up).
    The new contract: ``save()`` writes the masked preview, the next process
    boot loads that masked preview, ``update()`` recognises the ``***``
    pattern and discards it so the env (or empty fallback) is the source of
    truth for the real value.
    """
    reset_settings()
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    # First AppSettings writes the secret via save()
    first = AppSettings(
        data_dir=data_dir,
        download_dir=data_dir / "downloads",
        database_url=f"sqlite+aiosqlite:///{tmp_path}/aipulse.db",
    )
    first = first.update(llm_api_key="sk-restart-survive-AAAAAAAA")
    first.save()

    # On-disk value is masked, not plaintext — that's the security contract.
    persisted = json.loads(first.settings_path.read_text(encoding="utf-8"))
    assert persisted["llm_api_key"] == "sk-r***AAAA"

    # Second AppSettings is constructed fresh (no in-memory carryover)
    # against the same data_dir; its model_post_init reads settings.json,
    # detects the masked preview via ``***``, and discards it so the real
    # value falls back to LLM_API_KEY env (test placeholder in this run).
    reset_settings()
    second = AppSettings(
        data_dir=data_dir,
        download_dir=data_dir / "downloads",
        database_url=f"sqlite+aiosqlite:///{tmp_path}/aipulse.db",
    )
    # In this test the env provides a placeholder, so the secret reflects the
    # env, NOT the masked on-disk preview.
    assert second._get_secret_value("llm_api_key") == "sk-test-placeholder-llm"


@pytest.mark.unit
def test_client_dict_returns_real_secret_values(settings: AppSettings) -> None:
    settings = settings.update(llm_api_key="sk-secret-value")
    client = settings.to_client_dict()
    assert client["llm_api_key"] == "sk-secret-value"
    assert client["llm_base_url"] == "https://api.minimaxi.com/v1"


@pytest.mark.unit
def test_update_returns_same_instance_with_mutation(settings: AppSettings) -> None:
    """update() mutates in place and returns self. Constructing a new
    instance would re-run model_post_init and re-merge persisted JSON,
    silently overwriting caller-provided changes — see config.py
    ``update()`` docstring for the rationale.
    """
    updated = settings.update(llm_model="MiniMax-Text-01")
    assert updated is settings
    assert updated.llm_model == "MiniMax-Text-01"


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


# =====================================================================
# v0.4 minimax switch — legacy kimi_*/minimax_* → llm_* migration
# =====================================================================


@pytest.mark.unit
def test_load_persisted_only_kimi_prefix(tmp_path: Path) -> None:
    """Legacy kimi_* keys are migrated to llm_* on first load."""
    reset_settings()
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    settings_file = data_dir / "settings.json"
    settings_file.write_text(
        json.dumps(
            {
                "kimi_api_key": "sk-old-kimi-key",
                "kimi_base_url": "https://api.kimi.com/coding/v1",
                "kimi_model": "kimi-for-coding",
            }
        ),
        encoding="utf-8",
    )
    settings = AppSettings(
        data_dir=data_dir,
        download_dir=data_dir / "downloads",
        database_url=f"sqlite+aiosqlite:///{tmp_path}/aipulse.db",
    )
    assert settings.llm_api_key.get_secret_value() == "sk-old-kimi-key"
    assert settings.llm_base_url == "https://api.kimi.com/coding/v1"
    assert settings.llm_model == "kimi-for-coding"
    # After migration the legacy keys should be dropped from disk.
    migrated = json.loads(settings_file.read_text(encoding="utf-8"))
    assert "kimi_api_key" not in migrated
    assert "kimi_base_url" not in migrated
    assert "kimi_model" not in migrated


@pytest.mark.unit
def test_load_persisted_only_minimax_prefix(tmp_path: Path) -> None:
    """Legacy minimax_* keys are migrated to llm_* on first load."""
    reset_settings()
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    settings_file = data_dir / "settings.json"
    settings_file.write_text(
        json.dumps(
            {
                "minimax_api_key": "sk-old-minimax-key",
                "minimax_base_url": "https://api.minimaxi.com/v1",
                "minimax_model": "MiniMax-Text-01",
            }
        ),
        encoding="utf-8",
    )
    settings = AppSettings(
        data_dir=data_dir,
        download_dir=data_dir / "downloads",
        database_url=f"sqlite+aiosqlite:///{tmp_path}/aipulse.db",
    )
    assert settings.llm_api_key.get_secret_value() == "sk-old-minimax-key"
    assert settings.llm_base_url == "https://api.minimaxi.com/v1"
    assert settings.llm_model == "MiniMax-Text-01"
    migrated = json.loads(settings_file.read_text(encoding="utf-8"))
    assert "minimax_api_key" not in migrated


@pytest.mark.unit
def test_load_persisted_double_prefix_prefers_minimax(tmp_path: Path) -> None:
    """Legacy kimi_* + minimax_* both present: minimax_* wins (closest to llm_*)."""
    reset_settings()
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    settings_file = data_dir / "settings.json"
    settings_file.write_text(
        json.dumps(
            {
                "kimi_api_key": "sk-old-kimi-key",
                "kimi_base_url": "https://api.kimi.com/coding/v1",
                "kimi_model": "kimi-for-coding",
                "minimax_api_key": "sk-newer-minimax-key",
                "minimax_base_url": "https://api.minimaxi.com/v1",
                "minimax_model": "MiniMax-Text-01",
            }
        ),
        encoding="utf-8",
    )
    settings = AppSettings(
        data_dir=data_dir,
        download_dir=data_dir / "downloads",
        database_url=f"sqlite+aiosqlite:///{tmp_path}/aipulse.db",
    )
    assert settings.llm_api_key.get_secret_value() == "sk-newer-minimax-key"
    assert settings.llm_base_url == "https://api.minimaxi.com/v1"
    assert settings.llm_model == "MiniMax-Text-01"
    migrated = json.loads(settings_file.read_text(encoding="utf-8"))
    assert "kimi_api_key" not in migrated
    assert "minimax_api_key" not in migrated
