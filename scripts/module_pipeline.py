#!/usr/bin/env python3
"""Build module data chain from Trace spans and attribute first failing module.

Anchor: 取「第一次 dealer_change 之后、第二次之前」窗口内的最后一次 hero_action
（一手牌通常只有一次 dealer_change；若命中多次则记为异常并仍按第一次窗口取数），
再按 Trace Viewer 的 1:1 索引连线对齐到各模块，抽取每层的 business.request。
"""

from __future__ import annotations

import copy
import html
import json
from typing import Any, Optional

# Import compare helpers lazily to avoid circular import with compare_gto_requests


MODULES = [
    {
        "id": "signal",
        "title": "信号引擎",
        "service": "texas-holdem-signal-engine",
        "link_span": "hero_action",
        "prefer_spans": ["hero_action", "dealer_change"],
    },
    {
        "id": "state",
        "title": "状态引擎",
        "service": "game-state-engine",
        # Trace Viewer: hero_action[i] → action-validator-hero-doing[i]
        "link_span": "action-validator-hero-doing",
        "prefer_spans": ["action-validator-hero-doing"],
        # 旁路仍保留，便于模块链展示；证据页网关列走 gateway 模块
        "related_spans": ["game-gateway-strategy"],
    },
    {
        "id": "gateway",
        # 证据页「网关」列取 game-gateway-strategy 的 business.request（含 gameInfo）
        "title": "网关",
        "service": "game-state-engine",
        "link_span": "game-gateway-strategy",
        "prefer_spans": ["game-gateway-strategy"],
    },
    {
        "id": "chess",
        "title": "Chess API / GTO",
        "service": "chess-game-api",
        # Trace Viewer: action-validator-hero-doing[i] → gto-validation[i]
        "link_span": "gto-validation",
        "prefer_spans": ["gto-validation", "ws-message"],
    },
]

PAYLOAD_KEYS = (
    "business.request",
    "business.wsRequest",
    "business.result",
    "business.handData",
    "business.response",
)

# 与 trace-viewer.html RULES 对齐的索引连线（用于说明文案）
LINK_RULES = [
    ("hero_action", "action-validator-hero-doing", "hero动作"),
    ("action-validator-hero-doing", "gto-validation", "GTO校验"),
    ("game-gateway-strategy", "strategy.async", "策略请求"),
]


def esc(s: Any) -> str:
    return html.escape("" if s is None else str(s))


def _parse_jsonish(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, (dict, list)):
        return v
    if not isinstance(v, str):
        return v
    text = v.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        return text


def extract_payloads(span: dict) -> dict[str, Any]:
    attrs = span.get("SpanAttributes") or {}
    out: dict[str, Any] = {}
    for k in PAYLOAD_KEYS:
        if k in attrs and attrs[k] not in (None, ""):
            out[k] = _parse_jsonish(attrs[k])
    # also keep flat non-business attrs (short)
    extras = {}
    for k, v in attrs.items():
        if k in PAYLOAD_KEYS:
            continue
        if isinstance(v, (str, int, float, bool)) or v is None:
            extras[k] = v
    if extras:
        out["_attrs"] = extras
    return out


def extract_business_request(span: Optional[dict]) -> Any:
    """Only business.request (parsed JSON when possible)."""
    if not span:
        return None
    attrs = span.get("SpanAttributes") or {}
    if "business.request" not in attrs or attrs["business.request"] in (None, ""):
        return None
    return _parse_jsonish(attrs["business.request"])


def extract_fusion_corrected_data(payload: Any) -> Any:
    """取 payload.fusionCorrectedData（可为对象或 JSON 字符串）。"""
    if payload is None:
        return None
    obj = _parse_jsonish(payload) if isinstance(payload, str) else payload
    if not isinstance(obj, dict):
        return None
    if "fusionCorrectedData" not in obj:
        return None
    return _parse_jsonish(obj.get("fusionCorrectedData"))


def _looks_like_gto_request(obj: Any) -> bool:
    if not isinstance(obj, dict):
        return False
    gi = obj.get("gameInfo")
    if isinstance(gi, dict) and (
        "actionSequence" in gi or "players" in gi or "holeCards" in gi or "communityCards" in gi
    ):
        return True
    if "actionSequence" in obj or "players" in obj:
        return True
    return False


def extract_request_like(payloads: dict[str, Any]) -> Optional[dict]:
    """Best-effort pull a GTO-request-shaped dict from span payloads."""
    for k in PAYLOAD_KEYS:
        obj = payloads.get(k)
        # Chess：仅 business.request.fusionCorrectedData
        if k == "business.request":
            fcd = extract_fusion_corrected_data(obj)
            if fcd is not None and _looks_like_gto_request(fcd):
                return fcd if isinstance(fcd, dict) and "gameInfo" in fcd else (
                    {"gameInfo": fcd} if isinstance(fcd, dict) else None
                )
        if _looks_like_gto_request(obj):
            return obj if "gameInfo" in obj else {"gameInfo": obj}
        if isinstance(obj, dict):
            for nested_key in (
                "fusionCorrectedData",
                "request",
                "data",
                "body",
                "payload",
                "gtoRequest",
                "handData",
            ):
                # 非 business.request 时不把 fusionCorrectedData 当通用入口（避免误用 response）
                if nested_key == "fusionCorrectedData" and k != "business.request":
                    continue
                nested = obj.get(nested_key)
                nested = _parse_jsonish(nested) if isinstance(nested, str) else nested
                if _looks_like_gto_request(nested):
                    return nested if "gameInfo" in nested else {"gameInfo": nested}
            # sometimes request wraps gameInfo one level down
            if isinstance(obj.get("gameInfo"), dict):
                return obj
    return None


