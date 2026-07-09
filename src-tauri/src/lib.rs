use std::process::Stdio;

use anyhow::{Context, Result};
use tauri::menu::{Menu, MenuItem, PredefinedMenuItem};
use tauri::tray::TrayIconBuilder;
use tauri::{AppHandle, Emitter, Manager, WindowEvent};
use tauri_plugin_notification::NotificationExt;
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::Command;

pub mod app_state;
pub mod commands;
pub mod menu;
pub mod native_messaging;
pub mod python_runner;

pub use app_state::{AppState, SidecarResponse};
pub use commands::*;
pub use python_runner::*;

const INPUT_WINDOW_LABEL: &str = "input";
const SETTINGS_WINDOW_LABEL: &str = "settings";
const TASKS_WINDOW_LABEL: &str = "tasks";

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_log::Builder::default().build())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            #[cfg(target_os = "macos")]
            app.set_activation_policy(tauri::ActivationPolicy::Accessory);

            let handle = app.handle().clone();

            tauri::async_runtime::block_on(async {
                if let Err(e) = setup_sidecar(&handle).await {
                    log::error!("failed to start sidecar: {e}");
                }
            });

            setup_tray(&handle)?;

            Ok(())
        })
        .manage(AppState::default())
        .invoke_handler(tauri::generate_handler![
            submit_url,
            get_task_status,
            list_tasks,
            retry_task,
            get_settings,
            update_settings,
            open_obsidian,
            open_settings_window,
            open_tasks_window,
            show_input_window,
            hide_window,
        ])
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
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

fn is_popup_label(label: &str) -> bool {
    matches!(
        label,
        INPUT_WINDOW_LABEL | SETTINGS_WINDOW_LABEL | TASKS_WINDOW_LABEL
    )
}

async fn setup_sidecar(handle: &AppHandle) -> Result<()> {
    let python_path = python_runner::find_python_executable(handle).await?;
    let sidecar_script = python_runner::find_sidecar_script(handle).await?;

    let app_data_dir = handle
        .path()
        .app_data_dir()
        .context("failed to resolve app data dir")?;
    let data_dir = app_data_dir.join("data");
    let downloads_dir = data_dir.join("downloads");
    tokio::fs::create_dir_all(&data_dir)
        .await
        .context("failed to create data dir")?;
    tokio::fs::create_dir_all(&downloads_dir)
        .await
        .context("failed to create downloads dir")?;
    let database_url = format!(
        "sqlite+aiosqlite:///{}/aipulse.db",
        data_dir.to_string_lossy()
    );

    let mut child = Command::new(&python_path)
        .arg(&sidecar_script)
        .env("DATA_DIR", &data_dir)
        .env("DOWNLOAD_DIR", &downloads_dir)
        .env("DATABASE_URL", &database_url)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .context("failed to spawn python sidecar")?;

    let stderr = child.stderr.take().context("no stderr")?;
    tauri::async_runtime::spawn(async move {
        let reader = BufReader::new(stderr);
        let mut lines = reader.lines();
        while let Ok(Some(line)) = lines.next_line().await {
            log::error!("[sidecar stderr] {line}");
        }
    });

    let state = handle.state::<AppState>();
    state.set_sidecar(child).await?;

    let handle_clone = handle.clone();
    tauri::async_runtime::spawn(async move {
        read_sidecar_stdout(handle_clone).await;
    });

    Ok(())
}

async fn read_sidecar_stdout(handle: AppHandle) {
    loop {
        let line = {
            let state = handle.state::<AppState>();
            state.read_sidecar_line().await
        };

        match line {
            Ok(Some(json_line)) => {
                if let Err(e) = handle_sidecar_message(&handle, &json_line).await {
                    log::error!("failed to handle sidecar message: {e}");
                }
            }
            Ok(None) => {
                log::warn!("sidecar stdout closed");
                let state = handle.state::<AppState>();
                state.clear_sidecar().await;
                break;
            }
            Err(e) => {
                log::error!("failed to read sidecar stdout: {e}");
                let state = handle.state::<AppState>();
                state.clear_sidecar().await;
                break;
            }
        }
    }
}

