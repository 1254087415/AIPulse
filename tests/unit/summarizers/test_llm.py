"""Tests for LLM adapter."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from openai import APIError, AsyncOpenAI, RateLimitError
from pydantic import SecretStr

from aipulse.core.config import AppSettings
from aipulse.summarizers.llm import DEFAULT_BASE_URL, DEFAULT_MODEL, OpenAICompatibleAdapter


@pytest.fixture
def settings(tmp_path) -> AppSettings:
    return AppSettings(
        data_dir=tmp_path / "data",
        download_dir=tmp_path / "data" / "downloads",
        KIMI_BASE_URL="https://api.example.com/v1",
        KIMI_MODEL="test-model",
    )


@pytest.fixture
def mock_client() -> AsyncOpenAI:
    return MagicMock(spec=AsyncOpenAI)


@pytest.mark.unit
async def test_complete_returns_content(settings: AppSettings, mock_client: AsyncOpenAI) -> None:
    adapter = OpenAICompatibleAdapter(settings, client=mock_client)
    message = MagicMock()
    message.content = "hello"
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    mock_client.chat.completions.create = AsyncMock(return_value=response)

    result = await adapter.complete("prompt", system="system")

    assert result == "hello"
    mock_client.chat.completions.create.assert_awaited_once()
    call_kwargs = mock_client.chat.completions.create.await_args.kwargs
    assert call_kwargs["model"] == "test-model"
    assert call_kwargs["messages"][0]["role"] == "system"
    assert call_kwargs["messages"][1]["role"] == "user"


@pytest.mark.unit
async def test_complete_uses_defaults_when_settings_empty(mock_client: AsyncOpenAI) -> None:
    adapter = OpenAICompatibleAdapter(client=mock_client)
    assert adapter.base_url == DEFAULT_BASE_URL
    assert adapter.model == DEFAULT_MODEL


@pytest.mark.unit
def test_adapter_creates_real_client_from_settings(settings: AppSettings) -> None:
    settings.kimi_api_key = SecretStr("test-key")
    with patch("aipulse.summarizers.llm.AsyncOpenAI") as mock_client_cls:
        adapter = OpenAICompatibleAdapter(settings)
        assert adapter.base_url == "https://api.example.com/v1"
        assert adapter.model == "test-model"
        mock_client_cls.assert_called_once_with(
            base_url="https://api.example.com/v1",
            api_key="test-key",
            timeout=120.0,
        )


@pytest.mark.unit
def test_adapter_creates_real_client_with_default_key(monkeypatch: pytest.MonkeyPatch) -> None:
    # 构造一个不走 .env 的 settings：强制空 key，base_url 不传（走 defaults）。
    # conftest 在 os.environ 中放了 KIMI_API_KEY=sk-test-placeholder-kimi 以保证
    # build_agent_executor 不会因为缺少 OPENAI_API_KEY 崩溃；本测试要验证的是
    # _env_file=None + 显式空 kimi_api_key 的组合行为，所以必须把环境变量也
    # 屏蔽掉。
    monkeypatch.delenv("KIMI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    settings = AppSettings(_env_file=None, KIMI_API_KEY="")  # type: ignore[call-arg]
    with patch("aipulse.summarizers.llm.AsyncOpenAI") as mock_client_cls:
        adapter = OpenAICompatibleAdapter(settings)
        assert adapter.base_url == DEFAULT_BASE_URL
        assert adapter.model == DEFAULT_MODEL
        mock_client_cls.assert_called_once_with(
            base_url=DEFAULT_BASE_URL,
            api_key=None,
            timeout=120.0,
        )


@pytest.mark.unit
async def test_complete_raises_on_empty_response(
    settings: AppSettings, mock_client: AsyncOpenAI
) -> None:
    adapter = OpenAICompatibleAdapter(settings, client=mock_client)
    message = MagicMock()
    message.content = ""
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    mock_client.chat.completions.create = AsyncMock(return_value=response)

    with pytest.raises(RuntimeError, match="empty response"):
        await adapter.complete("prompt")


@pytest.mark.unit
async def test_complete_raises_on_rate_limit(
    settings: AppSettings, mock_client: AsyncOpenAI
) -> None:
    adapter = OpenAICompatibleAdapter(settings, client=mock_client)
    mock_client.chat.completions.create = AsyncMock(
        side_effect=RateLimitError("rate limited", response=MagicMock(), body=None)
    )

    with pytest.raises(RuntimeError, match="rate limit exceeded"):
        await adapter.complete("prompt")


@pytest.mark.unit
async def test_complete_raises_on_api_error(
    settings: AppSettings, mock_client: AsyncOpenAI
) -> None:
    adapter = OpenAICompatibleAdapter(settings, client=mock_client)
    mock_client.chat.completions.create = AsyncMock(
        side_effect=APIError("api error", request=MagicMock(), body=None)
    )

    with pytest.raises(RuntimeError, match="LLM API error"):
        await adapter.complete("prompt")


@pytest.mark.unit
async def test_complete_raises_on_none_content(
    settings: AppSettings, mock_client: AsyncOpenAI
) -> None:
    adapter = OpenAICompatibleAdapter(settings, client=mock_client)
    message = MagicMock()
    message.content = None
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    mock_client.chat.completions.create = AsyncMock(return_value=response)

    with pytest.raises(RuntimeError, match="empty response"):
        await adapter.complete("prompt")
