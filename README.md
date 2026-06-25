# AIPulse

> 感知 AI 领域的实时脉搏。

AIPulse 是一个开源的 AI 热点监控项目，通过聚合新闻、论文、GitHub 趋势、社交媒体和模型发布等多源信息，帮助关注 AI 的人快速了解当下最值得关注的技术、产品和话题。

## 为什么叫 AIPulse？

- **Pulse（脉搏）**：热点像脉搏一样持续跳动，项目希望捕捉这种节奏。
- **短而有力**：3 个音节，repo 名干净（`aipulse`），好读好记。
- **开源友好**：不带有太强的商业产品感，适合作为个人 vibe coding 项目。

## 项目定位

- **目标用户**：AI 从业者、研究者、开发者、技术观察者。
- **核心目标**：让人每天花 5 分钟就能知道 AI 领域发生了什么值得关心的事。
- **风格**：轻量、可扩展、个人化，先让自己用起来舒服，再考虑对外发布。

## 核心功能

1. **多源数据采集**
   - AI 新闻站点
   - arXiv / Hugging Face 论文与模型发布
   - GitHub Trending
   - 社交媒体讨论（如 Twitter/X、Reddit、知乎等）

2. **热点聚合与去重**
   - 按主题聚合相似内容
   - 去重与热度排序

3. **每日摘要生成**
   - 自动生成「今日 AI 热点」摘要
   - 支持多种输出格式（Markdown、JSON、邮件、Webhook）

4. **可自定义关注列表**
   - 用户可配置感兴趣的关键词、模型、公司或领域

5. **简单的 Web 看板**（可选）
   - 展示当前热点时间线
   - 支持搜索与筛选

## 推荐技术栈

- **语言**：Python（数据采集 + 后端）
- **数据库**：SQLite 起步，后续可迁移到 PostgreSQL
- **任务调度**：APScheduler / Celery
- **前端**：纯静态页面 或 Next.js / Vue（vibe 决定）
- **LLM**：用于摘要生成与主题聚类
- **部署**：Docker / Railway / 个人服务器

## 项目结构

```
AIPulse/
├── README.md
├── LICENSE
├── pyproject.toml
├── .env.example
├── src/
│   ├── collectors/      # 各数据源采集器
│   ├── processors/      # 清洗、去重、聚类
│   ├── summarizers/     # 摘要生成
│   ├── store/           # 数据存储
│   ├── web/             # Web 看板
│   └── cli.py           # 命令行入口
├── config/              # 配置文件
├── tests/               # 测试
└── docs/                # 设计文档
```

## 快速开始

待定。项目处于 vibe coding 早期，先跑通第一个数据采集器再说。

##  Roadmap

- [ ] 设计数据模型
- [ ] 实现第一个新闻采集器
- [ ] 实现 GitHub Trending 采集器
- [ ] 添加基础去重与热度评分
- [ ] 生成第一份每日摘要
- [ ] 搭建最小可用 Web 看板

## License

MIT
