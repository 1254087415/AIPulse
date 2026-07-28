# AIPulse Clipper 浏览器扩展实施计划

> 对应设计文档：`docs/superpowers/specs/2026-07-03-browser-extension-design.md`
> 日期：2026-07-03
> 范围：Chrome/Chromium 浏览器扩展（Manifest V3），支持 Bilibili、抖音、小红书、微信公众号、YouTube 的一键归档
> 预计工期：**2–3 周**

---

## 1. 目标与范围

### 1.1 目标

为 AIPulse 桌面端提供一个 Chromium 浏览器扩展，让用户在浏览支持的内容平台时，可以一键把视频/文章链接提交到本地 AIPulse 知识库进行处理（下载、转录、总结、写入 Obsidian）。

### 1.2 v1 范围

- **浏览器**：Chrome / Edge / Chromium（Manifest V3）
- **支持平台**：Bilibili、抖音、小红书、微信公众号文章、YouTube
- **提交方式**：
  - 主链路：Native Messaging → Tauri 桌面端 → Python sidecar
  - Fallback：HTTP `POST http://127.0.0.1:8000/api/videos/extract`
- **交互入口**：
  - 工具栏 popup：识别当前页面链接、选择提交模式、填写标题/标签/字幕
  - 右键上下文菜单：归档当前页面 / 归档此链接
  - 扩展图标 badge：显示当前页识别到的链接数量
- **平台增强**：
  - Bilibili：自动提取并预览可选字幕
  - 抖音：捕获官方分享短链（`v.douyin.com/xxx`）以绕过反爬签名
- **运行环境**：AIPulse 桌面端本地（Tauri + Python sidecar）

### 1.3 明确不做

- Firefox / Safari 扩展
- 云端部署或服务器端扩展
- 完整的用户配置 UI（仅保留必要的 `httpBaseUrl` storage 配置）
- 视频下载或解析完全在浏览器端完成（浏览器只负责采集 URL 和元数据）
- 自动滚动采集抖音 feed 全部视频（仅识别当前 active slide）

---

## 2. 关键决策

### 2.1 扩展与桌面端如何通信？

**决策**：Native Messaging 为主，HTTP fallback 为辅。

- Native Messaging 走 `com.aipulse.native_host`，由 Tauri 桌面应用注册 host manifest，扩展可直接与本地 sidecar 通信。
- 当桌面端未启动或 Native Messaging 不可用时，自动 fallback 到本地 HTTP API `http://127.0.0.1:8000/api/videos/extract`。
- 扩展通过 `chrome.storage.local` 中的 `httpBaseUrl` 允许用户或 E2E 测试覆盖 HTTP 地址。

### 2.2 内容采集在浏览器端做多少？

**决策**：浏览器端只做「URL + 元数据采集」，不下载视频或完整解析内容。

- 扩展负责：识别页面中的视频/文章链接、提取标题、Bilibili 字幕选项、抖音分享短链。
- 桌面端负责：下载、转录、LLM 总结、Obsidian 归档。
- 这样既能利用浏览器已经登录的平台 Cookie，又避免在扩展中维护重型的解析/下载逻辑。

### 2.3 抖音分享短链怎么拿？

**决策**：通过 MAIN world 脚本拦截抖音自己的 `web_shorten` 网络请求。

- 抖音的短链接口有反爬签名，扩展无法自己生成。
- 在 `document_start` 注入一个 `world: "MAIN"` 的内容脚本，覆盖 `fetch`/`XMLHttpRequest`，当抖音 JS 调用分享接口时捕获响应。
- 普通 isolated world 脚本通过 `window.postMessage` 接收捕获结果，popup 再触发悬停分享按钮来诱导抖音 JS 发起请求。

### 2.4 Bilibili 字幕怎么获取？

**决策**：混合策略：优先从页面 `__INITIAL_STATE__` 拿到 `aid`/`cid` 后请求 B站 API；失败时回退到解析页面内嵌字幕 JSON。

- API 路径：`https://api.bilibili.com/x/player/wbi/v2?cid=...&bvid=...`
- 页面内嵌：`window.__playinfo__` 或 `<script>` 中的 subtitle 数据。
- 背景脚本提供受控的 `FETCH_JSON` 代理，只允许访问 B站相关 host，避免扩展成为任意网络请求代理。

### 2.5 Popup 用何种技术栈？

**决策**：React + TypeScript + Vite，用 `vite-plugin-web-extension` 构建 Manifest V3 扩展。

- popup 使用 React 渲染，保持与前端 Vue/Tauri UI 解耦，避免扩展包体积过大。
- 构建产物输出到 `extensions/chromium/dist`，可直接加载到 Chrome。
- E2E 构建通过 `__E2E__` 全局变量注入测试桥，生产构建剥离测试代码。

