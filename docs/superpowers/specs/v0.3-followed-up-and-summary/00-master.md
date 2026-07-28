# AIPulse v0.3 关注 UP 主 + AI 知识库总结 — 总览与路由

> **状态**：v0.3-final 整合定稿（grilling Q1-Q154 + 第二轮 Q1-Q22 + 附录 E 全部 9 项决策落定）
> **拆分依据**：模块独立 + subagent 可并行执行
> **拆分目的**：主文件作为路由索引，每个子文件可独立分发给一个 subagent 执行

---

## 0. 文档导航（路由表）

| 子文件 | 内容 | 来源章节 | 可独立 subagent | 依赖 |
|---|---|---|---|---|
| [01-foundation-data-model.md](01-foundation-data-model.md) | 数据模型（4 个表 + ER + migration + Repository + Schema） | §3 | subagent-A（DB） | 无 |
| [02-bilibili-collector.md](02-bilibili-collector.md) | B站双轨采集 + 字幕 + 调度 | §4 | subagent-B（采集） | 依赖 01 |
| [03-langchain-agent.md](03-langchain-agent.md) | LangChain ReAct Agent + Kimi + 6 个 Tool + System Prompt | §5.1-5.8 | subagent-C（Agent） | 依赖 01 |
| [04-summary-queue-api.md](04-summary-queue-api.md) | 总结队列 + SSE 进度 + Summary API | §5.9-5.10 | subagent-D（队列） | 依赖 03 |
| [05-frontend-ui.md](05-frontend-ui.md) | Sidebar + 关注列表 + 详情页 + 三态按钮 + 路由 | §6 | subagent-E（前端） | 依赖 01 |
| [06-notification-failure.md](06-notification-failure.md) | 通知 + 学习提醒三方向存储 + 失败处理 | §7+§8 | subagent-F（通知） | 依赖 04 |
| [07-config-auth-vault.md](07-config-auth-vault.md) | AppSettings 新增 + Bearer 全局改造 + Obsidian vault 扫描 | §9 | subagent-G（配置） | 无（横切） |
| [08-acceptance-appendix.md](08-acceptance-appendix.md) | 验收清单 + 附录 A-H | §10+附录 | reviewer-only | — |

---

## 1. 背景与目标

### 1.1 用户与痛点

- **用户角色**：个人副业使用，兼小型运营/编辑团队
- **关注对象（v0.3 启动基线）**：
  - 跟李沐学 AI（B站 UID `1567748478`）
  - 数字黑魔法（B站 UID `1235535223`）
  - 慢学 AI（B站 UID `28321599`）
  - 阿尔法量化价格行为（B站 UID `437555998`）
- **核心痛点**：
  1. 担心漏看关注的 B站 UP主发布的新内容
  2. 需要判断这些内容是否值得学习并收入知识库
  3. 需要安排学习时间，避免积压

### 1.2 目标

实现一个本地自动化 pipeline：发现指定 B站 UP主新视频 → 提取字幕并总结 → AI 判断是否为技术相关内容 → 自动写入 Obsidian → 自动创建学习提醒 → 发送微信/飞书通知。

### 1.3 非目标（v0.3）

- v0.3 不覆盖微信公众号、小红书、抖音（B站验证后再扩展；表结构预留扩展位）
- v0.3 不上云，仅在 AIPulse 桌面端本地运行
- v0.3 不处理「热榜/排行榜」，只处理指定创作者更新
- v0.3 不做 RAG 知识库判重，仅由 AI 基于内容本身判断是否值得学习
- v0.3 通知走手动触发（先不上 APScheduler 自动调度 Agent）

---

## 2. 执行架构总览

### 2.1 串行依赖图（Phase 顺序）

```
Phase 1 ─→ Phase 2 ─→ Phase 3 ─→ Phase 4 ─→ Phase 5
   │                       │            │
   │                       ↓            ↓
   └─────────────→ Phase 5/6/7（横切或收尾）
                                  ↓
                              Phase 8 E2E
```

| Phase | 模块 | 来源 spec | 关键交付物 |
|---|---|---|---|
| 1 | 基础数据 + UI 框架 | 01 + 05 + 07 | DB 4 表 + sidebar + 关注列表 + Bearer |
| 2 | B站采集 | 02 | 双轨 Collector + sync API + APScheduler |
| 3 | LangChain Agent + Kimi | 03 | Agent + 6 tools + prompts |
| 4 | 总结队列 + SSE | 04 | asyncio.Queue + SSE + Summary API |
| 5 | Obsidian vault 自动扫描 | 07 | 扫描端点 + showDirectoryPicker |
| 6 | 归档与三方向存储 | 06 | 三方向 try/except + notify API |
| 7 | 失败处理 + 详情页 | 06 + 05 | 失败 tab + UP主详情 + 健康徽章 |
| 8 | E2E + TDD 验证 | 08 | 覆盖率 ≥80% + 6 条 E2E 路径 |

### 2.2 并行机会

**Phase 1 内部可并行**：
- subagent-A：DB 模型 + migration（01-foundation-data-model.md）
- subagent-E：前端 sidebar 框架（05-frontend-ui.md，仅依赖 01 的字段名清单）
- subagent-G：Bearer 全局改造 + AppSettings（07-config-auth-vault.md）

