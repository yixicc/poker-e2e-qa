"""把执行结果导出为 Excel：执行明细 + 汇总统计。"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from common.result_store import ExecRecord

DETAIL_HEADERS = [
    # 原始用例
    "case_id",
    "group",
    "title",
    "priority",
    "step_no",
    "user_question",
    "assert_hints",
    "expect_tools",
    "notes",
    # 自动化参数
    "tool_name",
    "role",
    "metric_codes",
    "assert_expr",
    "request_body",
    # 返回 / 结果
    "result",
    "http_status",
    "elapsed_ms",
    "response_summary",
    "response_raw",
    "error_message",
]


def _style_header(ws, color: str = "1F4E79") -> None:
    fill = PatternFill("solid", fgColor=color)
    font = Font(color="FFFFFF", bold=True)
    for cell in ws[1]:
        cell.fill = fill
        cell.font = font
        cell.alignment = Alignment(wrap_text=True, vertical="center")


def _autosize(ws, max_width: int = 40) -> None:
    for col in ws.columns:
        letter = get_column_letter(col[0].column)
        width = 10
        for cell in col[:80]:
            if cell.value is None:
                continue
            width = max(width, min(max_width, len(str(cell.value).split("\n")[0]) + 2))
        ws.column_dimensions[letter].width = width


def _trunc(text: Any, n: int = 3000) -> str:
    s = "" if text is None else str(text)
    return s if len(s) <= n else s[:n] + f"...(截断共{len(s)}字)"


def export_results_xlsx(records: list[ExecRecord], out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()

    # —— 执行明细 ——
    ws = wb.active
    ws.title = "执行明细"
    ws.append(DETAIL_HEADERS)
    for rec in records:
        d = rec.to_row()
        ws.append(
            [
                d.get("case_id", ""),
                d.get("group", ""),
                d.get("title", ""),
                d.get("priority", ""),
                d.get("step_no", ""),
                d.get("user_question", ""),
                _trunc(d.get("assert_hints", ""), 800),
                d.get("expect_tools", ""),
                d.get("notes", ""),
                d.get("tool_name", ""),
                d.get("role", ""),
                d.get("metric_codes", ""),
                d.get("assert_expr", ""),
                _trunc(d.get("request_body", ""), 4000),
                d.get("result", ""),
                d.get("http_status", ""),
                d.get("elapsed_ms", ""),
                _trunc(d.get("response_summary", ""), 1500),
                _trunc(d.get("response_raw", ""), 5000),
                _trunc(d.get("error_message", ""), 2000),
            ]
        )
    _style_header(ws)
    _autosize(ws, 36)
    ws.column_dimensions["N"].width = 48  # request_body
    ws.column_dimensions["R"].width = 40
    ws.column_dimensions["S"].width = 40
    # 结果列着色
    green = PatternFill("solid", fgColor="C8E6C9")
    red = PatternFill("solid", fgColor="FFCDD2")
    yellow = PatternFill("solid", fgColor="FFF9C4")
    result_col = DETAIL_HEADERS.index("result") + 1
    for r in range(2, ws.max_row + 1):
        cell = ws.cell(r, result_col)
        val = str(cell.value or "").lower()
        if val == "passed":
            cell.fill = green
        elif val in {"failed", "error"}:
            cell.fill = red
        elif val == "skipped":
            cell.fill = yellow

    # —— 汇总统计 ——
    ws2 = wb.create_sheet("汇总统计")
    total = len(records)
    by_result = Counter(str(r.result or "unknown") for r in records)
    passed = by_result.get("passed", 0)
    failed = by_result.get("failed", 0) + by_result.get("error", 0)
    skipped = by_result.get("skipped", 0)
    rate = f"{(passed / total * 100):.1f}%" if total else "N/A"

    elapsed_vals = []
    for r in records:
        try:
            elapsed_vals.append(float(r.elapsed_ms))
        except (TypeError, ValueError):
            pass
    avg_ms = round(sum(elapsed_vals) / len(elapsed_vals), 1) if elapsed_vals else ""
    max_ms = round(max(elapsed_vals), 1) if elapsed_vals else ""

    ws2.append(["项", "值"])
    summary_rows = [
        ("导出时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("执行总数", total),
        ("通过 passed", passed),
        ("失败 failed/error", failed),
        ("跳过 skipped", skipped),
        ("通过率", rate),
        ("平均耗时(ms)", avg_ms),
        ("最大耗时(ms)", max_ms),
    ]
    for row in summary_rows:
        ws2.append(list(row))

    ws2.append([])
    ws2.append(["按优先级", "总数", "通过", "失败", "跳过"])
    by_prio: dict[str, Counter] = {}
    for r in records:
        p = str(r.priority or "未标")
        by_prio.setdefault(p, Counter())[str(r.result or "unknown")] += 1
    for p, c in sorted(by_prio.items()):
        ws2.append(
            [
                p,
                sum(c.values()),
                c.get("passed", 0),
                c.get("failed", 0) + c.get("error", 0),
                c.get("skipped", 0),
            ]
        )

    ws2.append([])
    ws2.append(["按工具", "总数", "通过", "失败", "跳过"])
    by_tool: dict[str, Counter] = {}
    for r in records:
        t = str(r.tool_name or "未知")
        by_tool.setdefault(t, Counter())[str(r.result or "unknown")] += 1
    for t, c in sorted(by_tool.items(), key=lambda x: -sum(x[1].values())):
        ws2.append(
            [
                t,
                sum(c.values()),
                c.get("passed", 0),
                c.get("failed", 0) + c.get("error", 0),
                c.get("skipped", 0),
            ]
        )

    ws2.append([])
    ws2.append(["按分组", "总数", "通过", "失败", "跳过"])
    by_group: dict[str, Counter] = {}
    for r in records:
        g = str(r.group or "未分组")[:40]
        by_group.setdefault(g, Counter())[str(r.result or "unknown")] += 1
    for g, c in sorted(by_group.items(), key=lambda x: -sum(x[1].values())):
        ws2.append(
            [
                g,
                sum(c.values()),
                c.get("passed", 0),
                c.get("failed", 0) + c.get("error", 0),
                c.get("skipped", 0),
            ]
        )

    _style_header(ws2, "00695C")
    _autosize(ws2, 28)

    wb.save(out)
    return out