def _span_sort_key(s: dict) -> str:
    return str(s.get("Timestamp") or "")


def spans_named(spans: list[dict], *, service: str, name: str) -> list[dict]:
    """Spans of service+SpanName, sorted by Timestamp ascending (viewer order)."""
    out = [
        s
        for s in spans
        if (s.get("ServiceName") or "") == service and (s.get("SpanName") or "") == name
    ]
    out.sort(key=_span_sort_key)
    return out


def nth_span(items: list[dict], idx: int) -> Optional[dict]:
    if idx < 0 or idx >= len(items):
        return None
    return items[idx]


def _span_brief(span: Optional[dict], *, ordinal: Optional[int] = None) -> dict[str, Any]:
    if not span:
        return {}
    attrs = span.get("SpanAttributes") or {}
    out: dict[str, Any] = {
        "span_name": span.get("SpanName"),
        "span_id": span.get("SpanId"),
        "trace_id": span.get("TraceId"),
        "timestamp": span.get("Timestamp"),
        "hole_cards": attrs.get("business.holeCards"),
        "hand_index": attrs.get("business.handIndex"),
        "open_id": attrs.get("business.openId"),
    }
    if ordinal is not None:
        out["ordinal"] = ordinal
    return out


def find_last_hero_action(spans: list[dict]) -> tuple[Optional[dict], int, list[dict]]:
    """Legacy helper: last hero_action overall (kept for callers/tests)."""
    resolved = resolve_hero_anchor(spans)
    return resolved["anchor"], resolved["hero_index"], resolved["heroes"]


def resolve_hero_anchor(
    spans: list[dict],
    *,
    hero_ordinal: Optional[int] = None,
) -> dict[str, Any]:
    """Pick hero_action after the first dealer_change (before the second if any).

    One hand should have a single dealer_change. Multiple hits are abnormal;
    we still take the last hero_action in the first dealer_change's window.

    hero_ordinal: optional 1-based index into the full hero_action list.
    When set, selects that hero instead of the default "last in window".
    Existing callers omit it → behavior unchanged.
    """
    heroes = spans_named(
        spans,
        service="texas-holdem-signal-engine",
        name="hero_action",
    )
    dealers = spans_named(
        spans,
        service="texas-holdem-signal-engine",
        name="dealer_change",
    )
    warnings: list[dict[str, Any]] = []
    dealer_n = len(dealers)
    if dealer_n > 1:
        warnings.append(
            {
                "type": "multi_dealer_change",
                "count": dealer_n,
                "message": (
                    f"同一查询结果命中 {dealer_n} 次 dealer_change"
                    "（一手牌通常只有 1 次）"
                ),
            }
        )

    anchor: Optional[dict] = None
    mode = "none"
    window_start = None
    window_end = None
    window_hero_n = 0

    if hero_ordinal is not None:
        try:
            ord_i = int(hero_ordinal)
        except Exception:
            ord_i = -1
        if 1 <= ord_i <= len(heroes):
            anchor = heroes[ord_i - 1]
            mode = f"nth_hero_{ord_i}"
        elif heroes:
            warnings.append(
                {
                    "type": "hero_ordinal_oob",
                    "requested": ord_i,
                    "hero_count": len(heroes),
                    "message": f"hero_ordinal={ord_i} 超出 hero_action 范围（共 {len(heroes)}）",
                }
            )
            mode = "nth_hero_oob"
        # still compute window stats for diagnostics
        if dealers and heroes:
            first_dc = dealers[0]
            t0 = _span_sort_key(first_dc)
            t1 = _span_sort_key(dealers[1]) if dealer_n > 1 else None
            window_start = first_dc.get("Timestamp")
            window_end = dealers[1].get("Timestamp") if dealer_n > 1 else None
            window_heroes = [
                h
                for h in heroes
                if _span_sort_key(h) >= t0 and (t1 is None or _span_sort_key(h) < t1)
            ]
            if not window_heroes:
                window_heroes = [h for h in heroes if _span_sort_key(h) >= t0]
            window_hero_n = len(window_heroes)
    elif dealers and heroes:
        first_dc = dealers[0]
        t0 = _span_sort_key(first_dc)
        t1 = _span_sort_key(dealers[1]) if dealer_n > 1 else None
        window_start = first_dc.get("Timestamp")
        window_end = dealers[1].get("Timestamp") if dealer_n > 1 else None
        window_heroes = [
            h
            for h in heroes
            if _span_sort_key(h) >= t0 and (t1 is None or _span_sort_key(h) < t1)
        ]
        if not window_heroes:
            # 窗口内没有：退化为「第一次 dealer_change 之后」的全部 hero
            window_heroes = [h for h in heroes if _span_sort_key(h) >= t0]
        window_hero_n = len(window_heroes)
        if window_heroes:
            anchor = window_heroes[-1]
            mode = "first_dealer_change_last_hero"
    elif heroes:
        anchor = heroes[-1]
        mode = "last_hero_action"

    idx = -1
    if anchor is not None:
        for i, h in enumerate(heroes):
            if h is anchor or (
                h.get("SpanId") and h.get("SpanId") == anchor.get("SpanId")
            ):
                idx = i
                break
        if idx < 0:
            idx = len(heroes) - 1
            anchor = heroes[idx]
            mode = "last_hero_action"

    return {
        "anchor": anchor,
        "hero_index": idx,
        "heroes": heroes,
        "dealers": dealers,
        "dealer_change_n": dealer_n,
        "dealer_changes": [
            _span_brief(d, ordinal=i + 1) for i, d in enumerate(dealers)
        ],
        "warnings": warnings,
        "anchor_pick_mode": mode,
        "window_start": window_start,
        "window_end": window_end,
        "window_hero_n": window_hero_n,
        "first_dealer_change": _span_brief(dealers[0], ordinal=1) if dealers else None,
        "chosen_hero": _span_brief(anchor) if anchor else None,
    }


