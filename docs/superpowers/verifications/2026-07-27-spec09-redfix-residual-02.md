# spec09 残留修复 02：SSE not-found 行为统一

日期：2026-07-27
角色：worker 自检（最终结论由独立 verifier 给出）

## 修复范围

统一以下两条不存在记录路径：

- `GET /api/summary/events?bvid=<不存在>`
- `GET /api/summary/events/<job_id不存在>`

两者现在均返回：

- HTTP `200 OK`
- `Content-Type: text/event-stream`
- 首事件 `event: error`
- payload 中 `error: not_found`

query 路径 payload 使用 `video_id`，path 路径使用 `job_id`，保留各入口的标识语义。

## RED 证据

新增集成测试：

```text
test_sse_not_found_returns_error_event_for_query_and_job_path
```

命令：

```bash
uv run pytest tests/integration/test_summary_api.py::test_sse_not_found_returns_error_event_for_query_and_job_path --no-cov -q
```

修复前失败：

```text
assert 404 == 200
FAILED tests/integration/test_summary_api.py::test_sse_not_found_returns_error_event_for_query_and_job_path
1 failed
```

真实 8000 后端修复前 curl：

```text
/events?bvid=missing-sse-job      -> 404 application/json
/events/missing-sse-job           -> 200 text/event-stream + event:error
```

## GREEN 证据

新增测试：

```text
1 passed in 0.07s
```

Summary API 集成测试：

```bash
uv run pytest tests/integration/test_summary_api.py --no-cov -q
```

结果：

```text
7 passed in 1.66s
```

## 真实后端 curl

重启当前主 checkout 的真实 AIPulse 后端后验证：

```text
GET /api/summary/events?bvid=missing-sse-job
HTTP/1.1 200 OK
content-type: text/event-stream; charset=utf-8

event: error
data: {"video_id": "missing-sse-job", "error": "not_found"}
```

```text
GET /api/summary/events/missing-sse-job
HTTP/1.1 200 OK
content-type: text/event-stream; charset=utf-8

event: error
data: {"job_id": "missing-sse-job", "error": "not_found"}
```

后端日志：`/tmp/aipulse-backend-task2.log`

## 真浏览器验证

使用 `mcp__playwright` 直接打开真实 SSE URL：

1. `http://127.0.0.1:8000/api/summary/events?bvid=missing-sse-job`
   - Network: `[GET] ... => [200] OK`
   - 页面文本：`event: error data: {"video_id": "missing-sse-job", "error": "not_found"}`
   - 截图：`docs/superpowers/verifications/2026-07-27-spec09-redfix-residual-02-query.png`
2. `http://127.0.0.1:8000/api/summary/events/missing-sse-job`
   - Network: `[GET] ... => [200] OK`
   - 页面文本：`event: error data: {"job_id": "missing-sse-job", "error": "not_found"}`
   - 截图：`docs/superpowers/verifications/2026-07-27-spec09-redfix-residual-02-path.png`

## 代码审查

精确 diff 交由独立 `code-reviewer` 复核，结论：

```text
CRITICAL 0
HIGH 0
Verdict: APPROVE
```

审查同时核实：

- `summary_events_route` 是 `async def`，query 路径的 `await` 调用正确。
- path not-found 分支的 `finally` 会调用 `queue.unsubscribe`；最后一个订阅者移除后 `_subscribers.pop(job_id)`，不存在订阅泄漏。
- 一次性 async generator 是 `EventSourceResponse` 的合法输入。

统一审查记录：`docs/superpowers/verifications/2026-07-27-spec09-redfix-residual-code-review.md`

## 自检边界

- 未 mock 后端；curl 与浏览器均访问真实 uvicorn。
- 未写入或 reset 真实 DB；任务 2 仅查询不存在记录。
- 未读取、修改 `.env`、`data/settings.json` 或 secret。
- 未改变已存在 job 的 SSE 流程。
