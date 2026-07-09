"""Tests for the GitHub trending collector."""

import pytest
import respx
from httpx import Response

from aipulse.collectors.github import GithubTrendingCollector
from aipulse.collectors.registry import clear_registry, get_collector, register


@pytest.fixture(autouse=True)
def _clean_registry():
    """Clear registry before and after each test."""
    clear_registry()
    yield
    clear_registry()


@pytest.mark.unit
@respx.mock
async def test_github_collector_fetches_and_normalizes_repositories():
    """GithubTrendingCollector parses search results into HotspotCandidates."""
    payload = {
        "items": [
            {
                "full_name": "owner/repo",
                "html_url": "https://github.com/owner/repo",
                "description": "A trending repo",
                "stargazers_count": 1234,
            }
        ]
    }
    route = respx.get("https://api.github.com/search/repositories").mock(
        return_value=Response(200, json=payload)
    )

    collector = GithubTrendingCollector(language="Python")
    raw_items = await collector.fetch()

    assert len(raw_items) == 1
    assert raw_items[0].title == "owner/repo"
    assert raw_items[0].url == "https://github.com/owner/repo"
    assert raw_items[0].content == "A trending repo"
    assert raw_items[0].raw_metadata == {"stars": 1234, "source": "github"}
    assert route.called
    request = route.calls.last.request
    assert "q=language%3APython+stars%3A%3E100" in str(request.url)

    candidate = collector.normalize(raw_items[0])
    assert candidate.title == "owner/repo"
    assert candidate.canonical_url == "https://github.com/owner/repo"
    assert candidate.source_type == "github"


@pytest.mark.unit
@respx.mock
async def test_github_collector_sends_auth_header_when_token_provided():
    """GithubTrendingCollector includes Bearer token when configured."""
    respx.get("https://api.github.com/search/repositories").mock(
        return_value=Response(200, json={"items": []})
    )

    collector = GithubTrendingCollector(language="Go", api_token="secret-token")
    await collector.fetch()

    request = respx.routes[0].calls.last.request
    assert request.headers["Authorization"] == "Bearer secret-token"


@pytest.mark.unit
def test_github_collector_is_registered():
    """GithubTrendingCollector registers itself under github."""
    from aipulse.collectors.github import GithubTrendingCollector as ImportedCollector

    register(ImportedCollector)
    assert get_collector("github") is ImportedCollector
