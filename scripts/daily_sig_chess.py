"""信号 → Chess 按日账：分类汇总、趋势、按日跑批。"""

from __future__ import annotations

import json
import re
import threading
import time
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
DAY_DIR = ROOT / "data" / "daily_sig_chess"
JOB_DIR = DAY_DIR / "jobs"

_DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_lock = threading.Lock()
_jobs: dict[str, dict[str, Any]] = {}

KIND_META: list[tuple[str, str, str]] = [
    ("no_signal", "缺信号", "missing"),
    ("no_chess", "缺 Chess", "missing"),
    ("blinds", "盲注/前注", "structure"),
    ("player_n", "玩家人数", "structure"),
    ("position", "位置", "structure"),
    ("chips", "起始筹码", "structure"),
    ("board", "公共牌", "structure"),
    ("action_rewrite", "行动改写", "action"),
    ("action_missing", "漏行动", "action"),
    ("action_extra", "多余行动", "action"),
    ("other", "其他", "other"),
]
KIND_LABEL = {k: lab for k, lab, _g in KIND_META}
KIND_GROUP = {k: g for k, _lab, g in KIND_META}
KIND_ORDER = [k for k, _lab, _g in KIND_META]
STRUCTURE_KINDS = {k for k, _lab, g in KIND_META if g == "structure"}
ACTION_KINDS = {k for k, _lab, g in KIND_META if g == "action"}

# 细项：结构差「肯定有」不够用，趋势/日页按这些看大小盲、行动类型、金额单位等。
FACET_META: list[tuple[str, str, str]] = [
    ("sb", "小盲对不上", "blinds"),
    ("bb", "大盲对不上", "blinds"),
    ("ante", "前注对不上", "blinds"),
    ("straddle", "抢注对不上", "blinds"),
    ("chips_unit", "筹码单位（BB vs 筹码）", "expected"),
    ("chips_value", "筹码数值不同", "expected"),
    ("board_sys_empty", "Chess 公牌为空", "expected"),
    ("board_sig_empty", "信号公牌为空", "board"),
    ("board_len", "公牌张数不同", "board"),
    ("board_cards", "公牌内容不同", "board"),
    ("player_n", "玩家人数", "seat"),
    ("position", "位置", "seat"),
    ("act_amount_unit", "行动金额单位（BB vs 数）", "action_rewrite"),
    ("act_amount", "行动金额数值不同", "action_rewrite"),
    ("act_miss_street:PREFLOP", "漏行动 · 翻前", "action_miss"),
    ("act_miss_street:FLOP", "漏行动 · 翻牌", "action_miss"),
    ("act_miss_street:TURN", "漏行动 · 转牌", "action_miss"),
    ("act_miss_street:RIVER", "漏行动 · 河牌", "action_miss"),
    ("act_extra_street:PREFLOP", "多行动 · 翻前", "action_extra"),
    ("act_extra_street:FLOP", "多行动 · 翻牌", "action_extra"),
    ("act_extra_street:TURN", "多行动 · 转牌", "action_extra"),
    ("act_extra_street:RIVER", "多行动 · 河牌", "action_extra"),
    ("no_signal", "缺信号", "missing"),
    ("no_chess", "缺 Chess", "missing"),
]
FACET_LABEL = {k: lab for k, lab, _g in FACET_META}
FACET_GROUP = {k: g for k, _lab, g in FACET_META}
FACET_TREND = [k for k, _lab, _g in FACET_META]
FACET_GROUP_LABEL = {
    "blinds": "盲注细项",
    "expected": "已知口径（几乎天天有）",
    "board": "公共牌",
    "seat": "人数 / 位置",
    "action_rewrite": "行动改写",
    "action_miss": "漏行动",
    "action_extra": "多行动",
    "action_map": "行动类型映射",
    "action_type_miss": "漏了哪种行动",
    "missing": "缺报文",
    "other": "其他",
}
_STREET_CN = {
    "PREFLOP": "翻前",
    "FLOP": "翻牌",
    "TURN": "转牌",
    "RIVER": "河牌",
}

# Trace Discover 单次上限约 500；达到此数则拆窗补全。
DISCOVER_CAP = 480
KNOWN_WINDOWS: list[tuple[str, str, str]] = [
    ("2026-08-14", "2026-08-14 00:00:00", "2026-08-14 23:59:59"),
    ("2026-08-12", "2026-08-12 14:00:00", "2026-08-12 15:30:00"),
    ("2026-08-11", "2026-08-11 10:00:00", "2026-08-11 16:15:00"),
    ("2026-08-07", "2026-08-07 10:45:00", "2026-08-07 23:59:00"),
    ("2026-08-03", "2026-08-03 14:00:00", "2026-08-03 23:52:00"),
]


