#!/usr/bin/env python3
"""Align poker actionSequence with LCS so missing/extra/rewrite are distinguished."""

from __future__ import annotations

from typing import Any, Optional


STREET_CN = {"PREFLOP": "翻前", "FLOP": "翻牌", "TURN": "转牌", "RIVER": "河牌"}


def action_label(a: Any) -> str:
    if not isinstance(a, dict):
        return str(a)
    return f"{a.get('seat')} {a.get('actionType')} {a.get('amount')} ({a.get('street')})"


def soft_key(a: Any) -> Optional[tuple]:
    """Match key: same street + seat. actionType/amount compared as rewrite after match."""
    if not isinstance(a, dict):
        return None
    from compare_gto_requests import _canon_seat_token, _canon_street_token

    return (
        _canon_street_token(a.get("street")),
        _canon_seat_token(a.get("seat")),
    )


def hard_key(a: Any) -> Optional[tuple]:
    if not isinstance(a, dict):
        return None
    sk = soft_key(a)
    if sk is None:
        return None
    from compare_gto_requests import _is_numberish, _num

    amt = a.get("amount")
    if amt is not None and _is_numberish(amt):
        amt_k = f"{_num(amt):.9g}"
    else:
        amt_k = str(amt if amt is not None else "")
    return sk + (amt_k,)


def _pair_by_seat_street_nth(
    gt_acts: list, sys_acts: list
) -> tuple[dict[int, int], set[int], set[int]]:
    """同街同座位按出现次序（第 N 次）配对。

    Returns:
      pair_map: gt_index -> sys_index
      missing_g: gt indices with no sys counterpart
      extra_s: sys indices with no gt counterpart
    """
    from collections import defaultdict

    g_by: dict[tuple, list[tuple[int, dict]]] = defaultdict(list)
    s_by: dict[tuple, list[tuple[int, dict]]] = defaultdict(list)
    for i, a in enumerate(gt_acts):
        k = soft_key(a)
        if k is not None:
            g_by[k].append((i, a))
    for i, a in enumerate(sys_acts):
        k = soft_key(a)
        if k is not None:
            s_by[k].append((i, a))

    pair_map: dict[int, int] = {}
    missing_g: set[int] = set()
    extra_s: set[int] = set()
    for k in set(g_by) | set(s_by):
        gl = g_by.get(k) or []
        sl = s_by.get(k) or []
        n = max(len(gl), len(sl))
        for nth in range(n):
            if nth < len(gl) and nth < len(sl):
                pair_map[gl[nth][0]] = sl[nth][0]
            elif nth < len(gl):
                missing_g.add(gl[nth][0])
            else:
                extra_s.add(sl[nth][0])
    return pair_map, missing_g, extra_s


def _lcs_pairs(gt_acts: list, sys_acts: list) -> list[tuple[int, int]]:
    """Deprecated helper: soft_key LCS. Prefer _pair_by_seat_street_nth."""
    n, m = len(gt_acts), len(sys_acts)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        ki = soft_key(gt_acts[i - 1])
        for j in range(1, m + 1):
            kj = soft_key(sys_acts[j - 1])
            if ki is not None and ki == kj:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    pairs: list[tuple[int, int]] = []
    i, j = n, m
    while i > 0 and j > 0:
        ki, kj = soft_key(gt_acts[i - 1]), soft_key(sys_acts[j - 1])
        if ki is not None and ki == kj and dp[i][j] == dp[i - 1][j - 1] + 1:
            pairs.append((i - 1, j - 1))
            i -= 1
            j -= 1
        elif dp[i - 1][j] >= dp[i][j - 1]:
            i -= 1
        else:
            j -= 1
    pairs.reverse()
    return pairs


