# AIPulse

> 感知 AI 领域的实时脉搏。

AIPulse 是一个开源的 AI 内容处理与热点监控工具。它既能把你丢过来的视频/文章链接在后台**下载、转写、总结、归档到 Obsidian** 并推送到飞书/微信，也能**聚合多源 AI 热点**（新闻、论文、GitHub 趋势等），生成每日摘要，让你每天花 5 分钟了解 AI 领域最值得关心的事。

## 项目定位

- **目标用户**：AI 从业者、研究者、开发者、技术观察者。
- **核心目标**：一条链接进去，一份结构化总结出来；一份多源热点看板，每天 5 分钟掌握行业动态。
- **风格**：轻量、可扩展、个人化，本地优先，先让自己用起来舒服。

## 总体架构

AIPulse 由四个子系统组成，共享同一个 Python 后端：

```
┌─────────────────────────────────────────────────────────────┐
│  桌面端 (Tauri + Vue)        浏览器扩展 (Chromium MV3)        │
│  menubar 输入 / 任务 / 设置    链接识别 / 归档 / 知识检查      │
└──────────────┬───────────────────────────┬──────────────────┘
               │ JSON-RPC over stdio        │ Native Messaging / HTTP
               ▼                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Python 后端 (src/aipulse)                  │
│  sidecar · video/article 解析 · 转写 · LLM 总结 · 归档 · 推送  │
│  collectors 多源采集 · hotspot 处理 · APScheduler 调度        │
│ FastAPI (/api/hotspots /api/keywords /api/scheduler /api/sse) │
└──────────────┬───────────────────────────┬──────────────────┘
               │                            │
        SQLite (桌面端)               MySQL (热点看板)
                                             ▲
                                             │ HTTP / SSE
                                  ┌──────────┴──────────┐
                                  │  Web 看板 (web/)      │
                                  │  Vue 3 + Vite + TS    │
                                  └───────────────────────┘
```

## 子系统

| 目录 | 说明 |
|---|---|
| `src-tauri/` | Tauri 桌面端（Rust）：menubar 图标、窗口、托盘、sidecar 生命周期、Native Messaging 宿主 |
| `frontend/` | 桌面端前端（Vue 3 + Vite）：输入 / 任务 / 设置三视图，浅色珊瑚橙主题 |
| `src/aipulse/` | Python 后端：sidecar、解析、转写、总结、归档、推送、采集器、热点处理、调度、Web API |
| `web/` | 独立 Web 看板（Vue 3 + Vite + TS）：热点时间线、关键词、来源、定时任务、每日摘要 |
| `extensions/chromium/` | Chromium 扩展（MV3 + TS）：自动识别页面链接、Popup 归档/知识检查、平台适配 |
| `migrations/` | Alembic 数据库迁移（MySQL） |
| `tests/` | Python 测试（unit / integration / e2e） |
| `docs/` | 需求与设计文档 |

## 功能进度

> 设计文档见 [`docs/`](./docs/README.md)。以下为当前代码实际落地情况。

### v0.1 桌面端核心闭环（已完成，已合入 main）

链接/RSS → 下载/提取 → 转写 → 总结 → 归档 Obsidian → 飞书/微信通知。

- [x] Tauri menubar App + Python sidecar（JSON-RPC over stdio）
- [x] 视频平台解析：YouTube / Bilibili / 抖音 / 小红书 / 通用网页（策略 + 注册表）
- [x] 字幕获取：Bilibili 官方字幕、yt-dlp 内嵌字幕、faster-whisper 本地 ASR 兜底
- [x] 文章提取：微信公众号 / 普通网页
- [x] LLM 摘要（OpenAI 兼容接口，默认 kimi-for-coding）
- [x] Obsidian 归档（源笔记 + 总结笔记，双向链接）
- [x] 飞书 Webhook、微信公众号模板消息推送
- [x] RSS 订阅与同步
- [x] 桌面端前端重构：单窗口三视图（输入 / 任务 / 设置），浅色高级感珊瑚橙主题
- [x] Chromium 扩展：自动识别链接、Popup（归档 + 知识检查）、平台适配、Native Messaging + HTTP 降级

### v0.2 热点监控 + Web 看板（已完成，已合入 main）

