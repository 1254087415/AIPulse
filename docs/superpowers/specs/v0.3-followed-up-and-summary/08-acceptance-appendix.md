# 08 — 验收清单 + 附录（Phase 完成标准）

> **来源**：原文档 §10（验收清单）+ 附录 A-H
> **上游依赖**：全部 Phase 1-7
> **下游交付物**：
> - 功能验收清单（按模块勾选）
> - 性能验收（响应时间 / 资源占用）
> - E2E 验收（6 条用户路径）
> - 测试覆盖要求（≥80%）
> - 实施 Phase 拆分建议
> - 冲突决策记录
>
> **subagent 边界**：本文件为 reviewer-only，所有 Phase 完成后由独立 reviewer subagent 按此清单逐项验证。
> **执行模式**：Phase 8 单独执行（验证环节）。

---


## 10. 验收清单

实施完成后必须验证，分**功能 / 性能 / E2E** 三类独立勾选：

### 10.1 功能验收

#### UP 主管理
- [ ] 添加 UP主 → 自动校验存在性 + backfill 50 条历史视频（Q18+Q19+Q22）
- [ ] 只输入 uid，后端自动拉取昵称/头像（Q10+Q31）
- [ ] 重复 uid → 返回 409 Conflict（Q22）
- [ ] 添加接口 15 秒超时（Q36）
- [ ] 软删除 UP主 可重新添加（Q19+Q104）
- [ ] 超过 20 个 UP主 弹警告（Q16）

#### 定时采集
- [ ] 定时扫描每 `fetch_interval_minutes` 分钟触发，写入 hotspots `pending`（Q15+Q18+Q106）
- [ ] 增量同步：已存在的视频不重复入库（Q4+Q121）
- [ ] UP主详情页显示合集列表（accordion 折叠）+ 最近 20 条视频（Q15+Q21+Q115）
- [ ] 头像磁盘缓存 + URL 变了才更新（Q30+Q37）
- [ ] UP主被封禁 → 记录日志、不停用、UI 卡片小红点（Q32）

#### Agent Pipeline（手动触发）
- [ ] "总结"按钮 5 态切换：未总结 / 请求中 / 成功 / 失败 / 重试（Q13）
- [ ] 总结队列：并发 1 + 上限 20 + 超过返回 429（Q123-Q125）
- [ ] SSE 三态进度推送：黄色排队 / 蓝色进行 / 绿色完成（Q126）
- [ ] 5 分钟硬超时 + 工具级独立超时（Q141）
- [ ] 不自动重试，用户手动重试（Q128+Q142）
- [ ] judge_tech_relevance score < 0.6 → 不写入 Obsidian/DB/Notification（§5.7 规则 1）

#### 三方向存储（Q22）
- [ ] "归档"按钮 → Obsidian 笔记 + DB `learning_events` + Obsidian Tasks + Apple Reminders 同时写入
- [ ] 任一失败不影响其他（Apple Reminders 失败只 warning，整体仍 ok）
- [ ] Obsidian Task 格式：`- [ ] ⏰ {ISO 时间} {topic 截断 30 字}`

#### UI 布局（§6）
- [ ] sidebar 200px 单层平铺 6 项入口，左色条选中态（Q73-Q99）
- [ ] Dashboard 5 个 tab 切换正常（AI 热点 / 关注列表 / 处理记录 / 即将学习 / 失败）（Q6+Q17）
- [ ] 行内按钮按 `decision_status` 显示对应操作（Q14）
- [ ] "在 b 站打开"独立外链按钮与"总结"按钮并排（Q14）
- [ ] 即将学习 tab 显示 `learning_events` 列表，按 `scheduled_at` 排序
- [ ] 失败项入"失败" tab，支持重试 / 跳过（Q12+Q129）
- [ ] 已停用 UP主半透明 + 启用状态徽章（Q33）
- [ ] 添加 UP主 三处反馈齐全（modal 关闭 + toast + 新卡片插入顶部）（Q27）

