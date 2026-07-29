# v0.3 UI 一致性修复 Loop 群执行文档（Round 8-11）

> 创建：2026-07-29。目的：上下文重置后任何人（或新会话）可按本文档独立执行 4 个 UI 修复 loop，无需翻聊天记录。
> 依据报告：`docs/superpowers/verifications/2026-07-29-ui-consistency-audit.md`（15 findings：H3/M7/L5），截图 `docs/.screenshots/ui-audit/`。

---

## 0. 全局背景（必读）

- **分支**：所有 loop 基于 `feat/extension-real-e2e`（HEAD 含 6 条 E2E 路径测试 + Round 7 审查报告 + `68ced3c` avatar await 修复）。每轮 GREEN 后直接 merge 回此分支（用户已授权此模式，E2E loop 6 轮同款操作）。
- **已完成的 E2E loop 战绩**：Round 1-6 六条 E2E 路径（A 添加关注/B 摘要/C 失败重试/D 限流/E vault 扫描/F 鉴权）全部 GREEN 并 merge，测试在 `tests/e2e/`（17 个用例）。UI loop 不得破坏这些测试。
- **前置已修**：`src/aipulse/api/followed_up.py:646` avatar 缓存缺 `await` 已修复并 commit（`68ced3c`）。**L4（头像空占位）大概率自愈**，Loop D 验收时只需截图确认，可能无需改前端。
- **主 checkout 红线**：主 checkout 有用户另一会话的 sidecar 开发脏文件（`sidecar.py`、`llm.py`、`downloader.py`、`douyin.py`、AGENTS.md、CLAUDE.md、`05-frontend-ui.md` 等），**一律不碰、不 commit、不 checkout 还原**。
- **secrets 红线**：严禁 cat/echo `.env` 内容；测试只用 dummy token。

## 1. 环境与服务

| 项 | 命令/位置 |
|---|---|
| 后端 | `uv run uvicorn aipulse.server:app --host 127.0.0.1 --port 8000`（项目根；源码在 `src/aipulse/`） |
| 前端 | `cd frontend && pnpm dev --host 127.0.0.1 --port 5173` |
| 前端单测 | `cd frontend && pnpm test:unit`（vitest） |
| 前端构建检查 | `cd frontend && pnpm build`（vue-tsc + vite，类型检查靠它） |
| 健康检查 | `curl -sS http://127.0.0.1:8000/health` → `{"success":true,...}`；`curl -s http://127.0.0.1:5173/api/sources` 验证 vite proxy |
| 后端回归 | `uv run pytest tests/unit tests/integration --no-cov -q`；E2E `uv run pytest tests/e2e/ --no-cov -q`（约 2-4 分钟，含真实网络） |

注意：`frontend/package.json` 已声明 `@tanstack/vue-query`，若 worktree 里 node_modules 缺失需先 `pnpm install`（Round 7 踩过）。

## 2. Loop 机制（沿用 E2E loop 纪律）

- **拓扑**：主会话（kimi k3-256k）为唯一通讯枢纽。worker 与 verifier **零直接对话**；verifier 的问题清单由主会话打包进下一轮 prompt。
- **每轮新 agent**：worker provider `claude/MiniMax-M3[1M]`（modeId `bypassPermissions`），verifier provider `kimi/kimi-code/k3-256k`（modeId `auto`）。labels 打 `{loop: v03-ui, path: A|B|C|D, role: worker|verifier}`。
- **workspace**：`create_workspace isolation=worktree, mode=branch-off, baseBranch=feat/extension-real-e2e`。⚠️ **base 可能滞后**：worker prompt 必须写「开工第一步 `git merge feat/extension-real-e2e` 校准，并用 `git merge-base --is-ancestor <上轮merge sha> HEAD` 验证」。
- **worker prompt 铁律**：自包含（项目根、分支、启动命令、测试命令、验收清单、红线）；要求**分阶段 commit**（防断连丢工作）；最终汇报必须含 commit hash + 测试输出尾部 + 变更文件清单。
- **verifier prompt 铁律**：不信任申报——亲自跑 `pnpm test:unit` + `pnpm build` + 重启 dev server 用浏览器/截图核对每条 finding；核对 worker 日志原文；`git status` 干净；最终消息必须含 `VERDICT: GREEN / GREEN-WITH-WARN / RED` + 证据摘要 + 问题清单。没出 VERDICT 就 `send_agent_prompt` 催。
- **RED 处理**：verifier 问题清单打包进同 loop 下一轮（新 worker + 新 verifier，worktree 复用原分支继续）。
- **GREEN 处理**：主会话 merge worktree 分支回 `feat/extension-real-e2e`，然后起下一 loop。
- **串行不并行**：Loop A/C 都会大面积触碰相同页面组件，并行必冲突。一次只跑一个 loop。
- **UI 验证工具**：verifier 可用 kimi-webbridge（127.0.0.1:10086）或 playwright 截图核对；基准截图在 `docs/.screenshots/ui-audit/`，修复后截图放 `docs/.screenshots/ui-fix-<X>/`。

