"""跨平台：找 Python、检测/占用端口、打开浏览器。"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def project_python() -> str:
    if os.name == "nt":
        candidates = [
            ROOT / ".venv" / "Scripts" / "python.exe",
            ROOT / ".venv" / "Scripts" / "python",
        ]
    else:
        candidates = [
            ROOT / ".venv" / "bin" / "python3",
            ROOT / ".venv" / "bin" / "python",
        ]
    for cand in candidates:
        if cand.is_file():
            return str(cand)
    return sys.executable


def port_listening(port: int, host: str = "127.0.0.1") -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.4):
            return True
    except OSError:
        return False


def lan_ipv4() -> str:
    """尽量拿到一张非回环网卡 IP；失败返回空串。"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            if ip and not ip.startswith("127."):
                return ip
    except OSError:
        pass
    return ""


def open_url(url: str) -> None:
    try:
        webbrowser.open(url)
    except Exception:  # noqa: BLE001
        pass


def kill_pid(pid: int) -> None:
    if pid <= 0:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F", "/T"],
                check=False,
                capture_output=True,
            )
        else:
            os.kill(pid, 15)
    except OSError:
        pass


def read_pid_file(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        raw = path.read_text(encoding="utf-8").strip()
        return int(raw) if raw else None
    except (OSError, ValueError):
        return None
