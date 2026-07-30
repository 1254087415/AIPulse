"""统一时区工具：所有后端 datetime 写入 / 读取 / 序列化路径的归一入口。

v0.3 修时区缺陷（spec §9.1 I 类红线）：

- **写入层**：所有 ``now()`` 须走 :func:`now_utc` 返回 UTC aware；
  Python 3.12+ 已 ``DeprecationWarning`` ``datetime.utcnow()``，必须替。
- **读取层 / 比较层**：SQLite 存 ``DATETIME`` 时丢 tzinfo，DB 里既存
  naive UTC 记录与新写入 aware 记录并存。 :func:`to_utc` 接受二者统一
  归一为 UTC aware（naive 视为 UTC，aware 转为 UTC），让历史数据可
  平滑迁移。
- **序列化层**：API 输出串必须带偏移（``+00:00``），让前端 ``format.ts``
  不再走 fallback 误读为 +08:00。 :func:`format_iso_utc` 统一封装。
"""

from __future__ import annotations

from datetime import UTC, datetime


def now_utc() -> datetime:
    """Return the current UTC datetime as a timezone-aware object.

    Replace ``datetime.utcnow()`` (deprecated in Python 3.12+) and naive
    ``datetime.now()`` everywhere in the backend.
    """
    return datetime.now(UTC)


def to_utc(dt: datetime | None) -> datetime | None:
    """Normalize a datetime to a UTC-aware one.

    Legacy SQLite rows may carry naive UTC values (datetimes written
    before this fix). Treating them as UTC preserves user-visible
    timestamps while keeping comparisons safe — comparing naive vs
    aware downstream raises ``TypeError``.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def format_iso_utc(dt: datetime | None) -> str | None:
    """Serialize a datetime to ISO 8601 with ``+00:00`` offset.

    Naive inputs are treated as UTC (legacy rows). The output always
    carries an explicit offset so the frontend `format.ts` won't fall
    back to the local timezone and produce 8-hour slow displays.
    """
    if dt is None:
        return None
    return to_utc(dt).isoformat()
