"""v0.3 E2E path F — Bearer 鉴权。

Covers spec 09 §5.6 ``TC-E2E-PATH-F-01..06`` via real HTTP layer (httpx +
ASGITransport → FastAPI ``security_middleware`` → ``verify_auth_header``):

  TC-01  配置 token → 受保护端点必须 ``Authorization: Bearer <token>``
  TC-02  无 Authorization header → 401 + ``{"success": false, "error": "Unauthorized"}``
  TC-03  旧 ``X-AIPulse-Token`` header → 401（已废弃）
  TC-04  ``Authorization: Bearer wrong-value`` → 401
  TC-05  清空 token（dev-friendly 默认）→ /api/* 不校验, 全 200
  TC-06  SSE 端点同样鉴权（GET /api/sse/hotspots 无 header → 401）

链路关键点 (与 path E 同款):

- ``aipulse_api_token`` 默认从 ``.env`` 加载; worktree ``.env`` 无
  ``AIPULSE_API_TOKEN`` → settings 默认 ``SecretStr("")`` → middleware
  走 dev-bypass 分支。TC-05 直接验证该默认行为。
- 配置 token 走 ``monkeypatch.setattr`` 直接改 cached settings instance,
  与 ``tests/integration/test_security_middleware_integration.py`` 同款;
  每条测试独立设置, monkeypatch teardown 自动还原 (caches cleared by
  conftest autouse ``_isolate_db_and_settings``)。
- 数据/DB 隔离全靠 conftest autouse: ``DATA_DIR=tmp_path/data``, 引擎
  每次重建, 不碰主 checkout ``data/settings.json``。
- token 用 dummy 值 ``e2e-path-f-token`` (仅在测试模块内出现, 绝不进
  日志/print, 绝不写盘)。

绝对禁止:
- cat / echo / print 真实 ``.env`` / settings.json 内容
- 写主 checkout 任何文件
- 把 token 写到任何持久化层（.env / settings.json / DB）
"""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from httpx import AsyncClient
from pydantic import SecretStr

logger = logging.getLogger(__name__)


# =====================================================================
# MODULE-LEVEL ENVIRONMENT OVERRIDES
# =====================================================================
# 与 path B/C/D/E 同款: 加载 worktree 真 .env (不打印), 强制 minimaxi 模型。
# conftest autouse ``_isolate_db_and_settings`` 会覆盖 LLM 配置;
# 此处调用是 noc-op & idempotent, 与 conftest 兼容。

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

# Force MiniMax per conftest discipline; redundant with conftest autouse but
# guards against ordering changes.
os.environ["LLM_BASE_URL"] = "https://api.minimaxi.com/v1"
os.environ["LLM_MODEL"] = "MiniMax-M2.5"


# =====================================================================
# CONSTANTS
# =====================================================================

# Dummy test-only token. NEVER use the developer's real
# ``aipulse_api_token`` from .env / settings.json — this string is
# hard-coded so the value can only appear inside this test module.
TEST_TOKEN = "e2e-path-f-token"
WRONG_TOKEN = "this-is-not-the-real-token"

VALID_BEARER = {"Authorization": f"Bearer {TEST_TOKEN}"}
WRONG_BEARER = {"Authorization": f"Bearer {WRONG_TOKEN}"}
LEGACY_HEADER = {"X-AIPulse-Token": TEST_TOKEN}  # value matches, header wrong

# Endpoints exercised across the 6 TCs. All mounted under /api/ → middleware
# applies. ``/api/sse/hotspots`` is the spec TC-API-AUTH-05 SSE probe.
ENDPOINTS_NON_SSE = ("/api/hotspots", "/api/sources", "/api/settings")
ENDPOINT_SSE = "/api/sse/hotspots"

EXPECTED_UNAUTH_BODY: dict[str, Any] = {"success": False, "error": "Unauthorized"}


# =====================================================================
# Helper
# =====================================================================


