#!/usr/bin/env bash
# 启动结果门户 + 上传转换服务（Flask）
# 默认监听 0.0.0.0，本机与内网均可访问；常驻可用 ./scripts/install_lan_portal.sh
set -euo pipefail
cd "$(dirname "$0")/.."

PORT="${REPORT_PORT:-8767}"
HOST="${REPORT_HOST:-0.0.0.0}"
PID_FILE="reports/.report-server.pid"
LOG_FILE="reports/.report-server.log"
mkdir -p reports data/uploads

if [[ -x .venv/bin/python ]]; then
  PY=".venv/bin/python"
else
  PY="python3"
fi

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

lan_ip() {
  local ip=""
  if [[ "$(uname)" == "Darwin" ]]; then
    for iface in en0 en1 en2; do
      ip="$(ipconfig getifaddr "$iface" 2>/dev/null || true)"
      [[ -n "$ip" ]] && break
    done
  else
    ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
  fi
  echo "${ip:-}"
}

export REPORT_PORT="$PORT"
export REPORT_HOST="$HOST"
nohup "$PY" server/app.py >"$LOG_FILE" 2>&1 &
echo $! >"$PID_FILE"
sleep 0.8
if ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "服务启动失败，日志："
  tail -30 "$LOG_FILE" || true
  exit 1
fi

LAN="$(lan_ip)"
echo "监听:     ${HOST}:${PORT}"
echo "本机:     http://127.0.0.1:${PORT}/"
if [[ -n "$LAN" ]]; then
  echo "内网:     http://${LAN}:${PORT}/"
  echo "上传(内网): http://${LAN}:${PORT}/upload.html"
else
  echo "内网:     （未检测到局域网 IP，请用本机 ifconfig / ip 查看）"
fi
echo "Allure:   http://127.0.0.1:${PORT}/allure-report/"
echo "日志:     $LOG_FILE"
echo "常驻开机: ./scripts/install_lan_portal.sh"

if [[ "${REPORT_OPEN:-1}" == "1" ]]; then
  if [[ "$(uname)" == "Darwin" ]]; then
    open "http://127.0.0.1:${PORT}/" 2>/dev/null || true
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "http://127.0.0.1:${PORT}/" 2>/dev/null || true
  fi
fi
