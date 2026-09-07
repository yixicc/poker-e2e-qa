#!/usr/bin/env python3
"""正确值（Ground Truth）版本库。

目录：
  data/gt_store/current.json
  data/gt_store/versions/<version_id>/meta.json
  data/gt_store/versions/<version_id>/hands.json

hands.json 每手含 gt_raw（补全后的请求）及可选 old_req_raw（0703 last_step），
以便后续跑批不必再读 Excel。
"""

from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
GT_ROOT = ROOT / "data" / "gt_store"
VERSIONS_DIR = GT_ROOT / "versions"
CURRENT_PATH = GT_ROOT / "current.json"

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def validate_version_id(version_id: str) -> str:
    vid = str(version_id or "").strip()
    if not _ID_RE.match(vid):
        raise ValueError(
            "version_id 仅允许字母数字及 ._- ，且不以符号开头（建议 YYYYMMDD-标签）"
        )
    return vid


def list_gt_versions() -> list[dict[str, Any]]:
    VERSIONS_DIR.mkdir(parents=True, exist_ok=True)
    current = get_current_gt_version_id()
    out: list[dict[str, Any]] = []
    for d in sorted(VERSIONS_DIR.iterdir(), key=lambda p: p.name, reverse=True):
        if not d.is_dir():
            continue
        meta = _read_json(d / "meta.json", {}) or {}
        if not isinstance(meta, dict):
            meta = {}
        meta = dict(meta)
        meta.setdefault("id", d.name)
        meta["is_current"] = d.name == current
        hands_path = d / "hands.json"
        if "hand_count" not in meta and hands_path.exists():
            hands = _read_json(hands_path, {}) or {}
            meta["hand_count"] = len(hands) if isinstance(hands, dict) else 0
        out.append(meta)
    return out


def get_current_gt_version_id() -> Optional[str]:
    raw = _read_json(CURRENT_PATH, {}) or {}
    if isinstance(raw, dict):
        vid = str(raw.get("version_id") or "").strip()
        return vid or None
    return None


def set_current_gt_version(version_id: str) -> None:
    vid = validate_version_id(version_id)
    if not (VERSIONS_DIR / vid / "hands.json").exists():
        raise FileNotFoundError(f"正确值版本不存在: {vid}")
    _atomic_write(
        CURRENT_PATH,
        json.dumps(
            {"version_id": vid, "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S")},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )


def version_dir(version_id: str) -> Path:
    return VERSIONS_DIR / validate_version_id(version_id)


