#!/usr/bin/env python3
"""Screenshot indexing + problem-frame selection + evidence-card HTML helpers."""

from __future__ import annotations

import html
import json
import re
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional


from action_align import (
    action_label as align_action_label,
    align_requests,
    first_alignment_issue,
    summarize_alignment,
)
from cross_module import (
    build_cross_module_rows,
    extract_signal_field,
    layer_business_request,
    layer_chess_display_request,
    layer_chess_payload,
    module_anchor_metas,
    seat_street_nth_from_seq,
)

SHOT_PAT = re.compile(r"^(.+?)_([0-9a-fA-F]+)_(\d+)\.(jpg|jpeg|png)$", re.I)
ORIG_SHOT_PAT = re.compile(r"^([0-9a-fA-F]+)_(\d+)\.(jpg|jpeg|png)$", re.I)
STREET_CN = {"PREFLOP": "翻前", "FLOP": "翻牌", "TURN": "转牌", "RIVER": "河牌"}


def esc(s: Any) -> str:
    return html.escape("" if s is None else str(s))


def hole_compact(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, list):
        cards = value
    else:
        text = str(value).strip()
        try:
            cards = json.loads(text.replace("'", '"'))
        except Exception:
            return re.sub(r"[^A-Za-z0-9]", "", text) or None
    if not isinstance(cards, list):
        return None
    return "".join(str(c) for c in cards)


def index_screenshots(shots_dir: Path) -> dict[str, dict[str, list[tuple[int, Path]]]]:
    """hole_compact -> user_token -> sorted [(timestamp, path), ...]

    Expects renamed names: {hole}_{token}_{ts}.ext
    """
    index: dict[str, dict[str, list[tuple[int, Path]]]] = defaultdict(lambda: defaultdict(list))
    if not shots_dir.exists():
        return {}
    for f in shots_dir.iterdir():
        if not f.is_file():
            continue
        m = SHOT_PAT.match(f.name)
        if not m:
            continue
        hole, token, ts = m.group(1), m.group(2), int(m.group(3))
        index[hole][token].append((ts, f))
    for hole in index:
        for token in index[hole]:
            index[hole][token].sort(key=lambda x: x[0])
    return index


def index_original_shots(orig_dir: Path) -> dict[str, list[tuple[int, Path]]]:
    """user_token -> sorted [(timestamp, path), ...] from original {token}_{ts}.ext names."""
    index: dict[str, list[tuple[int, Path]]] = defaultdict(list)
    if not orig_dir or not Path(orig_dir).exists():
        return {}
    for f in Path(orig_dir).iterdir():
        if not f.is_file():
            continue
        m = ORIG_SHOT_PAT.match(f.name)
        if not m:
            continue
        token, ts = m.group(1), int(m.group(2))
        index[token].append((ts, f))
    for token in index:
        index[token].sort(key=lambda x: x[0])
    return index


def renamed_to_original_name(name: str) -> Optional[str]:
    """手牌_token_ts.ext -> token_ts.ext"""
    m = SHOT_PAT.match(name)
    if not m:
        return None
    return f"{m.group(2)}_{m.group(3)}.{m.group(4)}"


def resolve_shot_path(path: Path, orig_dir: Optional[Path] = None) -> Path:
    """Prefer original image; fall back to renamed path."""
    if not path:
        return path
    if orig_dir and Path(orig_dir).exists():
        orig_name = renamed_to_original_name(path.name)
        if orig_name:
            cand = Path(orig_dir) / orig_name
            if cand.exists():
                return cand
        # already original-style name
        m = ORIG_SHOT_PAT.match(path.name)
        if m:
            cand = Path(orig_dir) / path.name
            if cand.exists():
                return cand
    return path


def wepoker_ts(hand_id: Optional[str]) -> Optional[int]:
    if not hand_id:
        return None
    m = re.search(r"WePoker\.(\d+)", str(hand_id))
    return int(m.group(1)) if m else None


def event_ts(req: Optional[dict]) -> Optional[int]:
    if not req:
        return None
    gi = req.get("gameInfo") or {}
    eid = gi.get("eventId") or ""
    # ...HeroDoingEvent:32:1783954851516
    m = re.search(r":(\d+)$", str(eid))
    if m:
        return int(m.group(1))
    return wepoker_ts(gi.get("handId"))


def first_action_mismatch(gt: Optional[dict], sys: Optional[dict]) -> Optional[dict]:
    """Compatibility wrapper: alignment-aware first issue."""
    return first_alignment_issue(gt, sys)


def case_title(friendly: list[str], mismatch: Optional[dict]) -> str:
    if mismatch:
        kind = mismatch.get("kind")
        g, s = mismatch.get("gt"), mismatch.get("sys")
        if kind == "missing" and isinstance(g, dict):
            return f"行动缺失：系统缺少 {g.get('seat')} {g.get('actionType')}（{g.get('street')}）"
        if kind == "extra" and isinstance(s, dict):
            return f"行动多余：系统多出 {s.get('seat')} {s.get('actionType')}（{s.get('street')}）"
        if kind == "rewrite" and isinstance(g, dict) and isinstance(s, dict):
            from compare_gto_requests import action_types_equivalent, amounts_equivalent

            if not action_types_equivalent(g.get("actionType"), s.get("actionType")):
                return f"行动数据错误：{g.get('seat')} 应为 {g.get('actionType')}，系统写成 {s.get('actionType')}"
            if not amounts_equivalent(g.get("amount"), s.get("amount")):
                return f"行动金额错误：{g.get('seat')} amount {g.get('amount')}→{s.get('amount')}"
            return f"行动改写：{g.get('seat')} @ {g.get('street')}"
        # legacy fallback
        if g and not s:
            return f"行动缺失：系统缺少 {action_label(g)}"
        if s and not g:
            return f"行动多余：系统多出 {action_label(s)}"
        if isinstance(g, dict) and isinstance(s, dict) and g.get("seat") == s.get("seat"):
            return f"行动数据错误：{g.get('seat')} 应为 {g.get('actionType')}，系统写成 {s.get('actionType')}"
    if friendly:
        return friendly[0][:80]
    return "与真值存在差异"


def action_label(a: Any) -> str:
    return align_action_label(a)

