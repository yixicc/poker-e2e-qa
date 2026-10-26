#!/usr/bin/env bash
# 跨平台入口：委托 scripts/gen_allure.py（Windows 用 gen_allure.bat）
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -x .venv/bin/python ]]; then PY=".venv/bin/python"; else PY="python3"; fi
# 兼容旧参数：results out
exec "$PY" scripts/gen_allure.py "$@"
