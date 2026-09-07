#!/usr/bin/env python3
"""Local helper: Trace 查询表单 + spans 渲染 + 内网分享（含本地截图 HTTP）.

  # 仅本机
  python3 scripts/trace_config_server.py

  # 内网同事可访问（绑定 0.0.0.0，并打印局域网地址）
  python3 scripts/trace_config_server.py --host 0.0.0.0

  # 管理入口:  http://<你的内网IP>:8766/
  # 组合发现:  http://<你的内网IP>:8766/discover
  # 每日趋势:  http://<你的内网IP>:8766/discover/trend
  # P0 决策点: http://<你的内网IP>:8766/gt-steps
  # 决策点对比: http://<你的内网IP>:8766/step-compare
  # 当前总览:  http://<你的内网IP>:8766/output/index.html
  # 冻结跑批:  http://<你的内网IP>:8766/runs/<run_id>/index.html
  # 证据页:    http://<你的内网IP>:8766/hands/HAND_001.html
  # 截图:      http://<你的内网IP>:8766/local-shot/<文件名>
"""

from __future__ import annotations

import argparse
import html
import json
import mimetypes
import socket
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CONFIG_PATH = DATA / "trace_query.json"
OUT = ROOT / "output"
SCRIPTS = ROOT / "scripts"
RUNS_ROOT = DATA / "runs"

sys.path.insert(0, str(SCRIPTS))
from evidence_report import (  # noqa: E402
    build_issue_blocks,
    inject_live_hand_refresh,
    render_cross_module_table,
    render_issue_picks_html,
    render_module_anchor_strip,
    render_module_json_stack,
)
from module_pipeline import analyze_hand_trace  # noqa: E402
from cross_module import build_cross_module_rows  # noqa: E402
from local_shots import (  # noqa: E402
    collect_shot_dirs,
    find_local_shot,
    load_local_paths,
    rewrite_file_uris_to_local_shot,
    shot_dirs_from_config,
)
from hand_bugs import load_hand_bugs, save_hand_bugs  # noqa: E402
from gt_store import (  # noqa: E402
    get_current_gt_version_id,
    get_gt_hand,
    import_gt_from_excel,
    list_gt_hands_brief,
    list_gt_versions,
    load_gt_version,
    set_current_gt_version,
    update_gt_hand,
    update_gt_meta,
)
from run_store import (  # noqa: E402
    list_runs,
    load_run_trace_query,
    validate_run_id,
)
from rerun_report import refresh_run_trace, rerun_report  # noqa: E402
from manage_page import (  # noqa: E402
    inject_app_shell,
    render_discover_page,
    render_gt_detail_page,
    render_gt_page,
    render_manage_page,
    render_rerun_page,
    render_settings_page,
)
from gt_steps.pages import (  # noqa: E402
    render_gt_step_detail_page,
    render_gt_steps_index,
    render_gt_steps_version_page,
)
from gt_steps.split import get_step_detail, list_version_steps_brief  # noqa: E402
from step_compare_pages import (  # noqa: E402
    render_step_compare_list_page,
    render_step_compare_new_page,
    render_step_detail_page,
    render_step_run_index_html,
)
from discover_compare import (  # noqa: E402
    compare_hand_signal_chess,
    load_discover_meta,
    load_discover_step,
    load_discover_summary,
)
from discover_compare_pages import (  # noqa: E402
    render_discover_compare_index,
    render_discover_compare_loading_page,
)
from daily_sig_chess import (  # noqa: E402
    calendar_window,
    get_job,
    load_day,
    start_daily_job,
    validate_day,
)
from daily_sig_chess_pages import (  # noqa: E402
    render_day_page,
    render_trend_page,
)
from step_run_store import (  # noqa: E402
    list_step_runs,
    load_hand_spans,
    load_step_result,
    load_step_run_meta,
    load_step_run_summary,
    load_step_run_trace_query,
)
from nav_back import inject_smart_back  # noqa: E402
from trace_query_config import (  # noqa: E402
    apply_run_trace_to_hand_html,
    compact_hole_id,
    inject_run_trace_form,
    load_trace_api_settings,
    load_trace_query_config,
    query_summary_html,
    render_trace_query_page,
    resolve_trace_query,
    save_trace_api_settings,
)

def _template_trace_cfg() -> dict:
    """Seed for「生成报告」页：最近一次跑批的 Trace 条件 + local_paths 截图目录。"""
    cfg: dict = {}
    try:
        runs = list_runs()
        if runs:
            rid = str((runs[0] or {}).get("id") or "").strip()
            if rid:
                loaded = load_run_trace_query(rid)
                if isinstance(loaded, dict):
                    cfg = dict(loaded)
    except Exception:
        cfg = {}
    lp = load_local_paths()
    if isinstance(lp, dict):
        if not str(cfg.get("origShotsDir") or "").strip() and lp.get("origShotsDir"):
            cfg["origShotsDir"] = lp["origShotsDir"]
        if not str(cfg.get("shotsDir") or "").strip() and lp.get("shotsDir"):
            cfg["shotsDir"] = lp["shotsDir"]
    if not cfg.get("traceEnv"):
        cfg["traceEnv"] = "uat"
    return cfg


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8766
BUGS_PATH = DATA / "hand_bugs.json"


class ReuseHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


def _lan_ips() -> list[str]:
    ips: list[str] = []
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET, socket.SOCK_STREAM):
            ip = info[4][0]
            if ip and not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except Exception:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith("127.") and ip not in ips:
            ips.insert(0, ip)
    except Exception:
        pass
    return ips


