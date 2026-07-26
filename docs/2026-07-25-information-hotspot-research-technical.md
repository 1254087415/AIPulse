# AIPulse 资讯获取与热点发现技术调研文档

> 版本：v0.1
> 日期：2026-07-25
> 状态：调研结论
> 关联需求：`docs/2026-07-25-information-hotspot-research-requirements.md`

## 1. 技术结论

AIPulse 不应把 NewsNow 或 TrendRadar 作为运行时核心依赖，也不应把两个项目拼接成新的独立服务。推荐方案是：

- 在现有 Python sidecar 内继续使用 `BaseCollector` + Registry；
- 把 NewsNow 的“源适配器、分源刷新间隔、两级缓存、旧缓存降级”转化为 AIPulse 的采集层规范；
- 把 TrendRadar 的“排名历史、频次/排名热度、关键词分层、时段任务、报告模式”转化为 AIPulse 自有领域模型；
- 继续使用现有 FastAPI、SQLite/SQLAlchemy、APScheduler、SSE、LLM 分析和 Obsidian pipeline；
- 对 NewsNow 采用 MIT 允许的参考范围，但优先重新实现以匹配 Python sidecar；对 TrendRadar 仅参考公开设计和数学模型，不复制 GPL-3.0 源码。

## 2. 事实依据与可信度

### 2.1 NewsNow

核验仓库：`https://github.com/ourongxing/newsnow`

- NewsNow 的仓库元数据显示许可证为 MIT，主语言为 TypeScript；其前端实际采用 Vue 3，服务端采用 Nuxt 3/Nitro 相关结构，顶层包含 `server/`、`src/`、`shared/`。
- `server/sources/*.ts` 采用每源适配器；项目支持 HTML/API/RSS 等不同源类型。
- 其缓存实现按来源更新时间和来源刷新间隔判断是否复用，并在抓取失败时返回旧缓存。
- 其条目 ID 在不同源间并不统一，标题 ID 与 URL/平台 ID 并存，因此不能直接当作 AIPulse 的跨源去重方案。

### 2.2 TrendRadar

核验仓库：`https://github.com/sansan0/TrendRadar`

- GitHub 元数据显示许可证为 GPL-3.0，主代码在 `trendradar/`，另有 `mcp_server/`、`docker/`、`config/`。
- `trendradar/crawler/fetcher.py` 默认配置了一个 NewsNow API 地址；该地址是部署配置，不应视为 NewsNow 官方 API，AIPulse 不依赖该第三方地址。RSS 由独立模块解析。
- `trendradar/core/analyzer.py` 使用排名、出现频次和高排名比例组合热度；排名历史存储支持趋势展示。
- `trendradar/core/scheduler.py` 将 collect、analyze、push 和报告模式按时间段编排。
- `trendradar/notification/` 把统一消息分发到多个渠道；这些结构仅作为接口设计参考。

### 2.3 AIPulse 当前事实

- `src/aipulse/collectors/base.py:33-56` 定义 `fetch()` 和 `normalize()` 契约；`src/aipulse/collectors/registry.py:8-11` 负责注册。
- `src/aipulse/hotspot/models.py:35-150` 已有 Source、Hotspot、Keyword、DailyDigest 模型。
- `src/aipulse/hotspot/service.py:41-84` 已具备候选处理主链路，包含 URL 去重、LLM 分析、热度计算、入库和 SSE。
- `src/aipulse/hotspot/processor.py:67-92` 已包含来源、互动、关键词、多源、新鲜度和质量等评分维度，但关键词调用链仍需真实接入。
- `src/aipulse/scheduler/jobs/hotspot_sync.py:16-87` 已按 Source 隔离失败；`src/aipulse/server.py:76-93` 配置 30 分钟同步与每日 08:00 日报。
- `src/aipulse/web/routes.py` 已覆盖热点、关键词、来源、日报和 SSE API；前端热点消费界面仍需按当前产品范围确认和补齐。

## 3. 推荐系统架构

