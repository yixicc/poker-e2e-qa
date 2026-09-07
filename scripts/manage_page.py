#!/usr/bin/env python3
"""跑批管理：列表页 + 重跑子页 + 正确值管理子页。"""

from __future__ import annotations

import html
import json
from typing import Any, Optional


def _esc(s: Any) -> str:
    return html.escape("" if s is None else str(s), quote=True)


_NAV_ACTIVE_ALIAS = {"rerun": "runs"}

_NAV_GROUPS = (
    (
        "信号 → Chess",
        (
            ("discover", "/discover", "组合发现"),
            ("trend", "/discover/trend", "每日趋势"),
        ),
    ),
    (
        "正确值 / P0",
        (
            ("gt", "/gt", "正确值管理"),
            ("gt-steps", "/gt-steps", "P0 决策点报文"),
            ("step-compare", "/step-compare", "决策点对比"),
        ),
    ),
    (
        "跑批报告",
        (("runs", "/", "对比报告列表"),),
    ),
)


def _site_nav(active: str = "") -> str:
    """左侧菜单，按模块分组。active: runs | discover | trend | gt | gt-steps | step-compare | settings"""
    current = _NAV_ACTIVE_ALIAS.get(active, active)
    groups: list[str] = []
    for title, items in _NAV_GROUPS:
        links = []
        group_on = False
        for key, href, label in items:
            on = key == current
            group_on = group_on or on
            cls = ' class="is-active"' if on else ""
            links.append(f'<a href="{_esc(href)}"{cls}>{_esc(label)}</a>')
        gcls = " is-on" if group_on else ""
        groups.append(
            f'<div class="nav-group{gcls}">'
            f'<div class="nav-group-label">{_esc(title)}</div>'
            f"{''.join(links)}"
            "</div>"
        )
    gear_cls = " is-active" if current == "settings" else ""
    return (
        '<aside class="site-nav">'
        '<a class="site-brand" href="/">QA 跑批</a>'
        f'<nav class="site-nav-links">{"".join(groups)}</nav>'
        '<div class="site-nav-foot">'
        f'<a class="site-nav-gear{gear_cls}" href="/settings" title="连接与本地配置">'
        '<span class="gear-ico" aria-hidden="true">⚙</span>'
        "<span>配置</span></a>"
        "</div>"
        "</aside>"
    )


def _shell_open(active: str, *, wrap_class: str = "wrap") -> str:
    return (
        f'<div class="app-shell">{_site_nav(active)}'
        f'<main class="app-main"><div class="{_esc(wrap_class)}">'
    )


def _shell_close() -> str:
    return "</div></main></div>"


# 供报告总览 / 证据页等静态 HTML 注入（与管理页同一套侧栏）
_SITE_SHELL_CSS = """
:root { --nav-w: 200px; --bg: #f7f5f1; --line: #e7e0d5; --ink: #1c1917; --muted: #78716c; --accent: #0f766e; --accent-soft: #ccfbf1; }
body { margin: 0; background: var(--bg); }
.app-shell { display: flex; align-items: stretch; min-height: 100vh; }
.site-nav {
  width: var(--nav-w); flex-shrink: 0; background: #fff; border-right: 1px solid var(--line);
  padding: 20px 14px; position: sticky; top: 0; align-self: flex-start;
  height: 100vh; overflow: auto; display: flex; flex-direction: column;
  font-family: "PingFang SC", "Noto Sans SC", ui-sans-serif, system-ui, sans-serif;
  z-index: 40;
}
.site-brand {
  display: block; font-weight: 800; font-size: 15px; color: var(--ink);
  text-decoration: none; letter-spacing: -0.02em;
  padding: 4px 10px 16px; border-bottom: 1px solid #f0eeea; margin-bottom: 12px;
}
.site-brand:hover { color: var(--accent); }
.site-nav-links { display: flex; flex-direction: column; gap: 14px; }
.nav-group { display: flex; flex-direction: column; gap: 2px; }
.nav-group-label {
  font-size: 10px; font-weight: 800; letter-spacing: .04em;
  color: #a8a29e; padding: 2px 10px 4px;
}
.site-nav-links a {
  text-decoration: none; color: var(--muted); font-size: 13px; font-weight: 600;
  padding: 8px 10px; border-radius: 8px;
}
.site-nav-links a:hover { color: var(--ink); background: #f5f5f4; }
.site-nav-links a.is-active { color: var(--accent); background: var(--accent-soft); }
.site-nav-foot { margin-top: auto; padding-top: 16px; border-top: 1px solid #f0eeea; }
.site-nav-gear {
  display: inline-flex; align-items: center; gap: 6px;
  text-decoration: none; color: #a8a29e; font-size: 12px; font-weight: 600;
  padding: 8px 10px; border-radius: 8px;
}
.site-nav-gear:hover { color: var(--muted); background: #fafaf9; }
.site-nav-gear.is-active { color: var(--accent); background: var(--accent-soft); }
.site-nav-gear .gear-ico { font-size: 14px; line-height: 1; opacity: .85; }
.app-main { flex: 1; min-width: 0; }
@media (max-width: 800px) {
  .app-shell { flex-direction: column; }
  .site-nav {
    width: 100%; height: auto; position: static;
    border-right: none; border-bottom: 1px solid var(--line);
    padding: 12px 14px; display: block;
  }
  .site-brand { padding: 0 0 10px; margin-bottom: 8px; }
  .site-nav-links { flex-direction: row; flex-wrap: wrap; gap: 10px 18px; align-items: flex-start; }
  .nav-group { flex-direction: row; flex-wrap: wrap; gap: 4px; }
  .nav-group-label { width: 100%; padding: 0 6px 2px; }
  .site-nav-foot { margin-top: 8px; padding-top: 8px; border-top: none; display: inline-block; }
}
"""


def inject_app_shell(html: str, *, active: str = "runs") -> str:
    """给缺少侧栏的静态页（跑批总览 / 证据页）注入与管理页一致的左侧导航。"""
    import re

    if not html:
        return html
    if "class=\"site-nav\"" in html or "class='site-nav'" in html or "app-shell" in html:
        return html

    shell_open = (
        f'<div class="app-shell">{_site_nav(active)}'
        f'<main class="app-main">'
    )
    shell_close = "</main></div>"

    out = html
    if "/* qa-site-shell */" not in out:
        style = f"<style>/* qa-site-shell */{_SITE_SHELL_CSS}</style>"
        lower = out.lower()
        head_end = lower.find("</head>")
        if head_end >= 0:
            out = out[:head_end] + style + out[head_end:]
        else:
            out = style + out

    m = re.search(r"(<body\b[^>]*>)", out, flags=re.IGNORECASE)
    if not m:
        return out
    body_open_end = m.end()
    out = out[:body_open_end] + shell_open + out[body_open_end:]

    lower = out.lower()
    body_close = lower.rfind("</body>")
    if body_close >= 0:
        out = out[:body_close] + shell_close + out[body_close:]
    else:
        out = out + shell_close
    return out

