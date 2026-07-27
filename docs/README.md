# AIPulse 文档索引

本文档汇总 AIPulse 项目的设计文档和需求文档。

## 文档列表

| 文档 | 说明 |
|---|---|
| [AIPulse需求文档v0.1.md](./AIPulse需求文档v0.1.md) | 项目整体需求，按 v0.1 ~ v0.4 拆分 |
| [knowledge-base-deduplication.md](./knowledge-base-deduplication.md) | 知识库去重与查漏补缺方案（v0.2） |
| [v0.1-implementation-plan.md](./v0.1-implementation-plan.md) | v0.1 实现计划：独立 Tauri app + Python sidecar |

## 版本速览

- **v0.1 核心闭环**：视频下载 → 转写 → 总结 → 归档 Obsidian → 飞书通知
- **v0.2 热点监控 + 知识去重**：多源采集、热点聚合、知识库去重与查漏补缺
- **v0.3 看板与多端**：Web 看板、macOS 状态栏、iOS 快捷指令、浏览器扩展
- **v0.4 智能**：Agent 问答、热度归因、个性化推荐
