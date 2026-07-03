"""Tests for WeChat push strategy."""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from aipulse.core.config import AppSettings
from aipulse.pushers.base import PushMessage
from aipulse.pushers.wechat import TOKEN_URL, WechatPushStrategy


@pytest.fixture
def wechat_settings() -> AppSettings:
    return AppSettings(
        wechat_appid="appid-123",
        wechat_appsecret="secret-123",
        wechat_template_id="template-123",
        wechat_openid="openid-123",
    )


@pytest.fixture
def wechat_strategy(wechat_settings: AppSettings) -> WechatPushStrategy:
    return WechatPushStrategy(wechat_settings, client=httpx.AsyncClient(transport=httpx.MockTransport(None)))


@pytest.mark.unit
async def test_send_returns_false_when_not_configured() -> None:
    settings = AppSettings()
    strategy = WechatPushStrategy(
        settings, client=httpx.AsyncClient(transport=httpx.MockTransport(None))
    )
    message = PushMessage(title="T", summary="S", url="https://example.com")
    result = await strategy.send(message)
    assert result is False


@pytest.mark.unit
async def test_send_success(wechat_strategy: WechatPushStrategy) -> None:
    message = PushMessage(title="Title", summary="Summary", url="https://example.com")

    token_response = MagicMock()
    token_response.raise_for_status = MagicMock()
    token_response.json.return_value = {"access_token": "token-abc"}

    send_response = MagicMock()
    send_response.raise_for_status = MagicMock()

    wechat_strategy.client.get = AsyncMock(return_value=token_response)
    wechat_strategy.client.post = AsyncMock(return_value=send_response)

    result = await wechat_strategy.send(message)

    assert result is True
    wechat_strategy.client.get.assert_awaited_once_with(
        TOKEN_URL,
        params={
            "grant_type": "client_credential",
            "appid": "appid-123",
            "secret": "secret-123",
        },
    )
    call_args = wechat_strategy.client.post.call_args
    assert "access_token=token-abc" in call_args.args[0]
    assert call_args.kwargs["json"]["touser"] == "openid-123"
    assert call_args.kwargs["json"]["data"]["first"]["value"] == "Title"


@pytest.mark.unit
async def test_send_caches_access_token(wechat_strategy: WechatPushStrategy) -> None:
    message = PushMessage(title="T", summary="S", url="https://example.com")

    token_response = MagicMock()
    token_response.raise_for_status = MagicMock()
    token_response.json.return_value = {"access_token": "cached-token"}

    send_response = MagicMock()
    send_response.raise_for_status = MagicMock()

    wechat_strategy.client.get = AsyncMock(return_value=token_response)
    wechat_strategy.client.post = AsyncMock(return_value=send_response)

    await wechat_strategy.send(message)
    await wechat_strategy.send(message)

    wechat_strategy.client.get.assert_awaited_once()
    assert wechat_strategy.client.post.await_count == 2


@pytest.mark.unit
async def test_send_failure_on_token_error(wechat_strategy: WechatPushStrategy) -> None:
    message = PushMessage(title="T", summary="S", url="https://example.com")
    wechat_strategy.client.get = AsyncMock(side_effect=httpx.RequestError("network error"))

    result = await wechat_strategy.send(message)

    assert result is False


@pytest.mark.unit
async def test_send_failure_on_send_error(wechat_strategy: WechatPushStrategy) -> None:
    message = PushMessage(title="T", summary="S", url="https://example.com")

    token_response = MagicMock()
    token_response.raise_for_status = MagicMock()
    token_response.json.return_value = {"access_token": "token-abc"}

    wechat_strategy.client.get = AsyncMock(return_value=token_response)
    wechat_strategy.client.post = AsyncMock(side_effect=httpx.RequestError("network error"))

    result = await wechat_strategy.send(message)

    assert result is False


@pytest.mark.unit
async def test_invalid_token_response(wechat_strategy: WechatPushStrategy) -> None:
    message = PushMessage(title="T", summary="S", url="https://example.com")

    token_response = MagicMock()
    token_response.raise_for_status = MagicMock()
    token_response.json.return_value = {"access_token": None}

    wechat_strategy.client.get = AsyncMock(return_value=token_response)

    result = await wechat_strategy.send(message)

    assert result is False


@pytest.mark.unit
async def test_summary_truncation(wechat_strategy: WechatPushStrategy) -> None:
    long_summary = "x" * 200
    message = PushMessage(title="T", summary=long_summary, url="https://example.com")

    token_response = MagicMock()
    token_response.raise_for_status = MagicMock()
    token_response.json.return_value = {"access_token": "token-abc"}

    send_response = MagicMock()
    send_response.raise_for_status = MagicMock()

    wechat_strategy.client.get = AsyncMock(return_value=token_response)
    wechat_strategy.client.post = AsyncMock(return_value=send_response)

    await wechat_strategy.send(message)

    payload = wechat_strategy.client.post.call_args.kwargs["json"]
    assert len(payload["data"]["keyword1"]["value"]) == 100
