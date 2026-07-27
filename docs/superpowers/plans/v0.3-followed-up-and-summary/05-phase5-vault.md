# Phase 5 — Obsidian Vault 自动扫描 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `run_skill(name="subagent-driven-development")` 或 `run_skill(name="executing-plans")` 来实施本计划。
>
> **对应 spec**: [`../../specs/v0.3-followed-up-and-summary/07-config-auth-vault.md`](../../specs/v0.3-followed-up-and-summary/07-config-auth-vault.md) §9.4
> **上游依赖**: Phase 1 (AppSettings + Bearer)

**Goal:** 实施 Obsidian vault 自动扫描（macOS 标准路径 + 坚果云）+ 前端 showDirectoryPicker。

**Architecture:**
- 后端 `DEFAULT_VAULT_CANDIDATES` 常量
- `POST /api/settings/obsidian-vault/scan` 端点
- CWD 向上 5 层扫描
- 前端 `window.showDirectoryPicker()` + `webkitdirectory` 兜底

**Tech Stack:** Python 3.11+ pathlib / Vue 3 File System Access API

---

## 文件结构

- Modify: `src/aipulse/api/settings.py` — 新增 scan 端点
- Create: `src/aipulse/services/obsidian_scanner.py`
- Create: `tests/unit/test_obsidian_scanner.py`
- Create: `tests/integration/test_obsidian_vault_scan_api.py`
- Modify: `frontend/src/views/DashboardSettings.vue` — vault 选择 UI
- Create: `frontend/src/api/obsidianVault.ts`
- Create: `frontend/tests/unit/obsidian-vault-picker.test.ts`

---

## Task 1: DEFAULT_VAULT_CANDIDATES + scanner（subagent-G2）

**Files:**
- Create: `src/aipulse/services/obsidian_scanner.py`
- Test: `tests/unit/test_obsidian_scanner.py`

- [ ] **Step 1: 写失败测试** — scanner：
  - `DEFAULT_VAULT_CANDIDATES` 4 个标准路径
  - `scan_candidates() -> list[VaultCandidate]` 扫描并返回
  - CWD 向上 5 层扫描
  - 候选必须有 `.obsidian` 目录才视为 vault
- [ ] **Step 2: 运行 RED**
- [ ] **Step 3: 最小实现**
- [ ] **Step 4: 运行 GREEN**
- [ ] **Step 5: Commit**

## Task 2: scan API 端点（subagent-G2）

**Files:**
- Modify: `src/aipulse/api/settings.py`
- Test: `tests/integration/test_obsidian_vault_scan_api.py`

- [ ] **Step 1: 写失败测试** — `POST /api/settings/obsidian-vault/scan`：
  - 返回候选列表
  - Bearer 鉴权
- [ ] **Step 2: 运行 RED**
- [ ] **Step 3: 最小实现**
- [ ] **Step 4: 运行 GREEN**
- [ ] **Step 5: Commit**

## Task 3: 选择 vault 端点（subagent-G2）

**Files:**
- Modify: `src/aipulse/api/settings.py`

- [ ] **Step 1: 写失败测试** — `POST /api/settings/obsidian-vault`：
  - 持久化到 .env + 数据库
  - 保留掩码 secrets
- [ ] **Step 2: 运行 RED**
- [ ] **Step 3: 最小实现**
- [ ] **Step 4: 运行 GREEN**
- [ ] **Step 5: Commit**

## Task 4: 前端 showDirectoryPicker（subagent-G2 前端）

**Files:**
- Modify: `frontend/src/views/DashboardSettings.vue`
- Create: `frontend/src/api/obsidianVault.ts`
- Test: `frontend/tests/unit/obsidian-vault-picker.test.ts`

- [ ] **Step 1: 写失败测试** — 前端：
  - 主用 `window.showDirectoryPicker()`（Chromium）
  - 兜底 `<input type="file" webkitdirectory>`（Safari/Firefox）
  - 选择后调用 `POST /api/settings/obsidian-vault`
- [ ] **Step 2: 运行 RED**
- [ ] **Step 3: 最小实现**
- [ ] **Step 4: 运行 GREEN**
- [ ] **Step 5: Commit**

## Task 5: Phase 5 完整验证

- [ ] **Step 1: 单元测试 + 集成测试**
- [ ] **Step 2: 真实 macOS 路径测试** — `/Users/zab/Documents` 等
- [ ] **Step 3: 独立验证 subagent**
- [ ] **Step 4: 未通过则返工**

---

## 自审

- 自动扫描覆盖 macOS 标准 + 坚果云 + CWD 向上 5 层
- 前端 File System Access API + webkitdirectory 兜底
- 真实集成测试：必须在 macOS 路径下运行