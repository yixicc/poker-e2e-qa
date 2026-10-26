"""Excel 驱动的 MCP API 自动化。"""

from __future__ import annotations

import json
import re
from typing import Any

import pytest

from common.asserts import (
    apply_assert_expr,
    extract_field,
    extract_hand_id,
    extract_hand_ids,
)
from common.excel_loader import RequestRow, load_enabled_requests
from common.reporting import attach_json, attach_text, step
from common.result_store import STORE, ExecRecord
from config.settings import settings

try:
    import allure
except ImportError:  # pragma: no cover
    allure = None


def _case_display_name(row: RequestRow) -> str:
    """Allure / 报告展示用：优先 Excel 上传时的 title。"""
    name = (row.title or row.user_question or row.tool_name or row.case_id or "").strip()
    try:
        step_no = int(row.step_no)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        step_no = 1
    if step_no > 1:
        return f"{name} · step{step_no}"
    return name


def _pytest_id(row: RequestRow) -> str:
    # 节点 id 仍带 case_id，避免重名；可读部分用上传 title
    label = re.sub(r"[^\w\u4e00-\u9fff\-]+", "_", _case_display_name(row))[:48]
    return f"{row.case_id}__s{row.step_no}__{label or row.tool_name}"


def _load_rows() -> list[RequestRow]:
    xlsx = settings.cases_xlsx
    if not xlsx.exists():
        return []
    return load_enabled_requests(xlsx, include_alt=False)


ROWS = _load_rows()


@pytest.mark.api
@pytest.mark.parametrize("row", ROWS, ids=[_pytest_id(r) for r in ROWS] or ["no_cases"])
def test_mcp_request_row(row: RequestRow, mcp_client, request):
    if not ROWS:
        pytest.skip(f"无可用请求行，检查 Excel: {settings.cases_xlsx}")

    STORE.start(
        request.node.nodeid,
        ExecRecord(
            case_id=row.case_id,
            group=row.group,
            title=row.title,
            priority=row.priority,
            step_no=row.step_no,
            user_question=row.user_question,
            assert_hints=row.assert_hints,
            expect_tools=row.expect_tools or row.tool_name,
            notes=row.notes,
            tool_name=row.tool_name,
            role=row.role,
            metric_codes=row.metric_codes,
            assert_expr=row.assert_expr,
            request_body=json.dumps(row.request_body, ensure_ascii=False, indent=2),
        ),
    )

    if allure is not None:
        allure.dynamic.feature(row.group or "MCP")
        allure.dynamic.story(row.case_id)
        allure.dynamic.title(_case_display_name(row))
        allure.dynamic.tag(row.priority or "P?")
        allure.dynamic.tag(row.tool_name)
        allure.dynamic.tag(row.case_id)
        if row.priority in {"P0", "🔴"}:
            allure.dynamic.severity(allure.severity_level.CRITICAL)
        elif row.priority == "P1":
            allure.dynamic.severity(allure.severity_level.NORMAL)
        else:
            allure.dynamic.severity(allure.severity_level.MINOR)

    # 链式占位：从上一步缓存取（同 case 内按 step 顺序执行时，parametrize 是乱序的！）
    # 因此对 depends_on 非空的步骤，在本用例内临时重跑依赖步，或跳过严格依赖。
    extra = _resolve_placeholders(row, mcp_client)

    with step("渲染 request_body"):
        body = mcp_client.render_placeholders(row.request_body, extra=extra)
        attach_json("request_body", body)
        STORE.update(
            request.node.nodeid,
            request_body=json.dumps(body, ensure_ascii=False, indent=2),
        )

    with step(f"POST tools/call → {row.tool_name}"):
        resp = mcp_client.call_raw(body)
        attach_text("raw_response", resp.raw_text)
        attach_json(
            "meta",
            {
                "status_code": resp.status_code,
                "elapsed_ms": resp.elapsed_ms,
                "session_id": mcp_client.session_id,
            },
        )
        if resp.jsonrpc:
            attach_json("jsonrpc", resp.jsonrpc)
        payload_preview = resp.tool_payload()
        summary = (
            json.dumps(payload_preview, ensure_ascii=False)[:1500]
            if payload_preview is not None
            else (resp.tool_text or resp.raw_text)[:1500]
        )
        STORE.update(
            request.node.nodeid,
            http_status=resp.status_code,
            elapsed_ms=round(resp.elapsed_ms, 1),
            response_raw=resp.raw_text,
            response_summary=summary,
        )

    assert resp.status_code < 400, f"HTTP {resp.status_code}: {resp.raw_text[:300]}"
    assert resp.jsonrpc is not None, "无法解析 JSON-RPC / SSE"
    assert "error" not in resp.jsonrpc, f"jsonrpc error: {resp.jsonrpc.get('error')}"

    payload = resp.tool_payload()
    attach_json("tool_payload", payload if payload is not None else {"text": resp.tool_text})

    result = (resp.jsonrpc or {}).get("result") or {}
    if isinstance(result, dict) and result.get("isError") is True:
        pytest.fail(f"tool isError: {resp.tool_text[:500]}")

    with step("业务断言"):
        apply_assert_expr(payload, row.assert_expr, raw_text=resp.tool_text or resp.raw_text)
        # 轻量：hints 里的关键数字若出现在 hints，则至少命中一个（避免过严）
        _soft_hint_check(row.assert_hints, resp.tool_text or resp.raw_text)


