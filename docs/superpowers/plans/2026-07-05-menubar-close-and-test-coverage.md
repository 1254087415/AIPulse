# AIPulse Menubar 窗口关闭行为与 Rust 测试覆盖率提升计划

> 日期：2026-07-05  
> 范围：Tauri 桌面端 menubar 应用（macOS 优先）  
> 预计工期：**1 周**

---

## 1. 目标与范围

### 1.1 目标

- 将 menubar 弹窗（输入、设置、任务列表）的 **关闭行为** 从「销毁窗口 / 退出应用」改为 **「隐藏窗口」**，保证应用在后台持续运行、Python sidecar 不中断。
- 点击 tray icon 时显示输入窗口，并自动定位到 tray 图标下方。
- 弹窗失去焦点时自动隐藏，保持桌面整洁。
- 提供前端可调用的 `hide_window` 命令，用于主动隐藏任意弹窗。
- 提升 `src-tauri/src` 核心 Rust 模块的单元测试覆盖率，目标 **≥ 80%**。

### 1.2 范围

涉及文件：

- `src-tauri/src/lib.rs` — 应用入口、`setup_tray`、窗口事件处理、sidecar 消息循环。
- `src-tauri/src/commands.rs` — Tauri 命令：`hide_window`、`show_input_window`、`open_settings_window`、`open_tasks_window`、窗口创建辅助函数。
- `src-tauri/src/menu.rs` — tray 菜单常量与窗口定位辅助函数。
- `src-tauri/src/app_state.rs` — sidecar 状态管理、请求 / 响应路由。

### 1.3 明确不做

- 不改动前端 Vue 页面结构与样式。
- 不新增 sidecar JSON-RPC 业务方法。
- 不处理 Windows/Linux tray 多平台差异（macOS 优先，其他平台保持默认行为）。
- 不做端到端 UI 自动化测试（超出本计划范围）。

---

## 2. 关键缺口决策

### 2.1 关闭按钮应该退出还是隐藏？

**决策**：popup 窗口（`input` / `settings` / `tasks`）点关闭按钮时仅隐藏，不退出应用；仅 tray 菜单「退出」才结束进程。

- 原因：menubar 应用常驻后台，用户误点关闭按钮不应终止 sidecar 与后台任务。
- 实现：在 `on_window_event` 中监听 `WindowEvent::CloseRequested`，对 popup label 调用 `api.prevent_close()` + `window.hide()`。

### 2.2 失去焦点时是否隐藏？

**决策**：popup 窗口失去焦点时自动隐藏。

- 原因：menubar 弹窗属于临时面板，点击桌面其他区域应自动收起。
- 实现：监听 `WindowEvent::Focused(false)`，对 popup label 调用 `window.hide()`。

### 2.3 Tray 左键点击行为

**决策**：左键点击 tray icon 时，在图标正下方显示输入窗口（`input`）。

- 实现：使用 `TrayIconBuilder::on_tray_icon_event` 读取 `TrayIconEvent::Click.rect`，计算窗口 `x = icon_x + icon_width/2 - window_width/2`、`y = icon_y + icon_height`，调用 `show_input_window_at`。
- 同时 tray 菜单保留「输入链接...」「最近任务」「设置...」「打开 Obsidian」「退出」五个入口。

### 2.4 测试策略

**决策**：使用 Tauri 提供的 `tauri::test::mock_app()` 进行离线单元测试，使用 `tokio::process::Command::new("cat")` 模拟 sidecar 的 stdin/stdout。

- 避免在单元测试中启动真实 Python sidecar。
- 窗口行为测试通过 mock app 创建 / 查找窗口并断言 show/hide 结果。

---

## 3. 架构变化

### 3.1 修改模块

