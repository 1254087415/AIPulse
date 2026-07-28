"""Tests for scripts/clean_reminders.py — macOS Reminders test data cleanup.

These tests run on any platform:
- linux:    cleanup must be a no-op (skipped via darwin check).
- darwin:   subprocess is mocked; we assert the AppleScript payload + return-code handling.

The cleanup script must be importable without aipulse.* deps on sys.path; we load it
by absolute file path via importlib.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "clean_reminders.py"


@pytest.fixture
def cleanup_module():
    """Load scripts/clean_reminders.py by absolute path (no sys.path mutation)."""
    spec = importlib.util.spec_from_file_location("clean_reminders", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None, f"cannot load {SCRIPT_PATH}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def force_darwin(monkeypatch):
    """Pretend we are on macOS for the duration of one test."""
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    return monkeypatch


def test_load_succeeds(cleanup_module) -> None:
    """The script must expose the public cleanup entry point."""
    assert hasattr(cleanup_module, "cleanup_reminders_test_data")
    assert callable(cleanup_module.cleanup_reminders_test_data)
    assert hasattr(cleanup_module, "TEST_LIST_NAME")
    assert cleanup_module.TEST_LIST_NAME == "AIPulse测试"


def test_test_list_name_is_hardcoded(cleanup_module) -> None:
    """Safety: cleanup must target a single hard-coded list — no caller override."""
    import inspect

    sig = inspect.signature(cleanup_module.cleanup_reminders_test_data)
    # no positional / kw arguments that would let a caller widen the blast radius
    assert len(sig.parameters) == 0


def test_cleanup_skips_on_linux(cleanup_module, monkeypatch) -> None:
    """Non-darwin → no subprocess, return value signals skipped."""
    import asyncio

    monkeypatch.setattr(sys, "platform", "linux")
    # If subprocess is touched, the test will fail (subprocess will hang on missing osascript).
    outcome = asyncio.run(cleanup_module.cleanup_reminders_test_data())
    assert outcome == "skipped-non-darwin"


def test_cleanup_handles_missing_list(cleanup_module, force_darwin, monkeypatch) -> None:
    """Darwin + osascript success (list absent branch) → 'not-found' outcome, no raise."""
    import asyncio

    class _FakeProc:
        returncode = 0
        async def communicate(self):
            return (b"", b"")

    async def _fake_exec(*args, **kwargs):
        return _FakeProc()

    monkeypatch.setattr(
        "asyncio.create_subprocess_exec", _fake_exec, raising=True
    )

    outcome = asyncio.run(cleanup_module.cleanup_reminders_test_data())
    assert outcome == "not-found"


def test_cleanup_warns_on_applescript_failure(
    cleanup_module, force_darwin, monkeypatch, caplog
) -> None:
    """osascript returns non-zero → log warning, do NOT raise."""
    import asyncio
    import logging

    class _FakeProc:
        returncode = 1

        async def communicate(self):
            return (b"", b"Not authorized to access Reminders")

    async def _fake_exec(*args, **kwargs):
        return _FakeProc()

    monkeypatch.setattr(
        "asyncio.create_subprocess_exec", _fake_exec, raising=True
    )

    with caplog.at_level(logging.WARNING, logger="clean_reminders"):
        outcome = asyncio.run(cleanup_module.cleanup_reminders_test_data())

    assert outcome == "failed"
    assert any("osascript" in rec.message for rec in caplog.records)


def test_cleanup_uses_correct_list_name(
    cleanup_module, force_darwin, monkeypatch
) -> None:
    """The AppleScript must reference the exact ``AIPulse测试`` list."""
    import asyncio

    captured: dict = {}

    class _FakeProc:
        returncode = 0

        async def communicate(self):
            return (b"", b"")

    async def _fake_exec(*args, **kwargs):
        captured["args"] = args
        return _FakeProc()

    monkeypatch.setattr(
        "asyncio.create_subprocess_exec", _fake_exec, raising=True
    )

    asyncio.run(cleanup_module.cleanup_reminders_test_data())

    # osascript -e <script>
    assert captured["args"][0] == "osascript"
    assert captured["args"][1] == "-e"
    script = captured["args"][2]
    assert 'list "AIPulse测试"' in script
    assert "delete every reminder" in script
    assert "delete targetList" in script or "delete list" in script


def test_escape_for_applescript_quotes(cleanup_module) -> None:
    """The local escape helper must handle ``"`` and ``\\`` consistently."""
    esc = cleanup_module._escape_for_applescript
    assert esc('a"b') == 'a\\"b'
    assert esc("a\\b") == "a\\\\b"
    assert esc("") == ""
    assert esc("plain") == "plain"


def test_script_is_importable_via_scripts_package() -> None:
    """scripts/ must be a Python package so fixture can import it via ``scripts.clean_reminders``."""
    import scripts  # noqa: F401 — must exist as a package
    from scripts import clean_reminders  # noqa: F401

    assert callable(clean_reminders.cleanup_reminders_test_data)