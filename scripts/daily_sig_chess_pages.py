"""信号 → Chess 每日趋势 / 分类统计页。"""

from __future__ import annotations

from typing import Any, Optional
from urllib.parse import quote

from daily_sig_chess import (
    FACET_GROUP_LABEL,
    FACET_TREND,
    facet_group,
    facet_label,
    recompute_day,
)
from manage_page import _CSS, _JS_COMMON, _esc, _shell_close, _shell_open
from step_compare_pages import _cards_html

try:
    from gt_steps.pages import _CARDS_CSS
except Exception:  # pragma: no cover
    _CARDS_CSS = ""


def _pct(v: Any) -> str:
    if v is None or v == "":
        return "—"
    return f"{v}%"


def _num(v: Any) -> str:
    if v is None or v == "":
        return "—"
    return str(v)


def _line_chart(
    *,
    title: str,
    y_label: str,
    labels: list[str],
    series: list[tuple[str, list[Optional[float]], str]],
    y_max: float = 100,
) -> str:
    w, h = 720, 220
    pad_l, pad_r, pad_t, pad_b = 44, 12, 16, 36
    inner_w = w - pad_l - pad_r
    inner_h = h - pad_t - pad_b
    n = max(len(labels), 1)

    def xy(i: int, val: float) -> tuple[float, float]:
        x = pad_l + (inner_w * i / max(n - 1, 1) if n > 1 else inner_w / 2)
        y = pad_t + inner_h * (1 - (val / y_max if y_max else 0))
        return x, y

    grid = []
    for tick in (0, 25, 50, 75, 100):
        if tick > y_max:
            continue
        _x, y = xy(0, tick)
        grid.append(
            f'<line class="g" x1="{pad_l}" y1="{y:.1f}" x2="{w - pad_r}" y2="{y:.1f}"/>'
            f'<text class="gt" x="{pad_l - 6}" y="{y + 3:.1f}">{tick}</text>'
        )
    xlabels = []
    step = 1 if n <= 8 else max(1, n // 7)
    for i, lab in enumerate(labels):
        if i % step != 0 and i != n - 1:
            continue
        x, _y = xy(i, 0)
        short = lab[5:] if len(lab) >= 10 else lab
        xlabels.append(
            f'<text class="xl" x="{x:.1f}" y="{h - 8}">{_esc(short)}</text>'
        )

    paths = []
    legend = []
    for name, values, cls in series:
        segs: list[list[str]] = []
        cur: list[str] = []
        dots = []
        for i, v in enumerate(values):
            if v is None:
                if cur:
                    segs.append(cur)
                    cur = []
                continue
            x, y = xy(i, max(0, min(float(y_max), float(v))))
            cur.append(f"{x:.1f},{y:.1f}")
            dots.append(f'<circle class="{_esc(cls)}" cx="{x:.1f}" cy="{y:.1f}" r="3"/>')
        if cur:
            segs.append(cur)
        for seg in segs:
            if len(seg) == 1:
                continue
            paths.append(f'<polyline class="ln {_esc(cls)}" points="{" ".join(seg)}"/>')
        paths.extend(dots)
        legend.append(
            f'<span class="lg {_esc(cls)}"><i></i>{_esc(name)}</span>'
        )
    return f"""
<figure class="chart">
  <figcaption>{_esc(title)} <span class="unit">{_esc(y_label)}</span></figcaption>
  <svg viewBox="0 0 {w} {h}" role="img" aria-label="{_esc(title)}">
    {"".join(grid)}
    {"".join(paths)}
    {"".join(xlabels)}
  </svg>
  <div class="chart-lg">{"".join(legend)}</div>
</figure>"""


_TREND_CSS = """
.tr-page { max-width: 1120px; }
.tr-page h1 {
  font-size: 24px; letter-spacing: -0.03em;
  font-family: "Songti SC", "Noto Serif SC", "PingFang SC", serif; font-weight: 700;
}
.back-row { margin-bottom: 8px; font-size: 13px; }
.back-row a { color: var(--accent); text-decoration: none; font-weight: 600; }
.gs-metrics { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:16px; }
.gs-metric {
  display:flex; flex-direction:column; gap:2px; min-width:72px; padding:8px 12px;
  background:#fff; border:1px solid var(--line); border-radius:10px;
}
.gs-metric .k { font-size:11px; font-weight:700; color:var(--muted); }
.gs-metric .v { font-size:18px; font-weight:800; font-variant-numeric:tabular-nums; }
.gs-metric .v small { display:inline; margin-left:8px; font-size:13px; font-weight:700; color:var(--muted); }
.gs-metric.is-key { border-color:#fecaca; background:#fff7f7; }
.gs-metric.is-key .v { color:#b91c1c; }
.tot-metrics { margin-bottom:12px; }
table.tr-tbl tfoot th { text-align:left; padding:10px 12px; background:#f5f5f4;
  font-weight:800; font-size:12.5px; color:var(--ink); border-top:1px solid var(--line); }
table.tr-tbl tfoot th.num { font-variant-numeric:tabular-nums; font-family:ui-monospace,Menlo,monospace; }
.tr-run {
  display:flex; flex-wrap:wrap; align-items:flex-end; gap:10px 12px;
  padding:14px 16px; margin-bottom:16px;
  background:#fff; border:1px solid var(--line); border-radius:12px;
}
.tr-run .field { display:flex; flex-direction:column; gap:5px; }
.tr-run label { font-size:11px; font-weight:700; color:var(--muted); margin:0; }
.tr-run input[type="date"] {
  font:inherit; font-size:13px; padding:9px 11px;
  border:1px solid var(--line); border-radius:8px; background:#fafaf9;
}
.tr-run .status { font-size:13px; color:var(--muted); min-height:1.2em; }
.tr-run .status.err { color:var(--warn); }
.tr-run .status.ok { color:var(--accent); font-weight:700; }
.chart {
  background:#fff; border:1px solid var(--line); border-radius:12px;
  padding:12px 14px 10px; margin-bottom:14px;
}
.chart figcaption {
  font-size:13px; font-weight:700; margin:0 0 6px;
}
.chart .unit { font-weight:600; color:var(--muted); font-size:12px; margin-left:8px; }
.chart svg { width:100%; height:auto; display:block; }
.chart .g { stroke:#f0eeea; stroke-width:1; }
.chart .gt { fill:#a8a29e; font-size:10px; text-anchor:end;
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace; }
.chart .xl { fill:#78716c; font-size:10px; text-anchor:middle;
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace; }
.chart .ln { fill:none; stroke-width:2; }
.chart .ln.exact, .chart circle.exact { stroke:#0f766e; fill:#0f766e; }
.chart .ln.struct, .chart circle.struct { stroke:#c2410c; fill:#c2410c; }
.chart .ln.act, .chart circle.act { stroke:#1d4ed8; fill:#1d4ed8; }
.chart-lg { display:flex; flex-wrap:wrap; gap:10px 16px; margin-top:6px;
  font-size:12px; font-weight:600; color:var(--muted); }
.chart-lg i { display:inline-block; width:10px; height:3px; margin-right:6px;
  vertical-align:middle; background:currentColor; }
.chart-lg .exact { color:#0f766e; }
.chart-lg .struct { color:#c2410c; }
.chart-lg .act { color:#1d4ed8; }
table.tr-tbl { width:100%; border-collapse:collapse; font-size:13px; background:#fff;
  border:1px solid var(--line); border-radius:12px; overflow:hidden; }
table.tr-tbl th, table.tr-tbl td {
  text-align:left; padding:10px 12px; border-bottom:1px solid #f0ebe3; vertical-align:middle;
}
table.tr-tbl th {
  color:var(--muted); font-weight:700; font-size:11px; letter-spacing:.04em; background:#faf8f5;
}
table.tr-tbl td.num { font-variant-numeric:tabular-nums; font-family:ui-monospace,Menlo,monospace; font-size:12.5px; }
table.tr-tbl td.mono { font-family:ui-monospace,Menlo,monospace; font-size:12.5px; }
table.tr-tbl td.dim { color:var(--muted); }
table.tr-tbl a { color:var(--ink); font-weight:700; text-decoration:none; }
table.tr-tbl a:hover { color:var(--accent); }
table.tr-tbl tbody tr:hover { background:#f8fffd; }
.kind-tags { display:flex; flex-wrap:wrap; gap:4px; }
.kind-tag {
  font-size:10px; font-weight:700; padding:2px 7px; border-radius:999px;
  background:#f5f5f4; color:#57534e;
}
.kind-tag.g-structure { background:#fff7ed; color:#c2410c; }
.kind-tag.g-action { background:#eff6ff; color:#1d4ed8; }
.kind-tag.g-missing { background:#f5f5f4; color:#78716c; }
.kind-tag.g-expected { background:#f5f5f4; color:#57534e; }
.kind-tag.g-blinds { background:#fff7ed; color:#b45309; }
.kind-tag.g-board { background:#fefce8; color:#a16207; }
.kind-tag.g-seat { background:#fff1f2; color:#be123c; }
.kind-tag.g-action_map, .kind-tag.g-action_rewrite { background:#eff6ff; color:#1d4ed8; }
.kind-tag.g-action_miss, .kind-tag.g-action_type_miss { background:#f5f3ff; color:#6d28d9; }
.kind-tag.g-action_extra { background:#ecfeff; color:#0e7490; }
.heat-sec {
  background:#fff; border:1px solid var(--line); border-radius:12px;
  margin-bottom:14px; overflow:hidden;
}
.heat-sec > .sec-h,
.bar-sec > .sec-h {
  display:flex; align-items:baseline; justify-content:space-between; gap:12px;
  padding:10px 14px; border-bottom:1px solid var(--line);
}
.heat-sec > .sec-h h2,
.bar-sec > .sec-h h2 { margin:0; font-size:13px; font-weight:800; letter-spacing:.02em; }
.heat-sec > .sec-h .sub,
.bar-sec > .sec-h .sub { font-size:12px; color:var(--muted); font-weight:600; }
.heat-sec.tone-structure { border-left:3px solid #b45309; }
.heat-sec.tone-expected { border-left:3px solid #a8a29e; }
.heat-sec.tone-action { border-left:3px solid #0e7490; }
.heat-sec.tone-map { border-left:3px solid #1d4ed8; }
.heat-sec.tone-miss { border-left:3px solid #6d28d9; }
.heat-sec.tone-muted { border-left:3px solid #d6d3d1; }
.heat-sec.tone-structure > .sec-h,
.bar-sec.tone-structure > .sec-h { background:#fff7ed; }
.heat-sec.tone-expected > .sec-h,
.bar-sec.tone-expected > .sec-h { background:#fafaf9; color:#57534e; }
.heat-sec.tone-action > .sec-h,
.bar-sec.tone-action > .sec-h { background:#ecfeff; }
.heat-sec.tone-map > .sec-h,
.bar-sec.tone-map > .sec-h { background:#eff6ff; }
.heat-sec.tone-miss > .sec-h,
.bar-sec.tone-miss > .sec-h { background:#f5f3ff; }
.heat-sec.tone-muted > .sec-h,
.bar-sec.tone-muted > .sec-h { background:#fafaf9; }
.heat { width:100%; border-collapse:separate; border-spacing:0; background:#fff;
  border:none; border-radius:0; overflow:hidden; margin:0;
  font-size:12.5px; }
.heat th, .heat td { padding:7px 10px; border-bottom:1px solid #f0ebe3; }
.heat th { font-size:11px; color:var(--muted); font-weight:700; background:#fff;
  text-align:center; }
.heat th.lab { text-align:left; }
.heat td.lab { font-weight:650; white-space:nowrap; padding-left:16px; }
.heat td.h { text-align:center; font-variant-numeric:tabular-nums;
  font-family:ui-monospace,Menlo,monospace; font-size:12px; }
.heat td.h.is-hot { font-weight:800; }
.heat tr.grp td { font-size:11px; font-weight:700; letter-spacing:.04em;
  color:var(--muted); background:#fafaf9; padding:6px 14px; }
.heat tr.rare td.lab { font-weight:500; color:#a8a29e; padding-left:28px; }
.heat tr.rare td.h { font-weight:500; color:#a8a29e; }
.heat a { color:inherit; text-decoration:none; font-weight:700; }
.heat a:hover { color:var(--accent); }
.bar-list { margin-bottom:16px; }
.bar-sec { background:#fff; border:1px solid var(--line); border-radius:12px;
  margin-bottom:12px; overflow:hidden; }
.bar-sec.tone-structure { border-left:3px solid #b45309; }
.bar-sec.tone-expected { border-left:3px solid #a8a29e; }
.bar-sec.tone-action { border-left:3px solid #0e7490; }
.bar-sec.tone-map { border-left:3px solid #1d4ed8; }
.bar-sec.tone-miss { border-left:3px solid #6d28d9; }
.bar-sec.tone-muted { border-left:3px solid #d6d3d1; }
.bar-row { display:grid; grid-template-columns:168px 1fr 88px minmax(120px,1.2fr);
  gap:10px; align-items:center; padding:8px 12px; border-bottom:1px solid #f0ebe3;
  text-decoration:none; color:inherit; cursor:pointer; }
.bar-row:hover { background:#f8fffd; }
.bar-row.is-on { background:var(--accent-soft); }
.bar-row .name { font-size:13px; font-weight:700; }
.bar-row .track { height:8px; background:#f4f1ec; border-radius:99px; overflow:hidden; }
.bar-row .track > i { display:block; height:100%; background:#c2410c; border-radius:99px; }
.bar-row.g-action_rewrite .track > i,
.bar-row.g-action_map .track > i { background:#1d4ed8; }
.bar-row.g-action_miss .track > i,
.bar-row.g-action_type_miss .track > i { background:#7c3aed; }
.bar-row.g-expected .track > i { background:#a8a29e; }
.bar-row.g-blinds .track > i { background:#b45309; }
.bar-row .pct { font-variant-numeric:tabular-nums; font-family:ui-monospace,Menlo,monospace;
  font-size:12px; font-weight:700; text-align:right; }
.bar-row .ex { font-size:11px; color:var(--muted); overflow:hidden; text-overflow:ellipsis;
  white-space:nowrap; }
.bar-grp { padding:8px 12px 4px; font-size:11px; font-weight:700; color:var(--muted);
  letter-spacing:.04em; background:#fafaf9; border-bottom:1px solid #f0ebe3; }
.note { font-size:13px; color:var(--muted); margin:0 0 14px; line-height:1.55; }
.gs-empty { text-align:center; color:var(--muted); padding:40px; background:#fff;
  border:1px solid var(--line); border-radius:12px; }
.filter-row { display:flex; flex-wrap:wrap; gap:6px; margin:0 0 12px; }
.filter-row a {
  font-size:12px; font-weight:700; padding:5px 10px; border-radius:8px;
  text-decoration:none; color:var(--muted); border:1px solid var(--line); background:#fff;
}
.filter-row a.is-on { color:var(--accent); background:var(--accent-soft); border-color:#99f6e4; }
.st-tag {
  display:inline-block; font-size:11px; font-weight:800; padding:2px 8px;
  border-radius:999px; letter-spacing:.02em;
}
.st-tag.exact { background:#ccfbf1; color:#0f766e; }
.st-tag.diff { background:#ffedd5; color:#c2410c; }
.st-tag.incomp { background:#f5f5f4; color:#78716c; }
.pager {
  display:flex; align-items:center; flex-wrap:wrap; justify-content:flex-end; gap:8px;
  margin:8px 0 10px; font-size:13px;
}
.pager a, .pager span.pg {
  padding:5px 10px; border-radius:8px; border:1px solid var(--line);
  background:#fff; color:var(--ink); text-decoration:none; font-weight:700;
}
.pager a:hover { color:var(--accent); }
.pager span.pg.is-off { color:#a8a29e; font-weight:600; }
.pager .pg-info { color:var(--muted); font-variant-numeric:tabular-nums; margin-right:auto; }
.pager .ps { display:flex; align-items:center; gap:6px; color:var(--muted); font-weight:600; }
.pager .ps select {
  font:inherit; font-size:13px; font-weight:700; color:var(--ink);
  padding:5px 8px; border:1px solid var(--line); border-radius:8px; background:#fff;
}
"""


HEAT_SECTIONS: list[dict[str, Any]] = [
    {
        "id": "structure",
        "title": "牌局结构",
        "hint": "大小盲、公牌、人数 / 位置",
        "tone": "structure",
        "rgb": (180, 83, 9),
        "groups": ("blinds", "board", "seat"),
    },
    {
        "id": "expected",
        "title": "已知口径",
        "hint": "几乎天天有，不当成趋势信号",
        "tone": "expected",
        "rgb": (120, 113, 108),
        "groups": ("expected",),
    },
    {
        "id": "action",
        "title": "行动条数 / 金额",
        "hint": "漏了、多了、金额单位或数值",
        "tone": "action",
        "rgb": (14, 116, 144),
        "groups": ("action_rewrite", "action_miss", "action_extra"),
    },
    {
        "id": "map",
        "title": "行动类型对不上",
        "hint": "同一条行动，信号和 Chess 写成了不同动作",
        "tone": "map",
        "rgb": (29, 78, 216),
        "groups": ("action_map",),
        "split_rare": True,
    },
    {
        "id": "miss",
        "title": "漏了哪种行动",
        "hint": "信号有、Chess 没有的动作类型",
        "tone": "miss",
        "rgb": (109, 40, 217),
        "groups": ("action_type_miss",),
        "split_rare": True,
    },
    {
        "id": "missing",
        "title": "缺报文",
        "hint": "",
        "tone": "muted",
        "rgb": (120, 113, 108),
        "groups": ("missing",),
    },
]
RARE_MAX_PCT = 8.0


def _heat_style(pct: Optional[float], rgb: tuple[int, int, int] = (194, 65, 12)) -> str:
    if pct is None:
        return ""
    a = max(0.0, min(1.0, float(pct) / 100.0)) * 0.55
    r, g, b = rgb
    return f"background:rgba({r},{g},{b},{a:.2f})"


def _facet_ids_for_trend(docs_by_day: dict[str, dict], days: list[str]) -> list[str]:
    extra: set[str] = set()
    for d in days:
        doc = docs_by_day.get(d) or {}
        for fid in (doc.get("facets") or {}):
            extra.add(str(fid))
    out = [fid for fid in FACET_TREND]
    for fid in sorted(extra):
        if fid not in out and (
            fid.startswith("act_map:") or fid.startswith("act_miss_type:")
        ):
            out.append(fid)
    return out


def _max_facet_pct(
    fid: str, days: list[str], docs_by_day: dict[str, dict]
) -> float:
    mx = 0.0
    for d in days:
        info = ((docs_by_day.get(d) or {}).get("facets") or {}).get(fid) or {}
        pct = info.get("hero_pct")
        if pct is not None:
            mx = max(mx, float(pct))
    return mx


def _heat_row(
    *,
    fid: str,
    days: list[str],
    docs_by_day: dict[str, dict],
    rgb: tuple[int, int, int],
    rare: bool = False,
) -> Optional[str]:
    cells = []
    any_hit = False
    for d in days:
        info = ((docs_by_day.get(d) or {}).get("facets") or {}).get(fid) or {}
        pct = info.get("hero_pct")
        if pct is not None:
            any_hit = True
        if pct is None:
            cells.append('<td class="h dim">—</td>')
        else:
            hot = " is-hot" if float(pct) >= 40 else ""
            href = f"/discover/trend/{_esc(d)}?facet={quote(fid)}"
            cells.append(
                f'<td class="h{hot}" style="{_heat_style(pct, rgb)}">'
                f'<a href="{href}">{_esc(_pct(pct))}</a></td>'
            )
    if not any_hit:
        return None
    cls = ' class="rare"' if rare else ""
    return (
        f"<tr{cls}><td class=\"lab\">{_esc(facet_label(fid))}</td>"
        + "".join(cells)
        + "</tr>"
    )


def _heatmap_html(
    *,
    days: list[str],
    docs_by_day: dict[str, dict],
    facet_ids: list[str],
) -> str:
    if not days:
        return ""
    by_g: dict[str, list[str]] = {}
    for fid in facet_ids:
        by_g.setdefault(facet_group(fid), []).append(fid)

    head = '<th class="lab">细项</th>' + "".join(
        f'<th><a href="/discover/trend/{_esc(d)}">{_esc(d[5:] if len(d) >= 10 else d)}</a></th>'
        for d in days
    )
    sections = []
    used: set[str] = set()
    for spec in HEAT_SECTIONS:
        rgb = spec["rgb"]
        body: list[str] = []
        for g in spec["groups"]:
            ids = list(by_g.get(g) or [])
            if not ids:
                continue
            if spec.get("split_rare"):
                main, rare = [], []
                for fid in ids:
                    if _max_facet_pct(fid, days, docs_by_day) >= RARE_MAX_PCT:
                        main.append(fid)
                    else:
                        rare.append(fid)
            else:
                main, rare = ids, []
            if len(spec["groups"]) > 1:
                body.append(
                    f'<tr class="grp"><td colspan="{len(days) + 1}">'
                    f"{_esc(FACET_GROUP_LABEL.get(g) or g)}</td></tr>"
                )
            for fid in main:
                row = _heat_row(
                    fid=fid, days=days, docs_by_day=docs_by_day, rgb=rgb
                )
                if row:
                    body.append(row)
                    used.add(fid)
            if rare:
                body.append(
                    f'<tr class="grp"><td colspan="{len(days) + 1}">'
                    f"其他（各天都 &lt; {int(RARE_MAX_PCT)}%）</td></tr>"
                )
                for fid in rare:
                    row = _heat_row(
                        fid=fid,
                        days=days,
                        docs_by_day=docs_by_day,
                        rgb=rgb,
                        rare=True,
                    )
                    if row:
                        body.append(row)
                        used.add(fid)
        if not body:
            continue
        hint = spec.get("hint") or ""
        sections.append(
            f'<section class="heat-sec tone-{_esc(spec["tone"])}">'
            f'<div class="sec-h"><h2>{_esc(spec["title"])}</h2>'
            f'<span class="sub">{_esc(hint)}</span></div>'
            f'<table class="heat"><thead><tr>{head}</tr></thead>'
            f"<tbody>{''.join(body)}</tbody></table></section>"
        )

    leftover = [fid for fid in facet_ids if fid not in used]
    extra_body = []
    for fid in leftover:
        row = _heat_row(
            fid=fid,
            days=days,
            docs_by_day=docs_by_day,
            rgb=(120, 113, 108),
        )
        if row:
            extra_body.append(row)
    if extra_body:
        sections.append(
            f'<section class="heat-sec tone-muted">'
            f'<div class="sec-h"><h2>其他</h2></div>'
            f'<table class="heat"><thead><tr>{head}</tr></thead>'
            f"<tbody>{''.join(extra_body)}</tbody></table></section>"
        )
    if not sections:
        return '<p class="note">日账里还没有细项。刷新本页前请确认已回填 discover_live。</p>'
    return "".join(sections)


def render_trend_page(*, days: list[str], docs_by_day: dict[str, dict]) -> str:
    data_days = [
        d
        for d in days
        if (docs_by_day.get(d) or {}).get("hand_n")
    ]
    heat = _heatmap_html(
        days=data_days,
        docs_by_day=docs_by_day,
        facet_ids=_facet_ids_for_trend(docs_by_day, data_days),
    )
    tot_hands = 0
    tot_hero = 0
    tot_comp = 0
    tot_exact = 0
    tot_match_hands = 0
    tot_incomp_hands = 0
    for d in data_days:
        doc = docs_by_day.get(d) or {}
        m = doc.get("metrics") or {}
        tot_hands += int(doc.get("hand_n") or 0)
        tot_hero += int(m.get("hero_n") or 0)
        tot_comp += int(m.get("comparable_n") or 0)
        tot_exact += int(m.get("exact_n") or 0)
        for h in doc.get("hands") or []:
            if not isinstance(h, dict):
                continue
            comp = int(h.get("comparable_n") or 0)
            exact = int(h.get("exact_n") or 0)
            if comp <= 0:
                tot_incomp_hands += 1
            elif exact == comp and int(h.get("diff_n") or 0) == 0:
                tot_match_hands += 1
    tot_exact_pct = round(100.0 * tot_exact / tot_comp, 1) if tot_comp else None
    rows_html = []
    for d in days:
        doc = docs_by_day.get(d)
        m = (doc.get("metrics") if doc else None) or {}
        if not doc:
            rows_html.append(
                f'<tr><td class="mono">{_esc(d)}</td>'
                f'<td colspan="5" class="dim">未跑批</td>'
                f'<td><a href="/discover/trend/{_esc(d)}">打开</a></td></tr>'
            )
            continue
        facets = doc.get("facets") or {}
        ranked = sorted(
            (
                (fid, info)
                for fid, info in facets.items()
                if isinstance(info, dict) and facet_group(fid) != "expected"
            ),
            key=lambda kv: float(kv[1].get("hero_pct") or 0),
            reverse=True,
        )[:3]
        top = "、".join(
            f"{facet_label(fid)} {_pct(info.get('hero_pct'))}"
            for fid, info in ranked
        ) or "—"
        href = f"/discover/trend/{_esc(d)}"
        rows_html.append(
            "<tr>"
            f'<td class="mono"><a href="{href}">{_esc(d)}</a></td>'
            f'<td class="num">{_esc(_num(doc.get("hand_n")))}</td>'
            f'<td class="num">{_esc(_num(m.get("hero_n")))}</td>'
            f'<td class="num">{_esc(_num(m.get("comparable_n")))}</td>'
            f'<td>{_esc(top)}</td>'
            f'<td class="dim">{_esc(doc.get("window_start") or "—")} ~ '
            f'{_esc((doc.get("window_end") or "")[11:] or "")}</td>'
            "</tr>"
        )
    today = days[-1] if days else ""
    body_rows = "\n".join(rows_html) if rows_html else (
        '<tr><td colspan="6" class="dim" style="text-align:center;padding:28px">还没有日账。</td></tr>'
    )
    foot = ""
    if tot_hands:
        foot = (
            "<tfoot><tr>"
            f'<th>已跑合计 · {len(data_days)} 天</th>'
            f'<th class="num">{_esc(_num(tot_hands))}</th>'
            f'<th class="num">{_esc(_num(tot_hero))}</th>'
            f'<th class="num">{_esc(_num(tot_comp))}</th>'
            f'<th>完全一致 {_esc(_num(tot_exact))} / {_esc(_pct(tot_exact_pct))}'
            f' · 整手全对 {_esc(_num(tot_match_hands))}'
            f' · 无可比 {_esc(_num(tot_incomp_hands))}</th>'
            f"<th></th>"
            "</tr></tfoot>"
        )
    totals = ""
    if tot_hands:
        totals = f"""
  <div class="gs-metrics tot-metrics">
    <div class="gs-metric"><span class="k">已跑天数</span><span class="v">{len(data_days)}</span></div>
    <div class="gs-metric"><span class="k">手数合计</span><span class="v">{_esc(_num(tot_hands))}</span></div>
    <div class="gs-metric"><span class="k">hero 合计</span><span class="v">{_esc(_num(tot_hero))}</span></div>
    <div class="gs-metric"><span class="k">可比 hero</span><span class="v">{_esc(_num(tot_comp))}</span></div>
    <div class="gs-metric is-key"><span class="k">完全一致 hero</span><span class="v">{_esc(_num(tot_exact))}<small>{_esc(_pct(tot_exact_pct))}</small></span></div>
    <div class="gs-metric is-key"><span class="k">整手全对</span><span class="v">{_esc(_num(tot_match_hands))}</span></div>
    <div class="gs-metric"><span class="k">无可比手数</span><span class="v">{_esc(_num(tot_incomp_hands))}</span></div>
  </div>"""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>信号→Chess 每日细项</title>
<style>{_CSS}
{_TREND_CSS}
</style>
</head>
<body>
{_shell_open("trend", wrap_class="wrap tr-page")}
  <div class="topbar">
    <div class="topbar-text">
      <div class="back-row"><a class="js-no-back" href="/discover">← 组合发现</a></div>
      <h1>信号 → Chess · 细项对照</h1>
      <p class="lead">同一 hero 决策：左边信号还原的牌局，右边 Chess fusionCorrectedData。格子是该细项占可比 hero 的比例。点格子进当天并筛这一项。</p>
    </div>
  </div>
{totals}
  <p class="note">完全一致 = 这一次 hero 上盲注、人数、位置、筹码、公牌、行动全部对上。整手全对 = 该手每一次可比 hero 都完全一致。无可比 = 没拉到 hero_action 或没有 Chess，不能算对上，也不能算差异。</p>
  <div class="tr-run">
    <div class="field">
      <label for="day">跑批日期</label>
      <input id="day" type="date" value="{_esc(today)}"/>
    </div>
    <button class="btn primary" type="button" id="btn-run">跑这一天</button>
    <span class="status" id="st" aria-live="polite"></span>
  </div>
{heat}
  <table class="tr-tbl">
    <thead>
      <tr>
        <th>日期</th><th>手数</th><th>hero</th><th>可比</th>
        <th>除口径外最高的三项</th><th>窗口</th>
      </tr>
    </thead>
    <tbody>
{body_rows}
    </tbody>
{foot}
  </table>
{_shell_close()}
<script>
{_JS_COMMON}
(function() {{
  var btn = document.getElementById('btn-run');
  var st = document.getElementById('st');
  var timer = null;
  function setSt(t, kind) {{
    st.textContent = t || '';
    st.className = 'status' + (kind ? ' ' + kind : '');
  }}
  async function poll(id) {{
    var res = await fetch('/api/daily-sig-chess-job/' + encodeURIComponent(id));
    var data = await res.json().catch(function() {{ return {{}}; }});
    if (!data || !data.ok) throw new Error((data && data.error) || '查询任务失败');
    var j = data.job || {{}};
    var tot = j.total || 0;
    var done = j.done || 0;
    var msg = (tot ? (done + ' / ' + tot) : '启动中') + (j.current ? (' · ' + j.current) : '');
    if (j.status === 'running') {{
      setSt(msg);
      timer = setTimeout(function() {{ poll(id); }}, 1500);
      return;
    }}
    if (j.status === 'done') {{
      setSt('完成 · 成功 ' + (j.ok_n || 0) + ' · 失败 ' + (j.err_n || 0), 'ok');
      btn.disabled = false;
      location.href = '/discover/trend/' + encodeURIComponent(j.date || '');
      return;
    }}
    btn.disabled = false;
    setSt(j.error || '跑批失败', 'err');
  }}
  btn.addEventListener('click', async function() {{
    var day = document.getElementById('day').value;
    if (!day) {{ setSt('请选择日期', 'err'); return; }}
    btn.disabled = true;
    setSt('正在提交…');
    try {{
      var data = await postJson('/api/daily-sig-chess-run', {{ date: day }});
      setSt('已开始');
      await poll(data.job_id || (data.job && data.job.id) || '');
    }} catch (e) {{
      btn.disabled = false;
      setSt(String(e.message || e), 'err');
    }}
  }});
}})();
</script>
</body>
</html>"""


def _hand_status(h: dict[str, Any]) -> str:
    comp = int(h.get("comparable_n") or 0)
    exact = int(h.get("exact_n") or 0)
    if comp <= 0:
        return "incomp"
    if exact == comp and int(h.get("diff_n") or 0) == 0:
        return "exact"
    return "diff"


def _day_url(
    day: str,
    *,
    facet: str = "",
    status: str = "",
    page: int = 1,
    page_size: int = 10,
) -> str:
    q: list[str] = []
    if facet:
        q.append("facet=" + quote(facet))
    if status and status not in ("", "all"):
        q.append("status=" + quote(status))
    ps = _norm_page_size(page_size)
    if ps != DEFAULT_PAGE_SIZE:
        q.append("ps=" + str(ps))
    if int(page or 1) > 1:
        q.append("page=" + str(int(page)))
    path = "/discover/trend/" + quote(day)
    url = path + (("?" + "&".join(q)) if q else "")
    return url + "#hands"


PAGE_SIZES = (10, 20, 50, 100)
DEFAULT_PAGE_SIZE = 10
STATUS_LABEL = {
    "all": "全部",
    "diff": "有差异",
    "incomp": "无可比",
    "exact": "全对",
}


def _norm_page_size(v: Any) -> int:
    try:
        n = int(v)
    except (TypeError, ValueError):
        return DEFAULT_PAGE_SIZE
    return n if n in PAGE_SIZES else DEFAULT_PAGE_SIZE


def _facet_tags(facets: list[str]) -> str:
    bits = []
    for fid in facets[:8]:
        g = facet_group(fid)
        bits.append(
            f'<span class="kind-tag g-{_esc(g)}">{_esc(facet_label(fid))}</span>'
        )
    return '<span class="kind-tags">' + "".join(bits) + "</span>" if bits else "—"


def render_day_page(
    *,
    day: str,
    doc: Optional[dict[str, Any]],
    kind: str = "",
    facet: str = "",
    status: str = "",
    page: int = 1,
    page_size: Any = 10,
) -> str:
    kind = str(kind or "").strip()
    facet = str(facet or "").strip() or kind
    status = str(status or "").strip() or "all"
    if status not in STATUS_LABEL:
        status = "all"
    page_size = _norm_page_size(page_size)
    try:
        page = max(1, int(page or 1))
    except (TypeError, ValueError):
        page = 1
    if doc:
        doc = recompute_day(doc)
    m = (doc.get("metrics") if doc else None) or {}
    facets = (doc.get("facets") if doc else None) or {}
    all_hands = [h for h in ((doc or {}).get("hands") or []) if isinstance(h, dict)]
    hands = all_hands
    if facet:
        hands = [h for h in all_hands if facet in (h.get("facets") or [])]

    grouped: list[tuple[str, list[tuple[str, dict]]]] = []
    by_g: dict[str, list[tuple[str, dict]]] = {}
    order_g = [
        "expected",
        "blinds",
        "board",
        "seat",
        "action_map",
        "action_rewrite",
        "action_miss",
        "action_type_miss",
        "action_extra",
        "missing",
        "other",
    ]
    ranked = sorted(
        ((fid, info) for fid, info in facets.items() if isinstance(info, dict)),
        key=lambda kv: (
            order_g.index(facet_group(kv[0]))
            if facet_group(kv[0]) in order_g
            else 99,
            -float(kv[1].get("hero_pct") or 0),
        ),
    )
    for fid, info in ranked:
        by_g.setdefault(facet_group(fid), []).append((fid, info))
    for g in order_g:
        if g in by_g:
            grouped.append((g, by_g[g]))
    for g, items in by_g.items():
        if g not in order_g:
            grouped.append((g, items))

    bar_html = []
    grouped_map = dict(grouped)
    for spec in HEAT_SECTIONS:
        chunk = []
        for g in spec["groups"]:
            items = grouped_map.get(g) or []
            if not items:
                continue
            if len(spec["groups"]) > 1:
                chunk.append(
                    f'<div class="bar-grp">{_esc(FACET_GROUP_LABEL.get(g) or g)}</div>'
                )
            for fid, info in items:
                pct = float(info.get("hero_pct") or 0)
                href = _day_url(day, facet=fid, page_size=page_size)
                on = " is-on" if facet == fid else ""
                chunk.append(
                    f'<a class="bar-row g-{_esc(g)}{on}" href="{href}">'
                    f'<span class="name">{_esc(info.get("label") or facet_label(fid))}</span>'
                    f'<span class="track"><i style="width:{pct:.1f}%"></i></span>'
                    f'<span class="pct">{_esc(_pct(info.get("hero_pct")))} · {_esc(_num(info.get("hero_n")))}</span>'
                    f'<span class="ex" title="{_esc(info.get("example") or "")}">{_esc(info.get("example") or "")}</span>'
                    "</a>"
                )
        if not chunk:
            continue
        hint = spec.get("hint") or ""
        bar_html.append(
            f'<section class="bar-sec tone-{_esc(spec["tone"])}">'
            f'<div class="sec-h"><h2>{_esc(spec["title"])}</h2>'
            f'<span class="sub">{_esc(hint)}</span></div>'
            + "".join(chunk)
            + "</section>"
        )
    leftover_g = [
        g for g, _items in grouped if g not in {x for s in HEAT_SECTIONS for x in s["groups"]}
    ]
    if leftover_g:
        extra = []
        for g in leftover_g:
            extra.append(
                f'<div class="bar-grp">{_esc(FACET_GROUP_LABEL.get(g) or g)}</div>'
            )
            for fid, info in grouped_map[g]:
                pct = float(info.get("hero_pct") or 0)
                href = f"/discover/trend/{_esc(day)}?facet={quote(fid)}"
                on = " is-on" if facet == fid else ""
                extra.append(
                    f'<a class="bar-row g-{_esc(g)}{on}" href="{_day_url(day, facet=fid, page_size=page_size)}">'
                    f'<span class="name">{_esc(info.get("label") or facet_label(fid))}</span>'
                    f'<span class="track"><i style="width:{pct:.1f}%"></i></span>'
                    f'<span class="pct">{_esc(_pct(info.get("hero_pct")))} · {_esc(_num(info.get("hero_n")))}</span>'
                    f'<span class="ex" title="{_esc(info.get("example") or "")}">{_esc(info.get("example") or "")}</span>'
                    "</a>"
                )
        bar_html.append(
            '<section class="bar-sec tone-muted"><div class="sec-h"><h2>其他</h2></div>'
            + "".join(extra)
            + "</section>"
        )
    bars = (
        '<div class="bar-list">' + "".join(bar_html) + "</div>"
        if bar_html
        else '<p class="note">这一天还没有细项（需要从对比明细回填）。</p>'
    )

    n_status = {"all": 0, "diff": 0, "incomp": 0, "exact": 0}
    for h in all_hands:
        st = _hand_status(h)
        n_status[st] = n_status.get(st, 0) + 1
        n_status["all"] += 1
    show = hands
    if status != "all":
        show = [h for h in hands if _hand_status(h) == status]
    total_n = len(show)
    pages = max(1, (total_n + page_size - 1) // page_size) if total_n else 1
    if page > pages:
        page = pages
    start = (page - 1) * page_size
    page_hands = show[start : start + page_size]

    filters = []
    for sid, lab in STATUS_LABEL.items():
        on = " is-on" if (not facet and status == sid) else ""
        filters.append(
            f'<a class="{on}" href="{_day_url(day, status=sid, page_size=page_size)}">'
            f"{_esc(lab)} {n_status.get(sid) or 0}</a>"
        )
    chip_ids: list[str] = []
    if facet:
        chip_ids.append(facet)
    for fid, _info in ranked:
        if fid not in chip_ids:
            chip_ids.append(fid)
        if len(chip_ids) >= 20:
            break
    for fid in chip_ids:
        on = " is-on" if facet == fid else ""
        n_hit = sum(1 for h in all_hands if fid in (h.get("facets") or []))
        filters.append(
            f'<a class="{on}" href="{_day_url(day, facet=fid, page_size=page_size)}">'
            f"{_esc(facet_label(fid))} {n_hit}</a>"
        )

    hand_trs = []
    for h in page_hands:
        cid = str(h.get("compare_id") or "")
        href = f"/discover/compare/{quote(cid)}" if cid else "#"
        oid = str(h.get("open_id") or "")
        oid_s = oid if len(oid) <= 16 else oid[:8] + "…" + oid[-4:]
        hole = _cards_html(h.get("hole_key"))
        st = _hand_status(h)
        st_lab = STATUS_LABEL.get(st) or st
        tags = _facet_tags(list(h.get("facets") or []))
        if st == "exact":
            tags = '<span class="kind-tag g-missing">无差异</span>'
        elif st == "incomp" and not h.get("facets"):
            tags = '<span class="kind-tag g-missing">无可比</span>'
        exs = h.get("facet_examples") if isinstance(h.get("facet_examples"), dict) else {}
        hint = ""
        if facet and exs.get(facet):
            hint = str(exs.get(facet))
        elif st == "incomp":
            hint = "没有 hero_action 或没有 Chess"
        elif st == "exact":
            hint = "信号与 Chess 全部对上"
        else:
            hint = str(h.get("first_issue") or "")[:56]
        hand_trs.append(
            "<tr>"
            f'<td><span class="st-tag {st}">{_esc(st_lab)}</span></td>'
            f'<td class="mono"><a href="{_esc(href)}">{_esc(oid_s)}</a></td>'
            f"<td>{hole}</td>"
            f'<td class="num">{_esc(_num(h.get("hero_n")))}</td>'
            f'<td class="num">{_esc(_num(h.get("diff_n")))}</td>'
            f"<td>{tags}</td>"
            f'<td class="dim">{_esc(hint or "—")}</td>'
            "</tr>"
        )
    if not hand_trs:
        hand_trs.append(
            '<tr><td colspan="7" class="dim" style="text-align:center;padding:28px">这一天还没有手数。</td></tr>'
        )

    pager = ""
    if total_n:
        prev_html = (
            f'<a href="{_day_url(day, facet=facet, status=status, page=page - 1, page_size=page_size)}">上一页</a>'
            if page > 1
            else '<span class="pg is-off">上一页</span>'
        )
        next_html = (
            f'<a href="{_day_url(day, facet=facet, status=status, page=page + 1, page_size=page_size)}">下一页</a>'
            if page < pages
            else '<span class="pg is-off">下一页</span>'
        )
        size_opts = []
        for n in PAGE_SIZES:
            sel = " selected" if n == page_size else ""
            href = _day_url(day, facet=facet, status=status, page=1, page_size=n)
            size_opts.append(
                f'<option value="{_esc(href)}"{sel}>{n} 条</option>'
            )
        size_html = (
            '<label class="ps">每页 '
            f'<select class="js-page-size">{"".join(size_opts)}</select>'
            "</label>"
        )
        pager = (
            f'<div class="pager">'
            f'<span class="pg-info">一行一手 · 本页 {len(page_hands)} / 共 {_esc(_num(total_n))} 手 · '
            f"第 {page} / {pages} 页</span>"
            f"{size_html}"
            f"{prev_html}{next_html}</div>"
        )

    empty_note = ""
    if not doc:
        empty_note = (
            '<div class="gs-empty">这一天还没有日账。到趋势页点「跑这一天」。'
            "</div>"
        )
    facet_note = ""
    if facet:
        facet_note = (
            f'<p class="note">已筛选细项：<b>{_esc(facet_label(facet))}</b>'
            f' · 命中 {_esc(_num(len(hands)))} 手'
            f' · <a href="{_day_url(day, page_size=page_size)}">看全部手数</a></p>'
        )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{_esc(day)} · 信号→Chess 细项</title>
<style>{_CSS}
{_CARDS_CSS}
{_TREND_CSS}
</style>
</head>
<body>
{_shell_open("trend", wrap_class="wrap tr-page")}
  <div class="topbar">
    <div class="topbar-text">
      <div class="back-row"><a class="js-no-back" href="/discover/trend">← 细项对照</a></div>
      <h1>{_esc(day)}</h1>
      <p class="lead">上面是细项占比。下面每一行是 <b>一手牌</b>（同一 openId + 底牌）；hero 列是这手里的决策次数。用下拉选择每页 10 / 20 / 50 / 100 条。</p>
    </div>
  </div>
  <div class="gs-metrics">
    <div class="gs-metric"><span class="k">手数</span><span class="v">{_esc(_num((doc or {}).get("hand_n") or 0))}</span></div>
    <div class="gs-metric"><span class="k">可比 hero</span><span class="v">{_esc(_num(m.get("comparable_n")))}</span></div>
    <div class="gs-metric"><span class="k">窗口</span><span class="v" style="font-size:13px">{_esc(((doc or {}).get("window_start") or "")[11:] or "—")}</span></div>
  </div>
{empty_note}
{facet_note}
{bars}
  <h2 id="hands" style="font-size:15px;margin:8px 0 10px">当天手数（一行一手）</h2>
  <div class="filter-row">{"".join(filters)}</div>
{pager}
  <table class="tr-tbl">
    <thead>
      <tr><th>标识</th><th>OpenID</th><th>底牌</th><th>hero次数</th><th>差异条数</th><th>细项</th><th>例子</th></tr>
    </thead>
    <tbody>
{"".join(hand_trs)}
    </tbody>
  </table>
{pager}
<script>
document.querySelectorAll('.js-page-size').forEach(function(el) {{
  el.addEventListener('change', function() {{
    if (this.value) location.href = this.value;
  }});
}});
</script>
{_shell_close()}
</body>
</html>"""
