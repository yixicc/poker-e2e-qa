#!/usr/bin/env bash
# 跨平台入口：委托 scripts/stop_portal.py（Windows 用 stop_portal.bat）
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -x .venv/bin/python ]]; then PY=".venv/bin/python"; else PY="python3"; fi
exec "$PY" scripts/stop_portal.py "$@"
