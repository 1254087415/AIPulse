"""Tests for the DecisionStatusStr regex schema (Phase 8 A5 FIX).

Spec §3.0 / I7 requires that the five values be enforced at the schema
boundary so any caller (API, scheduler, collector) fails fast on typos.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from aipulse.schemas.followed_up import DecisionStatusStr  # re-exported below


class DecisionStatusProbe(BaseModel):
    """Minimal model that uses the DecisionStatusStr alias for testing."""

    decision_status: DecisionStatusStr


@pytest.mark.unit
def test_accepts_each_of_the_five_canonical_values() -> None:
    """All spec §3.0 values must pass."""
    for value in ("pending", "worth_learning", "worth_notified", "skipped", "failed"):
        model = DecisionStatusProbe(decision_status=value)
        assert model.decision_status == value


@pytest.mark.unit
def test_rejects_unknown_value() -> None:
    """A typo must raise ValidationError, not silently coerce."""
    with pytest.raises(ValidationError) as exc_info:
        DecisionStatusProbe(decision_status="worthlearing")  # missing underscore
    assert "decision_status" in str(exc_info.value)


@pytest.mark.unit
def test_rejects_empty_string() -> None:
    """Empty string is not a valid decision status."""
    with pytest.raises(ValidationError):
        DecisionStatusProbe(decision_status="")


@pytest.mark.unit
def test_decision_status_str_is_reexported_from_followed_up() -> None:
    """Spec calls for DecisionStatusStr; we expose it via followed_up schemas."""
    from aipulse.schemas.followed_up import DecisionStatusStr as FollowedUpDecision  # noqa: WPS433

    assert FollowedUpDecision is DecisionStatusStr