"""Followed-up HTTP API routes."""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from aipulse.repositories.followed_up_repo import (
    DuplicateFollowedUpError,
    FollowedUpNotFoundError,
    SqlAlchemyFollowedUpRepository,
)
from aipulse.schemas.followed_up import (
    FollowedUpCreate,
    FollowedUpResponse,
    FollowedUpUpdate,
)
from aipulse.store.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/followed-up", tags=["followed-up"])

_BILIBILI_CARD_URL = "https://api.bilibili.com/x/web-interface/card"
_BILIBILI_VALIDATE_TIMEOUT = 15.0


async def _resolve_bilibili_display_name(uid: str) -> tuple[str, str]:
    """Look up the B站 user display name via the public card API.

    Returns ``(display_name, profile_url)``. Network failures are tolerated:
    the caller falls back to ``uid`` as the display name.
    """
    profile_url = f"https://space.bilibili.com/{uid}"
    try:
        async with httpx.AsyncClient(timeout=_BILIBILI_VALIDATE_TIMEOUT) as client:
            response = await client.get(
                _BILIBILI_CARD_URL,
                params={"mid": uid},
                headers={"User-Agent": "AIPulse/0.3"},
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Bilibili card lookup failed for mid=%s: %s", uid, exc)
        return uid, profile_url

    data = payload.get("data") or {}
    card = data.get("card") or {}
    name = card.get("name") or uid
    return name, profile_url


@router.post("", status_code=201)
async def create_followed_up_route(
    payload: FollowedUpCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Create a new FollowedUp entry.

    If the caller omits ``display_name``, the B站 card API is consulted
    to fill it in. Network failures fall back to ``uid``.
    """
    repo = SqlAlchemyFollowedUpRepository(session)

    display_name = payload.display_name
    if not display_name and payload.platform == "bilibili":
        display_name, profile_url = await _resolve_bilibili_display_name(payload.uid)
    else:
        profile_url = payload.profile_url

    try:
        record = await repo.create(
            platform=payload.platform,
            uid=payload.uid,
            display_name=display_name,
            profile_url=profile_url,
            collector_strategy=payload.collector_strategy,
            fetch_interval_minutes=payload.fetch_interval_minutes,
            config=payload.config,
        )
    except DuplicateFollowedUpError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "success": False,
                "error": "Duplicate FollowedUp",
                "message": str(exc),
            },
        ) from exc

    await session.commit()
    return {"success": True, "data": FollowedUpResponse.model_validate(record).model_dump()}


@router.get("")
async def list_followed_up_route(
    session: Annotated[AsyncSession, Depends(get_session)],
    include_deleted: Annotated[bool, Query()] = False,
) -> dict[str, Any]:
    """List FollowedUp rows, newest first."""
    repo = SqlAlchemyFollowedUpRepository(session)
    records = await repo.list_all(include_deleted=include_deleted)
    return {
        "success": True,
        "data": [
            FollowedUpResponse.model_validate(r).model_dump() for r in records
        ],
    }


@router.get("/{followed_up_id}")
async def get_followed_up_route(
    followed_up_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Return a single FollowedUp by id."""
    repo = SqlAlchemyFollowedUpRepository(session)
    record = await repo.find_by_id(followed_up_id)
    if record is None or record.deleted_at is not None:
        raise HTTPException(status_code=404, detail="FollowedUp not found")
    return {
        "success": True,
        "data": FollowedUpResponse.model_validate(record).model_dump(),
    }


@router.patch("/{followed_up_id}")
async def update_followed_up_route(
    followed_up_id: str,
    payload: FollowedUpUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Partially update a FollowedUp."""
    repo = SqlAlchemyFollowedUpRepository(session)
    try:
        record = await repo.update(
            followed_up_id,
            **payload.model_dump(exclude_unset=True),
        )
    except FollowedUpNotFoundError as exc:
        await session.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await session.commit()
    return {
        "success": True,
        "data": FollowedUpResponse.model_validate(record).model_dump(),
    }


@router.delete("/{followed_up_id}")
async def delete_followed_up_route(
    followed_up_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Soft-delete a FollowedUp."""
    repo = SqlAlchemyFollowedUpRepository(session)
    try:
        await repo.soft_delete(followed_up_id)
    except FollowedUpNotFoundError as exc:
        await session.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await session.commit()
    return {"success": True, "data": {"id": followed_up_id}}


@router.post("/validate")
async def validate_followed_up_route(
    payload: FollowedUpCreate,
) -> dict[str, Any]:
    """Validate that a given (platform, uid) exists on the source platform.

    Currently only B站 is implemented. Returns the live display name and
    profile URL or a 502/504 if the upstream API is unreachable.
    """
    if payload.platform != "bilibili":
        raise HTTPException(
            status_code=400,
            detail=f"validate() not implemented for platform={payload.platform}",
        )

    try:
        display_name, profile_url = await asyncio.wait_for(
            _resolve_bilibili_display_name(payload.uid),
            timeout=_BILIBILI_VALIDATE_TIMEOUT,
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Bilibili card API timeout") from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=f"Bilibili card API error: {exc}") from exc

    return {
        "success": True,
        "data": {
            "platform": payload.platform,
            "uid": payload.uid,
            "display_name": display_name,
            "profile_url": profile_url,
        },
    }


@router.post("/{followed_up_id}/sync", status_code=501)
async def sync_followed_up_route(
    followed_up_id: str,
) -> dict[str, Any]:
    """Placeholder for Phase 2 collector implementation. Returns 501."""
    return {
        "success": False,
        "error": "Not implemented (Phase 2 placeholder)",
        "followed_up_id": followed_up_id,
    }
