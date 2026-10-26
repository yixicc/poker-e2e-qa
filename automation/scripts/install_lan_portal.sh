#!/usr/bin/env bash
# 安装常驻门户：默认 0.0.0.0 内网可访问
# - 项目在 Downloads/Desktop/Documents：用「登录项 + .command」（LaunchAgent 无权限读这些目录）
# - 其它路径：用 LaunchAgent KeepAlive
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="com.poker.mcp-report-portal"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
PORT="${REPORT_PORT:-8767}"
HOST="${REPORT_HOST:-0.0.0.0}"
COMMAND_FILE="$ROOT/scripts/start_portal.command"
DAEMON="$ROOT/scripts/run_portal_daemon.sh"

chmod +x "$DAEMON" "$COMMAND_FILE" "$ROOT/scripts/serve_reports.sh" \
  "$ROOT/scripts/uninstall_lan_portal.sh" 2>/dev/null || true
mkdir -p "$ROOT/reports" "$ROOT/data/uploads"

# 停旧监听
if command -v lsof >/dev/null 2>&1; then
  pids="$(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    # shellcheck disable=SC2086
    kill $pids 2>/dev/null || true
    sleep 0.4
  fi
fi
rm -f "$ROOT/reports/.report-server.pid"
launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null || true
launchctl unload "$PLIST" 2>/dev/null || true
rm -f "$PLIST"

lan_ip() {
  local ip=""
  if [[ "$(uname)" == "Darwin" ]]; then
    for iface in en0 en1 en2; do
      ip="$(ipconfig getifaddr "$iface" 2>/dev/null || true)"
      [[ -n "$ip" ]] && break
    done
  fi
  echo "${ip:-}"
}

protected_path=0
case "$ROOT" in
  */Downloads/*|*/Desktop/*|*/Documents/*) protected_path=1 ;;
esac

if [[ "$(uname)" != "Darwin" ]]; then
  echo "非 macOS：请用 screen/tmux/systemd 常驻，并设 REPORT_HOST=0.0.0.0"
  REPORT_HOST="$HOST" REPORT_PORT="$PORT" REPORT_OPEN=0 "$ROOT/scripts/serve_reports.sh"
  exit 0
fi

if [[ "$protected_path" -eq 1 ]]; then
  echo "检测到项目在受保护目录（Downloads/Desktop/Documents）。"
  echo "macOS LaunchAgent 无法读取该目录，改用「登录时打开 .command」。"
  # 立刻后台拉起（当前终端有权限）
  REPORT_HOST="$HOST" REPORT_PORT="$PORT" REPORT_OPEN=0 "$ROOT/scripts/serve_reports.sh"

  # 注册登录项（用户会话里开 Terminal 跑 .command）
  osascript <<EOF 2>/dev/null || true
tell application "System Events"
  set p to POSIX file "$COMMAND_FILE"
  set existsItem to false
  repeat with i in (get login items)
    if path of i is (POSIX path of p) then set existsItem to true
  end repeat
  if existsItem is false then
    make login item at end with properties {path:POSIX path of p, hidden:true, name:"MCP Report Portal"}
  end if
end tell
EOF
  echo "已尝试加入登录项：MCP Report Portal"
  echo "若系统弹出授权，请允许「系统事件 / 辅助功能」。"
  echo "也可：系统设置 → 通用 → 登录项 → 添加：$COMMAND_FILE"
  echo ""
  echo "更稳方案：把仓库移出 Downloads（如 ~/Projects/），再执行本脚本，将改用 LaunchAgent 崩溃自拉起。"
else
  cat >"$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>WorkingDirectory</key>
  <string>${ROOT}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>${DAEMON}</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>REPORT_HOST</key>
    <string>${HOST}</string>
    <key>REPORT_PORT</key>
    <string>${PORT}</string>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>ThrottleInterval</key>
  <integer>5</integer>
  <key>StandardOutPath</key>
  <string>${ROOT}/reports/.report-server.log</string>
  <key>StandardErrorPath</key>
  <string>${ROOT}/reports/.report-server.log</string>
</dict>
</plist>
EOF
  launchctl bootstrap "gui/$(id -u)" "$PLIST" 2>/dev/null || launchctl load -w "$PLIST"
  sleep 1
  echo "已安装 LaunchAgent: $LABEL"
fi

LAN="$(lan_ip)"
echo "本机: http://127.0.0.1:${PORT}/"
if [[ -n "$LAN" ]]; then
  echo "内网: http://${LAN}:${PORT}/"
fi
if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "状态: 正在监听 :${PORT}（0.0.0.0）"
else
  echo "状态: 未监听，请执行: REPORT_OPEN=0 ./scripts/serve_reports.sh"
fi
echo "卸载: ./scripts/uninstall_lan_portal.sh"
