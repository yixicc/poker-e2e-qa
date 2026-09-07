"""组合发现：每次 hero_action 做 信号引擎 vs Chess（无 Excel 真值）。"""

from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from evidence_report import build_issue_blocks, chess_norm_for_compare
from daily_sig_chess import brief_from_saved, classify_step_kinds, upsert_hand_brief
from module_pipeline import analyze_hand_trace, spans_named
from step_compare import _signal_from_chain
from trace_client import TraceClient, fetch_hand_spans
from trace_envs import DEFAULT_TRACE_ENV, get_trace_env, normalize_trace_env, resolve_api_base
from trace_query_config import _norm_time, is_valid_api_time

ROOT = Path(__file__).resolve().parent.parent
LIVE_DIR = ROOT / "data" / "discover_live"

_ID_RE = re.compile(r"^[A-Za-z0-9._-]{8,80}$")
_BLIND_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)(?:\s*\(\s*(\d+(?:\.\d+)?)\s*\))?"
)
_PENDING_ACT = {"", "LET", "DOING", "DOING_ACTION", "HERO_DOING"}
_ROLE_POS = {"DEALER": "BTN", "BTN": "BTN", "SB": "SB", "BB": "BB", "STRADDLE": "STRADDLE"}
_AFTER_BB = {
    1: ["UTG"],
    2: ["UTG", "CO"],
    3: ["UTG", "HJ", "CO"],
    4: ["UTG", "LJ", "HJ", "CO"],
    5: ["UTG", "UTG1", "LJ", "HJ", "CO"],
    6: ["UTG", "UTG1", "UTG2", "LJ", "HJ", "CO"],
}
_HH_STREET = (
    ("preflop", "PREFLOP"),
    ("flop", "FLOP"),
    ("turn", "TURN"),
    ("river", "RIVER"),
)


def validate_compare_id(cid: str) -> str:
    s = str(cid or "").strip()
    if not _ID_RE.fullmatch(s):
        raise ValueError("对比 ID 无效")
    return s


def _unwrap(v: Any) -> Any:
    if isinstance(v, dict) and "value" in v:
        return v.get("value")
    return v


def _numish(v: Any) -> Any:
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        if isinstance(v, float) and abs(v - round(v)) < 1e-9:
            return int(round(v))
        return v
    s = str(v).strip()
    if not s:
        return None
    try:
        f = float(s)
        if abs(f - round(f)) < 1e-9:
            return int(round(f))
        return f
    except ValueError:
        return s


def _clean_time(text: str) -> str:
    t = str(text or "").strip().replace("Z", "")
    t = re.sub(r"[+-]\d{2}:\d{2}$", "", t)
    return _norm_time(t)


