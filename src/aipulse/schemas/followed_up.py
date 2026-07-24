"""Pydantic schemas for FollowedUp / FollowedUpCollection."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


PlatformStr = Annotated[str, Field(min_length=1, max_length=16)]
UidStr = Annotated[str, Field(min_length=1, max_length=64)]
DisplayNameStr = Annotated[str, Field(min_length=1, max_length=128)]
ProfileUrlStr = Annotated[str, Field(min_length=1, max_length=256)]
CollectorStrategyStr = Annotated[str, Field(pattern=r"^(uapi|html)$")]
StatusStr = Annotated[str, Field(pattern=r"^(active|paused|auth_failed)$")]
HealthStr = Annotated[str, Field(pattern=r"^(healthy|warning|error)$")]


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

    Note: ``display_name`` is optional — the API layer will resolve it from
    the source platform (B站) when omitted. ``profile_url`` is required so
    the backend can build a canonical URL when the platform lookup fails.
    """

    model_config = ConfigDict(from_attributes=True, frozen=True)

    platform: PlatformStr
    uid: UidStr
    display_name: DisplayNameStr | None = None
    profile_url: ProfileUrlStr
    collector_strategy: CollectorStrategyStr = "uapi"
    fetch_interval_minutes: int = Field(default=30, ge=1, le=10080)
    config: dict[str, Any] | None = None

    @field_validator("profile_url")
    @classmethod
    def validate_profile_url(cls, v: str) -> str:
        """Require an http(s) URL."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("profile_url must start with http:// or https://")
        return v


class FollowedUpUpdate(BaseModel):
    """Partial update schema (PATCH semantics). All fields optional."""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    display_name: DisplayNameStr | None = None
    collector_strategy: CollectorStrategyStr | None = None
    fetch_interval_minutes: int | None = Field(default=None, ge=1, le=10080)
    is_active: bool | None = None
    status: StatusStr | None = None
    config: dict[str, Any] | None = None


class FollowedUpResponse(BaseModel):
    """Output schema for a single FollowedUp record."""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: str
    platform: PlatformStr
    uid: UidStr
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
