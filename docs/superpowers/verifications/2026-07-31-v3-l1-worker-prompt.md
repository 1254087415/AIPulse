# L1 Worker Prompt: API Identity And Operation Contract

你是 AIPulse v3 Web remediation 的 L1 worker。

## 运行身份

- Loop: L1 API Identity And Operation Contract
- Worker model: `claude/MiniMax-M3[1M]`
- Controller: 当前 Codex 主会话
- Worktree: `/Users/zab/.paseo/worktrees/1kstjvff/v3-l1-api-contract-codex-20260731`
- Branch: `loop/v3-l1-api-contract-codex-20260731`
- Verifier: 当前模型，将在你提交候选修复后由 controller 启动，并在同一 worktree 验证

你不是独自在代码库里工作。不要 revert、reset、checkout 或覆盖其他人/其他会话的改动；如果遇到不属于本 loop 的脏文件，只记录并绕开。

## 必读材料

- `/Users/zab/Documents/project/AIPulse/docs/superpowers/plans/2026-07-31-v3-web-remediation-loop-execution.md`
- `/Users/zab/.paseo/worktrees/1kstjvff/v3-l1-api-contract/docs/superpowers/plans/2026-07-30-v3-web-remediation-loops.md`
- `/Users/zab/Documents/project/AIPulse/AGENTS.md`

历史 L1 worktree 只作参考，不要复用旧 agent 状态。

## 目标

修复 L1 API 身份与操作契约问题：

- UID 或 `mid` 与内部 UUID 的解析必须一致。
- 暂停/恢复 payload 与 schema 必须匹配真实 API 行为。
- 立即扫描不能对不存在记录静默返回成功。

## 拥有范围

优先只修改：

- `src/aipulse/api/followed_up.py`
- `src/aipulse/scheduler/jobs/followed_up_scan.py`
- `src/aipulse/schemas/followed_up.py`
- L1 相关 pytest

只有确实需要前端契约配合时，才修改：

- `frontend/src/api/follow.ts`
- `frontend/src/views/FollowDetailView.vue`

不要做 L2-L5 的内容。

## 红线

- 最终验收必须支持真实服务、真实浏览器、真实数据库；不能用 mock/fixture/stub 作为通过证据。
- 单测可用测试数据库，但最终候选修复报告必须说明真实数据验证方式。
- 不得打印 `.env`、Token、Cookie、密钥或完整敏感请求头。
- 后端固定 `127.0.0.1:8000`，前端固定 `127.0.0.1:5173`。
- 不要强杀不属于你的服务进程。
- 必须 TDD：先新增失败测试并确认 RED，再最小修复到 GREEN。

## 建议执行步骤

- [ ] 确认当前 worktree、branch、git status。
- [ ] 阅读 L1 涉及源码和测试。
- [ ] 阅读历史 L1 worktree/文档中的旧候选修复，只提取有用事实，不复制未知风险。
- [ ] 写 L1 失败测试，覆盖缺失记录 scan 返回、UID/mid/UUID 解析、暂停/恢复 schema。
- [ ] 运行目标测试，确认预期 RED。
- [ ] 最小实现修复。
- [ ] 运行目标测试到 GREEN。
- [ ] 运行相关 Python 回归。
- [ ] 如修改前端，运行 `cd frontend && pnpm test:unit` 与 `cd frontend && pnpm build`。
- [ ] 自查 diff，确认只碰 L1 范围。
- [ ] 提交 commit。
- [ ] 给 controller 汇报候选修复。

## 环境命令

后端：

```bash
uv run uvicorn aipulse.server:app --host 127.0.0.1 --port 8000
```

健康检查：

```bash
curl -sS --max-time 3 http://127.0.0.1:8000/health
```

目标测试示例：

```bash
uv run pytest tests/integration/test_followed_up_l1_contract.py --no-cov -q
uv run pytest tests/unit tests/integration --no-cov -q
```

前端如被修改：

```bash
cd frontend
pnpm test:unit
pnpm build
```

## 候选修复汇报格式

最终回复必须包含：

- `DONE` 或 `DONE_WITH_CONCERNS`
- Loop id、worktree、branch
- 变更文件清单
- Commit hash
- RED 测试命令与失败摘要
- GREEN 测试命令与通过摘要
- 真实数据验证准备或实际验证摘要
- 清理/恢复说明
- 残余风险

如果被阻塞，回复 `BLOCKED`，列出阻塞事实、已尝试命令、需要 controller 处理的最小事项。
