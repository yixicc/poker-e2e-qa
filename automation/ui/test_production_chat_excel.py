"""与 API 共用 cases 表：按顺序提问，保留模型回答原文，只按预期结果核对数据。"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

from common.excel_loader import CaseRow, load_ui_cases
from common.reporting import attach_png, attach_text, step
from common.result_store import STORE, ExecRecord
from config.settings import settings
from ui.pages.production_chat_page import (
    ProductionChatPage,
    missing_reply_data,
)

try:
    import allure
except ImportError:  # pragma: no cover
    allure = None


pytestmark = [pytest.mark.ui]


def _load_cases() -> list[CaseRow]:
    xlsx = settings.cases_xlsx
    if not xlsx.exists():
        return []
    only = None
    raw_ids = os.getenv("UI_CASE_IDS", "").strip()
    if raw_ids:
        only = {x.strip() for x in re.split(r"[,，\s]+", raw_ids) if x.strip()}
    pri = None
    if settings.ui_priorities:
        pri = {x.strip() for x in re.split(r"[,，\s]+", settings.ui_priorities) if x.strip()}
    limit = settings.ui_case_limit or None
    return load_ui_cases(xlsx, only_case_ids=only, priorities=pri, limit=limit)


CASES = _load_cases()


def _log(request, msg: str) -> None:
    """跑的时候立刻打到控制台（不等整条测完）。只打一处，避免重复。"""
    line = f"[UI] {msg}"
    reporter = request.config.pluginmanager.get_plugin("terminalreporter")
    if reporter is not None:
        reporter.write_line(line)
        return
    print(line, file=sys.stderr, flush=True)


def _flush_shots(chat: ProductionChatPage, out_dir: Path, prefix: str) -> None:
    """把关键步骤截图写入目录，并挂到当前 Allure 步骤。"""
    shots = list(chat.shots)
    chat.shots.clear()
    for name, png in shots:
        safe_name = re.sub(r"[^\w\-]+", "_", name)[:40]
        (out_dir / f"{prefix}_{safe_name}.png").write_bytes(png)
        attach_png(name, png)


@pytest.fixture(scope="module")
def production_chat(browser, request):
    if not settings.ui_enabled:
        pytest.skip("UI_ENABLED=0，请在 automation/.env 打开")
    if not settings.ui_open_id:
        pytest.skip("未配置 UI_OPEN_ID / MCP_OPEN_ID")
    _log(request, f"打开聊天页 {settings.ui_chat_url}")
    context = browser.new_context(
        viewport={"width": 390, "height": 844},
        locale="zh-CN",
    )
    page = context.new_page()
    chat = ProductionChatPage(page, settings.ui_chat_url, open_id=settings.ui_open_id)
    chat.open()
    _log(request, "聊天页已打开")
    yield chat
    context.close()


@pytest.mark.P0
def test_production_chat_excel_sequential(production_chat: ProductionChatPage, request):
    """同一会话内按 cases 表顺序提问（共用 API 用例表）。"""
    if not CASES:
        pytest.skip(f"无 UI 可用 cases，检查 Excel: {settings.cases_xlsx}")

    total = len(CASES)
    if allure is not None:
        allure.dynamic.title(f"UI production 顺序跑 cases（{total} 条）")
        allure.dynamic.severity(allure.severity_level.CRITICAL)

    failures: list[str] = []
    out_dir = settings.excel_report_dir / "ui_chat_turns"
    out_dir.mkdir(parents=True, exist_ok=True)

    _log(request, f"开始跑 UI，共 {total} 条 · 用例表 {settings.cases_xlsx.name}")
    with step("打开聊天页"):
        _flush_shots(production_chat, out_dir, "000")

    passed_n = 0
    for idx, case in enumerate(CASES, 1):
        title = (case.title or case.user_question or case.case_id).strip()
        short_q = (case.user_question or "").replace("\n", " ")[:40]
        _log(request, f"({idx}/{total}) 开始 {case.case_id} {title}")
        if short_q:
            _log(request, f"({idx}/{total}) 提问：{short_q}")

        nodeid = f"{request.node.nodeid}::{case.case_id}"
        STORE.start(
            nodeid,
            ExecRecord(
                case_id=case.case_id,
                group=case.group,
                title=case.title,
                priority=case.priority,
                step_no=idx,
                user_question=case.user_question,
                assert_hints=case.assert_hints,
                expect_tools=case.expect_tools,
                tool_name="ui/chat",
                role="ui",
                notes="production Flutter chat",
            ),
        )
        # Allure 步骤名用上传 Excel 的 title
        step_name = title
        with step(step_name):
            if allure is not None:
                allure.dynamic.story(case.case_id)
                allure.dynamic.parameter("case_id", case.case_id)
                allure.dynamic.parameter("title", step_name)
            safe = re.sub(r"[^\w\-]+", "_", case.case_id)[:80]
            try:
                turn = production_chat.send(case.user_question)
            finally:
                _flush_shots(production_chat, out_dir, f"{idx:03d}_{safe}")
            attach_text("question", case.user_question)
            attach_text("模型回答", turn.reply)
            attach_text("预期结果", case.assert_hints)
            if turn.stream_raw:
                attach_text("stream_head", turn.stream_raw[:2000])

            # 落盘：预期描述 + 模型回答原文（工具不参与判断）
            (out_dir / f"{idx:03d}_{safe}.txt").write_text(
                f"case_id={case.case_id}\n"
                f"title={case.title}\n"
                f"question={case.user_question}\n"
                f"elapsed_ms={turn.elapsed_ms}\n"
                f"error={turn.error}\n"
                f"--- 预期结果 ---\n{case.assert_hints}\n"
                f"--- 模型回答原文 ---\n{turn.reply}\n",
                encoding="utf-8",
            )

            STORE.update(
                nodeid,
                elapsed_ms=turn.elapsed_ms,
                model_reply=turn.reply,
                response_summary=turn.reply[:1500],
                response_raw=turn.reply,
            )

            err = turn.error
            missing = [] if err else missing_reply_data(turn.reply, case.assert_hints)
            if err or missing:
                if err:
                    msg = err
                else:
                    msg = "数据不符：预期要有「" + "、".join(missing) + "」，模型回答里没有。"
                STORE.finish(nodeid, "failed", msg)
                failures.append(f"{case.case_id}: {msg}")
                _log(
                    request,
                    f"({idx}/{total}) 失败 {case.case_id} · {turn.elapsed_ms}ms · {msg[:120]}",
                )
            else:
                STORE.finish(nodeid, "passed")
                passed_n += 1
                _log(
                    request,
                    f"({idx}/{total}) 通过 {case.case_id} · {turn.elapsed_ms}ms",
                )

    _log(
        request,
        f"结束：通过 {passed_n}/{total}，失败 {len(failures)}/{total}",
    )
    assert not failures, "UI cases 失败:\n" + "\n".join(failures[:30])
