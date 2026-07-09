"""arXiv collector."""

import xml.etree.ElementTree as ET
from datetime import datetime

import httpx

from aipulse.collectors.base import BaseCollector, HotspotCandidate, RawItem
from aipulse.collectors.registry import register

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


def _parse_iso(value: str | None) -> datetime | None:
    """Parse an ISO 8601 date string to a timezone-aware datetime."""
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _parse_arxiv_xml(xml_text: str) -> list[RawItem]:
    """Parse arXiv Atom XML into raw items."""
    root = ET.fromstring(xml_text)
    items: list[RawItem] = []
    for entry in root.findall("atom:entry", ATOM_NS):
        items.append(
            RawItem(
                title=(entry.findtext("atom:title", namespaces=ATOM_NS) or "").strip(),
                url=(entry.findtext("atom:id", namespaces=ATOM_NS) or "").strip(),
                content=(entry.findtext("atom:summary", namespaces=ATOM_NS) or "").strip(),
                published_at=_parse_iso(entry.findtext("atom:published", namespaces=ATOM_NS)),
                raw_metadata={"source": "arxiv"},
            )
        )
    return items


@register
class ArxivCollector(BaseCollector):
    """Collector for arXiv papers."""

    source_type = "arxiv"
    name = "arXiv"

    def __init__(self, categories: list[str] | None = None, timeout: float = 30.0):
        self.categories = categories or ["cs.AI", "cs.CL"]
        self._client = httpx.AsyncClient(timeout=timeout)

    async def fetch(self) -> list[RawItem]:
        """Fetch recent papers from arXiv."""
        cat_query = " OR ".join(f"cat:{c}" for c in self.categories)
        url = (
            "http://export.arxiv.org/api/query"
            f"?search_query={cat_query}&sortBy=submittedDate&max_results=20"
        )
        response = await self._client.get(url)
        response.raise_for_status()
        return _parse_arxiv_xml(response.text)

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    def normalize(self, raw: RawItem) -> HotspotCandidate:
        """Normalize a raw arXiv entry into a hotspot candidate."""
        return HotspotCandidate(
            title=raw.title,
            url=raw.url,
            canonical_url=raw.url,
            content=raw.content,
            published_at=raw.published_at,
            source_type=self.source_type,
            raw_metadata=raw.raw_metadata,
        )
