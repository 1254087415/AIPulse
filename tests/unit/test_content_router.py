"""Tests for content router classification."""

import pytest

from aipulse.core.content_router import ContentType, classify_url


@pytest.mark.unit
@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.youtube.com/watch?v=123", ContentType.YOUTUBE),
        ("https://youtu.be/abc", ContentType.YOUTUBE),
        ("https://www.bilibili.com/video/BV1xx411c7mD", ContentType.BILIBILI),
        ("https://b23.tv/xyz", ContentType.BILIBILI),
        ("https://www.douyin.com/video/123", ContentType.DOUYIN),
        ("https://www.xiaohongshu.com/explore/123", ContentType.XIAOHONGSHU),
        ("https://xhslink.com/abc", ContentType.XIAOHONGSHU),
        ("https://mp.weixin.qq.com/s/abc", ContentType.WECHAT_ARTICLE),
        ("https://example.com/feed", ContentType.RSS_FEED),
        ("https://example.com/rss.xml", ContentType.RSS_FEED),
        ("https://unknown.example.com/page", ContentType.GENERIC_ARTICLE),
        ("https://unknown.example.com/unknown", ContentType.GENERIC_ARTICLE),
    ],
)
async def test_classify_url(url: str, expected: ContentType) -> None:
    result = await classify_url(url)
    assert result == expected
