# AIPulse 资讯聚合与热点发现深度调研 — 技术文档

> 版本：v0.1
> 日期：2026-07-26
> 文件性质：本轮新写，不修改既有 `docs/` 与 `docs/superpowers/` 源文档。
> 关联需求：`docs/superpowers/specs/2026-07-26-newsnow-trendradar-deep-research-requirements.md`。

## 1. 技术结论

- 不把 NewsNow 或 TrendRadar 作为运行时核心依赖，也不拼接成新独立服务。
- 在现有 Python sidecar 内继续使用 `BaseCollector` + Registry。
- NewsNow 借鉴：源适配器、分源刷新间隔、两级缓存、旧缓存降级。
- TrendRadar 借鉴：排名历史、频次/排名热度、关键词分层、时段任务、报告模式。
- 继续使用 FastAPI、SQLite/SQLAlchemy、APScheduler、SSE、LLM 分析与 Obsidian pipeline。
- NewsNow MIT 可参考实现，但优先在 Python sidecar 重新实现；TrendRadar GPL-3.0 源码不复制进 AIPulse。

## 2. 事实依据

### 2.1 NewsNow（核验仓库：ourongxing/newsnow）

- MIT；TypeScript；Vue 3 前端；Nuxt 3/Nitro 服务端；顶层 `server/`、`src/`、`shared/`；
- `server/sources/*.ts` 采用每源适配器；支持 HTML/API/RSS；
- 缓存按来源刷新时间和刷新间隔判断是否复用，抓取失败返回旧缓存；
- 条目 ID 不统一（标题 vs URL vs 平台 ID），不能直接用于跨源去重。

### 2.2 TrendRadar（核验仓库：sansan0/TrendRadar）

- GPL-3.0；Python；`is_template=true`；
- `trendradar/crawler/fetcher.py` 默认调用可配置的 NewsNow 部署（非官方 API）；
- `trendradar/core/analyzer.py` 用排名×0.6、频次×0.3、热度比例×0.1 组合热度，权重不作为通用真理；
- `trendradar/core/scheduler.py` 把 collect/analyze/push 与时段/报告模式编排；
- 多渠道渲染/分发仅作为接口设计参考。

### 2.3 AIPulse 现状

- `src/aipulse/collectors/base.py:33-56` 定义 `fetch()` 与 `normalize()`；`src/aipulse/collectors/registry.py:8-11` 注册；
- `src/aipulse/hotspot/models.py:35-150` 已有 Source/Hotspot/Keyword/DailyDigest；
- `src/aipulse/hotspot/service.py:41-84` 主链路已具备 URL 去重、LLM 分析、热度、入库与 SSE；
- `src/aipulse/hotspot/processor.py:67-92` 评分维度已就位，但 `process_candidates` 当前 `keyword_matches` 传空；
- `src/aipulse/scheduler/jobs/hotspot_sync.py:16-87` 已隔离 Source 失败；
- `src/aipulse/server.py:76-93` 当前固定 30 分钟轮询与每日 08:00 日报；
- `src/aipulse/web/routes.py` 覆盖热点/关键词/来源/日报/SSE；前端 Dashboard 消费界面需补齐。

## 3. 系统架构

```text
┌────────────────────────────────────────────────────────────────┐
│ Web Dashboard / Tauri Menu Bar / Chromium Extension            │
└───────────────────────┬────────────────────────────────────────┘
                        │ REST + SSE + content submit
┌───────────────────────▼────────────────────────────────────────┐
│ FastAPI API                                                    │
│ hotspots / sources / keywords / digests / sse / content/submit │
└───────────────────────┬────────────────────────────────────────┘
                        │
┌───────────────────────▼────────────────────────────────────────┐
│ Hotspot Service                                                │
│ normalize → validate → canonical dedup → keyword match         │
│ → rule/LLM analysis → heat score → persist → SSE/notify        │
└───────────────┬────────────────────────────────────────────────┘
                │
┌───────────────▼────────────────────────────────────────────────┐
│ Collector Layer + Scheduler                                    │
│ Registry + per-source fetch + APScheduler per-source next-run  │
└───────────────┬────────────────────────────────────────────────┘
                │
┌───────────────▼────────────────────────────────────────────────┐
│ SQLite + SQLAlchemy                                            │
│ sources / source_cache / hotspots / keyword_matches            │
│ hotspot_occurrences / digests / scheduler_job_log              │
└────────────────────────────────────────────────────────────────┘
```

边界原则：Collector 不直接调用 LLM 或发送通知；Hotspot Service 负责事务边界；Scheduler 只触发不复制规则；Pusher 只接收统一消息模型；Extension 走通用内容提交，不建立第二套热点存储。

## 4. 数据模型

### 4.1 Source（保留 + Phase 1 计划新增）

```text
id, name, source_type, collector_class, config, default_weight,
fetch_interval_minutes, is_active, last_fetched_at,
failed_at, last_error                  # 既有
+ consecutive_failures                # Phase 1 计划新增
+ max_age_hours                        # Phase 1 计划新增
+ health_status = healthy | degraded | disabled   # Phase 1 计划新增或由 API 计算
```

