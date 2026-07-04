//! Native Messaging host that forwards Chrome extension messages to the Python sidecar.

use std::process::Stdio;

use anyhow::{Context, Result};
use tokio::io::{AsyncBufReadExt, AsyncReadExt, AsyncWriteExt, BufReader};
use tokio::process::{ChildStderr, ChildStdin, ChildStdout, Command};

use std::path::PathBuf;

use crate::python_runner::{find_python_executable_at, find_sidecar_script_at};

/// Maximum allowed Native Messaging frame payload.
///
/// Chrome permits up to 1 GB per message, but we limit the host to 16 MB to
/// avoid accidental DoS from malformed or malicious extension payloads.
const MAX_MESSAGE_SIZE: usize = 16 * 1024 * 1024;

/// Determine the directory used to discover bundled Python and sidecar resources.
///
/// Chrome launches the native host with its CWD next to the host binary. On
/// macOS that is `AIPulse.app/Contents/MacOS`, while bundled resources live in
/// `Contents/Resources`. This helper tries the executable-derived bundle layout
/// first, then falls back to the current directory and the project root.
fn host_resource_dir() -> PathBuf {
    if let Ok(exe) = std::env::current_exe() {
        if let Some(exe_dir) = exe.parent() {
            #[cfg(target_os = "macos")]
            if exe_dir.file_name() == Some(std::ffi::OsStr::new("MacOS")) {
                if let Some(contents) = exe_dir.parent() {
                    let resources = contents.join("Resources");
                    if resources.exists() {
                        return resources;
                    }
                }
            }
            if exe_dir.exists() {
                return exe_dir.to_path_buf();
            }
        }
    }

    std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."))
}

/// Run the Native Messaging host loop.
///
/// Reads length-prefixed JSON messages from stdin, forwards them to the Python
/// sidecar as line-delimited JSON, and writes the sidecar response back to
/// stdout using Native Messaging framing.
pub async fn run_native_messaging_loop() -> Result<()> {
    let base_dir = host_resource_dir();
    let python_path = find_python_executable_at(&base_dir)?;
    let sidecar_script = find_sidecar_script_at(&base_dir)?;

    log::info!(
        "starting native messaging host; python={python_path:?}, sidecar={sidecar_script:?}"
    );

    let mut child = Command::new(&python_path)
        .arg(&sidecar_script)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .context("failed to spawn python sidecar")?;

    let stderr = child.stderr.take().context("sidecar has no stderr")?;
    tokio::spawn(drain_sidecar_stderr(stderr));

    let mut child_stdin = child.stdin.take().context("sidecar has no stdin")?;
    let mut child_stdout = BufReader::new(child.stdout.take().context("sidecar has no stdout")?);

    let mut host_stdin = tokio::io::stdin();
    let mut host_stdout = tokio::io::stdout();

    loop {
        let message = match read_native_message(&mut host_stdin).await {
            Ok(Some(message)) => message,
            Ok(None) => {
                log::info!("native messaging stdin closed");
                break;
            }
            Err(error) => {
                log::error!("failed to read native message: {error:#}");
                return Err(error);
            }
        };

        if let Err(error) = forward_to_sidecar(&mut child_stdin, &message).await {
            log::error!("failed to forward request to sidecar: {error:#}");
            return Err(error);
        }

        match read_sidecar_response(&mut child_stdout).await {
            Ok(Some(response)) => {
                if let Err(error) = write_native_message(&mut host_stdout, &response).await {
                    log::error!("failed to write native response: {error:#}");
                    return Err(error);
                }
            }
            Ok(None) => {
                log::warn!("sidecar stdout closed");
                break;
            }
            Err(error) => {
                log::error!("failed to read sidecar response: {error:#}");
                return Err(error);
            }
        }
    }

    if let Err(error) = child_stdin.shutdown().await {
        log::warn!("failed to shut down sidecar stdin: {error:#}");
    }
    Ok(())
}

