"""调用仓库 scripts/build_mcp_auto_cases 做原始表 → 自动化表转换。"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
SCRIPTS = REPO_ROOT / "scripts"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from build_mcp_auto_cases import convert_workbook  # noqa: E402


def convert_uploaded_excel(source: Path, out_dir: Path) -> dict[str, Any]:
    """
    转换上传的原始用例表。
    产出：
      - out_dir / 自动化步骤用例.xlsx
      - automation/data/MCP自动化步骤用例_latest.xlsx（另存；命令行仍以 MCP_CASES_XLSX 为准）
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "自动化步骤用例.xlsx"
    latest = ROOT / "data" / "MCP自动化步骤用例_latest.xlsx"
    latest.parent.mkdir(parents=True, exist_ok=True)

    stats = convert_workbook(source, out_file, also_copy_to=latest)
    # 仅在未配置 MCP_CASES_XLSX 时，命令行才会退回到这份路径
    active = ROOT / "data" / "active_cases_path.txt"
    active.write_text(str(latest.resolve()), encoding="utf-8")

    return {
        "ok": True,
        "source": str(source.resolve()),
        "converted": str(out_file.resolve()),
        "latest": str(latest.resolve()),
        "stats": stats,
    }
