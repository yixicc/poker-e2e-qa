#!/usr/bin/env python3
"""Cross-module path=value extraction for evidence cards.

信号引擎 hand_history 行: [seat, status, chips, action, amount, pot] → 下标 0–5
  定位: 街 → seat → 该座位本街第 N 次行动（与真值 actionSequence 对齐）
  取 amount: 同一行 [4]；取 actionType: 同一行 [3]
  events[i] 优先带 hand_history 的 hero_action（例: events[1]）

Blinds on signal only via table.pub_infos.table_show_info.value when relevant.
GTO-shaped payloads (真值 / 系统最终 / 状态 / 网关 / Chess) use gameInfo.actionSequence，
同样按「街 → seat → 本街该座位第 N 次」定位，再取 action / amount。
"""

from __future__ import annotations

import json
from typing import Any, Optional

STREET_TO_HH = {
    "PREFLOP": "preflop",
    "PRE_FLOP": "preflop",
    "FLOP": "flop",
    "TURN": "turn",
    "RIVER": "river",
}
STREET_ALIASES = {
    "PREFLOP": {"PREFLOP", "PRE_FLOP"},
    "PRE_FLOP": {"PREFLOP", "PRE_FLOP"},
    "FLOP": {"FLOP"},
    "TURN": {"TURN"},
    "RIVER": {"RIVER"},
}
HH_FIELD_IDX = {
    "seat": 0,
    "status": 1,
    "chips": 2,
    "actionType": 3,
    "action": 3,
    "amount": 4,
    "pot": 5,
    "initChips": 2,
}
BLIND_KEYS = ("smallBlind", "bigBlind", "ante", "straddle")


def _fmt(v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, float):
        # 160.0 → 160，避免与整型/字符串金额看起来不一致
        if abs(v - round(v)) < 1e-9:
            return str(int(round(v)))
        return f"{v:.10g}".rstrip("0").rstrip(".") if "." in f"{v:.10g}" else str(v)
    if isinstance(v, int):
        return str(v)
    if isinstance(v, str):
        s = v.strip()
        try:
            f = float(s)
            if abs(f - round(f)) < 1e-9:
                return str(int(round(f)))
        except ValueError:
            pass
        return v
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False, separators=(",", ":"))
    return str(v)


def _cell(path: Optional[str], value: Any, *, missing: bool = False) -> dict[str, str]:
    if missing or path is None:
        return {"path": "—", "value": "无此字段", "text": "—"}
    if value is None:
        return {"path": path, "value": "—", "text": f"{path}=—"}
    return {"path": path, "value": _fmt(value), "text": f"{path}={_fmt(value)}"}


def _seat_num(seat: Any) -> Optional[str]:
    """P2 / p2 / 2 → '2'（信号 hand_history[0] 用纯数字座位）."""
    if seat is None:
        return None
    s = str(seat).strip().upper()
    if not s:
        return None
    if s.startswith("P") and s[1:].isdigit():
        return s[1:]
    if s.isdigit():
        return s
    return s


def _seat_aliases(seat: Any) -> list[str]:
    """All forms that may appear in hand_history[0]."""
    n = _seat_num(seat)
    out: list[str] = []
    seen: set[str] = set()

    def add(x: Any) -> None:
        if x is None:
            return
        t = str(x).strip()
        if t and t not in seen:
            seen.add(t)
            out.append(t)

    add(n)
    if n is not None:
        add(f"P{n}")
        add(f"p{n}")
        # bare int-like without leading zeros quirks
        try:
            add(str(int(n)))
        except Exception:
            pass
    add(seat)
    return out


def _street_hh_key(street: Any) -> Optional[str]:
    if street is None:
        return None
    u = str(street).strip().upper()
    return STREET_TO_HH.get(u, u.lower() if u else None)


