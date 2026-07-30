#!/bin/bash
# Dev native messaging host wrapper for AIPulse browser E2E testing.
#
# Chrome launches the native host with the extension origin as argv[1], but the
# Tauri binary only enters native-messaging mode when argv[1] is exactly
# "--native-messaging" (see src-tauri/src/main.rs). This wrapper bridges the two.
#
# It also pins the environment so the spawned Python sidecar uses the project
# virtualenv and the project data/ directory (Obsidian vault path, .env keys):
#   - PATH: native_messaging.rs resolves python via `which python3`
#   - CWD:  sidecar AppSettings reads env_file=".env" and data_dir="./data"
set -e

echo "$(date '+%H:%M:%S') invoked args=[$*] cwd=$(pwd)" >> /tmp/aipulse-native-host.log

# wrapper 位于 scripts/，向上推一级即项目根。不依赖 chrome 启动 wrapper 时给的 cwd。
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$PROJECT_ROOT/.venv/bin:$PATH"
# Douyin/yt-dlp break when a stale shell proxy leaks into the host environment
# (the E2E fleet clears these too — tests/e2e/helpers/real-backend.ts).
unset http_proxy https_proxy all_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY || true
cd "$PROJECT_ROOT"
exec "$PROJECT_ROOT/src-tauri/target/release/aipulse-tauri" --native-messaging "$@"
