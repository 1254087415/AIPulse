# Paseo Loop 使用指南 · AIPulse v0.3

> 总结日期：2026-07-26
> 适用场景：v0.3 round 启动 worker + verifier 跑功能验证
> 经验教训：用户硬要求"Paseo UI 必须看到对话"

## TL;DR

**主会话只能 ↔ 验收者，验收者 ↔ worker。** 任何新创建的 agent 必须用 `paseo run -d` CLI（不用 MCP create_agent），否则用户在 Paseo UI 看不到对话。

---

## 1. 核心链路

```
┌─────────────────────────────────────────────────────────┐
│  主会话 d8cfc17b (Claude Code current session)            │
│  - 启动 verification round                                │
│  - 派任务给验收者 (mcp__paseo__send_agent_prompt)         │
│  - 收到验收者回执后认账                                    │
└────────────────────┬────────────────────────────────────┘
                     │ mcp__paseo__send_agent_prompt
                     ▼
┌─────────────────────────────────────────────────────────┐
│  验收者 (detached, Paseo UI 可见)                          │
│  - 读 spec / plan / 现状勘察                              │
│  - 写 B 组验收清单                                        │
│  - 派 worker 跑实现 (paseo run -d)                        │
│  - 独立复验 worker 产物                                   │
│  - 回执 send 主会话                                       │
└────────────────────┬────────────────────────────────────┘
                     │ paseo run -d (detached worker)
                     ▼
┌─────────────────────────────────────────────────────────┐
│  Worker (detached, Paseo UI 可见)                          │
│  - 读任务清单 (验收者派发的)                                │
│  - 改代码 + 跑单测 + 跑真链路                              │
│  - send 验收者 (不能 send 主会话!)                        │
└────────────────────┬────────────────────────────────────┘
                     │ 修完 send
                     ▼
              回到验收者独立复验
```

---

## 2. 创建方式对比（关键）

### ❌ `mcp__paseo__create_agent`（标 internal，UI 不可见）

```python
mcp__paseo__create_agent({
    "relationship": {"kind": "detached"},   # 或者 subagent
    "workspace": {"kind": "current", "cwd": "..."},
    "title": "...",
    "provider": "claude/claude-fable-5",
    "initialPrompt": "..."
})
```

**问题**：无论 `subagent` 还是 `detached` 标签，Paseo UI 都**只显示 finished 通知，看不到对话详情**。用户无法监督进度。

### ✅ `paseo run -d` CLI（detached，UI 完全可见，B 组验证过）

```bash
paseo run -d \
  --provider claude \
  --model claude-fable-5 \
  --title "v0.3 验收者 · claude-fable-5" \
  --cwd /Users/zab/Documents/project/AIPulse \
  --mode bypassPermissions \
  --label role=verifier \
  --label round=B \
  --label spec=01 \
  '<完整 prompt>'
```

**优势**：
- Paseo UI 显示完整对话（包括 tool 调用、推理、最终回执）
- 用户能实时监督进度
- detached = 顶层 root agent，不会被主会话 archive 链影响
- **走主 checkout** = 用户当前分支直接干活，commit 进主分支

### 可选 `--worktree <slug>`（仅需要隔离分支测试时）

```bash
paseo run -d --worktree verifier-spec09 \
  ... 其他参数同上
```

**何时用**：
- 需要独立 git worktree + 新分支（不动主 checkout WIP）
- 例如 minimax worker / verifier-minimax 那种需要 405 个 dirty 不污染主分支的场景
- **不是 UI 可见的必要条件**——B 组 spec 01-08 全部不带 `--worktree` 都成功 UI 可见

**注意**（2026-07-26 教训）：
- 我之前错误推断「必须 `--worktree` 才能 UI 可见」（受 minimax worker 误导）
- 实际：B 组所有 agent（spec 01-08）都是 `paseo run -d`（无 `--worktree`），用户在 UI 全看到
- minimax worker 用 `--worktree` 是因为它需要隔离分支做 kimi→MiniMax 重构，不是 UI 必要

---

## 3. 命令模板速查

### 3.1 创建验收者（detached）