def resolve_linked_module_spans(
    spans: list[dict],
    *,
    hero_ordinal: Optional[int] = None,
) -> dict[str, Any]:
    """Anchor on first-dealer_change window's last hero_action; 1:1 index link.

    Mirrors trace-viewer RULES index pairing among typed span lists.
    Optional hero_ordinal (1-based) selects a specific hero_action.
    """
    picked = resolve_hero_anchor(spans, hero_ordinal=hero_ordinal)
    anchor = picked["anchor"]
    idx = picked["hero_index"]
    heroes = picked["heroes"]
    result: dict[str, Any] = {
        "anchor_ok": anchor is not None,
        "hero_index": idx,
        "hero_count": len(heroes),
        "anchor": anchor,
        "by_module": {},
        "dealer_change_n": picked["dealer_change_n"],
        "dealer_changes": picked["dealer_changes"],
        "warnings": picked["warnings"],
        "anchor_pick_mode": picked["anchor_pick_mode"],
        "window_start": picked["window_start"],
        "window_end": picked["window_end"],
        "window_hero_n": picked["window_hero_n"],
        "first_dealer_change": picked["first_dealer_change"],
        "chosen_hero": picked["chosen_hero"],
    }
    if anchor is None:
        return result

    attrs = anchor.get("SpanAttributes") or {}
    result["anchor_meta"] = {
        "span_id": anchor.get("SpanId"),
        "trace_id": anchor.get("TraceId"),
        "timestamp": anchor.get("Timestamp"),
        "hole_cards": attrs.get("business.holeCards"),
        "hand_index": attrs.get("business.handIndex"),
        "open_id": attrs.get("business.openId"),
        "msg_key": None,
    }
    br = extract_business_request(anchor)
    if isinstance(br, dict) and br.get("msg_key") is not None:
        result["anchor_meta"]["msg_key"] = br.get("msg_key")

    for mod in MODULES:
        link_name = mod.get("link_span") or (mod.get("prefer_spans") or [None])[0]
        typed = spans_named(spans, service=mod["service"], name=link_name) if link_name else []
        primary = nth_span(typed, idx)
        related = []
        for rel_name in mod.get("related_spans") or []:
            rel_typed = spans_named(spans, service=mod["service"], name=rel_name)
            rel_span = nth_span(rel_typed, idx)
            if rel_span:
                related.append(
                    {
                        "span_name": rel_name,
                        "span": rel_span,
                        "business_request": extract_business_request(rel_span),
                    }
                )
        result["by_module"][mod["id"]] = {
            "span_name": link_name,
            "typed_count": len(typed),
            "span": primary,
            "business_request": extract_business_request(primary),
            "related": related,
            "link_ok": primary is not None,
        }
    return result


def pick_module_span(spans: list[dict], module: dict) -> Optional[dict]:
    """Fallback picker when no hero_action anchor exists."""
    svc = module["service"]
    mine = [s for s in spans if (s.get("ServiceName") or "") == svc]
    if not mine:
        return None
    prefer = module.get("prefer_spans") or []
    for name in prefer:
        hits = [s for s in mine if (s.get("SpanName") or "") == name]
        if hits:
            # prefer ones with request-like payload
            scored = []
            for s in hits:
                payloads = extract_payloads(s)
                req = extract_request_like(payloads)
                scored.append((1 if req else 0, _span_sort_key(s), s))
            scored.sort(key=lambda x: (-x[0], x[1]))
            return scored[0][2]
    # any span on this service with request-like payload
    scored = []
    for s in mine:
        payloads = extract_payloads(s)
        req = extract_request_like(payloads)
        scored.append((1 if req else 0, _span_sort_key(s), s))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return scored[0][2]


def _gto_from_business_request(business_request: Any) -> Optional[dict]:
    """Normalize business.request into GTO-request-shaped dict when possible."""
    if business_request is None:
        return None
    payloads = {"business.request": business_request}
    return extract_request_like(payloads)


def snapshot_summary(req: Optional[dict]) -> dict[str, Any]:
    if not req or not isinstance(req, dict):
        return {}
    gi = req.get("gameInfo") or {}
    if not isinstance(gi, dict):
        # signal-style CV payload
        if "parameters" in req or "msg_key" in req:
            ev = ((req.get("parameters") or {}) if isinstance(req.get("parameters"), dict) else {}).get("events") or []
            ev0 = ev[0] if isinstance(ev, list) and ev else None
            return {
                "msg_key": req.get("msg_key"),
                "event_type": (ev0 or {}).get("event_type") if isinstance(ev0, dict) else None,
                "raw_keys": list(req.keys())[:20],
            }
        return {"raw_keys": list(req.keys())[:20]}
    acts = gi.get("actionSequence") or []
    players = gi.get("players") or []
    hero = None
    for p in players if isinstance(players, list) else []:
        if isinstance(p, dict) and p.get("seat") in ("P0", 0, "0"):
            hero = {"seat": p.get("seat"), "holeCards": p.get("holeCards"), "initChips": p.get("initChips")}
            break
    return {
        "smallBlind": gi.get("smallBlind"),
        "bigBlind": gi.get("bigBlind"),
        "ante": gi.get("ante"),
        "communityCards": gi.get("communityCards"),
        "action_n": len(acts) if isinstance(acts, list) else None,
        "player_n": len(players) if isinstance(players, list) else None,
        "hero": hero,
        "last_actions": acts[-3:] if isinstance(acts, list) else None,
    }


