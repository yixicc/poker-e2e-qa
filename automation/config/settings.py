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
    ui_enabled: bool
    allure_results_dir: Path
    html_report_path: Path

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


def get_settings() -> Settings:
    default_xlsx = Path("/Users/xixi/Downloads/MCP自动化请求用例_郑秀雨.xlsx")
    alt = REPO_ROOT / "testdata" / "mcp" / "MCP自动化请求用例_郑秀雨.xlsx"
    if not default_xlsx.exists() and alt.exists():
        default_xlsx = alt

    return Settings(
        mcp_base_url=os.getenv("MCP_BASE_URL", "https://d943-223-70-117-10.ngrok-free.app/mcp").strip(),
        mcp_token=os.getenv("MCP_TOKEN", "").strip(),
        mcp_open_id=os.getenv("MCP_OPEN_ID", "1ad0c14143ae4d12894c41c89e603e94").strip(),
        mcp_protocol_version=os.getenv("MCP_PROTOCOL_VERSION", "2024-11-05").strip(),
        mcp_timeout_sec=float(os.getenv("MCP_TIMEOUT_SEC", "30")),
        cases_xlsx=_path("MCP_CASES_XLSX", default_xlsx),
        ui_base_url=os.getenv("UI_BASE_URL", "http://127.0.0.1:8765").strip(),
        ui_chat_path=os.getenv("UI_CHAT_PATH", "/chat").strip(),
        ui_enabled=_bool("UI_ENABLED", False),
        allure_results_dir=_path("ALLURE_RESULTS_DIR", ROOT / "reports" / "allure-results"),
        html_report_path=_path("HTML_REPORT_PATH", ROOT / "reports" / "report.html"),
    )


settings = get_settings()
