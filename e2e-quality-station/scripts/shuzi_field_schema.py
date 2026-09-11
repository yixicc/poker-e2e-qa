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
    """盲注 / 前注 / Straddle 等强制投入，不计入最后一次自愿动作。"""
    u = str(act or "").strip().upper().replace("-", "_").replace(" ", "_")
    if not u:
        return False
    if u in POST_SKIP:
        return True
    return u.startswith("POST_") or u.startswith("COST_")


def _copy_action_facts(dst: dict, src: dict) -> None:
    """只抄报文里有的过程字段，不推算底池和剩余筹码。"""
    if not isinstance(src, dict):
        return
    for src_k, dst_k in (
        ("timestamp", "timestamp"),
        ("time", "timestamp"),
        ("elapsed", "timestamp"),
        ("action_time", "timestamp"),
        ("ts", "timestamp"),
        ("pot_after", "pot"),
        ("current_pot", "pot"),
        ("potAfter", "pot"),
        ("pot", "pot"),
        ("remaining_chips", "chips"),
        ("chips_after", "chips"),
        ("remainingChips", "chips"),
        ("stack_after", "chips"),
        ("current_chips", "chips"),
        ("chipsAfter", "chips"),
    ):
        if dst_k in dst:
            continue
        if src_k not in src:
            continue
        v = src[src_k]
        if v is None or v == "":
            continue
        dst[dst_k] = v


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


CATS = ("卡牌", "行动", "文字", "图像", "数字")
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


def is_ui_snapshot_path(path: str) -> bool:
    """终局界面快照（最后一次动作、最后下注、空 comment），不参与还原比对。"""
    p = path.lower()
    if p.startswith("history."):
        return False
    if p == "players":
        return True
    if ".action" in p:
        return True
    if "bet_amount" in p:
        return True
    if ".comment" in p:
        return True
    return False


def skip_compare_path(path: str) -> bool:
    """翻前盲注/前注的位置动作金额只展示，不进匹配；底池变化仍要比。"""
    p = path or ""
    if not p.startswith("history.post."):
        return False
    return not p.endswith(".pot")


def classify(path: str) -> str:
    p = path.lower()
    if p.startswith("history."):
        return "行动"
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
    init = obj.get("init_stacks") or {}
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
            "init_chips": {"value": _g(init, i)},
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


STREET_KEY = {
    "PREFLOP": "preflop",
    "PRE_FLOP": "preflop",
    "FLOP": "flop",
    "TURN": "turn",
    "RIVER": "river",
}


def norm_street(s: Any) -> str:
    u = str(s or "").strip().upper().replace("-", "_").replace(" ", "_")
    if u in ("PRE_HAND", "PREHAND", "SETUP"):
        return ""
    return STREET_KEY.get(u, u.lower() if u else "")


def _card_list(raw: Any) -> list:
    if raw is None or raw is False or raw == "":
        return []
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [x for x in raw if x not in (None, "", False)]
    return [raw]


def _norm_act(act: Any) -> str:
    up = str(act or "").strip().upper().replace(" ", "_").replace("-", "_")
    if up in ("ALLIN", "ALL_IN"):
        return "ALL-IN"
    return up


def _has_chip(v: Any) -> bool:
    return v is not None and v != ""


def _round_chips(v: float) -> Any:
    if abs(v - round(v)) < 1e-6:
        return int(round(v))
    return v


def _action_puts_chips(act: Any) -> bool:
    u = _norm_act(act)
    if u in ("BET", "RAISE", "CALL", "ALL-IN"):
        return True
    lab = action_label(act)
    return lab in ("盲注", "前注", "straddle")


def fill_action_pots(hist: dict | None) -> dict | None:
    """逐步底池：报文有 pot 就用；没有则用已记录的前注/盲注/行动金额累加，不补没写过的动作。"""
    if not isinstance(hist, dict):
        return hist
    actions = hist.get("actions")
    if not isinstance(actions, list):
        return hist
    pot = 0.0
    ante = parse_num(hist.get("ante")) or 0.0
    ante_posted = any(
        isinstance(a, dict) and action_label(a.get("action")) == "前注"
        for a in actions
    )
    if ante > 0 and not ante_posted:
        n = sum(
            1
            for p in (hist.get("players") or [])
            if isinstance(p, dict) and p.get("seat") is not None
        )
        if n:
            pot += ante * n
    for a in actions:
        if not isinstance(a, dict):
            continue
        if _action_puts_chips(a.get("action")):
            amt = parse_num(a.get("amount"))
            if amt is not None and amt > 0:
                pot += amt
        if a.get("pot") not in (None, ""):
            continue
        a["pot"] = _round_chips(pot)
    return fill_action_stacks(hist)


