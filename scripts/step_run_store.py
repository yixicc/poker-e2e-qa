"""决策点对比跑批存储（独立于 data/runs）。

隔离约定：
  - 一次跑批 = data/step_runs/<run_id>/ 独立目录
  - Trace 条件（trace_query.json）与结果（hands/*.spans.json）同目录冻结
  - 写完后 meta.readonly=true；默认禁止再写；覆盖须显式 wipe 后重建
  - 读路径只读本 run_id，不读全局、不串其它 run

目录：
  data/step_runs/registry.json
  data/step_runs/<run_id>/meta.json
  data/step_runs/<run_id>/trace_query.json
  data/step_runs/<run_id>/summary.json
  data/step_runs/<run_id>/index.html
  data/step_runs/<run_id>/hands/<HAND>.spans.json
  data/step_runs/<run_id>/steps/<HAND>#P0-<n>.json
"""

from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
STEP_RUNS_ROOT = ROOT / "data" / "step_runs"
REGISTRY_PATH = STEP_RUNS_ROOT / "registry.json"

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class StepRunReadonlyError(PermissionError):
    """Frozen step-run cannot be mutated without explicit wipe+overwrite."""


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


def validate_step_run_id(run_id: str) -> str:
    rid = str(run_id or "").strip()
    if not _ID_RE.match(rid):
        raise ValueError(
            "run_id 仅允许字母数字及 ._- ，且不以符号开头（建议 YYYYMMDD-标签）"
        )
    return rid


def step_run_dir(run_id: str) -> Path:
    return STEP_RUNS_ROOT / validate_step_run_id(run_id)


def step_run_exists(run_id: str) -> bool:
    d = step_run_dir(run_id)
    return d.exists() and (d / "meta.json").exists()


def is_step_run_readonly(run_id: str) -> bool:
    if not step_run_exists(run_id):
        return False
    meta = _read_json(step_run_dir(run_id) / "meta.json", {}) or {}
    if not isinstance(meta, dict):
        return False
    # 默认：有 meta 即视为冻结（兼容旧跑批未写 readonly）
    if "readonly" not in meta:
        return True
    return bool(meta.get("readonly"))


def assert_step_run_writable(run_id: str, *, overwrite: bool = False) -> None:
    """Raise if existing frozen run would be mutated without overwrite."""
    rid = validate_step_run_id(run_id)
    if not step_run_exists(rid):
        return
    if overwrite:
        return
    raise FileExistsError(
        f"决策点跑批已存在且已冻结: {rid}。"
        "请换新 run_id（推荐），或勾选「覆盖同名跑批」整目录重建。"
        "覆盖会删除该目录下旧 Trace 条件与 spans，不可恢复。"
    )


def wipe_step_run(run_id: str) -> None:
    """Delete an entire step-run directory (explicit overwrite only)."""
    rid = validate_step_run_id(run_id)
    d = step_run_dir(rid)
    if d.exists():
        shutil.rmtree(d)


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


def list_step_runs() -> list[dict[str, Any]]:
    STEP_RUNS_ROOT.mkdir(parents=True, exist_ok=True)
    out: list[dict[str, Any]] = []
    for d in STEP_RUNS_ROOT.iterdir():
        if not d.is_dir():
            continue
        meta = _read_json(d / "meta.json")
        if not isinstance(meta, dict):
            continue
        meta = dict(meta)
        meta.setdefault("id", d.name)
        if "readonly" not in meta:
            meta["readonly"] = True
        out.append(meta)
    out.sort(key=lambda m: str(m.get("created_at") or m.get("id") or ""), reverse=True)
    return out


def load_step_run_meta(run_id: str) -> dict[str, Any]:
    d = step_run_dir(run_id)
    meta = _read_json(d / "meta.json")
    if not isinstance(meta, dict):
        raise FileNotFoundError(f"决策点跑批不存在: {run_id}")
    meta = dict(meta)
    meta.setdefault("id", validate_step_run_id(run_id))
    if "readonly" not in meta:
        meta["readonly"] = True
    return meta


def load_step_run_summary(run_id: str) -> dict[str, Any]:
    d = step_run_dir(run_id)
    summary = _read_json(d / "summary.json", {})
    return summary if isinstance(summary, dict) else {}


