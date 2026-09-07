#!/usr/bin/env python3
"""Resolve and rewrite local screenshot paths for intranet HTTP serving."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable, Optional
from urllib.parse import unquote, quote

# file:///.../basename.jpg — basename 仅字母数字._-，避免把 HTML 实体 &quot; 吃进文件名
_FILE_URI_RE = re.compile(
    r"file:///[^\s\"'<>]*?/([A-Za-z0-9._-]+\.(?:jpg|jpeg|png|webp|gif))",
    re.IGNORECASE,
)
_SHOT_EXT_RE = re.compile(
    r"^([A-Za-z0-9._-]+\.(?:jpg|jpeg|png|webp|gif))",
    re.IGNORECASE,
)


def normalize_dir(raw: Any) -> Optional[Path]:
    """Accept Mac/Windows paths; strip quotes; return existing directory or None."""
    if raw is None:
        return None
    text = str(raw).strip().strip('"').strip("'")
    if not text:
        return None
    # Windows: keep drive letters; expand ~
    p = Path(text).expanduser()
    try:
        p = p.resolve()
    except Exception:
        pass
    if p.is_dir():
        return p
    return None


def shot_dirs_from_config(cfg: Optional[dict[str, Any]]) -> list[Path]:
    """Prefer origShotsDir (原图), then shotsDir (重命名图)."""
    cfg = cfg or {}
    out: list[Path] = []
    for key in ("origShotsDir", "shotsDir", "localShotsDir"):
        d = normalize_dir(cfg.get(key))
        if d and d not in out:
            out.append(d)
    return out


def load_local_paths(path: Optional[Path] = None) -> dict[str, Any]:
    """截图等本地路径（与 Trace 查询条件分离）。"""
    root = Path(__file__).resolve().parent.parent
    p = Path(path) if path else (root / "data" / "local_paths.json")
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def collect_shot_dirs(
    *,
    cfg: Optional[dict[str, Any]] = None,
    runs_root: Optional[Path] = None,
) -> list[Path]:
    """合并：显式 cfg → data/local_paths.json → 各报告冻结的 Trace 配置里的截图目录。"""
    root = Path(__file__).resolve().parent.parent
    out: list[Path] = []

    def _add(dirs: list[Path]) -> None:
        for d in dirs:
            if d not in out:
                out.append(d)

    if cfg:
        _add(shot_dirs_from_config(cfg))
    _add(shot_dirs_from_config(load_local_paths()))
    rr = Path(runs_root) if runs_root else (root / "data" / "runs")
    if rr.is_dir():
        for run_dir in sorted(rr.iterdir(), reverse=True):
            tq = run_dir / "trace_query.json"
            if not tq.is_file():
                continue
            try:
                raw = json.loads(tq.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(raw, dict):
                _add(shot_dirs_from_config(raw))
    return out


def safe_shot_name(name: str) -> Optional[str]:
    """Basename only; reject path traversal; strip trailing HTML/JSON garbage."""
    if not name:
        return None
    name = unquote(str(name)).replace("\\", "/").strip()
    # 浏览器若把 &quot;, "ts"... 拼进 URL，先截到合法图片名
    m = _SHOT_EXT_RE.match(Path(name).name)
    if m:
        return m.group(1)
    base = Path(name).name
    if not base or base in (".", "..") or "/" in base or "\\" in base:
        return None
    if ".." in base:
        return None
    # 再尝试从脏串里抠出第一个图片名
    m2 = re.search(
        r"([A-Za-z0-9._-]+\.(?:jpg|jpeg|png|webp|gif))",
        base,
        re.IGNORECASE,
    )
    return m2.group(1) if m2 else None


def find_local_shot(name: str, dirs: Iterable[Path]) -> Optional[Path]:
    base = safe_shot_name(name)
    if not base:
        return None
    for d in dirs:
        cand = d / base
        if cand.is_file():
            return cand
    return None


def rewrite_file_uris_to_local_shot(html: str) -> str:
    """Rewrite absolute file:// image URLs to /local-shot/<basename> for LAN viewers."""

    def repl(m: re.Match[str]) -> str:
        base = safe_shot_name(m.group(1))
        if not base:
            return m.group(0)
        return "/local-shot/" + quote(base)

    return _FILE_URI_RE.sub(repl, html)
