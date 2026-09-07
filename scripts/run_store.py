#!/usr/bin/env python3
"""跑批（Run）冻结与对比。

目录：
  data/runs/registry.json
  data/runs/<run_id>/meta.json
  data/runs/<run_id>/trace_query.json
  data/runs/<run_id>/index.html
  data/runs/<run_id>/hands/...
  data/runs/<run_id>/summary.json
  ...（其余与 output/ 同结构）
"""

from __future__ import annotations

import csv
import json
import re
import shutil
import time
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
RUNS_ROOT = ROOT / "data" / "runs"
REGISTRY_PATH = RUNS_ROOT / "registry.json"
DEFAULT_OUTPUT = ROOT / "output"
DEFAULT_TRACE = ROOT / "data" / "trace_query.json"

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


def validate_run_id(run_id: str) -> str:
    rid = str(run_id or "").strip()
    if not _ID_RE.match(rid):
        raise ValueError(
            "run_id 仅允许字母数字及 ._- ，且不以符号开头（建议 YYYYMMDD-标签）"
        )
    return rid


def run_dir(run_id: str) -> Path:
    return RUNS_ROOT / validate_run_id(run_id)


def _load_registry() -> dict[str, Any]:
    raw = _read_json(REGISTRY_PATH, {}) or {}
    if not isinstance(raw, dict):
        raw = {}
    raw.setdefault("runs", [])
    return raw


