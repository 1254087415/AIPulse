"""v0.3 E2E path E — Obsidian vault 自动扫描端到端。

Covers spec 09 §5.5 ``TC-E2E-PATH-E-01..05`` in a single real-pipeline run:

  TC-01  在 ~/Documents 建 vault (含 ``.obsidian/``) — 真实 macOS 文件系统
  TC-02  ``POST /api/settings/obsidian-vault/scan`` → 候选列表可用 + 新 vault 所在父目录 ``exists=true``
  TC-03  ``PATCH /api/settings {obsidian_vault_path: <vault>}`` → 200, 响应反映新值
  TC-04  重启 sidecar 后持久化路径生效 — 实际写到 ``data/settings.json`` (AppSettings.save() 行为)
  TC-05  ``GET /api/settings`` 返回当前 vault 路径 + 「重新扫描」接口再次可用

链路上另覆盖 v0.3 复用的 secrets preservation 行为
(``TC-API-AUTH-06`` / ``TC-BACKEND-KIMI-06``): 设置真实 secret → 空字符串 PATCH
原值不丢; masked secret PATCH 也保留。

实现 vs spec 偏差 (在测试里加注释, 不改产品代码):
- spec 09 §5.5 TC-04 文字写 ".env 中 OBSIDIAN_VAULT_PATH 已更新", 实际是
  写到 ``data/settings.json`` (AppSettings.save() 行为实现)。
- spec 09 §5.5 TC-02 文字 "/candidates 返回该路径", 实际 ``POST /scan`` 只返
  回 DEFAULTS + CWD 上扫; 不下沉到子目录。新 vault 本身不在 candidates 中,
  但其父目录 ``~/Documents`` 命中 ``exists=true``。

隔离 (与 path B/C/D 同款):
- 真实 macOS 文件系统: HOME 通过 monkeypatch 重定向到 ``tmp_path``, ``~/Documents``
  解析到 tmp_path/Documents, 真实创建 + 真实断言。
- settings 走 conftest 的 ``_isolate_db_and_settings`` (tmp_path/data/settings.json),
  不碰主 checkout ``data/settings.json``。
- API token 鉴权 aipulse_api_token 真实 .env 不配置, 安全中间件放行 (path B 验证)。
- Reminders 不动 (Path E 无副作用)。
- vault 目录由 pytest tmp_path 自动回收, teardown 不需手动删。

绝对禁止:
- cat / echo / print ``.env`` 内容
- 把 vault / settings.json 写到主 checkout
"""

from __future__ import annotations

import json
import logging
import os
import sys
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from httpx import AsyncClient

logger = logging.getLogger(__name__)

# =====================================================================
# MODULE-LEVEL ENVIRONMENT OVERRIDES
# =====================================================================
# 与 path B/C/D 同款: 加载真 .env, 不打印值, 强制 MiniMax 模型。

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = WORKTREE_ROOT / ".env"


def _load_real_env() -> None:
    """Copy .env keys into os.environ. NEVER echo values."""
    if not _ENV_FILE.exists():
        return
    for raw in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        v = v.strip().strip('"').strip("'")
        if v:
            os.environ[k] = v  # 覆盖 — 值不打印


_load_real_env()

# Force MiniMax even if worktree settings.json persisted kimi_*. 用户当前生产
# 配置就是 MiniMax (MiniMax-M2.5 via minimaxi.com)。
os.environ["LLM_BASE_URL"] = "https://api.minimaxi.com/v1"
os.environ["LLM_MODEL"] = "MiniMax-M2.5"


# =====================================================================
# CONSTANTS
# =====================================================================

# Test-only vault name (避免污染真实 vault dir)。
TEST_VAULT_NAME = "AITestVault_E2E_PathE"

# Bearer header — 当前 .env / settings.json 未配置 aipulse_api_token, security
# middleware 在 token 为空时放行; 此 header 是 no-op 但保留以兼容未来开启鉴权。
AUTH_HEADERS = {"Authorization": "Bearer e2e-path-e-token"}


