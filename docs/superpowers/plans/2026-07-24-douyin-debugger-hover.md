# Douyin Debugger Hover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `run_skill(name="subagent-driven-development")` (recommended) or `run_skill(name="executing-plans")` to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Chromium 扩展在已获用户确认后，通过 `chrome.debugger` 的 `Input.dispatchMouseEvent` 自动悬停抖音分享按钮，并复用现有页面拦截器取得 `v.douyin.com` 短链。

**Architecture:** MV3 service worker 拥有 `chrome.debugger` 权限，负责 attach、发送真实鼠标事件、按 5 秒窗口重试最多 3 次并始终 detach。Content script 只定位当前作品的分享按钮、返回 viewport 中心坐标，并等待现有 MAIN-world fetch/XHR 拦截器写入短链；popup 负责首次说明和持久确认，未确认时仍保留长链接采集。

**Tech Stack:** TypeScript 5、Manifest V3、Chrome Extensions `debugger` API、CDP `Input.dispatchMouseEvent`、React 18、Vitest、Playwright

## 文件结构

- Create: `extensions/chromium/src/platform/douyin-debugger.ts` — 后台可测试的 debugger 会话、CDP 输入、重试和 detach 编排。
- Modify: `extensions/chromium/manifest.json` — 声明 `debugger` 权限。
- Modify: `extensions/chromium/src/background.ts` — 校验 Douyin 标签页与消息来源，调用 debugger 控制器。
- Modify: `extensions/chromium/src/content.ts` — 返回按钮坐标、触发后台真实悬停、等待现有短链 Map，并在失败时执行合成事件回退。
- Modify: `extensions/chromium/src/platform/douyin-share.ts` — 提供分享按钮中心坐标及等待捕获的小接口，保留当前合成流程。
- Modify: `extensions/chromium/src/popup.tsx` — 首次说明、确认持久化、未确认时不发 debugger 请求。
- Modify: `extensions/chromium/src/popup.css` — 首次说明卡片及键盘焦点样式。
- Create: `extensions/chromium/tests/unit/douyin-debugger.test.ts` — debugger 控制器单元测试。
- Modify: `extensions/chromium/tests/unit/background.test.ts` — 后台路由、来源校验、失败回退响应测试。
- Modify: `extensions/chromium/tests/unit/platform.test.ts` — 坐标与真实悬停编排测试。
- Create or modify: `extensions/chromium/tests/unit/popup.test.tsx` — 首次说明与确认持久化测试；若仓库现有测试结构不支持 popup DOM 测试，则抽取纯状态函数并测试该函数。
- Modify: `extensions/chromium/tests/e2e/douyin-share-short-link.spec.ts` — 登录态真实页面 debugger 悬停及 detach 验证。

### Task 1: Debugger 会话核心

**Files:**
- Create: `extensions/chromium/src/platform/douyin-debugger.ts`
- Test: `extensions/chromium/tests/unit/douyin-debugger.test.ts`

- [ ] **Step 1: 写失败测试**：用注入式 `DebuggerApi` 测试 attach 后依次发送 `mouseMoved`（必要时先发送当前位置外的移动）、捕获完成后 detach、单次 5 秒超时后 detach、最多 3 次尝试及递增间隔、attach 冲突返回可回退结果、每条异常路径只 detach 已成功 attach 的会话。
- [ ] **Step 2: 运行 RED**：`cd extensions/chromium && pnpm vitest run tests/unit/douyin-debugger.test.ts --reporter=verbose`，确认因模块不存在或行为未实现而失败。
- [ ] **Step 3: 最小实现**：定义 `HoverPoint { x; y }`、`DebuggerHoverResult` 和 `dispatchTrustedHover(tabId, point, options)`；使用 `chrome.debugger.attach({ tabId }, '1.3')`、`chrome.debugger.sendCommand(..., 'Input.dispatchMouseEvent', ...)` 与 `finally` 中的 `detach`。每次尝试是独立 attach/detach 会话，超时 5000ms，重试间隔为 1000ms、2000ms。
- [ ] **Step 4: 运行 GREEN**：重复 Task 1 Step 2，确认全部通过且无未清理计时器。

### Task 2: 分享按钮坐标接口

**Files:**
- Modify: `extensions/chromium/src/platform/douyin-share.ts`
- Modify: `extensions/chromium/tests/unit/platform.test.ts`

- [ ] **Step 1: 写失败测试**：覆盖推荐页 `[data-e2e="video-player-share"]`、详情页、图文页和 position fallback；断言返回的是内部 SVG 包装元素的 viewport 中心坐标，零尺寸或越界元素返回 `undefined`。
- [ ] **Step 2: 运行 RED**：`cd extensions/chromium && pnpm vitest run tests/unit/platform.test.ts --reporter=verbose`。
- [ ] **Step 3: 最小实现**：增加 `findActiveSlideShareHoverPoint(document): HoverPoint | undefined`，复用现有 `findActiveSlideShareButton` 与 hover target 规则；先 `scrollIntoView`，再读取 `getBoundingClientRect`，不复制选择器逻辑。
- [ ] **Step 4: 运行 GREEN**：重复 Task 2 Step 2。

### Task 3: 后台 debugger 消息路由

**Files:**
- Modify: `extensions/chromium/manifest.json`
- Modify: `extensions/chromium/src/background.ts`
- Modify: `extensions/chromium/tests/unit/background.test.ts`

