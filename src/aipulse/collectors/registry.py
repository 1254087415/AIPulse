"""Collector registry."""

from __future__ import annotations

from typing import Callable, TypeVar

from aipulse.collectors.base import BaseCollector

T = TypeVar("T", bound=BaseCollector)


# Legacy single-level registry: source_type → collector class.
# Preserved for backwards compatibility (get_collector / register /
# list_collectors). New code should prefer STRATEGY_REGISTRY.
_registry: dict[str, type[BaseCollector]] = {}


# Nested platform registry: platform → strategy_name → collector class.
# Allows the same source_type ("bilibili_up") to expose multiple strategy
# implementations (e.g. "uapi" vs "html") discoverable via a single decorator.
STRATEGY_REGISTRY: dict[str, dict[str, type[BaseCollector]]] = {}


def register(collector_class: type[BaseCollector]) -> type[BaseCollector]:
    """Register a collector class by its source_type.

    Backwards-compatible entrypoint: keeps the existing single-level registry
    alive. New code should prefer ``register_strategy(platform, strategy)``.
    """
    _registry[collector_class.source_type] = collector_class
    return collector_class


def register_strategy(
    platform: str, strategy: str | None = None
) -> Callable[[type[T]], type[T]]:
    """Decorator that registers a collector class into ``STRATEGY_REGISTRY``.

    The class must expose ``source_type`` and either a ``strategy`` attribute
    (preferred) or accept an explicit ``strategy=`` argument. Falls back to
    ``source_type`` if neither is present — that keeps simple single-strategy
    collectors addressable as a one-key bucket.

    Idempotent: re-registering the same class is a no-op; registering a
    different class under the same key overwrites the previous entry (mirrors
    the behaviour of the legacy ``register`` function).

    Also mirrors the class into the legacy ``_registry`` keyed by
    ``source_type`` so existing ``get_collector()`` callers keep working.
    """

    def _decorator(cls: type[T]) -> type[T]:
        strategy_name = strategy or getattr(cls, "strategy", None) or cls.source_type
        bucket = STRATEGY_REGISTRY.setdefault(platform, {})
        bucket[strategy_name] = cls
        _registry.setdefault(cls.source_type, cls)
        return cls

    return _decorator


def get_collector(source_type: str) -> type[BaseCollector]:
    """Return the collector class registered for source_type."""
    return _registry[source_type]


def get_strategy_collector(platform: str, strategy: str) -> type[BaseCollector]:
    """Return the collector class under STRATEGY_REGISTRY[platform][strategy].

    Raises ``KeyError`` if the platform or strategy is unknown.
    """
    return STRATEGY_REGISTRY[platform][strategy]


def list_collectors() -> dict[str, type[BaseCollector]]:
    """Return a shallow copy of the legacy registry."""
    return dict(_registry)


def list_strategies(platform: str | None = None) -> dict[str, list[str]]:
    """Return a snapshot of the nested strategy registry.

    With ``platform=None`` returns ``{platform: [strategy, ...]}`` for every
    platform. With ``platform='foo'`` returns ``{'foo': [strategy, ...]}``,
    possibly empty if the platform is unknown.
    """
    if platform is None:
        return {p: sorted(bucket.keys()) for p, bucket in STRATEGY_REGISTRY.items()}
    bucket = STRATEGY_REGISTRY.get(platform, {})
    return {platform: sorted(bucket.keys())}


def clear_registry() -> None:
    """Clear both registries. Useful for tests."""
    _registry.clear()
    STRATEGY_REGISTRY.clear()