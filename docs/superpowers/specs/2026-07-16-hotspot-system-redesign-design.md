# AIPulse 热点监控系统优化需求文档

> 版本：v0.1
> 日期：2026-07-16
> 目标：让 AIPulse Web 端能够稳定、实时地展示有价值的信息流

---

## 一、背景与现状

### 1.1 项目定位

AIPulse 是桌面端 AI 内容/任务管理工具（Tauri + Python sidecar + Vue web + Chromium Extension）。其中「AI 热点监控」子系统负责从多源聚合、筛选、排序热点内容，并在 web 端 Dashboard 呈现。

### 1.2 当前实现

| 模块 | 现状 |
|---|---|
| 后端采集器 | 仅 3 个固定来源：RSS News（机器之心）、GitHub Trending、arXiv |
| 浏览器扩展 | 已支持 Bilibili/抖音/小红书/微信公众号/YouTube 的页面识别，但识别结果走归档任务流，**不进 hotspot 表** |
| 关键词 | 提供 CRUD，但 `process_candidates` 中写死 `keyword_matches=[]`，未参与打分/过滤/通知 |
| 去重 | 仅 `canonical_url` 精确去重；`compute_similarity` 已定义但未调用 |
| 调度 | APScheduler，每 30 分钟同步一次，每天 08:00 生成日报 |
| 实时推送 | SSE `/api/sse/hotspots` |
| 通知 | 无邮件/桌面通知 |
| 数据初始化 | `AUTO_CREATE_TABLES` 默认 `False`，不自动建表/种子来源 |

### 1.3 核心问题

Web 端 Dashboard 经常「几乎没有信息」，原因包括：

1. 默认不自动建表/不种子来源；
2. 来源数量太少，且依赖 LLM 判断导致空窗；
3. 关键词未生效，无法按用户兴趣过滤/加权；
4. 浏览器扩展捕获的大量中文平台内容未进入热点流；
5. 没有中文互联网主流平台数据源。

---

## 二、目标与验收标准

### 2.1 核心目标

**用户在启动 AIPulse 后，无需复杂配置即可在 web 端 Dashboard 看到持续更新的信息流。**

### 2.2 验收标准

1. **开箱即用**：首次启动自动完成数据库初始化与默认来源配置；
2. **有数据**：Dashboard 在 5 分钟内出现至少 10 条热点条目；
3. **多源覆盖**：至少覆盖 10 个中文/国际数据源；
4. **关键词生效**：用户添加关键词后，匹配到的热点热度提升并触发通知；
5. **扩展接入**：浏览器扩展识别的 Bilibili/抖音/小红书/微信公众号链接可进入热点流；
6. **稳定更新**：每 30 分钟自动刷新，SSE 实时推送新热点。

---

## 三、业务需求（用户故事）

| 角色 | 需求 | 优先级 |
|---|---|---|
| 普通用户 | 打开 Dashboard 就能看到当前 AI/科技领域热点 | P0 |
| 普通用户 | 可以按平台、分类、重要性、时间范围筛选热点 | P0 |
| 关注特定主题的用户 | 添加关键词后，相关热点被高亮、排序靠前并通知我 | P1 |
| 内容创作者 | 浏览器上刷到的好内容自动进入 AIPulse 热点池 | P1 |
| 重度用户 | 每天收到一份热点日报/摘要 | P2 |
| 开发者 | 新增数据源只需实现一个标准采集器并注册 | P2 |

---

## 四、技术方案

### 4.1 架构调整

```
┌─────────────────────────────────────────────────────────────┐
│                        Web Dashboard                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Web API                           │
│  /api/hotspots  /api/sources  /api/keywords  /api/sse/hotspots│
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              Hotspot Service (process_candidates)            │
│  - 去重 (URL + 语义)                                        │
│  - 关键词匹配                                               │
│  - AI 分析 (is_real / relevance / importance / summary)     │
│  - 热度评分 (heat_score)                                    │
│  - 持久化 + SSE 广播                                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Collector Registry                        │
│  - 平台热榜源 (Bilibili/知乎/微博/抖音/百度/36氪/IT之家...) │
│  - RSS/News 源                                              │
│  - GitHub Trending / arXiv                                  │
│  - 扩展提交适配器                                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────┐  ┌─────────────────────┐  ┌───────────┐
│   APScheduler       │  │  Chromium Extension │  │  Manual   │
│   (30 min interval) │  │  (content submit)   │  │  trigger  │
└─────────────────────┘  └─────────────────────┘  └───────────┘
```

### 4.2 数据源规划