## 3. 设计基线（worker/verifier 共同依据）

- tokens：`frontend/src/styles/tokens.css` + `frontend/src/components/sidebar/sidebar.css`
  - 色板：`--surface-bg #F7F7F5`、`--surface-elevated #FFF`、`--border-subtle #E8E8E6`、`--text-primary #1A1A1A`、`--text-secondary #6B6B6B`、`--accent-coral #F97316`、`--status-green/amber/red`
  - 字号 `--text-xs 11px` ~ `--text-2xl 28px`；圆角 `--radius-sm 6px` / `--radius-md 10px` / `--radius-lg 16px`
- 设计文档：`docs/superpowers/specs/2026-07-09-v0.2-web-dashboard-design.md` §6.3（统一状态样式/页面头部）、§6.4（卡片 hover/标签化元信息）、§8.4（错误 sanitize）
- **原则：最小改动收敛样式，不重排信息架构，不改任何 API/逻辑行为。**

---

## 4. Loop A「按钮 + 页面头部体系」（H1 + M1 + H3）

**范围**：建两个基础组件并收敛全站调用点。

- **H1** `SummarizeButton.vue:214` idle 态引用未定义的 `--ink`/`--paper`（`web/` 旧主题变量）→ 退化成 UA 默认黑框按钮。改用现 token（如 `var(--text-primary)` 底 + `var(--surface-elevated)` 字，或并入下面的 secondary 规范）。顺带把 `--state-*` 从 sidebar.css 上移 tokens.css（可选）。
- **M1** 全站 ≥5 种按钮风格并存（橙实心/浅灰描边/红字描边/蓝链接/UA 默认/全宽橙描边「保存」/灰色小「刷新」），圆角混用。建 `AppButton`（`primary / secondary / danger / ghost` 四级 + size），收敛全部调用点；设置页「保存」→ primary 实心。
- **H3** 页面头部三套体系并存：A 套中文副标题（AI 热点/关注列表）、B 套英文 eyebrow（FOLLOW-UP/LEARNING QUEUE/ACTION REQUIRED）、C 套 Phase 占位 pill（来源/关键词/定时任务/摘要，Phase 编号互不一致）。建 `PageHeader`（标题 + 副标题 + 右侧 slot）全站复用；英文 eyebrow 移除或改中文副标题；Phase pill 移除或统一「Beta」标记；头部右侧操作位（主按钮/刷新/计数）走 slot。

**验收（verifier 清单）**：10 个页面（6 sidebar + dashboard 5 tab）截图逐页核对；不再有 UA 默认按钮；不再有 eyebrow/Phase pill；按钮四级语义一致；`pnpm test:unit` + `pnpm build` 绿；后端测试不受影响（不该动后端）。

## 5. Loop B「错误信息 sanitize」（H2 + M3 + L5）

- **H2** 失败 tab 直接渲染原始 API 错误 JSON（`Error code: 401 - {'error': {...}}` Python dict repr 单行英文）。前端建错误映射/截断（如「API Key 失效，请到 系统 页检查 LLM 配置」），原始错误收进 title/tooltip 或折叠详情。设计依据 §8.4。
- **M3** 技术细节泄漏：来源卡完整类路径 `aipulse.collectors.arxiv.ArxivCollector` **溢出卡片右边界**（真布局 bug）；定时任务 func 全路径 + trigger repr（`interval[0:01:00]`）；处理记录 BVID；arXiv 卡原始 httpx 英文错误（mono 深色，与失败 tab 红色不一致）。类路径/func 移入 tooltip 或折叠区；卡片 `overflow-wrap`/省略；trigger 转译「每 30 分钟」「每天 08:00」；错误展示统一走 H2 映射。
- **L5** 错误配色统一：失败 tab `--status-red` vs 来源卡 mono 深色 → 统一红色语义。

