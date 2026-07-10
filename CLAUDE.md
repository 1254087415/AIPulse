# AIPulse — Claude 项目指令

## 项目一句话

AIPulse 是一个桌面端 AI 内容/任务管理工具，采用 Tauri + Python sidecar + Vue + Chromium Extension 架构。

## 沟通语言约定

- **所有向用户输出的思考、解释、分析、方案对比、错误说明、下一步建议，必须使用中文。**
- 代码内部的命名、注释、变量名仍然遵循项目代码风格（英文）。
- 这条规则适用于本项目的所有子系统（Tauri、Python、Vue、Extension）。

## 任务完成与验证流程

### 1. 完成任务后必须启动验证子 agent

- 任何编码、修改、重构任务完成后，父 agent **不能自行宣布完成**。
- 必须启动一个独立的验证子 agent，针对本次改动运行相关测试与检查。
- 验证范围至少包括：单元测试、类型检查、 lint、以及与本任务相关的 E2E / 集成测试（如适用）。

### 2. 验证子 agent 有权打回重做

- 如果验证子 agent 发现测试失败、类型错误、lint 错误、回归问题或遗漏场景，必须明确列出问题。
- 验证子 agent 有权要求父 agent **返工修改**，父 agent 必须继续修复，而不是把问题抛给用户。
- 只有当验证子 agent 确认通过后，父 agent 才能向用户汇报任务完成。

### 3. 验证不通过时的处理

- 父 agent 根据验证子 agent 的反馈修复问题。
- 修复后再次启动验证子 agent 进行验证。
- 重复此循环，直到验证通过。

## 快速入口

| 子系统 | 路径 | 主要技术 |
|--------|------|----------|
| 前端界面 | `frontend/` | Vue 3 + Vite |
| 桌面后端 | `src-tauri/` | Rust + Tauri |
| Python sidecar | `src-python/`（`aipulse` 包） | Python |
| 浏览器扩展 | `extensions/chromium/` | TypeScript + Chrome Extension API |
| 测试 | `tests/`、`frontend/src/views/__tests__/`、`extensions/chromium/tests/` | pytest、Vitest、Playwright |

## 项目特定约定

### 1. 修改 Tauri 窗口尺寸

陷阱：Tauri 窗口存在多个入口点。修改窗口尺寸时，**必须同时同步托盘点击入口和菜单点击入口**，否则只有一个入口生效。

### 2. 新增或修改 Python sidecar

- 必须**完整打包 `aipulse` 包**，不能只拷贝单个 `.py` 文件。
- 必须验证**开发环境**和**生产环境**的 `sys.path` 都能正确导入 `aipulse`。
- 相关逻辑可参考 `src-tauri/src/app_state.rs` 和 Tauri 打包配置。

### 3. 浏览器扩展平台适配

- 新增平台（如 bilibili / douyin / xiaohongshu）时，需要在 `extensions/chromium/src/platform/` 下新增适配器。
- 同步更新 `background.ts` 和 `content.ts` 中的平台分发逻辑。
- 必须补充对应平台的 fixtures 以及单元测试 / E2E 测试。

### 4. 设置与敏感信息

- 后端设置项在 UI 回填时可能带有掩码或空值，保存时必须**保留原有 secrets**，不能因 UI 未显示而清空。
- 任何密钥、Token、密码都必须走环境变量或系统密钥管理，**禁止硬编码**。

### 5. 浏览器扩展 E2E 测试陷阱

- **构建必须用 `pnpm build:e2e`**（不是 `build`）：`AIPULSE_SUBMIT_URL` 桥在 `content.ts` 被 `if (__E2E__)` 包住，仅 `vite build --mode e2e` 编译进去；普通 build 剥离桥，提交/预览断言直接失败。
- **MV3 在 headless 下**：用 `headless: false` + args `--headless=new`。Playwright 的 `headless: true` 会注入 legacy 参数，service worker 注册不上。
- **读识别结果走 `chrome.storage.local.get('foundLinks')`，不要用 `GET_FOUND_LINKS`**：后者读内存 `foundLinksCache`，service worker 一回收就空。
- **mock server 端口必须在 `host_permissions` 内**（目前仅 `localhost:3456`）：用其他端口会触发 CORS 预检 `OPTIONS`，mock 必须回 `Access-Control-*`，否则真实 POST 被 Chromium 拦截。
- **抖音 note 页**：`lf-security.bytegoofy.com` 通过 `document.write` 注入 parser-blocking 反爬脚本，永不 `document_idle` → content script 不执行。测试里加 `page.route('**/*bytegoofy.com/**', r => r.abort())`（只拦第三方脚本，页面内容仍是真实 Douyin）。
- **Bilibili AI 字幕**：`aisubtitle.hdslb.com` 返回 `Access-Control-Allow-Origin: *`，请求须 `credentials: 'omit'`，否则被 Chromium 拒绝（见 `background.ts` / `bilibili-subtitles.ts`）。

## 不应出现在这里的

- 通用代码风格、测试覆盖率、TDD 流程、Git 提交规范、安全审查清单 → 见 `.claude/rules/ecc/`
- 具体 API 接口定义和详细模块说明 → 见代码本身或独立 `docs/`
- 通用 Vue / Rust / Python 编码规范 → 见各自语言规则文件