```text
┌─────────────────────────────────────────────────────────────┐
│ Web Dashboard / Tauri / Chromium Extension                  │
└───────────────────────┬─────────────────────────────────────┘
                        │ REST + SSE + content submit
┌───────────────────────▼─────────────────────────────────────┐
│ FastAPI API                                                 │
│ hotspots / sources / keywords / digests / sse               │
└───────────────────────┬─────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────┐
│ Hotspot Service                                             │
│ normalize → validate → deduplicate → keyword match          │
│ → rule/LLM analysis → score → persist → event               │
└───────────────┬─────────────────────────────┬───────────────┘
                │                             │
┌───────────────▼───────────────┐ ┌───────────▼───────────────┐
│ Collector Layer               │ │ Analysis / Delivery       │
│ Registry + per-source fetch  │ │ heat / trend / digest     │
│ RSS/API/HTML/extension       │ │ summary / pusher / vault  │
└───────────────┬───────────────┘ └───────────┬───────────────┘
                │                             │
┌───────────────▼─────────────────────────────▼───────────────┐
│ SQLite + SQLAlchemy                                          │
│ sources / source_cache / hotspots / keyword_matches          │
│ hotspot_occurrences / digests / scheduler_job_log            │
└─────────────────────────────────────────────────────────────┘
```

### 3.1 边界原则

- Collector 只负责获取和规范化，不直接调用 LLM、不发送通知。
- Hotspot Service 负责确定性处理和事务边界；LLM 是可选增强，不得成为采集成功的前置条件。
- Scheduler 只负责触发 Source 同步、分析和日报，不复制业务规则。
- Pusher 只接收统一消息模型，不了解 Collector 细节。
- Extension 通过通用内容提交接口进入同一 Hotspot Service，不建立第二套热点存储。

## 4. 数据模型建议

### 4.1 保留并补强 Source

现有 Source 字段（以当前代码为准）：

```text
id
name
source_type
collector_class
config
default_weight
fetch_interval_minutes
is_active
last_fetched_at
failed_at
last_error
```

以下字段不是当前 Source 模型的既有字段，属于 Phase 1 计划新增或由 API 层计算：

```text
max_age_hours          # Phase 1 计划新增：条目最大有效年龄
max_items_per_fetch    # Phase 1 计划新增：单次最多接收条目
is_builtin             # Phase 1 计划新增：内置源标记
health_status          # Phase 1 计划新增或由 API 计算：healthy / degraded / disabled
consecutive_failures   # Phase 1 计划新增或由日志聚合
config_version         # 后续按配置迁移需要新增
```

`config` 仅存非敏感配置；密钥、Cookie 和 Token 采用 SecretStr/统一 secret key，不通过公开 API 返回。

### 4.2 统一候选结构

```python
@dataclass(frozen=True)
class HotspotCandidate:
    title: str
    url: str | None
    canonical_url: str | None
    source_id: str
    published_at: datetime | None
    rank: int | None
    summary: str | None
    author: str | None
    interactions: Mapping[str, float]
    raw_id: str | None
    metadata: Mapping[str, str]
```

规范化要求：

1. URL 仅接受 `http`/`https`，拒绝 `javascript:`、`data:` 等 scheme；
2. canonicalization 只去除已知 tracking 参数，不改变有效路径和查询参数；
3. title 为空或 URL/平台 ID 不可用时，候选进入可观测丢弃计数；
4. `raw_id` 只用于同一来源内幂等，不作为跨来源全局 ID。

### 4.3 Hotspot 与跨源出现（Phase 2 计划新增）

现有 Hotspot 继续作为用户可消费实体。为支持 TrendRadar 式历史和多源聚合，Phase 2 建议新增独立的出现记录，而不是反复覆盖 Hotspot：

```text
hotspot_occurrences
- id
- hotspot_id
- source_id
- observed_at
- rank
- source_score
- raw_title
- raw_url
- interaction_snapshot JSON
```

后续可新增：

```text
hotspot.keyword_matches JSON
hotspot.cluster_id
hotspot.first_seen_at
hotspot.last_seen_at
hotspot.analysis_status
hotspot.analysis_confidence
```

第一阶段可以只写 occurrence 和关键词命中 JSON，第二阶段再引入语义聚类。

### 4.4 缓存模型（Phase 1 计划新增）

当前代码已有 Source 的抓取时间和错误字段，但尚未建立独立 `source_cache` 表。建议 Phase 1 为每个来源建立缓存元数据：

```text
source_cache
- source_id PRIMARY KEY
- fetched_at
- expires_at
- data JSON / compressed payload
- item_count
- fetch_status
- error_message
```