def _resolve_query_from_payload(payload: dict) -> dict:
    """Merge page query / config into a display+render query dict (no network)."""
    hand_uid = str(payload.get("hand_uid") or "").strip()
    hole_key = compact_hole_id(payload.get("hole_key") or payload.get("cards") or "")
    user_token = str(payload.get("user_token") or payload.get("data_open_id") or "").strip()
    page_q = payload.get("query") if isinstance(payload.get("query"), dict) else {}

    # 证据页以页内 payload.query（本报告冻结条件）为准，不再读全局配置
    api_s = load_trace_api_settings()
    seed = {
        "traceEnv": api_s.get("traceEnv") or "uat",
        "api": api_s.get("api") or "",
    }
    q = resolve_trace_query(
        seed,
        hand_uid=hand_uid or "HAND",
        hole_key=hole_key,
        data_open_id=user_token,
    )
    for k in (
        "api",
        "trace_env",
        "env_label",
        "open_id",
        "fallback_open_id",
        "cards",
        "hole_key",
        "start_time",
        "end_time",
        "pad_minutes",
        "open_id_mode",
    ):
        if page_q.get(k) not in (None, ""):
            q[k] = page_q[k]

    # 修复页内残留的坏时间窗（如 2026-08-1110:45:00）
    from trace_query_config import _norm_time

    if q.get("start_time"):
        q["start_time"] = _norm_time(str(q.get("start_time") or ""))
    if q.get("end_time"):
        q["end_time"] = _norm_time(str(q.get("end_time") or ""))

    page_cards = compact_hole_id(payload.get("cards") or page_q.get("cards") or "")
    if page_cards:
        q["cards"] = page_cards
        q["hole_key"] = page_cards
    elif not q.get("cards") and hole_key:
        q["cards"] = hole_key
        q["hole_key"] = hole_key
    return q


def load_normalized_gt_hand(hand_uid: str, version_id: str = "") -> dict:
    """从正确值库读取一手并 normalize（与跑批口径一致）。"""
    from compare_gto_requests import normalize_for_compare

    hid = (hand_uid or "").strip()
    if not hid:
        raise ValueError("缺少 hand_uid")
    vid = (version_id or "").strip() or get_current_gt_version_id()
    if not vid:
        raise ValueError("无当前正确值版本")
    hand = get_gt_hand(vid, hid)
    gt_raw = hand.get("gt_raw")
    if not isinstance(gt_raw, dict):
        raise ValueError(f"{hid} 无 gt_raw")
    gt_norm, trunc_meta = normalize_for_compare(gt_raw, truncate=True)
    return {
        "ok": True,
        "hand_uid": hid,
        "version_id": vid,
        "gt_norm": gt_norm,
        "trunc_meta": trunc_meta,
        "hole_key": hand.get("hole_key"),
    }


def render_hand_modules_from_spans(payload: dict) -> dict:
    """Render cross-module tables / JSON stack from browser-fetched spans (no Trace outbound)."""
    from compare_gto_requests import (
        badge_exact,
        deep_diff,
        filter_ignorable,
        json_with_value_marks,
        merge_diffs_with_alignment,
        render_action_street_compare_triple,
    )

    spans = payload.get("spans")
    if not isinstance(spans, list):
        spans = []
    gt_norm = payload.get("gt_norm")
    sys_norm = payload.get("sys_norm")
    old_norm = payload.get("old_norm")
    if not isinstance(gt_norm, dict):
        gt_norm = None
    if not isinstance(sys_norm, dict):
        sys_norm = None
    if not isinstance(old_norm, dict):
        old_norm = None

    q = _resolve_query_from_payload(payload)
    fetch_meta = payload.get("fetch_meta") if isinstance(payload.get("fetch_meta"), dict) else {}
    fetched = {
        "spans": spans,
        "open_id": payload.get("open_id_used") or fetch_meta.get("open_id") or q.get("open_id"),
        "hole_cards_used": payload.get("cards_used")
        or fetch_meta.get("hole_cards_used")
        or q.get("cards"),
        "start_time": fetch_meta.get("start_time") or q.get("start_time"),
        "end_time": fetch_meta.get("end_time") or q.get("end_time"),
        "tried": fetch_meta.get("tried") or [],
        "error": None if spans else (fetch_meta.get("error") or "无匹配 span"),
        "query": q,
    }

    chain = analyze_hand_trace(spans, gt_norm=gt_norm, fetch_meta=fetched)
    from evidence_report import chess_norm_for_compare

    chess_norm = chess_norm_for_compare(chain, gt_norm=gt_norm)
    compare_right = chess_norm
    blocks = (
        build_issue_blocks(gt_norm, compare_right)
        if gt_norm and compare_right
        else []
    )
    issue_tables = []
    for b in blocks:
        xrows = build_cross_module_rows(
            b, gt_norm=gt_norm, sys_norm=compare_right, trace_chain=chain
        )
        issue_tables.append(
            render_cross_module_table(
                xrows, trace_chain=chain, include_anchor_strip=False
            )
        )

    diff_n = len(blocks)
    exact = (
        (diff_n == 0) if (gt_norm is not None and compare_right is not None) else None
    )
    issues_html = None
    if gt_norm is not None and compare_right is not None:
        issues_html = render_issue_picks_html(
            gt_norm, compare_right, chain, blocks=blocks
        )
    elif gt_norm is not None and compare_right is None:
        span_hint = f"当前 Trace {len(spans)} 条 span"
        if chain.get("note"):
            span_hint += f"；{chain.get('note')}"
        issues_html = (
            '<div class="issue-picks" id="live-issue-picks" aria-label="差异列表">'
            '<p class="xmod-empty">Chess API 无 fusionCorrectedData（无值），无法与正确值对照。'
            f"（{html.escape(span_hint)}）下方完整 JSON 仍展示正确值与信号引擎；"
            "请确认时间窗/openId/holeCards，或点「更新数据」重试。</p></div>"
        )

    gt_pre_html = None
    chess_pre_html = None
    street_compare_html = None
    chess_badge_html = None
    if gt_norm is not None and compare_right is not None:
        chess_diffs = filter_ignorable(deep_diff(gt_norm, compare_right))
        chess_diffs = merge_diffs_with_alignment(gt_norm, compare_right, chess_diffs)
        gt_pre_html = json_with_value_marks(gt_norm, chess_diffs, "left")
        chess_pre_html = json_with_value_marks(compare_right, chess_diffs, "right")
        street_compare_html = render_action_street_compare_triple(
            gt_norm, None, compare_right, right_label="Chess API"
        )
        chess_badge_html = badge_exact(exact)
    elif compare_right is None:
        street_compare_html = (
            "<h2>行动序列对照（正确值 vs Chess API）</h2>"
            '<p class="xmod-empty">Chess API 无值，暂无法对照行动序列</p>'
        )

    return {
        "ok": True,
        "error": None if spans else fetched.get("error"),
        "query": q,
        "query_html": query_summary_html(q),
        "span_n": len(spans),
        "hero_index": chain.get("hero_index"),
        "anchor_mode": chain.get("anchor_mode"),
        "root_cause_title": chain.get("root_cause_title"),
        "issue_tables": issue_tables,
        "issues_html": issues_html,
        "diff_n": diff_n,
        "exact": exact,
        "chess_status": "ok" if compare_right is not None else "no_value",
        "anchor_strip_html": render_module_anchor_strip(chain),
        "json_stack_html": render_module_json_stack(gt_norm, None, chain),
        "gt_pre_html": gt_pre_html,
        "chess_pre_html": chess_pre_html,
        "sys_pre_html": None,  # 已隐藏系统最终
        "old_pre_html": None,
        "street_compare_html": street_compare_html,
        "chess_badge_html": chess_badge_html,
        "sys_badge_html": chess_badge_html,
        "cards_used": fetched.get("hole_cards_used") or q.get("cards"),
        "open_id_used": fetched.get("open_id") or q.get("open_id"),
        "compare_side": "chess",
    }


