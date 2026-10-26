#!/usr/bin/env bash
# 打印可点击的 file:// 链接，并在 macOS 上尝试打开
# 用法: print_and_open.sh "标签" /abs/path/to/file [force_open=1]
set -euo pipefail

LABEL="${1:-报告}"
FILE="${2:-}"
FORCE_OPEN="${3:-}"

if [[ -z "$FILE" || ! -e "$FILE" ]]; then
  echo "$LABEL: （文件不存在） $FILE"
  exit 0
fi

ABS="$(cd "$(dirname "$FILE")" && pwd)/$(basename "$FILE")"
# 空格等字符做简单 URL 编码，终端更易识别为链接
URI="file://${ABS// /%20}"

echo "$LABEL: $URI"

# 默认自动打开；REPORT_OPEN=0 可关闭
if [[ "${REPORT_OPEN:-1}" == "1" ]] || [[ "$FORCE_OPEN" == "1" ]]; then
  if [[ "$(uname)" == "Darwin" ]]; then
    open "$ABS" 2>/dev/null || true
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$ABS" 2>/dev/null || true
  fi
fi
