use std::collections::HashMap;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::process::{Child, ChildStdin, ChildStdout};
use tokio::sync::oneshot;
use tokio::sync::Mutex;
use tokio::time::{timeout, Duration};

#[derive(Default)]
pub struct AppState {
    sidecar: Mutex<Option<SidecarHandle>>,
    pending: Arc<Mutex<HashMap<u64, oneshot::Sender<SidecarResponse>>>>,
    next_id: AtomicU64,
}

pub struct SidecarHandle {
    #[allow(dead_code)]
    child: Child,
    stdin: Arc<Mutex<ChildStdin>>,
    stdout_reader: Arc<Mutex<BufReader<ChildStdout>>>,
}

impl AppState {
    pub async fn set_sidecar(&self, mut child: Child) -> Result<()> {
        let stdin = child.stdin.take().context("no stdin")?;
        let stdout = child.stdout.take().context("no stdout")?;
        let reader = BufReader::new(stdout);

        let mut guard = self.sidecar.lock().await;
        *guard = Some(SidecarHandle {
            child,
            stdin: Arc::new(Mutex::new(stdin)),
            stdout_reader: Arc::new(Mutex::new(reader)),
        });
        Ok(())
    }

    pub async fn read_sidecar_line(&self) -> Result<Option<String>> {
        let guard = self.sidecar.lock().await;
        let reader = guard
            .as_ref()
            .context("sidecar not running")?
            .stdout_reader
            .clone();
        drop(guard);

        let mut reader = reader.lock().await;
        let mut line = String::new();
        match reader.read_line(&mut line).await {
            Ok(0) => Ok(None),
            Ok(_) => Ok(Some(line.trim().to_string())),
            Err(e) => Err(e.into()),
        }
    }

    pub async fn write_sidecar(&self, json: &str) -> Result<()> {
        let guard = self.sidecar.lock().await;
        let stdin = guard.as_ref().context("sidecar not running")?.stdin.clone();
        drop(guard);

        let mut stdin = stdin.lock().await;
        stdin.write_all(json.as_bytes()).await?;
        stdin.write_all(b"\n").await?;
        stdin.flush().await?;
        Ok(())
    }

    pub async fn complete_request(&self, id: u64, response: SidecarResponse) {
        let mut pending = self.pending.lock().await;
        if let Some(sender) = pending.remove(&id) {
            if sender.send(response).is_err() {
                log::error!("failed to complete sidecar request: receiver dropped");
            }
        }
    }

    pub async fn clear_sidecar(&self) {
        let mut guard = self.sidecar.lock().await;
        *guard = None;
    }

    pub async fn send_request(
        &self,
        method: impl Into<String>,
        params: serde_json::Value,
    ) -> Result<SidecarResponse> {
        let id = self.next_id.fetch_add(1, Ordering::SeqCst);
        let req = SidecarRequest::new(id, method, params);
        let json = serde_json::to_string(&req).context("failed to serialize request")?;

        let (tx, rx) = oneshot::channel();
        {
            let mut pending = self.pending.lock().await;
            pending.insert(id, tx);
        }

        let result: Result<SidecarResponse> = async {
            self.write_sidecar(&json).await?;
            let response = timeout(Duration::from_secs(10), rx)
                .await
                .context("sidecar request timed out")?;
            response.context("sidecar response channel closed")
        }
        .await;

        {
            let mut pending = self.pending.lock().await;
            pending.remove(&id);
        }

        result
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SidecarRequest {
    pub jsonrpc: String,
    pub id: Option<u64>,
    pub method: String,
    pub params: serde_json::Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SidecarResponse {
    pub jsonrpc: String,
    pub id: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub result: Option<serde_json::Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<SidecarError>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SidecarError {
    pub code: i32,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub data: Option<serde_json::Value>,
}

impl SidecarRequest {
    pub fn new(id: u64, method: impl Into<String>, params: serde_json::Value) -> Self {
        Self {
            jsonrpc: "2.0".to_string(),
            id: Some(id),
            method: method.into(),
            params,
        }
    }
}

#[cfg(test)]
mod tests {
    use std::process::Stdio;
    use std::sync::Arc;

    use super::*;

    #[tokio::test]
    async fn complete_request_routes_response_to_pending_sender() {
        let state = AppState::default();
        let (tx, rx) = oneshot::channel();
        {
            let mut pending = state.pending.lock().await;
            pending.insert(42, tx);
        }

        let response = SidecarResponse {
            jsonrpc: "2.0".to_string(),
            id: Some(42),
            result: Some(serde_json::json!({"status": "ok"})),
            error: None,
        };
        state.complete_request(42, response.clone()).await;

        let received = rx.await.expect("response channel should receive");
        assert_eq!(received.id, response.id);
        assert_eq!(received.result, response.result);
    }

    #[tokio::test]
    #[cfg(unix)]
    async fn send_request_writes_expected_json_and_receives_response() {
        let state = Arc::new(AppState::default());
        let child = tokio::process::Command::new("cat")
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .spawn()
            .expect("cat is available on unix");
        state.set_sidecar(child).await.expect("set sidecar");

        let state_for_task = Arc::clone(&state);
        let helper = tokio::spawn(async move {
            let line = state_for_task
                .read_sidecar_line()
                .await
                .expect("read sidecar line")
                .expect("sidecar line is not empty");
            let req: serde_json::Value = serde_json::from_str(&line).unwrap();
            assert_eq!(req["jsonrpc"], "2.0");
            assert_eq!(req["method"], "test_method");
            assert_eq!(req["params"], serde_json::json!({"key": "value"}));

            let id = req["id"].as_u64().expect("id is u64");
            state_for_task
                .complete_request(
                    id,
                    SidecarResponse {
                        jsonrpc: "2.0".to_string(),
                        id: Some(id),
                        result: Some(serde_json::json!({"task_id": "abc"})),
                        error: None,
                    },
                )
                .await;
        });

        let response = state
            .send_request("test_method", serde_json::json!({"key": "value"}))
            .await
            .expect("send_request succeeds");

        helper.await.expect("helper task completes");

        assert_eq!(response.result, Some(serde_json::json!({"task_id": "abc"})));
        assert!(response.error.is_none());
    }

    #[tokio::test]
    async fn write_sidecar_errors_when_sidecar_missing() {
        let state = AppState::default();
        let err = state.write_sidecar("{}").await.unwrap_err();
        assert!(err.to_string().contains("sidecar not running"));
    }

    #[tokio::test]
    #[cfg(unix)]
    async fn clear_sidecar_removes_handle() {
        let state = AppState::default();
        let child = tokio::process::Command::new("cat")
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .spawn()
            .expect("cat is available on unix");
        state.set_sidecar(child).await.expect("set sidecar");

        state.clear_sidecar().await;

        let err = state.read_sidecar_line().await.unwrap_err();
        assert!(err.to_string().contains("sidecar not running"));
    }
}