def find_signal_hand_history(br: Any) -> tuple[Optional[dict], str]:
    """Return (hand_history, path_prefix) from signal business.request."""
    if not isinstance(br, dict):
        return None, ""
    if isinstance(br.get("hand_history"), dict):
        return br["hand_history"], "hand_history"
    params = br.get("parameters")
    if isinstance(params, dict):
        events = params.get("events")
        if isinstance(events, list):
            # Prefer hero_action event; else last with hand_history
            last_hit: tuple[Optional[dict], str] = (None, "")
            for i, ev in enumerate(events):
                if not isinstance(ev, dict) or not isinstance(ev.get("hand_history"), dict):
                    continue
                path = f"parameters.events[{i}].hand_history"
                last_hit = (ev["hand_history"], path)
                et = str(ev.get("event_type") or ev.get("type") or "").lower()
                if "hero" in et:
                    return last_hit
            if last_hit[0] is not None:
                return last_hit
    return None, ""


def signal_table_show_info(br: Any) -> tuple[Optional[str], Any]:
    if not isinstance(br, dict):
        return None, None
    table = br.get("table")
    if not isinstance(table, dict):
        return None, None
    pub = table.get("pub_infos")
    if not isinstance(pub, dict):
        return None, None
    info = pub.get("table_show_info")
    path = "table.pub_infos.table_show_info.value"
    if isinstance(info, dict):
        return path, info.get("value")
    if info is not None:
        return path, info
    return path, None


def _row_seat_token(row0: Any) -> str:
    """Normalize hand_history row[0] to comparable seat digit when possible."""
    s = str(row0).strip()
    n = _seat_num(s)
    return n if n is not None else s


def _seat_match(a: Any, b: Any) -> bool:
    """P2 ↔ 2 ↔ '2' 等视为同一座位."""
    if a is None or b is None:
        return False
    if str(a).strip() == str(b).strip():
        return True
    na, nb = _seat_num(a), _seat_num(b)
    return na is not None and nb is not None and na == nb


def _hh_rows_for_seat(hh: dict, street_key: str, seat: Any) -> list[tuple[int, list]]:
    """All hand_history rows on street for seat, in order: [(row_index, row), ...]."""
    rows = hh.get(street_key)
    if not isinstance(rows, list):
        return []
    aliases = {_row_seat_token(a) for a in _seat_aliases(seat)}
    aliases |= {str(a).strip() for a in _seat_aliases(seat)}
    out: list[tuple[int, list]] = []
    for i, row in enumerate(rows):
        if not isinstance(row, (list, tuple)) or not row:
            continue
        tok = _row_seat_token(row[0])
        raw = str(row[0]).strip()
        if tok in aliases or raw in aliases or _seat_match(row[0], seat):
            out.append((i, list(row)))
    return out


def _hh_nth_row(
    hh: dict, street_key: str, seat: Any, nth: Optional[int] = None
) -> tuple[Optional[list], Optional[int], Optional[int]]:
    """Return (row, row_index, seat_street_nth). nth None → last match."""
    hits = _hh_rows_for_seat(hh, street_key, seat)
    if not hits:
        return None, None, None
    if nth is None:
        i, row = hits[-1]
        return row, i, len(hits) - 1
    if nth < 0 or nth >= len(hits):
        return None, None, nth
    i, row = hits[nth]
    return row, i, nth


def _hh_last_row(hh: dict, street_key: str, seat: Any) -> tuple[Optional[list], Optional[int]]:
    """Find last hand_history row on street whose [0] matches seat (P2↔2)."""
    row, idx, _ = _hh_nth_row(hh, street_key, seat, None)
    return row, idx


