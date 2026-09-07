"""组合发现 · 信号 vs Chess 现场对比页。"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from manage_page import _CSS, _JS_COMMON, _esc, _shell_close, _shell_open
from step_compare_pages import _cards_html, _cards_plain, _fmt_time, _step_status_html

try:
    from gt_steps.pages import _CARDS_CSS
except Exception:  # pragma: no cover
    _CARDS_CSS = ""


def render_discover_compare_loading_page(
    *,
    open_id: str,
    hole_cards: str,
    start: str,
    end: str,
) -> str:
    hole_html = _cards_html(hole_cards)
    payload = {
        "openId": open_id,
        "holeCards": hole_cards,
        "startTime": start,
        "endTime": end,
    }
    import json

    payload_js = json.dumps(payload, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>信号→Chess · 对比中</title>
<style>{_CSS}
{_CARDS_CSS}
.sc-page {{ max-width: 720px; }}
.sc-page h1 {{
  font-size: 24px; letter-spacing: -0.03em;
  font-family: "Songti SC", "Noto Serif SC", "PingFang SC", serif; font-weight: 700;
}}
.back-row {{ margin-bottom: 8px; font-size: 13px; }}
.back-row a {{ color: var(--accent); text-decoration: none; font-weight: 600; }}
.status {{ margin-top: 12px; font-size: 13px; color: var(--muted); min-height: 1.4em; }}
.status.err {{ color: var(--warn); }}
.meta {{ font-size: 13px; color: var(--muted); }}
.meta strong {{ color: var(--ink); }}
</style>
</head>
<body>
{_shell_open("discover", wrap_class="wrap sc-page")}
  <div class="topbar">
    <div class="topbar-text">
      <div class="back-row"><a class="js-no-back" href="/discover">← 组合发现</a></div>
      <h1>信号 → Chess</h1>
      <p class="lead">按每次 hero_action 对照信号引擎与 Chess，看从上游到系统差了什么。</p>
    </div>
  </div>
  <section class="panel">
    <p class="meta">OpenID <strong class="mono">{_esc(open_id)}</strong></p>
    <p class="meta">底牌 {hole_html}</p>
    <p class="meta">时间窗 <strong>{_esc(start)}</strong> ~ <strong>{_esc(end)}</strong></p>
    <p class="status" id="st">正在拉取 Trace，并对每一次 hero_action 做对比…</p>
  </section>
{_shell_close()}
<script>
{_JS_COMMON}
(async function() {{
  var st = document.getElementById('st');
  try {{
    var data = await postJson('/api/discover-compare', {payload_js});
    if (!data || !data.ok) throw new Error((data && data.error) || '对比失败');
    location.href = '/discover/compare/' + encodeURIComponent(data.compare_id || '');
  }} catch (e) {{
    st.className = 'status err';
    st.textContent = String(e.message || e);
  }}
}})();
</script>
</body>
</html>"""


def render_discover_compare_index(
    *,
    compare_id: str,
    meta: dict[str, Any],
    summary: dict[str, Any],
) -> str:
    metrics = summary.get("metrics") if isinstance(summary.get("metrics"), dict) else {}
    steps = summary.get("steps") if isinstance(summary.get("steps"), list) else []
    hole = meta.get("hole_key") or (steps[0].get("hole_key") if steps else "")
    hole_html = _cards_html(hole)
    hole_plain = _cards_plain(hole)
    hole_compact = hole_plain.replace(" ", "")
    hand_search = " ".join(x for x in (hole_plain, hole_compact, str(hole or "")) if x)

    step_rows = []
    for s in steps:
        nth = int(s.get("nth") or 0)
        href = f"/discover/compare/{_esc(compare_id)}/{nth}"
        street = str(s.get("decision_street") or "—").upper()
        st_html = _step_status_html(
            s.get("chess_exact"),
            s.get("signal_present"),
            stored_signal=True,
        )
        issue = s.get("first_issue") or ""
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
    if step_rows:
        body = (
            f'<article class="hand-block" data-search="{_esc(hand_search)}">'
            f'<header class="hand-head">'
            f'<div class="hand-id">'
            f'<span class="hand-hole" title="手牌 {_esc(hole_plain)}">{hole_html}</span>'
            f'<span class="step-count">{len(steps)} 次 hero</span>'
            f"</div>"
            f"</header>"
            f'<div class="step-list">{"".join(step_rows)}</div>'
            f"</article>"
        )
    else:
        body = '<div class="gs-empty">这段 Trace 没有 hero_action，无法按决策点对照。</div>'

    exact_pct = metrics.get("exact_pct")
    pct_s = f"{exact_pct}%" if exact_pct is not None else "—"
    oid = meta.get("open_id") or "—"
    when = _fmt_time(metrics.get("generated_at"))
    q_start = meta.get("start_time") or ""
    q_end = meta.get("end_time") or ""
    retry_q = (
        f"/discover/compare?openId={quote(str(oid))}"
        f"&holeCards={quote(str(hole or ''))}"
        f"&start={quote(str(q_start))}"
        f"&end={quote(str(q_end))}"
    )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>信号→Chess · {_esc(compare_id)}</title>
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
.hand-head {{
  display:flex; flex-wrap:nowrap; align-items:center;
  gap:10px 16px; padding:12px 16px; background:#fafaf9; border-bottom:1px solid #f0eeea;
}}
.hand-id {{ display:flex; align-items:center; gap:10px; flex-wrap:nowrap; }}
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
}}
</style>
</head>
<body>
{_shell_open("discover", wrap_class="wrap sc-page")}
  <div class="topbar">
    <div class="topbar-text">
      <div class="back-row">
        <a class="js-no-back" href="/discover">← 组合发现</a>
        · <a class="js-no-back" href="{_esc(retry_q)}">重新对比</a>
      </div>
      <h1>信号 → Chess · {hole_html}</h1>
      <p class="lead">OpenID <code>{_esc(oid)}</code>
        · {_esc(q_start)} ~ {_esc(q_end)}
        · span {_esc(metrics.get("span_n") if metrics.get("span_n") is not None else meta.get("span_n") or 0)}
        · {_esc(when)}
        · 不写冻结报告，判定只看信号 vs Chess</p>
    </div>
  </div>
  <div class="gs-toolbar">
  <div class="gs-metrics">
    <div class="gs-metric"><span class="k">hero 次数</span><span class="v">{_esc(metrics.get("hero_n") or metrics.get("step_n") or 0)}</span></div>
    <div class="gs-metric"><span class="k">一致</span><span class="v">{_esc(metrics.get("exact_n") or 0)}</span></div>
    <div class="gs-metric"><span class="k">差异</span><span class="v">{_esc(metrics.get("diff_n") or 0)}</span></div>
    <div class="gs-metric"><span class="k">缺 Chess</span><span class="v">{_esc(metrics.get("no_chess_n") or 0)}</span></div>
    <div class="gs-metric"><span class="k">缺信号</span><span class="v">{_esc(metrics.get("no_signal_n") or 0)}</span></div>
    <div class="gs-metric"><span class="k">一致率</span><span class="v">{_esc(pct_s)}</span></div>
  </div>
  </div>
  <div class="hand-list">
{body}
  </div>
{_shell_close()}
</body>
</html>"""
