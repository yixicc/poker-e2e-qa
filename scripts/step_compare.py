"""按决策点对比：正确值 P0#k 前请求 vs Chess API fusionCorrectedData。

独立于现有「对比报告」（按手最后一次 P0）。
"""

from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any, Optional

from compare_gto_requests import strip_meta
from evidence_report import build_issue_blocks, chess_norm_for_compare
from gt_steps.split import split_gt_into_p0_steps
from gt_store import get_current_gt_version_id, load_gt_version
from module_pipeline import (
    analyze_hand_trace,
    extract_business_request,
    extract_fusion_corrected_data,
    spans_named,
)
from step_run_store import validate_step_run_id
from trace_client import TraceClient, fetch_hand_spans
from trace_envs import get_trace_env, normalize_trace_env, resolve_api_base
from trace_query_config import compact_hole_id, resolve_trace_query


def _action_seq_len(req: Optional[dict]) -> int:
    if not isinstance(req, dict):
        return -1
    gi = req.get("gameInfo") if isinstance(req.get("gameInfo"), dict) else {}
    return len(list(gi.get("actionSequence") or []))


def _fcd_seq_len_at(spans: list[dict], hero_index: int) -> int:
    chess = spans_named(spans, service="chess-game-api", name="gto-validation")
    if hero_index < 0 or hero_index >= len(chess):
        return -1
    br = extract_business_request(chess[hero_index])
    fcd = extract_fusion_corrected_data(br)
    if isinstance(fcd, dict) and "gameInfo" not in fcd:
        if "actionSequence" in fcd:
            fcd = {"gameInfo": fcd}
    return _action_seq_len(fcd if isinstance(fcd, dict) else None)


def pick_hero_ordinal_for_step(
    spans: list[dict],
    *,
    gt_norm: dict,
    nth: int,
    p0_count: int,
) -> tuple[Optional[int], str]:
    """Return (1-based hero_ordinal, align_mode)."""
    heroes = spans_named(
        spans,
        service="texas-holdem-signal-engine",
        name="hero_action",
    )
    if not heroes:
        return None, "no_hero"

    if len(heroes) == p0_count and 1 <= nth <= len(heroes):
        return nth, "p0_index"

    target = _action_seq_len(gt_norm)
    best: Optional[tuple[int, int]] = None  # (dist, ordinal)
    for i in range(len(heroes)):
        seq_len = _fcd_seq_len_at(spans, i)
        if seq_len < 0:
            continue
        dist = abs(seq_len - target)
        if best is None or dist < best[0]:
            best = (dist, i + 1)
    if best is not None and best[0] <= 2:
        return best[1], "action_len"

    if 1 <= nth <= len(heroes):
        return nth, "p0_index_fallback"
    return None, "unaligned"


def _signal_from_chain(chain: Optional[dict]) -> dict[str, Any]:
    """Pull signal-engine hero_action business.request from module chain (diagnostic only)."""
    layers = (chain or {}).get("layers") or []
    signal_layer = None
    for layer in layers:
        if isinstance(layer, dict) and layer.get("id") == "signal":
            signal_layer = layer
            break
    if not isinstance(signal_layer, dict):
        return {
            "signal_present": False,
            "signal_request": None,
            "signal_meta": {},
        }
    br = signal_layer.get("business_request")
    present = br is not None and br != ""
    msg_key = None
    if isinstance(br, dict) and br.get("msg_key") is not None:
        msg_key = br.get("msg_key")
    meta = {
        "timestamp": signal_layer.get("timestamp"),
        "span_id": signal_layer.get("span_id"),
        "span_name": signal_layer.get("span_name"),
        "msg_key": msg_key,
        "link_ok": bool(signal_layer.get("link_ok")),
        "status": signal_layer.get("status"),
    }
    return {
        "signal_present": bool(present),
        "signal_request": br if present else None,
        "signal_meta": meta,
    }


def compare_one_step(
    *,
    gt_request: dict,
    spans: list[dict],
    nth: int,
    p0_count: int,
    fetch_meta: Optional[dict] = None,
) -> dict[str, Any]:
    gt_norm = strip_meta(copy.deepcopy(gt_request))
    ordinal, align_mode = pick_hero_ordinal_for_step(
        spans, gt_norm=gt_norm, nth=nth, p0_count=p0_count
    )
    chain = analyze_hand_trace(
        spans,
        gt_norm=gt_norm,
        fetch_meta=fetch_meta,
        hero_ordinal=ordinal,
    )
    chess_norm = chess_norm_for_compare(chain, gt_norm=gt_norm)
    issues = build_issue_blocks(gt_norm, chess_norm) if chess_norm is not None else []
    if chess_norm is None:
        chess_exact = None
        # 总览用徽标表达无值；first_issue 留空避免重复文案
        first_issue = ""
        diff_count = None
    else:
        diff_count = len(issues)
        chess_exact = diff_count == 0
        first_issue = ""
        if issues:
            b0 = issues[0]
            first_issue = str(b0.get("title") or b0.get("summary") or b0.get("path") or "有差异")

    signal = _signal_from_chain(chain)

    return {
        "gt_norm": gt_norm,
        "chess_norm": chess_norm,
        "chess_exact": chess_exact,
        "diff_count": diff_count,
        "first_issue": first_issue,
        "issues": issues[:40],
        "align_mode": align_mode,
        "hero_ordinal": ordinal,
        "hero_index": None if ordinal is None else ordinal - 1,
        "hero_count": int(chain.get("hero_count") or 0),
        "trace_note": chain.get("note") or "",
        "anchor_mode": chain.get("anchor_mode") or "",
        "signal_present": signal["signal_present"],
        "signal_request": signal["signal_request"],
        "signal_meta": signal["signal_meta"],
    }


