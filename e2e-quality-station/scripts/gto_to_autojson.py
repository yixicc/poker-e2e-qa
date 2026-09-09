#!/usr/bin/env python3
"""黄金集 GTO / HandV2 → 好友桌 auto_json。

独立脚本，不改 e2e_source / gold_history。质量站走单独入口 /api/upload-gto。

  python3 scripts/gto_to_autojson.py 32手测试数据.jsonl -o out.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

STREET_N_BOARD = {"PREFLOP": 0, "FLOP": 3, "TURN": 4, "RIVER": 5}
VOL_ZERO = {"FOLD", "CHECK"}


class ConvertError(ValueError):
    """输入不是黄金集 GTO，或某手无法转换。"""


def looks_like_gto(obj: Any) -> bool:
    if not isinstance(obj, dict):
        return False
    gi = obj.get("gameInfo")
    return isinstance(gi, dict) and (
        isinstance(gi.get("actionSequence"), list) or isinstance(gi.get("players"), list)
    )


def looks_like_auto_json(obj: Any) -> bool:
    if not isinstance(obj, dict) or looks_like_gto(obj):
        return False
    return isinstance(obj.get("actions"), list) or isinstance(obj.get("seat_positions"), dict)


def seat_num(raw: Any) -> int | None:
    if raw is None or raw is False or raw == "":
        return None
    if isinstance(raw, int):
        return raw
    s = str(raw).strip().upper()
    if s.startswith("P") and s[1:].isdigit():
        return int(s[1:])
    if s.isdigit() or (s.startswith("-") and s[1:].isdigit()):
        return int(s)
    return None


def to_num(v: Any) -> float | int | None:
    if v is None or v is True or v is False or v == "":
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v) if v.is_integer() else v
    s = str(v).strip().replace(",", "")
    if s == "":
        return None
    try:
        n = float(s)
    except ValueError:
        return None
    return int(n) if n.is_integer() else n


def _norm_card_rank_suit(raw: Any) -> str | None:
    """QC / 10C / TH / Tc → Tc。"""
    if raw is None or raw is False or raw == "":
        return None
    s = str(raw).strip()
    if not s:
        return None
    suit = s[-1].lower()
    rank = s[:-1].upper().replace("10", "T")
    if rank == "10":
        rank = "T"
    if len(rank) > 1:
        rank = rank[0]
    if suit not in "shdc" or not rank:
        return None
    return rank + suit


def norm_cards(raw: Any) -> list[str]:
    if raw is None:
        return []
    items = raw if isinstance(raw, list) else [raw]
    out: list[str] = []
    for x in items:
        c = _norm_card_rank_suit(x)
        if c:
            out.append(c)
    return out


def last_street(seq: list[dict]) -> str:
    for a in reversed(seq):
        st = str((a or {}).get("street") or "").upper().replace("-", "_").replace(" ", "_")
        if st in STREET_N_BOARD:
            return st
    return "PREFLOP"


def split_board(cards: list[str], street: str) -> tuple[list[str], Any, Any]:
    n = STREET_N_BOARD.get(street, 0)
    use = cards[:n]
    flop = use[:3]
    turn = use[3] if len(use) > 3 else None
    river = use[4] if len(use) > 4 else None
    return flop, turn, river


def map_action_type(raw: Any) -> str:
    u = str(raw or "").strip().upper().replace(" ", "_").replace("-", "_")
    if u in {"ALLIN", "ALL_IN"}:
        return "ALL-IN"
    return u.replace("_", "-") if u == "ALL-IN" else u


def straddle_value(raw: Any) -> Any:
    if raw in (None, False, "", 0, "0"):
        return False
    n = to_num(raw)
    return False if n is None or n == 0 else n


def _seat_maps(players: list[dict]) -> tuple[dict[str, str], dict[str, str], dict[str, Any], int, int | None]:
    pos: dict[str, str] = {}
    names: dict[str, str] = {}
    init: dict[str, Any] = {}
    max_n = -1
    dealer = None
    for p in players:
        if not isinstance(p, dict):
            continue
        seat = seat_num(p.get("seat"))
        if seat is None:
            continue
        key = str(seat)
        max_n = max(max_n, seat)
        position = str(p.get("position") or "")
        pos[key] = position
        names[key] = str(p.get("name") or "")
        chips = to_num(p.get("initChips"))
        if chips is not None:
            init[key] = chips
        if position.upper() in {"BTN", "DEALER", "BUTTON"}:
            dealer = seat
    player_count = max_n + 1 if max_n >= 0 else 0
    return pos, names, init, player_count, dealer


def _hole_cards(players: list[dict], showdown_players: list[dict]) -> dict[str, list[str]]:
    holes: dict[str, list[str]] = {}
    for p in players:
        if not isinstance(p, dict):
            continue
        seat = seat_num(p.get("seat"))
        cards = norm_cards(p.get("holeCards"))
        if seat is None or len(cards) != 2:
            continue
        if seat == 0 or p.get("seat") == "P0":
            holes[str(seat)] = cards
    for sp in showdown_players:
        if not isinstance(sp, dict):
            continue
        if str(sp.get("status") or "").lower() != "show":
            continue
        seat = seat_num(sp.get("seat"))
        cards = norm_cards(sp.get("cards"))
        if seat is None or len(cards) != 2:
            continue
        holes.setdefault(str(seat), cards)
    return holes


def _convert_seats(items: Any) -> list[int]:
    out: list[int] = []
    for x in items or []:
        n = seat_num(x)
        if n is not None:
            out.append(n)
    return out


def _seed_preflop(pos: dict[str, str], sb: Any, bb: Any, straddle: Any) -> dict[int, float]:
    cum: dict[int, float] = {}
    sb_n = float(sb or 0)
    bb_n = float(bb or 0)
    st_n = float(straddle) if isinstance(straddle, (int, float)) and straddle else 0.0
    for key, position in pos.items():
        seat = int(key)
        u = position.upper()
        if u == "SB":
            cum[seat] = sb_n
        elif u == "BB":
            cum[seat] = bb_n
        elif st_n and u in {"STRADDLE", "STR"}:
            cum[seat] = st_n
    return cum


def _blind_posts(pos: dict[str, str], sb: Any, bb: Any, straddle: Any) -> list[dict]:
    posts: list[dict] = []
    sb_n, bb_n = to_num(sb), to_num(bb)
    st_n = straddle if isinstance(straddle, (int, float)) else None
    by_pos = {v.upper(): int(k) for k, v in pos.items()}
    if "SB" in by_pos and sb_n is not None:
        posts.append(
            {
                "seat": by_pos["SB"],
                "action": "POST_BLIND",
                "amount": sb_n,
                "street": "PRE_HAND",
                "position": "SB",
                "is_all_in": False,
            }
        )
    if "BB" in by_pos and bb_n is not None:
        posts.append(
            {
                "seat": by_pos["BB"],
                "action": "POST_BLIND",
                "amount": bb_n,
                "street": "PRE_HAND",
                "position": "BB",
                "is_all_in": False,
            }
        )
    if st_n:
        st_seat = by_pos.get("STRADDLE") or by_pos.get("STR")
        if st_seat is not None:
            posts.append(
                {
                    "seat": st_seat,
                    "action": "POST_STRADDLE",
                    "amount": st_n,
                    "street": "PRE_HAND",
                    "position": pos.get(str(st_seat)) or "UTG",
                    "is_all_in": False,
                }
            )
    return posts


def _convert_actions(seq: list[dict], pos: dict[str, str], sb: Any, bb: Any, straddle: Any) -> list[dict]:
    actions = _blind_posts(pos, sb, bb, straddle)
    street = None
    cum: dict[int, float] = {}
    for raw in seq:
        if not isinstance(raw, dict):
            continue
        st = str(raw.get("street") or "").upper().replace("-", "_").replace(" ", "_")
        if st not in STREET_N_BOARD:
            continue
        seat = seat_num(raw.get("seat"))
        if seat is None:
            continue
        act = map_action_type(raw.get("actionType") or raw.get("action"))
        if not act:
            continue
        amt = to_num(raw.get("amount"))
        amt_f = float(amt) if amt is not None else 0.0
        if st != street:
            street = st
            cum = _seed_preflop(pos, sb, bb, straddle) if st == "PREFLOP" else {}
        prev = float(cum.get(seat, 0.0))
        if act in VOL_ZERO:
            inc: Any = 0
        else:
            inc_n = amt_f - prev
            inc = 0 if inc_n < 0 else to_num(inc_n)
            if inc is None:
                inc = 0
        cum[seat] = max(prev, amt_f)
        item = {
            "seat": seat,
            "action": act,
            "amount": inc,
            "street": st,
            "position": pos.get(str(seat)) or "",
            "is_all_in": act == "ALL-IN",
        }
        actions.append(item)
    return actions


def gto_to_autojson(obj: dict) -> dict:
    if not looks_like_gto(obj):
        raise ConvertError("不是黄金集 GTO（需要 gameInfo.actionSequence）")
    gi = obj.get("gameInfo") or {}
    result = obj.get("result") if isinstance(obj.get("result"), dict) else {}
    players = [p for p in (gi.get("players") or []) if isinstance(p, dict)]
    seq = [a for a in (gi.get("actionSequence") or []) if isinstance(a, dict)]
    pos, names, init, player_count, dealer = _seat_maps(players)
    sb, bb = to_num(gi.get("smallBlind")), to_num(gi.get("bigBlind"))
    ante = to_num(gi.get("ante"))
    straddle = straddle_value(gi.get("straddle"))
    sd_players = result.get("showdown_players") or []
    if not isinstance(sd_players, list):
        sd_players = []
    board_cards = norm_cards(gi.get("communityCards"))
    flop, turn, river = split_board(board_cards, last_street(seq))
    winners = _convert_seats(result.get("winners"))
    pots_out = []
    for pot in result.get("pots") or []:
        if not isinstance(pot, dict):
            continue
        pots_out.append(
            {
                "type": pot.get("type") or "main",
                "amount": to_num(pot.get("amount")),
                "players": _convert_seats(pot.get("players")),
                "winners": _convert_seats(pot.get("winners")),
            }
        )
    sd_out = []
    for sp in sd_players:
        if not isinstance(sp, dict):
            continue
        seat = seat_num(sp.get("seat"))
        if seat is None:
            continue
        status = str(sp.get("status") or "").lower() or "muck"
        cards = norm_cards(sp.get("cards")) if status == "show" else []
        if status == "show" and len(cards) != 2:
            cards = []
        sd_out.append(
            {
                "seat": seat,
                "name": str(sp.get("name") or names.get(str(seat)) or ""),
                "cards": cards,
                "status": status,
            }
        )
    showdown = bool(result.get("showdown"))
    out: dict[str, Any] = {
        "hand_id": gi.get("handId") or "",
        "player_count": player_count,
        "hero_seat": 0,
        "small_blind": sb,
        "big_blind": bb,
        "ante": ante if ante is not None else 0,
        "straddle": straddle,
        "seat_positions": pos,
        "seat_player_names": names,
        "seat_nicknames": dict(names),
        "init_stacks": init,
        "hole_cards": _hole_cards(players, sd_players),
        "flop": flop,
        "turn": turn,
        "river": river,
        "actions": _convert_actions(seq, pos, sb, bb, straddle),
        "is_showdown": showdown,
        "result": {
            "total_pot": to_num(result.get("total_pot")),
            "winners": winners,
            "showdown": showdown,
            "showdown_players": sd_out,
            "pots": pots_out,
        },
    }
    if dealer is not None:
        out["dealer_position"] = dealer
    if winners:
        out["winner_seat"] = winners[0]
    return out


def iter_gto_objs(text: str) -> list[dict]:
    text = (text or "").strip()
    if not text:
        raise ConvertError("空文件")
    if text.startswith("[") or text.startswith("{"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = None
        if data is not None:
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = None
                for key in ("hands", "cases", "records", "data"):
                    if isinstance(data.get(key), list):
                        items = data[key]
                        break
                if items is None:
                    items = [data]
            else:
                raise ConvertError("json 不是对象或数组")
            return [x for x in items if isinstance(x, dict)]
    hands: list[dict] = []
    for i, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("//") or line.startswith("#"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            raise ConvertError(f"jsonl 第 {i} 行无法解析：{e}") from e
        if not isinstance(obj, dict):
            raise ConvertError(f"jsonl 第 {i} 行不是对象")
        hands.append(obj)
    return hands


def convert_objs(objs: list[dict]) -> list[dict]:
    if not objs:
        raise ConvertError("没有可用的手牌")
    if any(looks_like_auto_json(o) for o in objs):
        raise ConvertError("这是好友桌 auto_json，请用「上传文件」")
    if not all(looks_like_gto(o) for o in objs):
        raise ConvertError("不是黄金集 GTO jsonl（需要每行含 gameInfo）")
    out = []
    for i, obj in enumerate(objs, start=1):
        try:
            out.append(gto_to_autojson(obj))
        except ConvertError:
            raise
        except Exception as e:
            raise ConvertError(f"第 {i} 手转换失败：{e}") from e
    return out


def dumps_jsonl(hands: list[dict]) -> str:
    return "".join(json.dumps(h, ensure_ascii=False, separators=(",", ":")) + "\n" for h in hands)


def convert_text(text: str) -> str:
    return dumps_jsonl(convert_objs(iter_gto_objs(text)))


def convert_path(src: Path, dest: Path | None = None) -> Path:
    src = Path(src)
    text = convert_text(src.read_text(encoding="utf-8"))
    out = dest or src.with_name(src.stem + ".auto_json.jsonl")
    out.write_text(text, encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="黄金集 GTO jsonl → 好友桌 auto_json jsonl")
    p.add_argument("src", type=Path, help="GTO json / jsonl")
    p.add_argument("-o", "--output", type=Path, help="输出路径，默认 <stem>.auto_json.jsonl")
    args = p.parse_args(argv)
    try:
        dest = convert_path(args.src, args.output)
    except ConvertError as e:
        print(str(e), file=sys.stderr)
        return 1
    n = sum(1 for line in dest.read_text(encoding="utf-8").splitlines() if line.strip())
    print(f"wrote {n} hands → {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
