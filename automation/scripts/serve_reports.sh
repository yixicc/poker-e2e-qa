#!/usr/bin/env bash
# 启动结果门户 + 上传转换服务（Flask），替代纯 http.server
set -euo pipefail
cd "$(dirname "$0")/.."

PORT="${REPORT_PORT:-8767}"
PID_FILE="reports/.report-server.pid"
LOG_FILE="reports/.report-server.log"
mkdir -p reports data/uploads

# 优先用项目 venv
if [[ -x .venv/bin/python ]]; then
  PY=".venv/bin/python"
else
  PY="python3"
fi

# 确保依赖
if ! "$PY" -c "import flask, openpyxl" 2>/dev/null; then
  echo "正在安装 flask / openpyxl…"
  "$PY" -m pip install -q flask openpyxl
fi

# 停旧进程
if [[ -f "$PID_FILE" ]]; then
  old="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "$old" ]] && kill -0 "$old" 2>/dev/null; then
    kill "$old" 2>/dev/null || true
    sleep 0.3
  fi
  rm -f "$PID_FILE"
fi
if command -v lsof >/dev/null 2>&1; then
  pids="$(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    # shellcheck disable=SC2086
    kill $pids 2>/dev/null || true
    sleep 0.3
  fi
fi

export REPORT_PORT="$PORT"
nohup "$PY" server/app.py >"$LOG_FILE" 2>&1 &
echo $! >"$PID_FILE"
sleep 0.8
if ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "服务启动失败，日志："
  tail -30 "$LOG_FILE" || true
  exit 1
fi

URL="http://127.0.0.1:${PORT}/index.html"
UPLOAD="http://127.0.0.1:${PORT}/upload.html"
echo "结果页面: $URL"
echo "上传转换: $UPLOAD"
echo "Allure:    http://127.0.0.1:${PORT}/allure-report/index.html"

if [[ "${REPORT_OPEN:-1}" == "1" ]]; then
  if [[ "$(uname)" == "Darwin" ]]; then
    open "$URL" 2>/dev/null || true
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$URL" 2>/dev/null || true
  fi
fi
