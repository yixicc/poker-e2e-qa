"""公共模块。按需 import 子模块，避免未装 httpx 时拖垮 convert/web。"""

__all__ = [
    "CaseRow",
    "RequestRow",
    "McpClient",
    "McpError",
    "McpResponse",
]


def __getattr__(name: str):
    if name in {"CaseRow", "RequestRow", "load_cases", "load_enabled_requests", "load_config_sheet"}:
        from . import excel_loader as m

        return getattr(m, name)
    if name in {"McpClient", "McpError", "McpResponse"}:
        from . import mcp_client as m

        return getattr(m, name)
    raise AttributeError(name)
