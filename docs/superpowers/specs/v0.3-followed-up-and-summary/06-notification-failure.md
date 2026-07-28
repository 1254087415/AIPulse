# 06 — 通知 + 学习提醒三方向存储 + 失败处理

> **来源**：原文档 §7（通知）+ §8（失败处理）
> **上游依赖**：04 Summary API + 07 配置（学习提醒开关）
> **下游交付物**：
> - `learning_events` 表写入逻辑（已在 01 包含 schema）
> - Obsidian Tasks 写入（笔记末尾追加）
> - Apple Reminders 写入（`apple-assistant-eventkit` skill）
> - `PushStrategyRegistry` 触发（已在项目中）
> - 三方向独立 try/except
> - 失败 tab UI + 重试/跳过/强制决策
> - 失败入列逻辑（fetch_transcript / summarize / judge / obsidian / learning / notification）
>
> **subagent 边界**：本模块产出通知触发 + 学习提醒存储 + 失败处理，不产出 UI 组件（在 05）。
> **执行模式**：单独 subagent-F 串行执行。

---



### 7.1 通知（Q11）

- **配置**：`learning_notification_enabled: bool = True`（新增到 `AppSettings`）
- **持久化**：自动经 `AppSettings.save()` 写入 `data/settings.json`
- **触发**：仅当 `decision_status="worth_learning"` AND `notified=false` AND `enabled=true`
- **渠道**：复用 `PushStrategyRegistry`（`src/aipulse/pushers/` 已存在）
- **去重**：触发后置 `notified=true`

### 7.2 学习提醒三方向存储（Q22）

| 方向 | 存储位置 | 用途 |
|---|---|---|
| **数据库** | `learning_events` 表 | Dashboard"即将学习" tab 数据源 |
| **Obsidian Tasks** | 总结笔记末尾 `- [ ] ⏰ {scheduled_at}` | 用户日常查看 / Obsidian 复盘 |
| **Apple Reminders** | 通过 `apple-assistant-eventkit` skill 创建 | macOS 通知中心 / 系统级提醒 |

`learning_events` 表字段（详见 §3.3）：

- `scheduled_at`：默认 20:00 当天（用户可配置）
- `estimated_minutes`：max(15, video_duration × 2)
- `obsidian_task_created`：标记 Obsidian Tasks 是否成功创建
- `apple_reminder_id`：Apple Reminders 创建后回填

Apple Reminders 列表选择：
- `工作学习`：AI / 技术 / 编程 / 面试
- `搞钱！！！`：副业 / 创业 / 变现
- `琐碎生活`：其他

失败处理：三个方向独立 try/except，单方向失败不影响其他
- DB 写入失败 → 不能创建，提示用户重试
- Obsidian Task 失败 → 记录日志，`obsidian_task_created=false`，稍后重试
- Apple Reminders 失败 → 同上

---

## 8. 失败处理（Q12 + Q128 + Q142）

**核心原则**：不自动重试（Q128），不自动回滚（Q142），所有失败入"失败"tab，用户手动重试/跳过。

| 失败步骤 | 自动重试 | 失败入列 | 手动操作 |
|---|---|---|---|
| `fetch_transcript` | ❌ | ✅ | 重试 / 跳过 / 手动上传 |
| `summarize` | ❌ | ✅ | 重试 / 跳过 |
| `judge_tech_relevance` | ❌ | ✅ | 重试 / 强制标 worth_learning / 强制标 skipped |
| `create_obsidian_note` | ❌ | ✅ | 重试 / 换 vault 路径 |
| `create_learning_event` | ❌ | ✅ | 重试 |
| `send_notification` | ❌ | ✅ | 重试 / 跳过 |

> **注意**：本节与 §5/§10 一致，**全部不自动重试**。fetch_transcript / summarize 失败时只记 partial 状态。

| 失败步骤 | 自动重试 | 失败入列 | 手动操作 |
|---|---|---|---|
| `fetch_transcript` | ✅ 指数退避 3 次 | ✅ | 重试 / 跳过 / 手动上传 |
| `summarize` | ✅ 指数退避 3 次 | ✅ | 重试 / 跳过 |
| `judge_tech_relevance` | ❌ | ✅ | 重试 / 强制标 worth_learning / 强制标 skipped |
| `create_obsidian_note` | ❌ | ✅ | 重试 / 换 vault 路径 |
| `create_learning_event` | ❌ | ✅ | 重试 |
| `send_notification` | ❌ | ✅ | 重试 / 跳过 |

---
