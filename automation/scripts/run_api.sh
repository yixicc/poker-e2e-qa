#!/usr/bin/env bash
# 跑 API 自动化 → pytest-html + Allure 原始结果 → 自动生成 Allure HTML
set -uo pipefail
cd "$(dirname "$0")/.."

mkdir -p reports/allure-results

MARK="api"
if [[ "${1:-}" == "smoke" ]]; then
  MARK="api and smoke"
  shift || true
fi

set +e
python3 -m pytest -m "$MARK" \
  --alluredir=reports/allure-results \
  --html=reports/report.html \
  --self-contained-html \
  "$@"
PY_EXIT=$?
set -e

echo ""
echo "pytest-html: $(pwd)/reports/report.html"
echo "Excel 结果: $(pwd)/reports/MCP执行结果_latest.xlsx （及带时间戳的一份）"
./scripts/gen_allure.sh reports/allure-results reports/allure-report

exit "$PY_EXIT"