缓存策略：

```text
请求同步
  ├─ now < source.next_refresh_at → 返回有效缓存
  ├─ 缓存过期但 now < hard_expiry → 尝试抓取
  ├─ 抓取成功 → 原子替换缓存并更新状态
  └─ 抓取失败且有旧缓存 → 返回旧缓存 + degraded 状态
```

对持久化热点而言，缓存不是事实来源；它只是避免重复请求和支持降级的中间层。

## 5. 采集层设计

### 5.1 Collector 分类

| 类型 | 示例 | 处理方式 |
|---|---|---|
| RSS/Atom | 机器之心、用户自定义 RSS | feed parser，按发布时间过滤 |
| 官方 API | arXiv、GitHub、Bilibili 等 | httpx，结构化 JSON 校验 |
| 公开榜单 API | 可合规的热榜接口 | 记录 rank 和快照 |
| HTML 页面 | 仅在公开条款允许时使用 | 受限频率，解析器独立隔离 |
| Extension submit | 用户主动提交的页面 | 视为低频人工来源，不主动抓站 |

### 5.2 统一请求策略

每个 Collector 应使用项目统一 HTTP 客户端或其明确封装，至少具备：

- 总超时和连接超时；
- 有限重试，仅对连接错误、429、5xx 等可重试情况生效；
- 指数退避并设置上限；
- User-Agent 和请求来源可审计；
- 不把登录 Cookie 写入日志；
- 对响应 JSON/RSS 结构做边界校验；
- 记录请求耗时、条目数、状态码和失败原因。

不建议第一阶段引入代理池或浏览器自动化。需要登录态的平台应默认禁用，除非用户明确配置且合规边界已确认。

### 5.3 调度

沿用 APScheduler，但把全局 30 分钟改为 Source 级 next-run 判断：

- 高频热榜：10—15 分钟；
- 普通新闻/RSS：30—60 分钟；
- arXiv/GitHub 等低频源：6—24 小时；
- 手动同步绕过正常刷新间隔，但仍受并发、限流和最小间隔保护。

TrendRadar 的 `periods → day_plans → week_map` 可作为后续配置模型，但第一阶段只增加 `collect_enabled`、`analyze_enabled`、`push_enabled` 三个明确开关，避免一次引入复杂 DSL。

## 6. 热点处理与算法

### 6.1 确定性处理顺序

```text
RawItem
  → normalize
  → URL/domain validation
  → canonical URL dedup
  → keyword match
  → create/update occurrence
  → optional LLM analysis
  → heat score
  → transaction commit
  → SSE/event notification
```

LLM 分析失败不应回滚已经验证的候选；应写入 `analysis_status=failed/degraded`，并使用规则默认值。

### 6.2 关键词匹配

第一阶段：

```python
normalized_text = normalize(title + " " + (summary or ""))
matched = [keyword for keyword in active_keywords
           if keyword.value.casefold() in normalized_text.casefold()]
```

应将匹配结果作为持久化事实，避免每次列表查询重新计算。后续可增加 required/normal/exclude/alias 结构，但不要把 TrendRadar 的配置文件语法直接搬入数据库。

### 6.3 热度评分

AIPulse 现有评分框架继续使用：

```text
heat = source_weight * (
    interaction_score
  + keyword_score
  + multi_source_score
  + freshness_score
  + quality_score
)
```

对无互动指标的榜单源，增加独立的排名/频次分量：

```text
rank_score = normalized_rank(rank)
frequency_score = min(observation_count, cap) / cap
cross_source_score = min(source_count, cap) / cap
```

TrendRadar 的公开参考模型可表达为：排名 0.6、出现频次 0.3、高排名比例 0.1；这只是 TrendRadar 的参考算法，不是 AIPulse 当前默认值，也不是本方案的预设值。AIPulse 实施前必须用历史样本校准，不能把这些权重当作通用真理。

新鲜度必须按 source/category 配置半衰期。现有约 0.05 小时的默认值只适合极短周期热榜，不适合 RSS、论文和 GitHub 内容；迁移前应提供默认配置和回归测试。

### 6.4 去重与聚类路线

Phase 1：canonical URL 精确去重 + 同源 raw_id 幂等。

Phase 2：标题 3-gram/Jaccard 作为候选召回，结合时间窗口和来源信息形成 cluster。