- [x] MySQL 存储 + Alembic 迁移（`init` + `hotspot` 表）
- [x] 多源采集器：arXiv、GitHub Trending、RSS 新闻（可注册扩展）
- [x] 热点处理：清洗、去重、热度评分、AI 摘要
- [x] APScheduler 定时调度 + Jobs Web UI（`/api/scheduler/jobs`）
- [x] FastAPI 后端：`/api/hotspots`、`/api/keywords`、`/api/scheduler`、`/api/sse/hotspots`
- [x] SSE 实时热点推送
- [x] Web 看板：Dashboard / Keywords / Sources / Jobs / Digests 五个页面

### 进行中

- [ ] 浏览器扩展真实页面 E2E 加固（当前分支 `feat/extension-real-e2e`）：抖音登录态、平台适配稳定性
- [ ] 知识库去重与查漏补缺（见 `docs/knowledge-base-deduplication.md`）

### 规划中

- [ ] 关键词驱动的跨平台搜索采集（搜狗 / B 站 / 微博热搜 / HN 等）
- [ ] 更多采集器（机器之心、量子位、TechCrunch、Hugging Face 等）
- [ ] 每日摘要自动生成与多渠道推送
- [ ] v0.3：iOS 快捷指令、多端联动
- [ ] v0.4：Agent 问答、热度归因、个性化推荐

## 技术栈

| 层级 | 选型 |
|---|---|
| 桌面端 | Tauri（Rust）+ Vue 3 + Vite |
| 浏览器扩展 | Chromium MV3 + TypeScript + Vite |
| 后端 | Python 3.11+、FastAPI、APScheduler、SQLAlchemy 2.0 + Alembic |
| 桌面端存储 | SQLite（aiosqlite） |
| 热点看板存储 | MySQL（aiomysql / pymysql） |
| 视频下载 | yt-dlp |
| 转写 | faster-whisper |
| 摘要 | OpenAI 兼容接口（默认 kimi-for-coding） |
| 实时通信 | SSE |
| 包管理 | uv（Python）、npm / pnpm（前端） |

## 快速开始

### 环境准备

- Python 3.11+、uv、Node.js 18+、Rust 工具链
- MySQL（热点看板用；可用仓库根目录 `docker-compose.yml` 启动）
- 复制 `.env.example` 为 `.env` 并填写配置（数据库、LLM、飞书/微信、Obsidian 路径等）

### Python 后端 / Web 看板 API

```bash
uv sync --extra dev                          # 安装 Python 依赖（含测试工具）
cd migrations && uv run alembic upgrade head && cd ..   # 初始化/迁移数据库
uv run uvicorn aipulse.server:app --reload   # 启动 FastAPI（含定时调度）
```

也可直接用仓库根目录的 `docker-compose.yml` 一键启动（MySQL + 后端 + Web 静态资源）。

### Web 看板前端

```bash
cd web
npm install
npm run dev
```

### 桌面端（Tauri）

```bash
cd frontend && npm install && npm run dev   # 前端
cd src-tauri && cargo tauri dev             # 桌面 App
```

### 浏览器扩展

```bash
cd extensions/chromium
pnpm install
pnpm build          # 生产构建（E2E 用 pnpm build:e2e）
```

## 测试

```bash
# Python（unit / integration / e2e，覆盖率见 htmlcov/）
uv run pytest --cov

# 桌面端前端
cd frontend && npm run test:unit

# Web 看板
cd web && npm run test:unit && npm run test:e2e

# 浏览器扩展（E2E 需先 pnpm build:e2e）
cd extensions/chromium && pnpm test && pnpm e2e
```

## 文档

- 需求与版本规划：[`docs/AIPulse需求文档v0.1.md`](./docs/AIPulse需求文档v0.1.md)
- v0.1 实现计划：[`docs/v0.1-implementation-plan.md`](./docs/v0.1-implementation-plan.md)
- v0.2 桌面端重设计：[`docs/superpowers/specs/2026-07-09-aipulse-app-redesign-design.md`](./docs/superpowers/specs/2026-07-09-aipulse-app-redesign-design.md)
- v0.2 Web 看板设计：[`docs/superpowers/specs/2026-07-09-v0.2-web-dashboard-design.md`](./docs/superpowers/specs/2026-07-09-v0.2-web-dashboard-design.md)
- 知识库去重方案：[`docs/knowledge-base-deduplication.md`](./docs/knowledge-base-deduplication.md)

## License

MIT
