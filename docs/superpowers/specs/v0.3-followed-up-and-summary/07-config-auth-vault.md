# 07 — 配置 + 鉴权 + Obsidian Vault 扫描

> **来源**：原文档 §9（配置与持久化）
> **上游依赖**：无（横切模块，可与其他模块并行）
> **下游交付物**：
> - `AppSettings` 新增 `kimi_api_key` / `kimi_base_url` / `kimi_model` / `learning_notification_enabled`
> - `security_middleware.py` 改 Bearer 全局校验
> - 前端 `apiFetch` 内部发 `Authorization` 头
> - `DEFAULT_VAULT_CANDIDATES` 自动扫描列表
> - `POST /api/settings/obsidian-vault/scan` 端点
> - `POST /api/settings/obsidian-vault` 端点
> - 前端 `window.showDirectoryPicker()` + `webkitdirectory` 兜底
> - 安全约束（保留掩码 secrets）
>
> **subagent 边界**：本模块是横切模块，所有其他模块的鉴权依赖此。
> **执行模式**：Phase 1 内可与 01 数据模型 + 05 前端 sidebar 并行。

---



### 9.1 新增配置项

| 配置项 | 类型 | 默认值 | 说明 | 决策来源 |
|---|---|---|---|---|
| `learning_notification_enabled` | `bool` | `True` | 全局通知开关 | Q11 |
| `kimi_api_key` | `SecretStr` | `""` | Kimi API key | Q145 |
| `kimi_base_url` | `str` | `https://api.kimi.com/coding/v1` | Kimi endpoint | Q146 |
| `kimi_model` | `str` | `kimi-for-coding` | Kimi 模型名 | Q144 |

### 9.2 复用现有配置（向后兼容）

| Q 锁定 | 复用现有 |
|---|---|
| Q9 Obsidian vault | `obsidian_vault_path` / `obsidian_archive_folder`（**同时新增自动扫描**，详见 §9.4） |
| Q11 通知开关 | `learning_notification_enabled`（新增） |

### 9.3 Authorization Bearer 全局改造（Q130.B）

**最终方案**：全部 AIPulse API 改 `Authorization: Bearer <token>`，包括现有 `/api/hotspots` 等。

**变更范围**：
- 后端 `security_middleware` 彻底改为 Authorization，去掉 `X-AIPulse-Token` 分支
- 前端 `apiFetch` 内部改为发 `Authorization` 头
- 配置项 `aipulse_api_token` **名字不变**（保持向后兼容），仅 header 名称变化
- **未配置 token 时不校验**（本地开发友好，Q135 锁定）

```python
# src/aipulse/web/security_middleware.py
async def verify_auth_header(request: Request) -> bool:
    token = get_settings().aipulse_api_token  # 配置名不变
    if not token:  # 未配置则不校验
        return True
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return False
    return auth_header[len("Bearer "):] == token
```

### 9.4 Obsidian Vault 自动扫描（Q149-Q153）

**最终方案**：自动扫描 macOS 标准路径 + 坚果云路径 + 「选择文件夹」按钮，复用现有 `obsidian_vault_path` 作为后备。

**自动扫描路径**（后端 `DEFAULT_VAULT_CANDIDATES`）：

```python
DEFAULT_VAULT_CANDIDATES = [
    Path.home() / "Documents",                              # ~/Documents
    Path.home() / "Library/Mobile Documents/iCloud~md~obsidian/Documents",  # iCloud Obsidian
    Path.home() / "Nutstore Files",                         # 坚果云
    Path.home() / "坚果云",                                  # 坚果云中文
]
```

**后端实现**（Q151）：
- POST `/api/settings/obsidian-vault/scan`：扫描 `DEFAULT_VAULT_CANDIDATES` + 向上 5 层 CWD，返回候选列表
- POST `/api/settings/obsidian-vault`：前端选择 → 持久化到 .env + 数据库

**前端选择文件夹**（Q152）：
- 主用：`window.showDirectoryPicker()`（Chromium）
- 兜底：`<input type="file" webkitdirectory>`（Safari/Firefox）

**Tauri 集成**：暂不考虑（YAGNI，Q153 锁定）

### 9.5 安全约束

- 后端设置项 UI 回填时保留掩码 secrets（`AppSettings.update()` 已实现）
- 任何密钥、Token、密码走环境变量或系统密钥管理，**禁止硬编码**

---