def _run_trace_discover(
    *,
    start_time: str,
    end_time: str,
    trace_env: str = "",
    api: str = "",
) -> list:
    """Proxy Trace Viewer traceDiscover via configured Trace API."""
    from trace_client import TraceClient
    from trace_envs import DEFAULT_TRACE_ENV, normalize_trace_env, resolve_api_base
    from trace_query_config import _norm_time, is_valid_api_time

    st = _norm_time(str(start_time or ""))
    et = _norm_time(str(end_time or ""))
    if not st or not et:
        raise ValueError("请填写开始时间与结束时间")
    if not is_valid_api_time(st) or not is_valid_api_time(et):
        raise ValueError(f"时间格式无效：{st!r} ~ {et!r}")
    raw_env = str(trace_env or "").strip() or DEFAULT_TRACE_ENV
    env_id = normalize_trace_env(raw_env)
    client = TraceClient(
        env_id=env_id,
        base_url=resolve_api_base(env_id, override=str(api or "").strip()),
    )
    rows = client.trace_discover(start_time=st, end_time=et)
    return rows if isinstance(rows, list) else []


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, code: int, obj: dict) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _bytes(self, code: int, data: bytes, content_type: str) -> None:
        if content_type.startswith("text/html"):
            try:
                text = data.decode("utf-8")
                text = inject_app_shell(text, active="runs")
                text = inject_smart_back(text)
                data = text.encode("utf-8")
            except Exception:
                pass
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        # Allow intranet caching of images lightly
        if content_type.startswith("image/"):
            self.send_header("Cache-Control", "public, max-age=3600")
        elif content_type.startswith("text/html"):
            self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    def _serve_file(self, f: Path) -> bool:
        if not f.exists() or not f.is_file():
            return False
        ctype = mimetypes.guess_type(str(f))[0] or "application/octet-stream"
        if f.suffix.lower() in (".html", ".htm"):
            text = f.read_text(encoding="utf-8", errors="replace")
            text = rewrite_file_uris_to_local_shot(text)
            if "live-trace-payload" in text:
                text = inject_live_hand_refresh(text)
            self._bytes(200, text.encode("utf-8"), "text/html; charset=utf-8")
            return True
        self._bytes(200, f.read_bytes(), ctype)
        return True

    def _serve_local_shot(self, name: str) -> None:
        dirs = collect_shot_dirs()
        found = find_local_shot(name, dirs)
        if not found:
            self._json(
                404,
                {
                    "ok": False,
                    "error": f"未找到截图 {name!r}；请在 Trace 查询条件里配置 origShotsDir / shotsDir",
                    "dirs": [str(d) for d in dirs],
                },
            )
            return
        ctype = mimetypes.guess_type(str(found))[0] or "application/octet-stream"
        self._bytes(200, found.read_bytes(), ctype)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path.startswith("/local-shot/"):
            name = path[len("/local-shot/") :]
            self._serve_local_shot(name)
            return

        if path in ("/api/local-shots-status", "/local-shots-status"):
            dirs = collect_shot_dirs()
            info = []
            for d in dirs:
                try:
                    n = sum(1 for x in d.iterdir() if x.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"))
                except Exception:
                    n = -1
                info.append({"path": str(d), "ok": True, "image_n": n})
            self._json(
                200,
                {
                    "ok": bool(dirs),
                    "dirs": info,
                    "hint": "截图目录来自 data/local_paths.json 与各报告 trace_query.json",
                },
            )
            return

        if path in ("/api/hand-bugs", "/hand-bugs"):
            bugs = load_hand_bugs(BUGS_PATH)
            self._json(200, {"ok": True, "hands": bugs, "path": str(BUGS_PATH.relative_to(ROOT))})
            return

        if path in ("/api/manage-state", "/api/runs", "/api/gt-versions"):
            self._json(
                200,
                {
                    "ok": True,
                    "runs": list_runs(),
                    "gt_versions": list_gt_versions(),
                    "current_gt": get_current_gt_version_id(),
                },
            )
            return

        if path in ("/", "/manage", "/manage.html", "/runs.html"):
            body = render_manage_page(
                runs=list_runs(),
                gt_versions=list_gt_versions(),
                current_gt=get_current_gt_version_id(),
            ).encode("utf-8")
            self._bytes(200, body, "text/html; charset=utf-8")
            return

        if path in ("/rerun", "/manage/rerun", "/rerun.html"):
            csv_rel = "data/new.csv"
            csv_abs = ROOT / csv_rel
            body = render_rerun_page(
                gt_versions=list_gt_versions(),
                current_gt=get_current_gt_version_id(),
                trace_cfg=_template_trace_cfg(),
                csv_path=csv_rel,
                csv_exists=csv_abs.exists(),
            ).encode("utf-8")
            self._bytes(200, body, "text/html; charset=utf-8")
            return

        if path in ("/gt", "/manage/gt", "/gt.html"):
            body = render_gt_page(
                gt_versions=list_gt_versions(),
                current_gt=get_current_gt_version_id(),
            ).encode("utf-8")
            self._bytes(200, body, "text/html; charset=utf-8")
            return

        if path in ("/discover", "/manage/discover", "/discover.html"):
            body = render_discover_page().encode("utf-8")
            self._bytes(200, body, "text/html; charset=utf-8")
            return

        if path in ("/discover/trend", "/manage/discover/trend"):
            days = calendar_window(14)
            docs = {}
            for d in days:
                doc = load_day(d)
                if doc:
                    docs[d] = doc
            body = render_trend_page(days=days, docs_by_day=docs).encode("utf-8")
            self._bytes(200, body, "text/html; charset=utf-8")
            return

        if path.startswith("/discover/trend/"):
            rest = unquote(path[len("/discover/trend/") :]).strip("/")
            parts = [p for p in rest.split("/") if p]
            if len(parts) == 1:
                try:
                    day = validate_day(parts[0])
                except Exception as e:
                    self._json(400, {"ok": False, "error": str(e)})
                    return
                qs = parse_qs(parsed.query)
                kind = (qs.get("kind") or [""])[0]
                facet = (qs.get("facet") or [""])[0]
                status = (qs.get("status") or [""])[0]
                try:
                    page = int((qs.get("page") or ["1"])[0] or 1)
                except ValueError:
                    page = 1
                try:
                    page_size = int((qs.get("ps") or qs.get("page_size") or ["10"])[0] or 10)
                except ValueError:
                    page_size = 10
                doc = load_day(day)
                body = render_day_page(
                    day=day,
                    doc=doc,
                    kind=kind,
                    facet=facet,
                    status=status,
                    page=page,
                    page_size=page_size,
                ).encode("utf-8")
                self._bytes(200, body, "text/html; charset=utf-8")
                return

        if path in ("/discover/compare", "/manage/discover/compare"):
            qs = parse_qs(parsed.query)

            def _q(*keys: str) -> str:
                for k in keys:
                    v = (qs.get(k) or [""])[0]
                    if str(v).strip():
                        return str(v).strip()
                return ""

            oid = _q("openId", "open_id")
            hole = _q("holeCards", "hole_cards", "hole")
            start = _q("start", "startTime", "firstSeen")
            end = _q("end", "endTime", "lastSeen")
            if not (oid and hole and start and end):
                self._json(
                    400,
                    {"ok": False, "error": "缺少 openId / 底牌 / 时间窗"},
                )
                return
            body = render_discover_compare_loading_page(
                open_id=oid,
                hole_cards=hole,
                start=start,
                end=end,
            ).encode("utf-8")
            self._bytes(200, body, "text/html; charset=utf-8")
            return

        if path.startswith("/discover/compare/"):
            rest = unquote(path[len("/discover/compare/") :]).strip("/")
            parts = [p for p in rest.split("/") if p]
            if len(parts) == 1:
                cid = parts[0]
                try:
                    meta = load_discover_meta(cid)
                    summary = load_discover_summary(cid)
                except Exception as e:
                    code = 404 if isinstance(e, (FileNotFoundError, ValueError)) else 500
                    self._json(code, {"ok": False, "error": str(e)})
                    return
                body = render_discover_compare_index(
                    compare_id=cid, meta=meta, summary=summary
                ).encode("utf-8")
                self._bytes(200, body, "text/html; charset=utf-8")
                return
            if len(parts) == 2:
                cid, nth_s = parts[0], parts[1]
                try:
                    nth = int(nth_s)
                    step = load_discover_step(cid, nth)
                except Exception as e:
                    code = 404 if isinstance(
                        e, (FileNotFoundError, ValueError, KeyError)
                    ) else 500
                    self._json(code, {"ok": False, "error": str(e)})
                    return
                body = render_step_detail_page(
                    run_id=cid, step=step, pair_mode=True
                ).encode("utf-8")
                self._bytes(200, body, "text/html; charset=utf-8")
                return

        if path in ("/gt-steps", "/manage/gt-steps", "/gt-steps.html"):
            body = render_gt_steps_index(
                gt_versions=list_gt_versions(),
                current_gt=get_current_gt_version_id(),
            ).encode("utf-8")
            self._bytes(200, body, "text/html; charset=utf-8")
            return

        if path in ("/step-compare", "/manage/step-compare", "/step-compare.html"):
            body = render_step_compare_list_page(runs=list_step_runs()).encode("utf-8")
            self._bytes(200, body, "text/html; charset=utf-8")
            return

        if path in ("/step-compare/new", "/manage/step-compare/new"):
            body = render_step_compare_new_page(
                gt_versions=list_gt_versions(),
                current_gt=get_current_gt_version_id(),
                trace_cfg=_template_trace_cfg(),
            ).encode("utf-8")
            self._bytes(200, body, "text/html; charset=utf-8")
            return

        if path.startswith("/step-compare/"):
            rest = unquote(path[len("/step-compare/") :]).strip("/")
            parts = [p for p in rest.split("/") if p]
            if len(parts) == 1 and parts[0] != "new":
                rid = parts[0]
                try:
                    meta = load_step_run_meta(rid)
                    summary = load_step_run_summary(rid)
                except Exception as e:
                    self._json(404, {"ok": False, "error": str(e)})
                    return
                body = render_step_run_index_html(
                    run_id=rid, meta=meta, summary=summary
                ).encode("utf-8")
                self._bytes(200, body, "text/html; charset=utf-8")
                return
            if len(parts) == 3:
                rid, hid, nth_s = parts[0], parts[1], parts[2]
                try:
                    nth = int(nth_s)
                    step = load_step_result(rid, f"{hid}#P0-{nth}")
                except Exception as e:
                    code = 404 if isinstance(e, (FileNotFoundError, ValueError, KeyError)) else 500
                    self._json(code, {"ok": False, "error": str(e)})
                    return
                body = render_step_detail_page(run_id=rid, step=step).encode("utf-8")
                self._bytes(200, body, "text/html; charset=utf-8")
                return

        if path.startswith("/gt-steps/"):
            rest = unquote(path[len("/gt-steps/") :]).strip("/")
            parts = [p for p in rest.split("/") if p]
            if len(parts) == 1:
                vid = parts[0]
                try:
                    meta, _hands = load_gt_version(vid)
                    brief = list_version_steps_brief(vid)
                except Exception as e:
                    self._json(404, {"ok": False, "error": str(e)})
                    return
                body = render_gt_steps_version_page(
                    version_id=vid,
                    meta=meta,
                    brief=brief,
                    current_gt=get_current_gt_version_id(),
                ).encode("utf-8")
                self._bytes(200, body, "text/html; charset=utf-8")
                return
            if len(parts) == 3:
                vid, hid, nth_s = parts[0], parts[1], parts[2]
                try:
                    nth = int(nth_s)
                    detail = get_step_detail(vid, hid, nth)
                except Exception as e:
                    code = 404 if isinstance(e, (KeyError, ValueError)) else 500
                    self._json(code, {"ok": False, "error": str(e)})
                    return
                body = render_gt_step_detail_page(
                    version_id=vid,
                    hand_uid=hid,
                    nth=nth,
                    detail=detail,
                ).encode("utf-8")
                self._bytes(200, body, "text/html; charset=utf-8")
                return

        if path in ("/api/gt-steps",):
            qs = parse_qs(parsed.query)
            vid = (qs.get("version_id") or [""])[0]
            try:
                brief = list_version_steps_brief(vid)
            except Exception as e:
                self._json(404, {"ok": False, "error": str(e)})
                return
            self._json(200, {"ok": True, **brief})
            return

        if path in ("/api/gt-step",):
            qs = parse_qs(parsed.query)
            vid = (qs.get("version_id") or [""])[0]
            hid = (qs.get("hand_uid") or [""])[0]
            try:
                nth = int((qs.get("nth") or ["0"])[0])
                detail = get_step_detail(vid, hid, nth)
            except Exception as e:
                code = 404 if isinstance(e, (KeyError, ValueError)) else 500
                self._json(code, {"ok": False, "error": str(e)})
                return
            self._json(200, {"ok": True, **detail})
            return

        if path.startswith("/api/step-compare/") and path.endswith("/trace-query"):
            # GET /api/step-compare/<id>/trace-query — 只读本跑批冻结条件
            parts = [p for p in path.strip("/").split("/") if p]
            # api, step-compare, <id>, trace-query
            if len(parts) == 4:
                rid = parts[2]
                try:
                    meta = load_step_run_meta(rid)
                    tq = load_step_run_trace_query(rid)
                except Exception as e:
                    self._json(404, {"ok": False, "error": str(e)})
                    return
                self._json(
                    200,
                    {
                        "ok": True,
                        "run_id": rid,
                        "readonly": bool(meta.get("readonly", True)),
                        "isolation": meta.get("isolation") or "per_run_dir",
                        "trace_query": tq,
                    },
                )
                return

        if path.startswith("/api/step-compare/") and "/hands/" in path and path.endswith("/spans"):
            # GET /api/step-compare/<id>/hands/<hand>/spans
            parts = [p for p in path.strip("/").split("/") if p]
            # api step-compare <id> hands <hand> spans
            if len(parts) == 6 and parts[3] == "hands":
                rid, hid = parts[2], parts[4]
                try:
                    snap = load_hand_spans(rid, hid)
                except Exception as e:
                    self._json(404, {"ok": False, "error": str(e)})
                    return
                self._json(200, {"ok": True, "run_id": rid, "hand_uid": hid, **snap})
                return

        if path.startswith("/api/daily-sig-chess-job/"):
            jid = unquote(path[len("/api/daily-sig-chess-job/") :]).strip("/")
            job = get_job(jid) if jid else None
            if not job:
                self._json(404, {"ok": False, "error": "任务不存在"})
                return
            self._json(200, {"ok": True, "job": job, "job_id": job.get("id")})
            return

        if path in ("/api/trace-discover",):
            qs = parse_qs(parsed.query)
            try:
                rows = _run_trace_discover(
                    start_time=(qs.get("startTime") or qs.get("start_time") or [""])[0],
                    end_time=(qs.get("endTime") or qs.get("end_time") or [""])[0],
                    trace_env=(qs.get("traceEnv") or qs.get("trace_env") or [""])[0],
                    api=(qs.get("api") or [""])[0],
                )
            except Exception as e:
                code = 400 if isinstance(e, (KeyError, ValueError)) else 502
                self._json(code, {"ok": False, "error": str(e)})
                return
            self._json(
                200,
                {
                    "ok": True,
                    "success": True,
                    "result": rows,
                    "rows": rows,
                    "n": len(rows),
                },
            )
            return

        if path in ("/settings", "/manage/settings", "/settings.html"):
            body = render_settings_page().encode("utf-8")
            self._bytes(200, body, "text/html; charset=utf-8")
            return

        if path in ("/api/settings",):
            from trace_envs import DEFAULT_TRACE_ENV, get_trace_env, resolve_api_base

            cfg = load_trace_api_settings()
            try:
                env = get_trace_env(str(cfg.get("traceEnv") or DEFAULT_TRACE_ENV))
            except KeyError:
                env = get_trace_env(DEFAULT_TRACE_ENV)
            self._json(
                200,
                {
                    "ok": True,
                    "settings": {
                        "api": resolve_api_base(env["id"], override=str(cfg.get("api") or "")),
                        "trace_env": env["id"],
                        "env_label": env.get("env_label") or env["id"],
                    },
                },
            )
            return

        if path.startswith("/gt/"):
            vid = unquote(path[len("/gt/") :]).strip("/")
            if vid and "/" not in vid and vid not in ("manage",):
                try:
                    meta, _hands = load_gt_version(vid)
                    brief = list_gt_hands_brief(vid)
                except Exception as e:
                    self._json(404, {"ok": False, "error": str(e)})
                    return
                body = render_gt_detail_page(
                    version_id=vid,
                    meta=meta,
                    hands_brief=brief,
                    current_gt=get_current_gt_version_id(),
                ).encode("utf-8")
                self._bytes(200, body, "text/html; charset=utf-8")
                return

        if path in ("/api/gt-hand",):
            qs = parse_qs(parsed.query)
            vid = (qs.get("version_id") or [""])[0]
            hid = (qs.get("hand_uid") or [""])[0]
            try:
                hand = get_gt_hand(vid, hid)
            except Exception as e:
                self._json(404, {"ok": False, "error": str(e)})
                return
            self._json(200, {"ok": True, "hand": hand})
            return

        if path in ("/api/hand-gt-norm",):
            qs = parse_qs(parsed.query)
            vid = (qs.get("version_id") or [""])[0]
            hid = (qs.get("hand_uid") or [""])[0]
            try:
                result = load_normalized_gt_hand(hid, vid)
            except Exception as e:
                self._json(404, {"ok": False, "error": str(e)})
                return
            self._json(200, result)
            return

        if path in ("/trace_query.html", "/trace-query"):
            body = (
                "<!DOCTYPE html><meta charset=utf-8>"
                "<title>已取消全局 Trace 配置</title>"
                "<p>全局 <code>data/trace_query.json</code> 已删除。"
                "请到 <a href='/rerun'>生成报告</a> 填写本报告条件，"
                "或打开具体 <a href='/'>对比报告</a> 在总览页编辑该报告的 Trace。</p>"
            ).encode("utf-8")
            self._bytes(410, body, "text/html; charset=utf-8")
            return

        # Frozen run static files: /runs/<id>/...
        if path.startswith("/runs/"):
            rel = path[len("/runs/") :]
            parts = rel.split("/", 1)
            if not parts or not parts[0]:
                self.send_response(404)
                self._cors()
                self.end_headers()
                return
            run_id = parts[0]
            rest = parts[1] if len(parts) > 1 else "index.html"
            if rest in ("", "/"):
                rest = "index.html"
            # prevent path escape
            if ".." in rest.split("/"):
                self.send_response(400)
                self._cors()
                self.end_headers()
                return
            f = RUNS_ROOT / run_id / rest
            if rest == "index.html" and f.exists():
                try:
                    text = f.read_text(encoding="utf-8", errors="replace")
                    text = rewrite_file_uris_to_local_shot(text)
                    cfg = load_run_trace_query(run_id)
                    if not isinstance(cfg, dict):
                        cfg = {}
                    text = inject_run_trace_form(text, run_id, cfg)
                    self._bytes(200, text.encode("utf-8"), "text/html; charset=utf-8")
                    return
                except Exception:
                    pass
            # 证据页：强制用本跑批冻结的 Trace 条件（勿用全局 data/trace_query.json）
            if (
                rest.startswith("hands/")
                and rest.endswith(".html")
                and f.exists()
                and f.is_file()
            ):
                try:
                    text = f.read_text(encoding="utf-8", errors="replace")
                    text = rewrite_file_uris_to_local_shot(text)
                    cfg = load_run_trace_query(run_id)
                    if not isinstance(cfg, dict):
                        cfg = {}
                    text = apply_run_trace_to_hand_html(text, run_id, cfg)
                    text = inject_live_hand_refresh(text)
                    self._bytes(200, text.encode("utf-8"), "text/html; charset=utf-8")
                    return
                except Exception:
                    pass
            if self._serve_file(f):
                return
            self.send_response(404)
            self._cors()
            self.end_headers()
            return

        if path == "/index.html" or path == "/output/index.html":
            f = OUT / "index.html"
            if self._serve_file(f):
                return
        # Serve evidence pages & assets under output/
        rel = path.lstrip("/")
        if rel.startswith("output/"):
            rel = rel[len("output/") :]
        if rel.startswith("hands/") or rel in ("index.html", "trace_query.html", "summary.json", "REPORT.md"):
            f = OUT / rel
            if self._serve_file(f):
                return
        self.send_response(404)
        self._cors()
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("body must be a JSON object")
        except Exception as e:
            self._json(400, {"ok": False, "error": str(e)})
            return

        if path == "/save-trace-query":
            self._json(
                410,
                {
                    "ok": False,
                    "error": "已取消全局 Trace 配置；请在生成报告时提交，或到 /runs/<id>/ 保存本报告条件",
                },
            )
            return

        if path in ("/save-hand-bugs", "/api/save-hand-bugs"):
            try:
                path_out = save_hand_bugs(payload, BUGS_PATH)
            except Exception as e:
                self._json(500, {"ok": False, "error": str(e)})
                return
            self._json(
                200,
                {
                    "ok": True,
                    "path": str(path_out.relative_to(ROOT)),
                    "n": len(load_hand_bugs(BUGS_PATH)),
                },
            )
            return

        if path in ("/api/rerun-report",):
            try:
                tq = payload.get("trace_query") or payload.get("trace_cfg") or {}
                if not isinstance(tq, dict):
                    tq = {}
                meta = rerun_report(
                    run_id=str(payload.get("run_id") or ""),
                    tags=payload.get("tags") if isinstance(payload.get("tags"), list) else None,
                    note=str(payload.get("note") or ""),
                    gt_version=str(payload.get("gt_version") or "") or None,
                    new_csv=str(payload.get("new_csv") or "data/new.csv"),
                    overwrite=bool(payload.get("overwrite")),
                    skip_trace=payload.get("skip_trace", True) is not False,
                    trace_cfg=tq,
                    hand_uids=(
                        payload.get("hand_uids")
                        or payload.get("hands")
                        or payload.get("batch_hands")
                    ),
                )
            except Exception as e:
                self._json(400, {"ok": False, "error": str(e)})
                return
            self._json(200, {"ok": True, "meta": meta})
            return

        if path in ("/api/step-compare-run",):
            try:
                from step_compare import run_step_compare

                tq = payload.get("trace_query") or payload.get("trace_cfg") or {}
                if not isinstance(tq, dict):
                    tq = {}
                result = run_step_compare(
                    run_id=str(payload.get("run_id") or ""),
                    gt_version=str(payload.get("gt_version") or ""),
                    note=str(payload.get("note") or ""),
                    tags=payload.get("tags") if isinstance(payload.get("tags"), list) else None,
                    overwrite=bool(payload.get("overwrite")),
                    skip_trace=bool(payload.get("skip_trace")),
                    trace_query=tq,
                    hand_uids=(
                        payload.get("hand_uids")
                        or payload.get("hands")
                        or payload.get("batch_hands")
                    ),
                )
            except Exception as e:
                code = 403 if isinstance(e, PermissionError) else 400
                self._json(code, {"ok": False, "error": str(e)})
                return
            self._json(200, result)
            return

        # 禁止对决策点跑批原地改 Trace（隔离）
        if path.startswith("/api/step-compare/") and path.endswith("/trace-query"):
            from step_run_store import reject_inplace_trace_update

            parts = [p for p in path.strip("/").split("/") if p]
            rid = parts[2] if len(parts) >= 3 else ""
            try:
                reject_inplace_trace_update(rid)
            except Exception as e:
                self._json(403, {"ok": False, "error": str(e)})
                return
            self._json(403, {"ok": False, "error": "unreachable"})
            return

        if path in ("/api/settings/trace-api", "/api/settings/clickhouse", "/api/settings"):
            try:
                api = str(payload.get("api") or "").strip().rstrip("/")
                if not api:
                    raise ValueError("api 不能为空")
                from trace_envs import resolve_api_base

                env_id = str(payload.get("traceEnv") or payload.get("trace_env") or "uat")
                save_trace_api_settings({"api": api, "traceEnv": env_id})
                resolved = resolve_api_base(env_id, override=api)
            except Exception as e:
                self._json(400, {"ok": False, "error": str(e)})
                return
            self._json(
                200,
                {
                    "ok": True,
                    "path": "data/trace_api.json",
                    "settings": {"api": resolved, "trace_env": env_id},
                },
            )
            return

        if path in ("/api/settings/test-trace-api", "/api/settings/test-ch"):
            try:
                from trace_client import TraceClient
                from trace_envs import DEFAULT_TRACE_ENV, resolve_api_base

                api = str(payload.get("api") or "").strip()
                env_id = str(payload.get("traceEnv") or payload.get("trace_env") or DEFAULT_TRACE_ENV)
                base = resolve_api_base(env_id, override=api)
                client = TraceClient(env_id=env_id, base_url=base)
                # lightweight ping: empty discover over a tiny window still hits the service
                client.trace_discover(
                    start_time="2000-01-01 00:00:00",
                    end_time="2000-01-01 00:00:01",
                )
            except Exception as e:
                self._json(502, {"ok": False, "error": str(e)})
                return
            self._json(200, {"ok": True, "api": base, "hint": "traceDiscover ok"})
            return

        # POST /api/runs/<id>/refresh-trace — 保存 Trace、重导真值、重拉 Trace / 重比
        if path.startswith("/api/runs/") and path.endswith("/refresh-trace"):
            parts = path.strip("/").split("/")
            # api / runs / <id> / refresh-trace
            run_id = parts[2] if len(parts) >= 4 else ""
            try:
                validate_run_id(run_id)
                cfg = {
                    k: v
                    for k, v in payload.items()
                    if not str(k).startswith("_")
                }
                meta = refresh_run_trace(
                    run_id,
                    cfg,
                    new_csv=str(payload.get("_new_csv") or "data/new.csv"),
                    skip_trace=bool(payload.get("_skip_trace")),
                    skip_gt=bool(payload.get("_skip_gt")),
                )
            except Exception as e:
                self._json(400, {"ok": False, "error": str(e)})
                return
            self._json(200, {"ok": True, "meta": meta})
            return

        if path in ("/api/import-gt",):
            try:
                meta = import_gt_from_excel(
                    str(payload.get("excel_path") or "data/old.xlsx"),
                    str(payload.get("version_id") or ""),
                    tags=payload.get("tags") if isinstance(payload.get("tags"), list) else None,
                    note=str(payload.get("note") or ""),
                    set_current=payload.get("set_current", True) is not False,
                )
            except Exception as e:
                self._json(400, {"ok": False, "error": str(e)})
                return
            self._json(200, {"ok": True, "meta": meta})
            return

        if path in ("/api/set-current-gt",):
            try:
                set_current_gt_version(str(payload.get("version_id") or ""))
            except Exception as e:
                self._json(400, {"ok": False, "error": str(e)})
                return
            self._json(200, {"ok": True, "current_gt": get_current_gt_version_id()})
            return

        if path in ("/api/update-gt-meta",):
            try:
                meta = update_gt_meta(
                    str(payload.get("version_id") or ""),
                    tags=payload.get("tags") if isinstance(payload.get("tags"), list) else None,
                    note=None if "note" not in payload else str(payload.get("note") or ""),
                )
            except Exception as e:
                self._json(400, {"ok": False, "error": str(e)})
                return
            self._json(200, {"ok": True, "meta": meta})
            return

        if path in ("/api/update-gt-hand",):
            try:
                result = update_gt_hand(
                    str(payload.get("version_id") or ""),
                    str(payload.get("hand_uid") or ""),
                    hole_key=None
                    if "hole_key" not in payload
                    else str(payload.get("hole_key") or ""),
                    gt_raw=payload.get("gt_raw"),
                    old_req_raw=payload.get("old_req_raw"),
                    update_gt=bool(payload.get("update_gt")),
                    update_old=bool(payload.get("update_old")),
                )
            except Exception as e:
                self._json(400, {"ok": False, "error": str(e)})
                return
            self._json(200, {"ok": True, **result})
            return

        if path in ("/api/trace-query", "/trace-query"):
            try:
                from trace_client import TraceClient, TraceClientError
                from trace_envs import DEFAULT_TRACE_ENV, normalize_trace_env, resolve_api_base

                env_id = normalize_trace_env(
                    str(
                        payload.get("traceEnv")
                        or payload.get("trace_env")
                        or DEFAULT_TRACE_ENV
                    )
                )
                api = str(payload.get("api") or "").strip()
                client = TraceClient(
                    env_id=env_id,
                    base_url=resolve_api_base(env_id, override=api),
                )
                from trace_query_config import _norm_time

                spans = client.trace_query(
                    open_id=str(payload.get("openId") or payload.get("open_id") or ""),
                    hole_cards=str(
                        payload.get("holeCards") or payload.get("hole_cards") or ""
                    ),
                    start_time=_norm_time(
                        str(
                            payload.get("startTime")
                            or payload.get("start_time")
                            or ""
                        )
                    ),
                    end_time=_norm_time(
                        str(
                            payload.get("endTime") or payload.get("end_time") or ""
                        )
                    ),
                )
            except Exception as e:
                code = 400 if isinstance(e, KeyError) else 502
                self._json(code, {"ok": False, "error": str(e)})
                return
            self._json(
                200,
                {
                    "ok": True,
                    "success": True,
                    "trace_env": env_id,
                    "api": client.base_url,
                    "result": spans,
                    "spans": spans,
                },
            )
            return

        if path in ("/api/discover-compare",):
            try:
                result = compare_hand_signal_chess(
                    open_id=str(
                        payload.get("openId") or payload.get("open_id") or ""
                    ),
                    hole_cards=str(
                        payload.get("holeCards")
                        or payload.get("hole_cards")
                        or payload.get("hole")
                        or ""
                    ),
                    start_time=str(
                        payload.get("startTime")
                        or payload.get("start_time")
                        or payload.get("start")
                        or ""
                    ),
                    end_time=str(
                        payload.get("endTime")
                        or payload.get("end_time")
                        or payload.get("end")
                        or ""
                    ),
                    trace_env=str(
                        payload.get("traceEnv") or payload.get("trace_env") or ""
                    ),
                    api=str(payload.get("api") or ""),
                )
            except Exception as e:
                code = 400 if isinstance(e, ValueError) else 502
                self._json(code, {"ok": False, "error": str(e)})
                return
            self._json(200, result)
            return

        if path in ("/api/daily-sig-chess-run",):
            try:
                job = start_daily_job(
                    str(payload.get("date") or payload.get("day") or ""),
                    max_hands=int(payload.get("max_hands") or payload.get("maxHands") or 500),
                    trace_env=str(
                        payload.get("traceEnv") or payload.get("trace_env") or ""
                    ),
                    api=str(payload.get("api") or ""),
                    start_time=str(
                        payload.get("startTime")
                        or payload.get("start_time")
                        or payload.get("start")
                        or ""
                    ),
                    end_time=str(
                        payload.get("endTime")
                        or payload.get("end_time")
                        or payload.get("end")
                        or ""
                    ),
                )
            except Exception as e:
                code = 400 if isinstance(e, ValueError) else 500
                self._json(code, {"ok": False, "error": str(e)})
                return
            self._json(200, {"ok": True, "job": job, "job_id": job.get("id")})
            return

        if path in ("/api/trace-discover",):
            try:
                rows = _run_trace_discover(
                    start_time=str(
                        payload.get("startTime") or payload.get("start_time") or ""
                    ),
                    end_time=str(
                        payload.get("endTime") or payload.get("end_time") or ""
                    ),
                    trace_env=str(
                        payload.get("traceEnv") or payload.get("trace_env") or ""
                    ),
                    api=str(payload.get("api") or ""),
                )
            except Exception as e:
                code = 400 if isinstance(e, (KeyError, ValueError)) else 502
                self._json(code, {"ok": False, "error": str(e)})
                return
            self._json(
                200,
                {
                    "ok": True,
                    "success": True,
                    "result": rows,
                    "rows": rows,
                    "n": len(rows),
                },
            )
            return

        if path in ("/render-hand-trace", "/api/render-hand-trace"):
            try:
                result = render_hand_modules_from_spans(payload)
            except Exception as e:
                self._json(500, {"ok": False, "error": str(e)})
                return
            self._json(200, result)
            return

        if path in ("/fetch-hand-trace", "/api/fetch-hand-trace"):
            self._json(
                200,
                {
                    "ok": False,
                    "error": (
                        "已改为 data-platform /api/v1/traceQuery（或 POST /api/trace-query 代理）。"
                        "请刷新证据页。"
                    ),
                    "deprecated": True,
                },
            )
            return

        self._json(404, {"ok": False, "error": "not found"})


def main() -> None:
    parser = argparse.ArgumentParser(description="GTO QA Trace 本地/内网服务")
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help="监听地址。内网分享请用 0.0.0.0（默认 127.0.0.1 仅本机）",
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="端口（默认 8766）")
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    RUNS_ROOT.mkdir(parents=True, exist_ok=True)
    # 全局 Trace 配置已移除；启动时不再写 output/trace_query.html
    dirs = collect_shot_dirs()

    httpd = ReuseHTTPServer((args.host, args.port), Handler)
    print(f"QA 管理服务已启动")
    print(f"  管理入口: http://127.0.0.1:{args.port}/")
    print(f"  当前总览: http://127.0.0.1:{args.port}/output/index.html")
    if args.host in ("0.0.0.0", "::"):
        lan = _lan_ips()
        if lan:
            for ip in lan:
                print(f"  内网入口: http://{ip}:{args.port}/")
                print(f"  当前总览: http://{ip}:{args.port}/output/index.html")
        else:
            print(f"  内网:   http://<你的局域网IP>:{args.port}/  （请本机 ifconfig/ipconfig 查看）")
    else:
        print(f"  绑定:   http://{args.host}:{args.port}/")
    print(f"  Trace:  每报告 data/runs/<id>/trace_query.json（已取消全局配置）")
    if dirs:
        print("  截图目录:")
        for d in dirs:
            print(f"    - {d}")
    else:
        print("  截图目录: 未配置（同事看不到牌桌图）。在 Trace 查询条件填 origShotsDir / shotsDir 并保存。")
    print("  提示: 内网分享请用 --host 0.0.0.0；macOS 若拦访问请允许 Python 入站。")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