`config` 不存放 secrets；Token/Cookie 使用 SecretStr/统一 secret 管理。

### 4.2 Hotspot（保留 + Phase 1 计划新增）

```text
keyword_matches        JSON  default '[]'                 # Phase 1
keyword_match_count    Integer default 0                  # Phase 1
last_notified_at       DateTime nullable                  # Phase 1
+ analysis_status                                        # Phase 1
+ analysis_confidence                                     # Phase 1
```

### 4.3 Keyword（保留字段语义）

```text
value, is_active, notify_on_match, boost_factor
```

### 4.4 Phase 2 计划新增

```text
hotspot_occurrences (hotspot_id, source_id, observed_at, rank, raw_url, interaction JSON)
cluster_id, first_seen_at, last_seen_at
```

### 4.5 Phase 1 计划新增

```text
source_cache (source_id PRIMARY KEY, fetched_at, expires_at, data JSON,
              item_count, fetch_status, error_message)
```

缓存策略：

```
请求同步
  ├─ now < source.next_refresh_at → 返回有效缓存
  ├─ 过期但 now < hard_expiry   → 抓取
  ├─ 抓取成功                   → 原子替换
  └─ 抓取失败且有旧缓存         → 旧缓存 + degraded
```

## 5. 采集层

| 类型 | 示例 | 处理 |
|---|---|---|
| RSS/Atom | 机器之心 / 自定义 RSS | feedparser，按发布时间过滤 |
| 官方 API | arXiv / GitHub / Bilibili | httpx + 结构化 JSON 校验 |
| 公开榜单 API | 公开合规热榜 | 记录 rank 与快照 |
| HTML 页面 | 仅公开条款允许 | 受限频率；解析隔离 |
| Extension submit | 用户主动 | 不主动抓站；走通用提交接口 |

统一请求策略：总超时/连接超时、有限重试（连接错误/429/5xx）、指数退避、可审计 UA、不把登录 Cookie 写入日志、JSON/RSS 边界校验、记录耗时与状态码。

第一阶段不引入代理池或浏览器自动化。需登录态的平台默认禁用。

调度：当前统一 30 分钟轮询；目标是 Phase 1 改为 Source 级 next-run（高频 10–15 分钟；普通 30–60；低频 6–24 小时）。手动同步绕过正常刷新间隔，但仍受并发与最小间隔保护。

## 6. 热点处理与算法

### 6.1 确定性处理顺序

```
RawItem
  → normalize
  → URL/domain validation
  → canonical dedup
  → keyword match
  → create/update occurrence
  → optional LLM analysis
  → heat score
  → transaction commit
  → SSE/notify
```

LLM 失败时写入 `analysis_status=failed/degraded`，使用规则默认值，不回滚已验证候选。

### 6.2 关键词匹配（Phase 1）

```python
normalized_text = normalize(title + " " + (summary or ""))
matched = [
    keyword for keyword in active_keywords
    if keyword.value.casefold() in normalized_text.casefold()
]
```

匹配结果以 `keyword_matches` JSON + `keyword_match_count` 持久化。

### 6.3 热度评分

保留现有公式 `heat = source_weight * (interaction + keyword + multi_source + freshness + quality)`；为无互动指标的榜单源引入 `rank_score`、`frequency_score`、`cross_source_score`。

新鲜度半衰期需按 source/category 配置；现有约 0.05 小时默认仅适合短周期热榜，不适合 RSS/论文/GitHub 内容；迁移前需配置默认值和回归测试。TrendRadar 权重 0.6/0.3/0.1 只作为参考起点，必须以历史样本校准。

### 6.4 去重与聚类路线

- Phase 1：canonical URL 精确去重 + 同源 raw_id 幂等；
- Phase 2：标题 3-gram/Jaccard 召回 + 时间窗口形成 cluster；
- Phase 3：对 cluster 用 embedding/LLM 判断事件/补充/无关；
- 禁止把相似度阈值直接当作删除依据；聚类必须保留每个来源链接与原始排名。

## 7. 关键词通知（Phase 1 主线）

```
can_notify =
    keyword.is_active
  and keyword.notify_on_match
  and source.is_active
  and keyword_match_count >= 1
  and importance ∈ {medium, high, critical}
```

实现要点：

1. `process_candidates` 真接 `active_keywords`；落库 `keyword_matches` / `keyword_match_count`；
2. 通知决策在 service 层计算，写入 `last_notified_at` 并以 `(hotspot_id, keyword_id)` 幂等；
3. SSE 推送 `hotspot.notify` 事件；前端高亮命中 badge；
4. 桌面通知走既有 notification channel；
5. 与现有飞书/微信推送解耦，本阶段不引入多渠道渲染器；
6. 旧热点仅在 `last_notified_at is None` 时才触发，重复命中不重发；
7. 用户关闭关键词后，新热点 `keyword_match_count` 不再增长，旧记录保持不变。

