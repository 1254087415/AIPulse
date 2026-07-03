"""WeChat official account template message push strategy."""

import logging
from typing import Any

import httpx

from aipulse.core.config import AppSettings
from aipulse.pushers.base import PushMessage, PushStrategy

logger = logging.getLogger(__name__)

TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"
SEND_URL = "https://api.weixin.qq.com/cgi-bin/message/template/send"


class WechatPushStrategy(PushStrategy):
    """Push notifications via WeChat official account template messages."""

    def __init__(self, settings: AppSettings, client: httpx.AsyncClient | None = None):
        self.appid = settings.wechat_appid
        self.appsecret = (
            settings.wechat_appsecret.get_secret_value()
            if settings.wechat_appsecret
            else ""
        )
        self.template_id = settings.wechat_template_id
        self.openid = settings.wechat_openid
        self.client = client or httpx.AsyncClient(timeout=30.0)
        self._access_token: str | None = None

    def is_configured(self) -> bool:
        return all([self.appid, self.appsecret, self.template_id, self.openid])

    async def send(self, message: PushMessage) -> bool:
        if not self.is_configured():
            return False

        try:
            access_token = await self._get_access_token()
            url = f"{SEND_URL}?access_token={access_token}"
            payload: dict[str, Any] = {
                "touser": self.openid,
                "template_id": self.template_id,
                "url": message.url or "",
                "data": {
                    "first": {"value": message.title},
                    "keyword1": {"value": message.summary[:100]},
                },
            }
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            return True
        except httpx.HTTPError:
            logger.exception("Failed to send WeChat template message")
            return False
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected error sending WeChat message: %s", exc)
            return False

    async def _get_access_token(self) -> str:
        if self._access_token:
            return self._access_token
        params = {
            "grant_type": "client_credential",
            "appid": self.appid,
            "secret": self.appsecret,
        }
        response = await self.client.get(TOKEN_URL, params=params)
        response.raise_for_status()
        data = response.json()
        token = data.get("access_token")
        if not isinstance(token, str):
            raise ValueError("WeChat access_token is not a string")
        self._access_token = token
        return token

    def clear_token(self) -> None:
        """Clear cached access token (useful in tests)."""
        self._access_token = None