def fill_action_stacks(hist: dict | None) -> dict | None:
    """行动后剩余筹码：报文有 chips 就用；没有则用该侧起始筹码减去已记录的前注/盲注/行动金额。"""
    if not isinstance(hist, dict):
        return hist
    actions = hist.get("actions")
    if not isinstance(actions, list):
        return hist
    remaining: dict[int, float] = {}
    for p in hist.get("players") or []:
        if not isinstance(p, dict) or p.get("seat") is None:
            continue
        init = parse_num(p.get("init"))
        if init is None:
            continue
        remaining[int(p["seat"])] = float(init)
    ante_posted = any(
        isinstance(a, dict) and action_label(a.get("action")) == "前注"
        for a in actions
    )
    ante = parse_num(hist.get("ante")) or 0.0
    if ante > 0 and not ante_posted:
        for seat in list(remaining):
            remaining[seat] -= min(ante, remaining[seat])
    for a in actions:
        if not isinstance(a, dict):
            continue
        seat = a.get("seat")
        if seat is not None:
            try:
                seat = int(seat)
            except (TypeError, ValueError):
                seat = None
        if seat in remaining and _action_puts_chips(a.get("action")):
            amt = parse_num(a.get("amount"))
            if amt is not None and amt > 0:
                remaining[seat] -= min(amt, remaining[seat])
        if a.get("chips") not in (None, ""):
            cn = parse_num(a.get("chips"))
            if cn is not None and seat is not None:
                remaining[seat] = float(cn)
            continue
        if seat in remaining:
            a["chips"] = _round_chips(remaining[seat])
    return hist


def _pot_changed(a: dict, prev: Any) -> tuple[bool, Any]:
    pv = a.get("pot")
    if pv is None or pv == "":
        return False, prev
    if prev is None or not values_equal(pv, prev):
        return True, pv
    return False, prev


def infer_finals(hist: dict | None) -> dict | None:
    """源数据没有 final_stacks 时，用起始筹码 + 行动投入 + 赢家分池推最终筹码。"""
    if not isinstance(hist, dict):
        return hist
    players = hist.get("players") or []
    if not isinstance(players, list) or not players:
        return hist
    for p in players:
        if not isinstance(p, dict):
            continue
        if _has_chip(p.get("final")) or not _has_chip(p.get("init")) or not _has_chip(p.get("net")):
            continue
        init = parse_num(p.get("init"))
        net = parse_num(p.get("net"))
        if init is None or net is None:
            continue
        p["final"] = _round_chips(init + net)
    missing = [
        p
        for p in players
        if isinstance(p, dict) and p.get("seat") is not None and _has_chip(p.get("init")) and not _has_chip(p.get("final"))
    ]
    if not missing:
        return hist
    remaining: dict[int, float] = {}
    invested: dict[int, float] = {}
    street_put: dict[int, float] = {}
    for p in players:
        if not isinstance(p, dict) or p.get("seat") is None:
            continue
        init = parse_num(p.get("init"))
        if init is None:
            continue
        seat = int(p["seat"])
        remaining[seat] = init
        invested[seat] = 0.0
        street_put[seat] = 0.0
    ante_posted = any(action_label(a.get("action")) == "前注" for a in (hist.get("actions") or []) if isinstance(a, dict))
    ante = parse_num(hist.get("ante")) or 0.0
    if ante > 0 and not ante_posted:
        for seat in list(remaining):
            put = min(ante, remaining[seat])
            remaining[seat] -= put
            invested[seat] += put
    last_street = ""
    folded: set[int] = set()
    for a in hist.get("actions") or []:
        if not isinstance(a, dict) or a.get("seat") is None:
            continue
        try:
            seat = int(a["seat"])
        except (TypeError, ValueError):
            continue
        st = a.get("street") or "preflop"
        if st != last_street:
            if last_street:
                for s in street_put:
                    street_put[s] = 0.0
            last_street = st
        if _norm_act(a.get("action")) == "FOLD":
            folded.add(seat)
        if not _action_puts_chips(a.get("action")) or seat not in remaining:
            continue
        amt = parse_num(a.get("amount"))
        if amt is None or amt <= 0:
            continue
        put = min(amt, remaining[seat])
        remaining[seat] -= put
        invested[seat] += put
        street_put[seat] = street_put.get(seat, 0.0) + put
    ranked = sorted(street_put.values(), reverse=True)
    if ranked and ranked[0] > 0:
        uncalled = ranked[0] - (ranked[1] if len(ranked) > 1 else 0.0)
        if uncalled > 1e-9:
            who = None
            for s, v in street_put.items():
                if v + 1e-9 >= ranked[0]:
                    who = s
            if who is not None:
                remaining[who] += uncalled
                invested[who] -= uncalled
    pot = sum(invested.values())
    winners: list[int] = []
    for w in hist.get("winners") or []:
        try:
            s = int(w)
        except (TypeError, ValueError):
            continue
        if s in remaining:
            winners.append(s)
    if not winners:
        live = [s for s in remaining if s not in folded]
        if len(live) == 1:
            winners = live
    if winners and pot > 0:
        share = pot / len(winners)
        for s in winners:
            remaining[s] += share
    for p in players:
        if not isinstance(p, dict) or _has_chip(p.get("final")):
            continue
        seat = p.get("seat")
        if seat not in remaining:
            continue
        p["final"] = _round_chips(remaining[int(seat)])
        if not _has_chip(p.get("net")):
            init = parse_num(p.get("init"))
            if init is not None:
                p["net"] = _round_chips(p["final"] - init)
    return hist


