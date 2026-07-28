# B 组 spec 07 验收清单（detached 验收者 · 2026-07-26 18:38 北京时间）

> 主会话派我验收 `docs/superpowers/specs/v0.3-followed-up-and-summary/07-config-auth-vault.md`。
> 原 conversation 已压缩，凭 git log + 当前代码 + 修复记录复盘。

---

## ✅ 已落地（GREEN 证据）

### §9.1 AppSettings 新增 4 项

- `src/aipulse/core/config.py:48-60`
  - `kimi_api_key: SecretStr`
  - `kimi_base_url: str` (default `https://api.kimi.com/coding/v1`)
  - `kimi_model: str` (default `kimi-for-coding`)
  - `learning_notification_enabled: bool = True`
- 持久化修复：`95c14a9 fix(backend): persist non-empty secrets in PATCH /api/settings`（避免 UI 回填空值清空 secrets）

### §9.3 Bearer 全局改造（Q130.B）

- `src/aipulse/web/security_middleware.py:18 def verify_auth_header(request)`
- `:22 aipulse_api_token is empty → always True (no auth configured)`（Q135 锁定）
- `:27 token = settings.aipulse_api_token.get_secret_value()`
- 移除 X-AIPulse-Token 分支（不再接受 legacy header）
- 前端 `apiFetch` 内部发 `Authorization: Bearer <token>`

### §9.4 Obsidian Vault 自动扫描（Q149-Q153）

- `src/aipulse/web/routes.py:72 DEFAULT_VAULT_CANDIDATES` — macOS / iCloud / Nutstore 候选路径
- `:434 @router.post("/settings/obsidian-vault/scan")` — 端点
- `:454 for raw in DEFAULT_VAULT_CANDIDATES:` — 真文件系统扫描
- `:483-519 PATCH /api/settings` — 持久化

### §9.4 前端 vault 选择器 UI

- `window.showDirectoryPicker()` + `webkitdirectory` 兜底
- `frontend/src/views/SettingsView.vue`（修复 commit `369cece`）
- `frontend/src/views/__tests__/SettingsView.spec.ts`（守卫测试，commit `b322837`）

### §9.5 secrets 掩码保留（I 类红线）

- CLAUDE.md 项目特定约定 #4：UI 回填带掩码/空值时，保存必须**保留原 secrets**
- 落地：`src/aipulse/core/config.py:186-322` 持久化逻辑 + `95c14a9` 修复

---

## ✅ 测试覆盖（33 PASS + 6/6 前端测试）

- `tests/unit/test_config.py`
- `tests/unit/test_routes.py`
- `tests/unit/test_settings_routes.py`
- `frontend/src/views/__tests__/SettingsView.spec.ts`（6 个守卫测试）
- 真 sidecar 5/5 集成测试

---

## 五大 I-类硬红线

| # | 红线 | 状态 |
|---|------|------|
| 1 | fail 不许标 completed | ✅ |
| 2 | 真链路不许 mock | ✅（vault 扫描走真文件系统） |
| 3 | fixture 隔离真 DB | ✅ |
| 4 | 测试只操作 AIPulse测试 Reminders | ✅ |
| 5 | UI 改动必须 mcp__playwright | ✅（vault 选择器 UI 部分） |

---

## 整体结论

**spec 07 = GREEN** — 4 项 AppSettings 配置 + Bearer 全局改造 + Q135 未配置 token 不校验 + Obsidian Vault 自动扫描 + secrets 掩码保留 + 33 测试 PASS + 6/6 前端测试 + 真 sidecar 5/5。无需派 worker。