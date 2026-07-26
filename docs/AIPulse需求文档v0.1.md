# AIPulse 需求文档 v0.1

> 本文档按版本拆分需求。第一版只聚焦**最小可用闭环**：收到 RSS/链接 → 下载视频 → 转写总结 → 归档到 Obsidian → 飞书通知。

---

## 1. 项目背景

AI 领域信息爆炸，每天都有大量新闻、论文、模型、工具、融资事件涌现。对于 AI 从业者、研究者和开发者来说，手动追踪这些信息成本极高，容易错过真正重要的信号。

AIPulse 希望做一个**开源的 AI 热点监控与个人情报助手**：
- 第一阶段：先把**RSS/链接中的视频**自动下载、总结、归档到 Obsidian，解决个人知识库输入问题。
- 第二阶段：再扩展为 AI 热点监控看板。
- 第三阶段：加入 Agent 问答与移动端能力。

## 2. 产品定位

- **一句话描述**：感知 AI 领域的实时脉搏，把 RSS / 热点发现、视频下载与总结、自动归档、知识库问答串成闭环。
- **目标用户**：AI 从业者、研究者、开发者、技术观察者、AI 自媒体。
- **风格**：轻量、可扩展、个人化，先让自己用起来舒服，再考虑对外发布。

## 3. 版本规划

| 版本 | 目标 | 周期 |
|---|---|---|
| **v0.1 核心闭环** | 能处理 RSS/链接中的视频，自动总结归档到 Obsidian，并通知飞书 | 1-2 周 |
| **v0.2 热点监控 + 知识去重** | 增加 AI 新闻、论文、GitHub、社交媒体采集；与知识库比对去重和查漏补缺 | 2-3 周 |
| **v0.3 看板与多端** | Web 看板、macOS 状态栏、手机快捷指令、浏览器扩展 | 3-4 周 |
| **v0.4 智能** | Agent 知识库问答、热度归因、个性化推荐 | 长期 |

---

## 4. v0.1 核心需求

### 4.1 视频下载与处理

| 需求项 | 描述 | 优先级 |
|---|---|---|
| 链接解析 | 支持 YouTube / B 站 / 抖音 / Twitter 等主流平台（基于 yt-dlp） | P0 |
| 视频下载 | 调用 yt-dlp + FFmpeg 下载音视频 | P0 |
| 语音转文字 | 提取音频并生成字幕/逐字稿（Whisper / 平台字幕） | P0 |
| AI 视频总结 | 生成内容摘要、关键时间戳 | P0 |
| 元数据提取 | 标题、作者、时长、发布时间、原始链接 | P0 |

### 4.2 RSS 订阅采集

| 需求项 | 描述 | 优先级 |
|---|---|---|
| RSS 源管理 | 添加、编辑、删除 RSS/Atom 订阅源 | P0 |
| 自动同步 | 定时拉取 RSS，解析出文章和视频链接 | P0 |
| 视频链接识别 | 自动判断 RSS 条目中的链接是否为视频 | P0 |
| 自动处理 | 识别到视频后自动进入下载总结流程 | P1 |

### 4.3 知识库归档

| 需求项 | 描述 | 优先级 |
|---|---|---|
| Obsidian 归档 | 将视频总结、字幕、原始链接写入 Obsidian 指定文件夹 | P0 |
| Markdown 模板 | 生成统一的归档笔记格式 | P0 |
| 本地文件导出 | 同时保存视频文件、字幕文件到本地目录 | P1 |

### 4.4 通知

| 需求项 | 描述 | 优先级 |
|---|---|---|
| 飞书推送 | 处理完成后通过飞书机器人推送摘要和链接 | P0 |
| 处理失败通知 | 下载或总结失败时通知用户 | P1 |

### 4.5 命令行入口

| 需求项 | 描述 | 优先级 |
|---|---|---|
| 视频提取命令 | `aipulse video extract "https://..."` | P0 |
| RSS 同步命令 | `aipulse rss sync` | P0 |
| 配置管理命令 | `aipulse config` 设置 Obsidian 路径、飞书 Webhook 等 | P0 |
| 服务启动命令 | `aipulse server` 启动后端 API | P1 |

### 4.6 macOS 状态栏（v0.1 增强）

