# AIPulse 桌面端 v0.2 重设计文档

> 版本：v0.2  
> 日期：2026-07-09  
> 状态：已实施并与当前代码库同步  
> 目标：将 AIPulse 桌面端从早期多窗口/命令行交互重构为统一的 macOS menu bar 弹窗应用，提供「输入 → 任务 → 设置」三视图，并建立与 Python sidecar 的稳定 JSON-RPC 通信。

---

## 1. 概述

### 1.1 背景

AIPulse v0.1 已跑通核心后端流程：链接/RSS → 下载/提取 → 转写 → 总结 → 归档 Obsidian → 飞书/微信通知。但早期桌面端缺少统一、轻量的用户界面，操作分散在命令行、多个独立窗口与系统菜单中。v0.2 重设计的目标是把后端能力收敛到一个常驻菜单栏的弹出式应用中，让用户可以「一键粘贴链接 → 实时看进度 → 快速回看任务 → 随时调整设置」。

### 1.2 设计目标

1. **常驻菜单栏**：应用以 tray icon 形态运行，无 Dock 图标，随叫随到；
2. **单窗口三视图**：一个主弹出窗口内通过 Tab 切换「输入 / 任务 / 设置」；
3. **即时反馈**：提交链接后实时展示进度条、状态文案与最近任务；
4. **视觉统一**：浅色高级感 + 珊瑚橙强调色，与 AIPulse 品牌一致；
5. **跨语言稳定通信**：Tauri Rust 前端通过 JSON-RPC over stdio 与 Python sidecar 通信；
6. **可测试**：前端视图与 Rust 命令均配备单元测试。

### 1.3 非目标

- 不追求 Windows/Linux 菜单栏体验完全对齐（当前以 macOS 为主战场）；
- 不做复杂的状态管理库（无 Pinia/Vuex，视图级状态足够）；
- 不做 Web Dashboard 的完整功能复刻（热点看板由 `web/` 负责）；
- 不内置视频播放器或文章阅读器。

---

## 2. 总体架构

### 2.1 系统上下文

```
┌─────────────────────────────────────────────────────────────┐
│                    macOS 菜单栏 (AIPulse)                    │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Vue 3 前端 (frontend/src)                           │   │
│  │  AppHeader │ InputView │ TasksView │ SettingsView    │   │
│  └──────────────────┬──────────────────────────────────┘   │
│                     │ invoke / listen                        │
│                     ▼                                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Tauri Rust (src-tauri/src)                          │   │
│  │  commands.rs │ app_state.rs │ lib.rs (tray/window)  │   │
│  └──────────────────┬──────────────────────────────────┘   │
│                     │ JSON-RPC over stdio                    │
│                     ▼                                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Python sidecar (src/aipulse)                        │   │
│  │  链接解析 / 下载 / 转写 / 总结 / 归档 / 推送        │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 技术栈

| 层级 | 选型 |
|---|---|
| 桌面框架 | Tauri v2.11+（Rust） |
| 前端框架 | Vue 3.5+，Composition API，`<script setup>` |
| 路由 | Vue Router 4.6+，`createWebHashHistory` |
| 构建 | Vite 8+，TypeScript 6.0+，`vue-tsc` |
| 通信 | Tauri `invoke` + `listen`；后端 sidecar JSON-RPC over stdio |
| 通知 | `tauri-plugin-notification` |
| 测试 | Vitest + jsdom + `@vue/test-utils`；Rust `cargo test` |

### 2.3 通信模型

1. **调用（Invoke）**：前端通过 `invoke('command_name', args)` 调用 Rust 命令；Rust 通过 `AppState::send_request` 将请求序列化为 JSON-RPC 发送给 Python sidecar；sidecar 返回后由 Rust 回传给前端。
2. **事件（Listen）**：Python sidecar 在任务生命周期中主动推送 `task_progress`、`task_complete`、`notification` 等通知；Rust 在 `handle_sidecar_message` 中将这些消息通过 `handle.emit()` 转发为 Tauri 事件；前端使用 `listen()` 订阅并更新 UI。
3. **超时**：单次 JSON-RPC 请求 10 秒超时，由 `app_state.rs` 统一控制。

---

## 3. 窗口与交互模型

### 3.1 窗口策略

应用采用**无标题栏弹出窗口**模型，所有窗口尺寸固定为 **560 × 640**，无边框、不可缩放、始终置顶、不显示在 Dock/任务栏：

```rust
WebviewWindow::builder(...)
    .inner_size(560.0, 640.0)
    .resizable(false)
    .maximizable(false)
    .minimizable(false)
    .decorations(false)
    .always_on_top(true)
    .skip_taskbar(true)
    .accept_first_mouse(true)
    .focused(true)
    .visible(true)
    .shadow(true)