def gold_history(obj: dict) -> dict:
    """源数据一手：盲注、牌面、筹码、结算，以及从翻前起的每一次行动。"""
    n = int(obj.get("player_count") or len(obj.get("seat_positions") or {}) or 0)
    nick = obj.get("seat_nicknames") or {}
    names = obj.get("seat_player_names") or {}
    pos = obj.get("seat_positions") or {}
    init = obj.get("init_stacks") or {}
    final = obj.get("final_stacks") or {}
    net = obj.get("net_won_chips") or {}
    hole = obj.get("hole_cards") or {}
    hero_seat = obj.get("hero_seat")
    try:
        hero_seat = int(hero_seat) if hero_seat is not None else 0
    except (TypeError, ValueError):
        hero_seat = 0
    players = []
    for i in range(n):
        players.append(
            {
                "seat": i,
                "pos": _g(pos, i) or "",
                "name": _g(nick, i) or _g(names, i) or "",
                "init": _g(init, i),
                "final": _g(final, i),
                "net": _g(net, i),
                "cards": _card_list(_g(hole, i)),
                "hero": i == hero_seat,
            }
        )
    straddle_amt = None
    sb_seat = None
    bb_seat = None
    straddle_seat = None
    actions: list[dict] = []
    for a in obj.get("actions") or []:
        act = a.get("action")
        up = _norm_act(act)
        try:
            seat = int(a.get("seat"))
        except (TypeError, ValueError):
            seat = None
        p = (a.get("position") or (_g(pos, seat) if seat is not None else "") or "").upper()
        if is_forced_post(act):
            amt = parse_num(a.get("amount"))
            if "STRADDLE" in up:
                if amt is not None:
                    straddle_amt = amt
                if seat is not None:
                    straddle_seat = seat
            elif p == "SB" or "COST_SB" in up:
                sb_seat = seat if seat is not None else sb_seat
            elif p == "BB" or "COST_BB" in up:
                bb_seat = seat if seat is not None else bb_seat
            if seat is None:
                continue
            item = {
                "street": "preflop",
                "seat": seat,
                "pos": a.get("position") or _g(pos, seat) or "",
                "action": up,
                "amount": a.get("amount"),
                "post": True,
            }
            _copy_action_facts(item, a)
            actions.append(item)
            continue
        st = norm_street(a.get("street"))
        if not st or seat is None:
            continue
        item = {
            "street": st,
            "seat": seat,
            "pos": a.get("position") or _g(pos, seat) or "",
            "action": up,
            "amount": a.get("amount"),
            "post": False,
        }
        _copy_action_facts(item, a)
        actions.append(item)
    if sb_seat is None:
        for i in range(n):
            if str(_g(pos, i) or "").upper() == "SB":
                sb_seat = i
                break
    if bb_seat is None:
        for i in range(n):
            if str(_g(pos, i) or "").upper() == "BB":
                bb_seat = i
                break
    if straddle_amt is None and obj.get("straddle") not in (None, False, "", 0, "0"):
        n_str = parse_num(obj.get("straddle"))
        straddle_amt = n_str if n_str is not None else obj.get("straddle")
    result = obj.get("result") or {}
    winners = result.get("winners")
    if not isinstance(winners, list):
        winners = [obj["winner_seat"]] if obj.get("winner_seat") is not None else []
    winners = [int(x) for x in winners if x is not None and str(x) != ""]
    turn = obj.get("turn")
    river = obj.get("river")
    out = {
        "sb": obj.get("small_blind"),
        "bb": obj.get("big_blind"),
        "ante": obj.get("ante"),
        "straddle": straddle_amt if straddle_amt is not None else obj.get("straddle"),
        "sb_seat": sb_seat,
        "bb_seat": bb_seat,
        "straddle_seat": straddle_seat,
        "players": players,
        "actions": actions,
        "board": {
            "flop": _card_list(obj.get("flop")),
            "turn": _card_list(turn if isinstance(turn, list) else ([turn] if turn else [])),
            "river": _card_list(river if isinstance(river, list) else ([river] if river else [])),
        },
        "pot": result.get("total_pot"),
        "winners": winners,
        "showdown": bool(result.get("showdown") if result.get("showdown") is not None else obj.get("is_showdown")),
    }
    infer_finals(out)
    fill_action_pots(out)
    return out


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


