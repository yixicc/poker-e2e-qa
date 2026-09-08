"""源数据：Excel auto_json 列，或 jsonl / json 里的同结构对象。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shuzi_field_schema import auto_json_to_ui, gold_history, inventory_from_ui_trees, is_forced_post

SHEETS = ["PREFLOP", "FLOP", "TURN", "RIVER"]
STREET_CN = {"PREFLOP": "翻前", "FLOP": "翻牌", "TURN": "转牌", "RIVER": "河牌"}
EXCEL_SUFFIX = {".xlsx", ".xls"}
JSONL_SUFFIX = {".jsonl", ".json"}
ACT_LABEL = {
    "FOLD": "fold",
    "CHECK": "check",
    "BET": "bet",
    "RAISE": "raise",
    "CALL": "limp",
    "ALL_IN": "all in",
    "ALLIN": "all in",
}


def _g(d: Any, i: Any, default=""):
    if not isinstance(d, dict) or i is None:
        return default
    if i in d:
        return d[i]
    if str(i) in d:
        return d[str(i)]
    try:
        n = int(i)
    except (TypeError, ValueError):
        return default
    if n in d:
        return d[n]
    return d.get(str(n), default)


def _norm_header(h: Any) -> str:
    return str(h or "").strip().lower().replace(" ", "_").replace("-", "_")


def find_auto_json_col(headers: list) -> int | None:
    for i, h in enumerate(headers):
        key = _norm_header(h)
        if key in {"auto_json", "autojson"}:
            return i + 1
    return None


def unwrap_auto_json(raw: Any) -> dict:
    obj = raw
    if isinstance(obj, str):
        obj = json.loads(obj)
    if not isinstance(obj, dict):
        raise ValueError("auto_json 不是对象")
    inner = obj.get("auto_json")
    if inner is None:
        return obj
    if isinstance(inner, str):
        inner = json.loads(inner)
    if not isinstance(inner, dict):
        raise ValueError("auto_json 列不是对象")
    return inner


def vol_actions(obj: dict) -> list[dict]:
    return [
        a
        for a in (obj.get("actions") or [])
        if isinstance(a, dict) and not is_forced_post(a.get("action"))
    ]


def infer_sheet(obj: dict) -> str:
    streets = [
        str(a.get("street") or "").upper()
        for a in vol_actions(obj)
        if a.get("street") and str(a.get("street")).upper() not in {"PRE_HAND", ""}
    ]
    for s in reversed(streets):
        if s in STREET_CN:
            return s
    return "PREFLOP"


def last_action_label(obj: dict) -> str:
    vol = vol_actions(obj)
    if not vol:
        return ""
    act = str(vol[-1].get("action") or "").upper().replace("-", "_")
    return ACT_LABEL.get(act, act.lower())


def case_from_obj(
    obj: dict,
    *,
    seq: int,
    sheet: str,
    sheet_row: int,
    excel_row: int,
    extras: dict | None = None,
) -> dict:
    extras = extras or {}
    vol = vol_actions(obj)
    streets = [
        a.get("street")
        for a in vol
        if a.get("street") and a.get("street") not in ("PRE_HAND",)
    ]
    pos = obj.get("seat_positions") or {}
    hero_seat = obj.get("hero_seat")
    sb = obj.get("small_blind")
    bb = obj.get("big_blind")
    blinds = extras.get("blinds")
    if blinds is None or blinds == "":
        blinds = f"{sb}/{bb}" if sb is not None and bb is not None else ""
    n_players = extras.get("n_players")
    if n_players in (None, ""):
        n_players = int(obj.get("player_count") or len(pos) or 0)
    else:
        n_players = int(n_players)
    hero_pos = extras.get("hero_pos")
    if hero_pos in (None, ""):
        hero_pos = str(_g(pos, hero_seat) or "")
    action = extras.get("action")
    if action in (None, ""):
        action = last_action_label(obj)
    name = extras.get("name")
    if name in (None, ""):
        name = obj.get("hand_id") or ""
    sheet = sheet if sheet in STREET_CN else infer_sheet(obj)
    return {
        "seq": seq,
        "sheet": sheet,
        "street": STREET_CN[sheet],
        "sheet_row": sheet_row,
        "excel_row": excel_row,
        "name": name,
        "play": extras.get("play") or obj.get("table_mode") or obj.get("mode") or "",
        "blinds": str(blinds),
        "ante": extras.get("ante") if extras.get("ante") is not None else obj.get("ante"),
        "unit": extras.get("unit") if extras.get("unit") is not None else obj.get("unit"),
        "gps": extras.get("gps") if extras.get("gps") is not None else obj.get("show_gps_limit"),
        "delay": extras.get("delay") if extras.get("delay") is not None else obj.get("show_delay_card"),
        "random_seat": extras.get("random_seat") if extras.get("random_seat") is not None else obj.get("show_random_seat"),
        "straddle": extras.get("straddle") if extras.get("straddle") is not None else obj.get("straddle"),
        "allin2": extras.get("allin2") if extras.get("allin2") is not None else obj.get("show_all_in_double"),
        "sidepot": extras.get("sidepot"),
        "hero_acts": extras.get("hero_acts"),
        "n_players": n_players,
        "hero_pos": str(hero_pos or ""),
        "action": str(action or ""),
        "hand_id": obj.get("hand_id"),
        "session_id": obj.get("session_id"),
        "sb": sb,
        "bb": bb,
        "ante_j": obj.get("ante"),
        "showdown": bool(obj.get("is_showdown")),
        "n_vol_actions": len(vol),
        "vol_streets": ",".join(dict.fromkeys(str(s) for s in streets if s)),
        "total_pot": (obj.get("result") or {}).get("total_pot"),
        "hero_seat": hero_seat,
    }


def _idx_map(headers: list) -> dict[str, int]:
    idx: dict[str, int] = {}
    for i, h in enumerate(headers):
        if h is None or str(h).strip() == "":
            continue
        raw = str(h).strip()
        idx[raw] = i + 1
        idx[raw.lower()] = i + 1
    return idx


def _cell(ws, r: int, idx: dict[str, int], key: str, default=None):
    col = idx.get(key) or idx.get(key.lower())
    if not col:
        return default
    return ws.cell(r, col).value


def load_excel(src: Path) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    from openpyxl import load_workbook

    wb = load_workbook(src, data_only=True)
    names = list(wb.sheetnames)
    use = [s for s in SHEETS if s in names]
    if not use:
        use = [
            s
            for s in names
            if find_auto_json_col([c.value for c in wb[s][1]])
        ]
    if not use:
        raise ValueError("Excel 里没有 auto_json 列（四张街表或任意表均可）")

    rows: list[dict] = []
    trees: list[dict] = []
    histories: list[dict] = []
    seq = 0
    for sheet in use:
        ws = wb[sheet]
        headers = [c.value for c in ws[1]]
        jcol = find_auto_json_col(headers)
        if not jcol:
            continue
        idx = _idx_map(headers)
        sheet_row = 0
        for r in range(2, ws.max_row + 1):
            name = ws.cell(r, 1).value
            if not name:
                continue
            raw = ws.cell(r, jcol).value
            if raw in (None, ""):
                continue
            obj = unwrap_auto_json(raw)
            seq += 1
            sheet_row += 1
            trees.append(auto_json_to_ui(obj))
            histories.append(gold_history(obj))
            extras = {
                "name": name,
                "play": _cell(ws, r, idx, "玩法"),
                "blinds": _cell(ws, r, idx, "大小盲"),
                "ante": _cell(ws, r, idx, "前注"),
                "unit": _cell(ws, r, idx, "记分牌单位"),
                "gps": _cell(ws, r, idx, "限制GPS和IP"),
                "delay": _cell(ws, r, idx, "延迟看牌"),
                "random_seat": _cell(ws, r, idx, "随机入座"),
                "straddle": _cell(ws, r, idx, "Straddle"),
                "allin2": _cell(ws, r, idx, "Allin两次"),
                "sidepot": _cell(ws, r, idx, "预期是否存在边池"),
                "hero_acts": _cell(ws, r, idx, "Hero行动次数"),
                "n_players": _cell(ws, r, idx, "玩家人数"),
                "hero_pos": _cell(ws, r, idx, "英雄位"),
                "action": _cell(ws, r, idx, "动作"),
            }
            rows.append(
                case_from_obj(
                    obj,
                    seq=seq,
                    sheet=sheet if sheet in STREET_CN else infer_sheet(obj),
                    sheet_row=sheet_row,
                    excel_row=r,
                    extras=extras,
                )
            )
    if not rows:
        raise ValueError("Excel auto_json 列没有可用的手牌")
    return rows, inventory_from_ui_trees(trees, histories), trees, histories


def _hands_from_jsonl_text(text: str) -> list[dict]:
    hands: list[dict] = []
    for i, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("//") or line.startswith("#"):
            continue
        try:
            hands.append(unwrap_auto_json(json.loads(line)))
        except (json.JSONDecodeError, ValueError) as e:
            raise ValueError(f"jsonl 第 {i} 行无法解析：{e}") from e
    return hands


def _hands_from_json_data(data: Any) -> list[dict]:
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
        raise ValueError("json 不是对象或数组")
    out = []
    for i, item in enumerate(items, start=1):
        try:
            out.append(unwrap_auto_json(item))
        except (json.JSONDecodeError, ValueError) as e:
            raise ValueError(f"第 {i} 条无法解析：{e}") from e
    return out


def _iter_json_hands(src: Path) -> list[dict]:
    text = src.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError("空文件")
    suffix = src.suffix.lower()
    if suffix == ".jsonl":
        return _hands_from_jsonl_text(text)
    try:
        return _hands_from_json_data(json.loads(text))
    except json.JSONDecodeError:
        return _hands_from_jsonl_text(text)


def load_jsonl(src: Path) -> tuple[list[dict], list[dict], list[dict]]:
    hands = _iter_json_hands(src)
    rows: list[dict] = []
    trees: list[dict] = []
    histories: list[dict] = []
    sheet_rows: dict[str, int] = {s: 0 for s in SHEETS}
    for seq, obj in enumerate(hands, start=1):
        sheet = infer_sheet(obj)
        sheet_rows[sheet] = sheet_rows.get(sheet, 0) + 1
        trees.append(auto_json_to_ui(obj))
        histories.append(gold_history(obj))
        rows.append(
            case_from_obj(
                obj,
                seq=seq,
                sheet=sheet,
                sheet_row=sheet_rows[sheet],
                excel_row=seq,
            )
        )
    if not rows:
        raise ValueError("jsonl 里没有可用的手牌")
    return rows, inventory_from_ui_trees(trees, histories), trees, histories


def load_source(src: Path) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    src = Path(src)
    if not src.exists():
        raise FileNotFoundError(str(src))
    suffix = src.suffix.lower()
    if suffix in EXCEL_SUFFIX:
        return load_excel(src)
    if suffix in JSONL_SUFFIX:
        return load_jsonl(src)
    raise ValueError("只支持 Excel（读 auto_json 列）或 jsonl / json")