## 8. API 与事件

| 接口 | 现状 | Phase 1 调整 |
|---|---|---|
| `GET /api/hotspots` | 已支持分页/来源/分类/重要性/排序 | 增 `keyword` 筛选与命中 badge 字段 |
| `GET /api/hotspots/{id}` | 详情 | 增 `keyword_matches`、`last_notified_at`、`analysis_status` |
| `GET/POST/PATCH/DELETE /api/keywords` | 已 CRUD | 强化 `notify_on_match` UI 与命中统计 |
| `GET /api/sources` | 已支持 | 增 `health_status`、`consecutive_failures`、脱敏配置 |
| `POST /api/sources/{id}/sync` | 已支持 | 健康状态/缓存降级可见 |
| `GET /api/digests` | 已支持 | 历史与通过现有渠道发送 |
| `POST /api/content/submit` | 新增 | 扩展/手动提交统一入口，复用 Bearer Token |

SSE 事件：`hotspot.new`、`hotspot.updated`、`hotspot.notify`。客户端断线重连后按 `updated_since` 或分页补偿，事件仅做实时提示。

## 9. 可观测性与可靠性

- Source 健康：成功率、最近成功/失败、连续失败次数、平均延迟、条目数、解析丢弃数、缓存命中率；
- 连续失败策略：第一次失败记错误并降级；阈值后 degraded 并通知；长时间失败停止高频重试；恢复后清零并记录恢复事件；
- 数据质量：接收、规范化成功、URL 无效、过期过滤、重复、入库、LLM 降级计数；
- 数据保留：Hotspot 按知识价值长期保留；occurrence/cache 默认 30–90 天可配；原始响应默认不长期保存；
- 测试隔离：沿用项目 Apple Reminders/数据隔离与“禁 mock 后端”约束。

## 10. 安全与合规

1. URL 仅接受 `http`/`https`，校验重定向后域名与来源声明一致；
2. 每个新源上线前核查 robots、Terms、API 许可、频率限制与再分发条款；
3. 不存储平台登录 Cookie，除非进入 Secret 管理并经合规评审；
4. 日志/SSE/错误响应不输出 Token、Cookie、Authorization header、敏感 URL；
5. 新依赖检查许可证与漏洞；TrendRadar GPL-3.0 代码不得复制进闭源分发路径；
6. Web Dashboard 沿用 Bearer Token；新页面配 CSP 与安全响应头；
7. 采集器响应视为不可信输入，禁止执行其中脚本/模板/shell 内容；
8. sidecar 完整打包 `aipulse` 包并验证 dev/prod `sys.path`。

## 11. 测试策略

- 单元：URL 规范化、scheme/domain、Registry、Source 配置、候选 normalize、RSS/API/榜单 fixture、关键词匹配、热度计算、时间衰减、URL 去重与同源幂等、缓存 TTL/降级、通知去重；
- 集成：真实 SQLite 测试库验证 Source → Hotspot → Digest、单源失败隔离、SSE 连接与断线补偿、关键词命中一致性、content submit 与摘要/归档衔接；
- E2E：sidecar 真起，至少一个稳定 RSS/官方 API；Dashboard 列表/筛选/详情/原文；关键词真实命中高亮；失败源状态与旧缓存；扩展提交；日报与通知（测试渠道，不 mock 关键链路）；
- 沿用最低 80% 覆盖率，但不能用覆盖率替代端到端验证。

## 12. 阶段路线

- Phase 0 事实与合规基线：固化源清单与 Terms；选定 3 个低风险验收源；
- Phase 1 可靠信息流 + 关键词通知：完成 Source 健康/缓存/降级、关键词真实接入、SSE `hotspot.notify`、Dashboard UI、补齐 `Source.health_status` 与 `hotspots.keyword_match_count`；
- Phase 2 趋势与排名：occurrences、排名历史、时段化最小配置、健康面板、日报通知；
- Phase 3 AI/知识闭环：AI 兴趣筛选与事件聚类、热点→摘要/转写/Obsidian、自定义 RSS、MCP 查询。

## 13. 最终推荐

以既有 hotspot 子系统为基础，先完成“关键词命中 + 高亮 + 桌面通知 + 真实可用的信息流”。NewsNow 提供缓存/适配器参考，TrendRadar 提供趋势/调度参考，两者都不应成为运行时依赖。Phase 1 验收通过后再决定是否引入排名历史、事件聚类、AI 兴趣筛选和 MCP。

## 14. 引用约定

- 本文件以独立文件名落地：`docs/superpowers/specs/2026-07-26-newsnow-trendradar-deep-research-technical.md`；
- 不修改既有源文档；引用既有源文档段落时使用“引用 + 行号”，不直接编辑；
- `docs/2026-07-25-information-hotspot-research-*.md` 仅作为历史草稿保留，新决策以本文件和对应需求文档为准。
