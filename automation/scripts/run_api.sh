#!/usr/bin/env bash
# 跑 API 自动化 → 生成结果门户页（下载 Excel / 看 Allure / HTML）并自动打开门户
set -uo pipefail
cd "$(dirname "$0")/.."

mkdir -p reports/allure-results reports

MARK="api"
if [[ "${1:-}" == "smoke" ]]; then
  MARK="api and smoke"
  shift || true
fi

HTML_REPORT="$(pwd)/reports/report.html"
EXCEL_LATEST="$(pwd)/reports/MCP执行结果_latest.xlsx"
PORTAL="$(pwd)/reports/index.html"

set +e
python3 -m pytest -m "$MARK" \
  --alluredir=reports/allure-results \
  --html="$HTML_REPORT" \
  --self-contained-html \
  "$@"
PY_EXIT=$?
set -e

# Allure HTML（若已装 CLI）
./scripts/gen_allure.sh reports/allure-results reports/allure-report || true

# 结果门户页
python3 scripts/gen_results_portal.py \
  --reports-dir reports \
  --html "$HTML_REPORT" \
  --allure reports/allure-report/index.html \
  --excel-latest "$EXCEL_LATEST" \
  --title "MCP API 自动化测试结果" >/dev/null

echo ""
# 只自动打开门户页（不直接弹 Excel）
./scripts/print_and_open.sh "结果页面" "$PORTAL"

exit "$PY_EXIT"
