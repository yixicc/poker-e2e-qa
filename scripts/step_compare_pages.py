"""决策点对比 — 独立页面（不动对比报告列表）。"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any, Optional

from manage_page import (  # type: ignore
    _CSS,
    _JS_COMMON,
    _esc,
    _shell_close,
    _shell_open,
)

try:
    from gt_steps.pages import _CARDS_CSS, _cards_html, _cards_plain
except Exception:  # pragma: no cover
    _CARDS_CSS = ""

    def _cards_html(raw: Any) -> str:
        return _esc(str(raw or "—"))

    def _cards_plain(raw: Any) -> str:
        return str(raw or "").strip()


def _status_badge(exact: Any) -> str:
    if exact is True:
        return '<span class="badge ok">一致</span>'
    if exact is False:
        return '<span class="badge bad">差异</span>'
    return '<span class="badge muted">Chess API 无值</span>'


def _fmt_time(v: Any) -> str:
    s = str(v or "").strip()
    if not s:
        return "—"
    return s.replace("T", " ").replace("Z", "")[:19]


def render_step_compare_list_page(*, runs: list[dict[str, Any]]) -> str:
    rows = []
    for r in runs:
        rid = str(r.get("id") or "")
        metrics = r.get("metrics") if isinstance(r.get("metrics"), dict) else {}
        exact_pct = metrics.get("exact_pct")
        pct_s = f"{exact_pct}%" if exact_pct is not None else "—"
        when = _fmt_time(r.get("created_at") or r.get("updated_at"))
        frozen = ' <span class="badge ok">已冻结</span>' if r.get("readonly", True) else ""
        rows.append(
            "<tr>"
            f'<td class="mono"><a href="/step-compare/{_esc(rid)}">{_esc(rid)}</a>{frozen}</td>'
            f'<td class="mono">{_esc(r.get("gt_version_id") or "—")}</td>'
            f'<td class="num">{_esc(r.get("hand_n") if r.get("hand_n") is not None else "—")}</td>'
            f'<td class="num">{_esc(r.get("step_n") if r.get("step_n") is not None else "—")}</td>'
            f'<td class="num">{_esc(pct_s)}</td>'
            f'<td class="dim">{_esc(when)}</td>'
            f'<td class="dim">{_esc(str(r.get("note") or "")[:60] or "—")}</td>'
            "</tr>"
        )
    body = "\n".join(rows) if rows else (
        '<tr><td colspan="7" class="empty-cell">还没有决策点对比。'
        '<a href="/step-compare/new">新建一次</a></td></tr>'
    )
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>决策点对比</title>
<style>{_CSS}
.sc-page {{ max-width: 1100px; }}
.sc-page h1 {{
  font-size: 28px; letter-spacing: -0.03em;
  font-family: "Songti SC", "Noto Serif SC", "PingFang SC", serif; font-weight: 700;
}}
.badge {{ display:inline-block; font-size:11px; font-weight:700; padding:2px 7px;
  border-radius:999px; margin-left:6px; vertical-align:middle; }}
.badge.ok {{ background:var(--accent-soft); color:var(--accent); }}
.panel-flat {{ padding: 0; overflow: hidden; }}
table.sc-tbl {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
table.sc-tbl th, table.sc-tbl td {{
  text-align: left; padding: 12px 14px; border-bottom: 1px solid #f0ebe3; vertical-align: middle;
}}
table.sc-tbl th {{
  color: var(--muted); font-weight: 700; font-size: 11px; letter-spacing: .04em; background: #faf8f5;
}}
table.sc-tbl td.mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12.5px; }}
table.sc-tbl td.mono a {{ color: var(--ink); font-weight: 700; text-decoration: none; }}
table.sc-tbl td.mono a:hover {{ color: var(--accent); }}
table.sc-tbl td.num {{ font-variant-numeric: tabular-nums; }}
table.sc-tbl td.dim {{ color: var(--muted); }}
table.sc-tbl td.empty-cell {{ text-align: center; color: var(--muted); padding: 40px 16px; }}
table.sc-tbl tbody tr:hover {{ background: #f8fffd; }}
</style>
</head>
<body>
{_shell_open("step-compare", wrap_class="wrap sc-page")}
  <div class="topbar">
    <div class="topbar-text">
      <h1>决策点对比</h1>
      <p class="lead">正确值每一次 P0 决策点 vs Chess API。每份报告目录隔离冻结，互不影响。</p>
    </div>
    <div class="topbar-actions">
      <a class="btn primary" href="/step-compare/new">新建对比</a>
    </div>
  </div>
  <section class="panel panel-flat">
    <table class="sc-tbl">
      <thead>
        <tr>
          <th>跑批 ID</th><th>正确值版本</th><th>手数</th><th>决策点</th>
          <th>一致率</th><th>创建</th><th>备注</th>
        </tr>
      </thead>
      <tbody>
{body}
      </tbody>
    </table>
  </section>
{_shell_close()}
</body>
</html>"""


