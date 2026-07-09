"""WeChat bot push strategy using an external send script."""

import asyncio
import logging
from pathlib import Path

from aipulse.core.config import AppSettings
from aipulse.pushers.base import PushMessage, PushStrategy

logger = logging.getLogger(__name__)

SEND_TIMEOUT_SECONDS = 60


class WechatBotPushStrategy(PushStrategy):
    """Push notifications by invoking a configured WeChat bot send script."""

    def __init__(self, settings: AppSettings) -> None:
        self.bot_token = (
            settings.wechat_bot_token.get_secret_value() if settings.wechat_bot_token else ""
        )
        self.to_user = settings.wechat_to_user
        self.account_id = settings.wechat_account_id
        self.context_token_file = settings.wechat_context_token_file
        self.send_script = settings.wechat_send_script
        self.data_dir = settings.data_dir

    def _validated_script(self) -> Path | None:
        """Return the resolved script path if it passes safety checks."""
        if not self.send_script:
            return None
        try:
            return AppSettings.validate_script_path(self.send_script, self.data_dir)
        except ValueError as exc:
            logger.error("WeChat Bot send script rejected: %s", exc)
            return None

    def is_configured(self) -> bool:
        return self._validated_script() is not None

    async def send(self, message: PushMessage) -> bool:
        script = self._validated_script()
        if script is None:
            logger.warning("WeChat Bot push not configured or invalid script, skip")
            return False

        text = f"{message.title}\n\n{message.summary}".strip()
        try:
            proc = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    str(script),
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                ),
                timeout=SEND_TIMEOUT_SECONDS,
            )
            await asyncio.wait_for(
                proc.communicate(input=text.encode("utf-8")),
                timeout=SEND_TIMEOUT_SECONDS,
            )
            return proc.returncode == 0
        except (TimeoutError, OSError):
            logger.exception("WeChat Bot send failed")
            return False