def normalize_module_req(req: Optional[dict]) -> Optional[dict]:
    from compare_gto_requests import strip_meta, is_valid_request

    if not req or not isinstance(req, dict):
        return None
    if not is_valid_request(req) and not (req.get("gameInfo") or {}).get("actionSequence"):
        # still try strip_meta if gameInfo exists
        if "gameInfo" not in req:
            return None
    try:
        return strip_meta(copy.deepcopy(req))
    except Exception:
        return copy.deepcopy(req)


def diff_vs(gt_norm: Optional[dict], mod_norm: Optional[dict]) -> list[dict]:
    from compare_gto_requests import deep_diff, filter_ignorable

    if not gt_norm or not mod_norm:
        return []
    return filter_ignorable(deep_diff(gt_norm, mod_norm))


def _empty_layer(mod: dict, *, svc_count: int = 0) -> dict:
    return {
        "id": mod["id"],
        "title": mod["title"],
        "service": mod["service"],
        "status": "missing",
        "span_count": svc_count,
        "span_name": None,
        "timestamp": None,
        "span_id": None,
        "trace_id": None,
        "duration": None,
        "span_status": None,
        "hand_index": None,
        "open_id": None,
        "hole_cards": None,
        "payloads": {},
        "business_request": None,
        "fusion_corrected_data": None,
        "request": None,
        "norm": None,
        "summary": {},
        "vs_gt_diffs": [],
        "vs_prev_diffs": [],
        "vs_gt_n": 0,
        "vs_prev_n": 0,
        "role": None,
        "related": [],
        "link_ok": False,
    }


def _fmt_duration_ms(duration: Any) -> Optional[str]:
    """Span Duration → viewer-style '0.0ms'."""
    if duration is None or duration == "":
        return None
    try:
        # common: microseconds int, or already ms float/str
        v = float(duration)
        # heuristic: large ints are µs
        if v >= 1000 and float(duration) == int(float(duration)) and v >= 10_000:
            v = v / 1000.0
        return f"{v:.1f}ms"
    except Exception:
        s = str(duration).strip()
        if not s:
            return None
        if s.lower().endswith("ms"):
            return s
        return s


def _fmt_span_status(status_code: Any) -> Optional[str]:
    """Align Trace Viewer Status label (Unset / Ok / Error…)."""
    if status_code is None or status_code == "":
        return None
    raw = str(status_code).strip()
    mapping = {
        "0": "Unset",
        "1": "Ok",
        "2": "Error",
        "UNSET": "Unset",
        "OK": "Ok",
        "ERROR": "Error",
        "STATUS_CODE_UNSET": "Unset",
        "STATUS_CODE_OK": "Ok",
        "STATUS_CODE_ERROR": "Error",
    }
    return mapping.get(raw, mapping.get(raw.upper(), raw))


def _span_business_meta(span: Optional[dict], br: Any = None) -> dict[str, Any]:
    """Trace Viewer 基本信息 + 业务属性字段（无则 None）."""
    empty = {
        "span_name": None,
        "service": None,
        "duration": None,
        "span_status": None,
        "span_id": None,
        "trace_id": None,
        "timestamp": None,
        "hand_index": None,
        "open_id": None,
        "hole_cards": None,
    }
    if not span:
        return empty
    attrs = span.get("SpanAttributes") or {}
    hand_index = attrs.get("business.handIndex")
    if hand_index is None and isinstance(br, dict) and br.get("msg_key") is not None:
        hand_index = br.get("msg_key")
    return {
        "span_name": span.get("SpanName"),
        "service": span.get("ServiceName"),
        "duration": _fmt_duration_ms(span.get("Duration")),
        "span_status": _fmt_span_status(span.get("StatusCode")),
        "span_id": span.get("SpanId"),
        "trace_id": span.get("TraceId"),
        "timestamp": span.get("Timestamp"),
        "hand_index": hand_index,
        "open_id": attrs.get("business.openId"),
        "hole_cards": attrs.get("business.holeCards"),
    }