_CSS = """
:root {
  --bg: #f7f5f1;
  --card: #fff;
  --ink: #1c1917;
  --muted: #78716c;
  --line: #e7e0d5;
  --accent: #0f766e;
  --accent-soft: #ccfbf1;
  --warn: #9f1239;
  --nav-w: 200px;
}
* { box-sizing: border-box; }
body {
  margin: 0; font-family: "PingFang SC", "Noto Sans SC", ui-sans-serif, system-ui, sans-serif;
  background: var(--bg); color: var(--ink); line-height: 1.45;
}
.app-shell {
  display: flex; align-items: stretch; min-height: 100vh;
}
.site-nav {
  width: var(--nav-w); flex-shrink: 0;
  background: #fff; border-right: 1px solid var(--line);
  padding: 20px 14px; position: sticky; top: 0; align-self: flex-start;
  height: 100vh; overflow: auto;
  display: flex; flex-direction: column;
}
.site-brand {
  display: block; font-weight: 800; font-size: 15px; color: var(--ink);
  text-decoration: none; letter-spacing: -0.02em;
  padding: 4px 10px 16px; border-bottom: 1px solid #f0eeea; margin-bottom: 12px;
}
.site-brand:hover { color: var(--accent); }
.site-nav-links {
  display: flex; flex-direction: column; gap: 14px;
}
.nav-group { display: flex; flex-direction: column; gap: 2px; }
.nav-group-label {
  font-size: 10px; font-weight: 800; letter-spacing: .04em;
  color: #a8a29e; padding: 2px 10px 4px;
}
.site-nav-links a {
  text-decoration: none; color: var(--muted); font-size: 13px; font-weight: 600;
  padding: 8px 10px; border-radius: 8px;
}
.site-nav-links a:hover { color: var(--ink); background: #f5f5f4; }
.site-nav-links a.is-active {
  color: var(--accent); background: var(--accent-soft);
}
.site-nav-foot {
  margin-top: auto; padding-top: 16px; border-top: 1px solid #f0eeea;
}
.site-nav-gear {
  display: inline-flex; align-items: center; gap: 6px;
  text-decoration: none; color: #a8a29e; font-size: 12px; font-weight: 600;
  padding: 8px 10px; border-radius: 8px;
}
.site-nav-gear:hover { color: var(--muted); background: #fafaf9; }
.site-nav-gear.is-active { color: var(--accent); background: var(--accent-soft); }
.site-nav-gear .gear-ico { font-size: 14px; line-height: 1; opacity: .85; }
.app-main { flex: 1; min-width: 0; }
.wrap { max-width: 1280px; margin: 0 auto; padding: 22px 20px 64px; }
@media (max-width: 800px) {
  .app-shell { flex-direction: column; }
  .site-nav {
    width: 100%; height: auto; position: static;
    border-right: none; border-bottom: 1px solid var(--line);
    padding: 12px 14px;
    display: block;
  }
  .site-brand {
    padding: 0 0 10px; margin-bottom: 8px;
  }
  .site-nav-links { flex-direction: row; flex-wrap: wrap; gap: 10px 18px; align-items: flex-start; }
  .nav-group { flex-direction: row; flex-wrap: wrap; gap: 4px; }
  .nav-group-label { width: 100%; padding: 0 6px 2px; }
  .site-nav-foot {
    margin-top: 8px; padding-top: 8px; border-top: none;
    display: inline-block;
  }
}
.topbar {
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: 16px; margin-bottom: 18px; flex-wrap: nowrap;
}
.topbar-text { min-width: 0; flex: 1; }
.topbar-actions {
  display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
  flex: 0 0 auto; margin-left: auto;
}
h1 { font-size: 26px; margin: 0 0 6px; letter-spacing: -0.02em; }
.lead { color: var(--muted); font-size: 14px; margin: 0; }
.back { font-size: 13px; margin-bottom: 14px; }
.back a { color: var(--accent); text-decoration: none; font-weight: 600; }
.back a:hover { text-decoration: underline; }
.panel {
  background: var(--card); border: 1px solid var(--line); border-radius: 14px;
  padding: 18px 18px 14px; margin-bottom: 18px;
  box-shadow: 0 1px 0 rgba(28,25,23,.03);
}
.panel h2 { font-size: 16px; margin: 0 0 12px; }
.panel .hint { font-size: 12px; color: var(--muted); margin: -6px 0 12px; }
.panel-runs { padding: 16px 18px 8px; }
.panel-runs h2 { margin-bottom: 4px; }
.panel-runs .hint { margin-bottom: 12px; }
.runs-table-wrap { overflow-x: visible; margin: 0; }
table.runs-table {
  width: 100%; border-collapse: collapse; font-size: 12.5px;
  table-layout: fixed;
}
table.runs-table th,
table.runs-table td {
  text-align: left; padding: 10px 8px; border-bottom: 1px solid #f0eeea;
  vertical-align: middle;
}
table.runs-table th {
  font-size: 11px; color: var(--muted); font-weight: 700;
  letter-spacing: .03em; white-space: nowrap;
  border-bottom: 1px solid var(--line); background: #fafaf9;
}
table.runs-table col.c-run { width: 12%; }
table.runs-table col.c-tag { width: 9%; }
table.runs-table col.c-note { width: 12%; }
table.runs-table col.c-pct { width: 5.5%; }
table.runs-table col.c-gt { width: 13%; }
table.runs-table col.c-hands { width: 6%; }
table.runs-table col.c-time { width: 11%; }
table.runs-table col.c-win { width: 18%; }
table.runs-table col.c-op { width: 7%; }
table.runs-table tbody tr:hover td { background: #fffcf8; }
table.runs-table tbody tr:last-child td { border-bottom: none; }
table.runs-table .run-id {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12.5px; font-weight: 700; color: var(--ink);
  overflow-wrap: anywhere; word-break: break-word; white-space: normal;
}
table.runs-table .note-cell {
  color: #44403c; overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap;
}
table.runs-table .pct {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-weight: 700; white-space: nowrap;
}
table.runs-table .meta-cell {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11px; color: #57534e;
  overflow-wrap: anywhere; word-break: break-word; white-space: normal;
  line-height: 1.35;
}
table.runs-table .win-cell {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11px; color: #57534e; white-space: normal; line-height: 1.35;
}
table.runs-table .win-cell .win-line { display: block; }
table.runs-table .op-cell { white-space: nowrap; text-align: right; }
table.runs-table .op-cell .btn { padding: 5px 10px; font-size: 12px; }
table.gt-table { width: 100%; border-collapse: collapse; font-size: 13px; }
table.gt-table th,
table.gt-table td {
  text-align: left; padding: 11px 10px; border-bottom: 1px solid #f0eeea;
  vertical-align: middle;
}
table.gt-table th {
  font-size: 11px; color: var(--muted); font-weight: 700;
  letter-spacing: .03em; white-space: nowrap;
  border-bottom: 1px solid var(--line); background: #fafaf9;
}
table.gt-table tbody tr:hover td { background: #fffcf8; }
table.gt-table tbody tr:last-child td { border-bottom: none; }
table.gt-table .gt-id {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 13px; font-weight: 700; color: var(--ink); white-space: nowrap;
}
table.gt-table .num-cell {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px; white-space: nowrap;
}
table.gt-table .meta-cell {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11px; color: #57534e; white-space: nowrap;
}
table.gt-table .op-cell { white-space: nowrap; text-align: right; }
table.gt-table .op-cell .btn { padding: 5px 12px; font-size: 12px; }
table.gt-table .op-cell .row-actions { justify-content: flex-end; }
.panel-head {
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px; flex-wrap: wrap; margin-bottom: 4px;
}
.panel-head h2 { margin: 0; }
.panel-head .panel-actions { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.import-body {
  margin: 8px 0 14px; padding: 14px 0 4px; border-top: 1px solid #f0eeea;
  border-bottom: 1px solid #f0eeea;
}
.import-body[hidden] { display: none !important; }
.btn.active-toggle {
  background: var(--accent); border-color: var(--accent); color: #fff;
}
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { text-align: left; padding: 10px 8px; border-bottom: 1px solid #f0eeea; vertical-align: top; }
th { font-size: 11px; color: var(--muted); font-weight: 700; letter-spacing: .02em; }
tr:last-child td { border-bottom: none; }
.tags { display: inline-flex; flex-wrap: wrap; gap: 4px; }
.tags span {
  display: inline-block; font-size: 11px; padding: 2px 8px;
  border-radius: 999px; background: var(--accent-soft); color: #115e59; font-weight: 600;
}
.muted { color: var(--muted); font-size: 12px; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }
.btn {
  appearance: none; border: 1px solid var(--line); background: #fff; color: var(--ink);
  border-radius: 8px; padding: 7px 12px; font-size: 13px; cursor: pointer; font-weight: 600;
  text-decoration: none; display: inline-block;
}
.btn:hover { border-color: #d6d3d1; background: #fafaf9; }
.btn.primary { background: var(--accent); border-color: var(--accent); color: #fff; }
.btn.primary:hover { filter: brightness(0.96); }
a.btn.primary { color: #fff; }
.row-actions { display: flex; flex-wrap: wrap; gap: 6px; }
.form-grid {
  display: grid; grid-template-columns: 1fr 1fr; gap: 10px 14px; margin-bottom: 12px;
}
@media (max-width: 720px) { .form-grid { grid-template-columns: 1fr; } }
label { display: block; font-size: 12px; color: var(--muted); margin-bottom: 4px; font-weight: 600; }
input[type=text], textarea, select {
  width: 100%; border: 1px solid var(--line); border-radius: 8px; padding: 8px 10px;
  font-size: 13px; background: #fff; color: var(--ink);
}
textarea { min-height: 64px; resize: vertical; }
.toolbar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 4px; }
.status { font-size: 12px; color: var(--muted); min-height: 18px; margin-top: 8px; }
.status.err { color: var(--warn); }
.status.ok { color: #166534; }
.gen-progress {
  margin-top: 14px; border: 1px solid var(--line); border-radius: 12px;
  padding: 14px 16px; background: #fffcf8;
}
.gen-progress.is-running { border-color: #99f6e4; background: #f0fdfa; }
.gen-progress.is-ok { border-color: #bbf7d0; background: #f0fdf4; }
.gen-progress.is-err { border-color: #fecdd3; background: #fff1f2; }
.gen-progress[hidden] { display: none !important; }
.gen-progress-head {
  display: flex; align-items: flex-start; gap: 12px;
}
.gen-spinner {
  width: 22px; height: 22px; border-radius: 50%; flex: 0 0 auto; margin-top: 2px;
  border: 2.5px solid #ccfbf1; border-top-color: var(--accent);
  animation: gen-spin .7s linear infinite;
}
.gen-progress.is-ok .gen-spinner,
.gen-progress.is-err .gen-spinner { display: none; }
@keyframes gen-spin { to { transform: rotate(360deg); } }
.gen-progress-title { font-size: 14px; font-weight: 700; color: var(--ink); }
.gen-progress-sub { font-size: 12px; color: var(--muted); margin-top: 3px; line-height: 1.45; }
.gen-elapsed {
  margin-left: auto; font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 13px; font-weight: 700; color: #0f766e; white-space: nowrap;
}
.gen-progress.is-err .gen-elapsed { color: #9f1239; }
.gen-progress.is-ok .gen-elapsed { color: #166534; }
.gen-stages {
  list-style: none; margin: 14px 0 0; padding: 0; display: grid; gap: 8px;
}
.gen-stages li {
  display: flex; align-items: center; gap: 8px;
  font-size: 12px; color: #a8a29e; font-weight: 500;
}
.gen-stages li .dot {
  width: 8px; height: 8px; border-radius: 50%; background: #e7e5e4; flex: 0 0 auto;
}
.gen-stages li.done { color: #166534; }
.gen-stages li.done .dot { background: #22c55e; }
.gen-stages li.active { color: var(--ink); font-weight: 650; }
.gen-stages li.active .dot {
  background: var(--accent); box-shadow: 0 0 0 3px rgba(13,148,136,.18);
}
.gen-stages li.skip { color: #d6d3d1; text-decoration: line-through; }
.gen-progress-result { margin-top: 12px; font-size: 13px; line-height: 1.5; }
.gen-progress-result a { color: var(--accent); font-weight: 600; }
.gen-progress-actions { margin-top: 10px; display: flex; flex-wrap: wrap; gap: 8px; }
#gen-panel.is-busy .form-grid,
#gen-panel.is-busy .toolbar { opacity: .55; pointer-events: none; }
#gen-panel.is-busy #btn-rerun { opacity: 1; }
details.trace { margin-top: 6px; }
details.trace summary { cursor: pointer; color: var(--accent); font-size: 12px; font-weight: 600; }
.metrics { font-size: 12px; color: var(--muted); }
.badge-cur {
  display: inline-block; font-size: 10px; padding: 1px 6px; border-radius: 6px;
  background: #fef3c7; color: #92400e; font-weight: 700; margin-left: 6px;
}
.empty { color: var(--muted); font-size: 13px; padding: 12px 0; }
.sub-link { font-size: 13px; color: var(--muted); }
.sub-link a { color: var(--accent); }
.gt-layout {
  display: grid; grid-template-columns: minmax(200px, 260px) minmax(0, 1fr);
  gap: 14px; align-items: stretch;
}
@media (max-width: 900px) { .gt-layout { grid-template-columns: 1fr; } }
.hand-list-wrap {
  max-height: none; min-height: 0; overflow: visible;
}
.hand-row {
  display: grid; grid-template-columns: 88px 1fr auto; gap: 8px; align-items: start;
  padding: 8px 10px; border-bottom: 1px solid #f0eeea; cursor: pointer;
  border-radius: 8px;
}
.hand-row:hover { background: #fafaf9; }
.hand-row.active { background: var(--accent-soft); }
.hand-row .hid { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; font-weight: 700; }
.hand-row .hk {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 11px; color: #57534e;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; word-break: normal;
}
.hand-flags { font-size: 11px; color: var(--muted); white-space: nowrap; }
.editor-tabs { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; align-items: center; }
.editor-tabs .btn.active { background: var(--accent); border-color: var(--accent); color: #fff; }
.editor-area {
  width: 100%; min-height: calc(100vh - 200px); height: calc(100vh - 200px);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px; line-height: 1.4; border: 1px solid var(--line); border-radius: 8px;
  padding: 10px 12px; resize: vertical; background: #fff;
}
.editor-area.is-full {
  /* height 由 JS 按 scrollHeight 写入，避免 !important 盖掉导致裁切 */
  min-height: calc(100vh - 200px);
  overflow: hidden;
  resize: none;
}
.gt-detail-wrap { max-width: 1400px; }
.pill-ok { color: #166534; font-weight: 600; }
.pill-miss { color: #a8a29e; }
.prereq-grid {
  display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px;
}
@media (max-width: 800px) { .prereq-grid { grid-template-columns: 1fr; } }
.prereq-card {
  border: 1px solid var(--line); border-radius: 12px; padding: 14px 16px; background: #fffcf8;
}
.prereq-card.ok { border-color: #bbf7d0; background: #f0fdf4; }
.prereq-card.bad { border-color: #fecdd3; background: #fff1f2; }
.prereq-head {
  display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 8px;
}
.prereq-head h3 { margin: 0; font-size: 14px; }
.prereq-badge {
  font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 999px;
}
.prereq-badge.ok { background: #dcfce7; color: #166534; }
.prereq-badge.bad { background: #ffe4e6; color: #9f1239; }
.prereq-card .lines { font-size: 12px; color: #57534e; line-height: 1.55; }
.prereq-card .lines .mono { font-size: 11px; }
.prereq-card .actions { margin-top: 10px; display: flex; flex-wrap: wrap; gap: 6px; }
.gen-locked { opacity: .55; pointer-events: none; }
"""


