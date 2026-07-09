use tauri::{AppHandle, Manager, State, WebviewUrl, WebviewWindow};
use tauri_plugin_shell::ShellExt;

use crate::app_state::{AppState, SidecarResponse};

fn unwrap_response(response: SidecarResponse) -> Result<serde_json::Value, String> {
    match (response.error, response.result) {
        (Some(err), _) => Err(err.message),
        (None, Some(result)) => Ok(result),
        (None, None) => Err("invalid sidecar response: missing result and error".to_string()),
    }
}

#[tauri::command]
pub async fn submit_url(
    state: State<'_, AppState>,
    url: String,
    source: String,
) -> Result<String, String> {
    let params = serde_json::json!({"url": url, "source": source});
    let response = state
        .send_request("submit_url", params)
        .await
        .map_err(|e| e.to_string())?;
    let result = unwrap_response(response)?;
    let task_id = result
        .get("task_id")
        .and_then(|v| v.as_str())
        .ok_or_else(|| "missing task_id in sidecar response".to_string())?;
    Ok(task_id.to_string())
}

#[tauri::command]
pub async fn get_task_status(
    state: State<'_, AppState>,
    task_id: String,
) -> Result<serde_json::Value, String> {
    let params = serde_json::json!({"task_id": task_id});
    let response = state
        .send_request("get_task_status", params)
        .await
        .map_err(|e| e.to_string())?;
    unwrap_response(response)
}

#[tauri::command]
pub async fn list_tasks(
    state: State<'_, AppState>,
    limit: Option<u32>,
) -> Result<serde_json::Value, String> {
    let params = serde_json::json!({"limit": limit.unwrap_or(50).min(200)});
    let response = state
        .send_request("list_tasks", params)
        .await
        .map_err(|e| e.to_string())?;
    unwrap_response(response)
}

#[tauri::command]
pub async fn retry_task(state: State<'_, AppState>, task_id: String) -> Result<(), String> {
    let params = serde_json::json!({"task_id": task_id});
    let response = state
        .send_request("retry_task", params)
        .await
        .map_err(|e| e.to_string())?;
    unwrap_response(response)?;
    Ok(())
}

#[tauri::command]
pub async fn get_settings(state: State<'_, AppState>) -> Result<serde_json::Value, String> {
    let response = state
        .send_request("get_settings", serde_json::json!({}))
        .await
        .map_err(|e| e.to_string())?;
    unwrap_response(response)
}

#[tauri::command]
pub async fn update_settings(
    state: State<'_, AppState>,
    settings: serde_json::Value,
) -> Result<serde_json::Value, String> {
    let response = state
        .send_request("update_settings", settings)
        .await
        .map_err(|e| e.to_string())?;
    unwrap_response(response)
}

#[tauri::command]
#[allow(deprecated)]
pub async fn open_obsidian(handle: AppHandle) -> Result<(), String> {
    let state = handle.state::<AppState>();
    let settings = state
        .send_request("get_settings", serde_json::json!({}))
        .await
        .map_err(|e| e.to_string())?;
    let result = unwrap_response(settings)?;
    let vault_path = result
        .get("obsidian_vault_path")
        .and_then(|v| v.as_str())
        .map(|s| s.to_string())
        .or_else(|| std::env::var("OBSIDIAN_VAULT_PATH").ok())
        .or_else(|| {
            std::env::var("HOME")
                .ok()
                .map(|home| format!("{home}/Documents/Obsidian Vault"))
        })
        .ok_or_else(|| "无法确定 Obsidian vault 路径".to_string())?;
    let url = format!("obsidian://open?vault={}", urlencoding::encode(&vault_path));
    handle.shell().open(url, None).map_err(|e| e.to_string())?;
    Ok(())
}

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

#[tauri::command]
pub fn show_input_window(handle: AppHandle) -> Result<(), String> {
    center_window(
        &handle,
        "input",
        WebviewUrl::App("index.html#/input".into()),
        560.0,
        640.0,
    )
}

#[tauri::command]
pub fn open_settings_window(handle: AppHandle) -> Result<(), String> {
    center_window(
        &handle,
        "settings",
        WebviewUrl::App("index.html#/settings".into()),
        560.0,
        640.0,
    )
}

#[tauri::command]
pub fn open_tasks_window(handle: AppHandle) -> Result<(), String> {
    center_window(
        &handle,
        "tasks",
        WebviewUrl::App("index.html#/tasks".into()),
        560.0,
        640.0,
    )
}

