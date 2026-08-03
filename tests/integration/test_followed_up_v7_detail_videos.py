"""Integration tests for the Round 7 detail + paginated videos endpoints.

spec §6.12 — FollowDetailView loads the page from two distinct endpoints:

* ``GET /api/followed-up/{key}/detail`` returns the header + meta + collections
  block, with the ``avatar``/``enabled``/``health``/``strategy``/``interval_minutes``
  fields the new view expects.
* ``GET /api/followed-up/{key}/videos?offset=&limit=&collection_id=`` returns
  ``{ items, nextOffset }`` paginated by hotspot ``created_at desc``.

Both endpoints accept either the row's database UUID or, when that 404s, the
platform uid (B站 mid) via the by-uid alias.
"""

from __future__ import annotations

import pytest

from aipulse.hotspot.models import Hotspot, Source
from aipulse.store.database import get_session_maker


def _bearer() -> dict[str, str]:
    return {"Authorization": "Bearer test-token"}


async def _seed_source() -> str:
    async with get_session_maker()() as session:
        src = Source(name="bilibili", source_type="bilibili", collector_class="X")
        session.add(src)
        await session.commit()
        return src.id


async def _seed_hotspot(
    followed_up_id: str,
    *,
    bvid: str,
    title: str,
    collection_id: str | None,
    source_id: str,
) -> None:
    async with get_session_maker()() as session:
        session.add(
            Hotspot(
                content_id=bvid,
                followed_up_id=followed_up_id,
                followed_up_collection_id=collection_id,
                title=title,
                url=f"https://www.bilibili.com/video/{bvid}",
                canonical_url=f"https://www.bilibili.com/video/{bvid}",
                source_id=source_id,
                source_type="bilibili",
            )
        )
        await session.commit()


async def _create_up(
    client,
    *,
    uid: str,
    display_name: str = "示例 UP",
    config: dict | None = None,
) -> str:
    payload = {
        "platform": "bilibili",
        "uid": uid,
        "display_name": display_name,
        "profile_url": f"https://space.bilibili.com/{uid}",
        "collector_strategy": "uapi",
        "fetch_interval_minutes": 30,
    }
    if config is not None:
        payload["config"] = config
    resp = await client.post("/api/followed-up", json=payload, headers=_bearer())
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_detail_returns_spec_shape_by_db_id(client) -> None:
    fu_id = await _create_up(
        client,
        uid="round7-uid-1",
        display_name="测试 UP",
        config={"avatar_url": "https://x/a.jpg"},
    )
    resp = await client.get(f"/api/followed-up/{fu_id}/detail", headers=_bearer())
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["id"] == fu_id
    assert data["name"] == "测试 UP"
    assert data["mid"] == "round7-uid-1"
    assert data["url"] == "https://space.bilibili.com/round7-uid-1"
    assert data["avatar"] == "https://x/a.jpg"
    assert data["health"] == "healthy"
    assert data["enabled"] is True
    assert data["strategy"] == "uapi"
    assert data["interval_minutes"] == 30
    assert data["last_checked_at"] is None
    assert data["last_error"] is None
    assert data["collections"] == []
    assert data["orphan_videos"] == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_detail_falls_back_to_uid_alias(client) -> None:
    await _create_up(client, uid="round7-uid-2", display_name="Aliased UP")
    resp = await client.get(
        "/api/followed-up/round7-uid-2/detail", headers=_bearer()
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["name"] == "Aliased UP"
    assert data["mid"] == "round7-uid-2"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_detail_returns_404_for_unknown(client) -> None:
    resp = await client.get(
        "/api/followed-up/round7-nonesuch/detail", headers=_bearer()
    )
    assert resp.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
async def test_videos_paginate_with_next_offset(client) -> None:
    fu_id = await _create_up(client, uid="round7-uid-3", display_name="Videos UP")
    src_id = await _seed_source()
    for i in range(25):
        await _seed_hotspot(
            fu_id,
            bvid=f"BVrd7vid{i:02d}",
            title=f"视频 {i}",
            collection_id=None,
            source_id=src_id,
        )

    first = await client.get(
        f"/api/followed-up/{fu_id}/videos?offset=0&limit=20", headers=_bearer()
    )
    assert first.status_code == 200, first.text
    first_data = first.json()["data"]
    assert len(first_data["items"]) == 20
    assert first_data["nextOffset"] == 20
    # 25 hotspots created in ascending i; ordering is created_at desc so the
    # first page starts with the most-recently-inserted one (i=24).
    assert first_data["items"][0]["bvid"] == "BVrd7vid24"
    assert first_data["items"][-1]["bvid"] == "BVrd7vid05"

    second = await client.get(
        f"/api/followed-up/{fu_id}/videos?offset=20&limit=20", headers=_bearer()
    )
    assert second.status_code == 200, second.text
    second_data = second.json()["data"]
    assert len(second_data["items"]) == 5
    assert second_data["nextOffset"] is None
    assert second_data["items"][0]["bvid"] == "BVrd7vid04"
    assert second_data["items"][-1]["bvid"] == "BVrd7vid00"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_videos_by_uid_alias(client) -> None:
    fu_id = await _create_up(client, uid="round7-uid-4", display_name="Alias Videos")
    src_id = await _seed_source()
    await _seed_hotspot(
        fu_id,
        bvid="BValias01",
        title="alias",
        collection_id=None,
        source_id=src_id,
    )

    resp = await client.get(
        "/api/followed-up/by-uid/bilibili/round7-uid-4/videos?offset=0&limit=20",
        headers=_bearer(),
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()["data"]["items"]
    assert any(item["bvid"] == "BValias01" for item in items)
    assert resp.json()["data"]["nextOffset"] is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_videos_filter_by_collection_id(client) -> None:
    from aipulse.models.followed_up_collections import FollowedUpCollection

    fu_id = await _create_up(client, uid="round7-uid-5", display_name="Col Filter UP")
    async with get_session_maker()() as session:
        col = FollowedUpCollection(
            followed_up_id=fu_id,
            platform_collection_id="sid-x",
            title="过滤合集",
        )
        session.add(col)
        await session.commit()
        col_id = col.id

    src_id = await _seed_source()
    for i in range(3):
        await _seed_hotspot(
            fu_id,
            bvid=f"BVincol{i}",
            title=f"in {i}",
            collection_id=col_id,
            source_id=src_id,
        )
    for i in range(4):
        await _seed_hotspot(
            fu_id,
            bvid=f"BVorph{i}",
            title=f"orph {i}",
            collection_id=None,
            source_id=src_id,
        )

    in_col = await client.get(
        f"/api/followed-up/{fu_id}/videos?offset=0&limit=20&collection_id={col_id}",
        headers=_bearer(),
    )
    assert in_col.status_code == 200, in_col.text
    items = in_col.json()["data"]["items"]
    assert len(items) == 3
    assert {item["bvid"] for item in items} == {"BVincol0", "BVincol1", "BVincol2"}

    no_col = await client.get(
        f"/api/followed-up/{fu_id}/videos?offset=0&limit=20&collection_id=",
        headers=_bearer(),
    )
    assert no_col.status_code == 200, no_col.text
    items2 = no_col.json()["data"]["items"]
    assert len(items2) == 4
    assert {item["bvid"] for item in items2} == {f"BVorph{i}" for i in range(4)}
