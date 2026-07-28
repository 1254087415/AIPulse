"""Tests for the collector registry."""

from typing import Any

import pytest

from aipulse.collectors.base import BaseCollector, HotspotCandidate, RawItem
from aipulse.collectors.registry import (
    STRATEGY_REGISTRY,
    clear_registry,
    get_collector,
    get_strategy_collector,
    list_collectors,
    list_strategies,
    register,
    register_strategy,
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


class FakeStrategyACollector(BaseCollector):
    source_type = "fake_a"
    name = "FakeA"
    strategy = "alpha"

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


class FakeStrategyBCollector(BaseCollector):
    source_type = "fake_b"
    name = "FakeB"
    strategy = "beta"

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


# ===== STRATEGY_REGISTRY (nested platform registry) =====


@pytest.mark.unit
def test_register_strategy_writes_to_nested_bucket():
    """register_strategy populates STRATEGY_REGISTRY[platform][strategy]."""
    register_strategy("fake_platform", strategy="alpha")(FakeStrategyACollector)
    assert STRATEGY_REGISTRY["fake_platform"]["alpha"] is FakeStrategyACollector


@pytest.mark.unit
def test_register_strategy_uses_class_strategy_attribute_when_no_explicit_key():
    """省略 strategy= 参数时，回退到 cls.strategy 属性。"""
    register_strategy("fake_platform")(FakeStrategyACollector)
    assert STRATEGY_REGISTRY["fake_platform"]["alpha"] is FakeStrategyACollector


@pytest.mark.unit
def test_register_strategy_mirrors_into_legacy_registry():
    """register_strategy 也写入 legacy _registry，按 source_type 索引。"""
    register_strategy("fake_platform", strategy="alpha")(FakeStrategyACollector)
    assert get_collector("fake_a") is FakeStrategyACollector


@pytest.mark.unit
def test_register_strategy_is_idempotent():
    """重复注册同一个 class 不覆盖、也不重复添加。"""
    register_strategy("fake_platform", strategy="alpha")(FakeStrategyACollector)
    register_strategy("fake_platform", strategy="alpha")(FakeStrategyACollector)
    assert len(STRATEGY_REGISTRY["fake_platform"]) == 1
    assert STRATEGY_REGISTRY["fake_platform"]["alpha"] is FakeStrategyACollector


@pytest.mark.unit
def test_get_strategy_collector_returns_class():
    """get_strategy_collector(platform, strategy) 返回正确 class。"""
    register_strategy("fake_platform", strategy="alpha")(FakeStrategyACollector)
    register_strategy("fake_platform", strategy="beta")(FakeStrategyBCollector)
    assert get_strategy_collector("fake_platform", "alpha") is FakeStrategyACollector
    assert get_strategy_collector("fake_platform", "beta") is FakeStrategyBCollector


@pytest.mark.unit
def test_get_strategy_collector_raises_for_unknown_strategy():
    """get_strategy_collector 对未知 strategy 抛 KeyError。"""
    register_strategy("fake_platform", strategy="alpha")(FakeStrategyACollector)
    with pytest.raises(KeyError):
        get_strategy_collector("fake_platform", "missing")


@pytest.mark.unit
def test_get_strategy_collector_raises_for_unknown_platform():
    """get_strategy_collector 对未知 platform 抛 KeyError。"""
    with pytest.raises(KeyError):
        get_strategy_collector("missing_platform", "alpha")


@pytest.mark.unit
def test_list_strategies_returns_per_platform_sorted():
    """list_strategies 返回每个 platform 的 strategy 列表（按字母排序）。"""
    register_strategy("fake_platform", strategy="beta")(FakeStrategyBCollector)
    register_strategy("fake_platform", strategy="alpha")(FakeStrategyACollector)
    out = list_strategies()
    assert out == {"fake_platform": ["alpha", "beta"]}


@pytest.mark.unit
def test_list_strategies_for_specific_platform():
    """list_strategies(platform=...) 只返回指定 platform 的 strategies。"""
    register_strategy("fake_platform", strategy="beta")(FakeStrategyBCollector)
    register_strategy("fake_platform", strategy="alpha")(FakeStrategyACollector)
    out = list_strategies("fake_platform")
    assert out == {"fake_platform": ["alpha", "beta"]}


@pytest.mark.unit
def test_list_strategies_unknown_platform_returns_empty_bucket():
    """list_strategies 对未知 platform 返回空列表。"""
    out = list_strategies("missing_platform")
    assert out == {"missing_platform": []}


@pytest.mark.unit
def test_clear_registry_clears_both_legacy_and_nested():
    """clear_registry 同时清空 legacy _registry 和嵌套 STRATEGY_REGISTRY。"""
    register(FakeCollector)
    register_strategy("fake_platform", strategy="alpha")(FakeStrategyACollector)
    clear_registry()
    assert list_collectors() == {}
    assert STRATEGY_REGISTRY == {}
    assert list_strategies() == {}