def inventory_from_ui_trees(trees: list[dict], histories: list[dict] | None = None) -> list[dict]:
    counts: Counter[str] = Counter()
    for tree in trees:
        counts.update(iter_paths(tree))
    for hist in histories or []:
        counts.update(flatten_history(hist).keys())
    rows = []
    for path, total in counts.items():
        if is_ui_snapshot_path(path):
            continue
        rows.append({"path": path, "cat": classify(path), "total": int(total)})
    order = {c: i for i, c in enumerate(CATS)}
    rows.sort(key=lambda r: (order.get(r["cat"], 9), r["path"]))
    return rows


LEN_MARK = "__len__"
STREET_FLAT = ("preflop", "flop", "turn", "river")
SEQ_PARTS = ("who", "action", "amount")
_ACT_SHOW_AMT = {"BET", "RAISE", "CALL", "ALL-IN"}
_ACT_VERB = {
    "POST_BLIND": "盲注",
    "COST_SB": "盲注",
    "COST_BB": "盲注",
    "COST_BLIND": "盲注",
    "POST_ANTE": "前注",
    "ANTE": "前注",
    "COST_ANTE": "前注",
}


def action_label(act: Any) -> str:
    u = _norm_act(act)
    if not u:
        return ""
    if u in ("POST_BLIND", "COST_SB", "COST_BB", "COST_BLIND") or (
        "BLIND" in u and ("POST" in u or "COST" in u)
    ):
        return "盲注"
    if "STRADDLE" in u:
        return "straddle"
    if u in ("POST_ANTE", "COST_ANTE", "ANTE") or "ANTE" in u:
        return "前注"
    if u in ("ALLIN", "ALL_IN", "ALL-IN"):
        return "ALL-IN"
    return u


def format_act(a: dict | None) -> str:
    if not a:
        return ""
    pos = str(a.get("pos") or a.get("who") or (f"P{a['seat']}" if a.get("seat") is not None else "")).strip()
    verb = action_label(a.get("action")) or _norm_act(a.get("action"))
    show = verb in _ACT_SHOW_AMT or verb in ("盲注", "straddle", "前注")
    amt = a.get("amount")
    if show and amt not in (None, ""):
        n = parse_num(amt)
        if n is not None and abs(n - round(n)) < 1e-9:
            return f"{pos} {verb} {int(round(n))}".strip()
        return f"{pos} {verb} {amt}".strip()
    return f"{pos} {verb}".strip()


