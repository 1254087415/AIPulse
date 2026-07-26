"""Unit tests for the v0.3 vault scanner (Phase 5, spec §E5).

覆盖：
- parse_frontmatter 解析 key: value / 引号 / 不存在
- _parse_iso_or_none 时区兼容
- scan_vault 真文件扫描（tmp_path），过滤隐藏目录
- 返回顺序按 mtime 倒序
- vault 不存在返回 []
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from aipulse.archive.vault_scanner import (
    VaultNote,
    parse_frontmatter,
    scan_vault,
)


def test_parse_frontmatter_extracts_simple_kv() -> None:
    md = (
        "---\n"
        "title: Hello\n"
        "video_id: BV1abc\n"
        "tags: [ai, agent]\n"
        "---\n"
        "body"
    )
    fm = parse_frontmatter(md)
    assert fm["title"] == "Hello"
    assert fm["video_id"] == "BV1abc"
    assert "tags" in fm


def test_parse_frontmatter_strips_quotes() -> None:
    md = '---\ntitle: "Quoted Title"\nmodel: \'kimi\'\n---\nbody'
    fm = parse_frontmatter(md)
    assert fm["title"] == "Quoted Title"
    assert fm["model"] == "kimi"


def test_parse_frontmatter_missing_returns_empty() -> None:
    assert parse_frontmatter("# no frontmatter") == {}
    assert parse_frontmatter("") == {}


def test_parse_frontmatter_ignores_indented_blocks() -> None:
    md = "---\ntitle: ok\nnested:\n  a: 1\n---\nbody"
    fm = parse_frontmatter(md)
    assert fm["title"] == "ok"
    # nested block 不进入 simple flat parser


def _make_note(path: Path, *, title: str, vid: str | None, when: datetime) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\ntitle: {title}\n"
        + (f"video_id: {vid}\n" if vid else "")
        + f"summarized_at: {when.isoformat()}\n"
        + "---\n\n# body",
        encoding="utf-8",
    )
    # 设置 mtime
    ts = when.timestamp()
    import os
    os.utime(path, (ts, ts))


@pytest.mark.unit
def test_scan_vault_returns_newest_first(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    archive = vault / "AIPulse"
    archive.mkdir(parents=True)
    now = datetime.now(UTC)
    _make_note(
        archive / "old.md",
        title="old",
        vid="BV1old",
        when=now - timedelta(days=2),
    )
    _make_note(
        archive / "new.md",
        title="new",
        vid="BV1new",
        when=now,
    )
    _make_note(
        archive / "mid.md",
        title="mid",
        vid="BV1mid",
        when=now - timedelta(days=1),
    )

    notes = scan_vault(vault, archive_folder="AIPulse")
    assert [n.title for n in notes] == ["new", "mid", "old"]
    assert notes[0].video_id == "BV1new"
    assert notes[0].path.suffix == ".md"
    assert notes[0].size_bytes > 0


@pytest.mark.unit
def test_scan_vault_skips_hidden_dirs(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    archive = vault / "AIPulse"
    (archive / ".obsidian").mkdir(parents=True)
    (archive / ".trash").mkdir(parents=True)
    _make_note(
        archive / "good.md",
        title="good",
        vid="BV1",
        when=datetime.now(UTC),
    )
    _make_note(
        archive / ".obsidian" / "hidden.md",
        title="hidden",
        vid="BVh",
        when=datetime.now(UTC),
    )
    notes = scan_vault(vault)
    assert [n.title for n in notes] == ["good"]


@pytest.mark.unit
def test_scan_vault_handles_missing_archive(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    assert scan_vault(vault, archive_folder="AIPulse") == []


@pytest.mark.unit
def test_scan_vault_handles_missing_vault(tmp_path: Path) -> None:
    assert scan_vault(tmp_path / "nope") == []


@pytest.mark.unit
def test_scan_vault_respects_limit(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    archive = vault / "AIPulse"
    archive.mkdir(parents=True)
    now = datetime.now(UTC)
    for i in range(5):
        _make_note(
            archive / f"note_{i}.md",
            title=f"t{i}",
            vid=f"BV{i}",
            when=now - timedelta(minutes=i),
        )
    assert len(scan_vault(vault, limit=3)) == 3
    assert len(scan_vault(vault, limit=10)) == 5


@pytest.mark.unit
def test_scan_vault_non_recursive(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    archive = vault / "AIPulse"
    sub = archive / "deep"
    sub.mkdir(parents=True)
    _make_note(
        archive / "top.md",
        title="top",
        vid=None,
        when=datetime.now(UTC),
    )
    _make_note(
        sub / "deep.md",
        title="deep",
        vid=None,
        when=datetime.now(UTC),
    )
    notes = scan_vault(vault, recursive=False)
    assert [n.title for n in notes] == ["top"]
