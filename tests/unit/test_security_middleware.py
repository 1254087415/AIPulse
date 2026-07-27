"""Unit tests for verify_auth_header Bearer middleware."""

from __future__ import annotations

import pytest
from pydantic import SecretStr
from starlette.requests import Request

from aipulse.core.config import AppSettings, get_settings
from aipulse.web.security_middleware import verify_auth_header


def _make_request(headers: dict[str, str] | None = None) -> Request:
    """Build a minimal Request object with the given headers."""
    raw_headers = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/hotspots",
        "headers": raw_headers,
        "query_string": b"",
        "server": ("test", 80),
        "client": ("127.0.0.1", 12345),
        "scheme": "http",
        "root_path": "",
    }
    return Request(scope)


def _patch_token(monkeypatch: pytest.MonkeyPatch, value: str | None) -> None:
    """Replace the cached AppSettings.aipulse_api_token so monkeypatch restores it."""
    cached = get_settings()
    monkeypatch.setattr(cached, "aipulse_api_token", SecretStr(value or ""))


@pytest.mark.unit
def test_verify_auth_header_returns_true_when_token_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No configured token means verification is skipped (dev-friendly)."""
    _patch_token(monkeypatch, None)
    request = _make_request()
    assert verify_auth_header(request) is True


@pytest.mark.unit
def test_verify_auth_header_accepts_correct_bearer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Correct Bearer token passes."""
    _patch_token(monkeypatch, "secret123")
    request = _make_request({"Authorization": "Bearer secret123"})
    assert verify_auth_header(request) is True


@pytest.mark.unit
def test_verify_auth_header_rejects_wrong_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Wrong token fails."""
    _patch_token(monkeypatch, "secret123")
    request = _make_request({"Authorization": "Bearer wrong"})
    assert verify_auth_header(request) is False


@pytest.mark.unit
def test_verify_auth_header_rejects_missing_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing Authorization header when token is configured yields False."""
    _patch_token(monkeypatch, "secret123")
    request = _make_request()
    assert verify_auth_header(request) is False


@pytest.mark.unit
def test_verify_auth_header_rejects_non_bearer_scheme(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-Bearer auth scheme is rejected."""
    _patch_token(monkeypatch, "secret123")
    request = _make_request({"Authorization": "Basic secret123"})
    assert verify_auth_header(request) is False


@pytest.mark.unit
def test_verify_auth_header_rejects_legacy_x_token_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Legacy X-AIPulse-Token header is no longer accepted."""
    _patch_token(monkeypatch, "secret123")
    request = _make_request({"X-AIPulse-Token": "secret123"})
    assert verify_auth_header(request) is False


# ==============================================================
# AppSettings v0.3 new fields
# ==============================================================


@pytest.mark.unit
def test_settings_llm_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """AppSettings exposes llm_* defaults and learning_notification_enabled."""
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("KIMI_API_KEY", raising=False)
    monkeypatch.delenv("KIMI_BASE_URL", raising=False)
    monkeypatch.delenv("KIMI_MODEL", raising=False)
    monkeypatch.delenv("LEARNING_NOTIFICATION_ENABLED", raising=False)
    get_settings.cache_clear()

    # Construct with _env_file=None to bypass .env defaults so we observe
    # the model's true defaults.
    settings = AppSettings(_env_file=None)  # type: ignore[call-arg]
    # Defaults aligned with v0.4 minimax switch.
    assert settings.llm_base_url == "https://api.minimaxi.com/v1"
    assert settings.llm_model == "MiniMax-M2.5"
    assert settings.learning_notification_enabled is True
    # SecretStr default is empty
    assert settings.llm_api_key.get_secret_value() == ""


@pytest.mark.unit
def test_settings_llm_overrides_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Env vars override the llm defaults."""
    monkeypatch.setenv("LLM_API_KEY", "sk-llm-fake")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.com/v1")
    monkeypatch.setenv("LLM_MODEL", "custom-model")
    monkeypatch.setenv("LEARNING_NOTIFICATION_ENABLED", "false")
    get_settings.cache_clear()

    settings = get_settings()
    assert settings.llm_api_key.get_secret_value() == "sk-llm-fake"
    assert settings.llm_base_url == "https://example.com/v1"
    assert settings.llm_model == "custom-model"
    assert settings.learning_notification_enabled is False