def _set_token(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    """Replace ``cached.aipulse_api_token`` so middleware reads the new value.

    走 ``monkeypatch.setattr`` 而非 ``patch.object``, 是为了让 teardown
    自动还原到原 SecretStr (即 conftest 重建的 SecretStr("")), 避免
    测试间状态泄漏。``value=""`` 表示 dev-friendly 默认（不校验）。
    """
    from aipulse.core.config import get_settings

    cached = get_settings()
    monkeypatch.setattr(cached, "aipulse_api_token", SecretStr(value))


# =====================================================================
# Fixture — print baseline isolation for diagnostics
# =====================================================================


@pytest_asyncio.fixture
async def auth_env(
    tmp_path: Path,
) -> AsyncGenerator[dict[str, Any], None]:
    """诊断用 fixture: 确认 DATA_DIR 隔离 + 默认 token 状态。

    conftest autouse ``_isolate_db_and_settings`` 已 DATA_DIR 切到 tmp_path;
    本 fixture 只读出 ``get_settings().aipulse_api_token`` 默认值给测试
    函数做断言 (确保工作树 .env 不带 AIPULSE_API_TOKEN)。
    """
    from aipulse.core.config import get_settings

    settings = get_settings()
    default_token = settings.aipulse_api_token.get_secret_value()
    data_dir = Path(os.environ["DATA_DIR"])
    yield {
        "tmp_path": tmp_path,
        "data_dir": data_dir,
        "settings_path": data_dir / "settings.json",
        "default_token": default_token,
    }


# =====================================================================
# Tests — TC-E2E-PATH-F-01..06
# =====================================================================


@pytest.mark.e2e
async def test_e2e_path_f_tc01_token_configured_requires_bearer(
    monkeypatch: pytest.MonkeyPatch,
    client: AsyncClient,
    auth_env: dict[str, Any],
) -> None:
    """TC-F-01: 配置 token 后受保护端点必须 ``Authorization: Bearer <token>``.

    链路:
      - 默认状态 (worktree .env 无 AIPULSE_API_TOKEN) → dev-friendly 放行
      - ``_set_token(TEST_TOKEN)`` → middleware 进入 Bearer 校验
      - 三个不同 /api/* 端点同时验证: 无 header = 401, 正确 header = 200
      - TC-F-02 已隐含 (无 header 401), 这里 1 测覆盖 1 态是为了清晰

    断言: 默认 token 必须为空 ("") 才证明本次测试在不污染主 checkout
    配置的前提下能 toggle 鉴权状态。worktree .env 必须保持无 token。
    """
    # Baseline: 默认 token 必须为空 (worktree .env 无 AIPULSE_API_TOKEN).
    assert auth_env["default_token"] == "", (
        f"[TC-F-01] default aipulse_api_token must be empty (worktree .env must NOT "
        f"contain AIPULSE_API_TOKEN), got {auth_env['default_token']!r}"
    )

    # 1. 配置 token → 全部 /api/* 强制 Bearer.
    _set_token(monkeypatch, TEST_TOKEN)

    for endpoint in ENDPOINTS_NON_SSE:
        # (a) 无 header → 401 + 标准 error 字段.
        no_auth = await client.get(endpoint)
        assert no_auth.status_code == 401, (
            f"[TC-F-01] no-auth GET {endpoint} should return 401 (token configured), "
            f"got {no_auth.status_code}: {no_auth.text[:200]}"
        )
        no_auth_body = no_auth.json()
        assert no_auth_body == EXPECTED_UNAUTH_BODY, (
            f"[TC-F-01] 401 body should be {EXPECTED_UNAUTH_BODY}, "
            f"got {no_auth_body}"
        )

        # (b) 正确 Bearer → 200 + success=true.
        with_auth = await client.get(endpoint, headers=VALID_BEARER)
        assert with_auth.status_code == 200, (
            f"[TC-F-01] authed GET {endpoint} should return 200 with valid Bearer, "
            f"got {with_auth.status_code}: {with_auth.text[:200]}"
        )
        with_auth_body = with_auth.json()
        assert with_auth_body.get("success") is True, (
            f"[TC-F-01] authed GET {endpoint} body should have success=True, "
            f"got {with_auth_body}"
        )

    print(
        f"[TC-F-01] token configured → all of {list(ENDPOINTS_NON_SSE)} "
        f"return 401 without Bearer, 200 with Bearer",
        file=sys.stderr,
    )


@pytest.mark.e2e
async def test_e2e_path_f_tc02_missing_authorization_returns_401(
    monkeypatch: pytest.MonkeyPatch, client: AsyncClient
) -> None:
    """TC-F-02: 缺 Authorization header (其它 header 在场) → 401.

    与 TC-F-01 不同: 本测试明确「不是空请求体导致 401」, 而是「真的
    没有 Authorization 头」。附带若干无害 header (User-Agent 等) 验证
    middleware 只看 Authorization 不因其它 header 放行。
    """
    _set_token(monkeypatch, TEST_TOKEN)

    # 含其它常见 header 但无 Authorization → 401.
    noisy_headers = {
        "User-Agent": "tc-f-02-noisy/1.0",
        "Accept": "application/json",
        "X-Forwarded-For": "127.0.0.1",
    }
    resp = await client.get("/api/hotspots", headers=noisy_headers)
    assert resp.status_code == 401, (
        f"[TC-F-02] GET /api/hotspots without Authorization should return 401, "
        f"got {resp.status_code}: {resp.text[:200]}"
    )
    body = resp.json()
    assert body == EXPECTED_UNAUTH_BODY, (
        f"[TC-F-02] 401 body should be {EXPECTED_UNAUTH_BODY}, got {body}"
    )

    # 同时, 同样的请求带正确 Bearer 必须 200 (确保 noisy headers 不会
    # 与 Bearer 同时存在时被误判).
    combined = {**noisy_headers, **VALID_BEARER}
    ok_resp = await client.get("/api/hotspots", headers=combined)
    assert ok_resp.status_code == 200, (
        f"[TC-F-02] GET /api/hotspots with noisy headers + valid Bearer should 200, "
        f"got {ok_resp.status_code}: {ok_resp.text[:200]}"
    )

    print(
        f"[TC-F-02] missing Authorization → 401 ({EXPECTED_UNAUTH_BODY}); "
        f"with noisy headers + valid Bearer → 200",
        file=sys.stderr,
    )


@pytest.mark.e2e
async def test_e2e_path_f_tc03_legacy_x_header_rejected(
    monkeypatch: pytest.MonkeyPatch, client: AsyncClient
) -> None:
    """TC-F-03: 旧 ``X-AIPulse-Token`` header → 401（即使值正确, header 形式废弃）.

    spec 09 §3.6 TC-API-AUTH-03: 已切到 ``Authorization: Bearer <token>``,
    旧 X-AIPulse-Token 不再有效。验证两种语义:
      (a) 单独的 ``X-AIPulse-Token`` → 401 (header 不被 middleware 识别)
      (b) ``X-AIPulse-Token`` + ``Authorization: Bearer wrong`` → 401
          (Authorization 错误才决定, X-AIPulse-Token 被忽略)
      (c) ``X-AIPulse-Token`` + ``Authorization: Bearer correct`` → 200
          (Authorization 正确即放行, X-AIPulse-Token 被忽略, 不因 旧 header 而 fail)
    """
    _set_token(monkeypatch, TEST_TOKEN)

    # (a) 单独 X-AIPulse-Token → 401.
    solo_legacy = await client.get("/api/hotspots", headers=LEGACY_HEADER)
    assert solo_legacy.status_code == 401, (
        f"[TC-F-03] X-AIPulse-Token only should return 401, "
        f"got {solo_legacy.status_code}: {solo_legacy.text[:200]}"
    )
    assert solo_legacy.json() == EXPECTED_UNAUTH_BODY, (
        f"[TC-F-03] X-AIPulse-Token only body should be {EXPECTED_UNAUTH_BODY}, "
        f"got {solo_legacy.json()}"
    )

    # (b) X-AIPulse-Token + 错误 Bearer → 401 (Authorization 错误优先).
    legacy_plus_wrong = {
        "X-AIPulse-Token": TEST_TOKEN,
        **WRONG_BEARER,
    }
    resp_b = await client.get("/api/hotspots", headers=legacy_plus_wrong)
    assert resp_b.status_code == 401, (
        f"[TC-F-03] X-AIPulse-Token + wrong Bearer should return 401 "
        f"(legacy doesn't compensate), got {resp_b.status_code}"
    )

    # (c) X-AIPulse-Token + 正确 Bearer → 200 (Authorization 通过即放行,
    #     legacy header 不被当成 token credential 二次校验).
    legacy_plus_right = {**LEGACY_HEADER, **VALID_BEARER}
    resp_c = await client.get("/api/hotspots", headers=legacy_plus_right)
    assert resp_c.status_code == 200, (
        f"[TC-F-03] X-AIPulse-Token + valid Bearer should return 200 "
        f"(legacy not double-checked), got {resp_c.status_code}: "
        f"{resp_c.text[:200]}"
    )

    print(
        f"[TC-F-03] X-AIPulse-Token is fully deprecated: "
        f"solo→401, +wrong→401, +right→200 (not double-validated)",
        file=sys.stderr,
    )


@pytest.mark.e2e
async def test_e2e_path_f_tc04_wrong_token_value_returns_401(
    monkeypatch: pytest.MonkeyPatch, client: AsyncClient
) -> None:
    """TC-F-04: ``Authorization: Bearer wrong-value`` → 401.

    多种「错误 token 形态」全覆盖, 确保 middleware 的 constant-time/精确
    字符串比较不会被绕过:
      - 完全无关的字符串
      - 空 Bearer value (`Bearer ` 后只有空格)
      - 仅大小写差异
      - 仅尾部空白差异 (`Bearer <correct> `)

    所有形态都必须 401, 且 401 响应体是标准 error 字段。
    """
    _set_token(monkeypatch, TEST_TOKEN)

    malformed_forms = {
        "wrong-literal": WRONG_BEARER,
        "different-suffix": {"Authorization": "Bearer e2e-path-f-toke"},
        "different-prefix": {"Authorization": "Bearer 2e2-path-f-token"},
        "case-mismatch-lowercase": {
            "Authorization": "Bearer E2E-PATH-F-TOKEN"  # 全大写, 与 TEST_TOKEN 区分
        },
        "trailing-space": {"Authorization": f"Bearer {TEST_TOKEN} "},
        "leading-space": {"Authorization": f" Bearer {TEST_TOKEN}"},
        "empty-value": {"Authorization": "Bearer "},
    }

    for label, headers in malformed_forms.items():
        resp = await client.get("/api/hotspots", headers=headers)
        assert resp.status_code == 401, (
            f"[TC-F-04] malformed Bearer form {label!r} should return 401, "
            f"got {resp.status_code}: {resp.text[:200]}"
        )
        assert resp.json() == EXPECTED_UNAUTH_BODY, (
            f"[TC-F-04] malformed Bearer {label!r} body should be "
            f"{EXPECTED_UNAUTH_BODY}, got {resp.json()}"
        )

    # 同样: 错误 token 不能用在任何其它 /api/* 端点.
    other_endpoint = await client.get("/api/sources", headers=WRONG_BEARER)
    assert other_endpoint.status_code == 401, (
        f"[TC-F-04] wrong Bearer on /api/sources should also 401, "
        f"got {other_endpoint.status_code}"
    )

    print(
        f"[TC-F-04] {len(malformed_forms)} malformed Bearer variants all "
        f"→ 401 + standard error envelope",
        file=sys.stderr,
    )


@pytest.mark.e2e
async def test_e2e_path_f_tc05_no_token_dev_bypass(
    monkeypatch: pytest.MonkeyPatch, client: AsyncClient
) -> None:
    """TC-F-05: 清空 token (dev-friendly 默认) → /api/* 不校验, 全 200.

    验证三个维度:
      (a) 默认状态 (worktree .env 无 AIPULSE_API_TOKEN) → 全端点 200
      (b) 显式 ``_set_token(monkeypatch, "")`` (模拟用户在 settings 回空
          token) → 仍全端点 200
      (c) 显式带 Bearer 与不带都 → 200 (空 token 时 Bearer header 也被忽略)

    这是 spec §3.6 TC-API-AUTH-01 的 E2E 对应, 也是 ``aipulse_api_token``
    为空时让本地开发者不用配 token 就能访问 UI 的核心保证。
    """
    # (a) 默认状态 — 不能依赖「.env 不带 token」的事实, 必须显式设置。
    #     防御性: 显式给 cached instance 一次空, 避免任何 test 顺序污染。
    _set_token(monkeypatch, "")

    endpoints_to_check = (
        "/api/hotspots",
        "/api/sources",
        "/api/settings",
        "/api/keywords",
        "/api/digests",
    )

    # (a)(b) 任一被访问都 200, 无 Authorization header。
    for endpoint in endpoints_to_check:
        resp = await client.get(endpoint)
        assert resp.status_code == 200, (
            f"[TC-F-05(a/b)] GET {endpoint} should return 200 with empty token, "
            f"got {resp.status_code}: {resp.text[:200]}"
        )
        body = resp.json()
        assert body.get("success") is True, (
            f"[TC-F-05(a/b)] GET {endpoint} body should have success=True, "
            f"got {body}"
        )

    # (c) 同时, 即使客户端附带 Bearer header (任意值) 也必须 200:
    #     空 token 时 middleware 短路放行, 不读 Authorization。
    with_useless_bearer = {"Authorization": "Bearer absolutely-wrong-token"}
    for endpoint in endpoints_to_check:
        resp = await client.get(endpoint, headers=with_useless_bearer)
        assert resp.status_code == 200, (
            f"[TC-F-05(c)] GET {endpoint} with useless Bearer should still 200 "
            f"when token empty (dev mode bypass), got {resp.status_code}: "
            f"{resp.text[:200]}"
        )

    print(
        f"[TC-F-05] token empty → {len(endpoints_to_check)} endpoints open "
        f"(no header & spurious Bearer both 200)",
        file=sys.stderr,
    )


@pytest.mark.e2e
async def test_e2e_path_f_tc06_sse_endpoint_also_gated(
    monkeypatch: pytest.MonkeyPatch, client: AsyncClient
) -> None:
    """TC-F-06: SSE 端点同样鉴权. ``GET /api/sse/hotspots`` 无 header → 401.

    关键: middleware 在 ``call_next`` 之前 short-circuit 返回 JSONResponse,
    所以 SSE handler 不会触发 stream; middleware 的 401 是 plain JSON, httpx
    + ASGITransport 直接读到 (不会 hang 在 stream 上)。
    """
    _set_token(monkeypatch, TEST_TOKEN)

    # (a) 无 Authorization header → 401 + 标准 error 字段 (与 TC-F-02 同形).
    sse_no_auth = await client.get(ENDPOINT_SSE)
    assert sse_no_auth.status_code == 401, (
        f"[TC-F-06] SSE {ENDPOINT_SSE} without Authorization should 401, "
        f"got {sse_no_auth.status_code}: {sse_no_auth.text[:200]}"
    )
    assert sse_no_auth.json() == EXPECTED_UNAUTH_BODY, (
        f"[TC-F-06] SSE 401 body should be {EXPECTED_UNAUTH_BODY}, "
        f"got {sse_no_auth.json()}"
    )

    # (b) 旧 X-AIPulse-Token 也不被 SSE 端点接受 — 跨端点一致。
    sse_legacy = await client.get(ENDPOINT_SSE, headers=LEGACY_HEADER)
    assert sse_legacy.status_code == 401, (
        f"[TC-F-06] SSE {ENDPOINT_SSE} with X-AIPulse-Token should 401, "
        f"got {sse_legacy.status_code}"
    )

    # (c) 错误 Bearer → 401 (SSE 端点不是特例).
    sse_wrong = await client.get(ENDPOINT_SSE, headers=WRONG_BEARER)
    assert sse_wrong.status_code == 401, (
        f"[TC-F-06] SSE {ENDPOINT_SSE} with wrong Bearer should 401, "
        f"got {sse_wrong.status_code}"
    )

    # (d) 与正面对照: 同样条件, /api/hotspots 也是 401 (证明 gating 跟
    #     endpoint 类型无关, 是 middleware 统一行为). 这是 TC-F-02 的
    #     跨端点证据, 写在此测试里是因为本质是验证「SSE == 普通端点」.
    hotspots_no_auth = await client.get("/api/hotspots")
    assert hotspots_no_auth.status_code == 401, (
        f"[TC-F-06(d)] GET /api/hotspots should also 401 under same condition, "
        f"got {hotspots_no_auth.status_code}"
    )

    # NOTE: 显式不做「valid Bearer → SSE 200」的断言. SSE handler 真实返回
    # StreamingResponse, 在 httpx + ASGITransport 下 stream 会让 client.get
    # 等到 connection close, 给测试增加不可控等待. 「SSE 跟普通端点同
    # middleware 拦截」已由 (a)(c) 与 TC-F-01/02 的 (a/b) 对照证明; 「正确
    # Bearer → middleware 通过 → 路由可达」由 TC-F-01 (b) 端点处已隐含覆盖.

    print(
        f"[TC-F-06] SSE endpoint {ENDPOINT_SSE} gated identically to "
        f"/api/hotspots: no-header/legacy/wrong all 401",
        file=sys.stderr,
    )
