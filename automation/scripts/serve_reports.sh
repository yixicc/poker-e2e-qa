#!/usr/bin/env bash
# 用本地 HTTP 托管 reports/，避免 Allure 在 file:// 下 Failed to fetch
set -euo pipefail
cd "$(dirname "$0")/.."

PORT="${REPORT_PORT:-8767}"
ROOT="$(pwd)/reports"
PID_FILE="$ROOT/.report-server.pid"
LOG_FILE="$ROOT/.report-server.log"

mkdir -p "$ROOT"

# 停掉旧进程
if [[ -f "$PID_FILE" ]]; then
  old="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "$old" ]] && kill -0 "$old" 2>/dev/null; then
    kill "$old" 2>/dev/null || true
    sleep 0.3
  fi
  rm -f "$PID_FILE"
fi
# 若端口被占，尽量释放同目录起的 python http.server
if command -v lsof >/dev/null 2>&1; then
  pids="$(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    # shellcheck disable=SC2086
    kill $pids 2>/dev/null || true
    sleep 0.3
  fi
fi

cd "$ROOT"
# 后台启动
nohup python3 -m http.server "$PORT" --bind 127.0.0.1 >"$LOG_FILE" 2>&1 &
echo $! >"$PID_FILE"
sleep 0.4

URL="http://127.0.0.1:${PORT}/index.html"
echo "结果页面: $URL"
echo "Allure:    http://127.0.0.1:${PORT}/allure-report/index.html"
echo "（HTTP 托管中，勿用 file:// 打开 Allure）"

if [[ "${REPORT_OPEN:-1}" == "1" ]]; then
  if [[ "$(uname)" == "Darwin" ]]; then
    open "$URL" 2>/dev/null || true
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$URL" 2>/dev/null || true
  fi
fi