### 2.6 如何支持 SPA 动态导航？

**决策**：内容脚本通过 `MutationObserver` 监听 DOM 变化，URL 或抖音 active slide 变化时去抖重新扫描。

- 去抖间隔 500ms，避免频繁扫描。
- Background 监听 `tabs.onUpdated`，在同页 hash/query 变化时保留结果，真正导航时清除旧数据并更新 badge。
- 按 tabId 存储识别结果，避免多标签页互相污染。

---

## 3. 架构变化

### 3.1 新增目录与文件

| 文件 | 职责 |
|---|---|
| `extensions/chromium/manifest.json` | Manifest V3 配置：权限、host、content scripts、background |
| `extensions/chromium/src/background.ts` | Service worker：消息路由、右键菜单、badge、提交分发、tab 生命周期 |
| `extensions/chromium/src/content.ts` | 内容脚本：扫描链接、响应 RESCAN/FETCH_SUBTITLE/FETCH_DOUYIN_SHARE_URL |
| `extensions/chromium/src/popup.tsx` | React popup：展示识别链接、选择模式、填写标题/标签/字幕、提交 |
| `extensions/chromium/src/popup.css` | Popup 样式 |
| `extensions/chromium/src/types.ts` | 共享类型：`FoundLink`、`SubmitPayload`、`SubmitResult`、`VideoMetadata` 等 |
| `extensions/chromium/src/utils.ts` | 工具：清理 tracking 参数、链接去重 |
| `extensions/chromium/src/http.ts` | HTTP fallback 提交到 `/api/videos/extract` |
| `extensions/chromium/src/native.ts` | Native Messaging 提交到 `com.aipulse.native_host` |
| `extensions/chromium/src/context.ts` | Content script 入口占位（预留） |
| `extensions/chromium/src/platform/registry.ts` | 平台提取器注册表 |
| `extensions/chromium/src/platform/_helpers.ts` | 链接提取通用辅助函数 |
| `extensions/chromium/src/platform/bilibili.ts` | Bilibili 链接与字幕选项提取 |
| `extensions/chromium/src/platform/bilibili-subtitles.ts` | Bilibili 字幕解析与格式化 |
| `extensions/chromium/src/platform/douyin.ts` | 抖音链接提取（feed slide / 视频页 / 图文页） |
| `extensions/chromium/src/platform/douyin-share.ts` | 抖音分享短链捕获逻辑（isolated world 侧） |
| `extensions/chromium/src/platform/douyin-share-main.ts` | MAIN world 网络请求拦截器 |
| `extensions/chromium/src/platform/xiaohongshu.ts` | 小红书笔记/分享链接提取 |
| `extensions/chromium/src/platform/wechat.ts` | 微信公众号文章链接提取 |
| `extensions/chromium/vite.config.ts` | Vite + vite-plugin-web-extension 构建配置 |
| `extensions/chromium/playwright.config.ts` | E2E 测试配置 |
| `extensions/chromium/vitest.config.ts` | 单元测试配置 |
| `extensions/chromium/tests/unit/*.test.ts` | Vitest 单元测试 |
| `extensions/chromium/tests/e2e/*.spec.ts` | Playwright E2E 测试 |
| `extensions/chromium/tests/manual/real-browser-test-cases.md` | 人工真实浏览器测试用例 |

### 3.2 桌面端配合修改

| 文件 | 修改内容 |
|---|---|
| `src-tauri/src/native_messaging.rs` | 新增 Native Messaging host：读取 Chrome 长度前缀帧，转发给 Python sidecar，回写响应 |
| `src-tauri/src/lib.rs` | 注册 `--native-messaging` CLI 模式，启动 native messaging loop |
| `src-tauri/src/commands.rs` | Tauri 前端命令 `submit_url` 等已存在，扩展通过 native host 直接访问 sidecar |
| `src/aipulse/desktop/sidecar.py` | `submit_url` 方法支持 `source=browser_extension`、`mode`、`tags`、`subtitle_text` 等字段 |

---

## 4. 端到端 Workflow

```
[用户打开 B站/抖音/小红书/微信文章/YouTube]
            │
            ▼
[Content Script 扫描页面链接]
            │
            ▼
[Background 接收 FOUND_LINKS，按 tab 存储并更新 badge]
            │
            ▼
[用户点击扩展图标打开 Popup]
            │
            ▼
[Popup 从 Background 获取当前 tab 的识别结果]
            │
            ▼
[用户填写标题/标签/选择字幕/模式]
            │
            ▼
[Popup 发送 SUBMIT_URL 到 Background]
            │
            ▼
[Background 优先 Native Messaging → Tauri sidecar]
            │  fallback: HTTP POST /api/videos/extract
            ▼
[Python sidecar 创建 Task 并启动 pipeline]
```

