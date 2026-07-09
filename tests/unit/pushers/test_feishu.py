"""Tests for Feishu push strategy."""

import base64
import hashlib
import hmac
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from aipulse.core.config import AppSettings
from aipulse.pushers.base import PushMessage
from aipulse.pushers.feishu import FeishuPushStrategy


@pytest.fixture
def feishu_settings() -> AppSettings:
    return AppSettings(
        feishu_webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/xxx",
        feishu_secret="secret-123",
    )


@pytest.fixture
def feishu_strategy(feishu_settings: AppSettings) -> FeishuPushStrategy:
    return FeishuPushStrategy(
        feishu_settings, client=httpx.AsyncClient(transport=httpx.MockTransport(None))
    )


@pytest.mark.unit
async def test_send_returns_false_when_not_configured() -> None:
    settings = AppSettings()
    strategy = FeishuPushStrategy(
        settings, client=httpx.AsyncClient(transport=httpx.MockTransport(None))
    )
    message = PushMessage(title="T", summary="S", url="https://example.com")
    result = await strategy.send(message)
    assert result is False


@pytest.mark.unit
async def test_send_success(feishu_strategy: FeishuPushStrategy) -> None:
    message = PushMessage(
        title="Test Title",
        summary="Test summary",
        url="https://example.com/article",
    )

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    feishu_strategy.client.post = AsyncMock(return_value=mock_response)

    result = await feishu_strategy.send(message)

    assert result is True
    feishu_strategy.client.post.assert_awaited_once()
    call_args = feishu_strategy.client.post.call_args
    assert call_args.kwargs["json"]["msg_type"] == "post"
    assert call_args.kwargs["json"]["content"]["post"]["zh_cn"]["title"] == message.title


@pytest.mark.unit
async def test_send_failure(feishu_strategy: FeishuPushStrategy) -> None:
    message = PushMessage(title="T", summary="S", url="https://example.com")
    feishu_strategy.client.post = AsyncMock(side_effect=httpx.RequestError("network error"))

    result = await feishu_strategy.send(message)

    assert result is False


@pytest.mark.unit
def test_sign_without_secret(feishu_strategy: FeishuPushStrategy) -> None:
    feishu_strategy.secret = ""
    assert feishu_strategy._sign("1234567890") == ""


@pytest.mark.unit
def test_sign_with_secret(feishu_strategy: FeishuPushStrategy) -> None:
    timestamp = "1234567890"
    expected_string = f"{timestamp}\n{feishu_strategy.secret}"
    expected = base64.b64encode(
        hmac.new(
            feishu_strategy.secret.encode("utf-8"),
            expected_string.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
    ).decode("utf-8")

    assert feishu_strategy._sign(timestamp) == expected


@pytest.mark.unit
async def test_payload_contains_title_summary_link(feishu_strategy: FeishuPushStrategy) -> None:
    message = PushMessage(title="My Title", summary="My Summary", url="https://example.com")
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    feishu_strategy.client.post = AsyncMock(return_value=mock_response)

    await feishu_strategy.send(message)

    payload = feishu_strategy.client.post.call_args.kwargs["json"]
    content = payload["content"]["post"]["zh_cn"]
    assert content["title"] == "My Title"
    assert content["content"][0][0]["text"] == "My Summary"
    assert content["content"][1][0]["href"] == "https://example.com"
    assert payload["timestamp"]
    assert payload["sign"]
