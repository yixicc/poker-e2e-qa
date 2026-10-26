#!/bin/bash
# 双击或登录项启动：走 Terminal，可访问 Downloads 下的项目
cd "$(dirname "$0")/.." || exit 1
export REPORT_HOST="${REPORT_HOST:-0.0.0.0}"
export REPORT_PORT="${REPORT_PORT:-8767}"
# 若已在听则直接退出
if lsof -nP -iTCP:"$REPORT_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  exit 0
fi
exec ./scripts/run_portal_daemon.sh
