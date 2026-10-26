#!/usr/bin/env bash
# 跑 API 自动化 → pytest-html + Allure + Excel；结束打印可点击链接并自动打开 HTML
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

set +e
python3 -m pytest -m "$MARK" \
  --alluredir=reports/allure-results \
  --html="$HTML_REPORT" \
  --self-contained-html \
  "$@"
PY_EXIT=$?
set -e

echo ""
./scripts/print_and_open.sh "pytest-html" "$HTML_REPORT"
if [[ -f "$EXCEL_LATEST" ]]; then
  ./scripts/print_and_open.sh "Excel结果" "$EXCEL_LATEST" 0
  # Excel 也自动打开（可用 REPORT_OPEN_EXCEL=0 关闭）
  if [[ "${REPORT_OPEN_EXCEL:-1}" == "1" ]] && [[ "${REPORT_OPEN:-1}" == "1" ]]; then
    if [[ "$(uname)" == "Darwin" ]]; then
      open "$EXCEL_LATEST" 2>/dev/null || true
    fi
  fi
else
  echo "Excel结果: （尚未生成，请确认用例有执行记录）"
fi

./scripts/gen_allure.sh reports/allure-results reports/allure-report

exit "$PY_EXIT"
