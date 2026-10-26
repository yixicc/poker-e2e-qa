#!/bin/bash
cd "$(dirname "$0")/.." || exit 1
export REPORT_HOST="${REPORT_HOST:-0.0.0.0}"
export REPORT_PORT="${REPORT_PORT:-8767}"
export REPORT_OPEN=0
./scripts/serve_reports.sh
./scripts/keep_portal_alive.sh
exit 0