def _save_registry(reg: dict[str, Any]) -> None:
    reg = dict(reg)
    reg["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    _atomic_write(REGISTRY_PATH, json.dumps(reg, ensure_ascii=False, indent=2) + "\n")


def _trace_summary(cfg: Optional[dict]) -> dict[str, Any]:
    if not isinstance(cfg, dict):
        return {}
    return {
        "openId": cfg.get("openId") or cfg.get("open_id") or "",
        "openIdMode": cfg.get("openIdMode") or cfg.get("open_id_mode") or "",
        "startTime": cfg.get("startTime") or cfg.get("start_time") or "",
        "endTime": cfg.get("endTime") or cfg.get("end_time") or "",
        "traceEnv": cfg.get("traceEnv") or cfg.get("trace_env") or "uat",
        "api": cfg.get("api") or "",  # legacy
        "envLabel": cfg.get("envLabel") or cfg.get("env_label") or "",
    }


def _metrics_from_summary(summary: Optional[dict]) -> dict[str, Any]:
    if not isinstance(summary, dict):
        return {}
    keys = (
        "generated_at",
        "comparable_n",
        "old_accuracy_pct",
        "new_accuracy_pct",
        "old_exact_n",
        "new_exact_n",
        "old_comparable_n",
        "new_comparable_n",
        "fixed_n",
        "regressed_n",
        "new_category_counts",
    )
    return {k: summary.get(k) for k in keys if k in summary}


def _hands_from_summary_or_csv(run_path: Path, summary: Optional[dict]) -> list[dict[str, Any]]:
    if isinstance(summary, dict) and isinstance(summary.get("hands"), list):
        return list(summary["hands"])
    csv_path = run_path / "hands_overview.csv"
    if not csv_path.exists():
        return []
    out: list[dict[str, Any]] = []
    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            def exact(v: str) -> Optional[bool]:
                s = (v or "").strip()
                if s == "一致":
                    return True
                if s == "不一致":
                    return False
                return None

            old_col = next((k for k in row if "0703" in k), None)
            new_col = next((k for k in row if "0729" in k and "差异" not in k and "问题" not in k and "首要" not in k), None)
            # Prefer exact column names from header
            old_v = row.get("0703版本") or (row.get(old_col) if old_col else "")
            new_v = row.get("0729版本") or (row.get(new_col) if new_col else "")
            out.append(
                {
                    "hand_uid": row.get("ID") or "",
                    "hole_key": row.get("hole_cards_p0") or "",
                    "old_exact": exact(str(old_v)),
                    "new_exact": exact(str(new_v)),
                    "change": row.get("变化") or "",
                    "old_diff_count": row.get("0703版本差异处"),
                    "new_diff_count": row.get("0729版本差异处"),
                    "old_categories": [
                        x for x in str(row.get("0703版本问题类") or "").split("、") if x
                    ],
                    "new_categories": [
                        x for x in str(row.get("0729版本问题类") or "").split("、") if x
                    ],
                }
            )
    return out


def list_runs() -> list[dict[str, Any]]:
    RUNS_ROOT.mkdir(parents=True, exist_ok=True)
    items: list[dict[str, Any]] = []
    for d in sorted(RUNS_ROOT.iterdir(), key=lambda p: p.name, reverse=True):
        if not d.is_dir() or d.name.startswith("."):
            continue
        meta = _read_json(d / "meta.json", {}) or {}
        if not isinstance(meta, dict):
            meta = {"id": d.name}
        meta = dict(meta)
        meta.setdefault("id", d.name)
        meta.setdefault("has_index", (d / "index.html").exists())
        items.append(meta)
    return items


def load_run_meta(run_id: str) -> dict[str, Any]:
    d = run_dir(run_id)
    meta = _read_json(d / "meta.json", {}) or {}
    if not isinstance(meta, dict):
        meta = {}
    meta.setdefault("id", d.name)
    return meta


def load_run_trace_query(run_id: str) -> dict[str, Any]:
    return _read_json(run_dir(run_id) / "trace_query.json", {}) or {}


def save_run_trace_query(
    run_id: str,
    cfg: dict[str, Any],
    *,
    allow_mutate_frozen: bool = False,
) -> dict[str, Any]:
    """Write Trace 条件到本 Run，并同步 meta.trace_query 摘要。

    冻结 Run（readonly）默认拒绝原地改条件，避免新报告污染旧快照。
    显式 allow_mutate_frozen=True 时才允许（如用户确认的 refresh）。
    """
    rid = validate_run_id(run_id)
    dest = run_dir(rid)
    if not dest.exists():
        raise FileNotFoundError(f"Run 不存在: {rid}")
    meta = load_run_meta(rid)
    if meta.get("readonly") and not allow_mutate_frozen:
        raise PermissionError(
            f"Run {rid} 已冻结：不可原地改 Trace 条件。"
            "请新建 run_id 生成报告；或在 refresh 接口显式允许变更。"
        )
    payload = dict(cfg or {})
    _atomic_write(
        dest / "trace_query.json",
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    )
    meta["trace_query"] = _trace_summary(payload)
    meta["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    _atomic_write(dest / "meta.json", json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    return meta


def load_run_summary(run_id: str) -> dict[str, Any]:
    return _read_json(run_dir(run_id) / "summary.json", {}) or {}


def load_run_hands(run_id: str) -> list[dict[str, Any]]:
    d = run_dir(run_id)
    summary = load_run_summary(run_id)
    return _hands_from_summary_or_csv(d, summary)


def freeze_run(
    run_id: str,
    *,
    source_dir: Optional[Path] = None,
    tags: Optional[list[str]] = None,
    note: str = "",
    gt_version_id: Optional[str] = None,
    trace_query_path: Optional[Path] = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Copy current output (+ trace query) into a frozen run."""
    rid = validate_run_id(run_id)
    src = Path(source_dir) if source_dir else DEFAULT_OUTPUT
    if not src.exists():
        raise FileNotFoundError(f"源目录不存在: {src}")
    if not (src / "index.html").exists():
        raise FileNotFoundError(f"源目录缺少 index.html: {src}")

    dest = run_dir(rid)
    if dest.exists() and not overwrite:
        raise FileExistsError(f"Run 已存在: {rid}（传 overwrite=True 可覆盖）")
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    # Copy output contents (not the folder name)
    for item in src.iterdir():
        if item.name in (".DS_Store",):
            continue
        target = dest / item.name
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)

    trace_cfg: dict[str, Any] = {}
    if trace_query_path:
        tq_src = Path(trace_query_path)
        if tq_src.exists():
            shutil.copy2(tq_src, dest / "trace_query.json")
            loaded = _read_json(dest / "trace_query.json", {}) or {}
            if isinstance(loaded, dict):
                trace_cfg = loaded

    summary = _read_json(dest / "summary.json", {}) or {}
    if not isinstance(summary, dict):
        summary = {}

    # Ensure hands[] present for compare
    hands = _hands_from_summary_or_csv(dest, summary)
    if hands and "hands" not in summary:
        summary["hands"] = hands
        summary["gt_version_id"] = gt_version_id
        summary["run_id"] = rid
        _atomic_write(
            dest / "summary.json",
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        )

    tag_list = [str(t).strip() for t in (tags or []) if str(t).strip()]
    meta: dict[str, Any] = {
        "id": rid,
        "tags": tag_list,
        "note": str(note or "").strip(),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "source_dir": (
            str(src.relative_to(ROOT))
            if str(src.resolve()).startswith(str(ROOT.resolve()))
            else str(src)
        ),
        "gt_version_id": gt_version_id,
        "trace_query": _trace_summary(trace_cfg),
        "metrics": _metrics_from_summary(summary),
        "hand_n": len(hands),
        "batch_hands": summary.get("batch_hands") or None,
        "batch_hand_n": summary.get("batch_hand_n"),
        "readonly": True,
    }
    _atomic_write(dest / "meta.json", json.dumps(meta, ensure_ascii=False, indent=2) + "\n")

    reg = _load_registry()
    runs = [r for r in reg.get("runs", []) if isinstance(r, dict) and r.get("id") != rid]
    runs.insert(0, {"id": rid, "created_at": meta["created_at"], "tags": tag_list})
    reg["runs"] = runs
    _save_registry(reg)
    return meta


def compare_runs(run_a: str, run_b: str) -> dict[str, Any]:
    """Phase-1 compare: package metrics + hand pass/fail matrix."""
    a_id = validate_run_id(run_a)
    b_id = validate_run_id(run_b)
    meta_a = load_run_meta(a_id)
    meta_b = load_run_meta(b_id)
    sum_a = load_run_summary(a_id)
    sum_b = load_run_summary(b_id)
    hands_a = {h["hand_uid"]: h for h in load_run_hands(a_id) if h.get("hand_uid")}
    hands_b = {h["hand_uid"]: h for h in load_run_hands(b_id) if h.get("hand_uid")}
    all_ids = sorted(set(hands_a) | set(hands_b))

    def label(exact: Optional[bool]) -> str:
        if exact is True:
            return "一致"
        if exact is False:
            return "不一致"
        return "无对照"

    matrix = []
    counts = {
        "fixed": 0,
        "regressed": 0,
        "still_bad": 0,
        "still_ok": 0,
        "other": 0,
    }
    for hid in all_ids:
        ha = hands_a.get(hid) or {}
        hb = hands_b.get(hid) or {}
        a_new = ha.get("new_exact")
        b_new = hb.get("new_exact")
        if a_new is False and b_new is True:
            change = "修好"
            counts["fixed"] += 1
        elif a_new is True and b_new is False:
            change = "回退"
            counts["regressed"] += 1
        elif a_new is False and b_new is False:
            change = "仍错"
            counts["still_bad"] += 1
        elif a_new is True and b_new is True:
            change = "仍对"
            counts["still_ok"] += 1
        else:
            change = "其他"
            counts["other"] += 1
        matrix.append(
            {
                "hand_uid": hid,
                "hole_key": hb.get("hole_key") or ha.get("hole_key") or "",
                "a_old": label(ha.get("old_exact")),
                "a_new": label(a_new if isinstance(a_new, bool) or a_new is None else None),
                "b_old": label(hb.get("old_exact")),
                "b_new": label(b_new if isinstance(b_new, bool) or b_new is None else None),
                "change": change,
            }
        )

    return {
        "ok": True,
        "run_a": {"id": a_id, "meta": meta_a, "metrics": _metrics_from_summary(sum_a)},
        "run_b": {"id": b_id, "meta": meta_b, "metrics": _metrics_from_summary(sum_b)},
        "counts": counts,
        "matrix": matrix,
    }
