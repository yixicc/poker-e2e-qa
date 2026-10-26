#!/usr/bin/env python3
"""跨平台跑 API 用例 → Allure → 归档 → 刷新门户。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts._portal_util import project_python  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    os.chdir(ROOT)
    args = list(argv if argv is not None else sys.argv[1:])
    (ROOT / "reports" / "allure-results").mkdir(parents=True, exist_ok=True)
    (ROOT / "reports" / "runs").mkdir(parents=True, exist_ok=True)

    mark = "api"
    if args and args[0] == "smoke":
        mark = "api and smoke"
        args = args[1:]

    py = project_python()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    env["MCP_RUN_SUITE"] = "api"

    cases = subprocess.check_output(
        [py, "-c", "from config.settings import settings; print(settings.cases_xlsx)"],
        cwd=str(ROOT),
        env=env,
        text=True,
    ).strip()
    print(f"用例表: {cases}")
    print("（命令行使用 .env 的 MCP_CASES_XLSX，不必先上传）")
    if not Path(cases).is_file():
        print("找不到用例表。请把 MCP_CASES_XLSX 指到已有的自动化 Excel。")
        return 1

    html = ROOT / "reports" / "report.html"
    cmd = [
        py,
        "-m",
        "pytest",
        "-m",
        mark,
        "--alluredir=reports/allure-results",
        "--clean-alluredir",
        f"--html={html}",
        "--self-contained-html",
        *args,
    ]
    py_exit = subprocess.call(cmd, cwd=str(ROOT), env=env)

    subprocess.call([py, str(ROOT / "scripts" / "gen_allure.py")], cwd=str(ROOT), env=env)

    enrich = """
from pathlib import Path
import sys
sys.path.insert(0, str(Path('.').resolve()))
from common.run_archive import enrich_latest_run
from scripts.gen_results_portal import build_portal
meta = enrich_latest_run(
    Path('reports'),
    html_report=Path('reports/report.html'),
    allure_report_dir=Path('reports/allure-report'),
    suite='api',
)
print('enrich', meta.get('run_id') if meta else None)
build_portal(Path('reports'), title='MCP 自动化测试')
print('portal ok')
"""
    subprocess.call([py, "-c", enrich], cwd=str(ROOT), env=env)

    env["REPORT_OPEN"] = "0"
    subprocess.call([py, str(ROOT / "scripts" / "serve_reports.py")], cwd=str(ROOT), env=env)
    port = env.get("REPORT_PORT", "8767")
    print(f"看结果: http://127.0.0.1:{port}/ （展示服务请用 scripts/serve_reports.bat 或 ./scripts/serve_reports.sh 常开）")
    return py_exit


if __name__ == "__main__":
    raise SystemExit(main())
