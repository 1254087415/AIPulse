"""Tests for hotspot models."""

from datetime import UTC, datetime

import pytest

from aipulse.hotspot.models import Hotspot, Source


@pytest.mark.unit
def test_hotspot_can_be_instantiated_with_required_fields():
    """Hotspot required fields and defaults are correctly applied."""
    source = Source(name="HN", source_type="rss_news", collector_class="RssNewsCollector")
    hotspot = Hotspot(
        title="GPT-5 released",
        url="https://example.com/1?utm_source=x",
        canonical_url="https://example.com/1",
        source_id=source.id,
        source_type="rss_news",
        published_at=datetime.now(UTC),
    )
    assert hotspot.title == "GPT-5 released"
    assert hotspot.heat_score == 0.0
    assert hotspot.importance == "medium"