```bash
# prompt 必须先写文件，避免 zsh backtick 截断
cat > /tmp/verifier-prompt.md <<'EOF'
【主会话 d8cfc17b → 验收者 · 北京时间 ...】
你的任务...
EOF

# python3 subprocess 调 paseo run -d
python3 -c "
import subprocess
prompt = open('/tmp/verifier-prompt.md').read()
r = subprocess.run(
    ['paseo', 'run', '-d',
     '--provider', 'claude',
     '--model', 'claude-fable-5',
     '--title', 'v0.3 验收者 · claude-fable-5',
     '--cwd', '/Users/zab/Documents/project/AIPulse',
     '--mode', 'bypassPermissions',
     '--label', 'role=verifier',
     '--label', 'round=B',
     '--label', 'spec=01',
     prompt],
    capture_output=True, text=True, timeout=60
)
print(r.stdout, r.stderr, r.returncode)
"
```

**输出格式**：

```
AGENT ID                              STATUS      PROVIDER    CWD
456dfcb6-6609-4ffc-b2c5-54fd6bebf2d8  running     claude      /Users/zab/...
```

### 3.2 主会话 send 验收者

```python
mcp__paseo__send_agent_prompt({
    "agentId": "456dfcb6-6609-4ffc-b2c5-54fd6bebf2d8",
    "prompt": "..."
})
```

### 3.3 验收者创建 worker（在 worker 内部执行）

```bash
# worker 也是 detached，UI 可见。必须 --worktree 隔离 + 自己 worktree 内 git commit
paseo run -d --worktree <slug> \
  --provider claude \
  --model claude-fable-5 \
  --title "v0.3 worker · B 组 spec 01" \
  --cwd /Users/zab/Documents/project/AIPulse \
  --mode bypassPermissions \
  --label role=worker \
  --label round=B \
  --label spec=01 \
  '<worker prompt>'
```

**Worker 硬约束**（必加到 prompt）：

1. **禁止跨 worktree 操作**：所有 FileEdit/Write/Bash 改动限制在 `${worktree_root}` 内，不许动主 checkout
2. **必须用 git 工具**：写完跑 `git add` + `git commit -m "..."` 在 worktree 里
3. **完成后核对**：`cd <worktree_root> && git status --short && git log --oneline main..HEAD`
4. **禁止**用绝对路径 Edit/Write 绕过 worktree cwd

（教训：2026-07-27 v0.3 spec 09 RED 修复 worker 跨 worktree 改主 checkout，dirty 全错位）

### 3.4 验收者 send worker（在验收者内部执行）

```bash
paseo send <worker-agent-id> "<follow-up prompt>"
```

### 3.5 查看 agent 状态

```bash
paseo ls                              # 所有 active agent
paseo status                          # daemon 状态
paseo logs <agent-id> --limit 10      # agent 最近活动
```

或 MCP 工具：

```python
mcp__paseo__list_agents({"cwd": "..."})
mcp__paseo__get_agent_status({"agentId": "..."})
mcp__paseo__get_agent_activity({"agentId": "...", "limit": 5})
```

### 3.6 archive agent（任务结束）

```python
mcp__paseo__archive_agent({"agentId": "..."})
```

或 CLI：

```bash
paseo archive <agent-id>
```

---

## 4. 关键约束

### 4.1 `--mode` 必须是完整名

| Provider | 错误 mode | 正确 mode |
|---|---|---|
| claude | `bypass` | `bypassPermissions` |

错误信息：`Invalid mode 'bypass' for provider 'claude'. Available modes: plan, default, acceptEdits, auto, bypassPermissions`

### 4.2 `--model` 显式指定

不指定 `--model` 时，Paseo 自动挑 provider 的默认模型（claude 通常是 `claude-opus-4-8`）。要强制用 `claude-fable-5`：

```bash
--model claude-fable-5
```

### 4.3 prompt 长度 → 必须先写文件

`paseo run -d '<prompt>'` 的 prompt 参数如果超长或含特殊字符，zsh backtick 会截断。按 `feedback_paseo-long-prompt-via-python`：

```bash
# 先写文件
cat > /tmp/agent-prompt.md <<'EOF'
你的 prompt 内容
EOF

# 再 python3 subprocess 调
python3 -c "
import subprocess
prompt = open('/tmp/agent-prompt.md').read()
subprocess.run(['paseo', 'run', '-d', '--provider', 'claude', ..., prompt])
"
```

### 4.4 主会话只能 ↔ 验收者