```

窗口标签（label）：

| 标签 | 用途 | 入口 |
|---|---|---|
| `input` | 输入链接（主窗口） | 点击 tray icon / 菜单「输入链接...」 |
| `tasks` | 最近任务 | 菜单「最近任务」 |
| `settings` | 设置 | 菜单「设置...」 |

### 3.2 显隐行为

- 点击 tray icon 时，在图标正下方弹出 `input` 窗口；
- 弹出窗口在失去焦点（`Focused(false)`）或用户按 `Esc` 时自动隐藏，而非关闭；
- 点击窗口关闭按钮时阻止默认退出，改为隐藏窗口；
- 已创建的窗口再次打开时直接 `show` + `set_focus`，避免重复初始化。

实现位置：`src-tauri/src/lib.rs:61-78`。

### 3.3 菜单栏菜单

Tray 右键/左键菜单项（`src-tauri/src/lib.rs:237-242`）：

- 输入链接...
- 最近任务
- 设置...
- 打开 Obsidian
- 分隔线
- 退出

Tray 菜单 ID 常量定义在 `src-tauri/src/menu.rs:5-9`。

---

## 4. 视觉设计

### 4.1 设计原则

- **轻量**：小尺寸弹窗，信息密度适中；
- **高级感**：大面积米白背景、细边框、柔和阴影、低饱和强调色；
- **可操作性**：按钮和输入框使用珊瑚橙强调色，状态色明确区分任务状态；
- **原生感**：header 可拖拽、无系统标题栏、圆角面板。

### 4.2 设计令牌

定义在 `frontend/src/styles/tokens.css`：

```css
:root {
  --surface-bg: #F7F7F5;
  --surface-elevated: #FFFFFF;
  --surface-elevated-hover: #FAFAF8;
  --border-subtle: #E8E8E6;
  --text-primary: #1A1A1A;
  --text-secondary: #6B6B6B;
  --accent-coral: #F97316;
  --accent-coral-glow: rgba(249, 115, 22, 0.2);
  --status-amber: #F59E0B;
  --status-green: #22C55E;
  --status-red: #EF4444;

  --font-display: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
  --font-body: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
  --font-mono: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, monospace;

  --text-xs: 11px;
  --text-sm: 13px;
  --text-base: 15px;
  --text-lg: 18px;
  --text-xl: 22px;
  --text-2xl: 28px;

  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 16px;

  --shadow-glow: 0 0 24px var(--accent-coral-glow);
}
```

### 4.3 全局样式

`frontend/src/style.css`：

- 重置 `html/body/#app` 宽高为 100%；
- 默认字体 `var(--font-body)`，字号 `var(--text-base)`；
- 全局 `border-box`；
- 自定义窄滚动条，与浅色主题协调。

---

## 5. 页面设计

### 5.1 输入页（`/input`）

文件：`frontend/src/views/InputView.vue`

**布局：**

- 页面垂直居中，顶部状态提示「粘贴链接，开始处理」；
- 一个大型居中单行输入框，占位文案「粘贴 RSS / 视频 / 文章链接」；
- 输入框下方是「开始处理」按钮；
- 提交后展示细进度条与进度文案；
- 底部展示最近 3 条任务预览。

**交互：**

- 输入框在页面挂载时自动聚焦；
- 支持 `Enter` 提交；
- 空输入或提交中禁用按钮；
- 提交中按钮文案变为「提交中...」；
- 成功提交后清空输入框并显示「已加入处理队列」；
- 失败时显示错误文案；
- 按 `Esc` 调用 `hide_window({ label: 'input' })` 隐藏窗口；
- 监听 `task_progress` 事件更新进度条与最近任务；
- 监听 `task_complete` 事件清空进度条并显示成功/失败结果。

**最近任务预览：**

- 最多保留 3 条；
- 显示状态色点 + 任务标题（无标题时显示 URL）；
- 状态色：`pending` 灰、`running` 琥珀、`completed` 绿、`failed` 红；
- 同一任务更新时去重替换，而非追加。

### 5.2 任务页（`/tasks`）

文件：`frontend/src/views/TasksView.vue`

**布局：**

- 顶部标题「最近任务」+ 任务数量；
- 错误 banner（加载失败或重试失败时）；
- 空态：图标 + 「还没有任务」+ 「去输入页粘贴一个链接开始」+ 跳转按钮；
- 任务列表：卡片堆叠视觉，最新任务完整显示，旧任务依次向下偏移并轻微透明。

**交互：**

- 挂载时调用 `list_tasks({ limit: 50 })`；
- 实时监听 `task_progress` 事件，动态新增或更新任务；
- 任务状态标签：`PENDING` / `RUNNING` / `DONE` / `FAILED`；
- 失败任务卡片显示红色边框与「重试」按钮；
- 重试时调用 `retry_task({ task_id })`，按钮进入禁用状态；
- 点击「前往输入页」路由跳转到 `/input`。

