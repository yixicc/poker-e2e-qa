#!/usr/bin/env python3
"""只读数据工具。MCP 服务和聊天都走这里，不提供改数、重跑、写配置。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
STATION = ROOT / "e2e-quality-station"
for p in (SCRIPTS, STATION):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from gt_store import (  # noqa: E402
    get_current_gt_version_id,
    get_gt_hand,
    list_gt_hands_brief,
    list_gt_versions,
)
from hand_bugs import load_hand_bugs  # noqa: E402
from run_store import list_runs, load_run_hands, load_run_meta, load_run_summary, run_dir  # noqa: E402

MAX_TEXT = 14000

_METRIC_KEYS = (
    "generated_at",
    "comparable_n",
    "old_comparable_n",
    "new_comparable_n",
    "chess_comparable_n",
    "chess_missing_n",
    "old_exact_n",
    "new_exact_n",
    "chess_exact_n",
    "old_accuracy_pct",
    "new_accuracy_pct",
    "chess_accuracy_pct",
    "fixed_n",
    "regressed_n",
    "old_only_n",
    "new_only_n",
    "old_category_counts",
    "new_category_counts",
    "chess_category_counts",
)

_HAND_KEYS = (
    "hand_uid",
    "hole_key",
    "old_exact",
    "new_exact",
    "change",
    "old_diff_count",
    "new_diff_count",
    "old_categories",
    "new_categories",
)


def _obj_schema(props: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "type": "object",
        "properties": props,
        "additionalProperties": False,
    }
    if required:
        schema["required"] = required
    return schema


def _str_prop(desc: str) -> dict[str, str]:
    return {"type": "string", "description": desc}


def _int_prop(desc: str) -> dict[str, Any]:
    return {"type": "integer", "description": desc}


def _bool_prop(desc: str) -> dict[str, str]:
    return {"type": "boolean", "description": desc}


TOOL_SPECS: list[dict[str, Any]] = [
    {
        "name": "list_compare_runs",
        "description": "列出本地 GTO 对比跑批。用户问最近报告、某次跑批、有哪些 run 时先调这个。",
        "inputSchema": _obj_schema({}),
    },
    {
        "name": "get_run_overview",
        "description": "读取一次对比跑批的条件、正确值版本和准确率、问题分类计数。不含逐手明细。",
        "inputSchema": _obj_schema(
            {"run_id": _str_prop("跑批 id，例如 20260812-rerun")},
            ["run_id"],
        ),
    },
    {
        "name": "list_run_hands",
        "description": "列出一次跑批里的手牌对照摘要（手牌号、底牌、新旧是否一致、问题类）。",
        "inputSchema": _obj_schema(
            {
                "run_id": _str_prop("跑批 id"),
                "only_new_mismatch": _bool_prop("为 true 时只留新版与正确值不一致的手"),
                "limit": _int_prop("最多返回多少手，默认 40，最大 80"),
            },
            ["run_id"],
        ),
    },
    {
        "name": "list_ground_truth_versions",
        "description": "列出正确值版本，并标出当前版本。",
        "inputSchema": _obj_schema({}),
    },
    {
        "name": "list_ground_truth_hands",
        "description": "列出某个正确值版本里的手牌号和底牌，不含完整报文。",
        "inputSchema": _obj_schema(
            {
                "version_id": _str_prop("正确值版本 id。留空则用当前版本"),
                "limit": _int_prop("最多返回多少手，默认 40，最大 80"),
            }
        ),
    },
    {
        "name": "get_ground_truth_hand",
        "description": "读取一手正确值的结构摘要。只有用户明确要报文时才把 include_request 设为 true。",
        "inputSchema": _obj_schema(
            {
                "hand_uid": _str_prop("手牌号，例如 HAND_001"),
                "version_id": _str_prop("正确值版本 id。留空则用当前版本"),
                "include_request": _bool_prop("是否附带截断后的 gt_raw 报文"),
            },
            ["hand_uid"],
        ),
    },
    {
        "name": "list_hand_bug_notes",
        "description": "读取手牌 Bug 状态、负责人和备注。",
        "inputSchema": _obj_schema(
            {"status": _str_prop("按状态过滤：待确认、处理中、已修复、不修、关闭。留空返回全部已标记手牌")}
        ),
    },
    {
        "name": "query_trace",
        "description": "查询 data-platform 的 Trace。必须给出开始和结束时间。返回截断后的事件摘要，不含完整报文。",
        "inputSchema": _obj_schema(
            {
                "start_time": _str_prop("开始时间，如 2026-08-12 14:00:00"),
                "end_time": _str_prop("结束时间，如 2026-08-12 15:30:00"),
                "open_id": _str_prop("OpenID，可空"),
                "hole_cards": _str_prop("底牌，如 QC5H 或 QC,5H，可空"),
                "trace_env": _str_prop("环境 id，默认 uat"),
            },
            ["start_time", "end_time"],
        ),
    },
    {
        "name": "discover_traces",
        "description": "按时间窗做 Trace 组合发现，返回截断后的发现结果。",
        "inputSchema": _obj_schema(
            {
                "start_time": _str_prop("开始时间"),
                "end_time": _str_prop("结束时间"),
                "trace_env": _str_prop("环境 id，默认 uat"),
            },
            ["start_time", "end_time"],
        ),
    },
    {
        "name": "list_fusion_hands",
        "description": "按 sessionId 列出 fusion 场次里的手牌（手牌号、状态、视频、错误信息）。",
        "inputSchema": _obj_schema(
            {"session_id": _str_prop("fusion sessionId")},
            ["session_id"],
        ),
    },
    {
        "name": "get_fusion_hand",
        "description": "读取 fusion 里某一手的结果摘要。正文过长时会截断。",
        "inputSchema": _obj_schema(
            {
                "session_id": _str_prop("fusion sessionId"),
                "hand_id": _str_prop("fusion handId"),
            },
            ["session_id", "hand_id"],
        ),
    },
]


def _need(args: dict[str, Any], key: str) -> str:
    val = str(args.get(key) or "").strip()
    if not val:
        raise ValueError(f"缺少 {key}")
    return val


def _limit(args: dict[str, Any], default: int = 40) -> int:
    raw = args.get("limit", default)
    try:
        n = int(raw)
    except (TypeError, ValueError):
        n = default
    return max(1, min(n, 80))


def _clip_text(text: str, limit: int = MAX_TEXT) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "…(已截断)"


def dumps_tool(obj: Any) -> str:
    return _clip_text(json.dumps(obj, ensure_ascii=False, default=str))


def _preview(value: Any, limit: int = 500) -> str:
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False, default=str)
    return _clip_text(text, limit)


def _slim_trace_row(row: Any) -> Any:
    if not isinstance(row, dict):
        return _preview(row, 300)
    heavy = {
        "business",
        "request",
        "response",
        "payload",
        "attributes",
        "requestbody",
        "responsebody",
    }
    out: dict[str, Any] = {}
    for key, val in row.items():
        if str(key).lower() in heavy or (
            isinstance(val, (dict, list)) and len(json.dumps(val, ensure_ascii=False, default=str)) > 400
        ):
            out[key] = _preview(val, 240)
        else:
            out[key] = val
    return out


def _sketch_request(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    game = raw.get("gameInfo") if isinstance(raw.get("gameInfo"), dict) else {}
    actions = game.get("actionSequence")
    if not isinstance(actions, list):
        actions = raw.get("actionSequence") if isinstance(raw.get("actionSequence"), list) else []
    result = raw.get("result") if isinstance(raw.get("result"), dict) else {}
    players = game.get("players") if isinstance(game.get("players"), list) else raw.get("players")
    return {
        "top_keys": list(raw.keys())[:24],
        "action_n": len(actions),
        "player_n": len(players) if isinstance(players, list) else None,
        "total_pot": result.get("total_pot"),
        "board": game.get("board") or game.get("communityCards") or raw.get("board"),
    }


def list_compare_runs(_args: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for meta in list_runs():
        rows.append(
            {
                "id": meta.get("id"),
                "tags": meta.get("tags") or [],
                "note": meta.get("note") or "",
                "created_at": meta.get("created_at"),
                "updated_at": meta.get("updated_at"),
                "gt_version_id": meta.get("gt_version_id"),
                "readonly": bool(meta.get("readonly")),
                "has_index": bool(meta.get("has_index")),
            }
        )
    return {"n": len(rows), "runs": rows}


def _require_run(run_id: str) -> str:
    path = run_dir(run_id)
    if not path.is_dir():
        raise FileNotFoundError(f"跑批不存在: {run_id}")
    return path.name


def get_run_overview(args: dict[str, Any]) -> dict[str, Any]:
    run_id = _require_run(_need(args, "run_id"))
    meta = load_run_meta(run_id)
    summary = load_run_summary(run_id)
    metrics = {k: summary.get(k) for k in _METRIC_KEYS if k in summary}
    hands = summary.get("hands") if isinstance(summary.get("hands"), list) else load_run_hands(run_id)
    return {
        "id": meta.get("id") or run_id,
        "tags": meta.get("tags") or [],
        "note": meta.get("note") or "",
        "created_at": meta.get("created_at"),
        "gt_version_id": meta.get("gt_version_id"),
        "trace_query": meta.get("trace_query") or {},
        "metrics": metrics or meta.get("metrics") or {},
        "hand_n": len(hands),
    }


def list_run_hands_tool(args: dict[str, Any]) -> dict[str, Any]:
    run_id = _require_run(_need(args, "run_id"))
    only = bool(args.get("only_new_mismatch"))
    limit = _limit(args)
    rows = []
    for hand in load_run_hands(run_id):
        if only and hand.get("new_exact") is not False:
            continue
        rows.append({k: hand.get(k) for k in _HAND_KEYS})
    total = len(rows)
    return {"run_id": run_id, "n": total, "returned": min(total, limit), "hands": rows[:limit]}


def list_ground_truth_versions(_args: dict[str, Any]) -> dict[str, Any]:
    versions = []
    for meta in list_gt_versions():
        versions.append(
            {
                "id": meta.get("id"),
                "is_current": bool(meta.get("is_current")),
                "hand_count": meta.get("hand_count"),
                "note": meta.get("note") or "",
                "tags": meta.get("tags") or [],
                "created_at": meta.get("created_at"),
            }
        )
    return {"current": get_current_gt_version_id(), "n": len(versions), "versions": versions}


def list_ground_truth_hands(args: dict[str, Any]) -> dict[str, Any]:
    version_id = str(args.get("version_id") or "").strip() or None
    vid = version_id or get_current_gt_version_id()
    if not vid:
        raise FileNotFoundError("没有当前正确值版本")
    limit = _limit(args)
    hands = list_gt_hands_brief(vid)
    return {
        "version_id": vid,
        "n": len(hands),
        "returned": min(len(hands), limit),
        "hands": hands[:limit],
    }


def get_ground_truth_hand_tool(args: dict[str, Any]) -> dict[str, Any]:
    hand_uid = _need(args, "hand_uid")
    version_id = str(args.get("version_id") or "").strip()
    vid = version_id or get_current_gt_version_id()
    if not vid:
        raise FileNotFoundError("没有当前正确值版本")
    row = get_gt_hand(vid, hand_uid)
    gt = row.get("gt_raw")
    out: dict[str, Any] = {
        "version_id": vid,
        "hand_uid": hand_uid,
        "hole_key": row.get("hole_key") or "",
        "gt": _sketch_request(gt),
        "has_old_request": isinstance(row.get("old_req_raw"), dict),
    }
    if args.get("include_request"):
        out["gt_raw"] = _preview(gt, 8000)
    return out


def list_hand_bug_notes(args: dict[str, Any]) -> dict[str, Any]:
    status = str(args.get("status") or "").strip()
    bugs = load_hand_bugs()
    rows = []
    for hid, meta in bugs.items():
        if status and meta.get("status") != status:
            continue
        rows.append({"hand_uid": hid, **meta})
    return {"n": len(rows), "hands": rows}


def query_trace(args: dict[str, Any]) -> dict[str, Any]:
    from trace_client import TraceClient

    start = _need(args, "start_time")
    end = _need(args, "end_time")
    env = str(args.get("trace_env") or "").strip() or "uat"
    client = TraceClient(env)
    rows = client.trace_query(
        open_id=str(args.get("open_id") or ""),
        hole_cards=str(args.get("hole_cards") or ""),
        start_time=start,
        end_time=end,
    )
    slim = [_slim_trace_row(r) for r in rows[:20]]
    return {
        "trace_env": env,
        "n": len(rows),
        "returned": len(slim),
        "events": slim,
    }


def discover_traces(args: dict[str, Any]) -> dict[str, Any]:
    from trace_client import TraceClient

    start = _need(args, "start_time")
    end = _need(args, "end_time")
    env = str(args.get("trace_env") or "").strip() or "uat"
    client = TraceClient(env)
    rows = client.trace_discover(start_time=start, end_time=end)
    slim = [_slim_trace_row(r) for r in rows[:20]]
    return {
        "trace_env": env,
        "n": len(rows),
        "returned": len(slim),
        "rows": slim,
    }


def list_fusion_hands(args: dict[str, Any]) -> dict[str, Any]:
    from e2e_fusion import list_session_hands

    session_id = _need(args, "session_id")
    hands = list_session_hands(session_id)
    return {"session_id": session_id, "n": len(hands), "hands": hands[:80]}


def get_fusion_hand(args: dict[str, Any]) -> dict[str, Any]:
    from e2e_fusion import fetch_hand_result

    session_id = _need(args, "session_id")
    hand_id = _need(args, "hand_id")
    body = fetch_hand_result(session_id, hand_id)
    return {
        "session_id": session_id,
        "hand_id": hand_id,
        "found": body is not None,
        "result": _preview(body, 8000) if body is not None else None,
    }


HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "list_compare_runs": list_compare_runs,
    "get_run_overview": get_run_overview,
    "list_run_hands": list_run_hands_tool,
    "list_ground_truth_versions": list_ground_truth_versions,
    "list_ground_truth_hands": list_ground_truth_hands,
    "get_ground_truth_hand": get_ground_truth_hand_tool,
    "list_hand_bug_notes": list_hand_bug_notes,
    "query_trace": query_trace,
    "discover_traces": discover_traces,
    "list_fusion_hands": list_fusion_hands,
    "get_fusion_hand": get_fusion_hand,
}


def call_tool(name: str, arguments: dict[str, Any] | None) -> tuple[str, bool]:
    fn = HANDLERS.get(name)
    if fn is None:
        return dumps_tool({"ok": False, "error": f"未知工具 {name}"}), True
    try:
        payload = fn(arguments or {})
    except Exception as e:
        return dumps_tool({"ok": False, "error": f"{type(e).__name__}: {e}"}), True
    return dumps_tool({"ok": True, **payload} if isinstance(payload, dict) else {"ok": True, "result": payload}), False
