#!/usr/bin/env python3
"""以新会话拉起展示服务，避免被父 shell / Cursor 进程组连带杀掉。"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts._portal_util import port_listening, project_python  # noqa: E402

PID_FILE = ROOT / "reports" / ".report-server.pid"
LOG_FILE = ROOT / "reports" / ".report-server.log"
PORT = int(os.environ.get("REPORT_PORT", "8767"))


def main() -> int:
    ROOT.joinpath("reports").mkdir(parents=True, exist_ok=True)
    if port_listening(PORT) and os.environ.get("REPORT_FORCE_RESTART", "0") != "1":
        print(f"already_listening:{PORT}", flush=True)
        return 0

    log = LOG_FILE.open("w", encoding="utf-8")
    env = os.environ.copy()
    env.setdefault("REPORT_HOST", "0.0.0.0")
    env.setdefault("REPORT_PORT", str(PORT))

    creationflags = 0
    if os.name == "nt":
        # 脱离控制台，避免关终端时被杀掉
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(
            subprocess, "DETACHED_PROCESS", 0
        )

    proc = subprocess.Popen(
        [project_python(), str(ROOT / "server" / "app.py")],
        cwd=str(ROOT),
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=(os.name != "nt"),
        creationflags=creationflags,
        env=env,
        close_fds=(os.name != "nt"),
    )
    PID_FILE.write_text(str(proc.pid), encoding="utf-8")

    for _ in range(40):
        if port_listening(PORT):
            print(f"started:{proc.pid}", flush=True)
            return 0
        if proc.poll() is not None:
            log.close()
            print("exited_early", flush=True)
            try:
                print(LOG_FILE.read_text(encoding="utf-8")[-2000:], flush=True)
            except OSError:
                pass
            return 1
        time.sleep(0.25)

    print("timeout_waiting_listen", flush=True)
    try:
        print(LOG_FILE.read_text(encoding="utf-8")[-2000:], flush=True)
    except OSError:
        pass
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
