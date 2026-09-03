#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

PYTHON_BIN="${PYTHON_BIN:-python}"
MOBILE_BACKEND_PORT="${MOBILE_BACKEND_PORT:-8000}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  printf '未找到 Python：%s\n' "$PYTHON_BIN" >&2
  exit 1
fi

default_device="$(ip -4 route show table main default 2>/dev/null | awk 'NR == 1 {print $5}')"
lan_ip=""
if [[ -n "$default_device" ]]; then
  lan_ip="$(ip -4 -o addr show dev "$default_device" scope global 2>/dev/null | awk 'NR == 1 {split($4, address, "/"); print address[1]}')"
fi

"$PYTHON_BIN" scripts/seed_users.py

printf '\n校园搭子真机调试后端即将启动：\n'
printf '  监听地址：http://0.0.0.0:%s\n' "$MOBILE_BACKEND_PORT"
if [[ -n "$lan_ip" ]]; then
  printf '  手机地址：http://%s:%s\n' "$lan_ip" "$MOBILE_BACKEND_PORT"
  first_octet="${lan_ip%%.*}"
  remaining_octets="${lan_ip#*.}"
  second_octet="${remaining_octets%%.*}"
  if [[ "$first_octet" == "100" ]] && (( second_octet >= 64 && second_octet <= 127 )); then
    printf '  警告：该地址属于 100.64.0.0/10 共享地址段，校园网/公共 Wi-Fi 可能隔离终端。\n'
    printf '  如果手机报 ERR_ADDRESS_UNREACHABLE，请改用手机热点、家庭路由器或 HTTPS 后端。\n'
  fi
  printf '  使用“真机调试”扫码，连接成功后在远程调试控制台执行：\n'
  printf "  wx.setStorageSync('apiBaseUrl', 'http://%s:%s')\n" "$lan_ip" "$MOBILE_BACKEND_PORT"
  printf '  如果使用普通“预览”，该局域网 HTTP 地址仍会被域名白名单拦截。\n'
else
  printf '  未自动识别局域网 IP，请用 ip -4 address 手工确认。\n'
fi
printf '按 Ctrl+C 停止后端。\n\n'

exec "$PYTHON_BIN" -m uvicorn backend.app.main:app \
  --host 0.0.0.0 --port "$MOBILE_BACKEND_PORT"
