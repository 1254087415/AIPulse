"""Pydantic schemas for LearningEvent."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


PlatformStr = Annotated[str, Field(min_length=1, max_length=16)]
LearningStatusStr = Annotated[
    str, Field(pattern=r"^(unread|learning|mastered|review)$")
]


class LearningEventCreate(BaseModel):
    """Input schema for creating a learning event from a hotspot archive."""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    hotspot_id: str
    followed_up_id: str
    title: str = Field(min_length=1, max_length=256)
    scheduled_at: datetime | None = None
    estimated_minutes: int | None = Field(default=None, ge=1, le=1440)
    summary_note_path: str | None = Field(default=None, max_length=512)
    platform: PlatformStr = "bilibili"
    apple_reminders_list: str = Field(default="工作学习", max_length=64)


class LearningEventResponse(BaseModel):
    """Output schema for a learning event."""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: str
    hotspot_id: str
    followed_up_id: str
    platform: PlatformStr
    title: str
    summary_note_path: str | None
    scheduled_at: datetime
    estimated_minutes: int
    obsidian_task_created: bool
    apple_reminder_id: str | None
    apple_reminders_list: str
    completed_at: datetime | None
    learning_status: LearningStatusStr
    created_at: datetime
    updated_at: datetime
