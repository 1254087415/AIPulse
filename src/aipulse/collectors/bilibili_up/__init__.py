"""B站 UP主采集器族（双线路：uapi + html）。"""

from aipulse.collectors.bilibili_up.base import (
    BaseBilibiliUpCollector,
    UpCollection,
    UpVideo,
)
from aipulse.collectors.bilibili_up.factory import BilibiliUpCollectorFactory
from aipulse.collectors.bilibili_up.html import BilibiliUpHtmlCollector
from aipulse.collectors.bilibili_up.uapi import BilibiliUpUapiCollector

__all__ = [
    "BaseBilibiliUpCollector",
    "UpCollection",
    "UpVideo",
    "BilibiliUpCollectorFactory",
    "BilibiliUpHtmlCollector",
    "BilibiliUpUapiCollector",
]