def render_step_compare_new_page(
    *,
    gt_versions: list[dict[str, Any]],
    current_gt: Optional[str],
    trace_cfg: Optional[dict[str, Any]] = None,
) -> str:
    cfg = trace_cfg or {}
    opts = []
    for v in gt_versions:
        vid = str(v.get("id") or "")
        sel = " selected" if vid and vid == current_gt else ""
        label = vid
        if v.get("is_current") or vid == current_gt:
            label += "（当前）"
        opts.append(f'<option value="{_esc(vid)}"{sel}>{_esc(label)}</option>')
    opts_html = "\n".join(opts) or '<option value="">无正确值版本</option>'
    default_id = __import__("time").strftime("%Y%m%d-%H%M-steps")
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>新建决策点对比</title>
<style>{_CSS}
.sc-page {{ max-width: 720px; }}
.sc-page h1 {{
  font-size: 26px; letter-spacing: -0.03em;
  font-family: "Songti SC", "Noto Serif SC", "PingFang SC", serif; font-weight: 700;
}}
.form-grid {{ display: flex; flex-direction: column; gap: 14px; }}
.form-grid .field {{ display: flex; flex-direction: column; gap: 5px; }}
.form-grid label {{ font-size: 12px; font-weight: 700; color: var(--muted); margin: 0; }}
.form-grid input, .form-grid select, .form-grid textarea {{
  font: inherit; font-size: 13px; padding: 9px 11px;
  border: 1px solid var(--line); border-radius: 8px; background: #fff; color: var(--ink);
}}
.form-grid textarea {{ min-height: 64px; resize: vertical; }}
.form-row {{ display: flex; flex-wrap: wrap; gap: 12px; }}
.form-row .field {{ flex: 1; min-width: 180px; }}
.check {{ display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 600; }}
.check input {{ width: auto; }}
.status {{ margin-top: 12px; font-size: 13px; color: var(--muted); min-height: 1.4em; }}
.status.err {{ color: var(--warn); }}
.status.ok {{ color: var(--accent); font-weight: 700; }}
.back-row {{ margin-bottom: 8px; font-size: 13px; }}
.back-row a {{ color: var(--accent); text-decoration: none; font-weight: 600; }}
</style>
</head>
<body>
{_shell_open("step-compare", wrap_class="wrap sc-page")}
  <div class="topbar">
    <div class="topbar-text">
      <div class="back-row"><a class="js-no-back" href="/step-compare">← 决策点对比列表</a></div>
      <h1>新建决策点对比</h1>
      <p class="lead">每次跑批独立目录冻结 Trace 条件与结果；换条件请用新 ID，勿覆盖旧报告。</p>
    </div>
  </div>
  <section class="panel">
    <form class="form-grid" id="sc-form">
      <div class="field">
        <label for="run-id">跑批 ID（新报告请用新 ID）</label>
        <input id="run-id" name="run_id" value="{_esc(default_id)}" required/>
      </div>
      <div class="field">
        <label for="gt">正确值版本</label>
        <select id="gt" name="gt_version">{opts_html}</select>
      </div>
      <div class="field">
        <label for="hands">本批手牌（可选，空=全量）</label>
        <input id="hands" name="hand_uids" placeholder="HAND_001 HAND_002"/>
      </div>
      <div class="form-row">
        <div class="field">
          <label for="openId">openId</label>
          <input id="openId" value="{_esc(cfg.get('openId') or '')}"/>
        </div>
        <div class="field">
          <label for="traceEnv">Trace 环境</label>
          <input id="traceEnv" value="{_esc(cfg.get('traceEnv') or 'uat')}"/>
        </div>
      </div>
      <div class="form-row">
        <div class="field">
          <label for="startTime">开始时间</label>
          <input id="startTime" value="{_esc(cfg.get('startTime') or '')}" placeholder="YYYY-MM-DD HH:MM:SS"/>
        </div>
        <div class="field">
          <label for="endTime">结束时间</label>
          <input id="endTime" value="{_esc(cfg.get('endTime') or '')}" placeholder="YYYY-MM-DD HH:MM:SS"/>
        </div>
      </div>
      <div class="field">
        <label for="note">备注</label>
        <textarea id="note" placeholder="可选"></textarea>
      </div>
      <label class="check"><input type="checkbox" id="skip-trace"/> 跳过 Trace（仅拆正确值，Chess 全为无值）</label>
      <label class="check"><input type="checkbox" id="overwrite"/> 危险：覆盖同名跑批（整目录删除后重建，旧 Trace/结果不可恢复）</label>
      <p class="hint" style="margin:0">下方时间窗仅作本报告表单默认；保存后只写入本 run 目录，不影响其它报告。</p>
      <div>
        <button class="btn primary" type="submit" id="btn-run">开始对比</button>
      </div>
      <div class="status" id="status" aria-live="polite"></div>
    </form>
  </section>
{_shell_close()}
<script>
{_JS_COMMON}
document.getElementById('sc-form').addEventListener('submit', async function(e) {{
  e.preventDefault();
  var overwrite = document.getElementById('overwrite').checked;
  if (overwrite) {{
    var ok = window.confirm(
      '将整目录删除并重建该跑批（含 Trace 条件与 spans），旧数据不可恢复。确定覆盖？'
    );
    if (!ok) return;
  }}
  var btn = document.getElementById('btn-run');
  var st = document.getElementById('status');
  btn.disabled = true;
  st.className = 'status';
  st.textContent = '跑批中，请稍候…';
  try {{
    var data = await postJson('/api/step-compare-run', {{
      run_id: document.getElementById('run-id').value.trim(),
      gt_version: document.getElementById('gt').value,
      hand_uids: document.getElementById('hands').value.trim(),
      note: document.getElementById('note').value,
      skip_trace: document.getElementById('skip-trace').checked,
      overwrite: overwrite,
      trace_query: {{
        openId: document.getElementById('openId').value.trim(),
        startTime: document.getElementById('startTime').value.trim(),
        endTime: document.getElementById('endTime').value.trim(),
        traceEnv: document.getElementById('traceEnv').value.trim() || 'uat',
      }},
    }});
    st.className = 'status ok';
    st.textContent = '完成：决策点 ' + ((data.metrics || {{}}).step_n || 0)
      + ' · 一致率 ' + (((data.metrics || {{}}).exact_pct != null) ? data.metrics.exact_pct + '%' : '—');
    location.href = '/step-compare/' + encodeURIComponent(data.run_id || '');
  }} catch (err) {{
    st.className = 'status err';
    st.textContent = String(err.message || err);
    btn.disabled = false;
  }}
}});
</script>
</body>
</html>"""


def _signal_badge(present: Any, *, stored: bool = True) -> str:
    if not stored:
        return '<span class="badge muted" title="旧跑批未存信号字段">信号未存</span>'
    if present:
        return ""
    return '<span class="badge muted">信号无</span>'


def _chess_presence_badge(exact: Any) -> str:
    if exact is None:
        return '<span class="badge muted">Chess无</span>'
    return ""


def _step_status_html(
    exact: Any,
    signal_present: Any,
    *,
    stored_signal: bool = True,
) -> str:
    """一致只标一致；不一致只在缺数据时标「无」。"""
    parts = [_status_badge(exact)]
    if exact is True:
        return parts[0]
    # Chess API 无值 已说明 Chess 没有
    if exact is not None:
        chess = _chess_presence_badge(exact)
        if chess:
            parts.append(chess)
    sig = _signal_badge(signal_present, stored=stored_signal)
    if sig:
        parts.append(sig)
    return " ".join(parts)


def render_step_run_index_html(
    *,
    run_id: str,
    meta: dict[str, Any],
    summary: dict[str, Any],
) -> str:
    """Frozen overview HTML written into step_runs/<id>/index.html."""
    metrics = summary.get("metrics") if isinstance(summary.get("metrics"), dict) else {}
    steps = summary.get("steps") if isinstance(summary.get("steps"), list) else []
    by_hand: dict[str, list] = defaultdict(list)
    for s in steps:
        by_hand[str(s.get("hand_uid") or "")].append(s)

    blocks = []
    for hid in sorted(by_hand.keys(), key=lambda x: (len(x), x)):
        rows = by_hand[hid]
        hole = rows[0].get("hole_key") if rows else ""
        hole_html = _cards_html(hole)
        hole_plain = _cards_plain(hole)
        hole_compact = hole_plain.replace(" ", "")
        hand_search = " ".join(
            x for x in (hid, hole_plain, hole_compact, str(hole or "")) if x
        )
        step_rows = []
        for s in rows:
            nth = int(s.get("nth") or 0)
            href = f"/step-compare/{_esc(run_id)}/{_esc(hid)}/{nth}"
            street = str(s.get("decision_street") or "—").upper()
            has_signal_key = "signal_present" in s
            st_html = _step_status_html(
                s.get("chess_exact"),
                s.get("signal_present"),
                stored_signal=has_signal_key,
            )
            issue = s.get("first_issue") or ""
            # 无 Chess 时 first_issue 应为空；兼容旧数据里重复的「Chess API 无值」
            if s.get("chess_exact") is None and str(issue).strip() in (
                "Chess API 无值",
                "Chess API无值",
            ):
                issue = ""
            act = s.get("next_p0_label") or "—"
            row_search = f"{hand_search} {street} {act} {issue}"
            step_rows.append(
                f'<a class="step-row" href="{href}" data-street="{_esc(street.lower())}" '
                f'data-search="{_esc(row_search)}">'
                f'<span class="c-nth">P0#{nth}</span>'
                f'<span class="c-street"><span class="street-tag street-{_esc(street.lower())}">'
                f"{_esc(street)}</span></span>"
                f'<span class="c-act">{_esc(act)}</span>'
                f'<span class="c-st">{st_html}</span>'
                f'<span class="c-iss dim">{_esc(issue)}</span>'
                f"</a>"
            )
        blocks.append(
            f'<article class="hand-block" data-hand="{_esc(hid)}" data-search="{_esc(hand_search)}">'
            f'<header class="hand-head">'
            f'<div class="hand-id">'
            f'<span class="mono">{_esc(hid)}</span>'
            f'<span class="hand-hole" title="手牌 {_esc(hole_plain)}">{hole_html}</span>'
            f'<span class="step-count">{len(rows)} 次 P0</span>'
            f"</div>"
            f"</header>"
            f'<div class="step-list">{"".join(step_rows)}</div>'
            f"</article>"
        )
    body = "\n".join(blocks) if blocks else '<div class="gs-empty">无决策点</div>'

    exact_pct = metrics.get("exact_pct")
    pct_s = f"{exact_pct}%" if exact_pct is not None else "—"
    signal_n = metrics.get("signal_present_n")
    signal_metric = (
        f'<div class="gs-metric"><span class="k">有信号</span>'
        f'<span class="v">{_esc(signal_n if signal_n is not None else "—")}</span></div>'
    )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>决策点对比 · {_esc(run_id)}</title>
<style>{_CSS}
{_CARDS_CSS}
.sc-page {{ max-width: 1100px; }}
.sc-page h1 {{
  font-size: 24px; letter-spacing: -0.03em;
  font-family: "Songti SC", "Noto Serif SC", "PingFang SC", serif; font-weight: 700;
}}
.back-row {{ margin-bottom: 8px; font-size: 13px; }}
.back-row a {{ color: var(--accent); text-decoration: none; font-weight: 600; }}
.gs-metrics {{ display:flex; flex-wrap:wrap; gap:8px; }}
.gs-toolbar {{
  display:flex; flex-wrap:wrap; align-items:center; gap:12px 16px;
  margin-bottom:16px;
}}
.gs-filters {{ display:flex; flex-wrap:wrap; align-items:center; gap:8px 10px; margin-left:auto; }}
.gs-filters input[type="search"] {{
  font:inherit; font-size:13px; padding:9px 12px; width:min(280px, 100%);
  border:1px solid var(--line); border-radius:8px; background:#fff; color:var(--ink);
}}
.gs-filters input[type="search"]:focus {{
  outline:none; border-color:#5eead4; box-shadow:0 0 0 3px rgba(15,118,110,.12);
}}
.gs-filter-hint {{ font-size:12px; color:var(--muted); font-weight:600; min-width:4em; }}
.gs-metric {{
  display:flex; flex-direction:column; gap:2px; min-width:72px; padding:8px 12px;
  background:#fff; border:1px solid var(--line); border-radius:10px;
}}
.gs-metric .k {{ font-size:11px; font-weight:700; color:var(--muted); }}
.gs-metric .v {{ font-size:18px; font-weight:800; font-variant-numeric:tabular-nums; }}
.badge {{ display:inline-block; font-size:11px; font-weight:700; padding:2px 7px; border-radius:999px; }}
.badge.ok {{ background:var(--accent-soft); color:var(--accent); }}
.badge.bad {{ background:#ffe4e6; color:var(--warn); }}
.badge.muted {{ background:#f5f5f4; color:var(--muted); }}
.hand-list {{ display:flex; flex-direction:column; gap:10px; }}
.hand-block {{ background:#fff; border:1px solid var(--line); border-radius:12px; overflow:hidden; }}
.hand-block.is-hidden, .step-row.is-hidden {{ display:none; }}
.hand-head {{
  display:flex; flex-wrap:nowrap; align-items:center;
  gap:10px 16px; padding:12px 16px; background:#fafaf9; border-bottom:1px solid #f0eeea;
}}
.hand-id {{ display:flex; align-items:center; gap:10px; flex-wrap:nowrap; }}
.hand-id .mono {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:14px; font-weight:800; }}
.hand-id .hand-hole {{ display:inline-flex; align-items:center; flex:0 0 auto; }}
.hand-id .step-count {{
  font-size:12px; font-weight:700; color:var(--accent);
  background:var(--accent-soft); padding:2px 8px; border-radius:999px;
}}
.step-list {{ display:flex; flex-direction:column; }}
.step-row {{
  display:grid; grid-template-columns: 64px 100px 1fr auto minmax(120px, 1.2fr);
  gap:8px; align-items:center; padding:11px 16px; text-decoration:none; color:inherit;
  border-top:1px solid #f3efe8;
}}
.step-row:hover {{ background:#f8fffd; }}
.step-row .c-nth {{
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:12.5px; font-weight:800;
}}
.step-row .c-act {{
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:12.5px; font-weight:700;
}}
.step-row .c-st {{ display:inline-flex; flex-wrap:wrap; gap:4px; align-items:center; justify-content:flex-end; }}
.step-row .dim {{ color:var(--muted); font-size:12px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.street-tag {{
  display:inline-block; font-size:11px; font-weight:800; letter-spacing:.04em;
  padding:3px 7px; border-radius:6px; background:#f5f5f4; color:#57534e;
}}
.street-tag.street-preflop {{ background:#ecfdf5; color:#047857; }}
.street-tag.street-flop {{ background:#eff6ff; color:#1d4ed8; }}
.street-tag.street-turn {{ background:#fff7ed; color:#c2410c; }}
.street-tag.street-river {{ background:#faf5ff; color:#7e22ce; }}
.gs-empty {{ text-align:center; color:var(--muted); padding:40px; background:#fff; border:1px solid var(--line); border-radius:12px; }}
@media (max-width: 720px) {{
  .step-row {{ grid-template-columns: 56px 1fr auto; }}
  .step-row .c-iss {{ display:none; }}
  .gs-filters {{ margin-left:0; width:100%; }}
  .gs-filters input[type="search"] {{ width:100%; }}
}}
</style>
</head>
<body>
{_shell_open("step-compare", wrap_class="wrap sc-page")}
  <div class="topbar">
    <div class="topbar-text">
      <div class="back-row"><a class="js-no-back" href="/step-compare">← 决策点对比列表</a></div>
      <h1>决策点对比 · <span class="mono">{_esc(run_id)}</span></h1>
      <p class="lead">正确值版本 <code>{_esc(meta.get("gt_version_id") or "—")}</code>
        {_esc((" · " + str(meta.get("note"))) if meta.get("note") else "")}
        · 本报告已冻结隔离（Trace 条件与 spans 仅存在本目录）</p>
    </div>
  </div>
  <div class="gs-toolbar">
  <div class="gs-metrics">
    <div class="gs-metric"><span class="k">手数</span><span class="v">{_esc(metrics.get("hand_n") or 0)}</span></div>
    <div class="gs-metric"><span class="k">决策点</span><span class="v">{_esc(metrics.get("step_n") or 0)}</span></div>
    <div class="gs-metric"><span class="k">一致</span><span class="v">{_esc(metrics.get("exact_n") or 0)}</span></div>
    <div class="gs-metric"><span class="k">差异</span><span class="v">{_esc(metrics.get("diff_n") or 0)}</span></div>
    <div class="gs-metric"><span class="k">Chess 无值</span><span class="v">{_esc(metrics.get("no_chess_n") or 0)}</span></div>
    {signal_metric}
    <div class="gs-metric"><span class="k">一致率</span><span class="v">{_esc(pct_s)}</span></div>
    <div class="gs-metric"><span class="k">有差异手数</span><span class="v">{_esc(metrics.get("hands_with_diff_n") or 0)}</span></div>
  </div>
    <div class="gs-filters">
      <input id="q" type="search" placeholder="按手牌 / HAND / 行动查询，如 QC 5H" autocomplete="off"/>
      <span class="gs-filter-hint" id="filter-hint"></span>
    </div>
  </div>
  <div class="hand-list" id="hand-list">
{body}
  </div>
{_shell_close()}
<script>
(function() {{
  var q = document.getElementById('q');
  var hint = document.getElementById('filter-hint');
  var blocks = Array.prototype.slice.call(document.querySelectorAll('.hand-block'));
  function compact(s) {{ return String(s || '').toLowerCase().replace(/[^a-z0-9]/g, ''); }}
  function apply() {{
    var raw = (q.value || '').trim().toLowerCase();
    var cq = compact(raw);
    var shownHands = 0, shownSteps = 0;
    blocks.forEach(function(block) {{
      var rows = Array.prototype.slice.call(block.querySelectorAll('.step-row'));
      var handHit = 0;
      var hay = ((block.getAttribute('data-search') || '') + ' ' +
        rows.map(function(r) {{ return r.getAttribute('data-search') || ''; }}).join(' ')).toLowerCase();
      var hayC = compact(hay);
      var blockOk = !raw || hay.indexOf(raw) >= 0 || (cq && hayC.indexOf(cq) >= 0);
      rows.forEach(function(row) {{
        var text = ((row.getAttribute('data-search') || '') + ' ' + (block.getAttribute('data-search') || '')).toLowerCase();
        var ok = !raw || text.indexOf(raw) >= 0 || (cq && compact(text).indexOf(cq) >= 0);
        row.classList.toggle('is-hidden', !ok);
        if (ok) {{ handHit++; shownSteps++; }}
      }});
      var showBlock = blockOk && (handHit > 0 || !raw);
      if (raw) showBlock = handHit > 0;
      block.classList.toggle('is-hidden', !showBlock);
      if (showBlock) shownHands++;
    }});
    hint.textContent = raw ? (shownHands + ' 手 · ' + shownSteps + ' 点') : '';
  }}
  if (q) q.addEventListener('input', apply);
}})();
</script>
</body>
</html>"""


