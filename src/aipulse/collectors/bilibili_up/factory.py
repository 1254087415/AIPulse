"""UP主采集器工厂 + 策略注册。"""

from __future__ import annotations

import logging
from typing import Any

from aipulse.collectors.bilibili_up.base import BaseBilibiliUpCollector
from aipulse.collectors.bilibili_up.html import BilibiliUpHtmlCollector
from aipulse.collectors.bilibili_up.uapi import BilibiliUpUapiCollector


logger = logging.getLogger(__name__)

_STRATEGY_REGISTRY: dict[str, type[BaseBilibiliUpCollector]] = {}


def _register_strategy(cls: type[BaseBilibiliUpCollector]) -> type[BaseBilibiliUpCollector]:
    """把 collector class 注册到 _STRATEGY_REGISTRY[strategy]。幂等。"""
    _STRATEGY_REGISTRY.setdefault(cls.strategy, cls)
    return cls


# 触发装饰器副作用 —— 确保两个实现都注册到全局表
_register_strategy(BilibiliUpUapiCollector)
_register_strategy(BilibiliUpHtmlCollector)


class BilibiliUpCollectorFactory:
    """UP主采集器工厂。"""

    @staticmethod
    def create(strategy: str = "uapi", **kwargs: Any) -> BaseBilibiliUpCollector:
        """strategy: 'uapi' | 'html'。默认 uapi。"""
        key = (strategy or "uapi").lower()
        cls = _STRATEGY_REGISTRY.get(key)
        if cls is None:
            raise ValueError(
                f"Unknown bilibili_up strategy: {strategy!r}; "
                f"available: {sorted(_STRATEGY_REGISTRY.keys())}"
            )
        logger.debug("[factory] creating bilibili_up collector strategy=%s", key)
        return cls(**kwargs)

    @staticmethod
    def available_strategies() -> list[str]:
        return sorted(_STRATEGY_REGISTRY.keys())