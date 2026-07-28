"""Clean up macOS Reminders test data created by tests/unit/apple/test_reminders.py.

Deletes the ``AIPulse测试`` Reminders list (and any reminders inside it) that the
Reminders integration test creates on darwin + authorized sandboxes. Mirrors
the AppleScript call style of :mod:`aipulse.apple.reminders`.

Safety contract
---------------
- **Non-darwin**: no-op (returns ``"skipped-non-darwin"``).
- **List not present**: no-op (idempotent — returns ``"not-found"``).
- **AppleScript failure**: logs a warning, **never raises** — cleanup must not
  break test sessions or pollute exit codes.
- **Only touches** the ``AIPulse测试`` list by exact match — never ``学习`` or any
  other user list.

Return values
-------------
``"skipped-non-darwin"`` / ``"not-found"`` / ``"deleted"`` / ``"failed"``

Usage
-----
.. code-block:: bash

    python scripts/clean_reminders.py

.. code-block:: python

    from scripts.clean_reminders import cleanup_reminders_test_data
    await cleanup_reminders_test_data()
"""

from __future__ import annotations

import asyncio
import logging
import platform
import sys

logger = logging.getLogger("clean_reminders")

# Hard-coded by design. Do not parameterize — see safety contract above.
TEST_LIST_NAME = "AIPulse测试"

_OSASCRIPT_TIMEOUT_S = 5.0


def _escape_for_applescript(s: str) -> str:
    """Escape ``\\`` and ``"`` for use inside an AppleScript string literal.

    Local copy of :func:`aipulse.apple.reminders._escape_for_applescript` so this
    script remains importable without the ``aipulse`` package on ``sys.path``
    (see ``pyproject.toml`` ``pythonpath = ["src"]``).
    """
    if not s:
        return ""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _is_darwin() -> bool:
    """Match the platform check in ``aipulse.apple.reminders`` (line 44)."""
    return sys.platform == "darwin" and platform.system() == "Darwin"


def _build_applescript(list_name: str) -> str:
    """Build the AppleScript that deletes the test list and every reminder in it.

    Returns ``"deleted"`` if the list existed and was removed, ``"absent"`` if it
    was already gone — lets callers distinguish the two without extra round-trips.
    """
    list_esc = _escape_for_applescript(list_name)
    return f"""
    tell application "Reminders"
        if (exists list "{list_esc}") then
            set targetList to list "{list_esc}"
            delete every reminder of targetList
            delete targetList
            return "deleted"
        end if
        return "absent"
    end tell
    """


async def cleanup_reminders_test_data() -> str:
    """Delete the AIPulse测试 Reminders list on macOS. Best-effort, never raises.

    Returns a short status string suitable for logging or CLI output.
    """
    if not _is_darwin():
        return "skipped-non-darwin"

    script = _build_applescript(TEST_LIST_NAME)
    try:
        proc = await asyncio.create_subprocess_exec(
            "osascript",
            "-e",
            script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        logger.warning("osascript not found on PATH; skipping Reminders cleanup")
        return "failed"

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=_OSASCRIPT_TIMEOUT_S
        )
    except asyncio.TimeoutError:
        proc.kill()
        logger.warning("osascript timed out after %.1fs; aborting cleanup", _OSASCRIPT_TIMEOUT_S)
        return "failed"

    if proc.returncode != 0:
        err = stderr.decode("utf-8", errors="replace").strip() or stdout.decode(
            "utf-8", errors="replace"
        ).strip()
        logger.warning("osascript failed (rc=%s): %s", proc.returncode, err)
        return "failed"

    raw = stdout.decode("utf-8", errors="replace").strip()
    return "deleted" if raw == "deleted" else "not-found"


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    outcome = asyncio.run(cleanup_reminders_test_data())
    messages = {
        "deleted": f"✅ 已清理 {TEST_LIST_NAME} 列表",
        "not-found": f"ℹ️  {TEST_LIST_NAME} 列表不存在（无需清理）",
        "skipped-non-darwin": f"⏭️  非 macOS，跳过 Reminders 清理",
        "failed": f"⚠️  Reminders 清理失败，详情见上方日志",
    }
    print(messages.get(outcome, outcome))
    # Always exit 0 — cleanup is best-effort; never propagate to caller / CI
    return 0


if __name__ == "__main__":
    raise SystemExit(main())