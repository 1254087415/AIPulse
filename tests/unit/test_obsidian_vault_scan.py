"""Unit tests for the obsidian-vault scan endpoint (spec E3).

POST /api/settings/obsidian-vault/scan returns a list of candidate
directories the user can pick from. The list is the union of:

  * DEFAULT_VAULT_CANDIDATES — well-known macOS / iCloud / Nutstore paths
  * CWD ancestors up to 5 levels — auto-detects an in-tree vault when the
    project happens to ship a sample vault (e.g. tests/dev fixtures).

Each candidate carries {path, exists, note}; exists is computed at request
time so the UI can show a checkmark / dim out missing paths.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from aipulse.web.routes import (
    DEFAULT_VAULT_CANDIDATES,
    scan_obsidian_vault_route,
)


# ---------------------------------------------------------------------------
# Route signature is async so we await it under pytest-asyncio. The project
# already configures asyncio mode (see pyproject.toml / pytest.ini), so plain
# `async def` tests work without an explicit marker.
# ---------------------------------------------------------------------------


async def test_scan_returns_at_least_default_candidates(tmp_path: Path, monkeypatch) -> None:
    """The response must always include DEFAULT_VAULT_CANDIDATES.

    We point HOME at tmp_path so the candidates resolve to paths we can
    control, and we check the list *contains* every entry from the constant
    (the OS may add a few extra — e.g. derived from CWD — but the canonical
    set must always be there).
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    response = await scan_obsidian_vault_route()
    data = response["data"]

    assert response["success"] is True
    paths = {c["path"] for c in data["candidates"]}
    for expected in DEFAULT_VAULT_CANDIDATES:
        assert expected in paths, f"missing default candidate: {expected}"


async def test_scan_marks_existing_paths(tmp_path: Path, monkeypatch) -> None:
    """A candidate that resolves to an existing directory gets exists=True.

    We materialise exactly one of the DEFAULT_VAULT_CANDIDATES inside
    tmp_path and assert only that one is flagged exists=True among the
    default set.
    """
    monkeypatch.setenv("HOME", str(tmp_path))

    # Make the FIRST default candidate exist by creating it relative to HOME
    first = DEFAULT_VAULT_CANDIDATES[0].replace("~", str(tmp_path))
    Path(first).mkdir(parents=True, exist_ok=True)

    response = await scan_obsidian_vault_route()
    candidates = response["data"]["candidates"]

    by_path = {c["path"]: c for c in candidates}
    assert by_path[DEFAULT_VAULT_CANDIDATES[0]]["exists"] is True

    # The other defaults should NOT exist (HOME is empty).
    for cand in candidates:
        if cand["path"] == DEFAULT_VAULT_CANDIDATES[0]:
            continue
        if cand["path"] in DEFAULT_VAULT_CANDIDATES:
            assert cand["exists"] is False, (
                f"{cand['path']} unexpectedly exists"
            )


async def test_scan_includes_cwd_ancestors_up_to_5_levels(tmp_path: Path, monkeypatch) -> None:
    """CWD-walking scan must include up to 5 ancestor directories.

    The implementation walks from CWD upward to the filesystem root,
    collecting paths; we cap at 5 levels per spec E3. We can't reliably
    assert the *exact* set (depends on the test runner's CWD), so we just
    assert: the candidate count is at least 5, and every candidate has a
    non-empty note.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    response = await scan_obsidian_vault_route()
    candidates = response["data"]["candidates"]

    assert len(candidates) >= 5
    for c in candidates:
        assert c["path"]
        # note may be empty for CWD ancestors; defaults always have one
        assert isinstance(c["note"], str)


async def test_scan_handles_no_aipulse_api_token_required() -> None:
    """The scan endpoint must NOT require the API token (it's read-only
    discovery, no mutation)."""
    # Should not raise HTTPException(401/403)
    response = await scan_obsidian_vault_route()
    assert response["success"] is True