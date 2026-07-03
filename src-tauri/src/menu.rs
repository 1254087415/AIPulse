//! Menu bar tray and window helpers.

use tauri::{AppHandle, Manager};

pub const TRAY_INPUT_ID: &str = "input";
pub const TRAY_TASKS_ID: &str = "tasks";
pub const TRAY_SETTINGS_ID: &str = "settings";
pub const TRAY_OBSIDIAN_ID: &str = "obsidian";
pub const TRAY_QUIT_ID: &str = "quit";

pub fn center_window_at_tray(handle: &AppHandle, label: &str) {
    if let Some(window) = handle.get_webview_window(label) {
        let _ = window.center();
    }
}
