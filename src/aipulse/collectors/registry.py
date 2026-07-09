"""Collector registry."""

from aipulse.collectors.base import BaseCollector

_registry: dict[str, type[BaseCollector]] = {}


def register(collector_class: type[BaseCollector]) -> type[BaseCollector]:
    """Register a collector class by its source_type."""
    _registry[collector_class.source_type] = collector_class
    return collector_class


def get_collector(source_type: str) -> type[BaseCollector]:
    """Return the collector class registered for source_type."""
    return _registry[source_type]


def list_collectors() -> dict[str, type[BaseCollector]]:
    """Return a shallow copy of the registry."""
    return dict(_registry)


def clear_registry() -> None:
    """Clear the registry. Useful for tests."""
    _registry.clear()