| 文件 | 修改内容 |
|---|---|
| `src-tauri/src/lib.rs` | 新增 `on_window_event` 处理器：`CloseRequested` 阻止关闭并隐藏 popup；`Focused(false)` 隐藏 popup |
| `src-tauri/src/lib.rs` | `setup_tray` 中配置 `.show_menu_on_left_click(false)`，左键点击触发输入窗口定位显示 |
| `src-tauri/src/commands.rs` | 新增 `hide_window_by_label` 辅助函数与 `hide_window` Tauri command |
| `src-tauri/src/commands.rs` | 新增 `show_or_create_window` 统一封装，支持传入 `tauri::Position` |
| `src-tauri/src/menu.rs` | 新增 tray 菜单 ID 常量与 `center_window_at_tray` 辅助函数 |

### 3.2 不变模块

| 文件 | 说明 |
|---|---|
| `src-tauri/src/app_state.rs` | 业务逻辑不变，仅补充单元测试 |
| `src-tauri/src/python_runner.rs` | 不变 |
| `src-tauri/src/native_messaging.rs` | 不变 |
| `frontend/*` | 不变，前端继续通过 invoke 调用已有命令 |

---

## 4. 任务拆分与依赖

### Phase 1：窗口关闭行为改造

#### Task 1：隐藏而非关闭 popup 窗口

- **文件**：`src-tauri/src/lib.rs`
- **动作**：
  - 新增常量 `INPUT_WINDOW_LABEL`、`SETTINGS_WINDOW_LABEL`、`TASKS_WINDOW_LABEL`。
  - 新增 `is_popup_label(label: &str) -> bool` 判断。
  - 在 `on_window_event` 中处理 `WindowEvent::CloseRequested`：若窗口 label 是 popup，则 `api.prevent_close()` + `window.hide()`。
- **依赖**：无
- **风险**：低
- **TDD**：`tests` 模块覆盖 `is_popup_label` 真/假分支

#### Task 2：失焦自动隐藏 popup 窗口

- **文件**：`src-tauri/src/lib.rs`
- **动作**：
  - 同一 `on_window_event` 中处理 `WindowEvent::Focused(false)`，对 popup 调用 `window.hide()`。
- **依赖**：Task 1
- **风险**：低

#### Task 3：Tray 左键点击定位显示输入窗口

- **文件**：`src-tauri/src/lib.rs`、`src-tauri/src/commands.rs`、`src-tauri/src/menu.rs`
- **动作**：
  - `setup_tray` 设置 `.show_menu_on_left_click(false)`。
  - `on_tray_icon_event` 读取 click rect，计算物理坐标，调用 `commands::show_input_window_at`。
  - `commands.rs` 新增 `show_input_window_at(handle, position)`，复用 `show_or_create_window`。
  - `menu.rs` 新增 `TRAY_INPUT_ID` 等常量。
- **依赖**：无
- **风险**：中（多屏幕 / 高分屏坐标换算）
- **缓解**：统一使用 `tauri::Position::Physical` 计算

#### Task 4：新增 `hide_window` 命令

- **文件**：`src-tauri/src/commands.rs`、`src-tauri/src/lib.rs`
- **动作**：
  - 新增 `hide_window_by_label` 辅助函数。
  - 新增 `#[tauri::command] pub fn hide_window(handle, label: String)`。
  - 在 `invoke_handler` 中注册 `hide_window`。
- **依赖**：无
- **风险**：低
- **TDD**：`hide_window_command_errors_for_missing_label` 等测试

### Phase 2：Rust 单元测试补全

#### Task 5：commands.rs 单元测试

- **文件**：`src-tauri/src/commands.rs`
- **动作**：
  - `unwrap_response`：覆盖 success、error、both present、both missing 四种情况。
  - `hide_window_by_label`：覆盖窗口不存在时的错误。
  - `show_or_create_window`：覆盖已存在窗口与新建窗口两条分支。
- **依赖**：Task 4
- **风险**：低

#### Task 6：app_state.rs 单元测试

- **文件**：`src-tauri/src/app_state.rs`
- **动作**：
  - `complete_request_routes_response_to_pending_sender`
  - `send_request_writes_expected_json_and_receives_response`（使用 `cat` 模拟 sidecar）
  - `write_sidecar_errors_when_sidecar_missing`
  - `clear_sidecar_removes_handle`