按 `feedback_no-third-agent-in-loop`：

- ❌ 主会话直接 `paseo send <worker-id>` —— 违反规则
- ✅ 主会话只 `mcp__paseo__send_agent_prompt` 给验收者
- ✅ 验收者内部用 `paseo run -d` 创建 worker + `paseo send` 派活

### 4.5 worker 不许 send 主会话

按 `feedback_worker-no-direct-report`：

- ❌ worker 模仿验收者格式写"X GREEN / Y RED"上报主会话
- ✅ worker 修完只 send 验收者，由验收者独立复验后回执主会话

### 4.6 主会话信完成前必核验收者 status

按 `feedback_main-verify-before-believe`：

- 收到"X GREEN / Y RED / Z 硬阻塞"格式回执
- 必须 `get_agent_status` 确认验收者真 idle/closed
- 否则就是 worker 伪造

---

## 5. 完整 round 流程示例（B 组 spec 01）

### 5.1 主会话：创建验收者

```python
# Step 1: 写 prompt 文件
Write("/tmp/verifier-prompt.md", "<完整 prompt>")

# Step 2: python3 subprocess 调 paseo run -d
Bash("""
python3 -c "
import subprocess
prompt = open('/tmp/verifier-prompt.md').read()
r = subprocess.run(
    ['paseo', 'run', '-d',
     '--provider', 'claude',
     '--model', 'claude-fable-5',
     '--title', 'v0.3 验收者 · B 组 spec 01',
     '--cwd', '/Users/zab/Documents/project/AIPulse',
     '--mode', 'bypassPermissions',
     '--label', 'role=verifier',
     '--label', 'round=B',
     prompt],
    capture_output=True, text=True, timeout=60
)
print(r.stdout)
"
""")
# 输出：AGENT ID 456dfcb6-6609-4ffc-b2c5-54fd6bebf2d8 running claude /Users/zab/...
```

### 5.2 验收者：内部执行（用户 Paseo UI 可见）

```bash
# 1. 读 spec 01 + plan
cat docs/superpowers/specs/v0.3-followed-up-and-summary/01-foundation-data-model.md
cat docs/superpowers/plans/v0.3-followed-up-and-summary/...

# 2. 勘察现状
sqlite3 data/aipulse.db ".schema"
ls src/aipulse/schemas/

# 3. 写 B 组清单 + worker prompt
cat > /tmp/worker-prompt.md <<'EOF'
<worker 任务清单>
EOF

# 4. 创建 worker (detached)
paseo run -d \
  --provider claude \
  --model claude-fable-5 \
  --title "v0.3 worker · B 组 spec 01" \
  --cwd /Users/zab/Documents/project/AIPulse \
  --mode bypassPermissions \
  --label role=worker \
  --label round=B \
  --label spec=01 \
  "$(cat /tmp/worker-prompt.md)"

# 5. 等 worker 修完 send 回来
# 6. 独立复验（跑测试、查 DB、git diff）
# 7. 回执 send 主会话
paseo send d8cfc17b-8e81-47dc-86d5-69efa0508e04 "<回执>"
```

### 5.3 主会话：收到回执

```python
# 收到回执后核对事实
mcp__paseo__get_agent_status({"agentId": "456dfcb6-..."})  # 确认 status=closed/idle
# 核对回执里的 file:line / pytest 输出 / DB 真值 / git mtime
# 5 类 I-类红线核查（status 不吞异常 / 真链路无 mock / fixture 隔离 / Reminders 隔离 / UI 真实浏览器）

# 验收
TaskUpdate({"taskId": ..., "status": "completed"})
mcp__paseo__archive_agent({"agentId": "456dfcb6-..."})  # 归档本轮验收者
```

---

## 6. 常见错误 & 排查

### 6.1 `Invalid mode 'bypass'`

→ 用 `bypassPermissions` 完整名

### 6.2 zsh 截断 prompt

→ 先写文件再 python3 subprocess

### 6.3 Paseo UI 看不到对话

→ 用了 `mcp__paseo__create_agent` 而不是 `paseo run -d` CLI

### 6.4 验收者 send 错对象

→ 之前发生过：验收者 send `/goal` agent 而不是主会话 `d8cfc17b`
→ 主会话 ID 是 `d8cfc17b-8e81-47dc-86d5-69efa0508e04`，prompt 里必须**明确写这个 ID**

