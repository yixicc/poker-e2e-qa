#!/usr/bin/env python3
"""一轮聊天：连上数据 MCP，把工具交给大模型，由模型决定调用哪些。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from mcp_stdio import StdioReader, write_message

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / "data" / "chat.env"
SERVER = ROOT / "scripts" / "data_mcp_server.py"
MAX_ROUNDS = 6

SYSTEM_PROMPT = """你是扑克 GTO 质量站的数据助手。
用户问起跑批对比、正确值、手牌 Bug、Trace、fusion 场次时，先调用工具拿数，再据此回答。
工具是只读的。回答用中文：先给结论，再写你用到的 run id、手牌号或数字。
范围不清楚时，先用列表类工具缩小，或向用户追问时间窗、OpenID、sessionId。"""


class ChatConfigError(RuntimeError):
    pass


def load_chat_env(path: Path = ENV_PATH) -> dict[str, str]:
    out = {"CHAT_BASE_URL": "", "CHAT_API_KEY": "", "CHAT_MODEL": ""}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            if key in out:
                out[key] = val.strip().strip("'").strip('"')
    for key in list(out):
        if os.environ.get(key):
            out[key] = os.environ[key].strip()
    return out


def chat_configured(cfg: dict[str, str] | None = None) -> bool:
    src = cfg or load_chat_env()
    return bool(src["CHAT_BASE_URL"] and src["CHAT_API_KEY"] and src["CHAT_MODEL"])


class DataMcp:
    def __init__(self) -> None:
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        self.proc = subprocess.Popen(
            [sys.executable, str(SERVER)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(ROOT),
            env=env,
        )
        assert self.proc.stdin and self.proc.stdout and self.proc.stderr
        self.reader = StdioReader(self.proc.stdout.raw)
        self._seq = 0
        self._err = ""
        threading.Thread(target=self._drain_stderr, daemon=True).start()

    def _drain_stderr(self) -> None:
        assert self.proc.stderr
        chunks: list[bytes] = []
        while True:
            block = self.proc.stderr.raw.read(4096)
            if not block:
                break
            chunks.append(block)
            if sum(len(c) for c in chunks) > 8000:
                break
        self._err = b"".join(chunks).decode("utf-8", errors="replace")[-500:]

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.proc.poll() is not None:
            raise RuntimeError(f"数据 MCP 已退出 {self._err}".strip())
        self._seq += 1
        write_message(
            self.proc.stdin,
            {"jsonrpc": "2.0", "id": self._seq, "method": method, "params": params or {}},
        )
        while True:
            msg = self.reader.read_message()
            if msg.get("id") != self._seq:
                continue
            if "error" in msg:
                raise RuntimeError(str(msg["error"]))
            result = msg.get("result")
            return result if isinstance(result, dict) else {}

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.kill()
        self.proc.wait(timeout=5)


def list_tool_names() -> list[str]:
    mcp = DataMcp()
    try:
        mcp.request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "qa-chat", "version": "0.1.0"},
            },
        )
        write_message(mcp.proc.stdin, {"jsonrpc": "2.0", "method": "notifications/initialized"})
        listed = mcp.request("tools/list")
        tools = listed.get("tools") if isinstance(listed.get("tools"), list) else []
        return [str(t.get("name")) for t in tools if isinstance(t, dict) and t.get("name")]
    finally:
        mcp.close()


def chat_status() -> dict[str, Any]:
    cfg = load_chat_env()
    names: list[str] = []
    tool_error = ""
    try:
        names = list_tool_names()
    except Exception as e:
        tool_error = str(e)
    return {
        "ok": True,
        "configured": chat_configured(cfg),
        "model": cfg["CHAT_MODEL"] if chat_configured(cfg) else "",
        "base_url": cfg["CHAT_BASE_URL"] if chat_configured(cfg) else "",
        "tools": names,
        "tool_error": tool_error,
    }


def _completions_url(base: str) -> str:
    url = base.rstrip("/")
    if url.endswith("/chat/completions"):
        return url
    return url + "/chat/completions"


def _openai_tools(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tools = []
    for spec in specs:
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": spec["name"],
                    "description": spec.get("description") or "",
                    "parameters": spec.get("inputSchema") or {"type": "object", "properties": {}},
                },
            }
        )
    return tools


def _call_llm(cfg: dict[str, str], messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
    body = json.dumps(
        {
            "model": cfg["CHAT_MODEL"],
            "temperature": 0.2,
            "messages": messages,
            "tools": tools,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        _completions_url(cfg["CHAT_BASE_URL"]),
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg['CHAT_API_KEY']}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:400]
        raise ChatConfigError(f"模型接口 HTTP {e.code}：{detail}") from e
    except Exception as e:
        raise ChatConfigError(f"模型接口连不上：{e}") from e
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ChatConfigError("模型接口返回的不是 JSON") from e
    choices = data.get("choices") if isinstance(data, dict) else None
    if not choices:
        raise ChatConfigError("模型接口没有返回 choices")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        raise ChatConfigError("模型接口没有返回 message")
    return message


def _parse_arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        parsed = json.loads(str(raw))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _tool_text(result: dict[str, Any]) -> str:
    content = result.get("content")
    if isinstance(content, list):
        parts = [str(b.get("text") or "") for b in content if isinstance(b, dict)]
        return "\n".join(p for p in parts if p)
    return json.dumps(result, ensure_ascii=False)


def _public_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = str(msg.get("role") or "")
        if role not in ("user", "assistant"):
            continue
        content = str(msg.get("content") or "").strip()
        if not content:
            continue
        out.append({"role": role, "content": content})
    return out[-20:]


def run_chat(messages: list[dict[str, Any]]) -> dict[str, Any]:
    cfg = load_chat_env()
    if not chat_configured(cfg):
        raise ChatConfigError(
            "还没配置模型。复制 data/chat.env.example 为 data/chat.env，填上 CHAT_BASE_URL、CHAT_API_KEY、CHAT_MODEL。"
        )
    history = _public_messages(messages)
    if not history or history[-1]["role"] != "user":
        raise ChatConfigError("请发送一条用户消息")

    mcp = DataMcp()
    used: list[dict[str, Any]] = []
    try:
        mcp.request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "qa-chat", "version": "0.1.0"},
            },
        )
        write_message(mcp.proc.stdin, {"jsonrpc": "2.0", "method": "notifications/initialized"})
        listed = mcp.request("tools/list")
        specs = [t for t in (listed.get("tools") or []) if isinstance(t, dict)]
        tools = _openai_tools(specs)
        thread: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}, *history]
        reply = ""
        for _ in range(MAX_ROUNDS):
            message = _call_llm(cfg, thread, tools)
            tool_calls = message.get("tool_calls") if isinstance(message.get("tool_calls"), list) else []
            content = message.get("content")
            reply = content.strip() if isinstance(content, str) else ""
            if not tool_calls:
                if not reply:
                    reply = "模型没有返回文字。"
                return {"ok": True, "reply": reply, "tool_calls": used}
            thread.append(
                {
                    "role": "assistant",
                    "content": content if isinstance(content, str) else "",
                    "tool_calls": tool_calls,
                }
            )
            for call in tool_calls:
                if not isinstance(call, dict):
                    continue
                fn = call.get("function") if isinstance(call.get("function"), dict) else {}
                name = str(fn.get("name") or "")
                arguments = _parse_arguments(fn.get("arguments"))
                result = mcp.request("tools/call", {"name": name, "arguments": arguments})
                text = _tool_text(result)
                used.append(
                    {
                        "name": name,
                        "arguments": arguments,
                        "ok": not bool(result.get("isError")),
                        "preview": text[:500],
                    }
                )
                thread.append(
                    {
                        "role": "tool",
                        "tool_call_id": str(call.get("id") or name),
                        "content": text,
                    }
                )
        return {
            "ok": True,
            "reply": reply or "这一轮工具调用已到上限，请把问题收窄后再问。",
            "tool_calls": used,
        }
    finally:
        mcp.close()
