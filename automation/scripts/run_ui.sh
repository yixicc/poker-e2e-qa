#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

mkdir -p reports/allure-results

python3 -m pytest -m ui \
  --alluredir=reports/allure-results \
  --html=reports/report-ui.html \
  --self-contained-html \
  "$@"

echo "HTML 报告: $(pwd)/reports/report-ui.html"
