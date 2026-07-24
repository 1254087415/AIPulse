"""Scheduled job: Obsidian vault scan (spec §E5).

Returns the count of notes scanned; logs warnings if the vault is missing or
contains unreadable files.
"""

from __future__ import annotations

import logging

from aipulse.archive.vault_scanner import scan_vault
from aipulse.core.config import get_settings

logger = logging.getLogger(__name__)


async def scan_obsidian_vault_job() -> int:
    """Walk the Obsidian vault and log a summary of detected notes.

    Returns the number of notes scanned (for tests).
    """
    settings = get_settings()
    vault = settings.obsidian_vault_path
    if not vault.exists() or not vault.is_dir():
        logger.warning(
            "Obsidian vault path missing or not a directory: %s", vault
        )
        return 0
    notes = scan_vault(
        vault,
        archive_folder=settings.obsidian_archive_folder,
        limit=500,
    )
    logger.info(
        "Vault scan finished: %d notes under %s/%s",
        len(notes),
        vault,
        settings.obsidian_archive_folder,
    )
    return len(notes)
