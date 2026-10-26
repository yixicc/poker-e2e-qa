#!/usr/bin/env bash
# LaunchAgent / 常驻入口：必须经 .venv/bin/python3 启动，保留 site-packages
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export REPORT_HOST="${REPORT_HOST:-0.0.0.0}"
export REPORT_PORT="${REPORT_PORT:-8767}"
mkdir -p reports data/uploads

if [[ -x "$ROOT/.venv/bin/python3" ]]; then
  PY="$ROOT/.venv/bin/python3"
elif [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
else
  PY="$(command -v python3)"
fi

exec "$PY" "$ROOT/server/app.py"
