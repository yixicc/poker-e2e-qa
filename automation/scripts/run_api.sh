#!/usr/bin/env bash
# 跑 API 自动化 → 结果门户（HTTP）→ 可下载 Excel / 查看 Allure
set -uo pipefail
cd "$(dirname "$0")/.."

# Cursor/IDE 终端常不加载 ~/.zprofile
if ! command -v brew >/dev/null 2>&1; then
  if [[ -x /opt/homebrew/bin/brew ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  elif [[ -x /usr/local/bin/brew ]]; then
    eval "$(/usr/local/bin/brew shellenv)"
  fi
fi

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

./scripts/gen_allure.sh reports/allure-results reports/allure-report || true

python3 scripts/gen_results_portal.py \
  --reports-dir reports \
  --html "$HTML_REPORT" \
  --allure reports/allure-report/index.html \
  --excel-latest "$EXCEL_LATEST" \
  --title "MCP API 自动化测试结果" >/dev/null

echo ""
# 用 HTTP 打开门户（Allure 必须走 http，不能 file://）
./scripts/serve_reports.sh

exit "$PY_EXIT"