| 需求项 | 描述 | 优先级 |
|---|---|---|
| 状态栏图标 | 常驻菜单栏 | P1 |
| 粘贴链接处理 | 点击图标 → 输入/粘贴链接 → 提交后端处理 | P1 |
| 处理进度展示 | 显示当前任务状态（下载中 / 转写中 / 已完成） | P1 |
| 快捷入口 | 一键打开 Obsidian 归档文件夹 | P2 |

### 4.7 不进入 v0.1 的功能

以下功能明确放到后续版本，避免第一版范围膨胀：
- AI 新闻站点采集
- GitHub Trending 采集
- 论文与模型发布采集
- 热点聚合与去重
- 每日摘要生成
- Web 看板
- 关键词监控
- Agent 知识库问答
- iOS App / 快捷指令
- 浏览器扩展
- 微信 / 邮件 / Notion 推送
- 知识库去重与查漏补缺（v0.2 引入）

---

## 5. v0.2 热点监控需求

### 5.1 多源数据采集

| 需求项 | 描述 | 优先级 |
|---|---|---|
| AI 新闻站点采集 | 机器之心、量子位、TechCrunch AI 等 | P0 |
| 论文与模型发布采集 | arXiv、Hugging Face | P0 |
| GitHub Trending 采集 | AI 相关仓库热度 | P0 |
| 社交媒体采集 | Twitter/X、Reddit、知乎、即刻 | P1 |
| 融资动态采集 | Crunchbase、IT桔子 | P2 |

### 5.2 热点处理

| 需求项 | 描述 | 优先级 |
|---|---|---|
| 数据清洗 | 去除广告、垃圾内容 | P0 |
| 去重与聚合 | 相似内容合并为同一热点事件 | P0 |
| 热度评分 | 基于来源权重、互动量、时间衰减计算 | P0 |
| AI 摘要 | 生成中文摘要 | P0 |
| 可信度分析 | 判断真实性，排除标题党 | P1 |
| 重要性分级 | 低 / 中 / 高 / 紧急 | P1 |
| 主题分类 | LLM / Agent / 多模态 / 评测 / 产品 / 融资 | P1 |

### 5.3 每日摘要

| 需求项 | 描述 | 优先级 |
|---|---|---|
| 每日热点摘要 | 自动生成「今日 AI 热点」Markdown | P0 |
| 定时推送 | 每日固定时间推送到飞书 | P0 |
| 关键词监控 | 添加关注关键词，高相关热点优先展示 | P1 |

### 5.4 Web 看板

| 需求项 | 描述 | 优先级 |
|---|---|---|
| 热点时间线 | 按时间倒序展示热点 | P0 |
| 搜索与筛选 | 按关键词、来源、重要性、时间范围筛选 | P0 |
| 热点详情 | 展示摘要、多源链接 | P1 |
| 关键词管理页 | 添加、编辑、删除关键词 | P1 |
| 响应式适配 | 兼容桌面与移动端 | P1 |

### 5.5 知识库去重与查漏补缺

> 详见 `docs/knowledge-base-deduplication.md`

| 需求项 | 描述 | 优先级 |
|---|---|---|
| URL 去重 | 同一链接直接跳过，避免重复处理 | P0 |
| 语义相似度比对 | 把新热点/视频摘要向量化，和已有笔记计算余弦相似度 | P0 |
| LLM 关系判断 | 让 LLM 判断新信息与 top-k 相关笔记的关系：重复 / 补充 / 全新 | P0 |
| 增量归档策略 | 重复：跳过；补充：追加到原笔记；全新：创建新笔记 | P0 |
| 归档标签 | 给笔记打上 `duplicate` / `supplement` / `new` 标签 | P1 |
| 知识缺口识别 | 分析新信息填补了哪些已有知识空白，生成提示 | P1 |
| 双向链接 | 新笔记自动链接到相关旧笔记 | P2 |

---

## 6. v0.3 多端与快捷指令需求

### 6.1 iOS 快捷指令方案

| 需求项 | 描述 | 优先级 |
|---|---|---|
| 快捷指令接收 URL | 通过 Safari 分享表单获取当前页面 URL | P0 |
| 调用 AIPulse API | 将 URL 发送到后端 `POST /api/videos/extract` | P0 |
| 悬浮球触发 | 用户可将快捷指令绑定到 AssistiveTouch 菜单/手势 | P0 |
| 处理完成通知 | 通过 iOS 通知或飞书告知用户 | P1 |

### 6.2 手机 App

