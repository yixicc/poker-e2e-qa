#!/usr/bin/env bash
# 后台保活：展示服务挂了就自动拉起（与 pytest 无关）
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PORT="${REPORT_PORT:-8767}"
HOST="${REPORT_HOST:-0.0.0.0}"
PID_FILE="reports/.portal-watchdog.pid"
LOG_FILE="reports/.portal-watchdog.log"
SERVER_PID="reports/.report-server.pid"
SERVER_LOG="reports/.report-server.log"
mkdir -p reports

if [[ -x .venv/bin/python ]]; then PY=".venv/bin/python"; else PY="python3"; fi

if [[ -f "$PID_FILE" ]]; then
  old="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "$old" ]] && kill -0 "$old" 2>/dev/null; then
    echo "保活已在跑 pid=$old"
    exit 0
  fi
fi

# 先确保当前有服务
if ! lsof -tiTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  REPORT_HOST="$HOST" REPORT_PORT="$PORT" REPORT_OPEN=0 \
    ./scripts/serve_reports.sh >>"$LOG_FILE" 2>&1 || true
fi

nohup bash -c "
PY='${PY}'
ROOT='${ROOT}'
PORT='${PORT}'
HOST='${HOST}'
SERVER_PID='${ROOT}/${SERVER_PID}'
SERVER_LOG='${ROOT}/${SERVER_LOG}'
LOG='${ROOT}/${LOG_FILE}'
cd \"\$ROOT\" || exit 1
while true; do
  if lsof -tiTCP:\$PORT -sTCP:LISTEN >/dev/null 2>&1; then
    sleep 20
    continue
  fi
  echo \"[\$(date '+%F %T')] portal down, starting\" >>\"\$LOG\"
  export REPORT_HOST=\"\$HOST\" REPORT_PORT=\"\$PORT\"
  # 新会话拉起，避免和父 shell 互杀
  \"\$PY\" \"\$ROOT/scripts/start_portal_process.py\" >>\"\$LOG\" 2>&1 || true
  sleep 2
done
" >/dev/null 2>&1 &
echo $! >"$PID_FILE"
# 保活本身也脱离进程组
disown "$(cat "$PID_FILE")" 2>/dev/null || true
echo "已启动保活 pid=$(cat "$PID_FILE")，约每 20s 检查 :${PORT}"
echo "日志: $LOG_FILE"
echo "停保活: kill \$(cat $PID_FILE); rm -f $PID_FILE"
