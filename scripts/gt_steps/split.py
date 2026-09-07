"""从一手 gt_raw 拆出每一次 P0 行动前的 GTO 请求。"""

from __future__ import annotations

import copy
from typing import Any, Optional

STREET_BOARD_LEN = {
    "PREFLOP": 0,
    "FLOP": 3,
    "TURN": 4,
    "RIVER": 5,
}


def _p0_indexes(actions: list) -> list[int]:
    return [i for i, a in enumerate(actions) if isinstance(a, dict) and a.get("seat") == "P0"]


def truncate_before_p0_nth(req: dict, nth: int) -> tuple[dict, dict]:
    """裁到第 nth 次 P0 行动之前（nth 为 1-based）。

    保留 actionSequence[:p0_idx]，并按该次 P0 行动的 street 截 communityCards。
    """
    out = copy.deepcopy(req)
    gi = out.setdefault("gameInfo", {})
    actions = list(gi.get("actionSequence") or [])
    p0_idxs = _p0_indexes(actions)
    meta: dict[str, Any] = {
        "p0_action_count": len(p0_idxs),
        "nth": nth,
        "original_action_len": len(actions),
        "truncated_action_len": len(actions),
        "decision_street": None,
        "next_p0_action": None,
        "boundary_ok": True,
        "note": "",
    }
    if nth < 1 or nth > len(p0_idxs):
        meta["boundary_ok"] = False
        meta["note"] = f"P0#{nth} 不存在（共 {len(p0_idxs)} 次 P0）"
        return out, meta

    i = p0_idxs[nth - 1]
    next_action = actions[i]
    street = str(next_action.get("street") or "PREFLOP").upper()
    meta["decision_street"] = street
    meta["next_p0_action"] = next_action
    truncated = actions[:i]
    gi["actionSequence"] = truncated
    meta["truncated_action_len"] = len(truncated)
    meta["p0_seq_index"] = i

    board = list(gi.get("communityCards") or [])
    keep = STREET_BOARD_LEN.get(street, len(board))
    gi["communityCards"] = board[:keep]
    meta["community_cards_kept"] = keep
    meta["community_cards_original"] = len(board)
    return out, meta


def _action_label(a: Optional[dict]) -> str:
    if not isinstance(a, dict):
        return "—"
    t = str(a.get("type") or a.get("action") or a.get("actionType") or "?").upper()
    size = a.get("size")
    if size is None:
        size = a.get("amount")
    if size is None or size == "" or size == 0:
        return t
    return f"{t} {size}"


def split_gt_into_p0_steps(
    gt_raw: Optional[dict],
    *,
    hand_uid: str = "",
    hole_key: str = "",
    include_request: bool = True,
) -> list[dict[str, Any]]:
    """一手 → N 条「第 k 次 P0 前」快照。无 P0 时返回空列表。"""
    if not isinstance(gt_raw, dict) or "gameInfo" not in gt_raw:
        return []
    gi = gt_raw.get("gameInfo") or {}
    actions = list(gi.get("actionSequence") or [])
    p0_idxs = _p0_indexes(actions)
    steps: list[dict[str, Any]] = []
    for nth in range(1, len(p0_idxs) + 1):
        truncated, meta = truncate_before_p0_nth(gt_raw, nth)
        next_a = meta.get("next_p0_action") if isinstance(meta.get("next_p0_action"), dict) else {}
        step: dict[str, Any] = {
            "step_id": f"{hand_uid}#P0-{nth}" if hand_uid else f"P0-{nth}",
            "hand_uid": hand_uid,
            "hole_key": hole_key,
            "nth": nth,
            "p0_seq_index": meta.get("p0_seq_index"),
            "decision_street": meta.get("decision_street"),
            "truncated_action_len": meta.get("truncated_action_len"),
            "original_action_len": meta.get("original_action_len"),
            "p0_action_count": meta.get("p0_action_count"),
            "next_p0_action": next_a,
            "next_p0_label": _action_label(next_a),
            "community_cards": list((truncated.get("gameInfo") or {}).get("communityCards") or []),
            "boundary_ok": meta.get("boundary_ok", True),
            "note": meta.get("note") or "",
        }
        if include_request:
            step["request"] = truncated
        steps.append(step)
    return steps


def list_version_steps_brief(version_id: str) -> dict[str, Any]:
    """某正确值版本下全部决策点摘要（不含完整 request）。"""
    from gt_store import load_gt_version

    meta, hands = load_gt_version(version_id)

    def _sort_key(hid: str) -> int:
        try:
            return int(str(hid).split("_")[-1])
        except Exception:
            return 10**9

    steps_out: list[dict[str, Any]] = []
    hand_summaries: list[dict[str, Any]] = []
    for hid in sorted(hands.keys(), key=_sort_key):
        row = hands[hid] or {}
        gt = row.get("gt_raw") if isinstance(row.get("gt_raw"), dict) else None
        hole = str(row.get("hole_key") or "")
        steps = split_gt_into_p0_steps(gt, hand_uid=hid, hole_key=hole, include_request=False)
        hand_summaries.append(
            {
                "hand_uid": hid,
                "hole_key": hole,
                "has_gt": bool(gt),
                "p0_step_count": len(steps),
            }
        )
        steps_out.extend(steps)

    return {
        "meta": meta,
        "hand_count": len(hands),
        "with_gt_n": sum(1 for h in hand_summaries if h["has_gt"]),
        "step_count": len(steps_out),
        "hands": hand_summaries,
        "steps": steps_out,
    }


def get_step_detail(version_id: str, hand_uid: str, nth: int) -> dict[str, Any]:
    """单条决策点（含完整裁剪后 request）。"""
    from gt_store import get_gt_hand

    hand = get_gt_hand(version_id, hand_uid)
    gt = hand.get("gt_raw") if isinstance(hand.get("gt_raw"), dict) else None
    hole = str(hand.get("hole_key") or "")
    steps = split_gt_into_p0_steps(gt, hand_uid=hand_uid, hole_key=hole, include_request=True)
    if nth < 1 or nth > len(steps):
        raise KeyError(f"手牌 {hand_uid} 无 P0#{nth}（共 {len(steps)} 次）")
    return {
        "version_id": version_id,
        "hand_uid": hand_uid,
        "hole_key": hole,
        "p0_step_count": len(steps),
        "step": steps[nth - 1],
        "siblings": [
            {
                "nth": s["nth"],
                "decision_street": s["decision_street"],
                "next_p0_label": s["next_p0_label"],
                "truncated_action_len": s["truncated_action_len"],
            }
            for s in steps
        ],
    }
