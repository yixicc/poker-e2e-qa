"""读取 MCP 自动化 Excel（config / cases / requests）。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openpyxl import load_workbook


@dataclass
class CaseRow:
    case_id: str
    group: str
    title: str
    priority: str
    run_mode: str
    skip_reason: str
    expect_tools: str
    user_question: str
    assert_hints: str
    source_module: str
    remark: str


@dataclass
class RequestRow:
    case_id: str
    step_no: int
    enabled: str
    tool_name: str
    role: str
    method: str
    request_body: dict[str, Any]
    depends_on: str
    extract: str
    assert_type: str
    assert_expr: str
    notes: str
    # 关联 cases / 步骤表
    title: str = ""
    priority: str = ""
    group: str = ""
    user_question: str = ""
    assert_hints: str = ""
    metric_codes: str = ""
    expect_tools: str = ""


def _sheet_rows(ws) -> list[dict[str, Any]]:
    headers = [str(c.value).strip() if c.value is not None else f"col{i}" for i, c in enumerate(ws[1], 1)]
    out: list[dict[str, Any]] = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if all(v is None or str(v).strip() == "" for v in row):
            continue
        item = {headers[i]: row[i] if i < len(row) else None for i in range(len(headers))}
        out.append(item)
    return out


def load_config_sheet(xlsx: Path) -> dict[str, str]:
    wb = load_workbook(xlsx, data_only=True)
    if "config" not in wb.sheetnames:
        return {}
    cfg: dict[str, str] = {}
    for row in _sheet_rows(wb["config"]):
        key = str(row.get("key") or "").strip()
        if not key:
            continue
        cfg[key] = "" if row.get("value") is None else str(row.get("value")).strip()
    return cfg


def load_cases(xlsx: Path) -> dict[str, CaseRow]:
    wb = load_workbook(xlsx, data_only=True)
    cases: dict[str, CaseRow] = {}
    for row in _sheet_rows(wb["cases"]):
        cid = str(row.get("case_id") or "").strip()
        if not cid:
            continue
        cases[cid] = CaseRow(
            case_id=cid,
            group=str(row.get("group") or ""),
            title=str(row.get("title") or ""),
            priority=str(row.get("priority") or ""),
            run_mode=str(row.get("run_mode") or "").strip().lower(),
            skip_reason=str(row.get("skip_reason") or ""),
            expect_tools=str(row.get("expect_tools") or ""),
            user_question=str(
                row.get("user_question") or row.get("user_question_first") or ""
            ),
            assert_hints=str(row.get("assert_hints") or ""),
            source_module=str(row.get("source_module") or ""),
            remark=str(row.get("remark") or ""),
        )
    return cases


def _parse_body(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    text = str(raw or "").strip()
    if not text:
        raise ValueError("request_body 为空")
    return json.loads(text)


def load_enabled_requests(
    xlsx: Path,
    *,
    include_alt: bool = False,
    only_case_ids: set[str] | None = None,
) -> list[RequestRow]:
    cases = load_cases(xlsx)
    wb = load_workbook(xlsx, data_only=True)
    rows: list[RequestRow] = []
    for row in _sheet_rows(wb["requests"]):
        cid = str(row.get("case_id") or "").strip()
        if not cid:
            continue
        if only_case_ids is not None and cid not in only_case_ids:
            continue
        case = cases.get(cid)
        if case and case.run_mode != "auto":
            continue
        enabled = str(row.get("enabled") or "Y").strip().upper()
        role = str(row.get("role") or "preferred").strip().lower()
        if enabled != "Y":
            continue
        if role == "alt" and not include_alt:
            continue
        body = _parse_body(row.get("request_body"))
        step_no = int(row.get("step_no") or 1)
        title = str(row.get("title") or (case.title if case else "") or "")
        priority = str(row.get("priority") or (case.priority if case else "") or "")
        group = str(row.get("group") or (case.group if case else "") or "")
        uq = str(
            row.get("user_question")
            or row.get("user_input")
            or (case.user_question if case else "")
            or ""
        )
        hints = str(row.get("assert_hints") or (case.assert_hints if case else "") or "")
        rows.append(
            RequestRow(
                case_id=cid,
                step_no=step_no,
                enabled=enabled,
                tool_name=str(row.get("tool_name") or ""),
                role=role,
                method=str(row.get("method") or "tools/call"),
                request_body=body,
                depends_on=str(row.get("depends_on") or ""),
                extract=str(row.get("extract") or ""),
                assert_type=str(row.get("assert_type") or "contains"),
                assert_expr=str(row.get("assert_expr") or ""),
                notes=str(row.get("notes") or ""),
                title=title,
                priority=priority,
                group=group,
                user_question=uq,
                assert_hints=hints,
                metric_codes=str(row.get("metric_codes") or ""),
                expect_tools=str(
                    row.get("expect_tools") or (case.expect_tools if case else "") or ""
                ),
            )
        )
    rows.sort(key=lambda r: (r.case_id, r.step_no))
    return rows
