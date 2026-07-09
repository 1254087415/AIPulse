"""Pydantic schemas for hotspot API responses and requests."""

from datetime import datetime
from typing import Annotated

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
