"""Base collector framework."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class RawItem:
    """A raw item fetched from a source before normalization."""

    title: str
    url: str
    content: str = ""
    published_at: datetime | None = None
    raw_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class HotspotCandidate:
    """A normalized candidate ready for hotspot processing."""

    title: str
    url: str
    canonical_url: str
    content: str
    published_at: datetime | None
    source_type: str
    raw_metadata: dict[str, Any]


class BaseCollector(ABC):
    """Abstract base class for all collectors."""

    source_type: str
    name: str

    @classmethod
    def from_source(cls, source: Any) -> "BaseCollector":
        """Instantiate a collector from a source configuration object."""
        return cls(**(source.config or {}))

    @abstractmethod
    async def fetch(self) -> list[RawItem]:
        """Fetch raw items from the source."""
        ...

    @abstractmethod
    def normalize(self, raw: RawItem) -> HotspotCandidate:
        """Normalize a raw item into a hotspot candidate."""
        ...

    async def close(self) -> None:
        """Release any resources held by the collector."""
        return None