#### 配置与鉴权
- [ ] Kimi 配置用 `kimi_*` 前缀（kimi_api_key / kimi_base_url / kimi_model），与 llm_* 并存向后兼容（Q145-Q146）
- [ ] LangChain `create_react_agent` + `@tool` 装饰器 + 5min 硬超时（Q137-Q141）
- [ ] B站 API 策略可切换：UAPI + HTML 抓取 + 工厂模式（Q1+Q108）
- [ ] Authorization: Bearer 全局改造，前后端一致（Q130.B）
- [ ] 未配置 token 时不校验（本地开发友好）（Q130.B）
- [ ] Obsidian vault 自动扫描（macOS 标准路径 + 坚果云）+ 用户选择器（Q149-Q153）
- [ ] Obsidian vault 路径持久化到 .env（Q150）
- [ ] secrets 持久化保留掩码值（**UI 回填空值不覆盖原 secrets**）

### 10.2 性能验收

- [ ] UP主详情页首屏渲染 < 500ms（合集列表懒加载 + 视频分页 Q21）
- [ ] 定时扫描单次执行 < 60s（4 个 UP主 + backfill 50 条 × 4 = 200 条热点）
- [ ] Agent pipeline 单次总结 < 300s（含 Kimi 调用 + Obsidian 写入 + DB 写入）
- [ ] SSE 心跳间隔 15s，断连自动清理订阅
- [ ] 头像磁盘缓存命中率 > 95%（同 UP主重复请求不重新下载）
- [ ] 队列 worker 内存占用 < 50MB（视频上下文限长 + markdown 截断到 3000 字判定）
- [ ] /api/summaries POST p95 < 100ms（enqueue 不阻塞）
- [ ] /api/summaries/{video_id}/progress SSE 端到端延迟 < 500ms

### 10.3 E2E 验收（用户可手动跑通）

#### 路径 A：添加 UP 主 → 自动同步
1. 启动 sidecar + frontend + extension
2. 打开 web dashboard，点"来源" → "添加 UP 主" → 输入 `1567748478`
3. ✅ 看到 modal 顶部绿色 toast + 新卡片插入顶部
4. ✅ 卡片头像 + 昵称正确显示
5. ✅ 详情页看到合集列表（折叠）+ 最近 20 条视频
6. 等 30 分钟（或手动触发 scheduler）→ ✅ hotspot 数 +N

#### 路径 B：手动触发总结 → 三方向归档
1. 在 UP主详情页点单个视频的"总结"按钮
2. ✅ 按钮变黄色（排队中）→ 蓝色（生成中）→ 绿色（已完成）
3. ✅ SSE 推送 started → completed 事件
4. ✅ Obsidian vault 出现新笔记 `BVxxxx-标题.md`
5. ✅ DB `summaries` 表新增记录 + `learning_events` 新增记录
6. ✅ Obsidian 笔记末尾追加 `- [ ] ⏰ {+24h} {topic}`
7. ✅ macOS 提醒事项出现对应 reminder

#### 路径 C：失败重试
1. 故意把 Kimi API key 改错 → 点"总结"
2. ✅ 按钮变红色，显示"失败"
3. ✅ "失败" tab 出现对应记录
4. ✅ 改回正确 API key → 点"重试" → ✅ 重新进入队列 → 完成

#### 路径 D：限流
1. 同时点 25 个不同视频的"总结"
2. ✅ 前 20 个返回 202 + queue_position
3. ✅ 后 5 个返回 429 + "队列已满" 提示
4. ✅ worker 完成后 queue 释放 → 新请求可入队

#### 路径 E：Obsidian vault 自动扫描
1. 在 ~/Documents 建一个 Obsidian vault（含 `.obsidian/` 目录）
2. 重启 sidecar
3. ✅ `/api/settings/obsidian-vault/candidates` 返回该路径
4. 在前端点"选择 vault" → ✅ 选另一个目录 → POST 后端持久化
5. ✅ 重启后 .env 中 `OBSIDIAN_VAULT_PATH` 已更新

#### 路径 F：鉴权
1. 配置 `aipulse_api_token=test123` 后重启 sidecar
2. ✅ 带 `Authorization: Bearer test123` → API 正常 200
3. ✅ 不带 Authorization → 401
4. ✅ 带 `X-AIPulse-Token: test123`（旧方式）→ 401（已废弃）
5. 清空 `aipulse_api_token` 重启 → ✅ 不校验（本地开发友好）

### 10.4 测试覆盖

