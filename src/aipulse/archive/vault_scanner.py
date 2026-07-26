"""Obsidian vault 自动扫描 (spec §E5) — Phase 5。

职责：
- 遍历 ``obsidian_vault_path / obsidian_archive_folder`` 下所有 ``.md``
- 解析 YAML frontmatter（标题、video_id、日期、tags 等）
- 返回按 mtime 倒序的笔记清单，供 UI / scheduler 消费

实现策略：
- 同步读盘 + 简单 YAML 解析（不需要 PyYAML；用正则抓 frontmatter）
- 测试可在 tmp_path 里 mock 一个 vault 走真实文件系统
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
KV_RE = re.compile(r"^([a-zA-Z_][\w_-]*):\s*(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class VaultNote:
    """A markdown note found by the vault scanner."""

    path: Path
    title: str
    video_id: Optional[str]
    summarized_at: Optional[datetime]
    mtime: datetime
    size_bytes: int

    @property
    def rel_path(self) -> str:
        try:
            return str(self.path.relative_to(self.path.parents[len(self.path.parts) - 4]))
        except ValueError:
            return str(self.path)


def _strip_quotes(value: str) -> str:
    v = value.strip()
    if v.startswith(('"', "'")) and v.endswith(('"', "'")):
        return v[1:-1]
    return v


def parse_frontmatter(markdown: str) -> dict[str, str]:
    """Extract a flat dict from leading YAML frontmatter (very simple)."""
    match = FRONTMATTER_RE.match(markdown)
    if match is None:
        return {}
    block = match.group(1)
    return {m.group(1): _strip_quotes(m.group(2)) for m in KV_RE.finditer(block)}


def _parse_iso_or_none(s: str | None) -> datetime | None:
    if not s:
        return None
    s = s.strip()
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        # 兼容无时区的 ISO8601
        try:
            return datetime.fromisoformat(s + "+00:00")
        except ValueError:
            return None


def _scan_one(path: Path) -> VaultNote:
    text = path.read_text(encoding="utf-8", errors="replace")
    fm = parse_frontmatter(text)
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    return VaultNote(
        path=path,
        title=fm.get("title") or path.stem,
        video_id=fm.get("video_id"),
        summarized_at=_parse_iso_or_none(fm.get("summarized_at")),
        mtime=mtime,
        size_bytes=path.stat().st_size,
    )


def scan_vault(
    vault_root: Path,
    *,
    archive_folder: str = "AIPulse",
    limit: int = 200,
    recursive: bool = True,
) -> list[VaultNote]:
    """Walk ``vault_root/archive_folder`` returning ``VaultNote`` by mtime desc.

    实现：
    - 跳过 ``.obsidian``、``.trash`` 等 Obsidian 内部目录
    - 容忍单文件损坏（read_text 抛 UnicodeDecodeError 时跳过）
    - 不到 limit 截断
    """
    archive_dir = vault_root / archive_folder
    if not archive_dir.exists() or not archive_dir.is_dir():
        return []
    pattern = "**/*.md" if recursive else "*.md"
    notes: list[VaultNote] = []
    for md_path in archive_dir.glob(pattern):
        # 跳过 Obsidian 系统目录
        rel = md_path.relative_to(archive_dir)
        if any(part.startswith(".") for part in rel.parts):
            continue
        try:
            notes.append(_scan_one(md_path))
        except OSError as exc:
            logger.warning("Skip unreadable vault note %s: %s", md_path, exc)
            continue

    notes.sort(key=lambda n: n.mtime, reverse=True)
    return notes[:limit]
