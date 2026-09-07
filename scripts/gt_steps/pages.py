"""P0 决策点报文 — 独立页面（不改动正确值管理页）。"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any, Optional

from manage_page import (  # type: ignore
    _CSS,
    _JS_COMMON,
    _esc,
    _shell_close,
    _shell_open,
)

_SUIT_CLASS = {"H": "heart", "D": "diam", "C": "club", "S": "spade"}


def _parse_cards(raw: Any) -> list[str]:
    """Parse hole_key / communityCards into ['QC','5H', ...]."""
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        return [str(x).strip().upper() for x in raw if str(x).strip()]
    s = str(raw).strip()
    if not s or s == "—":
        return []
    try:
        v = json.loads(s)
        if isinstance(v, list):
            return [str(x).strip().upper() for x in v if str(x).strip()]
    except Exception:
        pass
    # QC5H / QC 5H / QC,5H
    parts = re.findall(r"[0-9TJQKA]{1,2}[CDHS]", s.upper())
    if parts:
        return parts
    return [s]


def _card_chip(code: str) -> str:
    c = str(code or "").strip().upper()
    if len(c) < 2:
        return f'<span class="card">{_esc(c or "?")}</span>'
    suit = c[-1]
    rank = c[:-1]
    cls = _SUIT_CLASS.get(suit, "")
    return (
        f'<span class="card {cls}" title="{_esc(c)}">'
        f'<b>{_esc(rank)}</b><i>{_esc(suit)}</i></span>'
    )


def _cards_html(raw: Any) -> str:
    cards = _parse_cards(raw)
    if not cards:
        return '<span class="cards-empty">—</span>'
    return '<span class="cards">' + "".join(_card_chip(c) for c in cards) + "</span>"


def _cards_plain(raw: Any) -> str:
    cards = _parse_cards(raw)
    return " ".join(cards) if cards else ""


_CARDS_CSS = """
.cards { display:inline-flex; flex-wrap:wrap; gap:4px; vertical-align:middle; }
.cards-empty { color:var(--muted); }
.card {
  display:inline-flex; align-items:baseline; gap:1px;
  min-width:2.1em; justify-content:center;
  padding:2px 6px; border-radius:6px;
  background:#f5f5f4; border:1px solid #e7e5e4;
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
  font-size:12px; font-weight:700; color:#1c1917; line-height:1.3;
}
.card i { font-style:normal; font-weight:600; font-size:10px; opacity:.75; margin-left:1px; }
.card.heart, .card.diam { color:#b91c1c; background:#fef2f2; border-color:#fecaca; }
.card.club, .card.spade { color:#1c1917; background:#f5f5f4; border-color:#e7e5e4; }
"""


def render_gt_steps_index(
    *,
    gt_versions: list[dict[str, Any]],
    current_gt: Optional[str],
) -> str:
    rows = []
    for v in gt_versions:
        vid = str(v.get("id") or "")
        is_cur = bool(v.get("is_current")) or (vid and vid == current_gt)
        badge = ' <span class="badge ok">当前</span>' if is_cur else ""
        note = _esc(str(v.get("note") or "")[:80])
        rows.append(
            "<tr>"
            f'<td class="mono"><a href="/gt-steps/{_esc(vid)}">{_esc(vid)}</a>{badge}</td>'
            f'<td class="num">{_esc(v.get("hand_count", "—"))}</td>'
            f'<td class="num">{_esc(v.get("with_gt_n", "—"))}</td>'
            f'<td class="dim">{_esc(v.get("updated_at") or v.get("created_at") or "—")}</td>'
            f'<td class="dim">{note or "—"}</td>'
            f'<td><a class="btn primary" href="/gt-steps/{_esc(vid)}">打开</a></td>'
            "</tr>"
        )
    body_rows = "\n".join(rows) if rows else (
        '<tr><td colspan="6" class="dim" style="text-align:center;padding:32px">'
        "暂无正确值版本</td></tr>"
    )
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>P0 决策点报文</title>
<style>{_CSS}
.gs-page {{ max-width: 1100px; }}
.gs-page h1 {{
  font-size: 28px; letter-spacing: -0.03em;
  font-family: "Songti SC", "Noto Serif SC", "PingFang SC", serif; font-weight: 700;
}}
.badge {{ display:inline-block; font-size:11px; font-weight:700; padding:2px 7px;
  border-radius:999px; margin-left:6px; vertical-align:middle; }}
.badge.ok {{ background:var(--accent-soft); color:var(--accent); }}
.panel-gs {{ padding: 0; overflow: hidden; }}
table.steps-ver {{ width:100%; border-collapse:collapse; font-size:13px; }}
table.steps-ver th, table.steps-ver td {{
  text-align:left; padding:12px 16px; border-bottom:1px solid #f0ebe3; vertical-align:middle;
}}
table.steps-ver th {{
  color:var(--muted); font-weight:700; font-size:11px; letter-spacing:.04em; background:#faf8f5;
}}
table.steps-ver td.mono {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:12.5px; }}
table.steps-ver td.mono a {{ color:var(--ink); font-weight:700; text-decoration:none; }}
table.steps-ver td.mono a:hover {{ color:var(--accent); }}
table.steps-ver td.num {{ font-variant-numeric:tabular-nums; }}
table.steps-ver td.dim {{ color:var(--muted); }}
table.steps-ver tbody tr:hover {{ background:#f8fffd; }}
table.steps-ver tbody tr:last-child td {{ border-bottom:none; }}
</style>
</head>
<body>
{_shell_open("gt-steps", wrap_class="wrap gs-page")}
  <div class="topbar">
    <div class="topbar-text">
      <h1>P0 决策点报文</h1>
      <p class="lead">从正确值拆出每一次 P0 行动前的请求快照（只读，不影响正确值管理）。</p>
    </div>
  </div>
  <section class="panel panel-gs">
    <table class="steps-ver">
      <thead>
        <tr>
          <th>版本</th><th>手数</th><th>有正确值</th><th>更新</th><th>备注</th><th></th>
        </tr>
      </thead>
      <tbody>
{body_rows}
      </tbody>
    </table>
  </section>
{_shell_close()}
</body>
</html>"""


def render_gt_steps_version_page(
    *,
    version_id: str,
    meta: dict[str, Any],
    brief: dict[str, Any],
    current_gt: Optional[str],
) -> str:
    is_cur = version_id == current_gt or bool(meta.get("is_current"))
    cur_badge = ' <span class="badge ok">当前</span>' if is_cur else ""
    step_n = int(brief.get("step_count") or 0)
    hand_n = int(brief.get("hand_count") or 0)
    with_gt = int(brief.get("with_gt_n") or 0)

    # Group steps by hand (preserve hand order from brief.hands)
    by_hand: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for s in brief.get("steps") or []:
        by_hand[str(s.get("hand_uid") or "")].append(s)

    hand_order = [str(h.get("hand_uid") or "") for h in (brief.get("hands") or [])]
    # append any stray hands
    for hid in by_hand:
        if hid not in hand_order:
            hand_order.append(hid)

    blocks: list[str] = []
    for hid in hand_order:
        steps = by_hand.get(hid) or []
        hand_meta = next((h for h in (brief.get("hands") or []) if h.get("hand_uid") == hid), {})
        hole_raw = hand_meta.get("hole_key") or (steps[0].get("hole_key") if steps else "")
        hole_html = _cards_html(hole_raw)
        hole_plain = _esc(_cards_plain(hole_raw) or str(hole_raw or ""))
        n_steps = len(steps)
        streets = sorted({str(s.get("decision_street") or "").upper() for s in steps if s.get("decision_street")})
        streets_attr = " ".join(st.lower() for st in streets)

        step_rows = []
        for s in steps:
            nth = int(s.get("nth") or 0)
            street = str(s.get("decision_street") or "—").upper()
            label = _esc(s.get("next_p0_label") or "—")
            alen = _esc(s.get("truncated_action_len"))
            href = f"/gt-steps/{_esc(version_id)}/{_esc(hid)}/{nth}"
            step_rows.append(
                f'<a class="step-row" href="{href}" '
                f'data-street="{_esc(street.lower())}" data-nth="{nth}" '
                f'data-search="{_esc(hid)} {hole_plain} {street} {label}">'
                f'<span class="c-nth">P0#{nth}</span>'
                f'<span class="c-street"><span class="street-tag street-{_esc(street.lower())}">'
                f"{_esc(street)}</span></span>"
                f'<span class="c-alen">{alen}</span>'
                f'<span class="c-act">{label}</span>'
                f'<span class="c-go">查看 →</span>'
                f"</a>"
            )

        if not step_rows:
            continue

        blocks.append(
            f'<article class="hand-block" data-hand="{_esc(hid)}" '
            f'data-streets="{_esc(streets_attr)}" '
            f'data-search="{_esc(hid)} {hole_plain}">'
            f'<header class="hand-head">'
            f'<div class="hand-id">'
            f'<span class="mono">{_esc(hid)}</span>'
            f'<span class="hand-hole" title="手牌">{hole_html}</span>'
            f'<span class="step-count">{n_steps} 次 P0</span>'
            f"</div>"
            f"</header>"
            f'<div class="step-cols" aria-hidden="true">'
            f'<span>序</span><span>街</span><span>裁后行动数</span><span>即将行动</span><span></span>'
            f"</div>"
            f'<div class="step-list">{"".join(step_rows)}</div>'
            f"</article>"
        )

    body_html = "\n".join(blocks) if blocks else (
        '<div class="gs-empty">该版本没有可拆分的 P0 决策点</div>'
    )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>决策点 · {_esc(version_id)}</title>
<style>{_CSS}
{_CARDS_CSS}
.gs-page {{ max-width: 1100px; }}
.gs-page h1 {{
  font-size: 26px; letter-spacing: -0.03em;
  font-family: "Songti SC", "Noto Serif SC", "PingFang SC", serif; font-weight: 700;
}}
.gs-page h1 .mono {{
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.72em; font-weight: 700; letter-spacing: -0.02em;
}}
.badge {{ display:inline-block; font-size:11px; font-weight:700; padding:2px 7px;
  border-radius:999px; margin-left:6px; vertical-align:middle; }}
.badge.ok {{ background:var(--accent-soft); color:var(--accent); }}
.back-row {{ margin-bottom:8px; font-size:13px; }}
.back-row a {{ color:var(--accent); text-decoration:none; font-weight:600; }}
.back-row a:hover {{ text-decoration:underline; }}

.gs-toolbar {{
  display:flex; flex-wrap:wrap; align-items:center; gap:12px 16px;
  margin-bottom:16px;
}}
.gs-metrics {{
  display:flex; flex-wrap:wrap; gap:8px;
}}
.gs-metric {{
  display:flex; flex-direction:column; gap:2px;
  min-width:72px; padding:8px 12px;
  background:#fff; border:1px solid var(--line); border-radius:10px;
}}
.gs-metric .k {{ font-size:11px; font-weight:700; color:var(--muted); }}
.gs-metric .v {{
  font-size:18px; font-weight:800; color:var(--ink);
  font-variant-numeric:tabular-nums; letter-spacing:-0.02em;
}}
.gs-filters {{
  display:flex; flex-wrap:wrap; align-items:center; gap:8px 10px;
  margin-left:auto;
}}
.gs-filters input[type="search"] {{
  font:inherit; font-size:13px; padding:9px 12px; width:min(260px, 100%);
  border:1px solid var(--line); border-radius:8px; background:#fff; color:var(--ink);
}}
.gs-filters input[type="search"]:focus {{
  outline:none; border-color:#5eead4; box-shadow:0 0 0 3px rgba(15,118,110,.12);
}}
.street-pills {{ display:flex; flex-wrap:wrap; gap:4px; }}
.street-pill {{
  appearance:none; border:1px solid var(--line); background:#fff;
  color:#57534e; font:inherit; font-size:12px; font-weight:600;
  padding:7px 10px; border-radius:8px; cursor:pointer;
}}
.street-pill:hover {{ border-color:#99f6e4; color:var(--accent); }}
.street-pill.is-on {{
  border-color:#99f6e4; color:var(--accent); background:var(--accent-soft);
}}
.gs-filter-hint {{ font-size:12px; color:var(--muted); font-weight:600; min-width:4em; }}

.hand-list {{ display:flex; flex-direction:column; gap:10px; }}
.hand-block {{
  background:#fff; border:1px solid var(--line); border-radius:12px; overflow:hidden;
  animation: gs-in .22s ease both;
}}
.hand-block.is-hidden {{ display:none; }}
@keyframes gs-in {{
  from {{ opacity:0; transform:translateY(4px); }}
  to {{ opacity:1; transform:none; }}
}}
.hand-head {{
  display:flex; flex-wrap:wrap; align-items:center;
  gap:10px 16px; padding:12px 16px; background:#fafaf9; border-bottom:1px solid #f0eeea;
}}
.hand-id {{ display:flex; align-items:center; gap:10px; flex-wrap:wrap; }}
.hand-id .hand-hole {{ display:inline-flex; align-items:center; }}
.hand-id .mono {{
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
  font-size:14px; font-weight:800; color:var(--ink);
}}
.hand-id .step-count {{
  font-size:12px; font-weight:700; color:var(--accent);
  background:var(--accent-soft); padding:2px 8px; border-radius:999px;
}}
.step-cols {{
  display:grid; grid-template-columns: 72px 110px 88px 1fr 64px;
  gap:8px; padding:6px 16px; font-size:11px; font-weight:700;
  color:var(--muted); letter-spacing:.03em; background:#fff;
}}
.step-list {{ display:flex; flex-direction:column; }}
.step-row {{
  display:grid; grid-template-columns: 72px 110px 88px 1fr 64px;
  gap:8px; align-items:center;
  padding:11px 16px; text-decoration:none; color:inherit;
  border-top:1px solid #f3efe8;
  transition: background .1s ease;
}}
.step-row:hover {{ background:#f8fffd; }}
.step-row.is-hidden {{ display:none; }}
.step-row .c-nth {{
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
  font-size:12.5px; font-weight:800; color:var(--ink);
}}
.step-row .c-alen {{
  font-variant-numeric:tabular-nums; font-weight:600; color:#57534e;
}}
.step-row .c-act {{
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
  font-size:12.5px; font-weight:700; color:var(--ink);
}}
.step-row .c-go {{
  text-align:right; font-size:12px; font-weight:700; color:var(--accent);
  opacity:.0; transition: opacity .12s ease;
}}
.step-row:hover .c-go {{ opacity:1; }}
.street-tag {{
  display:inline-block; font-size:11px; font-weight:800; letter-spacing:.04em;
  padding:3px 7px; border-radius:6px; background:#f5f5f4; color:#57534e;
}}
.street-tag.street-preflop {{ background:#ecfdf5; color:#047857; }}
.street-tag.street-flop {{ background:#eff6ff; color:#1d4ed8; }}
.street-tag.street-turn {{ background:#fff7ed; color:#c2410c; }}
.street-tag.street-river {{ background:#faf5ff; color:#7e22ce; }}
.gs-empty {{
  text-align:center; color:var(--muted); padding:48px 16px;
  background:#fff; border:1px solid var(--line); border-radius:12px;
}}
@media (max-width: 720px) {{
  .gs-filters {{ margin-left:0; width:100%; }}
  .gs-filters input[type="search"] {{ width:100%; }}
  .step-cols {{ display:none; }}
  .step-row {{
    grid-template-columns: 64px 1fr auto;
    grid-template-areas: "nth street go" "alen act act";
  }}
  .step-row .c-nth {{ grid-area: nth; }}
  .step-row .c-street {{ grid-area: street; }}
  .step-row .c-alen {{ grid-area: alen; font-size:12px; color:var(--muted); }}
  .step-row .c-alen::before {{ content: "裁后 "; font-weight:600; }}
  .step-row .c-act {{ grid-area: act; }}
  .step-row .c-go {{ grid-area: go; opacity:1; }}
}}
</style>
</head>
<body>
{_shell_open("gt-steps", wrap_class="wrap gs-page")}
  <div class="topbar">
    <div class="topbar-text">
      <div class="back-row"><a class="js-no-back" href="/gt-steps">← 版本列表</a></div>
      <h1>决策点 · <span class="mono">{_esc(version_id)}</span>{cur_badge}</h1>
    </div>
  </div>

  <div class="gs-toolbar">
    <div class="gs-metrics">
      <div class="gs-metric"><span class="k">手数</span><span class="v">{hand_n}</span></div>
      <div class="gs-metric"><span class="k">有正确值</span><span class="v">{with_gt}</span></div>
      <div class="gs-metric"><span class="k">决策点</span><span class="v">{step_n}</span></div>
    </div>
    <div class="gs-filters">
      <input id="q" type="search" placeholder="手牌 / 底牌 / 行动…" autocomplete="off"/>
      <div class="street-pills" role="group" aria-label="按街筛选">
        <button type="button" class="street-pill is-on" data-street="">全部</button>
        <button type="button" class="street-pill" data-street="preflop">翻前</button>
        <button type="button" class="street-pill" data-street="flop">翻牌</button>
        <button type="button" class="street-pill" data-street="turn">转牌</button>
        <button type="button" class="street-pill" data-street="river">河牌</button>
      </div>
      <span class="gs-filter-hint" id="filter-hint"></span>
    </div>
  </div>

  <div class="hand-list" id="hand-list">
{body_html}
  </div>
{_shell_close()}
<script>
{_JS_COMMON}
(function() {{
  var q = document.getElementById('q');
  var hint = document.getElementById('filter-hint');
  var street = '';
  var blocks = Array.prototype.slice.call(document.querySelectorAll('.hand-block'));
  var pills = Array.prototype.slice.call(document.querySelectorAll('.street-pill'));

  function apply() {{
    var qq = (q.value || '').trim().toLowerCase();
    var shownHands = 0, shownSteps = 0, totalSteps = 0;
    blocks.forEach(function(block) {{
      var rows = Array.prototype.slice.call(block.querySelectorAll('.step-row'));
      var handHit = 0;
      rows.forEach(function(row) {{
        totalSteps++;
        var text = ((row.getAttribute('data-search') || '') + ' ' + (block.getAttribute('data-search') || '')).toLowerCase();
        var okQ = !qq || text.indexOf(qq) >= 0;
        var okS = !street || (row.getAttribute('data-street') || '') === street;
        var ok = okQ && okS;
        row.classList.toggle('is-hidden', !ok);
        if (ok) {{ handHit++; shownSteps++; }}
      }});
      var showBlock = handHit > 0;
      block.classList.toggle('is-hidden', !showBlock);
      if (showBlock) shownHands++;
    }});
    if (qq || street) {{
      hint.textContent = shownHands + ' 手 · ' + shownSteps + ' 点';
    }} else {{
      hint.textContent = '';
    }}
  }}

  q.addEventListener('input', apply);
  pills.forEach(function(btn) {{
    btn.addEventListener('click', function() {{
      street = btn.getAttribute('data-street') || '';
      pills.forEach(function(p) {{ p.classList.toggle('is-on', p === btn); }});
      apply();
    }});
  }});
}})();
</script>
</body>
</html>"""


def render_gt_step_detail_page(
    *,
    version_id: str,
    hand_uid: str,
    nth: int,
    detail: dict[str, Any],
) -> str:
    step = detail.get("step") or {}
    siblings = detail.get("siblings") or []
    hole_html = _cards_html(detail.get("hole_key"))
    street = str(step.get("decision_street") or "—").upper()
    label = _esc(step.get("next_p0_label") or "—")
    alen = step.get("truncated_action_len")
    oalen = step.get("original_action_len")
    board_html = _cards_html(step.get("community_cards"))
    if not _parse_cards(step.get("community_cards")):
        board_html = '<span class="cards-empty">翻前 / 无公牌</span>'
    req = step.get("request")
    req_json = json.dumps(req, ensure_ascii=False, indent=2) if req is not None else "null"

    sib_links = []
    for s in siblings:
        sn = int(s.get("nth") or 0)
        cls = " is-active" if sn == nth else ""
        st = str(s.get("decision_street") or "?").upper()
        href = f"/gt-steps/{_esc(version_id)}/{_esc(hand_uid)}/{sn}"
        sib_links.append(
            f'<a class="sib{cls}" href="{href}">'
            f'<span class="sib-nth">P0#{sn}</span>'
            f'<span class="street-tag street-{_esc(st.lower())}">{_esc(st)}</span>'
            f'<span class="sib-act">{_esc(s.get("next_p0_label") or "")}</span>'
            f"</a>"
        )
    sibs_html = "\n".join(sib_links) if sib_links else '<p class="dim">无</p>'
    next_raw = json.dumps(step.get("next_p0_action") or {}, ensure_ascii=False, indent=2)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>P0#{nth} · {_esc(hand_uid)}</title>
<style>{_CSS}
{_CARDS_CSS}
.gs-page {{ max-width: 1100px; }}
.gs-page h1 {{
  font-size: 26px; letter-spacing: -0.03em;
  font-family: "Songti SC", "Noto Serif SC", "PingFang SC", serif; font-weight: 700;
}}
.gs-page h1 .mono {{
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.72em; font-weight: 700;
}}
.back-row {{ margin-bottom:8px; font-size:13px; }}
.back-row a {{ color:var(--accent); text-decoration:none; font-weight:600; }}
.back-row a:hover {{ text-decoration:underline; }}
.layout {{
  display:grid; grid-template-columns: minmax(200px, 250px) 1fr; gap:14px; align-items:start;
}}
@media (max-width: 900px) {{ .layout {{ grid-template-columns: 1fr; }} }}
.panel-side {{ padding: 14px; }}
.panel-side h2 {{
  font-size:12px; margin:0 0 10px; color:var(--muted); font-weight:700; letter-spacing:.04em;
}}
.sib-list {{ display:flex; flex-direction:column; gap:4px; }}
.sib {{
  display:grid; grid-template-columns: 52px auto 1fr; gap:8px; align-items:center;
  text-decoration:none; color:var(--muted); font-size:12px; font-weight:600;
  padding:9px 10px; border-radius:8px; border:1px solid transparent;
}}
.sib:hover {{ color:var(--ink); background:#f5f5f4; }}
.sib.is-active {{
  color:var(--accent); background:var(--accent-soft); border-color:#99f6e4;
}}
.sib-nth {{
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-weight:800; color:inherit;
}}
.sib-act {{
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
  font-size:11.5px; text-align:right; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
}}
.street-tag {{
  display:inline-block; font-size:10px; font-weight:800; letter-spacing:.04em;
  padding:2px 6px; border-radius:5px; background:#f5f5f4; color:#57534e;
}}
.street-tag.street-preflop {{ background:#ecfdf5; color:#047857; }}
.street-tag.street-flop {{ background:#eff6ff; color:#1d4ed8; }}
.street-tag.street-turn {{ background:#fff7ed; color:#c2410c; }}
.street-tag.street-river {{ background:#faf5ff; color:#7e22ce; }}
.meta-grid {{
  display:grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap:10px; margin-bottom:14px;
}}
.meta-item {{
  background:#fafaf9; border:1px solid #f0eeea; border-radius:10px; padding:10px 12px;
}}
.meta-item .k {{ font-size:11px; font-weight:700; color:var(--muted); margin-bottom:6px; }}
.meta-item .v {{ font-size:14px; font-weight:700; color:var(--ink); word-break:break-word; }}
.meta-item .v.mono {{
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-weight:700; font-size:13px;
}}
.toolbar {{ display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin-bottom:10px; }}
pre.json {{
  margin:0; padding:14px 16px; background:#1c1917; color:#fafaf9;
  border-radius:12px; overflow:auto; max-height:calc(100vh - 300px);
  font-size:12px; line-height:1.45;
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
}}
details.next-act {{ margin-bottom:12px; }}
details.next-act summary {{
  cursor:pointer; font-size:13px; font-weight:700; color:var(--muted);
}}
details.next-act pre {{
  margin-top:8px; padding:10px 12px; background:#faf8f5; border-radius:8px;
  font-size:12px; overflow:auto; max-height:180px;
}}
.copied {{ color:var(--accent); font-size:12px; font-weight:600; margin-left:6px; }}
.dim {{ color:var(--muted); font-size:13px; }}
</style>
</head>
<body>
{_shell_open("gt-steps", wrap_class="wrap gs-page")}
  <div class="topbar">
    <div class="topbar-text">
      <div class="back-row">
        <a class="js-no-back" href="/gt-steps/{_esc(version_id)}">← 返回决策点列表</a>
      </div>
      <h1>P0#{nth} · <span class="mono">{_esc(hand_uid)}</span> <span class="hand-hole">{hole_html}</span></h1>
      <p class="lead"><strong>{label}</strong> · {_esc(street)}</p>
    </div>
  </div>

  <div class="layout">
    <section class="panel panel-side">
      <h2>本手全部 P0</h2>
      <div class="sib-list">{sibs_html}</div>
    </section>

    <section class="panel">
      <div class="meta-grid">
        <div class="meta-item"><div class="k">底牌</div><div class="v">{hole_html}</div></div>
        <div class="meta-item"><div class="k">决策街</div><div class="v">
          <span class="street-tag street-{_esc(street.lower())}">{_esc(street)}</span>
        </div></div>
        <div class="meta-item"><div class="k">裁后行动数</div><div class="v">{_esc(alen)} <span style="color:var(--muted);font-weight:600">/ {_esc(oalen)}</span></div></div>
        <div class="meta-item"><div class="k">公牌</div><div class="v">{board_html}</div></div>
        <div class="meta-item"><div class="k">即将行动</div><div class="v mono">{label}</div></div>
        <div class="meta-item"><div class="k">版本</div><div class="v mono">{_esc(version_id)}</div></div>
      </div>

      <details class="next-act">
        <summary>即将发生的 P0 行动（原始对象，不在请求内）</summary>
        <pre>{_esc(next_raw)}</pre>
      </details>

      <div class="toolbar">
        <button class="btn primary" type="button" id="btn-copy">复制 JSON</button>
        <button class="btn" type="button" id="btn-download">下载</button>
        <span class="copied" id="copy-hint" hidden>已复制</span>
      </div>
      <pre class="json" id="req-json">{_esc(req_json)}</pre>
    </section>
  </div>
{_shell_close()}
<script>
{_JS_COMMON}
(function() {{
  var text = document.getElementById('req-json').textContent;
  var hint = document.getElementById('copy-hint');
  document.getElementById('btn-copy').addEventListener('click', async function() {{
    try {{
      await navigator.clipboard.writeText(text);
      hint.hidden = false;
      setTimeout(function() {{ hint.hidden = true; }}, 1600);
    }} catch (e) {{
      alert('复制失败: ' + e);
    }}
  }});
  document.getElementById('btn-download').addEventListener('click', function() {{
    var blob = new Blob([text], {{ type: 'application/json;charset=utf-8' }});
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = '{_esc(hand_uid)}_P0-{nth}_pre.json';
    a.click();
    URL.revokeObjectURL(a.href);
  }});
}})();
</script>
</body>
</html>"""