def align_actions(gt_acts: Optional[list], sys_acts: Optional[list]) -> list[dict]:
    """Align two action lists by (street, seat) occurrence index.

    同一街同一座位的第 N 次行动互相对齐：
      - 双侧都有 → equal / rewrite
      - 仅正确值有 → missing
      - 仅对照侧有 → extra

    Each op:
      op: equal | rewrite | missing | extra
      gt, sys, gt_index, sys_index
    """
    g = [a for a in (gt_acts or []) if isinstance(a, dict)]
    s = [a for a in (sys_acts or []) if isinstance(a, dict)]
    pair_map, missing_g, extra_s = _pair_by_seat_street_nth(g, s)
    matched_g = set(pair_map.keys())
    matched_s = set(pair_map.values())

    ops: list[dict] = []
    gi = si = 0
    while gi < len(g) or si < len(s):
        if gi < len(g) and gi not in matched_g:
            ops.append(
                {
                    "op": "missing",
                    "gt": g[gi],
                    "sys": None,
                    "gt_index": gi,
                    "sys_index": None,
                }
            )
            gi += 1
            continue
        if si < len(s) and si not in matched_s:
            ops.append(
                {
                    "op": "extra",
                    "gt": None,
                    "sys": s[si],
                    "gt_index": None,
                    "sys_index": si,
                }
            )
            si += 1
            continue
        if gi < len(g) and si < len(s) and pair_map.get(gi) == si:
            ga, sa = g[gi], s[si]
            from compare_gto_requests import (
                action_types_equivalent,
                amounts_equivalent,
                seats_equivalent,
                streets_equivalent,
            )

            same_amt = amounts_equivalent(ga.get("amount"), sa.get("amount"))
            same_type = action_types_equivalent(ga.get("actionType"), sa.get("actionType"))
            same_meta = seats_equivalent(ga.get("seat"), sa.get("seat")) and streets_equivalent(
                ga.get("street"), sa.get("street")
            )
            same_all = same_amt and same_type and same_meta
            if same_all:
                ignore = {"amount", "actionType", "seat", "street"}
                extra_diff = any(
                    (k not in ignore) and (ga.get(k) != sa.get(k))
                    for k in set(ga) | set(sa)
                )
                same_all = not extra_diff
            ops.append(
                {
                    "op": "equal" if same_all else "rewrite",
                    "gt": ga,
                    "sys": sa,
                    "gt_index": gi,
                    "sys_index": si,
                    "amount_diff": not same_amt,
                }
            )
            gi += 1
            si += 1
            continue
        # Should not happen often; advance cautiously
        if gi < len(g):
            ops.append(
                {
                    "op": "missing",
                    "gt": g[gi],
                    "sys": None,
                    "gt_index": gi,
                    "sys_index": None,
                }
            )
            gi += 1
        elif si < len(s):
            ops.append(
                {
                    "op": "extra",
                    "gt": None,
                    "sys": s[si],
                    "gt_index": None,
                    "sys_index": si,
                }
            )
            si += 1
    return ops


def get_actions(req: Optional[dict]) -> list:
    if not req:
        return []
    return list((req.get("gameInfo") or {}).get("actionSequence") or [])


def align_requests(gt: Optional[dict], sys: Optional[dict]) -> list[dict]:
    return align_actions(get_actions(gt), get_actions(sys))


def first_alignment_issue(gt: Optional[dict], sys: Optional[dict]) -> Optional[dict]:
    """First non-equal alignment op, shaped for evidence cards."""
    for op in align_requests(gt, sys):
        if op["op"] == "equal":
            continue
        g, s = op.get("gt"), op.get("sys")
        kind = op["op"]
        return {
            "kind": kind,  # missing | extra | rewrite
            "index": op.get("gt_index") if op.get("gt_index") is not None else op.get("sys_index"),
            "gt_index": op.get("gt_index"),
            "sys_index": op.get("sys_index"),
            "gt": g,
            "sys": s,
            "street": (g or s or {}).get("street") if isinstance(g or s, dict) else None,
            "seat": (g or s or {}).get("seat") if isinstance(g or s, dict) else None,
            "amount": (g or s or {}).get("amount") if isinstance(g or s, dict) else None,
        }
    return None


