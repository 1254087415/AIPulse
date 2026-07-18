# AIPulse — Agent 项目指令

> **同步约束**：`AGENTS.md` 与 `CLAUDE.md` 内容必须保持一致——修改其中任何一个，必须同步更新另一个。

## 项目一句话

AIPulse 是一个桌面端 AI 内容/任务管理工具，采用 Tauri + Python sidecar + Vue + Chromium Extension 架构。

## 沟通语言约定

- **所有向用户输出的思考、解释、分析、方案对比、错误说明、下一步建议，必须使用中文。**
- 代码内部的命名、注释、变量名仍然遵循项目代码风格（英文）。
- 这条规则适用于本项目的所有子系统（Tauri、Python、Vue、Extension）。

## 调研与需求分析前的 Grill-Me 流程

> 在开展任何新功能、新模块或重大改动的**项目调研、需求分析、技术方案设计**之前，**必须先调用 `/grill-me <主题>` 进入方案拷问环节**。

调用方式：

```text
/grill-me <你要被拷问的计划/设计/需求>
```

例如：

```text
/grill-me 给 AIPulse 扩展增加小红书图文解析能力
/grill-me v0.3 的 AI 摘要工作流 redesign
```

流程要求：

1. **主动触发**：如果用户没有主动调用 `/grill-me`，agent 应建议在正式调研前先用 `/grill-me` 澄清方向。
2. **目标澄清**：明确要解决什么问题、为谁解决、成功标准是什么。
3. **范围收敛**：明确本次做哪些、不做哪些；识别可能的范围蔓延。
4. **假设与风险**：列出关键假设、依赖项、最大风险点。
5. **替代方案**：是否已有现成方案？能否用更简单的方式满足需求？
6. **产出确认**：拷问结束后，再进入 `planner` / `architect` / 文档调研等后续步骤。

> 此流程不替代后续的方案设计与技术调研，而是确保在动手调研前先对齐问题本质，避免在错误的方向上做大量工作。

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

## 文件路由（遇到问题时先读这里）

| 你在做什么 | 先读哪个文件 | 说明 |
|------------|--------------|------|
| 看项目需求与范围 | `docs/AIPulse需求文档v0.1.md` | 产品愿景、功能范围、阶段目标 |
| 看 v0.1 实施计划 | `docs/v0.1-implementation-plan.md` | 里程碑拆解、任务排期、验收标准 |
| 看 v0.2 应用重设计 | `docs/superpowers/specs/2026-07-09-aipulse-app-redesign-design.md` | 新架构与交互设计决策 |
| 看 v0.2 Web Dashboard 设计 | `docs/superpowers/specs/2026-07-09-v0.2-web-dashboard-design.md` | 前端仪表盘设计与数据流 |
| 写前端 / 改 Vue 组件 | `frontend/`（Vue 3 + Vite） | 组件源码 + `frontend/src/views/__tests__/` 单元测试 |
| 写桌面后端 / 改 Tauri 逻辑 | `src-tauri/`（Rust + Tauri） | 窗口、托盘、sidecar 生命周期 |
| 写 Python sidecar / 改业务逻辑 | `src-python/`（`aipulse` 包） | 业务模块 + `tests/`（pytest） |
| 写浏览器扩展 / 加平台适配 | `extensions/chromium/` | TS + Chrome Extension API；fixtures 与 E2E 在 `extensions/chromium/tests/` |
| 不了解某个模块实现 | 直接读对应源码 + 单元测试 | 测试即文档，优先看 `tests/`、`__tests__/`、`extensions/chromium/tests/` |

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
