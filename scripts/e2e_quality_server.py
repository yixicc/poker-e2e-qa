#!/usr/bin/env python3
"""e2e-quality 本地站：静态页 + 上传 Excel（auto_json 列）或 jsonl。

  python3 scripts/e2e_quality_server.py
  打开 http://127.0.0.1:8767/
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from email import policy
from email.parser import BytesParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

ROOT = Path("/Users/xixi/Downloads/poker-gto-history-qa")
SITE_DIR = ROOT / "output" / "e2e-quality"
SCRIPTS = ROOT / "scripts"
MAX_UPLOAD = 80 * 1024 * 1024
ALLOWED = {".xlsx", ".xls", ".jsonl", ".json"}

sys.path.insert(0, str(SCRIPTS))
from build_shuzi_coverage_catalog import ingest_source, lookup_existing_batch  # noqa: E402


def parse_multipart(content_type: str, body: bytes) -> tuple[dict[str, str], dict[str, tuple[str, bytes]]]:
    head = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8")
    msg = BytesParser(policy=policy.default).parsebytes(head + body)
    fields: dict[str, str] = {}
    files: dict[str, tuple[str, bytes]] = {}
    parts = list(msg.iter_parts()) if msg.is_multipart() else [msg]
    for part in parts:
        name = part.get_param("name", header="content-disposition")
        if not name:
            continue
        filename = part.get_filename()
        payload = part.get_payload(decode=True) or b""
        if filename:
            files[str(name)] = (unquote(filename), payload)
        else:
            fields[str(name)] = payload.decode("utf-8", errors="replace")
    return fields, files


def make_handler(directory: Path):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(directory), **kwargs)

        def _cors(self) -> None:
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

        def _json(self, code: int, payload: dict) -> None:
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self._cors()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_OPTIONS(self) -> None:
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_POST(self) -> None:
            path = self.path.split("?", 1)[0]
            if path not in ("/api/upload", "/api/lookup"):
                self.send_error(404)
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = 0
            if length > MAX_UPLOAD:
                self._json(400, {"ok": False, "error": "文件太大或为空"})
                return
            body = self.rfile.read(length) if length else b""
            ctype = self.headers.get("Content-Type") or ""
            fields: dict[str, str] = {}
            files: dict[str, tuple[str, bytes]] = {}
            if "multipart/form-data" in ctype and body:
                try:
                    fields, files = parse_multipart(ctype, body)
                except Exception as e:
                    self._json(400, {"ok": False, "error": f"无法解析上传：{e}"})
                    return
            session_id = (fields.get("session_id") or "").strip()
            uploader = (fields.get("uploader") or "").strip()
            note = (fields.get("note") or fields.get("remark") or "").strip()
            if not session_id:
                self._json(400, {"ok": False, "error": "请填写本次对应的 fusion sessionId"})
                return
            try:
                if path == "/api/lookup":
                    batch = lookup_existing_batch(
                        fields.get("batch_id") or "",
                        session_id,
                        uploader,
                    )
                else:
                    item = files.get("file")
                    if not item:
                        self._json(400, {"ok": False, "error": "没有文件"})
                        return
                    filename, data = item
                    name = Path(filename).name
                    suffix = Path(name).suffix.lower()
                    if suffix not in ALLOWED:
                        self._json(400, {"ok": False, "error": "请上传 Excel（读取 auto_json 列）或 jsonl / json"})
                        return
                    if not data:
                        self._json(400, {"ok": False, "error": "空文件"})
                        return
                    uploads = SITE_DIR / "uploads"
                    uploads.mkdir(parents=True, exist_ok=True)
                    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    dest = uploads / f"{Path(name).stem}_{stamp}{suffix}"
                    dest.write_bytes(data)
                    batch = ingest_source(
                        dest,
                        uploader,
                        batch_id=Path(name).stem,
                        source_name=name,
                        session_id=session_id,
                        note=note,
                        fetch_fusion=False,
                    )
            except Exception as e:
                self._json(400, {"ok": False, "error": str(e)})
                return
            self._json(
                200,
                {
                    "ok": True,
                    "id": batch.get("id"),
                    "n": batch.get("n"),
                    "detail": batch.get("detail"),
                    "source_name": batch.get("source_name"),
                    "session_id": batch.get("session_id") or session_id,
                    "pair_rates": batch.get("pair_rates"),
                },
            )

        def log_message(self, fmt: str, *args) -> None:
            sys.stderr.write("%s - %s\n" % (self.log_date_time_string(), fmt % args))

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description="e2e-quality 本地上传服务")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8767)
    args = parser.parse_args()
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    httpd = ThreadingHTTPServer((args.host, args.port), make_handler(SITE_DIR))
    print(f"e2e-quality  http://{args.host}:{args.port}/")
    print("填 sessionId 后点「查询匹配率」，或上传 Excel/jsonl")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstop")


if __name__ == "__main__":
    main()