_JS_COMMON = """
function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;');
}
function tagsHtml(tags) {
  if (!tags || !tags.length) return '';
  return '<div class="tags">' + tags.map(t => '<span>' + esc(t) + '</span>').join('') + '</div>';
}
function setStatus(el, text, kind) {
  el.textContent = text || '';
  el.className = 'status' + (kind ? ' ' + kind : '');
}
async function postJson(url, body) {
  const res = await fetch(url, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body || {})
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data.ok === false) {
    throw new Error(data.error || ('HTTP ' + res.status));
  }
  return data;
}
function todayPrefix() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth()+1).padStart(2,'0');
  const day = String(d.getDate()).padStart(2,'0');
  return '' + y + m + day;
}
"""


def render_manage_page(
    *,
    runs: Optional[list[dict]] = None,
    gt_versions: Optional[list[dict]] = None,
    current_gt: Optional[str] = None,
) -> str:
    """列表页：只展示已跑报告。"""
    del gt_versions, current_gt  # reserved for API parity
    runs = runs or []
    runs_json = json.dumps(runs, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>QA 跑批管理</title>
<style>{_CSS}</style>
</head>
<body>
{_shell_open("runs")}
  <div class="topbar">
    <div class="topbar-text">
      <h1>对比报告列表</h1>
      <p class="lead">已生成报告列表。点「查看」进入该次总览。</p>
    </div>
    <div class="topbar-actions">
      <a class="btn primary" href="/rerun">生成报告</a>
    </div>
  </div>

  <section class="panel panel-runs" id="panel-runs">
    <p class="hint" style="margin-top:0">每条为一次完整留存。</p>
    <div id="runs-table" class="runs-table-wrap"></div>
  </section>
{_shell_close()}
<script>
{_JS_COMMON}
const INITIAL_RUNS = {runs_json};

function fmtTime(s) {{
  if (!s) return '';
  return String(s).replace('T', ' ').slice(0, 19);
}}

function pctCell(v) {{
  if (v == null || v === '') return '<span class="muted">—</span>';
  return '<span class="pct">' + esc(v) + '%</span>';
}}

function renderRuns(runs) {{
  const box = document.getElementById('runs-table');
  if (!runs.length) {{
    box.innerHTML = '<div class="empty">还没有对比报告。<a href="/rerun">生成报告</a> 创建第一次。</div>';
    return;
  }}
  const rows = runs.map(r => {{
    const id = r.id || '';
    const view = '/runs/' + encodeURIComponent(id) + '/index.html';
    const m = r.metrics || {{}};
    const tq = r.trace_query || {{}};
    const winTitle = (tq.startTime || tq.endTime)
      ? ((tq.startTime || '—') + ' ~ ' + (tq.endTime || '—'))
      : '';
    const winHtml = (tq.startTime || tq.endTime)
      ? ('<span class="win-line">' + esc(tq.startTime || '—') + '</span>'
        + '<span class="win-line">~ ' + esc(tq.endTime || '—') + '</span>')
      : '<span class="muted">—</span>';
    const note = r.note || '';
    return '<tr>'
      + '<td><div class="run-id">' + esc(id) + '</div></td>'
      + '<td>' + (tagsHtml(r.tags) || '<span class="muted">—</span>') + '</td>'
      + '<td class="note-cell" title="' + esc(note) + '">' + (note ? esc(note) : '<span class="muted">—</span>') + '</td>'
      + '<td>' + pctCell(m.old_accuracy_pct) + '</td>'
      + '<td>' + pctCell(m.new_accuracy_pct) + '</td>'
      + '<td class="meta-cell">' + (r.gt_version_id ? esc(r.gt_version_id) : '<span class="muted">—</span>') + '</td>'
      + '<td class="meta-cell">' + (r.batch_hand_n != null
        ? (esc(r.batch_hand_n) + ' 手')
        : (r.hand_n != null ? esc(r.hand_n) + ' 手' : '<span class="muted">—</span>')) + '</td>'
      + '<td class="meta-cell">' + (r.created_at ? esc(fmtTime(r.created_at)) : '<span class="muted">—</span>') + '</td>'
      + '<td class="win-cell" title="' + esc(winTitle) + '">' + winHtml + '</td>'
      + '<td class="op-cell"><a class="btn primary" href="' + view + '">查看</a></td>'
      + '</tr>';
  }}).join('');
  box.innerHTML = '<table class="runs-table">'
    + '<colgroup>'
    + '<col class="c-run"><col class="c-tag"><col class="c-note">'
    + '<col class="c-pct"><col class="c-pct"><col class="c-gt">'
    + '<col class="c-hands"><col class="c-time"><col class="c-win"><col class="c-op">'
    + '</colgroup>'
    + '<thead><tr>'
    + '<th>Run</th><th>标签</th><th>备注</th><th>0703</th><th>0729</th>'
    + '<th>正确值</th><th>手数</th><th>冻结时间</th><th>Trace 窗口</th><th></th>'
    + '</tr></thead><tbody>' + rows + '</tbody></table>';
}}

renderRuns(INITIAL_RUNS);
</script>
</body>
</html>
"""


def render_rerun_page(
    *,
    gt_versions: Optional[list[dict]] = None,
    current_gt: Optional[str] = None,
    trace_cfg: Optional[dict] = None,
    csv_path: str = "data/new.csv",
    csv_exists: bool = False,
) -> str:
    from trace_query_config import TRACE_FORM_CSS, render_trace_query_form

    gt_versions = gt_versions or []
    trace_cfg = dict(trace_cfg) if isinstance(trace_cfg, dict) else {}
    gt_json = json.dumps(gt_versions, ensure_ascii=False)
    current_gt_js = json.dumps(current_gt or "", ensure_ascii=False)
    csv_exists_js = "true" if csv_exists else "false"
    csv_path_js = json.dumps(csv_path, ensure_ascii=False)

    gt_ok = bool(current_gt) or bool(gt_versions)
    t_env = str(trace_cfg.get("traceEnv") or "uat").strip() or "uat"
    t_label = str(trace_cfg.get("envLabel") or "").strip()
    if not t_label:
        try:
            from trace_envs import get_trace_env

            t_label = str(get_trace_env(t_env).get("env_label") or t_env)
        except Exception:
            t_label = t_env
    t_oid = str(trace_cfg.get("openId") or "").strip()
    t_start = str(trace_cfg.get("startTime") or "").strip()
    t_end = str(trace_cfg.get("endTime") or "").strip()
    try:
        from trace_envs import normalize_trace_env

        normalize_trace_env(t_env)
        env_ok = True
    except Exception:
        env_ok = False
    trace_ok = bool(env_ok and t_oid and t_start and t_end)
    compare_ok = gt_ok and csv_exists
    can_gen = compare_ok and trace_ok

    def _badge(ok: bool) -> str:
        return (
            '<span class="prereq-badge ok">已就绪</span>'
            if ok
            else '<span class="prereq-badge bad">待补齐</span>'
        )

    gt_line = (
        f'当前正确值 <span class="mono">{_esc(current_gt)}</span>'
        if current_gt
        else "尚未导入正确值版本"
    )
    csv_line = (
        f'系统结果 <span class="mono">{_esc(csv_path)}</span>'
        + (" · 文件存在" if csv_exists else " · 文件不存在")
    )
    trace_lines = [
        f'环境 <span class="mono">{_esc(t_label)}</span>（data-platform API）',
        f'openId <span class="mono">{_esc(t_oid or "—")}</span>',
        f'窗口 <span class="mono">{_esc((t_start or "—") + " ~ " + (t_end or "—"))}</span>',
    ]

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>生成报告</title>
<style>{_CSS}
{TRACE_FORM_CSS}</style>
</head>
<body>
{_shell_open("rerun")}
  <div class="topbar">
    <div class="topbar-text">
      <h1>生成报告</h1>
      <p class="lead">对比数据就绪后，为本报告填写专属 Trace 条件再生成（已取消全局 Trace 配置）。</p>
    </div>
  </div>

  <div class="prereq-grid">
    <div class="prereq-card {"ok" if compare_ok else "bad"}" id="prereq-compare">
      <div class="prereq-head">
        <h3>1. 对比数据</h3>
        {_badge(compare_ok)}
      </div>
      <div class="lines">
        <div>{gt_line}</div>
        <div>{csv_line}</div>
        <div class="muted" style="margin-top:4px">需要：正确值版本 + 系统结果 CSV</div>
      </div>
      <div class="actions">
        <a class="btn" href="/gt">正确值管理</a>
      </div>
    </div>
    <div class="prereq-card" id="prereq-trace">
      <div class="prereq-head">
        <h3>2. 本报告 Trace 条件</h3>
        <span class="prereq-badge bad" id="trace-badge">待补齐</span>
      </div>
      <div class="lines">
        <div class="muted">下方表单仅用于本次生成，会冻结进本报告；不再使用全局配置</div>
      </div>
    </div>
  </div>

  <section class="panel" style="padding-top:4px">
    {render_trace_query_form(trace_cfg, standalone=False, run_id=None)}
  </section>

  <section class="panel" id="gen-panel">
    <h2>生成参数</h2>
    <p class="hint" id="gen-hint">{"两项已就绪，可以生成。" if can_gen else "前置条件未齐，请先补齐上方两项后再生成。"}</p>
    <div class="form-grid">
      <div>
        <label>Run ID（建议 YYYYMMDD-标签）</label>
        <input id="rerun-id" type="text" placeholder="20260807-rerun"/>
      </div>
      <div>
        <label>正确值版本</label>
        <select id="rerun-gt"></select>
      </div>
      <div>
        <label>标签（逗号分隔）</label>
        <input id="rerun-tags" type="text" placeholder="基线,验证"/>
      </div>
      <div>
        <label>系统结果 CSV</label>
        <input id="rerun-csv" type="text" value="{_esc(csv_path)}"/>
      </div>
      <div style="grid-column: 1 / -1">
        <label>本批手牌（可选，留空=全部）</label>
        <input id="rerun-hands" type="text" placeholder="HAND_001, HAND_006, HAND_014 或 1,6,14"/>
        <div class="muted" style="margin-top:4px">只生成这些手的总览与证据页，指标也只按本批计算</div>
      </div>
      <div style="grid-column: 1 / -1">
        <label>备注</label>
        <textarea id="rerun-note" placeholder="可选：本轮说明"></textarea>
      </div>
    </div>
    <div class="toolbar" id="gen-toolbar">
      <button class="btn primary" id="btn-rerun" type="button" {"disabled" if not can_gen else ""}>开始生成</button>
      <label style="display:inline-flex;align-items:center;gap:6px;margin:0;font-weight:500">
        <input id="rerun-overwrite" type="checkbox"/> 同名则覆盖
      </label>
      <label style="display:inline-flex;align-items:center;gap:6px;margin:0;font-weight:500">
        <input id="rerun-trace" type="checkbox"/> 同时拉 Trace（较慢）
      </label>
    </div>
    <div class="gen-progress" id="gen-progress" hidden>
      <div class="gen-progress-head">
        <div class="gen-spinner" aria-hidden="true"></div>
        <div style="min-width:0;flex:1">
          <div class="gen-progress-title" id="gen-progress-title">正在生成报告</div>
          <div class="gen-progress-sub" id="gen-progress-sub"></div>
        </div>
        <div class="gen-elapsed" id="gen-elapsed">00:00</div>
      </div>
      <ol class="gen-stages" id="gen-stages"></ol>
      <div class="gen-progress-result" id="gen-progress-result" hidden></div>
    </div>
  </section>
{_shell_close()}
<script>
{_JS_COMMON}
const INITIAL_GT = {gt_json};
const INITIAL_CURRENT_GT = {current_gt_js};
const CSV_EXISTS = {csv_exists_js};
let canGenerate = false;

function readTraceCfg() {{
  const oid = (document.getElementById('tq-openid') || {{}}).value || '';
  const start = (document.getElementById('tq-start') || {{}}).value || '';
  const end = (document.getElementById('tq-end') || {{}}).value || '';
  const env = (document.getElementById('tq-trace-env') || {{}}).value || 'uat';
  if (!(String(oid).trim() && String(start).trim() && String(end).trim() && String(env).trim())) return null;
  let hands = {{}};
  try {{ hands = JSON.parse((document.getElementById('tq-hands').value || '').trim() || '{{}}'); }}
  catch (e) {{ return null; }}
  const pad = parseInt((document.getElementById('tq-pad') || {{}}).value || '15', 10) || 15;
  return {{
    _comment: '本报告专属 Trace 条件',
    traceEnv: String(env).trim(),
    api: '',
    envLabel: ((document.getElementById('tq-env') || {{}}).value || '').trim(),
    openId: String(oid).trim(),
    openIdMode: ((document.getElementById('tq-mode') || {{}}).value || 'config_first'),
    startTime: String(start).trim(),
    endTime: String(end).trim(),
    padMinutes: pad,
    origShotsDir: ((document.getElementById('tq-orig-shots') || {{}}).value || '').trim(),
    shotsDir: ((document.getElementById('tq-shots') || {{}}).value || '').trim(),
    hands: hands
  }};
}}


function fillGtSelect(versions, currentId) {{
  const sel = document.getElementById('rerun-gt');
  if (!versions.length) {{
    sel.innerHTML = '<option value="">（请先导入正确值）</option>';
    return;
  }}
  sel.innerHTML = versions.map(v => {{
    const id = v.id || '';
    const cur = id === currentId ? '（当前）' : '';
    return '<option value="' + esc(id) + '">' + esc(id + cur) + '</option>';
  }}).join('');
  if (currentId) sel.value = currentId;
}}

let genTimer = null;
let genStageTimer = null;
let genStartedAt = 0;

function formatElapsed(ms) {{
  const s = Math.max(0, Math.floor(ms / 1000));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return String(m).padStart(2, '0') + ':' + String(r).padStart(2, '0');
}}

function buildStages(skipTrace) {{
  return [
    {{ id: 'validate', label: '校验参数与前置条件' }},
    {{ id: 'compare', label: '对比正确值与系统结果' }},
    {{ id: 'trace', label: skipTrace ? '跳过 Trace 拉取' : '拉取 Trace（ClickHouse）', skip: !!skipTrace }},
    {{ id: 'write', label: '写入报告与 Run 快照' }},
  ];
}}

function renderStages(stages, activeIdx) {{
  const ol = document.getElementById('gen-stages');
  ol.innerHTML = stages.map((st, i) => {{
    let cls = '';
    if (st.skip) cls = 'skip';
    else if (i < activeIdx) cls = 'done';
    else if (i === activeIdx) cls = 'active';
    return '<li class="' + cls + '"><span class="dot"></span><span>' + esc(st.label) + '</span></li>';
  }}).join('');
}}

function setBusy(busy) {{
  const panel = document.getElementById('gen-panel');
  const btn = document.getElementById('btn-rerun');
  if (busy) {{
    panel.classList.add('is-busy');
    btn.disabled = true;
    btn.textContent = '生成中…';
  }} else {{
    panel.classList.remove('is-busy');
    btn.textContent = '开始生成';
    refreshGate();
  }}
}}

function stopGenTimers() {{
  if (genTimer) {{ clearInterval(genTimer); genTimer = null; }}
  if (genStageTimer) {{ clearInterval(genStageTimer); genStageTimer = null; }}
}}

function showProgressRunning(skipTrace) {{
  const box = document.getElementById('gen-progress');
  const result = document.getElementById('gen-progress-result');
  const stages = buildStages(skipTrace);
  let active = 0;
  box.hidden = false;
  box.className = 'gen-progress is-running';
  result.hidden = true;
  result.innerHTML = '';
  document.getElementById('gen-progress-title').textContent = '正在生成报告';
  document.getElementById('gen-progress-sub').textContent = skipTrace
    ? '已跳过 Trace；对比与写报告进行中，请稍候。'
    : '含 Trace 拉取，可能较久；请保持本页打开。';
  document.getElementById('gen-elapsed').textContent = '00:00';
  renderStages(stages, active);
  genStartedAt = Date.now();
  stopGenTimers();
  genTimer = setInterval(() => {{
    document.getElementById('gen-elapsed').textContent = formatElapsed(Date.now() - genStartedAt);
  }}, 250);
  // 无后端真实进度时，按耗时启发式推进阶段提示
  const ticks = skipTrace ? [0, 2, 999, 8] : [0, 3, 12, 45];
  genStageTimer = setInterval(() => {{
    const sec = (Date.now() - genStartedAt) / 1000;
    let next = active;
    for (let i = 0; i < ticks.length; i++) {{
      if (stages[i] && stages[i].skip) continue;
      if (sec >= ticks[i]) next = i;
    }}
    if (next !== active) {{
      active = next;
      renderStages(stages, active);
    }}
  }}, 500);
  return stages;
}}

function finishProgressOk(meta, stages) {{
  stopGenTimers();
  const box = document.getElementById('gen-progress');
  const result = document.getElementById('gen-progress-result');
  const elapsed = formatElapsed(Date.now() - genStartedAt);
  document.getElementById('gen-elapsed').textContent = elapsed;
  renderStages(stages, stages.length);
  box.className = 'gen-progress is-ok';
  document.getElementById('gen-progress-title').textContent = '生成完成';
  const sec = meta && meta.rerun_seconds != null ? meta.rerun_seconds + 's' : elapsed;
  document.getElementById('gen-progress-sub').textContent =
    'Run ' + (meta && meta.id ? meta.id : '') + ' · 耗时 ' + sec;
  const rid = encodeURIComponent((meta && meta.id) || '');
  const batch = (meta && meta.batch_hands && meta.batch_hands.length)
    ? (' · 本批 ' + meta.batch_hands.length + ' 手：' + meta.batch_hands.join(', '))
    : '';
  result.hidden = false;
  result.innerHTML =
    '<div>报告已写入，可打开总览或回到列表继续查看。' + esc(batch) + '</div>'
    + '<div class="gen-progress-actions">'
    + '<a class="btn primary" href="/runs/' + rid + '/index.html">打开本轮总览</a>'
    + '<a class="btn" href="/">对比报告列表</a>'
    + '</div>';
}}

function finishProgressErr(message, stages, activeHint) {{
  stopGenTimers();
  const box = document.getElementById('gen-progress');
  const result = document.getElementById('gen-progress-result');
  document.getElementById('gen-elapsed').textContent = formatElapsed(Date.now() - genStartedAt);
  if (stages) renderStages(stages, typeof activeHint === 'number' ? activeHint : 1);
  box.className = 'gen-progress is-err';
  document.getElementById('gen-progress-title').textContent = '生成失败';
  document.getElementById('gen-progress-sub').textContent = '可修改参数后重试；错误摘要见下方。';
  result.hidden = false;
  result.innerHTML = '<div style="color:#9f1239;white-space:pre-wrap">' + esc(message || '未知错误') + '</div>';
}}

function refreshGate() {{
  const gt = document.getElementById('rerun-gt').value.trim();
  const csv = document.getElementById('rerun-csv').value.trim();
  const compareOk = !!gt && (csv === {csv_path_js} ? CSV_EXISTS : true);
  const tcfg = readTraceCfg();
  const traceOk = !!tcfg;
  const badge = document.getElementById('trace-badge');
  const card = document.getElementById('prereq-trace');
  if (badge) {{
    badge.textContent = traceOk ? '已就绪' : '待补齐';
    badge.className = 'prereq-badge ' + (traceOk ? 'ok' : 'bad');
  }}
  if (card) card.className = 'prereq-card ' + (traceOk ? 'ok' : 'bad');
  canGenerate = compareOk && traceOk;
  const btn = document.getElementById('btn-rerun');
  const busy = document.getElementById('gen-panel').classList.contains('is-busy');
  btn.disabled = busy || !canGenerate;
  document.getElementById('gen-hint').textContent = canGenerate
    ? '两项已就绪，可以生成。'
    : '前置条件未齐：需要正确值版本，且本报告 Trace 条件（环境 / openId / 时间窗）已填写。';
}}

async function rerunReport() {{
  const runId = document.getElementById('rerun-id').value.trim();
  const gtVersion = document.getElementById('rerun-gt').value.trim();
  const tags = document.getElementById('rerun-tags').value.split(/[,，]/).map(s => s.trim()).filter(Boolean);
  const note = document.getElementById('rerun-note').value.trim();
  const newCsv = document.getElementById('rerun-csv').value.trim() || 'data/new.csv';
  const overwrite = document.getElementById('rerun-overwrite').checked;
  const skipTrace = !document.getElementById('rerun-trace').checked;
  const traceQuery = readTraceCfg();
  if (!traceQuery) {{
    const stages = showProgressRunning(true);
    finishProgressErr('请先填写本报告 Trace 条件（环境、openId、起止时间）', stages, 0);
    return;
  }}
  if (!runId) {{
    const stages = showProgressRunning(skipTrace);
    finishProgressErr('请填写 Run ID', stages, 0);
    return;
  }}
  if (!gtVersion) {{
    const stages = showProgressRunning(skipTrace);
    finishProgressErr('请先导入正确值版本', stages, 0);
    return;
  }}
  const stages = showProgressRunning(skipTrace);
  setBusy(true);
  try {{
    const handsRaw = (document.getElementById('rerun-hands') || {{}}).value || '';
    const data = await postJson('/api/rerun-report', {{
      run_id: runId, tags, note, gt_version: gtVersion, new_csv: newCsv,
      overwrite, skip_trace: skipTrace, trace_query: traceQuery,
      hand_uids: String(handsRaw).trim(),
    }});
    finishProgressOk(data.meta || {{}}, stages);
  }} catch (e) {{
    finishProgressErr(String(e.message || e), stages, skipTrace ? 1 : 2);
  }} finally {{
    setBusy(false);
  }}
}}

fillGtSelect(INITIAL_GT, INITIAL_CURRENT_GT);
document.getElementById('rerun-id').value = todayPrefix() + '-rerun';
document.getElementById('rerun-gt').addEventListener('change', refreshGate);
document.getElementById('rerun-csv').addEventListener('input', refreshGate);
['tq-openid','tq-start','tq-end','tq-trace-env','tq-hands','tq-pad','tq-mode','tq-orig-shots','tq-shots'].forEach(id => {{
  const el = document.getElementById(id);
  if (el) {{ el.addEventListener('input', refreshGate); el.addEventListener('change', refreshGate); }}
}});
document.getElementById('btn-rerun').addEventListener('click', rerunReport);
refreshGate();
</script>
</body>
</html>
"""


def render_gt_page(
    *,
    gt_versions: Optional[list[dict]] = None,
    current_gt: Optional[str] = None,
) -> str:
    gt_versions = gt_versions or []
    gt_json = json.dumps(gt_versions, ensure_ascii=False)
    current_gt_js = json.dumps(current_gt or "", ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>正确值管理</title>
<style>{_CSS}</style>
</head>
<body>
{_shell_open("gt")}
  <div class="topbar">
    <div class="topbar-text">
      <h1>正确值管理</h1>
      <p class="lead">真值版本列表；生成报告时选用「当前」版本，不必每次读 Excel。</p>
    </div>
  </div>

  <section class="panel panel-runs">
    <div class="panel-head">
      <h2>版本列表</h2>
      <div class="panel-actions">
        <button class="btn" type="button" id="btn-toggle-import">从 Excel 导入</button>
      </div>
    </div>
    <p class="hint">「当前」会作为生成报告的默认正确值；历史 Run 会记下当时引用的版本号。</p>
    <div class="import-body" id="import-body" hidden>
      <p class="hint">导入后自动设为当前，并可进入该版本管理手牌。</p>
      <div class="form-grid">
        <div>
          <label>版本 ID</label>
          <input id="gt-id" type="text" placeholder="20260807-from-excel"/>
        </div>
        <div>
          <label>标签</label>
          <input id="gt-tags" type="text" placeholder="提bug真值"/>
        </div>
        <div>
          <label>Excel 路径</label>
          <input id="gt-excel" type="text" value="data/old.xlsx"/>
        </div>
        <div>
          <label>备注</label>
          <input id="gt-note" type="text" placeholder="可选"/>
        </div>
      </div>
      <div class="toolbar">
        <button class="btn primary" id="btn-import-gt" type="button">导入并设为当前</button>
      </div>
      <div class="status" id="gt-status"></div>
    </div>
    <div id="gt-table" class="runs-table-wrap"></div>
  </section>
{_shell_close()}
<script>
{_JS_COMMON}
const INITIAL_GT = {gt_json};
const INITIAL_CURRENT_GT = {current_gt_js};

function fmtTime(s) {{
  if (!s) return '';
  return String(s).replace('T', ' ').slice(0, 19);
}}

function renderGt(versions, currentId) {{
  const box = document.getElementById('gt-table');
  if (!versions.length) {{
    box.innerHTML = '<div class="empty">还没有正确值版本。点右上角「从 Excel 导入」。</div>';
    showImport(true);
    return;
  }}
  const rows = versions.map(v => {{
    const id = v.id || '';
    const isCur = id === currentId;
    const curBadge = isCur ? '<span class="badge-cur">当前</span>' : '<span class="muted">—</span>';
    const setBtn = isCur
      ? ''
      : '<button class="btn" type="button" data-set-gt="' + esc(id) + '">设为当前</button>';
    const manageBtn = '<a class="btn primary" href="/gt/' + encodeURIComponent(id) + '">管理</a>';
    const tags = tagsHtml(v.tags) || '<span class="muted">—</span>';
    const note = v.note ? (' title="' + esc(v.note) + '"') : '';
    const srcTitle = v.source ? (' title="来源: ' + esc(v.source) + '"') : '';
    return '<tr>'
      + '<td><div class="gt-id"' + srcTitle + '>' + esc(id) + '</div></td>'
      + '<td' + note + '>' + tags + (v.note ? ' <span class="muted">' + esc(v.note) + '</span>' : '') + '</td>'
      + '<td class="num-cell">' + esc(v.hand_count || 0) + '</td>'
      + '<td class="num-cell">' + esc(v.with_gt_n != null ? v.with_gt_n : '—') + '</td>'
      + '<td class="meta-cell">' + (v.created_at || v.updated_at
          ? esc(fmtTime(v.created_at || v.updated_at)) : '<span class="muted">—</span>') + '</td>'
      + '<td>' + curBadge + '</td>'
      + '<td class="op-cell"><div class="row-actions">' + manageBtn + setBtn + '</div></td>'
      + '</tr>';
  }}).join('');
  box.innerHTML = '<table class="gt-table"><thead><tr>'
    + '<th>版本</th><th>标签</th><th>手数</th><th>有真值</th><th>创建时间</th><th>当前</th><th></th>'
    + '</tr></thead><tbody>' + rows + '</tbody></table>';
  box.querySelectorAll('[data-set-gt]').forEach(btn => {{
    btn.addEventListener('click', function() {{
      setCurrentGt(btn.getAttribute('data-set-gt'));
    }});
  }});
}}

async function refreshGt() {{
  const res = await fetch('/api/manage-state');
  const data = await res.json();
  if (!data.ok) throw new Error(data.error || '加载失败');
  renderGt(data.gt_versions || [], data.current_gt || '');
}}

async function importGt() {{
  const st = document.getElementById('gt-status');
  const versionId = document.getElementById('gt-id').value.trim();
  const tags = document.getElementById('gt-tags').value.split(/[,，]/).map(s => s.trim()).filter(Boolean);
  const note = document.getElementById('gt-note').value.trim();
  const excel = document.getElementById('gt-excel').value.trim() || 'data/old.xlsx';
  if (!versionId) {{ setStatus(st, '请填写版本 ID', 'err'); return; }}
  setStatus(st, '导入中（读 Excel）…');
  try {{
    const data = await postJson('/api/import-gt', {{
      version_id: versionId, tags, note, excel_path: excel, set_current: true
    }});
    st.innerHTML = '已导入 <strong>' + esc(data.meta.id) + '</strong>（' + esc(data.meta.hand_count)
      + ' 手）。 <a href="/gt/' + encodeURIComponent(data.meta.id) + '">打开管理页</a>';
    st.className = 'status ok';
    await refreshGt();
  }} catch (e) {{
    setStatus(st, String(e.message || e), 'err');
  }}
}}

async function setCurrentGt(versionId) {{
  const st = document.getElementById('gt-status');
  setStatus(st, '切换中…');
  try {{
    await postJson('/api/set-current-gt', {{ version_id: versionId }});
    setStatus(st, '当前正确值：' + versionId, 'ok');
    await refreshGt();
  }} catch (e) {{
    setStatus(st, String(e.message || e), 'err');
  }}
}}

document.getElementById('gt-id').value = todayPrefix() + '-from-excel';
document.getElementById('btn-import-gt').addEventListener('click', importGt);

function showImport(on) {{
  const body = document.getElementById('import-body');
  const btn = document.getElementById('btn-toggle-import');
  if (!body || !btn) return;
  body.hidden = !on;
  btn.classList.toggle('active-toggle', !!on);
  btn.textContent = on ? '收起导入' : '从 Excel 导入';
}}
document.getElementById('btn-toggle-import').addEventListener('click', () => {{
  const body = document.getElementById('import-body');
  showImport(body.hidden);
}});

renderGt(INITIAL_GT, INITIAL_CURRENT_GT);
</script>
</body>
</html>
"""


def render_gt_detail_page(
    *,
    version_id: str,
    meta: Optional[dict] = None,
    hands_brief: Optional[list[dict]] = None,
    current_gt: Optional[str] = None,
) -> str:
    meta = meta or {}
    hands_brief = hands_brief or []
    vid = version_id
    meta_json = json.dumps(meta, ensure_ascii=False)
    hands_json = json.dumps(hands_brief, ensure_ascii=False)
    current_js = json.dumps(current_gt or "", ensure_ascii=False)
    tags_val = ", ".join(meta.get("tags") or []) if isinstance(meta.get("tags"), list) else ""
    note_val = str(meta.get("note") or "")
    is_cur = vid == (current_gt or "")
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>正确值 · {_esc(vid)}</title>
<style>{_CSS}</style>
</head>
<body>
{_shell_open("gt", wrap_class="wrap gt-detail-wrap")}
  <div class="back">
    <a href="/gt">← 返回版本列表</a>
  </div>
  <div class="topbar">
    <div class="topbar-text">
      <h1>正确值 · <span class="mono">{_esc(vid)}</span>
        {"<span class='badge-cur'>当前</span>" if is_cur else ""}
      </h1>
      <p class="lead">查看 / 编辑版本信息与每手真值 JSON。</p>
    </div>
    <div class="topbar-actions">
      {"" if is_cur else '<button class="btn" type="button" id="btn-set-cur">设为当前</button>'}
    </div>
  </div>

  <section class="panel">
    <h2>版本信息</h2>
    <div class="form-grid">
      <div>
        <label>标签（逗号分隔）</label>
        <input id="meta-tags" type="text" value="{_esc(tags_val)}"/>
      </div>
      <div>
        <label>备注</label>
        <input id="meta-note" type="text" value="{_esc(note_val)}"/>
      </div>
    </div>
    <div class="muted" style="margin-bottom:10px">
      手数 { _esc(meta.get("hand_count")) } · 有真值 { _esc(meta.get("with_gt_n")) }
      · 来源 <span class="mono">{_esc(meta.get("source") or "—")}</span>
    </div>
    <div class="toolbar">
      <button class="btn primary" type="button" id="btn-save-meta">保存版本信息</button>
    </div>
    <div class="status" id="meta-status"></div>
  </section>

  <div class="gt-layout">
    <section class="panel" style="margin:0">
      <h2>手牌列表</h2>
      <p class="hint">点选一手后，在右侧查看 / 编辑。</p>
      <div class="hand-list-wrap" id="hand-list"></div>
    </section>
    <section class="panel" style="margin:0">
      <h2 id="editor-title">手牌编辑</h2>
      <div class="form-grid" style="margin-bottom:8px">
        <div>
          <label>hole_key</label>
          <input id="edit-hole" type="text"/>
        </div>
        <div>
          <label>hand_uid</label>
          <input id="edit-hid" type="text" disabled/>
        </div>
      </div>
      <div class="editor-tabs">
        <button class="btn active" type="button" data-tab="gt">正确值 gt_raw</button>
        <button class="btn" type="button" data-tab="old">0703 old_req_raw</button>
        <button class="btn" type="button" id="btn-toggle-full" style="margin-left:auto">完全展示</button>
      </div>
      <textarea class="editor-area" id="edit-json" spellcheck="false"></textarea>
      <div class="toolbar" style="margin-top:10px">
        <button class="btn primary" type="button" id="btn-save-hand">保存本手</button>
        <button class="btn" type="button" id="btn-reload-hand">重新加载</button>
      </div>
      <div class="status" id="hand-status"></div>
    </section>
  </div>
{_shell_close()}
<script>
{_JS_COMMON}
const VERSION_ID = {json.dumps(vid, ensure_ascii=False)};
const INITIAL_HANDS = {hands_json};
const INITIAL_META = {meta_json};
const CURRENT_GT = {current_js};

let selectedHid = '';
let activeTab = 'gt';
let handCache = {{}};
let editorFull = false;

function applyEditorHeight() {{
  const ta = document.getElementById('edit-json');
  const btn = document.getElementById('btn-toggle-full');
  if (!ta || !btn) return;
  if (editorFull) {{
    ta.classList.add('is-full');
    // 先压到 0 再读 scrollHeight，才能量出全文高度；页面用浏览器滚动条浏览
    ta.style.height = '0px';
    ta.style.height = Math.max(ta.scrollHeight + 4, 320) + 'px';
    btn.textContent = '收起高度';
    btn.classList.add('active');
  }} else {{
    ta.classList.remove('is-full');
    ta.style.height = '';
    btn.textContent = '完全展示';
    btn.classList.remove('active');
  }}
}}

function formatHoleKey(raw) {{
  if (raw == null || raw === '') return '—';
  const text = String(raw).trim();
  try {{
    const parsed = JSON.parse(text.replace(/'/g, '"'));
    if (Array.isArray(parsed)) {{
      const cards = parsed.map(c => String(c || '').trim()).filter(Boolean);
      return cards.length ? cards.join(' ') : '—';
    }}
  }} catch (e) {{}}
  // ["QC","5H"] 或 QC5H / QC 5H → 按两字符牌面拆开平铺
  const m = text.match(/[A-Za-z0-9]{{2}}/g);
  if (m && m.length) return m.join(' ');
  return text;
}}

function renderHandList(hands) {{
  const box = document.getElementById('hand-list');
  if (!hands.length) {{
    box.innerHTML = '<div class="empty">无手牌</div>';
    return;
  }}
  box.innerHTML = hands.map(h => {{
    const hid = h.hand_uid || '';
    const hkRaw = h.hole_key || '';
    const hkShow = formatHoleKey(hkRaw);
    const flags = (h.has_gt ? '<span class="pill-ok">GT</span>' : '<span class="pill-miss">无GT</span>')
      + ' · '
      + (h.has_old_req ? '<span class="pill-ok">0703</span>' : '<span class="pill-miss">无0703</span>');
    return '<div class="hand-row' + (hid === selectedHid ? ' active' : '') + '" data-hid="' + esc(hid) + '">'
      + '<div class="hid">' + esc(hid) + '</div>'
      + '<div class="hk" title="' + esc(hkRaw || hkShow) + '">' + esc(hkShow) + '</div>'
      + '<div class="hand-flags">' + flags + '</div></div>';
  }}).join('');
  box.querySelectorAll('.hand-row').forEach(el => {{
    el.addEventListener('click', () => selectHand(el.getAttribute('data-hid')));
  }});
}}

function showTab(tab) {{
  activeTab = tab;
  document.querySelectorAll('.editor-tabs .btn[data-tab]').forEach(b => {{
    b.classList.toggle('active', b.getAttribute('data-tab') === tab);
  }});
  const hand = handCache[selectedHid];
  if (!hand) return;
  const obj = tab === 'old' ? hand.old_req_raw : hand.gt_raw;
  document.getElementById('edit-json').value = obj == null
    ? ''
    : JSON.stringify(obj, null, 2);
  applyEditorHeight();
}}

async function fetchHand(hid) {{
  if (handCache[hid]) return handCache[hid];
  const res = await fetch('/api/gt-hand?version_id=' + encodeURIComponent(VERSION_ID)
    + '&hand_uid=' + encodeURIComponent(hid));
  const data = await res.json();
  if (!res.ok || data.ok === false) throw new Error(data.error || '加载失败');
  handCache[hid] = data.hand;
  return data.hand;
}}

async function selectHand(hid) {{
  selectedHid = hid;
  renderHandList(INITIAL_HANDS);
  document.getElementById('editor-title').textContent = '编辑 ' + hid;
  setStatus(document.getElementById('hand-status'), '加载中…');
  try {{
    const hand = await fetchHand(hid);
    document.getElementById('edit-hid').value = hid;
    document.getElementById('edit-hole').value = hand.hole_key || '';
    showTab(activeTab);
    setStatus(document.getElementById('hand-status'), '');
  }} catch (e) {{
    setStatus(document.getElementById('hand-status'), String(e.message || e), 'err');
  }}
}}

async function saveMeta() {{
  const st = document.getElementById('meta-status');
  const tags = document.getElementById('meta-tags').value.split(/[,，]/).map(s => s.trim()).filter(Boolean);
  const note = document.getElementById('meta-note').value.trim();
  setStatus(st, '保存中…');
  try {{
    await postJson('/api/update-gt-meta', {{ version_id: VERSION_ID, tags, note }});
    setStatus(st, '版本信息已保存', 'ok');
  }} catch (e) {{
    setStatus(st, String(e.message || e), 'err');
  }}
}}

async function saveHand() {{
  const st = document.getElementById('hand-status');
  if (!selectedHid) {{ setStatus(st, '请先选择手牌', 'err'); return; }}
  const hole = document.getElementById('edit-hole').value.trim();
  const rawText = document.getElementById('edit-json').value.trim();
  let parsed = null;
  if (rawText) {{
    try {{ parsed = JSON.parse(rawText); }}
    catch (e) {{ setStatus(st, 'JSON 无法解析：' + e.message, 'err'); return; }}
    if (parsed !== null && typeof parsed !== 'object') {{
      setStatus(st, '必须是 JSON 对象', 'err'); return;
    }}
  }}
  const body = {{
    version_id: VERSION_ID,
    hand_uid: selectedHid,
    hole_key: hole,
    update_gt: activeTab === 'gt',
    update_old: activeTab === 'old',
  }};
  if (activeTab === 'gt') body.gt_raw = parsed;
  if (activeTab === 'old') body.old_req_raw = parsed;
  setStatus(st, '保存中…');
  try {{
    const data = await postJson('/api/update-gt-hand', body);
    handCache[selectedHid] = data.hand;
    // refresh brief flags
    const brief = INITIAL_HANDS.find(h => h.hand_uid === selectedHid);
    if (brief) {{
      brief.has_gt = !!data.hand.gt_raw;
      brief.has_old_req = !!data.hand.old_req_raw;
      brief.hole_key = data.hand.hole_key || '';
    }}
    renderHandList(INITIAL_HANDS);
    setStatus(st, '已保存 ' + selectedHid, 'ok');
  }} catch (e) {{
    setStatus(st, String(e.message || e), 'err');
  }}
}}

document.querySelectorAll('.editor-tabs .btn[data-tab]').forEach(b => {{
  b.addEventListener('click', () => showTab(b.getAttribute('data-tab')));
}});
document.getElementById('btn-toggle-full').addEventListener('click', () => {{
  editorFull = !editorFull;
  applyEditorHeight();
}});
document.getElementById('btn-save-meta').addEventListener('click', saveMeta);
document.getElementById('btn-save-hand').addEventListener('click', saveHand);
document.getElementById('btn-reload-hand').addEventListener('click', () => {{
  if (!selectedHid) return;
  delete handCache[selectedHid];
  selectHand(selectedHid);
}});
const setCur = document.getElementById('btn-set-cur');
if (setCur) {{
  setCur.addEventListener('click', async () => {{
    try {{
      await postJson('/api/set-current-gt', {{ version_id: VERSION_ID }});
      location.reload();
    }} catch (e) {{ alert(e.message || e); }}
  }});
}}

renderHandList(INITIAL_HANDS);
if (INITIAL_HANDS.length) selectHand(INITIAL_HANDS[0].hand_uid);
</script>
</body>
</html>
"""


def render_discover_page() -> str:
    """组合发现：复用 Trace Viewer 的 traceDiscover 能力（经本地服务代理）。"""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>组合发现</title>
<style>{_CSS}
.ds-page {{ max-width: 1080px; }}
.ds-page .topbar {{ margin-bottom: 20px; }}
.ds-page h1 {{
  font-size: 28px; letter-spacing: -0.03em;
  font-family: "Songti SC", "Noto Serif SC", "PingFang SC", serif;
  font-weight: 700;
}}
.ds-page .lead {{ max-width: 42em; }}

.ds-query {{
  display: flex; flex-wrap: wrap; align-items: flex-end; gap: 12px 14px;
  padding: 14px 16px; margin-bottom: 16px;
  background: #fff; border: 1px solid var(--line); border-radius: 12px;
}}
.ds-query .field {{ display: flex; flex-direction: column; gap: 5px; }}
.ds-query label {{
  font-size: 11px; font-weight: 700; color: var(--muted);
  letter-spacing: .04em; text-transform: none; margin: 0;
}}
.ds-query input[type="datetime-local"] {{
  font: inherit; font-size: 13px; padding: 9px 11px; min-width: 196px;
  border: 1px solid var(--line); border-radius: 8px;
  background: #fafaf9; color: var(--ink);
  transition: border-color .15s ease, background .15s ease, box-shadow .15s ease;
}}
.ds-query input[type="datetime-local"]:hover {{ background: #fff; }}
.ds-query input[type="datetime-local"]:focus {{
  outline: none; border-color: #5eead4; background: #fff;
  box-shadow: 0 0 0 3px rgba(15,118,110,.12);
}}
.ds-presets {{
  display: flex; flex-wrap: wrap; gap: 6px; align-items: center;
  padding-bottom: 1px;
}}
.ds-preset {{
  appearance: none; border: 1px solid var(--line); background: #fff;
  color: #57534e; font: inherit; font-size: 12px; font-weight: 600;
  padding: 7px 11px; border-radius: 8px; cursor: pointer;
  transition: background .12s ease, border-color .12s ease, color .12s ease;
}}
.ds-preset:hover {{ border-color: #99f6e4; color: var(--accent); background: #f0fdfa; }}
.ds-preset.is-on {{
  border-color: #99f6e4; color: var(--accent); background: var(--accent-soft);
}}
.ds-query .btn.primary {{
  padding: 9px 16px; min-width: 96px;
  transition: transform .12s ease, opacity .12s ease;
}}
.ds-query .btn.primary:active:not(:disabled) {{ transform: translateY(1px); }}
.ds-summary {{
  font-size: 13px; color: var(--muted); font-weight: 600;
  margin-left: auto; align-self: center; min-height: 1.2em;
}}
.ds-summary strong {{ color: var(--ink); font-weight: 800; }}
@media (max-width: 720px) {{
  .ds-summary {{ margin-left: 0; width: 100%; }}
  .ds-query input[type="datetime-local"] {{ min-width: 0; width: 100%; }}
}}

.ds-result {{
  background: #fff; border: 1px solid var(--line); border-radius: 12px;
  min-height: 320px; overflow: hidden;
  animation: ds-in .28s ease both;
}}
@keyframes ds-in {{
  from {{ opacity: 0; transform: translateY(6px); }}
  to {{ opacity: 1; transform: none; }}
}}
.ds-result-head {{
  display: flex; align-items: baseline; justify-content: space-between;
  gap: 12px; padding: 12px 16px; border-bottom: 1px solid #f0eeea;
}}
.ds-result-head h2 {{
  margin: 0; font-size: 13px; font-weight: 700; color: var(--ink);
  letter-spacing: .02em;
}}
.ds-result-head .meta {{ font-size: 12px; color: var(--muted); }}
.ds-table-wrap {{ overflow: auto; max-height: calc(100vh - 280px); }}
table.ds-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
table.ds-table th, table.ds-table td {{
  text-align: left; padding: 11px 16px; border-bottom: 1px solid #f3efe8; vertical-align: middle;
}}
table.ds-table th {{
  position: sticky; top: 0; z-index: 1;
  background: #faf8f5; color: var(--muted);
  font-weight: 700; font-size: 11px; letter-spacing: .04em;
}}
table.ds-table td.mono {{
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12.5px;
}}
table.ds-table td.hole {{
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 13px; font-weight: 700; letter-spacing: .02em;
}}
table.ds-table td.dim {{ color: var(--muted); white-space: nowrap; font-variant-numeric: tabular-nums; }}
table.ds-table td.count {{
  text-align: right; font-weight: 800; color: var(--accent);
  font-variant-numeric: tabular-nums;
}}
table.ds-table td.op {{ text-align: right; white-space: nowrap; }}
table.ds-table td.op .btn {{
  padding: 5px 10px; font-size: 12px;
}}
table.ds-table tbody tr {{ transition: background .1s ease; }}
table.ds-table tbody tr:hover {{ background: #f8fffd; }}
table.ds-table tbody tr:last-child td {{ border-bottom: none; }}

.ds-empty {{
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  text-align: center; min-height: 300px; padding: 48px 24px;
  color: var(--muted);
}}
.ds-empty-mark {{
  width: 52px; height: 52px; margin-bottom: 16px;
  border-radius: 14px; border: 1px dashed #d6d3d1;
  background:
    linear-gradient(135deg, rgba(15,118,110,.08), transparent 60%),
    #fafaf9;
  position: relative;
}}
.ds-empty-mark::after {{
  content: ""; position: absolute; inset: 14px;
  border: 1.5px solid #a8a29e; border-radius: 4px;
  opacity: .45;
  clip-path: polygon(0 0, 100% 0, 100% 70%, 70% 100%, 0 100%);
}}
.ds-empty-title {{
  margin: 0 0 6px; font-size: 15px; font-weight: 700; color: #44403c;
}}
.ds-empty-desc {{
  margin: 0; font-size: 13px; max-width: 28em; line-height: 1.55;
}}
.ds-empty.is-error .ds-empty-title {{ color: var(--warn); }}
.ds-empty.is-error .ds-empty-mark {{
  border-color: #fecdd3;
  background: linear-gradient(135deg, rgba(159,18,57,.06), transparent 60%), #fff;
}}
.ds-loading {{
  display: flex; flex-direction: column; gap: 10px; padding: 20px 16px;
}}
.ds-skel {{
  height: 14px; border-radius: 6px; background: #f0eeea;
  background-image: linear-gradient(90deg, #f0eeea 0%, #f7f5f1 45%, #f0eeea 90%);
  background-size: 220% 100%;
  animation: ds-shimmer 1.1s ease-in-out infinite;
}}
.ds-skel.w40 {{ width: 40%; }} .ds-skel.w55 {{ width: 55%; }}
.ds-skel.w70 {{ width: 70%; }} .ds-skel.w85 {{ width: 85%; }}
@keyframes ds-shimmer {{
  0% {{ background-position: 100% 0; }}
  100% {{ background-position: -100% 0; }}
}}
.ds-foot {{
  margin-top: 10px; font-size: 11px; color: #a8a29e;
}}
.ds-foot .mono {{ font-size: 11px; }}
</style>
</head>
<body>
{_shell_open("discover", wrap_class="wrap ds-page")}
  <div class="topbar">
    <div class="topbar-text">
      <h1>组合发现</h1>
      <p class="lead">按时间窗找出 Trace 里的 openId + 底牌组合。点「对比」看单手信号→Chess；<a href="/discover/trend">每日趋势</a>看分类统计与一致率。</p>
    </div>
  </div>

  <div class="ds-query">
    <div class="field">
      <label for="ds-start">开始</label>
      <input id="ds-start" type="datetime-local"/>
    </div>
    <div class="field">
      <label for="ds-end">结束</label>
      <input id="ds-end" type="datetime-local"/>
    </div>
    <div class="ds-presets" role="group" aria-label="快捷时间">
      <button type="button" class="ds-preset is-on" data-preset="today">今天</button>
      <button type="button" class="ds-preset" data-preset="3h">近 3 小时</button>
      <button type="button" class="ds-preset" data-preset="24h">近 24 小时</button>
    </div>
    <button class="btn primary" type="button" id="btn-discover">查询</button>
    <span class="ds-summary" id="ds-summary" aria-live="polite"></span>
  </div>

  <div class="ds-result" id="ds-result-shell">
    <div id="ds-result">
      <div class="ds-empty">
        <div class="ds-empty-mark" aria-hidden="true"></div>
        <p class="ds-empty-title">还没有结果</p>
        <p class="ds-empty-desc">选好时间后点查询，列出该时段全部 openId + holeCards 组合（最多 500 条）。</p>
      </div>
    </div>
  </div>
  <p class="ds-foot">经本地代理 <span class="mono">/api/trace-discover</span> · API 环境见「配置」</p>
{_shell_close()}
<script>
{_JS_COMMON}

function pad2(n) {{ return (n < 10 ? '0' : '') + n; }}
function toLocalInput(d) {{
  return d.getFullYear() + '-' + pad2(d.getMonth()+1) + '-' + pad2(d.getDate())
    + 'T' + pad2(d.getHours()) + ':' + pad2(d.getMinutes());
}}
function localInputToApi(v) {{
  if (!v) return '';
  var s = String(v).trim().replace('T', ' ');
  if (/^\\d{{4}}-\\d{{2}}-\\d{{2}} \\d{{2}}:\\d{{2}}$/.test(s)) s += ':00';
  return s;
}}
function shortTs(v) {{
  var s = String(v == null ? '' : v);
  if (!s) return '—';
  s = s.replace('T', ' ').replace('Z', '');
  return s.length >= 19 ? s.slice(0, 19) : s;
}}
function setPresetActive(name) {{
  document.querySelectorAll('.ds-preset').forEach(function(b) {{
    b.classList.toggle('is-on', b.getAttribute('data-preset') === name);
  }});
}}
function applyPreset(name) {{
  var now = new Date();
  var start, end;
  if (name === '3h') {{
    end = now;
    start = new Date(now.getTime() - 3 * 3600 * 1000);
  }} else if (name === '24h') {{
    end = now;
    start = new Date(now.getTime() - 24 * 3600 * 1000);
  }} else {{
    start = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0);
    end = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 0);
    name = 'today';
  }}
  document.getElementById('ds-start').value = toLocalInput(start);
  document.getElementById('ds-end').value = toLocalInput(end);
  setPresetActive(name);
}}
function emptyHtml(title, desc, isError) {{
  return '<div class="ds-empty' + (isError ? ' is-error' : '') + '">'
    + '<div class="ds-empty-mark" aria-hidden="true"></div>'
    + '<p class="ds-empty-title">' + esc(title) + '</p>'
    + '<p class="ds-empty-desc">' + esc(desc) + '</p>'
    + '</div>';
}}
function loadingHtml() {{
  return '<div class="ds-loading">'
    + '<div class="ds-skel w85"></div><div class="ds-skel w70"></div>'
    + '<div class="ds-skel w55"></div><div class="ds-skel w40"></div>'
    + '<div class="ds-skel w70"></div><div class="ds-skel w55"></div>'
    + '</div>';
}}

function renderRows(rows) {{
  var box = document.getElementById('ds-result');
  var sum = document.getElementById('ds-summary');
  if (!rows || !rows.length) {{
    box.innerHTML = emptyHtml('没有匹配组合', '这段时间里 Trace 没有 openId + 底牌记录，换个时间窗再试。');
    sum.innerHTML = '共 <strong>0</strong> 条';
    return;
  }}
  sum.innerHTML = '共 <strong>' + rows.length + '</strong> 条';
  var h = '<div class="ds-result-head"><h2>查询结果</h2>'
    + '<span class="meta">最多 500 条</span></div>'
    + '<div class="ds-table-wrap"><table class="ds-table"><thead><tr>'
    + '<th>OpenID</th><th>底牌</th><th>首次出现</th><th>最后出现</th>'
    + '<th style="text-align:right">记录数</th><th></th></tr></thead><tbody>';
  rows.forEach(function(r) {{
    var q = new URLSearchParams({{
      openId: r.openId || '',
      holeCards: r.holeCards || '',
      start: r.firstSeen || '',
      end: r.lastSeen || ''
    }});
    h += '<tr>'
      + '<td class="mono">' + esc(r.openId || '—') + '</td>'
      + '<td class="hole">' + esc(r.holeCards || '—') + '</td>'
      + '<td class="dim">' + esc(shortTs(r.firstSeen)) + '</td>'
      + '<td class="dim">' + esc(shortTs(r.lastSeen)) + '</td>'
      + '<td class="count">' + esc(r.spanCount != null ? r.spanCount : 0) + '</td>'
      + '<td class="op"><a class="btn" href="/discover/compare?' + q.toString() + '">对比</a></td>'
      + '</tr>';
  }});
  h += '</tbody></table></div>';
  box.innerHTML = h;
}}

async function runDiscover() {{
  var st = document.getElementById('ds-start').value;
  var en = document.getElementById('ds-end').value;
  var btn = document.getElementById('btn-discover');
  var sum = document.getElementById('ds-summary');
  var box = document.getElementById('ds-result');
  if (!st || !en) {{
    sum.textContent = '请选择时间范围';
    return;
  }}
  btn.disabled = true;
  btn.textContent = '查询中…';
  sum.textContent = '';
  box.innerHTML = loadingHtml();
  try {{
    var data = await postJson('/api/trace-discover', {{
      startTime: localInputToApi(st),
      endTime: localInputToApi(en),
    }});
    renderRows(data.result || data.rows || []);
  }} catch (e) {{
    box.innerHTML = emptyHtml('查询失败', String(e.message || e), true);
    sum.textContent = '查询失败';
  }} finally {{
    btn.disabled = false;
    btn.textContent = '查询';
  }}
}}

applyPreset('today');
document.getElementById('btn-discover').addEventListener('click', runDiscover);
document.querySelectorAll('.ds-preset').forEach(function(b) {{
  b.addEventListener('click', function() {{
    applyPreset(b.getAttribute('data-preset'));
  }});
}});
['ds-start', 'ds-end'].forEach(function(id) {{
  document.getElementById(id).addEventListener('input', function() {{
    setPresetActive('');
  }});
  document.getElementById(id).addEventListener('keydown', function(e) {{
    if (e.key === 'Enter') runDiscover();
  }});
}});
</script>
</body>
</html>
"""


def render_settings_page(*, ch_settings: Optional[dict] = None) -> str:
    """低调运维页：Trace data-platform API。"""
    from trace_envs import DEFAULT_TRACE_ENV, get_trace_env, resolve_api_base
    from trace_query_config import load_trace_api_settings

    cfg = load_trace_api_settings()
    try:
        env = get_trace_env(str(cfg.get("traceEnv") or DEFAULT_TRACE_ENV))
    except KeyError:
        env = get_trace_env(DEFAULT_TRACE_ENV)
    api = resolve_api_base(env["id"], override=str(cfg.get("api") or ""))
    initial = json.dumps(
        {
            "api": api,
            "trace_env": env["id"],
            "env_label": env.get("env_label") or env["id"],
        },
        ensure_ascii=False,
    )
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>配置</title>
<style>{_CSS}
.settings-narrow {{ max-width: 640px; }}
</style>
</head>
<body>
{_shell_open("settings", wrap_class="wrap settings-narrow")}
  <div class="topbar">
    <div class="topbar-text">
      <h1>配置</h1>
      <p class="lead">Trace 走 data-platform API。查询时间窗在各报告内配置，不在这里。</p>
    </div>
  </div>

  <section class="panel">
    <h2>Trace API</h2>
    <p class="hint">默认 UAT：<span class="mono">http://8.145.52.251:7121</span>。</p>
    <div class="form-grid">
      <div style="grid-column:1/-1">
        <label>API Base</label>
        <input id="tr-api" type="text" autocomplete="off" spellcheck="false"
          placeholder="http://8.145.52.251:7121"/>
      </div>
    </div>
    <div class="toolbar">
      <button class="btn primary" id="btn-save-api" type="button">保存</button>
      <button class="btn" id="btn-test-api" type="button">测试连接</button>
      <a class="btn" href="/rerun">生成报告（填 Trace 条件）</a>
    </div>
    <div class="status" id="tr-status"></div>
  </section>

  <p class="sub-link">API 写入 <span class="mono">data/trace_api.json</span>；各报告条件在 <span class="mono">data/runs/&lt;id&gt;/trace_query.json</span>。</p>
{_shell_close()}
<script>
{_JS_COMMON}
const INITIAL = {initial};

function fillForm() {{
  document.getElementById('tr-api').value = INITIAL.api || '';
}}

async function saveApi() {{
  const st = document.getElementById('tr-status');
  const api = document.getElementById('tr-api').value.trim().replace(/\\/$/, '');
  setStatus(st, '保存中…');
  try {{
    const data = await postJson('/api/settings/trace-api', {{ api }});
    if (data.settings) Object.assign(INITIAL, data.settings);
    fillForm();
    setStatus(st, '已保存', 'ok');
  }} catch (e) {{
    setStatus(st, String(e.message || e), 'err');
  }}
}}

async function testApi() {{
  const st = document.getElementById('tr-status');
  const api = document.getElementById('tr-api').value.trim().replace(/\\/$/, '');
  if (!api) {{ setStatus(st, '请填写 API Base', 'err'); return; }}
  setStatus(st, '测试中…');
  try {{
    const data = await postJson('/api/settings/test-trace-api', {{ api }});
    setStatus(st, '连接成功 · ' + (data.api || api) + (data.hint ? (' · ' + data.hint) : ''), 'ok');
  }} catch (e) {{
    setStatus(st, String(e.message || e), 'err');
  }}
}}

fillForm();
document.getElementById('btn-save-api').addEventListener('click', saveApi);
document.getElementById('btn-test-api').addEventListener('click', testApi);
</script>
</body>
</html>
"""