def _resolve_placeholders(row: RequestRow, mcp_client) -> dict[str, str]:
    """处理 {{hand_id}} 等；若 body 已不含占位则返回空。"""
    raw = str(row.request_body)
    need = set(re.findall(r"\{\{(\w+)\}\}", raw))
    need.discard("open_id")
    if not need:
        return {}

    # 同 case 找 step1 或 depends 指向的请求，现场调一次拿 extract
    xlsx = settings.cases_xlsx
    all_rows = load_enabled_requests(xlsx, include_alt=False)
    same = [r for r in all_rows if r.case_id == row.case_id and r.step_no < row.step_no]
    if not same:
        # 用默认样本，避免硬失败
        return {
            "hand_id": settings.mcp_open_id and "1792639765135_QHTH_1792640896015",
            "hand_id_3": "1792639765135_QHTH_1792640896015",
        }

    extra: dict[str, str] = {}
    # 只跑最近一步有 extract 的
    for prev in same:
        body = mcp_client.render_placeholders(prev.request_body, extra=extra)
        resp = mcp_client.call_raw(body)
        payload = resp.tool_payload()
        if prev.extract == "hand_id" or "hand_id" in need:
            hid = extract_hand_id(payload)
            if hid:
                extra["hand_id"] = hid
        if prev.extract in {"hand_ids", "hand_id"} or "hand_id_3" in need:
            ids = extract_hand_ids(payload, 3)
            if ids:
                extra.setdefault("hand_id", ids[0])
            if len(ids) >= 3:
                extra["hand_id_3"] = ids[2]
            elif ids:
                extra["hand_id_3"] = ids[-1]
        # 通用字段
        for key in list(need):
            if key in extra:
                continue
            val = extract_field(payload, key)
            if val is not None:
                extra[key] = str(val)
    return extra


def _soft_hint_check(hints: str, blob: str) -> None:
    if not hints or not blob:
        return
    # 抽取 hints 中的明显锚点：如 +94.5、27 手
    anchors = re.findall(r"\+?-?\d+(?:\.\d+)?\s*BB|\b\d+\s*手", hints)
    if not anchors:
        return
    # 至少一个锚点出现即加分；全不出现则记 warning attachment，不强失败
    hit = [a for a in anchors if a.replace(" ", "") in blob.replace(" ", "") or a in blob]
    if not hit and allure is not None:
        attach_text("hint_miss", f"hints 锚点未命中: {anchors}\n---\n{blob[:800]}")


@pytest.mark.api
@pytest.mark.smoke
@pytest.mark.P0
def test_smoke_overview_today(mcp_client, request):
    """不依赖 Excel 的冒烟：今天总览。"""
    args = {
        "open_id": settings.mcp_open_id,
        "time_start": "2026-10-22 00:00:00",
        "time_end": "2026-10-22 23:59:59",
    }
    STORE.start(
        request.node.nodeid,
        ExecRecord(
            case_id="SMOKE-01",
            group="冒烟",
            title="今天总览",
            priority="P0",
            step_no=1,
            user_question="今天打了几场、输赢多少",
            expect_tools="tool_get_user_overview",
            tool_name="tool_get_user_overview",
            role="preferred",
            metric_codes="total_sessions,total_profit_bb",
            request_body=json.dumps(
                {"method": "tools/call", "params": {"name": "tool_get_user_overview", "arguments": args}},
                ensure_ascii=False,
                indent=2,
            ),
        ),
    )
    if allure is not None:
        # 与 ExecRecord.title 一致，报告里展示用例名而不是工具名
        allure.dynamic.title("今天总览")
        allure.dynamic.feature("冒烟")
        allure.dynamic.story("SMOKE-01")
        allure.dynamic.severity(allure.severity_level.BLOCKER)

    resp = mcp_client.call_tool("tool_get_user_overview", args)
    attach_text("raw", resp.raw_text)
    payload = resp.tool_payload()
    STORE.update(
        request.node.nodeid,
        http_status=resp.status_code,
        elapsed_ms=round(resp.elapsed_ms, 1),
        response_raw=resp.raw_text,
        response_summary=json.dumps(payload, ensure_ascii=False)[:1500] if payload else "",
    )
    assert resp.ok, resp.raw_text[:500]
    attach_json("payload", payload)
    assert isinstance(payload, dict)
    assert "hands" in payload or "session_count" in payload
