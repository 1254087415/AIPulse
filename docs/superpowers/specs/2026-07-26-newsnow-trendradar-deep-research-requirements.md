# AIPulse 资讯聚合与热点发现深度调研 — 需求文档

> 版本：v0.1
> 日期：2026-07-26
> 文件性质：本轮新写，不修改既有 `docs/` 与 `docs/superpowers/` 源文档。
> 调研对象：NewsNow（MIT）、TrendRadar（GPL-3.0）、AIPulse 现状（MIT）。
> 关联技术文档：`docs/superpowers/specs/2026-07-26-newsnow-trendradar-deep-research-technical.md`。

## 1. 文档目的

把 NewsNow 的多源信息聚合能力与 TrendRadar 的热点筛选、趋势分析能力，转化为符合 AIPulse 定位的产品需求。AIPulse 的核心差异在于“信息不是终点”，而是后续 AI 摘要、视频/文章处理、Obsidian 归档、学习事件和通知的输入。本需求优先考虑本地优先、可追溯、可归档和可扩展，而不是单纯复制一个热榜站。

## 2. 上游项目调研结论

| 项目 | 核心能力 | 关键事实 | 对 AIPulse 的结论 |
|---|---|---|---|
| NewsNow | 多平台源适配、分源刷新间隔、两级 TTL 缓存、旧缓存降级、RSS/HTML/API 统一接入 | MIT；TypeScript；前端 Vue 3；服务端 Nuxt 3/Nitro | 仅借鉴适配器和缓存思想；不并入其前端/服务端框架；不引用其默认部署实例 |
| TrendRadar | 通过可配置的 NewsNow 部署获取热榜；维护排名历史；按关键词/AI 兴趣筛选；按时段执行；多渠道通知 | GPL-3.0；Python；`is_template=true`；默认模板是部署示例，不视为官方事实 | 仅借鉴数据模型、报告模式、调度模型；不复制源码；不依赖其默认 NewsNow 地址 |
| AIPulse | Collector Registry、热点评分、关键词 CRUD、LLM 分析、DailyDigest、SSE、Obsidian 归档、桌面通知 | MIT；本地优先；Python sidecar + Tauri + Vue + Extension | 以现有 sidecar/FastAPI/SQLite 为主；不新增独立聚合服务 |

## 3. 产品原则与目标

| 维度 | 决策 |
|---|---|
| 整体目标 | 在 AIPulse 既有 `Source → Collector → Hotspot → Digest` 链路上补齐关键词命中 + 高亮 + 通知闭环 |
| 单一事实源 | `hotspots` 是信息流事实存储；NewsNow/TrendRadar 不作为运行时必需依赖 |
| 本地优先 | 采集、缓存、关键词、日报、通知决策均在 Python sidecar/本地数据库完成 |
| 渐进增强 | 先规则与确定性指标，再用 LLM 做摘要/分类/筛选 |
| 可解释优先 | 列表排序必须能解释来源权重、关键词命中、新鲜度和跨源次数 |
| 合规优先 | 公开 API/RSS 优先；每个新源上线前记录 Terms、robots、频率限制和再分发边界 |

## 4. 用户故事

| 编号 | 用户故事 | 优先级 |
|---|---|---|
| US-01 | 打开 Dashboard 即可看到来自多个来源、按新鲜度/相关性排序的信息流 | P0 |
| US-02 | 按来源、分类、时间、重要性、关键词筛选热点 | P0 |
| US-03 | 配置关键词后，命中内容被标记、加权并按规则触发通知 | P0 |
| US-04 | 同一事件多源出现时显示聚合关系，保留每个来源链接与排名 | P1 |
| US-05 | 关键词命中可触发桌面通知，并按重要性/重复规则去重 | P0 |
| US-06 | 热点可送入现有摘要/归档流程，任务失败状态可回写 | P1 |
| US-07 | 每日报告可查看历史并通过既有通知渠道发送 | P1 |
| US-08 | 数据源最近成功时间、失败原因、健康状态可见 | P1 |
| US-09 | 添加 RSS 等低风险自定义来源 | P2 |
| US-10 | 配置采集/分析/通知时段，避开夜间无意义处理 | P2 |

## 5. Phase 1 范围

### 5.1 必须包含