def _fmt_val(v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, (list, dict)):
        try:
            return json.dumps(v, ensure_ascii=False)
        except Exception:
            return str(v)
    s = str(v).strip()
    return s if s else "—"


def _action_cell(a: Any) -> str:
    if not isinstance(a, dict):
        return _fmt_val(a)
    from compare_gto_requests import action_label

    return action_label(a)


def _verdict_label(kind: str) -> str:
    return {
        "ok": "一致",
        "diff": "差异",
        "missing": "漏行动",
        "extra": "多余行动",
        "pending": "待确认",
        "absent": "缺失",
    }.get(kind, kind or "—")


def build_structured_compare(
    gt: Optional[dict],
    chess: Optional[dict],
    *,
    issues: Optional[list] = None,
    mode: str = "gt_chess",
) -> dict[str, Any]:
    """Build tester-first structured rows.

    mode=gt_chess: 正确值 | Chess
    mode=sig_chess: 信号 | Chess（无 Excel 真值）
    """
    from action_align import align_requests
    from evidence_report import _num_same, action_issue_kind_label, rewrite_kind_label

    pair = mode == "sig_chess"
    left_name = "信号" if pair else "正确值"
    rows: list[dict[str, Any]] = []
    counts = {"ok": 0, "diff": 0, "missing": 0, "pending": 0}

    def add(item: str, gt_v: Any, sys_v: Any, verdict_kind: str, verdict: str) -> None:
        rows.append(
            {
                "item": item,
                "gt": gt_v,
                "sys": sys_v,
                "verdict_kind": verdict_kind,
                "verdict": verdict,
            }
        )
        if verdict_kind in counts:
            counts[verdict_kind] += 1
        elif verdict_kind == "extra":
            counts["diff"] += 1
        elif verdict_kind == "absent":
            counts["missing"] += 1

    if chess is None:
        left_present = "有信号" if pair else "有正确值"
        add("Chess API", left_present if gt else "无", "无值", "pending", "待确认 · Chess 无")
        for it in issues or []:
            title = str(it.get("title") or it.get("kind") or "待确认")
            if pair:
                title = title.replace("正确值", "信号")
            add(
                str(it.get("kind") or "差异"),
                "—",
                "—",
                "pending",
                title,
            )
        return {"rows": rows, "counts": counts, "pot_rows": []}

    gi_g = (gt or {}).get("gameInfo") if isinstance(gt, dict) else {}
    gi_s = (chess or {}).get("gameInfo") if isinstance(chess, dict) else {}
    if not isinstance(gi_g, dict):
        gi_g = {}
    if not isinstance(gi_s, dict):
        gi_s = {}

    # 盲注等关键字段
    for key, label in (
        ("ante", "前注"),
        ("straddle", "抢注"),
        ("smallBlind", "小盲"),
        ("bigBlind", "大盲"),
    ):
        vg, vs = gi_g.get(key), gi_s.get(key)
        if vg is None and vs is None:
            continue
        same = False
        try:
            if key == "straddle":
                from compare_gto_requests import straddle_values_equivalent

                same = straddle_values_equivalent(vg, vs)
            else:
                same = abs(float(vg) - float(vs)) < 1e-9
        except Exception:
            same = str(vg) == str(vs)
        if same:
            add(label, vg, vs, "ok", "一致")
        else:
            add(label, vg, vs, "diff", f"{label}不正确")

    board_g = list(gi_g.get("communityCards") or [])
    board_s = list(gi_s.get("communityCards") or [])
    if board_g or board_s:
        if board_g == board_s:
            add("公共牌", " ".join(str(x) for x in board_g) or "[]", " ".join(str(x) for x in board_s) or "[]", "ok", "一致")
        else:
            add(
                "公共牌",
                " ".join(str(x) for x in board_g) or "[]",
                " ".join(str(x) for x in board_s) or "[]",
                "diff",
                "公共牌不一致",
            )

    pg = [p for p in (gi_g.get("players") or []) if isinstance(p, dict)]
    ps = [p for p in (gi_s.get("players") or []) if isinstance(p, dict)]
    if len(pg) or len(ps):
        if len(pg) == len(ps):
            add("玩家人数", len(pg), len(ps), "ok", "一致")
        else:
            add("玩家人数", len(pg), len(ps), "diff", "玩家人数不一致")

    # 与列表 first_issue 同一口径：按座位对照位置 / 起始筹码
    by_g = {p.get("seat"): p for p in pg}
    by_s = {p.get("seat"): p for p in ps}
    for seat in sorted(set(by_g) | set(by_s), key=lambda x: str(x)):
        a, b = by_g.get(seat), by_s.get(seat)
        gt_pos = (a or {}).get("position") if a else "（无此座位）"
        sys_pos = (b or {}).get("position") if b else "（无此座位）"
        if a and b:
            pos_same = a.get("position") == b.get("position")
            chip_same = _num_same(a.get("initChips"), b.get("initChips"))
        else:
            pos_same = False
            chip_same = False
        add(
            f"{seat} 位置",
            gt_pos,
            sys_pos,
            "ok" if pos_same else "diff",
            "一致" if pos_same else "位置不正确",
        )
        gt_chip = (a or {}).get("initChips") if a else "（无此座位）"
        sys_chip = (b or {}).get("initChips") if b else "（无此座位）"
        add(
            f"{seat} 起始筹码",
            gt_chip,
            sys_chip,
            "ok" if chip_same else "diff",
            "一致" if chip_same else "起始筹码不正确",
        )

    # 行动序列逐条
    for i, op in enumerate(align_requests(gt, chess), start=1):
        g, s = op.get("gt"), op.get("sys")
        kind = op.get("op")
        item = f"行动 #{i}"
        if kind == "equal":
            add(item, _action_cell(g), _action_cell(s), "ok", "一致")
        elif kind == "missing":
            add(item, _action_cell(g), "（Chess 缺少）", "missing", "漏行动")
        elif kind == "extra":
            add(item, f"（{left_name}无）", _action_cell(s), "extra", "多余行动")
        elif kind == "rewrite":
            label = rewrite_kind_label(g, s)
            # map to shorter tester labels
            if "类型" in label and "金额" in label:
                short = "动作类型与金额错误"
            elif "类型" in label:
                short = "动作类型错误"
            elif "金额" in label:
                short = "金额错误"
            else:
                short = action_issue_kind_label("rewrite", g, s)
            add(item, _action_cell(g), _action_cell(s), "diff", short)
        else:
            add(item, _action_cell(g), _action_cell(s), "pending", "待确认")

    # 底池相关（展开用）
    pot_rows = []
    for key, label in (("pot", "底池"), ("currentBet", "当前注额"), ("totalPot", "总底池")):
        vg, vs = gi_g.get(key), gi_s.get(key)
        if vg is None and vs is None:
            continue
        try:
            same = abs(float(vg) - float(vs)) < 1e-9
        except Exception:
            same = str(vg) == str(vs)
        pot_rows.append(
            {
                "item": label,
                "gt": vg,
                "sys": vs,
                "verdict_kind": "ok" if same else "diff",
                "verdict": "一致" if same else f"{label}不一致",
            }
        )

    return {"rows": rows, "counts": counts, "pot_rows": pot_rows}