### 6.5 时间漂移（以为 worker idle 但实际跑了 3h）

→ 按 `feedback_main-must-check-time-when-waiting`：每 30 分钟主动核 wall-clock

---

## 7. 五大 I-类硬红线（每次 round 必查）

按 `feedback_status-must-not-mask-failure` + `feedback_no-mock-backend-e2e` + `feedback_test-fixture-must-not-touch-real-db` + `feedback_tests-must-isolate-apple-reminders` + `feedback_extension-e2e-verification`：

1. **fail 不许标 completed**：error/hotspot/note_path 三件齐才 completed
2. **真链路不许 mock**：打真实 sidecar，登录态页面形态要覆盖
3. **fixture 隔离真 DB**：默认 tmp_path 隔离，reset_db 仅 opt-in
4. **测试只操作 AIPulse测试 Reminders 列表**：阻止 helper 间接污染真实业务列表
5. **UI 改动必须 mcp__playwright 真实浏览器**：vitest+tsc+build 不够

---

## 8. 参考 memory

- `feedback_paseo-use-run-d-cli-not-mcp-create-agent` — MCP create_agent 不可见，必用 paseo run -d
- `feedback_paseo-visible-run` — 用户要实时进度用 `paseo run -d`
- `feedback_paseo-long-prompt-via-python` — 长 prompt 走 python 中转
- `feedback_paseo-self-detection` — 不要把当前 session 当成鬼影 agent
- `feedback_main-session-loop-coordinator` — 主会话只 ↔ 验收者，loop 结束再安排下一项
- `feedback_no-third-agent-in-loop` — 闭环只要 worker+verifier
- `feedback_worker-no-direct-report` — worker 禁越权伪闭环
- `feedback_main-verify-before-believe` — 信完成前必核验收者 status
- `feedback_main-break-loop-deadlock` — 死锁时主会话破例 send worker
- `feedback_main-must-check-time-when-waiting` — 每 30 分钟核 wall-clock 时间漂移
- `reference_paseo-workspace-cleanup` — workspace 关联 git worktree，清理走 `paseo worktree archive`

---

## 9. Workspace 清理指南（用户 UI 看到一堆 worktree 时用）

### 9.1 问题：UI workspace 列表堆积

每次 `paseo run -d`（不带 `--workspace`）默认新建一个 Paseo workspace entry（写入 `~/.paseo/projects/workspaces.json`）。跑几十次后 UI workspace 列表会塞满，影响用户判断。

**实际结构**：

```text
UI 显示的 workspace = metadata workspaceId + 关联的真 git worktree

~/.paseo/projects/workspaces.json  ← 持久化 workspace 记录（archived 也会保留）
~/.paseo/worktrees/<hash>/<slug>/ ← 真 git worktree 目录（Paseo 帮你创建）
git worktree list                 ← git 看到的 worktree 注册
```

**三类实体**：

| 实体 | 文件位置 | 归档方法 |
|------|----------|----------|
| Paseo workspace metadata | `~/.paseo/projects/workspaces.json` 的 `archivedAt` 字段 | 软删除：编辑 JSON / 走 WS `archive_workspace_request` |
| 真 git worktree 目录 | `~/.paseo/worktrees/<hash>/<slug>/` | `paseo worktree archive <slug>` 同时清 |
| git worktree 注册 | 主 repo `.git/worktrees/<name>/` | `paseo worktree archive <slug>` 同时清 |

### 9.2 清理命令：`paseo worktree archive`

```bash
paseo worktree archive <slug-or-branch-name>
```

**实测**（来自 agent 29d91e52 测试报告，2026-07-26 14:03）：

- 创建：`paseo run --worktree <slug> <prompt>` → 写入 `~/.paseo/worktrees/<hash>/<slug>/` + 新分支
- 归档：删 worktree 目录 + 删 `git worktree list` 注册 + 填 metadata `archivedAt`
- 不删 git 分支（git 设计 + Paseo 不主动 prune，需要 `git branch -D` 手动清）
- 归档后留空 hash 命名空间目录（可 `rmdir`，下次同源路径 worktree 复用）
- 归档耗时 ~3.8s（daemon 标 `ws_slow_request` 但不是错误）
- CLI 与 MCP `mcp__paseo__archive_workspace` 行为一致（MCP 是 CLI 薄壳）

