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
pub async fn open_obsidian(handle: AppHandle, _: ()) -> Result<(), String> {
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

#[tauri::command]
pub fn show_input_window(handle: AppHandle, _: ()) -> Result<(), String> {
    show_or_create_window(
        &handle,
        "input",
        WebviewUrl::App("/input".into()),
        420.0,
        180.0,
    )
}

#[tauri::command]
pub fn open_settings_window(handle: AppHandle, _: ()) -> Result<(), String> {
    show_or_create_window(
        &handle,
        "settings",
        WebviewUrl::App("/settings".into()),
        640.0,
        480.0,
    )
}

#[tauri::command]
pub fn open_tasks_window(handle: AppHandle, _: ()) -> Result<(), String> {
    show_or_create_window(
        &handle,
        "tasks",
        WebviewUrl::App("/tasks".into()),
        720.0,
        480.0,
    )
}

fn show_or_create_window(
    handle: &AppHandle,
    label: &str,
    url: WebviewUrl,
    width: f64,
    height: f64,
) -> Result<(), String> {
    if let Some(window) = handle.get_webview_window(label) {
        window.show().map_err(|e| e.to_string())?;
        window.set_focus().map_err(|e| e.to_string())?;
        return Ok(());
    }

    WebviewWindow::builder(handle, label, url)
        .title(label)
        .inner_size(width, height)
        .resizable(false)
        .maximizable(false)
        .minimizable(false)
        .always_on_top(true)
        .center()
        .build()
        .map_err(|e| e.to_string())?;

    Ok(())
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
}