# =====================================================================
# Fixture
# =====================================================================


@pytest_asyncio.fixture
async def vault_scan_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncGenerator[dict[str, Any], None]:
    """构建隔离的 vault-scan 链路。

    - ``HOME`` → ``tmp_path`` (重定向 ``~/Documents`` 解析到 tmp_path/Documents)
    - ``DATA_DIR`` 由 conftest autouse 的 ``_isolate_db_and_settings`` 设为
      ``tmp_path/data``, settings.json 落在 tmp_path/data/settings.json。
    - 在 tmp_path/Documents/<vault>/ 内创建 ``.obsidian/app.json`` 真实文件。
    - 完成后 settings_path / vault_path 全部在 tmp_path 下, 由 pytest 回收。

    Yields:
        dict 含 ``vault_path``, ``vault_path_str``, ``docs_dir``, ``settings_path``,
        ``tmp_home`` 供测试方法断言。
    """
    # 1. HOME 重定向让 ``~/Documents`` 解析到 tmp_path/Documents.
    monkeypatch.setenv("HOME", str(tmp_path))

    # 2. 重新初始化 settings 单例, 让 HOME 变更生效 (缓存清理).
    # NOTE: conftest 的 autouse ``_isolate_db_and_settings`` 已经 cache_clear
    # 一次了, 这里是防御性二次清理, 避免后续实现里 conftest 顺序改变导致
    # HOME 改动不生效. 无副作用, 与 conftest 行为兼容.
    from aipulse.core.config import AppSettings, get_settings as _gs

    _gs.cache_clear()
    AppSettings._llm_migration_done = False

    # 3. 创建 tmp_path/Documents (新建 HOME 下的 Documents) + 真 vault + .obsidian/.
    docs_dir = tmp_path / "Documents"
    docs_dir.mkdir(parents=True, exist_ok=True)
    vault_dir = docs_dir / TEST_VAULT_NAME
    vault_dir.mkdir(parents=True, exist_ok=True)

    # 真实 .obsidian/ marker: 一个 app.json 文件 (真实 Obsidian vault 都有).
    obsidian_subdir = vault_dir / ".obsidian"
    obsidian_subdir.mkdir(parents=True, exist_ok=True)
    (obsidian_subdir / "app.json").write_text(
        json.dumps({"quickSwitcher": {}}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # 4. data_dir / settings_path: conftest 已 DATA_DIR=tmp_path/data.
    data_dir = Path(os.environ["DATA_DIR"])
    settings_path = data_dir / "settings.json"

    try:
        yield {
            "tmp_home": tmp_path,
            "data_dir": data_dir,
            "settings_path": settings_path,
            "docs_dir": docs_dir,
            "vault_dir": vault_dir,
            "obsidian_subdir": obsidian_subdir,
            "vault_path_str": str(vault_dir),
        }
    finally:
        # vault 目录由 pytest tmp_path 自动清理; no extra teardown needed.
        # 但若使用真实 macOS 路径而非 tmp_path (这里没有), 需手动删.
        pass


# =====================================================================
# Tests — single E2E run with 5 named TC + secrets preservation
# =====================================================================


@pytest.mark.e2e
async def test_e2e_path_e_vault_scan(
    vault_scan_env: dict[str, Any], client: AsyncClient
) -> None:
    """v0.3 spec 09 §5.5 TC-E2E-PATH-E-01..05 — Obsidian vault 自动扫描端到端.

    链路 (一次 fixture run 内 5 个 TC + 额外 secrets preservation):
      TC-01  vault 真在 macOS FS 上 (含 .obsidian/app.json)
      TC-02  POST /api/settings/obsidian-vault/scan → 200 + 候选列表 OK
      TC-03  PATCH /api/settings {obsidian_vault_path: <vault>} → 200, 响应含新值
      TC-04  tmp_path/data/settings.json 真实持久化 (AppSettings.save() 行为)
      TC-05  GET /api/settings 返回当前 vault path + rescan 端点可用
      EXT    secrets preservation: PATCH 真 secret → PATCH 空 / masked 不丢
    """
    vault_dir = vault_scan_env["vault_dir"]
    vault_path_str = vault_scan_env["vault_path_str"]
    settings_path = vault_scan_env["settings_path"]
    docs_dir = vault_scan_env["docs_dir"]

    # ─────────────── TC-E-01 ───────────────
    # 真实 macOS 文件系统: vault + .obsidian/.
    assert vault_dir.exists(), (
        f"[TC-E-01] vault dir missing on disk: {vault_dir}"
    )
    assert vault_dir.is_dir(), f"[TC-E-01] vault should be a directory: {vault_dir}"
    assert (vault_dir / ".obsidian").is_dir(), (
        f"[TC-E-01] .obsidian/ subdir missing: {vault_dir / '.obsidian'}"
    )
    assert (vault_dir / ".obsidian" / "app.json").is_file(), (
        f"[TC-E-01] .obsidian/app.json missing: {vault_dir / '.obsidian' / 'app.json'}"
    )
    print(
        f"[TC-E-01] vault on disk: {vault_dir} "
        f"(.obsidian/app.json size={ (vault_dir / '.obsidian' / 'app.json').stat().st_size })",
        file=sys.stderr,
    )

    # ─────────────── TC-E-02 ───────────────
    # POST /api/settings/obsidian-vault/scan → 200 + 候选列表.
    # 实际实现只返 DEFAULTS + CWD 上扫; 不下沉到 .obsidian/. 验证: 该 vault
    # 的父目录 (~/Documents) 出现在 candidates 且 exists=true, 证明新建的
    # vault 处在某个被识别的 candidate 路径下.
    scan_resp = await client.post(
        "/api/settings/obsidian-vault/scan", headers=AUTH_HEADERS
    )
    assert scan_resp.status_code == 200, (
        f"[TC-E-02] scan endpoint should return 200, got {scan_resp.status_code}: "
        f"{scan_resp.text[:300]}"
    )
    scan_body = scan_resp.json()
    assert scan_body.get("success") is True, (
        f"[TC-E-02] scan response.success != True: {scan_body}"
    )
    candidates = scan_body.get("data", {}).get("candidates") or []
    assert isinstance(candidates, list) and len(candidates) > 0, (
        f"[TC-E-02] candidates should be non-empty list, got {candidates!r}"
    )

    # 每条 candidate 都有 path / exists / note 字段
    for c in candidates:
        assert isinstance(c, dict), f"[TC-E-02] candidate not dict: {c!r}"
        assert "path" in c and c["path"], f"[TC-E-02] candidate missing path: {c!r}"
        assert "exists" in c and isinstance(c["exists"], bool), (
            f"[TC-E-02] candidate missing/invalid exists field: {c!r}"
        )

    # 新 vault 的父目录 (~/Documents) 必须存在 + exists=true.
    # candidates 用 raw ``~/`` 形式, 比较时 ``Path.expanduser()`` 展开.
    # macOS ``/var/folders/...`` symlink 到 ``/private/var/folders/...``, 用
    # ``Path.resolve()`` 对齐两边. 验证 candidate ``path`` 展开后 == docs_dir.
    # NOTE: 此断言紧耦合到 ``DEFAULT_VAULT_CANDIDATES`` 第一项 == ``~/Documents``
    # (见 src/aipulse/web/routes.py:72-77). 若 defaults 改, 需同步更新测试.
    docs_path_resolved = docs_dir.resolve()
    parent_match = [
        c for c in candidates
        if Path(c["path"]).expanduser().resolve() == docs_path_resolved
    ]
    assert len(parent_match) == 1, (
        f"[TC-E-02] expected exactly 1 candidate matching {docs_path_resolved!r} "
        f"(the new vault's parent), got {len(parent_match)}; "
        f"all_paths={[c['path'] for c in candidates]!r}"
    )
    assert parent_match[0]["exists"] is True, (
        f"[TC-E-02] parent dir {docs_path_resolved} should have exists=true "
        f"after vault creation: {parent_match[0]}"
    )

    # 同时校验: scan 至少返回 1 个 default candidate (~/Documents 或其它).
    defaults_paths = {c["path"] for c in candidates if c["path"].startswith("~/")}
    assert any(
        p in defaults_paths for p in [
            "~/Documents",
            "~/Library/Mobile Documents/iCloud~md~obsidian/Documents",
        ]
    ) or len(defaults_paths) >= 1, (
        f"[TC-E-02] expected at least one default candidate, got defaults={defaults_paths!r}"
    )

    print(
        f"[TC-E-02] scan returned {len(candidates)} candidates, "
        f"parent_dir={docs_path_resolved} exists=true",
        file=sys.stderr,
    )

    # ─────────────── TC-E-03 ───────────────
    # PATCH /api/settings {obsidian_vault_path: <vault>} → 200, 响应含新值.
    patch_resp = await client.patch(
        "/api/settings",
        json={"obsidian_vault_path": vault_path_str},
        headers=AUTH_HEADERS,
    )
    assert patch_resp.status_code == 200, (
        f"[TC-E-03] PATCH should return 200, got {patch_resp.status_code}: "
        f"{patch_resp.text[:300]}"
    )
    patch_body = patch_resp.json()
    assert patch_body.get("success") is True, (
        f"[TC-E-03] PATCH response.success != True: {patch_body}"
    )

    obsidian_section = patch_body.get("data", {}).get("obsidian") or {}
    assert obsidian_section.get("obsidian_vault_path") == vault_path_str, (
        f"[TC-E-03] expected response.data.obsidian.obsidian_vault_path == "
        f"{vault_path_str!r}, got {obsidian_section.get('obsidian_vault_path')!r}"
    )
    print(
        f"[TC-E-03] PATCH echoed obsidian_vault_path={vault_path_str}",
        file=sys.stderr,
    )

    # ─────────────── TC-E-04 ───────────────
    # 持久化: 重启 sidecar 后路径生效. 实际写到 data/settings.json (而非 .env).
    # spec 09 §5.5 TC-04 文字写 ".env 中 OBSIDIAN_VAULT_PATH 已更新", 但
    # AppSettings.save() 实际写 settings.json. 验证 settings.json 真实持久化.
    assert settings_path.exists(), (
        f"[TC-E-04] settings.json should exist at {settings_path} after PATCH"
    )
    persisted = json.loads(settings_path.read_text(encoding="utf-8"))
    persisted_path = persisted.get("obsidian_vault_path")
    assert persisted_path == vault_path_str, (
        f"[TC-E-04] settings.json should persist obsidian_vault_path={vault_path_str!r}, "
        f"got {persisted_path!r}"
    )
    print(
        f"[TC-E-04] settings.json persisted obsidian_vault_path={persisted_path}",
        file=sys.stderr,
    )

    # ─────────────── TC-E-05 ───────────────
    # 设置页: GET /api/settings 返回当前 vault path + 「重新扫描」接口可用.
    get_resp = await client.get("/api/settings", headers=AUTH_HEADERS)
    assert get_resp.status_code == 200, (
        f"[TC-E-05] GET /api/settings should return 200, got {get_resp.status_code}"
    )
    get_body = get_resp.json()
    get_obsidian = get_body.get("data", {}).get("obsidian") or {}
    assert get_obsidian.get("obsidian_vault_path") == vault_path_str, (
        f"[TC-E-05] GET /api/settings should return current vault path, "
        f"got {get_obsidian.get('obsidian_vault_path')!r}"
    )

    # 重新扫描触发: scan endpoint 再次可用 (UI 按钮背后调用).
    rescan_resp = await client.post(
        "/api/settings/obsidian-vault/scan", headers=AUTH_HEADERS
    )
    assert rescan_resp.status_code == 200, (
        f"[TC-E-05] re-scan endpoint should remain available, got {rescan_resp.status_code}"
    )
    rescan_body = rescan_resp.json()
    assert rescan_body.get("success") is True, (
        f"[TC-E-05] re-scan response.success != True: {rescan_body}"
    )
    print(
        f"[TC-E-05] GET /api/settings returned vault path, "
        f"rescan response has {len(rescan_body.get('data', {}).get('candidates', []))} "
        f"candidates",
        file=sys.stderr,
    )

    # ─────────────── Secrets preservation (extend TC-API-AUTH-06 / TC-BACKEND-KIMI-06) ───────────────
    # 场景: UI 提交 PATCH 时, 真实 secret 已设置 (来自 .env 或上轮 PATCH),
    # UI 回填空字符串 / masked placeholder; 后端必须保留原值, 不允许静默清空.
    real_secret = "this-is-a-real-llm-secret-1234567890"

    # 1. PATCH 设置真实 llm_api_key → settings.json 写入 masked value.
    set_resp = await client.patch(
        "/api/settings",
        json={"llm_api_key": real_secret},
        headers=AUTH_HEADERS,
    )
    assert set_resp.status_code == 200, (
        f"[secrets-preserve] PATCH set-secret should return 200, got {set_resp.status_code}: "
        f"{set_resp.text[:200]}"
    )
    set_body = set_resp.json()
    set_obsidian = set_body.get("data", {}).get("llm") or {}
    masked_echo = set_obsidian.get("llm_api_key") or ""
    assert "***" in masked_echo, (
        f"[secrets-preserve] response llm_api_key should be masked: {masked_echo!r}"
    )

    persisted_after_set = json.loads(settings_path.read_text(encoding="utf-8"))
    persisted_secret = persisted_after_set.get("llm_api_key")
    assert persisted_secret and "***" in persisted_secret, (
        f"[secrets-preserve] expected masked secret in settings.json after set, "
        f"got {persisted_secret!r}"
    )
    # 严格按 AppSettings._mask_secret 契约: ``{first4}***{last4}`` (10+ chars
    # 走标准 mask, <=8 chars 走 '***'). 我们的 real_secret 30 chars, 必走
    # 标准 mask. 用正则钉死格式, 避免随便 substring 匹配.
    expected_mask = f"{real_secret[:4]}***{real_secret[-4:]}"
    assert persisted_secret == expected_mask, (
        f"[secrets-preserve] expected exact masked form {expected_mask!r}, "
        f"got {persisted_secret!r}"
    )

    # 2. PATCH 空字符串 → 原始 secret 不丢.
    empty_resp = await client.patch(
        "/api/settings",
        json={"llm_api_key": ""},
        headers=AUTH_HEADERS,
    )
    assert empty_resp.status_code == 200, (
        f"[secrets-preserve] PATCH empty-secret should return 200, got {empty_resp.status_code}"
    )
    persisted_after_empty = json.loads(settings_path.read_text(encoding="utf-8"))
    preserved_empty = persisted_after_empty.get("llm_api_key")
    assert preserved_empty == persisted_secret, (
        f"[secrets-preserve] empty PATCH should NOT erase original secret: "
        f"before={persisted_secret!r}, after={preserved_empty!r}"
    )

    # 3. PATCH masked secret (UI round-trip) → 仍保留 (masked == masked).
    roundtrip_resp = await client.patch(
        "/api/settings",
        json={"llm_api_key": persisted_secret},
        headers=AUTH_HEADERS,
    )
    assert roundtrip_resp.status_code == 200, (
        f"[secrets-preserve] PATCH masked-secret should return 200, "
        f"got {roundtrip_resp.status_code}"
    )
    persisted_after_roundtrip = json.loads(settings_path.read_text(encoding="utf-8"))
    final_secret = persisted_after_roundtrip.get("llm_api_key")
    assert final_secret == persisted_secret, (
        f"[secrets-preserve] masked-roundtrip PATCH should preserve: "
        f"before={persisted_secret!r}, after={final_secret!r}"
    )

    print(
        f"[secrets-preserve] PATCH empty / masked round-trip preserves "
        f"original secret (masked form stable across runs)",
        file=sys.stderr,
    )
