#!/usr/bin/env python3
"""本地结果门户 + 上传原始 Excel 转自动化用例。

启动：
  python3 server/app.py
  # 或 ./scripts/serve_reports.sh
默认 http://0.0.0.0:8767（本机 + 内网）
"""

from __future__ import annotations

import os
import re
import sys
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from flask import Flask, jsonify, redirect, request, send_from_directory

from common.case_convert import convert_uploaded_excel
from gen_results_portal import build_portal  # noqa: E402

REPORTS = ROOT / "reports"
UPLOADS = ROOT / "data" / "uploads"
DATA = ROOT / "data"

app = Flask(__name__, static_folder=None)


def _ensure_portal() -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "runs").mkdir(parents=True, exist_ok=True)
    build_portal(REPORTS, title="MCP 自动化测试")
    upload_page = REPORTS / "upload.html"
    upload_page.write_text(_UPLOAD_HTML, encoding="utf-8")


_UPLOAD_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>上传测试用例集</title>
<style>
  body { font-family: "PingFang SC", "SF Pro Text", sans-serif; background:#0f1419; color:#e7ecf3;
    max-width:720px; margin:40px auto; padding:0 16px; }
  a { color:#3d9cf0; }
  .card { background:#1a2332; border:1px solid #2d3a4d; border-radius:14px; padding:20px; }
  h1 { font-size:22px; margin:0 0 8px; }
  p { color:#8b9bb4; line-height:1.5; }
  .note { font-size:12px; color:#8b9bb4; margin-top:10px; }
  input[type=file] { margin:12px 0; color:#e7ecf3; }
  button { background:#3d9cf0; color:#041018; border:0; border-radius:10px; padding:10px 16px;
    font-weight:700; cursor:pointer; }
  button:disabled { opacity:.5; cursor:not-allowed; }
  #msg { margin-top:14px; white-space:pre-wrap; font-size:13px; }
  .ok { color:#3ecf8e; } .err { color:#f07178; }
</style>
</head>
<body>
  <p><a href="/index.html">← 返回执行历史</a></p>
  <div class="card">
    <h1>上传测试用例集</h1>
    <p>上传原始「MCP专项」xlsx。这里<strong>只做转换</strong>，不会立刻跑测，也不会新增执行历史行。</p>
    <p class="note">转换后设为当前用例集；请回终端执行 <code>./scripts/run_api.sh</code>，执行历史列表才会多一条结果。</p>
    <form id="f">
      <input type="file" id="file" accept=".xlsx,.xlsm" required />
      <div><button type="submit" id="btn">开始转换</button></div>
    </form>
    <div id="msg"></div>
  </div>
<script>
const msg = document.getElementById('msg');
const btn = document.getElementById('btn');
document.getElementById('f').addEventListener('submit', async (ev) => {
  ev.preventDefault();
  const file = document.getElementById('file').files[0];
  if (!file) return;
  btn.disabled = true;
  msg.className = '';
  msg.textContent = '上传并转换中…';
  const fd = new FormData();
  fd.append('file', file);
  try {
    const r = await fetch('/api/convert', { method: 'POST', body: fd });
    const data = await r.json();
    if (!r.ok || !data.ok) throw new Error(data.error || ('HTTP ' + r.status));
    msg.className = 'ok';
    msg.textContent = '转换成功\\n'
      + 'cases=' + (data.stats.cases||0)
      + ' steps=' + (data.stats.step_rows||0)
      + ' api=' + (data.stats.api_rows||0)
      + ' auto=' + (data.stats.auto||0)
      + ' skip=' + (data.stats.skip||0)
      + '\\n\\n下载: ' + data.download_url
      + '\\n已设为当前用例: ' + data.latest
      + '\\n\\n可返回结果页，或终端执行 ./scripts/run_api.sh';
  } catch (e) {
    msg.className = 'err';
    msg.textContent = '失败: ' + e.message;
  } finally {
    btn.disabled = false;
  }
});
</script>
</body>
</html>
"""


@app.get("/")
def root():
    _ensure_portal()
    return redirect("/index.html")


@app.get("/upload.html")
def upload_page():
    _ensure_portal()
    return send_from_directory(REPORTS, "upload.html")


@app.get("/index.html")
def index_page():
    _ensure_portal()
    return send_from_directory(REPORTS, "index.html")


@app.get("/allure-report/")
@app.get("/allure-report")
def allure_root():
    """带尾斜杠打开，保证相对路径 data/*.json 解析正确。"""
    return redirect("/allure-report/index.html")


@app.route("/<path:path>")
def static_reports(path: str):
    """托管 reports/ 下静态文件（含 Allure 的 data/*.json）。"""
    # 规范化，禁止 .. 穿越
    safe = Path(path)
    if ".." in safe.parts:
        return "Not Found", 404

    target = (REPORTS / safe).resolve()
    reports_root = REPORTS.resolve()
    if not str(target).startswith(str(reports_root)):
        return "Not Found", 404

    if target.is_dir():
        index = target / "index.html"
        if index.exists():
            rel = index.relative_to(reports_root).as_posix()
            return send_from_directory(reports_root, rel)
        return "Not Found", 404

    if target.exists() and target.is_file():
        # 关键：相对 reports 根目录发送，支持多层 allure-report/data/test-cases/xx.json
        rel = target.relative_to(reports_root).as_posix()
        return send_from_directory(reports_root, rel)

    # uploads / data 下载兜底
    up = (UPLOADS / safe).resolve()
    if str(up).startswith(str(UPLOADS.resolve())) and up.is_file():
        return send_from_directory(up.parent, up.name, as_attachment=True)
    data_file = (DATA / safe).resolve()
    if str(data_file).startswith(str(DATA.resolve())) and data_file.is_file():
        return send_from_directory(data_file.parent, data_file.name, as_attachment=True)
    return "Not Found", 404


@app.post("/api/convert")
def api_convert():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"ok": False, "error": "未选择文件"}), 400
    name = Path(f.filename).name
    if not re.search(r"\.xlsx?$", name, re.I) and not name.lower().endswith(".xlsm"):
        return jsonify({"ok": False, "error": "仅支持 .xlsx / .xlsm"}), 400

    # 大小限制 20MB
    f.stream.seek(0, os.SEEK_END)
    size = f.stream.tell()
    f.stream.seek(0)
    if size > 20 * 1024 * 1024:
        return jsonify({"ok": False, "error": "文件超过 20MB"}), 400

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = re.sub(r"[^\w.\u4e00-\u9fff-]+", "_", name)
    batch = UPLOADS / stamp
    batch.mkdir(parents=True, exist_ok=True)
    src_path = batch / f"原始_{safe}"
    f.save(src_path)

    try:
        result = convert_uploaded_excel(src_path, batch)
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()[-1500:]}), 400

    # 下载走 /downloads/...
    rel = f"{stamp}/自动化步骤用例.xlsx"
    return jsonify(
        {
            "ok": True,
            "stats": result["stats"],
            "latest": result["latest"],
            "converted": result["converted"],
            "download_url": f"/downloads/{rel}",
            "latest_download_url": "/data/MCP自动化步骤用例_latest.xlsx",
        }
    )


@app.get("/downloads/<path:subpath>")
def downloads(subpath: str):
    target = (UPLOADS / subpath).resolve()
    if not str(target).startswith(str(UPLOADS.resolve())) or not target.exists():
        return "Not Found", 404
    return send_from_directory(target.parent, target.name, as_attachment=True)


@app.get("/data/<path:subpath>")
def data_files(subpath: str):
    target = (DATA / subpath).resolve()
    if not str(target).startswith(str(DATA.resolve())) or not target.exists():
        return "Not Found", 404
    return send_from_directory(target.parent, target.name, as_attachment=True)


def _lan_ips() -> list[str]:
    import socket

    ips: list[str] = []
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if ip and not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except OSError:
        pass
    return ips


def main() -> None:
    port = int(os.getenv("REPORT_PORT", "8767"))
    host = os.getenv("REPORT_HOST", "0.0.0.0")
    UPLOADS.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)
    _ensure_portal()
    print(f"监听: {host}:{port}")
    print(f"本机: http://127.0.0.1:{port}/")
    for ip in _lan_ips():
        print(f"内网: http://{ip}:{port}/")
    print(f"上传: http://127.0.0.1:{port}/upload.html")
    app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
