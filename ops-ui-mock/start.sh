#!/bin/sh
set -e
cd "$(dirname "$0")"
PORT="${1:-8768}"
IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo '这台机器的局域网IP')"
echo "本机  http://127.0.0.1:${PORT}/poker-review-report-ops.html"
echo "内网  http://${IP}:${PORT}/poker-review-report-ops.html"
echo "页面稿，数字示意。不要覆盖正式运维台。"
exec python3 -m http.server "$PORT" --bind 0.0.0.0
