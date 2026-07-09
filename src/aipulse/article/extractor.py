"""Article extractor implementations."""

import logging

import httpx
from bs4 import BeautifulSoup
from readability import Document

from aipulse.article.base import ArticleExtractor, ExtractedArticle
from aipulse.core.config import get_settings

logger = logging.getLogger(__name__)


class WechatExtractor(ArticleExtractor):
    """Extract WeChat official account articles."""

    @property
    def supported_domains(self) -> list[str]:
        return ["mp.weixin.qq.com"]

    async def can_extract(self, url: str) -> bool:
        return "mp.weixin.qq.com" in url

    async def extract(self, url: str) -> ExtractedArticle:
        headers = {"User-Agent": get_settings().http_user_agent_mobile}
        try:
            async with httpx.AsyncClient(
                timeout=30.0, follow_redirects=True, headers=headers
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                html = response.text
        except httpx.HTTPError as exc:
            logger.warning("Failed to fetch WeChat article: %s", exc)
            return ExtractedArticle(url=url, title=None, author=None, content="")

        soup = BeautifulSoup(html, "lxml")
        title = self._extract_title(soup)
        author = self._extract_author(soup)
        content = self._extract_content(soup)
        return ExtractedArticle(
            url=url,
            title=title,
            author=author,
            content=content,
        )

    def _extract_title(self, soup: BeautifulSoup) -> str | None:
        tag = soup.find("h1", class_="rich_media_title") or soup.find(
            "h2", class_="rich_media_title"
        )
        return tag.get_text(strip=True) if tag else None

    def _extract_author(self, soup: BeautifulSoup) -> str | None:
        tag = soup.find("a", id="js_name") or soup.find("span", class_="profile_nickname")
        return tag.get_text(strip=True) if tag else None

    def _extract_content(self, soup: BeautifulSoup) -> str:
        body = soup.find("div", id="js_content") or soup.find("div", class_="rich_media_content")
        return body.get_text(separator="\n", strip=True) if body else ""


class GenericArticleExtractor(ArticleExtractor):
    """Generic web article extraction fallback."""

    @property
    def supported_domains(self) -> list[str]:
        return []

    async def can_extract(self, url: str) -> bool:
        return True

    async def extract(self, url: str) -> ExtractedArticle:
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
                html = response.text
        except httpx.HTTPError as exc:
            logger.warning("Failed to fetch article: %s", exc)
            return ExtractedArticle(url=url, title=None, author=None, content="")

        doc = Document(html)
        summary = doc.summary()
        soup = BeautifulSoup(summary, "lxml")
        return ExtractedArticle(
            url=url,
            title=doc.short_title() or None,
            author=None,
            content=soup.get_text(separator="\n", strip=True),
        )
