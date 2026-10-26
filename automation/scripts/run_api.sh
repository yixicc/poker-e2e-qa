#!/usr/bin/env bash
# 跑 API → 归档本次执行 → 刷新历史列表门户 → HTTP 打开
set -uo pipefail
cd "$(dirname "$0")/.."

if ! command -v brew >/dev/null 2>&1; then
  if [[ -x /opt/homebrew/bin/brew ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  elif [[ -x /usr/local/bin/brew ]]; then
    eval "$(/usr/local/bin/brew shellenv)"
  fi
fi

mkdir -p reports/allure-results reports/runs

MARK="api"
if [[ "${1:-}" == "smoke" ]]; then
  MARK="api and smoke"
  shift || true
fi

HTML_REPORT="$(pwd)/reports/report.html"
EXCEL_LATEST="$(pwd)/reports/MCP执行结果_latest.xlsx"

if [[ -x .venv/bin/python ]]; then PY=".venv/bin/python"; else PY="python3"; fi

CASES="$(PYTHONPATH=. "$PY" -c "from config.settings import settings; print(settings.cases_xlsx)")"
echo "用例表: $CASES"
echo "（命令行使用 .env 的 MCP_CASES_XLSX，不必先上传）"
if [[ ! -f "$CASES" ]]; then
  echo "找不到用例表。请把 MCP_CASES_XLSX 指到已有的自动化 Excel。"
  exit 1
fi

set +e
"$PY" -m pytest -m "$MARK" \
  --alluredir=reports/allure-results \
  --html="$HTML_REPORT" \
  --self-contained-html \
  "$@"
PY_EXIT=$?
set -e

./scripts/gen_allure.sh reports/allure-results reports/allure-report || true

# 把 HTML / Allure 补进最近一次 run 归档
"$PY" - <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, str(Path('.').resolve()))
from common.run_archive import enrich_latest_run
from scripts.gen_results_portal import build_portal
meta = enrich_latest_run(
    Path('reports'),
    html_report=Path('reports/report.html'),
    allure_report_dir=Path('reports/allure-report'),
)
print('enrich', meta.get('run_id') if meta else None)
build_portal(Path('reports'), title='MCP 自动化测试')
print('portal ok')
PY

echo ""
./scripts/serve_reports.sh

exit "$PY_EXIT"
