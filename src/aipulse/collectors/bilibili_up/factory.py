"""UP主采集器工厂 + 策略注册。

策略通过 ``aipulse.collectors.registry.register_strategy`` 装饰器注册到
全局 ``STRATEGY_REGISTRY["bilibili"]``；工厂从该表读取，可发现的策略集合
与 collectors 模块顶层 import 一致。
"""

from __future__ import annotations

import logging
from typing import Any

from aipulse.collectors.base import BaseCollector
from aipulse.collectors.bilibili_up.base import BaseBilibiliUpCollector
from aipulse.collectors.bilibili_up.html import BilibiliUpHtmlCollector
from aipulse.collectors.bilibili_up.uapi import BilibiliUpUapiCollector
from aipulse.collectors.registry import STRATEGY_REGISTRY, register_strategy


logger = logging.getLogger(__name__)

PLATFORM = "bilibili"


def _register_builtin_strategies() -> None:
    """Idempotent registration of bilibili_up strategies into the global table.

    Re-runnable so test fixtures that wipe the registry (e.g.
    ``test_registry.py``'s ``_clean_registry`` autouse) can be followed by
    a normal ``create()`` call without a module reload.
    """
    register_strategy(PLATFORM, strategy="uapi")(BilibiliUpUapiCollector)
    register_strategy(PLATFORM, strategy="html")(BilibiliUpHtmlCollector)


# Module-level registration — runs once on import.
_register_builtin_strategies()


class BilibiliUpCollectorFactory:
    """UP主采集器工厂。"""

    @staticmethod
    def _bucket() -> dict[str, type[BaseCollector]]:
        bucket = STRATEGY_REGISTRY.get(PLATFORM)
        if not bucket:
            # Registry was wiped (test fixture) — re-register lazily.
            _register_builtin_strategies()
            bucket = STRATEGY_REGISTRY.get(PLATFORM, {})
        return bucket

    @classmethod
    def create(cls, strategy: str = "uapi", **kwargs: Any) -> BaseBilibiliUpCollector:
        """strategy: 'uapi' | 'html'。默认 uapi。

        从全局 ``STRATEGY_REGISTRY["bilibili"]`` 查；找不到抛 ValueError。
        """
        key = (strategy or "uapi").lower()
        bucket = cls._bucket()
        impl = bucket.get(key)
        if impl is None:
            raise ValueError(
                f"Unknown bilibili_up strategy: {strategy!r}; "
                f"available: {sorted(bucket.keys())}"
            )
        logger.debug("[factory] creating bilibili_up collector strategy=%s", key)
        # Concrete uapi/html collectors only accept **kwargs; their
        # ``strategy`` attribute is hard-coded in __init__ (super().__init__).
        # Pass ``strategy`` through only when the constructor accepts it,
        # otherwise fall back to kwargs-only.
        try:
            return impl(strategy=key, **kwargs)  # type: ignore[call-arg]
        except TypeError:
            return impl(**kwargs)

    @classmethod
    def available_strategies(cls) -> list[str]:
        return sorted(cls._bucket().keys())