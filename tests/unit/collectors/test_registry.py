"""Tests for the collector registry."""

from typing import Any

import pytest

from aipulse.collectors.base import BaseCollector, HotspotCandidate, RawItem
from aipulse.collectors.registry import (
    clear_registry,
    get_collector,
    list_collectors,
    register,
)


class FakeCollector(BaseCollector):
    """Fake collector for registry tests."""

    source_type = "fake"
    name = "Fake"

    async def fetch(self) -> list[RawItem]:
        return []

    def normalize(self, raw: RawItem) -> HotspotCandidate:
        return HotspotCandidate(
            title=raw.title,
            url=raw.url,
            canonical_url=raw.url,
            content=raw.content,
            published_at=raw.published_at,
            source_type=self.source_type,
            raw_metadata=raw.raw_metadata,
        )


@pytest.fixture(autouse=True)
def _clean_registry():
    """Clear registry before and after each test."""
    clear_registry()
    yield
    clear_registry()


@pytest.mark.unit
def test_register_and_get_collector():
    """A registered collector can be retrieved by source_type."""
    register(FakeCollector)
    assert get_collector("fake") is FakeCollector


@pytest.mark.unit
def test_list_collectors_returns_snapshot():
    """list_collectors returns a copy of the registry."""
    register(FakeCollector)
    snapshot = list_collectors()
    assert snapshot == {"fake": FakeCollector}
    snapshot.clear()
    assert list_collectors() == {"fake": FakeCollector}


@pytest.mark.unit
def test_get_collector_raises_for_unknown():
    """get_collector raises KeyError for unregistered source_type."""
    with pytest.raises(KeyError):
        get_collector("unknown")


@pytest.mark.unit
def test_base_collector_from_source_ignores_config():
    """from_source instantiates with default kwargs when config is empty."""
    register(FakeCollector)
    source: Any = type("Source", (), {"config": None})()
    collector = FakeCollector.from_source(source)
    assert isinstance(collector, FakeCollector)
