import pytest

from aipulse.hotspot.processor import compute_similarity, normalize_url


@pytest.mark.unit
def test_normalize_url_removes_tracking_params():
    result = normalize_url("https://example.com/post?utm_source=x&id=42")
    assert "utm_source" not in result
    assert "id=42" in result


@pytest.mark.unit
def test_similarity_high_for_same_content():
    score = compute_similarity("OpenAI releases GPT-5", "OpenAI releases GPT-5")
    assert score > 0.95


@pytest.mark.unit
def test_similarity_low_for_different_content():
    score = compute_similarity("OpenAI releases GPT-5", "Banana bread recipe for beginners")
    assert score < 0.3
