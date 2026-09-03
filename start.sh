#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

PYTHON_BIN="${PYTHON_BIN:-python}"
BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
BACKEND_RELOAD="${BACKEND_RELOAD:-true}"
API_URL="${VITE_API_BASE_URL:-http://${BACKEND_HOST}:${BACKEND_PORT}}"
BACKEND_PID=""
FRONTEND_PID=""

log() {
  printf '\n[校园搭子] %s\n' "$1"
}

cleanup() {
  trap - EXIT INT TERM
  set +e
  if [[ -n "$FRONTEND_PID" ]] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null
  fi
  if [[ -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null
  fi
  wait "$FRONTEND_PID" 2>/dev/null
  wait "$BACKEND_PID" 2>/dev/null
  log "前后端已停止。"
}

trap cleanup EXIT INT TERM

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  log "未找到 Python：$PYTHON_BIN。可通过 PYTHON_BIN=/path/to/python 指定。"
  exit 1
fi
if ! command -v npm >/dev/null 2>&1; then
  log "未找到 npm，请先安装 Node.js 18+。"
  exit 1
fi

if [[ ! -f .env ]]; then
  cp .env.example .env
  log "已从 .env.example 创建本地 .env。"
fi

if ! "$PYTHON_BIN" -c "import fastapi, sqlalchemy, alembic, uvicorn" >/dev/null 2>&1; then
  log "安装 Python 依赖……"
  "$PYTHON_BIN" -m pip install -r requirements.txt
fi

if [[ ! -d frontend/node_modules ]]; then
  log "安装前端依赖……"
  npm --prefix frontend ci
fi

log "升级数据库并写入幂等 Demo 数据……"
"$PYTHON_BIN" -m alembic upgrade head
"$PYTHON_BIN" scripts/seed_users.py

backend_args=(
  -m uvicorn backend.app.main:app
  --host "$BACKEND_HOST"
  --port "$BACKEND_PORT"
)
if [[ "$BACKEND_RELOAD" == "true" ]]; then
  backend_args+=(--reload)
fi

log "启动后端：http://${BACKEND_HOST}:${BACKEND_PORT}"
"$PYTHON_BIN" "${backend_args[@]}" &
BACKEND_PID=$!

backend_ready=false
for _attempt in {1..60}; do
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    wait "$BACKEND_PID"
    exit 1
  fi
  if "$PYTHON_BIN" -c '
import http.client
import sys

connection = http.client.HTTPConnection(sys.argv[1], int(sys.argv[2]), timeout=0.2)
connection.request("GET", "/health")
raise SystemExit(0 if connection.getresponse().status == 200 else 1)
' "$BACKEND_HOST" "$BACKEND_PORT" >/dev/null 2>&1; then
    backend_ready=true
    break
  fi
  sleep 0.25
done
if [[ "$backend_ready" != "true" ]]; then
  log "后端在 15 秒内未就绪。"
  exit 1
fi

log "启动前端：http://${FRONTEND_HOST}:${FRONTEND_PORT}"
VITE_API_BASE_URL="$API_URL" npm --prefix frontend run dev -- \
  --host "$FRONTEND_HOST" --port "$FRONTEND_PORT" &
FRONTEND_PID=$!

log "启动完成。Web：http://${FRONTEND_HOST}:${FRONTEND_PORT}  API：http://${BACKEND_HOST}:${BACKEND_PORT}/docs"
log "Demo 登录：user001@ustc.edu.cn / CampusDemo123!；按 Ctrl+C 同时停止。"

wait -n "$BACKEND_PID" "$FRONTEND_PID"
