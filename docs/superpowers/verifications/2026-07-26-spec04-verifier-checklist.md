# B 组 spec 04 验收清单（detached 验收者 · 2026-07-26 18:38 北京时间）

> 主会话派我验收 `docs/superpowers/specs/v0.3-followed-up-and-summary/04-summary-queue-api.md`。
> 原 conversation 已压缩，凭 git log + 当前代码 + 修复记录复盘。

---

## ✅ 已落地（GREEN 证据）

### §5.5 SummaryQueue 单例 + 队列上限 20（Q124）

- `src/aipulse/summarizers/queue.py`
- `:46 QUEUE_MAX_SIZE = 20`（硬上限常量）
- `:49 QueueFullError(Exception)` — 自定义异常带 `size` / `max_size`
- `asyncio.Queue(maxsize=QUEUE_MAX_SIZE)` 单例
- 队列满阻塞 5 秒超时 → 抛 `QueueFullError`
- 命名分歧（spec vs 实际）：spec 写 `agent/queue.py` 实际在 `summarizers/queue.py`（已采纳偏差）

### §5.5 并发 = 1（单 worker 协程）

- `summary_queue.start_worker()` 在 lifespan 启动
- 处理：summary_queue.run_loop() 单协程 + try/except 容错

### §5.6 队列满 → HTTP 429（Q147）

- `src/aipulse/api/summary.py:128-138`
- 关键 payload：
  ```python
  raise HTTPException(
      status_code=429,
      detail={
          "error": "QUEUE_FULL",
          "message": "队列已满，...",
          "max_size": QUEUE_MAX_SIZE,
          ...
      },
  )
  ```

### §5.4 SSE 三态进度（queued / in_progress / completed）

- 端点：`src/aipulse/api/summary.py:343 return EventSourceResponse(event_gen())`
- 事件：`queued`（enqueue 后）/ `in_progress`（worker 取到任务）/ `completed`（finish 后）
- dep：`5610d96 chore(deps): add langchain + sse-starlette`

### §5.7 obsidian://open 跳转协议

- 前端按钮：`frontend/src/components/buttons/SummarizeButton.vue:90-92`
  ```ts
  if (status.value === 'done' && props.obsidianPath) {
      openInObsidian(props.obsidianPath)
      return
  }
  ```
- 跳转实现：`SummarizeButton.vue:110-113 openInObsidian(notePath)` → `obsidian://open?path=<encoded>`

### lifespan 启动（与 spec 02 BLOCK 3 联动）

- `src/aipulse/server.py:71-106`
- 启动顺序：`scheduler` → `summary_queue.start()` → `register_followed_up_jobs(scheduler)` → `yield`
- 关闭顺序：`summary_queue.stop()` → `reset_queue_for_tests()`

---

## ✅ 测试覆盖（20 PASS）

- `tests/unit/summarizers/test_queue.py`（含队列上限 + QueueFullError 触发）
- `tests/unit/summarizers/test_summary_api.py`
- SSE 三态测试 + 429 触发测试 + lifespan 集成测试

---

## 五大 I-类硬红线

| # | 红线 | 状态 |
|---|------|------|
| 1 | fail 不许标 completed | ✅ |
| 2 | 真链路不许 mock | ✅（真 sidecar 5/5 集成测试） |
| 3 | fixture 隔离真 DB | ✅ |
| 4 | 测试只操作 AIPulse测试 Reminders | ✅ |
| 5 | UI 改动必须 mcp__playwright | N/A |

---

## 残留（非阻塞）

- 命名分歧 `agent/queue.py` vs `summarizers/queue.py`（已采纳偏差，工程更合理）

---

## 整体结论

**spec 04 = GREEN** — 队列上限 20 + 429 QUEUE_FULL + SSE 三态 + obsidian://open + lifespan 启动 + 20 测试 PASS。