def validate_day(day: str) -> str:
    s = str(day or "").strip()[:10]
    if not _DAY_RE.fullmatch(s):
        raise ValueError("日期格式应为 YYYY-MM-DD")
    return s


def classify_issue_kind(raw: Any) -> str:
    s = str(raw or "").replace("正确值", "信号").strip()
    if not s:
        return ""
    if s in ("盲注/前注", "盲注"):
        return "blinds"
    if s == "玩家人数":
        return "player_n"
    if s == "位置":
        return "position"
    if s == "起始筹码":
        return "chips"
    if s == "公共牌":
        return "board"
    if s in ("行动缺失", "漏行动"):
        return "action_missing"
    if s in ("行动多余", "多余行动"):
        return "action_extra"
    if any(x in s for x in ("行动类型", "金额", "行动内容", "动作类型")):
        return "action_rewrite"
    if "盲" in s or "前注" in s or "抢注" in s:
        return "blinds"
    if "筹码" in s:
        return "chips"
    if "位置" in s:
        return "position"
    if "公共牌" in s or "公牌" in s:
        return "board"
    if "人数" in s:
        return "player_n"
    return "other"


def classify_step_kinds(step: dict[str, Any]) -> list[str]:
    seen: list[str] = []

    def add(k: str) -> None:
        if k and k not in seen:
            seen.append(k)

    if not step.get("signal_present"):
        add("no_signal")
    if step.get("chess_exact") is None:
        add("no_chess")
    if str(step.get("first_issue") or "").startswith("信号无法还原"):
        add("other")
    for it in step.get("issues") or []:
        if not isinstance(it, dict):
            continue
        add(classify_issue_kind(it.get("kind") or it.get("title") or ""))
    return seen


def _has_bb_unit(v: Any) -> bool:
    return "BB" in str(v or "").upper()