def _shift_api_time(text: str, minutes: int) -> str:
    raw = _clean_time(text)
    if not raw:
        return ""
    stamp = raw[:19]
    try:
        dt = datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return raw
    return (dt + timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")


def _parse_blinds(show_info: Any) -> dict[str, Any]:
    s = str(_unwrap(show_info) or "").strip()
    if not s:
        return {}
    m = _BLIND_RE.search(s)
    if not m:
        return {}
    out: dict[str, Any] = {
        "smallBlind": _numish(m.group(1)),
        "bigBlind": _numish(m.group(2)),
    }
    if m.group(3) is not None:
        out["ante"] = _numish(m.group(3))
    return out


def _community_cards(signal_req: dict) -> list[str]:
    table = signal_req.get("table") if isinstance(signal_req.get("table"), dict) else {}
    raw = table.get("community_cards")
    out: list[str] = []
    if isinstance(raw, list):
        for item in raw:
            v = str(_unwrap(item) or "").strip()
            if v:
                out.append(v)
    elif isinstance(raw, str) and raw.strip():
        out.extend(x for x in raw.replace(",", " ").split() if x)
    return out


def _hero_event(signal_req: Optional[dict]) -> Optional[dict]:
    if not isinstance(signal_req, dict):
        return None
    params = signal_req.get("parameters")
    events = params.get("events") if isinstance(params, dict) else None
    if not isinstance(events, list):
        return None
    last_hero = None
    for ev in events:
        if not isinstance(ev, dict):
            continue
        et = str(ev.get("event_type") or ev.get("type") or "").lower()
        if "hero" in et:
            last_hero = ev
    return last_hero


def signal_to_gto_norm(signal_req: Any) -> Optional[dict]:
    """把信号引擎 hero_action 还原成近似 gameInfo，供结构化对照。"""
    from step_compare_pages import _seat_p_label, signal_to_fusion_history

    if not isinstance(signal_req, dict):
        return None
    fh = signal_to_fusion_history(signal_req) or {}
    init_rows = list(fh.get("init") or [])
    if not init_rows and not any(fh.get(k) for k, _ in _HH_STREET):
        return None

    players: list[dict[str, Any]] = []
    pending_pos: list[dict[str, Any]] = []
    for row in init_rows:
        cells = list(row) + [""] * 6
        seat = _seat_p_label(cells[0])
        role = str(cells[3] or "").strip().upper()
        pos = _ROLE_POS.get(role, "")
        p = {"seat": seat, "position": pos or None, "initChips": _numish(cells[2])}
        players.append(p)
        if not pos:
            pending_pos.append(p)
    names = _AFTER_BB.get(len(pending_pos), [])
    if len(names) < len(pending_pos):
        extra = len(pending_pos) - len(names)
        names = [f"UTG{i}" if i else "UTG" for i in range(extra)] + list(names)
    for p, name in zip(pending_pos, names):
        p["position"] = name

    actions: list[dict[str, Any]] = []
    for hh_key, street in _HH_STREET:
        for row in fh.get(hh_key) or []:
            cells = list(row) + [""] * 6
            act = str(cells[3] or "").strip().upper()
            if act in _PENDING_ACT:
                continue
            if act == "BTN":
                act = "DEALER"
            amt = _numish(cells[4])
            if act in ("FOLD", "CHECK") and amt is None:
                amt = 0
            actions.append(
                {
                    "seat": _seat_p_label(cells[0]),
                    "street": street,
                    "actionType": act,
                    "amount": 0 if amt is None else amt,
                }
            )

    from cross_module import signal_table_show_info

    _path, show = signal_table_show_info(signal_req)
    blinds = _parse_blinds(show)
    gi: dict[str, Any] = {
        "players": players,
        "actionSequence": actions,
        "communityCards": _community_cards(signal_req),
        **blinds,
    }
    if gi.get("ante") is None:
        gi["ante"] = 0
    if "straddle" not in gi:
        gi["straddle"] = 0
    if not players and not actions:
        return None
    return {"gameInfo": gi}


def _hero_label(signal_req: Optional[dict], chess_norm: Optional[dict]) -> tuple[str, str]:
    """Return (decision_street, next_p0_label)."""
    ev = _hero_event(signal_req)
    street = ""
    label = ""
    if isinstance(ev, dict):
        act = str(ev.get("action") or "").strip().upper() or "DOING"
        amt = ev.get("action_amount")
        if amt in (None, "", 0, "0", "0.0"):
            label = act
        else:
            label = f"{act} {amt}"
    fh_street = ""
    if isinstance(signal_req, dict):
        from step_compare_pages import signal_to_fusion_history

        fh = signal_to_fusion_history(signal_req) or {}
        for key, name in reversed(_HH_STREET):
            if fh.get(key):
                fh_street = name
                break
    if not street:
        street = fh_street
    if not street and isinstance(chess_norm, dict):
        gi = chess_norm.get("gameInfo") if isinstance(chess_norm.get("gameInfo"), dict) else {}
        seq = list((gi or {}).get("actionSequence") or [])
        if seq and isinstance(seq[-1], dict):
            street = str(seq[-1].get("street") or "").upper()
        board = list((gi or {}).get("communityCards") or [])
        if not street:
            street = {0: "PREFLOP", 3: "FLOP", 4: "TURN", 5: "RIVER"}.get(len(board), "PREFLOP")
    if not label and isinstance(chess_norm, dict):
        gi = chess_norm.get("gameInfo") if isinstance(chess_norm.get("gameInfo"), dict) else {}
        seq = [a for a in ((gi or {}).get("actionSequence") or []) if isinstance(a, dict)]
        if seq:
            from compare_gto_requests import action_label

            label = action_label(seq[-1])
    return street or "PREFLOP", label or "—"


def _retitle(text: str) -> str:
    return (text or "").replace("正确值", "信号")


def _new_compare_id(open_id: str, hole: str, start: str, end: str) -> str:
    raw = f"{open_id}|{hole}|{start}|{end}".encode("utf-8")
    short = hashlib.sha1(raw).hexdigest()[:6]
    return time.strftime("%Y%m%d-%H%M%S") + "-" + short


def save_discover_compare(
    cid: str,
    *,
    meta: dict,
    summary: dict,
    steps: list[dict],
) -> Path:
    d = LIVE_DIR / cid
    (d / "steps").mkdir(parents=True, exist_ok=True)
    (d / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (d / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for s in steps:
        nth = int(s.get("nth") or 0)
        (d / "steps" / f"hero-{nth}.json").write_text(
            json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return d


def load_discover_meta(cid: str) -> dict:
    cid = validate_compare_id(cid)
    p = LIVE_DIR / cid / "meta.json"
    if not p.exists():
        raise FileNotFoundError(f"对比不存在：{cid}")
    return json.loads(p.read_text(encoding="utf-8"))


def load_discover_summary(cid: str) -> dict:
    cid = validate_compare_id(cid)
    p = LIVE_DIR / cid / "summary.json"
    if not p.exists():
        raise FileNotFoundError(f"对比不存在：{cid}")
    return json.loads(p.read_text(encoding="utf-8"))


def load_discover_step(cid: str, nth: int) -> dict:
    cid = validate_compare_id(cid)
    p = LIVE_DIR / cid / "steps" / f"hero-{int(nth)}.json"
    if not p.exists():
        raise FileNotFoundError(f"决策点不存在：{cid} P0#{nth}")
    return json.loads(p.read_text(encoding="utf-8"))


def compare_hand_signal_chess(
    *,
    open_id: str,
    hole_cards: str,
    start_time: str,
    end_time: str,
    trace_env: str = "",
    api: str = "",
    pad_minutes: int = 2,
    ledger: bool = True,
) -> dict[str, Any]:
    oid = str(open_id or "").strip()
    hole = str(hole_cards or "").strip()
    st = _clean_time(str(start_time or ""))
    et = _clean_time(str(end_time or ""))
    if not oid:
        raise ValueError("缺少 openId")
    if not hole:
        raise ValueError("缺少底牌")
    if not st or not et:
        raise ValueError("缺少时间窗")
    if not is_valid_api_time(st) or not is_valid_api_time(et):
        raise ValueError(f"时间格式无效：{st!r} ~ {et!r}")

    st_pad = _shift_api_time(st, -pad_minutes) or st
    et_pad = _shift_api_time(et, pad_minutes) or et

    raw_env = str(trace_env or "").strip() or DEFAULT_TRACE_ENV
    env_id = normalize_trace_env(raw_env)
    client = TraceClient(
        env_id=env_id,
        base_url=resolve_api_base(env_id, override=str(api or "").strip()),
    )
    t0 = time.time()
    fetched = fetch_hand_spans(
        client,
        open_id=oid,
        hole_key=hole,
        fixed_start=st_pad,
        fixed_end=et_pad,
    )
    spans = list(fetched.get("spans") or [])
    fetch_meta = {
        "open_id": fetched.get("open_id") or oid,
        "hole_cards_used": fetched.get("hole_cards_used") or hole,
        "start_time": fetched.get("start_time") or st_pad,
        "end_time": fetched.get("end_time") or et_pad,
        "span_n": len(spans),
        "error": fetched.get("error"),
        "tried": fetched.get("tried"),
    }
    try:
        env = get_trace_env(env_id)
        fetch_meta["env_label"] = env.get("env_label") or env_id
    except Exception:
        fetch_meta["env_label"] = env_id
    fetch_meta["trace_env"] = env_id

    heroes = spans_named(
        spans, service="texas-holdem-signal-engine", name="hero_action"
    )
    stats = {
        "hero_n": len(heroes),
        "step_n": 0,
        "exact_n": 0,
        "diff_n": 0,
        "no_chess_n": 0,
        "no_signal_n": 0,
        "comparable_n": 0,
        "span_n": len(spans),
    }
    steps: list[dict[str, Any]] = []
    hole_used = str(fetch_meta.get("hole_cards_used") or hole)

    for i in range(1, len(heroes) + 1):
        chain = analyze_hand_trace(
            spans,
            gt_norm=None,
            fetch_meta=fetch_meta,
            hero_ordinal=i,
        )
        signal = _signal_from_chain(chain)
        chess_norm = chess_norm_for_compare(chain, gt_norm=None)
        signal_req = signal.get("signal_request")
        signal_present = bool(signal.get("signal_present"))
        signal_gto = signal_to_gto_norm(signal_req) if signal_present else None
        street, label = _hero_label(signal_req if signal_present else None, chess_norm)

        issues: list[dict] = []
        first_issue = ""
        diff_count: Optional[int] = None
        if chess_norm is None:
            chess_exact: Optional[bool] = None
        elif not signal_present or signal_gto is None:
            chess_exact = False
            first_issue = "" if signal_present else ""
            if signal_present and signal_gto is None:
                first_issue = "信号无法还原为对照报文"
        else:
            issues = build_issue_blocks(signal_gto, chess_norm)
            diff_count = len(issues)
            chess_exact = diff_count == 0
            if issues:
                b0 = issues[0]
                first_issue = _retitle(
                    str(b0.get("title") or b0.get("summary") or b0.get("path") or "有差异")
                )

        gi = (signal_gto or {}).get("gameInfo") if isinstance(signal_gto, dict) else {}
        seq_len = len(list((gi or {}).get("actionSequence") or []))
        row = {
            "step_id": f"hero-{i}",
            "hand_uid": "",
            "hole_key": hole_used,
            "nth": i,
            "p0_count": len(heroes),
            "decision_street": street,
            "next_p0_label": label,
            "truncated_action_len": seq_len,
            "signal_gto": signal_gto,
            "chess_norm": chess_norm,
            "chess_exact": chess_exact,
            "diff_count": diff_count,
            "first_issue": first_issue,
            "issues": issues[:40],
            "align_mode": "nth_hero",
            "hero_ordinal": i,
            "hero_index": i - 1,
            "hero_count": int(chain.get("hero_count") or len(heroes)),
            "trace_note": chain.get("note") or "",
            "anchor_mode": chain.get("anchor_mode") or "",
            "signal_present": signal_present,
            "signal_request": signal_req,
            "signal_meta": signal.get("signal_meta") or {},
        }
        row["kinds"] = classify_step_kinds(row)
        steps.append(row)
        stats["step_n"] += 1
        if not signal_present:
            stats["no_signal_n"] += 1
        if chess_norm is None:
            stats["no_chess_n"] += 1
        elif signal_present and signal_gto is not None:
            if chess_exact is True:
                stats["exact_n"] += 1
            else:
                stats["diff_n"] += 1
            stats["comparable_n"] += 1

    comparable = int(stats["comparable_n"] or 0)
    exact = int(stats["exact_n"] or 0)
    stats["exact_pct"] = round(100.0 * exact / comparable, 1) if comparable else None
    stats["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    stats["elapsed_s"] = round(time.time() - t0, 2)

    cid = _new_compare_id(oid, hole, st, et)
    meta = {
        "id": cid,
        "open_id": oid,
        "hole_key": hole_used,
        "start_time": st,
        "end_time": et,
        "padded_start": st_pad,
        "padded_end": et_pad,
        "trace_env": env_id,
        "span_n": len(spans),
        "hero_n": len(heroes),
        "note": "信号引擎 vs Chess · 现场对比，不写入决策点冻结报告",
        "fetch": fetch_meta,
    }
    summary = {
        "compare_id": cid,
        "metrics": stats,
        "steps": [
            {
                "step_id": s["step_id"],
                "nth": s["nth"],
                "hole_key": s["hole_key"],
                "decision_street": s["decision_street"],
                "next_p0_label": s["next_p0_label"],
                "truncated_action_len": s["truncated_action_len"],
                "chess_exact": s["chess_exact"],
                "diff_count": s["diff_count"],
                "first_issue": s["first_issue"],
                "hero_ordinal": s["hero_ordinal"],
                "signal_present": bool(s.get("signal_present")),
                "kinds": list(s.get("kinds") or []),
            }
            for s in steps
        ],
    }
    save_discover_compare(cid, meta=meta, summary=summary, steps=steps)
    brief = brief_from_saved(
        meta=meta, metrics=stats, steps=steps, compare_id=cid
    )
    if ledger:
        try:
            upsert_hand_brief(brief, day=st[:10], source="upsert")
        except Exception:
            pass
    return {
        "ok": True,
        "compare_id": cid,
        "metrics": stats,
        "hero_n": len(heroes),
        "span_n": len(spans),
        "error": fetch_meta.get("error") if not spans else None,
        "brief": brief,
        "day": st[:10],
    }
