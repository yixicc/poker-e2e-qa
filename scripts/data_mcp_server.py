#!/usr/bin/env python3
"""把只读数据工具暴露成 stdio MCP。stdout 只写协议帧，日志走 stderr。"""

from __future__ import annotations

import sys
from typing import Any

from data_tools import TOOL_SPECS, call_tool
from mcp_stdio import StdioReader, write_message

PROTOCOL = "2024-11-05"


def _result(msg_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _error(msg_id: Any, message: str, code: int = -32603) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def handle(method: str, params: dict[str, Any]) -> dict[str, Any]:
    if method == "initialize":
        return {
            "protocolVersion": PROTOCOL,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "poker-qa-data", "version": "0.1.0"},
        }
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": TOOL_SPECS}
    if method == "tools/call":
        name = str(params.get("name") or "")
        arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
        text, is_error = call_tool(name, arguments)
        return {
            "content": [{"type": "text", "text": text}],
            "isError": is_error,
        }
    raise ValueError(f"不支持的方法 {method}")


def main() -> None:
    # 保住原来的 stdout，避免被替换后关掉协议用的管道。
    held_stdout = sys.stdout
    proto_in = sys.stdin.buffer.raw
    proto_out = held_stdout.buffer
    sys.stdout = sys.stderr
    reader = StdioReader(proto_in)
    while True:
        try:
            msg = reader.read_message()
        except EOFError:
            return
        except Exception as e:
            print(f"mcp read: {e}", file=sys.stderr)
            return
        if "id" not in msg:
            continue
        method = str(msg.get("method") or "")
        params = msg.get("params") if isinstance(msg.get("params"), dict) else {}
        try:
            write_message(proto_out, _result(msg["id"], handle(method, params)))
        except Exception as e:
            write_message(proto_out, _error(msg["id"], str(e)))


if __name__ == "__main__":
    main()
