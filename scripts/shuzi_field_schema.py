"""Excel auto_json → 模拟器界面树，并盘点左侧字段路径（分母）。"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

POST_SKIP = {
    "POST_BLIND",
    "POST_ANTE",
    "ANTE",
    "STRADDLE",
    "POST_STRADDLE",
    "COST_ANTE",
    "COST_STRADDLE",
    "COST_SB",
    "COST_BB",
    "COST_BLIND",
}


def is_forced_post(act: Any) -> bool:
    """盲注 / 前注 / Straddle 等强制投入，不计入最后一口自愿动作。"""
    u = str(act or "").strip().upper().replace("-", "_").replace(" ", "_")
    if not u:
        return False
    if u in POST_SKIP:
        return True
    return u.startswith("POST_") or u.startswith("COST_")


def vis_total_pot(hand: dict | None) -> Any:
    """视觉终局总底池，与规则 result.total_pot 对齐。"""
    if not isinstance(hand, dict):
        return None
    settle = hand.get("settlement") if isinstance(hand.get("settlement"), dict) else {}
    pots = hand.get("pots_structure") if isinstance(hand.get("pots_structure"), dict) else {}
    info = hand.get("pots_info") if isinstance(hand.get("pots_info"), dict) else {}
    result = hand.get("result") if isinstance(hand.get("result"), dict) else {}
    for v in (
        result.get("total_pot"),
        settle.get("total_pot"),
        pots.get("total_pot"),
        info.get("total_pot"),
        settle.get("pot"),
        hand.get("final_pot"),
        hand.get("total_pot"),
    ):
        if v is None or v == "":
            continue
        n = parse_num(v)
        return n if n is not None else v
    return None


CATS = ("卡牌", "文字", "图像", "数字")
PAIRS = (
    {"id": "gt_vis", "title": "源数据 → 视觉", "left": "源数据", "right": "视觉", "totals": "gold"},
    {"id": "vis_rule", "title": "视觉 → 规则", "left": "视觉", "right": "规则", "totals": None},
    {"id": "gt_rule", "title": "源数据 → 规则", "left": "源数据", "right": "规则", "totals": "gold"},
)


def _g(d: Any, i: int, default=None):
    if not isinstance(d, dict):
        return default
    if i in d:
        return d[i]
    if str(i) in d:
        return d[str(i)]
    return default


def classify(path: str) -> str:
    p = path.lower()
    if any(x in p for x in ("avatar", "dealer", "status", "image", "img")):
        return "图像"
    if "card" in p:
        return "卡牌"
    if any(x in p for x in ("bet_amount", "chips", "seat", "pot", ".sb", ".bb", "ante", "player_count")):
        return "数字"
    return "文字"


def auto_json_to_ui(obj: dict) -> dict:
    n = int(obj.get("player_count") or len(obj.get("seat_positions") or {}) or 0)
    dealer = obj.get("dealer_position")
    nick = obj.get("seat_nicknames") or {}
    names = obj.get("seat_player_names") or {}
    pos = obj.get("seat_positions") or {}
    hole = obj.get("hole_cards") or {}
    final = obj.get("final_stacks") or {}
    last_act: dict[int, str] = {}
    last_bet: dict[int, Any] = {}
    folded: set[int] = set()
    for a in obj.get("actions") or []:
        act = str(a.get("action") or "")
        if is_forced_post(act):
            continue
        try:
            seat = int(a.get("seat"))
        except (TypeError, ValueError):
            continue
        last_act[seat] = act
        up = act.upper().replace(" ", "").replace("_", "-")
        if up in ("BET", "RAISE", "CALL", "ALL-IN", "ALLIN"):
            last_bet[seat] = a.get("amount", 0)
        if up == "FOLD":
            folded.add(seat)

    players = {}
    for i in range(n):
        cards_raw = _g(hole, i) or []
        card_map = {}
        for ci, card in enumerate(cards_raw):
            if card is None or card == "":
                continue
            card_map[f"P{ci}"] = {"value": card}
        showdown = bool(obj.get("is_showdown"))
        if i in folded:
            status = "fold"
        elif showdown:
            status = "show"
        else:
            status = "in_hand"
        players[f"P{i}"] = {
            "name": {"value": _g(nick, i) or _g(names, i) or ""},
            "action": {"value": last_act.get(i) or ""},
            "comment": {"value": ""},
            "cards": card_map,
            "bet_amount": {"value": last_bet.get(i, 0)},
            "chips": {"value": _g(final, i)},
            "seat": {"value": i},
            "dealer": {"value": dealer is not None and int(dealer) == i},
            "status": {"value": status},
            "position": {"value": _g(pos, i) or ""},
        }

    board: list[dict] = []
    for x in obj.get("flop") or []:
        if x:
            board.append({"value": x})
    for key in ("turn", "river"):
        v = obj.get(key)
        if isinstance(v, str) and v:
            board.append({"value": v})
        elif isinstance(v, list):
            board.extend({"value": x} for x in v if x)

    result = obj.get("result") or {}
    return {
        "players": players,
        "table": {
            "community_cards": board,
            "pot": {"value": result.get("total_pot")},
            "sb": {"value": obj.get("small_blind")},
            "bb": {"value": obj.get("big_blind")},
            "ante": {"value": obj.get("ante")},
            "player_count": {"value": n},
            "showdown": {"value": bool(obj.get("is_showdown"))},
        },
    }


def _emit_path(path: str) -> bool:
    if not path:
        return False
    if path.endswith(".value"):
        return True
    last = path.split(".")[-1].split("[")[0]
    return last in {"players", "table", "cards", "community_cards"}


def iter_paths(obj: Any, prefix: str = "") -> list[str]:
    out: list[str] = []
    if isinstance(obj, dict):
        if set(obj.keys()) == {"value"}:
            if prefix:
                out.append(f"{prefix}.value")
            return out
        if prefix and _emit_path(prefix):
            out.append(prefix)
        for k, v in obj.items():
            p = f"{prefix}.{k}" if prefix else str(k)
            out.extend(iter_paths(v, p))
        return out
    if isinstance(obj, list):
        if prefix and _emit_path(prefix):
            out.append(prefix)
        for i, v in enumerate(obj):
            out.extend(iter_paths(v, f"{prefix}[{i}]"))
        return out
    if prefix:
        out.append(prefix)
    return out


def inventory_from_ui_trees(trees: list[dict]) -> list[dict]:
    counts: Counter[str] = Counter()
    for tree in trees:
        counts.update(iter_paths(tree))
    rows = []
    for path, total in counts.items():
        rows.append({"path": path, "cat": classify(path), "total": int(total)})
    order = {c: i for i, c in enumerate(CATS)}
    rows.sort(key=lambda r: (order.get(r["cat"], 9), r["path"]))
    return rows


LEN_MARK = "__len__"


def flatten_values(obj: Any, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(obj, dict) and set(obj.keys()) == {"value"}:
        if prefix:
            out[f"{prefix}.value"] = obj.get("value")
        return out
    if isinstance(obj, dict):
        if prefix and _emit_path(prefix):
            out[prefix] = (LEN_MARK, len(obj))
        for k, v in obj.items():
            p = f"{prefix}.{k}" if prefix else str(k)
            out.update(flatten_values(v, p))
        return out
    if isinstance(obj, list):
        if prefix and _emit_path(prefix):
            out[prefix] = (LEN_MARK, len(obj))
        for i, v in enumerate(obj):
            out.update(flatten_values(v, f"{prefix}[{i}]"))
        return out
    if prefix:
        out[prefix] = obj
    return out


def parse_num(v: Any) -> float | None:
    if v is None or v is True or v is False:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", "")
    s = re.sub(r"(?i)\s*(bb|筹码)\s*$", "", s).strip()
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def values_equal(a: Any, b: Any) -> bool:
    if a is b:
        return True
    if isinstance(a, tuple) and isinstance(b, tuple) and a and a[0] == LEN_MARK:
        return a == b
    na, nb = parse_num(a), parse_num(b)
    if na is not None and nb is not None:
        return abs(na - nb) < 1e-9
    if isinstance(a, bool) or isinstance(b, bool):
        return bool(a) == bool(b)
    sa = "" if a is None else str(a).strip()
    sb = "" if b is None else str(b).strip()
    if sa.lower() == sb.lower():
        return True
    return sa == sb


def compare_flat(left: dict[str, Any], right: dict[str, Any] | None) -> dict[str, str]:
    """path -> match | mismatch | missing | len_mismatch. 右侧多的不要。"""
    out: dict[str, str] = {}
    right = right or {}
    for path, lv in left.items():
        if path not in right:
            out[path] = "missing"
            continue
        rv = right[path]
        left_len = isinstance(lv, tuple) and lv and lv[0] == LEN_MARK
        right_len = isinstance(rv, tuple) and rv and rv[0] == LEN_MARK
        if left_len or right_len:
            out[path] = "match" if lv == rv else "len_mismatch"
            continue
        if path.endswith(".name.value"):
            sa = "" if lv is None else str(lv)
            sb = "" if rv is None else str(rv)
            out[path] = "match" if sa == sb else "mismatch"
            continue
        out[path] = "match" if values_equal(lv, rv) else "mismatch"
    return out
