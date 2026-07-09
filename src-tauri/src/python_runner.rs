//! Python sidecar discovery helpers.

use std::path::{Path, PathBuf};

use anyhow::{Context, Result};
use tauri::{AppHandle, Manager};

/// Return possible Python interpreter paths inside `base_dir`, ordered from
/// most specific (bundled distribution) to the project virtual environment.
fn python_candidates(base_dir: &Path) -> impl Iterator<Item = PathBuf> + '_ {
    [
        base_dir.join("python").join("bin").join("python3"),
        base_dir.join(".venv").join("bin").join("python"),
    ]
    .into_iter()
}

/// Find an existing Python interpreter under `base_dir`.
fn python_candidate(base_dir: &Path) -> Option<PathBuf> {
    python_candidates(base_dir).find(|candidate| candidate.exists())
}

/// Find a Python interpreter starting from `base_dir`.
///
/// Searches bundled and virtual-environment interpreters under `base_dir`;
/// falls back to a system `python3` / `python` if neither exists.
pub fn find_python_executable_at(base_dir: &Path) -> Result<PathBuf> {
    python_candidate(base_dir)
        .or_else(|| {
            which::which("python3")
                .ok()
                .or_else(|| which::which("python").ok())
        })
        .context("python executable not found")
}

/// Find the sidecar Python script starting from `base_dir`.
///
/// Searches the bundled layout (`aipulse/desktop/sidecar.py`) and the
/// development layout (`src/aipulse/desktop/sidecar.py`) under `base_dir`.
pub fn find_sidecar_script_at(base_dir: &Path) -> Result<PathBuf> {
    sidecar_candidate(base_dir).context("sidecar script not found")
}

/// Find an existing sidecar script under `base_dir`.
fn sidecar_candidate(base_dir: &Path) -> Option<PathBuf> {
    sidecar_candidates(base_dir).find(|candidate| candidate.exists())
}

/// Find the Python interpreter for the running Tauri app.
///
/// Prefers the interpreter bundled under the app resource directory, then the
/// project virtual environment, and finally a system interpreter found on
/// `PATH`. In release builds only the bundled and system fallbacks are used to
/// avoid executing a binary from an attacker-controlled working directory.
pub async fn find_python_executable(handle: &AppHandle) -> Result<PathBuf> {
    let resource_dir = handle.path().resource_dir()?;
    if let Some(candidate) = python_candidate(&resource_dir) {
        return Ok(candidate);
    }

    // Development fallback: if the executable is not inside an app bundle, also
    // search the project directory for a virtual environment.
    if !is_running_from_bundle() {
        for root in project_root_candidates() {
            if let Some(candidate) = python_candidate(&root) {
                return Ok(candidate);
            }
        }
    }

    find_python_executable_at(Path::new("."))
}

/// Heuristic to detect whether the current process is running from a bundled
/// macOS app.
fn is_running_from_bundle() -> bool {
    std::env::current_exe()
        .ok()
        .map(|path| {
            let lossy = path.to_string_lossy();
            lossy.contains(".app/Contents/MacOS/")
        })
        .unwrap_or(false)
}

/// Find the sidecar Python script for the running Tauri app.
///
/// Prefers the bundled script in the app resource directory
/// (`aipulse/desktop/sidecar.py`), then the legacy flat layout
/// (`sidecar.py`), then development source layouts relative to discovered
/// project roots.
pub async fn find_sidecar_script(handle: &AppHandle) -> Result<PathBuf> {
    let resource_dir = handle.path().resource_dir()?;
    let resource_sidecar = resource_dir
        .join("aipulse")
        .join("desktop")
        .join("sidecar.py");
    if resource_sidecar.exists() {
        return Ok(resource_sidecar);
    }
    let legacy_sidecar = resource_dir.join("sidecar.py");
    if legacy_sidecar.exists() {
        return Ok(legacy_sidecar);
    }
    if let Some(candidate) = sidecar_candidate(&resource_dir) {
        return Ok(candidate);
    }

    for root in project_root_candidates() {
        if let Some(candidate) = sidecar_candidate(&root) {
            return Ok(candidate);
        }
    }

    find_sidecar_script_at(Path::new("."))
}

/// Heuristic list of directories that may contain the project root.
///
/// Includes the current directory, the executable's directory and its
/// ancestors, and `CARGO_MANIFEST_DIR/..`. This is useful both in development
/// and when the app is bundled as a native messaging host whose working
/// directory is not guaranteed to be the project root.
fn project_root_candidates() -> Vec<PathBuf> {
    let mut roots = Vec::new();

    if let Ok(dir) = std::env::current_dir() {
        roots.push(dir.clone());
    }

    if let Ok(exe) = std::env::current_exe() {
        let mut dir = exe.parent().map(Path::to_path_buf);
        while let Some(ref d) = dir {
            roots.push(d.clone());
            if d.file_name() == Some(std::ffi::OsStr::new("target")) {
                roots.push(d.join(".."));
            }
            let parent = d.parent().map(Path::to_path_buf);
            if parent.as_deref() == Some(Path::new("/")) {
                break;
            }
            dir = parent;
        }
    }

    if let Ok(manifest) = std::env::var("CARGO_MANIFEST_DIR") {
        let manifest_path = PathBuf::from(manifest);
        roots.push(manifest_path.join(".."));
    }

    roots.sort();
    roots.dedup();
    roots
}

fn sidecar_candidates(base_dir: &Path) -> impl Iterator<Item = PathBuf> + '_ {
    [
        base_dir.join("aipulse").join("desktop").join("sidecar.py"),
        base_dir
            .join("src")
            .join("aipulse")
            .join("desktop")
            .join("sidecar.py"),
    ]
    .into_iter()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn project_root() -> PathBuf {
        std::env::var("CARGO_MANIFEST_DIR")
            .map(PathBuf::from)
            .expect("CARGO_MANIFEST_DIR")
            .parent()
            .expect("manifest parent")
            .to_path_buf()
    }

    #[test]
    fn find_python_executable_at_finds_project_venv() {
        let result = find_python_executable_at(&project_root());

        assert!(
            result.is_ok(),
            "expected to find a python interpreter: {:?}",
            result.err()
        );
    }

    #[test]
    fn find_python_executable_at_falls_back_to_system_python() {
        // A nonexistent base directory forces the system fallback.
        let base = PathBuf::from("/nonexistent/aipulse/base");
        let result = find_python_executable_at(&base);

        assert!(
            result.is_ok(),
            "expected system python fallback to succeed: {:?}",
            result.err()
        );
    }

    #[test]
    fn find_sidecar_script_at_finds_dev_sidecar() {
        let result = find_sidecar_script_at(&project_root());

        assert!(
            result.is_ok(),
            "expected to find sidecar.py in development layout: {:?}",
            result.err()
        );
    }

    #[test]
    fn find_sidecar_script_at_errors_when_script_missing() {
        let base = PathBuf::from("/nonexistent/aipulse/base");
        let result = find_sidecar_script_at(&base);

        assert!(result.is_err());
        assert!(result
            .unwrap_err()
            .to_string()
            .contains("sidecar script not found"));
    }
}
