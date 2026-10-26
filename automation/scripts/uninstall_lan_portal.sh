#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="com.poker.mcp-report-portal"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
COMMAND_FILE="$ROOT/scripts/start_portal.command"
PORT="${REPORT_PORT:-8767}"

launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null || true
launchctl unload "$PLIST" 2>/dev/null || true
rm -f "$PLIST"

if [[ "$(uname)" == "Darwin" ]]; then
  osascript <<EOF 2>/dev/null || true
tell application "System Events"
  set p to POSIX path of (POSIX file "$COMMAND_FILE")
  repeat with i in (get login items)
    if path of i is p then delete i
  end repeat
end tell
EOF
fi

if command -v lsof >/dev/null 2>&1; then
  pids="$(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    # shellcheck disable=SC2086
    kill $pids 2>/dev/null || true
  fi
fi
rm -f "$ROOT/reports/.report-server.pid"
echo "已卸载常驻配置并尝试停止 :${PORT}"
