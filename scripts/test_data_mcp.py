#!/usr/bin/env python3
"""离线检查数据 MCP：initialize、tools/list、本地只读工具。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from chat_turn import DataMcp, write_message  # noqa: E402


def main() -> None:
    mcp = DataMcp()
    try:
        init = mcp.request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0"},
            },
        )
        assert init["serverInfo"]["name"] == "poker-qa-data", init
        write_message(mcp.proc.stdin, {"jsonrpc": "2.0", "method": "notifications/initialized"})
        listed = mcp.request("tools/list")
        names = [t["name"] for t in listed["tools"]]
        assert "list_compare_runs" in names
        assert "query_trace" in names
        runs = mcp.request("tools/call", {"name": "list_compare_runs", "arguments": {}})
        assert runs["isError"] is False
        text = runs["content"][0]["text"]
        assert "20260812-rerun" in text
        overview = mcp.request(
            "tools/call",
            {"name": "get_run_overview", "arguments": {"run_id": "20260812-rerun"}},
        )
        assert overview["isError"] is False
        assert "21.4" in overview["content"][0]["text"]
        missing = mcp.request(
            "tools/call",
            {"name": "query_trace", "arguments": {}},
        )
        assert missing["isError"] is True
        print("ok", len(names), "tools")
    finally:
        mcp.close()


if __name__ == "__main__":
    main()