def pick_problem_frame(
    index: dict,
    hole_key_json: str,
    user_token: Optional[str],
    gt: Optional[dict],
    sys: Optional[dict],
    orig_index: Optional[dict] = None,
    orig_dir: Optional[Path] = None,
    neighbor_radius: int = 400,
) -> dict:
    """Default to current-hand first frame; gallery = consecutive originals around it.

    - Identify hand via renamed `{hole}_{token}_{ts}`; earliest = 牌局首帧.
    - Map to original `{token}_{ts}`; left/right browse consecutive original frames
      (not limited to this hand), centered on that first frame.
    """
    hole = hole_compact(json.loads(hole_key_json) if hole_key_json.startswith("[") else hole_key_json)
    if not hole:
        hole = hole_compact(hole_key_json)
    tokens = index.get(hole or "", {})
    frames: list[tuple[int, Path]] = []
    if user_token and user_token in tokens:
        frames = list(tokens[user_token])
    else:
        for lst in tokens.values():
            frames.extend(lst)
        frames.sort(key=lambda x: x[0])

    mismatch = first_action_mismatch(gt, sys)
    hand_ts = wepoker_ts((gt or {}).get("gameInfo", {}).get("handId") if gt else None)
    tgt = event_ts(gt) or event_ts(sys) or hand_ts

    if not frames:
        if orig_index and user_token and user_token in orig_index and tgt:
            cand = [f for f in orig_index[user_token] if f[0] >= (tgt - 2000)]
            frames = [min(cand, key=lambda x: x[0])] if cand else []
        if not frames:
            return {
                "primary": None,
                "gallery": [],
                "start_index": 0,
                "alternates": [],
                "reason": "无匹配截图",
                "target_ts": None,
            }

    if hand_ts:
        hand_end = hand_ts + 8 * 60 * 1000
        hand_frames = [f for f in frames if hand_ts - 2000 <= f[0] <= hand_end]
        if not hand_frames:
            hand_frames = [f for f in frames if f[0] >= hand_ts - 2000] or frames
    else:
        hand_frames = frames

    first_renamed = min(hand_frames, key=lambda x: x[0])
    first_ts = first_renamed[0]
    primary = (first_ts, resolve_shot_path(first_renamed[1], orig_dir))

    gallery_mode = "orig-neighbors"
    if orig_index and user_token and orig_index.get(user_token):
        orig_frames = list(orig_index[user_token])
        ts_list = [t for t, _ in orig_frames]
        if first_ts in ts_list:
            center_i = ts_list.index(first_ts)
            primary = orig_frames[center_i]
        else:
            after = [(i, f) for i, f in enumerate(orig_frames) if f[0] >= first_ts]
            if after:
                center_i, primary = after[0]
            else:
                center_i = min(range(len(orig_frames)), key=lambda i: abs(orig_frames[i][0] - first_ts))
                primary = orig_frames[center_i]
        lo = max(0, center_i - neighbor_radius)
        hi = min(len(orig_frames), center_i + neighbor_radius + 1)
        gallery = orig_frames[lo:hi]
        start_index = center_i - lo
    else:
        gallery_mode = "renamed-neighbors"
        renamed = sorted(frames, key=lambda x: x[0])
        renamed = [(t, resolve_shot_path(p, orig_dir)) for t, p in renamed]
        ts_list = [t for t, _ in renamed]
        center_i = ts_list.index(first_ts) if first_ts in ts_list else 0
        primary = renamed[center_i]
        lo = max(0, center_i - neighbor_radius)
        hi = min(len(renamed), center_i + neighbor_radius + 1)
        gallery = renamed[lo:hi]
        start_index = center_i - lo

    span_s = 0
    if len(gallery) >= 2:
        span_s = max(0, (gallery[-1][0] - gallery[0][0]) // 1000)

    reason_parts = [f"默认牌局首帧 ts={primary[0]}"]
    if mismatch:
        kind = mismatch.get("kind")
        if kind == "missing":
            reason_parts.append(f"缺失 {action_label(mismatch.get('gt'))}")
        elif kind == "extra":
            reason_parts.append(f"多余 {action_label(mismatch.get('sys'))}")
        elif kind == "rewrite":
            reason_parts.append(
                f"改写 {action_label(mismatch.get('gt'))} → {action_label(mismatch.get('sys'))}"
            )
        else:
            reason_parts.append(
                f"{action_label(mismatch.get('gt'))} vs {action_label(mismatch.get('sys'))}"
            )
    if gallery_mode == "orig-neighbors":
        reason_parts.append(
            f"原图连续前后帧可左右浏览（{len(gallery)} 帧 / 跨度约 {span_s}s，不限本手）"
        )
    else:
        reason_parts.append(
            f"重命名图前后帧可左右浏览（{len(gallery)} 帧；无原图目录时回退）"
        )

    return {
        "primary": primary,
        "gallery": gallery,
        "start_index": start_index,
        "alternates": [],
        "reason": "；".join(reason_parts),
        "target_ts": tgt,
        "mismatch": mismatch,
        "hole": hole,
        "n_frames": len(gallery),
        "n_hand_frames": len(hand_frames),
        "gallery_mode": gallery_mode,
        "span_s": span_s,
    }



def sample_timeline_by_time(
    frames: list[tuple[int, Path]],
    center_ts: int,
    *,
    window_ms: int = 8 * 60 * 1000,
    max_n: int = 48,
) -> tuple[list[tuple[int, Path]], int]:
    """Evenly sample frames in [center±window/2] by time (not consecutive dense frames).

    Returns (gallery, start_index_of_center).
    """
    if not frames:
        return [], 0
    half = window_ms // 2
    lo_ts, hi_ts = center_ts - half, center_ts + half
    in_win = [f for f in frames if lo_ts <= f[0] <= hi_ts]
    if not in_win:
        # nearest neighbors around center
        ordered = sorted(frames, key=lambda x: x[0])
        pi = min(range(len(ordered)), key=lambda i: abs(ordered[i][0] - center_ts))
        lo = max(0, pi - max_n // 2)
        hi = min(len(ordered), lo + max_n)
        lo = max(0, hi - max_n)
        gal = ordered[lo:hi]
        return gal, min(range(len(gal)), key=lambda i: abs(gal[i][0] - center_ts))

    if len(in_win) <= max_n:
        gal = in_win
    else:
        # pick max_n targets evenly across the time window, nearest frame each
        targets = [lo_ts + i * (hi_ts - lo_ts) / (max_n - 1) for i in range(max_n)]
        picked: list[tuple[int, Path]] = []
        used: set[int] = set()
        for t in targets:
            best_i = None
            best_d = None
            for i, (ts, _) in enumerate(in_win):
                if i in used:
                    continue
                d = abs(ts - t)
                if best_d is None or d < best_d:
                    best_d, best_i = d, i
            if best_i is not None:
                used.add(best_i)
                picked.append(in_win[best_i])
        gal = sorted(picked, key=lambda x: x[0])

    # ensure center frame present
    if not any(ts == center_ts for ts, _ in gal):
        # insert nearest to center_ts from in_win
        near = min(in_win, key=lambda x: abs(x[0] - center_ts))
        gal = sorted(gal + [near], key=lambda x: x[0])
        # trim if over
        if len(gal) > max_n:
            # keep those closest to center
            gal = sorted(gal, key=lambda x: abs(x[0] - center_ts))[:max_n]
            gal = sorted(gal, key=lambda x: x[0])

    start = min(range(len(gal)), key=lambda i: abs(gal[i][0] - center_ts))
    return gal, start


def path_to_file_url(path: Path) -> str:
    """file:// URL for direct browser reference (no asset copy)."""
    return Path(path).resolve().as_uri()


def gallery_file_refs(frames: list[tuple[int, Path]]) -> list[dict]:
    """Build gallery entries that point at original files directly."""
    out: list[dict] = []
    for i, (ts, src) in enumerate(frames):
        if not src or not Path(src).exists():
            continue
        out.append(
            {
                "rel": path_to_file_url(src),
                "ts": ts,
                "label": f"帧{i + 1}",
                "name": Path(src).name,
            }
        )
    return out


def copy_shot(src: Path, dest_dir: Path, hand_uid: str, tag: str) -> Optional[str]:
    if not src or not Path(src).exists():
        return None
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{hand_uid}_{tag}{Path(src).suffix.lower()}"
    shutil.copy2(src, dest)
    return dest.name


def copy_shot_gallery(
    frames: list[tuple[int, Path]],
    dest_dir: Path,
    hand_uid: str,
    tag: str,
) -> list[dict]:
    """Copy gallery frames; return [{rel, ts, label}, ...]."""
    out: list[dict] = []
    for i, (ts, src) in enumerate(frames):
        name = copy_shot(src, dest_dir, hand_uid, f"{tag}_{i:02d}")
        if not name:
            continue
        out.append(
            {
                "rel": f"assets/{name}",
                "ts": ts,
                "label": f"帧{i + 1}",
            }
        )
    return out


def json_snippet_for_mismatch(req: Optional[dict], mismatch: Optional[dict], which: str) -> str:
    """Show the mismatched action object (or short actionSequence window)."""
    if not req:
        return "（无报文）"
    acts = (req.get("gameInfo") or {}).get("actionSequence") or []
    if mismatch:
        kind = mismatch.get("kind")
        if which == "gt" and isinstance(mismatch.get("gt"), dict):
            target = mismatch["gt"]
            # find index in this req
            idx = None
            for i, a in enumerate(acts):
                if a == target:
                    idx = i
                    break
            if idx is None and mismatch.get("gt_index") is not None and which == "gt":
                idx = mismatch["gt_index"]
            if idx is not None:
                lo, hi = max(0, idx - 1), min(len(acts), idx + 2)
                return json.dumps(acts[lo:hi], ensure_ascii=False, indent=2)
            return json.dumps([target], ensure_ascii=False, indent=2)
        if which == "sys":
            if kind == "missing":
                return json.dumps(
                    {"note": "系统缺少下方行动", "missing": mismatch.get("gt")},
                    ensure_ascii=False,
                    indent=2,
                )
            if isinstance(mismatch.get("sys"), dict):
                target = mismatch["sys"]
                idx = None
                for i, a in enumerate(acts):
                    if a == target:
                        idx = i
                        break
                if idx is None and mismatch.get("sys_index") is not None:
                    idx = mismatch["sys_index"]
                if idx is not None:
                    lo, hi = max(0, idx - 1), min(len(acts), idx + 2)
                    return json.dumps(acts[lo:hi], ensure_ascii=False, indent=2)
                return json.dumps([target], ensure_ascii=False, indent=2)
    return json.dumps(acts[-5:], ensure_ascii=False, indent=2)


def full_json_text(req: Optional[dict]) -> str:
    if not req:
        return "（无报文）"
    return json.dumps(req, ensure_ascii=False, indent=2)


def _action_index_by_seat_street(acts: list, seat: Any, street: Any) -> Optional[int]:
    seat_s, street_s = str(seat or ""), str(street or "").upper()
    for i, a in enumerate(acts):
        if not isinstance(a, dict):
            continue
        if str(a.get("seat") or "") == seat_s and str(a.get("street") or "").upper() == street_s:
            return i
    return None


def _concrete_diff_paths(req: Optional[dict], diffs: list[dict], side: str) -> set[str]:
    """Resolve diffs (incl. alignment pseudo-paths) to concrete JSON paths in req."""
    out: set[str] = set()
    if not req or not diffs:
        return out
    gi = req.get("gameInfo") or {}
    acts = list(gi.get("actionSequence") or [])

    for d in diffs:
        path = str(d.get("path") or "")
        # Real deep-diff paths
        if path and "(" not in path and "@" not in path:
            out.add(path)
            continue

        # missing action — highlight whole object on GT side
        if d.get("type") == "missing_right" and side == "gt" and isinstance(d.get("left"), dict):
            a = d["left"]
            idx = None
            for i, act in enumerate(acts):
                if not isinstance(act, dict):
                    continue
                if (
                    act.get("seat") == a.get("seat")
                    and str(act.get("street") or "").upper() == str(a.get("street") or "").upper()
                    and act.get("actionType") == a.get("actionType")
                    and str(act.get("amount")) == str(a.get("amount"))
                ):
                    idx = i
                    break
            if idx is None:
                idx = _action_index_by_seat_street(acts, a.get("seat"), a.get("street"))
            if idx is not None:
                for k in acts[idx]:
                    out.add(f"gameInfo.actionSequence[{idx}].{k}")
            continue

        # extra action — highlight whole object on system side
        if d.get("type") == "missing_left" and side == "sys" and isinstance(d.get("right"), dict):
            a = d["right"]
            idx = None
            for i, act in enumerate(acts):
                if not isinstance(act, dict):
                    continue
                if (
                    act.get("seat") == a.get("seat")
                    and str(act.get("street") or "").upper() == str(a.get("street") or "").upper()
                    and act.get("actionType") == a.get("actionType")
                    and str(act.get("amount")) == str(a.get("amount"))
                ):
                    idx = i
                    break
            if idx is None:
                idx = _action_index_by_seat_street(acts, a.get("seat"), a.get("street"))
            if idx is not None:
                for k in acts[idx]:
                    out.add(f"gameInfo.actionSequence[{idx}].{k}")
            continue

        # rewrite: gameInfo.actionSequence[P3@PREFLOP].actionType
        m = re.match(
            r"gameInfo\.actionSequence\[([^@\]]+)@([^\]]+)\]\.(.+)$",
            path,
        )
        if m:
            seat, street, field = m.group(1), m.group(2), m.group(3)
            idx = _action_index_by_seat_street(acts, seat, street)
            if idx is not None:
                out.add(f"gameInfo.actionSequence[{idx}].{field}")
            continue

    return out


def highlight_full_json(
    req: Optional[dict],
    diffs: Optional[list] = None,
    side: str = "gt",
    mismatch: Optional[dict] = None,  # kept for call-site compat; unused when diffs given
) -> str:
    """Pretty JSON with ALL differing leaf values highlighted."""
    if not req:
        return esc("（无报文）")

    diffs = list(diffs or [])
    # Fallback: synthesize from first mismatch if no diffs passed
    if not diffs and mismatch:
        g, s = mismatch.get("gt"), mismatch.get("sys")
        kind = mismatch.get("kind")
        if kind == "missing" and isinstance(g, dict):
            diffs = [{"path": "", "type": "missing_right", "left": g, "right": None}]
        elif kind == "extra" and isinstance(s, dict):
            diffs = [{"path": "", "type": "missing_left", "left": None, "right": s}]
        elif isinstance(g, dict) and isinstance(s, dict):
            seat, street = g.get("seat"), g.get("street")
            for k in ("actionType", "amount", "street", "seat"):
                if g.get(k) != s.get(k):
                    diffs.append(
                        {
                            "path": f"gameInfo.actionSequence[{seat}@{street}].{k}",
                            "type": "value",
                            "left": g.get(k),
                            "right": s.get(k),
                        }
                    )

    changed = _concrete_diff_paths(req, diffs, side)
    first_marked = {"done": False}

    def mark_cell(path: str, cell: str) -> str:
        if path not in changed:
            return cell
        fid = ""
        if not first_marked["done"]:
            first_marked["done"] = True
            fid = f' id="focus-{"gt" if side == "gt" else "sys"}"'
        return f'<span class="mark-diff"{fid}>{cell}</span>'

    def render(val: Any, path: str, indent: int) -> list[str]:
        pad = "  " * indent
        lines: list[str] = []
        if isinstance(val, dict):
            if not val:
                lines.append(pad + "{}")
                return lines
            lines.append(pad + "{")
            items = list(val.items())
            for i, (k, v) in enumerate(items):
                p = f"{path}.{k}" if path else str(k)
                comma = "," if i < len(items) - 1 else ""
                if isinstance(v, (dict, list)):
                    lines.append(f'{pad}  "{esc(k)}":')
                    sub = render(v, p, indent + 1)
                    if sub:
                        block_hit = any(
                            c == p or c.startswith(p + ".") or c.startswith(p + "[")
                            for c in changed
                        )
                        if block_hit and isinstance(v, dict) and not any(
                            isinstance(x, (dict, list)) for x in v.values()
                        ):
                            # shallow object (e.g. one action): tint whole block lightly
                            sub = [f'<span class="json-focus">{x}</span>' for x in sub]
                        sub[-1] = sub[-1] + comma
                    lines.extend(sub)
                else:
                    raw = json.dumps(v, ensure_ascii=False)
                    cell = mark_cell(p, esc(raw))
                    lines.append(f'{pad}  "{esc(k)}": {cell}{comma}')
            lines.append(pad + "}")
            return lines
        if isinstance(val, list):
            if not val:
                lines.append(pad + "[]")
                return lines
            lines.append(pad + "[")
            for i, v in enumerate(val):
                p = f"{path}[{i}]"
                comma = "," if i < len(val) - 1 else ""
                if isinstance(v, (dict, list)):
                    sub = render(v, p, indent + 1)
                    if sub:
                        sub[-1] = sub[-1] + comma
                    lines.extend(sub)
                else:
                    raw = json.dumps(v, ensure_ascii=False)
                    cell = mark_cell(p, esc(raw))
                    lines.append(f"{pad}  {cell}{comma}")
            lines.append(pad + "]")
            return lines
        raw = json.dumps(val, ensure_ascii=False)
        lines.append(pad + mark_cell(path, esc(raw)))
        return lines

    return "\n".join(render(req, "", 0))


def callout_text(mismatch: Optional[dict], friendly: list[str]) -> str:
    if mismatch:
        kind = mismatch.get("kind")
        g, s = mismatch.get("gt"), mismatch.get("sys")
        if kind == "missing" and isinstance(g, dict):
            return f"系统缺少行动：{action_label(g)}（不是与后面座位对错，而是这条漏了）"
        if kind == "extra" and isinstance(s, dict):
            return f"系统多出行动：{action_label(s)}"
        if kind == "rewrite" and isinstance(g, dict) and isinstance(s, dict):
            from compare_gto_requests import action_types_equivalent, amounts_equivalent

            if not action_types_equivalent(g.get("actionType"), s.get("actionType")):
                return f"{g.get('seat')} 数据错误：应为 {g.get('actionType')}，系统是 {s.get('actionType')}（amount 真值={g.get('amount')} / 系统={s.get('amount')}）"
            if not amounts_equivalent(g.get("amount"), s.get("amount")):
                return f"{g.get('seat')} 金额错误：{g.get('amount')}→{s.get('amount')}"
            return f"{g.get('seat')} 行动被改写：真值「{action_label(g)}」vs 系统「{action_label(s)}」"
        if g and not s:
            return f"系统缺少行动：{action_label(g)}"
        if s and not g:
            return f"系统多出行动：{action_label(s)}"
    if friendly:
        return friendly[0]
    return "与真值不一致"


def glance_line(mismatch: Optional[dict], friendly: list[str], title: str) -> str:
    """One-line glance summary for the top of evidence card."""
    if mismatch:
        kind = mismatch.get("kind")
        g, s = mismatch.get("gt"), mismatch.get("sys")
        if kind == "missing" and isinstance(g, dict):
            street = STREET_CN.get(str(g.get("street") or "").upper(), g.get("street"))
            return f"系统缺少 {g.get('seat')} {g.get('actionType')}（{street}，amount={g.get('amount')}）"
        if kind == "extra" and isinstance(s, dict):
            street = STREET_CN.get(str(s.get("street") or "").upper(), s.get("street"))
            return f"系统多出 {s.get('seat')} {s.get('actionType')}（{street}，amount={s.get('amount')}）"
        if kind == "rewrite" and isinstance(g, dict) and isinstance(s, dict):
            from compare_gto_requests import action_types_equivalent, amounts_equivalent

            street = STREET_CN.get(str(g.get("street") or "").upper(), g.get("street"))
            if not action_types_equivalent(g.get("actionType"), s.get("actionType")):
                amt_part = ""
                if not amounts_equivalent(g.get("amount"), s.get("amount")):
                    amt_part = f"｜amount {g.get('amount')}→{s.get('amount')}"
                return f"{g.get('seat')} 应为 {g.get('actionType')}，系统写成 {s.get('actionType')}（{street}{amt_part}）"
            if not amounts_equivalent(g.get("amount"), s.get("amount")):
                return f"{g.get('seat')} amount {g.get('amount')}→{s.get('amount')}（{street}）"
            return f"{g.get('seat')} @ {street} 字段被改写"
        if g and not s:
            return f"系统缺少：{action_label(g)}"
        if s and not g:
            return f"系统多出：{action_label(s)}"
    return title or (friendly[0] if friendly else "与真值不一致")


def field_compare_rows(mismatch: Optional[dict], gt_norm: Optional[dict], sys_norm: Optional[dict]) -> list[dict]:
    """Build 字段|真值|系统 rows for the primary glance table."""
    rows: list[dict] = []
    if mismatch is not None:
        kind = mismatch.get("kind") or (
            "missing"
            if mismatch.get("gt") and not mismatch.get("sys")
            else ("extra" if mismatch.get("sys") and not mismatch.get("gt") else "rewrite")
        )
        g_raw = mismatch.get("gt")
        s_raw = mismatch.get("sys")
        kind_cn = action_issue_kind_label(kind, g_raw, s_raw)
        rows.append({"field": "问题类型", "gt": kind_cn, "sys": kind_cn, "diff": True})
        rows.append(
            {
                "field": "对齐序号(真/系)",
                "gt": mismatch.get("gt_index") if mismatch.get("gt_index") is not None else "—",
                "sys": mismatch.get("sys_index") if mismatch.get("sys_index") is not None else "—",
                "diff": False,
            }
        )
        g = g_raw if isinstance(g_raw, dict) else {}
        s = s_raw if isinstance(s_raw, dict) else {}
        for key, label in (
            ("street", "街次"),
            ("seat", "座位"),
            ("actionType", "行动类型"),
            ("amount", "金额"),
        ):
            if isinstance(g_raw, dict):
                gv = g.get(key, "—")
            else:
                gv = "（真值无此行动）"
            if isinstance(s_raw, dict):
                sv = s.get(key, "—")
            else:
                sv = "（系统缺少此行动）"
            if kind == "rewrite":
                from compare_gto_requests import scalar_values_equivalent

                diff = not scalar_values_equivalent(gv, sv, field=label)
            else:
                diff = True
            rows.append(
                {
                    "field": label,
                    "gt": gv if gv is not None else "—",
                    "sys": sv if sv is not None else "—",
                    "diff": diff,
                }
            )
        return rows

    gi_g = (gt_norm or {}).get("gameInfo") or {}
    gi_s = (sys_norm or {}).get("gameInfo") or {}
    for key, label in (
        ("ante", "前注"),
        ("straddle", "抢注"),
        ("smallBlind", "小盲"),
        ("bigBlind", "大盲"),
        ("communityCards", "公共牌"),
    ):
        gv, sv = gi_g.get(key), gi_s.get(key)
        if gv is None and sv is None:
            continue
        from compare_gto_requests import scalar_values_equivalent

        rows.append(
            {
                "field": label,
                "gt": gv,
                "sys": sv,
                "diff": not scalar_values_equivalent(gv, sv, field=label),
            }
        )
    if not rows:
        rows.append({"field": "说明", "gt": "见下方摘要", "sys": "见下方摘要", "diff": True})
    return rows


def render_field_compare_table(rows: list[dict]) -> str:
    trs = []
    for r in rows:
        cls = ' class="row-diff"' if r.get("diff") else ""
        mark = " ✗" if r.get("diff") else ""
        trs.append(
            f"<tr{cls}>"
            f"<td>{esc(r['field'])}{mark}</td>"
            f"<td><code>{esc(r['gt'])}</code></td>"
            f"<td><code>{esc(r['sys'])}</code></td>"
            "</tr>"
        )
    return (
        '<table class="field-compare"><thead><tr>'
        "<th>字段</th><th>正确值</th><th>Chess API</th>"
        "</tr></thead><tbody>"
        + "".join(trs)
        + "</tbody></table>"
    )


def rewrite_kind_label(g: Any, s: Any) -> str:
    """Human label for matched seat/street with changed action content."""
    if not isinstance(g, dict) or not isinstance(s, dict):
        return "行动内容不正确"
    from compare_gto_requests import action_types_equivalent, amounts_equivalent

    type_diff = not action_types_equivalent(g.get("actionType"), s.get("actionType"))
    amt_diff = not amounts_equivalent(g.get("amount"), s.get("amount"))
    if type_diff and amt_diff:
        return "行动类型与金额均不正确"
    if type_diff:
        return "行动类型不正确"
    if amt_diff:
        return "金额不正确"
    return "行动内容不正确"


def action_issue_kind_label(kind: str, g: Any = None, s: Any = None) -> str:
    if kind == "missing":
        return "行动缺失"
    if kind == "extra":
        return "行动多余"
    if kind == "rewrite":
        return rewrite_kind_label(g, s)
    return kind or "差异"


def seat_hint(mismatch: Optional[dict]) -> str:
    if not mismatch:
        return ""
    g, s = mismatch.get("gt"), mismatch.get("sys")
    seat = None
    if isinstance(g, dict):
        seat = g.get("seat")
    if not seat and isinstance(s, dict):
        seat = s.get("seat")
    if seat:
        return f"请在截图中核对座位 {seat}"
    return "请对照截图中的行动/筹码"


def _issue_from_action_op(op: dict) -> dict:
    """One semantic issue block from an alignment op."""
    kind = op["op"]
    g, s = op.get("gt"), op.get("sys")
    kind_cn = action_issue_kind_label(kind, g, s)
    mismatch = {
        "kind": kind,
        "gt": g,
        "sys": s,
        "gt_index": op.get("gt_index"),
        "sys_index": op.get("sys_index"),
        "index": op.get("gt_index") if op.get("gt_index") is not None else op.get("sys_index"),
        "street": (g or s or {}).get("street") if isinstance(g or s, dict) else None,
        "seat": (g or s or {}).get("seat") if isinstance(g or s, dict) else None,
    }
    title = glance_line(mismatch, [], kind_cn)
    return {
        "title": title,
        "kind": kind_cn,
        "rows": field_compare_rows(mismatch, None, None),
        "mismatch": mismatch,
    }


def _num_same(a: Any, b: Any) -> bool:
    if a is None and b is None:
        return True
    try:
        return abs(float(a) - float(b)) < 1e-9
    except Exception:
        return str(a) == str(b)


def _blind_same(key: str, a: Any, b: Any) -> bool:
    if key == "straddle":
        from compare_gto_requests import straddle_values_equivalent

        return straddle_values_equivalent(a, b)
    return _num_same(a, b)


def chess_norm_for_compare(
    trace_chain: Optional[dict],
    gt_norm: Optional[dict] = None,
) -> Optional[dict]:
    """Chess fusionCorrectedData → 与正确值同口径的可比对报文。

    有 gt_norm 时：不再按 Chess 自己的 last P0 裁剪，而是截到与正确值相同的
    actionSequence 长度 / 公牌长度（同一决策边界）。
    """
    import copy

    from compare_gto_requests import normalize_for_compare, strip_meta

    raw = layer_chess_payload(trace_chain)
    if raw is None:
        return None
    if isinstance(raw, dict) and "gameInfo" not in raw:
        if any(
            k in raw
            for k in ("actionSequence", "players", "smallBlind", "bigBlind", "communityCards")
        ):
            raw = {"gameInfo": raw}
        else:
            return None
    if not isinstance(raw, dict):
        return None

    if not isinstance(gt_norm, dict) or not isinstance(gt_norm.get("gameInfo"), dict):
        norm, _meta = normalize_for_compare(raw, truncate=True)
        return norm

    working = strip_meta(copy.deepcopy(raw))
    if not isinstance(working, dict):
        return None
    gi = working.setdefault("gameInfo", {})
    if not isinstance(gi, dict):
        return None
    gt_gi = gt_norm.get("gameInfo") or {}
    gt_seq = list(gt_gi.get("actionSequence") or [])
    seq = list(gi.get("actionSequence") or [])
    # 截到正确值决策边界（不伸长；Chess 更短则保持原长）
    gi["actionSequence"] = seq[: len(gt_seq)]
    gt_board = list(gt_gi.get("communityCards") or [])
    board = list(gi.get("communityCards") or [])
    gi["communityCards"] = board[: len(gt_board)]
    return working


def build_issue_blocks(gt: Optional[dict], sys: Optional[dict]) -> list[dict]:
    """Semantic, de-duplicated issue blocks for evidence cards.

    `sys` 为对照侧（证据页现为 Chess API fusionCorrectedData 规范化结果）。

    Display / review priority (high → low):
      1. 盲注 / 前注 / 抢注 / 大小盲
      2. 玩家人数
      3. 位置
      4. 起始筹码
      5. 公共牌
      6. 行动改写（类型/金额）
      7. 行动缺失 / 行动多余
    """
    if not gt or not sys:
        return []

    gi_g = gt.get("gameInfo") or {}
    gi_s = sys.get("gameInfo") or {}
    out: list[dict] = []

    # 1) 盲注
    blind_rows = []
    for key, label in (
        ("ante", "前注"),
        ("straddle", "抢注"),
        ("smallBlind", "小盲"),
        ("bigBlind", "大盲"),
    ):
        vg, vs = gi_g.get(key), gi_s.get(key)
        if vg is None and vs is None:
            continue
        if not _blind_same(key, vg, vs):
            blind_rows.append({"field": label, "gt": vg, "sys": vs, "diff": True})
    if blind_rows:
        out.append(
            {
                "title": f"盲注/前注不一致（{len(blind_rows)} 项）",
                "kind": "盲注/前注",
                "rows": blind_rows,
                "mismatch": None,
            }
        )

    pg = [p for p in (gi_g.get("players") or []) if isinstance(p, dict)]
    ps = [p for p in (gi_s.get("players") or []) if isinstance(p, dict)]
    by_g = {p.get("seat"): p for p in pg}
    by_s = {p.get("seat"): p for p in ps}

    # 2) 玩家人数
    if len(pg) != len(ps):
        out.append(
            {
                "title": f"玩家人数不一致：正确值 {len(pg)} vs Chess {len(ps)}",
                "kind": "玩家人数",
                "rows": [
                    {"field": "players.length", "gt": len(pg), "sys": len(ps), "diff": True}
                ],
                "mismatch": None,
            }
        )

    chip_rows = []
    pos_rows = []
    for seat in sorted(set(by_g) | set(by_s), key=lambda x: str(x)):
        a, b = by_g.get(seat), by_s.get(seat)
        # 正确值或系统任一侧有该座位都展示（另一侧缺失也要露出）
        if a and b:
            chip_diff = not _num_same(a.get("initChips"), b.get("initChips"))
            pos_diff = a.get("position") != b.get("position")
        elif a and not b:
            chip_diff = a.get("initChips") is not None
            pos_diff = a.get("position") is not None
        elif b and not a:
            chip_diff = b.get("initChips") is not None
            pos_diff = b.get("position") is not None
        else:
            continue
        if chip_diff:
            chip_rows.append(
                {
                    "field": f"{seat} initChips",
                    "gt": (a or {}).get("initChips") if a else "（无此座位）",
                    "sys": (b or {}).get("initChips") if b else "（无此座位）",
                    "diff": True,
                }
            )
        if pos_diff:
            pos_rows.append(
                {
                    "field": f"{seat} position",
                    "gt": (a or {}).get("position") if a else "（无此座位）",
                    "sys": (b or {}).get("position") if b else "（无此座位）",
                    "diff": True,
                }
            )

    # 3) 位置
    if pos_rows:
        out.append(
            {
                "title": f"位置不一致（{len(pos_rows)} 个座位）",
                "kind": "位置",
                "rows": pos_rows,
                "mismatch": None,
            }
        )

    # 4) 起始筹码
    if chip_rows:
        out.append(
            {
                "title": f"起始筹码不一致（{len(chip_rows)} 个座位）",
                "kind": "起始筹码",
                "rows": chip_rows,
                "mismatch": None,
            }
        )

    # 5) 公牌
    board_g = list(gi_g.get("communityCards") or [])
    board_s = list(gi_s.get("communityCards") or [])
    if board_g != board_s:
        out.append(
            {
                "title": "公共牌不一致",
                "kind": "公共牌",
                "rows": [
                    {
                        "field": "communityCards",
                        "gt": board_g or "[]",
                        "sys": board_s or "[]",
                        "diff": True,
                    }
                ],
                "mismatch": None,
            }
        )

    # 6–7) 行动：改写在前，缺失/多余靠后
    rewrites: list[dict] = []
    miss_extra: list[dict] = []
    for op in align_requests(gt, sys):
        if op["op"] == "equal":
            continue
        block = _issue_from_action_op(op)
        if op["op"] == "rewrite":
            rewrites.append(block)
        else:
            miss_extra.append(block)

    return out + rewrites + miss_extra


def compact_issue_line(block: dict, xrows: Optional[list[dict]] = None) -> str:
    """One-line list item, e.g. 金额不正确 · P2 amount 20→40（翻前）."""
    del xrows  # 保留参数兼容旧调用，折叠行不再塞各模块概要
    kind = str(block.get("kind") or "").strip()
    title = str(block.get("title") or "").strip()
    if kind and title and kind not in title:
        return f"{kind} · {title}"
    return title or kind or "差异"


def issue_summary_line(block: dict, xrows: Optional[list[dict]] = None) -> str:
    """兼容旧名：折叠行用短摘要。"""
    return compact_issue_line(block, xrows)


def render_issue_block(block: dict, index: int, primary: bool) -> str:
    cls = "issue-block primary" if primary else "issue-block compact"
    table = render_field_compare_table(block.get("rows") or [])
    return (
        f'<div class="{cls}">'
        f'<div class="issue-head">'
        f'<span class="issue-idx">{index}</span>'
        f'<span class="issue-kind">{esc(block.get("kind") or "")}</span>'
        f'<span class="issue-title">{esc(block.get("title") or "")}</span>'
        f"</div>"
        f"{table}"
        f"</div>"
    )


# 与 Trace Viewer「基本信息 / 业务属性」逐项对齐；无值也占位
ANCHOR_META_FIELDS = (
    ("SpanName", "span_name"),
    ("Service", "service"),
    ("Duration", "duration"),
    ("Status", "span_status"),
    ("Timestamp", "timestamp"),
    ("SpanId", "span_id"),
    ("TraceId", "trace_id"),
    ("handIndex", "hand_index"),
    ("holeCards", "hole_cards"),
    ("openId", "open_id"),
)


def render_module_anchor_card(meta: dict) -> str:
    """One module card: compact rows, full values (no truncation)."""
    ok = bool(meta.get("ok"))
    cls = "mod-anchor-card" + ("" if ok else " is-miss")
    title = esc(meta.get("title") or meta.get("id") or "")

    def row(label: str, key: str) -> str:
        full = meta.get(key)
        text = "" if full is None else str(full).strip()
        if not text:
            return (
                f'<div class="mod-anchor-row">'
                f'<span class="k">{esc(label)}</span>'
                f'<span class="v muted">—</span>'
                f"</div>"
            )
        return (
            f'<div class="mod-anchor-row">'
            f'<span class="k">{esc(label)}</span>'
            f'<code class="v">{esc(text)}</code>'
            f"</div>"
        )

    rows_html = "".join(row(label, key) for label, key in ANCHOR_META_FIELDS)
    return (
        f'<div class="{cls}">'
        f'<div class="mod-anchor-title">{title}</div>'
        f"{rows_html}"
        f"</div>"
    )


def render_anchor_anomaly_banner(trace_chain: Optional[dict]) -> str:
    """Compact warning when Trace hit multiple dealer_change for one hand."""
    if not trace_chain:
        return ""
    warnings = trace_chain.get("anchor_warnings") or []
    dealer_n = int(trace_chain.get("dealer_change_n") or 0)
    if dealer_n <= 1 and not warnings:
        return ""

    dealers = trace_chain.get("dealer_changes") or []
    chosen = trace_chain.get("chosen_hero") or trace_chain.get("anchor") or {}
    mode = trace_chain.get("anchor_mode") or ""

    def _short_ts(ts: Any) -> str:
        s = str(ts or "").strip()
        if not s:
            return "—"
        # 2026-07-13T04:25:54.849Z → 07-13 04:25:54
        s = s.replace("T", " ").replace("Z", "")
        if len(s) >= 19 and s[4] == "-":
            return s[5:19]
        return s[:19]

    def _short_id(sid: Any) -> str:
        s = str(sid or "").strip()
        if not s:
            return "—"
        return s if len(s) <= 10 else s[-8:]

    def _line(label: str, meta: dict, *, tag: str = "") -> str:
        if not meta:
            return ""
        bits = [
            f'<span class="k">{esc(label)}</span>',
            f'<code>{esc(_short_ts(meta.get("timestamp")))}</code>',
            f'<code>{esc(_short_id(meta.get("span_id")))}</code>',
        ]
        if tag:
            bits.append(f'<span class="tag">{esc(tag)}</span>')
        return f'<div class="anchor-anomaly-line">{" · ".join(bits)}</div>'

    dealer_lines = []
    for i, d in enumerate(dealers):
        tag = "采用" if i == 0 else "忽略"
        ord_n = d.get("ordinal") or (i + 1)
        dealer_lines.append(_line(f"dc#{ord_n}", d, tag=tag))
    hero_line = _line("hero", chosen, tag="锚点")

    pick_note = (
        "已取第1次 dc 后最后一次 hero_action"
        if mode == "first_dealer_change_last_hero"
        else "已按兜底规则取 hero_action"
    )

    return (
        '<details class="anchor-anomaly">'
        "<summary>"
        f"异常 · dealer_change×{esc(dealer_n)}（通常1次）· {esc(pick_note)}"
        "</summary>"
        f'{"".join(dealer_lines)}{hero_line}'
        "</details>"
        "<style>"
        ".anchor-anomaly{margin:0 0 6px;padding:0;border:1px solid #fcd34d;"
        "border-radius:6px;background:#fffbeb;color:#92400e;font-size:11px;"
        "line-height:1.35;overflow:hidden}"
        ".anchor-anomaly>summary{list-style:none;cursor:pointer;user-select:none;"
        "padding:4px 8px;font-weight:600;color:#92400e}"
        ".anchor-anomaly>summary::-webkit-details-marker{display:none}"
        ".anchor-anomaly>summary::before{content:'▸ ';color:#d97706;font-size:9px}"
        ".anchor-anomaly[open]>summary::before{content:'▾ '}"
        ".anchor-anomaly>summary:hover{background:#fef3c7}"
        ".anchor-anomaly-line{margin:0;padding:2px 8px 3px;"
        "font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:10px;"
        "color:#78350f;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}"
        ".anchor-anomaly-line .k{color:#92400e;font-weight:600;font-family:inherit}"
        ".anchor-anomaly-line .tag{display:inline-block;margin-left:2px;padding:0 4px;"
        "border-radius:3px;background:#fef3c7;color:#92400e;font-size:9px;"
        "font-weight:700;font-family:inherit}"
        "</style>"
    )


def render_module_anchor_strip(trace_chain: Optional[dict]) -> str:
    """Strip above cross-module table: compact, all fields, no copy buttons."""
    metas = module_anchor_metas(trace_chain)
    if not metas:
        metas = [
            {
                "id": mid,
                "title": title,
                "ok": False,
                "span_name": None,
                "service": None,
                "span_id": None,
                "trace_id": None,
                "timestamp": None,
                "duration": None,
                "span_status": None,
                "hand_index": None,
                "open_id": None,
                "hole_cards": None,
            }
            for mid, title in (
                ("signal", "信号引擎"),
                ("chess", "Chess API"),
            )
        ]
    note = ""
    if not trace_chain:
        note = '<div class="mod-anchor-note">无 Trace 链：字段已列出，打开页自动查询后回填</div>'
    # 证据页不展示状态引擎 / 网关
    cards = "".join(
        render_module_anchor_card(m)
        for m in metas
        if m.get("id") not in ("state", "gateway")
    )
    # 默认折叠，避免占满差异区；需要核对时再展开
    # 异常条由证据卡顶栏统一挂一次，不塞进每条差异的对照表
    return (
        '<details class="mod-anchor-strip" id="live-mod-anchor-strip">'
        '<summary class="mod-anchor-label">模块锚点（基本信息 + 业务属性 · 点击展开）</summary>'
        f"{note}"
        f'<div class="mod-anchor-grid">{cards}</div>'
        "</details>"
    )

def _cell_display(cell: Optional[dict]) -> tuple[str, str]:
    """Return (value_text, path_text) for a cross-module cell."""
    cell = cell or {}
    path = str(cell.get("path") or "").strip()
    value = cell.get("value")
    if value is None and cell.get("text"):
        text = str(cell.get("text") or "—")
        if "=" in text and text != "—":
            path, _, value = text.rpartition("=")
        else:
            value = text
    if value in (None, ""):
        value = "—"
    if cell.get("missing") and value == "—":
        value = "无此字段"
    return str(value), path


def issue_problem_desc(block: dict) -> str:
    """问题描述：不重复街次/PN（它们单独成行）。"""
    kind = str(block.get("kind") or "").strip()
    mm = block.get("mismatch") if isinstance(block.get("mismatch"), dict) else {}
    g, s = mm.get("gt"), mm.get("sys")
    if kind == "金额不正确" and isinstance(g, dict) and isinstance(s, dict):
        at = g.get("actionType") or ""
        return f"金额不正确 · {at} {g.get('amount')}→{s.get('amount')}".replace("  ", " ").strip()
    if kind == "行动类型不正确" and isinstance(g, dict) and isinstance(s, dict):
        return f"行动类型不正确 · {g.get('actionType')}→{s.get('actionType')}"
    if kind == "行动类型与金额均不正确" and isinstance(g, dict) and isinstance(s, dict):
        return (
            f"行动类型与金额均不正确 · {g.get('actionType')} {g.get('amount')}"
            f"→{s.get('actionType')} {s.get('amount')}"
        )
    if kind == "行动缺失" and isinstance(g, dict):
        return f"行动缺失 · 系统缺少 {g.get('actionType')}（amount={g.get('amount')}）"
    if kind == "行动多余" and isinstance(s, dict):
        return f"行动多余 · 系统多出 {s.get('actionType')}（amount={s.get('amount')}）"
    if kind == "行动内容不正确" and isinstance(g, dict) and isinstance(s, dict):
        return f"行动内容不正确 · {g.get('actionType')} {g.get('amount')}→{s.get('actionType')} {s.get('amount')}"
    if kind == "盲注/前注":
        fields = [str(r.get("field") or "") for r in (block.get("rows") or []) if r.get("diff")]
        return f"盲注/前注不一致" + (f"：{'、'.join(fields)}" if fields else "")
    if kind == "玩家人数":
        return str(block.get("title") or "玩家人数不一致")
    if kind in ("起始筹码", "位置", "公共牌"):
        return str(block.get("title") or kind)
    title = str(block.get("title") or "").strip()
    if title and kind and kind not in title:
        return f"{kind} · {title}"
    return title or kind or "差异"


def issue_street_pn(block: dict, *, seat_override: Any = None) -> tuple[str, str]:
    """Return (街次中文, PN)."""
    mm = block.get("mismatch") if isinstance(block.get("mismatch"), dict) else {}
    g = mm.get("gt") if isinstance(mm.get("gt"), dict) else None
    s = mm.get("sys") if isinstance(mm.get("sys"), dict) else None
    street_raw = None
    seat = seat_override
    if g:
        street_raw = g.get("street")
        if seat is None:
            seat = g.get("seat")
    if street_raw is None and s:
        street_raw = s.get("street")
    if seat is None and s:
        seat = s.get("seat")
    if seat is None:
        # 从 rows 里猜单个座位，如 "P2 initChips"
        seats = []
        for r in block.get("rows") or []:
            f = str(r.get("field") or "")
            tok = f.split()[0] if f.split() else ""
            if tok.startswith("P") and tok[1:].isdigit():
                seats.append(tok)
        if len(set(seats)) == 1:
            seat = seats[0]
    street_cn = "—"
    if street_raw:
        street_cn = STREET_CN.get(str(street_raw).upper(), str(street_raw))
    seat_s = str(seat).strip() if seat not in (None, "") else "—"
    return street_cn, seat_s


def render_issue_module_list(xrows: list[dict]) -> str:
    """各模块数据：纵向列出 正确值 / 信号 / Chess（已隐藏系统最终）。"""
    if not xrows:
        return '<p class="xmod-empty">无相关字段可对照</p>'
    modules = (
        ("gt", "正确值"),
        ("signal", "信号引擎"),
        ("chess", "Chess API"),
    )
    blocks = []
    multi = len(xrows) > 1
    for key, title in modules:
        vals = []
        paths = []
        for r in xrows:
            label = str(r.get("field") or "").strip() or "值"
            value, path = _cell_display(r.get(key) if isinstance(r.get(key), dict) else None)
            if multi:
                vals.append(f"<code>{esc(label)}</code>=<strong>{esc(value)}</strong>")
            else:
                vals.append(f"<strong>{esc(value)}</strong>")
            if path and path not in paths:
                paths.append(path)
        val_html = '<span class="sep"> · </span>'.join(vals) if vals else "—"
        path_html = ""
        if paths:
            path_html = (
                '<div class="issue-mod-paths">'
                + "<br/>".join(f"<code>{esc(p)}</code>" for p in paths)
                + "</div>"
            )
        blocks.append(
            f'<div class="issue-mod-row">'
            f'<div class="issue-mod-k">{esc(title)}</div>'
            f'<div class="issue-mod-v">{val_html}{path_html}</div>'
            f"</div>"
        )
    return f'<div class="issue-mod-list">{"".join(blocks)}</div>'


def render_issue_story_section(
    *,
    desc: str,
    street: str,
    seat: str,
    xrows: list[dict],
) -> str:
    """统一格式：问题描述 → 街次 → PN → 各模块数据。"""
    meta = (
        f'<div class="issue-story-meta">'
        f'<div class="issue-story-row"><span class="k">问题描述</span><span class="v">{esc(desc)}</span></div>'
        f'<div class="issue-story-row"><span class="k">街次</span><span class="v">{esc(street)}</span></div>'
        f'<div class="issue-story-row"><span class="k">PN</span><span class="v">{esc(seat)}</span></div>'
        f"</div>"
    )
    return f'<div class="issue-story">{meta}{render_issue_module_list(xrows)}</div>'


def render_issue_detail_html(block: dict, xrows: list[dict]) -> str:
    """Expand body for one issue block (may contain multiple PN sections)."""
    kind = str(block.get("kind") or "")
    desc = issue_problem_desc(block)
    street, seat = issue_street_pn(block)

    # 多座位块：每个 PN 单独一套「问题描述/街次/PN/各模块」
    if kind in ("起始筹码", "位置") or ("起始筹码" in kind) or (kind == "位置"):
        by_seat: dict[str, list[dict]] = {}
        order: list[str] = []
        for r in xrows:
            field = str(r.get("field") or "")
            tok = field.split()[0] if field.split() else "—"
            if tok not in by_seat:
                by_seat[tok] = []
                order.append(tok)
            by_seat[tok].append(r)
        if len(order) > 1:
            parts = []
            for tok in order:
                sub_desc = f"{kind}不一致" if kind in ("起始筹码", "位置") else desc
                field0 = str((by_seat[tok][0] or {}).get("field") or "")
                if "initChips" in field0:
                    sub_desc = "起始筹码不正确"
                elif "position" in field0:
                    sub_desc = "位置不正确"
                parts.append(
                    render_issue_story_section(
                        desc=sub_desc, street="—", seat=tok, xrows=by_seat[tok]
                    )
                )
            return "".join(parts)

    if kind in ("盲注/前注",) or "盲注" in kind:
        return render_issue_story_section(desc=desc, street="—", seat="—", xrows=xrows)
    if kind == "玩家人数":
        return render_issue_story_section(desc=desc, street="—", seat="—", xrows=xrows)
    if kind == "公共牌":
        return render_issue_story_section(desc=desc, street=street if street != "—" else "—", seat="—", xrows=xrows)

    return render_issue_story_section(desc=desc, street=street, seat=seat, xrows=xrows)


def _xmod_cell_html(value: str, path: str, *, kind: str = "") -> str:
    """One module cell; kind: miss | diff | ok | ''."""
    miss = value in ("—", "无此字段") or kind == "miss"
    classes = ["xmod-td"]
    if miss:
        classes.append("is-miss")
    elif kind == "diff":
        classes.append("is-diff")
    elif kind == "ok":
        classes.append("is-ok")
    path_html = ""
    if path and path not in ("—",) and not miss:
        path_html = f'<div class="xmod-path" title="{esc(path)}">{esc(path)}</div>'
    val_cls = "xmod-val muted" if miss else "xmod-val"
    display = "无此字段" if miss and value in ("—", "无此字段") else value
    return (
        f'<td class="{" ".join(classes)}"><div class="xmod-cell">'
        f'<div class="{val_cls}">{esc(display)}</div>'
        f"{path_html}"
        f"</div></td>"
    )


def _xmod_compare_kind(ref: str, value: str, field: str = "") -> str:
    from compare_gto_requests import scalar_values_equivalent, straddle_values_equivalent

    field_l = str(field or "").strip().lower()
    is_straddle = field_l in ("straddle", "抢注", "抓位") or "straddle" in field_l
    if is_straddle:

        def _norm(v: str) -> Any:
            if v in ("—", "无此字段", "", "None", "null", "none"):
                return None
            return v

        if straddle_values_equivalent(_norm(ref), _norm(value)):
            return "ok"
    if value in ("—", "无此字段"):
        return "miss"
    if ref in ("—", "无此字段"):
        return ""
    if scalar_values_equivalent(ref, value, field=field):
        return "ok"
    return "ok" if value == ref else "diff"


def render_cross_module_table(
    rows: list[dict],
    *,
    trace_chain: Optional[dict] = None,
    include_anchor_strip: bool = False,
) -> str:
    """跨模块对照表：字段 × 正确值 / 信号 / Chess（已隐藏系统最终）。"""
    strip = render_module_anchor_strip(trace_chain) if include_anchor_strip else ""
    if not rows:
        return strip + '<p class="xmod-empty">无相关字段可对照</p>'
    trs = []
    for r in rows:
        gt_v, gt_p = _cell_display(r.get("gt") if isinstance(r.get("gt"), dict) else None)
        sig_v, sig_p = _cell_display(
            r.get("signal") if isinstance(r.get("signal"), dict) else None
        )
        chess_v, chess_p = _cell_display(
            r.get("chess") if isinstance(r.get("chess"), dict) else None
        )
        cells = [
            _xmod_cell_html(
                gt_v, gt_p, kind="miss" if gt_v in ("—", "无此字段") else "ok"
            ),
            _xmod_cell_html(
                sig_v, sig_p, kind=_xmod_compare_kind(gt_v, sig_v, field=str(r.get("field") or ""))
            ),
            _xmod_cell_html(
                chess_v,
                chess_p,
                kind=_xmod_compare_kind(gt_v, chess_v, field=str(r.get("field") or "")),
            ),
        ]
        trs.append(
            f'<tr><th scope="row" class="xmod-field">{esc(r.get("field") or "")}</th>'
            f'{"".join(cells)}</tr>'
        )
    table = (
        '<div class="xmod-wrap"><table class="xmod-table">'
        "<thead><tr>"
        '<th class="xmod-col-field">字段</th>'
        '<th class="xmod-col-gt">正确值</th>'
        '<th class="xmod-col-sig">信号引擎</th>'
        '<th class="xmod-col-chess">Chess API</th>'
        "</tr></thead><tbody>"
        + "".join(trs)
        + "</tbody></table></div>"
    )
    return strip + table


def _json_pre_block(
    title: str,
    obj: Any,
    *,
    open_default: bool = False,
    html_body: Optional[str] = None,
) -> str:
    open_attr = " open" if open_default else ""
    if html_body is not None:
        body = f'<pre class="mod-json-pre">{html_body}</pre>'
    elif obj is None:
        body = '<pre class="mod-json-pre">（无数据）</pre>'
    else:
        try:
            plain = json.dumps(obj, ensure_ascii=False, indent=2, default=str)
        except Exception:
            plain = str(obj)
        body = f'<pre class="mod-json-pre">{esc(plain)}</pre>'
    # 复制按钮放在 details 外的标题栏，折叠/展开都始终可见
    return (
        f'<div class="mod-json-card">'
        f'<div class="mod-json-head">'
        f'<span class="mod-json-sum-title">{esc(title)}</span>'
        f'<button type="button" class="mod-json-copy" title="复制本列 JSON">复制</button>'
        f"</div>"
        f'<details class="mod-json-block"{open_attr}>'
        f'<summary class="mod-json-sum">点击展开 / 收起</summary>'
        f"{body}</details>"
        f"</div>"
    )


def _is_game_info_shaped(payload: Any) -> bool:
    return isinstance(payload, dict) and (
        "actionSequence" in payload
        or "players" in payload
        or "smallBlind" in payload
        or "bigBlind" in payload
    )


def _game_info_path_prefix(payload: Any, prefix: str = "") -> Optional[str]:
    """Locate gameInfo path inside module payload.

    Returns:
      - \"gameInfo\" / \"fusionCorrectedData.gameInfo\" when nested
      - \"fusionCorrectedData\" when nested object itself is gameInfo-shaped
      - \"\" when payload itself is gameInfo-shaped (caller strips gameInfo. from diffs)
      - None when not found
    """
    if not isinstance(payload, dict):
        return None
    if isinstance(payload.get("gameInfo"), dict):
        return f"{prefix}.gameInfo" if prefix else "gameInfo"
    # Root or nested envelope may already be gameInfo-shaped (no gameInfo key).
    if _is_game_info_shaped(payload):
        return prefix
    for k, v in payload.items():
        if not isinstance(v, dict):
            continue
        if str(k).startswith("_"):
            continue
        child = f"{prefix}.{k}" if prefix else str(k)
        found = _game_info_path_prefix(v, child)
        if found is not None:
            return found
    return None


def _normalize_mark_path(path: str) -> str:
    """Strip (seat=…,#n) annotations so json_with_value_marks can hit list indices."""
    return re.sub(r"\([^)]*\)", "", str(path or ""))


_ACTION_DIFF_RE = re.compile(
    r"^gameInfo\.actionSequence\[([^@\]]+)@([^\]]+)\]\.(.+)$"
)
_PLAYER_DIFF_RE = re.compile(r"^gameInfo\.players\[seat=([^\]]+)\]\.(.+)$")
_BLIND_DIFF_RE = re.compile(
    r"^gameInfo\.(smallBlind|bigBlind|ante|straddle|communityCards)$"
)


def _remap_gto_diffs_onto_payload(diffs: list[dict], payload: Any) -> list[dict]:
    """Map gameInfo.* diff paths onto the module payload's actual nesting."""
    if not diffs or not isinstance(payload, dict):
        return []
    gi_prefix = _game_info_path_prefix(payload)
    if gi_prefix is None:
        return []
    out: list[dict] = []
    for d in diffs:
        p = str(d.get("path") or "")
        if not p:
            left = d.get("left") if isinstance(d.get("left"), dict) else None
            right = d.get("right") if isinstance(d.get("right"), dict) else None
            act = left or right
            if isinstance(act, dict) and act.get("seat") is not None:
                seat, street = act.get("seat"), act.get("street")
                for field in ("amount", "actionType", "seat", "street"):
                    if gi_prefix == "":
                        np = f"actionSequence[{seat}@{street}].{field}"
                    else:
                        np = f"{gi_prefix}.actionSequence[{seat}@{street}].{field}"
                    out.append(
                        {"path": np, "type": d.get("type") or "value", "left": None, "right": None}
                    )
            continue
        if gi_prefix == "":
            if p.startswith("gameInfo."):
                out.append({**d, "path": p[len("gameInfo.") :]})
            elif p != "gameInfo":
                out.append(d)
            continue
        if p.startswith("gameInfo"):
            out.append({**d, "path": gi_prefix + p[len("gameInfo") :]})
    return out


def _signal_mark_diffs_from_gt_diffs(
    signal_br: Any,
    gt_norm: Optional[dict],
    diffs: list[dict],
) -> list[dict]:
    """Resolve GT↔系统差异到信号引擎 hand_history / 盲注路径，供高亮。"""
    if not diffs or not isinstance(signal_br, dict):
        return []
    gi = None
    if isinstance(gt_norm, dict):
        gi = gt_norm.get("gameInfo") if isinstance(gt_norm.get("gameInfo"), dict) else gt_norm
    seq = (gi or {}).get("actionSequence") if isinstance(gi, dict) else None

    marks: list[dict] = []
    seen: set[str] = set()

    def add_path(raw: Optional[str]) -> None:
        if not raw or raw in ("—",):
            return
        p = _normalize_mark_path(raw)
        if not p or p in seen or "?" in p:
            return
        seen.add(p)
        marks.append({"path": p, "type": "value", "left": None, "right": None})

    for d in diffs:
        p = str(d.get("path") or "")
        m = _ACTION_DIFF_RE.match(p)
        if m:
            seat, street, field = m.group(1), m.group(2), m.group(3)
            nth = None
            if isinstance(seq, list):
                # 用真值里该 seat@street 的对应行动估计 nth
                left = d.get("left")
                action = left if isinstance(left, dict) else {"seat": seat, "street": street}
                nth = seat_street_nth_from_seq(
                    seq, street=street, seat=seat, action=action if isinstance(action, dict) else None
                )
            cell = extract_signal_field(
                signal_br, field=field, street=street, seat=seat, nth=nth
            )
            add_path(cell.get("path"))
            continue

        m = _PLAYER_DIFF_RE.match(p)
        if m:
            seat, field = m.group(1), m.group(2)
            cell = extract_signal_field(signal_br, field=field, seat=seat)
            add_path(cell.get("path"))
            continue

        m = _BLIND_DIFF_RE.match(p)
        if m:
            field = m.group(1)
            cell = extract_signal_field(
                signal_br, field=field, blind_related=field in ("smallBlind", "bigBlind", "ante", "straddle")
            )
            add_path(cell.get("path"))
            continue

        # missing / extra：尽量标出同街同座位行动金额与类型
        left = d.get("left") if isinstance(d.get("left"), dict) else None
        right = d.get("right") if isinstance(d.get("right"), dict) else None
        act = left or right
        if isinstance(act, dict) and act.get("seat") is not None:
            seat, street = act.get("seat"), act.get("street")
            nth = seat_street_nth_from_seq(seq, street=street, seat=seat, action=act) if seq else None
            for field in ("amount", "actionType"):
                cell = extract_signal_field(
                    signal_br, field=field, street=street, seat=seat, nth=nth
                )
                add_path(cell.get("path"))

    return marks


def _chess_mark_diffs_from_gt_diffs(
    chess_display: Any,
    diffs: list[dict],
) -> list[dict]:
    """差异只标在 business.request.fusionCorrectedData 子树内。"""
    from module_pipeline import extract_fusion_corrected_data

    if not diffs or not isinstance(chess_display, dict):
        return []
    fcd = extract_fusion_corrected_data(chess_display)
    if fcd is None:
        return []
    marks = _remap_gto_diffs_onto_payload(diffs, fcd)
    out: list[dict] = []
    for m in marks:
        p = str(m.get("path") or "")
        if not p:
            continue
        if p.startswith("fusionCorrectedData."):
            out.append(m)
        else:
            out.append({**m, "path": f"fusionCorrectedData.{p}"})
    return out


def render_module_json_stack(
    gt_norm: Optional[dict],
    sys_norm: Optional[dict],
    trace_chain: Optional[dict],
) -> str:
    """JSON columns side-by-side（正确值 / 信号 / Chess；已隐藏系统最终）。

    高亮口径：正确值 vs Chess fusionCorrectedData。
    Chess 列展示整份 business.request，粉色仅标在 fusionCorrectedData 子树。
    `sys_norm` 保留入参兼容，不再渲染。
    """
    del sys_norm  # 证据页不再展示系统最终
    # Lazy import: compare_gto_requests imports this module at top level.
    from compare_gto_requests import (
        deep_diff,
        filter_ignorable,
        json_with_value_marks,
        merge_diffs_with_alignment,
    )

    signal_br = layer_business_request(trace_chain, "signal")
    chess_display = layer_chess_display_request(trace_chain)
    chess_norm = chess_norm_for_compare(trace_chain, gt_norm=gt_norm)

    gt_chess_diffs: list[dict] = []
    if gt_norm is not None and chess_norm is not None:
        gt_chess_diffs = filter_ignorable(deep_diff(gt_norm, chess_norm))
        gt_chess_diffs = merge_diffs_with_alignment(gt_norm, chess_norm, gt_chess_diffs)

    gt_html = None
    if gt_norm is not None and gt_chess_diffs:
        gt_html = json_with_value_marks(gt_norm, gt_chess_diffs, "left")
    elif gt_norm is not None:
        gt_html = json_with_value_marks(gt_norm, [], "left")

    signal_html = None
    if signal_br is not None and gt_chess_diffs:
        sig_marks = _signal_mark_diffs_from_gt_diffs(signal_br, gt_norm, gt_chess_diffs)
        signal_html = json_with_value_marks(signal_br, sig_marks, "right")
    elif signal_br is not None:
        signal_html = json_with_value_marks(signal_br, [], "right")

    chess_html = None
    if chess_display is not None and gt_chess_diffs:
        chess_marks = _chess_mark_diffs_from_gt_diffs(chess_display, gt_chess_diffs)
        chess_html = json_with_value_marks(chess_display, chess_marks, "right")
    elif chess_display is not None:
        chess_html = json_with_value_marks(chess_display, [], "right")

    parts = [
        _json_pre_block("正确值", gt_norm, html_body=gt_html, open_default=True),
        _json_pre_block("信号引擎", signal_br, html_body=signal_html, open_default=True),
        _json_pre_block("Chess API", chess_display, html_body=chess_html, open_default=True),
    ]
    note = ""
    if not trace_chain:
        note = '<p class="xmod-empty">无 Trace 链数据；进入页后会拉取 Chess 再对照。</p>'
    elif chess_norm is None:
        note = '<p class="xmod-empty">Chess API 无 fusionCorrectedData（无值）；下方仍展示正确值与信号引擎。</p>'
    return (
        '<div class="mod-json-stack" id="live-mod-json-stack">'
        '<div class="mod-json-toolbar">'
        '<div class="pane-label">完整 JSON（3 列并排 · 正确值 vs Chess · 默认全展开 · Chess 展示整份 business.request，仅高亮 fusionCorrectedData 内差异）</div>'
        '<button type="button" class="mod-json-toggle" data-expanded="1">全部收起</button>'
        "</div>"
        f"{note}"
        f'<div class="mod-json-row">{"".join(parts)}</div>'
        "</div>"
    )


def render_shot_carousel(
    shots: list[dict],
    start_index: int = 0,
    hint: str = "",
    note: str = "",
) -> str:
    """Hand-first-frame default; left/right browse consecutive original frames."""
    if not shots:
        return '<div class="no-shot">无截图</div>'
    start = max(0, min(int(start_index or 0), len(shots) - 1))
    # Lightweight: one <img> + JSON frame list (lazy load), supports large neighbor windows
    payload = [
        {
            "rel": s.get("rel") or "",
            "ts": s.get("ts"),
            "name": s.get("name") or "",
        }
        for s in shots
    ]
    frames_json = html.escape(json.dumps(payload, ensure_ascii=False), quote=True)
    label = (
        f"牌桌截图（佐证） · 第 <span class='shot-cur'>{start + 1}</span>/{len(shots)} 帧"
        f" · 默认牌局首帧"
    )
    if hint:
        label += f" · {esc(hint)}"
    label += " · ← → / 滑动切换 · 默认放大"
    return f"""
<div class="pane-label">{label}</div>
<div class="shot-carousel shot-compact is-zoomed" data-home="{start}" data-start="{start}" data-count="{len(shots)}" data-frames="{frames_json}" tabindex="0" role="region" aria-label="截图浏览，可用左右方向键切换">
  <div class="shot-viewport">
    <button type="button" class="shot-nav shot-prev" aria-label="上一帧">‹</button>
    <button type="button" class="shot-nav shot-next" aria-label="下一帧">›</button>
    <span class="shot-badge shot-badge-first">牌局首帧</span>
    <img class="shot-main" src="{esc(shots[start].get('rel') or '')}" alt="table shot" draggable="false"/>
  </div>
  <div class="shot-toolbar">
    <button type="button" class="shot-home">回到牌局首帧</button>
    <button type="button" class="shot-zoom" aria-pressed="true">缩小</button>
    <input type="range" class="shot-scrub" min="0" max="{len(shots) - 1}" value="{start}" aria-label="拖动浏览帧"/>
  </div>
</div>
<div class="shot-note">{esc(note)}</div>
"""


def render_evidence_card(
    side_name: str,
    exact: Optional[bool],
    friendly: list[str],
    img_rel: Optional[str],
    gt_norm: Optional[dict],
    sys_norm: Optional[dict],
    pick_meta: dict,
    all_diffs: Optional[list] = None,
    categories: Optional[list] = None,
    default_open: bool = True,
    shot_gallery: Optional[list] = None,
    shot_start: int = 0,
    trace_chain: Optional[dict] = None,
) -> str:
    """证据卡。`sys_norm` 现为对照侧（Chess 规范化报文），非系统最终。"""
    # 优先用页内 Trace 的 Chess；无则用传入的对照侧
    compare_right = chess_norm_for_compare(trace_chain, gt_norm=gt_norm) or sys_norm
    mismatch = first_action_mismatch(gt_norm, compare_right)
    diffs = list(all_diffs or [])
    hint = seat_hint(mismatch)
    blocks = build_issue_blocks(gt_norm, compare_right)

    if not blocks and diffs:
        for d in diffs:
            blocks.append(
                {
                    "title": d.get("category") or "字段差异",
                    "kind": d.get("category") or "其他",
                    "rows": [
                        {
                            "field": d.get("path") or "",
                            "gt": d.get("left"),
                            "sys": d.get("right"),
                            "diff": True,
                        }
                    ],
                    "mismatch": None,
                }
            )

    open_attr = " open" if default_open else ""
    gallery = list(shot_gallery or [])
    if not gallery and img_rel:
        gallery = [{"rel": img_rel, "label": "问题帧"}]
        shot_start = 0

    def wrap(status_html: str, summary_extra: str, inner: str) -> str:
        return f"""
<details class="evidence-fold"{open_attr}>
  <summary class="evidence-summary">
    <span class="evidence-summary-title">{esc(side_name)} vs 正确值</span>
    {status_html}
    <span class="evidence-summary-extra">{esc(summary_extra)}</span>
  </summary>
  <div class="evidence-body">{inner}</div>
</details>
"""

    if compare_right is None and exact is None:
        # 无 Chess 时仍展示正确值 / 信号 / 锚点 / 截图；文案用「无值」而非「待拉取」
        status = '<span class="badge muted">Chess API 无值</span>'
        banner = (
            '<p class="xmod-empty" id="live-chess-missing-banner">'
            "Chess API 无 fusionCorrectedData（无值），无法与正确值对照。"
            "下方仍展示正确值与已有 Trace；可点「更新数据」重试。"
            "</p>"
        )
        issue_list = (
            '<div class="issue-picks" id="live-issue-picks" aria-label="差异列表">'
            '<p class="xmod-empty">Chess API 无值，暂无对照差异。正确值见下方完整 JSON。</p>'
            "</div>"
        )
        json_stack = render_module_json_stack(gt_norm, None, trace_chain)
        anchor_strip = render_module_anchor_strip(trace_chain)
        shot_html = (
            render_shot_carousel(gallery, shot_start, "", pick_meta.get("reason") or "")
            if gallery
            else '<div class="no-shot">无截图</div>'
        )
        body = f"""
  {banner}
  <div class="evidence-grid">
    <div class="diff-pane">
      <div class="pane-label" id="live-diff-pane-label">差异清单 · Chess API 无值 · 点击展开详单</div>
      <div class="glance">Chess API 无值</div>
      {anchor_strip}
      {issue_list}
      {json_stack}
    </div>
    <div class="shot-pane shot-pane-sm is-zoomed">
      {shot_html}
    </div>
  </div>
"""
        return wrap(status, "正确值已展示 · Chess 无对照", body)

    if exact is True or (exact is None and compare_right is not None and not blocks and not diffs):
        status = '<span class="badge ok">与正确值一致</span>'
        body = f"<p>{esc(side_name)}与正确值一致，无需纠错证据。</p>"
        if gallery:
            body += (
                f'<div class="evidence-grid">'
                f'<div class="diff-pane"><div class="pane-label">结论</div>'
                f'<div class="glance ok-glance">与正确值一致</div></div>'
                f'<div class="shot-pane shot-pane-sm is-zoomed">'
                f'{render_shot_carousel(gallery, shot_start, "", pick_meta.get("reason") or "")}'
                f'</div></div>'
            )
        return wrap(status, "可展开查看", body)

    if exact is None and compare_right is None:
        status = '<span class="badge muted">无对照</span>'
        return wrap(status, "缺少可对比报文", "<p>缺少可对比报文。</p>")

    status = '<span class="badge bad">不一致</span>'
    shot_html = render_shot_carousel(
        gallery, shot_start, hint, pick_meta.get("reason") or ""
    )

    n = len(blocks)
    issue_list = render_issue_picks_html(
        gt_norm, compare_right, trace_chain, blocks=blocks
    )
    json_stack = render_module_json_stack(gt_norm, None, trace_chain)
    anchor_strip = render_module_anchor_strip(trace_chain)

    inner = f"""
  <div class="evidence-grid">
    <div class="diff-pane">
      <div class="pane-label" id="live-diff-pane-label">差异清单 · 共 {n} 处 · 点击展开详单</div>
      {anchor_strip}
      {issue_list}
      {json_stack}
    </div>
    <div class="shot-pane shot-pane-sm is-zoomed">
      {shot_html}
    </div>
  </div>
"""
    return wrap(status, f"共 {n} 处差异", inner)


def render_issue_picks_html(
    gt_norm: Optional[dict],
    sys_norm: Optional[dict],
    trace_chain: Optional[dict],
    *,
    blocks: Optional[list[dict]] = None,
) -> str:
    """差异折叠列表（含 live-xmod），供证据卡与 live 刷新共用。"""
    if blocks is None:
        blocks = (
            build_issue_blocks(gt_norm, sys_norm)
            if gt_norm is not None and sys_norm is not None
            else []
        )
    anomaly_html = render_anchor_anomaly_banner(trace_chain)
    accordion_items: list[str] = []
    for i, b in enumerate(blocks):
        xrows = build_cross_module_rows(
            b, gt_norm=gt_norm, sys_norm=sys_norm, trace_chain=trace_chain
        )
        line = compact_issue_line(b)
        kind = str(b.get("kind") or "")
        accordion_items.append(
            f'<details class="issue-acc" data-issue-kind="{esc(kind)}">'
            f'<summary class="issue-acc-sum">'
            f'<span class="issue-idx">{i + 1}</span>'
            f'<span class="issue-pick-text">{esc(line)}</span>'
            f"</summary>"
            f'<div class="issue-acc-body" data-issue-idx="{i}" data-issue-kind="{esc(kind)}">'
            f'<div class="pane-label">跨模块对照（路径=值）</div>'
            f'<div class="live-xmod" data-issue-idx="{i}" data-issue-kind="{esc(kind)}">'
            f"{render_cross_module_table(xrows, trace_chain=trace_chain, include_anchor_strip=False)}"
            f"</div>"
            f"</div>"
            f"</details>"
        )
    return (
        f'<div class="issue-picks" id="live-issue-picks" aria-label="差异列表">'
        f"{anomaly_html}"
        f'{"".join(accordion_items) or "<p>无可展示差异</p>"}'
        f"</div>"
    )


EVIDENCE_JS = """
(function(){
  var activeCarousel = null;
  function parseFrames(root){
    try {
      var raw = root.getAttribute('data-frames') || '[]';
      return JSON.parse(raw);
    } catch (e) { return []; }
  }
  function frameName(f){
    if (!f) return '';
    var raw = '';
    if (f.name) raw = String(f.name);
    else {
      var rel = String(f.rel || '');
      if (!rel) return '';
      try {
        var path = rel.split('?')[0];
        raw = decodeURIComponent(path.split('/').pop() || '');
      } catch (e) { raw = ''; }
    }
    var m = String(raw).match(/^[A-Za-z0-9._-]+\.(?:jpg|jpeg|png|webp|gif)/i)
      || String(raw).match(/[A-Za-z0-9._-]+\.(?:jpg|jpeg|png|webp|gif)/i);
    return m ? m[0] : '';
  }
  function frameSrc(f){
    var name = frameName(f);
    // 经本机/内网 HTTP 服务打开时，走 /local-shot，同事也能看图
    if (name && (location.protocol === 'http:' || location.protocol === 'https:')) {
      return location.origin + '/local-shot/' + encodeURIComponent(name);
    }
    return (f && f.rel) || '';
  }
  function initCarousel(root){
    var frames = parseFrames(root);
    var img = root.querySelector('.shot-main');
    var badge = root.querySelector('.shot-badge-first');
    var scrub = root.querySelector('.shot-scrub');
    var home = root.querySelector('.shot-home');
    var zoom = root.querySelector('.shot-zoom');
    var curEl = root.parentElement && root.parentElement.querySelector('.shot-cur');
    var homeIndex = parseInt(root.getAttribute('data-home') || root.getAttribute('data-start') || '0', 10) || 0;
    var i = homeIndex;
    if (!frames.length || !img) return;
    root.setAttribute('tabindex', '0');
    root.setAttribute('role', 'region');
    root.setAttribute('aria-label', '截图浏览，可用左右方向键切换');
    function show(n){
      if (!frames.length) return;
      i = (n + frames.length) % frames.length;
      var f = frames[i] || {};
      var src = frameSrc(f);
      if (src) img.src = src;
      if (curEl) curEl.textContent = String(i + 1);
      if (scrub) scrub.value = String(i);
      if (badge) badge.style.display = (i === homeIndex) ? '' : 'none';
      root.setAttribute('data-start', String(i));
    }
    function activate(){ activeCarousel = root; }
    root.addEventListener('pointerdown', activate);
    root.addEventListener('mouseenter', activate);
    root.addEventListener('focus', activate);
    root._shotShow = show;
    root._shotStep = function(dir){ show(i + dir); };
    var prev = root.querySelector('.shot-prev');
    var next = root.querySelector('.shot-next');
    if (prev) prev.addEventListener('click', function(e){ e.preventDefault(); e.stopPropagation(); activate(); show(i - 1); });
    if (next) next.addEventListener('click', function(e){ e.preventDefault(); e.stopPropagation(); activate(); show(i + 1); });
    if (home) home.addEventListener('click', function(e){ e.preventDefault(); activate(); show(homeIndex); });
    if (zoom) zoom.addEventListener('click', function(e){
      e.preventDefault(); activate();
      var on = root.classList.toggle('is-zoomed');
      var pane = root.closest('.shot-pane');
      if (pane) pane.classList.toggle('is-zoomed', on);
      zoom.setAttribute('aria-pressed', on ? 'true' : 'false');
      zoom.textContent = on ? '缩小' : '拉大';
    });
    // 默认放大：同步父级 pane
    if (root.classList.contains('is-zoomed')) {
      var pane0 = root.closest('.shot-pane');
      if (pane0) pane0.classList.add('is-zoomed');
      if (zoom) {
        zoom.setAttribute('aria-pressed', 'true');
        zoom.textContent = '缩小';
      }
    }
    if (scrub) scrub.addEventListener('input', function(){ activate(); show(parseInt(scrub.value || '0', 10) || 0); });
    var startX = 0, dx = 0, tracking = false;
    var vp = root.querySelector('.shot-viewport');
    if (!vp) return;
    vp.addEventListener('touchstart', function(e){
      if (!e.touches || !e.touches.length) return;
      activate();
      tracking = true; startX = e.touches[0].clientX; dx = 0;
    }, {passive: true});
    vp.addEventListener('touchmove', function(e){
      if (!tracking || !e.touches || !e.touches.length) return;
      dx = e.touches[0].clientX - startX;
    }, {passive: true});
    vp.addEventListener('touchend', function(){
      if (!tracking) return;
      tracking = false;
      if (Math.abs(dx) > 40) show(i + (dx < 0 ? 1 : -1));
      dx = 0;
    });
    var down = false, mx0 = 0, mdx = 0;
    vp.addEventListener('mousedown', function(e){
      if (e.target && e.target.closest && e.target.closest('.shot-nav')) return;
      activate();
      down = true; mx0 = e.clientX; mdx = 0; e.preventDefault();
    });
    window.addEventListener('mousemove', function(e){
      if (!down) return; mdx = e.clientX - mx0;
    });
    window.addEventListener('mouseup', function(){
      if (!down) return; down = false;
      if (Math.abs(mdx) > 50) show(i + (mdx < 0 ? 1 : -1));
      mdx = 0;
    });
    show(i);
  }
  document.querySelectorAll('.shot-carousel').forEach(initCarousel);
  document.addEventListener('keydown', function(e){
    if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
    var tag = (e.target && e.target.tagName) ? e.target.tagName.toLowerCase() : '';
    if (tag === 'input' || tag === 'textarea' || tag === 'select' || (e.target && e.target.isContentEditable)) return;
    var root = activeCarousel;
    if (!root || !document.body.contains(root)) {
      root = document.querySelector('.evidence-fold[open] .shot-carousel') ||
             document.querySelector('.shot-carousel');
    }
    if (!root || !root._shotStep) return;
    e.preventDefault();
    root._shotStep(e.key === 'ArrowLeft' ? -1 : 1);
    try { root.focus({preventScroll: true}); } catch (err) { root.focus(); }
  });

  document.querySelectorAll('.mod-json-toggle').forEach(function(btn){
    btn.addEventListener('click', function(e){
      e.preventDefault();
      e.stopPropagation();
      var stack = btn.closest('.mod-json-stack');
      if (!stack) return;
      var blocks = stack.querySelectorAll('.mod-json-block');
      var expand = btn.getAttribute('data-expanded') !== '1';
      blocks.forEach(function(d){
        if (expand) d.setAttribute('open', '');
        else d.removeAttribute('open');
      });
      btn.setAttribute('data-expanded', expand ? '1' : '0');
      btn.textContent = expand ? '全部收起' : '全部展开';
    });
  });

  function bindModJsonCopy(root){
    (root || document).querySelectorAll('.mod-json-copy').forEach(function(btn){
      if (btn._copyBound) return;
      btn._copyBound = true;
      btn.addEventListener('click', function(e){
        e.preventDefault();
        e.stopPropagation();
        var card = btn.closest('.mod-json-card') || btn.closest('.mod-json-block');
        var pre = card ? card.querySelector('.mod-json-pre') : null;
        var text = pre ? String(pre.textContent || '') : '';
        function done(ok){
          btn.classList.toggle('is-copied', !!ok);
          btn.setAttribute('title', ok ? '已复制' : '复制失败');
          // 按钮文案保持「复制」，不消失、不改成别的长期状态
          setTimeout(function(){
            btn.classList.remove('is-copied');
            btn.setAttribute('title', '复制本列 JSON');
          }, 1200);
        }
        if (!text) { done(false); return; }
        function fallback(){
          try {
            var ta = document.createElement('textarea');
            ta.value = text; document.body.appendChild(ta); ta.select();
            done(document.execCommand('copy')); document.body.removeChild(ta);
          } catch (err) { done(false); }
        }
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(function(){ done(true); }).catch(fallback);
        } else fallback();
      });
    });
  }
  bindModJsonCopy(document);
})();
"""


LIVE_TRACE_JS = """
(function(){
  var el = document.getElementById('live-trace-payload');
  if (!el) return;
  var payload;
  try { payload = JSON.parse(el.textContent || '{}'); }
  catch (e) { return; }
  if (!payload || !payload.hand_uid) return;

  var q = payload.query || {};
  var apiBase = String(q.api || '').replace(/\\/$/, '');
  var traceEnv = String(q.trace_env || 'uat').trim() || 'uat';
  var cards = String(q.cards || payload.cards || payload.hole_key || '').trim();
  var startTime = String(q.start_time || '').trim();
  var endTime = String(q.end_time || '').trim();
  var padMin = parseInt(q.pad_minutes || 15, 10) || 15;
  var centerMs = q.center_ms != null ? Number(q.center_ms) : null;
  var refreshing = false;
  var statusEl = document.getElementById('live-refresh-status');
  var btnEl = document.getElementById('live-refresh-btn');

  function pad2(n){ return (n < 10 ? '0' : '') + n; }
  function msToApi(ms){
    var d = new Date(ms);
    if (isNaN(d.getTime())) return '';
    return d.getFullYear() + '-' + pad2(d.getMonth()+1) + '-' + pad2(d.getDate())
      + ' ' + pad2(d.getHours()) + ':' + pad2(d.getMinutes()) + ':' + pad2(d.getSeconds());
  }
  function normalizeApiTime(s){
    s = String(s || '').trim().replace(/\\//g, '-').replace(/T/g, ' ');
    s = s.replace(/\\s+/g, ' ').trim();
    var m = s.match(/^(\\d{4}-\\d{2}-\\d{2})(\\d{2}:\\d{2}(?::\\d{2})?(?:\\.\\d+)?)$/);
    if (m) s = m[1] + ' ' + m[2];
    if (/^\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}$/.test(s)) s += ':00';
    return s;
  }
  function looksValidApiTime(s){
    return /^\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}/.test(String(s || ''));
  }
  function ensureWindow(){
    startTime = normalizeApiTime(startTime);
    endTime = normalizeApiTime(endTime);
    if (!looksValidApiTime(startTime) || !looksValidApiTime(endTime)) {
      if (centerMs && !isNaN(centerMs)) {
        var pad = padMin * 60 * 1000;
        startTime = msToApi(centerMs - pad);
        endTime = msToApi(centerMs + pad);
      }
    }
    if (q) {
      q.start_time = startTime;
      q.end_time = endTime;
    }
  }
  function setStatus(msg, kind){
    if (!statusEl) return;
    statusEl.textContent = msg || '';
    statusEl.classList.remove('is-ok', 'is-err');
    if (kind === 'ok') statusEl.classList.add('is-ok');
    if (kind === 'err') statusEl.classList.add('is-err');
  }
  function pageBases(){
    var out = [], seen = {};
    function add(b){
      b = String(b || '').replace(/\\/$/, '');
      if (!b || seen[b]) return;
      seen[b] = 1;
      out.push(b);
    }
    try {
      if (location.protocol === 'http:' || location.protocol === 'https:') add(location.origin);
    } catch (e) {}
    add('http://127.0.0.1:8766');
    add('http://localhost:8766');
    add('http://127.0.0.1:8765');
    add('http://localhost:8765');
    return out;
  }
  function persistPayload(){
    try { el.textContent = JSON.stringify(payload); } catch (e) {}
  }

  function openIds(){
    var out = [], seen = {};
    function add(s){
      s = String(s || '').trim();
      if (s && !seen[s]) { seen[s] = 1; out.push(s); }
    }
    add(q.open_id);
    add(q.fallback_open_id);
    add(payload.user_token);
    if (!out.length) out.push('');
    return out;
  }

  function holeVariants(hc){
    var out = [], seen = {};
    function add(s){
      s = String(s || '').trim();
      if (s && !seen[s]) { seen[s] = 1; out.push(s); }
    }
    add(hc);
    var compact = String(hc || '').replace(/[^A-Za-z0-9]/g, '');
    if (compact && compact.length % 2 === 0 && compact.length >= 4) {
      var parts = [];
      for (var i = 0; i < compact.length; i += 2) parts.push(compact.slice(i, i + 2));
      add(parts.join(','));
      add(compact);
    }
    return out.length ? out : [''];
  }

  function proxyEndpoints(){
    return pageBases().map(function(b){ return b + '/api/trace-query'; });
  }

  function fetchViaApi(params){
    if (!apiBase) return Promise.reject(new Error('无 Trace API'));
    var qp = new URLSearchParams();
    if (params.openId) qp.set('openId', params.openId);
    if (params.holeCards) qp.set('holeCards', params.holeCards);
    if (params.startTime) qp.set('startTime', params.startTime);
    if (params.endTime) qp.set('endTime', params.endTime);
    return fetch(apiBase + '/api/v1/traceQuery?' + qp.toString()).then(function(r){
      return r.json().then(function(j){
        if (!r.ok || j.success === false) throw new Error(j.message || ('HTTP ' + r.status));
        return j.result || [];
      });
    });
  }

  function fetchViaProxy(params){
    var urls = proxyEndpoints();
    var i = 0;
    var lastErr = null;
    function next(){
      if (i >= urls.length) {
        return Promise.reject(lastErr || new Error('本地代理不可用'));
      }
      var url = urls[i++];
      return fetch(url, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          traceEnv: params.traceEnv || traceEnv,
          openId: params.openId || '',
          holeCards: params.holeCards || '',
          startTime: params.startTime || '',
          endTime: params.endTime || ''
        })
      }).then(function(r){
        return r.json().then(function(j){
          if (!r.ok || j.ok === false) {
            throw new Error((j && (j.error || j.message)) || ('HTTP ' + r.status));
          }
          return j.result || j.spans || [];
        });
      }).catch(function(e){
        lastErr = e;
        return next();
      });
    }
    return next();
  }

  function fetchTraces(params){
    // 与 Trace Viewer 一致：优先直连 data-platform；失败再回退本地代理
    return fetchViaApi(params).catch(function(){
      return fetchViaProxy(params);
    });
  }

  function fetchSpansBrowser(){
    ensureWindow();
    var oids = openIds();
    var variants = holeVariants(cards);
    var tried = [];
    var oi = 0;

    function tryOpenId(){
      if (oi >= oids.length) {
        return Promise.resolve({
          spans: [],
          open_id: oids[0] || '',
          hole_cards_used: cards,
          start_time: startTime,
          end_time: endTime,
          tried: tried,
          error: '无匹配 span'
        });
      }
      var oid = oids[oi++];
      var vi = 0;

      function tryVariant(){
        if (vi >= variants.length) {
          // 禁止无 holeCards 兜底，避免整窗其它手牌污染本局分析
          return tryOpenId();
        }
        var hc = variants[vi++];
        tried.push((oid || '(no-openId)') + '|' + (hc || '(empty-cards)'));
        return fetchTraces({
          openId: oid, holeCards: hc, startTime: startTime, endTime: endTime
        }).then(function(spans){
          if (spans && spans.length) {
            return {
              spans: spans, open_id: oid, hole_cards_used: hc,
              start_time: startTime, end_time: endTime, tried: tried, error: null
            };
          }
          return tryVariant();
        }).catch(function(err){
          tried.push('proxy-error:' + String((err && err.message) || err));
          return tryVariant();
        });
      }
      return tryVariant();
    }
    return tryOpenId();
  }

  function renderEndpoints(){
    return pageBases().map(function(b){ return b + '/render-hand-trace'; });
  }

  function gtNormEndpoints(){
    var qs = 'hand_uid=' + encodeURIComponent(payload.hand_uid || '');
    if (payload.gt_version_id) qs += '&version_id=' + encodeURIComponent(payload.gt_version_id);
    return pageBases().map(function(b){ return b + '/api/hand-gt-norm?' + qs; });
  }

  function fetchFreshGt(){
    var urls = gtNormEndpoints();
    var i = 0;
    var lastErr = null;
    function next(){
      if (i >= urls.length) {
        return Promise.reject(lastErr || new Error('无法拉取正确值'));
      }
      var url = urls[i++];
      return fetch(url).then(function(r){
        return r.json().then(function(j){
          if (!r.ok || !j || j.ok === false || !j.gt_norm) {
            throw new Error((j && j.error) || ('HTTP ' + r.status));
          }
          return j;
        });
      }).catch(function(e){
        lastErr = e;
        return next();
      });
    }
    return next().then(function(j){
      payload.gt_norm = j.gt_norm;
      if (j.version_id) payload.gt_version_id_used = j.version_id;
      persistPayload();
      return j;
    });
  }

  function bindJsonControls(root){
    var scope = root || document;
    scope.querySelectorAll('.mod-json-toggle').forEach(function(btn){
      if (btn._liveBound) return;
      btn._liveBound = true;
      btn.addEventListener('click', function(e){
        e.preventDefault();
        e.stopPropagation();
        var st = btn.closest('.mod-json-stack');
        if (!st) return;
        var blocks = st.querySelectorAll('.mod-json-block');
        var expand = btn.getAttribute('data-expanded') !== '1';
        blocks.forEach(function(d){
          if (expand) d.setAttribute('open', '');
          else d.removeAttribute('open');
        });
        btn.setAttribute('data-expanded', expand ? '1' : '0');
        btn.textContent = expand ? '全部收起' : '全部展开';
      });
    });
    scope.querySelectorAll('.mod-json-copy').forEach(function(btn){
      if (btn._copyBound) return;
      btn._copyBound = true;
      btn.addEventListener('click', function(e){
        e.preventDefault();
        e.stopPropagation();
        var card = btn.closest('.mod-json-card') || btn.closest('.mod-json-block');
        var pre = card ? card.querySelector('.mod-json-pre') : null;
        var text = pre ? String(pre.textContent || '') : '';
        function done(ok){
          btn.classList.toggle('is-copied', !!ok);
          btn.setAttribute('title', ok ? '已复制' : '复制失败');
          setTimeout(function(){
            btn.classList.remove('is-copied');
            btn.setAttribute('title', '复制本列 JSON');
          }, 1200);
        }
        if (!text) { done(false); return; }
        function fallback(){
          try {
            var ta = document.createElement('textarea');
            ta.value = text; document.body.appendChild(ta); ta.select();
            done(document.execCommand('copy')); document.body.removeChild(ta);
          } catch (err) { done(false); }
        }
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(function(){ done(true); }).catch(fallback);
        } else fallback();
      });
    });
  }

  function ensureEvidenceScaffold(){
    var foldBody = document.querySelector('.evidence-fold .evidence-body');
    if (!foldBody) return;
    if (document.getElementById('live-issue-picks') && document.getElementById('live-mod-json-stack')) {
      return;
    }
    var shot = foldBody.querySelector('.shot-pane');
    var shotHtml = shot ? shot.outerHTML : '<div class="shot-pane shot-pane-sm is-zoomed"></div>';
    foldBody.innerHTML =
      '<div class="evidence-grid">'
      + '<div class="diff-pane">'
      + '<div class="pane-label" id="live-diff-pane-label">差异清单 · 点击展开详单</div>'
      + '<div class="issue-picks" id="live-issue-picks" aria-label="差异列表"></div>'
      + '<div class="mod-json-stack" id="live-mod-json-stack"></div>'
      + '</div>'
      + shotHtml
      + '</div>';
  }

  function applyResult(data){
    if (!data) return;
    ensureEvidenceScaffold();
    if (data.anchor_strip_html) {
      var tmpStrip = document.createElement('div');
      tmpStrip.innerHTML = data.anchor_strip_html;
      var neuStrip = tmpStrip.firstElementChild;
      if (neuStrip) {
        var strip = document.getElementById('live-mod-anchor-strip');
        if (strip) {
          strip.replaceWith(neuStrip);
        } else {
          document.querySelectorAll('.diff-pane > .pane-label').forEach(function(label){
            if ((label.textContent || '').indexOf('差异清单') < 0) return;
            if (label.nextElementSibling && label.nextElementSibling.id === 'live-mod-anchor-strip') return;
            label.insertAdjacentElement('afterend', neuStrip.cloneNode(true));
          });
        }
      }
    }
    var stack = document.getElementById('live-mod-json-stack');
    if (stack && data.json_stack_html) {
      var tmp = document.createElement('div');
      tmp.innerHTML = data.json_stack_html;
      var neu = tmp.firstElementChild;
      if (neu) stack.replaceWith(neu);
    }
    if (data.issues_html) {
      var picks = document.getElementById('live-issue-picks');
      if (picks) {
        var tmpP = document.createElement('div');
        tmpP.innerHTML = data.issues_html;
        var neuP = tmpP.firstElementChild;
        if (neuP) picks.replaceWith(neuP);
      }
    } else {
      var tables = data.issue_tables || [];
      document.querySelectorAll('.live-xmod[data-issue-idx]').forEach(function(node){
        var i = parseInt(node.getAttribute('data-issue-idx') || '-1', 10);
        if (i < 0 || !tables[i]) return;
        node.innerHTML = tables[i];
      });
    }
    if (data.diff_n != null || data.exact === null) {
      var paneLabel = document.getElementById('live-diff-pane-label');
      var prefix = payload.hand_title_prefix || ((payload.hand_uid || '') + ' Chess API vs 正确值');
      var title;
      if (data.exact === true) {
        title = prefix + ' · 0 处差异';
        if (paneLabel) paneLabel.textContent = '差异清单 · 共 0 处 · 点击展开详单';
      } else if (data.exact === false) {
        title = prefix + ' · ' + data.diff_n + ' 处差异';
        if (paneLabel) paneLabel.textContent = '差异清单 · 共 ' + data.diff_n + ' 处 · 点击展开详单';
      } else {
        title = prefix + ' · Chess API 无值';
        if (paneLabel) paneLabel.textContent = '差异清单 · Chess API 无值 · 点击展开详单';
      }
      var h1 = document.querySelector('h1');
      if (h1) h1.textContent = title;
      try { document.title = title; } catch (e) {}
      var fold = document.querySelector('.evidence-fold');
      if (fold) {
        var sumTitle = fold.querySelector('.evidence-summary-title');
        if (sumTitle) sumTitle.textContent = 'Chess API vs 正确值';
        var badge = fold.querySelector('.badge');
        var extra = fold.querySelector('.evidence-summary-extra');
        if (data.exact === true) {
          if (badge) { badge.className = 'badge ok'; badge.textContent = '与正确值一致'; }
          if (extra) extra.textContent = '可展开查看';
        } else if (data.exact === false) {
          if (badge) { badge.className = 'badge bad'; badge.textContent = '不一致'; }
          if (extra) extra.textContent = '共 ' + data.diff_n + ' 处差异';
        } else {
          if (badge) { badge.className = 'badge muted'; badge.textContent = 'Chess API 无值'; }
          if (extra) extra.textContent = '正确值已展示 · Chess 无对照';
        }
      }
      var glance = document.querySelector('.evidence-body .glance');
      if (glance && data.exact !== true && data.exact !== false) {
        glance.textContent = 'Chess API 无值';
        glance.classList.remove('ok-glance');
      }
      var missBanner = document.getElementById('live-chess-missing-banner');
      if (missBanner && data.exact !== true && data.exact !== false) {
        missBanner.textContent = 'Chess API 无 fusionCorrectedData（无值），无法与正确值对照。下方仍展示正确值与已有 Trace；可点「更新数据」重试。';
      }
    }
    if (data.street_compare_html) {
      var street = document.getElementById('live-street-compare');
      if (street) street.innerHTML = data.street_compare_html;
    }
    bindJsonControls(document);
  }

  function postRender(fetched){
    var urls = renderEndpoints();
    var i = 0;
    var lastErr = null;
    function next(){
      if (i >= urls.length) {
        return Promise.reject(lastErr || new Error('渲染服务不可用'));
      }
      var body = {
        hand_uid: payload.hand_uid,
        hole_key: payload.hole_key || cards,
        cards: fetched.hole_cards_used || cards,
        cards_used: fetched.hole_cards_used || cards,
        open_id_used: fetched.open_id,
        user_token: payload.user_token || '',
        gt_norm: payload.gt_norm,
        sys_norm: payload.sys_norm,
        old_norm: payload.old_norm || null,
        query: q,
        spans: fetched.spans || [],
        fetch_meta: fetched
      };
      var url = urls[i++];
      return fetch(url, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(body)
      }).then(function(res){
        return res.json().then(function(data){
          if (!res.ok && (!data || data.ok === false)) {
            throw new Error((data && data.error) || ('HTTP ' + res.status));
          }
          return data;
        });
      }).catch(function(e){
        lastErr = e;
        return next();
      });
    }
    return next();
  }

  function refreshAll(){
    if (refreshing) return;
    refreshing = true;
    if (btnEl) btnEl.disabled = true;
    setStatus('正在拉取正确值与 Trace…', '');
    var gtNote = '';
    fetchFreshGt().catch(function(err){
      gtNote = '正确值未更新（' + String((err && err.message) || err) + '）；';
      return null;
    }).then(function(){
      return fetchSpansBrowser();
    }).then(function(fetched){
      return postRender(fetched).then(function(data){
        applyResult(data);
        var spanN = (fetched && fetched.spans && fetched.spans.length) || 0;
        var tip = gtNote + '已更新 · Trace ' + spanN + ' spans · ' + new Date().toLocaleTimeString();
        setStatus(tip, gtNote ? 'err' : 'ok');
      });
    }).catch(function(err){
      setStatus('更新失败：' + String((err && err.message) || err), 'err');
    }).then(function(){
      refreshing = false;
      if (btnEl) btnEl.disabled = false;
    });
  }

  if (btnEl) {
    btnEl.addEventListener('click', function(e){
      e.preventDefault();
      refreshAll();
    });
  }
  // 进入页 / 浏览器刷新 / bfcache 返回：一律重拉正确值 + Trace
  window.addEventListener('pageshow', function(){ refreshAll(); });
})();
"""


_LIVE_HAND_SCRIPT_RE = re.compile(
    r'(<script\b[^>]*\bid=["\']live-trace-payload["\'][^>]*>.*?</script>\s*)'
    r"<script\b[^>]*>.*?</script>",
    re.IGNORECASE | re.DOTALL,
)
_NAV_BACK_RE = re.compile(
    r'(<div class="nav">\s*<a\b[^>]*>\s*←\s*返回\s*</a>)',
    re.IGNORECASE,
)


def inject_live_hand_refresh(html: str) -> str:
    """为已生成的证据页注入「更新数据」按钮、锚点 id，并替换为最新 live Trace/GT 脚本。"""
    if not html or "live-trace-payload" not in html:
        return html

    # 文案纠偏：无 fusionCorrectedData 是「无值」，不是「待拉取」
    if "待拉取" in html or "尚未取到 Chess" in html or "待补 Chess" in html:
        repls = [
            ("待拉取 Chess Trace 后对照行动序列", "Chess API 无值，暂无法对照行动序列"),
            ("待拉取 Chess Trace", "Chess API 无值"),
            ("差异清单 · 待拉取 Chess", "差异清单 · Chess API 无值"),
            ("· 待拉取 Chess", "· Chess API 无值"),
            ("· 待拉取 Trace", "· Chess API 无值"),
            (">待拉取 Chess<", ">Chess API 无值<"),
            ("正确值已展示 · 待补 Chess", "正确值已展示 · Chess 无对照"),
            (
                "尚未取到 Chess API（fusionCorrectedData）。下方仍展示正确值与已拉到的 Trace；进入页或点「更新数据」后将补 Chess 对照。",
                "Chess API 无 fusionCorrectedData（无值），无法与正确值对照。下方仍展示正确值与已有 Trace；可点「更新数据」重试。",
            ),
            (
                "尚未取到 Chess API（fusionCorrectedData）。进入页或点「更新数据」后将按正确值 vs Chess 对照。",
                "Chess API 无 fusionCorrectedData（无值），无法与正确值对照。下方仍展示正确值与已有 Trace；可点「更新数据」重试。",
            ),
            ("Chess 未到位，暂无对照差异", "Chess API 无值，暂无对照差异"),
            ("未取到 Chess fusionCorrectedData", "Chess API 无 fusionCorrectedData（无值）"),
        ]
        for a, b in repls:
            if a in html:
                html = html.replace(a, b)

    if 'id="live-refresh-btn"' not in html and _NAV_BACK_RE.search(html):
        html = _NAV_BACK_RE.sub(
            r"\1"
            r'\n    <button type="button" id="live-refresh-btn" class="live-refresh-btn">更新数据</button>'
            r'\n    <span id="live-refresh-status" class="live-refresh-status" aria-live="polite"></span>',
            html,
            count=1,
        )

    if ".live-refresh-btn" not in html:
        style = (
            "<style>"
            ".nav{display:flex;flex-wrap:wrap;align-items:center;gap:10px 14px}"
            ".live-refresh-btn{appearance:none;border:1px solid #d6d3d1;background:#fff;"
            "color:#1c1917;font-size:13px;font-weight:600;padding:5px 12px;border-radius:8px;"
            "cursor:pointer;font-family:inherit}"
            ".live-refresh-btn:hover{border-color:#a8a29e;background:#fafaf9}"
            ".live-refresh-btn:disabled{opacity:.55;cursor:wait}"
            ".live-refresh-status{font-size:12px;color:#78716c}"
            ".live-refresh-status.is-ok{color:#166534}"
            ".live-refresh-status.is-err{color:#b91c1c}"
            "</style>"
        )
        if re.search(r"</head>", html, re.I):
            html = re.sub(r"</head>", style + "</head>", html, count=1, flags=re.I)
        else:
            html = style + html
    # 旧静态页残留「系统最终」列：CSS + 轻量脚本隐藏，直到 live 刷新替换 DOM
    if "hide-sys-final-cols" not in html:
        hide = (
            "<style id=\"hide-sys-final-cols\">"
            ".xmod-table th.xmod-col-sys,"
            ".xmod-table:has(th.xmod-col-sys) td:nth-child(3){display:none!important}"
            "</style>"
            "<script>/*hide-sys-final-cols*/(function(){"
            "function hideSysLabels(){"
            "document.querySelectorAll('.issue-mod-k').forEach(function(k){"
            "if((k.textContent||'').indexOf('系统最终')>=0){"
            "var row=k.closest('.issue-mod-row'); if(row) row.style.display='none';"
            "}});"
            "document.querySelectorAll('.mod-json-sum-title').forEach(function(t){"
            "if((t.textContent||'').indexOf('系统最终')>=0){"
            "var card=t.closest('.mod-json-card'); if(card) card.style.display='none';"
            "}});"
            "}"
            "hideSysLabels();"
            "document.addEventListener('DOMContentLoaded', hideSysLabels);"
            "})();</script>"
        )
        if re.search(r"</head>", html, re.I):
            html = re.sub(r"</head>", hide + "</head>", html, count=1, flags=re.I)
        else:
            html = hide + html

    if 'id="live-issue-picks"' not in html:
        html = html.replace(
            '<div class="issue-picks"',
            '<div class="issue-picks" id="live-issue-picks"',
            1,
        )
    if 'id="live-diff-pane-label"' not in html:
        html = re.sub(
            r'(<div class="pane-label")(>差异清单)',
            r'\1 id="live-diff-pane-label"\2',
            html,
            count=1,
        )
    # 旧详情页：整段去掉「完整报文」双列区（对照已在证据卡 JSON 栈）
    if "完整报文（差异字段高亮）" in html:
        html = re.sub(
            r'<h2>完整报文（差异字段高亮）</h2>[\s\S]*?(?=<div class="footer">|<script\b)',
            "",
            html,
            count=1,
        )
    if 'id="live-street-compare"' not in html:
        html = re.sub(
            r"(<h2>行动序列对照[^<]*</h2>)",
            r'<div id="live-street-compare">\1',
            html,
            count=1,
        )
        if 'id="live-street-compare"' in html:
            # 闭合到 footer / 原完整报文位置 / script
            if '<div class="footer">' in html and "</div>\n\n  <div class=\"footer\">" not in html:
                html = html.replace(
                    '<div class="footer">',
                    '</div>\n\n  <div class="footer">',
                    1,
                )

    # 补 payload 字段（旧页可能没有）
    _payload_re = re.compile(
        r'(<script\b[^>]*\bid=["\']live-trace-payload["\'][^>]*>)(.*?)(</script>)',
        re.IGNORECASE | re.DOTALL,
    )
    pm = _payload_re.search(html)
    if pm:
        try:
            payload = json.loads(pm.group(2) or "{}")
            if isinstance(payload, dict):
                changed = False
                if not payload.get("hand_title_prefix") and payload.get("hand_uid"):
                    payload["hand_title_prefix"] = (
                        f"{payload.get('hand_uid')} Chess API vs 正确值"
                    )
                    changed = True
                elif "0729" in str(payload.get("hand_title_prefix") or ""):
                    payload["hand_title_prefix"] = (
                        f"{payload.get('hand_uid')} Chess API vs 正确值"
                    )
                    changed = True
                q = payload.get("query")
                if isinstance(q, dict):
                    try:
                        from trace_query_config import _norm_time

                        st = _norm_time(str(q.get("start_time") or ""))
                        et = _norm_time(str(q.get("end_time") or ""))
                        if st != (q.get("start_time") or "") or et != (
                            q.get("end_time") or ""
                        ):
                            q["start_time"] = st
                            q["end_time"] = et
                            payload["query"] = q
                            changed = True
                    except Exception:
                        pass
                if changed:
                    new_json = json.dumps(
                        payload, ensure_ascii=False, separators=(",", ":"), default=str
                    )
                    html = (
                        html[: pm.start()]
                        + pm.group(1)
                        + new_json
                        + pm.group(3)
                        + html[pm.end() :]
                    )
                # 旧页无 Chess 对照空白体：塞入正确值 JSON，避免整页空
                if (
                    'id="live-mod-json-stack"' not in html
                    and isinstance(payload.get("gt_norm"), dict)
                    and (
                        "尚未取到 Chess" in html
                        or "Chess API 无值" in html
                        or "待拉取 Chess Trace" in html
                    )
                ):
                    try:
                        stack = render_module_json_stack(
                            payload.get("gt_norm"), None, None
                        )
                        picks = (
                            '<div class="issue-picks" id="live-issue-picks" '
                            'aria-label="差异列表">'
                            '<p class="xmod-empty">Chess API 无值，暂无对照差异。'
                            "正确值见下方完整 JSON。</p></div>"
                        )
                        insert = picks + stack
                        if '<div class="glance">Chess API 无值</div>' in html:
                            html = html.replace(
                                '<div class="glance">Chess API 无值</div>',
                                '<div class="glance">Chess API 无值</div>' + insert,
                                1,
                            )
                        elif '<div class="glance">待拉取 Chess Trace</div>' in html:
                            html = html.replace(
                                '<div class="glance">待拉取 Chess Trace</div>',
                                '<div class="glance">Chess API 无值</div>' + insert,
                                1,
                            )
                        elif "Chess API 无 fusionCorrectedData" in html:
                            html = re.sub(
                                r"(Chess API 无 fusionCorrectedData[\s\S]*?</p>)",
                                lambda m: m.group(1) + insert,
                                html,
                                count=1,
                            )
                        elif "尚未取到 Chess API" in html:
                            html = re.sub(
                                r"(尚未取到 Chess API[\s\S]*?</p>)",
                                lambda m: m.group(1) + insert,
                                html,
                                count=1,
                            )
                    except Exception:
                        pass
        except Exception:
            pass

    if _LIVE_HAND_SCRIPT_RE.search(html):
        scroll_boot = """
document.querySelectorAll('[data-scroll-focus]').forEach(function(box) {
  var el = box.querySelector('.json-focus-hot, .json-focus, #focus-sys, #focus-gt, .mark-diff');
  if (!el) return;
  var pre = el.closest('pre');
  if (pre) {
    var top = el.offsetTop - pre.offsetTop - 40;
    pre.scrollTop = Math.max(0, top);
  }
});
"""
        html = _LIVE_HAND_SCRIPT_RE.sub(
            lambda m: (
                m.group(1)
                + "<script>\n"
                + scroll_boot
                + EVIDENCE_JS
                + "\n"
                + LIVE_TRACE_JS
                + "\n</script>"
            ),
            html,
            count=1,
        )
    elif "fetchFreshGt" not in html:
        # 旧结构无法整段替换时，在 </body> 前追加（并用标记避免重复）
        boot = (
            "<script>/* live-hand-refresh-v1 */\n"
            + LIVE_TRACE_JS
            + "\n</script>"
        )
        if "live-hand-refresh-v1" not in html:
            m_body = re.search(r"</body>", html, re.I)
            if m_body:
                # 不可用 re.sub 的 replacement：LIVE_TRACE_JS 含 \s/\d 会被当成转义
                html = html[: m_body.start()] + boot + html[m_body.start() :]
            else:
                html = html + boot
    return html

EVIDENCE_CSS = """
.nav {
  display: flex; flex-wrap: wrap; align-items: center; gap: 10px 14px;
}
.live-refresh-btn {
  appearance: none; border: 1px solid #d6d3d1; background: #fff;
  color: #1c1917; font-size: 13px; font-weight: 600;
  padding: 5px 12px; border-radius: 8px; cursor: pointer;
  font-family: inherit;
}
.live-refresh-btn:hover { border-color: #a8a29e; background: #fafaf9; }
.live-refresh-btn:disabled { opacity: 0.55; cursor: wait; }
.live-refresh-status { font-size: 12px; color: #78716c; }
.live-refresh-status.is-ok { color: #166534; }
.live-refresh-status.is-err { color: #b91c1c; }
.glance {
  font-size: 20px; font-weight: 700; margin: 6px 0 14px; color: #9f1239;
  line-height: 1.35; letter-spacing: -0.01em;
}
.glance-more { font-size: 14px; font-weight: 600; color: #a16207; margin-left: 4px; }
.ok-glance { color: #166534; font-size: 18px; font-weight: 650; }
.evidence { margin: 28px 0; }
.evidence-fold {
  margin: 20px 0 28px;
  border: 1px solid #e7e0d5;
  border-radius: 12px;
  background: #fffdf9;
  /* overflow must stay visible so .shot-pane sticky can pin to viewport */
}
.evidence-fold[open] { border-color: #e7e0d5; }
.evidence-summary {
  list-style: none;
  cursor: pointer;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  padding: 14px 16px;
  user-select: none;
  background: #faf6f0;
  border-bottom: 1px solid transparent;
  border-radius: 12px 12px 0 0;
}
.evidence-fold[open] > .evidence-summary { border-bottom-color: #e7e0d5; }
.evidence-summary::-webkit-details-marker { display: none; }
.evidence-summary::before {
  content: "▸";
  color: #78716c;
  font-size: 12px;
  width: 14px;
  display: inline-block;
}
.evidence-fold[open] > .evidence-summary::before { content: "▾"; }
.evidence-summary-title {
  font-size: 1.15rem; font-weight: 700; color: #1c1917;
}
.evidence-summary-extra { font-size: 13px; color: #78716c; margin-left: auto; }
.evidence-body { padding: 14px 16px 16px; }
.evidence-fold:not([open]) .evidence-summary { background: #f5f5f4; }
.evidence-fold[open] .evidence-summary-title { color: #9f1239; }
.evidence-grid {
  display: grid; grid-template-columns: 1.35fr 0.65fr; gap: 14px; align-items: start;
}
@media (max-width: 1000px) {
  .evidence-grid { grid-template-columns: 1fr; }
  .shot-pane { position: static; max-height: none; }
}
.shot-pane, .diff-pane, .json-pane {
  background: #fffdf9; border: 1px solid #e7e0d5; border-radius: 12px; padding: 12px;
}
.shot-pane {
  position: sticky;
  top: 12px;
  z-index: 6;
  align-self: start;
  max-height: calc(100vh - 24px);
  overflow: auto;
  box-shadow: 0 1px 0 rgba(28,25,23,0.04);
}
.shot-pane-sm .shot-main {
  max-height: min(280px, calc(100vh - 280px));
}
.shot-pane.is-zoomed, .shot-pane-sm.is-zoomed {
  position: sticky;
  z-index: 20;
}
.shot-pane.is-zoomed .shot-main, .shot-carousel.is-zoomed .shot-main {
  max-height: min(720px, calc(100vh - 120px));
}
.pane-label { font-size: 12px; color: #78716c; margin-bottom: 8px; font-weight: 600; }
.shot-pane img, .shot-only img, .shot-main {
  width: 100%; max-height: min(560px, calc(100vh - 200px)); object-fit: contain; border-radius: 8px;
  background: #111; display: block; user-select: none; -webkit-user-drag: none;
}
.shot-only { position: relative; border-radius: 8px; overflow: hidden; background: #111; }
.shot-toolbar {
  display: flex; align-items: center; gap: 10px; margin-top: 8px;
}
.shot-home {
  flex: 0 0 auto; font-size: 12px; padding: 4px 10px; border-radius: 8px;
  border: 1px solid #d6d3d1; background: #fff; color: #44403c; cursor: pointer;
}
.shot-home:hover { background: #f5f5f4; }
.shot-zoom {
  flex: 0 0 auto; font-size: 12px; padding: 4px 10px; border-radius: 8px;
  border: 1px solid #d6d3d1; background: #fff; color: #0f766e; cursor: pointer; font-weight: 600;
}
.shot-zoom:hover { background: #ecfdf5; }
.shot-zoom[aria-pressed="true"] { background: #0f766e; color: #fff; border-color: #0f766e; }
.shot-scrub { flex: 1 1 auto; min-width: 0; accent-color: #0f766e; }
.no-shot {
  min-height: 240px; display:flex; align-items:center; justify-content:center;
  background:#f5f5f4; border-radius:8px; color:#78716c;
}
.shot-note { font-size: 12px; color: #78716c; margin-top: 8px; }
.shot-carousel { position: relative; outline: none; }
.shot-carousel:focus-visible {
  outline: 2px solid #0f766e; outline-offset: 2px; border-radius: 8px;
}
.shot-viewport {
  position: relative; overflow: hidden; border-radius: 8px; background: #111;
  touch-action: pan-y; cursor: grab;
}
.shot-viewport:active { cursor: grabbing; }
.shot-track { position: relative; min-height: 280px; }
.shot-slide {
  display: none; position: relative;
}
.shot-slide.is-active { display: block; }
.shot-badge {
  position: absolute; top: 10px; left: 10px; z-index: 2;
  background: #9f1239; color: #fff; font-size: 11px; font-weight: 700;
  padding: 3px 8px; border-radius: 999px;
}
.shot-nav {
  position: absolute; top: 50%; transform: translateY(-50%); z-index: 3;
  width: 34px; height: 34px; border: none; border-radius: 999px;
  background: rgba(28,25,23,0.55); color: #fff; font-size: 22px; line-height: 1;
  cursor: pointer; display: flex; align-items: center; justify-content: center;
}
.shot-nav:hover { background: rgba(28,25,23,0.8); }
.shot-prev { left: 8px; }
.shot-next { right: 8px; }
.shot-dots {
  display: flex; flex-wrap: wrap; gap: 6px; justify-content: center; margin-top: 10px;
}
.shot-dot {
  width: 8px; height: 8px; border-radius: 999px; border: none; padding: 0;
  background: #d6d3d1; cursor: pointer;
}
.shot-dot.is-active { background: #9f1239; width: 18px; }
.issue-list { display: flex; flex-direction: column; gap: 10px; }
.issue-block {
  border: 1px solid #e7e0d5; border-radius: 10px; padding: 10px 10px 2px;
  background: #fff;
}
.issue-block.primary {
  border-color: #fecdd3; background: #fff8f8;
}
.issue-head {
  display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px 8px;
  margin-bottom: 8px; line-height: 1.35;
}
.issue-idx {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 20px; height: 20px; padding: 0 5px; border-radius: 999px;
  background: #9f1239; color: #fff; font-size: 11px; font-weight: 700;
}
.issue-block.compact .issue-idx { background: #a8a29e; min-width: 18px; height: 18px; font-size: 10px; }
.issue-kind {
  font-size: 11px; font-weight: 700; color: #9f1239;
  background: #ffe4e6; border-radius: 4px; padding: 1px 6px;
}
.issue-block.compact .issue-kind { background: #f5f5f4; color: #57534e; }
.issue-title { font-size: 14px; font-weight: 650; color: #1c1917; }
.issue-block.compact .issue-title { font-size: 12.5px; font-weight: 600; color: #44403c; }
.issue-block .field-compare { margin: 0 0 8px; }
.issue-block.primary .field-compare th,
.issue-block.primary .field-compare td { font-size: 13px; padding: 8px 10px; }
.issue-block.compact .field-compare th,
.issue-block.compact .field-compare td { font-size: 12px; padding: 5px 8px; }
.issue-block.compact .field-compare tr.row-diff code { font-size: 12px; font-weight: 650; }
.field-compare { width: 100%; border-collapse: collapse; margin: 0 0 12px; }
.field-compare th, .field-compare td {
  border: 1px solid #e7e0d5; padding: 10px 12px; text-align: left; font-size: 14px;
}
.field-compare th { background: #faf6f0; }
.field-compare tr.row-diff td {
  background: #fff1f2; color: #9f1239; font-weight: 650;
}
.field-compare tr.row-diff code { color: #9f1239; font-weight: 700; font-size: 14px; }
.focus-snip { margin: 8px 0 4px; }
.json-details { margin-top: 10px; border-top: 1px dashed #e7e0d5; padding-top: 8px; }
.json-details summary {
  cursor: pointer; color: #0f766e; font-size: 13px; font-weight: 600; user-select: none;
}
.dual-json { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 8px; }
.dual-json-full pre.full-json { max-height: 520px; }
.mini-h { font-size: 12px; color: #78716c; margin-bottom: 4px; }
.ok-pre, .bad-pre {
  margin: 0; padding: 10px; border-radius: 8px; font-size: 11px;
  white-space: pre-wrap; word-break: break-word; max-height: 280px; overflow: auto;
  font-family: ui-monospace, monospace;
}
.ok-pre { background: #ecfdf5; border: 1px solid #a7f3d0; }
.bad-pre { background: #fff1f2; border: 1px solid #fecdd3; }
.mark-diff {
  background: #fecdd3; color: #9f1239; font-weight: 700;
  padding: 0 2px; border-radius: 3px;
}
span.json-focus { display: block; background: rgba(254, 226, 226, 0.45); }
.meta-table { width: 100%; border-collapse: collapse; background: transparent; }
.meta-table th, .meta-table td {
  border: 0; border-bottom: 1px solid #f0ebe3; padding: 4px 8px 4px 0;
  text-align: left; font-size: 12px; line-height: 1.45; color: #78716c;
  vertical-align: top;
}
.meta-table th {
  background: transparent; width: 118px; font-weight: 500; color: #a8a29e;
  white-space: nowrap;
}
.meta-table td code {
  font-size: 11px; color: #78716c; font-weight: 400;
  background: transparent; padding: 0;
}
.hand-meta { margin: 8px 0 14px; }
.hand-meta-label { display: none; }

.issue-picks {
  display: flex; flex-direction: column; gap: 6px; margin-bottom: 12px;
}
.issue-acc {
  border: 1px solid #e7e0d5; border-radius: 8px;
  background: #fff; overflow: hidden;
}
/* 折叠时强制隐藏正文，避免嵌套 details / live 回填后出现「标题与表格错位」 */
details.issue-acc:not([open]) > .issue-acc-body { display: none !important; }
.issue-acc:nth-child(even) { background: #f8fafc; border-color: #e2e8f0; }
.issue-acc[open]:nth-child(odd) {
  border-color: #fda4af; background: #fff1f2;
  box-shadow: inset 3px 0 0 #e11d48;
}
.issue-acc[open]:nth-child(even) {
  border-color: #7dd3fc; background: #f0f9ff;
  box-shadow: inset 3px 0 0 #0284c7;
}
.issue-acc-sum {
  list-style: none; cursor: pointer; user-select: none;
  display: flex; align-items: center; gap: 8px;
  padding: 7px 10px; font-size: 13px; color: #1c1917; line-height: 1.35;
}
.issue-acc-sum::-webkit-details-marker { display: none; }
.issue-acc-sum::before {
  content: "▸"; color: #a8a29e; font-size: 11px; width: 12px; flex: 0 0 auto;
}
.issue-acc[open] > .issue-acc-sum::before { content: "▾"; }
.issue-acc[open]:nth-child(odd) > .issue-acc-sum::before { color: #9f1239; }
.issue-acc[open]:nth-child(even) > .issue-acc-sum::before { color: #0369a1; }
.issue-acc:nth-child(odd) > .issue-acc-sum:hover { background: #faf6f0; }
.issue-acc:nth-child(even) > .issue-acc-sum:hover { background: #eef2f7; }
.issue-acc[open]:nth-child(odd) > .issue-acc-sum { background: #ffe4e6; }
.issue-acc[open]:nth-child(even) > .issue-acc-sum { background: #e0f2fe; }
.issue-acc .issue-idx {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 18px; height: 18px; padding: 0 5px; border-radius: 999px;
  background: #a8a29e; color: #fff; font-size: 10px; font-weight: 700; flex: 0 0 auto;
}
.issue-acc[open]:nth-child(odd) .issue-idx { background: #9f1239; }
.issue-acc[open]:nth-child(even) .issue-idx { background: #0284c7; }
.issue-pick-text { flex: 1 1 auto; min-width: 0; }
.issue-acc-body {
  padding: 8px 10px 10px; border-top: 1px solid #e7e0d5;
}
.issue-acc[open]:nth-child(odd) > .issue-acc-body {
  border-top-color: #fecdd3; background: #fff8f8;
}
.issue-acc[open]:nth-child(even) > .issue-acc-body {
  border-top-color: #bae6fd; background: #f8fcff;
}
.issue-acc-body .field-compare th,
.issue-acc-body .field-compare td { font-size: 12px; padding: 5px 8px; }
.issue-story {
  margin: 0 0 10px; padding: 8px 10px; border: 1px solid #e7e0d5;
  border-radius: 8px; background: #fffdf9;
}
.issue-story + .issue-story { margin-top: 8px; }
.issue-story-meta { margin-bottom: 8px; }
.issue-story-row {
  display: grid; grid-template-columns: 72px 1fr; gap: 6px 10px;
  align-items: baseline; font-size: 13px; line-height: 1.4; margin: 2px 0;
}
.issue-story-row .k { color: #78716c; font-weight: 650; }
.issue-story-row .v { color: #1c1917; font-weight: 700; word-break: break-word; }
.issue-mod-list {
  border-top: 1px dashed #e7e0d5; padding-top: 8px; display: grid; gap: 6px;
}
.issue-mod-row {
  display: grid; grid-template-columns: 118px 1fr; gap: 6px 10px;
  align-items: start; font-size: 12.5px; line-height: 1.35;
}
.issue-mod-k { color: #57534e; font-weight: 650; }
.issue-mod-v {
  color: #1c1917; font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  word-break: break-word;
}
.issue-mod-v strong { font-size: 15px; font-weight: 750; letter-spacing: -0.01em; }
.issue-mod-v .sep { color: #d6d3d1; font-weight: 500; }
.issue-mod-paths {
  margin-top: 2px; font-size: 10px; color: #a8a29e; line-height: 1.35;
}
.issue-mod-paths code { font-family: inherit; color: inherit; }
.compact-table .field-compare { margin-bottom: 10px; }

.anchor-anomaly {
  margin: 0 0 6px;
  padding: 0;
  border: 1px solid #fcd34d;
  border-radius: 6px;
  background: #fffbeb;
  color: #92400e;
  font-size: 11px;
  line-height: 1.35;
  overflow: hidden;
}
.anchor-anomaly > summary {
  list-style: none;
  cursor: pointer;
  user-select: none;
  padding: 4px 8px;
  font-weight: 600;
  color: #92400e;
}
.anchor-anomaly > summary::-webkit-details-marker { display: none; }
.anchor-anomaly > summary::before {
  content: "▸ ";
  color: #d97706;
  font-size: 9px;
}
.anchor-anomaly[open] > summary::before { content: "▾ "; }
.anchor-anomaly > summary:hover { background: #fef3c7; }
.anchor-anomaly-title { font-weight: 700; color: #92400e; margin-bottom: 4px; }
.anchor-anomaly-sub { color: #a16207; margin-bottom: 6px; }
.anchor-anomaly-line {
  margin: 0;
  padding: 2px 8px 3px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 10px;
  color: #78350f;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.anchor-anomaly-line .k { color: #92400e; font-weight: 600; font-family: inherit; }
.anchor-anomaly-line .tag {
  display: inline-block;
  margin-left: 2px;
  padding: 0 4px;
  border-radius: 3px;
  background: #fef3c7;
  color: #92400e;
  font-size: 9px;
  font-weight: 700;
  font-family: inherit;
}
.mod-anchor-strip {
  margin: 0 0 10px; padding: 0; border: 1px solid #e7e0d5; border-radius: 8px;
  background: #fafaf9; overflow: hidden;
}
.mod-anchor-strip > .mod-anchor-label {
  list-style: none; cursor: pointer; user-select: none;
  font-size: 11px; font-weight: 700; color: #57534e;
  padding: 6px 8px; margin: 0;
}
.mod-anchor-strip > .mod-anchor-label::-webkit-details-marker { display: none; }
.mod-anchor-strip > .mod-anchor-label::before {
  content: "▸ "; color: #a8a29e; font-size: 10px;
}
.mod-anchor-strip[open] > .mod-anchor-label::before { content: "▾ "; }
.mod-anchor-strip > .mod-anchor-label:hover { background: #f5f5f4; }
.mod-anchor-note { font-size: 11px; color: #78716c; margin: 0 8px 4px; }
.mod-anchor-grid {
  display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px;
  padding: 0 8px 8px;
}
@media (max-width: 1100px) {
  .mod-anchor-grid { grid-template-columns: 1fr; }
}
.mod-anchor-card {
  border: 1px solid #d6d3d1; border-radius: 6px; background: #fff; padding: 5px 6px;
  min-width: 0;
}
.mod-anchor-card.is-miss { background: #fafaf9; border-style: dashed; opacity: 0.9; }
.mod-anchor-title {
  font-size: 11px; font-weight: 700; color: #1c1917; margin-bottom: 3px;
}
.mod-anchor-row {
  display: grid; grid-template-columns: 62px 1fr; gap: 4px; align-items: start;
  font-size: 10px; line-height: 1.3; margin-top: 1px;
}
.mod-anchor-row .k { color: #a8a29e; font-weight: 600; }
.mod-anchor-row .v {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  color: #1c1917; font-weight: 650;
  white-space: pre-wrap; word-break: break-all; user-select: text;
}
.mod-anchor-row .v.muted { color: #d6d3d1; font-weight: 500; }
.mod-json-meta { margin: 0 0 6px; }
.mod-json-meta .mod-anchor-card { box-shadow: none; }

.xmod-wrap {
  overflow-x: auto; margin: 2px 0 6px;
  border: 1px solid #e7e0d5; border-radius: 10px; background: #fff;
  box-shadow: 0 1px 0 rgba(28, 25, 23, 0.03);
}
.xmod-table {
  width: 100%; border-collapse: separate; border-spacing: 0;
  font-size: 12px; min-width: 640px;
}
.xmod-table thead th {
  position: sticky; top: 0; z-index: 1;
  padding: 8px 10px; text-align: left; white-space: nowrap;
  font-size: 11px; font-weight: 700; letter-spacing: 0.02em;
  color: #57534e; border-bottom: 1px solid #e7e0d5;
  background: linear-gradient(180deg, #fafaf9 0%, #f5f5f4 100%);
}
.xmod-table thead th.xmod-col-gt { color: #166534; }
.xmod-table thead th.xmod-col-sys { color: #9f1239; }
.xmod-table thead th.xmod-col-sig,
.xmod-table thead th.xmod-col-chess { color: #0f766e; }
.xmod-table tbody th.xmod-field {
  width: 108px; max-width: 132px; padding: 8px 10px;
  text-align: left; vertical-align: top;
  font-size: 12px; font-weight: 700; color: #44403c;
  background: #fafaf9; border-bottom: 1px solid #f0eeea;
  border-right: 1px solid #f0eeea; white-space: nowrap;
}
.xmod-table tbody td.xmod-td {
  padding: 7px 10px; vertical-align: top;
  border-bottom: 1px solid #f0eeea;
  background: #fff;
}
.xmod-table tbody tr:last-child th,
.xmod-table tbody tr:last-child td { border-bottom: none; }
.xmod-table tbody tr:hover th.xmod-field { background: #f5f5f4; }
.xmod-table tbody tr:hover td.xmod-td { background: #fcfcfb; }
.xmod-table tbody tr:hover td.xmod-td.is-diff { background: #fff1f2; }
.xmod-cell { display: block; line-height: 1.25; min-width: 0; }
.xmod-val {
  font-size: 14px; font-weight: 700; color: #1c1917;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  letter-spacing: -0.01em; word-break: break-word;
}
.xmod-val.muted { color: #d6d3d1; font-weight: 500; font-size: 12px; }
.xmod-path {
  margin-top: 2px; font-size: 10px; font-weight: 500; color: #a8a29e;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  max-width: 220px; line-height: 1.3;
}
.xmod-td.is-diff {
  background: #fff1f2;
  box-shadow: inset 3px 0 0 #fb7185;
}
.xmod-td.is-diff .xmod-val { color: #9f1239; }
.xmod-td.is-ok .xmod-val { color: #166534; }
.xmod-td.is-miss { background: #fafaf9; }
.xmod-col-gt { min-width: 88px; }
.xmod-col-sys { min-width: 96px; }
.xmod-empty { font-size: 12px; color: #78716c; margin: 6px 0; }
.issue-acc-body > .pane-label { margin-bottom: 6px; }

.mod-json-stack {
  margin-top: 14px; border-top: 1px dashed #e7e0d5; padding-top: 10px;
}
.mod-json-toolbar {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  margin-bottom: 8px;
}
.mod-json-toolbar .pane-label { margin-bottom: 0; flex: 1 1 auto; }
.mod-json-toggle {
  flex: 0 0 auto; font-size: 12px; padding: 4px 10px; border-radius: 8px;
  border: 1px solid #d6d3d1; background: #fff; color: #0f766e;
  cursor: pointer; font-weight: 600;
}
.mod-json-toggle:hover { background: #ecfdf5; }
.mod-json-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(160px, 1fr));
  gap: 8px;
  overflow-x: auto;
  align-items: start;
}
.mod-json-card {
  margin: 0; border: 1px solid #e7e0d5; border-radius: 8px;
  background: #fff; overflow: hidden; min-width: 0;
  display: flex; flex-direction: column;
}
.mod-json-head {
  display: flex; align-items: center; gap: 8px;
  padding: 8px; background: #faf6f0;
  border-bottom: 1px solid #e7e0d5;
  flex: 0 0 auto;
}
.mod-json-sum-title {
  flex: 1 1 auto; min-width: 0;
  font-size: 12px; font-weight: 650; color: #0f766e;
  line-height: 1.3; word-break: break-word;
}
.mod-json-copy {
  flex: 0 0 auto; font-size: 11px; font-weight: 600;
  padding: 2px 8px; border-radius: 6px; border: 1px solid #d6d3d1;
  background: #fff; color: #57534e; cursor: pointer;
}
.mod-json-copy:hover { background: #ecfdf5; color: #0f766e; border-color: #99f6e4; }
.mod-json-copy.is-copied {
  background: #ecfdf5; color: #0f766e; border-color: #5eead4;
}
.mod-json-block {
  margin: 0; border: 0; border-radius: 0;
  background: transparent; overflow: hidden; min-width: 0;
}
.mod-json-block > summary,
.mod-json-sum {
  cursor: pointer; padding: 6px 8px; font-size: 11px; font-weight: 600;
  color: #78716c; background: #fff; user-select: none;
  line-height: 1.3; list-style: none;
}
.mod-json-sum::-webkit-details-marker { display: none; }
.mod-json-sum::before { content: "▸ "; color: #a8a29e; font-size: 10px; }
.mod-json-block[open] > .mod-json-sum::before { content: "▾ "; }
.mod-json-block[open] > summary,
.mod-json-block[open] > .mod-json-sum { border-bottom: 1px solid #e7e0d5; }
.mod-json-pre {
  margin: 0; max-height: none; overflow: visible;
  background: #1c1917; color: #f5f5f4;
  padding: 8px; font-size: 10px; line-height: 1.35;
  white-space: pre-wrap; word-break: break-word;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
.mod-json-pre .mark-diff {
  background: #fecdd3; color: #9f1239; font-weight: 700;
  padding: 0 2px; border-radius: 3px;
}
.mod-json-pre .diff-line { background: rgba(254, 205, 211, 0.18); }
@media (max-width: 1100px) {
  .mod-json-row { grid-template-columns: repeat(3, minmax(160px, 1fr)); }
}
@media (max-width: 700px) {
  .mod-json-row { grid-template-columns: 1fr 1fr; }
}
"""
