"""automation 根 conftest：统一 sys.path + 导出 Excel 结果。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.result_exporter import export_results_xlsx  # noqa: E402
from common.result_store import STORE  # noqa: E402
from config.settings import settings  # noqa: E402


def pytest_configure(config):  # noqa: ARG001
    settings.allure_results_dir.mkdir(parents=True, exist_ok=True)
    settings.html_report_path.parent.mkdir(parents=True, exist_ok=True)
    settings.excel_report_dir.mkdir(parents=True, exist_ok=True)
    STORE.clear()


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    if rep.when != "call" and not (rep.when == "setup" and rep.skipped):
        # setup 失败/跳过也要记；call 记最终结果
        if rep.when == "setup" and (rep.failed or rep.skipped):
            pass
        else:
            return

    nodeid = item.nodeid
    if rep.skipped:
        reason = ""
        if hasattr(rep, "longrepr") and rep.longrepr:
            reason = str(rep.longrepr)
        STORE.finish(nodeid, "skipped", reason)
    elif rep.failed:
        STORE.finish(nodeid, "failed" if rep.when == "call" else "error", str(rep.longrepr)[:2000])
    elif rep.passed and rep.when == "call":
        STORE.finish(nodeid, "passed")


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001
    records = STORE.records()
    if not records:
        return
    out = settings.new_excel_report_path()
    try:
        path = export_results_xlsx(records, out)
        # 再写一份固定名，方便找最新
        latest = settings.excel_report_dir / "MCP执行结果_latest.xlsx"
        export_results_xlsx(records, latest)
        session.config._mcp_excel_report = str(path)  # type: ignore[attr-defined]
        print(f"\nExcel 执行结果已导出: {path}")
        print(f"最新副本: {latest}")
    except Exception as e:  # noqa: BLE001
        print(f"\n导出 Excel 失败: {e}")


def pytest_terminal_summary(terminalreporter, exitstatus, config):  # noqa: ARG001
    path = getattr(config, "_mcp_excel_report", None)
    if path:
        terminalreporter.write_sep("=", "Excel 结果导出")
        terminalreporter.write_line(path)
