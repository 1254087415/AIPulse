"""Unit tests for /api/settings routes.

Covers:
  - GET returns masked secrets (apikey never leaked in full)
  - GET groups fields by section (kimi / obsidian / wechat / feishu)
  - PATCH empty / masked secret preserves existing value
  - PATCH new value persists and is observable via to_client_dict
  - PATCH invalid obsidian vault path raises 400
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from aipulse.core.config import AppSettings
from aipulse.web.routes import get_settings_route, patch_settings_route

# `routes.py` imports `get_settings as get_global_settings` to avoid clashing
# with the path-parameter naming convention; tests patch under that alias.
GET_SETTINGS_TARGET = "aipulse.web.routes.get_global_settings"
RESET_SETTINGS_TARGET = "aipulse.web.routes.reset_global_settings"


def _build_settings(
    *,
    kimi_key: str = "sk-initial-kimi-1234567890",
    obsidian_path: str | None = None,
    wechat_secret: str = "wechat-initial-1234567890",
    feishu_secret: str = "feishu-initial-1234567890",
    tmp_path: Path | None = None,
) -> AppSettings:
    """Construct a real AppSettings with controllable secrets.

    Each test gets its own ``data_dir`` (under tmp_path) so the persisted
    ``settings.json`` from one test cannot leak secrets into another. The
    settings loader in ``model_post_init`` re-reads persisted JSON, so a
    shared ``data/`` directory would silently overwrite this fixture's
    secrets with whatever the previous run left behind.

    obsidian_path defaults to the same tmp_path/data dir so the "vault
    must exist" validation passes. Pass an explicit path for invalid-path
    tests.
    """
    import tempfile

    if tmp_path is None:
        tmp_path = Path(tempfile.mkdtemp(prefix="aipulse-settings-"))
    if obsidian_path is None:
        obsidian_path = tmp_path / "vault"
    data_dir = tmp_path / "data"
    return AppSettings(
        data_dir=data_dir,
        download_dir=data_dir / "downloads",
        kimi_api_key=kimi_key,
        kimi_base_url="https://api.kimi.com/coding/v1",
        kimi_model="kimi-for-coding",
        obsidian_vault_path=Path(obsidian_path),
        obsidian_archive_folder="AIPulse",
        wechat_appid="wx-test",
        wechat_appsecret=wechat_secret,
        wechat_template_id="tpl-1",
        feishu_webhook_url="https://open.feishu.cn/hook",
        feishu_secret=feishu_secret,
    )


async def test_get_settings_masks_secrets(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path=tmp_path)
    with patch(GET_SETTINGS_TARGET, return_value=settings):
        response = await get_settings_route()

    assert response["success"] is True
    data = response["data"]

    # Real value never exposed; mask format: first4 + "***" + last4
    kimi_value = data["kimi"]["kimi_api_key"]
    assert "sk-initial" not in kimi_value
    assert "1234567890" not in kimi_value  # body hidden
    assert "***" in kimi_value
    assert kimi_value.startswith("sk-i") and kimi_value.endswith("7890")

    wechat_value = data["wechat"]["wechat_appsecret"]
    assert "***" in wechat_value
    assert "wechat-initial" not in wechat_value

    feishu_value = data["feishu"]["feishu_secret"]
    assert "***" in feishu_value


async def test_get_settings_groups_by_section(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path=tmp_path)
    with patch(GET_SETTINGS_TARGET, return_value=settings):
        response = await get_settings_route()

    data = response["data"]
    # Required sections per spec §5.3
    assert set(data.keys()) >= {"kimi", "obsidian", "wechat", "feishu"}

    # Each section groups its own fields only
    assert "kimi_api_key" in data["kimi"]
    assert "kimi_model" in data["kimi"]
    assert "obsidian_vault_path" in data["obsidian"]
    assert "wechat_appid" in data["wechat"]
    assert "feishu_webhook_url" in data["feishu"]


async def test_get_settings_short_secret_is_fully_masked(tmp_path: Path) -> None:
    """Secrets shorter than 8 chars get fully masked to '***' (no prefix leak)."""
    settings = _build_settings(tmp_path=tmp_path, kimi_key="short")
    with patch(GET_SETTINGS_TARGET, return_value=settings):
        response = await get_settings_route()
    assert response["data"]["kimi"]["kimi_api_key"] == "***"


async def test_patch_settings_empty_secret_preserves_value(tmp_path: Path) -> None:
    """Empty string for secret must NOT clear the existing secret.

    Contract: AppSettings.update() mutates the existing instance in place
    and returns self. The original instance's secret is preserved because
    empty/masked values short-circuit out of the secret-mutation branch.
    """
    settings = _build_settings(tmp_path=tmp_path, kimi_key="sk-keep-me-9999888877776666")
    payload = MagicMock()
    payload.model_dump = MagicMock(return_value={"kimi_api_key": ""})

    with patch(GET_SETTINGS_TARGET, return_value=settings):
        with patch(RESET_SETTINGS_TARGET) as mock_reset:
            response = await patch_settings_route(payload)

    # reset_global_settings must NOT be called: update() mutates in place
    # and the cached singleton already reflects the new values.
    mock_reset.assert_not_called()
    assert response["success"] is True
    # Original instance's secret is preserved (in-memory update skips it
    # when value is empty or masked).
    assert settings.kimi_api_key.get_secret_value() == "sk-keep-me-9999888877776666"
    # The response must NOT leak the real value (it must show the masked form)
    kimi_value = response["data"]["kimi"]["kimi_api_key"]
    assert "sk-keep-me" not in kimi_value
    assert "***" in kimi_value


async def test_patch_settings_masked_secret_preserves_value(tmp_path: Path) -> None:
    """Masked placeholder like 'sk-***90' must NOT overwrite the real secret."""
    settings = _build_settings(tmp_path=tmp_path, kimi_key="sk-keep-me-9999888877776666")
    payload = MagicMock()
    payload.model_dump = MagicMock(return_value={"kimi_api_key": "sk-***66"})

    with patch(GET_SETTINGS_TARGET, return_value=settings):
        with patch(RESET_SETTINGS_TARGET):
            response = await patch_settings_route(payload)

    # Original instance untouched
    assert settings.kimi_api_key.get_secret_value() == "sk-keep-me-9999888877776666"
    # Response shows the mask, not the literal "sk-***66"
    kimi_value = response["data"]["kimi"]["kimi_api_key"]
    assert "sk-keep-me" not in kimi_value
    assert "***" in kimi_value


async def test_patch_settings_new_secret_overwrites(tmp_path: Path) -> None:
    """Non-empty, non-masked secret should overwrite the existing value.

    Contract: the PATCH response must reflect the new masked value.
    reset_global_settings is NOT called because update() mutates the
    cached singleton in place — the next GET picks up the new value
    without a cache clear.
    """
    settings = _build_settings(tmp_path=tmp_path, kimi_key="sk-old-value-1234567890")
    payload = MagicMock()
    payload.model_dump = MagicMock(
        return_value={"kimi_api_key": "sk-new-value-0987654321"}
    )

    with patch(GET_SETTINGS_TARGET, return_value=settings):
        with patch(RESET_SETTINGS_TARGET) as mock_reset:
            response = await patch_settings_route(payload)

    assert response["success"] is True
    mock_reset.assert_not_called()
    # Response shows the NEW value (still masked)
    kimi_value = response["data"]["kimi"]["kimi_api_key"]
    assert "sk-new-value" not in kimi_value
    assert kimi_value.startswith("sk-n") and kimi_value.endswith("4321")
    # The cached singleton now holds the new secret
    assert settings.kimi_api_key.get_secret_value() == "sk-new-value-0987654321"


async def test_patch_settings_updates_non_secret_field(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path=tmp_path)
    payload = MagicMock()
    payload.model_dump = MagicMock(
        return_value={"kimi_model": "kimi-k2-thinking", "kimi_api_key": ""}
    )

    with patch(GET_SETTINGS_TARGET, return_value=settings):
        with patch(RESET_SETTINGS_TARGET):
            response = await patch_settings_route(payload)

    assert response["data"]["kimi"]["kimi_model"] == "kimi-k2-thinking"
    # Original kimi key untouched (immutable contract)
    assert settings.kimi_api_key.get_secret_value() == "sk-initial-kimi-1234567890"


async def test_patch_settings_invalid_obsidian_path_returns_400(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path=tmp_path)
    payload = MagicMock()
    payload.model_dump = MagicMock(return_value={"obsidian_vault_path": "/no/such/dir/999"})

    with patch(GET_SETTINGS_TARGET, return_value=settings):
        with patch(RESET_SETTINGS_TARGET):
            with pytest.raises(HTTPException) as exc_info:
                await patch_settings_route(payload)

    assert exc_info.value.status_code == 400


async def test_patch_settings_response_returns_masked_secrets(tmp_path: Path) -> None:
    """After PATCH, the response must also mask secrets (no leak)."""
    settings = _build_settings(tmp_path=tmp_path)
    payload = MagicMock()
    payload.model_dump = MagicMock(
        return_value={"kimi_api_key": "sk-brand-new-key-aaaaaaaaaa"}
    )

    with patch(GET_SETTINGS_TARGET, return_value=settings):
        with patch(RESET_SETTINGS_TARGET):
            response = await patch_settings_route(payload)

    kimi_value = response["data"]["kimi"]["kimi_api_key"]
    assert "sk-brand-new-key" not in kimi_value
    assert "***" in kimi_value