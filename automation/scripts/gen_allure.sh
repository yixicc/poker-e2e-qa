#!/usr/bin/env bash
# 把 allure-results 生成可打开的 HTML 报告
set -euo pipefail
cd "$(dirname "$0")/.."

# IDE 终端可能没有 brew PATH
if ! command -v allure >/dev/null 2>&1; then
  if [[ -x /opt/homebrew/bin/allure ]]; then
    export PATH="/opt/homebrew/bin:$PATH"
  elif [[ -x /usr/local/bin/allure ]]; then
    export PATH="/usr/local/bin:$PATH"
  elif [[ -x /opt/homebrew/bin/brew ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  fi
fi

RESULTS="${1:-reports/allure-results}"
OUT="${2:-reports/allure-report}"

if [[ ! -d "$RESULTS" ]] || [[ -z "$(ls -A "$RESULTS" 2>/dev/null || true)" ]]; then
  echo "没有 Allure 原始结果：$RESULTS（请先跑 pytest --alluredir=...）"
  exit 0
fi

if ! command -v allure >/dev/null 2>&1; then
  echo "未安装 allure CLI，跳过 HTML 生成。"
  echo "安装（macOS）：brew install allure"
  echo "若已安装仍提示找不到：新开一个终端，或执行 eval \"\$(/opt/homebrew/bin/brew shellenv)\""
  echo "原始结果仍在：$RESULTS"
  echo "pytest-html 可用：reports/report.html"
  exit 0
fi

mkdir -p "$OUT"
allure generate "$RESULTS" -o "$OUT" --clean
INDEX="$(cd "$OUT" && pwd)/index.html"
echo "Allure 报告已生成：file://${INDEX// /%20}"
# 默认不单独弹 Allure（由结果门户页统一入口）；需要时 ALLURE_OPEN=1
if [[ "$(uname)" == "Darwin" ]] && [[ "${ALLURE_OPEN:-0}" == "1" ]]; then
  open "$INDEX" 2>/dev/null || true
fi
