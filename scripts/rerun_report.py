#!/usr/bin/env python3
"""从管理页触发：重跑报告并自动冻结为 Run。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
OUT = ROOT / "output"
DEFAULT_NEW = ROOT / "data" / "new.csv"
CONFIG_PATH = ROOT / "data" / "trace_query.json"  # deprecated; do not use
DATA = ROOT / "data"

sys.path.insert(0, str(SCRIPTS))
from gt_store import (  # noqa: E402
    get_current_gt_version_id,
    import_gt_from_excel,
    load_gt_version,
)
from run_store import (  # noqa: E402
    load_run_meta,
    run_dir,
    save_run_trace_query,
    validate_run_id,
)


def _resolve_gt_excel_path(gt_meta: dict[str, Any]) -> Path:
    """Prefer version excel_path / source; fall back to data/old.xlsx."""
    candidates: list[str] = []
    for key in ("excel_path", "source"):
        v = str(gt_meta.get(key) or "").strip()
        if v:
            candidates.append(v)
    candidates.append("data/old.xlsx")
    last_err = ""
    for raw in candidates:
        p = Path(raw)
        if not p.is_absolute():
            p = ROOT / p
        if p.exists() and p.is_file():
            return p
        last_err = str(p)
    raise FileNotFoundError(f"无法重拉真值：Excel 不存在（尝试到 {last_err}）")


def refresh_run_trace(
    run_id: str,
    trace_cfg: dict[str, Any],
    *,
    new_csv: str = "data/new.csv",
    skip_trace: bool = False,
    skip_gt: bool = False,
) -> dict[str, Any]:
    """Save Trace 条件到本 Run，重导真值（Excel），并重跑对比（默认会拉 Trace）。"""
    rid = validate_run_id(run_id)
    dest = run_dir(rid)
    if not dest.exists() or not (dest / "meta.json").exists():
        raise FileNotFoundError(f"Run 不存在: {rid}")

    meta_prev = load_run_meta(rid)
    vid = str(meta_prev.get("gt_version_id") or "").strip()
    if not vid:
        vid = get_current_gt_version_id() or ""
    if not vid:
        raise FileNotFoundError("本 Run 未记录正确值版本，且没有 current GT")
    gt_meta, _ = load_gt_version(vid)

    new_path = Path(new_csv)
    if not new_path.is_absolute():
        new_path = ROOT / new_path
    if not new_path.exists():
        raise FileNotFoundError(f"系统结果 CSV 不存在: {new_path}")

    cfg = dict(trace_cfg or {})
    if not str(cfg.get("traceEnv") or "").strip():
        cfg["traceEnv"] = "uat"
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
    try:
        from trace_envs import normalize_trace_env

        normalize_trace_env(str(cfg.get("traceEnv") or "uat"))
    except KeyError as e:
        raise ValueError(str(e)) from e

    started = time.time()
    gt_reimported: dict[str, Any] | None = None
    if not skip_gt:
        excel = _resolve_gt_excel_path(gt_meta if isinstance(gt_meta, dict) else {})
        was_current = bool(gt_meta.get("is_current"))
        tags_gt = gt_meta.get("tags") if isinstance(gt_meta.get("tags"), list) else []
        note_gt = str(gt_meta.get("note") or "")
        gt_reimported = import_gt_from_excel(
            excel,
            vid,
            tags=[str(t).strip() for t in tags_gt if str(t).strip()],
            note=note_gt,
            set_current=was_current,
        )

    DATA.mkdir(parents=True, exist_ok=True)
    # freeze_run 会清空 run 目录，配置先落到 data/ 临时文件
    pending = DATA / f".pending_trace_{rid}.json"
    pending.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    tags = meta_prev.get("tags") if isinstance(meta_prev.get("tags"), list) else []
    tag_list = [str(t).strip() for t in tags if str(t).strip()]
    note = str(meta_prev.get("note") or "")

    from compare_gto_requests import parse_hand_uids

    batch_hands = parse_hand_uids(meta_prev.get("batch_hands"))

    cmd = [
        sys.executable,
        str(SCRIPTS / "compare_gto_requests.py"),
        "--gt-version",
        vid,
        "--new",
        str(new_path),
        "--outdir",
        str(OUT),
        "--freeze-run",
        rid,
        "--freeze-tags",
        ",".join(tag_list),
        "--freeze-note",
        note,
        "--trace-config",
        str(pending),
        "--trace-env",
        str(cfg.get("traceEnv") or "uat"),
    ]
    if batch_hands:
        cmd.extend(["--hands", ",".join(batch_hands)])
    if skip_trace:
        cmd.append("--skip-trace")
    shots = str(cfg.get("shotsDir") or "").strip()
    orig = str(cfg.get("origShotsDir") or "").strip()
    if shots:
        cmd.extend(["--shots", shots])
    if orig:
        cmd.extend(["--orig-shots", orig])

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT),
            env=os.environ.copy(),
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip()
            raise RuntimeError(err[-2000:] if err else f"重跑失败 exit={proc.returncode}")
    finally:
        try:
            pending.unlink(missing_ok=True)
        except TypeError:
            if pending.exists():
                pending.unlink()

    # 再写一遍，保证表单与提交内容一致（并更新 meta 摘要）
    meta = save_run_trace_query(rid, cfg, allow_mutate_frozen=True)
    meta["rerun_seconds"] = round(time.time() - started, 1)
    meta["gt_version_id"] = vid
    meta["refreshed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    if batch_hands:
        meta["batch_hands"] = batch_hands
        meta["batch_hand_n"] = len(batch_hands)
    if gt_reimported:
        meta["gt_reimported_at"] = gt_reimported.get("updated_at") or meta["refreshed_at"]
        meta["gt_excel_path"] = gt_reimported.get("excel_path") or gt_reimported.get("source")
        meta["gt_hand_count"] = gt_reimported.get("hand_count")
    (dest / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return meta


def rerun_report(
    *,
    run_id: str,
    tags: Optional[list[str]] = None,
    note: str = "",
    gt_version: Optional[str] = None,
    new_csv: str = "data/new.csv",
    overwrite: bool = False,
    skip_trace: bool = True,
    trace_cfg: Optional[dict[str, Any]] = None,
    hand_uids: Optional[Any] = None,
) -> dict[str, Any]:
    """Run compare_gto_requests → write output/ → freeze as Run.

    Trace 条件必须由调用方传入（本报告专属），不再读取全局 data/trace_query.json。
    hand_uids 非空时只跑指定手牌。
    """
    from compare_gto_requests import parse_hand_uids

    rid = validate_run_id(run_id)
    dest = run_dir(rid)
    if dest.exists() and not overwrite:
        raise FileExistsError(f"Run 已存在: {rid}（勾选「同名则覆盖」可重跑）")

    vid = (gt_version or "").strip()
    if not vid or vid in ("current", "CURRENT"):
        vid = get_current_gt_version_id() or ""
    if not vid:
        raise FileNotFoundError("没有可用的正确值版本，请先从 Excel 导入（前置条件：对比数据）")
    load_gt_version(vid)  # validate exists

    new_path = Path(new_csv)
    if not new_path.is_absolute():
        new_path = ROOT / new_path
    if not new_path.exists():
        raise FileNotFoundError(f"系统结果 CSV 不存在: {new_path}（前置条件：对比数据）")

    cfg = dict(trace_cfg or {})
    if not str(cfg.get("traceEnv") or "").strip():
        cfg["traceEnv"] = "uat"
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
        raise ValueError(
            "Trace 条件未齐，缺少: "
            + ", ".join(missing)
            + "。请在生成报告页填写本报告的 Trace 条件"
        )
    try:
        from trace_envs import normalize_trace_env

        normalize_trace_env(str(cfg.get("traceEnv") or "uat"))
    except KeyError as e:
        raise ValueError(str(e)) from e

    batch_hands = parse_hand_uids(hand_uids)

    DATA.mkdir(parents=True, exist_ok=True)
    pending = DATA / f".pending_trace_{rid}.json"
    pending.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    tag_list = [str(t).strip() for t in (tags or []) if str(t).strip()]
    tag_csv = ",".join(tag_list)

    cmd = [
        sys.executable,
        str(SCRIPTS / "compare_gto_requests.py"),
        "--gt-version",
        vid,
        "--new",
        str(new_path),
        "--outdir",
        str(OUT),
        "--freeze-run",
        rid,
        "--freeze-tags",
        tag_csv,
        "--freeze-note",
        str(note or ""),
        "--trace-config",
        str(pending),
        "--trace-env",
        str(cfg.get("traceEnv") or "uat"),
    ]
    if batch_hands:
        cmd.extend(["--hands", ",".join(batch_hands)])
    if skip_trace:
        cmd.append("--skip-trace")
    shots = str(cfg.get("shotsDir") or "").strip()
    orig = str(cfg.get("origShotsDir") or "").strip()
    if shots:
        cmd.extend(["--shots", shots])
    if orig:
        cmd.extend(["--orig-shots", orig])

    env = os.environ.copy()
    started = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
        )
    finally:
        try:
            pending.unlink(missing_ok=True)
        except TypeError:
            if pending.exists():
                pending.unlink()

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(err[-2000:] if err else f"重跑失败 exit={proc.returncode}")

    # freeze_run already called inside compare; ensure meta + frozen cfg
    meta = save_run_trace_query(rid, cfg, allow_mutate_frozen=True)
    meta["rerun_seconds"] = round(time.time() - started, 1)
    meta["gt_version_id"] = vid
    if batch_hands:
        meta["batch_hands"] = batch_hands
        meta["batch_hand_n"] = len(batch_hands)
    (dest / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return meta
