"""automation 根 conftest：统一 sys.path + 导出 Excel + 归档执行历史。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.result_exporter import export_results_xlsx  # noqa: E402
from common.result_store import STORE  # noqa: E402
from common.run_archive import archive_run  # noqa: E402
from config.settings import settings  # noqa: E402


def pytest_configure(config):  # noqa: ARG001
    settings.allure_results_dir.mkdir(parents=True, exist_ok=True)
    settings.html_report_path.parent.mkdir(parents=True, exist_ok=True)
    settings.excel_report_dir.mkdir(parents=True, exist_ok=True)
    (settings.excel_report_dir / "runs").mkdir(parents=True, exist_ok=True)
    STORE.clear()


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    if rep.when != "call" and not (rep.when == "setup" and rep.skipped):
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


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001
    records = STORE.records()
    if not records:
        return
    out = settings.new_excel_report_path()
    try:
        path = export_results_xlsx(records, out)
        latest = settings.excel_report_dir / "MCP执行结果_latest.xlsx"
        export_results_xlsx(records, latest)

        html_report = settings.html_report_path
        # pytest-html 可能已写出
        meta = archive_run(
            reports_dir=settings.excel_report_dir,
            records=records,
            excel_path=path,
            html_report=html_report if html_report.exists() else None,
            allure_report_dir=None,  # Allure 在 shell 里生成后再 enrich
            cases_xlsx=str(settings.cases_xlsx),
            exitstatus=int(exitstatus),
            suite=os.getenv("MCP_RUN_SUITE", "").strip(),
        )
        session.config._mcp_excel_report = str(path)  # type: ignore[attr-defined]
        session.config._mcp_excel_latest = str(latest)  # type: ignore[attr-defined]
        session.config._mcp_run_id = meta.get("run_id", "")  # type: ignore[attr-defined]
        print(f"\nExcel 执行结果已导出: file://{path}")
        print(f"已归档执行记录: runs/{meta.get('run_id')}")
    except Exception as e:  # noqa: BLE001
        print(f"\n导出/归档失败: {e}")


def pytest_terminal_summary(terminalreporter, exitstatus, config):  # noqa: ARG001
    path = getattr(config, "_mcp_excel_report", None)
    rid = getattr(config, "_mcp_run_id", None)
    if path:
        terminalreporter.write_sep("=", "Excel / 执行归档")
        terminalreporter.write_line(f"file://{path}")
        if rid:
            terminalreporter.write_line(f"run_id={rid}")