1. 多源采集：沿用现有 Collector Registry，覆盖现有 RSS、GitHub、arXiv、Bilibili、知乎、微博、百度、V2EX 等可验证来源；
2. 关键词闭环：CRUD + 真实匹配 + 命中记录 + 排序加权 + Dashboard 高亮 + 桌面通知；
3. 通知去重：以 `(hotspot_id, keyword_id)` 与重要性阈值避免打扰；
4. 数据源健康：连续失败次数、最近错误、健康状态；
5. 旧缓存降级：来源抓取失败时返回最近成功数据。

### 5.2 后续阶段

- 跨源事件聚类与排名时间线；
- AI 自然语言兴趣筛选（确定性关键词匹配做可解释回退）；
- 多渠道渲染器；
- 自定义 RSS；
- 时段化 collect/analyze/push；
- MCP 查询工具。

### 5.3 明确不做

- 不直接复制 TrendRadar GPL-3.0 源码；
- 不把 NewsNow 的 Nuxt/Nitro 前端和独立用户系统并入 AIPulse；
- 不默认启用需登录 Cookie、绕过风控或高频抓取的来源；
- 不在第一阶段存储第三方文章全文；
- 不把热度分数等同于真实性或投资判断；
- 不为“实时”引入常驻浏览器池或代理池。

## 6. 关键词通知策略（Grill-Me 推荐）

```
can_notify =
    keyword.is_active
  and keyword.notify_on_match
  and source.is_active
  and keyword_match_count >= 1
  and importance ∈ {medium, high, critical}
```

- 关键词匹配：标题 + 摘要大小写无关字面匹配；命中后写入 `keyword_matches` JSON 与 `keyword_match_count`；
- 排序加权：沿用既有 `keyword_score = max(1, 10) * boost_factor`，不引入新公式；
- 通知渠道：默认桌面通知；与现有飞书/微信推送解耦，本阶段不引入多渠道渲染器；
- 通知去重：以 `(hotspot_id, keyword_id)` 唯一键维护幂等，更新 `last_notified_at`。

## 7. 验收

### P0

1. 至少 5 个来源能成功同步，5 分钟内出现可展示条目；
2. 单源失败隔离，可见健康状态；
3. 新增关键词后，新匹配热点立刻显示命中 badge，并参与排序；
4. 同 `canonical_url` 不重复创建；采集失败时仍可读旧数据；
5. Dashboard 支持分页/来源/分类/重要性/时间/关键词筛选；
6. 高重要性命中 1 分钟内桌面通知，重复命中不重发。

### P1

1. 一事件多源条目可关联查看；
2. 热点可进入现有摘要/归档流程；
3. 日报可查历史并通过已有渠道发送；
4. 连续失败达到阈值后健康状态变 degraded 并通知用户。

### P2

1. 时段化 collect/analyze/push；
2. 自然语言兴趣筛选和趋势图；
3. 自定义 RSS / MCP 查询。

## 8. 风险与产品约束

| 风险 | 约束/应对 |
|---|---|
| 平台 API 或页面变更 | Collector 隔离、健康状态、旧缓存降级、单源手动重试 |
| 反爬与限流 | 公开接口优先、分源频率、超时/退避；不默认代理池或登录 Cookie |
| 数据再分发 | 默认只保存标题/摘要/指标/原文链接；逐源确认条款 |
| TrendRadar GPL-3.0 | 仅参考架构/数学模型/配置思想，不复制源码或形成派生模块 |
| 热度误导 | 展示指标来源与更新时间；不视为真实性判断 |
| LLM 成本与延迟 | 先规则入库，批量/异步分析，失败降级，不阻塞采集 |
| 本地数据库增长 | 纳入清理/保留期/索引策略 |

## 9. 来源与文档引用约定

- 本文件以独立文件名落地：`docs/superpowers/specs/2026-07-26-newsnow-trendradar-deep-research-requirements.md`；
- 不修改既有源文档；如需引用既有源文档段落，使用“引用 + 行号”方式说明，不直接编辑；
- 既往由 LLM 自动生成的 `docs/2026-07-25-information-hotspot-research-requirements.md` 与 `docs/2026-07-25-information-hotspot-research-technical.md` 仅作为历史草稿保留，新决策与产物以本文与对应技术文档为准。