fn show_or_create_window<R: tauri::Runtime>(
    handle: &tauri::AppHandle<R>,
    label: &str,
    url: WebviewUrl,
    width: f64,
    height: f64,
    position: Option<tauri::Position>,
) -> Result<(), String> {
    if let Some(window) = handle.get_webview_window(label) {
        if let Some(pos) = position {
            window.set_position(pos).map_err(|e| e.to_string())?;
        }
        window.show().map_err(|e| e.to_string())?;
        window.set_focus().map_err(|e| e.to_string())?;
        return Ok(());
    }

    let mut builder = WebviewWindow::builder(handle, label, url)
        .title(label)
        .inner_size(width, height)
        .resizable(false)
        .maximizable(false)
        .minimizable(false)
        .decorations(false)
        .always_on_top(true)
        .skip_taskbar(true)
        .accept_first_mouse(true)
        .focused(true)
        .visible(true)
        .shadow(true);

    if let Some(pos) = position {
        let (x, y) = match pos {
            tauri::Position::Physical(p) => (p.x as f64, p.y as f64),
            tauri::Position::Logical(p) => (p.x, p.y),
        };
        builder = builder.position(x, y);
    } else {
        builder = builder.center();
    }

    let window = builder.build().map_err(|e| e.to_string())?;

    window.show().map_err(|e| e.to_string())?;
    window.set_focus().map_err(|e| e.to_string())?;

    Ok(())
}

pub fn show_input_window_at<R: tauri::Runtime>(
    handle: &tauri::AppHandle<R>,
    position: tauri::Position,
) -> Result<(), String> {
    show_or_create_window(
        handle,
        "input",
        WebviewUrl::App("index.html#/input".into()),
        560.0,
        640.0,
        Some(position),
    )
}

pub fn center_window<R: tauri::Runtime>(
    handle: &tauri::AppHandle<R>,
    label: &str,
    url: WebviewUrl,
    width: f64,
    height: f64,
) -> Result<(), String> {
    show_or_create_window(handle, label, url, width, height, None)
}

#[cfg(test)]
mod tests {
    use crate::app_state::SidecarError;

    use super::*;

    #[test]
    fn unwrap_response_returns_ok_when_no_error() {
        let response = SidecarResponse {
            jsonrpc: "2.0".to_string(),
            id: Some(1),
            result: Some(serde_json::json!({"task_id": "abc"})),
            error: None,
        };
        assert_eq!(
            unwrap_response(response).unwrap(),
            serde_json::json!({"task_id": "abc"})
        );
    }

    #[test]
    fn unwrap_response_returns_err_when_error_present() {
        let response = SidecarResponse {
            jsonrpc: "2.0".to_string(),
            id: Some(1),
            result: None,
            error: Some(SidecarError {
                code: -1,
                message: "something went wrong".to_string(),
                data: None,
            }),
        };
        assert_eq!(
            unwrap_response(response).unwrap_err(),
            "something went wrong"
        );
    }

    #[test]
    fn unwrap_response_returns_err_when_both_result_and_error_present() {
        let response = SidecarResponse {
            jsonrpc: "2.0".to_string(),
            id: Some(1),
            result: Some(serde_json::json!({"task_id": "abc"})),
            error: Some(SidecarError {
                code: -1,
                message: "something went wrong".to_string(),
                data: None,
            }),
        };
        assert_eq!(
            unwrap_response(response).unwrap_err(),
            "something went wrong"
        );
    }

    #[test]
    fn unwrap_response_returns_err_when_both_missing() {
        let response = SidecarResponse {
            jsonrpc: "2.0".to_string(),
            id: Some(1),
            result: None,
            error: None,
        };
        let err = unwrap_response(response).unwrap_err();
        assert!(err.contains("missing result and error"));
    }

    #[test]
    fn hide_window_command_errors_for_missing_label() {
        let app = tauri::test::mock_app();
        let handle = app.handle();
        let err = hide_window_by_label(handle, "missing").unwrap_err();
        assert!(err.contains("window not found"));
    }

    #[test]
    fn show_or_create_window_finds_existing_window() {
        let app = tauri::test::mock_app();
        let handle = app.handle();

        let _window = tauri::WebviewWindowBuilder::new(
            handle,
            "existing",
            WebviewUrl::App("/existing".into()),
        )
        .build()
        .expect("mock window can be created");

        let result = show_or_create_window(
            handle,
            "existing",
            WebviewUrl::App("/existing".into()),
            100.0,
            100.0,
            None,
        );
        assert!(result.is_ok());
    }
}