def _layer_from_span(
    mod: dict,
    span: Optional[dict],
    *,
    svc_count: int,
    business_request: Any = None,
    related: Optional[list] = None,
    link_ok: bool = False,
    gt_norm: Optional[dict] = None,
) -> dict:
    if not span:
        layer = _empty_layer(mod, svc_count=svc_count)
        layer["link_ok"] = link_ok
        return layer

    payloads = extract_payloads(span)
    br = business_request if business_request is not None else extract_business_request(span)
    # Chess 只认 business.request.fusionCorrectedData
    fcd = extract_fusion_corrected_data(br) if mod.get("id") == "chess" else None
    # Prefer GTO-shaped view from business.request; fall back to any payload
    req = _gto_from_business_request(br) if br is not None else extract_request_like(payloads)
    if mod.get("id") == "chess":
        # Chess 列展示/比对只用 fusionCorrectedData；没有则为空
        if fcd is not None and _looks_like_gto_request(fcd):
            req = fcd if isinstance(fcd, dict) and "gameInfo" in fcd else {"gameInfo": fcd}
        else:
            req = fcd if isinstance(fcd, dict) else None
    # If no GTO shape, still keep raw business.request as request for display/summary
    if req is None and isinstance(br, dict) and mod.get("id") != "chess":
        req = br
    norm = normalize_module_req(req) if req and _looks_like_gto_request(req) else None
    vs_gt = diff_vs(gt_norm, norm) if (gt_norm and norm) else []
    related_out = []
    for rel in related or []:
        rel_br = rel.get("business_request")
        rel_req = None
        if isinstance(rel_br, dict):
            rel_req = _gto_from_business_request(rel_br) or rel_br
        rel_span = rel.get("span") or {}
        rel_meta = _span_business_meta(rel_span if rel_span else None, rel_br)
        related_out.append(
            {
                "span_name": rel.get("span_name") or rel_meta.get("span_name"),
                "service": rel_meta.get("service"),
                "span_id": rel_meta.get("span_id"),
                "trace_id": rel_meta.get("trace_id"),
                "timestamp": rel_meta.get("timestamp"),
                "duration": rel_meta.get("duration"),
                "span_status": rel_meta.get("span_status"),
                "hand_index": rel_meta.get("hand_index"),
                "open_id": rel_meta.get("open_id"),
                "hole_cards": rel_meta.get("hole_cards"),
                "business_request": rel_br,
                "summary": snapshot_summary(rel_req) if isinstance(rel_req, dict) else {},
            }
        )
    meta = _span_business_meta(span, br)
    return {
        "id": mod["id"],
        "title": mod["title"],
        "service": meta.get("service") or mod["service"],
        "status": "ok" if not vs_gt else "diff",
        "span_count": svc_count,
        "span_name": meta["span_name"],
        "timestamp": meta["timestamp"],
        "span_id": meta["span_id"],
        "trace_id": meta["trace_id"],
        "duration": meta["duration"],
        "span_status": meta["span_status"],
        "hand_index": meta["hand_index"],
        "open_id": meta["open_id"],
        "hole_cards": meta["hole_cards"],
        "status_code": span.get("StatusCode"),
        "payloads": payloads,
        "business_request": br,
        "fusion_corrected_data": fcd,
        "request": req,
        "norm": norm,
        "summary": snapshot_summary(req if isinstance(req, dict) else None),
        "vs_gt_diffs": vs_gt[:40],
        "vs_prev_diffs": [],
        "vs_gt_n": len(vs_gt),
        "vs_prev_n": 0,
        "role": None,
        "related": related_out,
        "link_ok": link_ok,
    }


def build_module_chain(
    spans: list[dict],
    *,
    gt_norm: Optional[dict] = None,
    fetch_meta: Optional[dict] = None,
    hero_ordinal: Optional[int] = None,
) -> dict[str, Any]:
    """Return chain layers + root-cause attribution.

    Prefer last-hero_action index linking; fall back to prefer_spans picker.
    hero_ordinal: optional 1-based hero_action index (decision-point compare).
    """
    from compare_gto_requests import deep_diff, filter_ignorable

    linked = resolve_linked_module_spans(spans, hero_ordinal=hero_ordinal)
    layers: list[dict] = []
    used_anchor = bool(linked.get("anchor_ok"))

    for mod in MODULES:
        svc_count = sum(1 for s in spans if (s.get("ServiceName") or "") == mod["service"])
        if used_anchor:
            info = (linked.get("by_module") or {}).get(mod["id"]) or {}
            span = info.get("span")
            layer = _layer_from_span(
                mod,
                span,
                svc_count=svc_count,
                business_request=info.get("business_request"),
                related=info.get("related"),
                link_ok=bool(info.get("link_ok")),
                gt_norm=gt_norm,
            )
            layers.append(layer)
        else:
            span = pick_module_span(spans, mod)
            layer = _layer_from_span(
                mod,
                span,
                svc_count=svc_count,
                link_ok=bool(span),
                gt_norm=gt_norm,
            )
            layers.append(layer)

    # adjacent diffs (GTO-comparable norms only)
    prev_norm = None
    for layer in layers:
        if layer["norm"] and prev_norm:
            vd = filter_ignorable(deep_diff(prev_norm, layer["norm"]))
            layer["vs_prev_diffs"] = vd[:40]
            layer["vs_prev_n"] = len(vd)
        if layer["norm"]:
            prev_norm = layer["norm"]

    # attribution: first layer that has comparable norm and differs from GT
    root_id = None
    root_title = None
    root_detail = ""
    if gt_norm:
        for layer in layers:
            if layer["status"] == "missing":
                continue
            if not layer["norm"]:
                layer["role"] = "no_comparable_payload"
                continue
            if layer["vs_gt_n"] > 0:
                root_id = layer["id"]
                root_title = layer["title"]
                d0 = (layer["vs_gt_diffs"] or [{}])[0]
                root_detail = f"{d0.get('path')}: 真值={d0.get('left')} → 本层={d0.get('right')}"
                layer["role"] = "root_cause_candidate"
                layer["status"] = "root"
                idx = layers.index(layer)
                for later in layers[idx + 1 :]:
                    if later["status"] != "missing":
                        later["role"] = "downstream_contaminated"
                        if later["status"] == "ok":
                            later["status"] = "contaminated"
                break
            layer["role"] = "matches_gt"
            layer["status"] = "ok"

    note = None
    pick_mode = linked.get("anchor_pick_mode") or ""
    dealer_n = int(linked.get("dealer_change_n") or 0)
    if used_anchor:
        meta = linked.get("anchor_meta") or {}
        if str(pick_mode).startswith("nth_hero_"):
            note_bits = [
                f"锚点=第{int(linked.get('hero_index') or 0) + 1}次 hero_action"
                f"[{linked.get('hero_index')}]/{linked.get('hero_count')}",
            ]
        elif pick_mode == "first_dealer_change_last_hero":
            note_bits = [
                f"锚点=第1次 dealer_change 后最后一次 hero_action"
                f"[{linked.get('hero_index')}]/{linked.get('hero_count')}",
            ]
        else:
            note_bits = [
                f"锚点=最后一次 hero_action[{linked.get('hero_index')}]"
                f"/{linked.get('hero_count')}",
            ]
        if dealer_n:
            note_bits.append(f"dealer_change×{dealer_n}")
        if meta.get("timestamp"):
            note_bits.append(str(meta["timestamp"])[:19])
        if meta.get("msg_key") is not None:
            note_bits.append(f"msg_key={meta['msg_key']}")
        note = " · ".join(note_bits)
    if gt_norm and root_id is None:
        has_any_norm = any(l.get("norm") for l in layers)
        if not has_any_norm and spans:
            extra = "有 span，但未能抽出可与真值对比的 gameInfo 报文；请点开各层 business.request。"
            note = f"{note}；{extra}" if note else extra
        elif has_any_norm and not used_anchor:
            note = "各模块可对比快照相对真值未见偏离（或仅元数据差异）；若最终请求仍错，可能在导出/版本口径。"

    if not used_anchor and spans:
        fallback_note = "未找到 hero_action，已回退为各模块 prefer_spans 挑选。"
        note = f"{fallback_note} {note}" if note else fallback_note

    if used_anchor:
        if str(pick_mode).startswith("nth_hero_"):
            anchor_mode = pick_mode
        elif pick_mode == "first_dealer_change_last_hero":
            anchor_mode = "first_dealer_change_last_hero"
        else:
            anchor_mode = "last_hero_action"
    else:
        anchor_mode = "prefer_spans_fallback"

    services = sorted({(s.get("ServiceName") or "") for s in spans if s.get("ServiceName")})
    return {
        "ok": True,
        "span_n": len(spans),
        "services": services,
        "layers": layers,
        "root_cause_module": root_id,
        "root_cause_title": root_title,
        "root_cause_detail": root_detail,
        "note": note,
        "fetch": fetch_meta or {},
        "anchor": linked.get("anchor_meta"),
        "hero_index": linked.get("hero_index"),
        "hero_count": linked.get("hero_count"),
        "anchor_mode": anchor_mode,
        "dealer_change_n": dealer_n,
        "dealer_changes": linked.get("dealer_changes") or [],
        "anchor_warnings": linked.get("warnings") or [],
        "first_dealer_change": linked.get("first_dealer_change"),
        "chosen_hero": linked.get("chosen_hero"),
        "window_start": linked.get("window_start"),
        "window_end": linked.get("window_end"),
    }