- [ ] 80%+ 测试覆盖率（unit + integration + E2E）
- [ ] §3 数据模型：30 条单元测试通过
- [ ] §4 B站采集：22 条单元测试 + 11 API 集成测试通过
- [ ] §5 Agent Pipeline：23 条测试通过（6 tool + queue + API + 5min timeout）
- [ ] §6 UI：33 条组件测试 + 5 E2E 路径通过
- [ ] 前端 vue-tsc 通过（strict mode）
- [ ] 后端 mypy --strict 通过
- [ ] 前端 eslint 通过
- [ ] 后端 ruff + bandit 通过

---

---

## 附录 A：沿用 7-18 旧 spec 的部分

> 与 7-18 旧 spec 的差异对比详见附录 G。

### A.1 沿用部分

- **DASHBOARD 4 页面拆分**（Q6 修正为 tab）：关注列表 / 处理记录 / 即将学习 / 失败
- **失败重试策略**：❌ 全部不自动重试（Q128+Q142，**与原文不同**——统一改为失败入列 + 用户手动重试）
- **Pipeline 工具集**：fetch_subtitle / summarize / judge / create_obsidian_note / create_learning_event / send_notification
- **学习提醒落 Obsidian Tasks + Apple Reminders**

### A.2 修正差异

| 主题 | 7-18 旧 spec | 今天 spec（v0.3） | 决策理由 |
|---|---|---|---|
| 表名 | `monitored_creators` | `followed_up` | Q2：保留中文表名约定 |
| B站 API | UAPI（uapis.cn） | **双线路 uapi + html** | Q1：策略模式 + 工厂控制 |
| Agent 形态 | 固定步骤 + JSON 决策 | **LangChain ReAct + Tool Calling** | Q4：用户明确锁定 |
| LLM 配置 | Kimi 单独配置 | **复用 `llm_*`** | 项目已有 OpenAICompatibleAdapter |
| Kimi 配置 | 假设有 kimi_* | **复用 llm_*** | YAGNI |
| Summarizer 目录 | `summarizer/`（单数） | **现有 `summarizers/`**（复数） | 项目实际目录就是复数 |
| Backfill | 可选（5/10/0） | **固定 50 + 合集独立表** | Q19：阈值 50 + 详细合集数据 |
| 触发模式 | 全自动 pipeline | **手动触发为主** | Q14：先不上自动调度 |
| 扫描定时 | 全自动扫描 | **B. 扫描定时 + Agent 手动** | Q15：解耦两者 |
| 通知触发 | 全自动 | **半自动 + 设置开关** | Q8 + Q11 |
| 字幕来源 | 仅 AI 字幕 | **AI 字幕优先 + ASR 兜底** | Q10：复用 obsidian-clip-summary |
| Spec 文件 | 单独 spec | **单文件合并** | Q21 |
| 学习提醒存储 | Apple Reminders 为主 | **三方向 DB+Obsidian+Apple** | Q22 |

### A.3 旧 spec 暂未实现的部分（v0.3 延后）

- Apple Reminders 集成（`apple-assistant-eventkit`）
- 飞书卡片消息模板细化
- 失败重试的具体退避时间表

---

## 附录 B：现有复用资产

| 资产 | 路径 | 复用方式 |
|---|---|---|
| `OpenAICompatibleAdapter` | `src/aipulse/summarizers/llm.py` | LangChain 的 `ChatOpenAI(base_url=...)` 复用 |
| `VideoSummarizer` | `src/aipulse/summarizers/video_summarizer.py` | summarize tool 内部调用 |
| `ArticleSummarizer` | `src/aipulse/summarizers/article_summarizer.py` | 未来扩展公众号 / 网页 |
| `ObsidianArchiver` | `src/aipulse/archive/obsidian.py` | create_obsidian_note tool |
| `PushStrategyRegistry` | `src/aipulse/pushers/registry.py` | send_notification tool |
| `BilibiliHotCollector` | `src/aipulse/collectors/bilibili.py` | 范式参考（BaseCollector） |
| `BaseCollector` / `RawItem` / `HotspotCandidate` | `src/aipulse/collectors/base.py` | 新 BilibiliUpCollector 继承 |
| `@register` decorator | `src/aipulse/collectors/registry.py` | collector_strategy 双线路注册 |
| `AppSettings.save()` / `update()` | `src/aipulse/core/config.py` | secrets 持久化保留掩码 |
| `scheduler/client.py` | `src/aipulse/scheduler/client.py` | APScheduler 单 worker 串行调度 |
| `obsidian-clip-summary` skill | `~/.claude/skills/obsidian-clip-summary/` | 字幕提取 + 校验思路 |
| `HotspotDetailView` | `web/src/views/HotspotDetailView.vue` | 复用"归档到 Obsidian"按钮 |

