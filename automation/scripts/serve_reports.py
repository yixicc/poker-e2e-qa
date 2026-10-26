#!/usr/bin/env python3
"""跨平台启动结果展示服务（macOS / Windows / Linux）。"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts._portal_util import (  # noqa: E402
    kill_pid,
    lan_ipv4,
    open_url,
    port_listening,
    project_python,
    read_pid_file,
)
from scripts.start_portal_process import main as start_main  # noqa: E402


def _refresh_portal() -> None:
    from scripts.gen_results_portal import build_portal

    build_portal(ROOT / "reports", title="MCP 自动化测试")


def main() -> int:
    os.chdir(ROOT)
    port = int(os.environ.get("REPORT_PORT", "8767"))
    host = os.environ.get("REPORT_HOST", "0.0.0.0")
    pid_file = ROOT / "reports" / ".report-server.pid"
    log_file = ROOT / "reports" / ".report-server.log"
    (ROOT / "reports" / "runs").mkdir(parents=True, exist_ok=True)
    (ROOT / "data" / "uploads").mkdir(parents=True, exist_ok=True)

    py = project_python()
    try:
        import flask  # noqa: F401
        import openpyxl  # noqa: F401
    except ImportError:
        print("正在安装 flask / openpyxl…")
        os.system(f'"{py}" -m pip install -q flask openpyxl')

    force = os.environ.get("REPORT_FORCE_RESTART", "0") == "1"
    if port_listening(port) and not force:
        print(f"展示服务已在运行（端口 {port}），不重启。")
        try:
            _refresh_portal()
        except Exception as exc:  # noqa: BLE001
            print("刷新门户失败:", exc)
        lan = lan_ipv4()
        print(f"监听:     {host}:{port}")
        print(f"本机:     http://127.0.0.1:{port}/")
        if lan:
            print(f"内网:     http://{lan}:{port}/")
        print(f"上传:     http://127.0.0.1:{port}/upload.html")
        print(f"Allure:   http://127.0.0.1:{port}/allure-report/")
        if os.environ.get("REPORT_OPEN", "0") == "1":
            open_url(f"http://127.0.0.1:{port}/")
        return 0

    if force or port_listening(port):
        old = read_pid_file(pid_file)
        if old:
            kill_pid(old)
        for _ in range(15):
            if not port_listening(port):
                break
            time.sleep(0.2)
        if port_listening(port):
            print(f"端口 :{port} 仍被占用，请先 scripts/stop_portal.bat 或 stop_portal.sh")
            return 1

    os.environ["REPORT_PORT"] = str(port)
    os.environ["REPORT_HOST"] = host
    try:
        _refresh_portal()
    except Exception as exc:  # noqa: BLE001
        print("刷新门户失败:", exc)

    code = start_main()
    if code != 0:
        print("服务启动失败，日志：")
        if log_file.exists():
            print(log_file.read_text(encoding="utf-8", errors="replace")[-2000:])
        return code

    print("展示服务已启动（与 pytest 无关，可一直开着）")
    lan = lan_ipv4()
    print(f"监听:     {host}:{port}")
    print(f"本机:     http://127.0.0.1:{port}/")
    if lan:
        print(f"内网:     http://{lan}:{port}/")
    print(f"上传:     http://127.0.0.1:{port}/upload.html")
    print(f"Allure:   http://127.0.0.1:{port}/allure-report/")
    print(f"日志:     {log_file}")
    print("停止:     scripts\\stop_portal.bat  或  ./scripts/stop_portal.sh")
    if os.environ.get("REPORT_OPEN", "1") == "1":
        open_url(f"http://127.0.0.1:{port}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
