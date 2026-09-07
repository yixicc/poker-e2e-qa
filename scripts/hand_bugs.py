#!/usr/bin/env python3
"""Per-hand bug status + owner + note, persisted in data/hand_bugs.json.

重要：此文件与对比报告分离。重跑 compare / 重生 index.html 只会「读」它，
不会清空。保存时默认与已有记录合并，避免页面未加载完或旧版前端误覆盖。
"""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any, Optional

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "hand_bugs.json"

BUG_STATUSES = (
    "",
    "待确认",
    "处理中",
    "已修复",
    "不修",
    "关闭",
)

BUG_STATUS_LABELS = {
    "": "未标记",
    "待确认": "待确认",
    "处理中": "处理中",
    "已修复": "已修复",
    "不修": "不修",
    "关闭": "关闭",
}


def _normalize_meta(meta: dict) -> dict[str, str]:
    status = str(meta.get("status") or "").strip()
    if status not in BUG_STATUSES:
        status = ""
    owner = str(meta.get("owner") or "").strip()
    note = str(meta.get("note") or meta.get("remark") or "").strip()
    return {"status": status, "owner": owner, "note": note}


def load_hand_bugs(path: Optional[str | Path] = None) -> dict[str, dict[str, str]]:
    p = Path(path) if path else DEFAULT_PATH
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        # 主文件坏了则尝试 .bak
        bak = p.with_suffix(p.suffix + ".bak")
        if bak.exists():
            try:
                raw = json.loads(bak.read_text(encoding="utf-8"))
            except Exception:
                return {}
        else:
            return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, str]] = {}
    hands = raw.get("hands") if isinstance(raw.get("hands"), dict) else raw
    if not isinstance(hands, dict):
        return {}
    for hid, meta in hands.items():
        if str(hid).startswith("_") or not isinstance(meta, dict):
            continue
        norm = _normalize_meta(meta)
        if not norm["status"] and not norm["owner"] and not norm["note"]:
            continue
        out[str(hid)] = norm
    return out


def save_hand_bugs(
    bugs: dict[str, Any],
    path: Optional[str | Path] = None,
    *,
    merge: bool = True,
) -> Path:
    """Persist bug fields.

    merge=True（默认）: 与磁盘已有记录合并。
      - 请求里出现的 HAND_xxx：按请求更新；三项皆空则删除该手记录
      - 请求里未出现的 HAND_xxx：原样保留（防止旧页/未加载完覆盖）
    merge=False: 仅保留请求中的非空记录（全量替换，慎用）
    """
    p = Path(path) if path else DEFAULT_PATH
    p.parent.mkdir(parents=True, exist_ok=True)

    if isinstance(bugs.get("hands"), dict):
        hands_in = bugs["hands"]
    else:
        hands_in = {k: v for k, v in bugs.items() if not str(k).startswith("_")}
    if bugs.get("replace") is True or bugs.get("merge") is False:
        merge = False

    existing = load_hand_bugs(p) if merge else {}
    merged: dict[str, dict[str, str]] = dict(existing)

    for hid, meta in (hands_in or {}).items():
        if not isinstance(meta, dict):
            continue
        key = str(hid)
        norm = _normalize_meta(meta)
        if not norm["status"] and not norm["owner"] and not norm["note"]:
            merged.pop(key, None)
        else:
            merged[key] = norm

    payload = {
        "_comment": (
            "全部手牌 Bug 状态 / 负责人 / 备注。"
            "与对比报告分离；重跑报告不会清空。"
            "保存默认合并已有记录。"
        ),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "hands": merged,
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

    # 原子写 + 备份，避免中断写坏文件
    if p.exists():
        bak = p.with_suffix(p.suffix + ".bak")
        try:
            shutil.copy2(p, bak)
        except Exception:
            pass
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(p)
    return p


def bug_meta_for(bugs: dict[str, dict[str, str]], hand_uid: str) -> dict[str, str]:
    m = bugs.get(hand_uid) or {}
    return {
        "status": str(m.get("status") or ""),
        "owner": str(m.get("owner") or ""),
        "note": str(m.get("note") or ""),
    }
