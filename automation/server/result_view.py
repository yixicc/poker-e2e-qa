"""把某次执行的 result.xlsx 渲染成可在浏览器里看的页面。"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

_SECTIONS = {"结果一览", "失败原因", "按工具", "按优先级", "按分组"}
_RATE_HEADERS = {"占失败", "通过率"}

# 列表只放扫一眼用的列；长文（响应/报文）放展开区，避免互相遮挡
_DETAIL_MAIN = [
    "case_id",
    "step_no",
    "title",
    "group",
    "priority",
    "tool_name",
    "执行结果",
    "执行时间ms",
    "结果分析",
]

# 旧版 result.xlsx 列名 → 新列名
_HEADER_ALIASES = {
    "result": "执行结果",
    "失败说明": "结果分析",
    "模型回答": "响应答复",
    "response_raw": "响应答复",
    "response_summary": "响应答复",
    "elapsed_ms": "执行时间ms",
    "request_body": "请求报文",
    "原始报错": "结果分析",
}

# 原用例侧（来自 cases / requests）
_ORIGIN_FIELDS = [
    ("user_question", "原问题 user_question"),
    ("assert_hints", "原预期 assert_hints"),
    ("expect_tools", "期望工具 expect_tools"),
    ("assert_expr", "断言表达式 assert_expr"),
    ("metric_codes", "指标码 metric_codes"),
    ("notes", "备注 notes"),
    ("role", "角色 role"),
]

# 展开区上方：执行摘要（放在原用例旁）
_META_FIELDS = [
    ("执行结果", "执行结果"),
    ("结果分析", "结果分析"),
    ("执行时间ms", "执行时间ms"),
    ("http_status", "http_status"),
]


def _cells(row: tuple[Any, ...] | None) -> list[Any]:
    if not row:
        return []
    vals: list[Any] = []
    for value in row:
        if value is None:
            vals.append("")
        elif isinstance(value, float):
            vals.append(value)
        else:
            vals.append(str(value).strip())
    while vals and vals[-1] == "":
        vals.pop()
    return vals


def _fmt(value: Any, header: str = "") -> str:
    if value is None or value == "":
        return ""
    # 通过率在 Excel 里常是 0~1 的 float/int
    if header in _RATE_HEADERS or header == "通过率":
        try:
            f = float(value)
            if 0 <= f <= 1:
                return f"{f * 100:.1f}%"
        except (TypeError, ValueError):
            pass
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return f"{value:.1f}"
    if isinstance(value, int):
        return str(value)
    return str(value)


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _try_parse_json(text: str) -> Any | None:
    s = (text or "").strip()
    if not s:
        return None
    if s[0] not in "{[":
        return None
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return None


def _deep_parse_jsonish(obj: Any, *, depth: int = 0) -> Any:
    """把嵌套在字符串里的 JSON 再解析一层，方便阅读 content[].text。"""
    if depth > 6:
        return obj
    if isinstance(obj, dict):
        return {k: _deep_parse_jsonish(v, depth=depth + 1) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deep_parse_jsonish(v, depth=depth + 1) for v in obj]
    if isinstance(obj, str):
        inner = _try_parse_json(obj)
        if inner is not None:
            return _deep_parse_jsonish(inner, depth=depth + 1)
    return obj


def _extract_sse_json_payloads(text: str) -> list[Any]:
    """从 SSE（event/data 行）里抽出 data: 后的 JSON。"""
    payloads: list[Any] = []
    buf: list[str] = []
    for line in text.splitlines():
        if line.startswith("data:"):
            piece = line[5:].lstrip()
            if piece:
                buf.append(piece)
            continue
        if buf and line.strip() == "":
            raw = "".join(buf)
            buf = []
            parsed = _try_parse_json(raw)
            if parsed is not None:
                payloads.append(parsed)
    if buf:
        raw = "".join(buf)
        parsed = _try_parse_json(raw)
        if parsed is not None:
            payloads.append(parsed)
    return payloads


def _pretty_payload(text: str) -> str:
    """响应答复 / 请求报文：尽量格式化成缩进 JSON。"""
    s = (text or "").strip()
    if not s or s == "（空）":
        return s

    # 纯 JSON
    parsed = _try_parse_json(s)
    if parsed is not None:
        return json.dumps(_deep_parse_jsonish(parsed), ensure_ascii=False, indent=2)

    # SSE：event: message / data: {...}
    if "data:" in s and ("event:" in s or "jsonrpc" in s):
        payloads = _extract_sse_json_payloads(s)
        if len(payloads) == 1:
            return json.dumps(_deep_parse_jsonish(payloads[0]), ensure_ascii=False, indent=2)
        if len(payloads) > 1:
            return json.dumps(_deep_parse_jsonish(payloads), ensure_ascii=False, indent=2)
        # 兜底：抽第一段 data:
        for line in s.splitlines():
            if line.startswith("data:"):
                piece = line[5:].lstrip()
                parsed = _try_parse_json(piece)
                if parsed is not None:
                    return json.dumps(_deep_parse_jsonish(parsed), ensure_ascii=False, indent=2)

    # 正文里夹了一段 JSON
    for start_ch, end_ch in (("{", "}"), ("[", "]")):
        start = s.find(start_ch)
        end = s.rfind(end_ch)
        if start >= 0 and end > start:
            parsed = _try_parse_json(s[start : end + 1])
            if parsed is not None:
                return json.dumps(_deep_parse_jsonish(parsed), ensure_ascii=False, indent=2)

    return s


_JSONISH_KEYS = {"响应答复", "请求报文", "request_body", "response_raw", "response_summary", "模型回答"}


def parse_summary(ws) -> tuple[list[tuple[str, str]], str, list[dict[str, Any]]]:
    kpis: list[tuple[str, str]] = []
    callout = ""
    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for row in ws.iter_rows(values_only=True):
        cells = _cells(row)
        if not cells:
            continue
        head = str(cells[0])
        if head in _SECTIONS:
            current = {"title": head, "rows": []}
            sections.append(current)
            if any(c != "" for c in cells[1:]):
                current["rows"].append(cells)
            continue
        if head in {"MCP 执行汇总", "项"} or head.startswith("导出时间"):
            if head == "项" and len(cells) > 1:
                current = {"title": "结果", "rows": [cells]}
                sections.append(current)
            continue
        if current is None:
            current = {"title": "汇总", "rows": []}
            sections.append(current)
        if current["title"] == "结果一览":
            if len(cells) >= 3 and isinstance(cells[2], str) and len(cells[2]) > 12:
                callout = cells[2]
            label = head
            raw = cells[1] if len(cells) > 1 else ""
            kpis.append((label, _fmt(raw, label)))
            continue
        current["rows"].append(cells)
    return kpis, callout, sections


def parse_detail(ws) -> list[dict[str, str]]:
    row_iter = ws.iter_rows(values_only=True)
    header = _cells(next(row_iter, None))
    headers = [str(h) for h in header if str(h)]
    records: list[dict[str, str]] = []
    for row in row_iter:
        cells = list(row) if row else []
        if not any(c is not None and str(c).strip() for c in cells):
            continue
        item: dict[str, str] = {}
        for i, name in enumerate(headers):
            raw = cells[i] if i < len(cells) else ""
            text = _fmt(raw, name)
            canon = _HEADER_ALIASES.get(name, name)
            # 新列优先；旧列只在目标空时补上，避免覆盖
            if canon not in item or not item[canon]:
                item[canon] = text
            if name != canon:
                item[name] = text
        status = item.get("执行结果") or item.get("result") or ""
        if item.get("case_id") or status or item.get("title"):
            records.append(item)
    return records


def _enrich_from_cases_xlsx(records: list[dict[str, str]], cases_xlsx: str) -> None:
    """结果里缺原字段时，尽量从原始自动化表补齐（按 case_id + step_no）。"""
    path = Path(cases_xlsx) if cases_xlsx else None
    if not path or not path.exists():
        return
    try:
        from openpyxl import load_workbook

        from common.excel_loader import load_cases, load_enabled_requests
    except Exception:  # noqa: BLE001
        return

    try:
        cases = load_cases(path)
        reqs = load_enabled_requests(path, include_alt=True)
    except Exception:  # noqa: BLE001
        return

    by_step: dict[tuple[str, str], Any] = {}
    for r in reqs:
        by_step[(r.case_id, str(r.step_no))] = r

    for rec in records:
        cid = rec.get("case_id") or ""
        step = str(rec.get("step_no") or "")
        case = cases.get(cid)
        req = by_step.get((cid, step))
        if case:
            if not rec.get("user_question"):
                rec["user_question"] = case.user_question
            if not rec.get("assert_hints"):
                rec["assert_hints"] = case.assert_hints
            if not rec.get("expect_tools"):
                rec["expect_tools"] = case.expect_tools
            if not rec.get("title"):
                rec["title"] = case.title
            if not rec.get("group"):
                rec["group"] = case.group
        if req:
            if not rec.get("assert_expr"):
                rec["assert_expr"] = req.assert_expr
            if not rec.get("request_body"):
                rec["request_body"] = json.dumps(req.request_body, ensure_ascii=False)
            if not rec.get("metric_codes"):
                rec["metric_codes"] = req.metric_codes
            if not rec.get("user_question"):
                rec["user_question"] = req.user_question
            if not rec.get("assert_hints"):
                rec["assert_hints"] = req.assert_hints


_NUM_HEADERS = {"条数", "总数", "通过", "失败", "跳过", "占失败", "通过率", "平均耗时"}


def _normalize_table_rows(raw_rows: list[list[Any]]) -> tuple[list[str], list[list[Any]]]:
    """按表头列数对齐每一行，避免空单元格被吃掉后错位。"""
    if not raw_rows:
        return [], []
    headers = [str(c) for c in raw_rows[0]]
    # 去掉全空表头尾
    while headers and headers[-1] == "":
        headers.pop()
    n = len(headers)
    if n == 0:
        return [], []
    data: list[list[Any]] = []
    for row in raw_rows[1:]:
        cells = list(row) + [""] * max(0, n - len(row))
        cells = cells[:n]
        # 跳过整行占位 —
        if all(str(c).strip() in {"", "—", "-"} for c in cells):
            continue
        data.append(cells)
    return headers, data


_TEXT_HEADERS = {"类型", "工具", "断言字段", "说明", "代表用例", "分组", "优先级"}


def _table(headers: list[Any], rows: list[list[Any]], *, kind: str = "breakdown") -> str:
    if not headers:
        return ""
    n = len(headers)
    head_bits = []
    for h in headers:
        hs = str(h)
        hcls = ' class="num"' if hs in _NUM_HEADERS else ""
        head_bits.append(f"<th{hcls}>{_esc(hs)}</th>")
    head_html = "".join(head_bits)
    body = []
    for row in rows:
        padded = list(row) + [""] * max(0, n - len(row))
        tds = []
        for i, cell in enumerate(padded[:n]):
            header = str(headers[i])
            text = _fmt(cell, header)
            cls = ""
            if header in {"条数", "失败"} and text not in {"", "0", "0.0%"}:
                cls = ' class="num bad"'
            elif header in {"通过", "通过率"}:
                cls = ' class="num ok"'
            elif header in _NUM_HEADERS:
                cls = ' class="num"'
            elif header in _TEXT_HEADERS or i == 0:
                cls = ' class="text"'
            tds.append(f"<td{cls}>{_esc(text)}</td>")
        body.append("<tr>" + "".join(tds) + "</tr>")
    return (
        f'<div class="table-wrap"><table class="{_esc(kind)}">'
        f"<thead><tr>{head_html}</tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table></div>"
    )


def _summary_html(kpis: list[tuple[str, str]], callout: str, sections: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    if kpis:
        cards = []
        for label, value in kpis:
            tone = ""
            if label == "通过":
                tone = " ok"
            elif label == "失败":
                tone = " bad"
            cards.append(
                f'<div class="kpi{tone}"><span>{_esc(label)}</span><b>{_esc(value)}</b></div>'
            )
        parts.append('<div class="kpis">' + "".join(cards) + "</div>")
    if callout:
        parts.append(f'<p class="callout">{_esc(callout)}</p>')
    for section in sections:
        if section["title"] == "结果一览" or not section["rows"]:
            continue
        headers, data = _normalize_table_rows(section["rows"])
        if not headers:
            continue
        kind = "fail-table" if section["title"] == "失败原因" else "breakdown"
        parts.append(f'<h2>{_esc(section["title"])}</h2>')
        parts.append(_table(headers, data, kind=kind))
    if not parts:
        parts.append('<p class="muted">这份结果没有汇总表。</p>')
    return "".join(parts)


def _field_display(rec: dict[str, str], key: str) -> tuple[str, bool]:
    """返回 (展示文本, 是否为空)。"""
    val = (rec.get(key) or "").strip()
    if not val:
        return "（空）", True
    if key in _JSONISH_KEYS:
        val = _pretty_payload(val)
    return val, False


def _kv_grid(fields: list[tuple[str, str]], rec: dict[str, str], *, compact: bool = False) -> str:
    rows = []
    for key, label in fields:
        val, empty = _field_display(rec, key)
        empty_cls = " empty" if empty else ""
        v_cls = "v compact" if compact else "v"
        rows.append(
            f'<div class="kv{empty_cls}"><div class="k">{_esc(label)}</div>'
            f'<pre class="{v_cls}">{_esc(val)}</pre></div>'
        )
    return f'<div class="kv-grid">{"".join(rows)}</div>'


def _copyable_pane(title: str, text: str, copy_id: str) -> str:
    body = (text or "").strip()
    empty = not body
    shown = "（空）" if empty else _pretty_payload(body)
    empty_cls = " empty" if empty else ""
    return (
        f'<div class="payload{empty_cls}">'
        f'<div class="payload-head">'
        f"<h4>{_esc(title)}</h4>"
        f'<button type="button" class="copy-btn" data-target="{_esc(copy_id)}">复制</button>'
        f"</div>"
        f'<pre class="v payload-body" id="{_esc(copy_id)}">{_esc(shown)}</pre>'
        f"</div>"
    )


def _fold_section(title: str, body: str, *, section_id: str, open_by_default: bool = False) -> str:
    """可收起区块：默认收起，点标题再展开。"""
    opened = " open" if open_by_default else ""
    aria = "true" if open_by_default else "false"
    return (
        f'<section class="fold{opened}" data-fold="{_esc(section_id)}">'
        f'<button type="button" class="fold-head" aria-expanded="{aria}">'
        f'<span class="fold-title">{_esc(title)}</span>'
        f'<span class="fold-caret" aria-hidden="true"></span>'
        f"</button>"
        f'<div class="fold-body">{body}</div>'
        f"</section>"
    )


def _expand_panel(rec: dict[str, str], idx: int) -> str:
    """原用例 → 请求|响应 → 执行摘要；默认全部收起，点标题展开。"""
    origin_body = _kv_grid(_ORIGIN_FIELDS, rec, compact=True)
    origin = _fold_section(
        "原用例（Excel）", origin_body, section_id=f"origin-{idx}", open_by_default=False
    )

    req_raw = (rec.get("请求报文") or rec.get("request_body") or "").strip()
    resp_raw = (
        rec.get("响应答复")
        or rec.get("模型回答")
        or rec.get("response_raw")
        or rec.get("response_summary")
        or ""
    ).strip()
    io_body = (
        '<div class="io-row">'
        f'{_copyable_pane("实际请求", req_raw, f"copy-req-{idx}")}'
        f'{_copyable_pane("实际响应", resp_raw, f"copy-resp-{idx}")}'
        "</div>"
    )
    io = _fold_section(
        "实际请求 / 响应", io_body, section_id=f"io-{idx}", open_by_default=False
    )

    meta_body = _kv_grid(_META_FIELDS, rec, compact=True)
    meta = _fold_section(
        "执行摘要", meta_body, section_id=f"meta-{idx}", open_by_default=False
    )

    return f'<div class="expand">{origin}{io}{meta}</div>'


def _preview(text: str, limit: int = 120) -> str:
    s = (text or "").strip().replace("\r\n", "\n")
    if len(s) <= limit:
        return s
    return s[:limit].rstrip() + "…"


def _detail_html(records: list[dict[str, str]]) -> str:
    if not records:
        return '<p class="muted">这份结果没有执行明细。</p>'

    main_cols = [c for c in _DETAIL_MAIN if any(r.get(c) for r in records)] or list(_DETAIL_MAIN)
    for must in ("case_id", "执行结果", "结果分析"):
        if must not in main_cols:
            main_cols.append(must)

    col_class = {
        "case_id": "c-id",
        "step_no": "c-step",
        "title": "c-title",
        "group": "c-group",
        "priority": "c-pri",
        "tool_name": "c-tool",
        "执行结果": "c-res",
        "执行时间ms": "c-ms",
        "结果分析": "c-note",
    }
    head = '<th class="c-exp"></th>' + "".join(
        f'<th class="{col_class.get(c, "")}">{_esc(c)}</th>' for c in main_cols
    )
    body: list[str] = []
    panels: list[str] = []
    for i, rec in enumerate(records):
        result = (rec.get("执行结果") or rec.get("result") or "").lower()
        case_id = rec.get("case_id", "")
        title = rec.get("title", "")
        tds = [
            f'<td class="c-exp"><button type="button" class="toggle" data-i="{i}" '
            f'data-case="{_esc(case_id)}" data-title="{_esc(title)}" '
            f'data-result="{_esc(result)}">详情</button></td>'
        ]
        for col in main_cols:
            raw = rec.get(col, "")
            text = _preview(raw.replace("\n", " "), 72) if col == "结果分析" else raw
            cls = col_class.get(col, "")
            if col in {"执行结果", "result"}:
                cls = f"{cls} tag {_esc(result)}".strip()
            elif col == "结果分析":
                cls = f"{cls} note".strip()
            elif col == "执行时间ms":
                cls = f"{cls} num".strip()
            tds.append(f'<td class="{cls}" title="{_esc(raw)}">{_esc(text)}</td>')

        blob = _esc(
            " ".join(
                [
                    case_id,
                    title,
                    rec.get("tool_name", ""),
                    rec.get("user_question", ""),
                    rec.get("assert_hints", ""),
                    rec.get("assert_expr", ""),
                    rec.get("结果分析", "") or rec.get("失败说明", ""),
                    rec.get("expect_tools", ""),
                ]
            )
        )
        body.append(
            f'<tr class="main" data-result="{_esc(result)}" data-q="{blob}" data-i="{i}">'
            + "".join(tds)
            + "</tr>"
        )
        panels.append(
            f'<div class="drawer-panel" data-i="{i}" hidden>'
            f"{_expand_panel(rec, i)}"
            f"</div>"
        )

    return f"""
    <p class="hint">点「详情」打开右侧抽屉；抽屉内三块<strong>默认收起</strong>，再点标题展开（请求/响应可复制）。</p>
    <div class="toolbar">
      <button type="button" class="on" data-filter="all">全部 {len(records)}</button>
      <button type="button" data-filter="failed">失败</button>
      <button type="button" data-filter="passed">通过</button>
      <button type="button" data-filter="skipped">跳过</button>
      <input id="q" placeholder="搜索用例、问题、assert、结果分析" />
    </div>
    <div class="scroll">
      <table class="detail">
        <thead><tr>{head}</tr></thead>
        <tbody id="rows">{''.join(body)}</tbody>
      </table>
    </div>
    <div class="drawer-mask" id="drawer-mask" hidden></div>
    <aside class="drawer" id="drawer" hidden aria-hidden="true">
      <div class="drawer-head">
        <div class="drawer-head-main">
          <div class="drawer-case" id="drawer-case"></div>
          <div class="drawer-title" id="drawer-title"></div>
        </div>
        <div class="drawer-head-actions">
          <span class="drawer-badge" id="drawer-badge"></span>
          <button type="button" class="drawer-close" id="drawer-close">关闭</button>
        </div>
      </div>
      <div class="drawer-body" id="drawer-body">{''.join(panels)}</div>
    </aside>
    <script>
    const mains = [...document.querySelectorAll('tr.main')];
    const drawer = document.getElementById('drawer');
    const mask = document.getElementById('drawer-mask');
    const panels = [...document.querySelectorAll('.drawer-panel')];
    let filter = 'all';
    let query = '';
    let openIdx = null;

    function apply() {{
      const q = query.trim().toLowerCase();
      for (const tr of mains) {{
        const okf = filter === 'all' || tr.dataset.result === filter
          || (filter === 'failed' && tr.dataset.result === 'error');
        const okq = !q || (tr.dataset.q || '').toLowerCase().includes(q);
        tr.hidden = !(okf && okq);
      }}
    }}
    function setRowActive(i) {{
      mains.forEach(tr => tr.classList.toggle('active', tr.dataset.i === String(i)));
      document.querySelectorAll('.toggle').forEach(b => {{
        const on = b.dataset.i === String(i);
        b.classList.toggle('on', on);
        b.textContent = on ? '查看中' : '详情';
      }});
    }}
    function openDrawer(btn) {{
      const i = String(btn.dataset.i);
      openIdx = i;
      panels.forEach(p => {{
        const on = String(p.dataset.i) === i;
        p.hidden = !on;
        p.classList.toggle('active', on);
        // 每次打开都恢复为收起，需再点标题展开
        if (on) {{
          p.querySelectorAll('.fold').forEach(sec => {{
            sec.classList.remove('open');
            const h = sec.querySelector('.fold-head');
            if (h) h.setAttribute('aria-expanded', 'false');
          }});
        }}
      }});
      document.getElementById('drawer-case').textContent = btn.dataset.case || '';
      document.getElementById('drawer-title').textContent = btn.dataset.title || '';
      const badge = document.getElementById('drawer-badge');
      const res = (btn.dataset.result || '').toLowerCase();
      badge.textContent = res || '—';
      badge.className = 'drawer-badge ' + res;
      drawer.hidden = false;
      mask.hidden = false;
      drawer.classList.add('open');
      drawer.setAttribute('aria-hidden', 'false');
      document.body.classList.add('drawer-open');
      setRowActive(i);
      const body = document.getElementById('drawer-body');
      if (body) body.scrollTop = 0;
    }}
    function closeDrawer() {{
      openIdx = null;
      drawer.hidden = true;
      mask.hidden = true;
      drawer.classList.remove('open');
      drawer.setAttribute('aria-hidden', 'true');
      document.body.classList.remove('drawer-open');
      panels.forEach(p => {{
        p.hidden = true;
        p.classList.remove('active');
      }});
      setRowActive(null);
    }}
    document.querySelectorAll('.toolbar button').forEach(btn => {{
      btn.addEventListener('click', () => {{
        filter = btn.dataset.filter;
        document.querySelectorAll('.toolbar button').forEach(b => b.classList.toggle('on', b === btn));
        apply();
      }});
    }});
    document.getElementById('q').addEventListener('input', (ev) => {{
      query = ev.target.value || '';
      apply();
    }});
    document.querySelectorAll('.toggle').forEach(btn => {{
      btn.addEventListener('click', () => {{
        if (openIdx === btn.dataset.i) closeDrawer();
        else openDrawer(btn);
      }});
    }});
    document.getElementById('drawer-close').addEventListener('click', closeDrawer);
    mask.addEventListener('click', closeDrawer);
    document.addEventListener('keydown', (ev) => {{
      if (ev.key === 'Escape' && openIdx !== null) closeDrawer();
    }});
    async function copyText(text, btn) {{
      try {{
        await navigator.clipboard.writeText(text);
      }} catch (e) {{
        const ta = document.createElement('textarea');
        ta.value = text; document.body.appendChild(ta);
        ta.select(); document.execCommand('copy'); ta.remove();
      }}
      const old = btn.textContent;
      btn.textContent = '已复制';
      btn.classList.add('ok');
      setTimeout(() => {{ btn.textContent = old; btn.classList.remove('ok'); }}, 1200);
    }}
    document.querySelectorAll('.copy-btn').forEach(btn => {{
      btn.addEventListener('click', () => {{
        const el = document.getElementById(btn.dataset.target);
        if (!el) return;
        const text = el.textContent || '';
        if (!text || text === '（空）') return;
        copyText(text, btn);
      }});
    }});
    document.querySelectorAll('.fold-head').forEach(btn => {{
      btn.addEventListener('click', () => {{
        const sec = btn.closest('.fold');
        if (!sec) return;
        const open = !sec.classList.contains('open');
        sec.classList.toggle('open', open);
        btn.setAttribute('aria-expanded', open ? 'true' : 'false');
      }});
    }});
    </script>
    """


def render_result_page(*, xlsx: Path, run_id: str, download_href: str, back_href: str = "/index.html") -> str:
    from openpyxl import load_workbook

    meta_path = xlsx.parent / "meta.json"
    finished = run_id
    cases_name = ""
    cases_xlsx = ""
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            finished = str(meta.get("finished_at") or finished)
            cases_xlsx = str(meta.get("cases_xlsx") or "")
            cases_name = Path(cases_xlsx).name if cases_xlsx else ""
        except json.JSONDecodeError:
            pass

    wb = load_workbook(xlsx, data_only=True)
    try:
        summary_ws = wb["汇总"] if "汇总" in wb.sheetnames else (
            wb["汇总统计"] if "汇总统计" in wb.sheetnames else None
        )
        detail_ws = wb["执行明细"] if "执行明细" in wb.sheetnames else None
        kpis, callout, sections = parse_summary(summary_ws) if summary_ws is not None else ([], "", [])
        records = parse_detail(detail_ws) if detail_ws is not None else []
    finally:
        wb.close()

    _enrich_from_cases_xlsx(records, cases_xlsx)

    summary = _summary_html(kpis, callout, sections)
    detail = _detail_html(records)
    sub = finished + (f" · {cases_name}" if cases_name else "")
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>执行结果 { _esc(run_id) }</title>
<style>
  :root {{
    --bg:#f5f7fb; --panel:#ffffff; --soft:#f1f5f9; --line:#e2e8f0; --text:#0f172a;
    --muted:#64748b; --accent:#2563eb; --ok:#15803d; --bad:#b91c1c;
  }}
  * {{ box-sizing:border-box; }}
  body {{
    margin:0; font-family:"SF Pro Text","PingFang SC","Segoe UI",sans-serif;
    background:linear-gradient(180deg, #eef3fb 0%, var(--bg) 180px);
    color:var(--text); min-height:100vh;
  }}
  a {{ color:var(--accent); text-decoration:none; }}
  header {{
    display:flex; justify-content:space-between; gap:16px; align-items:center;
    padding:14px 28px; border-bottom:1px solid var(--line); background:rgba(255,255,255,.94);
    backdrop-filter:blur(8px); position:sticky; top:0; z-index:5;
  }}
  h1 {{ margin:0; font-size:20px; letter-spacing:-.02em; }}
  .sub {{ color:var(--muted); font-size:12px; margin-top:4px; }}
  .actions {{ display:flex; gap:10px; align-items:center; }}
  .btn {{
    background:var(--accent); color:#fff; border-radius:10px; padding:8px 14px;
    font-weight:700; font-size:13px;
  }}
  .btn.ghost {{ background:#fff; color:var(--text); border:1px solid var(--line); }}
  main {{ padding:16px 28px 48px; width:100%; max-width:1600px; margin:0 auto; }}
  .tabs {{ display:flex; gap:8px; margin-bottom:14px; }}
  .tabs button {{
    background:#fff; color:var(--text); border:1px solid var(--line); border-radius:999px;
    padding:6px 14px; cursor:pointer;
  }}
  .tabs button.on {{ background:var(--accent); color:#fff; border-color:transparent; font-weight:700; }}
  .kpis {{ display:flex; flex-wrap:wrap; gap:10px; margin-bottom:12px; }}
  .kpi {{
    background:var(--panel); border:1px solid var(--line); border-radius:12px;
    min-width:108px; padding:10px 12px; box-shadow:0 1px 2px rgba(15,23,42,.04);
  }}
  .kpi span {{ display:block; color:var(--muted); font-size:12px; }}
  .kpi b {{ font-size:22px; }}
  .kpi.ok b {{ color:var(--ok); }}
  .kpi.bad b {{ color:var(--bad); }}
  .callout {{
    background:#eff6ff; border:1px solid #bfdbfe; border-radius:12px;
    padding:12px 14px; color:var(--text); line-height:1.55;
  }}
  h2 {{ font-size:15px; margin:18px 0 8px; color:#334155; }}
  table {{
    width:100%; border-collapse:collapse; background:var(--panel);
    border:1px solid var(--line); border-radius:12px;
  }}
  th, td {{ padding:8px 10px; border-bottom:1px solid var(--line); text-align:left; font-size:12px; vertical-align:top; }}
  th {{ color:var(--muted); background:var(--soft); position:sticky; top:0; z-index:1; font-weight:600; }}
  .table-wrap {{
    display:block; width:100%; overflow:auto; border-radius:12px; margin-bottom:12px;
    border:1px solid var(--line); background:var(--panel);
    box-shadow:0 1px 2px rgba(15,23,42,.04);
  }}
  .table-wrap table {{ border:0; border-radius:0; width:100%; }}
  table.breakdown, table.fail-table {{ table-layout:fixed; width:100%; }}
  table.breakdown th, table.breakdown td,
  table.fail-table th, table.fail-table td {{
    padding:10px 12px; white-space:normal; overflow:visible;
    word-break:break-word; overflow-wrap:anywhere; vertical-align:top; line-height:1.45;
  }}
  table.breakdown td.num, table.fail-table td.num,
  table.breakdown th.num, table.fail-table th.num {{
    white-space:nowrap; text-align:right; font-variant-numeric:tabular-nums;
  }}
  table.breakdown th:first-child, table.breakdown td.text {{ width:40%; }}
  table.breakdown th:not(:first-child), table.breakdown td.num {{ width:12%; text-align:right; }}
  table.fail-table th:nth-child(1), table.fail-table td:nth-child(1) {{ width:11%; }}
  table.fail-table th:nth-child(2), table.fail-table td:nth-child(2) {{ width:6%; text-align:right; }}
  table.fail-table th:nth-child(3), table.fail-table td:nth-child(3) {{ width:7%; text-align:right; }}
  table.fail-table th:nth-child(4), table.fail-table td:nth-child(4) {{ width:15%; }}
  table.fail-table th:nth-child(5), table.fail-table td:nth-child(5) {{ width:13%; }}
  table.fail-table th:nth-child(6), table.fail-table td:nth-child(6) {{ width:28%; }}
  table.fail-table th:nth-child(7), table.fail-table td:nth-child(7) {{ width:20%; }}
  table.fail-table td.text {{ color:#1e293b; }}

  /* —— 执行明细列表：吃满宽度、固定列比、可换行不叠字 —— */
  .scroll {{
    overflow:auto; max-height:calc(100vh - 200px); border-radius:12px;
    border:1px solid var(--line); background:var(--panel);
    box-shadow:0 1px 2px rgba(15,23,42,.04);
  }}
  table.detail {{
    table-layout:fixed; width:100%; min-width:960px; border:0;
  }}
  table.detail th, table.detail td {{
    white-space:normal; word-break:break-word; overflow-wrap:anywhere;
    line-height:1.45; padding:10px 12px;
  }}
  table.detail .c-exp {{ width:56px; white-space:nowrap; }}
  table.detail .c-id {{ width:8%; }}
  table.detail .c-step {{ width:4%; white-space:nowrap; }}
  table.detail .c-title {{ width:18%; }}
  table.detail .c-group {{ width:11%; }}
  table.detail .c-pri {{ width:5%; white-space:nowrap; }}
  table.detail .c-tool {{ width:13%; }}
  table.detail .c-res {{ width:6%; white-space:nowrap; }}
  table.detail .c-ms {{ width:7%; white-space:nowrap; text-align:right; }}
  table.detail .c-note {{ width:28%; }}
  /* 列表摘要：单行省略，避免窄列把中文拆成竖排 */
  table.detail td.note {{
    color:#334155; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
    word-break:normal; overflow-wrap:normal;
  }}
  table.detail td.c-title, table.detail td.c-group, table.detail td.c-tool {{
    word-break:break-word; overflow-wrap:anywhere;
  }}
  table.detail td.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
  table.detail td.tag.passed {{ color:var(--ok); font-weight:700; }}
  table.detail td.tag.failed, table.detail td.tag.error {{ color:var(--bad); font-weight:700; }}
  td.bad {{ color:var(--bad); font-weight:700; }}
  td.ok {{ color:var(--ok); font-weight:700; }}
  .toggle {{
    background:#eff6ff; color:var(--accent); border:1px solid #bfdbfe;
    border-radius:8px; padding:4px 8px; cursor:pointer; font-size:12px; white-space:nowrap;
  }}
  .toggle.on {{ background:var(--accent); color:#fff; border-color:transparent; }}
  tr.main.active > td {{ background:#eff6ff; }}
  .hint {{ color:var(--muted); font-size:13px; margin:0 0 10px; line-height:1.5; }}
  .toolbar {{ display:flex; gap:8px; align-items:center; margin-bottom:12px; flex-wrap:wrap; }}
  .toolbar button, .toolbar input {{
    background:#fff; color:var(--text); border:1px solid var(--line); border-radius:999px;
    padding:6px 12px;
  }}
  .toolbar button.on {{ background:var(--accent); color:#fff; font-weight:700; }}
  .toolbar input {{ border-radius:10px; min-width:280px; flex:1; max-width:420px; background:#fff; }}
  .panel {{ display:none; }}
  .panel.on {{ display:block; }}
  .muted {{ color:var(--muted); }}
  tr.main:hover > td {{ background:#f8fafc; }}

  /* —— 右侧详情抽屉 —— */
  body.drawer-open {{ overflow:hidden; }}
  .drawer-mask {{
    position:fixed; inset:0; background:rgba(15,23,42,.28); z-index:40;
  }}
  .drawer {{
    position:fixed; top:0; right:0; bottom:0; z-index:41;
    width:min(720px, 92vw); background:#fff; border-left:1px solid var(--line);
    box-shadow:-8px 0 28px rgba(15,23,42,.12);
    display:none; flex-direction:column;
  }}
  .drawer.open {{ display:flex; }}
  .drawer-panel {{ display:none; }}
  .drawer-panel.active {{ display:block; }}
  .drawer-head {{
    flex:0 0 auto; display:flex; gap:12px; align-items:flex-start; justify-content:space-between;
    padding:14px 16px; border-bottom:1px solid var(--line); background:#fff;
  }}
  .drawer-head-main {{ min-width:0; flex:1; }}
  .drawer-case {{
    font-size:12px; font-weight:700; color:var(--accent); font-family:ui-monospace,Menlo,monospace;
  }}
  .drawer-title {{
    margin-top:4px; font-size:15px; font-weight:700; color:var(--text);
    word-break:break-word; line-height:1.4;
  }}
  .drawer-head-actions {{ display:flex; gap:8px; align-items:center; flex:0 0 auto; }}
  .drawer-badge {{
    font-size:12px; font-weight:700; padding:3px 8px; border-radius:999px; background:var(--soft); color:var(--muted);
  }}
  .drawer-badge.passed {{ background:#dcfce7; color:var(--ok); }}
  .drawer-badge.failed, .drawer-badge.error {{ background:#fee2e2; color:var(--bad); }}
  .drawer-close {{
    background:#fff; border:1px solid var(--line); border-radius:8px;
    padding:6px 12px; cursor:pointer; font-size:13px;
  }}
  .drawer-body {{
    flex:1 1 auto; overflow:auto; padding:14px 16px 24px; background:#f8fafc;
  }}
  .drawer-panel .expand {{
    display:flex; flex-direction:column; gap:12px; width:100%; padding:0;
  }}
  .fold {{
    background:#fff; border:1px solid var(--line); border-radius:12px; min-width:0; overflow:hidden;
  }}
  .fold-head {{
    width:100%; display:flex; align-items:center; justify-content:space-between; gap:12px;
    background:transparent; border:0; border-bottom:1px solid transparent;
    padding:12px 16px; cursor:pointer; text-align:left;
  }}
  .fold.open .fold-head {{ border-bottom-color:var(--line); }}
  .fold-title {{ font-size:14px; font-weight:700; color:var(--accent); }}
  .fold-caret {{
    width:8px; height:8px; border-right:2px solid var(--muted); border-bottom:2px solid var(--muted);
    transform:rotate(45deg); transition:transform .15s ease; flex:0 0 auto;
  }}
  .fold.open .fold-caret {{ transform:rotate(-135deg); }}
  .fold-body {{ display:none; padding:12px 16px 16px; }}
  .fold.open .fold-body {{ display:block; }}
  .payload-head h4 {{ margin:0; font-size:13px; color:var(--accent); }}
  .kv-grid {{
    display:grid; grid-template-columns:1fr; gap:12px;
  }}
  .fold[data-fold^="meta-"] .kv-grid {{ grid-template-columns:1fr 1fr; }}
  .kv {{ min-width:0; }}
  .kv.empty .v {{ color:var(--muted); font-style:italic; }}
  .k {{ color:var(--muted); font-size:12px; font-weight:600; margin-bottom:6px; }}
  .v {{
    margin:0; white-space:pre-wrap; word-break:break-word; overflow-wrap:anywhere;
    font-size:12.5px; font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
    line-height:1.5; color:#1e293b;
    background:var(--soft); border:1px solid var(--line); border-radius:8px;
    padding:10px 12px; overflow:auto;
  }}
  .v.compact {{ max-height:180px; }}
  .io-row {{
    display:grid; grid-template-columns:1fr; gap:12px; width:100%;
  }}
  .payload {{
    background:var(--soft); border:1px solid var(--line); border-radius:12px;
    padding:12px 14px; min-width:0; display:flex; flex-direction:column; gap:10px;
  }}
  .payload-head {{
    display:flex; align-items:center; justify-content:space-between; gap:10px;
    padding-bottom:8px; border-bottom:1px solid var(--line);
  }}
  .payload-body {{ max-height:min(40vh, 420px); flex:1; background:#fff; }}
  .copy-btn {{
    background:#eff6ff; color:var(--accent); border:1px solid #bfdbfe;
    border-radius:8px; padding:4px 12px; cursor:pointer; font-size:12px; font-weight:600;
  }}
  .copy-btn:hover {{ background:#dbeafe; }}
  .copy-btn.ok {{ background:#dcfce7; color:var(--ok); border-color:#86efac; }}
</style>
</head>
<body>
  <header>
    <div>
      <h1>执行结果</h1>
      <div class="sub">{_esc(sub)}</div>
    </div>
    <div class="actions">
      <a class="btn ghost" href="{_esc(back_href)}">返回列表</a>
      <a class="btn" href="{_esc(download_href)}" download>下载 Excel</a>
    </div>
  </header>
  <main>
    <div class="tabs">
      <button type="button" class="on" data-tab="summary">汇总</button>
      <button type="button" data-tab="detail">执行明细</button>
    </div>
    <section id="summary" class="panel on">{summary}</section>
    <section id="detail" class="panel">{detail}</section>
  </main>
  <script>
  document.querySelectorAll('.tabs button').forEach(btn => {{
    btn.addEventListener('click', () => {{
      document.querySelectorAll('.tabs button').forEach(b => b.classList.toggle('on', b === btn));
      document.querySelectorAll('.panel').forEach(p => p.classList.toggle('on', p.id === btn.dataset.tab));
    }});
  }});
  </script>
</body>
</html>
"""