**验收**：失败/来源/定时任务/处理记录四页截图；无任何原始 JSON/类路径/repr 上屏；溢出修复；`pnpm test:unit` + `pnpm build` 绿。

## 6. Loop C「状态 / 格式 / 空态统一」（M2 + M4 + M5 + L2 + M6）

- **M2** 状态呈现三制并存（彩色 badge / 纯文本 `Partial`/`Failed` / mono chip）。建 `StatusBadge`（成功绿/警告橙/失败红/中性灰）收敛；Failed 必须用 `--status-red`。
- **M4** 日期格式统一 `YYYY-MM-DD HH:mm`：`2026/7/24 11:00:00`（toLocaleString）vs `2026-07-29`（ISO）并存；间隔表达「30 分钟 / 次」vs「30 分钟」统一。建/收敛 `lib/format.ts`。
- **M5** 文案中文化：状态词 `Partial`/`Failed`/`medium` 翻译；任务名 `Scan all enabled followed UP主`、`sync_all_sources` 不上屏；`uid: 517327498` 不直接展示。
- **L2** 热点卡元信息 `bilibili_up medium 2026/7/24 11:00:00` 拼接串 → 标签化（设计 §6.4）；`热度 0.0` 橙色高亮是噪音，0 值降级为中性色或不显示。
- **M6** EmptyState 组件（图标 + 说明 + 可选引导按钮）：关键词页裸文本 vs 即将学习虚线卡片统一；摘要页「—」半空态处理。

**验收**：全页截图核对状态/日期/空态一致性；`pnpm test:unit` + `pnpm build` 绿。

## 7. Loop D「热点卡交互 + 杂项」（M7 + L1 + L3 + L4）

- **M7** 热点卡不可点击：`DashboardHotspotPanel.vue` 纯静态 div，但 `HotspotDetailView.vue` 存在且无入口。卡片标题包 `RouterLink`（或整卡可点），补 `cursor: pointer` 与焦点环（a11y）。
- **L1** 热点卡无 hover（设计 §6.4 上浮 + 加深阴影），与 M7 顺手做。
- **L3** sidebar 图标散装 unicode（◐/⚙/✎/⌚/✦/☰，语义错位）→ 统一 icon set（lucide 或同级），保持线宽一致。注意控制依赖新增，优先 SVG 内联。
- **L4** 头像空占位：**先验证 `68ced3c` 修复后是否自愈**（打开任一 UP 详情页触发缓存落盘 → 回关注列表看头像）。未自愈再做 fallback（首字符/默认图标）。

**验收**：热点卡可点进详情且路由正确；hover 生效；sidebar 图标风格统一；头像显示真实图或有内容 fallback；`pnpm test:unit` + `pnpm build` 绿 + 路由相关前端测试更新。

---

## 8. 执行顺序与进度记录

顺序：**A → B → C → D**（串行）。每轮 GREEN merge 后在此节打勾：

- [ ] Loop A（H1+M1+H3）— worker 分支 `ui-fix/loop-a-buttons-headers`
- [ ] Loop B（H2+M3+L5）— worker 分支 `ui-fix/loop-b-error-sanitize`
- [ ] Loop C（M2+M4+M5+L2+M6）— worker 分支 `ui-fix/loop-c-status-format-empty`
- [ ] Loop D（M7+L1+L3+L4）— worker 分支 `ui-fix/loop-d-hotspot-card-misc`

**全部收官后挂账**：① spec 09 §3.5/§5.5 vault scan 契约回写（实现是 POST /scan 而非 GET /candidates；持久层是 settings.json 而非 .env）；② plan 08「真实 Kimi」口径改为 MiniMax；③ 审查报告 15 findings 逐条标注修复 commit。