**Phase 2 内部可并行**：
- subagent-B1：Collector 双轨实现
- subagent-B2：API 端点 + sync 调度

**Phase 3 内部可并行**：
- subagent-C1：Agent 框架 + ReAct
- subagent-C2：6 个 Tool 实现
- subagent-C3：System Prompt

### 2.3 Phase 间串行硬约束

| 上游 | 下游 | 约束内容 |
|---|---|---|
| Phase 1 | Phase 2 | DB 表 schema + Repository 接口 |
| Phase 1 | Phase 3 | followed_up / hotspots 表 + 字段 |
| Phase 2 | Phase 3 | `summaries` 通过 UP主 → 视频（hotspot）路径 |
| Phase 3 | Phase 4 | Agent 工具调用契约 + JSON 输出格式 |
| Phase 4 | Phase 6 | Summary API 端点 → 归档触发 |
| Phase 5 | Phase 6 | vault 路径解析必须先于 Obsidian 写入 |
| Phase 1~6 | Phase 7 | 失败处理依赖所有上游产物 |
| Phase 1~7 | Phase 8 | E2E 验证 |

---

## 3. 关键决策摘要（来自附录 E）

| 决策 | 选择 | 来源 |
|---|---|---|
| 接口选型 | 双线路 UAPI + HTML（策略模式 + 工厂） | Q1 |
| 数据模型 | 通用化拆分（platform/uid/profile_url 等） | Q2 |
| 检测到视频存储 | `hotspots` 表新增 nullable 字段 | Q3 |
| Agent 形态 | LangChain ReAct + @tool + 半自动 | Q4 |
| Agent 并发 | 单 worker + 队列上限 20 | Q5 |
| UI 入口 | DashboardView 内嵌 tab | Q6 |
| 触发与扫描 | APScheduler 30min + 手动"总结"按钮 | Q7 |
| Agent 边界 | fetch_transcript / summarize / judge 自动，其他手动 | Q8 |
| Obsidian 结构 | 复用 obsidian-clip-summary 笔记结构 | Q9 |
| 字幕来源 | AI 字幕优先 + ASR 兜底 | Q10 |
| 通知触发 | `worth_learning` + `notified=false` | Q11 |
| 失败重试 | 不自动重试 + 失败 tab + 手动重试/跳过 | Q12 |
| Agent 入口 | 手动"总结"按钮 + Summary API | Q13 |
| UI 按钮位置 | UP主卡片 + 视频行内按钮 | Q14 |
| 扫描时机 | APScheduler 定时 + 手动 sync | Q15 |
| UP主上限 | 20 个 + 警告 | Q16 |
| UI 框架 | 沿用 Vue 3 + 现有 Dashboard | Q17 |
| 添加流程 | uid → 后端拉昵称 → 校验 → 入库 + backfill 50 | Q18 |
| 历史 backfill | 50 条 | Q19 |
| UP主详情页 | 合集 accordion + 视频列表 accordion | Q20 |
| Spec 文件组织 | 单文件 + grill 决策汇总 | Q21 |
| 学习提醒存储 | DB + Obsidian Tasks + Apple Reminders 三方向 | Q22 |

---

## 4. 必读：项目特定约定（执行 subagent 前必读）

- 修改 Tauri 窗口尺寸时需同步托盘点击和菜单点击两个入口
- 新增 Python sidecar 必须完整打包 `aipulse` 包，不能只拷贝单个文件
- 浏览器扩展平台适配需要在 `extensions/chromium/src/platform/` 下新增适配器
- 后端设置项 UI 回填时保留掩码 secrets
- 浏览器扩展 E2E 测试陷阱详见 `CLAUDE.md`

---

## 5. 拆分原则说明

**模块独立**：
- 每个子文件对应一个独立子系统（DB / 采集 / Agent / UI / 通知 / 配置）
- 子文件内部包含完整的"为什么 + 怎么做 + 测试 + 验收"
- 子文件之间通过明确的接口契约连接（schema / API / event）

**subagent 可并行**：
- 每个子文件可由一个独立 subagent 在 fresh context 中执行
- 子文件之间无共享可变状态（不同目录、不同 schema 锁版本）
- 串行依赖通过显式的"上游交付物清单"列出

**主文件只做路由**：
- 主文件不重复细节，只提供索引和路由
- 每个 subagent 只需读 1 个子文件 + 主文件的"上游交付物"清单
- 验收清单与决策摘要集中在 08 子文件

---

## 6. 参考文档

- 项目约束：`CLAUDE.md`
- 现有实现：`src-python/src/aipulse/`、`frontend/src/`、`extensions/chromium/`
- 类似 spec 参考：`docs/superpowers/specs/2026-07-09-aipulse-app-redesign-design.md`
- 类似 plan 参考：`docs/superpowers/plans/2026-07-18-creator-monitoring-v1-plan.md`

---

## 7. 完整 grill-me 决策过程（历史）

> 完整的 Q1-Q154 + 第二轮 Q1-Q22 决策过程已在原文档 `2026-07-25-followed-up-and-summary-design.md` §2 保留。subagent 执行时无需重读，仅在决策冲突时回查。