def extract_signal_field(
    br: Any,
    *,
    field: str,
    street: Any = None,
    seat: Any = None,
    blind_related: bool = False,
    nth: Optional[int] = None,
) -> dict[str, str]:
    if not isinstance(br, dict):
        return _cell(None, None, missing=True)

    if field in BLIND_KEYS:
        path, val = signal_table_show_info(br)
        if path is None:
            return _cell(None, None, missing=True)
        return _cell(path, val)

    hh, hh_prefix = find_signal_hand_history(br)
    if hh is None:
        if field == "communityCards":
            table = br.get("table") if isinstance(br.get("table"), dict) else {}
            return _cell("table.community_cards", (table or {}).get("community_cards"))
        return _cell(None, None, missing=True)

    if field == "communityCards":
        table = br.get("table") if isinstance(br.get("table"), dict) else {}
        return _cell("table.community_cards", (table or {}).get("community_cards"))

    street_key = _street_hh_key(street)
    seat_n = _seat_num(seat)
    if field == "street":
        if street_key and street_key in hh:
            return _cell(f"{hh_prefix}.{street_key}", street_key)
        return _cell(None, None, missing=True)

    if field == "initChips":
        row, idx = _hh_last_row(hh, "init", seat)
        if row is not None and idx is not None:
            path = f"{hh_prefix}.init[{idx}][2]"
            return _cell(path, row[2] if len(row) > 2 else None)
        seat_label = seat_n if seat_n is not None else "?"
        return _cell(f"{hh_prefix}.init[seat={seat_label}][?][2]", None)

    if not street_key or seat_n is None:
        return _cell(None, None, missing=True)

    # 定位: 街 → seat → 本街该座位第 N 次；amount → [4]
    row, idx, used_nth = _hh_nth_row(hh, street_key, seat, nth)
    fidx = HH_FIELD_IDX.get(field)
    nth_disp = (used_nth + 1) if used_nth is not None else "?"
    if row is None or idx is None:
        suffix = f"[{fidx}]" if fidx is not None else ""
        return _cell(
            f"{hh_prefix}.{street_key}[seat={seat_n},#{nth_disp}][?]{suffix}",
            None,
        )

    if field == "seat":
        path = f"{hh_prefix}.{street_key}[{idx}][0]"
        return _cell(path, row[0] if row else None)

    if fidx is None:
        return _cell(None, None, missing=True)
    path = f"{hh_prefix}.{street_key}[{idx}](seat={seat_n},#{nth_disp})[{fidx}]"
    val = row[fidx] if len(row) > fidx else None
    return _cell(path, val)


def _as_game_info_root(payload: Any, prefix: str = "") -> tuple[Optional[dict], str]:
    """Return (gameInfo-or-self, path_prefix) for GTO-shaped dicts.

    Digs into common envelopes (e.g. fusionCorrectedData) when gameInfo is nested
    or the nested object itself carries actionSequence/players/blinds.
    """
    if not isinstance(payload, dict):
        return None, ""
    if isinstance(payload.get("gameInfo"), dict):
        path = f"{prefix}.gameInfo" if prefix else "gameInfo"
        return payload["gameInfo"], path
    if (
        "actionSequence" in payload
        or "players" in payload
        or "smallBlind" in payload
        or "bigBlind" in payload
    ):
        return payload, prefix
    for k, v in payload.items():
        if not isinstance(v, dict) or str(k).startswith("_"):
            continue
        child = f"{prefix}.{k}" if prefix else str(k)
        found, found_prefix = _as_game_info_root(v, child)
        if found is not None:
            return found, found_prefix
    return None, ""


def _street_match(a: Any, b: Any) -> bool:
    au = str(a or "").strip().upper()
    bu = str(b or "").strip().upper()
    if not au or not bu:
        return False
    if au == bu:
        return True
    set_a = STREET_ALIASES.get(au, {au})
    set_b = STREET_ALIASES.get(bu, {bu})
    return bool(set_a & set_b)


def _iter_seat_street_actions(
    seq: Any, street: Any, seat: Any
) -> list[tuple[int, dict]]:
    """(global_index, action) for matching street+seat, in sequence order."""
    if not isinstance(seq, list):
        return []
    out: list[tuple[int, dict]] = []
    for i, a in enumerate(seq):
        if not isinstance(a, dict):
            continue
        if street and not _street_match(a.get("street"), street):
            continue
        if seat is not None and str(seat) != "" and not _seat_match(a.get("seat"), seat):
            continue
        out.append((i, a))
    return out


def seat_street_nth_from_seq(
    seq: Any,
    *,
    street: Any,
    seat: Any,
    index: Optional[int] = None,
    action: Optional[dict] = None,
) -> Optional[int]:
    """0-based: 该座位在本街上的第几次行动."""
    hits = _iter_seat_street_actions(seq, street, seat)
    if not hits:
        return None
    if index is not None:
        for n, (i, _) in enumerate(hits):
            if i == index:
                return n
    if isinstance(action, dict):
        for n, (_, a) in enumerate(hits):
            if a.get("actionType") == action.get("actionType") and str(a.get("amount")) == str(
                action.get("amount")
            ):
                return n
        if index is not None:
            best_n = None
            best_d = None
            for n, (i, _) in enumerate(hits):
                d = abs(i - index)
                if best_d is None or d < best_d:
                    best_d, best_n = d, n
            if best_n is not None:
                return best_n
    return len(hits) - 1


