"""Pydantic schemas for hotspot API responses and requests."""

from datetime import date, datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class HotspotOut(BaseModel):
    """Output schema for a single hotspot."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    url: str
    summary: str | None
    source_type: str
    heat_score: float
    importance: str
    category: str | None
    published_at: datetime | None


class HotspotListResponse(BaseModel):
    success: bool
    data: list[HotspotOut]
    meta: dict


class KeywordCreate(BaseModel):
    value: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
    ] = Field(...)


class KeywordOut(BaseModel):
    """Output schema for a keyword."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    value: str
    is_active: bool
    notify_on_match: bool
    created_at: datetime


class KeywordUpdate(BaseModel):
    is_active: bool | None = None
    notify_on_match: bool | None = None


class SourceOut(BaseModel):
    """Output schema for a configured source."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    source_type: str
    collector_class: str
    config: dict[str, Any] | None
    default_weight: float
    fetch_interval_minutes: int
    is_active: bool
    last_fetched_at: datetime | None
    last_error: str | None
    failed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class SourceUpdate(BaseModel):
    config: dict[str, Any] | None = None
    default_weight: float | None = None
    fetch_interval_minutes: int | None = None
    is_active: bool | None = None


class DailyDigestOut(BaseModel):
    """Output schema for a daily digest."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    date: date
    title: str
    content: str
    top_hotspot_ids: list[Any] | None
    generated_at: datetime
    pushed_at: datetime | None
