#!/usr/bin/env python3
"""跨平台生成 Allure HTML（找不到 allure CLI 则跳过）。"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    os.chdir(ROOT)
    results = Path(sys.argv[1] if len(sys.argv) > 1 else "reports/allure-results")
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "reports/allure-report")

    if not results.is_dir() or not any(results.iterdir()):
        print(f"没有 Allure 原始结果：{results}（请先跑 pytest --alluredir=...）")
        return 0

    allure = shutil.which("allure")
    if not allure and os.name == "nt":
        # scoop / chocolatey 常见路径
        for cand in (
            Path.home() / "scoop" / "shims" / "allure.cmd",
            Path("C:/ProgramData/chocolatey/bin/allure.bat"),
        ):
            if cand.is_file():
                allure = str(cand)
                break

    if not allure:
        print("未安装 allure CLI，跳过 HTML 生成。")
        print("安装：macOS → brew install allure；Windows → scoop install allure 或见 https://docs.qameta.io/allure/")
        print(f"原始结果仍在：{results}")
        print("pytest-html 可用：reports/report.html")
        return 0

    out.mkdir(parents=True, exist_ok=True)
    subprocess.run([allure, "generate", str(results), "-o", str(out), "--clean"], check=False)
    index = (out / "index.html").resolve()
    print(f"Allure 报告已生成：{index.as_uri()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
