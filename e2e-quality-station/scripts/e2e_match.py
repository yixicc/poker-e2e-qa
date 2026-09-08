"""视觉 / 规则 → 与源数据同一套界面树，再按字段比对。"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from shuzi_field_schema import (
    CATS,
    classify,
    compare_flat,
    flatten_hand,
    flatten_values,
    is_forced_post,
    parse_num,
    vis_total_pot,
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
            last_bet[seat] = parse_num(a.get("amount")) or 0
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
            last_bet[seat] = parse_num(amt) or 0
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
        players[f"P{seat}"] = {
            "name": {"value": cells[2] if len(cells) > 2 else ""},
            "action": {"value": last_act.get(seat) or ""},
            "comment": {"value": ""},
            "cards": card_map,
            "bet_amount": {"value": last_bet.get(seat, 0)},
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
        if net is None and init is not None and fin is not None:
            net = fin - init
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
    straddle = parse_num((blinds or {}).get("straddle")) or 0
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
                if not straddle:
                    straddle = amt or 0
            if seat is None:
                continue
            if "ANTE" in up:
                continue
            actions.append({"street": "preflop", "seat": seat, "pos": pos, "action": up, "amount": amt, "post": True})
            continue
        st = str(a.get("street") or "").strip().lower().replace("-", "_").replace(" ", "_")
        if st in {"pre_flop", "preflop"}:
            st = "preflop"
        if st not in {"preflop", "flop", "turn", "river"}:
            continue
        actions.append({
            "street": st,
            "seat": seat,
            "pos": pos,
            "action": up,
            "amount": parse_num(a.get("amount")),
            "post": False,
        })
    return {
        "actions": actions,
        "players": players,
        "ante": (blinds or {}).get("ante"),
        "straddle": straddle,
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
        net = (fin - init) if init is not None and fin is not None else None
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
    straddle = parse_num(blinds.get("straddle")) or 0
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
            if "STRADDLE" in up and amt is not None and not straddle:
                straddle = amt
            if seat is None:
                continue
            if "ANTE" in up:
                continue
            actions.append({"street": "preflop", "seat": seat, "pos": pos, "action": up, "amount": amt, "post": True})
            continue
        st = str(cells[1] or "").strip().lower().replace("-", "_").replace(" ", "_")
        if st in {"pre_flop", "preflop"}:
            st = "preflop"
        if st not in {"preflop", "flop", "turn", "river"}:
            continue
        actions.append({
            "street": st,
            "seat": seat,
            "pos": pos,
            "action": up,
            "amount": amt,
            "post": False,
        })
    return {
        "actions": actions,
        "players": players,
        "ante": blinds.get("ante"),
        "straddle": straddle,
    }


def _empty_bucket() -> dict:
    return {"total": 0, "match": 0, "mismatch": 0, "missing": 0, "len_mismatch": 0, "errors": []}


def _rate(match: int, total: int):
    if total <= 0:
        return None
    return round(100.0 * match / total, 1)


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
        "n_vis": n_vis,
        "n_rule": n_rule,
        "n_gold": len(gold_trees),
    }
