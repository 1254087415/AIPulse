"""Article extraction strategy base classes."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ExtractedArticle:
    """Result of extracting an article."""

    url: str
    title: str | None
    author: str | None
    content: str
    published_at: str | None = None


class ArticleExtractor(ABC):
    """Strategy for extracting article content from a URL."""

    @property
    @abstractmethod
    def supported_domains(self) -> list[str]:
        """Return supported domains."""

    @abstractmethod
    async def can_extract(self, url: str) -> bool:
        """Return True if this extractor handles the URL."""

    @abstractmethod
    async def extract(self, url: str) -> ExtractedArticle:
        """Extract the article content."""
