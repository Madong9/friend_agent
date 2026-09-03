#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_PATH="${MINIPROGRAM_PACKAGE_PATH:-$PROJECT_ROOT/deployment/campus-social-miniprogram.zip}"
PACKAGE_TMP_DIR="$(mktemp -d /tmp/campus-social-miniprogram-XXXXXX)"
PACKAGE_TMP="$PACKAGE_TMP_DIR/campus-social-miniprogram.zip"

cleanup_package() {
  if [[ -d "$PACKAGE_TMP_DIR" ]]; then
    gio trash "$PACKAGE_TMP_DIR" >/dev/null 2>&1 || true
  fi
}
trap cleanup_package EXIT

mkdir -p "$(dirname "$OUTPUT_PATH")"
cd "$PROJECT_ROOT"
zip -q -r "$PACKAGE_TMP" project.config.json miniprogram \
  -x '*/project.private.config.json' '*/config.js.save' '*.save' \
     '*/node_modules/*' '*/__pycache__/*' '*.pyc'
mv -f "$PACKAGE_TMP" "$OUTPUT_PATH"

printf 'Mini Program source package created: %s\n' "$OUTPUT_PATH"
printf 'Included: project.config.json and miniprogram source\n'
printf 'Excluded: node_modules, private configs, backup files, .env, backend and local data\n'