| 需求项 | 描述 | 优先级 |
|---|---|---|
| 分享扩展 | App 出现在 iOS 分享菜单中，一键发送链接 | P1 |
| 处理进度查看 | 查看正在处理和已归档的视频 | P1 |
| 热点浏览 | 查看每日 AI 热点摘要 | P2 |
| URL Scheme | `aipulse://extract?url=xxx` | P1 |

### 6.3 浏览器扩展

| 需求项 | 描述 | 优先级 |
|---|---|---|
| 右键归档 | 右键视频/文章页面，选择"归档到 AIPulse" | P2 |
| 一键总结 | 在浏览器中直接显示总结浮窗 | P2 |

---

## 7. v0.4 智能需求

| 需求项 | 描述 | 优先级 |
|---|---|---|
| 本地知识库问答 | 基于归档内容回答用户提问 | P0 |
| 热点趋势追问 | 对话式追问热点背景、影响、相关事件 | P1 |
| 热度归因 | 分析热点爆发原因 | P2 |
| 个性化推荐 | 根据关注关键词推荐内容 | P2 |
| 周报/月报 | 按主题自动生成报告 | P2 |

---

## 8. 非功能需求

### 8.1 性能要求
- 视频下载 + 转写 + 总结：10 分钟视频 < 5 分钟处理（依赖网络和模型）
- RSS 同步：100 个订阅源 < 2 分钟
- API 响应时间 < 1s

### 8.2 可用性要求
- 7x24 小时稳定运行
- 爬虫/下载频率可控，避免被封
- 任务失败可重试，错误可观测

### 8.3 安全要求
- API Key、Token 等敏感信息通过环境变量管理
- 不硬编码任何密钥
- 错误日志不暴露敏感信息

### 8.4 可扩展性要求
- 采集器、处理器、推送渠道均插件化
- 新数据源可通过统一接口接入
- 新推送渠道可通过配置扩展

---

## 9. 技术架构

### 9.1 推荐技术栈

| 层级 | 技术选型 | 说明 |
|---|---|---|
| 语言 | Python 3.11+ | 数据采集与后端主力语言 |
| Web 框架 | FastAPI | 轻量、现代、异步友好 |
| 数据库 | SQLite（起步）/ PostgreSQL（进阶） | 初期轻量，后续可迁移 |
| ORM | SQLAlchemy 2.0 + Alembic | 数据库模型与迁移 |
| 任务调度 | APScheduler / Celery + Redis | 定时采集与异步任务 |
| 爬虫 | httpx + parsel / BeautifulSoup / Playwright | 静态 + 动态页面 |
| 视频下载 | yt-dlp + FFmpeg | 1800+ 平台视频下载与处理 |
| 语音转写 | Whisper / yt-dlp 字幕 | 生成逐字稿 |
| LLM | OpenRouter / OpenAI / 本地模型 | 摘要、分析、问答 |
| 向量数据库 | Chroma / Qdrant（可选） | 知识库语义检索 |
| 前端 | 纯静态 HTML + HTMX / Next.js / Vue | vibe 决定 |
| 桌面端 | Tauri / Swift（macOS 状态栏） | 状态栏应用 |
| 移动端 | React Native / Flutter（可选） | 手机 App |
| 部署 | Docker / Railway / 个人服务器 | |

### 9.2 v0.1 项目结构

```
AIPulse/
├── README.md
├── LICENSE
├── pyproject.toml
├── .env.example
├── config/
│   ├── config.yaml           # 通用配置
│   └── rss.yaml              # RSS 订阅配置
├── src/
│   ├── cli.py                # 命令行入口
│   ├── server.py             # FastAPI 服务（v0.1 可选）
│   ├── rss/                  # RSS 解析与同步
│   ├── video/                # 视频下载、转写、总结
│   ├── summarizers/          # AI 摘要
│   ├── archive/              # 知识库归档（Obsidian）
│   ├── pushers/              # 飞书推送
│   ├── store/                # 数据存储（SQLite）
│   └── desktop/              # macOS 状态栏（v0.1 增强）
├── tests/                    # 测试
└── docs/                     # 设计文档
```

### 9.3 v0.1 数据流

```
用户输入链接 / RSS 更新
    ↓
链接识别：视频 / 文章
    ↓
视频下载（yt-dlp + FFmpeg）
    ↓
语音转文字（Whisper / 字幕）
    ↓
AI 总结（LLM）
    ↓
存储（SQLite）
    ↓
归档到 Obsidian
    ↓
飞书推送通知
```

