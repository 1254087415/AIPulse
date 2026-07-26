"""Spec E6 follow-up: secrets must be masked when persisted to disk.

The contract:
  * Saving AppSettings writes ``data/settings.json`` with secret fields
    masked (first4***last4 / *** for short secrets).
  * Non-secret fields are written verbatim.
  * The in-memory AppSettings keeps the real secret values; only the
    on-disk representation is masked.

This is independent from ``to_public_dict`` (which masks for the API
response). Both must use the same mask so a developer debugging the JSON
sees a value consistent with what the UI renders.
"""

from __future__ import annotations

import json
from pathlib import Path

from aipulse.core.config import AppSettings


def _build(tmp_path: Path) -> AppSettings:
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return AppSettings(
        data_dir=data_dir,
        download_dir=data_dir / "downloads",
        KIMI_API_KEY="sk-kimi-TsxKEwaG4OKQFffbiXQtYKWUTutLbFtKlfaulZVEMFyI64fvcUiM2cQnkQVB49VK",
        KIMI_BASE_URL="https://api.kimi.com/coding/v1",
        KIMI_MODEL="kimi-for-coding",
        wechat_appsecret="wechat-secret-aaaaaaaaaaaaaa",
        feishu_secret="feishu-secret-bbbbbbbbbbbbbb",
    )


def test_save_masks_kimi_api_key_on_disk(tmp_path: Path) -> None:
    settings = _build(tmp_path)
    settings.save()

    on_disk = json.loads(settings.settings_path.read_text(encoding="utf-8"))
    raw = on_disk["kimi_api_key"]
    # Mask: first4***last4
    assert raw.startswith("sk-k")
    assert raw.endswith("49VK")
    assert "***" in raw
    # Full real value must NOT appear on disk.
    full_real = "sk-kimi-TsxKEwaG4OKQFffbiXQtYKWUTutLbFtKlfaulZVEMFyI64fvcUiM2cQnkQVB49VK"
    assert full_real not in settings.settings_path.read_text(encoding="utf-8")


def test_save_masks_short_secret_with_three_stars(tmp_path: Path) -> None:
    settings = _build(tmp_path)
    # wechat_appsecret length > 8 → first4***last4 (16 chars => "wech***aaaa")
    # Force a short secret to exercise the "***" branch (length <= 8).
    settings.update(wechat_appsecret="short")
    settings.save()

    on_disk = json.loads(settings.settings_path.read_text(encoding="utf-8"))
    assert on_disk["wechat_appsecret"] == "***"


def test_save_masks_feishu_secret(tmp_path: Path) -> None:
    settings = _build(tmp_path)
    settings.save()

    on_disk = json.loads(settings.settings_path.read_text(encoding="utf-8"))
    raw = on_disk["feishu_secret"]
    assert raw != "feishu-secret-bbbbbbbbbbbbbb"
    assert "***" in raw


def test_save_keeps_real_secret_in_memory(tmp_path: Path) -> None:
    """The mask is for the on-disk file only; the in-memory instance must
    still hold the real value so subsequent API calls work."""
    settings = _build(tmp_path)
    settings.save()

    # The in-memory secret is still the real value (no data loss).
    assert (
        settings.kimi_api_key.get_secret_value()
        == "sk-kimi-TsxKEwaG4OKQFffbiXQtYKWUTutLbFtKlfaulZVEMFyI64fvcUiM2cQnkQVB49VK"
    )


def test_save_does_not_mask_non_secret_fields(tmp_path: Path) -> None:
    settings = _build(tmp_path)
    settings.save()

    on_disk = json.loads(settings.settings_path.read_text(encoding="utf-8"))
    assert on_disk["kimi_base_url"] == "https://api.kimi.com/coding/v1"
    assert on_disk["kimi_model"] == "kimi-for-coding"