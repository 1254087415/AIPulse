"""Hotspot processing utilities for normalization, similarity, and scoring."""

import math
from datetime import UTC, datetime
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
}

INTERACTION_WEIGHTS = {
    "views": 0.1,
    "likes": 1.0,
    "comments": 3.0,
    "shares": 5.0,
    "stars": 2.0,
    "forks": 2.0,
}
KEYWORD_MATCH_SCORE = 10.0
MULTI_SOURCE_CAP = 10
MULTI_SOURCE_SCORE = 5.0
FRESHNESS_HALF_LIFE_HOURS = 0.05
FRESHNESS_MAX_SCORE = 100.0
FALLBACK_AGE_HOURS = 24.0


def now_utc() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(UTC)


def normalize_url(url: str) -> str:
    """Return a canonical URL with tracking parameters removed."""
    parsed = urlparse(url)
    kept = sorted(
        (key, value) for key, value in parse_qsl(parsed.query) if key.lower() not in TRACKING_PARAMS
    )
    new_query = urlencode(kept)
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, "", new_query, ""))


def compute_similarity(text1: str, text2: str) -> float:
    """Compute a Jaccard-like similarity score based on character n-grams."""
    tokens1 = set(_ngrams(text1.lower(), 3))
    tokens2 = set(_ngrams(text2.lower(), 3))
    if not tokens1 or not tokens2:
        return 0.0
    return len(tokens1 & tokens2) / len(tokens1 | tokens2)


def _ngrams(text: str, n: int) -> list[str]:
    """Generate character n-grams from text."""
    if len(text) < n:
        return [text]
    return [text[i : i + n] for i in range(len(text) - n + 1)]


def calculate_heat_score(
    interactions: dict[str, int],
    source_weight: float,
    published_at: datetime | None,
    keyword_matches: list[str],
    source_count: int,
    quality_score: float,
) -> float:
    """Calculate a composite heat score for a hotspot item."""
    interaction_score = sum(
        interactions.get(key, 0) * weight for key, weight in INTERACTION_WEIGHTS.items()
    )
    keyword_score = len(keyword_matches) * KEYWORD_MATCH_SCORE
    multi_source_score = min(source_count, MULTI_SOURCE_CAP) * MULTI_SOURCE_SCORE
    if published_at is None:
        hours = FALLBACK_AGE_HOURS
    else:
        # Allow naive datetimes by treating them as UTC.
        reference = published_at
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=UTC)
        hours = max((now_utc() - reference).total_seconds() / 3600, 0)
    freshness_score = FRESHNESS_MAX_SCORE * math.exp(-FRESHNESS_HALF_LIFE_HOURS * hours)
    return source_weight * (
        interaction_score + keyword_score + multi_source_score + freshness_score + quality_score
    )
