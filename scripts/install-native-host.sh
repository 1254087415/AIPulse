#!/bin/bash
set -e

EXT_ID="${1:-AIPULSE_EXTENSION_ID}"
TAURI_BIN="${2:-/Applications/AIPulse.app/Contents/MacOS/AIPulse}"
MANIFEST_DIR="$HOME/Library/Application Support/Google/Chrome/NativeMessagingHosts"
MANIFEST_FILE="$MANIFEST_DIR/com.aipulse.native_host.json"

mkdir -p "$MANIFEST_DIR"
sed \
  -e "s|AIPULSE_TAURI_BINARY_PATH|$TAURI_BIN|g" \
  -e "s|AIPULSE_EXTENSION_ID|$EXT_ID|g" \
  scripts/com.aipulse.native_host.json > "$MANIFEST_FILE"

echo "Installed native host manifest to $MANIFEST_FILE"
