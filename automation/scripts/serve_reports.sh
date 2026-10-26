#!/usr/bin/env bash
# 跨平台入口：委托 scripts/serve_reports.py（Windows 用 serve_reports.bat）
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -x .venv/bin/python ]]; then PY=".venv/bin/python"; else PY="python3"; fi
exec "$PY" scripts/serve_reports.py "$@"
