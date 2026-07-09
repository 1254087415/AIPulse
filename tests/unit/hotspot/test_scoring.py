from datetime import UTC, datetime, timedelta

import pytest

from aipulse.hotspot.processor import calculate_heat_score


@pytest.mark.unit
def test_fresh_item_scores_higher():
    now = datetime.now(UTC)
    fresh = calculate_heat_score(
        interactions={"likes": 10},
        source_weight=1.0,
        published_at=now,
        keyword_matches=["AI"],
        source_count=1,
        quality_score=10,
    )
    old = calculate_heat_score(
        interactions={"likes": 10},
        source_weight=1.0,
        published_at=now - timedelta(days=7),
        keyword_matches=["AI"],
        source_count=1,
        quality_score=10,
    )
    assert fresh > old


@pytest.mark.unit
def test_more_keyword_matches_score_higher():
    now = datetime.now(UTC)
    more = calculate_heat_score(
        interactions={},
        source_weight=1.0,
        published_at=now,
        keyword_matches=["AI", "LLM"],
        source_count=1,
        quality_score=0,
    )
    less = calculate_heat_score(
        interactions={},
        source_weight=1.0,
        published_at=now,
        keyword_matches=["AI"],
        source_count=1,
        quality_score=0,
    )
    assert more > less