_FUSION_STREETS = ("init", "preflop", "flop", "turn", "river")
_FUSION_COLS = ("seat", "status", "chips", "role/action", "amount", "pot")
_BLIND_FIELDS = (
    ("smallBlind", "小盲"),
    ("bigBlind", "大盲"),
    ("ante", "前注"),
    ("straddle", "抢注"),
)
_STREET_TO_FUSION = {
    "PREFLOP": "preflop",
    "PRE_FLOP": "preflop",
    "FLOP": "flop",
    "TURN": "turn",
    "RIVER": "river",
    "INIT": "init",
}


def _seat_p_label(seat: Any) -> str:
    from cross_module import _seat_num

    n = _seat_num(seat)
    if n is not None and str(n).isdigit():
        return f"P{n}"
    s = str(seat or "").strip()
    return s


def _fusion_cell(v: Any) -> str:
    if v is None or v == "":
        return ""
    from cross_module import _fmt

    s = _fmt(v)
    return "" if s in ("—", "None") else s


def _normalize_fusion_rows(rows: Any) -> list[list[Any]]:
    out: list[list[Any]] = []
    if not isinstance(rows, list):
        return out
    for row in rows:
        if isinstance(row, dict):
            cells = [
                row.get("seat"),
                row.get("status"),
                row.get("chips"),
                row.get("roleOrAction") or row.get("action") or row.get("actionType"),
                row.get("amount"),
                row.get("pot"),
            ]
        elif isinstance(row, (list, tuple)):
            cells = list(row)
        else:
            continue
        while len(cells) < 6:
            cells.append("")
        cells[0] = _seat_p_label(cells[0])
        out.append(cells[:6])
    return out


def gto_norm_to_fusion_history(norm: Optional[dict]) -> Optional[dict[str, list]]:
    """从 gameInfo.players / actionSequence 还原 Console 同款分街表。"""
    if not isinstance(norm, dict):
        return None
    gi = norm.get("gameInfo") if isinstance(norm.get("gameInfo"), dict) else {}
    if not isinstance(gi, dict):
        gi = {}
    players = [p for p in (gi.get("players") or []) if isinstance(p, dict)]
    actions = [a for a in (gi.get("actionSequence") or []) if isinstance(a, dict)]
    if not players and not actions:
        return None
    out: dict[str, list] = {}
    if players:
        sb, bb = gi.get("smallBlind"), gi.get("bigBlind")
        init_rows = []
        for p in players:
            pos = str(p.get("position") or "").strip().upper()
            role = "DEALER" if pos == "BTN" else pos
            amount: Any = ""
            if pos == "SB":
                amount = sb
            elif pos == "BB":
                amount = bb
            init_rows.append(
                [
                    _seat_p_label(p.get("seat")),
                    "HOLD",
                    p.get("initChips"),
                    role,
                    amount,
                    "",
                ]
            )
        out["init"] = init_rows
    by_street: dict[str, list] = {k: [] for k in ("preflop", "flop", "turn", "river")}
    for a in actions:
        st = str(a.get("street") or "PREFLOP").strip().upper()
        key = _STREET_TO_FUSION.get(st, "preflop")
        if key == "init":
            key = "preflop"
        act = str(a.get("actionType") or "").strip().upper()
        status = "FOLD" if act == "FOLD" else "HOLD"
        amt = a.get("amount")
        if act in ("FOLD", "CHECK") and str(amt).strip() in ("0", "0.0", "0.00"):
            amt = ""
        by_street.setdefault(key, []).append(
            [
                _seat_p_label(a.get("seat")),
                status,
                "",
                act,
                amt,
                "",
            ]
        )
    for key, rows in by_street.items():
        if rows:
            out[key] = rows
    return out or None


def signal_to_fusion_history(signal_req: Any) -> Optional[dict[str, list]]:
    from cross_module import find_signal_hand_history

    hh, _path = find_signal_hand_history(signal_req)
    if not isinstance(hh, dict):
        return None
    out: dict[str, list] = {}
    for street in _FUSION_STREETS:
        rows = _normalize_fusion_rows(hh.get(street))
        if rows:
            out[street] = rows
    return out or None


_SPECIAL_ROLES = {"DEALER", "BTN", "SB", "BB", "STRADDLE"}


def _norm_role(v: Any) -> str:
    s = _fusion_cell(v).upper()
    return "DEALER" if s == "BTN" else s


def _init_roles_equivalent(a: Any, b: Any) -> bool:
    ga, gb = _norm_role(a), _norm_role(b)
    if ga == gb:
        return True
    # 信号 INIT 空角色 = 普通座位，不和 UTG/LJ/CO 等对照
    if gb == "" and ga not in _SPECIAL_ROLES:
        return True
    if ga == "" and gb not in _SPECIAL_ROLES:
        return True
    return False


