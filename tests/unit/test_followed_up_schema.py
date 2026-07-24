"""Unit tests for FollowedUp / LearningEvent Pydantic schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aipulse.schemas.followed_up import (
    FollowedUpCreate,
    FollowedUpUpdate,
)
from aipulse.schemas.learning_event import LearningEventCreate


@pytest.mark.unit
def test_followed_up_create_minimum_valid_payload():
    """FollowedUpCreate accepts the minimal required fields (display_name optional)."""
    payload = FollowedUpCreate(
        platform="bilibili",
        uid="1567748478",
        profile_url="https://space.bilibili.com/1567748478",
    )
    assert payload.platform == "bilibili"
    assert payload.uid == "1567748478"
    assert payload.display_name is None  # API layer resolves
    assert payload.collector_strategy == "uapi"
    assert payload.fetch_interval_minutes == 30


@pytest.mark.unit
def test_followed_up_create_rejects_non_url_profile():
    """profile_url must start with http(s)://."""
    with pytest.raises(ValidationError):
        FollowedUpCreate(
            platform="bilibili",
            uid="1567748478",
            display_name="Miyabi",
            profile_url="space.bilibili.com/1567748478",
        )


@pytest.mark.unit
def test_followed_up_create_rejects_unknown_collector_strategy():
    """collector_strategy must be uapi or html."""
    with pytest.raises(ValidationError):
        FollowedUpCreate(
            platform="bilibili",
            uid="1567748478",
            display_name="Miyabi",
            profile_url="https://space.bilibili.com/1567748478",
            collector_strategy="graphql",
        )


@pytest.mark.unit
def test_followed_up_create_enforces_uid_length():
    """uid > 64 chars is rejected."""
    with pytest.raises(ValidationError):
        FollowedUpCreate(
            platform="bilibili",
            uid="x" * 65,
            display_name="Miyabi",
            profile_url="https://space.bilibili.com/1567748478",
        )


@pytest.mark.unit
def test_followed_up_create_enforces_fetch_interval_range():
    """fetch_interval_minutes < 1 or > 10080 is rejected."""
    with pytest.raises(ValidationError):
        FollowedUpCreate(
            platform="bilibili",
            uid="1567748478",
            display_name="Miyabi",
            profile_url="https://space.bilibili.com/1567748478",
            fetch_interval_minutes=0,
        )
    with pytest.raises(ValidationError):
        FollowedUpCreate(
            platform="bilibili",
            uid="1567748478",
            display_name="Miyabi",
            profile_url="https://space.bilibili.com/1567748478",
            fetch_interval_minutes=10081,
        )


@pytest.mark.unit
def test_followed_up_update_all_fields_optional():
    """FollowedUpUpdate accepts an empty payload (PATCH semantics)."""
    payload = FollowedUpUpdate()
    assert payload.model_dump(exclude_unset=True) == {}


@pytest.mark.unit
def test_followed_up_update_partial_fields():
    """FollowedUpUpdate preserves only the provided fields."""
    payload = FollowedUpUpdate(display_name="New Name", is_active=False)
    dumped = payload.model_dump(exclude_unset=True)
    assert dumped == {"display_name": "New Name", "is_active": False}


@pytest.mark.unit
def test_learning_event_create_requires_hotspot_and_followed_up():
    """LearningEventCreate requires hotspot_id and followed_up_id."""
    payload = LearningEventCreate(
        hotspot_id="hotspot-abc",
        followed_up_id="up-xyz",
        title="Study: Vite 6 features",
    )
    assert payload.platform == "bilibili"
    assert payload.estimated_minutes is None
    assert payload.scheduled_at is None


@pytest.mark.unit
def test_learning_event_create_enforces_estimated_minutes_range():
    """estimated_minutes > 1440 is rejected."""
    with pytest.raises(ValidationError):
        LearningEventCreate(
            hotspot_id="hotspot-abc",
            followed_up_id="up-xyz",
            title="Study",
            estimated_minutes=5000,
        )


@pytest.mark.unit
def test_schemas_have_from_attributes_config():
    """Schemas expose ``from_attributes`` so they can hydrate from ORM rows."""
    from aipulse.schemas.followed_up import FollowedUpResponse

    cfg = FollowedUpResponse.model_config
    assert cfg.get("from_attributes") is True
