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
    "行动": "每次行动的位置、动作、下注额",
    "文字": "昵称、位置",
    "图像": "dealer、status、头像",
    "数字": "筹码、座位、底池、盲注",
}


def help_fold(text: str, extra_class: str = "") -> str:
    cls = "help-fold" + (f" {extra_class}" if extra_class else "")
    return f'<details class="{cls}"><summary>说明</summary><p>{text}</p></details>'

COMMON_CSS = """
:root {
  --bg:#eef2f6; --panel:#fff; --ink:#1d2733; --muted:#64748b; --line:#dde4ec;
  --accent:#1f8a70; --accent-soft:#e5f4ef; --fill:#1f8a70; --zero:#f4f7fa;
  --note:#e5f4ef; --gap:#fff4e5; --head:#f4f7fa;
  --side:#1d2733; --pending:#e08a2e; --ok:#2fa08c; --bad:#d64545;
  --hero:#d9a400; --hero-soft:#fff7e0;
  --act-fold:#8b95a1; --act-check:#4a90d9; --act-call:#2fa08c; --act-bet:#e08a2e;
  --act-raise:#a55eea; --act-allin:#d64545; --act-show:#3c9d4f;
  --shadow:0 1px 3px rgba(15,30,50,.08), 0 6px 18px rgba(15,30,50,.06);
  --fs:13px; --fs-sm:12px; --fs-xs:11px; --fs-md:14px; --fs-lg:16px; --fs-xl:20px;
}
* { box-sizing:border-box; }
html,body { margin:0; min-height:100%; overflow-x:hidden; }
body { font-family:system-ui,"PingFang SC","Microsoft YaHei","Noto Sans SC",sans-serif;
  background:var(--bg); color:var(--ink); line-height:1.45; font-size:var(--fs); }
a { color:var(--accent); }
input, select, button { accent-color:var(--accent); }
.app { display:grid; grid-template-columns:188px 1fr; min-height:100vh; }
.side { background:var(--side); color:#d7e0e8; padding:14px 10px 20px; position:sticky; top:0; height:100vh; }
.side .kicker { font-size:10px; letter-spacing:.16em; text-transform:uppercase; color:#8fa0b2; }
.side .brand { font-size:14px; font-weight:700; color:#fff; margin:4px 0 14px;
  display:flex; align-items:center; gap:8px; }
.side .brand::before { content:""; width:8px; height:8px; border-radius:50%; background:var(--accent);
  box-shadow:0 0 0 4px rgba(31,138,112,.28); }
.side nav a { display:block; padding:6px 10px; border-radius:8px; color:#c5d0da;
  text-decoration:none; font-size:13px; margin-bottom:2px; }
.side nav a:hover { background:#2a343d; color:#fff; }
.side nav a.active { background:var(--accent); color:#fff; }
.main { padding:14px 18px 32px; max-width:1280px; }
.main.is-index { max-width:1880px; padding:20px 24px 40px; }
.main.is-index .page-head { margin-bottom:16px; }
.main.is-index .page-head h1 { font-size:20px; }
.main.is-index .page-head .sub { margin:4px 0 0; }
.main.is-lookup { max-width:none; padding:14px 18px 32px; }
@media (max-width:900px) {
  .app { grid-template-columns:1fr; }
  .side { position:relative; height:auto; }
}
h1 { font-size:var(--fs-lg); font-weight:700; margin:0 0 2px; letter-spacing:-.02em; }
h2 { margin:0; font-size:var(--fs-md); font-weight:650; }
.sub { color:var(--muted); margin:0 0 6px; max-width:82ch; font-size:var(--fs-sm); }
.page-head { display:flex; flex-wrap:wrap; gap:8px; justify-content:space-between; align-items:flex-start; margin-bottom:8px; }
.page-head h1 { margin:0; }
.page-meta { display:flex; flex-wrap:wrap; gap:4px; margin:6px 0 0; }
.page-meta span { display:inline-flex; align-items:center; gap:4px; font-size:var(--fs-sm); color:var(--muted);
  background:#fff; border:1px solid var(--line); border-radius:99px; padding:2px 8px; }
.page-meta code { font-size:var(--fs-sm); color:var(--ink); }
.btn { display:inline-flex; align-items:center; background:var(--accent); color:#fff !important;
  text-decoration:none; border:1px solid var(--accent); border-radius:8px; padding:6px 12px; font-weight:650; font-size:13px;
  cursor:pointer; font-family:inherit; }
.btn:hover { opacity:.92; }
.btn-ghost { display:inline-flex; align-items:center; border:1px solid var(--line); background:#fff;
  color:var(--ink) !important; text-decoration:none; border-radius:8px; padding:6px 12px; font-size:13px;
  cursor:pointer; font-family:inherit; }
.btn-ghost:hover { background:var(--accent-soft); border-color:var(--accent); color:var(--accent) !important; }
.btn:disabled, .btn-ghost:disabled { opacity:.5; cursor:not-allowed; }
[hidden] { display:none !important; }
.cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(120px,1fr)); gap:8px; margin-bottom:4px; }
.card { background:var(--panel); border:1px solid var(--line); border-radius:11px; padding:10px 12px; box-shadow:var(--shadow); }
.card .label { color:var(--muted); font-size:var(--fs-sm); }
.card .value { font-size:var(--fs-xl); font-weight:700; margin-top:2px; font-variant-numeric:tabular-nums; color:var(--accent); }
.card .hint { font-size:var(--fs-sm); color:var(--muted); margin-top:2px; }
.section { background:var(--panel); border:1px solid var(--line); border-radius:10px;
  padding:12px 14px 10px; margin-top:10px; box-shadow:var(--shadow); }
.section-head { display:flex; justify-content:space-between; gap:10px; align-items:flex-start;
  margin:0 0 8px; padding:0 0 6px; border-bottom:1px solid var(--line); }
.section-head p { margin:0; color:var(--muted); font-size:var(--fs-sm); line-height:1.45; max-width:72ch; }
.help-fold { margin:0; max-width:72ch; }
.help-fold > summary {
  cursor:pointer; color:var(--muted); font-size:var(--fs-sm); font-weight:650;
  list-style:none; user-select:none; text-align:right;
}
.help-fold > summary::-webkit-details-marker { display:none; }
.help-fold > summary::after { content:" ▾"; font-size:10px; }
.help-fold[open] > summary::after { content:" ▴"; }
.help-fold p { margin:6px 0 0; color:var(--muted); font-size:var(--fs-sm); line-height:1.45;
  text-align:left; max-width:72ch; }
.seq-kicker { margin:8px 0 4px; font-size:11px; color:var(--muted); line-height:1.4; }
details.seq-kicker > summary { font-size:11px; }
.board-row { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:6px; }
@media (max-width:760px) { .board-row { grid-template-columns:1fr; } }
.board-row .rate-cell { display:grid; grid-template-columns:1fr auto; align-items:center; gap:0 10px;
  padding:6px 10px; border:1px solid var(--line); border-radius:8px; background:var(--head);
  text-align:left; text-decoration:none; color:inherit; }
.board-row .rate-lab { font-size:12px; font-weight:650; color:var(--ink); }
.board-row .rate { font-size:20px; font-weight:700; text-align:right; margin:0; line-height:1.05;
  font-variant-numeric:tabular-nums; grid-row:1 / span 2; color:var(--accent); }
.board-row .rate-hint { grid-column:1 / 2; margin:0; font-size:11px; color:var(--muted); }
.board-row .rate-cell:hover { background:var(--accent-soft); border-color:var(--accent); }
.board-row .rate-cell.active { background:var(--accent-soft); border-color:var(--accent);
  box-shadow:inset 3px 0 0 var(--accent); outline:none; }
.seq-lines { display:grid; gap:0; font-size:11px; line-height:1.35;
  font-variant-numeric:tabular-nums; white-space:nowrap; }
.seq-ok { color:var(--ok); }
.seq-bad { color:var(--bad); }
.seq-miss { color:var(--pending); }
.seq-na { color:var(--muted); }
.hand-mod-scroll { max-height:220px; }
table.list th, table.list td { padding:5px 8px; font-size:12px; }
.grid2 { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
@media (max-width:860px) { .grid2 { grid-template-columns:1fr; } }
.bar-row { display:grid; grid-template-columns:72px 1fr 40px 48px; gap:8px; align-items:center; margin:5px 0; font-size:13px; }
.bar-lab { color:var(--ink); }
.bar-track { height:8px; background:var(--head); border-radius:99px; overflow:hidden; }
.bar-fill { display:block; height:100%; background:var(--fill); }
.bar-n,.bar-p { font-variant-numeric:tabular-nums; color:var(--muted); text-align:right; }
.note,.gap { font-size:13px; padding:10px 12px; border-radius:10px; margin:0 0 12px; }
.note { background:var(--note); }
.gap { background:var(--gap); }
.align-note { display:flex; flex-wrap:wrap; gap:6px 16px; align-items:flex-end;
  font-size:12px; color:var(--ink); margin:0; padding:8px 12px;
  background:var(--accent-soft); border:1px solid var(--accent); border-radius:10px; box-shadow:none; }
.align-note > b { color:var(--muted); font-size:10px; font-weight:650; letter-spacing:.08em;
  text-transform:uppercase; align-self:center; }
.align-note .align-cell { display:flex; flex-direction:column; gap:0; min-width:4em; }
.align-note .align-cell .lab { font-size:10px; color:var(--muted); }
.align-note .align-cell strong { color:var(--ink); font-variant-numeric:tabular-nums; font-size:16px; font-weight:700; }
.align-note > span { color:var(--muted); font-size:12px; align-self:center; }
.align-note.is-bad { background:#fff7ed; border-color:#fdba74; }
.align-note .align-miss { flex-basis:100%; margin-top:2px; font-size:12px; color:var(--bad); }
.align-note .align-miss.is-rej { color:#9a3412; }
.align-note .align-miss .err-link { font-size:12px; }
.reject-banner { margin:0 0 8px; padding:10px 12px; background:#fff7ed; border:1px solid #fdba74;
  border-radius:8px; flex-shrink:0; }
.reject-banner[hidden] { display:none; }
.reject-banner .reject-title { display:flex; flex-wrap:wrap; gap:4px 12px; align-items:baseline; }
.reject-banner .reject-title b { color:#9a3412; font-size:14px; }
.reject-banner .reject-title span { color:#9a3412; font-size:12px; }
.reject-banner .reject-reason { margin:6px 0 0; font-size:13px; color:#7c2d12; line-height:1.45; }
.reject-banner details.reject-more { margin-top:6px; font-size:13px; color:#7c2d12; }
.reject-banner details.reject-more summary { cursor:pointer; color:#9a3412; font-size:12px; }
table.err-seq { border:1px solid var(--line); border-radius:10px; overflow:hidden; }
table.err-seq th { background:var(--head); color:var(--accent); font-size:12px; padding:8px 10px; }
table.err-seq td { padding:8px 10px; font-size:13px; }
table.err-seq td.pending { color:var(--muted); font-weight:400; }
table.err-seq td.val { font-family:ui-monospace,Consolas,monospace; font-size:12px;
  max-width:240px; overflow-wrap:anywhere; }
.pair-tabs { display:flex; flex-wrap:wrap; gap:0; margin:0 0 6px; border-bottom:1px solid var(--line); }
.pair-tab { font:inherit; border:none; border-bottom:2px solid transparent; background:transparent;
  border-radius:0; padding:6px 12px; cursor:pointer; font-size:13px; font-weight:650; color:var(--muted); }
.pair-tab.active { color:var(--accent); border-bottom-color:var(--accent); background:transparent; }
.pair-tab .pair-rate { display:block; font-size:11px; font-weight:500; margin-top:1px; }
table.fields { font-size:12px; line-height:1.2; width:100%; }
table.fields thead th { background:var(--head); color:var(--accent); position:sticky; top:0; z-index:2;
  white-space:nowrap; padding:4px 6px; font-size:11px; font-weight:650; border-bottom:1px solid var(--line); width:1%; }
table.fields th, table.fields td { padding:2px 6px; vertical-align:middle; }
table.fields td.path { font-size:12px; font-weight:650; white-space:nowrap; width:1%; }
table.fields th.num, table.fields td.num { width:1%; white-space:nowrap; padding:2px 8px; }
table.fields th.gutter, table.fields td.gutter { width:99%; padding:0; border:none; background:transparent; }
table.fields td.map { font-size:11px; font-weight:400; font-family:ui-monospace,Consolas,monospace;
  color:var(--muted); width:1%; white-space:nowrap; }
table.fields td.map i { font-style:normal; font-weight:650; color:var(--accent); }
table.fields tr.is-leaf td.path { padding-left:14px; font-weight:500; }
table.fields tr.sec td { background:var(--accent-soft); font-weight:700; font-size:11px; color:var(--accent);
  padding:3px 6px; border-bottom:1px solid var(--line); }
table.fields tr.act td { background:var(--head); font-weight:650; font-size:11px; color:var(--muted);
  padding:2px 6px 2px 10px; }
table.fields td.rate-ok { color:var(--ok); font-weight:650; }
table.fields td.rate-bad { color:var(--bad); font-weight:650; }
table.fields th.pair-hi { background:var(--accent-soft); color:var(--accent); }
table.fields td.pair-hi { background:var(--accent-soft); }
table.fields td .err-link { font-size:12px; }
tr.cat-head td { background:var(--head); font-weight:700; font-size:12px; padding:5px 8px;
  border-bottom:1px solid var(--line); scroll-margin-top:8px; }
tr.cat-head .cat-kpi { font-weight:500; margin-left:8px; }
.field-jump { display:flex; flex-wrap:wrap; gap:3px; margin:0 0 6px; }
.field-jump a { font-size:11px; font-weight:650; color:var(--muted); background:var(--head);
  border:1px solid var(--line); border-radius:99px; padding:2px 7px; text-decoration:none; }
.field-jump a:hover { color:var(--accent); border-color:var(--accent); background:var(--accent-soft); }
.field-jump a .n { font-weight:500; margin-left:4px; color:var(--muted); }
#fields-block { margin-bottom:0; }
.cat-kpi { font-size:12px; color:var(--muted); font-variant-numeric:tabular-nums; }
.cat-kpi b { font-variant-numeric:tabular-nums; }
.cat-kpi b.ok { color:var(--ok); }
.cat-kpi b.bad { color:var(--bad); }
.pill { display:inline-block; padding:1px 8px; border-radius:99px; font-size:var(--fs-sm); font-weight:650;
  white-space:nowrap; }
.pill.卡牌 { background:#dbeafe; color:#1e40af; }
.pill.行动 { background:var(--accent-soft); color:var(--accent); }
.pill.文字 { background:#ffedd5; color:var(--pending); }
.pill.图像 { background:#ede9fe; color:#5b21b6; }
.pill.数字 { background:var(--accent-soft); color:var(--ok); }
.pending { color:var(--pending); font-weight:650; }
table { width:100%; border-collapse:collapse; font-size:13px; }
th,td { padding:6px 8px; border-bottom:1px solid var(--line); text-align:left; }
th { color:var(--accent); font-weight:650; background:var(--head); }
td.num, th.num { text-align:right; font-variant-numeric:tabular-nums; }
table.cross td, table.cross th { text-align:center; }
table.cross th:first-child, table.cross td:first-child { text-align:left; }
table.cross td.zero { color:var(--muted); background:var(--zero); }
table.cross td.sum, table.cross tfoot td { font-weight:650; }
.table-scroll { overflow:auto; }
.toolbar { display:flex; flex-wrap:wrap; gap:6px; margin:0 0 6px; align-items:center; }
.toolbar label { display:flex; align-items:center; gap:6px; font-size:12px; color:var(--muted); }
select, input[type=search] { font:inherit; border:1px solid var(--line); background:#fff; border-radius:6px; padding:5px 8px; }
#count, #field-count, #origin-count, #hand-mod-count { color:var(--muted); font-size:12px; }
.list th { position:sticky; top:0; }
.list td.name { max-width:420px; }
code { font-size:12px; }
.board-wrap { overflow:auto; background:#fff; border:1px solid var(--line); border-radius:14px; }
table.board { border-collapse:separate; border-spacing:0; min-width:420px; }
table.board thead th { background:var(--head); color:var(--accent); font-size:12px; text-align:center; padding:10px 8px; }
table.board thead th:first-child { text-align:left; }
table.board td, table.board tbody th { border-bottom:1px solid var(--line); padding:0; vertical-align:stretch; }
table.board tbody th { text-align:left; padding:12px 14px; font-size:13px; background:var(--head); width:132px; }
.rate-cell { display:block; text-decoration:none; color:inherit; padding:8px 10px; text-align:center; }
.rate-cell:hover { background:var(--accent-soft); }
.rate-cell.active { background:var(--accent-soft); outline:2px solid var(--accent); outline-offset:-2px; }
.rate { font-size:16px; font-weight:750; font-variant-numeric:tabular-nums; line-height:1.2; color:var(--accent); }
.rate.is-empty { min-height:1.2em; }
.rate.is-dash { color:var(--muted); }
.rate-hint { font-size:11px; color:var(--muted); margin-top:4px; }
td.cat-卡牌 { box-shadow:inset 3px 0 0 #2563eb; }
td.cat-行动 { box-shadow:inset 3px 0 0 var(--accent); }
td.cat-文字 { box-shadow:inset 3px 0 0 #ea580c; }
td.cat-图像 { box-shadow:inset 3px 0 0 #7c3aed; }
td.cat-数字 { box-shadow:inset 3px 0 0 #16a34a; }
.legend { display:flex; flex-wrap:wrap; gap:10px 16px; margin:10px 0 0; font-size:12px; color:var(--muted); }
.legend span { display:inline-flex; align-items:center; gap:6px; }
.legend i { width:8px; height:8px; border-radius:99px; display:inline-block; }
.legend i.卡牌 { background:#2563eb; }
.legend i.行动 { background:var(--accent); }
.legend i.文字 { background:#ea580c; }
.legend i.图像 { background:#7c3aed; }
.legend i.数字 { background:#16a34a; }
.batch-table { margin-top:8px; }
.batch-table td.rates { font-variant-numeric:tabular-nums; font-size:12px; }
.tabs { display:flex; flex-wrap:wrap; gap:0; border-bottom:1px solid var(--line); margin:0 0 10px; }
.tab { font:inherit; background:transparent; border:none; border-bottom:2px solid transparent;
  padding:7px 12px; cursor:pointer; color:var(--muted); font-weight:650; font-size:13px; }
.tab:hover { color:var(--ink); }
.tab.active { color:var(--accent); border-bottom-color:var(--accent); }
.panel { display:none; }
.panel.active { display:block; }
.records-panel { background:#fff; border:1px solid var(--line); border-radius:14px;
  box-shadow:var(--shadow); overflow:hidden; }
.records-panel .table-scroll { overflow:auto; }
table.records { width:100%; background:#fff; border:none; border-radius:0;
  overflow:visible; border-collapse:separate; border-spacing:0; }
table.records thead th { background:#f8fafb; color:#64748b; font-size:11px; font-weight:600;
  white-space:nowrap; letter-spacing:.02em; }
table.records th, table.records td { padding:9px 10px; vertical-align:middle; border-bottom:1px solid #eef1f4; }
table.records tbody tr:last-child td { border-bottom:none; }
table.records th.file, table.records td.file { padding-right:12px; white-space:nowrap; width:1%; }
table.records td.file { font-weight:600; color:var(--ink); }
table.records th.num, table.records td.num { padding-left:10px; padding-right:12px; text-align:right;
  font-variant-numeric:tabular-nums; width:1%; }
table.records td.num { color:var(--muted); font-weight:500; }
table.records thead th.g { text-align:center; font-size:12px; font-weight:700; letter-spacing:.04em;
  border-bottom:none; padding:10px 10px 8px; }
table.records thead th.g .g-dot { display:inline-block; width:6px; height:6px; border-radius:50%;
  margin-right:6px; vertical-align:middle; background:currentColor; }
table.records thead tr.sub th { font-weight:600; text-align:right; padding:5px 8px 8px; color:#7b8794; }
table.records thead tr.sub th.exact-all { white-space:normal; max-width:7.4em; line-height:1.25;
  vertical-align:bottom; padding-top:4px; }
table.records thead th.g.vis-g { color:#1f8a70; background:#f3faf7;
  box-shadow:inset 0 -2px 0 #1f8a70; }
table.records thead tr.sub th.vis-g { color:#5b8f82; background:#f7fbf9; }
table.records td.vis-g { background:#fcfefd; }
table.records thead th.g.rule-g { color:#5b6470; background:#f4f6f8;
  box-shadow:inset 0 -2px 0 #94a3b8; }
table.records thead tr.sub th.rule-g { color:#7b8490; background:#f7f8fa; }
table.records td.rule-g { background:#fbfcfd; }
table.records tbody tr:hover td { background:#f6f8fa; }
table.records tbody tr:hover td.vis-g { background:#f1f7f4; }
table.records tbody tr:hover td.rule-g { background:#f3f5f8; }
table.records th.rule-g.start, table.records td.rule-g.start { padding-left:14px; }
table.records th.meta, table.records td.meta { padding-left:14px; width:1%; white-space:nowrap; }
table.records td.meta { color:#475569; }
table.records th.vis-g.end, table.records td.vis-g.end { padding-right:14px; }
table.records td.pct { font-variant-numeric:tabular-nums; white-space:nowrap; font-size:12px;
  text-align:right; padding:9px 8px; min-width:4.6em; color:#475569; }
table.records td.pct.all { font-size:13px; font-weight:700; color:var(--ink); }
table.records td.pct.hi { color:#1f8a70; }
table.records td.pct.lo { color:#c2410c; }
table.records td.pct.zero { color:#94a3b8; }
table.records td.pct.wait-span { text-align:center; min-width:0; }
table.records .waiting { display:inline-block; color:#a16207; background:#fffbeb;
  border:1px solid #fde68a; border-radius:99px; padding:1px 8px; font-weight:600; font-size:11px; }
table.records td.remark { color:var(--muted); font-size:11px; font-weight:400; max-width:12em;
  overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
table.records th.time, table.records td.time { white-space:nowrap; color:var(--muted); width:1%;
  font-variant-numeric:tabular-nums; padding-left:14px; }
table.records td.detail { width:1%; white-space:nowrap; text-align:right; padding-right:14px; }
table.records td.detail a { display:inline-flex; align-items:center; padding:3px 10px;
  border-radius:7px; background:var(--accent-soft); color:var(--accent); text-decoration:none;
  font-weight:650; font-size:12px; }
table.records td.detail a:hover { background:var(--accent); color:#fff; }
.work-card { background:#fff; border:1px solid var(--line); border-radius:14px; padding:14px 16px;
  margin-bottom:12px; box-shadow:var(--shadow); }
.filters { display:flex; flex-wrap:wrap; gap:10px 12px; align-items:flex-end; margin:0; }
.filters label { display:flex; flex-direction:column; gap:4px; font-size:12px; color:var(--muted); }
.filters input, .filters select { font:inherit; border:1px solid transparent; background:#f4f6f8;
  border-radius:8px; padding:7px 10px; min-width:140px; color:var(--ink); }
.filters input:focus, .filters select:focus { background:#fff; border-color:var(--accent);
  outline:none; box-shadow:0 0 0 3px rgba(31,138,112,.14); }
.filter-actions { display:flex; gap:8px; align-items:center; margin-left:auto; }
.filter-split { width:1px; height:28px; background:var(--line); margin:0 2px; }
.lookup-status { margin:10px 0 0; font-size:13px; color:var(--muted); }
.lookup-status:empty { display:none; }
.pager { display:flex; flex-wrap:wrap; align-items:center; gap:10px; margin:0; padding:12px 14px;
  font-size:13px; color:#6b7280; border-top:1px solid #eef1f4; background:#fafbfc; }
.pager-btns { display:flex; gap:6px; align-items:center; }
.pager-btn { min-width:32px; height:32px; padding:0 8px; border:1px solid var(--line); border-radius:8px;
  background:#fff; color:var(--ink); cursor:pointer; font:inherit; }
.pager-btn:hover:not(:disabled):not(.current) { border-color:var(--accent); color:var(--accent); }
.pager-btn.current { background:var(--accent); color:#fff; border-color:var(--accent); font-weight:650; }
.pager-btn:disabled { opacity:.4; cursor:not-allowed; }
.pager-size { display:flex; align-items:center; gap:8px; margin-left:auto; }
.pager-size select { background:#fff; }
.cat-blocks { margin-top:0; }
.cat-blocks .fields-wrap { border:1px solid var(--line); border-radius:8px; }
.hand-grid-wrap { overflow:auto; max-height:calc(100vh - 210px); border:1px solid var(--line); border-radius:8px; }
table.hand-grid { width:max-content; border-collapse:separate; border-spacing:0; font-size:var(--fs-sm); }
table.hand-grid th, table.hand-grid td { padding:4px 6px; border-bottom:1px solid var(--line); border-right:1px solid var(--head);
  white-space:nowrap; vertical-align:middle; width:1%; }
table.hand-grid thead th { position:sticky; top:0; z-index:3; background:var(--head); font-size:var(--fs-sm); font-weight:650; color:var(--accent); }
table.hand-grid thead tr.g th { top:0; z-index:5; background:var(--head); text-align:center; color:var(--accent);
  letter-spacing:0; border-bottom:1px solid var(--line); font-size:var(--fs-sm); font-weight:700; padding:6px 8px; }
table.hand-grid thead tr.sub th { top:30px; z-index:4; }
table.hand-grid thead tr.foot-vis td, table.hand-grid thead tr.foot-rule td {
  position:sticky; z-index:3; background:var(--head); font-size:var(--fs-sm); font-weight:400;
  font-variant-numeric:tabular-nums; }
table.hand-grid thead tr.foot-vis td { top:60px; }
table.hand-grid thead tr.foot-rule td { top:88px; border-bottom:2px solid var(--line); }
table.hand-grid thead tr.foot-vis td.rate, table.hand-grid thead tr.foot-rule td.rate { font-weight:400; }
table.hand-grid thead tr.foot-vis td.src, table.hand-grid thead tr.foot-rule td.src { font-weight:500; color:var(--muted); }
table.hand-grid thead tr.foot-vis td.is-ok, table.hand-grid thead tr.foot-rule td.is-ok,
table.hand-grid thead tr.foot-vis td.is-miss, table.hand-grid thead tr.foot-rule td.is-miss { color:inherit; }
table.hand-grid thead tr.foot-vis td.pin,
table.hand-grid thead tr.foot-vis td.pin-id,
table.hand-grid thead tr.foot-vis td.pin-src,
table.hand-grid thead tr.foot-vis td.pin-hero,
table.hand-grid thead tr.foot-rule td.pin,
table.hand-grid thead tr.foot-rule td.pin-id,
table.hand-grid thead tr.foot-rule td.pin-src,
table.hand-grid thead tr.foot-rule td.pin-hero {
  z-index:8; background:var(--head); }
table.hand-grid thead tr.g th.pin, table.hand-grid thead tr.g th.pin-id,
table.hand-grid thead tr.g th.pin-src, table.hand-grid thead tr.g th.pin-hero {
  z-index:6; background:var(--head); text-align:left; letter-spacing:0; vertical-align:middle; }
table.hand-grid th.pin, table.hand-grid td.pin { position:sticky; left:0; z-index:2; background:#fff;
  box-sizing:border-box; min-width:40px; width:40px; max-width:40px; }
table.hand-grid th.pin-id, table.hand-grid td.pin-id { position:sticky; left:40px; z-index:2; background:#fff;
  box-sizing:border-box; min-width:108px; width:108px; max-width:108px; overflow:hidden; text-overflow:ellipsis; }
table.hand-grid th.pin-src, table.hand-grid td.pin-src { position:sticky; left:148px; z-index:2; background:#fff;
  box-sizing:border-box; min-width:88px; width:88px; max-width:88px; }
table.hand-grid th.pin-hero, table.hand-grid td.pin-hero { position:sticky; left:236px; z-index:2; background:#fff;
  box-sizing:border-box; min-width:76px; width:76px; }
table.hand-grid thead th.pin, table.hand-grid thead th.pin-id, table.hand-grid thead th.pin-src,
table.hand-grid thead th.pin-hero, table.hand-grid thead td.pin, table.hand-grid thead td.pin-id,
table.hand-grid thead td.pin-src, table.hand-grid thead td.pin-hero {
  z-index:6; background:var(--head); }
table.hand-grid td.pin-hero { box-shadow:1px 0 0 var(--line); }
table.hand-grid td[rowspan] { vertical-align:middle; }
table.hand-grid tr.side-vis td { background:var(--head); }
table.hand-grid tr.side-vis td.pin,
table.hand-grid tr.side-vis td.pin-id,
table.hand-grid tr.side-vis td.pin-src,
table.hand-grid tr.side-vis td.pin-hero { background:var(--head); }
table.hand-grid tr.hand-end td { border-bottom:2px solid var(--line); }
table.hand-grid td.src { font-weight:650; color:var(--muted); }
table.hand-grid tr.side-vis td.src { color:var(--accent); }
table.hand-grid tr.side-rule td.src { color:#6d28d9; }
table.hand-grid td.is-pending { color:var(--muted); }
table.hand-grid .g-span { text-align:center; letter-spacing:.04em; background:var(--head); border-left:1px solid var(--line); }
table.hand-grid thead tr.sub th.pos-lab { font-size:11px; letter-spacing:0; }
table.hand-grid .occ-ok { color:var(--muted); }
table.hand-grid td.is-empty { color:var(--line); }
table.hand-grid td.is-ok { color:var(--ok); }
table.hand-grid td.is-vis { background:#fff7ed; }
table.hand-grid td.is-rule { background:#fef2f2; color:var(--bad); }
table.hand-grid td.is-click { cursor:pointer; }
table.hand-grid td.is-click:hover { outline:1px solid var(--accent); outline-offset:-1px; }
table.hand-grid .pcard { min-width:22px; height:22px; font-size:var(--fs-sm); padding:0 4px; }
table.hand-grid td.seq { font-variant-numeric:tabular-nums; max-width:9em; overflow:hidden; text-overflow:ellipsis; }
table.hand-grid td.rate { font-variant-numeric:tabular-nums; font-weight:650; }
table.hand-grid td.acc { background:#fff; color:inherit; }
table.hand-grid tfoot td { font-size:var(--fs-sm); font-weight:400; font-variant-numeric:tabular-nums;
  background:#fff; border-top:1px solid var(--line); }
.cat-block { background:#fff; border:1px solid var(--line); border-radius:8px; overflow:hidden;
  scroll-margin-top:8px; }
.cat-headbar { display:flex; flex-wrap:wrap; align-items:baseline; gap:4px 8px;
  padding:5px 8px; background:var(--head); border-bottom:1px solid var(--line); }
.cat-headbar h3 { margin:0; font-size:12px; font-weight:650; flex:1; }
.cat-block .table-scroll { max-height:none; }
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
.modal-file { border:1px dashed var(--line); border-radius:10px; padding:14px; background:var(--head);
  font-size:13px; color:var(--muted); cursor:pointer; }
.modal-file strong { color:var(--ink); font-weight:650; }
.modal-actions { display:flex; justify-content:flex-end; gap:8px; padding:0 20px 18px; }
.err-link { background:none; border:none; color:var(--accent); cursor:pointer; font:inherit; font-weight:650; padding:0; }
.err-link:hover { text-decoration:underline; }
.drawer-mask { position:fixed; inset:0; background:rgba(15,23,42,.4); z-index:90;
  display:none; justify-content:flex-end; align-items:flex-start; overflow:auto; }
.drawer-mask.show { display:flex; }
.drawer { width:max(100%, max-content); min-width:100%; max-width:none; background:#fff; height:auto;
  min-height:100%; max-height:none; overflow:visible; padding:6px 8px 16px; box-sizing:border-box;
  box-shadow:-12px 0 40px rgba(15,23,42,.18); display:flex; flex-direction:column; }
.drawer-head { display:flex; justify-content:space-between; align-items:flex-start; gap:8px; margin-bottom:4px; flex-shrink:0;
  position:sticky; top:0; z-index:5; background:#fff; padding-top:2px; }
.drawer-head h3 { margin:0 0 2px; font-size:var(--fs-lg); font-weight:700; word-break:break-all; }
.drawer-actions { display:flex; gap:6px; flex-shrink:0; }
.drawer-filter { display:flex; align-items:center; gap:6px; font-size:var(--fs-sm); color:var(--muted); margin:0 0 4px; flex-shrink:0;
  position:relative; z-index:3; background:#fff; }
#drawer-status { flex-shrink:0; margin:0 0 4px; font-size:var(--fs-sm); position:relative; z-index:3; background:#fff; }
#drawer-help { flex-shrink:0; margin:0 0 4px; max-width:none; position:relative; z-index:3; background:#fff; }
.drawer-clip { flex-shrink:0; margin:0 0 6px; border:1px solid var(--line); border-radius:8px; overflow:hidden; background:var(--side);
  position:relative; z-index:30; }
.drawer-clip[hidden] { display:none; }
.drawer-clip > summary.clip-bar { display:flex; justify-content:space-between; align-items:center; gap:8px;
  padding:5px 10px; background:var(--side); color:#d7e0e8; font-size:var(--fs-sm); cursor:pointer; list-style:none; user-select:none; }
.drawer-clip > summary.clip-bar::-webkit-details-marker { display:none; }
.drawer-clip > summary.clip-bar::before { content:"▸ "; color:#8fa0b2; flex-shrink:0; }
.drawer-clip[open] > summary.clip-bar::before { content:"▾ "; }
.drawer-clip .clip-bar a, .drawer-clip .clip-pip { color:#9ed9c8; text-decoration:none; flex-shrink:0;
  background:none; border:none; padding:0; font:inherit; font-weight:650; cursor:pointer; }
.drawer-clip .clip-bar a:hover, .drawer-clip .clip-pip:hover { text-decoration:underline; }
.drawer-clip .clip-bar-actions { display:flex; align-items:center; gap:10px; flex-shrink:0; }
.drawer-clip .clip-pip[hidden] { display:none; }
.drawer-clip video { display:block; width:100%; max-height:240px; background:#000; }
.drawer-clip:not([open]) video,
.drawer-clip:not([open]) .clip-url { display:none; }
.drawer-clip .clip-url { display:block; padding:6px 10px 8px; background:var(--side); color:#9ed9c8;
  font-size:var(--fs-xs); font-family:ui-monospace,Menlo,Consolas,monospace; line-height:1.4;
  word-break:break-all; text-decoration:none; }
#drawer-roster { flex:0 0 auto; min-width:max-content; max-height:none; overflow:visible; margin:0 0 4px;
  position:relative; z-index:2; background:#fff; }
#drawer-roster:empty { display:none; margin:0; }
#drawer-body { flex:0 0 auto; min-width:max-content; min-height:0; overflow:visible;
  padding:0 0 12px; position:relative; z-index:1; }
.lookup-grid { display:grid; grid-template-columns:220px minmax(0,1fr); gap:16px; align-items:start; }
@media (max-width:900px) { .lookup-grid { grid-template-columns:1fr; } }
.lookup-side { margin-top:0; padding:12px 0 0; position:sticky; top:12px; }
.lookup-side .hand-list { max-height:calc(100vh - 220px); }
.hand-head { display:flex; flex-wrap:wrap; justify-content:space-between; gap:10px; align-items:flex-start; margin-bottom:12px; }
.hand-head h2 { font-size:1.15rem; word-break:break-all; }
.hand-list { max-height:calc(100vh - 200px); overflow:auto; }
.hand-list button { display:block; width:100%; text-align:left; background:#fff; border:none;
  border-bottom:1px solid var(--line); padding:10px 12px; cursor:pointer; font:inherit; }
.hand-list button:hover { background:var(--accent-soft); }
.hand-list button.active { background:var(--accent-soft); }
.hand-list .hid-row { display:flex; align-items:baseline; gap:6px; }
.hand-list .idx { font-size:11px; color:var(--muted); font-variant-numeric:tabular-nums; flex-shrink:0; }
.hand-list .hid { font-family:ui-monospace,Consolas,monospace; font-size:12px; color:var(--ink);
  overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.hand-list .meta { display:flex; align-items:center; gap:6px; margin-top:4px; }
.st { display:inline-block; padding:1px 7px; border-radius:99px; font-size:11px; font-weight:650; background:var(--head); color:var(--muted); }
.st.ok { background:var(--accent-soft); color:var(--ok); }
.st.bad { background:#fee2e2; color:var(--bad); }
.stage-split { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
@media (max-width:1100px) { .stage-split { grid-template-columns:1fr; } }
.stage-col { min-width:0; }
.stage-head { display:flex; justify-content:space-between; align-items:center; gap:8px; margin:0 0 8px; }
.stage-head h3 { margin:0; font-size:13px; }
.json-fold { margin:0 0 16px; border:1px solid var(--line); border-radius:12px; background:var(--head); overflow:hidden; }
.json-fold > summary { cursor:pointer; padding:12px 16px; font-size:14px; font-weight:650; color:var(--ink);
  display:flex; align-items:center; gap:8px; list-style:none; }
.json-fold > summary::-webkit-details-marker { display:none; }
.json-fold > summary::before { content:"▸"; color:var(--muted); font-size:12px; }
.json-fold[open] > summary::before { content:"▾"; }
.json-fold > summary .hint { font-weight:500; color:var(--muted); font-size:12px; }
.json-fold > summary .raw-lab { flex:1; min-width:0; }
.json-fold > summary .btn-ghost { margin-left:auto; flex-shrink:0; }
.json-fold .stage-split { padding:0 14px 14px; }
.json-fold > pre.json-view { margin:0 14px 14px; max-height:28vh; }
.raw-json { margin-top:16px; display:grid; grid-template-columns:repeat(3, minmax(0,1fr));
  gap:10px; align-items:start; }
.raw-json-title { grid-column:1 / -1; margin:8px 0 0; font-size:14px; font-weight:650; }
.raw-json .json-fold { margin:0; min-width:0; }
.raw-json .json-fold > summary { padding:10px 12px; font-size:13px; }
.raw-json .json-fold > pre.json-view { margin:0 10px 10px; max-height:40vh; }
@media (max-width:900px) {
  .raw-json { grid-template-columns:1fr; }
}
.pcard { display:inline-flex; align-items:center; justify-content:center; min-width:26px; height:24px;
  padding:0 6px; border-radius:5px; background:#fff; border:1px solid #d1d5db; font-weight:650; font-size:var(--fs);
  font-family:inherit; letter-spacing:0; }
.pcard.s, .pcard.c { color:#111827; }
.pcard.h, .pcard.d { color:#dc2626; }
.pcard.unk { color:#9ca3af; background:#f9fafb; }
.hv-miss { color:var(--muted); padding:16px 0; font-size:14px; }
.json-view { font-family:ui-monospace,Menlo,Consolas,monospace; font-size:11px; line-height:1.45;
  background:var(--side); color:#e5e7eb; padding:12px 14px; border-radius:10px;
  overflow:auto; max-height:36vh; white-space:pre; margin:0; }
.json-empty { color:var(--muted); padding:28px 8px; font-size:14px; }
.cmp-banner { display:flex; flex-wrap:wrap; align-items:center; gap:8px 12px; margin:0 0 16px;
  padding:12px 14px; border-radius:12px; background:var(--accent-soft); border:1px solid var(--accent); font-size:13px; }
.cmp-banner.is-diff { background:#fff7ed; border-color:#fdba74; }
.cmp-banner strong { font-size:14px; }
.cmp-pills { display:flex; flex-wrap:wrap; gap:6px; }
.cmp-pill { background:#fff; border:1px solid #fed7aa; color:var(--bad); border-radius:99px;
  padding:2px 10px; font-size:12px; font-weight:650; }
.cmp-opt { display:inline-flex; align-items:center; gap:6px; color:var(--muted); margin-left:auto; }
.cmp-sec { font-size:13px; font-weight:700; color:#374151; margin:18px 0 8px; }
.cmp-kpis { display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:12px; margin:0 0 18px; }
.cmp-kpi { background:#f9fafb; border:1px solid var(--line); border-radius:12px; padding:14px 16px; }
.cmp-kpi.is-diff { background:#fff7ed; border-color:#fdba74; }
.cmp-kpi .lab { font-size:12px; color:var(--muted); margin-bottom:8px; }
.cmp-kpi .one { font-size:22px; font-weight:700; font-variant-numeric:tabular-nums; }
.cmp-kpi .pair { display:grid; grid-template-columns:1fr auto 1fr; gap:8px; align-items:center; }
.cmp-kpi .pair .col { display:flex; flex-direction:column; gap:2px; min-width:0; }
.cmp-kpi .pair .tag { font-size:11px; color:var(--muted); font-weight:650; }
.cmp-kpi .pair .num { font-size:18px; font-weight:700; font-variant-numeric:tabular-nums; word-break:break-all; }
.cmp-kpi .pair .vs { color:#d1d5db; font-size:13px; }
.cmp-board { display:flex; flex-wrap:wrap; align-items:center; gap:10px 16px; margin:0 0 16px;
  padding:12px 14px; border:1px solid var(--line); border-radius:12px; background:#fff; }
.cmp-board.is-diff { background:#fff7ed; border-color:#fdba74; }
.cmp-board .lab { color:var(--muted); font-size:12px; font-weight:650; }
.cmp-board .side { display:flex; align-items:center; gap:8px; }
.cmp-board .tag { font-size:11px; color:var(--muted); font-weight:650; }
table.cmp { width:100%; border-collapse:separate; border-spacing:0; font-size:13px; margin:0;
  border:1px solid var(--line); border-radius:12px; overflow:hidden; background:#fff; }
table.cmp th { position:sticky; top:0; background:var(--head); color:var(--accent); font-size:12px; padding:9px 12px; font-weight:650; }
table.cmp td { padding:10px 12px; vertical-align:middle; border-bottom:1px solid #f3f4f6; }
table.cmp tbody tr:last-child td { border-bottom:none; }
table.cmp td.is-diff { background:#fff7ed; }
table.cmp tr.is-fold { color:#6b7280; }
table.cmp td.pos { font-weight:700; width:64px; }
table.cmp .cell-one { font-variant-numeric:tabular-nums; }
table.cmp .cell-pair { display:grid; gap:3px; }
table.cmp .cell-pair .row { display:grid; grid-template-columns:2.6em 1fr; gap:6px; align-items:baseline;
  line-height:1.4; font-variant-numeric:tabular-nums; }
table.cmp .cell-pair .tag { font-size:11px; color:#6b7280; font-weight:650; }
table.cmp .cell-pair.is-bad .tag { color:var(--bad); }
table.cmp .hero-mark { margin-left:6px; font-size:11px; background:#dbeafe; color:#1e40af;
  border-radius:99px; padding:1px 6px; font-weight:650; }
.cmp-street { margin:0 0 14px; background:#fff; border:1px solid var(--line); border-radius:12px; padding:12px 14px 6px; }
.cmp-street h4 { margin:0 0 10px; font-size:14px; display:flex; align-items:baseline; gap:8px;
  padding-bottom:8px; border-bottom:1px solid var(--line); }
.cmp-street h4 .n { font-size:12px; color:var(--muted); font-weight:500; }
table.cmp-act { border:none; border-radius:0; }
table.cmp-act tr.is-diff td { background:#fff7ed; }
table.cmp-act td { font-size:13px; padding:8px 10px; }
table.cmp-act .n { width:36px; color:var(--muted); font-variant-numeric:tabular-nums; }
.act { display:flex; flex-wrap:wrap; align-items:baseline; gap:6px; }
.act .pos { font-weight:700; min-width:2.6em; }
.act .who { color:var(--muted); }
.act .verb { font-weight:650; }
.act .amt { font-variant-numeric:tabular-nums; font-weight:700; }
.act.is-bad .pos, .act.is-bad .verb { color:var(--bad); }
.act-meta { display:flex; flex-wrap:wrap; gap:4px 12px; margin-top:4px; font-size:12px;
  color:var(--muted); font-variant-numeric:tabular-nums; }
.act-meta .is-bad { color:var(--bad); font-weight:650; }
.cmp-win { display:flex; flex-wrap:wrap; gap:8px 16px; padding:12px 14px; border-radius:12px;
  background:var(--accent-soft); color:var(--ok); font-size:14px; margin:0 0 8px; border:1px solid var(--accent); }
.cmp-win.is-diff { background:#fff7ed; color:var(--bad); border-color:#fdba74; }
.hh-h { margin:18px 0 8px; font-size:14px; }
.hh-act td.n, .hh-act th.n { width:2.2em; color:var(--muted); font-variant-numeric:tabular-nums; white-space:nowrap; font-size:12px; }
.hh .hh-name { color:var(--muted); font-weight:500; margin-left:4px; }
.act-street { margin:0 0 8px; background:#fff; border:1px solid var(--line); border-radius:8px; overflow:hidden; }
.act-street-h { display:flex; justify-content:space-between; align-items:baseline; gap:10px;
  padding:5px 10px; background:var(--head); font-size:12px; font-weight:650; }
.act-street-h .n { color:var(--muted); font-weight:500; }
.act-street-h .pot { color:var(--muted); font-weight:500; font-variant-numeric:tabular-nums; }
table.act-log { width:100%; border-collapse:collapse; font-size:12px; }
table.act-log th { background:var(--head); text-align:left; font-weight:650; color:var(--accent);
  font-size:11px; padding:4px 8px; border-bottom:1px solid var(--line); }
table.act-log td { padding:4px 8px; vertical-align:middle; border-bottom:1px solid var(--head); }
table.act-log th, table.act-log td { width:1%; white-space:nowrap; }
table.act-log th:not(.n):not(.gutter), table.act-log td:not(.n):not(.gutter) { min-width:7.5em; }
table.act-log th.gutter, table.act-log td.gutter { width:99%; padding:0; border:none; }
table.act-log tr.is-diff td { background:#fff7ed; }
table.act-log tr.is-ok td { background:#fff; }
.act-cell { display:grid; grid-template-columns:repeat(5, max-content);
  grid-auto-flow:column; grid-auto-columns:max-content; align-items:center; column-gap:6px;
  justify-content:start; justify-items:start; width:max-content; min-width:max-content; max-width:none;
  height:auto; font-size:var(--fs); overflow:visible; }
.act-cell.has-pot, .act-cell.has-chips { grid-template-columns:repeat(6, max-content); }
.act-cell.has-pot.has-chips { grid-template-columns:repeat(7, max-content); }
.act-cell > * { min-width:max-content; overflow:visible; white-space:nowrap; }
.act-seat { font-weight:650; }
.act-name { overflow:visible; text-overflow:clip; white-space:nowrap; font-weight:650;
  min-width:max-content; max-width:none; }
.act-pos { color:var(--muted); font-weight:500; overflow:visible; text-overflow:clip; white-space:nowrap; }
.act-name.is-bad, .act-pos.is-bad, .act-seat.is-bad { color:var(--bad); }
.act-cell .diff-mark { display:inline-block; max-width:100%; min-width:0; padding:0 4px; box-sizing:border-box; }
.act-pill { display:inline-flex; align-items:center; justify-content:center; min-width:2.4em;
  padding:1px 6px; border-radius:99px; font-size:var(--fs-sm); font-weight:650; color:#fff; line-height:1.25; }
.act-pill.raise { background:var(--act-raise); }
.act-pill.bet { background:var(--act-bet); }
.act-pill.call { background:var(--act-call); }
.act-pill.check { background:var(--act-check); }
.act-pill.fold { background:var(--act-fold); }
.act-pill.allin { background:var(--act-allin); }
.act-pill.post { background:var(--act-fold); }
.act-pill.other { background:var(--muted); }
.act-pill.show { background:var(--act-show); }
.act-pill.is-bad { outline:2px solid var(--bad); outline-offset:1px; }
.act-pill.is-bad-vis { outline-color:#ea580c; }
.act-pill.is-bad-rule { outline-color:#e11d48; }
.act-amt, .act-pot, .act-stack { font-variant-numeric:tabular-nums; font-weight:650; text-align:right; min-width:0; font-size:inherit; }
.act-pot, .act-stack { color:var(--muted); font-weight:500; }
.act-amt.is-bad, .act-pot.is-bad, .act-stack.is-bad { color:var(--bad); }
.act-pill-h { display:inline-flex; align-items:center; justify-content:center; min-width:2.6em; flex-shrink:0; }
.act-cell.act-head { color:var(--muted); font-weight:650; font-size:var(--fs-xs); }
.act-cell.act-head .act-pill-h { justify-self:start; text-align:left; min-width:0; }
.act-cell.act-head .act-seat, .act-cell.act-head .act-name, .act-cell.act-head .act-pos,
.act-cell.act-head .act-amt, .act-cell.act-head .act-pot, .act-cell.act-head .act-stack { color:var(--muted); font-weight:650; }
.act-miss { color:var(--muted); }
.miss-lab { color:var(--bad); font-weight:650; white-space:nowrap; }
table.compare tr.act-cols td { background:#fff; color:var(--muted); font-weight:650; font-size:var(--fs-xs); padding-top:2px; padding-bottom:2px; border-bottom:1px dashed var(--line); }
.hh .hero-mark, table.compare .hero-mark { margin-left:6px; font-size:var(--fs-sm); background:#dbeafe; color:#1e40af;
  border-radius:99px; padding:1px 6px; font-weight:650; white-space:nowrap; }
table.compare { width:100%; border-collapse:collapse; font-size:var(--fs); }
table.compare th { position:sticky; top:0; z-index:1; background:var(--head); text-align:left;
  font-weight:650; color:var(--accent); padding:4px 6px; border-bottom:1px solid var(--line); font-size:var(--fs); }
table.compare td { padding:3px 6px; vertical-align:middle; border-bottom:1px solid #f3f4f6; font-size:var(--fs); }
table.compare td.path { font-family:ui-monospace,Consolas,monospace; font-size:var(--fs-sm); max-width:280px; word-break:break-all; }
table.compare td.who { white-space:nowrap; font-weight:650; width:7.5em; font-size:var(--fs); }
table.compare td.who .pos { color:var(--muted); font-weight:500; margin-left:4px; font-size:inherit; }
table.compare td.val { font-size:var(--fs); }
#drawer-body > table.compare { width:max-content; max-width:none; table-layout:auto; border-collapse:separate; border-spacing:0; }
#drawer-body > table.compare th { position:static; }
#drawer-body > table.compare th,
#drawer-body > table.compare td.who,
#drawer-body > table.compare td.val { white-space:nowrap; overflow:visible; text-overflow:clip; }
#drawer-body > table.compare td.cause { white-space:nowrap; overflow:visible; }
#drawer-body > table.compare thead th:first-child,
#drawer-body > table.compare td.who { position:static; width:1%; min-width:0; padding:2px 8px 2px 4px;
  box-shadow:none; }
#drawer-body > table.compare td.val { width:auto; min-width:max-content; padding:2px 8px 2px 4px; overflow:visible; }
#drawer-body > table.compare th.cause,
#drawer-body > table.compare td.cause { width:1%; min-width:4.2em; padding:2px 8px 2px 6px;
  position:static; box-shadow:none; }
#drawer-body > table.compare thead th.cause { background:var(--head); }
#drawer-body > table.compare tr.is-ok td.cause,
#drawer-body > table.compare tr.is-diff td.cause,
#drawer-body > table.compare tr.act-cols td.cause { background:#fff; }
#drawer-body > table.compare tr.is-ok td { color:var(--ink); background:#fff; }
#drawer-body > table.compare tr.is-diff td { background:#fff; }
#drawer-body > table.compare tr.is-ok td.who,
#drawer-body > table.compare tr.is-diff td.who,
#drawer-body > table.compare tr.act-cols td.who { background:#fff; }
#drawer-body > table.compare tr.is-diff td.who { box-shadow:inset 3px 0 0 var(--bad); }
#drawer-body > table.compare tr.sec td { background:var(--head); color:var(--accent); cursor:pointer; user-select:none; }
#drawer-body > table.compare tbody.cmp-fold tr.sec td {
  border-top:4px solid #fff; font-weight:700; padding:3px 6px;
  box-shadow:inset 3px 0 0 var(--accent); position:static;
  background:var(--head); }
#drawer-body > table.compare tbody.cmp-fold tr.sec .sec-in { position:static; width:100%; max-width:100%; min-width:0; }
#drawer-body > table.compare tbody.cmp-fold:first-of-type tr.sec td { border-top:none; }
#drawer-body > table.compare tbody.cmp-fold.is-closed tr:not(.sec) { display:none; }
#drawer-body > table.compare .caret { display:inline-block; width:1em; color:var(--muted); }
#drawer-body > table.compare tbody.cmp-fold.is-closed .caret { transform:rotate(-90deg); }
#drawer-body > table.compare .fold-n { margin-left:8px; font-weight:500; color:var(--bad); font-size:var(--fs-sm); }
#drawer-body > table.compare .fold-skip { margin-left:8px; font-weight:500; color:var(--muted); font-size:var(--fs-sm); }
#drawer-body > table.compare thead th:nth-child(3),
#drawer-body > table.compare thead th:nth-child(4),
#drawer-body > table.compare td.val:nth-child(3),
#drawer-body > table.compare td.val:nth-child(4) {
  box-shadow:inset 1px 0 0 var(--line);
  padding-left:6px;
}
#drawer-body > table.compare td.val:nth-child(3),
#drawer-body > table.compare tr.is-ok td.val:nth-child(3),
#drawer-body > table.compare tr.is-diff td.val:nth-child(3),
#drawer-body > table.compare tr.act-cols td.val:nth-child(3) { background:#f7f9fb; }
#drawer-body > table.compare td.val:nth-child(4),
#drawer-body > table.compare tr.is-ok td.val:nth-child(4),
#drawer-body > table.compare tr.is-diff td.val:nth-child(4),
#drawer-body > table.compare tr.act-cols td.val:nth-child(4) { background:#f4f8f6; }
#drawer-body > table.compare tr.act-cols td { background:var(--head); color:var(--muted); }
#drawer-body .pill.ok { background:var(--accent-soft); color:var(--ok); }
#drawer-body .pill.vis { background:#fef2f2; color:var(--bad); }
.roster { display:grid; grid-template-columns:repeat(3, minmax(max-content, 1fr)); gap:6px; align-items:stretch;
  margin:0; width:max-content; min-width:100%; overflow:visible; }
.roster-block { border:1px solid var(--line); border-radius:8px; overflow:visible; background:#fff;
  min-width:0; display:flex; flex-direction:column; }
.roster-h { background:var(--head); color:var(--accent); font-size:11px; font-weight:700;
  padding:3px 6px; display:flex; flex-wrap:wrap; gap:2px 6px; align-items:baseline; flex:0 0 auto; }
.roster-h .src { font-weight:700; }
.roster-h .meta { font-weight:500; color:var(--muted); }
.roster-scroll { overflow:visible; max-width:none; width:100%; }
.roster-grid { display:grid; width:max-content; max-width:none; min-width:100%;
  grid-template-columns:repeat(8, max-content);
  column-gap:8px; align-items:center; font-size:12px; }
.roster-grid > span { padding:1px 4px; white-space:nowrap; overflow:visible; text-overflow:clip;
  border-bottom:1px solid #f3f4f6; font-size:12px; line-height:1.35; }
.roster-grid > span:nth-child(-n+8) { color:var(--muted); font-weight:650; border-bottom:1px solid var(--line); background:#fff; }
.roster-grid > span:nth-last-child(-n+8) { border-bottom:none; }
.roster-grid .hero-star { color:var(--ink); margin-left:1px; }
.roster-grid .pnl-up { color:var(--ok); font-weight:650; }
.roster-grid .pnl-dn { color:var(--bad); font-weight:650; }
.roster-grid .pcard { min-width:18px; height:18px; padding:0 4px; font-size:12px; border-radius:3px; margin:0 1px 0 0; }
.roster-empty { margin:0; padding:10px; color:var(--muted); font-size:var(--fs-sm); }
table.compare td.val .pcard { margin:0 4px 0 0; }
table.compare tr.sec td { background:var(--head); font-weight:650; font-size:var(--fs); color:var(--ink);
  letter-spacing:0; padding:4px 6px; border-bottom:1px solid var(--line); }
table.compare tr.sec .sec-in { display:flex; justify-content:space-between; align-items:baseline; gap:10px; width:100%; }
table.compare tr.sec td .n, table.compare tr.sec td .pot { font-weight:500; color:#6b7280; letter-spacing:0; font-size:inherit; }
table.compare td.val .act-cell { column-gap:6px; min-width:max-content; width:max-content; max-width:none; }
table.compare tr.is-diff td { background:#fff7ed; }
table.compare tr.is-ok td { color:#6b7280; }
.pill.ok { background:var(--head); color:var(--muted); }
.pill.vis { background:#ffedd5; color:var(--pending); }
.pill.rule { background:#fee2e2; color:var(--bad); }
.pill.fix { background:var(--accent-soft); color:var(--ok); }
.pill.both { background:#ede9fe; color:#5b21b6; }
.pill.miss { background:#e5e7eb; color:#374151; }
.diff-mark { display:inline-block; box-sizing:border-box; border:1.5px solid #e11d48;
  border-radius:6px; padding:0 5px; line-height:1.45; background:#fff1f2; color:#be123c; font-weight:650; }
.diff-mark.vis { border-color:#ea580c; background:#fff7ed; color:#c2410c; }
.diff-mark.rule { border-color:#e11d48; background:#fff1f2; color:#be123c; }
.roster-grid .diff-mark { padding:0 3px; max-width:none; overflow:visible; text-overflow:clip; }
.roster-h .diff-mark { font-weight:650; }
.act-seat.diff-mark, .act-name.diff-mark, .act-pos.diff-mark,
.act-amt.diff-mark, .act-pot.diff-mark, .act-stack.diff-mark { padding:0 2px; }
#drawer-body > table.compare td.val .act-miss,
#drawer-body > table.compare td.val .diff-mark { display:inline-block; width:auto; max-width:none; box-sizing:border-box; vertical-align:middle; }
#drawer-body > table.compare td.val .diff-mark .pcard { font-weight:650; }
table.compare .post-cell { display:grid; grid-template-columns:repeat(2, max-content);
  grid-auto-flow:column; grid-auto-columns:max-content; align-items:baseline; column-gap:8px;
  width:max-content; min-width:max-content; max-width:none; white-space:nowrap; overflow:visible; }
table.compare .post-who { font-weight:650; }
table.compare .post-who .pos { color:var(--muted); font-weight:500; margin-left:4px; }
table.compare .post-who .hh-name { color:var(--muted); font-weight:500; margin-left:4px; }
table.compare .post-stack { color:var(--muted); font-variant-numeric:tabular-nums; font-weight:500; }
table.compare .post-amt { font-variant-numeric:tabular-nums; font-weight:700; }
table.compare .post-cards { display:inline-flex; align-items:center; }
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
    del by_cat, active_cat
    rates = pair_rates or empty_pair_rates({})
    cells = []
    for pair in PAIRS:
        row = rates.get(pair["id"]) or {}
        total_txt, total_cls = format_rate(row.get("all"))
        all_active = " active" if active_pair == pair["id"] else ""
        cells.append(
            f'<a class="rate-cell{all_active}" data-pair="{esc(pair["id"])}" data-cat="" '
            f'href="{esc(fields_href(pair["id"]))}">'
            f'<div class="rate-lab">{esc(pair["title"])}</div>'
            f'<div class="rate {total_cls}">{esc(total_txt)}</div>'
            f'<div class="rate-hint">{n_fields} 个字段 · {esc(pair["left"])} 为分母</div></a>'
        )
    return f'<div class="board-row">{"".join(cells)}</div>'


def seq_board_html(*, pair_rates: dict | None = None, active_pair: str | None = None) -> str:
    rates = pair_rates or {}
    cells = []
    for pair in PAIRS:
        row = rates.get(pair["id"]) or {}
        total_txt, total_cls = format_rate(row.get("exact"))
        all_active = " active" if active_pair == pair["id"] else ""
        n_hand = row.get("exact_t")
        hint = "重新查询后出整手准确率"
        if n_hand is not None:
            exact_n = row.get("exact_n") or 0
            steps = format_rate(row.get("steps"))[0] or "—"
            hint = f"{exact_n}/{n_hand} 手整条一致 · 步 {steps}"
        cells.append(
            f'<a class="rate-cell{all_active}" data-pair="{esc(pair["id"])}" data-kind="seq" '
            f'href="{esc(fields_href(pair["id"]))}">'
            f'<div class="rate-lab">{esc(pair["title"])}</div>'
            f'<div class="rate {total_cls}">{esc(total_txt)}</div>'
            f'<div class="rate-hint">{esc(hint)}</div></a>'
        )
    return f'<div class="board-row" id="seq-board">{"".join(cells)}</div>'


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
        f'<script src="{esc(src + ("?v=105" if src.endswith(".js") else ""))}"></script>\n'
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
    n = batch.get("n")
    waiting = batch.get("lookup") == "waiting"
    return {
        "id": batch.get("id") or "",
        "file": batch.get("source_name") or "",
        "n": "" if n in (None, "") else n,
        "waiting": waiting,
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
    seq_rates: dict | None = None,
    session_id: str = "",
    batch_id: str = "",
    note: str = "",
    source_path: str = "",
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
    seq_board = seq_board_html(pair_rates=seq_rates or {}, active_pair=None)
    meta_bits = [
        f"源数据 <code>{esc(source_name)}</code>",
        f"{n} 手",
        f"生成 {esc(generated)}",
    ]
    if session_id:
        meta_bits.append(f"session {esc(session_id)}")
    if note:
        meta_bits.append(esc(note))
    meta_html = "".join(f"<span>{bit}</span>" for bit in meta_bits)
    body = f"""
  <div class="page-head">
    <div>
      <h1>{esc(batch_title)}</h1>
      <p class="page-meta">{meta_html}</p>
    </div>
    <a class="btn-ghost" href="../../index.html">返回上传记录</a>
  </div>
  <div class="tabs" role="tablist">
    <button type="button" class="tab active" data-tab="grid">字段总表</button>
    <button type="button" class="tab" data-tab="match">匹配率</button>
    <button type="button" class="tab" data-tab="coverage">覆盖分布</button>
    <button type="button" class="tab" data-tab="origin">字段映射关系</button>
  </div>
  <p class="align-note" id="align-note"><b>对齐</b><span>源数据 <strong>{n}</strong></span><span>fusion <strong>—</strong></span><span>尚未查询 session</span></p>

  <div id="panel-grid" class="panel active">
    <section class="section" id="hand-grid-sec">
      <div class="section-head">
        <h2>按手汇总</h2>
        {help_fold("左侧钉住序号、hand_id、来源和 Hero 手牌。其余列从左到右：开局（人数、盲注、座位号、昵称、位置、Dealer、初始筹码、手牌）→ 过程（公牌、行动序列）→ 结算和终局（底池、摊牌、最终筹码、终局状态）。玩家列按源数据 P0 / P1 / … 展开；视觉/规则先按昵称找到同一个人再灌进这一列，再比座位号、位置、筹码。位置格比真实位置（BB 对 SB 算错）。行动仍按街第 i 步对第 i 步，不按昵称重排。这一手没人的座位写 —，不进分母。手牌只展开这批出现过手牌的座位。每手三行：源数据 / 视觉 / 规则。表头下面两行是各列相对源数据的命中率。查过 session 后，和源数据不一致的格子：视觉行橙底、规则行红字。点格子看整手差异。终局状态是这一手打完后：弃 / 摊 / 在手。")}
      </div>
      <div class="toolbar">
        <label><input type="checkbox" id="grid-only-err"/> 只看出错手</label>
        <label><input type="checkbox" id="grid-only-aligned" checked/> 只看对齐的手</label>
        <input id="grid-q" type="search" placeholder="筛选序号 / hand_id" style="flex:1;min-width:140px"/>
        <button type="button" class="btn-ghost" id="refresh-grid">重新查询</button>
        <span id="grid-count"></span>
      </div>
      <div class="hand-grid-wrap" id="hand-grid-wrap"></div>
    </section>
  </div>

  <div id="panel-match" class="panel">
    <section class="section">
      <div class="section-head"><h2>质量看板</h2>{help_fold("点一对高亮该列匹配率，并换成这一对的明细")}</div>
      {board}
      {help_fold("行动序列 · 整手链一致才算还原对；步匹配按这一手里的街和第几次计，不把第 i 次跨手当成同一字段", "seq-kicker")}
      {seq_board}
    </section>
    <section class="section" id="hand-mod">
      <div class="section-head"><h2>每手牌差异</h2>{help_fold("字段列是界面字段匹配率；行动序列是这一手整条链 / 步数")}</div>
      <div class="toolbar">
        <label>
          <input type="checkbox" id="hand-only-err"/> 只看出错手
        </label>
        <label>
          <input type="checkbox" id="hand-only-aligned" checked/> 只看对齐的手
        </label>
        <input id="hand-q" type="search" placeholder="筛选序号 / hand_id" style="flex:1;min-width:140px"/>
        <span id="hand-mod-count"></span>
      </div>
      <div class="table-scroll hand-mod-scroll">
        <table class="list">
          <thead>
            <tr>
              <th class="num">序号</th>
              <th>hand_id</th>
              <th class="num">出错字段</th>
              <th>行动序列</th>
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
    <section class="section" id="fields-block">
      <div class="section-head"><h2>字段匹配率</h2>{help_fold("手数 / 值差 / 缺失 / 长度 / 出错手是当前点中的那一对；右侧三列是三对匹配率")}</div>
      <div class="toolbar">
        <input id="f-path" type="search" placeholder="筛选中文名 / 模块 / 路径" style="flex:1;min-width:180px"/>
        <button type="button" class="btn-ghost" id="refresh-match">重新查询</button>
        <span id="field-count"></span>
      </div>
      <p class="sub" id="detail-caption"></p>
      <nav class="field-jump" id="field-jump"></nav>
      <div class="cat-blocks" id="cat-blocks"></div>
    </section>
  </div>

  <div id="panel-coverage" class="panel">
    <div class="cards">
      <div class="card"><div class="label">用例手数</div><div class="value">{n}</div></div>
      <div class="card"><div class="label">人数</div><div class="value">3–9</div></div>
      <div class="card"><div class="label">动作类型</div><div class="value">{len(actions)}</div><div class="hint">open…all in</div></div>
      <div class="card"><div class="label">摊牌</div><div class="value">{sum(1 for c in cases if c['showdown'])}</div><div class="hint">未摊牌 {sum(1 for c in cases if not c['showdown'])}</div></div>
    </div>
    <section class="section">
      <div class="section-head"><h2>覆盖分布</h2>{help_fold("一手只计一次")}</div>
      <div class="grid2">
        <div><h3 style="margin:0 0 8px;font-size:13px;color:var(--muted)">按人数</h3>{bar_rows(cases, "n_players", players, lambda p: f"{p}人")}</div>
        <div><h3 style="margin:0 0 8px;font-size:13px;color:var(--muted)">按英雄位</h3>{bar_rows(cases, "hero_pos", hero_pos)}</div>
        <div><h3 style="margin:0 0 8px;font-size:13px;color:var(--muted)">按街</h3>{bar_rows(cases, "street", STREETS)}</div>
        <div><h3 style="margin:0 0 8px;font-size:13px;color:var(--muted)">按动作</h3>{bar_rows(cases, "action", actions)}</div>
      </div>
    </section>
    <section class="section">
      <div class="section-head"><h2>人数 × 英雄位</h2>{help_fold("开局座位：灰格 0 表示该人数桌没有这个位置，或本批没覆盖")}</div>
      <div class="table-scroll">{table_cross(cases, "n_players", "hero_pos", players, hero_pos, "人数")}</div>
    </section>
    <section class="section">
      <div class="section-head"><h2>街 × 动作</h2>{help_fold("翻前没有 bet/raise/check；翻后没有 open/limp/3bet/4bet，这是场景设计不是缺测")}</div>
      <div class="table-scroll">{table_cross(cases, "street", "action", STREETS, actions, "街")}</div>
    </section>
    <section class="section">
      <div class="section-head"><h2>人数 × 街</h2></div>
      <div class="table-scroll">{table_cross(cases, "n_players", "street", players, STREETS, "人数")}</div>
    </section>
    <section class="section">
      <div class="section-head"><h2>{n} 手清单</h2>{help_fold("批跑序号 = 默认对齐序（翻前→翻牌→转牌→河牌）")}</div>
      <div class="toolbar">
        <input id="q" type="search" placeholder="搜索用例名 / hand_id / 动作" style="flex:1;min-width:200px"/>
        <select id="f-n"><option value="">人数：全部</option></select>
        <select id="f-hero"><option value="">英雄位：全部</option></select>
        <select id="f-street"><option value="">街：全部</option></select>
        <select id="f-action"><option value="">动作：全部</option></select>
        <span id="count"></span>
      </div>
      <div class="table-scroll" style="max-height:70vh">
        <table class="list">
          <thead>
            <tr>
              <th class="num">序号</th><th>人数</th><th>英雄位</th><th>盲注</th>
              <th>街</th><th>动作</th><th>摊牌</th><th>用例名称</th><th>hand_id</th><th>对照</th>
            </tr>
          </thead>
          <tbody id="tbody"></tbody>
        </table>
      </div>
    </section>
  </div>

  <div id="panel-origin" class="panel">
    <section class="section">
      <div class="section-head"><h2>字段映射关系</h2>{help_fold("源数据 / 视觉 / 规则各自从哪个模块、哪条路径取。只列各方实际记下的字段")}</div>
      <div class="toolbar">
        <input id="o-path" type="search" placeholder="筛选中文名 / 模块 / 路径" style="flex:1;min-width:180px"/>
        <span id="origin-count"></span>
      </div>
      <nav class="field-jump" id="origin-jump"></nav>
      <div class="cat-blocks" id="origin-blocks"></div>
    </section>
  </div>
  <div class="drawer-mask" id="drawer-mask">
    <div class="drawer" role="dialog" aria-modal="true">
      <div class="drawer-head">
        <div>
          <h3 id="drawer-title">对照</h3>
          <p class="sub" id="drawer-sub"></p>
        </div>
        <div class="drawer-actions">
          <button type="button" class="btn-ghost" id="drawer-back" hidden>返回字段差异</button>
          <button type="button" class="btn-ghost" id="drawer-close">关闭</button>
        </div>
      </div>
      <label class="drawer-filter" id="drawer-filter" hidden>
        <input type="checkbox" id="drawer-diff"/> 只看不一致
      </label>
      <div class="reject-banner" id="drawer-reject" hidden></div>
      <p class="sub" id="drawer-status"></p>
      <details class="help-fold" id="drawer-help" hidden>
        <summary>说明</summary>
        <p>整手差异都在下面：名单、强制投入、各街行动、结算、终局筹码和终局状态，起始筹码、手牌、公牌也在同一张表里。原始 JSON 默认收起。点标题可以收起某一段。</p>
      </details>
      <details class="drawer-clip" id="drawer-clip" hidden>
        <summary class="clip-bar">
          <span id="drawer-clip-name">原始切片</span>
          <span class="clip-bar-actions" id="drawer-clip-actions">
            <button type="button" class="clip-pip" id="drawer-clip-pip" hidden>画中画</button>
            <a id="drawer-clip-link" target="_blank" rel="noopener">打开牌局对比</a>
          </span>
        </summary>
        <video id="drawer-clip-video" controls playsinline preload="none"></video>
        <a class="clip-url" id="drawer-clip-url" target="_blank" rel="noopener"></a>
      </details>
      <div id="drawer-roster"></div>
      <div id="drawer-body"></div>
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
const SEQ_RATES = {json.dumps(seq_rates or {}, ensure_ascii=False)};
const FIELD_STATS = {json.dumps(field_stats or {}, ensure_ascii=False, separators=(",", ":"))};
let LOOKED_UP = {json.dumps(looked)};
const BATCH_ID = {json.dumps(batch_id or batch_title)};
const SESSION_ID = {json.dumps(session_id or "")};
const SOURCE_PATH = {json.dumps(source_path or "")};
const $ = id => document.getElementById(id);
function clearDrawerMain() {{
  $("drawer-body").innerHTML = "";
  const r = $("drawer-roster");
  if (r) r.innerHTML = "";
}}
const DEFAULT_API = "http://192.168.110.81:8080";
let HANDS = [];
let ALIGN = null;
let SAVED_API = DEFAULT_API;
let drawerSeq = 0;
let drawerPath = "";
let drawerRows = [];
let drawerHist = null;
let drawerRaw = {{ gold: null, vis: null, rule: null }};
let goldRawPack = null;
let goldRawWait = null;
let bodyCache = {{}};
const GRID_STATUS = {{ fold: "弃", show: "摊", in_hand: "在手" }};
const GRID_POS_ORDER = ["SB","BB","UTG","UTG+1","UTG+2","LJ","HJ","CO","BTN"];
const GRID_KIND_LAB = {{
  seat: "座位号", name: "昵称", position: "位置", dealer: "Dealer",
  init_chips: "初始筹码", cards: "手牌", chips: "最终筹码", status: "终局状态"
}};
function normGridPos(p) {{
  if (window.E2EMatch && E2EMatch.normPos) return E2EMatch.normPos(p) || "";
  const s = String(p || "").trim().toUpperCase().replace(/\\s+/g, "");
  if (!s) return "";
  if (s === "UTG1") return "UTG+1";
  if (s === "UTG2") return "UTG+2";
  if (s === "UTG3") return "UTG+3";
  if (s === "DEALER" || s === "BUTTON") return "BTN";
  if (s === "SMALLBLIND") return "SB";
  if (s === "BIGBLIND") return "BB";
  return s;
}}
function playerCardsOf(pl) {{
  const cards = (pl && pl.cards) || {{}};
  if (!cards || typeof cards !== "object") return [];
  const out = [];
  ["P0","P1"].forEach(k => {{
    const v = cards[k] && cards[k].value;
    if (v != null && v !== "") out.push(v);
  }});
  if (out.length) return out;
  Object.keys(cards).forEach(k => {{
    const v = cards[k] && cards[k].value;
    if (v != null && v !== "") out.push(v);
  }});
  return out;
}}
let gridSeatMemo = null;
let gridCardSeatMemo = null;
const posSeatMemo = {{}};
function collectGridSeats(wantCards) {{
  const seen = {{}};
  const pack = window.E2E_GOLD;
  ((pack && pack.trees) || []).forEach(tree => {{
    const players = (tree && tree.players) || {{}};
    Object.keys(players).forEach(k => {{
      if (k.charAt(0) !== "P") return;
      const n = parseInt(k.slice(1), 10);
      if (!isFinite(n)) return;
      if (wantCards && !playerCardsOf(players[k]).length) return;
      seen[n] = 1;
    }});
  }});
  return Object.keys(seen).map(Number).sort((a, b) => a - b);
}}
function gridSeatList() {{
  if (!gridSeatMemo) gridSeatMemo = collectGridSeats(false);
  return gridSeatMemo;
}}
function gridCardSeatList() {{
  if (!gridCardSeatMemo) gridCardSeatMemo = collectGridSeats(true);
  return gridCardSeatMemo;
}}
function goldSeatOfPos(seq, pos) {{
  const want = normGridPos(pos);
  if (!want) return null;
  let map = posSeatMemo[seq];
  if (!map) {{
    map = {{}};
    const players = ((goldOf(seq).tree) || {{}}).players || {{}};
    Object.keys(players).forEach(k => {{
      if (k.charAt(0) !== "P") return;
      const p = normGridPos(((players[k] || {{}}).position || {{}}).value);
      if (!p || p in map) return;
      const n = parseInt(k.slice(1), 10);
      if (!isFinite(n)) return;
      map[p] = n;
    }});
    posSeatMemo[seq] = map;
  }}
  return want in map ? map[want] : null;
}}
function posLive(seq, pos) {{
  return goldSeatOfPos(seq, pos) != null;
}}
function goldHasCards(seq, pos) {{
  const i = goldSeatOfPos(seq, pos);
  if (i == null) return false;
  return seatHasCards(seq, i);
}}
function seatHasCards(seq, i) {{
  if (i == null) return false;
  const pre = "players.P" + i + ".";
  return hasVal(gVal(seq, pre + "cards.P0.value")) || hasVal(gVal(seq, pre + "cards.P1.value"));
}}
function heroSeatOf(seq) {{
  const hist = goldOf(seq).hist;
  const hit = ((hist && hist.players) || []).find(p => p && p.hero);
  if (hit && hit.seat != null && isFinite(Number(hit.seat))) return Number(hit.seat);
  const c = caseOf(seq);
  if (c && c.hero_seat != null && isFinite(Number(c.hero_seat))) return Number(c.hero_seat);
  if (c && c.hero_pos) {{
    const i = goldSeatOfPos(seq, c.hero_pos);
    if (i != null) return i;
  }}
  return 0;
}}
function gridColCount() {{
  return 14 + gridSeatList().length * 7 + gridCardSeatList().length;
}}
const goldCache = {{}};
const stageCache = {{}};
let stageEpoch = 0;
const GRID_SIDES = [
  {{ id: "gold", lab: "源数据" }},
  {{ id: "vis", lab: "视觉" }},
  {{ id: "rule", lab: "规则" }},
];
function rateClass(v) {{
  if (v == null || v === "") return "is-empty";
  if (v === "—") return "is-dash";
  return "";
}}
function paintBoard() {{
  document.querySelectorAll("a.rate-cell[data-pair]").forEach(a => {{
    if (a.dataset.kind === "seq") return;
    const pair = a.dataset.pair;
    const cat = a.dataset.cat || "all";
    const v = (PAIR_RATES[pair] || {{}})[cat];
    const rateEl = a.querySelector(".rate");
    if (!rateEl) return;
    rateEl.className = "rate " + rateClass(v);
    rateEl.textContent = fmtRate(v);
  }});
  paintSeqBoard();
}}
function paintSeqBoard() {{
  document.querySelectorAll("#seq-board .rate-cell").forEach(a => {{
    const row = SEQ_RATES[a.dataset.pair] || {{}};
    const rateEl = a.querySelector(".rate");
    const hintEl = a.querySelector(".rate-hint");
    if (!rateEl) return;
    if (row.exact_t == null) {{
      rateEl.textContent = "";
      rateEl.className = "rate is-empty";
      if (hintEl) hintEl.textContent = "重新查询后出整手准确率";
      return;
    }}
    rateEl.textContent = fmtRate(row.exact);
    rateEl.className = "rate " + rateClass(row.exact);
    if (hintEl) {{
      hintEl.textContent = (row.exact_n || 0) + "/" + row.exact_t +
        " 手整条一致 · 步 " + (fmtRate(row.steps) || "—");
    }}
  }});
}}
try {{
  const saved = JSON.parse(localStorage.getItem("e2e-rates-" + BATCH_ID) || "null");
  const fresh = saved && Array.isArray(saved.hands) && saved.hands.length;
  if (fresh) {{
    if (saved.pair_rates) Object.assign(PAIR_RATES, saved.pair_rates);
    if (saved.seq_rates) Object.assign(SEQ_RATES, saved.seq_rates);
    if (saved.field_stats) {{
      Object.keys(saved.field_stats).forEach(k => {{ FIELD_STATS[k] = saved.field_stats[k]; }});
      LOOKED_UP = true;
    }}
    HANDS = saved.hands;
    if (saved.align) ALIGN = saved.align;
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
  if (tab === "map") tab = "origin";
  if (tab === "summary" || tab === "hands") tab = "grid";
  ["grid","match","coverage","origin"].forEach(id => {{
    const btn = document.querySelector('.tab[data-tab="'+id+'"]');
    const panel = $("panel-"+id);
    if (btn) btn.classList.toggle("active", id === tab);
    if (panel) panel.classList.toggle("active", id === tab);
  }});
  const url = new URL(location.href);
  url.searchParams.set("tab", tab);
  history.replaceState(null, "", url);
  if (tab === "origin") renderOrigin();
  if (tab === "grid" && typeof renderHandGrid === "function") renderHandGrid();
}}
document.querySelectorAll(".tab").forEach(btn => {{
  btn.addEventListener("click", () => setTab(btn.dataset.tab));
}});

const params = new URLSearchParams(location.search);
let currentPair = params.get("pair") || PAIRS[0].id;
if (!PAIRS.some(p => p.id === currentPair)) currentPair = PAIRS[0].id;
setTab(params.get("tab") || "grid");
function syncPairUi() {{
  document.querySelectorAll("a.rate-cell").forEach(a => {{
    a.classList.toggle("active", a.dataset.pair === currentPair);
  }});
}}
function showPair(pair) {{
  if (!PAIRS.some(p => p.id === pair)) return;
  currentPair = pair;
  syncPairUi();
  setTab("match");
  renderFields();
  const url = new URL(location.href);
  url.searchParams.set("tab", "match");
  url.searchParams.set("pair", currentPair);
  url.searchParams.delete("cat");
  history.replaceState(null, "", url);
  const block = $("fields-block");
  if (block) block.scrollIntoView({{ behavior: "smooth", block: "start" }});
}}

function pairOf(id) {{ return PAIRS.find(p => p.id === id); }}
function fmtRate(v) {{
  if (v == null || v === "") return "";
  if (v === "—") return "—";
  const n = Number(v);
  if (Number.isFinite(n)) return n.toFixed(1) + "%";
  return String(v);
}}
const STREET_LAB = {{ preflop: "翻前", flop: "翻牌", turn: "转牌", river: "河牌" }};
const SEQ_PART_LAB = {{ who: "位置", action: "动作", amount: "下注额" }};
const FIELD_GROUPS = [
  ["count", "人数"],
  ["blinds", "盲注 / 前注"],
  ["seat", "座位号"],
  ["name", "昵称"],
  ["position", "位置"],
  ["dealer", "Dealer"],
  ["init_chips", "初始筹码"],
  ["cards", "手牌"],
  ["board", "公牌"],
  ["seq", "行动序列"],
  ["pot", "底池"],
  ["showdown", "是否摊牌"],
  ["chips", "最终筹码"],
  ["status", "终局状态"],
  ["other", "其它"],
];
const FIELD_GROUP_IX = {{}};
FIELD_GROUPS.forEach((p, i) => {{ FIELD_GROUP_IX[p[0]] = i; }});
function groupLab(kind) {{
  return (FIELD_GROUPS.find(g => g[0] === kind) || [kind, kind])[1];
}}
function fieldKind(path) {{
  if (path.indexOf("history.") === 0) return "seq";
  if (/^players\\.P\\d+\\.cards/.test(path)) return "cards";
  if (path.indexOf("community_cards") >= 0) return "board";
  if (path.indexOf(".init_chips.") >= 0) return "init_chips";
  if (path.indexOf(".chips.") >= 0) return "chips";
  if (/\\.pot\\.value$/.test(path)) return "pot";
  if (/\\.(sb|bb|ante)\\.value$/.test(path)) return "blinds";
  if (path.indexOf(".name.") >= 0) return "name";
  if (path.indexOf(".position.") >= 0) return "position";
  if (path.indexOf(".seat.") >= 0) return "seat";
  if (path.indexOf(".dealer.") >= 0) return "dealer";
  if (path.indexOf(".status.") >= 0) return "status";
  if (path.indexOf("showdown") >= 0) return "showdown";
  if (path.indexOf("player_count") >= 0) return "count";
  return "other";
}}
function fieldLabel(path, compact) {{
  const hm = path.match(/^history\\.(vol|post)\\.(preflop|flop|turn|river)(?:\\[(\\d+)\\](?:\\.(who|action|amount))?)?$/);
  if (hm) {{
    const lab = STREET_LAB[hm[2]] + (hm[1] === "post" ? "盲注" : "");
    if (hm[3] == null) return compact ? "次数" : lab + " 次数";
    const head = lab + "第 " + (Number(hm[3]) + 1) + " 次";
    if (!hm[4]) return compact ? head : head;
    return compact ? SEQ_PART_LAB[hm[4]] : head + " · " + SEQ_PART_LAB[hm[4]];
  }}
  const seat = (path.match(/^players\\.(P\\d+)/) || [])[1] || "";
  const kind = fieldKind(path);
  const lab = groupLab(kind);
  if (kind === "cards") {{
    const cm = path.match(/\\.cards\\.P(\\d+)\\.value$/);
    const name = cm ? "手牌" + (Number(cm[1]) + 1) : (/\\.cards$/.test(path) ? "手牌张数" : lab);
    return compact ? name : (seat ? seat + " " + name : name);
  }}
  if (kind === "board") {{
    const bm = path.match(/community_cards\\[(\\d+)\\]/);
    return bm ? "公牌 " + (Number(bm[1]) + 1) : "公牌张数";
  }}
  if (path === "players") return "玩家列表";
  if (path === "table") return "桌面";
  if (kind === "blinds") {{
    if (path.indexOf(".sb.") >= 0) return "小盲";
    if (path.indexOf(".bb.") >= 0) return "大盲";
    if (path.indexOf(".ante.") >= 0) return "前注";
  }}
  if (kind === "pot") return "总底池";
  if (kind === "showdown") return "摊牌";
  if (kind === "count") return "人数";
  if (seat) return compact ? lab : seat + " " + lab;
  return lab;
}}
function seqStreetLab(path) {{
  const m = path.match(/^history\\.(vol|post)\\.(preflop|flop|turn|river)/);
  if (!m) return "";
  return STREET_LAB[m[2]] + (m[1] === "post" ? "盲注" : "");
}}
function seqActLab(path) {{
  const m = path.match(/^history\\.(vol|post)\\.(preflop|flop|turn|river)\\[(\\d+)\\]/);
  if (!m) return "";
  return "第 " + (Number(m[3]) + 1) + " 次";
}}
function seqSortKey(path) {{
  const m = path.match(/^history\\.(vol|post)\\.(preflop|flop|turn|river)(?:\\[(\\d+)\\](?:\\.(who|action|amount))?)?$/);
  if (!m) return [99, 99, 9999, 99];
  const st = ["preflop", "flop", "turn", "river"].indexOf(m[2]);
  const kind = m[1] === "post" ? 0 : 1;
  const idx = m[3] == null ? -1 : Number(m[3]);
  const part = m[4] ? ["who", "action", "amount"].indexOf(m[4]) : -1;
  return [st, kind, idx, part];
}}
function sortFields(list) {{
  return list.slice().sort((a, b) => {{
    const ia = FIELD_GROUP_IX[fieldKind(a.path)];
    const ib = FIELD_GROUP_IX[fieldKind(b.path)];
    if (ia !== ib) return (ia == null ? 99 : ia) - (ib == null ? 99 : ib);
    if (fieldKind(a.path) === "seq") {{
      const ka = seqSortKey(a.path);
      const kb = seqSortKey(b.path);
      for (let i = 0; i < ka.length; i++) if (ka[i] !== kb[i]) return ka[i] - kb[i];
      return 0;
    }}
    const sa = parseInt(((a.path.match(/^players\\.P(\\d+)/) || [])[1] || "-1"), 10);
    const sb = parseInt(((b.path.match(/^players\\.P(\\d+)/) || [])[1] || "-1"), 10);
    if (sa !== sb) return sa - sb;
    return a.path.localeCompare(b.path);
  }});
}}
function escTxt(s) {{
  return String(s == null ? "" : s).replace(/[&<>"]/g, c => ({{"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;"}}[c]));
}}
function fieldOrigin(path) {{
  const seatM = path.match(/^players\\.P(\\d+)/);
  const seat = seatM ? seatM[1] : "i";
  const o = (g, v, r) => ({{ gold: ["auto_json", g], vis: ["llm_extraction", v], rule: ["ruleResult", r] }});
  const hm = path.match(/^history\\.(vol|post)\\.(preflop|flop|turn|river)(?:\\[(\\d+)\\](?:\\.(who|action|amount))?)?$/);
  if (hm) {{
    const lab = STREET_LAB[hm[2]] + (hm[1] === "post" ? "盲注" : "");
    const nth = hm[3] == null ? "次数" : "第 " + (Number(hm[3]) + 1) + " 次";
    const where = lab + nth;
    const goldPart = hm[4] === "who" ? "position" : (hm[4] || "length");
    const visPart = {{ who: "player_position", action: "action", amount: "amount" }}[hm[4]] || "length";
    const rulePart = {{ who: "[0]→players[][1] 位置", action: "[2] 动作", amount: "[3] 下注额" }}[hm[4]] || ".length";
    return o(
      "actions[]（" + where + "）." + goldPart,
      "hands[0].actions[]（" + where + "）." + visPart,
      "actions[]（" + where + "）" + rulePart
    );
  }}
  const cardM = path.match(/\\.cards\\.P(\\d+)\\.value$/);
  if (cardM) {{
    const ci = cardM[1];
    return o(
      "hole_cards[" + seat + "][" + ci + "]",
      "hands[0].players[].shown_cards[" + ci + "]（Hero 可回落到 hero_cards[" + ci + "]）",
      "players[][6][" + ci + "] 摊牌牌，否则 players[][3][" + ci + "]"
    );
  }}
  if (/^players\\.P\\d+\\.cards$/.test(path)) {{
    return o("hole_cards[" + seat + "]", "hands[0].players[].shown_cards / hero_cards", "players[][6] 或 players[][3]");
  }}
  if (/community_cards\\[(\\d+)\\]/.test(path)) {{
    const i = path.match(/community_cards\\[(\\d+)\\]/)[1];
    return o("flop / turn / river 拼成公牌[" + i + "]", "hands[0].community_cards[" + i + "]", "board[" + i + "]");
  }}
  if (path === "table.community_cards") {{
    return o("flop + turn + river", "hands[0].community_cards", "board");
  }}
  const leaf = [
    [".init_chips.value", "init_stacks[" + seat + "]", "hands[0].players[].initial_chips", "players[][4]"],
    [".chips.value", "final_stacks[" + seat + "]", "hands[0].players[].final_chips", "players[][5]"],
    [".name.value", "seat_nicknames[" + seat + "] / seat_player_names[" + seat + "]", "hands[0].players[].nickname", "players[][2]"],
    [".position.value", "seat_positions[" + seat + "]", "hands[0].players[].position", "players[][1]"],
    [".seat.value", "座位下标 " + seat, "hands[0].players 自己的座位/下标", "players[][0] 座位号"],
    [".dealer.value", "dealer_position === " + seat, "hands[0].players[].is_dealer", "players[][1] === BTN"],
    [".status.value", "actions[].fold / is_showdown", "hands[0].players[].status + actions fold", "actions[] fold / result.showdown"],
  ];
  for (let i = 0; i < leaf.length; i++) {{
    if (path.indexOf(leaf[i][0]) >= 0) return o(leaf[i][1], leaf[i][2], leaf[i][3]);
  }}
  if (/\\.pot\\.value$/.test(path)) {{
    return o("result.total_pot", "hands[0].pots_structure.total_pot / final_pot", "result.total_pot");
  }}
  if (/\\.sb\\.value$/.test(path)) {{
    return o("small_blind", "blind_level 或 blinds_config.small_blind", "blinds.sb");
  }}
  if (/\\.bb\\.value$/.test(path)) {{
    return o("big_blind", "blind_level 或 blinds_config.big_blind", "blinds.bb");
  }}
  if (/\\.ante\\.value$/.test(path)) {{
    return o("ante", "blinds_config.ante / ante_per_player", "blinds.ante");
  }}
  if (path.indexOf("player_count") >= 0) {{
    return o("player_count", "hands[0].players.length", "players.length");
  }}
  if (path.indexOf("showdown") >= 0) {{
    return o("is_showdown", "hands[0].settlement.showdown / outcome", "result.showdown");
  }}
  if (path === "players") {{
    return o("seat_positions / player_count", "hands[0].players", "players");
  }}
  if (path === "table") {{
    return o("桌面字段（盲注、公牌、底池）", "hands[0] 桌面字段", "blinds / board / result");
  }}
  return {{ gold: ["界面树", path], vis: ["llm_extraction", "对齐后的同一界面树路径"], rule: ["ruleResult", "对齐后的同一界面树路径"] }};
}}
function originSides(path) {{
  const src = fieldOrigin(path);
  return [
    ["源数据", src.gold[0], src.gold[1]],
    ["视觉", src.vis[0], src.vis[1]],
    ["规则", src.rule[0], src.rule[1]],
  ];
}}
function pairOriginRows(path) {{
  const p = pairOf(currentPair);
  return originSides(path).filter(row => row[0] === p.left || row[0] === p.right);
}}
function originSearch(path) {{
  return originSides(path).map(r => r.join(" ")).join(" ");
}}
function sideOf(path, lab) {{
  return originSides(path).find(row => row[0] === lab) || [lab, "", ""];
}}
function mapCell(side) {{
  if (!side || !side[1]) return "<td class='map'>—</td>";
  return "<td class='map' title='" + escTxt(side[1] + "." + side[2]) + "'>" +
    "<i>" + escTxt(side[1]) + "</i>." + escTxt(side[2]) + "</td>";
}}
function fieldNameCell(f, compact) {{
  return "<td class='path' title='" + escTxt(f.path) + "'>" +
    escTxt(fieldLabel(f.path, compact)) + "</td>";
}}
function originCells(f, compact) {{
  return fieldNameCell(f, compact) +
    mapCell(sideOf(f.path, "源数据")) +
    mapCell(sideOf(f.path, "视觉")) +
    mapCell(sideOf(f.path, "规则")) +
    "<td class='gutter'></td>";
}}
function colSpan(mode) {{
  return mode === "origin" ? 5 : 1 + PAIRS.length + 6;
}}
function pairRateCell(f, pairId) {{
  const hi = pairId === currentPair ? " pair-hi" : "";
  if (!LOOKED_UP) return "<td class='num" + hi + "'></td>";
  const row = (FIELD_STATS[pairId] || {{}})[f.path] || {{}};
  const total = row.total || 0;
  const rate = total ? ((100 * row.match / total).toFixed(1) + "%") : "—";
  const rateCls = !total ? "" : (row.match === total ? " rate-ok" : " rate-bad");
  const errN = row.n_error || 0;
  const inner = errN
    ? "<button type='button' class='err-link' data-err-path='" + encodeURIComponent(f.path) +
      "' data-err-pair='" + pairId + "' title='" + errN + "/" + total + " 手出错'>" + rate + "</button>"
    : rate;
  return "<td class='num" + rateCls + hi + "'>" + inner + "</td>";
}}
function pairDetailCells(f) {{
  if (!LOOKED_UP) {{
    return "<td class='num'></td><td class='num'></td><td class='num'></td><td class='num'></td><td class='num'></td>";
  }}
  const row = (FIELD_STATS[currentPair] || {{}})[f.path] || {{}};
  const total = row.total || 0;
  const errN = row.n_error || 0;
  const errBtn = errN
    ? "<button type='button' class='err-link' data-err-path='" + encodeURIComponent(f.path) +
      "' data-err-pair='" + currentPair + "'>" + errN + "/" + total + "</button>"
    : "0";
  return "<td class='num'>" + total + "</td>" +
    "<td class='num'>" + (row.mismatch || 0) + "</td>" +
    "<td class='num'>" + (row.missing || 0) + "</td>" +
    "<td class='num'>" + (row.len_mismatch || 0) + "</td>" +
    "<td class='num'>" + errBtn + "</td>";
}}
function rowHtml(f, extraClass, compact, mode) {{
  const cls = extraClass ? " class='" + extraClass + "'" : "";
  if (mode === "origin") return "<tr" + cls + ">" + originCells(f, compact) + "</tr>";
  return "<tr" + cls + ">" + fieldNameCell(f, compact) +
    pairDetailCells(f) +
    PAIRS.map(p => pairRateCell(f, p.id)).join("") +
    "<td class='gutter'></td></tr>";
}}
function fieldsHead(mode) {{
  if (mode === "origin") {{
    return "<thead><tr>" +
      "<th>字段</th>" +
      "<th>源数据 · 模块.字段</th>" +
      "<th>视觉 · 模块.字段</th>" +
      "<th>规则 · 模块.字段</th>" +
      "<th class='gutter'></th>" +
      "</tr></thead>";
  }}
  const p = pairOf(currentPair);
  return "<thead><tr>" +
    "<th>字段</th>" +
    "<th class='num' title='" + escTxt(p.title) + " 参与比对的手数'>手数</th>" +
    "<th class='num' title='记下的值不一致'>值差</th>" +
    "<th class='num'>缺失</th>" +
    "<th class='num' title='列表项数不一致'>长度</th>" +
    "<th class='num' title='出错手数 / 参与比对手数'>出错手</th>" +
    PAIRS.map(x => "<th class='num" + (x.id === currentPair ? " pair-hi" : "") + "'>" +
      escTxt(x.title) + "</th>").join("") +
    "<th class='gutter'></th>" +
    "</tr></thead>";
}}
function groupKpi(list, mode) {{
  if (mode === "origin" || !LOOKED_UP) return "<span class='cat-kpi'>" + list.length + " 个字段</span>";
  const bits = PAIRS.map(p => {{
    let total = 0, match = 0;
    list.forEach(f => {{
      const st = (FIELD_STATS[p.id] || {{}})[f.path] || {{}};
      total += st.total || 0;
      match += st.match || 0;
    }});
    const rate = total ? (100 * match / total).toFixed(1) + "%" : "—";
    const cls = !total ? "" : (match === total ? "ok" : "bad");
    return "<b class='" + cls + "'>" + rate + "</b>";
  }});
  return "<span class='cat-kpi'>" + bits.join(" · ") + " · " + list.length + " 个字段</span>";
}}
function rowsForGroup(kind, list, mode) {{
  const bits = [];
  const span = colSpan(mode);
  if (kind === "seq") {{
    let lastStreet = "", lastAct = "";
    list.forEach(f => {{
      const street = seqStreetLab(f.path);
      const act = seqActLab(f.path);
      if (street && street !== lastStreet) {{
        bits.push("<tr class='sec'><td colspan='" + span + "'>" + street + "</td></tr>");
        lastStreet = street;
        lastAct = "";
      }}
      if (act && act !== lastAct) {{
        bits.push("<tr class='act'><td colspan='" + span + "'>" + act + "</td></tr>");
        lastAct = act;
      }}
      bits.push(rowHtml(f, act ? "is-leaf" : "", true, mode));
    }});
    return bits.join("");
  }}
  if (kind === "cards") {{
    let lastSeat = "";
    list.forEach(f => {{
      const seat = (f.path.match(/^players\\.(P\\d+)/) || [])[1] || "";
      if (seat && seat !== lastSeat) {{
        bits.push("<tr class='act'><td colspan='" + span + "'>" + seat + "</td></tr>");
        lastSeat = seat;
      }}
      bits.push(rowHtml(f, seat ? "is-leaf" : "", true, mode));
    }});
    return bits.join("");
  }}
  return list.map(f => rowHtml(f, "", false, mode)).join("");
}}
function fieldBuckets(q) {{
  const all = sortFields(FIELDS);
  const part = all.filter(f => {{
    if (!q) return true;
    const blob = (f.path + " " + fieldLabel(f.path) + " " + originSearch(f.path)).toLowerCase();
    return blob.includes(q);
  }});
  const buckets = [];
  FIELD_GROUPS.forEach(g => {{
    const list = part.filter(f => fieldKind(f.path) === g[0]);
    if (list.length) buckets.push([g[0], g[1], list]);
  }});
  const extra = part.filter(f => FIELD_GROUP_IX[fieldKind(f.path)] == null);
  if (extra.length) buckets.push(["other", "其它", extra]);
  return {{ part: part, total: all.length, buckets: buckets }};
}}
function paintFieldBlocks(jumpId, blocksId, countId, mode, prefix) {{
  const qEl = mode === "origin" ? $("o-path") : $("f-path");
  const q = ((qEl && qEl.value) || "").trim().toLowerCase();
  const got = fieldBuckets(q);
  $(jumpId).innerHTML = got.buckets.map(b =>
    "<a href='#" + prefix + b[0] + "'>" + b[1] + "<span class='n'>" + b[2].length + "</span></a>"
  ).join("");
  $(blocksId).innerHTML = got.buckets.length
    ? "<div class='fields-wrap'><table class='fields'>" + fieldsHead(mode) + "<tbody>" +
      got.buckets.map(b =>
        "<tr class='cat-head' id='" + prefix + b[0] + "'><td colspan='" + colSpan(mode) + "'>" +
        "<span class='cat-title'>" + b[1] + "</span>" + groupKpi(b[2], mode) + "</td></tr>" +
        rowsForGroup(b[0], b[2], mode)
      ).join("") + "</tbody></table></div>"
    : "<p class='sub'>没有匹配字段</p>";
  $(countId).textContent = "显示 " + got.part.length + " / " + got.total;
  document.querySelectorAll("#" + blocksId + " .err-link[data-err-path]").forEach(btn => {{
    btn.addEventListener("click", () => {{
      if (btn.dataset.errPair && btn.dataset.errPair !== currentPair) {{
        currentPair = btn.dataset.errPair;
        syncPairUi();
        renderFields();
      }}
      openErrorHands(decodeURIComponent(btn.dataset.errPath));
    }});
  }});
}}
function renderFields() {{
  const p = pairOf(currentPair);
  const rates = LOOKED_UP
    ? PAIRS.map(x => fmtRate((PAIR_RATES[x.id] || {{}}).all) || "—").join(" · ")
    : "";
  $("detail-caption").textContent = (rates ? "三对总匹配率 " + rates + " · " : "") +
    "明细列是「" + p.title + "」。只比各方记下的值";
  paintFieldBlocks("field-jump", "cat-blocks", "field-count", "rates", "block-");
  renderAlignNote();
  syncPairUi();
  renderHandMod();
}}
function renderOrigin() {{
  if (!$("origin-blocks")) return;
  paintFieldBlocks("origin-jump", "origin-blocks", "origin-count", "origin", "orig-");
}}
$("f-path").addEventListener("input", renderFields);
if ($("o-path")) $("o-path").addEventListener("input", renderOrigin);
document.querySelectorAll("a.rate-cell").forEach(a => {{
  a.addEventListener("click", e => {{
    e.preventDefault();
    showPair(a.dataset.pair);
  }});
}});
syncPairUi();
paintBoard();
renderFields();
hydrateRejects();

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
    "<td class='num'>" + c.n_players + "</td>" +
    "<td>" + c.hero_pos + "</td>" +
    "<td>" + c.blinds + "</td>" +
    "<td>" + c.street + "</td>" +
    "<td>" + c.action + "</td>" +
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
  const seen = {{}};
  PAIRS.forEach(p => {{
    const stats = FIELD_STATS[p.id] || {{}};
    Object.keys(stats).forEach(path => {{
      const errs = stats[path] && stats[path].errors;
      if (Array.isArray(errs) && errs.indexOf(seq) >= 0) seen[path] = 1;
    }});
  }});
  return Object.keys(seen).length;
}}
function handAligned(seq) {{
  return !!(handOf(seq) || {{}}).fusionHandId;
}}
function renderHandMod() {{
  const box = $("hand-mod-body");
  if (!box) return;
  const only = $("hand-only-err") && $("hand-only-err").checked;
  const alignedOnly = $("hand-only-aligned") && $("hand-only-aligned").checked;
  const q = (($("hand-q") && $("hand-q").value) || "").trim().toLowerCase();
  if (!LOOKED_UP) {{
    box.innerHTML = "<tr><td colspan='8'>还没有匹配率。点上方「重新查询」后再看每手。</td></tr>";
    $("hand-mod-count").textContent = "";
    return;
  }}
  const rows = CASES.filter(c => {{
    const nErr = nErrorForSeq(c.seq);
    if (only && !nErr) return false;
    if (alignedOnly && !handAligned(c.seq)) return false;
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
    return "<tr>" +
      "<td class='num'>" + c.seq + "</td>" +
      "<td><code>" + (h.hand_id || c.hand_id || "") + "</code></td>" +
      "<td class='num'>" + nErr + "</td>" +
      "<td>" + fmtActionSeq(h.action_seq) + "</td>" +
      "<td>" + fmtPct(h.gt_vis) + "</td>" +
      "<td>" + fmtPct(h.vis_rule) + "</td>" +
      "<td>" + fmtPct(h.gt_rule) + "</td>" +
      "<td>" + (LOOKED_UP
        ? ((h.downstream && h.downstream.reject)
          ? "<span class='st bad'>" + escTxt(h.downstream.short || "下游拒绝") + "</span> "
          : "") +
          "<button type='button' class='err-link' data-hand-seq='" + c.seq + "'>差异</button>"
        : "") + "</td>" +
      "</tr>";
  }}).join("") || "<tr><td colspan='8'>没有匹配的手。</td></tr>";
  box.querySelectorAll("[data-hand-seq]").forEach(btn => {{
    btn.addEventListener("click", () => openCompare(Number(btn.dataset.handSeq), true));
  }});
}}
["hand-only-err","hand-only-aligned","hand-q"].forEach(id => {{
  const el = $(id);
  if (!el) return;
  el.addEventListener("input", renderHandMod);
  el.addEventListener("change", renderHandMod);
}});
function valAt(tree, path, hist) {{
  if (!window.E2EMatch || !tree) return undefined;
  if (E2EMatch.valueAt) return E2EMatch.valueAt(tree, hist, path);
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
const KIND_ORDER = FIELD_GROUPS;
function kindOf(path) {{
  return fieldKind(path);
}}
function seatOf(path) {{
  const m = path.match(/^players\\.(P\\d+)/);
  return m ? m[1] : "";
}}
function isLenVal(v) {{
  return Array.isArray(v) && v[0] === "__len__";
}}
function isContainerPath(path) {{
  return path === "players" || path === "table" ||
    /\\.cards$/.test(path) || path === "table.community_cards";
}}
function posOf(rows, seat) {{
  const r = (rows || []).find(x => x.path === "players." + seat + ".position.value");
  if (!r) return "";
  const v = r.gold != null && r.gold !== "" ? r.gold : (r.vis != null ? r.vis : r.rule);
  return v == null ? "" : String(v);
}}
function firstBadCause(children) {{
  const bad = (children || []).filter(c => c.cause && c.cause.id !== "ok");
  if (!bad.length) return {{ id: "ok", lab: "匹配" }};
  const ids = [];
  bad.forEach(c => {{ if (ids.indexOf(c.cause.id) < 0) ids.push(c.cause.id); }});
  if (ids.length === 1) return bad[0].cause;
  return {{ id: "both", lab: "多处不一致" }};
}}
function cardCodes(children, side) {{
  const leaves = (children || []).filter(r =>
    /\\.cards\\.P\\d+\\.value$/.test(r.path) || /community_cards\\[\\d+\\]\\.value$/.test(r.path)
  );
  if (!leaves.length) return null;
  return leaves.map(r => r[side]);
}}
function parseCard(code) {{
  const raw = String(code == null ? "" : code).trim();
  const compact = raw.replace(/\\s/g, "");
  if (!compact) return {{ cls: "unk", text: "—" }};
  if (/^x+$/i.test(compact) || /^x.x$/i.test(compact)) return {{ cls: "unk", text: "?" }};
  const last = compact.slice(-1);
  const suitCh = {{ s: "s", S: "s", "♠": "s", h: "h", H: "h", "♥": "h",
    d: "d", D: "d", "♦": "d", c: "c", C: "c", "♣": "c" }}[last];
  let rank = compact.slice(0, -1).toUpperCase();
  if (rank === "10") rank = "T";
  const letter = {{ s: "S", h: "H", d: "D", c: "C" }}[suitCh];
  if (!letter) return {{ cls: "unk", text: compact }};
  return {{ cls: suitCh, text: rank + letter }};
}}
function hasVal(v) {{
  if (window.E2EMatch && E2EMatch.hasVal) return E2EMatch.hasVal(v);
  if (v == null || v === "") return false;
  if (Array.isArray(v) && v[0] === "__len__") return Number(v[1]) > 0;
  if (Array.isArray(v)) return v.some(hasVal);
  return true;
}}
function emptyTxt(side, goldVal) {{
  if (window.E2EMatch && E2EMatch.emptyTxt) return E2EMatch.emptyTxt(side, goldVal);
  return (side === "gold" || !hasVal(goldVal)) ? "—" : "缺失";
}}
function emptyHtml(side, goldVal) {{
  if (window.E2EMatch && E2EMatch.emptyHtml) return E2EMatch.emptyHtml(side, goldVal);
  return (side === "gold" || !hasVal(goldVal)) ? "—" : "<span class='miss-lab'>缺失</span>";
}}
function cardsHtml(list, side, goldList) {{
  if (list == null || !list.length || list.every(v => v == null || v === "")) {{
    return emptyHtml(side || "gold", goldList !== undefined ? goldList : list);
  }}
  return list.map(code => {{
    const p = parseCard(code);
    return "<span class='pcard " + p.cls + "'>" + p.text + "</span>";
  }}).join("");
}}
function prettyScalar(v, side, goldVal) {{
  if (v == null || v === "") return emptyHtml(side || "gold", goldVal !== undefined ? goldVal : v);
  if (isLenVal(v)) return "共 " + v[1] + " 项";
  if (typeof v === "boolean") return v ? "是" : "否";
  if (v === "true") return "是";
  if (v === "false") return "否";
  if (typeof v === "number" && isFinite(v)) {{
    return Math.abs(v - Math.round(v)) < 1e-9 ? String(Math.round(v)) : String(v);
  }}
  const s = String(v).trim();
  if (/^-?\\d+\\.0+$/.test(s)) return String(Math.round(Number(s)));
  return window.E2EMatch ? E2EMatch.displayVal(v, side) : s;
}}
function ringVal(html, side, gold, v) {{
  if (side === "gold") return html;
  if (window.E2EMatch && E2EMatch.wrapDiff) {{
    const eqFn = (Array.isArray(gold) || Array.isArray(v)) && E2EMatch.cardsEq ? E2EMatch.cardsEq : null;
    return E2EMatch.wrapDiff(html, side, gold, v, eqFn);
  }}
  const eq = window.E2EMatch && E2EMatch.valuesEqual
    ? E2EMatch.valuesEqual : ((a, b) => a === b);
  if ((gold == null || gold === "") && (v == null || v === "")) return html;
  if (eq(gold, v)) return html;
  return "<span class='diff-mark " + side + "'>" + html + "</span>";
}}
function prettyVal(kind, v, side, goldVal) {{
  if (kind === "cards" || kind === "board") {{
    const list = Array.isArray(v) ? v : (v == null || v === "" ? null : [v]);
    const goldList = goldVal === undefined ? list
      : (Array.isArray(goldVal) ? goldVal : (goldVal == null || goldVal === "" ? null : [goldVal]));
    return cardsHtml(list, side, goldList);
  }}
  return prettyScalar(v, side, goldVal);
}}
function whoOf(kind, path, seat, allRows) {{
  if (kind === "seq") return fieldLabel(path);
  if (kind === "blinds") {{
    if (path.indexOf(".sb.") >= 0) return "小盲";
    if (path.indexOf(".bb.") >= 0) return "大盲";
    if (path.indexOf(".ante.") >= 0) return "前注";
  }}
  if (kind === "pot") return "总底池";
  if (kind === "board") return "公共牌";
  if (kind === "count") return "人数";
  if (kind === "showdown") return "摊牌";
  if (seat) {{
    const pos = posOf(allRows, seat);
    return seat + (pos ? " <span class='pos'>" + pos + "</span>" : "");
  }}
  return "牌桌";
}}
function packCompareRows(rows) {{
  const packed = [];
  const used = {{}};
  const seats = [];
  (rows || []).forEach(r => {{
    const s = seatOf(r.path);
    if (s && seats.indexOf(s) < 0) seats.push(s);
  }});
  seats.sort((a, b) => parseInt(a.slice(1), 10) - parseInt(b.slice(1), 10));
  seats.forEach(seat => {{
    const kids = (rows || []).filter(r => r.path === "players." + seat + ".cards" ||
      r.path.indexOf("players." + seat + ".cards.") === 0);
    if (!kids.length) return;
    kids.forEach(r => {{ used[r.path] = 1; }});
    packed.push({{
      kind: "cards",
      seat: seat,
      path: "players." + seat + ".cards",
      gold: cardCodes(kids, "gold"),
      vis: cardCodes(kids, "vis"),
      rule: cardCodes(kids, "rule"),
      cause: firstBadCause(kids),
    }});
  }});
  const boardKids = (rows || []).filter(r => r.path.indexOf("table.community_cards") === 0);
  if (boardKids.length) {{
    boardKids.forEach(r => {{ used[r.path] = 1; }});
    packed.push({{
      kind: "board",
      seat: "",
      path: "table.community_cards",
      gold: cardCodes(boardKids, "gold"),
      vis: cardCodes(boardKids, "vis"),
      rule: cardCodes(boardKids, "rule"),
      cause: firstBadCause(boardKids),
    }});
  }}
  (rows || []).forEach(r => {{
    if (used[r.path] || isContainerPath(r.path)) return;
    if (r.path.indexOf(".comment.") >= 0) {{
      const empty = (v) => v == null || v === "";
      if (empty(r.gold) && empty(r.vis) && empty(r.rule)) return;
    }}
    packed.push({{
      kind: kindOf(r.path),
      seat: seatOf(r.path),
      path: r.path,
      gold: r.gold,
      vis: r.vis,
      rule: r.rule,
      cause: r.cause || {{ id: "ok", lab: "匹配" }},
    }});
  }});
  return packed;
}}
function causeCell(cause) {{
  if (!cause || cause.id === "ok") return "<td class='cause'></td>";
  return "<td class='cause'><span class='pill " + cause.id + "'>" + cause.lab + "</span></td>";
}}
function compareTableHtml(rows, onlyDiff, skipKinds, bodyOnly) {{
  if (!window.E2EMatch) return bodyOnly ? "" : "<p class='sub'>缺少 e2e-match.js。</p>";
  skipKinds = skipKinds || [];
  const packed = packCompareRows(rows).filter(r => {{
    if (skipKinds.indexOf(r.kind) >= 0) return false;
    return !onlyDiff || (r.cause && r.cause.id !== "ok");
  }});
  if (!packed.length) return bodyOnly ? "" : "<p class='sub'>其它字段没有不一致。</p>";
  const groups = [];
  KIND_ORDER.forEach(pair => {{
    const kind = pair[0], lab = pair[1];
    const part = packed.filter(r => r.kind === kind);
    if (part.length) groups.push({{ kind, lab, part }});
  }});
  const extra = packed.filter(r => !KIND_ORDER.some(k => k[0] === r.kind));
  if (extra.length) groups.push({{ kind: "other", lab: "其它", part: extra }});
  let body = "";
  groups.forEach(g => {{
    let html = "";
    let nBad = 0;
    g.part.forEach(r => {{
      const cls = r.cause.id === "ok" ? "is-ok" : "is-diff";
      if (cls === "is-diff") nBad += 1;
      html += "<tr class='" + cls + "' title='" + r.path + "'>" +
        "<td class='who'>" + whoOf(r.kind, r.path, r.seat, rows) + "</td>" +
        "<td class='val'>" + prettyVal(r.kind, r.gold, "gold") + "</td>" +
        "<td class='val'>" + ringVal(prettyVal(r.kind, r.vis, "vis", r.gold), "vis", r.gold, r.vis) + "</td>" +
        "<td class='val'>" + ringVal(prettyVal(r.kind, r.rule, "rule", r.gold), "rule", r.gold, r.rule) + "</td>" +
        causeCell(r.cause) +
        "</tr>";
    }});
    const mark = nBad ? "<span class='fold-n'>" + nBad + " 处不一致</span>" : "";
    body += "<tbody class='cmp-fold'><tr class='sec'><td colspan='5'><span class='caret'>▾</span> " +
      g.lab + mark + "</td></tr>" + html + "</tbody>";
  }});
  if (bodyOnly) return body;
  return "<table class='compare'><thead><tr>" +
    "<th>谁</th><th>源数据</th><th>视觉</th><th>规则</th><th class='cause'>归因</th>" +
    "</tr></thead>" + body + "</table>";
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
function rejectedOf() {{
  if (ALIGN && Array.isArray(ALIGN.rejected) && ALIGN.rejected.length) return ALIGN.rejected;
  return (HANDS || []).filter(h => h && h.downstream && h.downstream.reject).map(h => ({{
    seq: h.seq,
    hand_id: h.hand_id || "",
    short: h.downstream.short || "",
    reason: h.downstream.reason || "",
    affect: h.downstream.affect || "",
  }}));
}}
function currentAlign() {{
  const rejected = rejectedOf();
  const rejSeq = {{}};
  rejected.forEach(x => {{ rejSeq[x.seq] = 1; }});
  if (ALIGN && ALIGN.n_gold != null) {{
    return Object.assign({{}}, ALIGN, {{
      rejected: rejected,
      unmatched_gold: (ALIGN.unmatched_gold || []).filter(x => !rejSeq[x.seq]),
    }});
  }}
  if (!LOOKED_UP) {{
    return {{ n_gold: CASES.length, n_fusion: null, n_matched: 0, unmatched_gold: [], unmatched_fusion: [], rejected: [], mode: "" }};
  }}
  const unmatchedGold = CASES.filter(c => !handOf(c.seq).fusionHandId && !rejSeq[c.seq])
    .map(c => ({{ seq: c.seq, hand_id: c.hand_id || "" }}));
  return {{
    n_gold: CASES.length,
    n_fusion: null,
    n_matched: CASES.length - unmatchedGold.length - rejected.length,
    unmatched_gold: unmatchedGold,
    unmatched_fusion: [],
    rejected: rejected,
    mode: "",
  }};
}}
function missBits(items, fmt) {{
  if (!items || !items.length) return "";
  const show = items.slice(0, 12).map(fmt).join("、");
  return show + (items.length > 12 ? " 等 " + items.length + " 个" : "");
}}
function rejectIndexHtml(items) {{
  if (!items || !items.length) return "";
  const show = items.slice(0, 12).map(x =>
    "<button type='button' class='err-link' data-hand-seq='" + x.seq + "'>序号 " + x.seq +
    (x.short ? " " + escTxt(x.short) : "") + "</button>"
  ).join("、");
  return show + (items.length > 12 ? " 等 " + items.length + " 手" : "");
}}
function renderAlignNote() {{
  const el = $("align-note");
  if (!el) return;
  const a = currentAlign();
  const cell = (lab, v) => "<span class='align-cell'><span class='lab'>" + lab + "</span><strong>" +
    (v == null || v === "" ? "—" : v) + "</strong></span>";
  if (!LOOKED_UP) {{
    el.className = "align-note";
    el.innerHTML = "<b>对齐</b>" + cell("源数据", a.n_gold) + cell("fusion", "—") + "<span>尚未查询 session</span>";
    return;
  }}
  const mode = a.mode === "hand_id" ? "按 hand_id 对齐"
    : (a.mode === "hero" ? "按 Hero 手牌对齐（hand_id 对不上视频名）"
    : (a.mode === "index" ? "按顺序对齐（hand_id 对不上视频名）" : "已对齐"));
  let html = "<b>对齐</b>" + cell("源数据", a.n_gold) + cell("fusion", a.n_fusion) +
    cell("对上", a.n_matched) + "<span>" + mode + "</span>";
  const rj = rejectIndexHtml(a.rejected);
  const ug = missBits(a.unmatched_gold, x => "序号 " + x.seq + (x.hand_id ? " " + escTxt(x.hand_id) : ""));
  const uf = missBits(a.unmatched_fusion, x => escTxt(x.video || x.fusionHandId || ""));
  if (rj) html += "<div class='align-miss is-rej'><b>" + a.rejected.length + " 手下游拒绝</b>：" + rj + "</div>";
  if (ug) html += "<div class='align-miss'>源数据未对上：" + ug + "</div>";
  if (uf) html += "<div class='align-miss'>fusion 多出来的手：" + uf + "</div>";
  el.className = "align-note" + ((rj || ug || uf) ? " is-bad" : "");
  el.innerHTML = html;
  el.querySelectorAll("[data-hand-seq]").forEach(btn => {{
    btn.addEventListener("click", () => openCompare(Number(btn.dataset.handSeq), true));
  }});
}}
async function hydrateRejects() {{
  if (!LOOKED_UP || !SESSION_ID || !HANDS.length) return;
  if (!window.E2EMatch || !E2EMatch.fetchRejects || !E2EMatch.attachDownstream) return;
  if (HANDS.some(h => h && h.downstream && h.downstream.reject)) {{
    renderAlignNote();
    return;
  }}
  try {{
    const segs = await E2EMatch.fetchRejects({{ sessionId: SESSION_ID, cases: CASES }});
    const rejected = E2EMatch.attachDownstream(HANDS, HANDS.map(() => null), segs);
    ALIGN = Object.assign({{}}, ALIGN || {{}}, {{ rejected: rejected }});
    if (ALIGN.unmatched_gold) {{
      const rejSeq = {{}};
      rejected.forEach(x => {{ rejSeq[x.seq] = 1; }});
      ALIGN.unmatched_gold = ALIGN.unmatched_gold.filter(x => !rejSeq[x.seq]);
    }}
    renderAlignNote();
    renderHandMod();
    if (drawerSeq) paintReject(drawerSeq);
    try {{
      const saved = JSON.parse(localStorage.getItem("e2e-rates-" + BATCH_ID) || "null");
      if (saved && Array.isArray(saved.hands)) {{
        saved.hands = HANDS;
        saved.align = ALIGN;
        localStorage.setItem("e2e-rates-" + BATCH_ID, JSON.stringify(saved));
      }}
    }} catch (e) {{}}
  }} catch (e) {{}}
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
function fmtSeqOne(lab, s) {{
  if (!s) return "<span class='seq-na'>" + lab + " —</span>";
  if (s.miss) return "<span class='seq-miss'>" + lab + " 缺失</span>";
  if (s.exact) return "<span class='seq-ok'>" + lab + " 整条</span>";
  const bits = lab + " " + (s.step_n || 0) + "/" + (s.step_t || 0) + "步" +
    (s.hint ? " · " + escTxt(s.hint) : "");
  return "<span class='seq-bad'>" + bits + "</span>";
}}
function fmtActionSeq(pack) {{
  if (!pack) return "<span class='seq-na'>重新查询后出整手序列</span>";
  return "<div class='seq-lines'>" +
    fmtSeqOne("源→视", pack.gt_vis) +
    fmtSeqOne("视→规", pack.vis_rule) +
    fmtSeqOne("源→规", pack.gt_rule) +
    "</div>";
}}
function goldOf(seq) {{
  if (goldCache[seq]) return goldCache[seq];
  const pack = window.E2E_GOLD;
  const tree = pack && pack.trees && pack.trees[seq - 1];
  let hist = null;
  if (window.E2EMatch && E2EMatch.packHistories) {{
    const p = E2EMatch.packHistories(pack && pack.histories && pack.histories[seq - 1], tree, null);
    hist = p && p.gold;
  }}
  goldCache[seq] = {{ tree: tree, hist: hist }};
  return goldCache[seq];
}}
function gVal(seq, path) {{
  const g = goldOf(seq);
  return valAt(g.tree, path, g.hist);
}}
function sidePack(seq, side) {{
  if (side === "gold") return goldOf(seq);
  const st = stageCache[seq];
  if (!st || !st.done) return {{ tree: null, hist: null }};
  return {{
    tree: side === "vis" ? st.vis : st.rule,
    hist: st.hist && (side === "vis" ? st.hist.vis : st.hist.rule),
  }};
}}
function sVal(seq, side, path) {{
  if (side === "gold") return gVal(seq, path);
  const p = sidePack(seq, side);
  return valAt(p.tree, path, p.hist);
}}
function sideReadyHtml(seq, side) {{
  if (side === "gold") return null;
  if (!LOOKED_UP) return "—";
  const st = stageCache[seq];
  if (!st || !st.done) return "…";
  return null;
}}
function pathErr(pairId, seq, paths) {{
  if (!LOOKED_UP) return false;
  const stats = FIELD_STATS[pairId] || {{}};
  const known = (paths || []).filter(p => stats[p] && Array.isArray(stats[p].errors));
  if (known.length) {{
    return known.some(p => stats[p].errors.indexOf(seq) >= 0);
  }}
  const side = pairId === "gt_vis" ? "vis" : "rule";
  const eq = window.E2EMatch && E2EMatch.valuesEqual
    ? (a, b) => E2EMatch.valuesEqual(a, b)
    : (a, b) => a === b;
  const posEq = window.E2EMatch && E2EMatch.posEq
    ? (a, b) => E2EMatch.posEq(a, b)
    : eq;
  return (paths || []).some(p => {{
    if (window.E2EMatch && E2EMatch.skipComparePath && E2EMatch.skipComparePath(p)) return false;
    const key = window.E2EMatch && E2EMatch.playerSeatKey ? E2EMatch.playerSeatKey(p) : "";
    const follow = window.E2EMatch && E2EMatch.isPlayerFollowOn && E2EMatch.isPlayerFollowOn(p);
    if (follow && key) {{
      const occ = sVal(seq, side, "players." + key + ".position.value") != null
        || sVal(seq, side, "players." + key + ".name.value") != null
        || sVal(seq, side, "players." + key + ".seat.value") != null;
      if (!occ) return false;
    }}
    if (key && /\\.position\\.value$/.test(p)) {{
      const g = gVal(seq, p);
      const v = sVal(seq, side, p);
      if (g == null || g === "") return false;
      if (v == null || v === "") return true;
      return !posEq(g, v);
    }}
    const g = gVal(seq, p);
    const v = sVal(seq, side, p);
    if ((g == null || g === "") && (v == null || v === "")) return false;
    return !eq(g, v);
  }});
}}
function tdVal(seq, side, paths, html, extraCls) {{
  const ready = sideReadyHtml(seq, side);
  const bits = extraCls ? extraCls.slice() : [];
  bits.push("is-click");
  if (ready === "…") bits.push("is-pending");
  if (side !== "gold" && LOOKED_UP && ready !== "—" && ready !== "…") {{
    if (pathErr(side === "vis" ? "gt_vis" : "gt_rule", seq, paths)) {{
      bits.push(side === "vis" ? "is-vis" : "is-rule");
    }}
  }}
  return "<td class='" + bits.join(" ") + "' data-hand-seq='" + seq + "'>" +
    (ready || html) + "</td>";
}}
function seatLive(seq, i) {{
  const n = gVal(seq, "table.player_count.value");
  if (n != null && Number(n) <= i) return false;
  return gVal(seq, "players.P" + i + ".seat.value") != null
    || gVal(seq, "players.P" + i + ".position.value") != null
    || gVal(seq, "players.P" + i + ".chips.value") != null;
}}
function boardPaths() {{
  const p = ["table.community_cards"];
  for (let i = 0; i < 5; i++) p.push("table.community_cards[" + i + "].value");
  return p;
}}
function seatPaths(i, kind) {{
  const pre = "players.P" + i + ".";
  if (kind === "cards") return [pre + "cards", pre + "cards.P0.value", pre + "cards.P1.value"];
  if (kind === "init_chips") return [pre + "init_chips.value"];
  if (kind === "chips") return [pre + "chips.value"];
  if (kind === "position") return [pre + "position.value"];
  if (kind === "dealer") return [pre + "dealer.value"];
  if (kind === "status") return [pre + "status.value"];
  if (kind === "name") return [pre + "name.value"];
  if (kind === "seat") return [pre + "seat.value"];
  return [];
}}
function histActN(hist) {{
  if (!hist || !Array.isArray(hist.actions)) return null;
  return hist.actions.length;
}}
function fmtSeqSide(seq, side, c, h) {{
  const ready = sideReadyHtml(seq, side);
  if (ready) return ready;
  if (side === "gold") {{
    const n = histActN(goldOf(seq).hist);
    if (n != null) return n + "步";
    return c.n_vol_actions != null ? c.n_vol_actions + "步" : "—";
  }}
  const pack = h.action_seq || {{}};
  const s = (side === "vis" ? pack.gt_vis : pack.gt_rule) || {{}};
  if (LOOKED_UP && (s.miss || s.exact || s.step_t != null)) {{
    if (s.miss) {{
      const gn = histActN(goldOf(seq).hist);
      return emptyHtml(side, gn > 0 ? gn : null);
    }}
    if (s.exact) return "整条";
    return (s.step_n || 0) + "/" + (s.step_t || 0);
  }}
  const n = histActN(sidePack(seq, side).hist);
  const gn = histActN(goldOf(seq).hist);
  return n != null ? n + "步" : emptyHtml(side, gn > 0 ? gn : null);
}}
function seqSideCls(seq, side, h) {{
  const bits = ["seq"];
  const ready = sideReadyHtml(seq, side);
  if (side === "gold" || !LOOKED_UP || !h.action_seq || ready === "—" || ready === "…") return bits;
  const s = (side === "vis" ? h.action_seq.gt_vis : h.action_seq.gt_rule) || {{}};
  if (s.miss || !s.exact) bits.push(side === "vis" ? "is-vis" : "is-rule");
  return bits;
}}
function seatLeafTh(i) {{
  return "<th class='pos-lab'>P" + i + "</th>";
}}
function gridHead(seqs) {{
  const seats = gridSeatList();
  const cards = gridCardSeatList();
  const n = seats.length;
  const groups = [
    {{ lab: "牌桌初始信息", span: 4 }},
    {{ lab: "座位号", span: n }},
    {{ lab: "昵称", span: n }},
    {{ lab: "位置", span: n }},
    {{ lab: "Dealer", span: n }},
    {{ lab: "玩家初始筹码", span: n }},
    {{ lab: "玩家手牌", span: cards.length }},
    {{ lab: "公牌", span: 1 }},
    {{ lab: "行动序列", span: 1 }},
    {{ lab: "结算", span: 2 }},
    {{ lab: "玩家最终筹码", span: n }},
    {{ lab: "终局状态", span: n }},
    {{ lab: "准确率", span: 2 }},
  ].filter(g => g.span > 0);
  const leaves = ["人数","小盲","大盲","前注"];
  const gRow = "<th class='pin' rowspan='2'>序号</th>" +
    "<th class='pin-id' rowspan='2'>hand_id</th>" +
    "<th class='pin-src' rowspan='2'>来源</th>" +
    "<th class='pin-hero' rowspan='2'>Hero 手牌</th>" +
    groups.map(g => "<th class='g-span' colspan='" + g.span + "'>" + g.lab + "</th>").join("");
  const subBits = leaves.map(lab => "<th>" + lab + "</th>");
  ["seat","name","position","dealer","init_chips"].forEach(() => {{
    seats.forEach(i => subBits.push(seatLeafTh(i)));
  }});
  cards.forEach(i => subBits.push(seatLeafTh(i)));
  subBits.push("<th>公牌</th>","<th>步数</th>","<th>总底池</th>","<th>摊牌</th>");
  seats.forEach(i => subBits.push(seatLeafTh(i)));
  seats.forEach(i => subBits.push(seatLeafTh(i)));
  subBits.push("<th>视觉</th>","<th>规则</th>");
  return "<thead><tr class='g'>" + gRow + "</tr><tr class='sub'>" + subBits.join("") + "</tr>" +
    gridFootRows(seqs) + "</thead>";
}}
function gridFieldCols() {{
  const cols = [
    {{ kind: "cards", hero: true, needCards: true }},
    {{ paths: ["table.player_count.value"] }},
    {{ paths: ["table.sb.value"] }},
    {{ paths: ["table.bb.value"] }},
    {{ paths: ["table.ante.value"] }},
  ];
  ["seat","name","position","dealer","init_chips"].forEach(kind => {{
    gridSeatList().forEach(i => cols.push({{ kind: kind, seat: i }}));
  }});
  gridCardSeatList().forEach(i => cols.push({{ kind: "cards", seat: i, needCards: true }}));
  cols.push({{ paths: boardPaths() }});
  cols.push({{ kind: "seq" }});
  cols.push({{ paths: ["table.pot.value"] }});
  cols.push({{ paths: ["table.showdown.value"] }});
  ["chips","status"].forEach(kind => {{
    gridSeatList().forEach(i => cols.push({{ kind: kind, seat: i }}));
  }});
  return cols;
}}
function colPaths(seq, col) {{
  if (col.hero) {{
    const i = heroSeatOf(seq);
    if (i == null) return [];
    return seatPaths(i, col.kind || "cards");
  }}
  if (col.seat != null) {{
    if (!seatLive(seq, col.seat)) return [];
    return seatPaths(col.seat, col.kind);
  }}
  return col.paths || [];
}}
function footPct(ok, tot) {{
  if (!tot) return {{ txt: "—", cls: "is-empty", title: "" }};
  const v = 100 * ok / tot;
  const cls = ok === tot ? "is-ok" : "is-miss";
  return {{
    txt: v.toFixed(1) + "%",
    cls: cls,
    title: ok + "/" + tot + " 手一致",
  }};
}}
function pairSideMiss(pairId, seq) {{
  const h = handOf(seq) || {{}};
  if (pairId === "gt_vis") return !!h.miss_vis;
  if (pairId === "gt_rule") return !!h.miss_rule;
  if (pairId === "vis_rule") return !!(h.miss_vis || h.miss_rule);
  return false;
}}
function footFieldCell(pairId, col, seqs) {{
  if (!LOOKED_UP) return "<td class='is-empty" + (col.hero ? " pin-hero" : "") + "'>—</td>";
  if (col.kind === "seq") {{
    let ok = 0, tot = 0, has = false;
    seqs.forEach(seq => {{
      if (pairSideMiss(pairId, seq)) return;
      const s = (handOf(seq).action_seq || {{}})[pairId];
      if (!s || s.miss) return;
      has = true;
      tot += 1;
      if (s.exact) ok += 1;
    }});
    if (!has) {{
      const row = SEQ_RATES[pairId] || {{}};
      if (row.exact_t) return "<td class='rate " + ((row.exact_n || 0) === row.exact_t ? "is-ok" : "is-miss") +
        "' title='整条行动序列'>" + (100 * (row.exact_n || 0) / row.exact_t).toFixed(1) + "%</td>";
      const txt = fmtRate(row.exact) || "—";
      return "<td class='rate" + (txt === "—" ? " is-empty" : "") + "'>" + txt + "</td>";
    }}
    const p = footPct(ok, tot);
    return "<td class='rate " + p.cls + "' title='" + p.title + "'>" + p.txt + "</td>";
  }}
  const stats = FIELD_STATS[pairId] || {{}};
  let ok = 0, tot = 0, errPath = "";
  seqs.forEach(seq => {{
    if (pairSideMiss(pairId, seq)) return;
    if (col.seat != null && !seatLive(seq, col.seat)) return;
    if (col.needCards && col.seat != null && !seatHasCards(seq, col.seat)) return;
    if (col.hero && col.needCards && !seatHasCards(seq, heroSeatOf(seq))) return;
    const paths = colPaths(seq, col);
    if (!paths.length) return;
    const known = paths.filter(p => stats[p] && stats[p].total);
    if (!known.length) {{
      const st = stageCache[seq];
      if (!st || !st.done) return;
    }}
    tot += 1;
    if (!pathErr(pairId, seq, paths)) ok += 1;
    else if (!errPath) errPath = known.find(p => stats[p] && stats[p].n_error) || paths[0] || "";
  }});
  if (!tot) return "<td class='is-empty" + (col.hero ? " pin-hero" : "") + "'>—</td>";
  const p = footPct(ok, tot);
  const seatAttr = col.seat != null
    ? " data-foot-seat='" + col.seat + "' data-foot-kind='" + escTxt(col.kind || "") + "'" +
      (col.needCards ? " data-foot-cards='1'" : "")
    : (col.hero ? " data-foot-hero='1'" : "");
  return "<td class='rate " + p.cls + " is-click" + (col.hero ? " pin-hero" : "") + "' title='" + p.title +
    "' data-foot-pair='" + pairId + "'" + seatAttr +
    " data-foot-path='" + encodeURIComponent(errPath || (col.hero ? "hero:cards" : (col.seat != null ? ("seat:" + col.seat + ":" + col.kind) : ""))) + "'>" +
    p.txt + "</td>";
}}
function footOverallCell(pairId, selfId, seqs) {{
  if (pairId !== selfId) return "<td class='is-empty'>—</td>";
  if (!LOOKED_UP) return "<td class='is-empty'>—</td>";
  let s = 0, n = 0;
  seqs.forEach(seq => {{
    const v = handOf(seq)[selfId];
    if (v == null || v === "") return;
    s += Number(v);
    n += 1;
  }});
  const v = n ? s / n : (PAIR_RATES[selfId] || {{}}).all;
  const txt = fmtRate(v) || "—";
  return "<td class='rate acc" + (txt === "—" ? " is-empty" : "") + "'>" + txt + "</td>";
}}
function gridFootRows(seqs) {{
  const cols = gridFieldCols();
  const visCells = cols.map(col => footFieldCell("gt_vis", col, seqs)).join("");
  const ruleCells = cols.map(col => footFieldCell("gt_rule", col, seqs)).join("");
  const nLab = seqs.length + "手";
  return "<tr class='foot-vis'>" +
      "<td class='pin'>汇总</td>" +
      "<td class='pin-id'>" + nLab + "</td>" +
      "<td class='pin-src src'>视觉准确率</td>" +
      visCells +
      footOverallCell("gt_vis", "gt_vis", seqs) +
      footOverallCell("gt_vis", "gt_rule", seqs) +
    "</tr>" +
    "<tr class='foot-rule'>" +
      "<td class='pin'></td>" +
      "<td class='pin-id'></td>" +
      "<td class='pin-src src'>规则准确率</td>" +
      ruleCells +
      footOverallCell("gt_rule", "gt_vis", seqs) +
      footOverallCell("gt_rule", "gt_rule", seqs) +
    "</tr>";
}}
function stickGridHead(table) {{
  if (!table) return;
  const g = table.querySelector("thead tr.g");
  const sub = table.querySelector("thead tr.sub");
  const vis = table.querySelector("thead tr.foot-vis");
  const rule = table.querySelector("thead tr.foot-rule");
  const gH = g ? g.getBoundingClientRect().height : 0;
  const subH = sub ? sub.getBoundingClientRect().height : 0;
  const visH = vis ? vis.getBoundingClientRect().height : 0;
  if (sub) sub.querySelectorAll("th").forEach(th => {{ th.style.top = gH + "px"; }});
  if (vis) vis.querySelectorAll("td").forEach(td => {{ td.style.top = (gH + subH) + "px"; }});
  if (rule) rule.querySelectorAll("td").forEach(td => {{ td.style.top = (gH + subH + visH) + "px"; }});
}}
function scalarCell(seq, side, path, fallback) {{
  const v = sVal(seq, side, path);
  const g = gVal(seq, path);
  const shown = (v == null || v === "") && side === "gold" ? fallback : v;
  const goldShown = (g == null || g === "") ? fallback : g;
  return tdVal(seq, side, [path], prettyScalar(shown, side, goldShown));
}}
function posOccupied(seq, side, i) {{
  const pre = "players.P" + i + ".";
  return sVal(seq, side, pre + "position.value") != null
    || sVal(seq, side, pre + "name.value") != null
    || sVal(seq, side, pre + "seat.value") != null;
}}
function posCell(seq, side, pos, kind) {{
  const i = goldSeatOfPos(seq, pos);
  if (i == null) return "<td class='is-empty'>" + emptyHtml(side, null) + "</td>";
  if (kind === "cards" && !goldHasCards(seq, pos)) {{
    return "<td class='is-empty'>" + emptyHtml(side, null) + "</td>";
  }}
  if (kind === "position") {{
    const paths = seatPaths(i, "position");
    if (side === "gold") return tdVal(seq, side, paths, "<span class='occ-ok'>有</span>");
    const html = posOccupied(seq, side, i) ? "<span class='occ-ok'>有</span>" : emptyHtml(side, true);
    return tdVal(seq, side, paths, html);
  }}
  return seatCell(seq, side, i, kind);
}}
function heroCardCell(seq, side) {{
  const i = heroSeatOf(seq);
  if (i == null) return tdVal(seq, side, [], emptyHtml(side, null), ["pin-hero"]);
  return seatCell(seq, side, i, "cards").replace("<td class='", "<td class='pin-hero ");
}}
function seatCell(seq, side, i, kind) {{
  if (!seatLive(seq, i)) return "<td class='is-empty'>" + emptyHtml(side, null) + "</td>";
  const paths = seatPaths(i, kind);
  const pre = "players.P" + i + ".";
  let html;
  if (kind === "cards") {{
    const goldCards = [gVal(seq, pre + "cards.P0.value"), gVal(seq, pre + "cards.P1.value")];
    html = cardsHtml([sVal(seq, side, pre + "cards.P0.value"), sVal(seq, side, pre + "cards.P1.value")], side, goldCards);
  }} else if (kind === "status") {{
    const raw = sVal(seq, side, pre + "status.value");
    html = raw == null || raw === ""
      ? emptyHtml(side, gVal(seq, pre + "status.value"))
      : (GRID_STATUS[raw] || prettyScalar(raw, side, gVal(seq, pre + "status.value")));
  }} else html = prettyScalar(sVal(seq, side, paths[0]), side, gVal(seq, paths[0]));
  return tdVal(seq, side, paths, html);
}}
function gridHandRows(c) {{
  const seq = c.seq;
  const h = handOf(seq);
  const hid = h.hand_id || c.hand_id || "";
  const seats = gridSeatList();
  const cards = gridCardSeatList();
  return GRID_SIDES.map((side, si) => {{
    const first = si === 0;
    const last = si === GRID_SIDES.length - 1;
    const pin = first
      ? "<td class='pin num is-click' rowspan='3' data-hand-seq='" + seq + "'>" + seq + "</td>" +
        "<td class='pin-id is-click' rowspan='3' data-hand-seq='" + seq + "'><code>" + escTxt(hid) + "</code></td>"
      : "";
    const rates = first
      ? "<td class='rate acc is-click' rowspan='3' data-hand-seq='" + seq + "'>" + fmtPct(h.gt_vis) + "</td>" +
        "<td class='rate acc is-click' rowspan='3' data-hand-seq='" + seq + "'>" + fmtPct(h.gt_rule) + "</td>"
      : "";
    return "<tr class='side-" + side.id + (last ? " hand-end" : "") + "'>" + pin +
      "<td class='pin-src src'>" + side.lab + "</td>" +
      heroCardCell(seq, side.id) +
      scalarCell(seq, side.id, "table.player_count.value", c.n_players) +
      scalarCell(seq, side.id, "table.sb.value", c.sb) +
      scalarCell(seq, side.id, "table.bb.value", c.bb) +
      scalarCell(seq, side.id, "table.ante.value", c.ante_j != null ? c.ante_j : c.ante) +
      seats.map(i => seatCell(seq, side.id, i, "seat")).join("") +
      seats.map(i => seatCell(seq, side.id, i, "name")).join("") +
      seats.map(i => seatCell(seq, side.id, i, "position")).join("") +
      seats.map(i => seatCell(seq, side.id, i, "dealer")).join("") +
      seats.map(i => seatCell(seq, side.id, i, "init_chips")).join("") +
      cards.map(i => seatHasCards(seq, i) ? seatCell(seq, side.id, i, "cards") : "<td class='is-empty'>" + emptyHtml(side.id, null) + "</td>").join("") +
      tdVal(seq, side.id, boardPaths(), cardsHtml(
        boardPaths().slice(1).map(p => sVal(seq, side.id, p)),
        side.id,
        boardPaths().slice(1).map(p => gVal(seq, p))
      )) +
      tdVal(seq, side.id, ["action_seq"], fmtSeqSide(seq, side.id, c, h), seqSideCls(seq, side.id, h)) +
      scalarCell(seq, side.id, "table.pot.value", c.total_pot) +
      scalarCell(seq, side.id, "table.showdown.value", c.showdown) +
      seats.map(i => seatCell(seq, side.id, i, "chips")).join("") +
      seats.map(i => seatCell(seq, side.id, i, "status")).join("") +
      rates +
      "</tr>";
  }}).join("");
}}
async function loadGridStage(seq) {{
  const epoch = stageEpoch;
  const goldPack = window.E2E_GOLD;
  const gold = goldPack && goldPack.trees && goldPack.trees[seq - 1];
  const h = handOf(seq);
  try {{
    if (!window.E2EMatch || !gold || !h.fusionHandId || !h.sessionId) {{
      if (epoch !== stageEpoch) return;
      stageCache[seq] = {{ vis: null, rule: null, hist: null, done: true, error: !h.fusionHandId ? "缺 fusion" : null }};
      return;
    }}
    const body = await fetchBody(seq);
    if (epoch !== stageEpoch) return;
    const stages = E2EMatch.stageTrees(gold, body);
    const hist = E2EMatch.packHistories
      ? E2EMatch.packHistories(goldPack.histories && goldPack.histories[seq - 1], gold, body)
      : null;
    stageCache[seq] = {{
      vis: stages && stages.vis || null,
      rule: stages && stages.rule || null,
      hist: hist,
      done: true,
      error: null,
    }};
  }} catch (e) {{
    if (epoch !== stageEpoch) return;
    stageCache[seq] = {{ vis: null, rule: null, hist: null, done: true, error: String((e && e.message) || e) }};
  }}
}}
function renderHandGrid() {{
  const box = $("hand-grid-wrap");
  if (!box) return;
  const only = $("grid-only-err") && $("grid-only-err").checked;
  const alignedOnly = $("grid-only-aligned") && $("grid-only-aligned").checked;
  const q = (($("grid-q") && $("grid-q").value) || "").trim().toLowerCase();
  const rows = CASES.filter(c => {{
    const nErr = LOOKED_UP ? nErrorForSeq(c.seq) : 0;
    if (only && LOOKED_UP && !nErr) return false;
    if (alignedOnly && LOOKED_UP && !handAligned(c.seq)) return false;
    if (q) {{
      const blob = (c.seq + " " + (c.hand_id || "")).toLowerCase();
      if (!blob.includes(q)) return false;
    }}
    return true;
  }});
  if ($("grid-count")) $("grid-count").textContent = "显示 " + rows.length + " / " + CASES.length;
  const body = rows.map(gridHandRows).join("");
  box.innerHTML = "<table class='hand-grid'>" + gridHead(rows.map(c => c.seq)) + "<tbody>" +
    (body || "<tr><td colspan='" + gridColCount() + "'>没有匹配的手。</td></tr>") + "</tbody></table>";
  stickGridHead(box.querySelector("table.hand-grid"));
  box.querySelectorAll("[data-hand-seq]").forEach(el => {{
    el.addEventListener("click", () => {{
      if (!LOOKED_UP) {{
        alert("还没有匹配率。请先点「重新查询」。");
        return;
      }}
      openCompare(Number(el.dataset.handSeq), true);
    }});
  }});
  box.querySelectorAll("[data-foot-path]").forEach(el => {{
    el.addEventListener("click", () => {{
      if (!LOOKED_UP) {{
        alert("还没有匹配率。请先点「重新查询」。");
        return;
      }}
      if (el.dataset.footPair) {{
        currentPair = el.dataset.footPair;
        if (typeof syncPairUi === "function") syncPairUi();
      }}
      if (el.dataset.footHero) {{
        openPosErrorHands(el.dataset.footPair || currentPair, "", "cards", true, true);
        return;
      }}
      if (el.dataset.footSeat != null && el.dataset.footSeat !== "") {{
        openPosErrorHands(
          el.dataset.footPair || currentPair,
          el.dataset.footSeat,
          el.dataset.footKind || "",
          el.dataset.footCards === "1"
        );
        return;
      }}
      openErrorHands(decodeURIComponent(el.dataset.footPath));
    }});
  }});
  if (!LOOKED_UP) return;
  const seqs = rows.map(c => c.seq);
  const need = seqs.filter(s => !stageCache[s] || (!stageCache[s].done && !stageCache[s].loading));
  if (!need.length) return;
  need.forEach(s => {{
    stageCache[s] = Object.assign({{ vis: null, rule: null, hist: null }}, stageCache[s] || {{}}, {{ loading: true }});
  }});
  const epoch = stageEpoch;
  mapPool(need, 4, loadGridStage).then(() => {{
    if (epoch !== stageEpoch) return;
    renderHandGrid();
  }});
}}
["grid-only-err","grid-only-aligned","grid-q"].forEach(id => {{
  const el = $(id);
  if (!el) return;
  el.addEventListener("input", renderHandGrid);
  el.addEventListener("change", renderHandGrid);
}});
if ($("refresh-grid")) $("refresh-grid").addEventListener("click", () => {{
  if ($("refresh-match")) $("refresh-match").click();
  else refreshMatch();
}});
renderHandGrid();
function showDrawer() {{
  $("drawer-mask").classList.add("show");
}}
let clipSrc = "";
function pipAvailable() {{
  const vid = $("drawer-clip-video");
  return !!(vid && (
    (document.pictureInPictureEnabled && vid.requestPictureInPicture) ||
    vid.webkitSetPresentationMode
  ));
}}
function syncPipBtn() {{
  const btn = $("drawer-clip-pip");
  const box = $("drawer-clip");
  const vid = $("drawer-clip-video");
  if (!btn) return;
  btn.hidden = !(box && box.open && pipAvailable());
  const inPip = !!(vid && (
    document.pictureInPictureElement === vid ||
    vid.webkitPresentationMode === "picture-in-picture"
  ));
  btn.textContent = inPip ? "退出画中画" : "画中画";
}}
function ensureClipSrc() {{
  const vid = $("drawer-clip-video");
  if (!vid || !clipSrc) return;
  vid.preload = "metadata";
  if (vid.getAttribute("src") !== clipSrc) vid.src = clipSrc;
  else if (vid.readyState === 0) vid.load();
}}
async function togglePip(e) {{
  if (e) {{ e.preventDefault(); e.stopPropagation(); }}
  const vid = $("drawer-clip-video");
  if (!vid || !pipAvailable()) return;
  ensureClipSrc();
  try {{
    if (document.pictureInPictureElement === vid) {{
      await document.exitPictureInPicture();
    }} else if (vid.webkitPresentationMode === "picture-in-picture" && vid.webkitSetPresentationMode) {{
      vid.webkitSetPresentationMode("inline");
    }} else {{
      if (document.pictureInPictureEnabled && vid.requestPictureInPicture) {{
        const pipP = vid.requestPictureInPicture();
        vid.play().catch(() => {{}});
        await pipP;
      }} else if (vid.webkitSetPresentationMode) {{
        vid.webkitSetPresentationMode("picture-in-picture");
        vid.play().catch(() => {{}});
      }}
    }}
  }} catch (err) {{}}
  syncPipBtn();
}}
function hideClip() {{
  const box = $("drawer-clip");
  const vid = $("drawer-clip-video");
  const link = $("drawer-clip-link");
  const urlEl = $("drawer-clip-url");
  clipSrc = "";
  if (vid) {{
    if (document.pictureInPictureElement === vid) {{
      document.exitPictureInPicture().catch(() => {{}});
    }} else if (vid.webkitPresentationMode === "picture-in-picture" && vid.webkitSetPresentationMode) {{
      vid.webkitSetPresentationMode("inline");
    }}
    vid.pause();
    vid.removeAttribute("src");
    try {{ vid.load(); }} catch (e) {{}}
  }}
  if (link) link.removeAttribute("href");
  if (urlEl) {{
    urlEl.removeAttribute("href");
    urlEl.textContent = "";
  }}
  if (box) {{
    box.open = false;
    box.hidden = true;
  }}
  syncPipBtn();
}}
function viewerPageUrl(fusionHandId) {{
  if (!fusionHandId) return "";
  const rel = "../../poker-hand-viewer.html?handId=" + encodeURIComponent(fusionHandId);
  try {{ return new URL(rel, location.href).href; }} catch (e) {{ return rel; }}
}}
function showClip(url, fusionHandId) {{
  const box = $("drawer-clip");
  const vid = $("drawer-clip-video");
  const name = $("drawer-clip-name");
  const link = $("drawer-clip-link");
  const urlEl = $("drawer-clip-url");
  if (!box || !vid || !url) {{
    hideClip();
    return;
  }}
  const label = (window.E2EMatch && E2EMatch.videoName)
    ? E2EMatch.videoName(url) : String(url).split("/").pop();
  if (name) name.textContent = "原始切片 · " + (label || "视频");
  const jump = viewerPageUrl(fusionHandId) || url;
  if (link) {{
    link.href = jump;
    link.hidden = false;
  }}
  if (urlEl) {{
    urlEl.href = jump;
    urlEl.textContent = jump;
  }}
  clipSrc = url;
  box.open = false;
  box.hidden = false;
  if (vid.getAttribute("src")) {{
    vid.pause();
    vid.removeAttribute("src");
    try {{ vid.load(); }} catch (e) {{}}
  }}
  syncPipBtn();
}}
async function clipUrlOf(h) {{
  if (h && h.videoUrl) return h.videoUrl;
  if (!window.E2EMatch || !E2EMatch.clipUrlForHand || !h || !h.fusionHandId || !h.sessionId) return "";
  try {{
    return await E2EMatch.clipUrlForHand(SAVED_API, h.sessionId, h.fusionHandId) || "";
  }} catch (e) {{
    return "";
  }}
}}
function closeDrawer() {{
  hideClip();
  $("drawer-mask").classList.remove("show");
}}
function setDrawerHelp(on) {{
  const el = $("drawer-help");
  if (!el) return;
  el.hidden = !on;
  el.removeAttribute("open");
}}
function openPosErrorHands(pairId, seat, kind, needCards, hero) {{
  const token = hero ? "hero:cards" : ("seat:" + seat + ":" + kind);
  drawerPath = token;
  hideClip();
  setDrawerHelp(false);
  $("drawer-title").textContent = "字段差异";
  $("drawer-sub").textContent = hero ? "Hero 手牌" : ((GRID_KIND_LAB[kind] || kind) + " · P" + seat);
  $("drawer-filter").hidden = true;
  $("drawer-back").hidden = true;
  const col = hero
    ? {{ kind: "cards", hero: true, needCards: true }}
    : {{ kind: kind, seat: Number(seat), needCards: !!needCards }};
  const pathBySeq = {{}};
  const seqs = [];
  let nTot = 0;
  CASES.forEach(c => {{
    const seq = c.seq;
    if (pairSideMiss(pairId, seq)) return;
    if (!hero && !seatLive(seq, Number(seat))) return;
    if (!hero && needCards && !seatHasCards(seq, Number(seat))) return;
    if (hero && needCards && !seatHasCards(seq, heroSeatOf(seq))) return;
    const paths = colPaths(seq, col);
    if (!paths.length) return;
    nTot += 1;
    if (!pathErr(pairId, seq, paths)) return;
    seqs.push(seq);
    pathBySeq[seq] = paths[0];
  }});
  if (!LOOKED_UP) {{
    $("drawer-status").textContent = "还没有匹配率。请先点「重新查询」。";
    clearDrawerMain();
    showDrawer();
    return;
  }}
  if (!seqs.length) {{
    $("drawer-status").textContent = "这一字段没有出错手。";
    clearDrawerMain();
    showDrawer();
    return;
  }}
  $("drawer-status").textContent = seqs.length + "/" + nTot + " 手该字段不一致。";
  clearDrawerMain();
  $("drawer-body").innerHTML =
    "<table class='err-seq compare'><thead><tr>" +
    "<th class='num'>序号</th><th>hand_id</th><th>源数据</th><th>视觉</th><th>规则</th><th></th>" +
    "</tr></thead><tbody>" +
    seqs.map(seq => errorSeqRow(pathBySeq[seq], seq)).join("") +
    "</tbody></table>";
  showDrawer();
  bindErrorSeqButtons(token);
  mapPool(seqs, 4, seq => loadErrorSeq(pathBySeq[seq], seq));
}}
function openErrorHands(path) {{
  drawerPath = path;
  hideClip();
  setDrawerHelp(false);
  $("drawer-title").textContent = "字段差异";
  $("drawer-sub").textContent = fieldLabel(path) + " · " + path;
  $("drawer-filter").hidden = true;
  $("drawer-back").hidden = true;
  const seqs = fieldErrors(path);
  const st = (FIELD_STATS[pairOf(currentPair).id] || {{}})[path] || {{}};
  const nErr = st.n_error || seqs.length;
  const nTot = st.total || 0;
  if (!LOOKED_UP) {{
    $("drawer-status").textContent = "还没有匹配率。请先点「重新查询」。";
    clearDrawerMain();
    showDrawer();
    return;
  }}
  if (!seqs.length) {{
    $("drawer-status").textContent = nErr
      ? "记下 " + nErr + "/" + nTot + " 手出错，但本机没有序号清单。重新查询一次即可。"
      : "这一字段没有出错手。";
    clearDrawerMain();
    showDrawer();
    return;
  }}
  $("drawer-status").textContent = nErr + "/" + nTot + " 手该字段不一致。";
  clearDrawerMain();
  $("drawer-body").innerHTML =
    "<table class='err-seq compare'><thead><tr>" +
    "<th class='num'>序号</th><th>hand_id</th><th>源数据</th><th>视觉</th><th>规则</th><th></th>" +
    "</tr></thead><tbody>" +
    seqs.map(seq => errorSeqRow(path, seq)).join("") +
    "</tbody></table>";
  showDrawer();
  bindErrorSeqButtons(path);
  mapPool(seqs, 4, seq => loadErrorSeq(path, seq));
}}
function goldValNow(path, seq) {{
  const M = window.E2EMatch;
  const goldPack = window.E2E_GOLD;
  const gold = goldPack && goldPack.trees && goldPack.trees[seq - 1];
  if (!M || !gold) return undefined;
  const pack = M.packHistories
    ? M.packHistories(goldPack.histories && goldPack.histories[seq - 1], gold, null)
    : null;
  return valAt(gold, path, pack && pack.gold);
}}
function errorSeqRow(path, seq) {{
  const h = handOf(seq);
  const c = caseOf(seq);
  const hid = escTxt((h.hand_id || c.hand_id || ""));
  const M = window.E2EMatch;
  const goldTxt = M ? M.displayVal(goldValNow(path, seq)) : "—";
  return "<tr id='err-row-" + seq + "' data-err-path='" + encodeURIComponent(path) + "'>" +
    "<td class='num'>" + seq + "</td>" +
    "<td><code>" + hid + "</code></td>" +
    "<td class='val'>" + goldTxt + "</td>" +
    "<td class='val pending'>正在拉…</td>" +
    "<td class='val pending'>正在拉…</td>" +
    "<td><button type='button' class='err-link' data-hand-seq='" + seq + "'>整手</button></td>" +
    "</tr>";
}}
function bindErrorSeqButtons(path) {{
  const box = $("drawer-body");
  box.querySelectorAll("[data-hand-seq]").forEach(btn => {{
    btn.addEventListener("click", () => openCompare(Number(btn.dataset.handSeq), false));
  }});
}}
async function loadErrorSeq(path, seq) {{
  const tr = document.getElementById("err-row-" + seq);
  if (!tr) return;
  const stillThis = () => {{
    const row = document.getElementById("err-row-" + seq);
    if (!row) return false;
    const leaf = decodeURIComponent(row.dataset.errPath || path || "");
    return drawerPath === path || leaf === path;
  }};
  if (!stillThis()) return;
  const M = window.E2EMatch;
  const goldPack = window.E2E_GOLD;
  if (!M || !goldPack) {{
    tr.querySelectorAll("td.pending").forEach(td => {{ td.textContent = "缺少比对脚本"; }});
    return;
  }}
  const gold = goldPack.trees && goldPack.trees[seq - 1];
  const h = handOf(seq);
  const c = caseOf(seq);
  let goldVal = goldValNow(path, seq), visVal, ruleVal, cause;
  if (!gold) {{
    cause = {{ id: "miss", lab: "缺源数据" }};
  }} else {{
    try {{
      const body = await fetchBody(seq);
      if (!stillThis()) return;
      const stages = M.stageTrees(gold, body);
      const pack = M.packHistories
        ? M.packHistories(goldPack.histories && goldPack.histories[seq - 1], gold, body)
        : null;
      goldVal = valAt(gold, path, pack && pack.gold);
      visVal = stages.vis ? valAt(stages.vis, path, pack && pack.vis) : undefined;
      ruleVal = stages.rule ? valAt(stages.rule, path, pack && pack.rule) : undefined;
      cause = M.causeOf(goldVal, visVal, ruleVal, !!stages.vis, !!stages.rule);
    }} catch (e) {{
      if (!stillThis()) return;
      cause = {{ id: "miss", lab: "拉 fusion 失败" }};
    }}
  }}
  if (!stillThis()) return;
  const hid = escTxt((h.hand_id || c.hand_id || ""));
  const cls = cause && cause.id === "ok" ? "is-ok" : "is-diff";
  tr.className = cls;
  tr.innerHTML =
    "<td class='num'>" + seq + "</td>" +
    "<td><code>" + hid + "</code></td>" +
    "<td class='val'>" + M.displayVal(goldVal, "gold") + "</td>" +
    "<td class='val'>" + M.displayVal(visVal, "vis") + "</td>" +
    "<td class='val'>" + M.displayVal(ruleVal, "rule") + "</td>" +
    "<td>" + (cause && cause.id && cause.id !== "ok"
      ? "<span class='pill " + cause.id + "'>" + cause.lab + "</span> "
      : "") +
    "<button type='button' class='err-link' data-hand-seq='" + seq + "'>整手</button></td>";
  tr.querySelectorAll("[data-hand-seq]").forEach(btn => {{
    btn.addEventListener("click", () => openCompare(Number(btn.dataset.handSeq), false));
  }});
}}
function paintCompare() {{
  if ($("drawer-filter").hidden) return;
  paintReject(drawerSeq);
  const only = $("drawer-diff").checked;
  const histSkip = ["action", "bet", "blinds", "cards", "board", "chips", "init_chips", "pot", "showdown", "seq"];
  const roster = (window.E2EMatch && E2EMatch.rosterHtml && drawerHist)
    ? E2EMatch.rosterHtml(drawerHist) : "";
  const hist = (window.E2EMatch && E2EMatch.historyHtml && drawerHist)
    ? E2EMatch.historyHtml(drawerHist, only) : "";
  const play = hist && typeof hist === "object" ? (hist.play || "") : (hist || "");
  const cards = hist && typeof hist === "object" ? (hist.cards || "") : "";
  const body = play
    ? play +
      compareTableHtml(drawerRows, only, histSkip.concat(["count", "seat", "name", "position", "dealer", "other"]), true) +
      cards +
      compareTableHtml(drawerRows, only, histSkip.concat(["status"]), true)
    : compareTableHtml(drawerRows, only, [], true);
  const table = body
    ? "<table class='compare'><thead><tr>" +
      "<th>谁</th><th>源数据</th><th>视觉</th><th>规则</th><th class='cause'>归因</th>" +
      "</tr></thead>" + body + "</table>"
    : "<p class='sub'>没有可对照的字段。</p>";
  $("drawer-body").innerHTML = table + rawJsonHtml();
  const rosterBox = $("drawer-roster");
  if (rosterBox) rosterBox.innerHTML = roster;
  if (window.E2EMatch && E2EMatch.syncCompareLayout) {{
    E2EMatch.syncCompareLayout(rosterBox);
    E2EMatch.syncCompareLayout($("drawer-body"));
  }}
  if (rosterBox) rosterBox.scrollTop = rosterBox.scrollLeft = 0;
  const mask = $("drawer-mask");
  if (mask) mask.scrollTop = mask.scrollLeft = 0;
  const drawerEl = document.querySelector(".drawer");
  if (drawerEl) drawerEl.scrollTop = drawerEl.scrollLeft = 0;
  bindRawJsonCopy($("drawer-body"));
  bindCompareFolds($("drawer-body"));
}}
function bindCompareFolds(box) {{
  if (!box) return;
  box.querySelectorAll("tbody.cmp-fold tr.sec").forEach(tr => {{
    tr.addEventListener("click", () => {{
      tr.parentElement.classList.toggle("is-closed");
    }});
  }});
}}
function prettyJson(obj) {{
  if (obj == null) return "";
  try {{ return JSON.stringify(obj, null, 2); }} catch (e) {{ return String(obj); }}
}}
function goldSourceUrl() {{
  const p = String(SOURCE_PATH || "").replace(/\\\\/g, "/");
  const m = p.match(/uploads\\/[^/]+$/);
  if (m) return "../../" + m[0];
  if (/\\.(jsonl|json)$/i.test(p)) return "../../uploads/" + p.split("/").pop();
  return "";
}}
function unwrapGoldObj(obj) {{
  if (!obj || typeof obj !== "object") return null;
  if (obj.auto_json && typeof obj.auto_json === "object") return obj.auto_json;
  return obj;
}}
function parseGoldFile(text) {{
  const byId = {{}};
  const list = [];
  const trimmed = String(text || "").trim();
  if (!trimmed) return {{ byId, list }};
  const push = raw => {{
    const obj = unwrapGoldObj(raw);
    if (!obj) return;
    list.push(obj);
    if (obj.hand_id != null && obj.hand_id !== "") byId[String(obj.hand_id)] = obj;
  }};
  if (trimmed.charAt(0) === "[") {{
    try {{ JSON.parse(trimmed).forEach(push); }} catch (e) {{}}
    return {{ byId, list }};
  }}
  trimmed.split("\\n").forEach(line => {{
    line = line.trim();
    if (!line) return;
    try {{ push(JSON.parse(line)); }} catch (e) {{}}
  }});
  return {{ byId, list }};
}}
async function ensureGoldRaws() {{
  if (goldRawPack) return goldRawPack;
  if (goldRawWait) return goldRawWait;
  goldRawWait = (async () => {{
    const pack = window.E2E_GOLD;
    if (pack && Array.isArray(pack.raws) && pack.raws.length) {{
      goldRawPack = parseGoldFile(JSON.stringify(pack.raws));
      if (!goldRawPack.list.length) {{
        const list = pack.raws.map(unwrapGoldObj).filter(Boolean);
        const byId = {{}};
        list.forEach(obj => {{
          if (obj.hand_id != null && obj.hand_id !== "") byId[String(obj.hand_id)] = obj;
        }});
        goldRawPack = {{ byId, list }};
      }}
      return goldRawPack;
    }}
    const url = goldSourceUrl();
    if (!url) {{
      goldRawPack = {{ byId: {{}}, list: [] }};
      return goldRawPack;
    }}
    try {{
      const res = await fetch(url);
      if (!res.ok) throw new Error(res.status);
      goldRawPack = parseGoldFile(await res.text());
    }} catch (e) {{
      goldRawPack = {{ byId: {{}}, list: [] }};
    }}
    return goldRawPack;
  }})();
  try {{
    return await goldRawWait;
  }} finally {{
    goldRawWait = null;
  }}
}}
async function goldRawOf(seq) {{
  const pack = await ensureGoldRaws();
  const hid = String((handOf(seq).hand_id || caseOf(seq).hand_id || ""));
  if (hid && pack.byId[hid]) return pack.byId[hid];
  return pack.list[seq - 1] || null;
}}
function rawBlock(kind, title, obj, missing) {{
  const has = obj != null;
  const text = has ? prettyJson(obj) : (missing || "没有这份 JSON。");
  const copy = has
    ? "<button type='button' class='btn-ghost' data-raw-copy='" + kind + "'>复制</button>"
    : "";
  return "<details class='json-fold'>" +
    "<summary><span class='raw-lab'>" + title + "</span>" + copy + "</summary>" +
    "<pre class='json-view' data-raw-pre='" + kind + "'>" + escTxt(text) + "</pre></details>";
}}
function rawJsonHtml() {{
  return "<div class='raw-json'><div class='raw-json-title'>原始 JSON</div>" +
    rawBlock("gold", "源数据 JSON", drawerRaw.gold, "没有源数据原文。") +
    rawBlock("vis", "视觉 JSON", drawerRaw.vis, "这一手没有视觉结果。") +
    rawBlock("rule", "规则 JSON", drawerRaw.rule, "这一手没有规则返回。") +
    "</div>";
}}
function copyRawJson(kind, btn) {{
  const obj = drawerRaw[kind];
  const text = obj == null ? "" : prettyJson(obj);
  if (!text) {{
    alert("还没有可复制的内容。");
    return;
  }}
  const label = btn ? btn.textContent : "复制";
  const done = () => {{
    if (!btn) return;
    btn.textContent = "已复制";
    setTimeout(() => {{ btn.textContent = label; }}, 1200);
  }};
  if (navigator.clipboard && navigator.clipboard.writeText) {{
    navigator.clipboard.writeText(text).then(done, () => alert("复制失败"));
  }} else {{
    alert("当前浏览器不能复制，请手动全选 JSON。");
  }}
}}
function bindRawJsonCopy(root) {{
  if (!root) return;
  root.querySelectorAll("[data-raw-copy]").forEach(btn => {{
    btn.addEventListener("click", e => {{
      e.preventDefault();
      e.stopPropagation();
      copyRawJson(btn.dataset.rawCopy, btn);
    }});
  }});
}}
function paintReject(seq) {{
  const el = $("drawer-reject");
  if (!el) return;
  const d = (handOf(seq) || {{}}).downstream;
  if (!d || (!d.reject && !d.parse_fail)) {{
    el.hidden = true;
    el.innerHTML = "";
    return;
  }}
  const video = d.video_ok ? "视频解析成功" : "视频解析失败";
  const data = d.data_ok ? "数据处理成功" : "数据处理失败";
  const affect = d.affect === "rule" ? "只影响规则"
    : d.affect === "vis" ? "只影响视觉"
    : "视觉 / 规则都未产出";
  const title = d.parse_fail ? (d.short || "视频解析失败") : (d.short || "下游拒绝");
  const reason = String(d.reason || "");
  const long = reason.length > 36 || /[|；;]/.test(reason);
  el.hidden = false;
  el.innerHTML = "<div class='reject-title'><b>" + escTxt(title) + "</b><span>" +
    video + " · " + data + " · " + affect + "</span></div>" +
    (reason
      ? (long
        ? "<details class='reject-more'><summary>完整原因</summary><p class='reject-reason'>" +
          escTxt(reason) + "</p></details>"
        : "<p class='reject-reason'>" + escTxt(reason) + "</p>")
      : "");
}}
async function openCompare(seq, fromList) {{
  drawerSeq = seq;
  $("drawer-back").hidden = !!fromList;
  $("drawer-filter").hidden = false;
  $("drawer-title").textContent = "第 " + seq + " 手差异";
  const h = handOf(seq);
  const c = caseOf(seq);
  $("drawer-sub").textContent =
    (h.hand_id || c.hand_id || "") +
    (h.fusionHandId ? " · fusion " + h.fusionHandId : "");
  $("drawer-status").textContent = "正在拉视觉 / 规则…";
  paintReject(seq);
  setDrawerHelp(false);
  hideClip();
  drawerRaw = {{ gold: null, vis: null, rule: null }};
  clearDrawerMain();
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
  if (!LOOKED_UP) {{
    $("drawer-status").textContent = "还没有匹配率。请先点「重新查询」。";
    return;
  }}
  let body = null;
  if (h.fusionHandId && h.sessionId) {{
    try {{
      body = await fetchBody(seq);
    }} catch (e) {{
      $("drawer-status").textContent = "拉 fusion 失败：" + ((e && e.message) || e);
      return;
    }}
  }}
  const stages = E2EMatch.stageTrees(gold, body);
  drawerHist = E2EMatch.packHistories
    ? E2EMatch.packHistories(goldPack.histories && goldPack.histories[seq - 1], gold, body)
    : null;
  drawerRows = E2EMatch.compareStages(
    gold, stages.vis, stages.rule,
    drawerHist && drawerHist.gold, drawerHist && drawerHist.vis, drawerHist && drawerHist.rule
  );
  const miss = [];
  if (!stages.vis) miss.push("视觉");
  if (!stages.rule) miss.push("规则");
  $("drawer-status").textContent = miss.length
    ? "缺 " + miss.join("、") + "。下面仍按源数据列出布局和字段。"
    : "";
  setDrawerHelp(true);
  drawerRaw = {{
    gold: await goldRawOf(seq),
    vis: body && body.rawJson != null ? body.rawJson : null,
    rule: body && body.ruleResult != null ? body.ruleResult : null,
  }};
  if ($("drawer-title").textContent !== "第 " + seq + " 手差异") return;
  paintCompare();
  const clip = await clipUrlOf(h);
  if ($("drawer-title").textContent !== "第 " + seq + " 手差异") return;
  if (clip) {{
    h.videoUrl = clip;
    showClip(clip, h.fusionHandId);
  }}
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
(function bindClipUi() {{
  const box = $("drawer-clip");
  const actions = $("drawer-clip-actions");
  const pip = $("drawer-clip-pip");
  const link = $("drawer-clip-link");
  const vid = $("drawer-clip-video");
  if (box) box.addEventListener("toggle", () => {{
    if (box.open) ensureClipSrc();
    else {{
      const v = $("drawer-clip-video");
      if (v && document.pictureInPictureElement !== v) v.pause();
    }}
    syncPipBtn();
  }});
  if (actions) actions.addEventListener("click", e => e.stopPropagation());
  if (link) link.addEventListener("click", e => e.stopPropagation());
  if (pip) pip.addEventListener("click", togglePip);
  if (vid) {{
    vid.addEventListener("enterpictureinpicture", syncPipBtn);
    vid.addEventListener("leavepictureinpicture", syncPipBtn);
  }}
}})();
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
    ALIGN = result.align || null;
    bodyCache = {{}};
    stageEpoch += 1;
    Object.keys(stageCache).forEach(k => {{ delete stageCache[k]; }});
    Object.assign(PAIR_RATES, result.pair_rates);
    if (result.seq_rates) Object.assign(SEQ_RATES, result.seq_rates);
    Object.keys(result.field_stats || {{}}).forEach(k => {{ FIELD_STATS[k] = result.field_stats[k]; }});
    LOOKED_UP = true;
    saveLocalRates({{
      pair_rates: result.pair_rates,
      dim_rates: result.dim_rates,
      seq_rates: result.seq_rates,
      field_stats: result.field_stats,
      session_id: sid,
      n_vis: result.n_vis,
      n_rule: result.n_rule,
      n_gold: result.n_gold,
      n_fusion: result.n_fusion,
      align: ALIGN,
      hands: result.hands,
      api: SAVED_API,
      at: new Date().toISOString()
    }});
    paintBoard();
    renderFields();
    renderOrigin();
    renderCoverage();
    if (typeof renderHandGrid === "function") renderHandGrid();
    $("detail-caption").textContent = "已更新匹配率。点差异看整手；点出错手数看该字段。";
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
    <div>
      <h1>上传记录</h1>
      <p class="sub">视觉与规则引擎按上传文件查看。单手全要素完全符合率：这一手里牌、位置、动作、金额、底池全部对上才算一手，分母是查到结果的手数。准确率是字段加权。底池按每次变化计对错，源数据没逐步底池时用已记录的前注、盲注和行动金额累加。</p>
    </div>
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
        <span class="filter-split"></span>
        <button type="button" class="btn" id="u-btn">上传文件</button>
        <button type="button" class="btn-ghost" id="u-gto-btn">上传黄金集</button>
      </div>
    </form>
    <p id="u-status" class="lookup-status"></p>
  </div>
  <div class="records-panel">
    <div class="table-scroll">
      <table class="records">
        <thead>
          <tr>
            <th class="file" rowspan="2">文件</th>
            <th class="num" rowspan="2">手数</th>
            <th class="g vis-g" colspan="7"><i class="g-dot"></i>视觉 (VLM)</th>
            <th class="g rule-g start" colspan="7"><i class="g-dot"></i>规则引擎</th>
            <th class="time" rowspan="2">上传时间</th>
            <th rowspan="2">详情</th>
          </tr>
          <tr class="sub">
            <th class="vis-g exact-all" title="这一手里牌、位置、动作、金额、底池全部对上才算一手；分母是查到结果的手数">单手全要素<br/>完全符合率</th>
            <th class="vis-g">准确率</th><th class="vis-g">牌</th><th class="vis-g">位置</th>
            <th class="vis-g">动作</th><th class="vis-g">金额</th><th class="vis-g end" title="底池每变化一次计一次">底池</th>
            <th class="rule-g start exact-all" title="这一手里牌、位置、动作、金额、底池全部对上才算一手；分母是查到结果的手数">单手全要素<br/>完全符合率</th>
            <th class="rule-g">准确率</th><th class="rule-g">牌</th><th class="rule-g">位置</th>
            <th class="rule-g">动作</th><th class="rule-g">金额</th><th class="rule-g" title="底池每变化一次计一次">底池</th>
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
  </div>
  <div class="modal-mask" id="upload-mask" role="dialog" aria-modal="true" aria-labelledby="upload-title">
    <div class="modal">
      <h3 id="upload-title">上传文件</h3>
      <p class="modal-sub" id="upload-sub">支持 Excel（读 auto_json 列）、json、jsonl。上传后按 sessionId 向 fusion 查匹配率。</p>
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
const LOCAL_UPLOAD = location.origin;
const DEFAULT_API = "http://192.168.110.81:8080";
let page = 1;
let pickedFile = null;
let uploadKind = "auto";
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
const DIM_KEYS = ["牌", "位置", "动作", "金额", "底池"];
function dimPackFromSaved(saved, side) {{
  if (!saved) return null;
  let pack = saved.dim_rates && saved.dim_rates[side];
  if (!pack) {{
    if (!window.E2EMatch || !E2EMatch.dimRatesFromFieldStats) return null;
    const miss = side === "vis" ? "miss_vis" : "miss_rule";
    const pair = side === "vis" ? "gt_vis" : "gt_rule";
    const fs = (saved.field_stats || {{}})[pair] || {{}};
    pack = E2EMatch.dimRatesFromFieldStats(fs, saved.hands || [], miss);
  }}
  if (pack && pack.all5 == null && pack.n) {{
    pack.all5 = Math.round(1000 * (pack.n_all5 || 0) / pack.n) / 10;
  }}
  return pack;
}}
function pctTone(v) {{
  const n = Number(v);
  if (!Number.isFinite(n)) return "";
  if (n >= 80) return " hi";
  if (n >= 50) return "";
  if (n > 0.05) return " lo";
  return " zero";
}}
function pctCell(v, cls, title) {{
  if (v == null || v === "") return "<td class='pct " + cls + "'><span class='waiting'>等结果</span></td>";
  const t = fmtListRate(v);
  const tip = title ? " title='" + escText(title) + "'" : "";
  return "<td class='pct " + cls + pctTone(v) + "'" + tip + ">" + (t || "—") + "</td>";
}}
function dimCols(pack, grp) {{
  if (!pack || pack.all == null) {{
    const extra = grp === "rule-g" ? " start" : " end";
    return "<td class='pct wait-span " + grp + extra + "' colspan='7'><span class='waiting'>等结果</span></td>";
  }}
  const dims = pack.dims || {{}};
  const nIn = pack.n || 0;
  const nAll5 = pack.n_all5 || 0;
  const all5 = pack.all5 != null ? pack.all5 : (nIn ? Math.round(1000 * nAll5 / nIn) / 10 : null);
  const all5Tip = nIn ? (nAll5 + "/" + nIn + " 手牌、位置、动作、金额、底池全部对上") : "";
  let html = pctCell(all5, grp + (grp === "rule-g" ? " start all exact" : " all exact"), all5Tip);
  html += pctCell(pack.all, grp + " all");
  DIM_KEYS.forEach((k, i) => {{
    const last = i === DIM_KEYS.length - 1;
    html += pctCell(dims[k], grp + (last && grp === "vis-g" ? " end" : ""));
  }});
  return html;
}}
function ratesKey(id) {{ return "e2e-rates-" + id; }}
function applySavedRates() {{
  RECORDS.forEach(r => {{
    if (!r.id) return;
    try {{
      const saved = JSON.parse(localStorage.getItem(ratesKey(r.id)) || "null");
      if (!saved || !Array.isArray(saved.hands) || !saved.hands.length) return;
      r.dim_vis = dimPackFromSaved(saved, "vis");
      r.dim_rule = dimPackFromSaved(saved, "rule");
      r.waiting = false;
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
    "<td class='file'>" + escText(r.file) + "</td>" +
    "<td class='num'>" + (r.n === "" || r.n == null ? "" : r.n) + "</td>" +
    dimCols(r.dim_vis, "vis-g") +
    dimCols(r.dim_rule, "rule-g") +
    "<td class='time'>" + escText(r.time) + "</td>" +
    "<td class='detail'>" + (r.detail
      ? "<a href='" + r.detail + "'>详情</a>"
      : (r.id ? "<a href='batches/" + encodeURIComponent(r.id) + "/detail.html'>详情</a>" : "")) + "</td>" +
    "</tr>"
  ).join("") || "<tr><td colspan='18'>没有匹配的记录</td></tr>";
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
  if ($("u-gto-btn")) $("u-gto-btn").disabled = on;
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
    dim_rates: payload.dim_rates,
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
    dim_rates: result.dim_rates,
    seq_rates: result.seq_rates,
    field_stats: result.field_stats,
    session_id: sid,
    n_vis: result.n_vis,
    n_rule: result.n_rule,
    n_gold: result.n_gold,
    n_fusion: result.n_fusion,
    align: result.align,
    hands: result.hands,
    api: api,
    at: new Date().toISOString()
  }});
  return result;
}}
function openUpload(kind) {{
  uploadKind = kind === "gto" ? "gto" : "auto";
  pickedFile = null;
  $("m-file").value = "";
  $("m-fname").textContent = "未选择文件";
  if (uploadKind === "gto") {{
    $("upload-title").textContent = "上传黄金集";
    $("upload-sub").textContent = "只接受 GTO / HandV2 的 json、jsonl（gameInfo + actionSequence）。会先转成 auto_json 再走现有比对，不影响「上传文件」。";
    $("m-file").accept = ".json,.jsonl,application/json";
  }} else {{
    $("upload-title").textContent = "上传文件";
    $("upload-sub").textContent = "支持 Excel（读 auto_json 列）、json、jsonl。上传后按 sessionId 向 fusion 查匹配率。";
    $("m-file").accept = ".xlsx,.xls,.json,.jsonl,application/json";
  }}
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
  if (uploadKind === "gto") {{
    if (!/\\.(jsonl|json)$/i.test(file.name)) {{
      alert("黄金集请上传 json 或 jsonl");
      return;
    }}
  }} else if (!/\\.(xlsx|xls|jsonl|json)$/i.test(file.name)) {{
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
    alert(uploadKind === "gto" ? "请选择 json 或 jsonl 文件" : "请选择 Excel、json 或 jsonl 文件");
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
    const ep = uploadKind === "gto" ? "/api/upload-gto" : "/api/upload";
    const res = await fetch(LOCAL_UPLOAD + ep, {{ method: "POST", body: fd }});
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
      alert("上传需要质量站服务。请用这台服务的地址打开本页（不要直接打开 html 文件），例如 http://内网IP:8767/");
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
$("u-btn").addEventListener("click", () => openUpload("auto"));
$("u-gto-btn").addEventListener("click", () => openUpload("gto"));
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
  $("m-drop").style.borderColor = "var(--accent)";
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
        main_class="is-index",
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
        <details class="json-fold" id="json-fold">
          <summary>原始 JSON <span class="hint">默认折叠 · 点开看视觉 / 规则原文</span></summary>
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
        <div id="viz-compare"></div>
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
    seq_rates: dict | None = None,
    session_id: str = "",
    trees: list[dict] | None = None,
    histories: list[dict] | None = None,
    note: str = "",
) -> dict:
    batch_dir = site_dir / "batches" / batch_id
    batch_dir.mkdir(parents=True, exist_ok=True)
    scripts_dir = Path(__file__).resolve().parent
    for name in ("e2e-match.js", "e2e-session-lookup.js", "poker-hand-viewer.html"):
        src = scripts_dir / name
        if src.exists():
            shutil.copy(src, site_dir / name)
    (site_dir / "lookup.html").write_text(lookup_html(), encoding="utf-8")
    if trees:
        gold = {
            "id": batch_id,
            "cases": [{"hand_id": c.get("hand_id"), "seq": c.get("seq")} for c in cases],
            "trees": trees,
            "histories": histories or [],
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
            seq_rates=seq_rates,
            session_id=session_id,
            batch_id=batch_id,
            source_path=source_path,
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
