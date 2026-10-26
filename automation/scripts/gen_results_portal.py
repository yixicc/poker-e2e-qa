#!/usr/bin/env python3
"""生成执行历史列表门户：右上角上传用例，主区为每次跑测结果列表。"""

from __future__ import annotations

import argparse
import html
import json
from datetime import datetime
from pathlib import Path

# 允许从 automation 根或 scripts 目录调用
import sys

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from common.run_archive import list_runs  # noqa: E402


def _migrate_legacy_excels(reports_dir: Path) -> None:
    """把旧的 MCP执行结果_时间戳.xlsx 补成 runs 记录（仅 meta，无 html/allure）。"""
    runs_root = reports_dir / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    for xlsx in sorted(reports_dir.glob("MCP执行结果_20*.xlsx")):
        # MCP执行结果_20261026_115055.xlsx
        stem = xlsx.stem.replace("MCP执行结果_", "", 1)
        run_dir = runs_root / stem
        meta_f = run_dir / "meta.json"
        if meta_f.exists():
            continue
        run_dir.mkdir(parents=True, exist_ok=True)
        dst = run_dir / "result.xlsx"
        if not dst.exists():
            dst.write_bytes(xlsx.read_bytes())
        meta = {
            "run_id": stem,
            "finished_at": f"{stem[0:4]}-{stem[4:6]}-{stem[6:8]} {stem[9:11]}:{stem[11:13]}:{stem[13:15]}"
            if len(stem) >= 15
            else stem,
            "cases_xlsx": "",
            "exitstatus": 0,
            "has_excel": True,
            "has_html": False,
            "has_allure": False,
            "total": "",
            "passed": "",
            "failed": "",
            "skipped": "",
            "pass_rate": "",
            "legacy": True,
        }
        meta_f.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def build_portal(
    reports_dir: Path,
    *,
    html_report: Path | None = None,  # 兼容旧签名
    allure_report: Path | None = None,
    excel_latest: Path | None = None,
    excel_stamped: Path | None = None,
    title: str = "MCP 自动化测试",
) -> Path:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    _migrate_legacy_excels(reports_dir)
    runs = list_runs(reports_dir)

    rows_html: list[str] = []
    for i, m in enumerate(runs):
        rid = html.escape(str(m.get("run_id", "")))
        when = html.escape(str(m.get("finished_at", rid)))
        total = m.get("total", "—")
        passed = m.get("passed", "—")
        failed = m.get("failed", "—")
        skipped = m.get("skipped", "—")
        rate = html.escape(str(m.get("pass_rate", "—")))
        cases = html.escape(Path(str(m.get("cases_xlsx") or "")).name or "（未记录）")
        legacy = " · 历史补录" if m.get("legacy") else ""

        links = []
        if m.get("has_excel"):
            links.append(f'<a href="/runs/{rid}/result.xlsx" download>Excel</a>')
        if m.get("has_html"):
            links.append(f'<a href="/runs/{rid}/report.html" target="_blank">HTML</a>')
        if m.get("has_allure"):
            links.append(f'<a href="/runs/{rid}/allure-report/" target="_blank">Allure</a>')
        # 兼容：最新一次也链到全局 allure
        if i == 0 and not m.get("has_allure"):
            if (reports_dir / "allure-report" / "index.html").exists():
                links.append('<a href="/allure-report/" target="_blank">Allure(最新)</a>')
        link_s = " · ".join(links) if links else "—"

        fail_n = failed if isinstance(failed, int) else 0
        status_cls = "ok" if fail_n == 0 and passed not in ("", "—", 0) else "bad"
        if passed in ("", "—") and failed in ("", "—"):
            status_cls = "muted"

        rows_html.append(
            f"""
            <tr>
              <td class="mono">{when}{html.escape(legacy)}</td>
              <td class="cases" title="{cases}">{cases}</td>
              <td><span class="pill {status_cls}">{passed} / {failed} / {skipped}</span></td>
              <td>{total}</td>
              <td>{rate}</td>
              <td class="actions">{link_s}</td>
            </tr>"""
        )

    empty = ""
    if not rows_html:
        empty = """
        <div class="empty">
          还没有执行记录。请先在右上角上传用例集，然后终端执行
          <code>./scripts/run_api.sh</code>
        </div>"""

    body = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{html.escape(title)}</title>