---

## 5. 实施任务

### Phase 1：基础骨架（第 1 周）

1. **初始化扩展工程**
   - 创建 `extensions/chromium/`，配置 `package.json`、TypeScript、`vite-plugin-web-extension`、Vitest、Playwright。
   - 编写 `manifest.json`（Manifest V3），申请必要权限：`activeTab`、`scripting`、`contextMenus`、`nativeMessaging`、`notifications`、`storage`、`tabs`。
   - 配置 host_permissions 覆盖目标平台。

2. **核心通信层**
   - 实现 `src/types.ts` 公共类型。
   - 实现 `src/http.ts`：带 timeout 的 HTTP fallback。
   - 实现 `src/native.ts`：基于 `chrome.runtime.connectNative` 的 JSON-RPC 调用。
   - 实现 `src/utils.ts`：tracking 参数清理、去重。

3. **Background Service Worker**
   - 实现 `src/background.ts`：
     - 消息监听：`FOUND_LINKS`、`GET_FOUND_LINKS`、`SUBMIT_URL`、`FETCH_JSON`。
     - 右键菜单：归档当前页面 / 归档此链接。
     - Badge 管理：按 tab 计数，导航时清理。
     - 提交分发：Native Messaging 优先，失败 fallback HTTP。

### Phase 2：平台识别与 Popup（第 1–2 周）

4. **内容脚本与平台提取器**
   - 实现 `src/content.ts`：页面加载后扫描，SPA 变化时去抖重扫，响应 popup 消息。
   - 实现平台提取器：
     - `platform/bilibili.ts`：识别 `bilibili.com/video/BV...` 和 `b23.tv` 短链。
     - `platform/douyin.ts`：识别 feed active slide、视频页、图文页。
     - `platform/xiaohongshu.ts`：识别笔记页和 `xhslink.com` 短链。
     - `platform/wechat.ts`：识别 `mp.weixin.qq.com/s/...`。
   - 实现 `platform/registry.ts` 统一注册。

5. **Popup UI**
   - 实现 `src/popup.tsx`：
     - 显示当前 tab 识别到的链接。
     - 模式切换：`archive` / `knowledge_check`。
     - 标题、标签输入框。
     - 复制链接按钮。
     - 提交按钮与状态反馈。

6. **Bilibili 字幕**
   - 实现 `platform/bilibili-subtitles.ts`：
     - 从页面提取字幕选项。
     - 通过 background `FETCH_JSON` 请求 API 字幕选项。
     - 格式化字幕条目为文本。
   - popup 中选择字幕后请求 content script 加载具体内容。

### Phase 3：抖音分享短链（第 2 周）

7. **MAIN world 拦截器**
   - 实现 `platform/douyin-share-main.ts`：在 `world: "MAIN"` 注入，拦截 `fetch`/`XHR`，识别抖音 `web_shorten` 响应，通过 `postMessage` 回传。

8. **Isolated world 捕获逻辑**
   - 实现 `platform/douyin-share.ts`：
     - `installShareCapture` 监听 `message` 事件。
     - `requestShareUrlCapture` 模拟悬停分享按钮，等待捕获结果。
     - popup 在识别到抖音链接后自动触发捕获。

### Phase 4：桌面端集成（第 2–3 周）

9. **Native Messaging Host**
   - 实现 `src-tauri/src/native_messaging.rs`：长度前缀帧读写、转发 sidecar、16MB 上限保护。
   - 在 `src-tauri/src/lib.rs` 添加 `--native-messaging` 启动分支。
   - 配置 host manifest（按平台分别处理 macOS/Windows/Linux 注册）。

10. **Sidecar 适配**
    - 修改 `src/aipulse/desktop/sidecar.py` 的 `_submit_url`：
      - 接收 `source`、`mode`、`tags`、`subtitle_text`、`subtitle_language`。
      - `source` 默认值改为可传入，`browser_extension` 时写入 Task。
      - 根据 `mode` 决定后续 pipeline 分支（archive vs knowledge_check）。

### Phase 5：测试与发布准备（第 3 周）

11. **单元测试**
    - `tests/unit/background.test.ts`：消息处理、URL 校验、提交分发。
    - `tests/unit/platform.test.ts`：各平台链接提取正则。
    - `tests/unit/bilibili-subtitles.test.ts`：字幕解析。
    - `tests/unit/utils.test.ts`：tracking 参数清理、去重。