def flatten_history(hist: dict | None) -> dict[str, Any]:
    """按街、按第几次行动展开：位置、动作、下注额；底池只在发生变化的那一步展开。"""
    if not isinstance(hist, dict):
        return {}
    fill_action_pots(hist)
    posts: dict[str, list] = {s: [] for s in STREET_FLAT}
    vols: dict[str, list] = {s: [] for s in STREET_FLAT}
    for a in hist.get("actions") or []:
        if not isinstance(a, dict):
            continue
        st = a.get("street") or "preflop"
        if st not in vols:
            continue
        (posts if a.get("post") else vols)[st].append(a)
    out: dict[str, Any] = {}
    prev_pot = None
    for st in STREET_FLAT:
        for kind, bag in (("post", posts), ("vol", vols)):
            lst = bag[st]
            if not lst:
                continue
            prefix = f"history.{kind}.{st}"
            out[prefix] = (LEN_MARK, len(lst))
            for i, a in enumerate(lst):
                p = f"{prefix}[{i}]"
                out[f"{p}.who"] = a.get("pos") or ""
                out[f"{p}.action"] = action_label(a.get("action"))
                out[f"{p}.amount"] = a.get("amount")
                changed, prev_pot = _pot_changed(a, prev_pot)
                if changed:
                    out[f"{p}.pot"] = a.get("pot")
    return out


def _fill_player_chip(ui: dict | None, hist: dict | None, field: str, hist_key: str) -> None:
    if not isinstance(ui, dict):
        return
    nodes = ui.get("players") or {}
    if not isinstance(nodes, dict):
        return
    by_seat: dict[Any, dict] = {}
    for p in (hist or {}).get("players") or []:
        if isinstance(p, dict) and p.get("seat") is not None:
            by_seat[p.get("seat")] = p
    for key, node in nodes.items():
        if not isinstance(node, dict):
            continue
        cur = (node.get(field) or {}).get("value") if isinstance(node.get(field), dict) else None
        if cur is not None and cur != "":
            continue
        try:
            seat = int(str(key)[1:]) if str(key).startswith("P") else None
        except ValueError:
            seat = None
        p = by_seat.get(seat)
        v = None if not p else p.get(hist_key)
        if v is None or v == "":
            continue
        node[field] = {"value": v}


def _fill_init_chips(ui: dict | None, hist: dict | None) -> None:
    """旧界面树没有 init_chips 时，从 history.players[].init 补上。"""
    _fill_player_chip(ui, hist, "init_chips", "init")


def _fill_final_chips(ui: dict | None, hist: dict | None) -> None:
    """源数据没有 final_stacks 时，用行动推算出的 history.players[].final 补上。"""
    infer_finals(hist)
    _fill_player_chip(ui, hist, "chips", "final")


def flatten_hand(ui: dict | None, hist: dict | None = None) -> dict[str, Any]:
    _fill_init_chips(ui, hist)
    _fill_final_chips(ui, hist)
    flat = flatten_values(ui or {})
    if hist:
        flat.update(flatten_history(hist))
    return {path: val for path, val in flat.items() if not is_ui_snapshot_path(path)}


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


def has_val(v: Any) -> bool:
    """源数据没有记下的值：不算缺失，也不进分母。"""
    if v is None or v == "":
        return False
    if isinstance(v, tuple) and v and v[0] == LEN_MARK:
        return (v[1] or 0) > 0
    if isinstance(v, list):
        return any(has_val(x) for x in v)
    return True


def _player_seat_key(path: str) -> str:
    m = re.match(r"^players\.(P\d+)\.", path or "")
    return m.group(1) if m else ""


def _player_occupied(flat: dict[str, Any], key: str) -> bool:
    if not key or not flat:
        return False
    prefix = f"players.{key}."
    return any(p.startswith(prefix) for p in flat)


def _is_player_follow_on(path: str) -> bool:
    if not _player_seat_key(path):
        return False
    if path.endswith(".position.value"):
        return False
    if re.search(r"\.(name|seat|init_chips|chips|dealer|status)\.value$", path):
        return True
    return ".cards" in path


def compare_flat(left: dict[str, Any], right: dict[str, Any] | None) -> dict[str, str]:
    """path -> match | mismatch | missing | len_mismatch. 右侧多的不要。源数据空值不进缺失。
    开局玩家先按位置对齐；对不上的位置只记一次缺失，不对齐后再比昵称/筹码/座位。
    """
    out: dict[str, str] = {}
    right = right or {}
    for path, lv in left.items():
        if skip_compare_path(path):
            continue
        if not has_val(lv):
            continue
        key = _player_seat_key(path)
        if key and path.endswith(".position.value"):
            out[path] = "match" if _player_occupied(right, key) else "missing"
            continue
        if _is_player_follow_on(path) and not _player_occupied(right, key):
            continue
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