<style>
  :root {{
    --bg:#0f1419; --panel:#1a2332; --line:#2d3a4d; --text:#e7ecf3;
    --muted:#8b9bb4; --accent:#3d9cf0; --ok:#3ecf8e; --bad:#f07178;
  }}
  * {{ box-sizing:border-box; }}
  body {{
    margin:0; font-family:"SF Pro Text","PingFang SC","Segoe UI",sans-serif;
    background:radial-gradient(1200px 600px at 10% -10%, #1b2a40, var(--bg));
    color:var(--text); min-height:100vh;
  }}
  .top {{
    display:flex; align-items:center; justify-content:space-between; gap:16px;
    padding:18px 28px; border-bottom:1px solid var(--line);
    background:rgba(26,35,50,.9); backdrop-filter:blur(8px);
    position:sticky; top:0; z-index:10;
  }}
  .brand h1 {{ margin:0; font-size:20px; letter-spacing:-.02em; }}
  .brand p {{ margin:4px 0 0; color:var(--muted); font-size:12px; }}
  .btn {{
    display:inline-block; text-decoration:none; background:var(--accent); color:#041018;
    font-weight:700; font-size:14px; padding:10px 16px; border-radius:10px; white-space:nowrap;
  }}
  .btn:hover {{ filter:brightness(1.08); }}
  .btn.ghost {{ background:transparent; color:var(--accent); border:1px solid rgba(61,156,240,.45); }}
  .wrap {{ max-width:1100px; margin:0 auto; padding:24px 20px 48px; }}
  h2 {{ font-size:16px; margin:0 0 12px; color:var(--muted); font-weight:600; }}
  .hint {{
    margin:0 0 18px; padding:12px 14px; border-radius:10px;
    background:rgba(61,156,240,.08); border:1px solid rgba(61,156,240,.25);
    color:var(--muted); font-size:13px; line-height:1.55;
  }}
  table {{
    width:100%; border-collapse:collapse; background:var(--panel);
    border:1px solid var(--line); border-radius:14px; overflow:hidden;
  }}
  th, td {{ padding:12px 14px; text-align:left; font-size:13px; border-bottom:1px solid var(--line); }}
  th {{ color:var(--muted); font-weight:600; background:rgba(0,0,0,.2); }}
  tr:last-child td {{ border-bottom:0; }}
  tr:hover td {{ background:rgba(61,156,240,.06); }}
  .mono {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:12px; }}
  .cases {{ max-width:220px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:var(--muted); }}
  .actions a {{ color:var(--accent); margin-right:4px; }}
  .pill {{
    display:inline-block; padding:2px 8px; border-radius:999px; font-size:12px; font-weight:700;
  }}
  .pill.ok {{ background:rgba(62,207,142,.15); color:var(--ok); }}
  .pill.bad {{ background:rgba(240,113,120,.15); color:var(--bad); }}
  .pill.muted {{ background:rgba(139,155,180,.15); color:var(--muted); }}
  .empty {{
    padding:36px; text-align:center; color:var(--muted); border:1px dashed var(--line);
    border-radius:14px; background:var(--panel);
  }}
  code {{ color:#c3e0ff; font-size:12px; }}
  footer {{ margin-top:22px; color:var(--muted); font-size:12px; }}
</style>
</head>
<body>
  <header class="top">
    <div class="brand">
      <h1>{html.escape(title)}</h1>
      <p>执行历史可回溯 · 上传与结果查看分离 · {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>
    </div>
    <div style="display:flex;gap:10px;align-items:center">
      <a class="btn ghost" href="/allure-report/" target="_blank">最新 Allure</a>
      <a class="btn" href="/upload.html">上传测试用例集</a>
    </div>
  </header>

  <div class="wrap">
    <div class="hint">
      <b>上传用例集</b>：右上角按钮，把原始「MCP专项」xlsx 转成自动化表（不产生执行记录）。<br/>
      <b>执行结果</b>：下方列表，每跑一次 <code>./scripts/run_api.sh</code> 增加一行，可下载该次 Excel / 打开 HTML / Allure。
    </div>

    <h2>执行历史（共 {len(runs)} 次）</h2>
    {empty if empty else f'''
    <table>
      <thead>
        <tr>
          <th>完成时间</th>
          <th>用例集</th>
          <th>通过 / 失败 / 跳过</th>
          <th>总数</th>
          <th>通过率</th>
          <th>报告</th>
        </tr>
      </thead>
      <tbody>
        {''.join(rows_html)}
      </tbody>
    </table>
    '''}
    <footer>
      请通过 <code>http://127.0.0.1:8767/</code> 访问（不要用 file://）。Allure 详情也必须走 HTTP。
    </footer>
  </div>
</body>
</html>
"""
    out = reports_dir / "index.html"
    out.write_text(body, encoding="utf-8")

    # 保持 upload 页由 server 写入；此处写一个兜底
    upload = reports_dir / "upload.html"
    if not upload.exists():
        upload.write_text(
            "<!DOCTYPE html><meta charset=utf-8><title>upload</title>"
            "<p>请通过服务访问 <a href='/upload.html'>/upload.html</a></p>",
            encoding="utf-8",
        )
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reports-dir", type=Path, default=Path("reports"))
    ap.add_argument("--title", default="MCP 自动化测试")
    # 兼容旧参数，忽略
    ap.add_argument("--html", type=Path, default=None)
    ap.add_argument("--allure", type=Path, default=None)
    ap.add_argument("--excel-latest", type=Path, default=None)
    args = ap.parse_args()
    path = build_portal(args.reports_dir, title=args.title)
    print(path.resolve())


if __name__ == "__main__":
    main()