/// Read a single Native Messaging frame from `reader`.
///
/// Returns `Ok(None)` when stdin has closed cleanly. Returns an error if the
/// frame length exceeds `MAX_MESSAGE_SIZE` or if the payload cannot be read.
pub async fn read_native_message<R>(reader: &mut R) -> Result<Option<Vec<u8>>>
where
    R: AsyncReadExt + Unpin,
{
    let mut length_bytes = [0u8; 4];
    match reader.read_exact(&mut length_bytes).await {
        Ok(_) => {}
        Err(error) if error.kind() == std::io::ErrorKind::UnexpectedEof => {
            return Ok(None);
        }
        Err(error) => return Err(error.into()),
    }

    let length = u32::from_le_bytes(length_bytes) as usize;
    if length > MAX_MESSAGE_SIZE {
        anyhow::bail!("native message too large: {length} bytes (max {MAX_MESSAGE_SIZE})");
    }

    let mut payload = vec![0u8; length];
    reader.read_exact(&mut payload).await?;

    Ok(Some(payload))
}

/// Write `payload` to `writer` using Native Messaging framing.
pub async fn write_native_message<W>(writer: &mut W, payload: &[u8]) -> Result<()>
where
    W: AsyncWriteExt + Unpin,
{
    let length = payload.len();
    if length > u32::MAX as usize {
        anyhow::bail!("native message payload exceeds u32::MAX");
    }

    writer.write_all(&(length as u32).to_le_bytes()).await?;
    writer.write_all(payload).await?;
    writer.flush().await?;

    Ok(())
}

async fn forward_to_sidecar(stdin: &mut ChildStdin, payload: &[u8]) -> Result<()> {
    stdin.write_all(payload).await?;
    stdin.write_all(b"\n").await?;
    stdin.flush().await?;
    Ok(())
}

async fn read_sidecar_response(reader: &mut BufReader<ChildStdout>) -> Result<Option<Vec<u8>>> {
    let mut line = String::new();

    loop {
        line.clear();
        match reader.read_line(&mut line).await {
            Ok(0) => return Ok(None),
            Ok(_) => {}
            Err(error) => return Err(error.into()),
        }

        let trimmed = line.trim_end();
        if trimmed.is_empty() {
            continue;
        }

        match serde_json::from_str::<serde_json::Value>(trimmed) {
            Ok(value) if value.get("id").is_some() => {
                return Ok(Some(trimmed.as_bytes().to_vec()));
            }
            Ok(_) => {
                log::debug!("ignoring sidecar notification: {trimmed}");
                continue;
            }
            Err(error) => {
                log::warn!("ignoring non-JSON sidecar output: {error}");
                continue;
            }
        }
    }
}

async fn drain_sidecar_stderr(stderr: ChildStderr) {
    let reader = BufReader::new(stderr);
    let mut lines = reader.lines();

    loop {
        match lines.next_line().await {
            Ok(Some(line)) => log::error!("[sidecar stderr] {line}"),
            Ok(None) => break,
            Err(error) => {
                log::error!("failed to read sidecar stderr: {error:#}");
                break;
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn native_message_framing_round_trip() {
        let payload = br#"{"jsonrpc":"2.0","id":1,"method":"submit_url"}"#;

        let mut encoded = Vec::new();
        write_native_message(&mut encoded, payload).await.unwrap();

        let mut reader = encoded.as_slice();
        let decoded = read_native_message(&mut reader)
            .await
            .unwrap()
            .expect("message should be decoded");

        assert_eq!(decoded, payload);
    }

    #[tokio::test]
    async fn read_native_message_returns_none_on_clean_eof() {
        let mut reader: &[u8] = b"";
        let result = read_native_message(&mut reader).await.unwrap();
        assert!(result.is_none());
    }

    #[tokio::test]
    async fn read_native_message_rejects_oversized_frame() {
        let length = (MAX_MESSAGE_SIZE + 1) as u32;
        let mut encoded = Vec::new();
        encoded.extend_from_slice(&length.to_le_bytes());
        encoded.resize(encoded.len() + MAX_MESSAGE_SIZE + 1, 0u8);

        let mut reader = encoded.as_slice();
        let result = read_native_message(&mut reader).await;
        assert!(result.is_err());
        assert!(result
            .unwrap_err()
            .to_string()
            .contains("native message too large"));
    }
}
