"""从环境变量 / .env 加载自动化配置。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent

# 优先读 automation/.env，再读仓库根 .env
load_dotenv(ROOT / ".env")
load_dotenv(REPO_ROOT / ".env")


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _path(name: str, default: Path) -> Path:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    p = Path(raw).expanduser()
    return p if p.is_absolute() else (ROOT / p)


@dataclass(frozen=True)
class Settings:
    mcp_base_url: str
    mcp_token: str
    mcp_open_id: str
    mcp_protocol_version: str
    mcp_timeout_sec: float
    cases_xlsx: Path
    ui_base_url: str
    ui_chat_path: str
    ui_open_id: str
    ui_enabled: bool
    ui_headed: bool
    ui_case_limit: int
    ui_priorities: str
    allure_results_dir: Path
    html_report_path: Path
    excel_report_dir: Path

    @property
    def ui_chat_url(self) -> str:
        base = self.ui_base_url.rstrip("/")
        path = self.ui_chat_path if self.ui_chat_path.startswith("/") else f"/{self.ui_chat_path}"
        return f"{base}{path}"

    def require_mcp(self) -> None:
        if not self.mcp_base_url:
            raise RuntimeError("未配置 MCP_BASE_URL")
        if not self.mcp_token:
            raise RuntimeError("未配置 MCP_TOKEN（可写在 automation/.env）")

    def new_excel_report_path(self) -> Path:
        from datetime import datetime

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        fixed = os.getenv("EXCEL_REPORT_PATH", "").strip()
        if fixed:
            p = Path(fixed).expanduser()
            return p if p.is_absolute() else (ROOT / p)
        return self.excel_report_dir / f"MCP执行结果_{stamp}.xlsx"


def _env_cases_xlsx() -> Path | None:
    """`.env` 里 MCP_CASES_XLSX：命令行要跑的那份，已指定目录下的文件。"""
    env = os.getenv("MCP_CASES_XLSX", "").strip()
    if not env:
        return None
    p = Path(env).expanduser()
    return p if p.is_absolute() else (ROOT / p)


def _default_cases_xlsx() -> Path:
    """命令行直接跑已指定的用例表，不必先上传。

    配了 MCP_CASES_XLSX 就用它（文件不存在也返回该路径，方便报错指到原目录）。
    没配环境变量时，才退回上传激活表、data/latest、Downloads、testdata。
    """
    env_path = _env_cases_xlsx()
    if env_path is not None:
        return env_path

    active = ROOT / "data" / "active_cases_path.txt"
    if active.exists():
        raw = active.read_text(encoding="utf-8").strip()
        if raw and Path(raw).exists():
            return Path(raw)

    latest = ROOT / "data" / "MCP自动化步骤用例_latest.xlsx"
    if latest.exists():
        return latest

    downloads = Path("/Users/xixi/Downloads/MCP自动化步骤用例_10月26.xlsx")
    if downloads.exists():
        return downloads
    legacy = Path("/Users/xixi/Downloads/MCP自动化步骤用例_10月23.xlsx")
    if legacy.exists():
        return legacy

    alt = REPO_ROOT / "testdata" / "mcp" / "MCP自动化步骤用例_10月26.xlsx"
    if alt.exists():
        return alt
    alt23 = REPO_ROOT / "testdata" / "mcp" / "MCP自动化步骤用例_10月23.xlsx"
    return alt23 if alt23.exists() else downloads


def get_settings() -> Settings:
    default_xlsx = _default_cases_xlsx()

    return Settings(
        mcp_base_url=os.getenv("MCP_BASE_URL", "https://d943-223-70-117-10.ngrok-free.app/mcp").strip(),
        mcp_token=os.getenv("MCP_TOKEN", "").strip(),
        mcp_open_id=os.getenv("MCP_OPEN_ID", "1ad0c14143ae4d12894c41c89e603e94").strip(),
        mcp_protocol_version=os.getenv("MCP_PROTOCOL_VERSION", "2024-11-05").strip(),
        mcp_timeout_sec=float(os.getenv("MCP_TIMEOUT_SEC", "30")),
        cases_xlsx=default_xlsx,
        ui_base_url=os.getenv("UI_BASE_URL", "http://192.168.110.147:3100").strip(),
        ui_chat_path=os.getenv("UI_CHAT_PATH", "/web/production/").strip(),
        ui_open_id=os.getenv("UI_OPEN_ID", os.getenv("MCP_OPEN_ID", "")).strip(),
        ui_enabled=_bool("UI_ENABLED", False),
        ui_headed=_bool("UI_HEADED", False),
        ui_case_limit=int(os.getenv("UI_CASE_LIMIT", "0") or "0"),
        ui_priorities=os.getenv("UI_PRIORITIES", "").strip(),
        allure_results_dir=_path("ALLURE_RESULTS_DIR", ROOT / "reports" / "allure-results"),
        html_report_path=_path("HTML_REPORT_PATH", ROOT / "reports" / "report.html"),
        excel_report_dir=_path("EXCEL_REPORT_DIR", ROOT / "reports"),
    )


settings = get_settings()