def _fusion_cells_equal(
    a: Any,
    b: Any,
    *,
    col: int = 0,
    street: str = "",
) -> bool:
    if street == "init" and col == 3:
        return _init_roles_equivalent(a, b)
    sa, sb = _fusion_cell(a), _fusion_cell(b)
    if sa == sb:
        return True
    from evidence_report import _num_same

    if _num_same(a, b):
        return True
    return sa.upper() == sb.upper()


def _fusion_row_keys(rows: list) -> list[tuple[str, int]]:
    seen: dict[str, int] = {}
    keys: list[tuple[str, int]] = []
    for row in rows:
        seat = _seat_p_label((row or [""])[0] if row else "")
        n = seen.get(seat, 0)
        seen[seat] = n + 1
        keys.append((seat, n))
    return keys


def _blank_fusion_marks(fh: Optional[dict]) -> dict[str, list]:
    out: dict[str, list] = {}
    if not fh:
        return out
    for street in _FUSION_STREETS:
        rows = fh.get(street) or []
        out[street] = [{"cols": {}, "tips": {}} for _ in rows]
    return out


_FUSION_SIDE_LABEL = {"sig": "信号", "chess": "Chess", "gt": "正确值"}
_FUSION_SIDE_ORDER = ("sig", "chess", "gt")


def _pad_fusion_row(row: Any) -> list:
    return (list(row) + [""] * 6)[:6]


def _fusion_tip(cells_by_side: dict[str, Any]) -> str:
    parts = []
    for side in _FUSION_SIDE_ORDER:
        if side not in cells_by_side:
            continue
        parts.append(
            f"{_FUSION_SIDE_LABEL[side]} {_fusion_cell(cells_by_side[side]) or '（空）'}"
        )
    return " ≠ ".join(parts)


def build_fusion_diff_marks(
    gt_fh: Optional[dict],
    chess_fh: Optional[dict],
    sig_fh: Optional[dict],
    *,
    pair_mode: bool = False,
) -> dict[str, dict[str, list]]:
    """同一街道同一座位：有数据的模块把不一致格子都标出来。

    pair_mode=True：只比信号 vs Chess（无正确值列）。差异一律标红。
    """
    marks = {
        "gt": _blank_fusion_marks(gt_fh),
        "chess": _blank_fusion_marks(chess_fh),
        "sig": _blank_fusion_marks(sig_fh),
    }
    fhs = {"gt": gt_fh or {}, "chess": chess_fh or {}, "sig": sig_fh or {}}
    sides = ("sig", "chess") if pair_mode else _FUSION_SIDE_ORDER

    def _set(side: str, street: str, ri: int, col: int, kind: str, tip: str) -> None:
        street_marks = marks[side].setdefault(street, [])
        while len(street_marks) <= ri:
            street_marks.append({"cols": {}, "tips": {}})
        mark = street_marks[ri]
        prev = mark["cols"].get(col)
        if prev == "chess" and kind == "sig":
            return
        mark["cols"][col] = kind
        mark["tips"][col] = tip

    for street in _FUSION_STREETS:
        rows = {k: list(fhs[k].get(street) or []) for k in sides}
        maps = {k: {key: i for i, key in enumerate(_fusion_row_keys(v))} for k, v in rows.items()}
        all_keys: set[tuple[str, int]] = set()
        for mp in maps.values():
            all_keys |= set(mp.keys())

        for key in all_keys:
            who = [k for k in sides if key in maps[k]]
            if len(who) == 1:
                side = who[0]
                ri = maps[side][key]
                if pair_mode:
                    other = "chess" if side == "sig" else "sig"
                    for c in range(6):
                        _set(
                            side,
                            street,
                            ri,
                            c,
                            "chess",
                            f"{_FUSION_SIDE_LABEL[other]} 无此行",
                        )
                elif side == "sig":
                    for c in range(6):
                        _set(side, street, ri, c, "sig", "正确值 / Chess 无此行")
                elif rows.get("gt") or rows.get("chess"):
                    other = "chess" if side == "gt" else "gt"
                    for c in range(6):
                        _set(
                            side,
                            street,
                            ri,
                            c,
                            "chess",
                            f"{_FUSION_SIDE_LABEL[other]} 无此行",
                        )
                continue

            padded = {k: _pad_fusion_row(rows[k][maps[k][key]]) for k in who}
            for c in range(1, 6):
                if street == "init" and c == 3:
                    present = {k: padded[k][c] for k in who}
                else:
                    present = {
                        k: padded[k][c] for k in who if _fusion_cell(padded[k][c]) != ""
                    }
                if len(present) < 2:
                    continue
                items = list(present.items())
                base = items[0][1]
                if all(
                    _fusion_cells_equal(base, v, col=c, street=street) for _, v in items[1:]
                ):
                    continue

                if pair_mode:
                    kind = "chess"
                else:
                    gt_v, ch_v = present.get("gt"), present.get("chess")
                    if (
                        gt_v is not None
                        and ch_v is not None
                        and not _fusion_cells_equal(gt_v, ch_v, col=c, street=street)
                    ):
                        kind = "chess"
                    else:
                        kind = "sig"

                tip = _fusion_tip({k: padded[k][c] for k in who})
                mark_sides = who if (pair_mode or len(who) == 3) else list(present.keys())
                for side in mark_sides:
                    if c in (2, 5) and _fusion_cell(padded[side][c]) == "":
                        continue
                    _set(side, street, maps[side][key], c, kind, tip)
    return marks


def _street_key_union(*row_lists: list) -> list[tuple[str, int]]:
    seen: set[tuple[str, int]] = set()
    out: list[tuple[str, int]] = []
    for rows in row_lists:
        for k in _fusion_row_keys(rows or []):
            if k not in seen:
                seen.add(k)
                out.append(k)
    return out


def _norm_game_info(norm: Any) -> dict:
    if not isinstance(norm, dict):
        return {}
    gi = norm.get("gameInfo")
    return gi if isinstance(gi, dict) else {}


def _render_blinds_bar(gi: dict, peer_gis: list[dict]) -> str:
    """桌面级盲注/前注。INIT 座位表的 AMOUNT 只是 SB/BB 已下额，不含前注。"""
    from evidence_report import _blind_same

    chips: list[str] = []
    for key, label in _BLIND_FIELDS:
        v = gi.get(key)
        diff = any(not _blind_same(key, v, peer.get(key)) for peer in peer_gis)
        cls = "bb-diff" if diff else "bb-ok"
        tip = f"{label}两侧不一致" if diff else label
        chips.append(
            f'<span class="{cls}" title="{_esc(tip)}">'
            f"{_esc(label)} {_esc(_fmt_val(v))}</span>"
        )
    return '<div class="bhv-blinds">' + "".join(chips) + "</div>"


def _render_one_street_table(
    *,
    rows: list,
    marks: Optional[list],
    street: str,
    current_street: str,
    aligned_keys: list[tuple[str, int]],
) -> str:
    cur = _STREET_TO_FUSION.get(str(current_street or "").strip().upper(), "")
    cur_cls = " is-current" if street == cur else ""
    keymap = {k: i for i, k in enumerate(_fusion_row_keys(rows))}
    mark_list = marks or []
    trs: list[str] = []
    for key in aligned_keys:
        seat, _nth = key
        if key in keymap:
            ri = keymap[key]
            cells = list(rows[ri]) + [""] * 6
            mark = mark_list[ri] if ri < len(mark_list) else {"cols": {}, "tips": {}}
            tds = []
            for i in range(6):
                kind = (mark.get("cols") or {}).get(i) or ""
                tip = (mark.get("tips") or {}).get(i) or ""
                cls = f' class="bhv-{_esc(kind)}"' if kind in ("chess", "sig") else ""
                title = f' title="{_esc(tip)}"' if tip else ""
                tds.append(f"<td{cls}{title}>{_esc(_fusion_cell(cells[i]))}</td>")
            trs.append(f"<tr>{''.join(tds)}</tr>")
        else:
            trs.append(
                '<tr class="bhv-absent" title="本模块无此行">'
                f"<td>{_esc(seat)}</td>"
                '<td colspan="5" class="dim">无此行</td>'
                "</tr>"
            )
    if not aligned_keys:
        body = '<p class="dim" style="margin:6px 0 0">无数据</p>'
        table = ""
    else:
        ths = "".join(f"<th>{_esc(c)}</th>" for c in _FUSION_COLS)
        table = (
            f'<div class="bhv-scroll"><table class="bhv-tbl">'
            f"<thead><tr>{ths}</tr></thead>"
            f'<tbody>{"".join(trs)}</tbody>'
            "</table></div>"
        )
        body = ""
    init_note = ""
    if street == "init":
        init_note = (
            '<div class="bhv-street-note">'
            "AMOUNT = 本座位已下的小盲/大盲，不是前注；前注看本列上方桌面行"
            "</div>"
        )
    return (
        f'<div class="bhv-street{cur_cls}">'
        f'<div class="bhv-street-h">{_esc(street.upper())}</div>'
        f"{init_note}{table}{body}"
        "</div>"
    )


