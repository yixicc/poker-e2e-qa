from __future__ import annotations

import sys
from pathlib import Path

import pytest

# 保证从 automation/ 根导入 config / common
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.mcp_client import McpClient  # noqa: E402
from config.settings import settings  # noqa: E402


@pytest.fixture(scope="session")
def mcp_settings():
    return settings


@pytest.fixture(scope="session")
def mcp_client(mcp_settings):
    mcp_settings.require_mcp()
    if not mcp_settings.cases_xlsx.exists():
        pytest.skip(f"找不到用例表: {mcp_settings.cases_xlsx}")
    client = McpClient(
        base_url=mcp_settings.mcp_base_url,
        token=mcp_settings.mcp_token,
        protocol_version=mcp_settings.mcp_protocol_version,
        timeout_sec=mcp_settings.mcp_timeout_sec,
        open_id=mcp_settings.mcp_open_id,
    )
    with client:
        yield client
