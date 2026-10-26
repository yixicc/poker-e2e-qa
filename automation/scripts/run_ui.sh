#!/usr/bin/env bash
# 跑 production UI（共用 cases 表）→ 归档 → 刷新门户
set -uo pipefail
cd "$(dirname "$0")/.."

if ! command -v brew >/dev/null 2>&1; then
  if [[ -x /opt/homebrew/bin/brew ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  elif [[ -x /usr/local/bin/brew ]]; then
    eval "$(/usr/local/bin/brew shellenv)"
  fi
fi

mkdir -p reports/allure-results reports/runs reports/ui_chat_turns

if [[ -x .venv/bin/python ]]; then PY=".venv/bin/python"; else PY="python3"; fi

# smoke：前 3 条；headed：看得见浏览器窗口。两个可以一起用，顺序不限。
# export 会盖过 .env 里的同名变量。
SMOKE=0
HEADED=0
PASSTHRU=()
for arg in "$@"; do
  case "$arg" in
    smoke) SMOKE=1 ;;
    headed|--headed) HEADED=1 ;;
    *) PASSTHRU+=("$arg") ;;
  esac
done

if [[ "$SMOKE" == "1" ]]; then
  export UI_CASE_LIMIT=3
  echo "UI 冒烟：同一张 cases 表，只问前 3 条"
else
  export UI_CASE_LIMIT=0
  echo "UI 全量：同一张 cases 表，按顺序全部提问"
fi
if [[ "$HEADED" == "1" ]]; then
  export UI_HEADED=1
  echo "UI 有界面：浏览器窗口可见"
else
  echo "UI 无头：不弹出浏览器窗口"
fi

CASES="$(PYTHONPATH=. "$PY" -c "from config.settings import settings; print(settings.cases_xlsx)")"
echo "用例表: $CASES"
if [[ ! -f "$CASES" ]]; then
  echo "找不到用例表。请把 MCP_CASES_XLSX 指到已有的自动化 Excel。"
  exit 1
fi

HTML_REPORT="$(pwd)/reports/report-ui.html"

set +e
PYTEST_ARGS=(
  -m ui
  --ignore=ui/test_chat_smoke.py
  --alluredir=reports/allure-results
  --html="$HTML_REPORT"
  --self-contained-html
)
if [[ ${#PASSTHRU[@]} -gt 0 ]]; then
  PYTEST_ARGS+=("${PASSTHRU[@]}")
fi
"$PY" -m pytest "${PYTEST_ARGS[@]}"
PY_EXIT=$?
set -e

./scripts/gen_allure.sh reports/allure-results reports/allure-report || true

"$PY" - <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, str(Path('.').resolve()))
from common.run_archive import enrich_latest_run
from scripts.gen_results_portal import build_portal
enrich_latest_run(
    Path('reports'),
    html_report=Path('reports/report-ui.html'),
    allure_report_dir=Path('reports/allure-report'),
)
build_portal(Path('reports'), title='MCP 自动化测试')
print('portal ok')
PY

echo ""
REPORT_OPEN=0 ./scripts/serve_reports.sh || true
echo "看结果: http://127.0.0.1:${REPORT_PORT:-8767}/ （展示服务请用 ./scripts/serve_reports.sh 常开）"

exit "$PY_EXIT"