def _parse_hand_uids(raw: Any) -> Optional[list[str]]:
    if raw is None:
        return None
    if isinstance(raw, list):
        out = [str(x).strip() for x in raw if str(x).strip()]
        return out or None
    text = str(raw).strip()
    if not text:
        return None
    parts = []
    for chunk in text.replace(",", " ").replace(";", " ").split():
        if chunk.strip():
            parts.append(chunk.strip())
    return parts or None


def run_step_compare(
    *,
    run_id: str,
    gt_version: str = "",
    trace_query: Optional[dict] = None,
    hand_uids: Any = None,
    note: str = "",
    tags: Optional[list[str]] = None,
    skip_trace: bool = False,
    overwrite: bool = False,
) -> dict[str, Any]:
    from step_run_store import (
        assert_step_run_writable,
        save_step_run,
        validate_step_run_id,
    )
    from step_compare_pages import render_step_run_index_html

    rid = validate_step_run_id(run_id)
    # 存在则必须显式覆盖；覆盖时 save_step_run 会整目录 wipe，避免旧 spans 残留
    assert_step_run_writable(rid, overwrite=overwrite)

    vid = str(gt_version or "").strip() or (get_current_gt_version_id() or "")
    if not vid:
        raise ValueError("未指定正确值版本，且没有 current GT")
    gt_meta, hands = load_gt_version(vid)

    wanted = _parse_hand_uids(hand_uids)
    hand_items = []
    for hid, row in hands.items():
        if wanted and hid not in wanted:
            continue
        gt = row.get("gt_raw") if isinstance(row.get("gt_raw"), dict) else None
        if not gt:
            continue
        hand_items.append((hid, row, gt))

    def _sort_key(item: tuple) -> int:
        try:
            return int(str(item[0]).split("_")[-1])
        except Exception:
            return 10**9

    hand_items.sort(key=_sort_key)

    cfg = dict(trace_query or {})
    if not str(cfg.get("traceEnv") or "").strip():
        cfg["traceEnv"] = "uat"
    try:
        env_id = normalize_trace_env(str(cfg.get("traceEnv") or "uat"))
    except KeyError:
        env_id = "uat"
    cfg["traceEnv"] = env_id

    client = None
    if not skip_trace:
        missing = [
            k
            for k, v in (
                ("openId", cfg.get("openId")),
                ("startTime", cfg.get("startTime")),
                ("endTime", cfg.get("endTime")),
            )
            if not str(v or "").strip()
        ]
        if missing:
            raise ValueError("Trace 条件未齐，缺少: " + ", ".join(missing))
        client = TraceClient(
            env_id=env_id,
            base_url=resolve_api_base(env_id, override=str(cfg.get("api") or "").strip()),
        )

    t0 = time.time()
    steps_out: list[dict[str, Any]] = []
    hand_spans_out: dict[str, Any] = {}
    stats = {
        "hand_n": len(hand_items),
        "step_n": 0,
        "exact_n": 0,
        "diff_n": 0,
        "no_chess_n": 0,
        "comparable_n": 0,
        "signal_present_n": 0,
        "trace_fetched_n": 0,
        "trace_hit_n": 0,
        "trace_error_n": 0,
        "hands_with_diff_n": 0,
    }

    for hid, row, gt in hand_items:
        hole = str(row.get("hole_key") or "")
        step_defs = split_gt_into_p0_steps(
            gt, hand_uid=hid, hole_key=hole, include_request=True
        )
        if not step_defs:
            continue

        spans: list[dict] = []
        fetch_meta: dict[str, Any] = {"skipped": bool(skip_trace)}
        if client is not None:
            stats["trace_fetched_n"] += 1
            q = resolve_trace_query(
                cfg,
                hand_uid=hid,
                hole_key=hole,
                data_open_id="",
            )
            q["trace_env"] = env_id
            try:
                env = get_trace_env(env_id)
                q["env_label"] = env.get("env_label") or env_id
            except Exception:
                q["env_label"] = env_id
            try:
                fetched = fetch_hand_spans(
                    client,
                    open_id=q.get("open_id") or str(cfg.get("openId") or ""),
                    hole_key=q.get("cards") or compact_hole_id(hole) or hole,
                    fixed_start=q.get("start_time") or str(cfg.get("startTime") or ""),
                    fixed_end=q.get("end_time") or str(cfg.get("endTime") or ""),
                    fallback_open_id=str(cfg.get("openId") or ""),
                )
                spans = list(fetched.get("spans") or [])
                fetch_meta = {
                    "query": q,
                    "open_id": fetched.get("open_id"),
                    "hole_cards_used": fetched.get("hole_cards_used"),
                    "start_time": fetched.get("start_time"),
                    "end_time": fetched.get("end_time"),
                    "span_n": len(spans),
                }
                hand_spans_out[hid] = {"spans": spans, "fetch": fetch_meta}
                if spans:
                    stats["trace_hit_n"] += 1
            except Exception as e:
                stats["trace_error_n"] += 1
                fetch_meta = {"error": str(e), "query": q}
                hand_spans_out[hid] = {"spans": [], "fetch": fetch_meta}

        hand_has_diff = False
        p0_count = len(step_defs)
        for sd in step_defs:
            nth = int(sd.get("nth") or 0)
            req = sd.get("request")
            if not isinstance(req, dict):
                continue
            cmp = compare_one_step(
                gt_request=req,
                spans=spans,
                nth=nth,
                p0_count=p0_count,
                fetch_meta=fetch_meta,
            )
            step_id = str(sd.get("step_id") or f"{hid}#P0-{nth}")
            row_out = {
                "step_id": step_id,
                "hand_uid": hid,
                "hole_key": hole,
                "nth": nth,
                "p0_count": p0_count,
                "decision_street": sd.get("decision_street"),
                "next_p0_label": sd.get("next_p0_label"),
                "truncated_action_len": sd.get("truncated_action_len"),
                "gt_norm": cmp["gt_norm"],
                "chess_norm": cmp["chess_norm"],
                "chess_exact": cmp["chess_exact"],
                "diff_count": cmp["diff_count"],
                "first_issue": cmp["first_issue"],
                "issues": cmp["issues"],
                "align_mode": cmp["align_mode"],
                "hero_ordinal": cmp["hero_ordinal"],
                "hero_index": cmp["hero_index"],
                "hero_count": cmp["hero_count"],
                "trace_note": cmp["trace_note"],
                "anchor_mode": cmp["anchor_mode"],
                "signal_present": cmp["signal_present"],
                "signal_request": cmp["signal_request"],
                "signal_meta": cmp["signal_meta"],
            }
            steps_out.append(row_out)
            stats["step_n"] += 1
            if cmp.get("signal_present"):
                stats["signal_present_n"] = int(stats.get("signal_present_n") or 0) + 1
            if cmp["chess_exact"] is True:
                stats["exact_n"] += 1
                stats["comparable_n"] += 1
            elif cmp["chess_exact"] is False:
                stats["diff_n"] += 1
                stats["comparable_n"] += 1
                hand_has_diff = True
            else:
                stats["no_chess_n"] += 1
        if hand_has_diff:
            stats["hands_with_diff_n"] += 1

    comparable = int(stats["comparable_n"] or 0)
    exact = int(stats["exact_n"] or 0)
    stats["exact_pct"] = round(100.0 * exact / comparable, 1) if comparable else None
    stats["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    stats["elapsed_s"] = round(time.time() - t0, 2)

    summary = {
        "run_id": rid,
        "gt_version_id": vid,
        "metrics": stats,
        "steps": [
            {
                "step_id": s["step_id"],
                "hand_uid": s["hand_uid"],
                "hole_key": s["hole_key"],
                "nth": s["nth"],
                "decision_street": s["decision_street"],
                "next_p0_label": s["next_p0_label"],
                "truncated_action_len": s["truncated_action_len"],
                "chess_exact": s["chess_exact"],
                "diff_count": s["diff_count"],
                "first_issue": s["first_issue"],
                "align_mode": s["align_mode"],
                "hero_ordinal": s["hero_ordinal"],
                "signal_present": bool(s.get("signal_present")),
            }
            for s in steps_out
        ],
    }

    meta = {
        "id": rid,
        "gt_version_id": vid,
        "gt_note": gt_meta.get("note") or "",
        "note": str(note or "").strip(),
        "tags": [str(t).strip() for t in (tags or []) if str(t).strip()],
        "hand_n": stats["hand_n"],
        "step_n": stats["step_n"],
        "skip_trace": bool(skip_trace),
        "batch_hands": wanted,
        "readonly": True,
        "isolation": "per_run_dir",
    }

    index_html = render_step_run_index_html(run_id=rid, meta=meta, summary=summary)
    saved = save_step_run(
        rid,
        meta=meta,
        summary=summary,
        index_html=index_html,
        steps=steps_out,
        hand_spans=hand_spans_out if hand_spans_out else None,
        trace_query=cfg,
        overwrite=overwrite,
    )
    return {"ok": True, "meta": saved, "metrics": stats, "run_id": rid}
