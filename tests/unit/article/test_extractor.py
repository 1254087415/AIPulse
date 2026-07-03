"""Tests for article extractors.

Exercises ArticleExtractorRegistry.resolve and ArticleExtractor.extract for WeChat and generic articles.
"""

from unittest.mock import MagicMock, patch

import httpx

from aipulse.article.base import ExtractedArticle
from aipulse.article.extractor import GenericArticleExtractor, WechatExtractor
from aipulse.article.registry import ArticleExtractorRegistry, get_article_registry

WECHAT_HTML = """
<!DOCTYPE html>
<html>
<head><title>WeChat Title</title></head>
<body>
    <h1 class="rich_media_title">Article Title</h1>
    <a id="js_name">Author Name</a>
    <div id="js_content"><p>Paragraph one.</p><p>Paragraph two.</p></div>
</body>
</html>
"""

ARTICLE_HTML = """
<!DOCTYPE html>
<html>
<head><title>Page Title</title></head>
<body>
    <article>
        <h1>Real Article</h1>
        <p>This is the main content of the article.</p>
    </article>
</body>
</html>
"""


async def test_wechat_extractor_can_extract():
    extractor = WechatExtractor()
    assert await extractor.can_extract("https://mp.weixin.qq.com/s/abc")
    assert not await extractor.can_extract("https://example.com/article")


async def test_wechat_extractor_parses_page():
    extractor = WechatExtractor()
    with patch("aipulse.article.extractor.httpx.AsyncClient") as mock_client:
        instance = mock_client.return_value.__aenter__.return_value
        instance.get.return_value = MagicMock(
            text=WECHAT_HTML, raise_for_status=MagicMock()
        )
        result = await extractor.extract("https://mp.weixin.qq.com/s/abc")

    assert isinstance(result, ExtractedArticle)
    assert result.title == "Article Title"
    assert result.author == "Author Name"
    assert "Paragraph one" in result.content


async def test_wechat_extractor_returns_empty_on_http_error():
    extractor = WechatExtractor()
    with patch("aipulse.article.extractor.httpx.AsyncClient") as mock_client:
        instance = mock_client.return_value.__aenter__.return_value
        instance.get.side_effect = httpx.HTTPError("network error")
        result = await extractor.extract("https://mp.weixin.qq.com/s/abc")

    assert result.title is None
    assert result.content == ""


async def test_generic_extractor_can_extract_any_url():
    extractor = GenericArticleExtractor()
    assert await extractor.can_extract("https://example.com/article")


async def test_generic_extractor_uses_readability():
    extractor = GenericArticleExtractor()
    with patch("aipulse.article.extractor.httpx.AsyncClient") as mock_client:
        instance = mock_client.return_value.__aenter__.return_value
        instance.get.return_value = MagicMock(
            text=ARTICLE_HTML, raise_for_status=MagicMock()
        )
        result = await extractor.extract("https://example.com/article")

    assert isinstance(result, ExtractedArticle)
    assert result.title is not None
    assert "main content" in result.content


async def test_registry_resolve_prefers_wechat():
    registry = ArticleExtractorRegistry()
    registry.register(WechatExtractor())
    registry.register(GenericArticleExtractor())

    wechat = registry.resolve("https://mp.weixin.qq.com/s/abc")
    generic = registry.resolve("https://example.com/article")

    assert isinstance(wechat, WechatExtractor)
    assert isinstance(generic, GenericArticleExtractor)


def test_get_article_registry_singleton():
    reg1 = get_article_registry()
    reg2 = get_article_registry()
    assert reg1 is reg2