def seat_street_nth_from_block(
    block: dict, gt_norm: Optional[dict] = None
) -> Optional[int]:
    """Derive nth from issue mismatch + 真值 actionSequence."""
    mismatch = block.get("mismatch") if isinstance(block, dict) else None
    if not isinstance(mismatch, dict):
        return None
    g = mismatch.get("gt") if isinstance(mismatch.get("gt"), dict) else None
    s = mismatch.get("sys") if isinstance(mismatch.get("sys"), dict) else None
    action = g or s
    if not isinstance(action, dict):
        return None
    street = action.get("street")
    seat = action.get("seat")
    gi = None
    if isinstance(gt_norm, dict):
        gi = gt_norm.get("gameInfo") if isinstance(gt_norm.get("gameInfo"), dict) else gt_norm
    seq = (gi or {}).get("actionSequence") if isinstance(gi, dict) else None
    idx = mismatch.get("gt_index")
    if idx is None and g is None:
        idx = mismatch.get("sys_index")
    return seat_street_nth_from_seq(
        seq, street=street, seat=seat, index=idx, action=action
    )


def _find_action(
    gi: dict,
    street: Any,
    seat: Any,
    nth: Optional[int] = None,
) -> tuple[Optional[dict], Optional[int], Optional[int]]:
    """Locate by street → seat → nth. Returns (action, global_index, seat_street_nth)."""
    hits = _iter_seat_street_actions(gi.get("actionSequence"), street, seat)
    if not hits:
        return None, None, None
    if nth is None:
        i, a = hits[-1]
        return a, i, len(hits) - 1
    if nth < 0 or nth >= len(hits):
        return None, None, nth
    i, a = hits[nth]
    return a, i, nth


def extract_gto_field(
    payload: Any,
    *,
    field: str,
    street: Any = None,
    seat: Any = None,
    nth: Optional[int] = None,
) -> dict[str, str]:
    gi, prefix = _as_game_info_root(payload)
    if gi is None:
        return _cell(None, None, missing=True)
    p = f"{prefix}." if prefix else ""

    if field in BLIND_KEYS or field == "communityCards":
        return _cell(f"{p}{field}", gi.get(field))

    if field == "initChips":
        players = gi.get("players") or []
        if isinstance(players, list):
            for i, pl in enumerate(players):
                if isinstance(pl, dict) and _seat_match(pl.get("seat"), seat):
                    return _cell(f"{p}players[{i}].initChips", pl.get("initChips"))
        return _cell(None, None, missing=True)

    if field == "position":
        players = gi.get("players") or []
        if isinstance(players, list):
            for i, pl in enumerate(players):
                if isinstance(pl, dict) and _seat_match(pl.get("seat"), seat):
                    return _cell(f"{p}players[{i}].position", pl.get("position"))
        return _cell(None, None, missing=True)

    if field in ("players", "players.length"):
        players = gi.get("players") or []
        n = len(players) if isinstance(players, list) else None
        return _cell(f"{p}players.length", n)

    if field in ("amount", "actionType", "seat", "street"):
        act, idx, used_nth = _find_action(gi, street, seat, nth)
        seat_s = str(seat or "")
        street_u = str(street or "").upper() or "?"
        nth_disp = (used_nth + 1) if used_nth is not None else "?"
        if act is None or idx is None:
            return _cell(
                f"{p}actionSequence[street={street_u},seat={seat_s},#{nth_disp}].{field}",
                None,
            )
        return _cell(
            f"{p}actionSequence[{idx}](street={street_u},seat={seat_s},#{nth_disp}).{field}",
            act.get(field),
        )

    if field in gi:
        return _cell(f"{p}{field}", gi.get(field))
    return _cell(None, None, missing=True)


def related_field_specs(
    block: dict, *, gt_norm: Optional[dict] = None
) -> list[dict[str, Any]]:
    """Fields to show in cross-module table for one issue block.

    只放「本条差异真正涉及」的字段，不附带上下文（如金额错时不写盲注）。
    """
    kind = str(block.get("kind") or "")
    mismatch = block.get("mismatch") or {}
    g = mismatch.get("gt") if isinstance(mismatch, dict) else None
    s = mismatch.get("sys") if isinstance(mismatch, dict) else None
    street = None
    seat = None
    if isinstance(g, dict):
        street = g.get("street")
        seat = g.get("seat")
    if street is None and isinstance(s, dict):
        street = s.get("street")
    if seat is None and isinstance(s, dict):
        seat = s.get("seat")

    specs: list[dict[str, Any]] = []

    def add(key: str, label: str, *, blind: bool = False, seat_override: Any = None) -> None:
        specs.append(
            {
                "key": key,
                "label": label,
                "street": street,
                "seat": seat_override if seat_override is not None else seat,
                "nth": None,  # filled after specs built
                "blind_related": blind,
            }
        )

    # --- 行动类：只写实际出错的字段 ---
    if kind == "金额不正确":
        add("amount", "金额")
    elif kind == "行动类型不正确":
        add("actionType", "行动类型")
    elif kind == "行动类型与金额均不正确" or ("行动类型" in kind and "金额" in kind):
        add("actionType", "行动类型")
        add("amount", "金额")
    elif kind in ("行动缺失", "行动多余"):
        # 缺失/多余本身就是整条行动，用定位字段描述「哪一条」
        add("seat", "座位")
        add("street", "街次")
        add("actionType", "行动类型")
        add("amount", "金额")
    elif kind == "行动内容不正确" and isinstance(g, dict) and isinstance(s, dict):
        from compare_gto_requests import scalar_values_equivalent

        for key in ("actionType", "amount", "seat", "street"):
            if not scalar_values_equivalent(g.get(key), s.get(key), field=key):
                add(key, key)
        if not specs:
            add("amount", "amount")
            add("actionType", "actionType")
    elif kind in ("盲注/前注",) or "盲注" in kind:
        label_to_key = {
            "小盲": "smallBlind",
            "大盲": "bigBlind",
            "前注": "ante",
            "抢注": "straddle",
            "抓位": "straddle",
            "smallBlind": "smallBlind",
            "bigBlind": "bigBlind",
            "ante": "ante",
            "straddle": "straddle",
        }
        for row in block.get("rows") or []:
            if not row.get("diff"):
                continue
            f = str(row.get("field") or "")
            key = label_to_key.get(f) or (f if f in BLIND_KEYS else "")
            if key:
                add(key, key, blind=True)
        if not specs:
            add("smallBlind", "smallBlind", blind=True)
            add("bigBlind", "bigBlind", blind=True)
            add("ante", "ante", blind=True)
    elif kind in ("起始筹码",) or "起始筹码" in kind:
        for row in block.get("rows") or []:
            if not row.get("diff"):
                continue
            f = str(row.get("field") or "")
            if "initChips" not in f:
                continue
            seat_i = f.split()[0] if f.split() else seat
            add("initChips", f"{seat_i} initChips" if seat_i else "initChips", seat_override=seat_i)
        if not specs:
            add("initChips", "initChips")
    elif kind in ("公共牌",) or "公共牌" in kind:
        add("communityCards", "communityCards")
    elif kind in ("位置",) or "位置" in kind:
        for row in block.get("rows") or []:
            if not row.get("diff"):
                continue
            f = str(row.get("field") or "")
            seat_i = f.split()[0] if f.split() else seat
            add("position", f"{seat_i} position" if seat_i else "position", seat_override=seat_i)
        if not specs:
            add("position", "position")
    elif kind in ("玩家人数",):
        add("players", "players.length")
    else:
        # Fallback：只从本块 diff 行推导，不扩上下文
        for row in block.get("rows") or []:
            if not row.get("diff"):
                continue
            f = str(row.get("field") or "")
            if f in ("问题类型", "对齐序号(真/系)", "说明"):
                continue
            key = f
            for cand in (
                "amount",
                "actionType",
                "seat",
                "street",
                "smallBlind",
                "bigBlind",
                "ante",
                "straddle",
                "communityCards",
                "initChips",
                "position",
            ):
                if cand.lower() in f.lower().replace(" ", ""):
                    key = cand
                    break
            seat_i = seat
            if "initChips" in f or "position" in f:
                seat_i = f.split()[0] if f.split() else seat
                key = "initChips" if "initChips" in f else ("position" if "position" in f else key)
            add(key, f if f != key else key, blind=key in BLIND_KEYS, seat_override=seat_i)
        if not specs and isinstance(g, dict) and isinstance(s, dict):
            from compare_gto_requests import scalar_values_equivalent

            for key in ("actionType", "amount"):
                if not scalar_values_equivalent(g.get(key), s.get(key), field=key):
                    add(key, key)

    # Deduplicate by (key, seat) preserving order
    seen = set()
    out = []
    for sp in specs:
        k = (sp["key"], sp.get("seat"))
        if k in seen:
            continue
        seen.add(k)
        out.append(sp)

    # 行动字段：按真值算出「本街该座位第几次」，供信号 / Chess 等同口径定位
    nth = seat_street_nth_from_block(block, gt_norm)
    action_keys = {"amount", "actionType", "seat", "street"}
    for sp in out:
        if sp["key"] in action_keys:
            sp["nth"] = nth
    return out


def layer_by_id(trace_chain: Optional[dict], module_id: str) -> Optional[dict]:
    if not trace_chain:
        return None
    for layer in trace_chain.get("layers") or []:
        if layer.get("id") == module_id:
            return layer
    return None


def layer_business_request(trace_chain: Optional[dict], module_id: str) -> Any:
    layer = layer_by_id(trace_chain, module_id)
    return layer.get("business_request") if layer else None


def layer_chess_payload(trace_chain: Optional[dict]) -> Any:
    """Chess 取值：business.request.fusionCorrectedData（跨模块表用）。"""
    from module_pipeline import extract_fusion_corrected_data

    layer = layer_by_id(trace_chain, "chess")
    if not layer:
        return None
    fcd = layer.get("fusion_corrected_data")
    if fcd is not None:
        return fcd
    return extract_fusion_corrected_data(layer.get("business_request"))


def layer_chess_display_request(trace_chain: Optional[dict]) -> Any:
    """Chess 完整 JSON：整份 business.request；fusionCorrectedData 解析成对象便于高亮。"""
    import copy

    from module_pipeline import extract_fusion_corrected_data

    br = layer_business_request(trace_chain, "chess")
    if not isinstance(br, dict):
        return br
    out = copy.deepcopy(br)
    fcd = extract_fusion_corrected_data(out)
    if fcd is not None:
        out["fusionCorrectedData"] = fcd
    return out


def _prefix_chess_fcd_cell(cell: dict[str, str]) -> dict[str, str]:
    """跨模块路径加上 fusionCorrectedData. 前缀，标明取值位置。"""
    path = str(cell.get("path") or "")
    if not path or path in ("—", "-") or path.startswith("fusionCorrectedData"):
        return cell
    new_path = f"fusionCorrectedData.{path}"
    value = cell.get("value")
    if value in (None, "无此字段"):
        return {**cell, "path": new_path}
    return {
        **cell,
        "path": new_path,
        "text": f"{new_path}={value}",
    }


def _empty_anchor_meta(module_id: str, title: str) -> dict[str, Any]:
    return {
        "id": module_id,
        "title": title,
        "service": None,
        "span_name": None,
        "span_id": None,
        "trace_id": None,
        "timestamp": None,
        "duration": None,
        "span_status": None,
        "hand_index": None,
        "open_id": None,
        "hole_cards": None,
        "ok": False,
    }


def gateway_layer_meta(trace_chain: Optional[dict]) -> dict[str, Any]:
    """Meta for the span that backs the 网关 column."""
    empty = _empty_anchor_meta("gateway", "网关")
    layer = layer_by_id(trace_chain, "gateway")
    if layer and layer.get("span_name") == "game-gateway-strategy" and layer.get("span_id"):
        return {
            **empty,
            "service": layer.get("service"),
            "span_name": layer.get("span_name"),
            "span_id": layer.get("span_id"),
            "trace_id": layer.get("trace_id"),
            "timestamp": layer.get("timestamp"),
            "duration": layer.get("duration"),
            "span_status": layer.get("span_status"),
            "hand_index": layer.get("hand_index"),
            "open_id": layer.get("open_id"),
            "hole_cards": layer.get("hole_cards"),
            "ok": True,
        }
    state = layer_by_id(trace_chain, "state")
    if state:
        for rel in state.get("related") or []:
            if rel.get("span_name") == "game-gateway-strategy":
                return {
                    **empty,
                    "service": rel.get("service") or state.get("service"),
                    "span_name": rel.get("span_name"),
                    "span_id": rel.get("span_id"),
                    "trace_id": rel.get("trace_id"),
                    "timestamp": rel.get("timestamp"),
                    "duration": rel.get("duration"),
                    "span_status": rel.get("span_status"),
                    "hand_index": rel.get("hand_index"),
                    "open_id": rel.get("open_id") if rel.get("open_id") is not None else state.get("open_id"),
                    "hole_cards": rel.get("hole_cards")
                    if rel.get("hole_cards") is not None
                    else state.get("hole_cards"),
                    "ok": bool(rel.get("span_id") or rel.get("business_request")),
                }
    if layer:
        return {
            **empty,
            "service": layer.get("service"),
            "span_name": layer.get("span_name"),
            "span_id": layer.get("span_id"),
            "trace_id": layer.get("trace_id"),
            "timestamp": layer.get("timestamp"),
            "duration": layer.get("duration"),
            "span_status": layer.get("span_status"),
            "hand_index": layer.get("hand_index"),
            "open_id": layer.get("open_id"),
            "hole_cards": layer.get("hole_cards"),
            "ok": bool(layer.get("span_id")),
        }
    return empty


def module_anchor_metas(trace_chain: Optional[dict]) -> list[dict[str, Any]]:
    """Per core-module span meta; always same keys (None if missing)."""
    out: list[dict[str, Any]] = []
    for mid, title in (
        ("signal", "信号引擎"),
        ("state", "状态引擎"),
        ("gateway", "网关"),
        ("chess", "Chess API"),
    ):
        if mid == "gateway":
            out.append(gateway_layer_meta(trace_chain))
            continue
        layer = layer_by_id(trace_chain, mid)
        if not layer:
            out.append(_empty_anchor_meta(mid, title))
            continue
        out.append(
            {
                "id": mid,
                "title": title,
                "service": layer.get("service"),
                "span_name": layer.get("span_name"),
                "span_id": layer.get("span_id"),
                "trace_id": layer.get("trace_id"),
                "timestamp": layer.get("timestamp"),
                "duration": layer.get("duration"),
                "span_status": layer.get("span_status"),
                "hand_index": layer.get("hand_index"),
                "open_id": layer.get("open_id"),
                "hole_cards": layer.get("hole_cards"),
                "ok": bool(layer.get("span_id") or layer.get("business_request")),
            }
        )
    return out


def gateway_business_request(trace_chain: Optional[dict]) -> Any:
    """网关列：game-gateway-strategy.business.request（优先于 strategy.async）。"""
    if not trace_chain:
        return None
    # Prefer dedicated gateway layer if it already is game-gateway-strategy
    for layer in trace_chain.get("layers") or []:
        if layer.get("id") == "gateway":
            if layer.get("span_name") == "game-gateway-strategy":
                return layer.get("business_request")
            # Fall through to related on state
    for layer in trace_chain.get("layers") or []:
        if layer.get("id") != "state":
            continue
        for rel in layer.get("related") or []:
            if rel.get("span_name") == "game-gateway-strategy":
                return rel.get("business_request")
    return layer_business_request(trace_chain, "gateway")


def extract_gto_field_at_index(
    payload: Any,
    *,
    field: str,
    index: Optional[int],
) -> dict[str, str]:
    """按 actionSequence 全局下标取值（对齐结果展示用）。"""
    gi, prefix = _as_game_info_root(payload)
    if gi is None:
        return _cell(None, None, missing=True)
    p = f"{prefix}." if prefix else ""
    seq = gi.get("actionSequence")
    if not isinstance(seq, list):
        return _cell(None, None, missing=True)
    if index is None or index < 0 or index >= len(seq):
        return _cell(
            f"{p}actionSequence[{index if index is not None else '?'}].{field}",
            None,
            missing=True,
        )
    act = seq[index]
    if not isinstance(act, dict):
        return _cell(None, None, missing=True)
    street = act.get("street")
    seat = act.get("seat")
    street_u = str(street or "").upper()
    seat_s = str(seat) if seat is not None else "?"
    path = f"{p}actionSequence[{index}](street={street_u},seat={seat_s}).{field}"
    if field in ("amount", "actionType", "seat", "street"):
        return _cell(path, act.get(field))
    return _cell(path, act.get(field))


