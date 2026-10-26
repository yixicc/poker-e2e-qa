#!/usr/bin/env bash
# 跨平台入口：委托 scripts/run_api.py（Windows 用 run_api.bat）
set -uo pipefail
cd "$(dirname "$0")/.."
if [[ -x .venv/bin/python ]]; then PY=".venv/bin/python"; else PY="python3"; fi
exec "$PY" scripts/run_api.py "$@"
