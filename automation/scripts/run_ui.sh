#!/usr/bin/env bash
# 跑 UI 自动化 → 结果门户页并自动打开
set -uo pipefail
cd "$(dirname "$0")/.."

mkdir -p reports/allure-results reports
HTML_REPORT="$(pwd)/reports/report-ui.html"
PORTAL="$(pwd)/reports/index.html"

set +e
python3 -m pytest -m ui \
  --alluredir=reports/allure-results \
  --html="$HTML_REPORT" \
  --self-contained-html \
  "$@"
PY_EXIT=$?
set -e

./scripts/gen_allure.sh reports/allure-results reports/allure-report-ui || true

python3 scripts/gen_results_portal.py \
  --reports-dir reports \
  --html "$HTML_REPORT" \
  --allure reports/allure-report-ui/index.html \
  --excel-latest reports/MCP执行结果_latest.xlsx \
  --title "MCP UI 自动化测试结果" >/dev/null

echo ""
./scripts/print_and_open.sh "结果页面" "$PORTAL"

exit "$PY_EXIT"
