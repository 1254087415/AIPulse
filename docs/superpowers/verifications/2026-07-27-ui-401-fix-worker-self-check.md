# Round 3 UI 401 修复 — Worker 自检

## 基线与范围

- 分支：`fix/extension-real-e2e-ui-auth`
- 指定基线：`feat/extension-real-e2e @ 1e2495c`
- 修复范围：新版 `frontend/` 六个主导航页面的认证启动、AI 热点真实数据面板、认证回归测试
- 未修改：`.env`、`.env.example`、`data/settings.json`、真实数据库、真实 secrets

## 根因

后端在 `AIPULSE_API_TOKEN` 非空时要求所有 `/api/*` 请求携带 Bearer token。新版前端的 `apiFetch` 已正确构造 `Authorization: Bearer <token>`，但 token 只从 `localStorage` 读取；首次打开 UI 时 storage 为空，而 `/api/settings` 本身也受鉴权保护，因此形成认证启动死锁，六个数据页面全部返回 401。

此外，Dashboard 的 AI 热点面板仍是 Phase 占位组件，没有请求真实 `/api/hotspots`。

## 修复

1. `frontend/vite.config.ts` 从项目根环境读取与 loopback FastAPI 相同的 `AIPULSE_API_TOKEN`，仅把该变量加入前端 env allowlist。
2. `frontend/src/lib/settings-store.ts` 以 localStorage 用户值优先、环境 token 兜底。
3. `SettingsView.vue` 成功保存新的非空 API token 后同步 localStorage；空值和掩码仍遵守现有 secret 保留约束。
4. `DashboardHotspotPanel.vue` 请求真实 `/api/hotspots`，展示 loading / error / empty / list 状态，不再渲染 Phase 占位文案。

## TDD 证据

### RED

- `settings-store.test.ts`：环境 token 兜底期望失败，实际得到空字符串。
- `settings-view-http.test.ts`：新 token 保存后同步 localStorage 期望失败，mock 调用次数为 0。
- `dashboard-hotspot-panel.test.ts`：期望调用 `/api/hotspots` 失败，实际调用次数为 0。
- 后端基线测试确认：配置 token 时，不带 Bearer 请求 `/api/sources` 返回 401。

### GREEN

- 上述三个前端回归测试全部通过。
- 后端认证集成测试 6/6 通过。

## 真实 E2E

由于用户已有进程占用 5173/8000，本轮未停止或覆盖这些进程；使用隔离端口 15173/18000、临时 SQLite 和 fake token `round3-test-token` 启动真实 Vite + FastAPI。没有 mock API，也没有读取或修改真实 secrets/DB。

六页请求均携带 Bearer 并返回 200：

- `/dashboard` → `GET /api/hotspots?...` → 200
- `/sources` → `GET /api/sources` → 200，展示 9 个后端 seed 来源
- `/keywords` → `GET /api/keywords` → 200
- `/jobs` → `GET /api/scheduler/jobs` → 200，展示真实 APScheduler jobs
- `/digests` → `GET /api/digests` → 200
- `/settings` → `GET /api/settings` → 200

Console：0 个 401，0 个 error；只有 Vite 连接 debug 日志。

截图：

- `/tmp/aipulse-round3-frontend-e2e/dashboard.png`
- `/tmp/aipulse-round3-frontend-e2e/sources.png`
- `/tmp/aipulse-round3-frontend-e2e/keywords.png`
- `/tmp/aipulse-round3-frontend-e2e/jobs.png`
- `/tmp/aipulse-round3-frontend-e2e/digests.png`
- `/tmp/aipulse-round3-frontend-e2e/settings.png`

## 最终验证

- Frontend Vitest：25 files，175 tests passed
- Pytest：673 passed，2 skipped，coverage 86.97%
- `vue-tsc -b && vite build`：通过
- `ruff check tests/integration/test_security_middleware_integration.py`：通过
- `git diff --check`：通过
- 全仓 Ruff 仍有本基线已有的历史告警；本次改动 Python 文件无 Ruff 问题
- 独立代码 / Vue / 安全复核：无 CRITICAL/HIGH 共识阻塞项
