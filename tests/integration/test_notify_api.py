"""Integration tests for spec 06 plan §Task 4 — ``POST /api/hotspots/{id}/notify``.

验证三重 gate：
1. ``settings.learning_notification_enabled`` 必须为 true
2. hotspot.notified 必须为 false（防止重复推送）
3. hotspot.decision_status == "worth_learning"

触发后置 ``hotspot.notified = true`` 持久化。
"""

from __future__ import annotations

from typing import Any

import pytest
import pytest_asyncio

from aipulse.hotspot.models import Hotspot, Source
from aipulse.store.database import reset_db


@pytest_asyncio.fixture(autouse=True)
async def _reset_database_before_each_test():
    await reset_db()


async def _seed_hotspot(
    db_session,
    *,
    decision_status: str = "worth_learning",
    notified: bool = False,
    hotspot_id: str = "hs-notify-1",
) -> str:
    """最小 Source + Hotspot，返回 hotspot_id。"""
    src = Source(
        id="src-notify-1",
        name="NotifyTest",
        source_type="bilibili",
        collector_class="aipulse.collectors.bilibili.HotBilibiliCollector",
        is_active=True,
    )
    hs = Hotspot(
        id=hotspot_id,
        title="Notify Hotspot",
        url="https://example.com/notify",
        canonical_url="https://example.com/notify",
        source_id="src-notify-1",
        source_type="bilibili",
        decision_status=decision_status,
        notified=notified,
        summary="核心要点：值得学习",
    )
    db_session.add_all([src, hs])
    await db_session.commit()
    return hotspot_id


@pytest.fixture
def fake_push_registry(monkeypatch: pytest.MonkeyPatch):
    """Mock PushStrategyRegistry.list_configured 返回 1 个 fake strategy。"""
    from aipulse.pushers import registry as reg_mod
    from aipulse.pushers.base import PushMessage, PushStrategy

    class _FakeStrategy(PushStrategy):
        def __init__(self) -> None:
            self.received: list[PushMessage] = []

        async def send(self, message: PushMessage) -> bool:
            self.received.append(message)
            return True

        def is_configured(self) -> bool:
            return True

    fake_strategy = _FakeStrategy()

    class _FakeRegistry:
        def __init__(self, s: _FakeStrategy) -> None:
            self._s = s

        def list_configured(self) -> list[PushStrategy]:
            return [self._s]

    fake_registry = _FakeRegistry(fake_strategy)
    monkeypatch.setattr(reg_mod, "get_push_registry", lambda _settings: fake_registry)
    return fake_strategy


@pytest.fixture
def empty_push_registry(monkeypatch: pytest.MonkeyPatch):
    """Mock PushStrategyRegistry 没有任何 configured strategy → sent_to=[]。"""

    class _EmptyRegistry:
        def list_configured(self) -> list[Any]:
            return []

    from aipulse.pushers import registry as reg_mod

    monkeypatch.setattr(
        reg_mod, "get_push_registry", lambda _settings: _EmptyRegistry()
    )


@pytest.mark.integration
async def test_notify_hotspot_success(
    client, db_session, fake_push_registry
):
    """三重 gate 通过 → 推送 + notified=true 持久化。"""
    hotspot_id = await _seed_hotspot(db_session)

    response = await client.post(f"/api/hotspots/{hotspot_id}/notify")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    data = body["data"]
    assert data["hotspot_id"] == hotspot_id
    assert data["notified"] is True
    assert "_FakeStrategy" in data["sent_to"]
    # 推送消息内容
    msg = fake_push_registry.received[0]
    assert msg.title == "Notify Hotspot"
    assert msg.url == "https://example.com/notify"

    # DB 持久化
    await db_session.refresh(
        await db_session.get(Hotspot, hotspot_id)
    )
    hs = await db_session.get(Hotspot, hotspot_id)
    assert hs.notified is True


@pytest.mark.integration
async def test_notify_hotspot_404_when_missing(client, fake_push_registry):
    response = await client.post("/api/hotspots/does-not-exist/notify")
    assert response.status_code == 404
    assert "Hotspot not found" in response.text


@pytest.mark.integration
async def test_notify_hotspot_idempotent_returns_409(
    client, db_session, fake_push_registry
):
    """notified=true 已推送过 → 409 already_notified。"""
    hotspot_id = await _seed_hotspot(db_session, notified=True)

    response = await client.post(f"/api/hotspots/{hotspot_id}/notify")
    assert response.status_code == 409
    assert "already_notified" in response.text


@pytest.mark.integration
async def test_notify_hotspot_skipped_when_not_worth_learning(
    client, db_session, fake_push_registry
):
    """decision_status != worth_learning → 409 not_worth_learning。"""
    hotspot_id = await _seed_hotspot(db_session, decision_status="pending")

    response = await client.post(f"/api/hotspots/{hotspot_id}/notify")
    assert response.status_code == 409
    assert "not_worth_learning" in response.text


@pytest.mark.integration
async def test_notify_hotspot_409_when_setting_disabled(
    client, db_session, fake_push_registry, monkeypatch
):
    """settings.learning_notification_enabled=false → 409 disabled。"""
    from aipulse.core import config as cfg

    settings = cfg.get_settings()
    settings = settings.update(learning_notification_enabled=False)
    monkeypatch.setattr(settings, "learning_notification_enabled", False, raising=False)
    hotspot_id = await _seed_hotspot(db_session)

    response = await client.post(f"/api/hotspots/{hotspot_id}/notify")
    assert response.status_code == 409
    assert "learning_notification_disabled" in response.text


@pytest.mark.integration
async def test_notify_hotspot_with_no_configured_strategies(
    client, db_session, empty_push_registry
):
    """没有任何 push strategy 配置 → 200 + sent_to=[]，但仍置 notified=true。"""
    hotspot_id = await _seed_hotspot(db_session)

    response = await client.post(f"/api/hotspots/{hotspot_id}/notify")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["data"]["notified"] is True
    assert body["data"]["sent_to"] == []