---

## 附录 C：实施 Phase 拆分建议

Phase 1：**基础数据 + UI 框架**
- DB migration：`followed_up` + `followed_up_collections` + `learning_events` + `hotspots` 新字段
- 后端：`POST /api/followed-up` CRUD + 列表接口
- 前端：关注列表 panel + 添加表单
- 验证：能添加 / 暂停 / 删除 UP主

Phase 2：**B站采集**
- 实现 `BilibiliUpUapiCollector` + `BilibiliUpHtmlCollector`
- `BilibiliUpCollectorFactory`
- `POST /api/followed-up/{id}/scan` 手动扫描
- APScheduler 定时任务
- 验证：UP主扫描 → 写入 hotspots（pending）

Phase 3：**Agent Pipeline（手动触发）**
- LangChain 集成：`ChatOpenAI(base_url=kimi)` + 5 个 tool
- `POST /api/agent/process` 手动入口
- 字幕提取 + 校验 + ASR 兜底
- 验证：点"AI 处理" → 字幕/总结/判断写入 hotspot

Phase 4：**归档与通知 + 三方向存储**
- "归档到 Obsidian"按钮 → `POST /api/hotspots/{id}/archive`
- 三方向存储：DB `learning_events` + Obsidian Tasks + Apple Reminders
- "通知"按钮 → `POST /api/hotspots/{id}/notify`
- 验证：归档双笔记 + DB 表 + Apple Reminder 三处同步创建

Phase 5：**失败处理 + 详情页**
- "失败" tab + 重试/跳过/强制决策
- UP主详情页（合集列表 + 视频列表）
- 健康状态徽章
- 验证：所有失败路径 + 详情页交互

Phase 6：**E2E + 验证**
- 真实 B站 UP主端到端测试
- 真实 LLM API 集成测试（2026-07-30 口径回写：实际执行为 MiniMax-M3，非 Kimi）
- 真实 Obsidian 写入测试
- 覆盖率 ≥ 80%

---

## 附录 D：术语

- **UP主**：B站内容创作者
- **合集**：B站 UP主的视频集合（类似播放列表 / 课程系列）
- **Hotspot**：本项目核心数据模型之一，承载 AI 热点 / 订阅更新
- **Agent**：LangChain 编排的 ReAct Agent
- **Tool Calling**：Agent 调用外部工具（字幕 / 总结 / 归档 / 通知等）
- **Backfill**：新增 UP主 时批量加载历史视频
- **Decision Status**：hotspot 的处理状态（pending / worth_learning / skipped / failed）
- **三方向存储**：DB + Obsidian Tasks + Apple Reminders 同时持久化学习提醒（Q22）

---

## 附录 E：冲突决策记录（v0.3-final）

> 整合原 grilling Q1-Q154 + 第二轮 brainstorming Q1-Q22 + 9 个冲突决策后，最终定稿的 9 个冲突点决策。

