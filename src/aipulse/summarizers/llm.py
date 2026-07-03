"""OpenAI-compatible LLM adapter."""

import logging

from openai import APIError, AsyncOpenAI, RateLimitError
from openai.types.chat import ChatCompletionMessageParam

from aipulse.core.config import AppSettings

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.kimi.com/coding/v1"
DEFAULT_MODEL = "kimi-for-coding"


class OpenAICompatibleAdapter:
    """Adapter for OpenAI-compatible APIs such as Kimi and OpenRouter."""

    def __init__(
        self,
        settings: AppSettings | None = None,
        base_url: str | None = None,
        model: str | None = None,
        client: AsyncOpenAI | None = None,
    ) -> None:
        self.settings = settings or AppSettings()
        self.base_url = base_url or self.settings.llm_base_url or DEFAULT_BASE_URL
        self.model = model or self.settings.llm_model or DEFAULT_MODEL
        if client is not None:
            self.client = client
        else:
            api_key = (
                self.settings.llm_api_key.get_secret_value()
                if self.settings.llm_api_key
                else None
            )
            self.client = AsyncOpenAI(
                base_url=self.base_url,
                api_key=api_key,
                timeout=120.0,
            )

    async def complete(self, prompt: str, system: str | None = None) -> str:
        """Send a chat completion request and return the generated text."""
        messages: list[ChatCompletionMessageParam] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
            )
        except RateLimitError as exc:
            logger.exception("LLM rate limit exceeded")
            raise RuntimeError("LLM rate limit exceeded") from exc
        except APIError as exc:
            logger.exception("LLM API error")
            raise RuntimeError(f"LLM API error: {exc}") from exc

        content = response.choices[0].message.content
        if content is None or content.strip() == "":
            raise RuntimeError("LLM returned empty response")
        return content