参考 [DailyHotApi](https://github.com/imsyy/DailyHotApi) 与 [NewsNow](https://github.com/ourongxing/newsnow) 的实现，优先接入**公开 API 稳定、无需登录**的中文平台：

| 来源 | 接口类型 | 是否接入 | 说明 |
|---|---|---|---|
| 机器之心 RSS | RSS | 已有 | 保留 |
| GitHub Trending | 官方/第三方 | 已有 | 保留 |
| arXiv | 官方 API | 已有 | 保留 |
| 知乎热榜 | 公开 API | **新增** | `api.zhihu.com/topstory/hot-lists/total` |
| 微博热搜 | 公开 API | **新增** | `weibo.com/ajax/side/hotSearch` |
| Bilibili 热门榜 | 公开 API | **新增** | `api.bilibili.com/x/web-interface/ranking/v2` |
| 百度热搜 | 公开 API | **新增** | 参考 DailyHotApi |
| 抖音热点 | 公开 API | **新增** | 参考 DailyHotApi |
| 36氪热榜 | 公开 API | **新增** | 参考 DailyHotApi |
| IT之家热榜 | 公开 API | **新增** | 参考 DailyHotApi |
| V2EX 热门 | 公开 API | **新增** | `v2ex.com/api/topics/hot.json` |
| HackerNews | 官方 API | **新增** | Algolia HN Search |
| 扩展提交 (Bilibili/抖音/小红书/微信) | HTTP/Native | **新增** | 进入 hotspot 表 |

> 合规原则：优先使用平台公开 API；如需爬取页面，应遵守 robots.txt，控制频率，避免对源站造成压力。

### 4.3 采集与调度

1. **统一 Collector 接口**：沿用现有 `BaseCollector`，新增 `fetch()` 返回 `list[RawItem]`；
2. **自动注册**：参考 DailyHotApi 的 `registry.ts`，从 `src/aipulse/collectors/` 自动发现采集器；
3. **调度策略**：
   - 默认每 30 分钟全量同步；
   - 高频源（微博热搜、知乎热榜）可配置为 10 分钟；
   - 低频源（GitHub Trending、日报类）可配置为 6-24 小时；
   - 支持 Web 端手动触发单个来源同步；
4. **失败重试**：单个源失败记录 `last_error`，不影响其他源；连续失败 3 次自动暂停并通知用户。

### 4.4 热度评分算法

综合 HackerNews/Reddit 时间衰减思想与 AIPulse 现有指标：

```python
heat_score = (
    base_interaction_score      # views/likes/comments/shares/stars/forks 归一化
    * source_weight             # 来源权重，用户可配置
    * recency_decay             # 时间衰减，越新越高
    * quality_score             # AI 判断的 relevance/importance
    * keyword_boost             # 匹配用户关键词时的加成
)
```

- **时间衰减**：`recency_decay = exp(-hours_since_published / half_life)`，默认 `half_life=12h`；
- **来源权重**：用户可在 Sources 页调整每个源的权重；
- **关键词加成**：匹配到关键词时 `keyword_boost = 1.5`，未匹配 `=1.0`。

### 4.5 去重策略

采用三层去重：

1. **URL 规范化去重**：去掉 tracking 参数、尾斜杠、`www.` 前缀，生成 `canonical_url`；
2. **语义去重**：调用已有的 `compute_similarity`（或接入 embedding 语义相似度），相似度 > 0.85 的合并为同一 `duplicate_group_id`，保留发布时间最早/互动最高的一条；
3. **标题模糊去重**：作为 fallback，标题编辑距离 < 0.9 的视为重复。

### 4.6 关键词匹配

1. **预匹配**：对标题 + 摘要做关键词字面匹配（不区分大小写、支持中文分词）；
2. **AI 匹配**：在 `analyze_hotspot` 中返回 `keywordMentioned` 与匹配到的关键词；
3. **生效点**：
   - 热度评分 `keyword_boost`；
   - 通知触发：命中关键词且 importance ≥ medium 时发送通知；
   - Dashboard 筛选：按关键词筛选。

### 4.7 扩展内容接入

浏览器扩展识别到的链接当前走 `tasks` 表。新增适配：

1. 扩展提交时可选「加入热点池」；
2. 后端 `content_router` 识别 URL 类型后，生成 `RawItem` 直接进入 `process_candidates`；
3. 若 LLM 判定 `is_real=True` 且相关性足够，写入 `hotspots` 表。

### 4.8 通知机制

| 触发条件 | 通知方式 | 优先级 |
|---|---|---|
| 新热点 importance=high/urgent | SSE + 桌面通知 | P1 |
| 命中用户关键词的新热点 | SSE + 桌面通知 | P1 |
| 每日 08:00 | 日报摘要（web 内 + 可选邮件） | P2 |
| 来源连续失败 3 次 | 桌面通知 + 源状态标记 | P2 |

---

## 五、数据模型调整

### 5.1 Source 表新增字段

```sql
- update_interval_minutes: int  # 自定义更新频率
- is_builtin: bool              # 是否内置源
- category: str                 # 分类：social/tech/news/video/academic
- default_weight: float         # 默认来源权重
- max_age_hours: int            # 内容最大有效时长
```

### 5.2 Hotspot 表新增字段

```sql
- duplicate_group_id: uuid?     # 语义去重组 ID
- keyword_matches: json         # 命中的关键词列表
- author_avatar: str?           # 作者头像
- author_followers: int?        # 作者粉丝数
- comment_count: int?           # 评论数
- share_count: int?             # 分享数
```

### 5.3 Keyword 表保持，但启用匹配逻辑

```sql
- is_active: bool
- notify_on_match: bool         # 是否推送通知
- boost_factor: float           # 热度加成系数，默认 1.5
```

---

## 六、接口调整

| 接口 | 变更 |
|---|---|
| `GET /api/hotspots` | 新增 `keyword`、`category`、`source`、`min_importance` 筛选 |
| `POST /api/sources/{id}/sync` | 支持手动触发，返回任务 ID |
| `GET /api/sources` | 返回源状态（最后成功/失败时间、健康状态） |
| `POST /api/videos/extract` | **新增/补全**：接收扩展提交，进入热点处理流程 |
| `GET /api/keywords` | 返回关键词匹配统计 |
| `GET /api/sse/hotspots` | 保持不变，按 keyword 过滤推送 |

---

## 七、实施路线图

### Phase 1：让 web 端立刻有数据（P0，1-2 天）

1. 修复默认配置：
   - `.env.example` 中将 `AUTO_CREATE_TABLES=true` 作为推荐默认值；
   - 确保 `init_db()` + `_seed_default_sources()` 在开发环境默认执行；
2. 新增中文平台采集器：知乎热榜、微博热搜、Bilibili 热门、百度热搜、V2EX 热门；
3. 修复 LLM 配置检测：无 LLM key 时回退到规则化分析，避免全部丢弃；
4. 提供手动同步按钮并确保可用。

### Phase 2：关键词与去重生效（P1，2-3 天）

1. 实现关键词预匹配，写入 `keyword_matches`；
2. 热度评分加入 `keyword_boost`；
3. 启用语义去重 `duplicate_group_id`；
4. 关键词命中通知（SSE + 桌面通知）。

### Phase 3：扩展接入与数据源扩展（P1，3-5 天）

1. 实现 `/api/videos/extract`（或更通用的 `/api/content/submit`）进入 `process_candidates`；
2. 浏览器扩展增加「加入热点池」选项；
3. 新增抖音、36氪、IT之家、HackerNews、arXiv 增强源。

### Phase 4：日报与高级功能（P2，后续迭代）

1. 日报邮件/桌面推送；
2. 热度趋势图；
3. 来源健康度面板；
4. 用户自定义 RSS 源。

---

## 八、风险与合规

| 风险 | 应对措施 |
|---|---|
| 公开 API 变更或限流 | 每个采集器独立失败处理；配置 fallback 接口；监控 `last_error` |
| 反爬封 IP | 控制请求频率；使用公开 API 优先；必要时加代理配置 |
| 数据合规与版权 | 仅存储标题、摘要、链接，不存储全文；保留原文跳转 |
| LLM 成本过高 | 支持批量分析；对平台热榜高置信内容可跳过 AI 分析 |
| 数据量过大 | 限制每个源每次同步条目数；按 `max_age_hours` 过滤旧内容 |

---

## 九、参考项目

- [DailyHotApi](https://github.com/imsyy/DailyHotApi) — 50+ 中文平台热榜聚合 API
- [NewsNow](https://github.com/ourongxing/newsnow) — Cloudflare Workers 实时新闻聚合，40+ 源
- [TopList](https://github.com/tophubs/TopList) — Go 多协程热榜抓取
- [yupi-hot-monitor](https://github.com/liyupi/yupi-hot-monitor) — 关键词驱动的热点监控
- [How Hacker News ranking really works](http://www.righto.com/2013/11/how-hacker-news-ranking-really-works.html)
