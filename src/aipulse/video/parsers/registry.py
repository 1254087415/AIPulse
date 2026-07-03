"""Parser registry (factory for content parsers)."""

from aipulse.video.parsers.base import ContentParser


class ParserRegistry:
    """Factory that resolves a parser for a given URL."""

    def __init__(self) -> None:
        self._parsers: list[ContentParser] = []

    def register(self, parser: ContentParser) -> None:
        """Register a parser strategy."""
        self._parsers.append(parser)

    def resolve(self, url: str) -> ContentParser | None:
        """Return the first parser that can handle the URL.

        Falls back to a parser with no supported_domains if no domain matches.
        """
        fallback: ContentParser | None = None
        for parser in self._parsers:
            if not parser.supported_domains:
                fallback = parser
                continue
            for domain in parser.supported_domains:
                if domain in url:
                    return parser
        return fallback


# Global registry populated at import time.
_registry: ParserRegistry | None = None


def get_parser_registry() -> ParserRegistry:
    """Return the singleton parser registry."""
    global _registry
    if _registry is None:
        _registry = ParserRegistry()
        _register_default_parsers(_registry)
    return _registry


def _register_default_parsers(registry: ParserRegistry) -> None:
    """Register built-in platform parsers."""
    from aipulse.video.parsers.bilibili import BilibiliParser
    from aipulse.video.parsers.douyin import DouyinParser
    from aipulse.video.parsers.generic import GenericParser
    from aipulse.video.parsers.xiaohongshu import XiaohongshuParser
    from aipulse.video.parsers.youtube import YoutubeParser

    registry.register(BilibiliParser())
    registry.register(YoutubeParser())
    registry.register(DouyinParser())
    registry.register(XiaohongshuParser())
    registry.register(GenericParser())