def empty_chain(reason: str, fetch_meta: Optional[dict] = None) -> dict[str, Any]:
    layers = [_empty_layer(m) for m in MODULES]
    return {
        "ok": False,
        "span_n": 0,
        "services": [],
        "layers": layers,
        "root_cause_module": None,
        "root_cause_title": None,
        "root_cause_detail": "",
        "note": reason,
        "fetch": fetch_meta or {},
        "anchor": None,
        "hero_index": -1,
        "hero_count": 0,
        "anchor_mode": None,
        "dealer_change_n": 0,
        "dealer_changes": [],
        "anchor_warnings": [],
        "first_dealer_change": None,
        "chosen_hero": None,
        "window_start": None,
        "window_end": None,
    }


def analyze_hand_trace(
    spans: list[dict],
    *,
    gt_norm: Optional[dict] = None,
    fetch_meta: Optional[dict] = None,
    hero_ordinal: Optional[int] = None,
) -> dict[str, Any]:
    if not spans:
        return empty_chain(
            (fetch_meta or {}).get("error") or "未拉到 Trace span",
            fetch_meta=fetch_meta,
        )
    return build_module_chain(
        spans,
        gt_norm=gt_norm,
        fetch_meta=fetch_meta,
        hero_ordinal=hero_ordinal,
    )


def _status_badge(status: str) -> str:
    mapping = {
        "ok": ('ok', '与真值一致'),
        "diff": ('bad', '相对真值有差异'),
        "root": ('bad', '相对真值有差异'),
        "contaminated": ('warn', '可能被上游污染'),
        "missing": ('muted', '无数据'),
    }
    cls, label = mapping.get(status, ('muted', status or '—'))
    return f'<span class="badge {cls}">{esc(label)}</span>'


def _summary_dl(summary: dict) -> str:
    if not summary:
        return '<div class="mod-empty">无可提取的快照摘要</div>'
    rows = []
    for k in ("msg_key", "event_type", "smallBlind", "bigBlind", "ante", "communityCards", "action_n", "player_n"):
        if k in summary and summary[k] is not None:
            rows.append(f"<tr><th>{esc(k)}</th><td><code>{esc(json.dumps(summary[k], ensure_ascii=False))}</code></td></tr>")
    hero = summary.get("hero")
    if hero:
        rows.append(f"<tr><th>hero</th><td><code>{esc(json.dumps(hero, ensure_ascii=False))}</code></td></tr>")
    lasts = summary.get("last_actions")
    if lasts:
        rows.append(f"<tr><th>末几行动</th><td><code>{esc(json.dumps(lasts, ensure_ascii=False))}</code></td></tr>")
    return f'<table class="mod-sum">{"".join(rows)}</table>'


def _diff_preview(diffs: list[dict], limit: int = 5) -> str:
    if not diffs:
        return ""
    items = []
    for d in diffs[:limit]:
        items.append(
            f"<li><code>{esc(d.get('path'))}</code> "
            f"真/上=<code>{esc(d.get('left'))}</code> → "
            f"本=<code>{esc(d.get('right'))}</code></li>"
        )
    more = f"<li>…另有 {len(diffs) - limit} 处</li>" if len(diffs) > limit else ""
    return f'<ul class="mod-diffs">{"".join(items)}{more}</ul>'


def _json_pre(obj: Any, *, limit: int = 200000) -> str:
    if obj is None:
        return "（无 business.request）"
    try:
        text = json.dumps(obj, ensure_ascii=False, indent=2)
    except Exception:
        text = str(obj)
    if len(text) > limit:
        text = text[:limit] + "\n…(truncated)"
    return esc(text)


