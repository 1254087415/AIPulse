#!/bin/bash
# Sync the Python aipulse package into src-tauri/resources so Tauri bundles it.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC_DIR="$PROJECT_ROOT/src/aipulse"
RESOURCES_DIR="$PROJECT_ROOT/src-tauri/resources/aipulse"

mkdir -p "$RESOURCES_DIR"
rm -rf "$RESOURCES_DIR"
cp -R "$SRC_DIR" "$RESOURCES_DIR"

echo "Synced aipulse package to $RESOURCES_DIR"