12. **E2E 测试**
    - `tests/e2e/extension.spec.ts`：扩展加载、popup 交互、提交到 mock 服务器。
    - `tests/e2e/douyin.spec.ts`：抖音链接识别与短链捕获。
    - `tests/e2e/douyin-article.spec.ts`：抖音图文页。
    - `tests/e2e/subtitle.spec.ts`：Bilibili 字幕加载。
    - `tests/e2e/obsidian-archive.spec.ts`：完整归档链路。
    - 配置 mock HTTP 服务器和 E2E 测试桥（`__E2E__`）。

13. **真实浏览器测试**
    - 完善 `tests/manual/real-browser-test-cases.md`，覆盖 Bilibili、抖音、小红书、微信、右键菜单、Native Messaging 等场景。

14. **CI 集成**
    - 在根目录 CI 中添加扩展构建命令：`cd extensions/chromium && pnpm install && pnpm build`。
    - 添加扩展单元测试：`pnpm test`。
    - E2E 测试在 CI 中可选运行（受浏览器环境限制）。

---

## 6. 测试计划

| 层级 | 范围 | 工具 | 目标 |
|---|---|---|---|
| 单元 | background 消息、平台正则、字幕解析、utils | Vitest | 覆盖率 ≥70% |
| E2E | 扩展加载、popup、链接识别、提交到 mock | Playwright | 核心用例自动化 |
| 集成 | Native Messaging ↔ Tauri ↔ sidecar | Rust 单元测试 + 手动 | 帧协议 round-trip |
| 手动 | 真实浏览器各平台页面 | `tests/manual/real-browser-test-cases.md` | 上线前验证 |

### 关键 E2E 用例

- TC-01：Bilibili 视频页识别与 badge 更新。
- TC-02：抖音首页 feed active slide 识别。
- TC-03：小红书笔记页及短链识别。
- TC-04：微信公众号文章识别。
- TC-05：Popup 提交到 mock HTTP 服务器。
- TC-06：`knowledge_check` 模式提交。
- TC-07：右键菜单归档当前页面。
- TC-08：右键菜单归档链接。
- TC-09：无支持链接页面不显示 badge。
- TC-10：Native Messaging fallback 到 HTTP。
- TC-11：无效 URL 被拒绝。
- TC-12：SPA 导航后重新识别。

---

## 7. 风险与应对

| 风险 | 影响 | 应对 |
|---|---|---|
| Chrome Web Store 审核对 `nativeMessaging` 和 `tabs` 权限提出质疑 | 中 | 在商店描述中明确说明扩展仅与本地 AIPulse 桌面应用通信；提供隐私政策 |
| 抖音页面结构频繁变化导致提取器失效 | 高 | 提取器使用多个 heuristics（data-e2e、class、href、data-aweme-id）；E2E 监控及时告警 |
| B站 API 字幕需要登录 Cookie | 中 | 背景脚本请求携带 credentials，依赖用户已在浏览器登录 B站 |
| Native Messaging host manifest 安装需要用户或安装器配合 | 中 | 提供安装脚本；HTTP fallback 保证未安装时也能基本使用 |
| Manifest V3 service worker 生命周期导致长任务被 kill | 中 | 保持消息处理异步但快速；复杂任务交给 sidecar，不在扩展内执行 |
| 扩展包体积因 React 变大 | 低 | 仅 popup 使用 React，content/background 保持轻量；build 时 tree-shake |

---

## 8. 验收标准

- [ ] `pnpm build` 成功产出 `extensions/chromium/dist`，可手动加载到 Chrome 无错误。
- [ ] 在 Bilibili 视频页点击扩展图标，popup 显示视频链接并可提交到 mock 服务器。
- [ ] 在抖音首页，badge 显示当前 active slide 视频数量；popup 能获取官方分享短链。
- [ ] 右键菜单「归档当前页面」和「归档此链接」可正常工作。
- [ ] 桌面端启动时，扩展优先通过 Native Messaging 提交；关闭桌面端后自动 fallback HTTP。
- [ ] 单元测试全部通过；E2E 核心用例在本地可通过 `pnpm e2e` 运行。
- [ ] 真实浏览器测试用例覆盖 Bilibili、抖音、小红书、微信公众号，人工验证通过。

---

## 9. 后续版本（Deferred）

- Firefox 扩展适配
- Safari 扩展适配
- 支持更多平台：知乎、Twitter/X、Threads、B站专栏等
- Popup 内直接显示任务处理进度（SSE/WebSocket）
- 扩展内配置页面（服务器地址、默认模式、标签模板）
- 自动归档当前播放列表/收藏夹