- **依赖**：无
- **风险**：低
- **约束**：`cat` 模拟测试仅在 `#[cfg(unix)]` 下运行

#### Task 7：lib.rs 辅助函数测试

- **文件**：`src-tauri/src/lib.rs`
- **动作**：
  - `is_popup_label` 对 `input` / `settings` / `tasks` / 其他 label 的断言。
  - 可选：使用 `tauri::test::mock_app()` 创建窗口并触发 `CloseRequested`，验证窗口未被销毁。
- **依赖**：Task 1
- **风险**：中（Tauri mock event 测试较繁琐）

### Phase 3：集成验证与覆盖率

#### Task 8：本地集成验证

- **动作**：
  - 运行 `cargo test` 全部通过。
  - 手动验证：
    1. 启动应用，点击 tray icon 弹出输入窗口。
    2. 点击关闭按钮，窗口隐藏，应用仍在后台运行。
    3. 点击桌面其他区域，窗口自动隐藏。
    4. tray 菜单「退出」后进程结束。
- **依赖**：Task 1–4
- **风险**：低

#### Task 9：覆盖率检查与门禁

- **动作**：
  - 运行 `cargo llvm-cov --workspace --lcov --output-path lcov.info`（或 `cargo tarpaulin`）。
  - 核心模块（`commands.rs`、`app_state.rs`、`lib.rs` 辅助函数）行覆盖率目标 **≥ 80%**。
  - 在 CI 中加入 `cargo test` 与覆盖率检查步骤。
- **依赖**：Task 5–7
- **风险**：低

---

## 5. 依赖关系图

```
Phase 1: 窗口行为改造
    │
    ├── Task 1: 关闭隐藏
    ├── Task 2: 失焦隐藏
    ├── Task 3: Tray 左键定位
    └── Task 4: hide_window 命令
            │
            ▼
Phase 2: Rust 单元测试补全
    │
    ├── Task 5: commands.rs 测试
    ├── Task 6: app_state.rs 测试
    └── Task 7: lib.rs 辅助函数测试
            │
            ▼
Phase 3: 集成验证与覆盖率
    │
    ├── Task 8: 本地手动验证
    └── Task 9: 覆盖率门禁
```

**可独立并行**：
- Task 5 与 Task 6 可并行。
- Task 1 / Task 3 / Task 4 可并行。

---

## 6. 建议迭代顺序（按可交付里程碑）

### Milestone 1：窗口行为改造（3 天）

目标：menubar 弹窗关闭即隐藏、失焦隐藏、tray 左键可呼出。
- 交付：Task 1–4
- 验收：手动操作无崩溃，关闭按钮不退出应用。

### Milestone 2：Rust 单元测试补全（2 天）

目标：核心 Rust 模块均有单元测试覆盖。
- 交付：Task 5–7
- 验收：`cargo test` 全部通过。

### Milestone 3：覆盖率门禁与收尾（2 天）

目标：覆盖率达标，CI 加入检查。
- 交付：Task 8–9
- 验收：核心模块覆盖率 ≥ 80%，CI 通过。

**总工期：约 1 周。**

---

## 7. 关键风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| `CloseRequested` 阻止关闭后未正确隐藏，用户仍看到窗口 | 中 | 同时调用 `window.hide()` 并记录 error log；手动验证 |
| Tray 图标坐标在高分屏 / 多显示器下偏移 | 中 | 统一使用 `PhysicalPosition`；手动在 Retina 屏上验证 |
| `tauri::test::mock_app()` 对窗口 show/hide 的断言能力有限 | 中 | 优先测试错误分支与辅助函数；关键行为通过手动验证补充 |
| `cat` 模拟 sidecar 测试在 Windows 不可运行 | 低 | 用 `#[cfg(unix)]` 条件编译隔离 |
| 覆盖率工具安装复杂 | 低 | 使用 `cargo llvm-cov`，提供安装命令；CI 统一环境 |

---

## 8. 验收标准

### 8.1 功能验收

