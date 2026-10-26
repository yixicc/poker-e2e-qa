"""每次跑测归档到 reports/runs/{run_id}/，供门户历史列表回溯。"""

from __future__ import annotations

import json
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from common.result_store import ExecRecord


def new_run_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def summarize(records: list[ExecRecord]) -> dict[str, Any]:
    c = Counter(str(r.result or "unknown") for r in records)
    total = len(records)
    passed = c.get("passed", 0)
    failed = c.get("failed", 0) + c.get("error", 0)
    skipped = c.get("skipped", 0)
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "pass_rate": f"{(passed / total * 100):.1f}%" if total else "N/A",
    }


def archive_run(
    *,
    reports_dir: Path,
    records: list[ExecRecord],
    excel_path: Path,
    html_report: Path | None = None,
    allure_report_dir: Path | None = None,
    cases_xlsx: str = "",
    exitstatus: int = 0,
    run_id: str | None = None,
) -> dict[str, Any]:
    """写入 runs/{run_id}/meta.json + 结果文件副本。"""
    reports_dir = Path(reports_dir)
    rid = run_id or new_run_id()
    run_dir = reports_dir / "runs" / rid
    run_dir.mkdir(parents=True, exist_ok=True)

    stats = summarize(records)
    # Excel
    excel_dst = run_dir / "result.xlsx"
    if excel_path.exists():
        shutil.copy2(excel_path, excel_dst)

    # pytest-html
    html_dst = run_dir / "report.html"
    if html_report and html_report.exists():
        shutil.copy2(html_report, html_dst)

    # Allure（整目录复制，便于历史回看）
    allure_dst = run_dir / "allure-report"
    has_allure = False
    if allure_report_dir and (allure_report_dir / "index.html").exists():
        if allure_dst.exists():
            shutil.rmtree(allure_dst)
        shutil.copytree(allure_report_dir, allure_dst)
        has_allure = True

    meta = {
        "run_id": rid,
        "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "cases_xlsx": cases_xlsx,
        "exitstatus": exitstatus,
        "has_excel": excel_dst.exists(),
        "has_html": html_dst.exists(),
        "has_allure": has_allure,
        **stats,
    }
    (run_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # 最新指针
    (reports_dir / "runs" / "latest.txt").write_text(rid, encoding="utf-8")
    return meta


def list_runs(reports_dir: Path) -> list[dict[str, Any]]:
    runs_root = Path(reports_dir) / "runs"
    if not runs_root.exists():
        return []
    items: list[dict[str, Any]] = []
    for d in sorted(runs_root.iterdir(), reverse=True):
        if not d.is_dir():
            continue
        meta_f = d / "meta.json"
        if not meta_f.exists():
            continue
        try:
            meta = json.loads(meta_f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        meta.setdefault("run_id", d.name)
        items.append(meta)
    return items


def enrich_latest_run(
    reports_dir: Path,
    *,
    html_report: Path | None = None,
    allure_report_dir: Path | None = None,
) -> dict[str, Any] | None:
    """pytest 结束后由 shell 调用：把 HTML/Allure 补进最近一次 run 目录。"""
    reports_dir = Path(reports_dir)
    latest_f = reports_dir / "runs" / "latest.txt"
    if not latest_f.exists():
        return None
    rid = latest_f.read_text(encoding="utf-8").strip()
    run_dir = reports_dir / "runs" / rid
    meta_f = run_dir / "meta.json"
    if not meta_f.exists():
        return None
    meta = json.loads(meta_f.read_text(encoding="utf-8"))

    if html_report and html_report.exists():
        shutil.copy2(html_report, run_dir / "report.html")
        meta["has_html"] = True

    if allure_report_dir and (allure_report_dir / "index.html").exists():
        dst = run_dir / "allure-report"
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(allure_report_dir, dst)
        meta["has_allure"] = True

    meta_f.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta

