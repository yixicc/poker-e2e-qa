#!/usr/bin/env python3
"""Compare GTO request payloads: ground truth vs old/new system versions.

Outputs:
  - output/index.html          overview + links
  - output/hands/HAND_xxx.html per-hand triple comparison
  - output/summary.json        machine-readable metrics
  - output/diff_table.csv      flat diff rows
"""

from __future__ import annotations

import argparse
import copy
import csv
import html
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from evidence_report import (
    EVIDENCE_CSS,
    EVIDENCE_JS,
    LIVE_TRACE_JS,
    build_issue_blocks,
    case_title,
    event_ts,
    first_action_mismatch,
    gallery_file_refs,
    hole_compact,
    index_original_shots,
    index_screenshots,
    pick_problem_frame,
    render_evidence_card,
)
from action_align import (
    align_actions,
    get_actions,
    merge_diffs_with_alignment,
    summarize_alignment,
)
from module_pipeline import (
    analyze_hand_trace,
    chain_to_sidecar,
)
from trace_client import TraceClient, TraceClientError, extract_msg_keys, fetch_hand_spans
from trace_query_config import (
    TRACE_FORM_CSS,
    compact_hole_id,
    load_trace_query_config,
    render_trace_query_form,
    render_trace_query_page,
    resolve_trace_query,
)
from hand_bugs import BUG_STATUSES, BUG_STATUS_LABELS, load_hand_bugs, bug_meta_for


STREET_BOARD_LEN = {
    "PREFLOP": 0,
    "FLOP": 3,
    "TURN": 4,
    "RIVER": 5,
}

IGNORE_TOP_KEYS = {"userId", "gtoType"}  # gtoType 属策略档位，不计入行动历史还原准确率
IGNORE_GAMEINFO_KEYS = {"handId", "eventId"}
META_PATH_HINTS = ("userId", "handId", "eventId", "userToken", "timestamp", "latency", "gtotype")

# UI labels (internal fields remain old/new)
LABEL_OLD = "0703版本"
LABEL_NEW = "0729版本"


# ---------------------------------------------------------------------------
# Parsing / normalization
# ---------------------------------------------------------------------------

def parse_json_cell(value: Any) -> Optional[dict]:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, dict):
        return value
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    # Fix occasional Excel mojibake like å" before a quote
    text = re.sub(r"å\"", '"', text)
    text = text.replace("å\"", '"')
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else {"_non_object": obj}
    except json.JSONDecodeError:
        try:
            obj = json.loads(text.replace("'", '"'))
            return obj if isinstance(obj, dict) else {"_non_object": obj}
        except Exception as exc:
            return {"_parse_error": str(exc), "_raw_preview": text[:300]}


def norm_hole_key(value: Any) -> Optional[str]:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if isinstance(value, list):
        cards = value
    else:
        text = str(value).strip()
        try:
            cards = json.loads(text)
        except Exception:
            try:
                cards = json.loads(text.replace("'", '"'))
            except Exception:
                return text
    if isinstance(cards, list):
        return json.dumps(cards, ensure_ascii=False, separators=(",", ":"))
    return str(cards)


def wepoker_ts(hand_id: Optional[str]) -> Optional[int]:
    if not hand_id:
        return None
    m = re.search(r"WePoker\.(\d+)", str(hand_id))
    return int(m.group(1)) if m else None


def extract_hand_id(req: Optional[dict]) -> Optional[str]:
    if not req or not isinstance(req, dict):
        return None
    gi = req.get("gameInfo") or {}
    return gi.get("handId")


def is_valid_request(req: Optional[dict]) -> bool:
    return bool(
        req
        and isinstance(req, dict)
        and "gameInfo" in req
        and "_parse_error" not in req
        and "_non_object" not in req
    )


# ---------------------------------------------------------------------------
# Truncation: keep everything before P0's last action
# ---------------------------------------------------------------------------

def truncate_before_last_p0(req: dict) -> tuple[dict, dict]:
    """Return (truncated_request, meta)."""
    out = copy.deepcopy(req)
    gi = out.setdefault("gameInfo", {})
    actions = list(gi.get("actionSequence") or [])
    p0_idxs = [i for i, a in enumerate(actions) if a.get("seat") == "P0"]
    meta = {
        "p0_action_count": len(p0_idxs),
        "original_action_len": len(actions),
        "truncated_action_len": len(actions),
        "decision_street": None,
        "last_p0_action": None,
        "boundary_ok": True,
        "note": "",
    }
    if not p0_idxs:
        meta["note"] = "GT 中未找到 P0 行动，无法裁剪"
        meta["boundary_ok"] = False
        return out, meta

    last_i = p0_idxs[-1]
    last_action = actions[last_i]
    street = str(last_action.get("street") or "PREFLOP").upper()
    meta["decision_street"] = street
    meta["last_p0_action"] = last_action
    truncated = actions[:last_i]
    gi["actionSequence"] = truncated
    meta["truncated_action_len"] = len(truncated)

    board = list(gi.get("communityCards") or [])
    keep = STREET_BOARD_LEN.get(street, len(board))
    gi["communityCards"] = board[:keep]
    meta["community_cards_kept"] = keep
    meta["community_cards_original"] = len(board)
    return out, meta


def strip_meta(req: dict) -> dict:
    out = copy.deepcopy(req)
    for k in list(out.keys()):
        if k in IGNORE_TOP_KEYS or any(h in k.lower() for h in ("timestamp",)):
            out.pop(k, None)
    gi = out.get("gameInfo")
    if isinstance(gi, dict):
        for k in list(gi.keys()):
            if k in IGNORE_GAMEINFO_KEYS:
                gi.pop(k, None)
    return out


def normalize_for_compare(req: Optional[dict], *, truncate: bool) -> tuple[Optional[dict], dict]:
    if not is_valid_request(req):
        return None, {"valid": False, "note": "无效请求报文"}
    meta = {"valid": True}
    working = copy.deepcopy(req)
    if truncate:
        working, tmeta = truncate_before_last_p0(working)
        meta.update(tmeta)
    return strip_meta(working), meta


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------

def _is_numberish(x: Any) -> bool:
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        return True
    if isinstance(x, str):
        try:
            float(x)
            return True
        except ValueError:
            return False
    return False


def _num(x: Any) -> float:
    return float(x)


_STREET_CANON = {
    "PREFLOP": "PREFLOP",
    "PRE_FLOP": "PREFLOP",
    "FLOP": "FLOP",
    "TURN": "TURN",
    "RIVER": "RIVER",
}


def _canon_street_token(street: Any) -> str:
    s = str(street or "").strip().upper().replace("-", "_")
    return _STREET_CANON.get(s, s)


def _canon_seat_token(seat: Any) -> str:
    s = str(seat if seat is not None else "").strip()
    if not s:
        return s
    if s.isdigit():
        return f"P{s}"
    if len(s) >= 2 and s[0] in "Pp" and s[1:].isdigit():
        return f"P{s[1:]}"
    return s


def straddle_values_equivalent(a: Any, b: Any) -> bool:
    """正确值 straddle 为 0 时：空 / 0 / None 都视为一致。"""

    def zeroish(v: Any) -> bool:
        if v is None:
            return True
        if isinstance(v, str):
            s = v.strip()
            if s == "" or s.lower() in ("none", "null", "—", "-"):
                return True
            try:
                return abs(float(s)) < 1e-9
            except ValueError:
                return False
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return abs(float(v)) < 1e-9
        return False

    return zeroish(a) and zeroish(b)


def amounts_equivalent(a: Any, b: Any) -> bool:
    """金额/筹码：160 与 160.0 / \"160\" / \"160.0\" 视为相同。"""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    if not (_is_numberish(a) and _is_numberish(b)):
        return str(a).strip() == str(b).strip()
    return abs(_num(a) - _num(b)) < 1e-9


def seats_equivalent(a: Any, b: Any) -> bool:
    """座位：P8 / p8 / 8 视为相同。"""
    ca, cb = _canon_seat_token(a), _canon_seat_token(b)
    if not ca and not cb:
        return True
    return bool(ca) and ca == cb


def streets_equivalent(a: Any, b: Any) -> bool:
    """街次：FLOP / flop / PREFLOP / PRE_FLOP 视为相同。"""
    ca, cb = _canon_street_token(a), _canon_street_token(b)
    if not ca and not cb:
        return True
    return bool(ca) and ca == cb


_ACTION_TYPE_ALIASES = {
    "LET": "CHECK",  # 信号引擎让牌
    "CHECK": "CHECK",
    "CALL": "CALL",
    "BET": "BET",
    "RAISE": "RAISE",
    "FOLD": "FOLD",
    "ALLIN": "ALLIN",
    "ALL_IN": "ALLIN",
}


def _canon_action_type(action: Any) -> str:
    s = str(action if action is not None else "").strip().upper().replace("-", "_")
    return _ACTION_TYPE_ALIASES.get(s, s)


def action_types_equivalent(a: Any, b: Any) -> bool:
    """行动类型：大小写不敏感；信号 LET ≡ CHECK。"""
    ca, cb = _canon_action_type(a), _canon_action_type(b)
    if not ca and not cb:
        return True
    return bool(ca) and ca == cb


def scalar_values_equivalent(a: Any, b: Any, *, field: str = "") -> bool:
    """展示/对照用标量等价（金额、座位、街次、行动类型等）。"""
    if a is None and b is None:
        return True
    sa = "" if a is None else str(a).strip()
    sb = "" if b is None else str(b).strip()
    if sa in ("—", "无此字段", "-", "None", "null") or sb in (
        "—",
        "无此字段",
        "-",
        "None",
        "null",
    ):
        return sa == sb
    if sa == sb:
        return True

    field_l = str(field or "").strip().lower()
    if field_l in (
        "amount",
        "金额",
        "initchips",
        "chips",
        "pot",
        "ante",
        "smallblind",
        "bigblind",
        "straddle",
    ) or any(
        k in field_l
        for k in (
            "amount",
            "chip",
            "金额",
            "筹码",
            "盲",
            "前注",
            "抢注",
            "pot",
        )
    ):
        if field_l in ("straddle", "抢注", "抓位") or "straddle" in field_l:
            return straddle_values_equivalent(a, b) or amounts_equivalent(a, b)
        return amounts_equivalent(a, b)

    if field_l in ("seat", "座位", "pn") or field_l.endswith(" seat"):
        return seats_equivalent(a, b)
    if "initchips" in field_l.replace(" ", "") or field_l.endswith("initchips"):
        return amounts_equivalent(a, b)
    if field_l in ("street", "街次", "街") or "street" in field_l:
        return streets_equivalent(a, b)
    if field_l in ("actiontype", "action", "行动类型", "行动") or "actiontype" in field_l.replace(
        " ", ""
    ):
        return action_types_equivalent(a, b)

    # 无字段提示时：数值优先，再试座位/街次/行动
    if _is_numberish(a) and _is_numberish(b):
        return amounts_equivalent(a, b)
    if seats_equivalent(a, b) and (
        str(a).strip().lstrip("Pp").isdigit() or str(b).strip().lstrip("Pp").isdigit()
    ):
        return True
    if streets_equivalent(a, b) and _canon_street_token(a) in {
        "PREFLOP",
        "FLOP",
        "TURN",
        "RIVER",
    }:
        return True
    if action_types_equivalent(a, b) and _canon_action_type(a) in set(
        _ACTION_TYPE_ALIASES.values()
    ):
        return True
    return False


def _is_straddle_path(path: str) -> bool:
    leaf = str(path or "").split(".")[-1].split("[")[0]
    return leaf == "straddle"


def _seat_sort_key(seat: Any) -> tuple:
    s = str(seat or "")
    m = re.match(r"^P?(\d+)$", s.strip(), re.I)
    if m:
        return (0, int(m.group(1)), s)
    return (1, 0, s)


def _is_players_list(xs: Any) -> bool:
    if not isinstance(xs, list) or not xs:
        return False
    dicts = [x for x in xs if isinstance(x, dict)]
    if len(dicts) < max(1, len(xs) // 2):
        return False
    return sum(1 for x in dicts if "seat" in x) >= max(1, len(dicts) // 2)


def _diff_players_by_seat(a: list, b: list, path: str) -> list[dict]:
    """Compare players arrays keyed by seat (P0↔P0), not by list index."""
    diffs: list[dict] = []
    by_a = {
        str(p.get("seat")): p
        for p in a
        if isinstance(p, dict) and p.get("seat") is not None
    }
    by_b = {
        str(p.get("seat")): p
        for p in b
        if isinstance(p, dict) and p.get("seat") is not None
    }
    seats = sorted(set(by_a) | set(by_b), key=_seat_sort_key)
    if len(a) != len(b):
        diffs.append(
            {
                "path": f"{path}.length" if path else "length",
                "type": "length",
                "left": len(a),
                "right": len(b),
            }
        )
    for seat in seats:
        p = f"{path}[seat={seat}]" if path else f"[seat={seat}]"
        if seat not in by_a:
            diffs.append({"path": p, "type": "missing_left", "left": None, "right": by_b[seat]})
        elif seat not in by_b:
            diffs.append({"path": p, "type": "missing_right", "left": by_a[seat], "right": None})
        else:
            diffs.extend(deep_diff(by_a[seat], by_b[seat], p))
    return diffs


def deep_diff(a: Any, b: Any, path: str = "") -> list[dict]:
    diffs: list[dict] = []
    if _is_straddle_path(path) and straddle_values_equivalent(a, b):
        return []
    if type(a) != type(b) and not (_is_numberish(a) and _is_numberish(b)):
        # treat None vs missing separately below
        if a is None or b is None:
            diffs.append({"path": path or "$", "type": "value", "left": a, "right": b})
            return diffs
        diffs.append({"path": path or "$", "type": "type", "left": a, "right": b})
        return diffs

    if _is_numberish(a) and _is_numberish(b):
        if abs(_num(a) - _num(b)) > 1e-9:
            diffs.append({"path": path or "$", "type": "value", "left": a, "right": b})
        return diffs

    if isinstance(a, dict) and isinstance(b, dict):
        keys = sorted(set(a) | set(b), key=lambda x: str(x))
        for k in keys:
            p = f"{path}.{k}" if path else str(k)
            if k not in a:
                if k == "straddle" and straddle_values_equivalent(None, b[k]):
                    continue
                diffs.append({"path": p, "type": "missing_left", "left": None, "right": b[k]})
            elif k not in b:
                if k == "straddle" and straddle_values_equivalent(a[k], None):
                    continue
                diffs.append({"path": p, "type": "missing_right", "left": a[k], "right": None})
            else:
                diffs.extend(deep_diff(a[k], b[k], p))
        return diffs

    if isinstance(a, list) and isinstance(b, list):
        # players: always align by seat
        if _is_players_list(a) or _is_players_list(b) or path.endswith("players"):
            return _diff_players_by_seat(a, b, path)
        n = max(len(a), len(b))
        if len(a) != len(b):
            diffs.append(
                {
                    "path": f"{path}.length" if path else "length",
                    "type": "length",
                    "left": len(a),
                    "right": len(b),
                }
            )
        for i in range(n):
            p = f"{path}[{i}]"
            if i >= len(a):
                diffs.append({"path": p, "type": "missing_left", "left": None, "right": b[i]})
            elif i >= len(b):
                diffs.append({"path": p, "type": "missing_right", "left": a[i], "right": None})
            else:
                diffs.extend(deep_diff(a[i], b[i], p))
        return diffs

    if a != b:
        diffs.append({"path": path or "$", "type": "value", "left": a, "right": b})
    return diffs


def classify_diff(path: str) -> str:
    p = path.lower()
    if any(h in p for h in META_PATH_HINTS) or p.endswith("gtotype") or p == "gtotype":
        return "元数据(可忽略)"
    if "actionsequence" in p:
        if "actiontype" in p:
            return "行动类型错误"
        if "amount" in p:
            return "行动金额错误"
        if "seat" in p:
            return "行动座位错误"
        if "street" in p:
            return "街次错误"
        if "length" in p or p.endswith("]") and "actionsequence" in p:
            return "行动序列长度/条目差异"
        return "行动序列差异"
    if "communitycards" in p:
        return "公共牌错误"
    if "holecards" in p:
        return "底牌错误"
    if "initchips" in p:
        return "起始筹码错误"
    if "position" in p:
        return "位置错误"
    if "players" in p:
        if "length" in p:
            return "玩家人数错误"
        return "玩家信息错误"
    if any(k in p for k in ("bigblind", "smallblind", "ante", "straddle")):
        return "盲注/前注错误"
    if "gtotype" in p:
        return "gtoType差异"
    return "其他字段差异"


def filter_ignorable(diffs: list[dict]) -> list[dict]:
    kept = []
    for d in diffs:
        cat = classify_diff(d["path"])
        if cat == "元数据(可忽略)":
            continue
        kept.append({**d, "category": cat})
    return kept


def severity_score(diffs: list[dict]) -> int:
    """Higher = more likely to change GTO advice."""
    weights = {
        "盲注/前注错误": 12,
        "公共牌错误": 11,
        "起始筹码错误": 10,
        "行动缺失": 10,
        "行动多余": 8,
        "行动类型错误": 10,
        "行动序列长度/条目差异": 9,
        "行动序列差异": 8,
        "行动座位错误": 8,
        "街次错误": 8,
        "行动金额错误": 6,
        "位置错误": 4,
        "玩家人数错误": 7,
        "玩家信息错误": 3,
        "底牌错误": 10,
        "gtoType差异": 2,
        "其他字段差异": 1,
    }
    return sum(weights.get(d.get("category", ""), 1) for d in diffs)


STREET_ORDER = ["PREFLOP", "FLOP", "TURN", "RIVER"]
STREET_CN = {"PREFLOP": "翻前", "FLOP": "翻牌", "TURN": "转牌", "RIVER": "河牌"}


def action_label(a: Any) -> str:
    if not isinstance(a, dict):
        return str(a)
    seat = a.get("seat") or "?"
    at = a.get("actionType") or "?"
    amt = a.get("amount")
    street = a.get("street") or ""
    return f"{seat} {at} {amt}" + (f" ({street})" if street else "")


def _actions_by_street(req: Optional[dict]) -> dict[str, list]:
    if not req:
        return {}
    acts = (req.get("gameInfo") or {}).get("actionSequence") or []
    out: dict[str, list] = {s: [] for s in STREET_ORDER}
    for a in acts:
        if not isinstance(a, dict):
            continue
        st = str(a.get("street") or "PREFLOP").upper()
        out.setdefault(st, []).append(a)
    return out


def friendly_summaries(gt: Optional[dict], sys: Optional[dict], diffs: list[dict]) -> list[str]:
    """Human-readable issue bullets for overview + detail page."""
    if not gt and not sys:
        return ["无数据可对比"]
    if not gt:
        return ["缺少真值报文"]
    if not sys:
        return ["缺少系统报文"]
    if not diffs:
        return []

    notes: list[str] = []
    gi_g = gt.get("gameInfo") or {}
    gi_s = sys.get("gameInfo") or {}

    # 1) 盲注
    for k, label in (
        ("ante", "前注"),
        ("straddle", "抢注"),
        ("smallBlind", "小盲"),
        ("bigBlind", "大盲"),
    ):
        vg, vs = gi_g.get(k), gi_s.get(k)
        if vg is None and vs is None:
            continue
        if k == "straddle" and straddle_values_equivalent(vg, vs):
            continue
        try:
            same = abs(float(vg) - float(vs)) < 1e-9
        except Exception:
            same = str(vg) == str(vs)
        if not same:
            notes.append(f"{label}不一致：真值 {vg} vs 系统 {vs}")

    pg = gi_g.get("players") or []
    ps = gi_s.get("players") or []
    by_seat_g = {p.get("seat"): p for p in pg if isinstance(p, dict)}
    by_seat_s = {p.get("seat"): p for p in ps if isinstance(p, dict)}
    chip_mismos = []
    pos_mismos = []
    for seat in sorted(set(by_seat_g) | set(by_seat_s), key=lambda x: str(x)):
        a, b = by_seat_g.get(seat), by_seat_s.get(seat)
        if a and b:
            if not amounts_equivalent(a.get("initChips"), b.get("initChips")):
                chip_mismos.append(f"{seat}:{a.get('initChips')}→{b.get('initChips')}")
            if a.get("position") != b.get("position"):
                pos_mismos.append(f"{seat}:{a.get('position')}→{b.get('position')}")
        elif a and not b:
            chip_mismos.append(f"{seat}:{a.get('initChips')}→（无此座位）")
            if a.get("position") is not None:
                pos_mismos.append(f"{seat}:{a.get('position')}→（无此座位）")
        elif b and not a:
            chip_mismos.append(f"{seat}:（无此座位）→{b.get('initChips')}")
            if b.get("position") is not None:
                pos_mismos.append(f"{seat}:（无此座位）→{b.get('position')}")

    # 2) 玩家人数
    if len(pg) != len(ps):
        notes.append(f"玩家人数不一致：真值 {len(pg)} vs 系统 {len(ps)}")

    # 3) 位置
    if pos_mismos:
        show = "，".join(pos_mismos[:6])
        notes.append(f"位置不一致（{show}）")

    # 4) 起始筹码
    if chip_mismos:
        show = "，".join(chip_mismos[:6])
        extra = f" 等{len(chip_mismos)}处" if len(chip_mismos) > 6 else ""
        notes.append(f"起始筹码不一致（{show}{extra}）")

    # 5) 公牌
    bg = list(gi_g.get("communityCards") or [])
    bs = list(gi_s.get("communityCards") or [])
    if bg != bs:
        notes.append(f"公共牌不一致：真值 {bg or '[]'} vs 系统 {bs or '[]'}")

    # 6–7) 行动：改写在前，缺失/多余靠后
    align_notes = summarize_alignment(gt, sys, limit=50)
    rewrite_notes = []
    miss_extra_notes = []
    for n in align_notes:
        if any(k in n for k in ("缺失", "多余", "缺少整条", "多出整条")):
            miss_extra_notes.append(n)
        else:
            rewrite_notes.append(n)
    notes.extend(rewrite_notes)
    notes.extend(miss_extra_notes)

    # Deduplicate while preserving order; keep actionable first
    seen = set()
    uniq = []
    for n in notes:
        if n not in seen:
            seen.add(n)
            uniq.append(n)

    # If still empty but diffs exist, fall back to path list
    if not uniq:
        for d in diffs[:8]:
            uniq.append(
                f"{d.get('category')}: {d['path']} "
                f"真值={json.dumps(d.get('left'), ensure_ascii=False)} "
                f"系统={json.dumps(d.get('right'), ensure_ascii=False)}"
            )
    return uniq


def detail_fields_text(diffs: list[dict], friendly: list[str], limit: int = 20) -> str:
    """Compact text for overview table cell — keep more items so new-vs-GT is reviewable."""
    if friendly:
        items = friendly[:limit]
        more = f"；…共{len(friendly)}项" if len(friendly) > limit else ""
        return "；".join(items) + more
    if not diffs:
        return "-"
    paths = []
    for d in diffs[:limit]:
        paths.append(f"{d.get('category')}:{d['path']}")
    more = f"；…共{len(diffs)}项" if len(diffs) > limit else ""
    return "；".join(paths) + more


def collect_diff_paths(diffs: list[dict]) -> set[str]:
    return {d["path"] for d in diffs}


# ---------------------------------------------------------------------------
# Alignment
# ---------------------------------------------------------------------------

@dataclass
class HandPair:
    hand_uid: str
    hole_key: str
    old_row_idx: Optional[int]
    new_row_idx: Optional[int]
    gt_raw: Optional[dict]
    old_req_raw: Optional[dict]
    new_req_raw: Optional[dict]
    created_at_old: Any = None
    created_at_new: Any = None
    match_method: str = ""
    notes: list[str] = field(default_factory=list)


def align_hands(old_df: pd.DataFrame, new_df: pd.DataFrame) -> list[HandPair]:
    """Align hands; output order follows 0703 Excel row order (created_at early→late)."""
    old_records = []
    for idx, row in old_df.iterrows():
        gt = parse_json_cell(row.get("补全后的请求"))
        old_req = parse_json_cell(row.get("last_step_request"))
        hk = norm_hole_key(row.get("hole_cards_p0"))
        old_records.append(
            {
                "idx": idx,
                "hk": hk,
                "gt": gt,
                "old_req": old_req,
                "created_at": row.get("created_at"),
                "ts": wepoker_ts(extract_hand_id(gt) or extract_hand_id(old_req)),
                "used": False,
            }
        )

    new_records = []
    for idx, row in new_df.iterrows():
        new_req = parse_json_cell(row.get("last_step_request"))
        hk = norm_hole_key(row.get("hole_cards_p0"))
        new_records.append(
            {
                "idx": idx,
                "hk": hk,
                "new_req": new_req,
                "created_at": row.get("created_at"),
                "ts": wepoker_ts(extract_hand_id(new_req) or row.get("hand_id")),
                "used": False,
            }
        )

    new_by_hk: dict[str, list] = defaultdict(list)
    for r in new_records:
        if r["hk"]:
            new_by_hk[r["hk"]].append(r)

    # Count old per hole key for unique vs multi matching
    old_count: dict[str, int] = Counter()
    for r in old_records:
        if r["hk"]:
            old_count[r["hk"]] += 1

    pairs: list[HandPair] = []

    def pick_new(hk: str, o: dict) -> tuple[Optional[dict], str, list[str]]:
        """Pick best unused new record for this old row."""
        cands = [x for x in new_by_hk.get(hk, []) if not x["used"]]
        if not cands:
            return None, "old_only", ["0729 数据中无匹配手牌"]
        if len(cands) == 1 and old_count.get(hk, 0) == 1:
            return cands[0], "hole_cards_p0_unique", []
        # Multi / ambiguous: nearest WePoker timestamp
        best = None
        best_score = None
        for n in cands:
            if o["ts"] is not None and n["ts"] is not None:
                score = abs(o["ts"] - n["ts"])
            else:
                score = 10**18
            if best_score is None or score < best_score:
                best_score = score
                best = n
        notes = []
        if best_score is not None and best_score > 5000:
            notes.append(f"时间戳差距较大: {best_score}ms")
        method = f"hole_cards_p0+closest_ts(delta={best_score})"
        return best, method, notes

    # Walk 0703 rows in Excel order (already early→late by created_at)
    for o in old_records:
        hk = o["hk"] or ""
        n, method, notes = pick_new(hk, o) if hk else (None, "old_only", ["无 hole_cards_p0"])
        if n is not None:
            n["used"] = True
        pairs.append(
            HandPair(
                hand_uid="",  # assigned after final order
                hole_key=hk or "UNKNOWN",
                old_row_idx=o["idx"],
                new_row_idx=n["idx"] if n else None,
                gt_raw=o["gt"],
                old_req_raw=o["old_req"],
                new_req_raw=n["new_req"] if n else None,
                created_at_old=o["created_at"],
                created_at_new=n["created_at"] if n else None,
                match_method=method,
                notes=notes,
            )
        )
        o["used"] = True

    # Append 0729-only hands, sorted by their created_at
    leftovers = [n for n in new_records if not n["used"]]

    def _ts_key(v: Any):
        try:
            return pd.Timestamp(v).timestamp()
        except Exception:
            return float("inf")

    leftovers.sort(key=lambda n: (_ts_key(n.get("created_at")), n["idx"]))
    for n in leftovers:
        pairs.append(
            HandPair(
                hand_uid="",
                hole_key=n["hk"] or "UNKNOWN",
                old_row_idx=None,
                new_row_idx=n["idx"],
                gt_raw=None,
                old_req_raw=None,
                new_req_raw=n["new_req"],
                created_at_new=n["created_at"],
                match_method="new_only",
                notes=["0703 / 真值中无匹配手牌"],
            )
        )
        n["used"] = True

    for i, p in enumerate(pairs, start=1):
        p.hand_uid = f"HAND_{i:03d}"
    return pairs


def align_hands_from_gt(
    gt_hands: dict[str, dict],
    new_df: Optional["pd.DataFrame"] = None,
    *,
    old_df: Optional["pd.DataFrame"] = None,
) -> list[HandPair]:
    """Build HandPairs from GT version hands; optionally align 0729 CSV / refresh 0703 from Excel.

    Preserves HAND_xxx ids from the GT store. If old_df is provided, old_req_raw/gt_raw
    still prefer the store (Excel is ignored for GT). new_df supplies 0729 last_step.
    """
    new_records: list[dict] = []
    if new_df is not None:
        for idx, row in new_df.iterrows():
            new_req = parse_json_cell(row.get("last_step_request"))
            hk = norm_hole_key(row.get("hole_cards_p0"))
            new_records.append(
                {
                    "idx": idx,
                    "hk": hk,
                    "new_req": new_req,
                    "created_at": row.get("created_at"),
                    "ts": wepoker_ts(extract_hand_id(new_req) or row.get("hand_id")),
                    "used": False,
                }
            )
    new_by_hk: dict[str, list] = defaultdict(list)
    for r in new_records:
        if r["hk"]:
            new_by_hk[r["hk"]].append(r)

    # Stable order: HAND_001, HAND_002, ...
    def _hand_sort_key(hid: str):
        try:
            return int(str(hid).split("_")[-1])
        except Exception:
            return 10**9

    pairs: list[HandPair] = []
    for hid in sorted(gt_hands.keys(), key=_hand_sort_key):
        row = gt_hands[hid] or {}
        hk = norm_hole_key(row.get("hole_key")) or str(row.get("hole_key") or "") or "UNKNOWN"
        gt = row.get("gt_raw") if isinstance(row.get("gt_raw"), dict) else None
        old_req = row.get("old_req_raw") if isinstance(row.get("old_req_raw"), dict) else None
        created_old = row.get("created_at_old")

        n = None
        method = "gt_store"
        notes: list[str] = []
        cands = [x for x in new_by_hk.get(hk, []) if not x["used"]] if hk and hk != "UNKNOWN" else []
        if cands:
            if len(cands) == 1:
                n = cands[0]
                method = "gt_store+hole_unique"
            else:
                ots = wepoker_ts(extract_hand_id(gt) or extract_hand_id(old_req))
                best = None
                best_score = None
                for cand in cands:
                    if ots is not None and cand["ts"] is not None:
                        score = abs(ots - cand["ts"])
                    else:
                        score = 10**18
                    if best_score is None or score < best_score:
                        best_score = score
                        best = cand
                n = best
                method = f"gt_store+closest_ts(delta={best_score})"
            if n is not None:
                n["used"] = True
        elif new_df is not None:
            notes.append("0729 数据中无匹配手牌")
            method = "gt_store_old_only"

        pairs.append(
            HandPair(
                hand_uid=str(hid),
                hole_key=hk,
                old_row_idx=None,
                new_row_idx=n["idx"] if n else None,
                gt_raw=gt,
                old_req_raw=old_req,
                new_req_raw=n["new_req"] if n else None,
                created_at_old=created_old,
                created_at_new=n["created_at"] if n else None,
                match_method=method,
                notes=notes,
            )
        )

    # Append 0729-only leftovers
    leftovers = [n for n in new_records if not n["used"]]

    def _ts_key(v: Any):
        try:
            return pd.Timestamp(v).timestamp()
        except Exception:
            return float("inf")

    leftovers.sort(key=lambda n: (_ts_key(n.get("created_at")), n["idx"]))
    extra_i = len(pairs)
    for n in leftovers:
        extra_i += 1
        pairs.append(
            HandPair(
                hand_uid=f"HAND_{extra_i:03d}",
                hole_key=n["hk"] or "UNKNOWN",
                old_row_idx=None,
                new_row_idx=n["idx"],
                gt_raw=None,
                old_req_raw=None,
                new_req_raw=n["new_req"],
                created_at_new=n["created_at"],
                match_method="new_only",
                notes=["正确值库中无匹配手牌"],
            )
        )
    return pairs


# ---------------------------------------------------------------------------
# Analysis per hand
# ---------------------------------------------------------------------------

@dataclass
class HandResult:
    hand_uid: str
    hole_key: str
    match_method: str
    notes: list[str]
    has_gt: bool
    has_old: bool
    has_new: bool
    old_exact: Optional[bool]
    new_exact: Optional[bool]
    old_diff_count: int
    new_diff_count: int
    old_severity: int
    new_severity: int
    old_categories: list[str]
    new_categories: list[str]
    old_friendly: list[str]
    new_friendly: list[str]
    old_detail_fields: str
    new_detail_fields: str
    trunc_meta: dict
    old_diffs: list[dict]
    new_diffs: list[dict]
    gt_norm: Optional[dict]
    old_norm: Optional[dict]
    new_norm: Optional[dict]
    boundary_flags: list[str]
    created_at_old: Any
    created_at_new: Any
    user_token: Optional[str] = None
    hand_id: Optional[str] = None
    old_user_token: Optional[str] = None
    new_user_token: Optional[str] = None
    old_hand_id: Optional[str] = None
    new_hand_id: Optional[str] = None
    community_cards: Any = None
    old_shot_rel: Optional[str] = None
    new_shot_rel: Optional[str] = None
    old_shot_meta: dict = field(default_factory=dict)
    new_shot_meta: dict = field(default_factory=dict)
    old_shot_gallery: list = field(default_factory=list)
    new_shot_gallery: list = field(default_factory=list)
    old_shot_start: int = 0
    new_shot_start: int = 0
    old_case_title: str = ""
    new_case_title: str = ""
    trace_chain: Optional[dict] = None
    root_cause_module: Optional[str] = None
    root_cause_title: Optional[str] = None
    trace_query: Optional[dict] = None
    # 总览主口径：正确值 vs Chess API（无 FCD 时 chess_exact=None → 无对照）
    chess_exact: Optional[bool] = None
    chess_diff_count: int = 0
    chess_categories: list[str] = field(default_factory=list)
    chess_first_issue: str = ""


def attach_chess_overview(results: list[HandResult]) -> None:
    """Fill Chess-vs-GT fields used by overview (same口径 as evidence page)."""
    from evidence_report import build_issue_blocks, chess_norm_for_compare

    for r in results:
        chess = chess_norm_for_compare(r.trace_chain, gt_norm=r.gt_norm)
        if r.gt_norm is None or chess is None:
            r.chess_exact = None
            r.chess_diff_count = 0
            r.chess_categories = []
            r.chess_first_issue = "Chess API 无值" if r.gt_norm is not None else "无对照"
            continue
        blocks = build_issue_blocks(r.gt_norm, chess)
        kinds: list[str] = []
        for b in blocks:
            k = str(b.get("kind") or "").strip()
            if k and k not in kinds:
                kinds.append(k)
        r.chess_exact = len(blocks) == 0
        r.chess_diff_count = len(blocks)
        r.chess_categories = kinds
        r.chess_first_issue = str(blocks[0].get("title") or "") if blocks else ""


def analyze_pair(pair: HandPair) -> HandResult:
    gt_norm, trunc_meta = normalize_for_compare(pair.gt_raw, truncate=True)
    old_norm, old_meta = normalize_for_compare(pair.old_req_raw, truncate=False)
    new_norm, new_meta = normalize_for_compare(pair.new_req_raw, truncate=False)

    old_diffs = filter_ignorable(deep_diff(gt_norm, old_norm)) if gt_norm and old_norm else []
    new_diffs = filter_ignorable(deep_diff(gt_norm, new_norm)) if gt_norm and new_norm else []
    if gt_norm and old_norm:
        old_diffs = merge_diffs_with_alignment(gt_norm, old_norm, old_diffs)
    if gt_norm and new_norm:
        new_diffs = merge_diffs_with_alignment(gt_norm, new_norm, new_diffs)

    boundary_flags = []
    # Check whether system last_step action length matches expected truncated length
    expected_len = trunc_meta.get("truncated_action_len")
    if expected_len is not None and old_norm:
        old_len = len((old_norm.get("gameInfo") or {}).get("actionSequence") or [])
        if old_len != expected_len:
            boundary_flags.append(f"{LABEL_OLD} last_step 行动数={old_len}，期望(P0最后行动前)={expected_len}")
    if expected_len is not None and new_norm:
        new_len = len((new_norm.get("gameInfo") or {}).get("actionSequence") or [])
        if new_len != expected_len:
            boundary_flags.append(f"{LABEL_NEW} last_step 行动数={new_len}，期望(P0最后行动前)={expected_len}")

    if not trunc_meta.get("boundary_ok", True):
        boundary_flags.append(trunc_meta.get("note") or "裁剪边界异常")

    old_cats = sorted({d["category"] for d in old_diffs})
    new_cats = sorted({d["category"] for d in new_diffs})

    old_friendly = friendly_summaries(gt_norm, old_norm, old_diffs) if (gt_norm or old_norm) else (["缺少对照"] if not old_norm else [])
    new_friendly = friendly_summaries(gt_norm, new_norm, new_diffs) if (gt_norm or new_norm) else (["缺少对照"] if not new_norm else [])
    if gt_norm and old_norm and not old_diffs:
        old_friendly = []
    if gt_norm and new_norm and not new_diffs:
        new_friendly = []
    if not gt_norm:
        old_friendly = ["缺少真值"] if old_norm else [f"缺少真值与{LABEL_OLD}"]
        new_friendly = ["缺少真值"] if new_norm else [f"缺少真值与{LABEL_NEW}"]
    if gt_norm and not old_norm:
        old_friendly = [f"{LABEL_OLD}无 last_step_request"]
    if gt_norm and not new_norm:
        new_friendly = [f"{LABEL_NEW}无匹配手牌或无 last_step_request"]

    user_token = None
    hand_id = None
    community = None
    src = pair.gt_raw or pair.old_req_raw or pair.new_req_raw
    if isinstance(src, dict):
        user_token = src.get("userId")
        gi = src.get("gameInfo") or {}
        hand_id = gi.get("handId")
        community = gi.get("communityCards")

    def _ids(req: Optional[dict]) -> tuple[Optional[str], Optional[str]]:
        if not isinstance(req, dict):
            return None, None
        gi = req.get("gameInfo") or {}
        return req.get("userId"), gi.get("handId") if isinstance(gi, dict) else None

    old_user_token, old_hand_id = _ids(pair.old_req_raw)
    new_user_token, new_hand_id = _ids(pair.new_req_raw)

    old_m = first_action_mismatch(gt_norm, old_norm)
    new_m = first_action_mismatch(gt_norm, new_norm)

    return HandResult(
        hand_uid=pair.hand_uid,
        hole_key=pair.hole_key,
        match_method=pair.match_method,
        notes=list(pair.notes),
        has_gt=is_valid_request(pair.gt_raw),
        has_old=is_valid_request(pair.old_req_raw),
        has_new=is_valid_request(pair.new_req_raw),
        old_exact=(len(old_diffs) == 0) if (gt_norm and old_norm) else None,
        new_exact=(len(new_diffs) == 0) if (gt_norm and new_norm) else None,
        old_diff_count=len(old_diffs),
        new_diff_count=len(new_diffs),
        old_severity=severity_score(old_diffs),
        new_severity=severity_score(new_diffs),
        old_categories=old_cats,
        new_categories=new_cats,
        old_friendly=old_friendly,
        new_friendly=new_friendly,
        old_detail_fields=detail_fields_text(old_diffs, old_friendly),
        new_detail_fields=detail_fields_text(new_diffs, new_friendly),
        trunc_meta=trunc_meta,
        old_diffs=old_diffs,
        new_diffs=new_diffs,
        gt_norm=gt_norm,
        old_norm=old_norm,
        new_norm=new_norm,
        boundary_flags=boundary_flags,
        created_at_old=pair.created_at_old,
        created_at_new=pair.created_at_new,
        user_token=user_token,
        hand_id=hand_id,
        old_user_token=old_user_token,
        new_user_token=new_user_token,
        old_hand_id=old_hand_id,
        new_hand_id=new_hand_id,
        community_cards=community,
        old_case_title=case_title(old_friendly, old_m),
        new_case_title=case_title(new_friendly, new_m),
    )


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------

CSS = """
:root {
  --bg: #f6f3ee;
  --panel: #fffdf9;
  --ink: #1c1917;
  --muted: #78716c;
  --line: #e7e0d5;
  --ok: #166534;
  --ok-bg: #dcfce7;
  --bad: #9f1239;
  --bad-bg: #ffe4e6;
  --warn: #9a3412;
  --warn-bg: #ffedd5;
  --accent: #0f766e;
  --diff: #fff1f2;
  --miss: #fef3c7;
  --extra: #e0e7ff;
  --same: transparent;
}
* { box-sizing: border-box; }
body {
  margin: 0; font-family: "IBM Plex Sans", "Noto Sans SC", sans-serif;
  background: linear-gradient(180deg, #efe8dc 0%, var(--bg) 240px);
  color: var(--ink); line-height: 1.45;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
.wrap { max-width: 1480px; margin: 0 auto; padding: 28px 20px 60px; }
h1 { font-family: "Source Serif 4", "Noto Serif SC", serif; font-weight: 600; margin: 0 0 8px; }
h2 { margin-top: 36px; font-size: 1.25rem; }
details.fold-section { margin-top: 36px; }
details.fold-section > summary {
  list-style: none; cursor: pointer; font-size: 1.25rem; font-weight: 650;
  padding: 10px 14px; border-radius: 10px; background: #f3ebe1; border: 1px solid var(--line);
  display: flex; align-items: center; gap: 8px; user-select: none;
}
details.fold-section > summary::-webkit-details-marker { display: none; }
details.fold-section > summary::before {
  content: "▶"; font-size: 11px; color: var(--muted); transition: transform .15s ease;
}
details.fold-section[open] > summary::before { transform: rotate(90deg); }
details.fold-section > summary:hover { background: #efe6da; }
details.fold-section .fold-body { margin-top: 10px; }
.sub { color: var(--muted); margin-bottom: 24px; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
.card {
  background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 14px 16px;
}
.card .label { color: var(--muted); font-size: 12px; }
.card .value { font-size: 28px; font-weight: 650; margin-top: 4px; }
.card .hint { font-size: 12px; color: var(--muted); margin-top: 4px; }
.badge {
  display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 12px; font-weight: 600;
}
.badge.ok { background: var(--ok-bg); color: var(--ok); }
.badge.bad { background: var(--bad-bg); color: var(--bad); }
.badge.warn { background: var(--warn-bg); color: var(--warn); }
.badge.muted { background: #f5f5f4; color: var(--muted); }
.badge.miss { background: var(--miss); color: #92400e; }
.badge.extra { background: var(--extra); color: #3730a3; }
.table-scroll { overflow-x: auto; border: 1px solid var(--line); border-radius: 10px; }
table { width: 100%; border-collapse: collapse; background: var(--panel); }
th, td { padding: 10px 12px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; font-size: 13px; }
th { background: #faf6f0; position: sticky; top: 0; z-index: 1; white-space: nowrap; }
tr:hover td { background: #faf7f2; }
td.detail { max-width: 320px; font-size: 12px; color: #44403c; line-height: 1.4; }
td.cats { max-width: 160px; font-size: 12px; }
td.num { white-space: nowrap; font-variant-numeric: tabular-nums; font-weight: 650; }
td.preview { max-width: 280px; }
.pill-row { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; }
.pill {
  display: inline-block; padding: 1px 7px; border-radius: 999px;
  background: #ffe4e6; color: #9f1239; font-size: 11px; font-weight: 650; white-space: nowrap;
}
.pill.more { background: #f5f5f4; color: #57534e; font-weight: 600; }
.one-line {
  font-size: 12.5px; color: #44403c; line-height: 1.35;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.one-line .more { color: #a16207; font-weight: 650; margin-left: 4px; white-space: nowrap; }
body.hide-old .col-old { display: none; }
.filters label.toggle {
  display: inline-flex; align-items: center; gap: 6px; font-size: 13px; color: var(--muted);
  user-select: none; cursor: pointer; margin-left: 4px;
}
.filters label.toggle input { accent-color: var(--accent); }
#all th, #all td { vertical-align: middle; }
#all tbody tr { height: 1px; } /* keep rows compact */
#all tbody tr.jump-target {
  outline: 2px solid #e11d48; outline-offset: -2px;
  background: #fff1f2 !important;
  transition: background 0.3s ease;
}
.filters { display: flex; flex-wrap: wrap; gap: 8px; margin: 16px 0; align-items: center; }
input[type=search], select {
  border: 1px solid var(--line); border-radius: 8px; padding: 8px 10px; background: white; min-width: 180px;
}
.bug-status, .bug-owner, .bug-note {
  border: 1px solid var(--line); border-radius: 6px; padding: 4px 6px; background: #fff;
  font-size: 12px; min-width: 0; width: 100%; max-width: 110px; box-sizing: border-box;
}
.bug-owner { max-width: 96px; }
.bug-note {
  max-width: none; min-width: 220px; width: 280px;
  min-height: 52px; max-height: 140px; resize: vertical;
  line-height: 1.35; white-space: pre-wrap; word-break: break-word;
  font-family: inherit;
}
.bug-save-hint { font-size: 12px; color: var(--muted); margin-left: 8px; }
.bug-save-hint.ok { color: #166534; }
.bug-save-hint.err { color: #9f1239; }
td.bug-cell { min-width: 100px; max-width: 120px; }
td.bug-note-cell {
  min-width: 240px; max-width: 360px; width: 300px;
  vertical-align: top;
}
#all th:nth-child(5), #all td.bug-note-cell { white-space: normal; }
""" + TRACE_FORM_CSS + """
.triple { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 16px; }
.triple.twin { grid-template-columns: repeat(2, 1fr); }
@media (max-width: 1100px) { .triple { grid-template-columns: 1fr; } }
.col {
  background: var(--panel); border: 1px solid var(--line); border-radius: 12px; overflow: hidden;
  display: flex; flex-direction: column; min-height: 420px;
}
.col h3 {
  margin: 0; padding: 12px 14px; background: #faf6f0; border-bottom: 1px solid var(--line);
  font-size: 14px; display: flex; justify-content: space-between; align-items: center;
}
pre {
  margin: 0; padding: 12px; overflow: auto; font-size: 11.5px; line-height: 1.4;
  font-family: "IBM Plex Mono", ui-monospace, monospace; flex: 1;
  white-space: pre-wrap; word-break: break-word;
}
.diff-line { background: var(--diff); }
.mark-diff { background: #fecdd3; padding: 0 2px; border-radius: 3px; }
.meta-box {
  background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 14px 16px; margin: 16px 0;
}
.taglist span {
  display: inline-block; margin: 2px 4px 2px 0; padding: 2px 8px; background: #f5f5f4;
  border-radius: 6px; font-size: 12px;
}
.friendly-list { margin: 8px 0 0; padding-left: 18px; }
.friendly-list li { margin: 4px 0; }
.diff-table td.path { font-family: ui-monospace, monospace; font-size: 12px; }
.nav { margin-bottom: 14px; color: var(--muted); font-size: 13px; }
.nav a { color: var(--accent); font-weight: 600; text-decoration: none; }
.nav a:hover { text-decoration: underline; }
.footer { margin-top: 40px; color: var(--muted); font-size: 12px; }
.street-block { margin: 14px 0; border: 1px solid var(--line); border-radius: 12px; overflow: hidden; background: var(--panel); }
.street-h {
  padding: 10px 14px; background: #faf6f0; border-bottom: 1px solid var(--line);
  display: flex; justify-content: space-between; align-items: center; font-weight: 600;
}
.act-grid { display: grid; grid-template-columns: 70px 1fr 1fr; gap: 0; }
.act-grid .hd { background: #f5f5f4; font-size: 12px; color: var(--muted); padding: 8px 10px; border-bottom: 1px solid var(--line); }
.act-row { display: contents; }
.act-row > div { padding: 8px 10px; border-bottom: 1px solid var(--line); font-size: 12.5px; font-family: ui-monospace, monospace; }
.act-row.same > div { background: #fff; }
.act-row.diff > div { background: var(--diff); }
.act-row.miss > div { background: var(--miss); }
.act-row.extra > div { background: var(--extra); }
.legend { display: flex; flex-wrap: wrap; gap: 10px; margin: 10px 0 0; font-size: 12px; color: var(--muted); }
.legend i { display: inline-block; width: 12px; height: 12px; border-radius: 3px; margin-right: 4px; vertical-align: -1px; }
.legend .c-same { background: #fff; border: 1px solid var(--line); }
.legend .c-diff { background: #fecdd3; }
.legend .c-miss { background: #fde68a; }
.legend .c-extra { background: #c7d2fe; }
"""


def pretty_json(obj: Any) -> str:
    if obj is None:
        return "（无数据）"
    return json.dumps(obj, ensure_ascii=False, indent=2)


def parse_hand_uids(raw: Any) -> list[str]:
    """Parse batch hand ids from text/list.

    Accepts ``HAND_001``, ``hand-6``, ``1``, ``014``; separators: comma / 顿号 / space / newline.
    Empty input → [].
    """
    if raw is None:
        return []
    if isinstance(raw, (list, tuple, set)):
        parts = [str(x).strip() for x in raw]
    else:
        text = str(raw).strip()
        if not text:
            return []
        parts = re.split(r"[,，、;；\s]+", text)
    out: list[str] = []
    seen: set[str] = set()
    for p in parts:
        if not p:
            continue
        m = re.match(r"(?i)^(?:hand[_-]?)?(\d+)$", p)
        if m:
            uid = f"HAND_{int(m.group(1)):03d}"
        else:
            uid = p
        if uid not in seen:
            seen.add(uid)
            out.append(uid)
    return out


def filter_pairs_by_hands(
    pairs: list[HandPair], hand_uids: list[str]
) -> list[HandPair]:
    """Keep only requested hands; preserve request order. Raises if any id missing."""
    if not hand_uids:
        return pairs
    by_id = {p.hand_uid: p for p in pairs}
    missing = [h for h in hand_uids if h not in by_id]
    if missing:
        raise ValueError(
            "本批手牌在正确值中不存在: "
            + ", ".join(missing)
            + f"（正确值共 {len(by_id)} 手）"
        )
    return [by_id[h] for h in hand_uids]


def esc(s: Any) -> str:
    return html.escape("" if s is None else str(s))


def badge_exact(flag: Optional[bool]) -> str:
    if flag is True:
        return '<span class="badge ok">一致</span>'
    if flag is False:
        return '<span class="badge bad">不一致</span>'
    return '<span class="badge muted">无对照</span>'


def badge_chess(flag: Optional[bool]) -> str:
    """Overview Chess column: missing FCD is 无值, not 不一致."""
    if flag is True:
        return '<span class="badge ok">一致</span>'
    if flag is False:
        return '<span class="badge bad">不一致</span>'
    return '<span class="badge muted">Chess API 无值</span>'


def change_badge(r: "HandResult") -> str:
    if r.old_exact is False and r.new_exact is True:
        return f'<span class="badge ok">{LABEL_NEW}修好</span>'
    if r.old_exact is True and r.new_exact is False:
        return f'<span class="badge bad">{LABEL_NEW}回退</span>'
    if r.old_exact is False and r.new_exact is False:
        if r.new_severity < r.old_severity:
            return f'<span class="badge warn">{LABEL_NEW}减轻</span>'
        if r.new_severity > r.old_severity:
            return f'<span class="badge bad">{LABEL_NEW}加重</span>'
        return '<span class="badge muted">仍不一致</span>'
    if r.old_exact is True and r.new_exact is True:
        return '<span class="badge ok">均正确</span>'
    return '<span class="badge muted">-</span>'


_ACTION_MARK_PATH_RE = re.compile(
    r"^(.*actionSequence\[)([^@\]]+)@([^\]]+)(\].*)$",
    re.IGNORECASE,
)


def _canon_action_mark_path(path: str) -> str:
    """Normalize seat/street tokens so PRE_FLOP↔PREFLOP、2↔P2 still hit marks."""
    p = str(path or "")
    m = _ACTION_MARK_PATH_RE.match(p)
    if not m:
        return p
    return (
        f"{m.group(1)}{_canon_seat_token(m.group(2))}"
        f"@{_canon_street_token(m.group(3))}{m.group(4)}"
    )


def json_with_value_marks(obj: Any, diffs: list[dict], side: str) -> str:
    """Pretty JSON with changed leaf values wrapped for highlight.

    side: 'left' marks GT values that differ; 'right' marks system values.
    Paths may use players[seat=P0] and actionSequence[P0@PREFLOP] forms.
    """
    if obj is None:
        return esc("（无数据）")

    changed: dict[str, Any] = {}
    canon_diffs: list[dict] = []
    for d in diffs:
        key = "left" if side == "left" else "right"
        raw_path = str(d.get("path") or "")
        path = _canon_action_mark_path(raw_path)
        changed[path] = d.get(key)
        if path != raw_path:
            canon_diffs.append({**d, "path": path})
        else:
            canon_diffs.append(d)

    def path_hit(p: str) -> bool:
        cp = _canon_action_mark_path(p)
        if cp in changed or p in changed:
            return True
        return any(
            d["path"] == cp
            or d["path"] == p
            or d["path"].startswith(cp + ".")
            or d["path"].startswith(cp + "[")
            or d["path"].startswith(p + ".")
            or d["path"].startswith(p + "[")
            for d in canon_diffs
        )

    def leaf_marked(p: str, cell: str) -> str:
        cp = _canon_action_mark_path(p)
        if cp in changed or p in changed:
            return f'<span class="mark-diff">{cell}</span>'
        return cell

    def render(val: Any, path: str, indent: int) -> list[str]:
        pad = "  " * indent
        lines: list[str] = []
        if isinstance(val, dict):
            if not val:
                lines.append(pad + "{}")
                return lines
            lines.append(pad + "{")
            items = list(val.items())
            for i, (k, v) in enumerate(items):
                p = f"{path}.{k}" if path else str(k)
                comma = "," if i < len(items) - 1 else ""
                if isinstance(v, (dict, list)):
                    lines.append(f'{pad}  "{esc(k)}":')
                    sub = render(v, p, indent + 1)
                    if sub:
                        sub[-1] = sub[-1] + comma
                    lines.extend(sub)
                else:
                    raw = json.dumps(v, ensure_ascii=False)
                    cell = leaf_marked(p, esc(raw))
                    lines.append(f'{pad}  "{esc(k)}": {cell}{comma}')
            lines.append(pad + "}")
            return lines
        if isinstance(val, list):
            if not val:
                lines.append(pad + "[]")
                return lines
            lines.append(pad + "[")
            is_actions = path.lower().endswith("actionsequence")
            # action 行也带 seat，不能靠 _is_players_list 误判，否则会走 [seat=P2]
            # 而差异路径是 [P2@PREFLOP]，导致 amount/actionType 无法高亮。
            is_players = (not is_actions) and (
                path.endswith("players") or _is_players_list(val)
            )
            for i, v in enumerate(val):
                p_idx = f"{path}[{i}]"
                p_alt = None
                if isinstance(v, dict):
                    if is_actions and (v.get("seat") is not None or v.get("street") is not None):
                        seat = _canon_seat_token(v.get("seat"))
                        street = _canon_street_token(v.get("street"))
                        p_alt = f"{path}[{seat}@{street}]"
                    elif is_players and v.get("seat") is not None:
                        p_alt = f"{path}[seat={_canon_seat_token(v.get('seat'))}]"
                p_keys = [p for p in (p_idx, p_alt) if p]
                comma = "," if i < len(val) - 1 else ""
                if isinstance(v, (dict, list)):
                    # Prefer seat-aligned path for nested leaf marks
                    prefer = p_alt or p_idx
                    sub = render(v, prefer, indent + 1)
                    if sub:
                        block_hit = any(path_hit(pk) for pk in p_keys)
                        if block_hit:
                            sub = [f'<span class="diff-line">{x}</span>' for x in sub]
                        # Also mark leaves under index path if only index diffs exist
                        if prefer != p_idx:
                            # re-check leaves already marked via prefer path
                            pass
                        sub[-1] = sub[-1] + comma
                    lines.extend(sub)
                else:
                    raw = json.dumps(v, ensure_ascii=False)
                    cell = esc(raw)
                    if any(
                        _canon_action_mark_path(pk) in changed or pk in changed
                        for pk in p_keys
                    ):
                        cell = f'<span class="mark-diff">{cell}</span>'
                    lines.append(f"{pad}  {cell}{comma}")
            lines.append(pad + "]")
            return lines
        raw = json.dumps(val, ensure_ascii=False)
        cell = leaf_marked(path, esc(raw))
        lines.append(pad + cell)
        return lines

    return "\n".join(render(obj, "", 0))


def render_action_street_compare_triple(
    gt: Optional[dict],
    old: Optional[dict],
    new: Optional[dict],
    title: str = "",
    *,
    right_label: str = "",
) -> str:
    """Aligned rows: missing/extra/rewrite；默认对照正确值 vs Chess API。

    `old` 保留入参以兼容旧调用，不再参与渲染。
    """
    del old  # 行动序列对照不再展示 0703
    label = (right_label or "").strip() or "Chess API"
    if not title:
        title = f"行动序列对照（正确值 vs {label}，按对齐）"
    g_all = get_actions(gt)
    n_ops = align_actions(g_all, get_actions(new))

    def ops_by_street(ops: list[dict]) -> dict[str, list]:
        out: dict[str, list] = {s: [] for s in STREET_ORDER}
        for op in ops:
            a = op.get("gt") or op.get("sys") or {}
            st = str(a.get("street") or "PREFLOP").upper()
            out.setdefault(st, []).append(op)
        return out

    n_by = ops_by_street(n_ops)

    blocks = [
        f"<h2>{esc(title)}</h2>",
        '<div class="legend">'
        '<span><i class="c-same"></i>对齐一致</span>'
        '<span><i class="c-diff"></i>内容错误（类型/金额）</span>'
        '<span><i class="c-miss"></i>对照侧缺失</span>'
        '<span><i class="c-extra"></i>对照侧多余</span>'
        "</div>",
        "<p style='color:#78716c;font-size:12px;margin:6px 0 12px'>说明：按 (街次,座位,行动类型) 对齐后比较；缺行动标「缺失」，不再把后面的 Pn 错位拿来对。</p>",
    ]

    def fmt_sys(op: Optional[dict]) -> tuple[str, str]:
        if not op:
            return "—", "color:#a8a29e;"
        kind = op.get("op")
        a = op.get("sys")
        if kind == "missing":
            return "（缺失）", "background:#fef3c7;font-weight:700;"
        if kind == "extra":
            return action_label(a) + "（多余）", "background:#e0e7ff;font-weight:700;"
        if kind == "rewrite":
            return action_label(a), "background:#fff1f2;font-weight:700;"
        return action_label(a) if a else "—", ""

    any_street = False
    for st in STREET_ORDER:
        n_list = n_by.get(st) or []
        if not n_list:
            continue
        any_street = True
        cn = STREET_CN.get(st, st)

        miss = sum(1 for o in n_list if o["op"] == "missing")
        extra = sum(1 for o in n_list if o["op"] == "extra")
        rw = sum(1 for o in n_list if o["op"] == "rewrite")
        if n_list and all(x["op"] == "equal" for x in n_list):
            status = f'<span class="badge ok">{esc(label)}一致</span>'
        else:
            bits = []
            if miss:
                bits.append(f"缺{miss}")
            if extra:
                bits.append(f"多{extra}")
            if rw:
                bits.append(f"错{rw}")
            if not bits:
                status = f'<span class="badge muted">{esc(label)}</span>'
            else:
                cls = "miss" if miss else ("extra" if extra and not rw else "bad")
                status = f'<span class="badge {cls}">{esc(label)}{"/".join(bits)}</span>'

        n_by_gt = {}
        n_extras = []
        for op in n_list:
            if op.get("gt_index") is not None:
                n_by_gt[op["gt_index"]] = op
            else:
                n_extras.append(op)
        gt_indices = sorted(n_by_gt)

        rows = [
            "<div class='table-scroll'><table><thead><tr>"
            f"<th style='width:70px'>对齐</th><th>正确值</th><th>{esc(label)}</th>"
            "</tr></thead><tbody>",
        ]
        for gi in gt_indices:
            n_op = n_by_gt.get(gi)
            gt_act = (n_op or {}).get("gt")
            gtxt = action_label(gt_act) if gt_act else "—"
            ntxt, ncss = fmt_sys(n_op)
            tag = "同座"
            if n_op and n_op["op"] == "missing":
                tag = "缺失"
            elif n_op and n_op["op"] == "rewrite":
                tag = "内容错"
            rows.append(
                "<tr>"
                f"<td>{esc(tag)}</td>"
                f"<td><code>{esc(gtxt)}</code></td>"
                f'<td style="{ncss}"><code>{esc(ntxt)}</code></td>'
                "</tr>"
            )
        for n_op in n_extras:
            ntxt, ncss = fmt_sys(n_op)
            rows.append(
                "<tr>"
                "<td>多余</td>"
                "<td><code>—</code></td>"
                f'<td style="{ncss}"><code>{esc(ntxt)}</code></td>'
                "</tr>"
            )
        rows.append("</tbody></table></div>")
        blocks.append(
            f'<div class="street-block"><div class="street-h"><span>{esc(cn)}（{esc(st)}）</span>'
            f"<span>{status}</span></div>"
            + "".join(rows)
            + "</div>"
        )
    if not any_street:
        blocks.append("<p>无行动序列可展示</p>")
    return "\n".join(blocks)



def render_friendly_box(title: str, items: list[str]) -> str:
    if not items:
        return f'<div class="meta-box"><b>{esc(title)}</b>：无（与真值一致或无对照）</div>'
    lis = "".join(f"<li>{esc(x)}</li>" for x in items)
    return f'<div class="meta-box"><b>{esc(title)}</b><ul class="friendly-list">{lis}</ul></div>'


def render_hand_html(result: HandResult, out_path: Path) -> None:
    from evidence_report import chess_norm_for_compare

    chess_norm = chess_norm_for_compare(result.trace_chain, gt_norm=result.gt_norm)
    compare_right = chess_norm
    chess_diffs: list = []
    if result.gt_norm and compare_right is not None:
        chess_diffs = filter_ignorable(deep_diff(result.gt_norm, compare_right))
        chess_diffs = merge_diffs_with_alignment(
            result.gt_norm, compare_right, chess_diffs
        )

    last_p0 = result.trunc_meta.get("last_p0_action")
    n_chess = (
        len(build_issue_blocks(result.gt_norm, compare_right))
        if result.gt_norm and compare_right is not None
        else 0
    )
    chess_exact = (
        (n_chess == 0) if (result.gt_norm and compare_right is not None) else None
    )
    # Page title: 正确值 vs Chess API
    if compare_right is None:
        primary_title = f"{result.hand_uid} Chess API vs 正确值 · Chess API 无值"
    else:
        primary_title = f"{result.hand_uid} Chess API vs 正确值 · {n_chess} 处差异"

    new_time = esc(result.created_at_new) if result.created_at_new not in (None, "") else "—"
    hand_meta = f"""
  <div class="hand-meta">
    <table class="meta-table">
      <tr><th>内部 ID</th><td>{esc(result.hand_uid)}</td><th>hole_cards_p0</th><td><code>{esc(result.hole_key)}</code></td></tr>
      <tr><th>userId</th><td>{esc(result.new_user_token) if result.new_user_token else "—"}</td>
          <th>时间</th><td><code>{new_time}</code></td></tr>
      <tr><th>handId</th><td colspan="3"><code>{esc(result.new_hand_id) if result.new_hand_id else "—"}</code></td></tr>
      <tr><th>公共牌</th><td colspan="3"><code>{esc(json.dumps(result.community_cards, ensure_ascii=False))}</code></td></tr>
      <tr><th>裁剪边界</th><td colspan="3">决策街 {esc(result.trunc_meta.get('decision_street'))}；最后 P0 行动 <code>{esc(json.dumps(last_p0, ensure_ascii=False))}</code>；
        GT 行动 {esc(result.trunc_meta.get('original_action_len'))} → 裁剪后 {esc(result.trunc_meta.get('truncated_action_len'))}</td></tr>
    </table>
  </div>"""

    new_evidence = render_evidence_card(
        "Chess API",
        chess_exact,
        result.new_friendly,
        result.new_shot_rel,
        result.gt_norm,
        compare_right,
        result.new_shot_meta or {},
        all_diffs=chess_diffs,
        categories=result.new_categories,
        default_open=(chess_exact is False),
        shot_gallery=result.new_shot_gallery,
        shot_start=result.new_shot_start,
        trace_chain=result.trace_chain,
    )

    cards = compact_hole_id(result.hole_key)
    # 嵌入查询条件供证据页经本地服务代理查 ClickHouse
    q = result.trace_query
    if not isinstance(q, dict) or not q:
        cfg = {}
        q = resolve_trace_query(
            cfg,
            hand_uid=result.hand_uid,
            hole_key=result.hole_key,
            data_open_id=(result.new_user_token or result.user_token or ""),
        )
        result.trace_query = q
    live_query = {
        "trace_env": q.get("trace_env") or "uat",
        "api": q.get("api") or "",
        "env_label": q.get("env_label") or "",
        "open_id": q.get("open_id") or "",
        "fallback_open_id": q.get("fallback_open_id") or "",
        "cards": q.get("cards") or cards,
        "hole_key": q.get("hole_key") or cards,
        "start_time": q.get("start_time") or "",
        "end_time": q.get("end_time") or "",
        "pad_minutes": q.get("pad_minutes") or 15,
        "open_id_mode": q.get("open_id_mode") or "",
        "center_ms": _center_ms_for_hand(result),
    }
    live_payload = {
        "hand_uid": result.hand_uid,
        "hole_key": cards,
        "cards": cards,
        "user_token": (result.new_user_token or result.user_token or ""),
        "gt_norm": result.gt_norm,
        "sys_norm": result.new_norm,  # 兼容旧 payload；对照侧改为服务端 Chess
        "old_norm": result.old_norm,
        "hand_title_prefix": f"{result.hand_uid} Chess API vs 正确值",
        "query": live_query,
    }
    live_json = json.dumps(live_payload, ensure_ascii=False, default=str).replace(
        "<", "\\u003c"
    )

    if compare_right is not None:
        street_block = render_action_street_compare_triple(
            result.gt_norm,
            None,
            compare_right,
            right_label="Chess API",
        )
    else:
        street_block = (
            "<h2>行动序列对照（正确值 vs Chess API）</h2>"
            '<p class="xmod-empty">Chess API 无值，暂无法对照行动序列</p>'
        )

    body = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{esc(result.hand_uid)} {esc(primary_title)}</title><style>{CSS}{EVIDENCE_CSS}</style></head><body>
<div class="wrap">
  <div class="nav">
    <a href="../index.html#{esc(result.hand_uid)}">← 返回</a>
    <button type="button" id="live-refresh-btn" class="live-refresh-btn">更新数据</button>
    <span id="live-refresh-status" class="live-refresh-status" aria-live="polite"></span>
  </div>
  <h1>{esc(primary_title)}</h1>

  {hand_meta}

  {new_evidence}

  <div id="live-street-compare">{street_block}</div>

  <div class="footer">忽略字段：userId / handId / eventId / gtoType / 时间戳。证据页按「正确值 vs Chess API」对照；进入/刷新会重拉正确值与 Trace。请保持 python3 scripts/trace_config_server.py 运行。</div>
</div>
<script type="application/json" id="live-trace-payload">{live_json}</script>
<script>
document.querySelectorAll('[data-scroll-focus]').forEach(function(box) {{
  var el = box.querySelector('.json-focus-hot, .json-focus, #focus-sys, #focus-gt, .mark-diff');
  if (!el) return;
  var pre = el.closest('pre');
  if (pre) {{
    var top = el.offsetTop - pre.offsetTop - 40;
    pre.scrollTop = Math.max(0, top);
  }}
}});
{EVIDENCE_JS}
{LIVE_TRACE_JS}
</script>
</body></html>
"""
    out_path.write_text(body, encoding="utf-8")


def overview_issue_meta(
    gt: Optional[dict], sys: Optional[dict], exact: Optional[bool]
) -> tuple[int, list[str], str]:
    """Semantic count / kinds / first title for overview scan."""
    if exact is True:
        return 0, [], ""
    if exact is None:
        return 0, [], "无对照"
    if not gt or not sys:
        return 0, [], "缺少报文"
    blocks = build_issue_blocks(gt, sys)
    kinds: list[str] = []
    for b in blocks:
        k = str(b.get("kind") or "").strip()
        if k and k not in kinds:
            kinds.append(k)
    first = str(blocks[0].get("title") or "") if blocks else ""
    return len(blocks), kinds, first


def render_pills(kinds: list[str], limit: int = 3) -> str:
    if not kinds:
        return '<span class="pill more">—</span>'
    shown = kinds[:limit]
    parts = [f'<span class="pill">{esc(k)}</span>' for k in shown]
    extra = len(kinds) - len(shown)
    if extra > 0:
        parts.append(f'<span class="pill more">+{extra}</span>')
    return f'<div class="pill-row">{"".join(parts)}</div>'


def render_preview(first: str, total: int) -> str:
    if not first and total <= 0:
        return '<span class="one-line">—</span>'
    more = f'<span class="more">+{total - 1}</span>' if total > 1 else ""
    return f'<div class="one-line" title="{esc(first)}">{esc(first)}{more}</div>'


def render_index(
    results: list[HandResult],
    metrics: dict,
    out_path: Path,
    *,
    trace_cfg: Optional[dict] = None,
    run_id: Optional[str] = None,
) -> None:
    cfg = trace_cfg if trace_cfg is not None else {}
    form_html = render_trace_query_form(cfg, standalone=False, run_id=run_id)
    bugs = load_hand_bugs()
    rows_html = []
    for r in results:
        href = f"hands/{r.hand_uid}.html"
        n_chess = int(r.chess_diff_count or 0)
        kinds_chess = list(r.chess_categories or [])
        first_chess = str(r.chess_first_issue or "")
        n_old, kinds_old, first_old = overview_issue_meta(r.gt_norm, r.old_norm, r.old_exact)
        # 兼容：旧列仍可从 new_* 取（默认隐藏）
        n_new, kinds_new, first_new = overview_issue_meta(r.gt_norm, r.new_norm, r.new_exact)
        meta = bug_meta_for(bugs, r.hand_uid)
        st = meta["status"]
        owner = meta["owner"]
        note = meta["note"]
        st_opts = "".join(
            f'<option value="{html.escape(s)}"'
            f'{" selected" if s == st else ""}>'
            f'{html.escape(BUG_STATUS_LABELS.get(s, s) or "未标记")}</option>'
            for s in BUG_STATUSES
        )
        q = " ".join(
            [
                r.hole_key,
                r.hand_uid,
                first_chess,
                first_new,
                first_old,
                " ".join(kinds_chess),
                " ".join(kinds_new),
                " ".join(kinds_old),
                st,
                owner,
                note,
            ]
        )
        chess_n_cell = (
            str(n_chess)
            if r.chess_exact is False
            else ("0" if r.chess_exact is True else "—")
        )
        if r.chess_exact is False:
            kinds_cell = render_pills(kinds_chess)
            first_cell = render_preview(first_chess, n_chess)
        elif r.chess_exact is True:
            kinds_cell = render_pills([])
            first_cell = render_preview("", 0)
        else:
            kinds_cell = '<span class="pill more">—</span>'
            first_cell = '<span class="one-line">Chess API 无值</span>'
        rows_html.append(
            f"<tr id='hand-{esc(r.hand_uid)}' data-hand='{esc(r.hand_uid)}' data-old='{esc(r.old_exact)}' "
            f"data-new='{esc(r.chess_exact if r.chess_exact is not None else 'None')}' data-csv='{esc(r.new_exact if r.new_exact is not None else 'None')}' "
            f"data-bug-status='{esc(st)}' data-bug-owner='{esc(owner)}' data-bug-note='{esc(note)}' data-q='{esc(q)}'>"
            f"<td><a class='hand-link' href='{href}' data-hand='{esc(r.hand_uid)}'>{esc(r.hand_uid)}</a></td>"
            f"<td><code>{esc(r.hole_key)}</code></td>"
            f"<td class='bug-cell'><select class='bug-status' data-hand='{esc(r.hand_uid)}'>{st_opts}</select></td>"
            f"<td class='bug-cell'><input class='bug-owner' data-hand='{esc(r.hand_uid)}' type='text' "
            f"placeholder='姓名' value='{esc(owner)}' maxlength='32'/></td>"
            f"<td class='bug-note-cell'><textarea class='bug-note' data-hand='{esc(r.hand_uid)}' "
            f"placeholder='备注' rows='3' maxlength='500'>{esc(note)}</textarea></td>"
            f"<td class='col-old'>{badge_exact(r.old_exact)}</td>"
            f"<td>{badge_chess(r.chess_exact)}</td>"
            f"<td class='col-old'>{change_badge(r)}</td>"
            f"<td class='num'>{chess_n_cell}</td>"
            f"<td>{kinds_cell}</td>"
            f"<td class='preview'>{first_cell}</td>"
            f"<td class='col-old num'>{n_old if r.old_exact is False else ('0' if r.old_exact is True else '—')}</td>"
            f"<td class='col-old'>{render_pills(kinds_old)}</td>"
            f"<td class='col-old preview'>{render_preview(first_old, n_old)}</td>"
            f"<td><a class='hand-link' href='{href}' data-hand='{esc(r.hand_uid)}'>打开证据页</a></td>"
            "</tr>"
        )

    cat_rows = []
    for cat, cnt in metrics.get("chess_category_counts") or []:
        cat_rows.append(f"<tr><td>{esc(cat)}</td><td>{cnt}</td></tr>")

    top_rows = []
    for r in metrics["top_failures"]:
        n_chess = int(getattr(r, "chess_diff_count", 0) or 0)
        kinds_chess = list(getattr(r, "chess_categories", None) or [])
        first_chess = str(getattr(r, "chess_first_issue", "") or "")
        top_rows.append(
            f"<tr><td><a class='hand-link' href='hands/{r.hand_uid}.html' data-hand='{esc(r.hand_uid)}'>{esc(r.hand_uid)}</a></td>"
            f"<td><code>{esc(r.hole_key)}</code></td>"
            f"<td class='num'>{n_chess}</td>"
            f"<td>{render_pills(kinds_chess)}</td>"
            f"<td class='preview'>{render_preview(first_chess, n_chess)}</td></tr>"
        )

    filter_status_opts = "".join(
        f'<option value="{html.escape(s)}">{html.escape(BUG_STATUS_LABELS.get(s, s) or "未标记")}</option>'
        for s in BUG_STATUSES
    )

    body = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>GTO 行动历史还原质量对比</title><style>{CSS}</style></head><body class="hide-old">
<div class="wrap">
  <div class="nav"><a href="/">← 返回</a></div>
  <h1>GTO 行动历史还原质量对比</h1>
  <div class="sub">主对照口径：<b>正确值 vs Chess API（fusionCorrectedData）</b>。
  Chess 无值时总览显示「Chess API 无值」，差异处为 —（不算不一致）。
  生成时间：{esc(metrics['generated_at'])}
  {("· <b>本批手牌 " + str(metrics.get("batch_hand_n")) + " 手</b>：" + esc(", ".join(metrics.get("batch_hands") or [])) + "（仅生成这些）") if metrics.get("batch_hands") else ""}
  · <a href="trace_query.html">单独打开查询条件页</a></div>

  {form_html}

  <div class="cards">
    <div class="card"><div class="label">可对齐手数（有正确值）</div><div class="value">{metrics['comparable_n']}</div></div>
    <div class="card"><div class="label">Chess 整包准确率</div><div class="value">{metrics.get('chess_accuracy_pct', 0)}%</div>
      <div class="hint">{metrics.get('chess_exact_n', 0)}/{metrics.get('chess_comparable_n', 0)} · 无值 {metrics.get('chess_missing_n', 0)}</div></div>
    <div class="card col-old"><div class="label">{LABEL_OLD}整包准确率</div><div class="value">{metrics['old_accuracy_pct']}%</div>
      <div class="hint">{metrics['old_exact_n']}/{metrics['old_comparable_n']}</div></div>
    <div class="card col-old"><div class="label">{LABEL_NEW} CSV 准确率</div><div class="value">{metrics['new_accuracy_pct']}%</div>
      <div class="hint">{metrics['new_exact_n']}/{metrics['new_comparable_n']}</div></div>
    <div class="card"><div class="label">Trace 已归因手数</div><div class="value">{metrics.get('trace_attributed_n', 0)}</div>
      <div class="hint">拉取 {metrics.get('trace_fetched_n', 0)} / 命中 {metrics.get('trace_hit_n', 0)} / 锚点 {metrics.get('trace_anchored_n', 0)}</div></div>
  </div>

  <details class="fold-section">
    <summary>问题分类统计（手数，一手可多类 · Chess）</summary>
    <div class="fold-body table-scroll"><table><thead><tr><th>问题类</th><th>Chess 手数</th></tr></thead>
    <tbody>{''.join(cat_rows) or '<tr><td colspan=2>无</td></tr>'}</tbody></table></div>
  </details>

  <details class="fold-section">
    <summary>Top 失败 case（按 Chess 差异处）</summary>
    <div class="fold-body table-scroll"><table><thead><tr>
      <th>手牌</th><th>hole_cards_p0</th><th>差异处</th><th>问题类</th><th>首要问题</th>
    </tr></thead>
    <tbody>{''.join(top_rows) or '<tr><td colspan=5>无</td></tr>'}</tbody></table></div>
  </details>

  <h2>全部手牌</h2>
  <div class="sub" style="margin-top:-8px">主列 = Chess API vs 正确值。无 Chess 时显示「Chess API 无值」，差异处为 —。
  Bug 状态 / 负责人 / 备注可直接改，自动保存到 <code>data/hand_bugs.json</code>（需本地服务）。
  <span class="bug-save-hint" id="bug-save-hint"></span></div>
  <div class="filters">
    <input id="q" type="search" placeholder="搜索 HAND / 底牌 / 问题 / 负责人 / 备注"/>
    <select id="fnew">
      <option value="">Chess：全部</option>
      <option value="True">Chess 一致</option>
      <option value="False">Chess 不一致</option>
      <option value="None">Chess API 无值</option>
    </select>
    <select id="fold">
      <option value="">{LABEL_OLD}：全部</option>
      <option value="True">{LABEL_OLD}一致</option>
      <option value="False">{LABEL_OLD}不一致</option>
      <option value="None">{LABEL_OLD}无对照</option>
    </select>
    <select id="fbug">
      <option value="">Bug 状态：全部</option>
      {filter_status_opts}
    </select>
    <label class="toggle"><input type="checkbox" id="showOld"/> 显示{LABEL_OLD}对比</label>
  </div>
  <div class="table-scroll"><table id="all"><thead><tr>
    <th>ID</th><th>hole_cards_p0</th>
    <th>Bug状态</th><th>负责人</th><th>备注</th>
    <th class="col-old">{LABEL_OLD}</th><th>Chess API</th><th class="col-old">变化</th>
    <th>Chess 差异处</th><th>问题类</th><th>首要问题</th>
    <th class="col-old">{LABEL_OLD}差异处</th>
    <th class="col-old">{LABEL_OLD}问题类</th>
    <th class="col-old">{LABEL_OLD}首要问题</th>
    <th>证据页</th>
  </tr></thead><tbody>{''.join(rows_html)}</tbody></table></div>

  <div class="meta-box" style="margin-top:28px">
    <b>口径说明</b>
    <ul>
      <li>总览与证据页主对照均为 <b>正确值 vs Chess API（fusionCorrectedData）</b>。</li>
      <li>Chess 无值（未取到 fusionCorrectedData）：状态为「Chess API 无值」，差异处显示 —，<b>不算不一致</b>。</li>
      <li>比对忽略 userId / handId / eventId / gtoType / 时间戳；真值裁剪到 P0 最后一次行动前。</li>
      <li>{LABEL_OLD} 列默认隐藏，勾选「显示{LABEL_OLD}对比」后展开（历史 CSV 对照，非主口径）。</li>
      <li>Bug 状态 / 负责人 / 备注：写入 <code>data/hand_bugs.json</code>；重跑报告不会清空。</li>
    </ul>
  </div>
  <div class="footer">可复用脚本：scripts/compare_gto_requests.py</div>
</div>
<script>
const q=document.getElementById('q'), fnew=document.getElementById('fnew'), fold=document.getElementById('fold');
const fbug=document.getElementById('fbug');
const showOld=document.getElementById('showOld');
const hint=document.getElementById('bug-save-hint');
function setHint(msg, ok){{
  if (!hint) return;
  hint.textContent = msg || '';
  hint.className = 'bug-save-hint' + (ok === true ? ' ok' : (ok === false ? ' err' : ''));
}}
function apply(){{
  const qq=q.value.trim().toLowerCase();
  document.querySelectorAll('#all tbody tr').forEach(tr=>{{
    const text=tr.innerText.toLowerCase();
    const okQ=!qq || text.includes(qq) || (tr.dataset.q||'').toLowerCase().includes(qq);
    const okN=!fnew.value || tr.dataset.new===fnew.value;
    const okO=!fold.value || tr.dataset.old===fold.value;
    const st = (tr.querySelector('.bug-status') || {{}}).value;
    const okBug = !fbug.value || st === fbug.value;
    tr.style.display=(okQ&&okN&&okO&&okBug)?'':'none';
  }});
}}
function syncOld(){{
  document.body.classList.toggle('hide-old', !showOld.checked);
}}
q.addEventListener('input', apply); fnew.addEventListener('change', apply); fold.addEventListener('change', apply);
if (fbug) fbug.addEventListener('change', apply);
showOld.addEventListener('change', syncOld);
syncOld();

function bugEndpoints(path){{
  return [
    'http://127.0.0.1:8766'+path,
    'http://localhost:8766'+path,
    'http://127.0.0.1:8765'+path,
    'http://localhost:8765'+path
  ];
}}
function collectBugs(){{
  const hands = {{}};
  // 每一行都提交（含清空），服务端合并时：页内手牌可改/可清，页外手牌保留
  document.querySelectorAll('#all tbody tr[data-hand]').forEach(tr=>{{
    const id = tr.getAttribute('data-hand');
    const st = (tr.querySelector('.bug-status') || {{}}).value || '';
    const owner = ((tr.querySelector('.bug-owner') || {{}}).value || '').trim();
    const note = ((tr.querySelector('.bug-note') || {{}}).value || '').trim();
    tr.dataset.bugStatus = st;
    tr.dataset.bugOwner = owner;
    tr.dataset.bugNote = note;
    hands[id] = {{ status: st, owner: owner, note: note }};
  }});
  return {{ hands: hands, merge: true }};
}}
let saveTimer = null;
function saveBugsSoon(){{
  apply();
  setHint('保存中…', null);
  if (saveTimer) clearTimeout(saveTimer);
  saveTimer = setTimeout(saveBugsNow, 350);
}}
function saveBugsNow(i){{
  i = i || 0;
  const urls = bugEndpoints('/save-hand-bugs');
  if (i >= urls.length) {{
    setHint('保存失败：请先运行 python3 scripts/trace_config_server.py', false);
    return;
  }}
  const body = collectBugs();
  fetch(urls[i], {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify(body)
  }}).then(function(res){{
    return res.json().then(function(data){{
      if (!res.ok) throw new Error((data && data.error) || ('HTTP '+res.status));
      setHint('已保存 ' + (data.path || 'data/hand_bugs.json'), true);
    }});
  }}).catch(function(){{ saveBugsNow(i + 1); }});
}}
function hydrateBugs(map){{
  const hands = (map && map.hands) ? map.hands : (map || {{}});
  document.querySelectorAll('#all tbody tr[data-hand]').forEach(tr=>{{
    const id = tr.getAttribute('data-hand');
    const m = hands[id] || {{}};
    const sel = tr.querySelector('.bug-status');
    const inp = tr.querySelector('.bug-owner');
    const noteEl = tr.querySelector('.bug-note');
    if (sel && m.status != null) sel.value = m.status || '';
    if (inp && m.owner != null) inp.value = m.owner || '';
    if (noteEl && m.note != null) noteEl.value = m.note || '';
    tr.dataset.bugStatus = (sel && sel.value) || '';
    tr.dataset.bugOwner = (inp && inp.value) || '';
    tr.dataset.bugNote = (noteEl && noteEl.value) || '';
  }});
  apply();
}}
function loadBugs(i){{
  i = i || 0;
  const urls = bugEndpoints('/api/hand-bugs');
  if (i >= urls.length) return;
  fetch(urls[i]).then(function(res){{ return res.json(); }}).then(function(data){{
    if (data && data.ok !== false) hydrateBugs(data);
  }}).catch(function(){{ loadBugs(i + 1); }});
}}
document.querySelectorAll('.bug-status').forEach(function(el){{
  el.addEventListener('change', saveBugsSoon);
}});
document.querySelectorAll('.bug-owner').forEach(function(el){{
  el.addEventListener('change', saveBugsSoon);
  el.addEventListener('keydown', function(e){{ if (e.key === 'Enter') {{ e.preventDefault(); el.blur(); }} }});
}});
document.querySelectorAll('.bug-note').forEach(function(el){{
  el.addEventListener('change', saveBugsSoon);
  el.addEventListener('blur', saveBugsSoon);
}});
loadBugs();

function rememberHand(id){{
  if (!id) return;
  try {{ sessionStorage.setItem('qa_last_hand', id); }} catch (e) {{}}
}}
function focusHand(id){{
  if (!id) return;
  const tr = document.getElementById('hand-' + id) ||
    document.querySelector('#all tbody tr[data-hand="' + id + '"]');
  if (!tr) return;
  // 若被筛选隐藏，先清筛选再定位
  if (tr.style.display === 'none') {{
    if (q) q.value = '';
    if (fnew) fnew.value = '';
    if (fold) fold.value = '';
    if (fbug) fbug.value = '';
    apply();
  }}
  tr.classList.add('jump-target');
  try {{
    tr.scrollIntoView({{ block: 'center', behavior: 'instant' in HTMLElement.prototype ? 'instant' : 'auto' }});
  }} catch (e) {{
    tr.scrollIntoView(true);
  }}
  setTimeout(function(){{ tr.classList.remove('jump-target'); }}, 2200);
}}
function restoreHandFocus(){{
  let id = (location.hash || '').replace(/^#/, '');
  if (id.indexOf('hand-') === 0) id = id.slice(5);
  if (!id) {{
    try {{ id = sessionStorage.getItem('qa_last_hand') || ''; }} catch (e) {{ id = ''; }}
  }}
  if (id) {{
    // 等 bug hydrate / 布局稳定后再滚
    setTimeout(function(){{ focusHand(id); }}, 60);
  }}
}}
document.querySelectorAll('a.hand-link[data-hand]').forEach(function(a){{
  a.addEventListener('click', function(){{
    rememberHand(a.getAttribute('data-hand'));
  }});
}});
window.addEventListener('hashchange', restoreHandFocus);
window.addEventListener('pageshow', restoreHandFocus);
restoreHandFocus();
</script>
</body></html>
"""
    out_path.write_text(body, encoding="utf-8")
    try:
        (out_path.parent / "trace_query.html").write_text(
            render_trace_query_page(cfg), encoding="utf-8"
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Recommendations from data
# ---------------------------------------------------------------------------

def build_recommendations(results: list[HandResult], metrics: dict) -> list[str]:
    recs = []
    new_map = dict(metrics["new_category_counts"])
    old_map = metrics["old_category_map"]

    if metrics["new_accuracy_pct"] < metrics["old_accuracy_pct"]:
        recs.append(
            f"{LABEL_NEW}整包准确率（{metrics['new_accuracy_pct']}%）低于{LABEL_OLD}（{metrics['old_accuracy_pct']}%），"
            f"优先排查导致回退的手牌（见 Top 失败与「{LABEL_NEW}回退」标记）。"
        )
    elif metrics["new_accuracy_pct"] > metrics["old_accuracy_pct"]:
        recs.append(
            f"{LABEL_NEW}整包准确率（{metrics['new_accuracy_pct']}%）高于{LABEL_OLD}（{metrics['old_accuracy_pct']}%），"
            "但仍有失败样本，建议按问题类集中修高频差异。"
        )
    else:
        recs.append("0703 / 0729 整包准确率持平，需看字段级与严重度是否改善。")

    hot = [c for c, n in metrics["new_category_counts"][:5]]
    if hot:
        recs.append(f"{LABEL_NEW}高频问题类：" + "、".join(hot) + "。由差异反推验证顺序建议：")
        if any("行动" in c for c in hot):
            recs.append("→ 行动序列类问题：在游戏引擎/智能补全对 actionSequence 的修补链路做回放单测（以真值裁剪结果为断言）。")
        if any("盲注" in c or "前注" in c for c in hot):
            recs.append("→ 盲注/前注类问题：核对视觉识别与消噪对 SB/BB/ante/straddle 的读取，以及引擎是否二次改写。")
        if any("公共牌" in c for c in hot):
            recs.append("→ 公共牌类问题：核对街次推进与 communityCards 截断是否与 HeroDoing 决策点一致。")
        if any("筹码" in c or "玩家" in c for c in hot):
            recs.append("→ 筹码/玩家信息：核对 initChips 与座位映射是否在消噪阶段被错误过滤。")

    boundary_n = sum(1 for r in results if r.boundary_flags)
    if boundary_n:
        recs.append(
            f"有 {boundary_n} 手存在 last_step 边界与「P0 最后行动前」不一致，"
            "说明部分失败不只是字段值错误，而是决策点选错/多截/少截。"
        )

    if metrics["regressed_n"]:
        recs.append(f"{LABEL_NEW}相对{LABEL_OLD}回退 {metrics['regressed_n']} 手，建议作为回归用例锁定。")
    if metrics["fixed_n"]:
        recs.append(f"{LABEL_NEW}修好 {metrics['fixed_n']} 手，可对照这些样本确认有效改动并防止回退。")

    recs.append(
        "建议下一步：打开证据页「模块数据链」，从最后一次 hero_action 的 business.request 出发，"
        "顺着同索引连线核对状态引擎 / 网关 / Chess API 各层 business.request，定位盲注或行动金额在哪一层开始偏离。"
    )
    return recs


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _center_ms_for_hand(r: HandResult) -> Optional[int]:
    for src in (r.gt_norm, r.new_norm, r.old_norm):
        ts = event_ts(src)
        if ts:
            return ts
    if r.hand_id:
        return wepoker_ts(r.hand_id)
    meta_ts = (r.new_shot_meta or {}).get("target_ts") or (r.old_shot_meta or {}).get("target_ts")
    if meta_ts:
        try:
            return int(meta_ts)
        except (TypeError, ValueError):
            pass
    return None


def attach_trace_chains(
    results: list[HandResult],
    *,
    env_id: str = "uat",
    hands_dir: Path,
    fetch_frames: bool = False,
    pad_minutes: int = 15,
    fallback_open_id: str = "",
    fixed_start: str = "",
    fixed_end: str = "",
    trace_cfg: Optional[dict] = None,
    api_base: str = "",  # deprecated, ignored
) -> dict[str, int]:
    from trace_envs import normalize_trace_env

    cfg = trace_cfg or {}
    try:
        eid = normalize_trace_env(
            env_id or cfg.get("traceEnv") or "uat"
        )
    except KeyError:
        eid = "uat"
    client = TraceClient(
        env_id=eid,
        base_url=str(api_base or cfg.get("api") or "").strip(),
    )
    stats = {"fetched": 0, "hit": 0, "attributed": 0, "errors": 0, "anchored": 0}
    for r in results:
        stats["fetched"] += 1
        center = _center_ms_for_hand(r)
        q = resolve_trace_query(
            cfg,
            hand_uid=r.hand_uid,
            hole_key=r.hole_key,
            data_open_id=(r.new_user_token or r.user_token or ""),
        )
        # CLI fixed window / openId still win when explicitly passed
        if fallback_open_id and not cfg.get("openId"):
            q["fallback_open_id"] = fallback_open_id
            if not q.get("open_id"):
                q["open_id"] = fallback_open_id
        if fixed_start and fixed_end:
            q["start_time"] = fixed_start
            q["end_time"] = fixed_end
        if pad_minutes and not (q.get("start_time") and q.get("end_time")):
            q["pad_minutes"] = pad_minutes
        q["trace_env"] = eid
        if not q.get("env_label"):
            from trace_envs import get_trace_env

            q["env_label"] = get_trace_env(eid).get("env_label") or eid
        r.trace_query = q

        try:
            fetched = fetch_hand_spans(
                client,
                open_id=q.get("open_id") or "",
                hole_key=q.get("cards") or r.hole_key,
                center_ms=center,
                created_at=r.created_at_old or r.created_at_new,
                pad_minutes=int(q.get("pad_minutes") or pad_minutes or 15),
                fallback_open_id=q.get("fallback_open_id") or "",
                fixed_start=q.get("start_time") or "",
                fixed_end=q.get("end_time") or "",
            )
        except Exception as e:
            stats["errors"] += 1
            chain = analyze_hand_trace(
                [],
                gt_norm=r.gt_norm,
                fetch_meta={"error": str(e), "query": q},
            )
            r.trace_chain = chain
            continue

        # Persist resolved query alongside fetch meta for evidence page / sidecar
        fetched = dict(fetched)
        fetched["query"] = q

        spans = fetched.get("spans") or []
        if spans:
            stats["hit"] += 1
        if fetch_frames and spans and (fetched.get("open_id") or q.get("open_id") or r.user_token):
            keys = extract_msg_keys(spans)
            if keys:
                try:
                    frames = client.image_frames_by_keys(
                        open_id=fetched.get("open_id") or q.get("open_id") or r.user_token,
                        msg_keys=keys[:40],
                    )
                    fetched["key_frames_n"] = len(frames or [])
                except TraceClientError as e:
                    fetched["key_frames_error"] = str(e)

        chain = analyze_hand_trace(spans, gt_norm=r.gt_norm, fetch_meta=fetched)
        r.trace_chain = chain
        r.root_cause_module = chain.get("root_cause_module")
        r.root_cause_title = chain.get("root_cause_title")
        if r.root_cause_module:
            stats["attributed"] += 1
        if chain.get("anchor_mode") in (
            "last_hero_action",
            "first_dealer_change_last_hero",
        ):
            stats["anchored"] += 1

        sidecar = hands_dir / f"{r.hand_uid}.trace.json"
        slim_fetch = {k: v for k, v in fetched.items() if k != "spans"}
        chain_out = dict(chain)
        chain_out["fetch"] = slim_fetch
        chain_out["query"] = q
        sidecar.write_text(
            json.dumps(chain_to_sidecar(chain_out), ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
    return stats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--old",
        default="",
        help="Old Excel path（正确值来源）。若指定 --gt-version 则可省略。",
    )
    ap.add_argument("--new", required=True, help="New CSV path")
    ap.add_argument("--outdir", required=True, help="Output directory")
    ap.add_argument(
        "--gt-version",
        default="",
        help="使用正确值版本库中的版本 ID（或 current）。指定后可不读 Excel。",
    )
    ap.add_argument(
        "--import-gt",
        default="",
        help="从 --old Excel 导入正确值到该版本 ID 后退出（例：20260807-from-excel）",
    )
    ap.add_argument(
        "--freeze-run",
        default="",
        help="生成报告后冻结为 Run ID（写入 data/runs/<id>/）",
    )
    ap.add_argument(
        "--freeze-tags",
        default="",
        help="冻结 Run 的标签，逗号分隔",
    )
    ap.add_argument(
        "--freeze-note",
        default="",
        help="冻结 Run 备注",
    )
    ap.add_argument(
        "--skip-trace",
        action="store_true",
        help="跳过 Trace 拉取（管理页重跑默认开启；证据页仍可浏览器补拉）",
    )
    ap.add_argument(
        "--shots",
        default="",
        help="Renamed screenshot folder (手牌_usertoken_时间戳.jpg) — used to match hole cards",
    )
    ap.add_argument(
        "--orig-shots",
        default="",
        help="Original screenshot folder (usertoken_时间戳.jpg). Prefer for display/gallery.",
    )
    ap.add_argument(
        "--trace-api",
        default="",
        help="(已废弃) 旧 HTTP API 地址；现改为直连 ClickHouse，请用 --trace-env",
    )
    ap.add_argument(
        "--trace-env",
        default="",
        help="Trace ClickHouse 环境 id（默认读配置 traceEnv，目前仅 uat）",
    )
    ap.add_argument(
        "--trace-pad-minutes",
        type=int,
        default=15,
        help="Time window half-width (minutes) around decision ts for traceQuery",
    )
    ap.add_argument(
        "--trace-frames",
        action="store_true",
        help="Also fetch key frames via imageFramesByKeys (slower)",
    )
    ap.add_argument(
        "--trace-open-id",
        default="",
        help="Fixed fallback openId when hand user_token misses "
        "(or env TRACE_OPEN_ID). Example: 693ba6566e468032",
    )
    ap.add_argument(
        "--trace-start",
        default="",
        help="Fixed startTime for all hands (or env TRACE_START), e.g. '2026-08-03 18:30:00'",
    )
    ap.add_argument(
        "--trace-end",
        default="",
        help="Fixed endTime for all hands (or env TRACE_END), e.g. '2026-08-03 23:59:59'",
    )
    ap.add_argument(
        "--trace-config",
        default="",
        help="Trace 查询条件配置 JSON（默认 data/trace_query.json）。"
        "可配 openId/startTime/endTime/api，及按手牌覆盖。",
    )
    ap.add_argument(
        "--hands",
        default="",
        help="只跑指定手牌（逗号分隔），如 HAND_001,HAND_006 或 1,6,14；留空=全部",
    )
    args = ap.parse_args()

    import os

    from gt_store import (
        get_current_gt_version_id,
        import_gt_from_excel,
        load_gt_version,
    )
    from run_store import freeze_run

    if args.import_gt:
        if not args.old:
            raise SystemExit("--import-gt 需要同时提供 --old Excel")
        meta = import_gt_from_excel(
            args.old,
            args.import_gt,
            tags=["from-excel"],
            note="CLI 导入",
            set_current=True,
        )
        print(json.dumps(meta, ensure_ascii=False, indent=2))
        return

    trace_cfg_path = (args.trace_config or os.environ.get("TRACE_CONFIG") or "").strip()
    if not trace_cfg_path:
        default_cfg = Path(__file__).resolve().parent.parent / "data" / "trace_query.json"  # optional legacy
        if default_cfg.exists():
            trace_cfg_path = str(default_cfg)
    trace_cfg = load_trace_query_config(trace_cfg_path) if trace_cfg_path else {}

    from trace_envs import DEFAULT_TRACE_ENV, normalize_trace_env

    skip_trace = bool(getattr(args, "skip_trace", False))
    raw_env = (
        (getattr(args, "trace_env", None) or os.environ.get("TRACE_ENV") or "").strip()
        or str(trace_cfg.get("traceEnv") or DEFAULT_TRACE_ENV)
    )
    try:
        trace_env = "" if skip_trace else normalize_trace_env(raw_env)
    except KeyError as e:
        raise SystemExit(str(e)) from e

    trace_open_id = (args.trace_open_id or os.environ.get("TRACE_OPEN_ID") or "").strip()
    if not trace_open_id and trace_cfg.get("openId"):
        # Prefer config openId; empty CLI means "use config"
        trace_open_id = ""
    trace_start = (args.trace_start or os.environ.get("TRACE_START") or "").strip()
    if not trace_start and trace_cfg.get("startTime"):
        trace_start = ""
    trace_end = (args.trace_end or os.environ.get("TRACE_END") or "").strip()
    if not trace_end and trace_cfg.get("endTime"):
        trace_end = ""
    # Temporary fixed CRM openId only when neither CLI nor config provides one
    if not trace_open_id and not (trace_cfg.get("openId") or "").strip():
        trace_open_id = "693ba6566e468032"

    outdir = Path(args.outdir)
    hands_dir = outdir / "hands"
    assets_dir = hands_dir / "assets"
    hands_dir.mkdir(parents=True, exist_ok=True)

    new_df = pd.read_csv(args.new)
    gt_version_id = (args.gt_version or "").strip()
    if gt_version_id in ("", "current", "CURRENT"):
        gt_version_id = get_current_gt_version_id() or ""

    if gt_version_id:
        gt_meta, gt_hands = load_gt_version(gt_version_id)
        print(f"GT version: {gt_meta.get('id')} (hands={len(gt_hands)})")
        pairs = align_hands_from_gt(gt_hands, new_df)
    else:
        if not args.old:
            raise SystemExit("未指定 --gt-version 时必须提供 --old Excel")
        old_df = pd.read_excel(args.old)
        pairs = align_hands(old_df, new_df)
        gt_version_id = None

    batch_hands = parse_hand_uids(getattr(args, "hands", "") or "")
    if batch_hands:
        try:
            pairs = filter_pairs_by_hands(pairs, batch_hands)
        except ValueError as e:
            raise SystemExit(str(e)) from e
        print(f"Batch hands ({len(pairs)}): {', '.join(batch_hands)}")

    # 子集跑批前清掉旧证据页，避免 freeze 把上轮全量手牌拷进本 Run
    for pat in ("HAND_*.html", "HAND_*.trace.json"):
        for stale in hands_dir.glob(pat):
            try:
                stale.unlink()
            except OSError:
                pass

    shot_index = index_screenshots(Path(args.shots)) if args.shots else {}
    orig_dir = Path(args.orig_shots) if args.orig_shots else None
    # Sensible default next to renamed folder if not provided
    if (not orig_dir or not orig_dir.exists()) and args.shots:
        guess = Path("/Users/xixi/Downloads/0713图片和json")
        if guess.exists():
            orig_dir = guess
    orig_index = index_original_shots(orig_dir) if orig_dir else {}

    results = [analyze_pair(p) for p in pairs]

    # Attach hand-first-frame screenshots (original file:// refs)
    for r in results:
        if not shot_index and not orig_index:
            continue
        old_pick = pick_problem_frame(
            shot_index,
            r.hole_key,
            r.user_token,
            r.gt_norm,
            r.old_norm,
            orig_index=orig_index,
            orig_dir=orig_dir,
        )
        new_pick = pick_problem_frame(
            shot_index,
            r.hole_key,
            r.user_token,
            r.gt_norm,
            r.new_norm,
            orig_index=orig_index,
            orig_dir=orig_dir,
        )
        r.old_shot_meta = {
            "reason": old_pick.get("reason"),
            "target_ts": old_pick.get("target_ts"),
            "n_frames": old_pick.get("n_frames"),
            "gallery_mode": old_pick.get("gallery_mode"),
        }
        r.new_shot_meta = {
            "reason": new_pick.get("reason"),
            "target_ts": new_pick.get("target_ts"),
            "n_frames": new_pick.get("n_frames"),
            "gallery_mode": new_pick.get("gallery_mode"),
        }
        old_gallery_src = old_pick.get("gallery") or (
            [old_pick["primary"]] if old_pick.get("primary") else []
        )
        new_gallery_src = new_pick.get("gallery") or (
            [new_pick["primary"]] if new_pick.get("primary") else []
        )
        if old_gallery_src:
            r.old_shot_gallery = gallery_file_refs(old_gallery_src)
            r.old_shot_start = int(old_pick.get("start_index") or 0)
            if r.old_shot_gallery:
                idx = min(r.old_shot_start, len(r.old_shot_gallery) - 1)
                r.old_shot_rel = r.old_shot_gallery[idx]["rel"]
        if new_gallery_src:
            same = (
                old_gallery_src
                and len(old_gallery_src) == len(new_gallery_src)
                and all(a[1] == b[1] for a, b in zip(old_gallery_src, new_gallery_src))
                and r.old_shot_gallery
            )
            if same:
                r.new_shot_gallery = list(r.old_shot_gallery)
                r.new_shot_start = int(new_pick.get("start_index") or 0)
            else:
                r.new_shot_gallery = gallery_file_refs(new_gallery_src)
                r.new_shot_start = int(new_pick.get("start_index") or 0)
            if r.new_shot_gallery:
                idx = min(r.new_shot_start, len(r.new_shot_gallery) - 1)
                r.new_shot_rel = r.new_shot_gallery[idx]["rel"]

    trace_stats = {"fetched": 0, "hit": 0, "attributed": 0, "errors": 0}
    if trace_env:
        print(f"Trace env (data-platform API): {trace_env}")
        if trace_cfg_path:
            print(f"Trace config: {trace_cfg_path}")
        if trace_cfg.get("openId"):
            print(f"Trace config openId: {trace_cfg.get('openId')} (mode={trace_cfg.get('openIdMode') or 'config_first'})")
        if trace_open_id:
            print(f"Trace CLI openId/fallback: {trace_open_id}")
        win_s = trace_start or trace_cfg.get("startTime") or ""
        win_e = trace_end or trace_cfg.get("endTime") or ""
        if win_s and win_e:
            print(f"Trace window: {win_s} ~ {win_e}")
            try:
                from trace_client import TraceClient as _TC
                from trace_envs import resolve_api_base as _rab

                _api = _rab(trace_env, override=str(trace_cfg.get("api") or ""))
                print(f"Trace API: {_api}")
                _disc = _TC(env_id=trace_env, base_url=_api).trace_discover(
                    start_time=str(win_s), end_time=str(win_e)
                ) or []
                _hcs = sorted({str(d.get("holeCards") or "") for d in _disc if d.get("holeCards")})
                _oids = sorted({str(d.get("openId") or "") for d in _disc if d.get("openId")})
                print(
                    f"Trace discover: sessions={len(_disc)} openIds={_oids or ['—']} "
                    f"holeCards={_hcs or ['—']}"
                )
            except Exception as _e:
                print(f"Trace discover: failed ({_e})")
        pad = int(args.trace_pad_minutes)
        if trace_cfg.get("padMinutes") is not None and not (win_s and win_e):
            try:
                pad = int(trace_cfg.get("padMinutes"))
            except Exception:
                pass
        trace_stats = attach_trace_chains(
            results,
            env_id=trace_env,
            hands_dir=hands_dir,
            fetch_frames=bool(args.trace_frames),
            pad_minutes=pad,
            fallback_open_id=trace_open_id,
            fixed_start=trace_start,
            fixed_end=trace_end,
            trace_cfg=trace_cfg,
        )
        print(
            f"Trace: fetched={trace_stats['fetched']} hit={trace_stats['hit']} "
            f"anchored={trace_stats.get('anchored', 0)} "
            f"attributed={trace_stats['attributed']} errors={trace_stats['errors']}"
        )

    attach_chess_overview(results)

    comparable = [r for r in results if r.has_gt]
    old_comp = [r for r in comparable if r.has_old]
    new_comp = [r for r in comparable if r.has_new]
    chess_comp = [r for r in comparable if r.chess_exact is not None]
    chess_missing = [r for r in comparable if r.chess_exact is None]
    old_exact_n = sum(1 for r in old_comp if r.old_exact)
    new_exact_n = sum(1 for r in new_comp if r.new_exact)
    chess_exact_n = sum(1 for r in chess_comp if r.chess_exact)

    both = [r for r in comparable if r.has_old and r.has_new]
    fixed_n = sum(1 for r in both if r.old_exact is False and r.new_exact is True)
    regressed_n = sum(1 for r in both if r.old_exact is True and r.new_exact is False)

    old_cat = Counter()
    new_cat = Counter()
    chess_cat = Counter()
    root_cat = Counter()
    for r in results:
        for c in r.old_categories:
            old_cat[c] += 1
        for c in r.new_categories:
            new_cat[c] += 1
        for c in r.chess_categories:
            chess_cat[c] += 1
        if r.root_cause_title:
            root_cat[r.root_cause_title] += 1

    top_failures = sorted(
        [r for r in chess_comp if r.chess_exact is False],
        key=lambda x: (-x.chess_diff_count, x.hand_uid),
    )[:15]

    metrics = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "comparable_n": len(comparable),
        "old_comparable_n": len(old_comp),
        "new_comparable_n": len(new_comp),
        "chess_comparable_n": len(chess_comp),
        "chess_missing_n": len(chess_missing),
        "old_exact_n": old_exact_n,
        "new_exact_n": new_exact_n,
        "chess_exact_n": chess_exact_n,
        "old_accuracy_pct": round(100.0 * old_exact_n / len(old_comp), 1) if old_comp else 0.0,
        "new_accuracy_pct": round(100.0 * new_exact_n / len(new_comp), 1) if new_comp else 0.0,
        "chess_accuracy_pct": round(100.0 * chess_exact_n / len(chess_comp), 1) if chess_comp else 0.0,
        "fixed_n": fixed_n,
        "regressed_n": regressed_n,
        "old_only_n": sum(1 for r in results if r.has_gt and not r.has_new),
        "new_only_n": sum(1 for r in results if r.has_new and not r.has_gt),
        "new_category_counts": new_cat.most_common(),
        "chess_category_counts": chess_cat.most_common(),
        "old_category_map": dict(old_cat),
        "root_cause_counts": root_cat.most_common(),
        "trace_fetched_n": trace_stats.get("fetched", 0),
        "trace_hit_n": trace_stats.get("hit", 0),
        "trace_anchored_n": trace_stats.get("anchored", 0),
        "trace_attributed_n": trace_stats.get("attributed", 0),
        "trace_env": trace_env or None,
        "batch_hands": batch_hands or None,
        "batch_hand_n": len(batch_hands) if batch_hands else None,
        "top_failures": top_failures,
    }
    recommendations = build_recommendations(results, metrics)
    hands_summary = []
    for r in results:
        if r.old_exact is False and r.new_exact is True:
            ch = f"{LABEL_NEW}修好"
        elif r.old_exact is True and r.new_exact is False:
            ch = f"{LABEL_NEW}回退"
        elif r.old_exact is False and r.new_exact is False:
            if r.new_severity < r.old_severity:
                ch = f"{LABEL_NEW}减轻"
            elif r.new_severity > r.old_severity:
                ch = f"{LABEL_NEW}加重"
            else:
                ch = "仍不一致"
        elif r.old_exact is True and r.new_exact is True:
            ch = "均正确"
        else:
            ch = "-"
        hands_summary.append(
            {
                "hand_uid": r.hand_uid,
                "hole_key": r.hole_key,
                "old_exact": r.old_exact,
                "new_exact": r.new_exact,
                "chess_exact": r.chess_exact,
                "chess_diff_count": r.chess_diff_count,
                "chess_categories": r.chess_categories,
                "chess_first_issue": r.chess_first_issue,
                "change": ch,
                "old_diff_count": r.old_diff_count,
                "new_diff_count": r.new_diff_count,
                "old_severity": r.old_severity,
                "new_severity": r.new_severity,
                "old_categories": r.old_categories,
                "new_categories": r.new_categories,
            }
        )
    metrics_out = {
        **{k: v for k, v in metrics.items() if k != "top_failures"},
        "gt_version_id": gt_version_id,
        "hands": hands_summary,
        "top_failures": [
            {
                "hand_uid": r.hand_uid,
                "hole_key": r.hole_key,
                "new_severity": r.new_severity,
                "new_diff_count": r.new_diff_count,
                "categories": r.new_categories,
                "root_cause_module": r.root_cause_module,
                "root_cause_title": r.root_cause_title,
            }
            for r in top_failures
        ],
        "recommendations": recommendations,
        "note_about_columns": (
            "比对使用 last_step_request。旧表 last_step_response 实为 GTO strategy 返回，不是请求报文。"
        ),
    }

    for r in results:
        render_hand_html(r, hands_dir / f"{r.hand_uid}.html")
    freeze_id = str(getattr(args, "freeze_run", "") or "").strip() or None
    render_index(
        results,
        metrics,
        outdir / "index.html",
        trace_cfg=trace_cfg,
        run_id=freeze_id,
    )

    (outdir / "summary.json").write_text(
        json.dumps(metrics_out, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # overview CSV matching HTML columns
    with (outdir / "hands_overview.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "ID",
                "hole_cards_p0",
                LABEL_OLD,
                LABEL_NEW,
                "变化",
                f"{LABEL_OLD}差异处",
                f"{LABEL_NEW}差异处",
                f"{LABEL_OLD}问题类",
                f"{LABEL_OLD}首要问题",
                f"{LABEL_NEW}问题类",
                f"{LABEL_NEW}首要问题",
            ]
        )
        for r in results:
            if r.old_exact is False and r.new_exact is True:
                ch = f"{LABEL_NEW}修好"
            elif r.old_exact is True and r.new_exact is False:
                ch = f"{LABEL_NEW}回退"
            elif r.old_exact is False and r.new_exact is False:
                if r.new_severity < r.old_severity:
                    ch = f"{LABEL_NEW}减轻"
                elif r.new_severity > r.old_severity:
                    ch = f"{LABEL_NEW}加重"
                else:
                    ch = "仍不一致"
            elif r.old_exact is True and r.new_exact is True:
                ch = "均正确"
            else:
                ch = "-"
            w.writerow(
                [
                    r.hand_uid,
                    r.hole_key,
                    {True: "一致", False: "不一致", None: "无对照"}[r.old_exact],
                    {True: "一致", False: "不一致", None: "无对照"}[r.new_exact],
                    ch,
                    r.old_diff_count,
                    r.new_diff_count,
                    "、".join(r.old_categories),
                    r.old_detail_fields,
                    "、".join(r.new_categories),
                    r.new_detail_fields,
                ]
            )

    # flat CSV
    with (outdir / "diff_table.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "hand_uid",
                "hole_cards_p0",
                "side",
                "exact_match",
                "diff_count",
                "severity",
                "categories",
                "friendly_detail",
                "path",
                "diff_type",
                "category",
                "gt_value",
                "sys_value",
            ]
        )
        for r in results:
            for side, exact, diffs, sev, cats, friendly in [
                ("old", r.old_exact, r.old_diffs, r.old_severity, r.old_categories, r.old_detail_fields),
                ("new", r.new_exact, r.new_diffs, r.new_severity, r.new_categories, r.new_detail_fields),
            ]:
                if not diffs:
                    w.writerow(
                        [
                            r.hand_uid,
                            r.hole_key,
                            side,
                            exact,
                            0,
                            sev,
                            "|".join(cats),
                            friendly,
                            "",
                            "",
                            "",
                            "",
                            "",
                        ]
                    )
                else:
                    for d in diffs:
                        w.writerow(
                            [
                                r.hand_uid,
                                r.hole_key,
                                side,
                                exact,
                                len(diffs),
                                sev,
                                "|".join(cats),
                                friendly,
                                d["path"],
                                d.get("type"),
                                d.get("category"),
                                json.dumps(d.get("left"), ensure_ascii=False),
                                json.dumps(d.get("right"), ensure_ascii=False),
                            ]
                        )

    # brief markdown report
    md = [
        "# GTO 行动历史还原质量报告",
        "",
        f"- 生成时间：{metrics['generated_at']}",
        f"- 可对齐手数（有真值）：{metrics['comparable_n']}",
        f"- {LABEL_OLD}整包准确率：{metrics['old_accuracy_pct']}% ({metrics['old_exact_n']}/{metrics['old_comparable_n']})",
        f"- {LABEL_NEW}整包准确率：{metrics['new_accuracy_pct']}% ({metrics['new_exact_n']}/{metrics['new_comparable_n']})",
        f"- {LABEL_NEW}修好：{metrics['fixed_n']}；回退：{metrics['regressed_n']}",
        "",
        "## 改进建议",
        "",
    ]
    for rec in recommendations:
        md.append(f"- {rec}")
    md.append("")
    md.append("打开 `index.html` 查看总览与逐手三方报文对比。")
    (outdir / "REPORT.md").write_text("\n".join(md), encoding="utf-8")

    print(json.dumps({k: metrics_out[k] for k in [
        "comparable_n", "old_accuracy_pct", "new_accuracy_pct", "fixed_n", "regressed_n",
        "old_exact_n", "new_exact_n", "old_comparable_n", "new_comparable_n"
    ]}, ensure_ascii=False, indent=2))
    print("HTML:", outdir / "index.html")

    if args.freeze_run:
        tags = [t.strip() for t in str(args.freeze_tags or "").split(",") if t.strip()]
        tq_path = Path(trace_cfg_path) if trace_cfg_path else None
        meta = freeze_run(
            args.freeze_run,
            source_dir=outdir,
            tags=tags,
            note=str(args.freeze_note or ""),
            gt_version_id=gt_version_id,
            trace_query_path=tq_path,
            overwrite=True,
        )
        print("Frozen run:", meta.get("id"), "→ data/runs/" + str(meta.get("id")))


if __name__ == "__main__":
    main()
