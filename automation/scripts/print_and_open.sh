#!/usr/bin/env bash
# 打印可点击的 file:// 链接，并在 macOS 上尝试打开
# 用法: print_and_open.sh "标签" /abs/path/to/file
# REPORT_OPEN=0 时只打印不打开
set -euo pipefail

LABEL="${1:-报告}"
FILE="${2:-}"

if [[ -z "$FILE" || ! -e "$FILE" ]]; then
  echo "$LABEL: （文件不存在） $FILE"
  exit 0
fi

ABS="$(cd "$(dirname "$FILE")" && pwd)/$(basename "$FILE")"
URI="file://${ABS// /%20}"

echo "$LABEL: $URI"

if [[ "${REPORT_OPEN:-1}" == "1" ]]; then
  if [[ "$(uname)" == "Darwin" ]]; then
    open "$ABS" 2>/dev/null || true
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$ABS" 2>/dev/null || true
  fi
fi
