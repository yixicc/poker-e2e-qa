#!/usr/bin/env python3
"""Load Trace Viewer–aligned query config for core-module fetches."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "data" / "trace_query.json"
# 已废弃全局 Trace 配置；保留常量仅兼容旧 CLI 显式 --trace-config 路径。
LOCAL_PATHS_PATH = Path(__file__).resolve().parent.parent / "data" / "local_paths.json"
TRACE_API_PATH = Path(__file__).resolve().parent.parent / "data" / "trace_api.json"

# openIdMode:
#   config_first — 配置 openId 优先（模拟器 userId 变了时用这个）
#   data_first   — 数据里的 user_token 优先，配置作兜底
#   config_only  — 只用配置 openId
VALID_OPEN_ID_MODES = ("config_first", "data_first", "config_only")


def compact_hole_id(hole_key: Any) -> str:
    """手牌 ID 紧凑写法，如 QC5S / QC5H（Trace Viewer Cards 栏同款）。"""
    import re

    if hole_key is None:
        return ""
    if isinstance(hole_key, list):
        return "".join(str(c).strip() for c in hole_key if str(c).strip())
    text = str(hole_key).strip()
    if not text:
        return ""
    try:
        parsed = json.loads(text.replace("'", '"'))
        if isinstance(parsed, list):
            return "".join(str(c).strip() for c in parsed if str(c).strip())
    except Exception:
        pass
    return re.sub(r"[^A-Za-z0-9]", "", text)


def load_trace_api_settings(path: Optional[str | Path] = None) -> dict[str, Any]:
    """可选 API Base 覆盖（非查询时间窗）。"""
    p = Path(path) if path else TRACE_API_PATH
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def save_trace_api_settings(cfg: dict[str, Any], path: Optional[str | Path] = None) -> Path:
    p = Path(path) if path else TRACE_API_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "_comment": "可选：覆盖 data-platform API Base。留空则用环境目录默认 UAT。",
        "api": str(cfg.get("api") or "").strip().rstrip("/"),
        "traceEnv": str(cfg.get("traceEnv") or "uat").strip() or "uat",
    }
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p


def load_trace_query_config(path: Optional[str | Path] = None) -> dict[str, Any]:
    """Load a Trace 条件 JSON。未传 path 时不再隐式读全局文件，返回 {}。"""
    if path is None:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {}
    # Drop example-only keys under hands
    hands = raw.get("hands")
    if isinstance(hands, dict):
        cleaned = {
            k: v
            for k, v in hands.items()
            if not str(k).startswith("_") and isinstance(v, dict)
        }
        raw = dict(raw)
        raw["hands"] = cleaned
    return raw


def _pick_hand_override(cfg: dict[str, Any], *, hand_uid: str, hole_key: str) -> dict[str, Any]:
    hands = cfg.get("hands") or {}
    if not isinstance(hands, dict):
        return {}
    for key in (hand_uid, hole_key, (hole_key or "").upper(), (hole_key or "").lower()):
        if key and key in hands and isinstance(hands[key], dict):
            return hands[key]
    return {}


def resolve_trace_query(
    cfg: dict[str, Any],
    *,
    hand_uid: str,
    hole_key: str,
    data_open_id: str = "",
) -> dict[str, Any]:
    """Resolve effective Trace query params for one hand.

    Returns keys used by fetch_hand_spans + display fields for evidence page:
      trace_env, api (legacy), open_id, fallback_open_id, hole_key/cards,
      start_time, end_time, pad_minutes, open_id_mode, env_label
    """
    from trace_envs import DEFAULT_TRACE_ENV, get_trace_env, normalize_trace_env

    ov = _pick_hand_override(cfg, hand_uid=hand_uid, hole_key=hole_key)
    mode = str(ov.get("openIdMode") or cfg.get("openIdMode") or "config_first").strip()
    if mode not in VALID_OPEN_ID_MODES:
        mode = "config_first"

    cfg_oid = str(ov.get("openId") or cfg.get("openId") or "").strip()
    data_oid = str(data_open_id or "").strip()

    if mode == "config_only":
        primary, fallback = cfg_oid, ""
    elif mode == "data_first":
        primary, fallback = data_oid or cfg_oid, (cfg_oid if data_oid and cfg_oid != data_oid else "")
    else:  # config_first
        primary, fallback = cfg_oid or data_oid, (data_oid if cfg_oid and data_oid and cfg_oid != data_oid else "")

    cards_raw = str(ov.get("cards") or ov.get("holeCards") or "").strip()
    # 配置未写 cards 时，自动带入当前手牌 ID（QC5S 形式）
    cards = compact_hole_id(cards_raw) if cards_raw else compact_hole_id(hole_key)
    start = str(ov.get("startTime") or cfg.get("startTime") or "").strip()
    end = str(ov.get("endTime") or cfg.get("endTime") or "").strip()
    # Normalize common Trace Viewer datetime form "2026/08/03 17:45" → "2026-08-03 17:45:00"
    start = _norm_time(start)
    end = _norm_time(end)

    pad = ov.get("padMinutes", cfg.get("padMinutes", 15))
    try:
        pad_i = int(pad)
    except Exception:
        pad_i = 15

    api = str(ov.get("api") or cfg.get("api") or "").strip()
    raw_env = str(ov.get("traceEnv") or cfg.get("traceEnv") or "").strip()
    if not raw_env:
        raw_env = DEFAULT_TRACE_ENV
    try:
        from trace_envs import resolve_api_base

        trace_env = normalize_trace_env(raw_env)
        env_meta = get_trace_env(trace_env)
        api = resolve_api_base(trace_env, override=api)
    except KeyError:
        trace_env = DEFAULT_TRACE_ENV
        env_meta = get_trace_env(trace_env)
        from trace_envs import resolve_api_base

        api = resolve_api_base(trace_env, override=api)
    env_label = str(
        ov.get("envLabel") or cfg.get("envLabel") or env_meta.get("env_label") or ""
    ).strip()

    return {
        "trace_env": trace_env,
        "api": api,
        "env_label": env_label,
        "open_id": primary,
        "fallback_open_id": fallback,
        "cards": cards,
        "hole_key": cards or compact_hole_id(hole_key),
        "start_time": start,
        "end_time": end,
        "pad_minutes": pad_i,
        "open_id_mode": mode,
        "hand_override": bool(ov),
        "config_open_id": cfg_oid,
        "data_open_id": data_oid,
    }


def _norm_time(text: str) -> str:
    """Normalize Trace API time strings.

    Fixes common paste/UI glitches:
      - ISO ``T`` separator → space
      - missing space: ``2026-08-1110:45:00`` → ``2026-08-11 10:45:00``
      - ``YYYY-MM-DD HH:MM`` → append ``:00``
    """
    if not text:
        return ""
    t = text.strip().replace("/", "-").replace("T", " ")
    t = re.sub(r"\s+", " ", t).strip()
    # 2026-08-1110:45:00 or 2026-08-1110:45
    m = re.match(
        r"^(\d{4}-\d{2}-\d{2})(\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?)$",
        t,
    )
    if m:
        t = f"{m.group(1)} {m.group(2)}"
    if re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$", t):
        t = t + ":00"
    return t


def is_valid_api_time(text: str) -> bool:
    """True if text looks like ``YYYY-MM-DD HH:MM:SS`` (optional fractional)."""
    t = _norm_time(text)
    return bool(re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)?$", t))


def query_summary_html(q: dict[str, Any]) -> str:
    """Compact HTML block showing the Trace query used (for evidence page)."""
    import html as html_mod

    def esc(s: Any) -> str:
        return html_mod.escape("" if s is None else str(s))

    if not q:
        return ""
    rows = [
        ("Trace 环境", q.get("trace_env") or q.get("env_label") or "—"),
        ("环境说明", q.get("env_label") or "—"),
        ("OpenID", q.get("open_id") or "—"),
        ("OpenID 模式", q.get("open_id_mode") or "—"),
        ("Cards", q.get("cards") or q.get("hole_key") or "—"),
        ("开始", q.get("start_time") or "（按决策点 ±pad）"),
        ("结束", q.get("end_time") or "（按决策点 ±pad）"),
    ]
    if q.get("fallback_open_id"):
        rows.insert(2, ("OpenID 兜底", q.get("fallback_open_id")))
    if q.get("data_open_id") and q.get("data_open_id") != q.get("open_id"):
        rows.append(("数据原 userId", q.get("data_open_id")))
    trs = "".join(
        f"<tr><th>{esc(k)}</th><td><code>{esc(v)}</code></td></tr>" for k, v in rows
    )
    note = "来自本报告 Trace 条件" + (" · 含单手覆盖" if q.get("hand_override") else "")
    cards = q.get("cards") or q.get("hole_key") or "—"
    oid = q.get("open_id") or "—"
    summary_meta = f"OpenID {oid} · Cards {cards}"
    return (
        f'<details class="trace-query-box">'
        f'<summary class="trace-query-sum">'
        f'<span>Trace 查询条件（核心模块取数）</span>'
        f'<span class="trace-query-meta">{esc(summary_meta)} · 点击展开</span>'
        f"</summary>"
        f'<div class="trace-query-body">'
        f'<div class="pane-label">{esc(note)}</div>'
        f'<table class="meta-table trace-query-table">{trs}</table>'
        f"</div></details>"
    )


TRACE_FORM_CSS = """
.tq-panel {
  margin: 0 0 28px; border: 1px solid #bae6fd; border-radius: 14px; background: #f0f9ff;
  overflow: hidden;
}
.tq-panel > summary.tq-sum {
  list-style: none; cursor: pointer; user-select: none;
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  padding: 12px 16px; font-size: 1.05rem; font-weight: 700; color: #0c4a6e;
}
.tq-panel > summary.tq-sum::-webkit-details-marker { display: none; }
.tq-panel > summary.tq-sum::before {
  content: "▸"; color: #0284c7; font-size: 12px; width: 14px; flex: 0 0 auto;
}
.tq-panel[open] > summary.tq-sum::before { content: "▾"; }
.tq-panel > summary.tq-sum:hover { background: #e0f2fe; }
.tq-sum-meta { font-size: 12px; font-weight: 600; color: #0369a1; margin-left: auto; }
.tq-body { padding: 0 16px 16px; border-top: 1px solid #bae6fd; }
.tq-standalone .tq-body { border-top: none; padding-top: 16px; }
.tq-hint { color: #0369a1; font-size: 13px; margin: 12px 0 14px; line-height: 1.45; }
.tq-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px 12px; align-items: end;
}
.tq-field label {
  display: block; font-size: 12px; font-weight: 650; color: #075985; margin-bottom: 4px;
}
.tq-field input, .tq-field select, .tq-field textarea {
  width: 100%; border: 1px solid #7dd3fc; border-radius: 8px;
  padding: 8px 10px; background: #fff; font-size: 13px; color: #0f172a;
}
.tq-field textarea { min-height: 72px; font-family: ui-monospace, monospace; font-size: 12px; }
.tq-field.wide { grid-column: 1 / -1; }
.tq-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; align-items: center; }
.tq-actions button {
  border: 1px solid #0284c7; background: #0284c7; color: #fff;
  border-radius: 8px; padding: 8px 14px; font-size: 13px; font-weight: 650; cursor: pointer;
}
.tq-actions button.secondary { background: #fff; color: #0369a1; }
.tq-actions button:hover { filter: brightness(1.05); }
.tq-status { font-size: 13px; color: #0c4a6e; min-height: 1.2em; }
.tq-status.ok { color: #166534; }
.tq-status.err { color: #9f1239; }
.tq-preview {
  margin-top: 12px; background: #0f172a; color: #e2e8f0; border-radius: 8px;
  padding: 10px 12px; font-size: 11px; max-height: 180px; overflow: auto;
  white-space: pre-wrap; word-break: break-word;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
"""


def render_trace_query_form(
    cfg: Optional[dict[str, Any]] = None,
    *,
    standalone: bool = False,
    run_id: Optional[str] = None,
) -> str:
    """Fillable Trace Viewer–style query form.

    - Run 页（run_id 或 URL /runs/<id>/）：保存到本 Run 并重拉 Trace / 重比
    - 生成报告页（无 run_id）：仅作本次生成入参，不写全局文件
    """
    import html as html_mod

    def esc(s: Any) -> str:
        return html_mod.escape("" if s is None else str(s))

    from trace_envs import DEFAULT_TRACE_ENV, get_trace_env, list_trace_envs, normalize_trace_env

    cfg = dict(cfg or {})
    rid = str(run_id or "").strip()
    hands = cfg.get("hands") if isinstance(cfg.get("hands"), dict) else {}
    hands_clean = {
        k: v for k, v in hands.items() if not str(k).startswith("_") and isinstance(v, dict)
    }
    hands_text = json.dumps(hands_clean, ensure_ascii=False, indent=2) if hands_clean else "{}"
    mode = str(cfg.get("openIdMode") or "config_first")
    opts = []
    for val, label in (
        ("config_first", "配置优先（模拟器 userId 变了用这个）"),
        ("data_first", "数据 userId 优先，配置作兜底"),
        ("config_only", "只用配置 OpenID"),
    ):
        sel = " selected" if mode == val else ""
        opts.append(f'<option value="{val}"{sel}>{esc(label)}</option>')

    try:
        cur_env = normalize_trace_env(str(cfg.get("traceEnv") or DEFAULT_TRACE_ENV))
    except KeyError:
        cur_env = DEFAULT_TRACE_ENV
    env_opts = []
    for env in list_trace_envs(enabled_only=True):
        eid = str(env.get("id") or "")
        sel = " selected" if eid == cur_env else ""
        env_opts.append(
            f'<option value="{esc(eid)}"{sel}>{esc(env.get("label") or eid)}</option>'
        )
    try:
        env_meta = get_trace_env(cur_env)
        default_env_label = str(cfg.get("envLabel") or env_meta.get("env_label") or "")
    except KeyError:
        default_env_label = str(cfg.get("envLabel") or "")

    nav = ""
    if standalone:
        nav = '<div class="nav" style="margin-bottom:12px"><a href="/">← 返回</a></div>'

    initial = {
        "traceEnv": cur_env,
        "envLabel": default_env_label,
        "openId": cfg.get("openId") or "",
        "openIdMode": mode,
        "startTime": cfg.get("startTime") or "",
        "endTime": cfg.get("endTime") or "",
        "padMinutes": cfg.get("padMinutes", 15),
        "origShotsDir": cfg.get("origShotsDir") or "",
        "shotsDir": cfg.get("shotsDir") or "",
        "hands": hands_clean,
    }
    initial_json = html_mod.escape(json.dumps(initial, ensure_ascii=False), quote=True)
    run_attr = f' data-run-id="{esc(rid)}"' if rid else ""

    open_id_show = str(cfg.get("openId") or "未填")
    time_show = ""
    if cfg.get("startTime") or cfg.get("endTime"):
        time_show = f" · {cfg.get('startTime') or '?'} ~ {cfg.get('endTime') or '?'}"

    if rid:
        hint = f"""  <p class="tq-hint">
    以下为生成本 Run（<code>{esc(rid)}</code>）时使用的 Trace 条件，可修改后保存。
    Trace 经 TexasDataCenter data-platform API 查询（与 Trace Viewer 相同）。
    保存将写入本 Run，并从 Excel 重导该 Run 绑定的正确值版本，再重新拉取 Trace、重新对比。
  </p>"""
        save_label = "保存并重拉 Trace / 真值"
        save_btn = f'<button type="button" id="tq-save">{esc(save_label)}</button>'
    else:
        hint = """  <p class="tq-hint">
    已取消全局 Trace 配置。此处条件仅用于<strong>本次生成报告</strong>，会冻结进该报告自己的
    <code>data/runs/&lt;id&gt;/trace_query.json</code>。已有报告请到对应总览页改 Trace。
  </p>"""
        save_btn = ""

    # 截图目录缺省时补 local_paths
    if not str(cfg.get("origShotsDir") or "").strip() or not str(cfg.get("shotsDir") or "").strip():
        try:
            from local_shots import load_local_paths

            lp = load_local_paths()
            if not str(cfg.get("origShotsDir") or "").strip() and lp.get("origShotsDir"):
                cfg["origShotsDir"] = lp.get("origShotsDir")
            if not str(cfg.get("shotsDir") or "").strip() and lp.get("shotsDir"):
                cfg["shotsDir"] = lp.get("shotsDir")
            # refresh initial after fill
            initial["origShotsDir"] = cfg.get("origShotsDir") or ""
            initial["shotsDir"] = cfg.get("shotsDir") or ""
            initial_json = html_mod.escape(json.dumps(initial, ensure_ascii=False), quote=True)
        except Exception:
            pass

    fields = f"""  <div class="tq-grid">
    <div class="tq-field">
      <label for="tq-openid">OpenID</label>
      <input id="tq-openid" type="text" value="{esc(cfg.get('openId') or '')}" placeholder="693ba6566e468032"/>
    </div>
    <div class="tq-field">
      <label for="tq-mode">OpenID 模式</label>
      <select id="tq-mode">{''.join(opts)}</select>
    </div>
    <div class="tq-field">
      <label for="tq-start">开始</label>
      <input id="tq-start" type="text" value="{esc(cfg.get('startTime') or '')}" placeholder="2026-08-03 17:45:00"/>
    </div>
    <div class="tq-field">
      <label for="tq-end">结束</label>
      <input id="tq-end" type="text" value="{esc(cfg.get('endTime') or '')}" placeholder="2026-08-05 19:52:00"/>
    </div>
    <div class="tq-field">
      <label for="tq-trace-env">查询环境</label>
      <select id="tq-trace-env">{''.join(env_opts)}</select>
    </div>
    <div class="tq-field">
      <label for="tq-env">环境说明 / API</label>
      <input id="tq-env" type="text" value="{esc(default_env_label)}" placeholder="UAT · 8.145.52.251:7121" readonly/>
    </div>
    <div class="tq-field">
      <label for="tq-pad">padMinutes（无固定时间窗时）</label>
      <input id="tq-pad" type="number" min="1" value="{esc(cfg.get('padMinutes', 15))}"/>
    </div>
    <div class="tq-field wide">
      <label for="tq-orig-shots">原图目录 origShotsDir（内网看图必填；Mac/Windows 本机绝对路径）</label>
      <input id="tq-orig-shots" type="text" value="{esc(cfg.get('origShotsDir') or '')}" placeholder="/Users/你/Downloads/0713图片和json 或 D:\\shots\\orig"/>
    </div>
    <div class="tq-field wide">
      <label for="tq-shots">重命名图目录 shotsDir（可选；orig 找不到时回退）</label>
      <input id="tq-shots" type="text" value="{esc(cfg.get('shotsDir') or '')}" placeholder="/Users/你/Downloads/手牌重命名 或 D:\\shots\\renamed"/>
    </div>
    <div class="tq-field wide">
      <label for="tq-hands">单手覆盖 hands（JSON，可选；键为 QC5H 或 HAND_001）</label>
      <textarea id="tq-hands" spellcheck="false">{esc(hands_text)}</textarea>
    </div>
  </div>
  <div class="tq-actions">
    {save_btn}
    <button type="button" class="secondary" id="tq-download">下载 JSON</button>
    <button type="button" class="secondary" id="tq-copy">复制 JSON</button>
    <span class="tq-status" id="tq-status"></span>
  </div>
  <pre class="tq-preview" id="tq-preview"></pre>"""

    # Standalone edit page: form open immediately (no collapsed intermediate click).
    # Index embed: keep collapsed details summary.
    if standalone:
        panel = f"""
{nav}
<div class="tq-panel tq-standalone" id="trace-query-form" data-initial="{initial_json}"{run_attr}>
  <div class="tq-body">
{hint}
{fields}
  </div>
</div>
"""
    else:
        panel = f"""
{nav}
<details class="tq-panel" id="trace-query-form" data-initial="{initial_json}"{run_attr}>
  <summary class="tq-sum">
    <span>Trace 查询条件</span>
    <span class="tq-sum-meta">OpenID {esc(open_id_show)}{esc(time_show)} · 点击展开</span>
  </summary>
  <div class="tq-body">
{hint}
{fields}
  </div>
</details>
"""

    env_labels_js = json.dumps(
        {
            e["id"]: e.get("env_label") or e.get("label") or e["id"]
            for e in list_trace_envs()
        },
        ensure_ascii=False,
    )
    env_apis_js = json.dumps(
        {e["id"]: e.get("api_base") or "" for e in list_trace_envs()},
        ensure_ascii=False,
    )
    return (
        panel
        + """
<script>
(function(){
  var root = document.getElementById('trace-query-form');
  if (!root) return;
  var statusEl = document.getElementById('tq-status');
  var preview = document.getElementById('tq-preview');
  var ENV_LABELS = """
        + env_labels_js
        + """;
  var ENV_APIS = """
        + env_apis_js
        + """;
  var pathMatch = (location.pathname || '').match(/\\/runs\\/([^\\/]+)\\//);
  var runId = (root.getAttribute('data-run-id') || (pathMatch && pathMatch[1]) || '').trim();
  var saveBtn = document.getElementById('tq-save');
  if (runId && saveBtn) saveBtn.textContent = '保存并重拉 Trace / 真值';
  function setStatus(msg, ok){
    statusEl.textContent = msg || '';
    statusEl.className = 'tq-status' + (ok === true ? ' ok' : (ok === false ? ' err' : ''));
  }
  function syncEnvLabel(){
    var sel = document.getElementById('tq-trace-env');
    var lab = document.getElementById('tq-env');
    if (!sel || !lab) return;
    lab.value = ENV_LABELS[sel.value] || sel.value || '';
  }
  function buildCfg(){
    var handsRaw = (document.getElementById('tq-hands').value || '').trim() || '{}';
    var hands;
    try { hands = JSON.parse(handsRaw); }
    catch (e) { throw new Error('单手覆盖 JSON 无效：' + e.message); }
    if (!hands || typeof hands !== 'object' || Array.isArray(hands)) {
      throw new Error('单手覆盖必须是 JSON 对象');
    }
    var pad = parseInt(document.getElementById('tq-pad').value || '15', 10);
    if (!isFinite(pad) || pad < 1) pad = 15;
    syncEnvLabel();
    var envId = (document.getElementById('tq-trace-env').value || 'uat').trim();
    return {
      _comment: 'Trace 经 data-platform HTTP API（与 Trace Viewer 相同）。',
      traceEnv: envId,
      api: (ENV_APIS[envId] || '').replace(/\\/$/, ''),
      envLabel: (document.getElementById('tq-env').value || '').trim(),
      openId: (document.getElementById('tq-openid').value || '').trim(),
      openIdMode: document.getElementById('tq-mode').value || 'config_first',
      startTime: (document.getElementById('tq-start').value || '').trim(),
      endTime: (document.getElementById('tq-end').value || '').trim(),
      padMinutes: pad,
      origShotsDir: (document.getElementById('tq-orig-shots').value || '').trim(),
      shotsDir: (document.getElementById('tq-shots').value || '').trim(),
      hands: hands
    };
  }
  function refreshPreview(){
    try {
      var cfg = buildCfg();
      preview.textContent = JSON.stringify(cfg, null, 2);
      setStatus('', null);
      return cfg;
    } catch (e) {
      setStatus(String(e.message || e), false);
      return null;
    }
  }
  ['tq-openid','tq-mode','tq-start','tq-end','tq-trace-env','tq-pad','tq-orig-shots','tq-shots','tq-hands'].forEach(function(id){
    var el = document.getElementById(id);
    if (!el) return;
    el.addEventListener('input', refreshPreview);
    el.addEventListener('change', refreshPreview);
  });
  var envSel = document.getElementById('tq-trace-env');
  if (envSel) envSel.addEventListener('change', function(){ syncEnvLabel(); refreshPreview(); });
  refreshPreview();

  document.getElementById('tq-download').addEventListener('click', function(){
    var cfg = refreshPreview();
    if (!cfg) return;
    var blob = new Blob([JSON.stringify(cfg, null, 2)], {type:'application/json'});
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'trace_query.json';
    a.click();
    URL.revokeObjectURL(a.href);
    setStatus('已下载 JSON（可作本报告 Trace 条件备份）', true);
  });

  document.getElementById('tq-copy').addEventListener('click', function(){
    var cfg = refreshPreview();
    if (!cfg) return;
    var text = JSON.stringify(cfg, null, 2);
    function ok(){ setStatus('已复制到剪贴板', true); }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(ok).catch(function(){
        setStatus('复制失败，请手动从下方预览复制', false);
      });
    } else {
      setStatus('请手动从下方预览复制', false);
    }
  });

  var saveBtn = document.getElementById('tq-save');
  if (saveBtn) saveBtn.addEventListener('click', function(){
    var cfg = refreshPreview();
    if (!cfg) return;
    if (!runId) {
      setStatus('已取消全局配置；请在「生成报告」页提交，或到具体报告页保存', false);
      return;
    }
    setStatus('正在保存并重拉 Trace / 真值 / 重比（可能需数十秒）…', null);
    saveBtn.disabled = true;
    fetch('/api/runs/' + encodeURIComponent(runId) + '/refresh-trace', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(cfg)
    }).then(function(res){
      return res.json().then(function(body){
        if (!res.ok || (body && body.ok === false)) {
          throw new Error((body && body.error) || ('HTTP ' + res.status));
        }
        setStatus('已更新本 Run，正在刷新页面…', true);
        location.reload();
      });
    }).catch(function(e){
      saveBtn.disabled = false;
      setStatus(String(e.message || e), false);
    });
  });
})();
</script>
"""
    )

_RUN_FORM_RE = re.compile(
    r'<details[^>]*\bid=["\']trace-query-form["\'][\s\S]*?</details>\s*<script>[\s\S]*?</script>',
    re.IGNORECASE,
)


def inject_run_trace_form(html: str, run_id: str, cfg: Optional[dict[str, Any]] = None) -> str:
    """Replace baked Trace form on a run index page with cfg from that run."""
    rid = str(run_id or "").strip()
    if not rid or "trace-query-form" not in html:
        return html
    form = render_trace_query_form(cfg or {}, standalone=False, run_id=rid)
    if _RUN_FORM_RE.search(html):
        # 用函数替换，避免 form 里的反斜杠被 re.sub 当转义
        return _RUN_FORM_RE.sub(lambda _m: form, html, count=1)
    return html


_LIVE_PAYLOAD_RE = re.compile(
    r'(<script\b[^>]*\bid=["\']live-trace-payload["\'][^>]*>)(.*?)(</script>)',
    re.IGNORECASE | re.DOTALL,
)


def apply_run_trace_to_hand_html(
    html: str, run_id: str, cfg: Optional[dict[str, Any]] = None
) -> str:
    """用本跑批冻结的 Trace 条件覆盖证据页 #live-trace-payload.query。

    每个报告自己的 start/end/openId/api，不回落到全局 data/trace_query.json。
    center_ms（截图文件名时间）保留，仅作无固定窗时的兜底，不覆盖配置窗。
    """
    rid = str(run_id or "").strip()
    if not rid or "live-trace-payload" not in html:
        return html
    m = _LIVE_PAYLOAD_RE.search(html)
    if not m:
        return html
    try:
        payload = json.loads(m.group(2) or "{}")
    except Exception:
        return html
    if not isinstance(payload, dict):
        return html
    cfg = cfg if isinstance(cfg, dict) else {}
    q_old = payload.get("query") if isinstance(payload.get("query"), dict) else {}
    resolved = resolve_trace_query(
        cfg,
        hand_uid=str(payload.get("hand_uid") or ""),
        hole_key=str(
            payload.get("hole_key")
            or payload.get("cards")
            or q_old.get("cards")
            or q_old.get("hole_key")
            or ""
        ),
        data_open_id=str(
            payload.get("user_token")
            or q_old.get("fallback_open_id")
            or q_old.get("open_id")
            or ""
        ),
    )
    payload["run_id"] = rid
    payload["query"] = {
        "trace_env": resolved.get("trace_env") or "uat",
        "api": resolved.get("api") or "",
        "env_label": resolved.get("env_label") or "",
        "open_id": resolved.get("open_id") or "",
        "fallback_open_id": resolved.get("fallback_open_id") or "",
        "cards": resolved.get("cards") or payload.get("cards") or "",
        "hole_key": resolved.get("hole_key") or payload.get("hole_key") or "",
        "start_time": resolved.get("start_time") or "",
        "end_time": resolved.get("end_time") or "",
        "pad_minutes": resolved.get("pad_minutes") or 15,
        "open_id_mode": resolved.get("open_id_mode") or "",
        "center_ms": q_old.get("center_ms"),
        "run_id": rid,
    }
    new_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return html[: m.start()] + m.group(1) + new_json + m.group(3) + html[m.end() :]


def render_trace_query_page(cfg: Optional[dict[str, Any]] = None) -> str:
    form = render_trace_query_form(cfg, standalone=True)
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Trace 查询条件</title>
<style>
body {{
  margin: 0; font-family: "IBM Plex Sans", "Noto Sans SC", sans-serif;
  background: #f6f3ee; color: #1c1917; line-height: 1.45;
}}
.wrap {{ max-width: 960px; margin: 0 auto; padding: 28px 20px 60px; }}
a {{ color: #0f766e; }}
{TRACE_FORM_CSS}
</style></head><body>
<div class="wrap">
  <h1>Trace 查询条件</h1>
  {form}
</div>
</body></html>
"""

