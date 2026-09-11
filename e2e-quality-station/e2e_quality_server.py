#!/usr/bin/env python3
"""e2e-quality 本地站：静态页 + 上传 Excel（auto_json 列）或 jsonl。

黄金集 GTO 走单独入口 /api/upload-gto，先转 auto_json 再 ingest；/api/upload 行为不变。

  python3 e2e_quality_server.py
  本机打开 http://127.0.0.1:8767/
  内网给同事：python3 e2e_quality_server.py --host 0.0.0.0
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
from datetime import datetime
from email import policy
from email.parser import BytesParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

STATION = Path(__file__).resolve().parent
sys.path.insert(0, str(STATION))
from station_paths import ROOT, SITE_DIR  # noqa: E402

MAX_UPLOAD = 80 * 1024 * 1024
ALLOWED = {".xlsx", ".xls", ".jsonl", ".json"}
import build_shuzi_coverage_catalog  # noqa: E402
import e2e_match  # noqa: E402
import e2e_quality_pages  # noqa: E402
import e2e_source  # noqa: E402
import gto_to_autojson  # noqa: E402
import shuzi_field_schema  # noqa: E402
from build_shuzi_coverage_catalog import ingest_source, lookup_existing_batch  # noqa: E402


def reload_site_code() -> None:
    """上传时重新加载页面模板，避免长驻进程一直用启动时的旧 HTML。"""
    import importlib

    importlib.reload(shuzi_field_schema)
    importlib.reload(e2e_source)
    importlib.reload(gto_to_autojson)
    importlib.reload(e2e_match)
    importlib.reload(e2e_quality_pages)
    importlib.reload(build_shuzi_coverage_catalog)
    global ingest_source, lookup_existing_batch
    ingest_source = build_shuzi_coverage_catalog.ingest_source
    lookup_existing_batch = build_shuzi_coverage_catalog.lookup_existing_batch


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

        def end_headers(self) -> None:
            path = (self.path or "").split("?", 1)[0]
            if path.endswith((".js", ".html")):
                self.send_header("Cache-Control", "no-store")
            super().end_headers()

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
            if path not in ("/api/upload", "/api/upload-gto", "/api/lookup"):
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
                reload_site_code()
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
                    if path == "/api/upload-gto":
                        if suffix not in {".jsonl", ".json"}:
                            self._json(400, {"ok": False, "error": "黄金集请上传 json / jsonl"})
                            return
                    elif suffix not in ALLOWED:
                        self._json(400, {"ok": False, "error": "请上传 Excel（读取 auto_json 列）或 jsonl / json"})
                        return
                    if not data:
                        self._json(400, {"ok": False, "error": "空文件"})
                        return
                    uploads = SITE_DIR / "uploads"
                    uploads.mkdir(parents=True, exist_ok=True)
                    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    dest_suffix = ".jsonl" if path == "/api/upload-gto" else suffix
                    dest = uploads / f"{Path(name).stem}_{stamp}{dest_suffix}"
                    extra = 1
                    while dest.exists() or (SITE_DIR / "batches" / dest.stem).exists():
                        extra += 1
                        dest = uploads / f"{Path(name).stem}_{stamp}_{extra}{dest_suffix}"
                    if path == "/api/upload-gto":
                        try:
                            converted = gto_to_autojson.convert_text(data.decode("utf-8"))
                        except gto_to_autojson.ConvertError as e:
                            self._json(400, {"ok": False, "error": str(e)})
                            return
                        dest.write_text(converted, encoding="utf-8")
                        note = (note + " · 黄金集GTO已转auto_json") if note else "黄金集GTO已转auto_json"
                    else:
                        dest.write_bytes(data)
                    batch = ingest_source(
                        dest,
                        uploader,
                        batch_id=dest.stem,
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


class ReuseHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


def lan_ips() -> list[str]:
    ips: list[str] = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith("127.") and ip not in ips:
            ips.append(ip)
    except Exception:
        pass
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET, socket.SOCK_STREAM):
            ip = info[4][0]
            if ip and not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except Exception:
        pass
    return ips


def main() -> None:
    parser = argparse.ArgumentParser(description="e2e-quality 本地/内网上传服务")
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="监听地址。内网给同事用请加 --host 0.0.0.0（默认 127.0.0.1 仅本机）",
    )
    parser.add_argument("--port", type=int, default=8767)
    args = parser.parse_args()
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    httpd = ReuseHTTPServer((args.host, args.port), make_handler(SITE_DIR))
    print(f"e2e-quality  http://127.0.0.1:{args.port}/")
    if args.host in ("0.0.0.0", "::"):
        lan = lan_ips()
        if lan:
            for ip in lan:
                print(f"内网入口  http://{ip}:{args.port}/")
        else:
            print(f"内网入口  http://<这台机器的局域网IP>:{args.port}/")
    else:
        print(f"绑定      http://{args.host}:{args.port}/")
    print("同事请用上面的内网地址打开；填 sessionId 后点「查询匹配率」，或上传 Excel/jsonl")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstop")


if __name__ == "__main__":
    main()
