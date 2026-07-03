"""Push strategy registry (factory)."""

from aipulse.core.config import AppSettings
from aipulse.pushers.base import PushStrategy


class PushStrategyRegistry:
    """Factory for push strategies."""

    def __init__(self) -> None:
        self._strategies: dict[str, PushStrategy] = {}

    def register(self, name: str, strategy: PushStrategy) -> None:
        """Register a named push strategy."""
        self._strategies[name] = strategy

    def get(self, name: str) -> PushStrategy | None:
        """Return a strategy by name."""
        return self._strategies.get(name)

    def list_configured(self) -> list[PushStrategy]:
        """Return all configured strategies."""
        return [s for s in self._strategies.values() if s.is_configured()]


# Global registry populated at import time.
_registry: PushStrategyRegistry | None = None


def get_push_registry(settings: AppSettings) -> PushStrategyRegistry:
    """Return the push registry initialized with settings."""
    global _registry
    if _registry is None:
        _registry = PushStrategyRegistry()
        _register_default_strategies(_registry, settings)
    return _registry


def _register_default_strategies(registry: PushStrategyRegistry, settings: AppSettings) -> None:
    """Register built-in push strategies."""
    from aipulse.pushers.feishu import FeishuPushStrategy
    from aipulse.pushers.wechat import WechatPushStrategy

    registry.register("feishu", FeishuPushStrategy(settings))
    registry.register("wechat", WechatPushStrategy(settings))
