#!/usr/bin/env python3
"""跨平台停止结果展示服务。"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts._portal_util import kill_pid, port_listening, read_pid_file  # noqa: E402


def main() -> int:
    os.chdir(ROOT)
    port = int(os.environ.get("REPORT_PORT", "8767"))
    pid_file = ROOT / "reports" / ".report-server.pid"
    old = read_pid_file(pid_file)
    if old:
        kill_pid(old)
    if pid_file.exists():
        try:
            pid_file.unlink()
        except OSError:
            pass
    # 再等一下端口释放
    for _ in range(20):
        if not port_listening(port):
            break
        time.sleep(0.15)
    print(f"已停止展示服务 :{port}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
