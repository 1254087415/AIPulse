# spec09 残留修复代码审查记录

日期：2026-07-27
范围：任务 1 UID 正则字符集、任务 2 SSE not-found 行为统一

## 任务 1

文件：

- `frontend/src/components/follow-list-panel/AddFollowForm.vue`
- `frontend/tests/unit/add-follow-form-url.test.ts`

审查结果：0 CRITICAL。初次 reviewer 给出的两项 HIGH 均建议把 URL 端重新收紧为纯数字或改测裸 UID，但这会直接违背明确验收输入 `space.bilibili.com/123_456`，且 reviewer 引用了过期的 `\d+` 基线；当前后端 UID schema 支持该字符集。因此这些建议不适用于本任务。

保留的非阻塞建议：未来独立处理 URL host 锚定与 query/path 边界，不与本次最小字符集修复捆绑。

## 任务 2

文件：

- `src/aipulse/api/summary.py`
- `tests/integration/test_summary_api.py`

初次隔离 worktree 审查无法看到未提交 diff；Python reviewer 因把 `async def summary_events_route` 当作普通函数，误报 `await` TypeError，并误报订阅泄漏。

父 worker 复核：

- `summary_events_route` 是 `async def`，必须 `await` 才能取得 `EventSourceResponse`。
- `queue.unsubscribe` 会在最后订阅者移除后执行 `_subscribers.pop(job_id, None)`。
- pytest、真实 uvicorn curl、Playwright 两条 URL 均实际得到 `200 + event:error`。

随后把精确生产/测试 diff与以上事实交给新的独立 code-reviewer；最终有效审查结果：

```text
CRITICAL 0
HIGH 0
MEDIUM 1（一次性 async generator 无 await，不影响合法性）
LOW 2（字符串断言与 SSE dict 风格建议）
Verdict: APPROVE
```

## 结论边界

本记录仅是 worker 的代码审查材料，不替代主会话派出的独立 verifier，也不自报最终 GREEN/RED 结论。