def load_gt_version(
    version_id: Optional[str] = None,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Return (meta, hands). hands keyed by HAND_xxx."""
    vid = validate_version_id(version_id) if version_id else get_current_gt_version_id()
    if not vid:
        raise FileNotFoundError("未指定正确值版本，且没有 current")
    d = version_dir(vid)
    meta = _read_json(d / "meta.json", {}) or {}
    hands = _read_json(d / "hands.json", {}) or {}
    if not isinstance(hands, dict):
        raise ValueError(f"hands.json 格式错误: {vid}")
    if not isinstance(meta, dict):
        meta = {"id": vid}
    meta.setdefault("id", vid)
    meta["is_current"] = vid == get_current_gt_version_id()
    return meta, hands  # type: ignore[return-value]


def list_gt_hands_brief(version_id: str) -> list[dict[str, Any]]:
    """Hand rows for management UI (no full payloads)."""
    _, hands = load_gt_version(version_id)

    def _sort_key(hid: str) -> int:
        try:
            return int(str(hid).split("_")[-1])
        except Exception:
            return 10**9

    out: list[dict[str, Any]] = []
    for hid in sorted(hands.keys(), key=_sort_key):
        row = hands[hid] or {}
        gt = row.get("gt_raw") if isinstance(row.get("gt_raw"), dict) else None
        old = row.get("old_req_raw") if isinstance(row.get("old_req_raw"), dict) else None
        out.append(
            {
                "hand_uid": hid,
                "hole_key": str(row.get("hole_key") or ""),
                "has_gt": bool(gt),
                "has_old_req": bool(old),
                "created_at_old": row.get("created_at_old"),
            }
        )
    return out


def update_gt_meta(
    version_id: str,
    *,
    tags: Optional[list[str]] = None,
    note: Optional[str] = None,
) -> dict[str, Any]:
    meta, hands = load_gt_version(version_id)
    if tags is not None:
        meta["tags"] = [str(t).strip() for t in tags if str(t).strip()]
    if note is not None:
        meta["note"] = str(note).strip()
    meta["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    meta["hand_count"] = len(hands)
    meta["with_gt_n"] = sum(1 for h in hands.values() if h.get("gt_raw"))
    meta["with_old_req_n"] = sum(1 for h in hands.values() if h.get("old_req_raw"))
    d = version_dir(version_id)
    _atomic_write(d / "meta.json", json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    return meta


def update_gt_hand(
    version_id: str,
    hand_uid: str,
    *,
    hole_key: Optional[str] = None,
    gt_raw: Any = None,
    old_req_raw: Any = None,
    update_gt: bool = False,
    update_old: bool = False,
) -> dict[str, Any]:
    """Update one hand; only fields with update_* True (or hole_key if provided) are written."""
    meta, hands = load_gt_version(version_id)
    hid = str(hand_uid or "").strip()
    if hid not in hands:
        raise KeyError(f"手牌不存在: {hid}")
    row = dict(hands[hid] or {})
    if hole_key is not None:
        row["hole_key"] = str(hole_key)
    if update_gt:
        if gt_raw is None:
            row["gt_raw"] = None
        elif isinstance(gt_raw, dict):
            row["gt_raw"] = _jsonable(gt_raw)
        else:
            raise ValueError("gt_raw 必须是 JSON 对象或 null")
    if update_old:
        if old_req_raw is None:
            row["old_req_raw"] = None
        elif isinstance(old_req_raw, dict):
            row["old_req_raw"] = _jsonable(old_req_raw)
        else:
            raise ValueError("old_req_raw 必须是 JSON 对象或 null")
    hands[hid] = row
    d = version_dir(version_id)
    _atomic_write(d / "hands.json", json.dumps(hands, ensure_ascii=False, indent=2) + "\n")
    meta["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    meta["hand_count"] = len(hands)
    meta["with_gt_n"] = sum(1 for h in hands.values() if h.get("gt_raw"))
    meta["with_old_req_n"] = sum(1 for h in hands.values() if h.get("old_req_raw"))
    _atomic_write(d / "meta.json", json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    return {"meta": meta, "hand": {"hand_uid": hid, **row}}


def get_gt_hand(version_id: str, hand_uid: str) -> dict[str, Any]:
    _, hands = load_gt_version(version_id)
    hid = str(hand_uid or "").strip()
    if hid not in hands:
        raise KeyError(f"手牌不存在: {hid}")
    row = hands[hid] or {}
    return {"hand_uid": hid, **row}


def _jsonable(v: Any) -> Any:
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    # pandas Timestamp / datetime / numpy
    try:
        import pandas as pd

        if isinstance(v, pd.Timestamp):
            return None if pd.isna(v) else v.isoformat()
    except Exception:
        pass
    try:
        if hasattr(v, "isoformat"):
            return v.isoformat()
    except Exception:
        pass
    return str(v)


def save_gt_version(
    version_id: str,
    hands: dict[str, dict[str, Any]],
    *,
    tags: Optional[list[str]] = None,
    note: str = "",
    source: str = "",
    set_current: bool = True,
    extra_meta: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Create or overwrite a GT version (overwrite only if empty? — allow overwrite with care)."""
    vid = validate_version_id(version_id)
    if not hands:
        raise ValueError("hands 不能为空")
    d = version_dir(vid)
    d.mkdir(parents=True, exist_ok=True)
    clean_hands: dict[str, dict[str, Any]] = {}
    for hid, row in hands.items():
        if not isinstance(row, dict):
            continue
        key = str(hid)
        gt = row.get("gt_raw")
        if gt is not None and not isinstance(gt, dict):
            continue
        clean_hands[key] = {
            "hole_key": str(row.get("hole_key") or ""),
            "gt_raw": _jsonable(gt) if isinstance(gt, dict) else None,
            "old_req_raw": _jsonable(row.get("old_req_raw"))
            if isinstance(row.get("old_req_raw"), dict)
            else None,
            "created_at_old": _jsonable(row.get("created_at_old")),
            "match_method": str(row.get("match_method") or ""),
            "notes": list(row.get("notes") or [])
            if isinstance(row.get("notes"), list)
            else [],
        }
    if not clean_hands:
        raise ValueError("没有可保存的正确值手牌")

    tag_list = [str(t).strip() for t in (tags or []) if str(t).strip()]
    meta: dict[str, Any] = {
        "id": vid,
        "tags": tag_list,
        "note": str(note or "").strip(),
        "source": str(source or "").strip(),
        "hand_count": len(clean_hands),
        "with_gt_n": sum(1 for h in clean_hands.values() if h.get("gt_raw")),
        "with_old_req_n": sum(1 for h in clean_hands.values() if h.get("old_req_raw")),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    if extra_meta:
        for k, v in extra_meta.items():
            if k not in ("id", "hand_count") and v is not None:
                meta[k] = v
    existing = _read_json(d / "meta.json", {}) or {}
    if isinstance(existing, dict) and existing.get("created_at"):
        meta["created_at"] = existing["created_at"]

    _atomic_write(d / "hands.json", json.dumps(clean_hands, ensure_ascii=False, indent=2) + "\n")
    _atomic_write(d / "meta.json", json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    if set_current:
        set_current_gt_version(vid)
    return meta


def import_gt_from_pairs(
    pairs: list[Any],
    version_id: str,
    *,
    tags: Optional[list[str]] = None,
    note: str = "",
    source: str = "excel",
    set_current: bool = True,
) -> dict[str, Any]:
    """Build GT version from HandPair-like objects (hand_uid, hole_key, gt_raw, ...)."""
    hands: dict[str, dict[str, Any]] = {}
    for p in pairs:
        hid = str(getattr(p, "hand_uid", "") or "")
        if not hid:
            continue
        hands[hid] = {
            "hole_key": getattr(p, "hole_key", "") or "",
            "gt_raw": getattr(p, "gt_raw", None),
            "old_req_raw": getattr(p, "old_req_raw", None),
            "created_at_old": getattr(p, "created_at_old", None),
            "match_method": getattr(p, "match_method", "") or "",
            "notes": list(getattr(p, "notes", None) or []),
        }
    return save_gt_version(
        version_id,
        hands,
        tags=tags,
        note=note,
        source=source,
        set_current=set_current,
    )


def import_gt_from_excel(
    excel_path: str | Path,
    version_id: str,
    *,
    tags: Optional[list[str]] = None,
    note: str = "",
    set_current: bool = True,
) -> dict[str, Any]:
    """Import 正确值 (+ 0703 last_step) from Excel row order → HAND_001…"""
    import pandas as pd

    # Lazy import to avoid circular deps at module load
    from compare_gto_requests import (  # noqa: WPS433
        extract_hand_id,
        norm_hole_key,
        parse_json_cell,
        wepoker_ts,
    )

    path = Path(excel_path)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        raise FileNotFoundError(f"Excel 不存在: {path}")

    df = pd.read_excel(path)
    hands: dict[str, dict[str, Any]] = {}
    i = 0
    for _, row in df.iterrows():
        gt = parse_json_cell(row.get("补全后的请求"))
        old_req = parse_json_cell(row.get("last_step_request"))
        hk = norm_hole_key(row.get("hole_cards_p0")) or ""
        # Skip completely empty rows
        if not gt and not old_req and not hk:
            continue
        i += 1
        hid = f"HAND_{i:03d}"
        hands[hid] = {
            "hole_key": hk or "UNKNOWN",
            "gt_raw": gt,
            "old_req_raw": old_req,
            "created_at_old": row.get("created_at"),
            "match_method": "excel_row_order",
            "notes": [],
            "wepoker_ts": wepoker_ts(extract_hand_id(gt) or extract_hand_id(old_req)),
        }
    return save_gt_version(
        version_id,
        hands,
        tags=tags,
        note=note,
        source=str(path),
        set_current=set_current,
        extra_meta={"excel_path": str(path)},
    )


def delete_gt_version(version_id: str, *, allow_current: bool = False) -> None:
    vid = validate_version_id(version_id)
    cur = get_current_gt_version_id()
    if vid == cur and not allow_current:
        raise ValueError("不能删除当前正确值版本；请先切换 current")
    d = version_dir(vid)
    if not d.exists():
        raise FileNotFoundError(vid)
    shutil.rmtree(d)
    if vid == cur:
        CURRENT_PATH.unlink(missing_ok=True)