---

## 10. 数据模型（v0.1）

```python
class RssFeed:
    """RSS 订阅源"""
    id: str
    name: str
    url: str
    check_interval_minutes: int
    is_active: bool
    last_fetched_at: datetime
    created_at: datetime

class RssEntry:
    """RSS 条目"""
    id: str
    feed_id: str
    title: str
    url: str
    content_type: str     # article / video / unknown
    is_processed: bool
    published_at: datetime
    fetched_at: datetime

class VideoSummary:
    """视频总结记录"""
    id: str
    title: str
    original_url: str
    local_video_path: str
    subtitle_path: str
    transcript: str
    summary: str
    key_moments: list     # [{timestamp, title}]
    source: str           # rss / manual / menubar
    status: str           # pending / downloading / transcribing / summarizing / done / failed
    archived: bool
    created_at: datetime
    updated_at: datetime

class ArchiveEntry:
    """知识库归档记录"""
    id: str
    target_id: str
    target_type: str      # video_summary
    destination: str      # obsidian / local
    destination_path: str
    archived_at: datetime
```

---

## 11. 接口设计（v0.1）

### 11.1 RESTful API

```
# RSS 管理
GET    /api/rss
POST   /api/rss
PUT    /api/rss/{id}
DELETE /api/rss/{id}
POST   /api/rss/sync

# 视频处理
POST   /api/videos/extract       # 提交链接
GET    /api/videos               # 列表
GET    /api/videos/{id}
POST   /api/videos/{id}/retry    # 失败重试

# 归档
POST   /api/videos/{id}/archive

# 配置
GET    /api/settings
PUT    /api/settings
```

### 11.2 CLI 命令

```bash
# 视频提取
aipulse video extract "https://www.youtube.com/watch?v=xxx"

# RSS 同步
aipulse rss sync
aipulse rss add --name "AI 博客" --url https://example.com/feed.xml

# 配置
aipulse config set obsidian.vault_path /Users/xxx/Obsidian
aipulse config set feishu.webhook_url https://open.feishu.cn/...

# 启动服务
aipulse server

# 启动状态栏（macOS）
aipulse menubar
```

### 11.3 iOS 快捷指令配置（v0.3 预览）

快捷指令步骤：
1. **从共享表单接收** → 选择 **URL**
2. **从输入中获取 URL**
3. **获取 URL 的内容** 或 **获取剪贴板**
4. **获取 URL 的内容** 使用 POST 请求到 `https://your-aipulse/api/videos/extract`
5. 显示通知："已提交 AIPulse 处理"

悬浮球绑定：
- 设置 → 辅助功能 → 触控 → 辅助触控
- 自定义顶层菜单或手势，选择该快捷指令

---

## 12. 验收标准

### v0.1 功能验收
- [ ] 能添加、编辑、删除 RSS 订阅源
- [ ] 能手动输入视频链接并自动下载
- [ ] 能生成视频字幕和中文总结
- [ ] 能将总结归档到 Obsidian 指定文件夹
- [ ] 能在处理完成后收到飞书通知
- [ ] 失败任务能重试并通知
- [ ] macOS 状态栏能输入链接并提交处理

### v0.1 代码验收
- [ ] 测试覆盖率 ≥ 80%
- [ ] 无硬编码密钥
- [ ] 关键路径有错误处理和日志

---

## 13. Roadmap

### v0.1 核心闭环（1-2 周）
- [ ] 项目结构与数据模型
- [ ] yt-dlp 视频下载模块
- [ ] Whisper 转写模块
- [ ] LLM 视频总结
- [ ] Obsidian 归档
- [ ] 飞书推送
- [ ] RSS 订阅解析
- [ ] CLI 命令行
- [ ] macOS 状态栏（增强）

### v0.2 热点监控（2-3 周）
- [ ] AI 新闻采集
- [ ] GitHub Trending 采集
- [ ] 论文与模型采集
- [ ] 热点聚合与去重
- [ ] 每日摘要生成
- [ ] Web 看板

### v0.3 多端与快捷指令（3-4 周）
- [ ] iOS 快捷指令
- [ ] iPhone App 分享扩展
- [ ] 浏览器扩展
- [ ] 微信 / 邮件 / Notion 推送扩展

### v0.4 智能（长期）
- [ ] Agent 知识库问答
- [ ] 热度归因
- [ ] 个性化推荐
- [ ] 插件市场
