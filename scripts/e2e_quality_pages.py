"""e2e-quality 静态站：上传记录列表 + 详情两 Tab（匹配率 / 覆盖分布）。"""

from __future__ import annotations

import json
import shutil
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shuzi_field_schema import CATS, PAIRS  # noqa: E402

STREETS = ["翻前", "翻牌", "转牌", "河牌"]
CAT_HINT = {
    "卡牌": "手牌、公牌",
    "文字": "昵称、动作、comment、位置",
    "图像": "dealer、status、头像",
    "数字": "筹码、下注、座位、底池、盲注",
}

COMMON_CSS = """
:root {
  --bg:#f3f4f6; --panel:#fff; --ink:#111827; --muted:#6b7280; --line:#e5e7eb;
  --accent:#0f766e; --fill:#0f766e; --zero:#f5f5f4; --note:#fffbeb; --gap:#ffedd5;
  --side:#111827; --pending:#b45309;
}
* { box-sizing:border-box; }
html,body { margin:0; min-height:100%; }
body { font-family:"IBM Plex Sans","PingFang SC","Noto Sans SC",sans-serif;
  background:var(--bg); color:var(--ink); line-height:1.45; }
a { color:var(--accent); }
.app { display:grid; grid-template-columns:232px 1fr; min-height:100vh; }
.side { background:var(--side); color:#e5e7eb; padding:20px 14px 28px; position:sticky; top:0; height:100vh; }
.side .kicker { font-size:11px; letter-spacing:.14em; text-transform:uppercase; color:#9ca3af; }
.side .brand { font-size:16px; font-weight:700; color:#fff; margin:6px 0 22px; }
.side nav a { display:block; padding:9px 12px; border-radius:8px; color:#d1d5db;
  text-decoration:none; font-size:14px; margin-bottom:4px; }
.side nav a.active { background:var(--accent); color:#fff; }
.main { padding:24px 28px 72px; max-width:1240px; }
.main.is-lookup { max-width:none; padding:20px 22px 48px; }
@media (max-width:900px) {
  .app { grid-template-columns:1fr; }
  .side { position:relative; height:auto; }
}
h1 { font-size:1.45rem; font-weight:700; margin:0 0 6px; }
h2 { margin:0; font-size:1.05rem; }
.sub { color:var(--muted); margin:0 0 18px; max-width:82ch; font-size:14px; }
.page-head { display:flex; flex-wrap:wrap; gap:12px; justify-content:space-between; align-items:center; margin-bottom:16px; }
.page-head h1 { margin:0; }
.btn { display:inline-flex; align-items:center; background:var(--accent); color:#fff !important;
  text-decoration:none; border:none; border-radius:8px; padding:8px 14px; font-weight:650; font-size:13px;
  cursor:pointer; font-family:inherit; }
.btn-ghost { display:inline-flex; align-items:center; border:1px solid var(--line); background:#fff;
  color:var(--ink) !important; text-decoration:none; border-radius:8px; padding:8px 14px; font-size:13px;
  cursor:pointer; font-family:inherit; }
.btn:disabled, .btn-ghost:disabled { opacity:.5; cursor:not-allowed; }
[hidden] { display:none !important; }
.cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:10px; }
.card { background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:12px 14px; }
.card .label { color:var(--muted); font-size:12px; }
.card .value { font-size:22px; font-weight:650; margin-top:4px; font-variant-numeric:tabular-nums; }
.card .hint { font-size:11px; color:var(--muted); margin-top:3px; }
.section { background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:16px 16px 10px; margin-top:18px; }
.section-head { display:flex; justify-content:space-between; gap:12px; align-items:baseline; margin-bottom:12px; }
.section-head p { margin:0; color:var(--muted); font-size:13px; }
.grid2 { display:grid; grid-template-columns:1fr 1fr; gap:18px; }
@media (max-width:860px) { .grid2 { grid-template-columns:1fr; } }
.bar-row { display:grid; grid-template-columns:72px 1fr 40px 48px; gap:8px; align-items:center; margin:5px 0; font-size:13px; }
.bar-lab { color:var(--ink); }
.bar-track { height:8px; background:#efe8dc; border-radius:99px; overflow:hidden; }
.bar-fill { display:block; height:100%; background:var(--fill); }
.bar-n,.bar-p { font-variant-numeric:tabular-nums; color:var(--muted); text-align:right; }
.note,.gap { font-size:13px; padding:10px 12px; border-radius:10px; margin:0 0 12px; }
.note { background:var(--note); }
.gap { background:var(--gap); }
.pair-tabs { display:flex; flex-wrap:wrap; gap:8px; margin:0 0 12px; }
.pair-tab { font:inherit; border:1px solid var(--line); background:#fff; border-radius:8px; padding:7px 12px; cursor:pointer; }
.pair-tab.active { background:var(--accent); color:#fff; border-color:var(--accent); }
table.fields thead th { background:#111827; color:#fff; }
table.fields td.path { font-family:ui-monospace,Consolas,monospace; font-size:12px; }
tr.cat-head td { background:#f9fafb; font-weight:700; font-size:13px; padding:10px 8px; }
.pill { display:inline-block; padding:1px 8px; border-radius:99px; font-size:12px; font-weight:650; }
.pill.卡牌 { background:#dbeafe; color:#1e40af; }
.pill.文字 { background:#ffedd5; color:#9a3412; }
.pill.图像 { background:#ede9fe; color:#5b21b6; }
.pill.数字 { background:#dcfce7; color:#166534; }
.pending { color:var(--pending); font-weight:650; }
table { width:100%; border-collapse:collapse; font-size:13px; }
th,td { padding:7px 8px; border-bottom:1px solid var(--line); text-align:left; }
th { color:var(--muted); font-weight:650; background:#f9fafb; }
td.num, th.num { text-align:right; font-variant-numeric:tabular-nums; }
table.cross td, table.cross th { text-align:center; }
table.cross th:first-child, table.cross td:first-child { text-align:left; }
table.cross td.zero { color:#a8a29e; background:var(--zero); }
table.cross td.sum, table.cross tfoot td { font-weight:650; }
.table-scroll { overflow:auto; }
.toolbar { display:flex; flex-wrap:wrap; gap:8px; margin:0 0 12px; align-items:center; }
.toolbar .pair-tabs { width:100%; margin:0; }
select, input[type=search] { font:inherit; border:1px solid var(--line); background:#fff; border-radius:8px; padding:7px 10px; }
#count, #field-count { color:var(--muted); font-size:13px; }
.list th { position:sticky; top:0; }
.list td.name { max-width:420px; }
code { font-size:12px; }
.board-wrap { overflow:auto; background:#fff; border:1px solid var(--line); border-radius:14px; }
table.board { border-collapse:separate; border-spacing:0; min-width:760px; }
table.board thead th { background:#111827; color:#fff; font-size:12px; text-align:center; padding:10px 8px; }
table.board thead th:first-child { text-align:left; }
table.board td, table.board tbody th { border-bottom:1px solid var(--line); padding:0; vertical-align:stretch; }
table.board tbody th { text-align:left; padding:12px 14px; font-size:13px; background:#f9fafb; width:132px; }
.rate-cell { display:block; text-decoration:none; color:inherit; padding:12px 10px; text-align:center; min-height:72px; }
.rate-cell:hover { background:#f0fdfa; }
.rate-cell.active { background:#ecfdf5; outline:2px solid var(--accent); outline-offset:-2px; }
.rate { font-size:18px; font-weight:750; font-variant-numeric:tabular-nums; line-height:1.2; }
.rate.is-empty { min-height:1.2em; }
.rate.is-dash { color:var(--muted); }
.rate-hint { font-size:11px; color:var(--muted); margin-top:4px; }
td.cat-卡牌 { box-shadow:inset 3px 0 0 #2563eb; }
td.cat-文字 { box-shadow:inset 3px 0 0 #ea580c; }
td.cat-图像 { box-shadow:inset 3px 0 0 #7c3aed; }
td.cat-数字 { box-shadow:inset 3px 0 0 #16a34a; }
.legend { display:flex; flex-wrap:wrap; gap:10px 16px; margin:10px 0 0; font-size:12px; color:var(--muted); }
.legend span { display:inline-flex; align-items:center; gap:6px; }
.legend i { width:8px; height:8px; border-radius:99px; display:inline-block; }
.legend i.卡牌 { background:#2563eb; }
.legend i.文字 { background:#ea580c; }
.legend i.图像 { background:#7c3aed; }
.legend i.数字 { background:#16a34a; }
.batch-table { margin-top:8px; }
.batch-table td.rates { font-variant-numeric:tabular-nums; font-size:12px; }
.tabs { display:flex; flex-wrap:wrap; gap:4px; border-bottom:1px solid var(--line); margin:0 0 18px; }
.tab { font:inherit; background:transparent; border:none; border-bottom:2px solid transparent;
  padding:10px 16px; cursor:pointer; color:var(--muted); font-weight:650; font-size:14px; }
.tab.active { color:var(--accent); border-bottom-color:var(--accent); }
.panel { display:none; }
.panel.active { display:block; }
table.records { width:100%; background:#fff; border:1px solid var(--line); border-radius:12px; overflow:hidden; }
table.records thead th { background:#111827; color:#fff; font-size:12px; white-space:nowrap; }
table.records td { vertical-align:middle; }
.work-card { background:#fff; border:1px solid var(--line); border-radius:12px; padding:14px 16px; margin-bottom:14px; }
.filters { display:flex; flex-wrap:wrap; gap:10px 12px; align-items:flex-end; margin:0; }
.filters label { display:flex; flex-direction:column; gap:4px; font-size:12px; color:var(--muted); }
.filters input, .filters select { font:inherit; border:1px solid var(--line); background:#fff;
  border-radius:8px; padding:7px 10px; min-width:140px; color:var(--ink); }
.filter-actions { display:flex; gap:8px; align-items:center; margin-left:auto; }
.lookup-status { margin:10px 0 0; font-size:13px; color:var(--muted); }
.lookup-status:empty { display:none; }
.pager { display:flex; flex-wrap:wrap; align-items:center; gap:10px; margin-top:14px; font-size:13px; color:#6b7280; }
.pager-btns { display:flex; gap:8px; align-items:center; }
.pager-btn { min-width:32px; height:32px; padding:0 8px; border:none; border-radius:6px;
  background:#e5e7eb; color:#4b5563; cursor:pointer; font:inherit; }
.pager-btn.current { background:#d1d5db; font-weight:650; }
.pager-btn:disabled { opacity:.4; cursor:not-allowed; }
.pager-size { display:flex; align-items:center; gap:8px; }
.cat-blocks { display:grid; gap:16px; }
.cat-block { background:#fff; border:1px solid var(--line); border-radius:14px; overflow:hidden; }
.cat-block.卡牌 { border-top:4px solid #2563eb; }
.cat-block.文字 { border-top:4px solid #ea580c; }
.cat-block.图像 { border-top:4px solid #7c3aed; }
.cat-block.数字 { border-top:4px solid #16a34a; }
.cat-headbar { display:flex; flex-wrap:wrap; align-items:center; gap:10px; padding:12px 16px; background:#f9fafb; border-bottom:1px solid var(--line); }
.cat-headbar h3 { margin:0; font-size:15px; flex:1; }
.cat-kpi { font-size:13px; color:var(--muted); font-variant-numeric:tabular-nums; }
.cat-block .table-scroll { max-height:340px; }
.waiting { color:var(--pending); font-weight:650; }
.modal-mask { position:fixed; inset:0; background:rgba(17,24,39,.45); z-index:80;
  display:none; align-items:center; justify-content:center; padding:24px; }
.modal-mask.show { display:flex; }
.modal { background:#fff; border-radius:14px; width:min(560px,100%);
  box-shadow:0 18px 50px rgba(15,23,42,.2); }
.modal h3 { margin:0; padding:18px 20px 0; font-size:16px; }
.modal .modal-sub { margin:6px 20px 0; color:var(--muted); font-size:13px; }
.modal-body { padding:16px 20px; display:grid; gap:12px; }
.modal-row { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
@media (max-width:560px) { .modal-row { grid-template-columns:1fr; } }
.modal-body label { display:flex; flex-direction:column; gap:5px; font-size:12px; color:var(--muted); }
.modal-body input[type=text], .modal-body textarea {
  font:inherit; border:1px solid var(--line); border-radius:8px; padding:8px 10px; color:var(--ink); }
.modal-body #m-api { font-family:ui-monospace,Menlo,monospace; font-size:12px; }
.modal-body textarea { min-height:76px; resize:vertical; }
.modal-file { border:1px dashed #cbd5e1; border-radius:10px; padding:14px; background:#f8fafc;
  font-size:13px; color:var(--muted); cursor:pointer; }
.modal-file strong { color:var(--ink); font-weight:650; }
.modal-actions { display:flex; justify-content:flex-end; gap:8px; padding:0 20px 18px; }
.err-link { background:none; border:none; color:var(--accent); cursor:pointer; font:inherit; font-weight:650; padding:0; }
.err-link:hover { text-decoration:underline; }
.drawer-mask { position:fixed; inset:0; background:rgba(17,24,39,.4); z-index:90;
  display:none; justify-content:flex-end; }
.drawer-mask.show { display:flex; }
.drawer { width:min(960px,100%); background:#fff; height:100%; overflow:auto;
  padding:18px 20px 40px; box-shadow:-8px 0 28px rgba(15,23,42,.18); }
.drawer-head { display:flex; justify-content:space-between; align-items:flex-start; gap:12px; margin-bottom:10px; }
.drawer-head h3 { margin:0 0 4px; font-size:16px; word-break:break-all; }
.drawer-filter { display:flex; align-items:center; gap:6px; font-size:13px; color:var(--muted); margin:0 0 10px; }
.lookup-grid { display:grid; grid-template-columns:200px minmax(0,1fr); gap:16px; align-items:start; }
@media (max-width:900px) { .lookup-grid { grid-template-columns:1fr; } }
.lookup-side { margin-top:0; padding:12px 0 0; }
.hand-head { display:flex; flex-wrap:wrap; justify-content:space-between; gap:10px; align-items:flex-start; margin-bottom:12px; }
.hand-head h2 { font-size:1.15rem; word-break:break-all; }
.hand-list { max-height:calc(100vh - 200px); overflow:auto; }
.hand-list button { display:block; width:100%; text-align:left; background:#fff; border:none;
  border-bottom:1px solid var(--line); padding:10px 12px; cursor:pointer; font:inherit; }
.hand-list button:hover { background:#f0fdfa; }
.hand-list button.active { background:#ecfdf5; }
.hand-list .hid-row { display:flex; align-items:baseline; gap:6px; }
.hand-list .idx { font-size:11px; color:var(--muted); font-variant-numeric:tabular-nums; flex-shrink:0; }
.hand-list .hid { font-family:ui-monospace,Consolas,monospace; font-size:12px; color:var(--ink);
  overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.hand-list .meta { display:flex; align-items:center; gap:6px; margin-top:4px; }
.st { display:inline-block; padding:1px 7px; border-radius:99px; font-size:11px; font-weight:650; background:#f3f4f6; color:#4b5563; }
.st.ok { background:#dcfce7; color:#166534; }
.st.bad { background:#fee2e2; color:#991b1b; }
.stage-split { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
@media (max-width:1100px) { .stage-split { grid-template-columns:1fr; } }
.stage-col { min-width:0; }
.stage-head { display:flex; justify-content:space-between; align-items:center; gap:8px; margin:0 0 8px; }
.stage-head h3 { margin:0; font-size:14px; }
.json-fold { margin-top:16px; border-top:1px solid var(--line); padding-top:10px; }
.json-fold > summary { cursor:pointer; color:var(--muted); font-size:13px; font-weight:650; margin:0 0 10px; }
.pcard { display:inline-flex; align-items:center; justify-content:center; min-width:32px; height:38px;
  padding:0 7px; border-radius:6px; background:#fff; border:1px solid #d1d5db; font-weight:750; font-size:15px;
  font-family:"IBM Plex Sans","PingFang SC",sans-serif; letter-spacing:.02em; }
.pcard.s, .pcard.c { color:#111827; }
.pcard.h, .pcard.d { color:#dc2626; }
.pcard.unk { color:#9ca3af; background:#f9fafb; }
.hv-miss { color:var(--muted); padding:16px 0; font-size:14px; }
.json-view { font-family:ui-monospace,Menlo,Consolas,monospace; font-size:12px; line-height:1.45;
  background:#111827; color:#e5e7eb; padding:14px 16px; border-radius:12px;
  overflow:auto; max-height:42vh; white-space:pre; margin:0; }
.json-empty { color:var(--muted); padding:28px 8px; font-size:14px; }
.cmp-banner { display:flex; flex-wrap:wrap; align-items:center; gap:10px 14px; margin:0 0 14px;
  padding:10px 12px; border-radius:10px; background:#f0fdfa; font-size:13px; }
.cmp-banner.is-diff { background:#fff7ed; }
.cmp-banner strong { font-size:15px; }
.cmp-opt { display:inline-flex; align-items:center; gap:6px; color:var(--muted); margin-left:auto; }
.cmp-kpis { display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:10px; margin:0 0 16px; }
.cmp-kpi { background:#f9fafb; border:1px solid var(--line); border-radius:12px; padding:10px 12px; }
.cmp-kpi.is-diff { background:#fff7ed; border-color:#fdba74; }
.cmp-kpi .lab { font-size:12px; color:var(--muted); margin-bottom:6px; }
.cmp-kpi .one { font-size:20px; font-weight:700; font-variant-numeric:tabular-nums; }
.cmp-kpi .pair { display:grid; gap:4px; }
.cmp-kpi .pair span { display:flex; justify-content:space-between; gap:8px; font-variant-numeric:tabular-nums; }
.cmp-kpi .pair .tag { font-size:11px; color:var(--muted); font-weight:650; }
.cmp-kpi .pair .num { font-size:18px; font-weight:700; }
.cmp-board { display:flex; flex-wrap:wrap; align-items:center; gap:10px 16px; margin:0 0 16px;
  padding:10px 12px; border:1px solid var(--line); border-radius:12px; background:#fff; }
.cmp-board.is-diff { background:#fff7ed; border-color:#fdba74; }
.cmp-board .lab { color:var(--muted); font-size:12px; font-weight:650; }
.cmp-board .side { display:flex; align-items:center; gap:8px; }
.cmp-board .tag { font-size:11px; color:var(--muted); font-weight:650; }
table.cmp { width:100%; border-collapse:separate; border-spacing:0; font-size:14px; margin:0 0 16px; }
table.cmp th { position:sticky; top:0; background:#111827; color:#fff; font-size:12px; padding:9px 10px; }
table.cmp td { padding:12px 12px; vertical-align:top; border-bottom:1px solid var(--line); }
table.cmp tr.is-diff td { background:#fff7ed; }
table.cmp tr.is-fold { color:#9ca3af; }
table.cmp td.pos { font-weight:700; width:64px; }
table.cmp .cell-one { font-variant-numeric:tabular-nums; }
table.cmp .cell-pair { display:grid; gap:6px; }
table.cmp .cell-pair .row { display:flex; align-items:baseline; gap:8px; line-height:1.4; font-variant-numeric:tabular-nums; }
table.cmp .cell-pair .tag { flex:0 0 1.2em; font-size:11px; color:#9a3412; font-weight:700; }
table.cmp .hero-mark { margin-left:6px; font-size:11px; background:#dbeafe; color:#1e40af;
  border-radius:99px; padding:1px 6px; font-weight:650; }
.cmp-street { margin:0 0 16px; }
.cmp-street h4 { margin:0 0 8px; font-size:14px; display:flex; align-items:baseline; gap:8px; }
.cmp-street h4 .n { font-size:12px; color:var(--muted); font-weight:500; }
table.cmp-act td { font-size:13px; padding:8px 10px; }
table.cmp-act .n { width:36px; color:var(--muted); font-variant-numeric:tabular-nums; }
.act { display:flex; flex-wrap:wrap; align-items:baseline; gap:6px; }
.act .pos { font-weight:700; min-width:2.6em; }
.act .who { color:var(--muted); }
.act .verb { font-weight:650; }
.act .amt { font-variant-numeric:tabular-nums; font-weight:700; }
.cmp-win { display:flex; flex-wrap:wrap; gap:8px 16px; padding:10px 12px; border-radius:12px;
  background:#ecfdf5; color:#166534; font-size:14px; margin:0 0 8px; }
.cmp-win.is-diff { background:#fff7ed; color:#9a3412; }
.legend-diff { font-size:12px; color:var(--muted); margin:0 0 12px; }
table.compare td.path { font-family:ui-monospace,Consolas,monospace; font-size:11px; max-width:280px; word-break:break-all; }
table.compare td.val { font-size:12px; max-width:180px; word-break:break-all; }
table.compare tr.is-diff td { background:#fff7ed; }
table.compare tr.is-ok td { color:#6b7280; }
.pill.ok { background:#f3f4f6; color:#6b7280; }
.pill.vis { background:#ffedd5; color:#9a3412; }
.pill.rule { background:#fee2e2; color:#991b1b; }
.pill.fix { background:#dcfce7; color:#166534; }
.pill.both { background:#ede9fe; color:#5b21b6; }
.pill.miss { background:#e5e7eb; color:#374151; }
.hand-diff-row td { background:#f8fafc; padding:12px 14px 16px; }
.hand-diff-row .sub { margin:0 0 8px; }
.hand-diff-tools { display:flex; align-items:center; gap:10px; margin:0 0 10px; font-size:13px; color:var(--muted); }
table.compare { width:100%; border-collapse:collapse; font-size:13px; }
table.compare th { text-align:left; font-weight:650; color:var(--muted); padding:8px 10px; border-bottom:1px solid var(--line); }
"""


