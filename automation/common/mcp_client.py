"""MCP Streamable HTTP 客户端：initialize → tools/call，解析 SSE。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

import httpx


class McpError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, body: str = "") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


@dataclass
class McpResponse:
    status_code: int
    headers: dict[str, str]
    raw_text: str
    jsonrpc: dict[str, Any] | None = None
    elapsed_ms: float = 0.0

    @property
    def ok(self) -> bool:
        if self.status_code >= 400:
            return False
        if not self.jsonrpc:
            return False
        if "error" in self.jsonrpc:
            return False
        result = self.jsonrpc.get("result")
        if isinstance(result, dict) and result.get("isError") is True:
            return False
        return True

    @property
    def tool_text(self) -> str:
        """tools/call 返回的文本内容拼接。"""
        result = (self.jsonrpc or {}).get("result") or {}
        content = result.get("content") or []
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text") or ""))
        return "\n".join(parts)

    def tool_payload(self) -> Any:
        """尝试把 tool_text 解析成 JSON；失败则返回原文。"""
        text = self.tool_text.strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text


_DATA_RE = re.compile(r"^data:\s*(.+)$", re.M)


def parse_sse_jsonrpc(raw: str) -> dict[str, Any] | None:
    """从 text/event-stream 或纯 JSON 中取出 jsonrpc 对象。"""
    text = (raw or "").strip()
    if not text:
        return None
    if text.startswith("{"):
        try:
            obj = json.loads(text)
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            pass
    matches = _DATA_RE.findall(text)
    for chunk in reversed(matches):
        chunk = chunk.strip()
        if not chunk or chunk == "[DONE]":
            continue
        try:
            obj = json.loads(chunk)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    return None


@dataclass
class McpClient:
    base_url: str
    token: str
    protocol_version: str = "2024-11-05"
    timeout_sec: float = 30.0
    open_id: str = ""
    _client: httpx.Client | None = field(default=None, init=False, repr=False)
    session_id: str | None = field(default=None, init=False)

    def __enter__(self) -> "McpClient":
        self.open()
        self.initialize()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def open(self) -> None:
        if self._client is None:
            self._client = httpx.Client(
                timeout=self.timeout_sec,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "ngrok-skip-browser-warning": "true",
                },
            )

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
        self.session_id = None

    def _headers(self, *, with_session: bool) -> dict[str, str]:
        h: dict[str, str] = {}
        if with_session:
            if not self.session_id:
                raise McpError("缺少 Mcp-Session-Id，请先 initialize")
            h["Mcp-Session-Id"] = self.session_id
        return h

    def _post(self, body: dict[str, Any], *, with_session: bool) -> McpResponse:
        self.open()
        assert self._client is not None
        resp = self._client.post(
            self.base_url,
            json=body,
            headers=self._headers(with_session=with_session),
        )
        sid = resp.headers.get("mcp-session-id") or resp.headers.get("Mcp-Session-Id")
        if sid:
            self.session_id = sid
        raw = resp.text
        parsed = parse_sse_jsonrpc(raw)
        out = McpResponse(
            status_code=resp.status_code,
            headers={k: v for k, v in resp.headers.items()},
            raw_text=raw,
            jsonrpc=parsed,
            elapsed_ms=resp.elapsed.total_seconds() * 1000,
        )
        if resp.status_code == 401:
            raise McpError("unauthorized：检查 MCP_TOKEN 是否带 Bearer 值", status_code=401, body=raw)
        if resp.status_code >= 400 and parsed is None:
            raise McpError(f"HTTP {resp.status_code}", status_code=resp.status_code, body=raw)
        if parsed and "error" in parsed:
            err = parsed["error"]
            msg = err.get("message") if isinstance(err, dict) else str(err)
            if "Session not found" in str(msg) or "Missing session" in str(msg):
                raise McpError(str(msg), status_code=resp.status_code, body=raw)
        return out

    def initialize(self) -> McpResponse:
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": self.protocol_version,
                "capabilities": {},
                "clientInfo": {"name": "poker-mcp-auto", "version": "0.1.0"},
            },
        }
        resp = self._post(body, with_session=False)
        if not self.session_id:
            raise McpError("initialize 未返回 mcp-session-id", body=resp.raw_text)
        # notifications/initialized（无 id，可 202）
        self._client.post(  # type: ignore[union-attr]
            self.base_url,
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            headers=self._headers(with_session=True),
        )
        return resp

    def ensure_session(self) -> None:
        if not self.session_id:
            self.initialize()

    def call_raw(self, body: dict[str, Any], *, retry_on_session_lost: bool = True) -> McpResponse:
        """直接发送完整 JSON-RPC body（来自 Excel request_body）。"""
        self.ensure_session()
        try:
            return self._post(body, with_session=True)
        except McpError as e:
            if retry_on_session_lost and e.body and "Session" in e.body:
                self.session_id = None
                self.initialize()
                return self._post(body, with_session=True)
            raise

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None, *, req_id: int = 3) -> McpResponse:
        body = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
        }
        return self.call_raw(body)

    def render_placeholders(self, body: dict[str, Any], extra: dict[str, str] | None = None) -> dict[str, Any]:
        """替换 {{open_id}} / {{hand_id}} 等占位符。"""
        mapping = {"open_id": self.open_id, **(extra or {})}
        raw = json.dumps(body, ensure_ascii=False)

        def repl(m: re.Match[str]) -> str:
            key = m.group(1)
            return mapping.get(key, m.group(0))

        rendered = re.sub(r"\{\{(\w+)\}\}", repl, raw)
        return json.loads(rendered)
