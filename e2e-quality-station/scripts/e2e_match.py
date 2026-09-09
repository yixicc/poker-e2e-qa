"""视觉 / 规则 → 与源数据同一套界面树，再按字段比对。"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from shuzi_field_schema import (
    CATS,
    STREET_FLAT,
    action_label,
    classify,
    compare_flat,
    flatten_hand,
    flatten_values,
    is_forced_post,
    parse_num,
    values_equal,
    vis_total_pot,
    _copy_action_facts,
)

POS_ALIAS = {
    "UTG1": "UTG+1",
    "UTG2": "UTG+2",
    "UTG3": "UTG+3",
    "DEALER": "BTN",
    "BUTTON": "BTN",
    "SMALLBLIND": "SB",
    "BIGBLIND": "BB",
}
BLIND_LV = re.compile(
    r"^\s*(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)(?:\s*\((\d+(?:\.\d+)?)\))?"
)


def norm_pos(p: Any) -> str:
    s = str(p or "").strip().upper().replace(" ", "")
    s = s.replace("UTG+", "UTG+")
    if s in POS_ALIAS:
        return POS_ALIAS[s]
    if s.startswith("UTG") and len(s) > 3 and s[3].isdigit() and "+" not in s:
        return "UTG+" + s[3:]
    return s


def is_post(act: Any) -> bool:
    return is_forced_post(act)


def norm_action(act: Any) -> str:
    u = str(act or "").strip().upper().replace("-", "_").replace(" ", "_")
    if u in ("ALLIN", "ALL_IN"):
        return "ALL-IN"
    return u


def pos_map_from_ui(ui: dict) -> dict[str, int]:
    out: dict[str, int] = {}
    for key, p in (ui.get("players") or {}).items():
        if not str(key).startswith("P"):
            continue
        try:
            seat = int(str(key)[1:])
        except ValueError:
            continue
        pos = norm_pos(((p or {}).get("position") or {}).get("value"))
        if pos:
            out[pos] = seat
    return out


def resolve_seat(pos: Any, pos_map: dict[str, int]) -> int | None:
    p = norm_pos(pos)
    if p in pos_map:
        return pos_map[p]
    if p == "UTG+1" and "UTG" in pos_map and "UTG+1" not in pos_map:
        return pos_map["UTG"]
    return None


def parse_blind_level(s: Any) -> dict[str, Any]:
    m = BLIND_LV.match(str(s or ""))
    if not m:
        return {}
    return {"sb": float(m.group(1)), "bb": float(m.group(2)), "ante": float(m.group(3) or 0)}


def extract_vis(body: dict | None) -> tuple[dict | None, dict]:
    if not isinstance(body, dict):
        return None, {}
    raw = body.get("rawJson") or {}
    ext = raw.get("llm_extraction") or {}
    hands = ext.get("hands") or []
    hand = hands[0] if hands and isinstance(hands[0], dict) else None
    blinds = parse_blind_level(ext.get("blind_level"))
    cfg = ext.get("blinds_config") or {}
    if not blinds:
        blinds = {
            "sb": cfg.get("small_blind"),
            "bb": cfg.get("big_blind"),
            "ante": cfg.get("ante_per_player") or cfg.get("ante"),
        }
    return hand, blinds


def vis_to_ui(hand: dict | None, blinds: dict, pos_map: dict[str, int]) -> dict | None:
    if not isinstance(hand, dict) or not pos_map:
        return None
    by_pos: dict[str, dict] = {}
    for p in hand.get("players") or []:
        if isinstance(p, dict) and p.get("position"):
            by_pos[norm_pos(p.get("position"))] = p

    last_act: dict[int, str] = {}
    last_bet: dict[int, Any] = {}
    folded: set[int] = set()
    for a in hand.get("actions") or []:
        if not isinstance(a, dict) or is_post(a.get("action")):
            continue
        seat = resolve_seat(a.get("player_position"), pos_map)
        if seat is None:
            continue
        act = norm_action(a.get("action"))
        last_act[seat] = act
        if act.replace("_", "").replace("-", "") in ("BET", "RAISE", "CALL", "ALLIN"):
            last_bet[seat] = parse_num(a.get("amount"))
        if act == "FOLD":
            folded.add(seat)

    settle = hand.get("settlement") or {}
    showdown = bool(settle.get("showdown") or hand.get("outcome") == "showdown")
    players: dict[str, Any] = {}
    for pos, seat in pos_map.items():
        p = by_pos.get(pos)
        if not p:
            continue
        cards_raw = p.get("shown_cards") or []
        if p.get("is_hero") and not cards_raw:
            cards_raw = hand.get("hero_cards") or []
        card_map = {}
        for ci, card in enumerate(cards_raw or []):
            if card:
                card_map[f"P{ci}"] = {"value": card}
        if seat in folded:
            status = "fold"
        elif showdown:
            status = "show"
        else:
            status = "in_hand"
        players[f"P{seat}"] = {
            "name": {"value": p.get("nickname") or ""},
            "action": {"value": last_act.get(seat) or ""},
            "comment": {"value": ""},
            "cards": card_map,
            "bet_amount": {"value": last_bet.get(seat, 0)},
            "init_chips": {"value": parse_num(p.get("initial_chips"))},
            "chips": {"value": parse_num(p.get("final_chips"))},
            "seat": {"value": seat},
            "dealer": {"value": bool(p.get("is_dealer"))},
            "status": {"value": status},
            "position": {"value": pos},
        }

    board: list[dict] = []
    for x in hand.get("community_cards") or []:
        if x:
            board.append({"value": x})
    pot = vis_total_pot(hand)
    n = len(hand.get("players") or []) or len(pos_map)
    return {
        "players": players,
        "table": {
            "community_cards": board,
            "pot": {"value": pot},
            "sb": {"value": blinds.get("sb")},
            "bb": {"value": blinds.get("bb")},
            "ante": {"value": blinds.get("ante")},
            "player_count": {"value": n},
            "showdown": {"value": showdown},
        },
    }


def _row(row: Any) -> list:
    return list(row) if isinstance(row, (list, tuple)) else []


def rule_to_ui(rr: Any, pos_map: dict[str, int]) -> dict | None:
    if not isinstance(rr, dict) or not pos_map:
        return None
    by_label: dict[str, list] = {}
    by_pos: dict[str, list] = {}
    for row in rr.get("players") or []:
        cells = _row(row)
        if len(cells) < 3:
            continue
        by_label[str(cells[0])] = cells
        by_pos[norm_pos(cells[1])] = cells

    last_act: dict[int, str] = {}
    last_bet: dict[int, Any] = {}
    folded: set[int] = set()
    for a in rr.get("actions") or []:
        cells = _row(a)
        if len(cells) < 3 or is_post(cells[2]):
            continue
        src = by_label.get(str(cells[0]))
        seat = resolve_seat(src[1] if src else None, pos_map)
        if seat is None:
            continue
        act = norm_action(cells[2])
        last_act[seat] = act
        amt = cells[3] if len(cells) > 3 else 0
        if act.replace("_", "").replace("-", "") in ("BET", "RAISE", "CALL", "ALLIN"):
            last_bet[seat] = parse_num(amt)
        if act == "FOLD":
            folded.add(seat)

    result = rr.get("result") or {}
    showdown = bool(result.get("showdown"))
    players: dict[str, Any] = {}
    for pos, seat in pos_map.items():
        cells = by_pos.get(pos)
        if not cells:
            continue
        hole = cells[3] if len(cells) > 3 else None
        shown = cells[6] if len(cells) > 6 else None
        cards_raw = shown if isinstance(shown, list) and shown else hole
        if not isinstance(cards_raw, list):
            cards_raw = []
        card_map = {}
        for ci, card in enumerate(cards_raw):
            if card:
                card_map[f"P{ci}"] = {"value": card}
        if seat in folded:
            status = "fold"
        elif showdown:
            status = "show"
        else:
            status = "in_hand"
        final = cells[5] if len(cells) > 5 else None
        init = cells[4] if len(cells) > 4 else None
        players[f"P{seat}"] = {
            "name": {"value": cells[2] if len(cells) > 2 else ""},
            "action": {"value": last_act.get(seat) or ""},
            "comment": {"value": ""},
            "cards": card_map,
            "bet_amount": {"value": last_bet.get(seat, 0)},
            "init_chips": {"value": parse_num(init)},
            "chips": {"value": parse_num(final)},
            "seat": {"value": seat},
            "dealer": {"value": norm_pos(cells[1]) == "BTN"},
            "status": {"value": status},
            "position": {"value": pos},
        }

    board: list[dict] = []
    raw_board = rr.get("board")
    if isinstance(raw_board, list):
        for x in raw_board:
            if isinstance(x, str) and x:
                board.append({"value": x})
            elif isinstance(x, list):
                board.extend({"value": c} for c in x if c)
    blinds = rr.get("blinds") or {}
    n = len(rr.get("players") or []) or len(pos_map)
    return {
        "players": players,
        "table": {
            "community_cards": board,
            "pot": {"value": (result.get("total_pot"))},
            "sb": {"value": blinds.get("sb")},
            "bb": {"value": blinds.get("bb")},
            "ante": {"value": blinds.get("ante")},
            "player_count": {"value": n},
            "showdown": {"value": showdown},
        },
    }


def vis_history(hand: dict | None, blinds: dict, pos_map: dict[str, int]) -> dict | None:
    if not isinstance(hand, dict) or not pos_map:
        return None
    by_pos = {}
    for p in hand.get("players") or []:
        if isinstance(p, dict) and p.get("position"):
            by_pos[norm_pos(p.get("position"))] = p
    players = []
    for pos, seat in pos_map.items():
        p = by_pos.get(pos)
        init = parse_num(p.get("initial_chips")) if p else None
        fin = parse_num(p.get("final_chips")) if p else None
        net = parse_num((p or {}).get("net_won") or (p or {}).get("profit") or (p or {}).get("chips_won")) if p else None
        players.append({
            "seat": seat,
            "pos": pos,
            "name": (p or {}).get("nickname") or "",
            "init": init,
            "final": fin,
            "net": net,
            "hero": bool(p and p.get("is_hero")),
        })
    players.sort(key=lambda x: x["seat"])
    straddle = parse_num((blinds or {}).get("straddle"))
    sb_seat = pos_map.get("SB")
    bb_seat = pos_map.get("BB")
    straddle_seat = None
    actions = []
    for a in hand.get("actions") or []:
        if not isinstance(a, dict):
            continue
        pos = norm_pos(a.get("player_position"))
        seat = resolve_seat(a.get("player_position"), pos_map)
        up = norm_action(a.get("action"))
        if is_post(a.get("action")):
            amt = parse_num(a.get("amount"))
            if "STRADDLE" in up:
                if straddle is None and amt is not None:
                    straddle = amt
                if seat is not None:
                    straddle_seat = seat
            elif pos == "SB":
                sb_seat = seat if seat is not None else sb_seat
            elif pos == "BB":
                bb_seat = seat if seat is not None else bb_seat
            if seat is None:
                continue
            item = {"street": "preflop", "seat": seat, "pos": pos, "action": up, "amount": amt, "post": True}
            _copy_action_facts(item, a)
            actions.append(item)
            continue
        st = str(a.get("street") or "").strip().lower().replace("-", "_").replace(" ", "_")
        if st in {"pre_flop", "preflop"}:
            st = "preflop"
        if st not in {"preflop", "flop", "turn", "river"}:
            continue
        item = {
            "street": st,
            "seat": seat,
            "pos": pos,
            "action": up,
            "amount": parse_num(a.get("amount")),
            "post": False,
        }
        _copy_action_facts(item, a)
        actions.append(item)
    return {
        "actions": actions,
        "players": players,
        "sb": (blinds or {}).get("sb"),
        "bb": (blinds or {}).get("bb"),
        "ante": (blinds or {}).get("ante"),
        "straddle": straddle,
        "sb_seat": sb_seat,
        "bb_seat": bb_seat,
        "straddle_seat": straddle_seat,
    }


def rule_history(rr: dict | None, pos_map: dict[str, int]) -> dict | None:
    if not isinstance(rr, dict) or not pos_map:
        return None
    by_label = {}
    by_pos = {}
    for row in rr.get("players") or []:
        cells = row if isinstance(row, list) else []
        if len(cells) < 3:
            continue
        by_label[str(cells[0])] = cells
        by_pos[norm_pos(cells[1])] = cells
    players = []
    for pos, seat in pos_map.items():
        cells = by_pos.get(pos)
        init = parse_num(cells[4]) if cells and len(cells) > 4 else None
        fin = parse_num(cells[5]) if cells and len(cells) > 5 else None
        net = None
        players.append({
            "seat": seat,
            "pos": pos,
            "name": cells[2] if cells and len(cells) > 2 else "",
            "init": init,
            "final": fin,
            "net": net,
            "hero": bool(cells and "hero" in str(cells[2] or "").lower()),
        })
    players.sort(key=lambda x: x["seat"])
    blinds = rr.get("blinds") or {}
    straddle = parse_num(blinds.get("straddle"))
    sb_seat = pos_map.get("SB")
    bb_seat = pos_map.get("BB")
    straddle_seat = None
    actions = []
    for row in rr.get("actions") or []:
        cells = row if isinstance(row, list) else []
        if len(cells) < 3:
            continue
        src = by_label.get(str(cells[0]))
        pos = norm_pos(src[1]) if src else ""
        seat = resolve_seat(pos, pos_map)
        up = norm_action(cells[2])
        amt = parse_num(cells[3]) if len(cells) > 3 else None
        if is_post(cells[2]):
            if "STRADDLE" in up:
                if amt is not None and not straddle:
                    straddle = amt
                if seat is not None:
                    straddle_seat = seat
            elif pos == "SB":
                sb_seat = seat if seat is not None else sb_seat
            elif pos == "BB":
                bb_seat = seat if seat is not None else bb_seat
            if seat is None:
                continue
            item = {"street": "preflop", "seat": seat, "pos": pos, "action": up, "amount": amt, "post": True}
            if isinstance(row, dict):
                _copy_action_facts(item, row)
            actions.append(item)
            continue
        st = str(cells[1] or "").strip().lower().replace("-", "_").replace(" ", "_")
        if st in {"pre_flop", "preflop"}:
            st = "preflop"
        if st not in {"preflop", "flop", "turn", "river"}:
            continue
        item = {
            "street": st,
            "seat": seat,
            "pos": pos,
            "action": up,
            "amount": amt,
            "post": False,
        }
        if isinstance(row, dict):
            _copy_action_facts(item, row)
        actions.append(item)
    return {
        "actions": actions,
        "players": players,
        "sb": blinds.get("sb"),
        "bb": blinds.get("bb"),
        "ante": blinds.get("ante"),
        "straddle": straddle,
        "sb_seat": sb_seat,
        "bb_seat": bb_seat,
        "straddle_seat": straddle_seat,
    }


def _empty_bucket() -> dict:
    return {"total": 0, "match": 0, "mismatch": 0, "missing": 0, "len_mismatch": 0, "errors": []}


def _rate(match: int, total: int):
    if total <= 0:
        return None
    return round(100.0 * match / total, 1)


_SEQ_STREET_LAB = {"preflop": "翻前", "flop": "翻牌", "turn": "转牌", "river": "河牌"}


def seq_groups(hist: dict | None) -> list[dict]:
    vols: dict[str, list] = {s: [] for s in STREET_FLAT}
    for a in (hist or {}).get("actions") or []:
        if not isinstance(a, dict) or a.get("post"):
            continue
        st = a.get("street") or "preflop"
        if st not in vols:
            continue
        vols[st].append({
            "who": norm_pos(a.get("pos") or a.get("who") or ""),
            "action": action_label(a.get("action")),
            "amount": a.get("amount"),
        })
    return [{
        "key": f"vol.{st}",
        "lab": _SEQ_STREET_LAB.get(st, st),
        "steps": vols[st],
    } for st in STREET_FLAT]


def _step_equal(a: dict, b: dict) -> bool:
    return a["who"] == b["who"] and a["action"] == b["action"] and values_equal(a["amount"], b["amount"])


def _step_part(a: dict, b: dict) -> str:
    if a["who"] != b["who"]:
        return "位置"
    if a["action"] != b["action"]:
        return "动作"
    return "额"


def compare_seq(left_hist: dict | None, right_hist: dict | None, right_missing: bool = False) -> dict:
    left_g = seq_groups(left_hist)
    left_n = sum(len(g["steps"]) for g in left_g)
    if right_missing:
        return {
            "exact": left_n == 0,
            "miss": left_n > 0,
            "len_diff": left_n > 0,
            "step_n": 0,
            "step_t": left_n,
            "left_n": left_n,
            "right_n": 0,
            "hint": "缺记录" if left_n else "",
        }
    right_g = seq_groups(right_hist)
    step_n = step_t = 0
    right_n = 0
    exact = True
    len_diff = False
    hint = ""

    def set_hint(h: str) -> None:
        nonlocal hint
        if not hint:
            hint = h

    for lg, rg in zip(left_g, right_g):
        ls, rs = lg["steps"], rg["steps"]
        lab = lg["lab"]
        right_n += len(rs)
        if len(ls) != len(rs):
            exact = False
            len_diff = True
            if len(rs) < len(ls):
                set_hint(f"{lab}漏{len(ls) - len(rs)}步")
            else:
                set_hint(f"{lab}多{len(rs) - len(ls)}步")
        n = min(len(ls), len(rs))
        for i, step in enumerate(ls):
            step_t += 1
            if i < n and _step_equal(step, rs[i]):
                step_n += 1
            else:
                exact = False
                if i < n and len(ls) == len(rs):
                    set_hint(f"{lab}第{i + 1}次{_step_part(step, rs[i])}")
        if len(rs) > len(ls):
            exact = False
    return {
        "exact": exact,
        "miss": False,
        "len_diff": len_diff,
        "step_n": step_n,
        "step_t": step_t,
        "left_n": left_n,
        "right_n": right_n,
        "hint": "" if exact else hint,
    }


def summarize_seq(
    left_trees: list[dict | None],
    right_trees: list[dict | None],
    left_hists: list[dict | None] | None = None,
    right_hists: list[dict | None] | None = None,
) -> dict:
    exact_n = exact_t = 0
    step_n = step_t = 0
    n_len = n_miss = 0
    per: list[dict | None] = []
    for i, left in enumerate(left_trees):
        if left is None:
            per.append(None)
            continue
        lh = left_hists[i] if left_hists and i < len(left_hists) else None
        miss = i >= len(right_trees) or right_trees[i] is None
        rh = None if miss else (right_hists[i] if right_hists and i < len(right_hists) else None)
        cmp = compare_seq(lh, rh, right_missing=miss)
        exact_t += 1
        if cmp["exact"]:
            exact_n += 1
        step_n += cmp["step_n"]
        step_t += cmp["step_t"]
        if cmp["len_diff"]:
            n_len += 1
        if cmp["miss"]:
            n_miss += 1
        per.append(cmp)
    return {
        "exact": _rate(exact_n, exact_t),
        "exact_n": exact_n,
        "exact_t": exact_t,
        "steps": _rate(step_n, step_t),
        "step_n": step_n,
        "step_t": step_t,
        "n_len": n_len,
        "n_miss": n_miss,
        "per": per,
    }


def _seq_rates_of(s: dict) -> dict:
    return {
        "exact": s["exact"],
        "exact_n": s["exact_n"],
        "exact_t": s["exact_t"],
        "steps": s["steps"],
        "step_n": s["step_n"],
        "step_t": s["step_t"],
        "n_len": s["n_len"],
        "n_miss": s["n_miss"],
    }


def summarize_pair(
    left_trees: list[dict | None],
    right_trees: list[dict | None],
    seqs: list[int],
    left_hists: list[dict | None] | None = None,
    right_hists: list[dict | None] | None = None,
) -> dict:
    by_path: dict[str, dict] = defaultdict(_empty_bucket)
    for i, left in enumerate(left_trees):
        seq = seqs[i] if i < len(seqs) else i + 1
        if left is None:
            continue
        lh = left_hists[i] if left_hists and i < len(left_hists) else None
        rh = right_hists[i] if right_hists and i < len(right_hists) else None
        flat_l = flatten_hand(left, lh)
        right = right_trees[i] if i < len(right_trees) else None
        flat_r = flatten_hand(right, rh) if right is not None else None
        verdicts = compare_flat(flat_l, flat_r)
        bad = False
        for path, kind in verdicts.items():
            b = by_path[path]
            b["total"] += 1
            b[kind] = b.get(kind, 0) + 1
            if kind != "match":
                bad = True
        if bad:
            for path, kind in verdicts.items():
                if kind != "match":
                    errs = by_path[path]["errors"]
                    if seq not in errs:
                        errs.append(seq)
    stats = {}
    cat_tot = {c: [0, 0] for c in CATS}
    all_m = all_t = 0
    for path, b in by_path.items():
        total = int(b["total"])
        match = int(b["match"])
        rate = _rate(match, total)
        stats[path] = {
            "total": total,
            "match": match,
            "mismatch": int(b["mismatch"]),
            "missing": int(b["missing"]),
            "len_mismatch": int(b["len_mismatch"]),
            "rate": rate,
            "n_error": len(b["errors"]),
            "errors": b["errors"][:12],
        }
        cat = classify(path)
        if cat in cat_tot:
            cat_tot[cat][0] += match
            cat_tot[cat][1] += total
        all_m += match
        all_t += total
    rates = {"all": _rate(all_m, all_t)}
    for cat in CATS:
        m, t = cat_tot[cat]
        rates[cat] = "—" if t == 0 else _rate(m, t)
    return {"rates": rates, "fields": stats}


def match_batch(
    gold_trees: list[dict],
    fusion_aligned: list[dict | None],
    gold_histories: list[dict] | None = None,
) -> dict:
    vis_trees: list[dict | None] = []
    rule_trees: list[dict | None] = []
    vis_hists: list[dict | None] = []
    rule_hists: list[dict | None] = []
    for i, gold in enumerate(gold_trees):
        pos_map = pos_map_from_ui(gold)
        item = fusion_aligned[i] if i < len(fusion_aligned) else None
        body = (item or {}).get("body") if item else None
        hand, blinds = extract_vis(body)
        vis_trees.append(vis_to_ui(hand, blinds, pos_map) if hand else None)
        vis_hists.append(vis_history(hand, blinds, pos_map) if hand else None)
        rr = body.get("ruleResult") if isinstance(body, dict) else None
        rule_trees.append(rule_to_ui(rr, pos_map) if rr else None)
        rule_hists.append(rule_history(rr, pos_map) if rr else None)

    gold_hists = list(gold_histories or [None] * len(gold_trees))
    seqs = list(range(1, len(gold_trees) + 1))
    gt_vis = summarize_pair(gold_trees, vis_trees, seqs, gold_hists, vis_hists)
    vis_rule = summarize_pair(vis_trees, rule_trees, seqs, vis_hists, rule_hists)
    gt_rule = summarize_pair(gold_trees, rule_trees, seqs, gold_hists, rule_hists)
    seq_gt_vis = summarize_seq(gold_trees, vis_trees, gold_hists, vis_hists)
    seq_vis_rule = summarize_seq(vis_trees, rule_trees, vis_hists, rule_hists)
    seq_gt_rule = summarize_seq(gold_trees, rule_trees, gold_hists, rule_hists)
    n_vis = sum(1 for t in vis_trees if t is not None)
    n_rule = sum(1 for t in rule_trees if t is not None)
    return {
        "pair_rates": {
            "gt_vis": gt_vis["rates"],
            "vis_rule": vis_rule["rates"],
            "gt_rule": gt_rule["rates"],
        },
        "field_stats": {
            "gt_vis": gt_vis["fields"],
            "vis_rule": vis_rule["fields"],
            "gt_rule": gt_rule["fields"],
        },
        "seq_rates": {
            "gt_vis": _seq_rates_of(seq_gt_vis),
            "vis_rule": _seq_rates_of(seq_vis_rule),
            "gt_rule": _seq_rates_of(seq_gt_rule),
        },
        "n_vis": n_vis,
        "n_rule": n_rule,
        "n_gold": len(gold_trees),
    }