async fn handle_sidecar_message(handle: &AppHandle, line: &str) -> Result<()> {
    let msg: serde_json::Value = serde_json::from_str(line).context("invalid json from sidecar")?;

    if let Some(id) = msg.get("id").and_then(|v| v.as_u64()) {
        let state = handle.state::<AppState>();
        let response: SidecarResponse =
            serde_json::from_value(msg).context("invalid json-rpc response from sidecar")?;
        state.complete_request(id, response).await;
        return Ok(());
    }

    if let Some(method) = msg.get("method").and_then(|m| m.as_str()) {
        let params = msg
            .get("params")
            .cloned()
            .unwrap_or(serde_json::Value::Null);
        match method {
            "task_progress" => {
                handle.emit("task_progress", params.clone())?;
            }
            "task_complete" => {
                handle.emit("task_complete", params.clone())?;
                notify_task_complete(handle, &params).await?;
            }
            "notification" => {
                handle.emit("notification", params.clone())?;
            }
            _ => {
                log::debug!("unknown sidecar notification: {method}");
            }
        }
    }

    Ok(())
}

async fn notify_task_complete(handle: &AppHandle, params: &serde_json::Value) -> Result<()> {
    let title = params
        .get("result")
        .and_then(|r| r.get("title"))
        .and_then(|t| t.as_str())
        .or_else(|| params.get("title").and_then(|t| t.as_str()))
        .unwrap_or("AIPulse");
    let status = params
        .get("status")
        .and_then(|s| s.as_str())
        .unwrap_or("done");

    let body = if status == "failed" {
        "处理失败，请查看任务列表重试"
    } else {
        "处理完成，已归档到 Obsidian"
    };

    handle
        .notification()
        .builder()
        .title(title)
        .body(body)
        .show()
        .context("failed to show notification")?;

    Ok(())
}

fn setup_tray(handle: &AppHandle) -> Result<()> {
    let input_i = MenuItem::with_id(handle, "input", "输入链接...", true, None::<&str>)?;
    let tasks_i = MenuItem::with_id(handle, "tasks", "最近任务", true, None::<&str>)?;
    let settings_i = MenuItem::with_id(handle, "settings", "设置...", true, None::<&str>)?;
    let obsidian_i = MenuItem::with_id(handle, "obsidian", "打开 Obsidian", true, None::<&str>)?;
    let separator = PredefinedMenuItem::separator(handle)?;
    let quit_i = MenuItem::with_id(handle, "quit", "退出", true, None::<&str>)?;

    let menu = Menu::with_items(
        handle,
        &[
            &input_i,
            &tasks_i,
            &settings_i,
            &obsidian_i,
            &separator,
            &quit_i,
        ],
    )?;

    let tray = TrayIconBuilder::new()
        .icon(
            handle
                .default_window_icon()
                .cloned()
                .unwrap_or_else(|| tauri::image::Image::new_owned(vec![0, 0, 0, 0], 1, 1)),
        )
        .menu(&menu)
        .show_menu_on_left_click(false)
        .on_tray_icon_event(|tray, event| {
            if let tauri::tray::TrayIconEvent::Click { rect, .. } = event {
                let handle = tray.app_handle();
                let width = 560.0;
                let _height = 640.0;
                let (icon_x, icon_y) = match rect.position {
                    tauri::Position::Physical(pos) => (pos.x as f64, pos.y as f64),
                    tauri::Position::Logical(pos) => (pos.x, pos.y),
                };
                let icon_width = match rect.size {
                    tauri::Size::Physical(size) => size.width as f64,
                    tauri::Size::Logical(size) => size.width,
                };
                let icon_height = match rect.size {
                    tauri::Size::Physical(size) => size.height as f64,
                    tauri::Size::Logical(size) => size.height,
                };
                let x = icon_x + (icon_width / 2.0) - (width / 2.0);
                let y = icon_y + icon_height;
                let position = tauri::Position::Physical(tauri::PhysicalPosition {
                    x: x as i32,
                    y: y as i32,
                });
                let _ = commands::show_input_window_at(handle, position);
            }
        })
        .on_menu_event(|handle, event| match event.id().as_ref() {
            "input" => {
                let _ = show_input_window(handle.clone());
            }
            "tasks" => {
                let _ = open_tasks_window(handle.clone());
            }
            "settings" => {
                let _ = open_settings_window(handle.clone());
            }
            "obsidian" => {
                let handle = handle.clone();
                tauri::async_runtime::spawn(async move {
                    let _ = open_obsidian(handle).await;
                });
            }
            "quit" => {
                handle.exit(0);
            }
            _ => {}
        })
        .build(handle)?;

    tray.set_tooltip(Some("AIPulse"))?;
    Ok(())
}
