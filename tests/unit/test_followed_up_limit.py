"""Tests for spec 09 TC-API-FOLLOWED-UP-04: 20 UP 主上限 → 422."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from aipulse.api.followed_up import create_followed_up_route
from aipulse.schemas.followed_up import FollowedUpCreate


@pytest.mark.unit
async def test_create_followed_up_returns_422_when_at_limit() -> None:
    """已达 20 个 UP 主上限时，新请求必须返回 422 + FOLLOW_LIMIT_EXCEEDED."""
    session = AsyncMock()
    repo = MagicMock()
    repo.count_active = AsyncMock(return_value=20)
    payload = FollowedUpCreate(
        platform="bilibili",
        uid="12345",
        display_name="new_up",
        profile_url="https://space.bilibili.com/12345",
    )
    with patch(
        "aipulse.api.followed_up.SqlAlchemyFollowedUpRepository", return_value=repo
    ):
        with pytest.raises(HTTPException) as exc_info:
            await create_followed_up_route(payload, session)

    assert exc_info.value.status_code == 422
    detail = exc_info.value.detail
    assert detail["error"] == "FOLLOW_LIMIT_EXCEEDED"
    assert detail["max_size"] == 20
    assert detail["current_count"] == 20


@pytest.mark.unit
async def test_create_followed_up_passes_when_under_limit() -> None:
    """未达上限时，校验通过，正常走 create 流程（这里只断言 count 被调用）。"""
    session = AsyncMock()
    session.commit = AsyncMock()
    repo = MagicMock()
    repo.count_active = AsyncMock(return_value=5)
    repo.create = AsyncMock(side_effect=Exception("stop here - just need count check"))

    payload = FollowedUpCreate(
        platform="bilibili",
        uid="12345",
        display_name="new_up",
        profile_url="https://space.bilibili.com/12345",
    )

    with patch(
        "aipulse.api.followed_up.SqlAlchemyFollowedUpRepository", return_value=repo
    ):
        with pytest.raises(Exception, match="stop here"):
            await create_followed_up_route(payload, session)

    repo.count_active.assert_awaited_once()