def load_step_run_trace_query(run_id: str) -> dict[str, Any]:
    """本跑批冻结的 Trace 条件（不读全局）。"""
    d = step_run_dir(run_id)
    if not (d / "meta.json").exists():
        raise FileNotFoundError(f"决策点跑批不存在: {run_id}")
    raw = _read_json(d / "trace_query.json", {}) or {}
    return raw if isinstance(raw, dict) else {}


def load_step_result(run_id: str, step_id: str) -> dict[str, Any]:
    d = step_run_dir(run_id)
    safe = str(step_id).replace("/", "_")
    path = d / "steps" / f"{safe}.json"
    data = _read_json(path)
    if not isinstance(data, dict):
        raise FileNotFoundError(f"决策点结果不存在: {run_id}/{step_id}")
    out = dict(data)
    out.setdefault("run_id", validate_step_run_id(run_id))
    return out


def load_hand_spans(run_id: str, hand_uid: str) -> dict[str, Any]:
    """只读本 run 目录下的 spans 快照。"""
    d = step_run_dir(run_id)
    hid = str(hand_uid or "").strip()
    path = d / "hands" / f"{hid}.spans.json"
    data = _read_json(path)
    if not isinstance(data, dict):
        raise FileNotFoundError(f"本跑批无手牌 Trace 快照: {run_id}/{hid}")
    return data


def save_step_run(
    run_id: str,
    *,
    meta: dict[str, Any],
    summary: dict[str, Any],
    index_html: str,
    steps: list[dict[str, Any]],
    hand_spans: Optional[dict[str, Any]] = None,
    trace_query: Optional[dict[str, Any]] = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    rid = validate_step_run_id(run_id)
    assert_step_run_writable(rid, overwrite=overwrite)
    if overwrite and step_run_exists(rid):
        wipe_step_run(rid)

    d = step_run_dir(rid)
    d.mkdir(parents=True, exist_ok=True)
    (d / "steps").mkdir(exist_ok=True)
    (d / "hands").mkdir(exist_ok=True)

    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    meta_out = dict(meta or {})
    meta_out["id"] = rid
    meta_out["feature"] = "decision_point"
    meta_out["isolation"] = "per_run_dir"
    meta_out["readonly"] = True
    meta_out.setdefault("created_at", now)
    meta_out["updated_at"] = now
    meta_out["frozen_at"] = now
    meta_out["step_n"] = len(steps)
    metrics = (summary or {}).get("metrics") if isinstance(summary, dict) else {}
    if isinstance(metrics, dict):
        meta_out["metrics"] = metrics

    if isinstance(trace_query, dict):
        _atomic_write(
            d / "trace_query.json",
            json.dumps(trace_query, ensure_ascii=False, indent=2) + "\n",
        )
        meta_out["trace_query"] = {
            "openId": trace_query.get("openId") or "",
            "startTime": trace_query.get("startTime") or "",
            "endTime": trace_query.get("endTime") or "",
            "traceEnv": trace_query.get("traceEnv") or "uat",
        }

    _atomic_write(d / "meta.json", json.dumps(meta_out, ensure_ascii=False, indent=2) + "\n")
    _atomic_write(d / "summary.json", json.dumps(summary or {}, ensure_ascii=False, indent=2) + "\n")
    _atomic_write(d / "index.html", index_html if index_html.endswith("\n") else index_html + "\n")

    for step in steps:
        sid = str(step.get("step_id") or "").strip()
        if not sid:
            continue
        payload = dict(step)
        payload.setdefault("run_id", rid)
        _atomic_write(
            d / "steps" / f"{sid}.json",
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        )

    if isinstance(hand_spans, dict):
        for hid, payload in hand_spans.items():
            snap = dict(payload) if isinstance(payload, dict) else {"spans": payload}
            snap.setdefault("run_id", rid)
            snap.setdefault("hand_uid", hid)
            _atomic_write(
                d / "hands" / f"{hid}.spans.json",
                json.dumps(snap, ensure_ascii=False, indent=2) + "\n",
            )

    reg = _load_registry()
    runs = [r for r in reg.get("runs") or [] if str(r) != rid]
    runs.insert(0, rid)
    reg["runs"] = runs
    _save_registry(reg)
    return meta_out


def reject_inplace_trace_update(run_id: str) -> None:
    """API guard: never mutate frozen step-run Trace in place."""
    rid = validate_step_run_id(run_id)
    if step_run_exists(rid):
        raise StepRunReadonlyError(
            f"决策点跑批 {rid} 已冻结隔离：不可原地改 Trace。"
            "请新建 run_id 再跑；旧目录的条件与 spans 会原样保留。"
        )
