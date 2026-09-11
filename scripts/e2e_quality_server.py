#!/usr/bin/env python3
"""兼容入口。质量站代码已集中到 e2e-quality-station/。"""

from pathlib import Path
import runpy

runpy.run_path(
    str(Path(__file__).resolve().parent.parent / "e2e-quality-station" / "e2e_quality_server.py"),
    run_name="__main__",
)
