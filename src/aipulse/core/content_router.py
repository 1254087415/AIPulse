"""Content type router (Chain of Responsibility pattern)."""

from abc import ABC, abstractmethod
from enum import StrEnum

from aipulse.article.registry import get_article_registry
from aipulse.video.parsers.registry import get_parser_registry


class ContentType(StrEnum):
    """Enumeration-like content types."""

    YOUTUBE = "youtube"
    BILIBILI = "bilibili"
    DOUYIN = "douyin"
    XIAOHONGSHU = "xiaohongshu"
    WECHAT_ARTICLE = "wechat_article"
    RSS_FEED = "rss_feed"
    GENERIC_VIDEO = "generic_video"
    GENERIC_ARTICLE = "generic_article"
    UNKNOWN = "unknown"


class ContentTypeHandler(ABC):
    """Handler in the chain of responsibility."""

    def __init__(self) -> None:
        self._next: ContentTypeHandler | None = None

    def set_next(self, handler: "ContentTypeHandler") -> "ContentTypeHandler":
        """Set the next handler in the chain."""
        self._next = handler
        return handler

    async def handle(self, url: str) -> ContentType:
        """Handle the URL or pass it to the next handler."""
        result = await self._check(url)
        if result is not None:
            return result
        if self._next:
            return await self._next.handle(url)
        return ContentType.UNKNOWN

    @abstractmethod
    async def _check(self, url: str) -> ContentType | None:
        """Return a ContentType value or None to pass to next handler."""


class YoutubeHandler(ContentTypeHandler):
    """Detect YouTube URLs."""

    async def _check(self, url: str) -> ContentType | None:
        if any(domain in url for domain in ("youtube.com", "youtu.be")):
            return ContentType.YOUTUBE
        return None


class BilibiliHandler(ContentTypeHandler):
    """Detect Bilibili URLs."""

    async def _check(self, url: str) -> ContentType | None:
        if any(domain in url for domain in ("bilibili.com", "b23.tv")):
            return ContentType.BILIBILI
        return None


class DouyinHandler(ContentTypeHandler):
    """Detect Douyin URLs."""

    async def _check(self, url: str) -> ContentType | None:
        if "douyin.com" in url:
            return ContentType.DOUYIN
        return None


class XiaohongshuHandler(ContentTypeHandler):
    """Detect Xiaohongshu URLs."""

    async def _check(self, url: str) -> ContentType | None:
        if any(domain in url for domain in ("xiaohongshu.com", "xhslink.com")):
            return ContentType.XIAOHONGSHU
        return None


class WechatArticleHandler(ContentTypeHandler):
    """Detect WeChat official account article URLs."""

    async def _check(self, url: str) -> ContentType | None:
        if "mp.weixin.qq.com" in url:
            return ContentType.WECHAT_ARTICLE
        return None


class RssHandler(ContentTypeHandler):
    """Detect RSS feed URLs."""

    async def _check(self, url: str) -> ContentType | None:
        lower_url = url.lower()
        if any(marker in lower_url for marker in (".rss", "/feed", "/rss")):
            return ContentType.RSS_FEED
        return None


class VideoHandler(ContentTypeHandler):
    """Detect video URLs via the parser registry."""

    async def _check(self, url: str) -> ContentType | None:
        registry = get_parser_registry()
        parser = registry.resolve(url)
        if parser is not None and parser.supported_domains:
            # Prefer platform-specific detection over generic video.
            platform = parser.supported_domains[0].split(".")[0]
            if platform in {"youtube", "bilibili", "douyin", "xiaohongshu"}:
                return ContentType(platform)
            return ContentType.GENERIC_VIDEO
        return None


class ArticleHandler(ContentTypeHandler):
    """Detect article URLs via the extractor registry."""

    async def _check(self, url: str) -> ContentType | None:
        registry = get_article_registry()
        extractor = registry.resolve(url)
        if extractor is not None and extractor.supported_domains:
            domain = extractor.supported_domains[0]
            if "weixin" in domain:
                return ContentType.WECHAT_ARTICLE
            return ContentType.GENERIC_ARTICLE
        if extractor is not None:
            return ContentType.GENERIC_ARTICLE
        return None


async def classify_url(url: str) -> ContentType:
    """Classify a URL into a content type using the chain of responsibility."""
    youtube = YoutubeHandler()
    bilibili = BilibiliHandler()
    douyin = DouyinHandler()
    xiaohongshu = XiaohongshuHandler()
    wechat = WechatArticleHandler()
    rss = RssHandler()
    video = VideoHandler()
    article = ArticleHandler()

    (
        youtube.set_next(bilibili)
        .set_next(douyin)
        .set_next(xiaohongshu)
        .set_next(wechat)
        .set_next(rss)
        .set_next(video)
        .set_next(article)
    )

    return await youtube.handle(url)