Phase 3：对候选 cluster 使用 embedding/LLM 判断“同一事件/补充信息/无关”，保留多源 occurrence 和主热点。

禁止把相似度阈值直接作为删除依据；错误合并会损失来源和上下文，应支持人工查看与撤销。

## 7. API 与事件

### 7.1 REST

沿用现有接口并补齐语义：

- `GET /api/hotspots`：分页、来源、分类、重要性、关键词、时间范围、排序；
- `GET /api/hotspots/{id}`：详情、occurrences、命中关键词和分析状态；
- `POST /api/sources/{id}/sync`：手动同步，返回 job 标识或同步结果；
- `GET /api/sources`：包含当前已实现的来源配置和最近错误；Phase 1 计划补充健康状态，并在 API 层过滤敏感配置。当前 `SourceOut.config` 的脱敏行为必须在实现阶段显式补齐并用 API 测试锁定，不能默认假设已完成。
- `GET/POST/PATCH/DELETE /api/keywords`：关键词管理；
- `GET /api/digests` 和 `/latest`：日报历史；
- `POST /api/content/submit`（Phase 1 需新增）：扩展/手动提交统一进入热点处理，复用 Bearer Token 认证。

所有外部输入在 API 边界校验；URL、分页、枚举和配置字段不可直接透传到文件系统或 shell。

### 7.2 SSE

事件类型建议保持简单：

```json
{
  "event": "hotspot.new",
  "data": {
    "id": "...",
    "source_id": "...",
    "heat_score": 42.1,
    "importance": "high",
    "keyword_matches": ["agent"]
  }
}
```

事件只做实时提示，不保证历史可靠传输。客户端重连时按 `updated_since` 或普通分页接口补偿。

## 8. AI、摘要与归档集成

- 规则层先完成 URL、关键词、来源和时间处理；
- LLM 层负责摘要、分类、相关性、重要性和事件关系；
- 每条 AI 结果保存模型/版本、分析时间、置信度和失败状态；
- 关键词命中和高重要性热点可触发已有 pusher，但通知去重必须以 hotspot/event ID 为键；
- “加入处理任务”和“归档到 Obsidian”通过既有 pipeline，不在热点模块重新实现下载/转写/归档；
- 日报只读取已持久化热点，生成失败应保留失败日志和可重试状态。

## 9. 可观测性与可靠性

### 9.1 Source 健康

记录：成功率、最近成功/失败、连续失败次数、平均延迟、条目数、解析丢弃数、缓存命中率。

连续失败策略：

1. 第一次失败：记录错误，使用缓存；
2. 连续失败达到阈值：标记 degraded，通知用户；
3. 长时间失败：停止自动高频重试，等待手动恢复或配置更新；
4. 恢复成功：清除连续失败计数并记录恢复事件。

### 9.2 数据质量

每次同步至少统计：接收条目、规范化成功、URL 无效、过期过滤、重复、入库、LLM 降级数量。

### 9.3 数据保留

建议分开保留策略：

- Hotspot：按用户知识库价值长期保留；
- occurrence/cache：默认保留 30—90 天，可配置清理；
- 原始响应：默认不长期保存，调试时脱敏短期保留；
- 文章全文：第一阶段不自动保存。

## 10. 安全与合规

1. 只允许 `http`/`https` 原文链接，并校验重定向后的最终域名是否符合来源声明。
2. 每个来源上线前核查 robots、Terms、API 许可、频率限制和再分发条款；结论记录在 Source 文档或配置元数据中。
3. 不存储平台登录 Cookie，除非用户明确配置、进入 Secret 管理且经过单独合规评审。
4. 不在日志、SSE、错误响应中输出 Token、Cookie、Authorization header 或完整敏感 URL。
5. 新增依赖必须检查许可证和漏洞；TrendRadar GPL-3.0 代码不得复制进 AIPulse 闭源分发路径。
6. Web Dashboard 使用现有 Bearer Token 认证；若新增动态页面，配置生产 CSP 和安全响应头。
7. 采集器响应数据视为不可信输入，禁止执行其中的脚本、模板或 shell 内容。

## 11. 测试策略

### 11.1 单元测试

