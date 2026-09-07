#!/usr/bin/env python3
"""Trace 查询环境目录（TexasDataCenter data-platform HTTP API）。

与 trace-viewer.html 对齐：浏览器/本工具 → API → 服务端查 ClickHouse。
当前仅开放 uat；prod 条目预留但默认不启用。
"""

from __future__ import annotations

from typing import Any


TRACE_ENVS: dict[str, dict[str, Any]] = {
    "uat": {
        "id": "uat",
        "label": "UAT / 测试（data-platform）",
        "api_base": "http://8.145.52.251:7121",
        "env_label": "UAT · 8.145.52.251:7121",
        "enabled": True,
    },
    # 与 Viewer「阿里云生产」一致；默认不启用，避免误查。
    "prod": {
        "id": "prod",
        "label": "生产（data-platform）",
        "api_base": "http://8.145.52.251:8121",
        "env_label": "PROD · 8.145.52.251:8121",
        "enabled": False,
    },
}

DEFAULT_TRACE_ENV = "uat"


def list_trace_envs(*, enabled_only: bool = True) -> list[dict[str, Any]]:
    items = []
    for env in TRACE_ENVS.values():
        if enabled_only and not env.get("enabled", True):
            continue
        items.append(dict(env))
    return items


def get_trace_env(env_id: str | None) -> dict[str, Any]:
    """Resolve env id; empty → default uat. Unknown id raises."""
    eid = str(env_id or "").strip() or DEFAULT_TRACE_ENV
    env = TRACE_ENVS.get(eid)
    if not env:
        known = ", ".join(sorted(TRACE_ENVS.keys())) or "(none)"
        raise KeyError(f"未知 Trace 环境: {eid!r}（可选: {known}）")
    if not env.get("enabled", True):
        raise KeyError(f"Trace 环境未启用: {eid!r}")
    return dict(env)


def normalize_trace_env(env_id: str | None) -> str:
    return str(get_trace_env(env_id)["id"])


def resolve_api_base(env_id: str | None = None, *, override: str = "") -> str:
    """Effective API base: explicit override wins, else catalog api_base."""
    ov = str(override or "").strip().rstrip("/")
    if ov:
        return ov
    return str(get_trace_env(env_id).get("api_base") or "").rstrip("/")
