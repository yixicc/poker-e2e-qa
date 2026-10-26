#!/usr/bin/env bash
# 跑 UI 自动化 → 自动打开 HTML 报告
set -uo pipefail
cd "$(dirname "$0")/.."

mkdir -p reports/allure-results reports
HTML_REPORT="$(pwd)/reports/report-ui.html"

set +e
python3 -m pytest -m ui \
  --alluredir=reports/allure-results \
  --html="$HTML_REPORT" \
  --self-contained-html \
  "$@"
PY_EXIT=$?
set -e

echo ""
./scripts/print_and_open.sh "pytest-html" "$HTML_REPORT"
./scripts/gen_allure.sh reports/allure-results reports/allure-report-ui

exit "$PY_EXIT"