- [ ] **Step 1: 写失败测试**：新增 `DOUYIN_DEBUGGER_HOVER` 消息测试，要求 `sender.tab.id` 存在、标签页 URL 属于 `https://www.douyin.com/`、坐标是有限且非负数字；有效请求调用 `dispatchTrustedHover`，attach 冲突返回 `{ ok: false, fallback: true }`，其他错误返回清晰错误且不泄露内部对象。
- [ ] **Step 2: 运行 RED**：`cd extensions/chromium && pnpm vitest run tests/unit/background.test.ts --reporter=verbose`。
- [ ] **Step 3: 最小实现**：manifest 加入 `"debugger"`；扩展 `BackgroundMessage`；只信任 sender tab 而不接受调用者提供 tabId；调用 Task 1 控制器并返回结构化结果。tab 移除或更新时调用安全 detach，忽略“未 attach”错误。
- [ ] **Step 4: 运行 GREEN**：重复 Task 3 Step 2。

### Task 4: Content script 编排与合成回退

**Files:**
- Modify: `extensions/chromium/src/content.ts`
- Modify: `extensions/chromium/src/platform/douyin-share.ts`
- Modify: `extensions/chromium/tests/unit/platform.test.ts`

- [ ] **Step 1: 写失败测试**：debugger 成功发送时，content script等待已有 `capturedShareUrls`；5 秒内捕获即返回短链；debugger attach 冲突或三次尝试均未捕获时，调用现有 `requestShareUrlCapture`；按钮不存在时直接走当前回退；同一 videoId 捕获成功后不重复触发。
- [ ] **Step 2: 运行 RED**：`cd extensions/chromium && pnpm vitest run tests/unit/platform.test.ts --reporter=verbose`。
- [ ] **Step 3: 最小实现**：将 `FETCH_DOUYIN_SHARE_URL` 处理改为：读取坐标 → `chrome.runtime.sendMessage({ type: 'DOUYIN_DEBUGGER_HOVER', point })` → 等待现有 Map → 失败则 `requestShareUrlCapture`。不要用 CDP 抓响应体，不改变 MAIN-world 拦截器。
- [ ] **Step 4: 运行 GREEN**：重复 Task 4 Step 2。

### Task 5: 首次说明与确认持久化

**Files:**
- Modify: `extensions/chromium/src/popup.tsx`
- Modify: `extensions/chromium/src/popup.css`
- Test: `extensions/chromium/tests/unit/popup.test.tsx` 或等价纯函数测试

- [ ] **Step 1: 写失败测试**：`chrome.storage.local` 无 `douyinDebuggerAccepted` 时显示一次说明；确认后写入布尔值 `true` 并从当前作品触发短链请求；未确认时仍显示/提交 canonical 长链接且不发送 debugger 请求；再次打开不显示说明。
- [ ] **Step 2: 运行 RED**：运行新增 popup 测试文件；若现有 Vitest 没有 React DOM 配置，先写纯函数存储测试而非引入新测试依赖。
- [ ] **Step 3: 最小实现**：在 popup 中加入可聚焦说明卡片与“启用自动获取”按钮；不提供隐式自动确认；确认状态使用 `chrome.storage.local` 布尔值；未确认时状态提示保持非错误，不阻止复制或提交长链接。
- [ ] **Step 4: 运行 GREEN**：重复 Task 5 Step 2。

### Task 6: 真实页面 E2E

**Files:**
- Modify: `extensions/chromium/tests/e2e/douyin-share-short-link.spec.ts`

- [ ] **Step 1: 写/调整 E2E 断言**：使用现有登录 Cookie；先在扩展 storage 写入确认状态，打开推荐页、视频详情页和图文详情页中的可用真实样本；验证当前作品变化后短链被捕获、域名是 `v.douyin.com`、后台最终 detach。保留 `page.route('**/*bytegoofy.com/**', route => route.abort())` 的 note 页规避。
- [ ] **Step 2: 构建 E2E 包**：`cd extensions/chromium && pnpm build:e2e`。
- [ ] **Step 3: 运行真实 E2E**：`cd extensions/chromium && pnpm playwright test tests/e2e/douyin-share-short-link.spec.ts --project=chromium`；必须使用项目既有 `headless: false` + `--headless=new` 配置，不能以 mock 后端替代 sidecar 提交流程。
- [ ] **Step 4: 根据真实 DOM/权限行为最小修正**：仅修复观察到的坐标、时序或 detach 问题，然后重跑 Step 2-3。

### Task 7: 完整验证与审查

**Files:**
- Review all files above

- [ ] **Step 1: 单元测试**：`cd extensions/chromium && pnpm test -- --run`。
- [ ] **Step 2: 类型与构建**：`cd extensions/chromium && pnpm build`。
- [ ] **Step 3: 扩展真实 E2E 回归**：运行与抖音推荐、视频详情、图文详情及真实 sidecar 提交有关的测试。
- [ ] **Step 4: 专项审查**：调用 TypeScript reviewer、React reviewer、security reviewer 和独立 code reviewer；修复所有 Critical/High 以及明确的正确性问题。
- [ ] **Step 5: 独立验证子 agent**：让未参与实现的 agent 运行单元测试、类型检查、构建和相关真实 E2E；未通过则返工并重新验证。

## 自审

- 决策覆盖：Q1–Q10 均映射至 manifest、popup、重试、回退、超时和 detach 任务。
- 架构边界：只有 service worker 调用 `chrome.debugger`；content script 不接触该 API。
- 响应捕获：复用既有 MAIN-world `web_shorten` 拦截，不新增 `Network.getResponseBody`。
- 安全边界：后台从 `sender.tab` 获取目标，只允许 Douyin HTTPS 页面，校验坐标，不接受任意 tabId。
- 无占位符：所有任务均给出具体行为与测试命令。
