#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_PATH="${CLOUDBASE_PACKAGE_PATH:-$PROJECT_ROOT/deployment/cloudbase-campus-social-agent.zip}"
PACKAGE_TMP_DIR="$(mktemp -d /tmp/campus-social-cloudbase-XXXXXX)"
PACKAGE_TMP="$PACKAGE_TMP_DIR/cloudbase-campus-social-agent.zip"

cleanup_package() {
  if [[ -d "$PACKAGE_TMP_DIR" ]]; then
    gio trash "$PACKAGE_TMP_DIR" >/dev/null 2>&1 || true
  fi
}
trap cleanup_package EXIT

mkdir -p "$(dirname "$OUTPUT_PATH")"

cd "$PROJECT_ROOT"
zip -q -r "$PACKAGE_TMP" \
  Dockerfile \
  requirements.txt \
  alembic.ini \
  backend \
  migrations \
  scripts \
  deployment/cloudbase_schema.sql \
  -x '*/__pycache__/*' '*.pyc' '*.pyo' '*.db' '*.sqlite' '*.sqlite3'

mv -f "$PACKAGE_TMP" "$OUTPUT_PATH"
printf 'CloudBase deployment package created: %s\n' "$OUTPUT_PATH"
printf 'Included: Dockerfile, requirements, backend, migrations, scripts, CloudBase schema SQL\n'
printf 'Excluded by construction: .env, Mini Program, Web frontend, tests, local databases\n'
