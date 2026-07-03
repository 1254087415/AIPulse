"""Article extractor registry (factory)."""

from aipulse.article.base import ArticleExtractor


class ArticleExtractorRegistry:
    """Factory that resolves an article extractor for a URL."""

    def __init__(self) -> None:
        self._extractors: list[ArticleExtractor] = []

    def register(self, extractor: ArticleExtractor) -> None:
        """Register an extractor strategy."""
        self._extractors.append(extractor)

    def resolve(self, url: str) -> ArticleExtractor | None:
        """Return the first extractor matching the URL domain."""
        fallback: ArticleExtractor | None = None
        for extractor in self._extractors:
            if not extractor.supported_domains:
                fallback = extractor
                continue
            for domain in extractor.supported_domains:
                if domain in url:
                    return extractor
        return fallback


# Global registry populated at import time.
_registry: ArticleExtractorRegistry | None = None


def get_article_registry() -> ArticleExtractorRegistry:
    """Return the singleton article extractor registry."""
    global _registry
    if _registry is None:
        _registry = ArticleExtractorRegistry()
        _register_default_extractors(_registry)
    return _registry


def _register_default_extractors(registry: ArticleExtractorRegistry) -> None:
    """Register built-in article extractors."""
    from aipulse.article.extractor import GenericArticleExtractor, WechatExtractor

    registry.register(WechatExtractor())
    registry.register(GenericArticleExtractor())
