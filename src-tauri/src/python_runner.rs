//! Python sidecar discovery helpers.

use std::path::PathBuf;

use anyhow::{Context, Result};
use tauri::{AppHandle, Manager};

pub async fn find_python_executable(handle: &AppHandle) -> Result<PathBuf> {
    let resource_dir = handle.path().resource_dir()?;
    let bundled = resource_dir.join("python").join("bin").join("python3");
    if bundled.exists() {
        return Ok(bundled);
    }

    let project_python = PathBuf::from(".venv/bin/python");
    if project_python.exists() {
        return Ok(std::env::current_dir()?.join(project_python));
    }

    which::which("python3")
        .or_else(|_| which::which("python"))
        .context("python executable not found")
}

pub async fn find_sidecar_script(handle: &AppHandle) -> Result<PathBuf> {
    let resource_dir = handle.path().resource_dir()?;
    let bundled = resource_dir
        .join("aipulse")
        .join("desktop")
        .join("sidecar.py");
    if bundled.exists() {
        return Ok(bundled);
    }

    let dev_script = std::env::current_dir()?.join("src/aipulse/desktop/sidecar.py");
    if dev_script.exists() {
        return Ok(dev_script);
    }

    anyhow::bail!("sidecar script not found")
}