**视觉细节：**

- 运行中卡片带有琥珀色呼吸阴影动画；
- 卡片进入有轻微上滑动画；
- 任务来源域名使用等宽字体显示。

### 5.3 设置页（`/settings`）

文件：`frontend/src/views/SettingsView.vue`

**布局：**

- 页面标题「设置」；
- 可滚动内容区，包含 4 个折叠面板；
- 底部固定「保存」按钮与错误/成功提示。

**面板：**

1. **Kimi Code LLM**（默认展开）
   - API Key（密码输入，可显示/隐藏）
   - Base URL（默认 `https://api.kimi.com/coding/v1`）
   - Model（默认 `kimi-for-coding`）
2. **Obsidian**（默认折叠）
   - Vault 路径
   - 归档文件夹（默认 `AIPulse`）
3. **飞书推送**（默认折叠）
   - Webhook URL
   - Secret（密码输入，可显示/隐藏）
4. **微信推送**（默认折叠）
   - AppID
   - AppSecret（密码输入，可显示/隐藏）
   - Template ID
   - OpenID

**交互：**

- 点击面板标题展开/折叠；
- 密码字段右侧提供「显示 / 隐藏」切换；
- 保存时构建 payload：若字段值包含 `***`，则跳过该字段，避免把后端脱敏后的占位值再传回去；
- 保存过程中按钮显示「保存中...」，成功后显示「已保存」1.5 秒；
- 保存失败在按钮上方显示「保存失败，请重试」；
- 加载失败时同样显示错误文案。

---

## 6. 组件设计

### 6.1 AppHeader

文件：`frontend/src/components/AppHeader.vue`

- 左侧品牌区：logo 图标 + `AIPulse` 文字；
- 右侧 Tab 导航：输入、任务、设置；
- 当前 Tab 使用珊瑚橙下划线高亮；
- Header 整体可拖拽（`-webkit-app-region: drag`），但品牌与 Tab 区域不可拖拽以保证可点击；
- Header 高度 44px，底部 1px 细边框。

### 6.2 App.vue

文件：`frontend/src/App.vue`

- 根容器 `app-shell` 垂直布局：header + main；
- main 区域占满剩余空间并隐藏溢出，视图内部自行滚动；
- 背景使用 `var(--surface-bg)`。

---

## 7. Tauri 命令清单

定义在 `src-tauri/src/commands.rs`，注册于 `src-tauri/src/lib.rs:48-60`：

| 命令 | 参数 | 说明 |
|---|---|---|
| `submit_url` | `url: String`, `source: String` | 提交链接到 sidecar，返回 `task_id` |
| `get_task_status` | `task_id: String` | 查询单个任务状态 |
| `list_tasks` | `limit: Option<u32>` | 列出最近任务，默认 50，最大 200 |
| `retry_task` | `task_id: String` | 重试失败任务 |
| `get_settings` | 无 | 获取当前设置 |
| `update_settings` | `settings: Value` | 更新设置，返回更新后的设置 |
| `open_obsidian` | 无 | 打开 Obsidian vault（支持环境变量回退） |
| `open_settings_window` | 无 | 打开/显示 settings 窗口 |
| `open_tasks_window` | 无 | 打开/显示 tasks 窗口 |
| `show_input_window` | 无 | 打开/显示 input 窗口 |
| `hide_window` | `label: String` | 按 label 隐藏窗口 |

### 7.1 Sidecar JSON-RPC 协议

`src-tauri/src/app_state.rs` 封装：

- 请求格式：`{ "jsonrpc": "2.0", "id": 1, "method": "...", "params": {} }`
- 响应格式：`{ "jsonrpc": "2.0", "id": 1, "result": {} }` 或 `{ "error": { "code", "message" } }`
- 请求超时：10 秒
- 待处理请求表：`HashMap<u64, oneshot::Sender<SidecarResponse>>`

---

## 8. 通知与系统集成

### 8.1 任务完成通知

`src-tauri/src/lib.rs:207-234`：

- sidecar 推送 `task_complete` 后，Rust 调用 `tauri-plugin-notification`；
- 成功时标题为文章标题，正文「处理完成，已归档到 Obsidian」；
- 失败时正文「处理失败，请查看任务列表重试」。

### 8.2 打开 Obsidian

`open_obsidian` 命令（`src-tauri/src/commands.rs:92-114`）：

- 优先读取设置中的 `obsidian_vault_path`；
- 回退环境变量 `OBSIDIAN_VAULT_PATH`；
- 再次回退 `$HOME/Documents/Obsidian Vault`；
- 通过 `obsidian://open?vault=` URL scheme 打开。