def render_module_behavior_grid(
    *,
    gt: Optional[dict],
    chess: Optional[dict],
    signal_req: Any,
    signal_status: str,
    signal_meta_line: str,
    nth: int,
    current_street: str,
    sides: Optional[tuple[str, ...]] = None,
    sig_norm: Optional[dict] = None,
) -> str:
    gt_fh = gto_norm_to_fusion_history(gt) or {}
    chess_fh = gto_norm_to_fusion_history(chess) or {}
    sig_fh = signal_to_fusion_history(signal_req) or {}
    side_order = tuple(sides) if sides else ("sig", "chess", "gt")
    pair_mode = side_order == ("sig", "chess")
    marks = build_fusion_diff_marks(
        None if pair_mode else gt_fh,
        chess_fh,
        sig_fh,
        pair_mode=pair_mode,
    )
    all_mods = [
        ("sig", "信号引擎", f"hero_action · {signal_status} · {signal_meta_line}", sig_fh, marks.get("sig") or {}),
        ("chess", "Chess", "Chess API", chess_fh, marks.get("chess") or {}),
        ("gt", "正确值", f"P0#{nth} 前", gt_fh, marks.get("gt") or {}),
    ]
    if not pair_mode:
        all_mods[1] = (
            "chess",
            "系统实际（Chess）",
            "Chess API",
            chess_fh,
            marks.get("chess") or {},
        )
    mods = [m for m in all_mods if m[0] in side_order]
    mods.sort(key=lambda m: side_order.index(m[0]))
    kickers = {
        "sig": "模块 1 · 上游",
        "chess": "模块 2 · 系统",
        "gt": "模块 3 · 真值",
    }
    gi_by_mod = {
        "sig": _norm_game_info(sig_norm),
        "chess": _norm_game_info(chess),
        "gt": _norm_game_info(gt),
    }
    peer_gis = [gi_by_mod[m[0]] for m in mods]
    parts: list[str] = []
    for mod, title, sub, _fh, _m in mods:
        others = [gi_by_mod[m[0]] for m in mods if m[0] != mod]
        blinds = _render_blinds_bar(gi_by_mod[mod], others or peer_gis)
        parts.append(
            f'<header class="bhv-mod-head bhv-mod-{_esc(mod)}">'
            f'<span class="bhv-mod-kicker">{_esc(kickers[mod])}</span>'
            f"<strong>{_esc(title)}</strong>"
            f'<span class="bhv-mod-sub">{_esc(sub)}</span>'
            f"{blinds}"
            "</header>"
        )
    n_mod = len(mods)
    for street in _FUSION_STREETS:
        gt_rows = list(gt_fh.get(street) or [])
        chess_rows = list(chess_fh.get(street) or [])
        sig_rows = list(sig_fh.get(street) or [])
        side_rows = {"sig": sig_rows, "chess": chess_rows, "gt": gt_rows}
        union_lists = [side_rows[m[0]] for m in mods]
        aligned = _street_key_union(*union_lists)
        if not aligned and not any(union_lists):
            continue
        for mod, _title, _sub, _fh, col_marks in mods:
            parts.append(
                f'<div class="bhv-street-cell bhv-mod-{_esc(mod)}">'
                + _render_one_street_table(
                    rows=side_rows[mod],
                    marks=col_marks.get(street) if isinstance(col_marks, dict) else None,
                    street=street,
                    current_street=current_street,
                    aligned_keys=aligned,
                )
                + "</div>"
            )
    if len(parts) <= n_mod:
        return '<p class="dim">无行为表可还原</p>'
    return f'<div class="bhv-grid bhv-cols-{n_mod}">' + "".join(parts) + "</div>"


