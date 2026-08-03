"""L1 contract tests — follow-up identity, pause/resume payload, scan errors.

Covers three regressions found in the v3 web audit:

1. **UID(mid) ⇄ UUID resolution consistency.**
   The FollowDetailView UI addresses everything by ``uid`` (B站 mid), but
   PATCH/DELETE/sync/health/overview endpoints only accept the DB UUID.
   That meant clicking 暂停/恢复/立即扫描/删除 in the UI failed silently
   because the frontend's mid never matched a UUID row.

2. **Pause/resume payload schema mismatch.**
   ``setEnabled`` (follow.ts) sends ``{enabled: true|false}`` per spec §6.12,
   but ``FollowedUpUpdate`` only accepted ``is_active``. The DB column
   stayed unchanged, so 暂停/恢复 was a no-op.

3. **Immediate scan silent 202 on missing record.**
   ``scan_followed_up_by_id`` returned an empty ``ScanOutcome`` when the
   row was missing; the sync endpoint then returned 202 + ``new_videos: 0``
   — a fabricated success that polluted observability. Must return 404.
"""

from __future__ import annotations

import pytest
import pytest_asyncio

from aipulse.store.database import reset_db


@pytest_asyncio.fixture(autouse=True)
async def _reset_db():
    await reset_db()


@pytest.fixture
def created(client):
    """Create a single real bilibili FollowedUp row and yield the create payload."""

    async def _make(uid: str = "1567748478", name: str = "Miyabi") -> dict:
        payload = {
            "platform": "bilibili",
            "uid": uid,
            "display_name": name,
            "profile_url": f"https://space.bilibili.com/{uid}",
            "collector_strategy": "uapi",
        }
        resp = await client.post("/api/followed-up", json=payload)
        assert resp.status_code == 201, resp.text
        return resp.json()["data"]

    return _make


# ============================================================
# Issue 1 + 2: PATCH (暂停/恢复) accepts both id forms + enabled field
# ============================================================
@pytest.mark.integration
@pytest.mark.asyncio
async def test_patch_by_uid_accepts_enabled_field_pauses(client, created):
    """PATCH /api/followed-up/{mid} with {enabled:false} flips is_active=False."""
    record = await created()

    resp = await client.patch(
        f"/api/followed-up/{record['uid']}",
        json={"enabled": False},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["is_active"] is False
    assert body["id"] == record["id"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_patch_by_uid_accepts_enabled_field_resumes(client, created):
    """PATCH /api/followed-up/{mid} with {enabled:true} flips is_active=True."""
    record = await created()

    # 先暂停
    pause = await client.patch(
        f"/api/followed-up/{record['uid']}",
        json={"enabled": False},
    )
    assert pause.status_code == 200

    # 再恢复
    resp = await client.patch(
        f"/api/followed-up/{record['uid']}",
        json={"enabled": True},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_active"] is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_patch_by_uuid_accepts_enabled_field(client, created):
    """PATCH by DB UUID still works (back-compat for any caller using UUID)."""
    record = await created()

    resp = await client.patch(
        f"/api/followed-up/{record['id']}",
        json={"enabled": False},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_active"] is False


# ============================================================
# Issue 1: DELETE accepts uid too
# ============================================================
@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_by_uid_soft_deletes(client, created):
    """DELETE /api/followed-up/{mid} soft-deletes via uid lookup."""
    record = await created()

    resp = await client.delete(f"/api/followed-up/{record['uid']}")
    assert resp.status_code == 200, resp.text

    # 再 GET 该 mid 应 404（被软删）
    follow_up = await client.get(f"/api/followed-up/{record['uid']}")
    assert follow_up.status_code == 404


# ============================================================
# Issue 1 + 3: POST /sync accepts uid AND returns 404 on not-found
# ============================================================
@pytest.mark.integration
@pytest.mark.asyncio
async def test_sync_by_uid_triggers_scan(client, created):
    """POST /api/followed-up/{mid}/sync resolves by uid (frontend contract)."""
    record = await created()

    resp = await client.post(f"/api/followed-up/{record['uid']}/sync")
    assert resp.status_code == 202, resp.text
    body = resp.json()["data"]
    # followed_up_id 必须是 DB 内部 UUID，而不是传入的 uid
    assert body["followed_up_id"] == record["id"]
    # status 是 ok/timeout 二选一（前者从 uapi 拉过空视频列表）
    assert body["status"] in ("ok", "timeout")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sync_unknown_id_returns_404_not_silent_202(client):
    """POST /api/followed-up/{unknown}/sync → 404，不能伪 202 成功。"""
    resp = await client.post("/api/followed-up/nonexistent-id-xyz/sync")
    assert resp.status_code == 404, resp.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sync_unknown_uid_returns_404(client):
    """POST /api/followed-up/{unknown-mid}/sync → 404。"""
    resp = await client.post("/api/followed-up/9999999999999/sync")
    assert resp.status_code == 404, resp.text


# ============================================================
# Issue 1: health / overview 也按 mid 可达
# ============================================================
@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_by_uid(client, created):
    """GET /api/followed-up/{mid}/health resolves by uid."""
    record = await created()

    resp = await client.get(f"/api/followed-up/{record['uid']}/health")
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["id"] == record["id"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_overview_by_uuid(client, created):
    """GET /api/followed-up/{uuid}/overview resolves by uuid."""
    record = await created()

    resp = await client.get(f"/api/followed-up/{record['id']}/overview")
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["id"] == record["id"]


# ============================================================
# Issue 2: FollowedUpUpdate schema 直接接受 enabled（pydantic 级）
# ============================================================
@pytest.mark.integration
@pytest.mark.asyncio
async def test_followed_up_update_schema_accepts_enabled():
    """schema-level：FollowedUpUpdate 接受 enabled，model_validator 把它归一到 is_active。

    spec §6.12 用 ``enabled`` 作为暂停/恢复字段名；持久层列名是
    ``is_active``。两者必须同步。
    """
    from aipulse.schemas.followed_up import FollowedUpUpdate

    model = FollowedUpUpdate.model_validate({"enabled": True})
    assert model.enabled is True
    assert model.is_active is True  # 别名：归一到 is_active


@pytest.mark.integration
@pytest.mark.asyncio
async def test_followed_up_update_schema_accepts_is_active_alias():
    """schema-level：旧的 is_active 仍可用（不破坏现有调用方）。

    注：``enabled`` 仅作为 input 别名（enabled → is_active）；反向不会
    自动从 is_active 反推 enabled，原因是 schema 是 input helper 而非
    round-trip model，repo 只关心 ``is_active``。
    """
    from aipulse.schemas.followed_up import FollowedUpUpdate

    model = FollowedUpUpdate.model_validate({"is_active": False})
    assert model.is_active is False


# ============================================================
# Issue 3: scan_followed_up_by_id（直接调底层）也要 raise
# ============================================================
@pytest.mark.integration
@pytest.mark.asyncio
async def test_scan_followed_up_by_id_raises_for_unknown():
    """底层函数对未知 id 必须 raise，不能返回伪 ScanOutcome。"""
    from aipulse.repositories.followed_up_repo import FollowedUpNotFoundError
    from aipulse.scheduler.jobs.followed_up_scan import scan_followed_up_by_id

    with pytest.raises(FollowedUpNotFoundError):
        await scan_followed_up_by_id("nonexistent-id-zzz")