def render_module_chain(chain: Optional[dict]) -> str:
    """HTML block for hand evidence page."""
    if not chain:
        return (
            '<section class="mod-chain">'
            '<h2>模块数据链</h2>'
            '<div class="meta-box">未接入 Trace API（传入 <code>--trace-api</code> 后生成）。</div>'
            "</section>"
        )

    root_title = chain.get("root_cause_title")
    root_detail = chain.get("root_cause_detail") or ""
    note = chain.get("note") or ""
    fetch = chain.get("fetch") or {}
    anchor = chain.get("anchor") or {}
    mode = chain.get("anchor_mode") or ""

    if root_title:
        attrib = (
            f'<div class="mod-attrib root">'
            f'<b>归因：</b>{esc(root_title)}'
            f'{(" · " + esc(root_detail)) if root_detail else ""}'
            f"</div>"
        )
    elif chain.get("ok"):
        attrib = f'<div class="mod-attrib ok"><b>归因：</b>未定位到相对真值的首次偏离模块。{esc(note)}</div>'
    else:
        attrib = f'<div class="mod-attrib muted"><b>归因：</b>{esc(note or "无 Trace 数据")}</div>'

    meta_bits = [
        f"span {chain.get('span_n', 0)} 条",
        f"服务 {len(chain.get('services') or [])} 个",
    ]
    if mode:
        meta_bits.append(f"锚点模式={mode}")
    if chain.get("hero_count"):
        meta_bits.append(
            f"hero_action {int(chain.get('hero_index', -1)) + 1}/{chain.get('hero_count')}"
        )
    if fetch.get("hole_cards_used") is not None:
        meta_bits.append(f"holeCards={fetch.get('hole_cards_used')!s}")
    if fetch.get("start_time"):
        meta_bits.append(f"{fetch.get('start_time')} ~ {fetch.get('end_time')}")

    anchor_box = ""
    if anchor:
        if mode == "first_dealer_change_last_hero":
            anchor_title = "第1次 dealer_change 后最后一次 hero_action"
        else:
            anchor_title = "最后一次 hero_action"
        warn_html = ""
        dealer_n = int(chain.get("dealer_change_n") or 0)
        if dealer_n > 1:
            warn_html = (
                f'<div class="mod-anchor-hint" style="color:#92400e">'
                f"异常：命中 {dealer_n} 次 dealer_change（一手通常 1 次），"
                f"已取第 1 次窗口内最后一次 hero_action"
                f"</div>"
            )
        anchor_box = (
            '<div class="mod-anchor">'
            f"<b>{esc(anchor_title)}</b>"
            f" · ts=<code>{esc(anchor.get('timestamp'))}</code>"
            f" · holeCards=<code>{esc(anchor.get('hole_cards'))}</code>"
            f" · handIndex=<code>{esc(anchor.get('hand_index'))}</code>"
            f" · msg_key=<code>{esc(anchor.get('msg_key'))}</code>"
            f" · SpanId=<code>{esc(anchor.get('span_id'))}</code>"
            f"{warn_html}"
            "<div class=\"mod-anchor-hint\">"
            "连线规则：hero_action → action-validator-hero-doing → gto-validation；"
            "game-gateway-strategy → strategy.async（同索引）"
            "</div></div>"
        )

    cards = []
    for layer in chain.get("layers") or []:
        br = layer.get("business_request")
        br_json = _json_pre(br)
        has_br = br is not None

        related_html = ""
        for rel in layer.get("related") or []:
            related_html += f"""
<details class="mod-related">
  <summary>旁路 · <code>{esc(rel.get('span_name'))}</code> 的 business.request</summary>
  {_summary_dl(rel.get('summary') or {})}
  <pre class="mod-pre">{_json_pre(rel.get('business_request'))}</pre>
</details>
"""

        prev_html = _diff_preview(layer.get("vs_prev_diffs") or [])
        gt_html = _diff_preview(layer.get("vs_gt_diffs") or [])
        open_attr = " open" if layer.get("role") == "root_cause_candidate" or layer.get("id") == "signal" else ""
        link_flag = "" if layer.get("link_ok") else ' <span class="badge muted">未对齐到锚点索引</span>'
        br_flag = "" if has_br else ' <span class="badge muted">无 business.request</span>'

        cards.append(
            f"""
<details class="mod-card status-{esc(layer.get('status'))}"{open_attr}>
  <summary>
    <span class="mod-title">{esc(layer.get("title"))}</span>
    {_status_badge(layer.get("status") or "missing")}
    {link_flag}{br_flag}
    <span class="mod-meta">{esc(layer.get("span_name") or "—")} · {esc(layer.get("span_count"))} spans</span>
  </summary>
  <div class="mod-body">
    <div class="mod-kv">Timestamp: <code>{esc(layer.get("timestamp"))}</code>
      · SpanId: <code>{esc(layer.get("span_id"))}</code>
      · vs真值差异: <b>{esc(layer.get("vs_gt_n"))}</b>
      · vs上一层: <b>{esc(layer.get("vs_prev_n"))}</b>
    </div>
    {_summary_dl(layer.get("summary") or {})}
    {f'<div class="pane-label">相对真值</div>{gt_html}' if gt_html else ""}
    {f'<div class="pane-label">相对上一层</div>{prev_html}' if prev_html else ""}
    <div class="pane-label">business.request</div>
    <pre class="mod-pre">{br_json}</pre>
    {related_html}
  </div>
</details>
"""
        )

    return f"""
<section class="mod-chain">
  <h2>模块数据链</h2>
  <div class="sub">来自 Trace Viewer API · 以最后一次 hero_action 为锚点抽取各模块 business.request · {" · ".join(esc(x) for x in meta_bits)}</div>
  {anchor_box}
  {attrib}
  <div class="mod-flow">{"".join(cards)}</div>
</section>
"""