def esc(s) -> str:
    return (
        str("" if s is None else s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def cat_counts(fields: list[dict]) -> dict[str, int]:
    c = Counter(f["cat"] for f in fields)
    return {cat: int(c.get(cat, 0)) for cat in CATS}


def empty_pair_rates(by_cat: dict[str, int]) -> dict:
    rows = {}
    for pair in PAIRS:
        row = {"all": None}
        for cat in CATS:
            row[cat] = None if by_cat.get(cat, 0) else "—"
        rows[pair["id"]] = row
    return rows


def format_rate(val) -> tuple[str, str]:
    if val is None or val == "":
        return "", "is-empty"
    if val == "—":
        return "—", "is-dash"
    try:
        return f"{float(val):.1f}%", ""
    except (TypeError, ValueError):
        return str(val), ""


def fields_href(pair_id: str, cat: str | None = None) -> str:
    q = f"?tab=match&pair={quote(pair_id)}"
    if cat:
        q += f"&cat={quote(cat)}"
    return q


def rate_board_html(
    *,
    by_cat: dict[str, int],
    n_fields: int,
    pair_rates: dict | None = None,
    active_pair: str | None = None,
    active_cat: str | None = "",
) -> str:
    rates = pair_rates or empty_pair_rates(by_cat)
    heads = "".join(f"<th>{esc(cat)}</th>" for cat in CATS)
    rows = []
    for pair in PAIRS:
        row = rates.get(pair["id"]) or {}
        total_txt, total_cls = format_rate(row.get("all"))
        all_active = " active" if active_pair == pair["id"] and not active_cat else ""
        cells = [
            f'<td><a class="rate-cell{all_active}" data-pair="{esc(pair["id"])}" data-cat="" '
            f'href="{esc(fields_href(pair["id"]))}">'
            f'<div class="rate {total_cls}">{esc(total_txt)}</div>'
            f'<div class="rate-hint">{n_fields} 条路径</div></a></td>'
        ]
        for cat in CATS:
            txt, cls = format_rate(row.get(cat))
            n = by_cat.get(cat, 0)
            hint = f"{n} 条路径" if n else "本批无此类叶子"
            cat_active = " active" if active_pair == pair["id"] and active_cat == cat else ""
            cells.append(
                f'<td class="cat-{esc(cat)}"><a class="rate-cell{cat_active}" '
                f'data-pair="{esc(pair["id"])}" data-cat="{esc(cat)}" '
                f'href="{esc(fields_href(pair["id"], cat))}">'
                f'<div class="rate {cls}">{esc(txt)}</div>'
                f'<div class="rate-hint">{esc(hint)}</div></a></td>'
            )
        rows.append(
            f'<tr><th>{esc(pair["title"])}<div class="rate-hint">左侧 {esc(pair["left"])} 为分母</div></th>'
            + "".join(cells)
            + "</tr>"
        )
    legend = "".join(
        f'<span><i class="{esc(cat)}"></i>{esc(cat)} · {esc(CAT_HINT[cat])}</span>' for cat in CATS
    )
    return (
        '<div class="board-wrap"><table class="board"><thead>'
        f'<tr><th>比对环节</th><th>总匹配率</th>{heads}</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
        f'<div class="legend">{legend}</div>'
    )


def page(
    *,
    title: str,
    nav: str,
    home_href: str,
    body: str,
    script: str = "",
    extra_scripts: list[str] | None = None,
    main_class: str = "",
) -> str:
    lookup_href = home_href.replace("index.html", "lookup.html") if "index.html" in home_href else "lookup.html"
    items = (
        ("index", home_href, "上传记录"),
        ("lookup", lookup_href, "session 查询"),
    )
    nav_html = "".join(
        f'<a class="{"active" if nav == key else ""}" href="{esc(href)}">{esc(lab)}</a>'
        for key, href, lab in items
    )
    extra = '<a class="active" href="#">本批详情</a>' if nav == "detail" else ""
    extras = "".join(
        f'<script src="{esc(src + ("?v=11" if src.endswith(".js") else ""))}"></script>\n'
        for src in (extra_scripts or [])
    )
    script_block = f"<script>\n{script}\n</script>" if script else ""
    main_cls = "main" + (f" {main_class}" if main_class else "")
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{esc(title)}</title>
<style>{COMMON_CSS}</style>
</head>
<body>
<div class="app">
  <aside class="side">
    <div class="kicker">Texas Hold'em</div>
    <div class="brand">数字好友桌 e2e</div>
    <nav>{nav_html}{extra}</nav>
  </aside>
  <div class="{main_cls}">
{body}
  </div>
</div>
{extras}{script_block}
</body>
</html>
"""


def matrix(cases: list[dict], row_key: str, col_key: str, rows: list, cols: list) -> list[list]:
    cnt: dict[tuple, int] = Counter((c[row_key], c[col_key]) for c in cases)
    return [[cnt.get((rk, ck), 0) for ck in cols] for rk in rows]


def bar_rows(cases: list[dict], key: str, order: list, label_fn=None) -> str:
    n = len(cases)
    cnt = Counter(c[key] for c in cases)
    parts = []
    for k in order:
        v = cnt[k]
        pct = 100.0 * v / n if n else 0
        lab = label_fn(k) if label_fn else k
        parts.append(
            f'<div class="bar-row"><span class="bar-lab">{esc(lab)}</span>'
            f'<span class="bar-track"><span class="bar-fill" style="width:{pct:.1f}%"></span></span>'
            f'<span class="bar-n">{v}</span><span class="bar-p">{pct:.1f}%</span></div>'
        )
    return "".join(parts)


def table_cross(cases: list[dict], row_key, col_key, rows, cols, row_lab) -> str:
    n = len(cases)
    mat = matrix(cases, row_key, col_key, rows, cols)
    head = "".join(f"<th>{esc(c)}</th>" for c in cols)
    body = []
    col_sums = [0] * len(cols)
    for ri, rk in enumerate(rows):
        tds = []
        rs = 0
        for ci, val in enumerate(mat[ri]):
            cls = ' class="zero"' if val == 0 else ""
            tds.append(f"<td{cls}>{val}</td>")
            rs += val
            col_sums[ci] += val
        body.append(f"<tr><th>{esc(rk)}</th>{''.join(tds)}<td class='sum'>{rs}</td></tr>")
    foot = "".join(f"<td>{v}</td>" for v in col_sums)
    return (
        f"<table class='cross'><thead><tr><th>{esc(row_lab)}</th>{head}<th>合计</th></tr></thead>"
        f"<tbody>{''.join(body)}</tbody>"
        f"<tfoot><tr><th>合计</th>{foot}<td class='sum'>{n}</td></tr></tfoot></table>"
    )


def list_val(val, *, waiting: bool = False) -> str:
    if waiting:
        return "等结果"
    if val is None or val == "" or val == "—":
        return ""
    try:
        return f"{float(val):.1f}%"
    except (TypeError, ValueError):
        return str(val)


def batch_list_item(batch: dict) -> dict:
    rates = batch.get("pair_rates") or {}
    gt = rates.get("gt_vis") or {}
    vis = rates.get("vis_rule") or {}
    rule = rates.get("gt_rule") or {}
    n = batch.get("n")
    waiting = batch.get("lookup") == "waiting"
    return {
        "id": batch.get("id") or "",
        "file": batch.get("source_name") or "",
        "n": "" if n in (None, "") else n,
        "gt_vis": list_val(gt.get("all"), waiting=waiting),
        "vis_rule": list_val(vis.get("all"), waiting=waiting),
        "gt_rule": list_val(rule.get("all"), waiting=waiting),
        "uploader": batch.get("uploader") or "",
        "note": batch.get("note") or "",
        "time": batch.get("generated_at") or "",
        "detail": batch.get("detail") or batch.get("match") or "#",
        "lookup": batch.get("lookup") or "",
        "session_id": batch.get("session_id") or "",
    }


def detail_html(
    *,
    batch_title: str,
    source_name: str,
    generated: str,
    cases: list[dict],
    fields: list[dict],
    actions: list[str],
    players: list[int],
    hero_pos: list[str],
    pair_rates: dict | None = None,
    field_stats: dict | None = None,
    session_id: str = "",
    batch_id: str = "",
    note: str = "",
) -> str:
    n = len(cases)
    by_cat = cat_counts(fields)
    n_fields = len(fields)
    rates = pair_rates or empty_pair_rates(by_cat)
    looked = bool(field_stats)
    board = rate_board_html(
        by_cat=by_cat,
        n_fields=n_fields,
        pair_rates=rates,
        active_pair=None,
        active_cat="",
    )
    sess_note = f" · session {esc(session_id)}" if session_id else ""
    note_note = f" · {esc(note)}" if note else ""
    body = f"""
  <div class="page-head">
    <div>
      <h1>{esc(batch_title)}</h1>
      <p class="sub">源数据 <code>{esc(source_name)}</code> · {n} 手 · 生成 {esc(generated)}{sess_note}{note_note}。</p>
    </div>
    <a class="btn-ghost" href="../../index.html">返回上传记录</a>
  </div>
  <div class="tabs" role="tablist">
    <button type="button" class="tab active" data-tab="match">匹配率</button>
    <button type="button" class="tab" data-tab="coverage">覆盖分布</button>
  </div>

  <div id="panel-match" class="panel active">
    <section class="section" style="padding-bottom:16px">
      <div class="section-head"><h2>质量看板</h2><p>点格子筛到下方字段。还没查到的格子留空，不是 0%</p></div>
      {board}
    </section>
    <section class="section" id="fields-block">
      <div class="section-head"><h2>字段匹配率</h2><p>点出错手数看这一字段在源数据 / 视觉 / 规则的差异</p></div>
      <div class="toolbar">
        <div class="pair-tabs" id="pair-tabs"></div>
        <input id="f-path" type="search" placeholder="筛选字段路径" style="flex:1;min-width:180px"/>
        <button type="button" class="btn-ghost" id="refresh-match">重新查询</button>
        <span id="field-count"></span>
      </div>
      <p class="sub" id="detail-caption" style="margin:0 0 12px"></p>
      <div class="cat-blocks" id="cat-blocks"></div>
    </section>
    <section class="section" id="hand-mod">
      <div class="section-head"><h2>每手牌差异</h2><p>每手三对匹配率。点差异在本页展开这一手全部不一致字段</p></div>
      <div class="toolbar">
        <label style="display:flex;align-items:center;gap:6px;font-size:13px;color:var(--muted)">
          <input type="checkbox" id="hand-only-err"/> 只看出错手
        </label>
        <input id="hand-q" type="search" placeholder="筛选序号 / hand_id" style="flex:1;min-width:160px"/>
        <span id="hand-mod-count"></span>
      </div>
      <div class="table-scroll" style="max-height:none">
        <table class="list">
          <thead>
            <tr>
              <th class="num">序号</th>
              <th>hand_id</th>
              <th class="num">出错字段</th>
              <th>源→视觉</th>
              <th>视觉→规则</th>
              <th>源→规则</th>
              <th></th>
            </tr>
          </thead>
          <tbody id="hand-mod-body"></tbody>
        </table>
      </div>
    </section>
  </div>

  <div id="panel-coverage" class="panel">
    <div class="cards">
      <div class="card"><div class="label">用例手数</div><div class="value">{n}</div></div>
      <div class="card"><div class="label">动作类型</div><div class="value">{len(actions)}</div><div class="hint">open…all in</div></div>
      <div class="card"><div class="label">人数</div><div class="value">3–9</div></div>
      <div class="card"><div class="label">摊牌</div><div class="value">{sum(1 for c in cases if c['showdown'])}</div><div class="hint">未摊牌 {sum(1 for c in cases if not c['showdown'])}</div></div>
    </div>
    <section class="section">
      <div class="section-head"><h2>覆盖分布</h2><p>一手只计一次</p></div>
      <div class="grid2">
        <div><h3 style="margin:0 0 8px;font-size:13px;color:var(--muted)">按街</h3>{bar_rows(cases, "street", STREETS)}</div>
        <div><h3 style="margin:0 0 8px;font-size:13px;color:var(--muted)">按动作</h3>{bar_rows(cases, "action", actions)}</div>
        <div><h3 style="margin:0 0 8px;font-size:13px;color:var(--muted)">按人数</h3>{bar_rows(cases, "n_players", players, lambda p: f"{p}人")}</div>
        <div><h3 style="margin:0 0 8px;font-size:13px;color:var(--muted)">按英雄位</h3>{bar_rows(cases, "hero_pos", hero_pos)}</div>
      </div>
    </section>
    <section class="section">
      <div class="section-head"><h2>街 × 动作</h2><p>翻前没有 bet/raise/check；翻后没有 open/limp/3bet/4bet，这是场景设计不是缺测</p></div>
      <div class="table-scroll">{table_cross(cases, "street", "action", STREETS, actions, "街")}</div>
    </section>
    <section class="section">
      <div class="section-head"><h2>人数 × 英雄位</h2><p>灰格 0：该人数桌没有这个位置，或本批没覆盖</p></div>
      <div class="table-scroll">{table_cross(cases, "n_players", "hero_pos", players, hero_pos, "人数")}</div>
    </section>
    <section class="section">
      <div class="section-head"><h2>人数 × 街</h2></div>
      <div class="table-scroll">{table_cross(cases, "n_players", "street", players, STREETS, "人数")}</div>
    </section>
    <section class="section">
      <div class="section-head"><h2>{n} 手清单</h2><p>批跑序号 = 默认对齐序（翻前→翻牌→转牌→河牌）</p></div>
      <div class="toolbar">
        <input id="q" type="search" placeholder="搜索用例名 / hand_id / 动作" style="flex:1;min-width:200px"/>
        <select id="f-street"><option value="">街：全部</option></select>
        <select id="f-action"><option value="">动作：全部</option></select>
        <select id="f-n"><option value="">人数：全部</option></select>
        <select id="f-hero"><option value="">英雄位：全部</option></select>
        <span id="count"></span>
      </div>
      <div class="table-scroll" style="max-height:70vh">
        <table class="list">
          <thead>
            <tr>
              <th class="num">序号</th><th>街</th><th>动作</th><th>人数</th><th>英雄位</th>
              <th>盲注</th><th>摊牌</th><th>用例名称</th><th>hand_id</th><th>对照</th>
            </tr>
          </thead>
          <tbody id="tbody"></tbody>
        </table>
      </div>
    </section>
  </div>
  <div class="drawer-mask" id="drawer-mask">
    <div class="drawer" role="dialog" aria-modal="true">
      <div class="drawer-head">
        <div>
          <h3 id="drawer-title">对照</h3>
          <p class="sub" id="drawer-sub"></p>
        </div>
        <div style="display:flex;gap:8px;flex-shrink:0">
          <button type="button" class="btn-ghost" id="drawer-back" hidden>返回字段差异</button>
          <button type="button" class="btn-ghost" id="drawer-close">关闭</button>
        </div>
      </div>
      <label class="drawer-filter" id="drawer-filter" hidden>
        <input type="checkbox" id="drawer-diff" checked/> 只看不一致
      </label>
      <p class="sub" id="drawer-status"></p>
      <div class="table-scroll" id="drawer-body"></div>
    </div>
  </div>
"""
    script = f"""
const FIELDS = {json.dumps(fields, ensure_ascii=False, separators=(",", ":"))};
const PAIRS = {json.dumps(list(PAIRS), ensure_ascii=False)};
const CATS = {json.dumps(list(CATS), ensure_ascii=False)};
const CAT_HINT = {json.dumps(CAT_HINT, ensure_ascii=False)};
const CASES = {json.dumps(cases, ensure_ascii=False, separators=(",", ":"))};
const PAIR_RATES = {json.dumps(rates, ensure_ascii=False)};
const FIELD_STATS = {json.dumps(field_stats or {}, ensure_ascii=False, separators=(",", ":"))};
let LOOKED_UP = {json.dumps(looked)};
const BATCH_ID = {json.dumps(batch_id or batch_title)};
const SESSION_ID = {json.dumps(session_id or "")};
const $ = id => document.getElementById(id);
const DEFAULT_API = "http://192.168.110.81:8080";
let HANDS = [];
let SAVED_API = DEFAULT_API;
let drawerPath = "";
let drawerRows = [];
let bodyCache = {{}};
let handDiffOpen = null;
let handDiffPack = {{}};
function rateClass(v) {{
  if (v == null || v === "") return "is-empty";
  if (v === "—") return "is-dash";
  return "";
}}
function paintBoard() {{
  document.querySelectorAll("a.rate-cell[data-pair]").forEach(a => {{
    const pair = a.dataset.pair;
    const cat = a.dataset.cat || "all";
    const v = (PAIR_RATES[pair] || {{}})[cat];
    const rateEl = a.querySelector(".rate");
    if (!rateEl) return;
    rateEl.className = "rate " + rateClass(v);
    rateEl.textContent = fmtRate(v);
  }});
}}
try {{
  const saved = JSON.parse(localStorage.getItem("e2e-rates-" + BATCH_ID) || "null");
  const fresh = saved && Array.isArray(saved.hands) && saved.hands.length;
  if (fresh) {{
    if (saved.pair_rates) Object.assign(PAIR_RATES, saved.pair_rates);
    if (saved.field_stats) {{
      Object.keys(saved.field_stats).forEach(k => {{ FIELD_STATS[k] = saved.field_stats[k]; }});
      LOOKED_UP = true;
    }}
    HANDS = saved.hands;
  }}
  if (saved && saved.api) SAVED_API = saved.api;
  else {{
    const last = localStorage.getItem("e2e-last-api");
    if (last) SAVED_API = last;
  }}
}} catch (e) {{}}
function fillSelect(id, values) {{
  const el = $(id);
  values.forEach(v => {{
    const o = document.createElement("option");
    o.value = String(v); o.textContent = String(v);
    el.appendChild(o);
  }});
}}
fillSelect("f-street", {json.dumps(STREETS, ensure_ascii=False)});
fillSelect("f-action", {json.dumps(actions, ensure_ascii=False)});
fillSelect("f-n", {json.dumps(players)});
fillSelect("f-hero", {json.dumps(hero_pos, ensure_ascii=False)});

function setTab(tab) {{
  if (tab === "board" || tab === "fields") tab = "match";
  ["match","coverage"].forEach(id => {{
    const btn = document.querySelector('.tab[data-tab="'+id+'"]');
    const panel = $("panel-"+id);
    if (btn) btn.classList.toggle("active", id === tab);
    if (panel) panel.classList.toggle("active", id === tab);
  }});
  const url = new URL(location.href);
  url.searchParams.set("tab", tab);
  history.replaceState(null, "", url);
}}
document.querySelectorAll(".tab").forEach(btn => {{
  btn.addEventListener("click", () => setTab(btn.dataset.tab));
}});

const params = new URLSearchParams(location.search);
let currentPair = params.get("pair") || PAIRS[0].id;
if (!PAIRS.some(p => p.id === currentPair)) currentPair = PAIRS[0].id;
let currentCat = params.get("cat") || "";
if (currentCat && !CATS.includes(currentCat)) currentCat = "";
setTab(params.get("tab") || "match");
$("pair-tabs").innerHTML = PAIRS.map(p =>
  "<button type='button' class='pair-tab' data-pair='" + p.id + "'>" + p.title + "</button>"
).join("");
function syncPairUi() {{
  document.querySelectorAll(".pair-tab").forEach(btn => {{
    btn.classList.toggle("active", btn.dataset.pair === currentPair);
  }});
  document.querySelectorAll("a.rate-cell").forEach(a => {{
    a.classList.toggle("active", a.dataset.pair === currentPair && (a.dataset.cat || "") === currentCat);
  }});
}}
function showPair(pair, cat, scroll) {{
  currentPair = pair;
  currentCat = cat || "";
  window.__scrolledCat = !scroll;
  syncPairUi();
  renderFields();
  const url = new URL(location.href);
  url.searchParams.set("tab", "match");
  url.searchParams.set("pair", currentPair);
  if (currentCat) url.searchParams.set("cat", currentCat);
  else url.searchParams.delete("cat");
  history.replaceState(null, "", url);
}}
document.querySelectorAll(".pair-tab").forEach(btn => {{
  btn.addEventListener("click", () => showPair(btn.dataset.pair, "", false));
}});

function pairOf(id) {{ return PAIRS.find(p => p.id === id); }}
function fmtRate(v) {{
  if (v == null || v === "") return "";
  if (v === "—") return "—";
  const n = Number(v);
  if (Number.isFinite(n)) return n.toFixed(1) + "%";
  return String(v);
}}
function rowHtml(f, p) {{
  const blank = "";
  const st = (FIELD_STATS[p.id] || {{}})[f.path];
  if (!LOOKED_UP) {{
    const total = p.totals === "gold" ? f.total : blank;
    return "<tr>" +
      "<td class='path'>" + f.path + "</td>" +
      "<td class='num'>" + total + "</td>" +
      "<td class='num'>" + blank + "</td>" +
      "<td class='num'>" + blank + "</td>" +
      "<td class='num'>" + blank + "</td>" +
      "<td class='num'>" + blank + "</td>" +
      "<td>" + blank + "</td>" +
      "<td class='num'>" + blank + "</td>" +
      "</tr>";
  }}
  const row = st || {{ total: 0, match: 0, mismatch: 0, missing: 0, len_mismatch: 0, n_error: 0, errors: [] }};
  const rate = row.total ? ((100 * row.match / row.total).toFixed(1) + "%") : "—";
  const errN = row.n_error || 0;
  const errBtn = errN
    ? "<button type='button' class='err-link' data-err-path='" + encodeURIComponent(f.path) + "'>" + errN + "</button>"
    : "0";
  return "<tr>" +
    "<td class='path'>" + f.path + "</td>" +
    "<td class='num'>" + row.total + "</td>" +
    "<td class='num'>" + row.match + "</td>" +
    "<td class='num'>" + row.mismatch + "</td>" +
    "<td class='num'>" + row.missing + "</td>" +
    "<td class='num'>" + row.len_mismatch + "</td>" +
    "<td>" + rate + "</td>" +
    "<td class='num'>" + errBtn + "</td>" +
    "</tr>";
}}
function renderFields() {{
  const p = pairOf(currentPair);
  const q = $("f-path").value.trim().toLowerCase();
  const focus = currentCat;
  $("detail-caption").textContent = p.title + " · 卡牌 / 文字 / 图像 / 数字分块对照";
  let shown = 0;
  $("cat-blocks").innerHTML = CATS.map(cat => {{
    if (focus && cat !== focus) return "";
    const all = FIELDS.filter(f => f.cat === cat);
    const part = all.filter(f => !q || f.path.toLowerCase().includes(q));
    shown += part.length;
    const catRate = LOOKED_UP ? fmtRate((PAIR_RATES[p.id] || {{}})[cat]) : "";
    const body = part.length
      ? part.map(f => rowHtml(f, p)).join("")
      : "<tr><td colspan='8'>没有匹配字段</td></tr>";
    return "<section class='cat-block " + cat + "' id='block-" + cat + "'>" +
      "<div class='cat-headbar'>" +
      "<span class='pill " + cat + "'>" + cat + "</span>" +
      "<h3>" + (CAT_HINT[cat] || "") + "</h3>" +
      "<div class='cat-kpi'>匹配率 " + catRate + " · " + all.length + " 条路径" +
      (part.length !== all.length ? " · 显示 " + part.length : "") + "</div>" +
      "</div>" +
      "<div class='table-scroll'><table class='fields'><thead><tr>" +
      "<th>字段</th><th class='num'>总数</th><th class='num'>匹配</th>" +
      "<th class='num'>值不匹配</th><th class='num'>缺失</th><th class='num'>列表长度不匹配</th>" +
      "<th>匹配率</th><th class='num'>出错手数</th>" +
      "</tr></thead><tbody>" + body + "</tbody></table></div></section>";
  }}).join("");
  $("field-count").textContent = "显示 " + shown + " / " + FIELDS.length;
  document.querySelectorAll(".err-link[data-err-path]").forEach(btn => {{
    btn.addEventListener("click", () => openErrorHands(decodeURIComponent(btn.dataset.errPath)));
  }});
  if (focus && !window.__scrolledCat) {{
    window.__scrolledCat = true;
    const el = $("block-" + focus);
    if (el) el.scrollIntoView({{ behavior: "smooth", block: "start" }});
  }}
  renderHandMod();
}}
$("f-path").addEventListener("input", renderFields);
document.querySelectorAll("a.rate-cell").forEach(a => {{
  a.addEventListener("click", e => {{
    e.preventDefault();
    showPair(a.dataset.pair, a.dataset.cat || "", true);
  }});
}});
syncPairUi();
paintBoard();
renderFields();

function renderCoverage() {{
  const q = $("q").value.trim().toLowerCase();
  const st = $("f-street").value;
  const ac = $("f-action").value;
  const np = $("f-n").value;
  const hero = $("f-hero").value;
  const rows = CASES.filter(c => {{
    if (st && c.street !== st) return false;
    if (ac && c.action !== ac) return false;
    if (np && String(c.n_players) !== np) return false;
    if (hero && c.hero_pos !== hero) return false;
    if (q) {{
      const blob = (c.name + " " + c.hand_id + " " + c.action + " " + c.hero_pos).toLowerCase();
      if (!blob.includes(q)) return false;
    }}
    return true;
  }});
  $("count").textContent = "显示 " + rows.length + " / " + CASES.length;
  $("tbody").innerHTML = rows.map(c =>
    "<tr>" +
    "<td class='num'>" + c.seq + "</td>" +
    "<td>" + c.street + "</td>" +
    "<td>" + c.action + "</td>" +
    "<td class='num'>" + c.n_players + "</td>" +
    "<td>" + c.hero_pos + "</td>" +
    "<td>" + c.blinds + "</td>" +
    "<td>" + (c.showdown ? "是" : "否") + "</td>" +
    "<td class='name'>" + c.name + "</td>" +
    "<td><code>" + c.hand_id + "</code></td>" +
    "<td>" + (LOOKED_UP
      ? "<button type='button' class='err-link' data-seq='" + c.seq + "'>对照</button>"
      : "") + "</td>" +
    "</tr>"
  ).join("");
  document.querySelectorAll("#tbody .err-link[data-seq]").forEach(btn => {{
    btn.addEventListener("click", () => openCompare(Number(btn.dataset.seq), true));
  }});
}}
["q","f-street","f-action","f-n","f-hero"].forEach(id => $(id).addEventListener("input", renderCoverage));
renderCoverage();

function nErrorForSeq(seq) {{
  const p = pairOf(currentPair);
  const stats = (p && FIELD_STATS[p.id]) || {{}};
  let n = 0;
  Object.keys(stats).forEach(path => {{
    const errs = stats[path] && stats[path].errors;
    if (Array.isArray(errs) && errs.indexOf(seq) >= 0) n += 1;
  }});
  return n;
}}
function renderHandMod() {{
  const box = $("hand-mod-body");
  if (!box) return;
  const only = $("hand-only-err") && $("hand-only-err").checked;
  const q = (($("hand-q") && $("hand-q").value) || "").trim().toLowerCase();
  if (!LOOKED_UP) {{
    box.innerHTML = "<tr><td colspan='7'>还没有匹配率。点上方「重新查询」后再看每手。</td></tr>";
    $("hand-mod-count").textContent = "";
    return;
  }}
  const rows = CASES.filter(c => {{
    const nErr = nErrorForSeq(c.seq);
    if (only && !nErr) return false;
    if (q) {{
      const blob = (c.seq + " " + (c.hand_id || "")).toLowerCase();
      if (!blob.includes(q)) return false;
    }}
    return true;
  }});
  $("hand-mod-count").textContent = "显示 " + rows.length + " / " + CASES.length;
  box.innerHTML = rows.map(c => {{
    const h = handOf(c.seq);
    const nErr = nErrorForSeq(c.seq);
    const open = handDiffOpen === c.seq;
    return "<tr>" +
      "<td class='num'>" + c.seq + "</td>" +
      "<td><code>" + (h.hand_id || c.hand_id || "") + "</code></td>" +
      "<td class='num'>" + nErr + "</td>" +
      "<td>" + fmtPct(h.gt_vis) + "</td>" +
      "<td>" + fmtPct(h.vis_rule) + "</td>" +
      "<td>" + fmtPct(h.gt_rule) + "</td>" +
      "<td>" + (LOOKED_UP
        ? "<button type='button' class='err-link' data-hand-seq='" + c.seq + "'>" + (open ? "收起" : "差异") + "</button>"
        : "") + "</td>" +
      "</tr>" +
      "<tr class='hand-diff-row' id='hand-diff-row-" + c.seq + "'" + (open ? "" : " hidden") + ">" +
      "<td colspan='7'>" +
      "<div class='hand-diff-tools'>" +
      "<label><input type='checkbox' id='hand-diff-only-" + c.seq + "' checked/> 只看不一致</label>" +
      "<span id='hand-diff-st-" + c.seq + "'></span>" +
      "</div>" +
      "<div id='hand-diff-" + c.seq + "'></div>" +
      "</td></tr>";
  }}).join("") || "<tr><td colspan='7'>没有匹配的手。</td></tr>";
  box.querySelectorAll("[data-hand-seq]").forEach(btn => {{
    btn.addEventListener("click", () => toggleHandDiff(Number(btn.dataset.handSeq)));
  }});
  if (handDiffOpen) paintHandDiff(handDiffOpen);
}}
["hand-only-err","hand-q"].forEach(id => {{
  const el = $(id);
  if (!el) return;
  el.addEventListener("input", renderHandMod);
  el.addEventListener("change", renderHandMod);
}});
function valAt(tree, path) {{
  if (!window.E2EMatch || !tree) return undefined;
  const flat = E2EMatch.flattenValues(tree);
  return path in flat ? flat[path] : undefined;
}}
async function fetchBody(seq) {{
  if (bodyCache[seq] !== undefined) return bodyCache[seq];
  const h = handOf(seq);
  if (!h.fusionHandId || !h.sessionId) {{
    bodyCache[seq] = null;
    return null;
  }}
  const p = E2EMatch.fetchHandResult(SAVED_API, h.sessionId, h.fusionHandId).catch(err => {{
    delete bodyCache[seq];
    throw err;
  }});
  bodyCache[seq] = p;
  return p;
}}
function compareTableHtml(rows, onlyDiff) {{
  const M = window.E2EMatch;
  if (!M) return "<p class='sub'>缺少 e2e-match.js。</p>";
  const part = (rows || []).filter(r => !onlyDiff || (r.cause && r.cause.id !== "ok"));
  if (!part.length) return "<p class='sub'>没有不一致字段。</p>";
  return "<table class='compare'><thead><tr>" +
    "<th>字段</th><th>源数据</th><th>视觉</th><th>规则</th><th>归因</th>" +
    "</tr></thead><tbody>" +
    part.map(r => {{
      const cls = r.cause.id === "ok" ? "is-ok" : "is-diff";
      return "<tr class='" + cls + "'>" +
        "<td class='path'>" + r.path + "</td>" +
        "<td class='val'>" + M.displayVal(r.gold) + "</td>" +
        "<td class='val'>" + M.displayVal(r.vis) + "</td>" +
        "<td class='val'>" + M.displayVal(r.rule) + "</td>" +
        "<td><span class='pill " + r.cause.id + "'>" + r.cause.lab + "</span></td>" +
        "</tr>";
    }}).join("") + "</tbody></table>";
}}
function paintHandDiff(seq) {{
  const pack = handDiffPack[seq];
  const box = $("hand-diff-" + seq);
  const st = $("hand-diff-st-" + seq);
  if (!box) return;
  if (!pack) return;
  if (st) st.textContent = pack.status || "";
  const onlyEl = $("hand-diff-only-" + seq);
  box.innerHTML = compareTableHtml(pack.rows, !onlyEl || onlyEl.checked);
  if (onlyEl && !onlyEl.dataset.bound) {{
    onlyEl.dataset.bound = "1";
    onlyEl.addEventListener("change", () => paintHandDiff(seq));
  }}
}}
async function loadHandDiff(seq) {{
  if (handDiffPack[seq]) return handDiffPack[seq];
  const st = $("hand-diff-st-" + seq);
  const h = handOf(seq);
  const goldPack = window.E2E_GOLD;
  const gold = goldPack && goldPack.trees && goldPack.trees[seq - 1];
  if (!gold) {{
    handDiffPack[seq] = {{ rows: [], status: "没有这手的源数据界面树。请重新生成站点。" }};
    return handDiffPack[seq];
  }}
  if (!window.E2EMatch) {{
    handDiffPack[seq] = {{ rows: [], status: "缺少 e2e-match.js，请重新生成站点后刷新。" }};
    return handDiffPack[seq];
  }}
  if (!h.fusionHandId || !h.sessionId) {{
    handDiffPack[seq] = {{ rows: [], status: "这批匹配率是旧的，没有每手 fusion id。请重新查询。" }};
    return handDiffPack[seq];
  }}
  if (st) st.textContent = "正在拉这一手的差异…";
  try {{
    const body = await fetchBody(seq);
    const stages = E2EMatch.stageTrees(gold, body);
    const rows = E2EMatch.compareStages(gold, stages.vis, stages.rule);
    const miss = [];
    if (!stages.vis) miss.push("视觉");
    if (!stages.rule) miss.push("规则");
    handDiffPack[seq] = {{
      rows: rows,
      status: miss.length
        ? "缺 " + miss.join("、") + "。下面仍按源数据字段列出。"
        : "只列出不一致字段。归因：视觉引入 / 规则引入 / 规则救回 / 视觉错、规则又偏。"
    }};
  }} catch (e) {{
    handDiffPack[seq] = {{ rows: [], status: "拉 fusion 失败：" + ((e && e.message) || e) }};
  }}
  return handDiffPack[seq];
}}
async function toggleHandDiff(seq) {{
  const row = $("hand-diff-row-" + seq);
  if (!row) return;
  if (handDiffOpen === seq && !row.hidden) {{
    row.hidden = true;
    handDiffOpen = null;
    document.querySelectorAll("[data-hand-seq]").forEach(b => {{ b.textContent = "差异"; }});
    return;
  }}
  document.querySelectorAll(".hand-diff-row").forEach(el => {{ el.hidden = true; }});
  document.querySelectorAll("[data-hand-seq]").forEach(b => {{ b.textContent = "差异"; }});
  row.hidden = false;
  handDiffOpen = seq;
  const btn = document.querySelector("[data-hand-seq='" + seq + "']");
  if (btn) btn.textContent = "收起";
  await loadHandDiff(seq);
  paintHandDiff(seq);
  row.scrollIntoView({{ behavior: "smooth", block: "nearest" }});
}}
async function mapPool(items, limit, fn) {{
  const out = new Array(items.length);
  let i = 0;
  async function worker() {{
    while (i < items.length) {{
      const idx = i++;
      out[idx] = await fn(items[idx], idx);
    }}
  }}
  const n = Math.min(limit, items.length) || 1;
  await Promise.all(Array.from({{ length: n }}, worker));
  return out;
}}
function fieldErrors(path) {{
  const p = pairOf(currentPair);
  const row = (FIELD_STATS[p.id] || {{}})[path] || {{}};
  return Array.isArray(row.errors) ? row.errors : [];
}}
function handOf(seq) {{
  return HANDS.find(h => h.seq === seq) || {{}};
}}
function caseOf(seq) {{
  return CASES.find(c => c.seq === seq) || {{}};
}}
function fmtPct(v) {{
  if (v == null || v === "") return "—";
  return v + "%";
}}
function showDrawer() {{
  $("drawer-mask").classList.add("show");
}}
function closeDrawer() {{
  $("drawer-mask").classList.remove("show");
}}
function openErrorHands(path) {{
  drawerPath = path;
  $("drawer-title").textContent = "字段差异";
  $("drawer-sub").textContent = path;
  $("drawer-filter").hidden = true;
  $("drawer-back").hidden = true;
  const seqs = fieldErrors(path);
  if (!LOOKED_UP) {{
    $("drawer-status").textContent = "还没有匹配率。请先在上传记录里查过，再点出错手数。";
    $("drawer-body").innerHTML = "";
    showDrawer();
    return;
  }}
  if (!seqs.length) {{
    $("drawer-status").textContent = "这一字段没有记下出错序号。回到上传记录重新查一次匹配率即可。";
    $("drawer-body").innerHTML = "";
    showDrawer();
    return;
  }}
  $("drawer-status").textContent = "正在拉 " + seqs.length + " 手的字段值…";
  $("drawer-body").innerHTML = "";
  showDrawer();
  const M = window.E2EMatch;
  const goldPack = window.E2E_GOLD;
  if (!M) {{
    $("drawer-status").textContent = "缺少 e2e-match.js，请重新生成站点后刷新。";
    return;
  }}
  let done = 0;
  mapPool(seqs, 4, async seq => {{
    const h = handOf(seq);
    const c = caseOf(seq);
    const gold = goldPack && goldPack.trees && goldPack.trees[seq - 1];
    let goldVal, visVal, ruleVal, cause;
    if (!gold) {{
      cause = {{ id: "miss", lab: "缺源数据" }};
    }} else {{
      try {{
        const body = await fetchBody(seq);
        const stages = M.stageTrees(gold, body);
        goldVal = valAt(gold, path);
        visVal = stages.vis ? valAt(stages.vis, path) : undefined;
        ruleVal = stages.rule ? valAt(stages.rule, path) : undefined;
        cause = M.causeOf(goldVal, visVal, ruleVal, !!stages.vis, !!stages.rule);
      }} catch (e) {{
        cause = {{ id: "miss", lab: "拉 fusion 失败" }};
      }}
    }}
    done += 1;
    $("drawer-status").textContent = "正在拉字段差异 " + done + " / " + seqs.length;
    return {{ seq, h, c, goldVal, visVal, ruleVal, cause }};
  }}).then(rows => {{
    $("drawer-status").textContent = seqs.length + " 手 · 只列出该字段在源数据 / 视觉 / 规则的差异";
    $("drawer-body").innerHTML =
      "<table class='compare'><thead><tr>" +
      "<th class='num'>序号</th><th>hand_id</th><th>源数据</th><th>视觉</th><th>规则</th><th>归因</th>" +
      "</tr></thead><tbody>" +
      rows.map(r => {{
        const cls = r.cause && r.cause.id === "ok" ? "is-ok" : "is-diff";
        return "<tr class='" + cls + "'>" +
          "<td class='num'>" + r.seq + "</td>" +
          "<td><code>" + ((r.h && r.h.hand_id) || (r.c && r.c.hand_id) || "") + "</code></td>" +
          "<td class='val'>" + M.displayVal(r.goldVal) + "</td>" +
          "<td class='val'>" + M.displayVal(r.visVal) + "</td>" +
          "<td class='val'>" + M.displayVal(r.ruleVal) + "</td>" +
          "<td><span class='pill " + ((r.cause && r.cause.id) || "miss") + "'>" +
          ((r.cause && r.cause.lab) || "") + "</span></td>" +
          "</tr>";
      }}).join("") + "</tbody></table>";
  }}).catch(e => {{
    $("drawer-status").textContent = "拉字段差异失败：" + ((e && e.message) || e);
  }});
}}
function paintCompare() {{
  $("drawer-body").innerHTML = compareTableHtml(drawerRows, $("drawer-diff").checked);
}}
async function openCompare(seq, fromList) {{
  $("drawer-back").hidden = !!fromList;
  $("drawer-filter").hidden = false;
  $("drawer-title").textContent = "第 " + seq + " 手对照";
  const h = handOf(seq);
  const c = caseOf(seq);
  $("drawer-sub").textContent =
    (h.hand_id || c.hand_id || "") +
    (h.fusionHandId ? " · fusion " + h.fusionHandId : "");
  $("drawer-status").textContent = "正在拉视觉 / 规则…";
  $("drawer-body").innerHTML = "";
  showDrawer();
  const goldPack = window.E2E_GOLD;
  const gold = goldPack && goldPack.trees && goldPack.trees[seq - 1];
  if (!gold) {{
    $("drawer-status").textContent = "没有这手的源数据界面树。请重新生成站点。";
    return;
  }}
  if (!window.E2EMatch) {{
    $("drawer-status").textContent = "缺少 e2e-match.js，请重新生成站点后刷新。";
    return;
  }}
  if (!h.fusionHandId || !h.sessionId) {{
    $("drawer-status").textContent = "这批匹配率是旧的，没有每手 fusion id。请回到上传记录重新查一次。";
    return;
  }}
  let body = null;
  try {{
    body = await fetchBody(seq);
  }} catch (e) {{
    $("drawer-status").textContent = "拉 fusion 失败：" + ((e && e.message) || e);
    return;
  }}
  const stages = E2EMatch.stageTrees(gold, body);
  drawerRows = E2EMatch.compareStages(gold, stages.vis, stages.rule);
  const miss = [];
  if (!stages.vis) miss.push("视觉");
  if (!stages.rule) miss.push("规则");
  $("drawer-status").textContent = miss.length
    ? "缺 " + miss.join("、") + "。下面仍按源数据字段列出。"
    : "差异已标色。归因：视觉引入 / 规则引入 / 规则救回 / 视觉错、规则又偏。";
  paintCompare();
}}
$("drawer-close").addEventListener("click", closeDrawer);
$("drawer-back").addEventListener("click", () => {{
  if (drawerPath) openErrorHands(drawerPath);
  else closeDrawer();
}});
$("drawer-mask").addEventListener("click", e => {{
  if (e.target === $("drawer-mask")) closeDrawer();
}});
$("drawer-diff").addEventListener("change", paintCompare);
document.addEventListener("keydown", e => {{
  if (e.key === "Escape") closeDrawer();
}});
function saveLocalRates(payload) {{
  try {{ localStorage.setItem("e2e-rates-" + BATCH_ID, JSON.stringify(payload)); }} catch (e) {{}}
}}
async function refreshMatch() {{
  if (!window.E2EMatch || !window.E2E_GOLD) {{
    alert("缺少比对脚本。请重新生成站点后刷新。");
    return;
  }}
  let sid = SESSION_ID;
  if (!sid) {{
    sid = window.prompt("fusion sessionId", "") || "";
    sid = sid.trim();
  }}
  if (!sid) return;
  const btn = $("refresh-match");
  btn.disabled = true;
  $("detail-caption").textContent = "正在查 fusion…";
  try {{
    const result = await E2EMatch.lookup({{
      base: SAVED_API,
      sessionId: sid,
      gold: window.E2E_GOLD,
      onProgress: m => {{ $("detail-caption").textContent = m; }}
    }});
    HANDS = result.hands || [];
    handDiffPack = {{}};
    handDiffOpen = null;
    bodyCache = {{}};
    Object.assign(PAIR_RATES, result.pair_rates);
    Object.keys(result.field_stats || {{}}).forEach(k => {{ FIELD_STATS[k] = result.field_stats[k]; }});
    LOOKED_UP = true;
    saveLocalRates({{
      pair_rates: result.pair_rates,
      field_stats: result.field_stats,
      session_id: sid,
      n_vis: result.n_vis,
      n_rule: result.n_rule,
      n_gold: result.n_gold,
      n_fusion: result.n_fusion,
      hands: result.hands,
      api: SAVED_API,
      at: new Date().toISOString()
    }});
    paintBoard();
    renderFields();
    renderCoverage();
    $("detail-caption").textContent = "已更新匹配率。点出错手数看字段差异；底部展开每手差异。";
  }} catch (e) {{
    $("detail-caption").textContent = "";
    alert((e && e.message) || e);
  }} finally {{
    btn.disabled = false;
  }}
}}
$("refresh-match").addEventListener("click", refreshMatch);
if (SESSION_ID && !HANDS.length) refreshMatch();
"""
    return page(
        title=f"{batch_title} · 详情",
        nav="detail",
        home_href="../../index.html",
        body=body,
        script=script,
        extra_scripts=["gold_trees.js", "../../e2e-match.js"],
    )


def index_html(batches: list[dict], generated: str) -> str:
    items = [batch_list_item(b) for b in batches]
    body = f"""
  <div class="page-head">
    <h1>上传记录</h1>
  </div>
  <div class="work-card">
    <form class="filters" id="filters" onsubmit="return false">
      <label>文件<input id="q-file" type="search" placeholder="文件名"/></label>
      <label>上传人<input id="q-uploader" type="search" placeholder="上传人"/></label>
      <label>上传时间起<input id="q-from" type="date"/></label>
      <label>上传时间止<input id="q-to" type="date"/></label>
      <div class="filter-actions">
        <button type="button" class="btn" id="q-search">查询</button>
        <button type="button" class="btn-ghost" id="q-reset">重置</button>
        <button type="button" class="btn" id="u-btn">上传文件</button>
      </div>
    </form>
    <p id="u-status" class="lookup-status"></p>
  </div>
  <div class="table-scroll">
    <table class="records">
      <thead>
        <tr>
          <th>文件</th>
          <th class="num">手数</th>
          <th>源数据→视觉</th>
          <th>视觉→规则</th>
          <th>源数据→规则</th>
          <th>上传人</th>
          <th>备注</th>
          <th>上传时间</th>
          <th>详情</th>
        </tr>
      </thead>
      <tbody id="record-body"></tbody>
    </table>
  </div>
  <div class="pager">
    <span id="pager-total">共 0 条</span>
    <div class="pager-btns" id="pager-btns"></div>
    <div class="pager-size">
      <span>每页显示：</span>
      <select id="page-size">
        <option value="10">10</option>
        <option value="20">20</option>
        <option value="50" selected>50</option>
        <option value="100">100</option>
      </select>
    </div>
  </div>
  <div class="modal-mask" id="upload-mask" role="dialog" aria-modal="true" aria-labelledby="upload-title">
    <div class="modal">
      <h3 id="upload-title">上传文件</h3>
      <p class="modal-sub">支持 Excel（读 auto_json 列）、json、jsonl。上传后按 sessionId 向 fusion 查匹配率。</p>
      <div class="modal-body">
        <div class="modal-row">
          <label>sessionId
            <input id="m-session" type="text" placeholder="fusion sessionId"/>
          </label>
          <label>fusion API
            <input id="m-api" type="text" value="http://192.168.110.81:8080" spellcheck="false"/>
          </label>
        </div>
        <label>上传人
          <input id="m-name" type="text" placeholder="可空"/>
        </label>
        <label>备注
          <textarea id="m-note" placeholder="可空，例如这批数字筹码 / 无 Straddle"></textarea>
        </label>
        <label>文件
          <div class="modal-file" id="m-drop">点击选择文件，或把文件拖到这里<br/><strong id="m-fname">未选择文件</strong></div>
          <input id="m-file" type="file" accept=".xlsx,.xls,.json,.jsonl,application/json" hidden/>
        </label>
      </div>
      <div class="modal-actions">
        <button type="button" class="btn-ghost" id="m-cancel">取消</button>
        <button type="button" class="btn" id="m-ok">上传</button>
      </div>
    </div>
  </div>
"""
    script = f"""
const RECORDS = {json.dumps(items, ensure_ascii=False)};
const $ = id => document.getElementById(id);
const LOCAL_UPLOAD = "http://127.0.0.1:8767";
const DEFAULT_API = "http://192.168.110.81:8080";
let page = 1;
let pickedFile = null;
function dayOf(s) {{
  return String(s || "").slice(0, 10);
}}
function escText(s) {{
  return String(s || "").replace(/[&<>"]/g, c => ({{"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;"}}[c]));
}}
function filtered() {{
  const file = $("q-file").value.trim().toLowerCase();
  const who = $("q-uploader").value.trim().toLowerCase();
  const from = $("q-from").value;
  const to = $("q-to").value;
  return RECORDS.filter(r => {{
    if (file && !String(r.file).toLowerCase().includes(file)) return false;
    if (who && !String(r.uploader).toLowerCase().includes(who)) return false;
    const d = dayOf(r.time);
    if (from && (!d || d < from)) return false;
    if (to && (!d || d > to)) return false;
    return true;
  }});
}}
function fmtListRate(v) {{
  if (v == null || v === "") return "";
  if (v === "—") return "—";
  const n = Number(v);
  if (Number.isFinite(n)) return n.toFixed(1) + "%";
  return String(v);
}}
function ratesKey(id) {{ return "e2e-rates-" + id; }}
function applySavedRates() {{
  RECORDS.forEach(r => {{
    if (!r.id) return;
    try {{
      const saved = JSON.parse(localStorage.getItem(ratesKey(r.id)) || "null");
      if (!saved || !saved.pair_rates || !Array.isArray(saved.hands) || !saved.hands.length) return;
      const pr = saved.pair_rates;
      r.gt_vis = fmtListRate((pr.gt_vis || {{}}).all);
      r.vis_rule = fmtListRate((pr.vis_rule || {{}}).all);
      r.gt_rule = fmtListRate((pr.gt_rule || {{}}).all);
    }} catch (e) {{}}
  }});
}}
function render() {{
  const rows = filtered();
  const size = Math.max(1, parseInt($("page-size").value, 10) || 50);
  const pages = Math.max(1, Math.ceil(rows.length / size));
  if (page > pages) page = pages;
  if (page < 1) page = 1;
  const start = (page - 1) * size;
  const slice = rows.slice(start, start + size);
  $("pager-total").textContent = "共 " + rows.length + " 条";
  $("record-body").innerHTML = slice.map(r =>
    "<tr>" +
    "<td>" + escText(r.file) + "</td>" +
    "<td class='num'>" + (r.n === "" || r.n == null ? "" : r.n) + "</td>" +
    "<td>" + (r.gt_vis === "等结果" ? "<span class='waiting'>等结果</span>" : escText(r.gt_vis)) + "</td>" +
    "<td>" + (r.vis_rule === "等结果" ? "<span class='waiting'>等结果</span>" : escText(r.vis_rule)) + "</td>" +
    "<td>" + (r.gt_rule === "等结果" ? "<span class='waiting'>等结果</span>" : escText(r.gt_rule)) + "</td>" +
    "<td>" + escText(r.uploader) + "</td>" +
    "<td>" + escText(r.note) + "</td>" +
    "<td>" + escText(r.time) + "</td>" +
    "<td>" + (r.detail
      ? "<a href='" + r.detail + "'>详情</a>"
      : (r.id ? "<a href='batches/" + encodeURIComponent(r.id) + "/detail.html'>详情</a>" : "")) + "</td>" +
    "</tr>"
  ).join("") || "<tr><td colspan='9'>没有匹配的记录</td></tr>";
  const btns = [];
  btns.push("<button type='button' class='pager-btn' data-p='" + (page - 1) + "'" + (page <= 1 ? " disabled" : "") + ">‹</button>");
  for (let i = 1; i <= pages; i++) {{
    if (pages > 7 && i > 2 && i < pages - 1 && Math.abs(i - page) > 1) {{
      if (i === 3 || i === pages - 2) btns.push("<span>…</span>");
      continue;
    }}
    btns.push("<button type='button' class='pager-btn" + (i === page ? " current" : "") + "' data-p='" + i + "'>" + i + "</button>");
  }}
  btns.push("<button type='button' class='pager-btn' data-p='" + (page + 1) + "'" + (page >= pages ? " disabled" : "") + ">›</button>");
  $("pager-btns").innerHTML = btns.join("");
  $("pager-btns").querySelectorAll("button").forEach(btn => {{
    btn.addEventListener("click", () => {{
      const n = parseInt(btn.dataset.p, 10);
      if (!n || n < 1 || n > pages) return;
      page = n;
      render();
    }});
  }});
}}
$("q-search").addEventListener("click", () => {{ page = 1; render(); }});
$("q-reset").addEventListener("click", () => {{
  $("q-file").value = "";
  $("q-uploader").value = "";
  $("q-from").value = "";
  $("q-to").value = "";
  page = 1;
  render();
}});
$("page-size").addEventListener("change", () => {{ page = 1; render(); }});
["q-file","q-uploader"].forEach(id => $(id).addEventListener("keydown", e => {{
  if (e.key === "Enter") {{ page = 1; render(); }}
}}));
function fusionBase() {{
  return ($("m-api").value || DEFAULT_API).replace(/\\/+$/, "");
}}
function setStatus(msg) {{
  const el = $("u-status");
  if (el) el.textContent = msg || "";
}}
function busy(on) {{
  $("u-btn").disabled = on;
  $("m-ok").disabled = on;
  $("m-cancel").disabled = on;
}}
function saveRates(id, payload) {{
  const key = ratesKey(id);
  try {{ localStorage.setItem(key, JSON.stringify(payload)); return; }} catch (e) {{}}
  const slim = JSON.parse(JSON.stringify(payload));
  Object.keys(slim.field_stats || {{}}).forEach(pair => {{
    Object.keys(slim.field_stats[pair] || {{}}).forEach(path => {{
      const row = slim.field_stats[pair][path];
      if (row) delete row.errors;
    }});
  }});
  try {{ localStorage.setItem(key, JSON.stringify(slim)); return; }} catch (e) {{}}
  localStorage.setItem(key, JSON.stringify({{
    pair_rates: payload.pair_rates,
    n_vis: payload.n_vis, n_rule: payload.n_rule, n_gold: payload.n_gold,
    session_id: payload.session_id,
    hands: payload.hands,
    api: payload.api
  }}));
}}
function loadGold(batchId) {{
  return new Promise((resolve, reject) => {{
    const prev = document.getElementById("e2e-gold");
    if (prev) prev.remove();
    window.E2E_GOLD = null;
    const s = document.createElement("script");
    s.id = "e2e-gold";
    s.src = "batches/" + encodeURIComponent(batchId) + "/gold_trees.js";
    s.onload = () => window.E2E_GOLD ? resolve(window.E2E_GOLD) : reject(new Error("源数据脚本为空"));
    s.onerror = () => reject(new Error("加载源数据失败。请打开整个 e2e-quality 目录里的 index.html，不要只拷单个页面。"));
    document.head.appendChild(s);
  }});
}}
async function runLookup(batchId, sid, api) {{
  if (!window.E2EMatch) throw new Error("缺少 e2e-match.js，请重新生成站点后刷新");
  const gold = await loadGold(batchId);
  const result = await E2EMatch.lookup({{
    base: api,
    sessionId: sid,
    gold,
    onProgress: setStatus
  }});
  saveRates(batchId, {{
    pair_rates: result.pair_rates,
    field_stats: result.field_stats,
    session_id: sid,
    n_vis: result.n_vis,
    n_rule: result.n_rule,
    n_gold: result.n_gold,
    n_fusion: result.n_fusion,
    hands: result.hands,
    api: api,
    at: new Date().toISOString()
  }});
  return result;
}}
function openUpload() {{
  pickedFile = null;
  $("m-file").value = "";
  $("m-fname").textContent = "未选择文件";
  try {{
    $("m-session").value = localStorage.getItem("e2e-last-session") || (RECORDS[0] && RECORDS[0].session_id) || "";
    $("m-api").value = localStorage.getItem("e2e-last-api") || DEFAULT_API;
  }} catch (e) {{
    $("m-api").value = DEFAULT_API;
  }}
  $("m-name").value = "";
  $("m-note").value = "";
  $("upload-mask").classList.add("show");
  $("m-session").focus();
}}
function closeUpload() {{
  $("upload-mask").classList.remove("show");
}}
function setPicked(file) {{
  if (!file) return;
  if (!/\\.(xlsx|xls|jsonl|json)$/i.test(file.name)) {{
    alert("请上传 Excel（.xlsx / .xls）、json 或 jsonl");
    return;
  }}
  pickedFile = file;
  $("m-fname").textContent = file.name;
}}
async function submitUpload() {{
  const sid = $("m-session").value.trim();
  const api = fusionBase();
  if (!sid) {{
    alert("请填写 fusion sessionId");
    $("m-session").focus();
    return;
  }}
  if (!pickedFile) {{
    alert("请选择 Excel、json 或 jsonl 文件");
    return;
  }}
  const fd = new FormData();
  fd.append("session_id", sid);
  fd.append("uploader", $("m-name").value.trim());
  fd.append("note", $("m-note").value.trim());
  fd.append("file", pickedFile, pickedFile.name);
  busy(true);
  $("m-ok").textContent = "上传中…";
  setStatus("正在解析源数据…");
  try {{
    localStorage.setItem("e2e-last-session", sid);
    localStorage.setItem("e2e-last-api", api);
    const res = await fetch(LOCAL_UPLOAD + "/api/upload", {{ method: "POST", body: fd }});
    const data = await res.json().catch(() => ({{}}));
    if (!res.ok) throw new Error(data.error || ("上传失败 " + res.status));
    const batchId = data.id;
    if (!batchId) throw new Error("上传成功但没有批次 id");
    $("m-ok").textContent = "查询匹配率…";
    setStatus("已上传，正在向 fusion 查匹配率。手数多时请稍候。");
    await runLookup(batchId, sid, api);
    closeUpload();
    setStatus("已出匹配率，正在刷新…");
    location.reload();
  }} catch (e) {{
    const msg = (e && e.message) ? e.message : String(e);
    setStatus("");
    if (/Failed to fetch|NetworkError|Load failed/i.test(msg) && !/连不上 fusion/.test(msg)) {{
      alert("上传需要本地服务。请先运行 python3 scripts/e2e_quality_server.py，再用 http://127.0.0.1:8767/ 打开本页。");
    }} else if (/连不上 fusion/.test(msg)) {{
      alert("文件已上传，但连不上 fusion。请确认弹框里的 API 和 sessionId，和调试台同一套。");
    }} else {{
      alert(msg);
    }}
  }} finally {{
    busy(false);
    $("m-ok").textContent = "上传";
  }}
}}
$("u-btn").addEventListener("click", openUpload);
$("m-cancel").addEventListener("click", closeUpload);
$("upload-mask").addEventListener("click", e => {{ if (e.target === $("upload-mask")) closeUpload(); }});
document.addEventListener("keydown", e => {{
  if (e.key === "Escape" && $("upload-mask").classList.contains("show")) closeUpload();
}});
$("m-drop").addEventListener("click", () => $("m-file").click());
$("m-file").addEventListener("change", () => {{
  const f = $("m-file").files && $("m-file").files[0];
  if (f) setPicked(f);
}});
["dragenter","dragover"].forEach(ev => $("m-drop").addEventListener(ev, e => {{
  e.preventDefault();
  $("m-drop").style.borderColor = "#0f766e";
}}));
["dragleave","drop"].forEach(ev => $("m-drop").addEventListener(ev, e => {{
  e.preventDefault();
  $("m-drop").style.borderColor = "";
}}));
$("m-drop").addEventListener("drop", e => {{
  const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
  if (f) setPicked(f);
}});
$("m-ok").addEventListener("click", submitUpload);
applySavedRates();
render();
"""
    return page(
        title="e2e 上传记录",
        nav="index",
        home_href="index.html",
        body=body,
        script=script,
        extra_scripts=["e2e-match.js"],
    )


def lookup_html() -> str:
    body = """
  <div class="page-head">
    <div>
      <h1>session 查询</h1>
      <p class="sub">按 fusion sessionId 列出这一局里的手牌。视觉与规则对齐对照，橙色表示不一致。</p>
    </div>
  </div>
  <div class="work-card">
    <form class="filters" id="lookup-form" onsubmit="return false">
      <label>sessionId
        <input id="q-session" type="text" placeholder="fusion sessionId" style="min-width:240px"/>
      </label>
      <label>fusion API
        <input id="q-api" type="text" placeholder="http://192.168.110.81:8080" style="min-width:260px;font-family:ui-monospace,Menlo,monospace;font-size:12px"/>
      </label>
      <div class="filter-actions">
        <button type="button" class="btn" id="q-go">查询</button>
        <button type="button" class="btn-ghost" id="q-dump">下载本 session 全部</button>
      </div>
    </form>
    <p id="q-status" class="lookup-status"></p>
  </div>
  <div class="lookup-grid">
    <section class="section lookup-side">
      <div class="toolbar" style="padding:0 12px">
        <input id="q-hand" type="search" placeholder="筛选 handId / 状态" style="flex:1;min-width:0"/>
        <span id="hand-count"></span>
      </div>
      <div class="hand-list" id="hand-list"></div>
    </section>
    <section class="section" style="margin-top:0">
      <div class="hand-head">
        <div>
          <h2 id="json-title">视觉 / 规则对照</h2>
          <p id="user-hint" class="sub" style="margin:4px 0 0"></p>
        </div>
        <button type="button" class="btn-ghost" id="q-copy-id" hidden>复制 handId</button>
      </div>
      <p class="json-empty" id="json-empty">先查 session，再点左侧一手。</p>
      <div id="stage-wrap" hidden>
        <div id="viz-compare"></div>
        <details class="json-fold">
          <summary>原始 JSON</summary>
          <div class="stage-split" id="stage-split">
            <div class="stage-col">
              <div class="stage-head">
                <h3>视觉 JSON</h3>
                <button type="button" class="btn-ghost" id="q-copy-vis">复制视觉</button>
              </div>
              <pre class="json-view" id="json-vis"></pre>
            </div>
            <div class="stage-col">
              <div class="stage-head">
                <h3>规则 JSON</h3>
                <button type="button" class="btn-ghost" id="q-copy-rule">复制规则</button>
              </div>
              <pre class="json-view" id="json-rule"></pre>
            </div>
          </div>
        </details>
      </div>
    </section>
  </div>
"""
    return page(
        title="session 查询",
        nav="lookup",
        home_href="index.html",
        body=body,
        script="E2ESessionLookup.start();",
        extra_scripts=["e2e-match.js", "e2e-session-lookup.js"],
        main_class="is-lookup",
    )


def legacy_redirect(rel_url: str, label: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta http-equiv="refresh" content="0;url={esc(rel_url)}"/>
<title>跳转</title>
</head>
<body>
<p>页面已拆分。正在打开 <a href="{esc(rel_url)}">{esc(label)}</a>。</p>
</body>
</html>
"""


def upsert_batches(index_path: Path, batch: dict) -> list[dict]:
    data = {"batches": []}
    if index_path.exists():
        try:
            data = json.loads(index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {"batches": []}
    batches = [b for b in data.get("batches", []) if b.get("id") != batch["id"]]
    batches.insert(0, batch)
    return batches


def write_site(
    *,
    site_dir: Path,
    batch_id: str,
    batch_title: str,
    source_name: str,
    source_path: str,
    generated: str,
    cases: list[dict],
    fields: list[dict],
    actions: list[str],
    players: list[int],
    hero_pos: list[str],
    snapshot: dict,
    uploader: str = "",
    pair_rates: dict | None = None,
    field_stats: dict | None = None,
    session_id: str = "",
    trees: list[dict] | None = None,
    note: str = "",
) -> dict:
    batch_dir = site_dir / "batches" / batch_id
    batch_dir.mkdir(parents=True, exist_ok=True)
    scripts_dir = Path(__file__).resolve().parent
    for name in ("e2e-match.js", "e2e-session-lookup.js"):
        src = scripts_dir / name
        if src.exists():
            shutil.copy(src, site_dir / name)
    (site_dir / "lookup.html").write_text(lookup_html(), encoding="utf-8")
    if trees:
        gold = {
            "id": batch_id,
            "cases": [{"hand_id": c.get("hand_id"), "seq": c.get("seq")} for c in cases],
            "trees": trees,
        }
        (batch_dir / "gold_trees.js").write_text(
            "window.E2E_GOLD=" + json.dumps(gold, ensure_ascii=False, separators=(",", ":")) + ";\n",
            encoding="utf-8",
        )
    (batch_dir / "detail.html").write_text(
        detail_html(
            batch_title=batch_title,
            source_name=source_name,
            generated=generated,
            cases=cases,
            fields=fields,
            actions=actions,
            players=players,
            hero_pos=hero_pos,
            pair_rates=pair_rates,
            field_stats=field_stats,
            session_id=session_id,
            batch_id=batch_id,
            note=note,
        ),
        encoding="utf-8",
    )
    (batch_dir / "match.html").write_text(legacy_redirect("detail.html?tab=match", "匹配率"), encoding="utf-8")
    (batch_dir / "coverage.html").write_text(legacy_redirect("detail.html?tab=coverage", "覆盖分布"), encoding="utf-8")
    (batch_dir / "snapshot.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    by_cat = cat_counts(fields)
    rates = pair_rates or empty_pair_rates(by_cat)
    batch = {
        "id": batch_id,
        "title": batch_title,
        "source": source_path,
        "source_name": source_name,
        "n": len(cases),
        "n_fields": len(fields),
        "cats": by_cat,
        "pair_rates": rates,
        "generated_at": generated,
        "uploader": uploader or "",
        "note": note or "",
        "session_id": session_id or "",
        "lookup": "" if field_stats else "waiting",
        "status": "已出匹配率" if field_stats else "匹配率待批跑",
        "detail": f"batches/{batch_id}/detail.html",
        "match": f"batches/{batch_id}/detail.html?tab=match",
        "coverage": f"batches/{batch_id}/detail.html?tab=coverage",
    }
    (batch_dir / "meta.json").write_text(
        json.dumps(batch, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    index_path = site_dir / "batches.json"
    batches = upsert_batches(index_path, batch)
    index_path.write_text(
        json.dumps({"updated_at": generated, "batches": batches}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (site_dir / "index.html").write_text(index_html(batches, generated), encoding="utf-8")
    return batch
