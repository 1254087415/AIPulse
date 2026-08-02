"""Pydantic schemas for FollowedUp / FollowedUpCollection."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator

from aipulse.core.datetime_utils import format_iso_utc

PlatformStr = Annotated[str, Field(min_length=1, max_length=16)]
UidStr = Annotated[str, Field(min_length=1, max_length=64)]
DisplayNameStr = Annotated[str, Field(min_length=1, max_length=128)]
ProfileUrlStr = Annotated[str, Field(min_length=1, max_length=256)]
CollectorStrategyStr = Annotated[str, Field(pattern=r"^(uapi|html)$")]
StatusStr = Annotated[str, Field(pattern=r"^(active|paused|auth_failed)$")]
HealthStr = Annotated[str, Field(pattern=r"^(healthy|warning|error)$")]
# Phase 8 A5 FIX: spec §3.0 / I7 — Hotspot.decision_status is one of exactly
# five values. The DB stores it as a 16-char varchar; this schema-level
# regex is the boundary check so collectors and scheduler jobs fail fast on
# typos instead of silently writing garbage.
DecisionStatusStr = Annotated[
    str,
    Field(pattern=r"^(pending|worth_learning|worth_notified|skipped|failed)$"),
]




class FollowedUpBase(BaseModel):
    """Common fields for FollowedUp create / response."""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    platform: PlatformStr
    uid: UidStr
    display_name: DisplayNameStr
    profile_url: ProfileUrlStr
    collector_strategy: CollectorStrategyStr = "uapi"
    fetch_interval_minutes: int = Field(default=30, ge=1, le=10080)


class FollowedUpCreate(BaseModel):
    """Input schema for POST /api/followed-up.

    Spec §6.6: callers paste a B站 profile URL and the backend derives
    ``platform``, ``uid``, ``display_name`` and ``profile_url``. Only
    ``platform`` and ``uid`` are mandatory; the rest are filled in by the
    API layer (see ``create_followed_up_route``).
    """

    model_config = ConfigDict(from_attributes=True, frozen=True)

    platform: PlatformStr
    uid: UidStr
    display_name: DisplayNameStr | None = None
    profile_url: str | None = Field(default=None, max_length=256)
    collector_strategy: CollectorStrategyStr = "uapi"
    fetch_interval_minutes: int = Field(default=30, ge=1, le=10080)
    config: dict[str, Any] | None = None

    @field_validator("profile_url")
    @classmethod
    def validate_profile_url(cls, v: str | None) -> str | None:
        """Require an http(s) URL when the caller supplies one."""
        if v is None:
            return v
        if not v.startswith(("http://", "https://")):
            raise ValueError("profile_url must start with http:// or https://")
        return v


class FollowedUpUpdate(BaseModel):
    """Partial update schema (PATCH semantics). All fields optional.

    spec §6.12 ships ``enabled`` as the canonical pause/resume payload
    (mirrors the ``enabled`` field returned by ``GET /detail``), while the
    persistence column is ``is_active``. Accept both names; ``enabled``
    wins when both are present. They must agree when both are provided.
    """

    model_config = ConfigDict(from_attributes=True, frozen=True)

    display_name: DisplayNameStr | None = None
    collector_strategy: CollectorStrategyStr | None = None
    fetch_interval_minutes: int | None = Field(default=None, ge=1, le=10080)
    is_active: bool | None = None
    # spec §6.12 canonical pause/resume field. Coerced onto is_active in the
    # model_validator below; the repository layer never sees this alias.
    enabled: bool | None = None
    status: StatusStr | None = None
    config: dict[str, Any] | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_enabled(cls, data):
        if not isinstance(data, dict):
            return data
        enabled = data.get("enabled")
        is_active = data.get("is_active")
        if enabled is not None and is_active is not None and bool(enabled) != bool(is_active):
            raise ValueError(
                "`enabled` and `is_active` disagree; send only one or matching values"
            )
        if enabled is not None and is_active is None:
            data["is_active"] = enabled
        return data


class FollowedUpResponse(BaseModel):
    """Output schema for a single FollowedUp record."""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: str
    platform: PlatformStr
    uid: UidStr
    mid: str | None = None
    display_name: DisplayNameStr
    profile_url: ProfileUrlStr
    collector_strategy: CollectorStrategyStr
    last_cursor_id: str | None = None
    fetch_interval_minutes: int
    is_active: bool
    status: StatusStr
    health: HealthStr
    last_checked_at: datetime | None = None
    last_error: str | None = None
    failed_at: datetime | None = None
    config: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    video_count: int = Field(default=0, ge=0)

    @field_serializer(
        "last_checked_at",
        "failed_at",
        "created_at",
        "updated_at",
        "deleted_at",
        check_fields=False,
    )
    def _serialize_datetime(self, value: datetime | None) -> str | None:
        """v0.3 时区修复：所有 datetime 字段序列化必带 +00:00 偏移。

        SQLite 读回 DATETIME 字段会丢 tzinfo，让 Pydantic 默认
        ``isoformat()`` 输出无偏移字符串 → 前端 format.ts fallback
        按 +08:00 误读 → 显示比真实慢 8 小时。这里走 format_iso_utc
        统一归一为 UTC aware 后再序列化。
        """
        return format_iso_utc(value)


class FollowedUpCollectionCreate(BaseModel):
    """Input schema for collections (collector-driven, not exposed in API)."""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    followed_up_id: str
    platform_collection_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=256)
    description: str | None = None
    video_count: int = Field(default=0, ge=0)


class FollowedUpCollectionResponse(BaseModel):
    """Output schema for a collection."""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: str
    followed_up_id: str
    platform_collection_id: str
    title: str
    description: str | None
    video_count: int
    last_synced_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @field_serializer(
        "last_synced_at",
        "created_at",
        "updated_at",
        check_fields=False,
    )
    def _serialize_datetime(self, value: datetime | None) -> str | None:
        return format_iso_utc(value)