| # | 严重度 | 主题 | 原 grilling 锁定 | 当前 spec 描述 | **最终决策** | 决策理由 |
|---|---|---|---|---|---|---|
| 1 | HIGH | summarizer 目录 | `src/aipulse/summarizer/`（单数新子包） | 引用 `summarizers/`（复数） | **复数 + agent 子包** | 复用 `summarizers/`，在其下新增 `agent/` `tools/` `prompts/` `obsidian/` 子包 |
| 2 | HIGH | Kimi 配置命名 | `kimi_*` 前缀 | 复用 `llm_*` | **新增 `kimi_*` 前缀** | 与 `llm_*` 并存，向后兼容；用户原话"都叫 kimi 开头" |
| 3 | MEDIUM | B站 API 策略 | 单一 HTML 抓取（Q108） | 双轨 uapi + html | **双轨 uapi + html** | 策略模式 + 工厂，UP 主可独立切换 |
| 4 | MEDIUM | 字段集 | 最小集（Q100-Q107） | 通用化字段 | **通用化字段** | 预留多平台扩展（wechat_mp / douyin） |
| 5 | MEDIUM | Agent 实现 | `create_react_agent` + `@tool` | `create_tool_calling_agent` | **`create_react_agent` + `@tool`** | ReAct 风格 + system prompt 复用 obsidian-clip-summary |
| 6 | MEDIUM | Agent 触发 | 全手动 + 队列上限 20 | 半自动 | **半自动** | fetch_transcript/summarize/judge 自动，obsidian/learning/notification 手动 |
| 7 | MEDIUM | Authorization 改造 | 全部 API 改 Bearer | 未指定 | **全部 API 改 Authorization** | 鉴权架构级统一，前后端一致 |
| 8 | LOW | Obsidian vault | 自动扫描 + 用户选择器 | 复用现有 settings | **自动扫描 + 选择器** | 自动 + 手动并存，复用 settings 作为后备 |
| 9 | LOW | Spec 组织 | 单文件 | 已单文件 | **单文件 + 整合所有内容** | 把 Q1-Q154 + Q1-Q22 + 9 决策全部合入本 spec |

---

## 附录 F：原 grilling Q1-Q154 关键决策汇总（精简版）

> 完整原文见 `/Users/zab/.claude/projects/-Users-zab-Documents-project-AIPulse/grilling-extract-{1a,1b,2,3}.md`

### F.1 主题分组

| 主题 | Q 范围 | 关键决策 |
|---|---|---|
| **数据源与采集策略** | Q1-Q22 | Source 层替换、每视频=1 hotspot、增量同步、HTML 抓取 |
| **UI 布局与交互** | Q40-Q99 | sidebar 200px 单层平铺、左色条选中、4px 圆角、版本号底部 |
| **数据模型** | Q100-Q107 | `followed_up` 表 + 虚拟 Source + `hotspots.deleted_at` + 部分索引 |
| **总结功能队列** | Q116-Q129 | 全局手动 + asyncio.Queue + 队列上限 20 + SSE 三态进度 |
| **鉴权改造** | Q130-Q135 | Authorization: Bearer 全局改造 |
| **Kimi + LangChain** | Q136-Q148 | LangChain ReAct Agent + `@tool` + `kimi-for-coding` + `kimi_*` 命名 |
| **Obsidian vault** | Q149-Q153 | 自动扫描 + 用户选择器 + window.showDirectoryPicker |

### F.2 用户原话引用（重要决策）

| Q | 用户原话 | 锁定结论 |
|---|---|---|
| Q1 | "两个线路都跑，策略模式 + 工厂控制" | 双轨 uapi + html |
| Q2 | "感觉现在设计的字段名不是很通用，重新设计下" | 通用化字段 |
| Q4 | "以当前时间节点作为比较" | 增量同步 |
| Q14 | "不不不，上面一个，先手动触发吧，别跑自动调度先" | 全手动触发 |
| Q22 | "我有是三个方向，数据库，Obsidian Task和mac的提醒事项都想实现！" | 三方向存储 |
| Q116 | "按照 obsidian-clip-summary 中的设计，在构建知识库总结agent！这个是核心设计点" | AIPulse 自建总结 agent |
| Q130 | "整体都是用 Authorization: Bearer" | 全局 Authorization 改造 |
| Q136 | "？？？对接kimi的api就好，用langchain的后端架构去写" | Kimi + LangChain |
| Q144 | "那就2.6也可以" | `kimi-for-coding` 模型 |
| Q145 | "都叫kimi开头配置，不要moonshot" | `kimi_*` 前缀命名 |

### F.3 重大转折点（情绪/方向）

1. **Q99 用户情绪爆发**："还有多少个问题！！！" → 选择 A（继续 grill）
2. **Q116 中断 + 大转弯**：从"复制 URL 到 obsidian-clip-summary"改为"AIPulse 自建总结 agent"
3. **Q123 → Q123.B 修正**：先选 1（多任务并发）后修正为"并发 1 + 队列串行"
4. **Q130 → Q130.B**：从"复用 X-AIPulse-Token"翻案为"全部 Authorization: Bearer"
5. **Q136 推翻**：从 Claude Sonnet 4.6 改为 Kimi + LangChain

---

## 附录 G：与 7-18 旧 spec 的差异