def build_cross_module_rows(
    block: dict,
    *,
    gt_norm: Optional[dict],
    sys_norm: Optional[dict],
    trace_chain: Optional[dict],
) -> list[dict[str, Any]]:
    """Rows for: 真值 | 系统最终 | 信号 | 状态 | 网关 | Chess.

    行动类差异：正确值 / Chess 按对齐下标 gt_index / sys_index 取值，
    与结论文案同一对行动；信号仍按正确值侧街座位第 N 次定位。
    """
    signal_br = layer_business_request(trace_chain, "signal")
    state_br = layer_business_request(trace_chain, "state")
    gateway_br = gateway_business_request(trace_chain)
    # Chess 列优先用对照侧 norm（与 build_issue_blocks 同一份），避免原始 FCD 未裁剪
    chess_br = sys_norm if isinstance(sys_norm, dict) else layer_chess_payload(trace_chain)

    mismatch = block.get("mismatch") if isinstance(block.get("mismatch"), dict) else {}
    gt_index = mismatch.get("gt_index") if mismatch else None
    sys_index = mismatch.get("sys_index") if mismatch else None
    use_align_index = gt_index is not None or sys_index is not None

    rows = []
    for spec in related_field_specs(block, gt_norm=gt_norm):
        field = spec["key"]
        street = spec.get("street")
        seat = spec.get("seat")
        nth = spec.get("nth")
        blind = bool(spec.get("blind_related")) or field in BLIND_KEYS
        action_field = field in ("amount", "actionType", "seat", "street")

        if use_align_index and action_field:
            gt_cell = (
                extract_gto_field_at_index(gt_norm, field=field, index=gt_index)
                if gt_index is not None
                else _cell(None, None, missing=True)
            )
            chess_cell = (
                extract_gto_field_at_index(chess_br, field=field, index=sys_index)
                if sys_index is not None
                else _cell(None, None, missing=True)
            )
            # 信号：有正确值行动时仍按 GT 的街/座/第 N 次定位
            if gt_index is not None:
                sig_cell = extract_signal_field(
                    signal_br,
                    field=field,
                    street=street,
                    seat=seat,
                    nth=nth,
                    blind_related=blind,
                )
            else:
                sig_cell = _cell(None, None, missing=True)
            state_cell = (
                extract_gto_field_at_index(state_br, field=field, index=gt_index)
                if gt_index is not None
                else _cell(None, None, missing=True)
            )
            gateway_cell = (
                extract_gto_field_at_index(gateway_br, field=field, index=gt_index)
                if gt_index is not None
                else _cell(None, None, missing=True)
            )
            sys_cell = (
                extract_gto_field_at_index(sys_norm, field=field, index=sys_index)
                if sys_index is not None
                else _cell(None, None, missing=True)
            )
        else:
            gt_cell = extract_gto_field(
                gt_norm, field=field, street=street, seat=seat, nth=nth
            )
            sys_cell = extract_gto_field(
                sys_norm, field=field, street=street, seat=seat, nth=nth
            )
            sig_cell = extract_signal_field(
                signal_br,
                field=field,
                street=street,
                seat=seat,
                nth=nth,
                blind_related=blind,
            )
            state_cell = extract_gto_field(
                state_br, field=field, street=street, seat=seat, nth=nth
            )
            gateway_cell = extract_gto_field(
                gateway_br, field=field, street=street, seat=seat, nth=nth
            )
            chess_cell = extract_gto_field(
                chess_br, field=field, street=street, seat=seat, nth=nth
            )

        rows.append(
            {
                "field": spec["label"],
                "gt": gt_cell,
                "sys": sys_cell,
                "signal": sig_cell,
                "state": state_cell,
                "gateway": gateway_cell,
                "chess": _prefix_chess_fcd_cell(chess_cell),
            }
        )
    return rows