def _facet_num(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    s = str(v).upper().replace("BB", "").strip()
    if s in ("（无此座位）", "[]", "NONE", "NULL"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _cards_list(v: Any) -> list[str]:
    if v is None or v == "" or v == "[]":
        return []
    if isinstance(v, list):
        return [str(x) for x in v]
    return [str(v)]


def _norm_act(v: Any) -> str:
    return str(v or "").strip().upper()


def _street_key(v: Any) -> str:
    s = str(v or "").strip().upper().replace("PRE_FLOP", "PREFLOP")
    return s if s in _STREET_CN else ""


def facet_label(fid: str) -> str:
    if fid in FACET_LABEL:
        return FACET_LABEL[fid]
    if fid.startswith("act_map:"):
        pair = fid.split(":", 1)[1]
        a, _, b = pair.partition(">")
        return f"{a or '?'}→{b or '?'}"
    if fid.startswith("act_miss_type:"):
        return "漏 " + fid.split(":", 1)[1]
    if fid.startswith("act_extra_type:"):
        return "多 " + fid.split(":", 1)[1]
    if fid.startswith("act_miss_street:"):
        st = fid.split(":", 1)[1]
        return "漏行动 · " + (_STREET_CN.get(st) or st)
    if fid.startswith("act_extra_street:"):
        st = fid.split(":", 1)[1]
        return "多行动 · " + (_STREET_CN.get(st) or st)
    return fid


def facet_group(fid: str) -> str:
    if fid in FACET_GROUP:
        return FACET_GROUP[fid]
    if fid.startswith("act_map:"):
        return "action_map"
    if fid.startswith("act_miss_type:"):
        return "action_type_miss"
    if fid.startswith("act_extra_type:"):
        return "action_extra"
    if fid.startswith("act_miss_street:"):
        return "action_miss"
    if fid.startswith("act_extra_street:"):
        return "action_extra"
    return "other"


def _example_pair(left: Any, right: Any, *, limit: int = 48) -> str:
    a = str(left if left is not None else "—")
    b = str(right if right is not None else "—")
    if len(a) > limit:
        a = a[: limit - 1] + "…"
    if len(b) > limit:
        b = b[: limit - 1] + "…"
    return f"{a} → {b}"


def facets_from_issue(it: dict[str, Any]) -> list[tuple[str, str]]:
    """一条 issue → [(facet_id, example), ...]。"""
    kind = str(it.get("kind") or "").strip()
    title = str(it.get("title") or "").strip()
    rows = [r for r in (it.get("rows") or []) if isinstance(r, dict)]
    mm = it.get("mismatch") if isinstance(it.get("mismatch"), dict) else {}
    out: list[tuple[str, str]] = []

    def add(fid: str, example: str = "") -> None:
        if fid:
            out.append((fid, example or title[:80]))

    if kind in ("盲注/前注", "盲注") or (
        "盲" in kind and "行动" not in kind and kind != "起始筹码"
    ):
        hit = False
        for row in rows:
            field = str(row.get("field") or "")
            ex = _example_pair(row.get("gt"), row.get("sys"))
            if "小盲" in field:
                add("sb", f"小盲 {ex}")
                hit = True
            elif "大盲" in field:
                add("bb", f"大盲 {ex}")
                hit = True
            elif "前注" in field:
                add("ante", f"前注 {ex}")
                hit = True
            elif "抢注" in field:
                add("straddle", f"抢注 {ex}")
                hit = True
        if not hit:
            add("sb", title)
        return out

    if kind == "起始筹码":
        unit = value = False
        ex_unit = ex_val = title
        for row in rows:
            if not row.get("diff"):
                continue
            g, s = row.get("gt"), row.get("sys")
            if _has_bb_unit(g) != _has_bb_unit(s):
                unit = True
                ex_unit = _example_pair(g, s)
            ng, ns = _facet_num(g), _facet_num(s)
            if ng is None or ns is None or abs(ng - ns) > 1e-9:
                value = True
                ex_val = _example_pair(g, s)
        if unit:
            add("chips_unit", ex_unit)
        if value:
            add("chips_value", ex_val)
        if not unit and not value:
            add("chips_value", title)
        return out

    if kind == "公共牌":
        row = rows[0] if rows else {}
        left, right = _cards_list(row.get("gt")), _cards_list(row.get("sys"))
        ex = _example_pair(left or "[]", right or "[]")
        if left and not right:
            add("board_sys_empty", ex)
        elif right and not left:
            add("board_sig_empty", ex)
        elif len(left) != len(right):
            add("board_len", ex)
        else:
            add("board_cards", ex)
        return out

    if kind == "玩家人数":
        row = rows[0] if rows else {}
        add("player_n", _example_pair(row.get("gt"), row.get("sys")) if row else title)
        return out
    if kind == "位置":
        add("position", title)
        return out

    g = mm.get("gt") if isinstance(mm.get("gt"), dict) else {}
    s = mm.get("sys") if isinstance(mm.get("sys"), dict) else {}
    street = _street_key(mm.get("street") or g.get("street") or s.get("street"))
    op = str(mm.get("kind") or "").strip().lower()
    gt_act = _norm_act(g.get("actionType"))
    sys_act = _norm_act(s.get("actionType"))
    gt_amt, sys_amt = g.get("amount"), s.get("amount")

    if "缺失" in kind or op == "missing":
        if street:
            add(f"act_miss_street:{street}", title)
        if gt_act:
            add(f"act_miss_type:{gt_act}", title)
        if not street and not gt_act:
            add("act_miss_street:PREFLOP", title)
        return out
    if "多余" in kind or op == "extra":
        if street:
            add(f"act_extra_street:{street}", title)
        if sys_act:
            add(f"act_extra_type:{sys_act}", title)
        if not street and not sys_act:
            add("act_extra_street:PREFLOP", title)
        return out

    if (
        "行动" in kind
        or "金额" in kind
        or op == "rewrite"
        or kind in ("行动类型不正确", "金额不正确", "行动类型与金额均不正确", "行动内容不正确")
    ):
        if gt_act and sys_act and gt_act != sys_act:
            add(f"act_map:{gt_act}>{sys_act}", title)
        unit = value = False
        if _has_bb_unit(gt_amt) != _has_bb_unit(sys_amt) and (
            gt_amt not in (None, "") or sys_amt not in (None, "")
        ):
            unit = True
        ng, ns = _facet_num(gt_amt), _facet_num(sys_amt)
        if ng is not None and ns is not None:
            if abs(ng - ns) > 1e-9:
                value = True
        elif "金额" in kind:
            value = True
        if unit:
            add("act_amount_unit", _example_pair(gt_amt, sys_amt))
        if value:
            add("act_amount", _example_pair(gt_amt, sys_amt))
        if not out:
            add("act_amount", title)
        return out

    return out


def facets_from_step(step: dict[str, Any]) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(fid: str, example: str = "") -> None:
        if fid and fid not in seen:
            seen.add(fid)
            found.append((fid, example))

    if not step.get("signal_present"):
        add("no_signal", "缺信号报文")
    if step.get("chess_exact") is None:
        add("no_chess", "缺 Chess 报文")
    for it in step.get("issues") or []:
        if not isinstance(it, dict):
            continue
        for fid, ex in facets_from_issue(it):
            add(fid, ex)
    return found


def facet_fields_from_steps(steps: list[dict[str, Any]]) -> dict[str, Any]:
    facet_hero: Counter[str] = Counter()
    facet_hand: set[str] = set()
    examples: dict[str, str] = {}
    for s in steps:
        for fid, ex in facets_from_step(s):
            facet_hero[fid] += 1
            facet_hand.add(fid)
            if fid not in examples and ex:
                examples[fid] = ex
    ordered = _order_facets(facet_hand)
    return {
        "facets": ordered,
        "facet_hero": {k: int(facet_hero[k]) for k in ordered},
        "facet_examples": {k: examples[k] for k in ordered if examples.get(k)},
    }


def _order_facets(ids: Any) -> list[str]:
    have = set(ids)
    out: list[str] = []
    for fid in FACET_TREND:
        if fid in have:
            out.append(fid)
    rest = sorted(have - set(out), key=lambda x: (not x.startswith("act_map:"), x))
    out.extend(rest)
    return out


def _hand_key(open_id: str, hole: str) -> str:
    return f"{(open_id or '').strip()}|{(hole or '').strip()}"


def brief_from_saved(
    *,
    meta: dict[str, Any],
    metrics: dict[str, Any],
    steps: list[dict[str, Any]],
    compare_id: str,
) -> dict[str, Any]:
    kind_hero: Counter[str] = Counter()
    kind_hand: set[str] = set()
    first_issue = ""
    structure_hero_n = 0
    action_hero_n = 0
    for s in steps:
        ks = list(s.get("kinds") or classify_step_kinds(s))
        s["kinds"] = ks
        for k in ks:
            kind_hero[k] += 1
        kind_hand.update(ks)
        if set(ks) & STRUCTURE_KINDS:
            structure_hero_n += 1
        if set(ks) & ACTION_KINDS:
            action_hero_n += 1
        if not first_issue and s.get("chess_exact") is False and s.get("first_issue"):
            first_issue = str(s.get("first_issue"))
    comparable = int(metrics.get("comparable_n") or 0)
    diff_n = int(metrics.get("diff_n") or 0)
    extra = facet_fields_from_steps(steps)
    return {
        "open_id": meta.get("open_id") or "",
        "hole_key": meta.get("hole_key") or "",
        "start_time": meta.get("start_time") or "",
        "end_time": meta.get("end_time") or "",
        "compare_id": compare_id,
        "hero_n": int(metrics.get("hero_n") or metrics.get("step_n") or 0),
        "exact_n": int(metrics.get("exact_n") or 0),
        "diff_n": diff_n,
        "no_chess_n": int(metrics.get("no_chess_n") or 0),
        "no_signal_n": int(metrics.get("no_signal_n") or 0),
        "comparable_n": comparable,
        "structure_hero_n": structure_hero_n,
        "action_hero_n": action_hero_n,
        "kinds": [k for k in KIND_ORDER if k in kind_hand],
        "kind_hero": {k: int(kind_hero[k]) for k in KIND_ORDER if kind_hero[k]},
        "first_issue": first_issue,
        "dirty": diff_n > 0,
        "structure": structure_hero_n > 0,
        "action": action_hero_n > 0,
        **extra,
    }


def empty_day(day: str) -> dict[str, Any]:
    return {
        "date": day,
        "source": "empty",
        "generated_at": "",
        "elapsed_s": 0,
        "discover_n": 0,
        "hand_n": 0,
        "error_n": 0,
        "metrics": {},
        "kinds": {},
        "facets": {},
        "hands": [],
        "errors": [],
    }


def recompute_day(doc: dict[str, Any]) -> dict[str, Any]:
    hands = [h for h in (doc.get("hands") or []) if isinstance(h, dict)]
    errors = [e for e in (doc.get("errors") or []) if isinstance(e, dict)]
    hero_n = sum(int(h.get("hero_n") or 0) for h in hands)
    exact_n = sum(int(h.get("exact_n") or 0) for h in hands)
    diff_n = sum(int(h.get("diff_n") or 0) for h in hands)
    comparable_n = sum(int(h.get("comparable_n") or 0) for h in hands)
    no_chess_n = sum(int(h.get("no_chess_n") or 0) for h in hands)
    no_signal_n = sum(int(h.get("no_signal_n") or 0) for h in hands)
    dirty_hand_n = sum(1 for h in hands if h.get("dirty"))
    kind_hero: Counter[str] = Counter()
    kind_hand: Counter[str] = Counter()
    for h in hands:
        kh = h.get("kind_hero") if isinstance(h.get("kind_hero"), dict) else {}
        for k, n in kh.items():
            kind_hero[str(k)] += int(n or 0)
        for k in h.get("kinds") or []:
            kind_hand[str(k)] += 1
    structure_hits = sum(int(kind_hero[k]) for k in STRUCTURE_KINDS)
    action_hits = sum(int(kind_hero[k]) for k in ACTION_KINDS)
    structure_hero_n = sum(int(h.get("structure_hero_n") or 0) for h in hands)
    action_hero_n = sum(int(h.get("action_hero_n") or 0) for h in hands)
    structure_hand_n = sum(1 for h in hands if h.get("structure"))
    action_hand_n = sum(1 for h in hands if h.get("action"))
    exact_pct = round(100.0 * exact_n / comparable_n, 1) if comparable_n else None
    structure_pct = (
        round(100.0 * structure_hero_n / comparable_n, 1) if comparable_n else None
    )
    action_pct = (
        round(100.0 * action_hero_n / comparable_n, 1) if comparable_n else None
    )

    kinds: dict[str, Any] = {}
    for k in KIND_ORDER:
        hn = int(kind_hero.get(k) or 0)
        hnd = int(kind_hand.get(k) or 0)
        if hn or hnd:
            kinds[k] = {
                "hero_n": hn,
                "hand_n": hnd,
                "label": KIND_LABEL[k],
                "group": KIND_GROUP[k],
                "hero_pct": round(100.0 * hn / comparable_n, 1) if comparable_n else None,
            }

    facet_hero: Counter[str] = Counter()
    facet_hand: Counter[str] = Counter()
    facet_ex: dict[str, str] = {}
    for h in hands:
        fh = h.get("facet_hero") if isinstance(h.get("facet_hero"), dict) else {}
        for k, n in fh.items():
            facet_hero[str(k)] += int(n or 0)
        for k in h.get("facets") or []:
            facet_hand[str(k)] += 1
        exs = h.get("facet_examples") if isinstance(h.get("facet_examples"), dict) else {}
        for k, ex in exs.items():
            if k not in facet_ex and ex:
                facet_ex[str(k)] = str(ex)
    facet_ids = _order_facets(set(facet_hero) | set(facet_hand))
    facets: dict[str, Any] = {}
    for fid in facet_ids:
        hn = int(facet_hero.get(fid) or 0)
        hnd = int(facet_hand.get(fid) or 0)
        if hn or hnd:
            facets[fid] = {
                "hero_n": hn,
                "hand_n": hnd,
                "label": facet_label(fid),
                "group": facet_group(fid),
                "hero_pct": round(100.0 * hn / comparable_n, 1) if comparable_n else None,
                "example": facet_ex.get(fid) or "",
            }

    doc["hand_n"] = len(hands)
    doc["error_n"] = len(errors)
    doc["hands"] = hands
    doc["errors"] = errors
    doc["kinds"] = kinds
    doc["facets"] = facets
    doc["metrics"] = {
        "hero_n": hero_n,
        "exact_n": exact_n,
        "diff_n": diff_n,
        "comparable_n": comparable_n,
        "exact_pct": exact_pct,
        "no_chess_n": no_chess_n,
        "no_signal_n": no_signal_n,
        "dirty_hand_n": dirty_hand_n,
        "structure_hits": structure_hits,
        "action_hits": action_hits,
        "structure_hero_n": structure_hero_n,
        "action_hero_n": action_hero_n,
        "structure_pct": structure_pct,
        "action_pct": action_pct,
        "structure_hand_n": structure_hand_n,
        "action_hand_n": action_hand_n,
    }
    return doc


def day_path(day: str) -> Path:
    return DAY_DIR / f"{validate_day(day)}.json"


def load_day(day: str) -> Optional[dict[str, Any]]:
    p = day_path(day)
    if not p.exists():
        return None
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(doc, dict):
        return None
    return doc


def save_day(doc: dict[str, Any]) -> Path:
    day = validate_day(str(doc.get("date") or ""))
    DAY_DIR.mkdir(parents=True, exist_ok=True)
    doc = recompute_day(doc)
    doc["date"] = day
    if not doc.get("generated_at"):
        doc["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    p = day_path(day)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)
    return p


def list_days() -> list[str]:
    if not DAY_DIR.exists():
        return []
    out = []
    for p in DAY_DIR.glob("*.json"):
        if _DAY_RE.fullmatch(p.stem):
            out.append(p.stem)
    out.sort()
    return out


def calendar_window(n: int = 14, *, until: str = "") -> list[str]:
    if until:
        end = datetime.strptime(validate_day(until), "%Y-%m-%d")
    else:
        end = datetime.now()
    return [(end - timedelta(days=n - 1 - i)).strftime("%Y-%m-%d") for i in range(n)]


def upsert_hand_brief(
    brief: dict[str, Any], *, day: str, source: str = "upsert"
) -> dict[str, Any]:
    day = validate_day(day)
    key = _hand_key(str(brief.get("open_id") or ""), str(brief.get("hole_key") or ""))
    with _lock:
        doc = load_day(day) or empty_day(day)
        hands = [h for h in (doc.get("hands") or []) if isinstance(h, dict)]
        hands = [
            h
            for h in hands
            if _hand_key(str(h.get("open_id") or ""), str(h.get("hole_key") or "")) != key
        ]
        hands.append(brief)
        doc["hands"] = hands
        if doc.get("source") in (None, "", "empty"):
            doc["source"] = source
        elif doc.get("source") != source:
            doc["source"] = "mixed"
        doc["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        save_day(doc)
        return load_day(day) or doc


def enrich_day_from_live(day: str) -> dict[str, Any]:
    """用已落盘的 discover_live 明细回填细项，不必重跑 Trace。"""
    day = validate_day(day)
    doc = load_day(day)
    if not doc:
        raise FileNotFoundError(f"没有日账：{day}")
    live = ROOT / "data" / "discover_live"
    hands_out: list[dict[str, Any]] = []
    filled = 0
    for h in doc.get("hands") or []:
        if not isinstance(h, dict):
            continue
        cid = str(h.get("compare_id") or "").strip()
        step_dir = live / cid / "steps"
        steps: list[dict[str, Any]] = []
        if cid and step_dir.is_dir():
            for p in sorted(step_dir.glob("hero-*.json")):
                try:
                    steps.append(json.loads(p.read_text(encoding="utf-8")))
                except Exception:
                    continue
        if steps:
            h = dict(h)
            h.update(facet_fields_from_steps(steps))
            filled += 1
        hands_out.append(h)
    doc["hands"] = hands_out
    save_day(doc)
    print(f"enrich {day} hands={len(hands_out)} filled={filled}", flush=True)
    return load_day(day) or doc


def enrich_all_days() -> list[str]:
    days = list_days()
    for d in days:
        enrich_day_from_live(d)
    return days


def write_job(job: dict[str, Any]) -> None:
    JOB_DIR.mkdir(parents=True, exist_ok=True)
    jid = str(job.get("id") or "")
    if not jid:
        return
    p = JOB_DIR / f"{jid}.json"
    p.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")


def get_job(jid: str) -> Optional[dict[str, Any]]:
    with _lock:
        if jid in _jobs:
            return dict(_jobs[jid])
    p = JOB_DIR / f"{jid}.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def start_daily_job(
    day: str,
    *,
    max_hands: int = 500,
    trace_env: str = "",
    api: str = "",
    start_time: str = "",
    end_time: str = "",
) -> dict[str, Any]:
    day = validate_day(day)
    start = str(start_time or "").strip() or f"{day} 00:00:00"
    end = str(end_time or "").strip() or f"{day} 23:59:59"
    with _lock:
        for j in _jobs.values():
            if j.get("date") == day and j.get("status") == "running":
                return dict(j)
        jid = time.strftime("%Y%m%d-%H%M%S") + "-" + day
        job = {
            "id": jid,
            "date": day,
            "status": "running",
            "total": 0,
            "done": 0,
            "ok_n": 0,
            "err_n": 0,
            "current": "",
            "error": "",
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "max_hands": int(max_hands),
            "start_time": start,
            "end_time": end,
        }
        _jobs[jid] = job
        write_job(job)

    t = threading.Thread(
        target=_run_daily_job,
        args=(jid, day, int(max_hands), trace_env, api, start, end),
        daemon=True,
    )
    t.start()
    return dict(job)


def _update_job(jid: str, **kwargs: Any) -> None:
    with _lock:
        job = _jobs.get(jid) or {}
        job.update(kwargs)
        _jobs[jid] = job
        write_job(job)


def _parse_window_dt(text: str) -> datetime:
    return datetime.strptime(str(text or "").strip()[:19], "%Y-%m-%d %H:%M:%S")


def _discover_row_key(row: dict[str, Any]) -> str:
    return "|".join(
        [
            str(row.get("openId") or row.get("open_id") or "").strip(),
            str(row.get("holeCards") or row.get("hole_cards") or "").strip(),
            str(row.get("firstSeen") or row.get("first_seen") or "").strip()[:19],
        ]
    )


def discover_all_rows(client: Any, start: str, end: str) -> list[dict[str, Any]]:
    """traceDiscover 单次约 500 封顶时拆窗合并，避免整天只拿到最新 500 手。"""

    def merge(st: str, et: str, min_span_s: int = 600) -> dict[str, dict[str, Any]]:
        raw = client.trace_discover(start_time=st, end_time=et)
        chunk = raw if isinstance(raw, list) else []
        t0 = _parse_window_dt(st)
        t1 = _parse_window_dt(et)
        span_s = max(0.0, (t1 - t0).total_seconds())
        if len(chunk) < DISCOVER_CAP or span_s <= min_span_s:
            out: dict[str, dict[str, Any]] = {}
            for r in chunk:
                if isinstance(r, dict):
                    out[_discover_row_key(r)] = r
            return out
        mid = t0 + (t1 - t0) / 2
        mid_s = mid.strftime("%Y-%m-%d %H:%M:%S")
        left = merge(st, mid_s, min_span_s)
        right = merge(mid_s, et, min_span_s)
        left.update(right)
        return left

    merged = merge(start, end)
    return sorted(
        merged.values(),
        key=lambda r: str(r.get("firstSeen") or r.get("lastSeen") or ""),
    )


def run_window_blocking(
    day: str,
    start: str,
    end: str,
    *,
    max_hands: int = 0,
    trace_env: str = "uat",
    api: str = "",
) -> dict[str, Any]:
    day = validate_day(day)
    start = str(start or "").strip() or f"{day} 00:00:00"
    end = str(end or "").strip() or f"{day} 23:59:59"
    jid = time.strftime("%Y%m%d-%H%M%S") + "-" + day + "-cli"
    job = {
        "id": jid,
        "date": day,
        "status": "running",
        "total": 0,
        "done": 0,
        "ok_n": 0,
        "err_n": 0,
        "current": "",
        "error": "",
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "max_hands": int(max_hands),
        "start_time": start,
        "end_time": end,
    }
    with _lock:
        _jobs[jid] = job
        write_job(job)
    print(f"job {jid} {day} {start} ~ {end}", flush=True)
    _run_daily_job(jid, day, int(max_hands), trace_env, api, start, end)
    return get_job(jid) or job


def _run_daily_job(
    jid: str,
    day: str,
    max_hands: int,
    trace_env: str,
    api: str,
    start_time: str = "",
    end_time: str = "",
) -> None:
    t0 = time.time()
    try:
        from discover_compare import compare_hand_signal_chess
        from trace_client import TraceClient
        from trace_envs import DEFAULT_TRACE_ENV, normalize_trace_env, resolve_api_base
        from trace_query_config import _norm_time, is_valid_api_time

        start = str(start_time or "").strip() or f"{day} 00:00:00"
        end = str(end_time or "").strip() or f"{day} 23:59:59"
        win_start = _norm_time(start)
        win_end = _norm_time(end)
        if not is_valid_api_time(win_start) or not is_valid_api_time(win_end):
            raise ValueError(f"时间格式无效：{win_start} ~ {win_end}")
        raw_env = str(trace_env or "").strip() or DEFAULT_TRACE_ENV
        env_id = normalize_trace_env(raw_env)
        client = TraceClient(
            env_id=env_id,
            base_url=resolve_api_base(env_id, override=str(api or "").strip()),
        )
        rows = discover_all_rows(client, win_start, win_end)
        if max_hands and len(rows) > max_hands:
            rows = rows[:max_hands]
        _update_job(jid, total=len(rows), current="已发现组合，开始逐手对比")
        print(f"  discover {day} n={len(rows)}", flush=True)

        hands: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        seen: set[str] = set()
        existing = load_day(day)
        if (
            isinstance(existing, dict)
            and existing.get("source") == "batch"
            and str(existing.get("window_start") or "") == start
            and str(existing.get("window_end") or "") == end
        ):
            for h in existing.get("hands") or []:
                if not isinstance(h, dict):
                    continue
                rk = _hand_key(str(h.get("open_id") or ""), str(h.get("hole_key") or ""))
                rk = rk + "|" + str(h.get("start_time") or "")[:19]
                if rk in seen:
                    continue
                seen.add(rk)
                hands.append(h)

        def flush(*, finished: bool = False) -> None:
            doc = empty_day(day)
            doc["source"] = "batch"
            doc["discover_n"] = len(rows)
            doc["hands"] = list(hands)
            doc["errors"] = list(errors)
            doc["elapsed_s"] = round(time.time() - t0, 2)
            doc["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            doc["job_id"] = jid
            doc["window_start"] = start
            doc["window_end"] = end
            doc["status"] = "done" if finished else "running"
            with _lock:
                save_day(doc)

        for i, r in enumerate(rows, start=1):
            if not isinstance(r, dict):
                continue
            oid = str(r.get("openId") or r.get("open_id") or "").strip()
            hole = str(r.get("holeCards") or r.get("hole_cards") or "").strip()
            hand_start = str(r.get("firstSeen") or start)
            hand_end = str(r.get("lastSeen") or end)
            rk = _hand_key(oid, hole) + "|" + hand_start[:19]
            label = f"{oid[:10]}… {hole}" if len(oid) > 10 else f"{oid} {hole}"
            _update_job(jid, done=i - 1, current=label)
            if rk in seen:
                _update_job(jid, done=i, ok_n=len(hands), err_n=len(errors), current=label)
                continue
            if not oid or not hole:
                errors.append({"open_id": oid, "hole_key": hole, "error": "缺 openId/底牌"})
                continue
            try:
                result = compare_hand_signal_chess(
                    open_id=oid,
                    hole_cards=hole,
                    start_time=hand_start,
                    end_time=hand_end,
                    trace_env=trace_env,
                    api=api,
                    ledger=False,
                )
                brief = result.get("brief")
                if not isinstance(brief, dict):
                    raise ValueError("对比未返回日账单手摘要")
                hands.append(brief)
                seen.add(rk)
                _update_job(jid, done=i, ok_n=len(hands), err_n=len(errors), current=label)
                print(
                    f"  {day} {i}/{len(rows)} ok {label} hero={brief.get('hero_n')} "
                    f"exact={brief.get('exact_n')}/{brief.get('comparable_n')}",
                    flush=True,
                )
            except Exception as e:
                errors.append({"open_id": oid, "hole_key": hole, "error": str(e)})
                _update_job(jid, done=i, ok_n=len(hands), err_n=len(errors), current=label)
                print(f"  {day} {i}/{len(rows)} ERR {label} {e}", flush=True)
            if i % 3 == 0:
                flush(finished=False)
        flush(finished=True)
        _update_job(
            jid,
            status="done",
            done=len(rows),
            ok_n=len(hands),
            err_n=len(errors),
            current="",
            elapsed_s=round(time.time() - t0, 2),
        )
        print(
            f"  done {day} ok={len(hands)} err={len(errors)} "
            f"{round(time.time() - t0, 1)}s",
            flush=True,
        )
    except Exception as e:
        _update_job(
            jid, status="error", error=str(e), elapsed_s=round(time.time() - t0, 2)
        )
        print(f"  FAIL {day} {e}", flush=True)


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    p = argparse.ArgumentParser(description="信号→Chess 按已知时间窗跑日账")
    p.add_argument("--all", action="store_true", help="跑 KNOWN_WINDOWS 全部日期")
    p.add_argument("--probe", action="store_true", help="只探 discover 条数，不对比")
    p.add_argument("--enrich", action="store_true", help="从已有 discover_live 回填细项，不重跑")
    p.add_argument("--day", default="", help="只跑某一天 YYYY-MM-DD")
    p.add_argument("--start", default="", help="开始时间")
    p.add_argument("--end", default="", help="结束时间")
    p.add_argument("--max-hands", type=int, default=0, help="0=不截断")
    p.add_argument("--trace-env", default="uat")
    args = p.parse_args(argv)

    windows = list(KNOWN_WINDOWS)
    if args.day:
        day = validate_day(args.day)
        hit = [w for w in windows if w[0] == day]
        if args.start or args.end:
            windows = [
                (
                    day,
                    args.start or (hit[0][1] if hit else f"{day} 00:00:00"),
                    args.end or (hit[0][2] if hit else f"{day} 23:59:59"),
                )
            ]
        elif hit:
            windows = hit
        else:
            windows = [(day, f"{day} 00:00:00", f"{day} 23:59:59")]
    elif args.enrich:
        windows = []
    elif not args.all and not args.probe:
        p.error("请指定 --all / --probe / --enrich / --day")

    if args.enrich:
        if args.day:
            enrich_day_from_live(validate_day(args.day))
        else:
            enrich_all_days()
        return 0

    if args.probe:
        from trace_client import TraceClient
        from trace_envs import DEFAULT_TRACE_ENV, normalize_trace_env, resolve_api_base
        from trace_query_config import _norm_time

        env_id = normalize_trace_env(args.trace_env or DEFAULT_TRACE_ENV)
        client = TraceClient(
            env_id=env_id, base_url=resolve_api_base(env_id)
        )
        for day, start, end in windows:
            st, et = _norm_time(start), _norm_time(end)
            rows = discover_all_rows(client, st, et)
            print(f"{day}\t{st} ~ {et}\tn={len(rows)}")
        return 0

    for day, start, end in windows:
        run_window_blocking(
            day,
            start,
            end,
            max_hands=int(args.max_hands),
            trace_env=args.trace_env,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
