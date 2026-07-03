"""Feishu webhook push strategy."""

import base64
import hashlib
import hmac
import logging
import time

import httpx

from aipulse.core.config import AppSettings
from aipulse.pushers.base import PushMessage, PushStrategy

logger = logging.getLogger(__name__)


class FeishuPushStrategy(PushStrategy):
    """Push notifications via Feishu custom bot webhook."""

    def __init__(self, settings: AppSettings, client: httpx.AsyncClient | None = None):
        self.webhook_url = settings.feishu_webhook_url
        self.secret = (
            settings.feishu_secret.get_secret_value()
            if settings.feishu_secret
            else ""
        )
        self.client = client or httpx.AsyncClient(timeout=30.0)

    def is_configured(self) -> bool:
        return bool(self.webhook_url)

    async def send(self, message: PushMessage) -> bool:
        if not self.is_configured():
            return False

        try:
            timestamp = str(int(time.time()))
            signature = self._sign(timestamp)

            payload = {
                "timestamp": timestamp,
                "sign": signature,
                "msg_type": "post",
                "content": {
                    "post": {
                        "zh_cn": {
                            "title": message.title,
                            "content": [
                                [{"tag": "text", "text": message.summary}],
                                [
                                    {
                                        "tag": "a",
                                        "text": "查看链接",
                                        "href": message.url or "",
                                    }
                                ],
                            ],
                        }
                    }
                },
            }

            response = await self.client.post(self.webhook_url, json=payload)
            response.raise_for_status()
            return True
        except httpx.HTTPError:
            logger.exception("Failed to send Feishu message to %s", self.webhook_url)
            return False
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected error sending Feishu message: %s", exc)
            return False

    def _sign(self, timestamp: str) -> str:
        if not self.secret:
            return ""
        string_to_sign = f"{timestamp}\n{self.secret}"
        hmac_code = hmac.new(
            self.secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        return base64.b64encode(hmac_code).decode("utf-8")
