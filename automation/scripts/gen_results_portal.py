#!/usr/bin/env python3
"""生成测试结果门户页 reports/index.html，汇总下载 Excel / 打开报告链接。"""

from __future__ import annotations

import argparse
import html
from datetime import datetime
from pathlib import Path


def _rel(from_dir: Path, target: Path | None) -> str | None:
    if target is None or not target.exists():
        return None
    try:
        return target.resolve().relative_to(from_dir.resolve()).as_posix()
    except ValueError:
        return target.resolve().as_uri()


def _file_uri(path: Path) -> str:
    return path.resolve().as_uri()


def build_portal(
    reports_dir: Path,
    *,
    html_report: Path | None = None,
    allure_report: Path | None = None,
    excel_latest: Path | None = None,
    excel_stamped: Path | None = None,
    title: str = "MCP 自动化测试结果",
) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    out = reports_dir / "index.html"

    html_report = html_report or (reports_dir / "report.html")
    allure_report = allure_report or (reports_dir / "allure-report" / "index.html")
    excel_latest = excel_latest or (reports_dir / "MCP执行结果_latest.xlsx")

    if excel_stamped is None:
        stamped = sorted(reports_dir.glob("MCP执行结果_20*.xlsx"), reverse=True)
        excel_stamped = stamped[0] if stamped else None

    def card(name: str, desc: str, path: Path | None, *, download: bool = False) -> str:
        ok = path is not None and path.exists()
        if not ok:
            return f"""
            <div class="card muted">
              <h3>{html.escape(name)}</h3>
              <p>{html.escape(desc)}</p>
              <p class="badge bad">未生成</p>
            </div>"""
        # Allure 必须走站点相对路径 /allure-report/（由 HTTP 服务托管），禁止 file://
        if path and "allure-report" in path.parts and path.name == "index.html":
            href = "/allure-report/"
        else:
            href = _rel(reports_dir, path) or _file_uri(path)
        attrs = ' download' if download else ' target="_blank" rel="noopener"'
        btn = "下载" if download else "打开查看"
        size = path.stat().st_size
        size_s = f"{size/1024:.1f} KB" if size < 1024 * 1024 else f"{size/1024/1024:.2f} MB"
        mtime = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        return f"""
            <div class="card">
              <h3>{html.escape(name)}</h3>
              <p>{html.escape(desc)}</p>
              <p class="meta">{html.escape(path.name)} · {size_s} · {mtime}</p>
              <p class="badge ok">已就绪</p>
              <a class="btn" href="{html.escape(href)}"{attrs}>{btn}</a>
            </div>"""

    allure_dir = reports_dir / "allure-report"
    allure_ok = allure_report.exists() if allure_report else False
    allure_hint = ""
    if not allure_ok:
        allure_hint = (
            '<p class="hint">未检测到 Allure HTML。请先 <code>brew install allure</code>，'
            "再跑 <code>./scripts/run_api.sh</code>；或手动 "
            "<code>./scripts/gen_allure.sh</code>。</p>"
        )
    else:
        allure_hint = (
            '<p class="hint">查看 Allure 请点上方按钮（地址形如 '
            "<code>http://127.0.0.1:8767/allure-report/</code>）。"
            "若用 <code>file://</code> 直接打开本地 html，点用例详情会 <b>500 Failed to fetch</b>，这是浏览器限制。</p>"
        )

    body = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{html.escape(title)}</title>
<style>
  :root {{
    --bg: #0f1419;
    --panel: #1a2332;
    --line: #2d3a4d;
    --text: #e7ecf3;
    --muted: #8b9bb4;
    --accent: #3d9cf0;
    --ok: #3ecf8e;
    --bad: #f07178;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; font-family: "SF Pro Text", "PingFang SC", "Segoe UI", sans-serif;
    background: radial-gradient(1200px 600px at 10% -10%, #1b2a40, var(--bg));
    color: var(--text); min-height: 100vh; padding: 32px 20px 48px;
  }}
  .wrap {{ max-width: 960px; margin: 0 auto; }}
  h1 {{ font-size: 28px; margin: 0 0 8px; letter-spacing: -0.02em; }}
  .sub {{ color: var(--muted); margin: 0 0 28px; font-size: 14px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; }}
  .card {{
    background: var(--panel); border: 1px solid var(--line); border-radius: 14px;
    padding: 18px 18px 16px; display: flex; flex-direction: column; gap: 8px;
  }}
  .card.muted {{ opacity: 0.72; }}
  .card h3 {{ margin: 0; font-size: 17px; }}
  .card p {{ margin: 0; color: var(--muted); font-size: 13px; line-height: 1.5; }}
  .meta {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px !important; }}
  .badge {{
    display: inline-block; width: fit-content; font-size: 12px; font-weight: 700;
    padding: 2px 8px; border-radius: 999px;
  }}
  .badge.ok {{ background: rgba(62,207,142,.15); color: var(--ok); }}
  .badge.bad {{ background: rgba(240,113,120,.15); color: var(--bad); }}
  .btn {{
    margin-top: 8px; display: inline-block; text-align: center; text-decoration: none;
    background: var(--accent); color: #041018; font-weight: 700; font-size: 14px;
    padding: 10px 14px; border-radius: 10px;
  }}
  .btn:hover {{ filter: brightness(1.08); }}
  .hint {{
    margin-top: 22px; padding: 12px 14px; border-radius: 10px;
    background: rgba(61,156,240,.08); border: 1px solid rgba(61,156,240,.25);
    color: var(--muted); font-size: 13px; line-height: 1.55;
  }}
  code {{ color: #c3e0ff; font-size: 12px; }}
  footer {{ margin-top: 28px; color: var(--muted); font-size: 12px; }}
</style>
</head>
<body>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <p class="sub">生成时间 {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} · 点击下方按钮下载 Excel 或查看报告</p>
    <div class="grid">
      {card("Excel 执行结果", "明细 + 汇总统计，可下载后用 Excel / Numbers 打开", excel_latest, download=True)}
      {card("Excel（带时间戳）", "本次运行归档副本", excel_stamped, download=True)}
      {card("Pytest HTML 报告", "用例通过/失败列表与日志", html_report)}
      {card("Allure 报告", "步骤、附件、趋势更完整的可视化报告", allure_report if allure_ok else None)}
    </div>
    {allure_hint}
    <footer>
      由 automation/scripts/gen_results_portal.py 自动生成。
      请通过 <code>http://127.0.0.1:8767/</code> 打开（不要用 file://，否则 Allure 会 Failed to fetch）。
      关闭自动打开：REPORT_OPEN=0
    </footer>
  </div>
</body>
</html>
"""
    out.write_text(body, encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reports-dir", type=Path, default=Path("reports"))
    ap.add_argument("--html", type=Path, default=None)
    ap.add_argument("--allure", type=Path, default=None)
    ap.add_argument("--excel-latest", type=Path, default=None)
    ap.add_argument("--title", default="MCP 自动化测试结果")
    args = ap.parse_args()
    path = build_portal(
        args.reports_dir,
        html_report=args.html,
        allure_report=args.allure,
        excel_latest=args.excel_latest,
        title=args.title,
    )
    print(path.resolve())


if __name__ == "__main__":
    main()