def summarize_alignment(gt: Optional[dict], sys: Optional[dict], limit: int = 12) -> list[str]:
    notes: list[str] = []
    ops = align_requests(gt, sys)
    missing = [o for o in ops if o["op"] == "missing"]
    extras = [o for o in ops if o["op"] == "extra"]
    rewrites = [o for o in ops if o["op"] == "rewrite"]

    # Group missing/extra by street
    def by_street(items: list[dict], side: str) -> dict[str, list]:
        out: dict[str, list] = {}
        for o in items:
            a = o.get("gt") if side == "gt" else o.get("sys")
            st = str((a or {}).get("street") or "?").upper()
            out.setdefault(st, []).append(a)
        return out

    miss_st = by_street(missing, "gt")
    for st, acts in miss_st.items():
        cn = STREET_CN.get(st, st)
        if len(acts) >= 2 and len({a.get("seat") for a in acts if a}) >= 2:
            # possible whole-street gap if sys has 0 on that street
            notes.append(
                f"{cn}街系统缺少 {len(acts)} 条行动："
                + "；".join(action_label(a) for a in acts[:4])
                + ("…" if len(acts) > 4 else "")
            )
        else:
            for a in acts:
                notes.append(f"{cn}街缺失：系统缺少 {action_label(a)}")

    extra_st = by_street(extras, "sys")
    for st, acts in extra_st.items():
        cn = STREET_CN.get(st, st)
        for a in acts[:5]:
            notes.append(f"{cn}街多余：系统多出 {action_label(a)}")
        if len(acts) > 5:
            notes.append(f"{cn}街另有 {len(acts)-5} 条系统多余行动")

    for o in rewrites:
        g, s = o["gt"], o["sys"]
        from compare_gto_requests import action_types_equivalent, amounts_equivalent

        cn = STREET_CN.get(str(g.get("street") or "").upper(), g.get("street"))
        type_diff = not action_types_equivalent(g.get("actionType"), s.get("actionType"))
        amt_diff = not amounts_equivalent(g.get("amount"), s.get("amount"))
        if type_diff and amt_diff:
            notes.append(
                f"{cn}街 {g.get('seat')} 行动类型与金额均不正确："
                f"{g.get('actionType')} {g.get('amount')}→{s.get('actionType')} {s.get('amount')}"
            )
        elif type_diff:
            notes.append(
                f"{cn}街 {g.get('seat')} 行动类型不正确：{g.get('actionType')}→{s.get('actionType')}"
            )
        elif amt_diff:
            notes.append(
                f"{cn}街 {g.get('seat')} 金额不正确：{g.get('amount')}→{s.get('amount')}"
            )
        else:
            notes.append(f"{cn}街 {g.get('seat')} 行动内容不正确")

    # Whole-street missing/extra (sys has zero actions on a street that GT has)
    g_by: dict[str, int] = {}
    s_by: dict[str, int] = {}
    for a in get_actions(gt):
        if isinstance(a, dict):
            g_by[str(a.get("street") or "").upper()] = g_by.get(str(a.get("street") or "").upper(), 0) + 1
    for a in get_actions(sys):
        if isinstance(a, dict):
            s_by[str(a.get("street") or "").upper()] = s_by.get(str(a.get("street") or "").upper(), 0) + 1
    for st in ("PREFLOP", "FLOP", "TURN", "RIVER"):
        gn, sn = g_by.get(st, 0), s_by.get(st, 0)
        cn = STREET_CN.get(st, st)
        if gn > 0 and sn == 0:
            msg = f"缺少整条{cn}街行动（真值 {gn} 条，系统 0 条）"
            if msg not in notes:
                notes.insert(0, msg)
        elif gn == 0 and sn > 0:
            msg = f"多出整条{cn}街行动（真值 0 条，系统 {sn} 条）"
            if msg not in notes:
                notes.insert(0, msg)

    return notes[:limit]


def alignment_to_diffs(gt: Optional[dict], sys: Optional[dict]) -> list[dict]:
    """Convert alignment ops to diff records (replaces index-based actionSequence diffs)."""
    diffs: list[dict] = []
    for op in align_requests(gt, sys):
        if op["op"] == "equal":
            continue
        if op["op"] == "missing":
            a = op["gt"]
            diffs.append(
                {
                    "path": f"gameInfo.actionSequence(missing:{a.get('seat')}@{a.get('street')})",
                    "type": "missing_right",
                    "left": a,
                    "right": None,
                    "category": "行动缺失",
                }
            )
        elif op["op"] == "extra":
            a = op["sys"]
            diffs.append(
                {
                    "path": f"gameInfo.actionSequence(extra:{a.get('seat')}@{a.get('street')})",
                    "type": "missing_left",
                    "left": None,
                    "right": a,
                    "category": "行动多余",
                }
            )
        elif op["op"] == "rewrite":
            from compare_gto_requests import action_types_equivalent, amounts_equivalent

            g, s = op["gt"], op["sys"]
            seat = g.get("seat")
            street = g.get("street")
            if not action_types_equivalent(g.get("actionType"), s.get("actionType")):
                diffs.append(
                    {
                        "path": f"gameInfo.actionSequence[{seat}@{street}].actionType",
                        "type": "value",
                        "left": g.get("actionType"),
                        "right": s.get("actionType"),
                        "category": "行动类型错误",
                    }
                )
            if not amounts_equivalent(g.get("amount"), s.get("amount")):
                diffs.append(
                    {
                        "path": f"gameInfo.actionSequence[{seat}@{street}].amount",
                        "type": "value",
                        "left": g.get("amount"),
                        "right": s.get("amount"),
                        "category": "行动金额错误",
                    }
                )
            # other field diffs
            for k in set(g) | set(s):
                if k in ("actionType", "amount", "seat", "street"):
                    continue
                if g.get(k) != s.get(k):
                    diffs.append(
                        {
                            "path": f"gameInfo.actionSequence[{seat}@{street}].{k}",
                            "type": "value",
                            "left": g.get(k),
                            "right": s.get(k),
                            "category": "行动序列差异",
                        }
                    )
    return diffs


def merge_diffs_with_alignment(gt: Optional[dict], sys: Optional[dict], diffs: list[dict]) -> list[dict]:
    """Drop index-based actionSequence diffs; inject alignment-based ones."""
    kept = [d for d in diffs if "actionsequence" not in d.get("path", "").lower()]
    return kept + alignment_to_diffs(gt, sys)