- [ ] 点击输入 / 设置 / 任务窗口的关闭按钮，窗口隐藏，应用不退出。
- [ ] 点击桌面其他区域，输入 / 设置 / 任务窗口自动隐藏。
- [ ] 点击 tray icon，输入窗口出现在 tray 图标下方。
- [ ] tray 菜单「输入链接...」「最近任务」「设置...」「打开 Obsidian」「退出」均正常工作。
- [ ] 前端可通过 `invoke('hide_window', { label })` 隐藏指定窗口。
- [ ] tray 菜单「退出」后应用进程完全结束。

### 8.2 代码验收

- [ ] `cargo test` 全部通过。
- [ ] `cargo clippy` 无警告。
- [ ] `commands.rs`、`app_state.rs`、`lib.rs` 核心逻辑测试覆盖率 ≥ 80%。
- [ ] 所有测试不依赖真实 Python sidecar。
- [ ] 无硬编码路径或平台相关魔法数字。

### 8.3 性能验收

- [ ] tray 左键点击到窗口显示延迟 < 200ms。
- [ ] 窗口隐藏 / 显示无可见卡顿。

---

## 9. 实施纪律

1. **TDD**：每个 Task 先写失败测试，再实现代码，最后重构。
2. **小步提交**：每个 Task 独立 commit，使用 conventional commits（如 `feat(tauri): hide popup on close request`）。
3. **验证闭环**：每个 Task 完成后运行 `cargo test`、`cargo clippy`、手动验证。
4. **文档同步**：若修改 `CLAUDE.md` 或 `AGENTS.md`，同步更新另一个。

---

## 10. 附录：关键代码草案

### 10.1 窗口事件处理（`src-tauri/src/lib.rs`）

```rust
.on_window_event(|window, event| {
    if let WindowEvent::CloseRequested { api, .. } = event {
        if is_popup_label(window.label()) {
            api.prevent_close();
            if let Err(e) = window.hide() {
                log::error!("failed to hide popup window: {e}");
            }
        }
    }

    if let WindowEvent::Focused(false) = event {
        if is_popup_label(window.label()) {
            if let Err(e) = window.hide() {
                log::error!("failed to hide popup window: {e}");
            }
        }
    }
})
```

### 10.2 hide_window 命令（`src-tauri/src/commands.rs`）

```rust
fn hide_window_by_label<R: tauri::Runtime>(
    handle: &tauri::AppHandle<R>,
    label: &str,
) -> Result<(), String> {
    let window = handle
        .get_webview_window(label)
        .ok_or_else(|| format!("window not found: {label}"))?;
    window.hide().map_err(|e| e.to_string())
}

#[tauri::command]
pub fn hide_window<R: tauri::Runtime>(
    handle: tauri::AppHandle<R>,
    label: String,
) -> Result<(), String> {
    hide_window_by_label(&handle, &label)
}
```

### 10.3 Tray 左键定位显示（`src-tauri/src/lib.rs`）

```rust
.on_tray_icon_event(|tray, event| {
    if let tauri::tray::TrayIconEvent::Click { rect, .. } = event {
        let handle = tray.app_handle();
        let width = 560.0;
        let (icon_x, icon_y) = match rect.position { ... };
        let icon_width = match rect.size { ... };
        let icon_height = match rect.size { ... };
        let x = icon_x + (icon_width / 2.0) - (width / 2.0);
        let y = icon_y + icon_height;
        let position = tauri::Position::Physical(tauri::PhysicalPosition {
            x: x as i32,
            y: y as i32,
        });
        let _ = commands::show_input_window_at(handle, position);
    }
})
```

### 10.4 测试用例示例（`src-tauri/src/commands.rs`）

```rust
#[test]
fn hide_window_command_errors_for_missing_label() {
    let app = tauri::test::mock_app();
    let handle = app.handle();
    let err = hide_window_by_label(handle, "missing").unwrap_err();
    assert!(err.contains("window not found"));
}
```

### 10.5 覆盖率检查命令

```bash
cd src-tauri
cargo test
cargo llvm-cov --workspace --lcov --output-path lcov.info
```