| 主题 | 7-18 旧 spec | v0.3 final | 决策理由 |
|---|---|---|---|
| 表名 | `monitored_creators` | `followed_up` | Q2 |
| B站 API | UAPI 单一 | **双轨 uapi + html** | 冲突 3 |
| Agent 形态 | 固定步骤 + JSON | **LangChain ReAct + @tool** | 冲突 5 |
| LLM | Kimi 单独配置 | **`kimi_*` 前缀** | 冲突 2 |
| Summarizer 目录 | 单数 `summarizer/` | **复数 `summarizers/` + agent 子包** | 冲突 1 |
| Backfill | 可选 5/10/0 | **固定 50 + 合集独立表** | Q19 |
| 触发模式 | 全自动 | **半自动** | 冲突 6 |
| 鉴权 | X-AIPulse-Token | **Authorization: Bearer 全局** | 冲突 7 |
| 字幕来源 | 仅 AI 字幕 | **AI 字幕优先 + ASR 兜底** | Q10 |
| 学习提醒存储 | Apple Reminders 为主 | **三方向 DB + Obsidian + Apple** | Q22 |
| Spec 文件 | 单独 spec | **单文件合并（含 Q1-Q154 + 9 决策）** | 冲突 9 |

---

## 附录 H：实施 Phase 拆分（v0.3 final）

> 实施阶段参考，第二轮 brainstorming + 原 grilling 整合后。

### Phase 1：基础数据 + UI 框架
- DB migration：`followed_up` + `followed_up_collections` + `learning_events` + `hotspots` 新字段
- `AppSettings` 新增 `kimi_*` + `learning_notification_enabled`（Q145-Q146 + Q11）
- Authorization: Bearer 全局改造（Q130.B）
- 后端：`POST /api/followed-up` CRUD + 列表接口
- 前端：sidebar 200px 框架（Q73-Q99） + 关注列表 panel + 添加表单

### Phase 2：B站采集（Q1）
- `BilibiliUpCollectorFactory` + 双轨 `BilibiliUpUapiCollector` + `BilibiliUpHtmlCollector`
- `POST /api/followed-up/{id}/sync` 手动扫描
- APScheduler 定时任务（30 分钟）
- UP主卡片 7 字段（Q114）+ accordion 折叠列表（Q115）

### Phase 3：LangChain Agent + Kimi（Q4 + Q144-Q146）
- `src/aipulse/summarizers/agent/` 下新增 agent / tools / prompts / obsidian
- `kimi-for-coding` + `langchain_openai.ChatOpenAI` + `create_react_agent`
- `@tool` 装饰器 + 6 个工具（fetch_transcript / summarize / judge / create_obsidian_note / create_learning_event / send_notification）
- 半自动模式（Q8）：fetch_transcript / summarize / judge 自动，obsidian/learning/notification 手动

### Phase 4：总结队列 + SSE 进度（Q123-Q129）
- 后端 `asyncio.Queue` + 单 worker（FastAPI lifespan）
- 队列上限 20，超出 429
- SSE 推送三态进度（排队/进行/完成）
- 跳转用 `obsidian://open?path=...` 协议

### Phase 5：Obsidian vault 自动扫描（Q149-Q153）
- `DEFAULT_VAULT_CANDIDATES` + CWD 向上 5 层扫描
- `POST /api/settings/obsidian-vault/scan` + `/api/settings/obsidian-vault`
- 前端 `window.showDirectoryPicker()` + webkitdirectory 兜底

### Phase 6：归档与三方向存储（Q22）
- "归档到 Obsidian" 按钮 → `POST /api/hotspots/{id}/archive`
- 三方向独立 try/except：DB `learning_events` + Obsidian Tasks + Apple Reminders
- "通知"按钮 → `POST /api/hotspots/{id}/notify`

### Phase 7：失败处理 + UP主详情页
- "失败" tab + 重试/跳过/强制决策
- UP主详情页（合集列表 + 视频列表 + accordion 折叠）
- 健康状态徽章（healthy/warning/error）

### Phase 8：E2E + 验证
- 真实 B站 UP主端到端测试
- 真实 LLM API 集成测试（2026-07-30 口径回写：实际执行为 MiniMax-M3，非 Kimi）
- 真实 Obsidian 写入测试