### 8.3 启动行为

- 应用启动时设置 macOS `ActivationPolicy::Accessory`（`src-tauri/src/lib.rs:33`），不在 Dock 显示；
- 同步启动 Python sidecar，创建 `data/` 与 `downloads/` 目录（`src-tauri/src/lib.rs:90-140`）；
- sidecar stdout 持续读取并分发事件；stderr 重定向到 Rust log。

---

## 9. 安全与隐私

### 9.1 凭证输入

- API Key、飞书 Secret、微信 AppSecret 默认以 `password` 类型输入框展示；
- 用户可点击「显示」临时查看，离开后仍可隐藏；
- 设置保存时，若字段值包含 `***` 则视为后端脱敏占位符，不会回传。

### 9.2 URL 与 Shell 安全

- `tauri.conf.json` 中 `shell.open` 仅允许 `^https?://` 与 `obsidian://open\?vault=`；
- Obsidian vault 路径通过 `urlencoding::encode` 编码后再拼接 URL。

### 9.3 错误处理

- 前端错误仅展示简要文案，不暴露底层栈；
- Rust 命令统一将错误转换为字符串回传；
- sidecar stderr 进入 log，不向 UI 泄露。

---

## 10. 可访问性与性能

### 10.1 可访问性

- 输入框与按钮有明确的焦点状态；
- 设置面板使用 `<label>` 关联输入框；
- 错误信息使用 `role="alert"`；
- 支持 `prefers-reduced-motion: reduce`，禁用任务卡片动画与面板展开过渡。

### 10.2 性能

- 弹出窗口固定小尺寸，启动快；
- 任务列表最多拉取 50 条，前端不做虚拟列表（数量可控）；
- 事件监听在组件卸载时清理，避免内存泄漏；
- 无重型依赖，构建产物小。

---

## 11. 构建与开发

### 11.1 前端开发

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

`vite.config.ts` 配置：

- `base: './'`：支持以 `file://` 协议加载；
- `port: 5173`，`strictPort: true`；
- `envPrefix: ['VITE_', 'TAURI_']`。

### 11.2 Tauri 开发

```bash
cd src-tauri
cargo tauri dev
```

`tauri.conf.json`：

- `frontendDist`: `../frontend/dist`
- `devUrl`: `http://localhost:5173`
- `beforeBuildCommand` 同步 sidecar 资源后构建前端；
- 打包目标 `dmg`，最低 macOS 版本 `12.0`。

### 11.3 生产构建

```bash
cd src-tauri
cargo tauri build
```

输出 `.dmg` 安装包，应用标识 `com.aipulse.app`。

---

## 12. 测试策略

### 12.1 前端单元测试

使用 Vitest + jsdom + `@vue/test-utils`：

| 测试文件 | 覆盖内容 |
|---|---|
| `frontend/src/components/__tests__/AppHeader.test.ts` | 品牌与 Tab 渲染、当前路由高亮 |
| `frontend/src/views/__tests__/InputView.test.ts` | 输入框渲染、提交、进度条、最近任务、Esc 隐藏 |
| `frontend/src/views/__tests__/TasksView.test.ts` | 列表加载、空态、状态标签、重试、事件更新 |
| `frontend/src/views/__tests__/SettingsView.test.ts` | 面板展开、密码显示切换、保存、脱敏字段跳过 |

运行：

```bash
cd frontend
npm run test:unit
```

### 12.2 Rust 单元测试

`src-tauri/src/commands.rs` 与 `src-tauri/src/app_state.rs` 包含：

- JSON-RPC 响应解析（result/error/缺省情况）；
- 隐藏不存在的窗口报错；
- 已存在窗口复用；
- sidecar 请求/响应管道。

运行：

```bash
cd src-tauri
cargo test
```

---

## 13. 参考文件

- 前端入口：`frontend/src/main.ts`
- 前端路由：`frontend/src/router.ts`
- 前端全局样式：`frontend/src/style.css`
- 设计令牌：`frontend/src/styles/tokens.css`
- 应用壳：`frontend/src/App.vue`
- 顶部导航：`frontend/src/components/AppHeader.vue`
- 输入视图：`frontend/src/views/InputView.vue`
- 任务视图：`frontend/src/views/TasksView.vue`
- 设置视图：`frontend/src/views/SettingsView.vue`
- Tauri 主入口：`src-tauri/src/lib.rs`
- Tauri 命令：`src-tauri/src/commands.rs`
- Sidecar 状态：`src-tauri/src/app_state.rs`
- Tray 常量：`src-tauri/src/menu.rs`
- Tauri 配置：`src-tauri/tauri.conf.json`
- 相关实施计划：`docs/superpowers/plans/2026-07-09-v0.2-web-dashboard.md`
