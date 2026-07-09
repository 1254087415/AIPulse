"""GitHub trending collector."""

import httpx

from aipulse.collectors.base import BaseCollector, HotspotCandidate, RawItem
from aipulse.collectors.registry import register


@register
class GithubTrendingCollector(BaseCollector):
    """Collector for trending GitHub repositories via the Search API."""

    source_type = "github"
    name = "GitHub Trending"

    def __init__(
        self,
        language: str = "Python",
        timeout: float = 30.0,
        api_token: str = "",
    ):
        self.language = language
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "AIPulse/0.2",
        }
        if api_token:
            headers["Authorization"] = f"Bearer {api_token}"
        self._client = httpx.AsyncClient(timeout=timeout, headers=headers)

    async def fetch(self) -> list[RawItem]:
        """Fetch trending repositories from the GitHub Search API."""
        params = {
            "q": f"language:{self.language} stars:>100",
            "sort": "stars",
            "order": "desc",
            "per_page": "20",
        }
        response = await self._client.get(
            "https://api.github.com/search/repositories",
            params=params,
        )
        response.raise_for_status()
        items = response.json().get("items", [])
        return [
            RawItem(
                title=repo["full_name"],
                url=repo["html_url"],
                content=repo.get("description") or "",
                published_at=None,
                raw_metadata={
                    "stars": repo.get("stargazers_count", 0),
                    "source": "github",
                },
            )
            for repo in items
        ]

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    def normalize(self, raw: RawItem) -> HotspotCandidate:
        """Normalize a raw GitHub repository into a hotspot candidate."""
        return HotspotCandidate(
            title=raw.title,
            url=raw.url,
            canonical_url=raw.url,
            content=raw.content,
            published_at=raw.published_at,
            source_type=self.source_type,
            raw_metadata=raw.raw_metadata,
        )