### 9.3 验证清理完成

```bash
git worktree list
# 应该只剩 1 个主 checkout

ls ~/.paseo/worktrees/
# 应该只剩空的 hash 命名空间目录

paseo ls
# 应该看不到已归档的 agent
```

### 9.4 错误判断警告

❌ **不要看到 `paseo worktree ls` 报 `cwd or repoRoot is required` 就以为命令不能用在 workspace 上**。这是缺上下文错误（命令依赖当前 cwd 找主 repo root），跟 workspace/worktree 无关。`paseo worktree archive <slug>` 在 AIPulse 这种 local checkout 项目里**就是清理 Paseo workspace 的正确命令**。

❌ **不要靠 docstring 推断命令语义**。必须实测一次（建一个 → 归档 → 验证 git worktree list）才能下结论。

❌ **不要直接 `paseo daemon restart` 来"刷新 UI"**。会杀所有 running agent（包括主会话本身），曾经踩过这个坑：把自己干掉了。

### 9.5 fallback 路径：手动改 JSON（仅在 `paseo worktree archive` 失效时）

```bash
# 1. 备份
cp ~/.paseo/projects/workspaces.json ~/.paseo/projects/workspaces.json.bak-$(date +%Y-%m-%d)

# 2. 给孤儿 workspace 标 archivedAt
python3 -c "
import json, os
from datetime import datetime, timezone
with open('/Users/zab/.paseo/projects/workspaces.json') as f:
    ws = json.load(f)
now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
n = 0
for w in ws:
    if not w.get('cwd','').endswith('AIPulse'): continue
    if w.get('archivedAt'): continue
    w['archivedAt'] = now
    n += 1
tmp = '/Users/zab/.paseo/projects/workspaces.json.tmp'
with open(tmp, 'w') as f: json.dump(ws, f, ensure_ascii=False, indent=2)
os.replace(tmp, '/Users/zab/.paseo/projects/workspaces.json')
print(f'marked {n} as archived')
"
```

**风险**：
- daemon 内存缓存不会自动 reload → UI 短暂不一致（直到下一次 daemon 重启或下次 fetch_workspaces 自然刷新）
- 不要 restart daemon 来刷新（会杀主会话）

---

## 10. 避免 workspace 堆积（主动措施）

### 10.1 复用现有 workspace

`paseo run -d --workspace <existing-workspace-id>` 让新 agent 跑在已有 workspace 下，不创建新 entry。

```bash
# 第一次：默认创建 workspace（返回 wks_xxx）
paseo run -d --provider claude --title "B-verifier-spec01" ...  # 输出 wks_xxx

# 后续：复用同一个 workspace
paseo run -d --provider claude --title "B-verifier-spec02" \
  --workspace wks_xxx ...  # 不再创建新 workspace
```

**安全性**：
- 多 agent 共用 workspace 时**必须串行**（按 `feedback_main-session-loop-coordinator` — 主会话等当前验收者 idle 才派下一个）
- 不要并发跑多个 agent 在同一 workspace（DB / 文件读写冲突）
- workspace 内共享 cwd，写文件不冲突靠子目录隔离

### 10.2 `--worktree <slug>` vs 默认行为

| 场景 | 用法 | workspace 数 |
|------|------|-------------|
| 普通验收 round | `paseo run -d`（默认） | 每轮 +1（可接受） |
| 需要隔离分支测试 | `paseo run -d --worktree <slug>` | 每轮 +1 + 真 git worktree |
| 复用 workspace | `paseo run -d --workspace <wks_id>` | 不增 |

**建议**：
- 验收 round 用默认 + `--workspace`（如果不想 workspaces.json 涨）
- 隔离测试用 `--worktree`，完事用 `paseo worktree archive <slug>` 清
- **不要再用 `mcp__paseo__create_agent`**（UI 不可见）

### 10.3 定期清理节奏

- 每个验收 round 结束：归档本轮验收者（`paseo archive <id>`）+ 用 `paseo worktree archive` 清 worktree
- 不要攒超过 5-10 个 active workspace（UI 会挤）
- 主会话每周/重要节点查一次 `git worktree list` 和 `paseo ls`，确认没残留