#!/usr/bin/env python3
"""Trace 客户端：调用 TexasDataCenter data-platform HTTP API（与 trace-viewer 一致）。"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Optional

from trace_envs import DEFAULT_TRACE_ENV, normalize_trace_env, resolve_api_base

TIMEOUT_S = 45


class TraceClientError(RuntimeError):
    pass


class TraceClient:
    """HTTP Trace client → data-platform ``/api/v1/traceQuery`` 等。"""

    def __init__(
        self,
        env_id: str = DEFAULT_TRACE_ENV,
        *,
        base_url: str = "",
        timeout: float = TIMEOUT_S,
    ):
        self.env_id = normalize_trace_env(env_id)
        self.base_url = resolve_api_base(self.env_id, override=base_url)
        if not self.base_url:
            raise TraceClientError(f"环境 {self.env_id!r} 未配置 api_base")
        self.timeout = timeout

    def _get_json(self, path: str, params: dict[str, Any]) -> Any:
        qs = urllib.parse.urlencode(
            {k: v for k, v in params.items() if v is not None and str(v) != ""}
        )
        url = f"{self.base_url}{path}"
        if qs:
            url = f"{url}?{qs}"
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace") if e.fp else ""
            raise TraceClientError(f"HTTP {e.code} {path}: {body[:400] or e.reason}") from e
        except Exception as e:
            raise TraceClientError(f"{path} 失败: {e}") from e
        try:
            data = json.loads(raw) if raw else {}
        except json.JSONDecodeError as e:
            raise TraceClientError(f"{path} 返回非 JSON: {raw[:200]}") from e
        if isinstance(data, dict):
            if data.get("success") is False or data.get("ok") is False:
                raise TraceClientError(
                    str(data.get("message") or data.get("error") or data)
                )
            if "result" in data:
                return data.get("result")
        return data

    def trace_query(
        self,
        *,
        open_id: str = "",
        hole_cards: str = "",
        start_time: str = "",
        end_time: str = "",
    ) -> list[dict]:
        result = self._get_json(
            "/api/v1/traceQuery",
            {
                "openId": open_id or None,
                "holeCards": hole_cards or None,
                "startTime": start_time or None,
                "endTime": end_time or None,
            },
        )
        if result is None:
            return []
        if not isinstance(result, list):
            raise TraceClientError(f"traceQuery 结果不是列表: {type(result).__name__}")
        return result

    def trace_discover(self, *, start_time: str, end_time: str) -> list[dict]:
        result = self._get_json(
            "/api/v1/traceDiscover",
            {"startTime": start_time or None, "endTime": end_time or None},
        )
        if result is None:
            return []
        if not isinstance(result, list):
            raise TraceClientError(f"traceDiscover 结果不是列表: {type(result).__name__}")
        return result

    def image_frames_by_keys(self, *, open_id: str, msg_keys: list[Any]) -> list[dict]:
        keys = [str(k) for k in (msg_keys or []) if k is not None and str(k) != ""]
        if not keys:
            return []
        result = self._get_json(
            "/api/v1/imageFramesByKeys",
            {"openId": open_id or None, "msgKeys": ",".join(keys)},
        )
        if result is None:
            return []
        if not isinstance(result, list):
            raise TraceClientError(
                f"imageFramesByKeys 结果不是列表: {type(result).__name__}"
            )
        return result

    def image_frames_by_range(
        self, *, open_id: str, min_msg_key: Any, max_msg_key: Any
    ) -> list[dict]:
        result = self._get_json(
            "/api/v1/imageFramesByRange",
            {
                "openId": open_id or None,
                "minMsgKey": min_msg_key,
                "maxMsgKey": max_msg_key,
            },
        )
        if result is None:
            return []
        if not isinstance(result, list):
            raise TraceClientError(
                f"imageFramesByRange 结果不是列表: {type(result).__name__}"
            )
        return result


def get_trace_client(env_id: Optional[str] = None, **kwargs: Any) -> TraceClient:
    return TraceClient(env_id=env_id or DEFAULT_TRACE_ENV, **kwargs)


def hole_cards_variants(hole_key: Any) -> list[str]:
    """Generate holeCards query variants from hole_cards_p0 / compact forms."""
    out: list[str] = []
    seen: set[str] = set()

    def add(s: str) -> None:
        s = (s or "").strip()
        if s and s not in seen:
            seen.add(s)
            out.append(s)

    if hole_key is None:
        return out
    if isinstance(hole_key, list):
        cards = [str(c).strip() for c in hole_key if str(c).strip()]
        if cards:
            add(",".join(cards))
            add("".join(cards))
            add(json.dumps(cards, ensure_ascii=False))
        return out

    text = str(hole_key).strip()
    try:
        parsed = json.loads(text.replace("'", '"'))
        if isinstance(parsed, list):
            cards = [str(c).strip() for c in parsed if str(c).strip()]
            if cards:
                add(",".join(cards))
                add("".join(cards))
                add(text)
            return out
    except Exception:
        pass

    add(text)
    compact = re.sub(r"[^A-Za-z0-9]", "", text)
    if compact and len(compact) % 2 == 0 and len(compact) >= 4:
        cards = [compact[i : i + 2] for i in range(0, len(compact), 2)]
        add(",".join(cards))
        add(compact)
    return out


def ms_to_api_time(ms: Optional[int]) -> Optional[str]:
    if ms is None:
        return None
    try:
        dt = datetime.fromtimestamp(int(ms) / 1000.0)
    except (OSError, OverflowError, ValueError):
        return None
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def time_window_around(
    center_ms: Optional[int],
    *,
    pad_minutes: int = 15,
    created_at: Any = None,
) -> tuple[str, str]:
    """Build start/end timestamps for Trace API time filter."""
    day = None
    if created_at is not None:
        text = str(created_at).strip()
        m = re.match(r"(\d{4}-\d{2}-\d{2})", text)
        if m:
            day = m.group(1)
        elif hasattr(created_at, "strftime"):
            try:
                day = created_at.strftime("%Y-%m-%d")
            except Exception:
                day = None

    if day:
        start_ms = ms_to_api_time(int(center_ms) - pad_minutes * 60_000) if center_ms else None
        end_ms = ms_to_api_time(int(center_ms) + pad_minutes * 60_000) if center_ms else None
        if start_ms and end_ms and start_ms.startswith(day) and end_ms.startswith(day):
            return start_ms, end_ms
        return f"{day} 00:00:00", f"{day} 23:59:59"

    if center_ms is not None:
        start = ms_to_api_time(int(center_ms) - pad_minutes * 60_000)
        end = ms_to_api_time(int(center_ms) + pad_minutes * 60_000)
        if start and end:
            return start, end

    now = datetime.now()
    day = now.strftime("%Y-%m-%d")
    return f"{day} 00:00:00", f"{day} 23:59:59"


def fetch_hand_spans(
    client: TraceClient,
    *,
    open_id: str,
    hole_key: Any,
    center_ms: Optional[int] = None,
    created_at: Any = None,
    pad_minutes: int = 15,
    fallback_open_id: str = "",
    fixed_start: str = "",
    fixed_end: str = "",
) -> dict[str, Any]:
    """Try holeCards variants until spans are found (or all fail)."""
    if fixed_start and fixed_end:
        start, end = fixed_start, fixed_end
    else:
        start, end = time_window_around(center_ms, pad_minutes=pad_minutes, created_at=created_at)
    variants = hole_cards_variants(hole_key)
    errors: list[str] = []
    tried: list[str] = []

    open_ids: list[str] = []
    for oid in (open_id or "", fallback_open_id or ""):
        oid = (oid or "").strip()
        if oid and oid not in open_ids:
            open_ids.append(oid)
    if not open_ids:
        open_ids = [""]

    for oid in open_ids:
        for hc in variants or [""]:
            tried.append(f"{oid or '(no-openId)'}|{hc or '(empty-cards)'}")
            try:
                spans = client.trace_query(
                    open_id=oid,
                    hole_cards=hc,
                    start_time=start,
                    end_time=end,
                )
            except TraceClientError as e:
                errors.append(f"{tried[-1]}: {e}")
                continue
            if spans:
                return {
                    "spans": spans,
                    "open_id": oid,
                    "hole_cards_used": hc,
                    "start_time": start,
                    "end_time": end,
                    "tried": tried,
                    "error": None,
                    "fallback_used": bool(
                        fallback_open_id and oid == fallback_open_id and oid != open_id
                    ),
                    "trace_env": getattr(client, "env_id", DEFAULT_TRACE_ENV),
                    "api": getattr(client, "base_url", ""),
                }

    return {
        "spans": [],
        "open_id": open_id,
        "hole_cards_used": variants[0] if variants else "",
        "start_time": start,
        "end_time": end,
        "tried": tried,
        "error": "; ".join(errors)
        if errors
        else (
            "无匹配 span（已按手牌查询，未使用无 holeCards 兜底）"
            if variants
            else "无匹配 span"
        ),
        "trace_env": getattr(client, "env_id", DEFAULT_TRACE_ENV),
        "api": getattr(client, "base_url", ""),
    }


def extract_msg_keys(spans: list[dict]) -> list[int]:
    keys: list[int] = []
    for s in spans:
        if (s.get("ServiceName") or "") != "texas-holdem-signal-engine":
            continue
        attrs = s.get("SpanAttributes") or {}
        mk = attrs.get("msg_key")
        if mk is None and attrs.get("business.request"):
            try:
                mk = json.loads(attrs["business.request"]).get("msg_key")
            except Exception:
                mk = None
        if mk is None:
            continue
        try:
            keys.append(int(mk))
        except (TypeError, ValueError):
            continue
    seen: set[int] = set()
    out: list[int] = []
    for k in keys:
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out