MODULE_CHAIN_CSS = """
.mod-chain { margin: 24px 0 28px; }
.mod-attrib {
  padding: 12px 14px; border-radius: 10px; margin: 10px 0 14px;
  border: 1px solid #e7e0d5; background: #fffdf9; font-size: 14px;
}
.mod-attrib.root { border-color: #fecdd3; background: #fff1f2; color: #9f1239; }
.mod-attrib.ok { border-color: #bbf7d0; background: #f0fdf4; color: #166534; }
.mod-attrib.muted { color: #78716c; }
.mod-anchor {
  padding: 12px 14px; border-radius: 10px; margin: 10px 0 14px;
  border: 1px solid #bfdbfe; background: #eff6ff; font-size: 13px; color: #1e3a8a;
}
.mod-anchor-hint { margin-top: 6px; font-size: 12px; color: #64748b; }
.mod-flow { display: flex; flex-direction: column; gap: 8px; }
.mod-card {
  border: 1px solid #e7e0d5; border-radius: 10px; background: #fffdf9; overflow: hidden;
}
.mod-card.status-root { border-color: #fb7185; box-shadow: 0 0 0 1px rgba(159,18,57,.12); }
.mod-card > summary {
  list-style: none; cursor: pointer; display: flex; flex-wrap: wrap; align-items: center;
  gap: 8px 12px; padding: 10px 12px; background: #faf6f0; user-select: none;
}
.mod-card > summary::-webkit-details-marker { display: none; }
.mod-title { font-weight: 700; color: #1c1917; }
.mod-meta { font-size: 12px; color: #78716c; margin-left: auto; }
.mod-body { padding: 10px 12px 12px; border-top: 1px solid #e7e0d5; }
.mod-kv { font-size: 12px; color: #78716c; margin-bottom: 8px; }
.mod-sum { width: 100%; border-collapse: collapse; font-size: 12px; margin-bottom: 8px; }
.mod-sum th, .mod-sum td { text-align: left; padding: 4px 6px; border-bottom: 1px solid #f0ebe3; vertical-align: top; }
.mod-sum th { width: 110px; color: #78716c; font-weight: 600; }
.mod-diffs { margin: 4px 0 10px 18px; font-size: 12px; }
.mod-empty { font-size: 12px; color: #78716c; margin: 6px 0; }
.mod-related { margin-top: 10px; border: 1px dashed #d6d3d1; border-radius: 8px; padding: 6px 8px; }
.mod-related summary { cursor: pointer; font-size: 12px; color: #0f766e; }
.mod-raw { margin-top: 6px; }
.mod-raw summary { cursor: pointer; font-size: 12px; color: #0f766e; }
.mod-pre {
  max-height: 360px; overflow: auto; background: #1c1917; color: #f5f5f4;
  padding: 10px; border-radius: 8px; font-size: 11px; line-height: 1.4;
}
"""


def chain_to_sidecar(chain: dict) -> dict:
    """JSON-serializable sidecar (keep business.request per layer)."""
    layers_out = []
    for layer in chain.get("layers") or []:
        layers_out.append(
            {
                "id": layer.get("id"),
                "title": layer.get("title"),
                "service": layer.get("service"),
                "status": layer.get("status"),
                "role": layer.get("role"),
                "span_count": layer.get("span_count"),
                "span_name": layer.get("span_name"),
                "timestamp": layer.get("timestamp"),
                "span_id": layer.get("span_id"),
                "trace_id": layer.get("trace_id"),
                "duration": layer.get("duration"),
                "span_status": layer.get("span_status"),
                "hand_index": layer.get("hand_index"),
                "open_id": layer.get("open_id"),
                "hole_cards": layer.get("hole_cards"),
                "link_ok": layer.get("link_ok"),
                "summary": layer.get("summary"),
                "vs_gt_n": layer.get("vs_gt_n"),
                "vs_prev_n": layer.get("vs_prev_n"),
                "vs_gt_diffs": layer.get("vs_gt_diffs"),
                "vs_prev_diffs": layer.get("vs_prev_diffs"),
                "business_request": layer.get("business_request"),
                "fusion_corrected_data": layer.get("fusion_corrected_data"),
                "request": layer.get("request"),
                "related": [
                    {
                        "span_name": r.get("span_name"),
                        "service": r.get("service"),
                        "span_id": r.get("span_id"),
                        "trace_id": r.get("trace_id"),
                        "timestamp": r.get("timestamp"),
                        "duration": r.get("duration"),
                        "span_status": r.get("span_status"),
                        "hand_index": r.get("hand_index"),
                        "open_id": r.get("open_id"),
                        "hole_cards": r.get("hole_cards"),
                        "business_request": r.get("business_request"),
                        "summary": r.get("summary"),
                    }
                    for r in (layer.get("related") or [])
                ],
                "payload_keys": list((layer.get("payloads") or {}).keys()),
            }
        )
    return {
        "ok": chain.get("ok"),
        "span_n": chain.get("span_n"),
        "services": chain.get("services"),
        "root_cause_module": chain.get("root_cause_module"),
        "root_cause_title": chain.get("root_cause_title"),
        "root_cause_detail": chain.get("root_cause_detail"),
        "note": chain.get("note"),
        "fetch": {
            k: v
            for k, v in (chain.get("fetch") or {}).items()
            if k != "spans"  # spans already huge; layers hold extracted requests
        },
        "query": chain.get("query"),
        "anchor": chain.get("anchor"),
        "hero_index": chain.get("hero_index"),
        "hero_count": chain.get("hero_count"),
        "anchor_mode": chain.get("anchor_mode"),
        "layers": layers_out,
    }
