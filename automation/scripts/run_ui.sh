#!/usr/bin/env bash
# 跑 UI 自动化 → 自动生成报告
set -uo pipefail
cd "$(dirname "$0")/.."

mkdir -p reports/allure-results

set +e
python3 -m pytest -m ui \
  --alluredir=reports/allure-results \
  --html=reports/report-ui.html \
  --self-contained-html \
  "$@"
PY_EXIT=$?
set -e

echo ""
echo "pytest-html: $(pwd)/reports/report-ui.html"
./scripts/gen_allure.sh reports/allure-results reports/allure-report-ui

exit "$PY_EXIT"