- URL 规范化和 scheme/domain 校验；
- Collector Registry、Source 配置和候选 normalize；
- RSS/API/榜单 fixture 解析；
- 关键词 required/normal/exclude/alias（逐阶段实现）；
- 热度计算、排名归一化、时间衰减和缺失指标；
- URL 去重、同源幂等、跨源 occurrence；
- 缓存 TTL、旧缓存降级和连续失败状态。

### 11.2 集成测试

- 使用真实 SQLite 测试数据库验证 Source → Hotspot → Digest；
- 验证单源失败不会影响其他源；
- 验证真实 API 认证、分页、筛选、SSE 连接和断线补偿；
- 验证关键词命中后评分、列表和通知状态一致；
- 验证 content submit 与现有摘要/归档任务衔接。

### 11.3 E2E

- 启动 sidecar，真实同步至少一个稳定 RSS/官方 API；
- Dashboard 查看列表、筛选、详情、打开原文；
- 添加关键词后等待真实条目命中并验证高亮/筛选；
- 手动同步失败源，确认错误状态和旧缓存；
- 从扩展提交链接并确认进入热点/任务链路；
- 现有 AIPulse 扩展关键链路必须使用项目约定的 `pnpm build:e2e`，并在真实页面/真实 sidecar 联调中验证；不能用普通 `build` 或 mock 后端替代关键提交链路。
- MV3 扩展 E2E 需要按项目约定使用 `headless: false` + `--headless=new`，并针对 service worker、storage.local 和平台页面陷阱进行验证。
- 修改 Python sidecar 后必须完整打包 `aipulse` 包，并分别验证开发环境与生产打包环境的导入路径。
- 使用真实数据源的集成/E2E 测试必须控制频率、使用专门测试源或 fixture，不能对第三方平台进行无界高频抓取。

## 12. 分阶段实施路线

### Phase 0：事实与合规基线

- 固化 Source 清单和每个源的 API/Terms/robots 结论；
- 确认当前数据库迁移和默认初始化行为；
- 选 3 个低风险源作为真实验收源：一个 RSS、一个官方 API、一个榜单源。

### Phase 1：可靠信息流

- 完成 source 健康字段、缓存元数据和旧缓存降级；
- 统一 HTTP/解析错误模型；
- 接入关键词实际匹配和持久化；
- 完成热点列表/详情/筛选的 Web 消费闭环；
- 保证 LLM 不可用时仍可入库。

### Phase 2：热点趋势

- 增加 `hotspot_occurrences` 和排名历史；
- 增加排名、频次、跨源出现分量；
- 引入时段化 collect/analyze/push 配置的最小版本；
- 实现来源健康面板和日报通知。

### Phase 3：AI 与知识闭环

- AI 兴趣筛选和事件聚类；
- 热点到摘要/转写/Obsidian 的一键动作；
- 关键词通知去重和个性化日报；
- 自定义 RSS、趋势查询和 MCP 接口。

## 13. 技术决策记录

| 决策 | 选择 | 原因 |
|---|---|---|
| 是否直接依赖 NewsNow | 否，优先自有 Collector | 避免外部 API 单点和跨语言运行时耦合 |
| 是否直接集成 TrendRadar | 否 | GPL-3.0 与 AIPulse 分发模式不匹配 |
| 是否引入独立消息队列 | 第一阶段不引入 | 现有 APScheduler、SQLite、SSE 足够支撑个人本地场景 |
| 是否默认浏览器自动化抓取 | 否 | 复杂、资源重、合规和稳定性风险高 |
| 是否先上 AI 筛选 | 否，先确定性关键词 | 可解释、低成本，并有稳定回退 |
| 是否把缓存作为热点事实 | 否 | 缓存只服务降级和限流，Hotspot 才是用户事实层 |
| 是否立即做语义聚类 | 否，分阶段 | 先解决可见性和可靠性，再处理高成本相似度问题 |

## 14. 最终推荐

以现有 AIPulse hotspot 子系统为基础，先完成“真实可用的信息流 + 关键词闭环 + 来源健康 + 旧缓存降级”。NewsNow 贡献采集与缓存的设计参考，TrendRadar 贡献趋势和调度的设计参考；两者都不应成为 AIPulse 的隐式运行时依赖。等 Phase 1 的真实源、缓存、筛选和 Dashboard 验收通过，再决定是否引入排名历史、事件聚类、AI 兴趣筛选和 MCP。
