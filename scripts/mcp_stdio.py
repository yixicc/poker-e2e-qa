#!/usr/bin/env python3
"""MCP stdio 帧：Content-Length + JSON-RPC。聊天进程和数据服务共用。"""

from __future__ import annotations

import json
from typing import Any, BinaryIO


class McpFramingError(RuntimeError):
    pass


class StdioReader:
    """读未缓冲 raw 流。管道上 BufferedReader.read(n) 会一直等到 n 字节或 EOF。"""

    def __init__(self, raw: BinaryIO):
        self.raw = raw
        self.buf = b""

    def read_message(self) -> dict[str, Any]:
        while b"\r\n\r\n" not in self.buf:
            chunk = self.raw.read(4096)
            if not chunk:
                raise EOFError("MCP 连接已关闭")
            self.buf += chunk
            if len(self.buf) > 1_000_000 and b"\r\n\r\n" not in self.buf:
                raise McpFramingError("MCP 头过长")
        head, self.buf = self.buf.split(b"\r\n\r\n", 1)
        length = _content_length(head)
        while len(self.buf) < length:
            chunk = self.raw.read(length - len(self.buf))
            if not chunk:
                raise EOFError("MCP 消息被截断")
            self.buf += chunk
        body, self.buf = self.buf[:length], self.buf[length:]
        try:
            msg = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as e:
            raise McpFramingError(f"MCP 消息不是 JSON: {e}") from e
        if not isinstance(msg, dict):
            raise McpFramingError("MCP 消息必须是对象")
        return msg


def write_message(raw: BinaryIO, msg: dict[str, Any]) -> None:
    body = json.dumps(msg, ensure_ascii=False).encode("utf-8")
    raw.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body)
    raw.flush()


def _content_length(head: bytes) -> int:
    for line in head.split(b"\r\n"):
        if line.lower().startswith(b"content-length:"):
            try:
                n = int(line.split(b":", 1)[1].strip())
            except ValueError as e:
                raise McpFramingError("Content-Length 非法") from e
            if n < 0 or n > 8_000_000:
                raise McpFramingError("Content-Length 超出范围")
            return n
    raise McpFramingError("缺少 Content-Length")
