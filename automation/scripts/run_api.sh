#!/usr/bin/env bash
# 在 automation/ 目录执行 API 自动化并生成 HTML + Allure 结果
set -euo pipefail
cd "$(dirname "$0")/.."

mkdir -p reports/allure-results

MARK="api"
if [[ "${1:-}" == "smoke" ]]; then
  MARK="api and smoke"
  shift || true
fi

python3 -m pytest -m "$MARK" \
  --alluredir=reports/allure-results \
  --html=reports/report.html \
  --self-contained-html \
  "$@"

echo ""
echo "HTML 报告: $(pwd)/reports/report.html"
echo "Allure 结果: $(pwd)/reports/allure-results"
echo "若已安装 allure CLI: allure serve reports/allure-results"
