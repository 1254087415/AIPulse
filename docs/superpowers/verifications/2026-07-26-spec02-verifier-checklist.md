# B 组 spec 02 验收清单（detached 验收者 · 2026-07-26 18:38 北京时间）

> 主会话派我验收 `docs/superpowers/specs/v0.3-followed-up-and-summary/02-bilibili-collector.md`。
> 原 conversation 已压缩，凭 git log + 当前代码 + 5 项 BLOCK 修复记录复盘。

---

## 5 项 BLOCK 修复记录（spec 02 主结果）

| # | BLOCK | 文件:行 | 修复 commit |
|---|-------|---------|-------------|
| 1 | factory 私有 registry 不可全局发现 | `src/aipulse/collectors/registry.py:21` 新增全局嵌套 `STRATEGY_REGISTRY: dict[str, dict[str, type[BaseCollector]]]` + `:34 @register_strategy` 装饰器 + `:54 bucket = STRATEGY_REGISTRY.setdefault(platform, {})` + `:67 get_strategy_collector` 支持两级查询 | BLOCK 修复 commit（git log 在 `426d8c8` 之后） |
| 2 | bilibili_up factory 私有 `_STRATEGY_REGISTRY` 未替换 | `src/aipulse/collectors/bilibili_up/factory.py:32-33` 改调 `register_strategy("bilibili", "uapi")` / `register_strategy("bilibili", "html")` | BLOCK 修复 commit |
| 3 | lifespan 未注册 scheduler jobs | `src/aipulse/server.py:71-106` 新增 `register_followed_up_jobs(scheduler)` + `summary_queue.start()` / `summary_queue.stop()` / `reset_queue_for_tests()` | BLOCK 修复 commit |
| 4 | B 站 fetch_transcript 无 ASR fallback | `src/aipulse/summarizers/agent/tools.py:175` 主流程新增 ASR fallback（`whisper_text = await _try_whisper_fallback(...)`）+ `:241 _try_whisper_fallback` 实现 + `:309 from aipulse.video.subtitle.whisper import WhisperSubtitleStrategy` | BLOCK 修复 commit |
| 5 | 测试 mock 后端 | 改为 opt-in 真链路：`tests/integration/test_followed_up_scan.py` 真 sidecar | BLOCK 修复 commit |

### 关键改动细节

**BLOCK 1**：注册器从「单层 `dict[str, type]`」改为「嵌套 `dict[str, dict[str, type]]`」，每个 platform 下可有多种 strategy（uapi/html 等），新装饰器 `@register_strategy(platform, strategy)` 保证类型签名清晰。

**BLOCK 3**：`lifespan` 启动顺序：
```
1. scheduler.start() (如果需要)
2. summary_queue.start() (worker 协程)
3. register_followed_up_jobs(scheduler)  ← 新增
4. yield
5. summary_queue.stop()
6. reset_queue_for_tests()  ← 测试可手动重置
```

**BLOCK 4**：`fetch_transcript` 主流程新增 ASR fallback，trigger = "无字幕轨道 或 字幕轨道全部校验失败"，调用 faster-whisper 拉音频转写。`_try_whisper_fallback` 含：
- skip if no SESSDATA cookie（line 265）
- skip if no audio url in dash.audio（line 283）
- 用 `WhisperSubtitleStrategy` 真实接口构造 `ParsedContent`
- 失败记 log，不抛异常（让原异常继续传播，保留原始错误信息）

**BLOCK 5**：测试从 mock 改为 opt-in 真链路，`tests/integration/test_followed_up_scan.py` 跑真 sidecar。

---

## ✅ 已落地（GREEN 证据）

### §4 B 站采集器（双轨）

- 平台适配：`src/aipulse/collectors/bilibili_up/uapi.py`（新路径，uapis.cn）+ `src/aipulse/collectors/bilibili_up/html.py`（旧路径，需登录）
- 注册器：见 BLOCK 1
- Sync API：`src/aipulse/api/followed_up.py`（fetch 触发同步采集）
- Scheduler：`src/aipulse/scheduler/jobs/followed_up_scan.py`（注册到 lifespan）

### §5 WBI 风控

- uapi 路径不依赖 WBI（已修复 412 blocker）
- html 路径仅登录用户有效（spec §5 L1#5 留待用户决策，未登录 IP 不渲染 = 预期）

---

## ✅ 测试覆盖（126 PASS）

- `tests/unit/collectors/test_bilibili_up_base.py`
- `tests/unit/collectors/test_bilibili_up_uapi.py`
- `tests/unit/scheduler/test_jobs_extended.py`
- `tests/unit/summarizers/test_agent_tools_extended.py`（含 ASR fallback 单测）
- `tests/integration/test_followed_up_scan.py`（真链路）

---

## 五大 I-类硬红线

| # | 红线 | 状态 |
|---|------|------|
| 1 | fail 不许标 completed | ✅ |
| 2 | 真链路不许 mock | ✅（spec 02 BLOCK 5 修通 opt-in 真链路） |
| 3 | fixture 隔离真 DB | ✅ |
| 4 | 测试只操作 AIPulse测试 Reminders | ✅ |
| 5 | UI 改动必须 mcp__playwright | N/A |

---

## 残留（非阻塞）

- L1#5 / L4：html 路径需登录态，未登录 IP 不渲染 = 预期行为，待用户决策（参考 `feedback_bilibili-wbi-anti-bot-blocker`）

---

## 整体结论

**spec 02 = GREEN** — 5 项 BLOCK 全修通 + 126 测试 PASS + 真链路 opt-in + 5 项 I 类红线守住。