def render_step_detail_page(
    *,
    run_id: str,
    step: dict[str, Any],
    pair_mode: bool = False,
    back_href: str = "",
) -> str:
    hid = str(step.get("hand_uid") or "")
    nth = int(step.get("nth") or 0)
    street = str(step.get("decision_street") or "—").upper()
    hole_html = _cards_html(step.get("hole_key"))
    chess = step.get("chess_norm") if isinstance(step.get("chess_norm"), dict) else None
    issues = step.get("issues") if isinstance(step.get("issues"), list) else []
    if pair_mode:
        left = step.get("signal_gto") if isinstance(step.get("signal_gto"), dict) else None
        compare_mode = "sig_chess"
        left_col = "信号引擎"
        right_col = "Chess"
        back = back_href or f"/discover/compare/{run_id}"
        back_text = "← 返回信号→Chess 总览"
        lead_note = "判定：信号引擎 vs Chess。无 Excel 真值。"
        json_summary = "原始报文对照（信号引擎 / Chess）"
        json_hint = (
            "两列按街道横切对齐；同一座位缺行会留空位。红格 = 信号 ≠ Chess。"
            "各列上方「小盲/大盲/前注」是桌面参数；INIT 的 AMOUNT 只是 SB/BB 已下额，不含前注。"
        )
        json_fold = "原始 JSON（信号引擎 / Chess）"
        legend = (
            '<p class="bhv-legend"><span class="lg-chess"><i></i>红格：信号 ≠ Chess'
            "</span><span>悬停可看两侧对照值</span></p>"
        )
        grid_sides: Optional[tuple[str, ...]] = ("sig", "chess")
    else:
        left = step.get("gt_norm") if isinstance(step.get("gt_norm"), dict) else None
        compare_mode = "gt_chess"
        left_col = "正确值"
        right_col = "系统实际（Chess）"
        back = back_href or f"/step-compare/{run_id}"
        back_text = "← 返回总览"
        lead_note = "测试先看结论，研发再展开 JSON"
        json_summary = "原始报文对照（信号引擎 / Chess / 正确值）"
        json_hint = "三列按街道横切对齐；同一座位缺行会留空位，便于左右对照。一致判定仍只看正确值 vs Chess。"
        json_fold = "原始 JSON（信号引擎 / Chess / 正确值）"
        legend = (
            '<p class="bhv-legend"><span class="lg-chess"><i></i>红格：正确值 ≠ Chess（三列同标）</span>'
            '<span class="lg-sig"><i></i>橙格：Chess 与正确值一致，但信号引擎不同</span>'
            "<span>悬停可看三模块对照值</span></p>"
        )
        grid_sides = None

    structured = build_structured_compare(left, chess, issues=issues, mode=compare_mode)
    rows = structured["rows"]
    counts = structured["counts"]
    pot_rows = structured["pot_rows"]

    gt_json = json.dumps(left, ensure_ascii=False, indent=2) if left is not None else "null"
    chess_json = (
        json.dumps(chess, ensure_ascii=False, indent=2)
        if chess is not None
        else "null  /* Chess API 无值 */"
    )

    has_signal_field = "signal_present" in step or "signal_request" in step
    signal_present = bool(step.get("signal_present"))
    signal_req = step.get("signal_request")
    signal_meta = step.get("signal_meta") if isinstance(step.get("signal_meta"), dict) else {}
    if not has_signal_field:
        signal_status = "本跑批未存信号，请重跑"
        signal_json = "/* 旧跑批无信号引擎字段，请重新生成决策点对比 */"
    elif signal_present and signal_req is not None:
        signal_status = "有"
        signal_json = json.dumps(signal_req, ensure_ascii=False, indent=2)
    else:
        signal_status = "无"
        signal_json = "null  /* 信号引擎无值 */"

    meta_bits = []
    if signal_meta.get("msg_key") is not None:
        meta_bits.append(f"msg_key={signal_meta.get('msg_key')}")
    if signal_meta.get("timestamp"):
        meta_bits.append(_fmt_time(signal_meta.get("timestamp")))
    signal_meta_line = " · ".join(str(x) for x in meta_bits if x) or "—"

    sig_norm = left if pair_mode else (
        step.get("signal_gto") if isinstance(step.get("signal_gto"), dict) else None
    )
    behavior_grid = render_module_behavior_grid(
        gt=None if pair_mode else left,
        chess=chess,
        signal_req=signal_req if has_signal_field else None,
        signal_status=signal_status,
        signal_meta_line=signal_meta_line,
        nth=nth,
        current_street=street,
        sides=grid_sides,
        sig_norm=sig_norm if isinstance(sig_norm, dict) else None,
    )

    def _row_tr(r: dict[str, Any]) -> str:
        vk = r.get("verdict_kind") or ""
        return (
            f'<tr class="vk-{_esc(vk)}">'
            f'<td class="c-item">{_esc(r.get("item") or "—")}</td>'
            f'<td class="c-gt mono">{_esc(_fmt_val(r.get("gt")))}</td>'
            f'<td class="c-sys mono">{_esc(_fmt_val(r.get("sys")))}</td>'
            f'<td class="c-verdict"><span class="tag tag-{_esc(vk)}">{_esc(r.get("verdict") or _verdict_label(vk))}</span></td>'
            f"</tr>"
        )

    issue_rows = [r for r in rows if (r.get("verdict_kind") or "") != "ok"]
    ok_rows = [r for r in rows if (r.get("verdict_kind") or "") == "ok"]
    issue_trs = [_row_tr(r) for r in issue_rows]
    ok_trs = [_row_tr(r) for r in ok_rows]
    if issue_trs:
        table_body = "\n".join(issue_trs)
    elif not ok_trs:
        table_body = (
            '<tr><td colspan="4" class="dim" style="text-align:center;padding:28px">无可对照条目</td></tr>'
        )
    else:
        table_body = (
            '<tr><td colspan="4" class="dim" style="text-align:center;padding:18px">'
            "无不一致项，下方可展开查看全部一致对照"
            "</td></tr>"
        )
    ok_fold = ""
    if ok_trs:
        ok_fold = f"""
  <details class="fold">
    <summary>一致项（默认折叠 · {len(ok_trs)} 项）</summary>
    <div class="fold-body">
      <table class="cmp-table compact">
        <thead><tr><th>项目</th><th>{left_col}</th><th>{right_col}</th><th>差异结论</th></tr></thead>
        <tbody>{"".join(ok_trs)}</tbody>
      </table>
    </div>
  </details>"""

    def _pot_tr(r: dict[str, Any]) -> str:
        vk = r.get("verdict_kind") or ""
        return (
            f'<tr class="vk-{_esc(vk)}">'
            f'<td>{_esc(r.get("item") or "—")}</td>'
            f'<td class="mono">{_esc(_fmt_val(r.get("gt")))}</td>'
            f'<td class="mono">{_esc(_fmt_val(r.get("sys")))}</td>'
            f'<td><span class="tag tag-{_esc(vk)}">{_esc(r.get("verdict") or "")}</span></td>'
            f"</tr>"
        )

    pot_issue = [r for r in pot_rows if (r.get("verdict_kind") or "") != "ok"]
    pot_ok = [r for r in pot_rows if (r.get("verdict_kind") or "") == "ok"]
    pot_section = ""
    if pot_issue:
        pot_section += f"""
  <section class="panel panel-tight" style="margin-top:12px">
    <p class="hint" style="margin:0 0 8px">底池 / 注额不一致</p>
    <div class="cmp-wrap">
      <table class="cmp-table compact">
        <thead><tr><th>项目</th><th>{left_col}</th><th>{right_col}</th><th>结论</th></tr></thead>
        <tbody>{"".join(_pot_tr(r) for r in pot_issue)}</tbody>
      </table>
    </div>
  </section>"""
    if pot_ok:
        pot_section += f"""
  <details class="fold">
    <summary>底池 / 注额一致项（默认折叠 · {len(pot_ok)} 项）</summary>
    <div class="fold-body">
      <table class="cmp-table compact">
        <thead><tr><th>项目</th><th>{left_col}</th><th>{right_col}</th><th>结论</th></tr></thead>
        <tbody>{"".join(_pot_tr(r) for r in pot_ok)}</tbody>
      </table>
    </div>
  </details>"""

    overall = _step_status_html(
        step.get("chess_exact"),
        signal_present if has_signal_field else False,
        stored_signal=has_signal_field,
    )
    nav_active = "discover" if pair_mode else "step-compare"
    json_grid_cls = "json-grid bhv-cols-2" if pair_mode else "json-grid"
    chess_head = "Chess" if pair_mode else "系统实际（Chess）"
    json_gt_col = ""
    if not pair_mode:
        json_gt_col = f"""
        <div class="json-col bhv-mod-gt">
          <header class="bhv-mod-head">
            <span class="bhv-mod-kicker">模块 3 · 真值</span>
            <strong>正确值</strong>
            <span class="bhv-mod-sub">P0#{nth} 前</span>
          </header>
          <pre class="json">{_esc(gt_json)}</pre>
        </div>"""
    hid_title = hid or (step.get("hole_key") or "hand")
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>P0#{nth} · {_esc(hid_title)}</title>
<style>{_CSS}
{_CARDS_CSS}
.sc-page {{ max-width: 1440px; }}
.sc-page h1 {{
  font-size: 24px; letter-spacing: -0.03em;
  font-family: "Songti SC", "Noto Serif SC", "PingFang SC", serif; font-weight: 700;
  display:flex; flex-wrap:wrap; align-items:center; gap:8px 10px;
}}
.sc-page h1 .hand-hole {{ display:inline-flex; align-items:center; }}
.back-row {{ margin-bottom: 8px; font-size: 13px; }}
.back-row a {{ color: var(--accent); text-decoration: none; font-weight: 600; }}
.badge {{ display:inline-block; font-size:11px; font-weight:700; padding:2px 7px; border-radius:999px; margin-left:8px; vertical-align:middle; }}
.badge.ok {{ background:var(--accent-soft); color:var(--accent); }}
.badge.bad {{ background:#ffe4e6; color:var(--warn); }}
.badge.muted {{ background:#f5f5f4; color:var(--muted); }}
.meta-line {{
  display:flex; flex-wrap:wrap; gap:8px 14px; align-items:center;
  font-size:13px; color:var(--muted); margin-bottom:14px;
}}
.meta-line strong {{ color:var(--ink); }}
.street-tag {{
  display:inline-block; font-size:11px; font-weight:800; padding:3px 7px; border-radius:6px;
  background:#f5f5f4; color:#57534e;
}}
.street-tag.street-preflop {{ background:#ecfdf5; color:#047857; }}
.street-tag.street-flop {{ background:#eff6ff; color:#1d4ed8; }}
.street-tag.street-turn {{ background:#fff7ed; color:#c2410c; }}
.street-tag.street-river {{ background:#faf5ff; color:#7e22ce; }}
.verdict-bar {{
  display:flex; flex-wrap:wrap; gap:8px; margin-bottom:14px;
}}
.vchip {{
  display:flex; flex-direction:column; gap:2px; min-width:76px;
  padding:8px 12px; background:#fff; border:1px solid var(--line); border-radius:10px;
}}
.vchip .k {{ font-size:11px; font-weight:700; color:var(--muted); }}
.vchip .v {{ font-size:18px; font-weight:800; font-variant-numeric:tabular-nums; }}
.vchip.ok .v {{ color:var(--accent); }}
.vchip.diff .v {{ color:var(--warn); }}
.vchip.missing .v {{ color:#b45309; }}
.vchip.pending .v {{ color:#57534e; }}
.cmp-wrap {{ overflow:auto; }}
table.cmp-table {{ width:100%; border-collapse:collapse; font-size:13px; }}
table.cmp-table th, table.cmp-table td {{
  text-align:left; padding:10px 12px; border-bottom:1px solid #f0ebe3; vertical-align:top;
}}
table.cmp-table th {{
  position:sticky; top:0; background:#faf8f5; color:var(--muted);
  font-size:11px; font-weight:700; letter-spacing:.04em; z-index:1;
}}
table.cmp-table td.mono {{
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:12.5px;
}}
table.cmp-table tr.vk-diff {{ background:#fff7f7; }}
table.cmp-table tr.vk-missing {{ background:#fffbeb; }}
table.cmp-table tr.vk-extra {{ background:#fff7ed; }}
table.cmp-table tr.vk-pending {{ background:#fafaf9; }}
table.cmp-table.compact td, table.cmp-table.compact th {{ padding:8px 10px; }}
.tag {{
  display:inline-block; font-size:11px; font-weight:800; padding:3px 8px; border-radius:6px;
  background:#f5f5f4; color:#57534e; white-space:nowrap;
}}
.tag-ok {{ background:var(--accent-soft); color:var(--accent); }}
.tag-diff {{ background:#ffe4e6; color:var(--warn); }}
.tag-missing {{ background:#fef3c7; color:#b45309; }}
.tag-extra {{ background:#ffedd5; color:#c2410c; }}
.tag-pending {{ background:#e7e5e4; color:#44403c; }}
.tag-absent {{ background:#fef3c7; color:#b45309; }}
.fold {{
  background:#fff; border:1px solid var(--line); border-radius:12px;
  margin-top:12px; padding:0;
}}
.fold > summary {{
  cursor:pointer; list-style:none; padding:12px 16px;
  font-size:13px; font-weight:700; color:var(--ink);
}}
.fold > summary::-webkit-details-marker {{ display:none; }}
.fold > summary::before {{
  content:"▸ "; color:var(--muted); font-weight:800;
}}
.fold[open] > summary::before {{ content:"▾ "; }}
.fold-body {{ padding:0 16px 14px; }}
.fold .hint {{ font-size:12px; color:var(--muted); margin:0 0 10px; font-weight:600; }}
.json-grid {{ display:grid; grid-template-columns:1fr 1fr 1fr; gap:16px; align-items:start; }}
.json-grid.bhv-cols-2 {{ grid-template-columns:1fr 1fr; }}
@media (max-width: 1100px) {{ .json-grid {{ grid-template-columns:1fr; }} }}
.bhv-grid {{
  display:grid; grid-template-columns:1fr 1fr 1fr;
  column-gap:16px; row-gap:0; align-items:stretch;
}}
.bhv-grid.bhv-cols-2 {{ grid-template-columns:1fr 1fr; }}
.bhv-mod {{
  min-width:0;
}}
.bhv-mod-sig {{ --mod:#c2410c; --mod-soft:#fff7ed; --mod-ink:#9a3412; }}
.bhv-mod-chess {{ --mod:#1d4ed8; --mod-soft:#eff6ff; --mod-ink:#1e40af; }}
.bhv-mod-gt {{ --mod:#0f766e; --mod-soft:#ccfbf1; --mod-ink:#0f766e; }}
.bhv-mod-head {{
  position:sticky; top:0; z-index:3;
  display:flex; flex-direction:column; gap:2px;
  padding:10px 12px; background:var(--mod-soft);
  border:1px solid var(--line);
  border-top:3px solid var(--mod, #78716c);
  border-radius:12px 12px 0 0;
  min-width:0;
}}
.bhv-street-cell {{
  min-width:0; background:#fff; padding:10px 10px 12px;
  border:1px solid var(--line); border-top:none;
}}
.bhv-grid:not(.bhv-cols-2) .bhv-street-cell:nth-last-child(-n+3),
.bhv-grid.bhv-cols-2 .bhv-street-cell:nth-last-child(-n+2) {{
  border-radius:0 0 12px 12px; padding-bottom:14px;
}}
.bhv-mod-kicker {{
  font-size:10px; font-weight:800; letter-spacing:.06em; text-transform:uppercase;
  color:var(--mod-ink);
}}
.bhv-mod-head strong {{
  font-size:14px; font-weight:800; color:var(--mod-ink); letter-spacing:-.02em;
}}
.bhv-mod-sub {{
  font-size:11px; font-weight:600; color:var(--muted); line-height:1.35;
  word-break:break-all;
}}
.bhv-blinds {{
  display:flex; flex-wrap:wrap; gap:4px 8px; margin-top:6px;
  font-size:11px; font-weight:700; font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
}}
.bhv-blinds .bb-ok {{ color:var(--mod-ink); opacity:.85; }}
.bhv-blinds .bb-diff {{
  background:#fee2e2; color:#b91c1c; padding:1px 6px; border-radius:4px;
}}
.bhv-street-note {{
  font-size:10px; color:var(--muted); font-weight:600; margin:0 0 6px; line-height:1.35;
}}
.bhv-street {{ margin:0; }}
.bhv-street-h {{
  font-size:10px; font-weight:800; color:var(--mod-ink);
  text-transform:uppercase; letter-spacing:.04em; margin:0 0 4px;
}}
.bhv-street.is-current .bhv-street-h {{ color:#047857; }}
.bhv-scroll {{ overflow-x:auto; }}
table.bhv-tbl {{ width:100%; border-collapse:collapse; font-size:11px; }}
table.bhv-tbl th {{
  color:var(--mod-ink); font-size:9px; font-weight:700; text-transform:uppercase;
  text-align:left; padding:6px 4px 4px; border-bottom:2px solid var(--line);
  white-space:nowrap; letter-spacing:.02em; background:#fff;
}}
table.bhv-tbl td {{
  padding:3px 4px; font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
  font-size:10.5px; border-bottom:1px solid #f0ebe3; white-space:nowrap;
  color:var(--ink);
}}
table.bhv-tbl tr:last-child td {{ border-bottom:none; }}
table.bhv-tbl tr.bhv-absent td {{
  background:#fafaf9; color:#a8a29e; font-style:italic;
}}
table.bhv-tbl td.bhv-chess {{
  background:#ffe4e6; color:var(--warn); font-weight:700;
  box-shadow:inset 0 0 0 1px #fda4af; border-radius:3px; font-style:normal;
}}
table.bhv-tbl td.bhv-sig {{
  background:#fff7ed; color:#c2410c; font-weight:700;
  box-shadow:inset 0 0 0 1px #fdba74; border-radius:3px; font-style:normal;
}}
.json-col {{
  min-width:0; background:#fff; border:1px solid var(--line); border-radius:12px;
  overflow:hidden; border-top:3px solid var(--mod, #78716c);
}}
.json-col .bhv-mod-head {{
  margin:0; border-radius:0; border:none; border-bottom:1px solid var(--line);
}}
.json-col pre.json {{ border-radius:0; max-height:420px; }}
.bhv-legend {{
  display:flex; flex-wrap:wrap; gap:10px 16px; align-items:center;
  font-size:11px; color:var(--muted); margin:0 0 10px; font-weight:600;
}}
.bhv-legend i {{
  display:inline-block; width:10px; height:10px; border-radius:2px;
  margin-right:5px; vertical-align:-1px;
}}
.bhv-legend .lg-chess i {{ background:#ffe4e6; box-shadow:inset 0 0 0 1px #fda4af; }}
.bhv-legend .lg-sig i {{ background:#fff7ed; box-shadow:inset 0 0 0 1px #fdba74; }}
.json-col .hint {{
  display:flex; flex-wrap:wrap; align-items:center; gap:6px;
  font-size:12px; color:var(--muted); margin:0 0 8px; font-weight:700;
}}
.json-col .hint .sub {{ font-weight:600; color:#a8a29e; }}
pre.json {{
  margin:0; padding:12px 14px; background:#1c1917; color:#fafaf9;
  border-radius:12px; overflow:auto; max-height:420px;
  font-size:12px; line-height:1.45;
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
}}
.dim {{ color:var(--muted); }}
.panel-tight {{ padding:14px 16px; }}
</style>
</head>
<body>
{_shell_open(nav_active, wrap_class="wrap sc-page")}
  <div class="topbar">
    <div class="topbar-text">
      <div class="back-row">
        <a class="js-no-back" href="{_esc(back)}">{_esc(back_text)}</a>
      </div>
      <h1>P0#{nth} · {_esc(hid_title)} <span class="hand-hole">{hole_html}</span> {overall}</h1>
      <p class="lead">{_esc(step.get("next_p0_label") or "")} ·
        <span class="street-tag street-{_esc(street.lower())}">{_esc(street)}</span>
        · {_esc(lead_note)}</p>
    </div>
  </div>

  <div class="meta-line">
    <span>手牌 {hole_html}</span>
    <span>裁后行动数 <strong>{_esc(step.get("truncated_action_len"))}</strong></span>
    <span>对齐 <strong>{_esc(step.get("align_mode") or "—")}</strong></span>
    <span>hero <strong>{_esc(step.get("hero_ordinal") or "—")} / {_esc(step.get("hero_count") or "—")}</strong></span>
    <span>信号引擎 <strong>{_esc(signal_status)}</strong>
      <span class="dim">({_esc(signal_meta_line)})</span></span>
  </div>

  <div class="verdict-bar" aria-label="判定汇总">
    <div class="vchip ok"><span class="k">一致</span><span class="v">{counts.get("ok", 0)}</span></div>
    <div class="vchip diff"><span class="k">差异</span><span class="v">{counts.get("diff", 0)}</span></div>
    <div class="vchip missing"><span class="k">漏/缺</span><span class="v">{counts.get("missing", 0)}</span></div>
    <div class="vchip pending"><span class="k">待确认</span><span class="v">{counts.get("pending", 0)}</span></div>
  </div>

  <section class="panel panel-tight">
    <p class="hint" style="margin:0 0 10px">默认只展开不一致项；一致项折叠在下方。</p>
    <div class="cmp-wrap">
      <table class="cmp-table">
        <thead>
          <tr>
            <th style="width:18%">项目</th>
            <th style="width:28%">{_esc(left_col)}</th>
            <th style="width:28%">{_esc(right_col)}</th>
            <th style="width:26%">差异结论</th>
          </tr>
        </thead>
        <tbody>
{table_body}
        </tbody>
      </table>
    </div>
  </section>
{ok_fold}

{pot_section}

  <details class="fold" open>
    <summary>{_esc(json_summary)}</summary>
    <div class="fold-body">
      <p class="hint">{_esc(json_hint)}</p>
      {legend}
{behavior_grid}
    </div>
  </details>

  <details class="fold">
    <summary>{_esc(json_fold)}</summary>
    <div class="fold-body">
      <p class="hint">原始报文，需要抠字段时再展开。</p>
      <div class="{json_grid_cls}">
        <div class="json-col bhv-mod-sig">
          <header class="bhv-mod-head">
            <span class="bhv-mod-kicker">模块 1 · 上游</span>
            <strong>信号引擎</strong>
            <span class="bhv-mod-sub">hero_action · {_esc(signal_status)} · {_esc(signal_meta_line)}</span>
          </header>
          <pre class="json">{_esc(signal_json)}</pre>
        </div>
        <div class="json-col bhv-mod-chess">
          <header class="bhv-mod-head">
            <span class="bhv-mod-kicker">模块 2 · 系统</span>
            <strong>{_esc(chess_head)}</strong>
            <span class="bhv-mod-sub">Chess API</span>
          </header>
          <pre class="json">{_esc(chess_json)}</pre>
        </div>
        {json_gt_col}
      </div>
    </div>
  </details>
{_shell_close()}
</body>
</html>"""
