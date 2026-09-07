#!/usr/bin/env python3
"""Build the weekly quality board workbook with expanded drill-downs."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import openpyxl
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.worksheet import Worksheet

ROOT = Path("/Users/xixi/Downloads/poker-gto-history-qa")
CASES_XLSX = Path("/Users/xixi/Downloads/app测试用例_第一版 (1).xlsx")
PRD_PAGES = Path(
    "/Users/xixi/Documents/ChatGPT/复盘需求/qa-case-system/runs/PHASE-1-FULL-PRD/prd-page-detailed-extract.json"
)
PRD_LIST = Path(
    "/Users/xixi/Documents/ChatGPT/复盘需求/qa-case-system/runs/PHASE-1-FULL-PRD/prd-page-list-extract.json"
)
TP_JSON = ROOT / "report-metric-qa/test-points.json"
OUT = Path("/Users/xixi/Downloads/质量看板_周报明细_第一版.xlsx")
SNAP = ROOT / "output/weekly_quality_board_snapshot.json"

HEADER_FILL = PatternFill("solid", fgColor="1F4E79")
HEADER_FONT = Font(color="FFFFFF", bold=True, name="Microsoft YaHei", size=10)
TITLE_FONT = Font(bold=True, name="Microsoft YaHei", size=14)
WRAP = Alignment(wrap_text=True, vertical="top")
THIN = Border(
    left=Side(style="thin", color="D9D9D9"),
    right=Side(style="thin", color="D9D9D9"),
    top=Side(style="thin", color="D9D9D9"),
    bottom=Side(style="thin", color="D9D9D9"),
)
PASS_FILL = PatternFill("solid", fgColor="E2EFDA")
FAIL_FILL = PatternFill("solid", fgColor="FCE4D6")
SKIP_FILL = PatternFill("solid", fgColor="FFF2CC")
TODO_FILL = PatternFill("solid", fgColor="F2F2F2")
MODEL_FILL = PatternFill("solid", fgColor="DEEBF7")
FACT_FILL = PatternFill("solid", fgColor="E2EFDA")
BILL_FILL = PatternFill("solid", fgColor="FCE4D6")
EDIT_FILL = PatternFill("solid", fgColor="FFF8DC")
GROUP_FILL = PatternFill("solid", fgColor="E8DFD0")
KPI_FILL = PatternFill("solid", fgColor="F3EFE7")
PAGE_BANDS = (
    PatternFill("solid", fgColor="F7F4EE"),
    PatternFill("solid", fgColor="EEF5F2"),
)
BODY_FONT = Font(name="Microsoft YaHei", size=11)
HINT_FONT = Font(name="Microsoft YaHei", size=10, color="78716C")

CHROME = {
    "状态栏",
    "返回",
    "底部导航",
    "关闭",
    "三方登录按钮",
    "协议勾选及协议",
    "隐私入口",
    "品牌价值区",
    "轻量“复盘报告”标题和返回",
    "标题、返回",
    "开始使用",
    "确认采用底部弹层",
    "不设置独立录屏授权说明页",
}

# 内部状态 / 配置 / 非页面展示，不算「页面上的数据」
NOT_PAGE_DATA = {
    "待回跳目标",
    "用户首次状态",
    "欢迎页版本",
    "盲注选项元数据",
    "FAQ 发布配置",
    "语言发布配置",
    "退出状态",
    "登录方式",
}

NON_POKER_PAGES = {
    "P01",
    "P02",
    "P19",
    "P20",
    "P21",
    "P22",
    "P23",
    "P24",
    "P25",
    "P26",
    "P27",
    "P28",
    "P29",
    "P30",
    "P31",
    "P32",
    "P33",
    "P34",
}

MODEL_NAME_RE = re.compile(
    r"GTO|建议改进|打法亮点|改进建议|AI 分析|AI分析|弱点|决策质量|情绪|模型|"
    r"智能总结|整体改进|建议摘要|亮点摘要|表现总结|主结论|洞察|打法分析|对抗总结|"
    r"位置总结|本场建议|本场亮点|下次提醒|对手判断"
)
AI_LOC_RE = re.compile(r"AI-\d+")
# 卡片容器会挂 AI 章节，本身仍是事实列表，不进模型结论
MODEL_SKIP_CONTAINERS = ("复盘卡", "完成场次卡", "场次卡列表", "消息列表")

LABEL_CODES = {
    "ev_relation_type",
    "luck_direction",
    "decision_impact_direction",
    "decision_quality_label",
}


def executed_status(st: str) -> str:
    if st in {"通过"}:
        return "pass"
    if st in {"失败", "未通过"}:
        return "fail"
    if st in {"阻塞"}:
        return "block"
    if st in {"跳过", "暂不执行"}:
        return "skip"
    return "todo"


def norm_status(st: str) -> str:
    if st in {"未通过"}:
        return "失败"
    if st in {"暂不执行"}:
        return "跳过"
    if st in {"", None}:
        return "未执行"
    return st


def style_header(ws: Worksheet, row: int, ncols: int) -> None:
    for c in range(1, ncols + 1):
        cell = ws.cell(row, c)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        cell.border = THIN


def autosize(ws: Worksheet, widths: dict[int, int]) -> None:
    for i, w in widths.items():
        ws.column_dimensions[get_column_letter(i)].width = w


def apply_border_wrap(ws: Worksheet, r: int, ncols: int) -> None:
    for c in range(1, ncols + 1):
        ws.cell(r, c).alignment = WRAP
        ws.cell(r, c).border = THIN


def load_cases() -> list[dict]:
    wb = openpyxl.load_workbook(CASES_XLSX, data_only=False)
    sheets = {
        "核心业务流程": {
            "module": "核心业务流程",
            "id": 1,
            "title": 2,
            "status": 3,
            "date": 4,
            "prio": 6,
            "page": 7,
            "header": 4,
        },
        "页面测试": {
            "module": "页面测试",
            "id": 1,
            "title": 2,
            "status": 3,
            "date": 4,
            "prio": 6,
            "page": 7,
            "header": 4,
        },
        "数据流测试": {
            "module": "数据流测试",
            "id": 1,
            "title": 2,
            "status": 3,
            "date": 4,
            "prio": 6,
            "page": 7,
            "header": 4,
        },
        "切局模块测试": {
            "module": "切局模块测试",
            "id": 1,
            "title": 2,
            "status": 3,
            "date": 4,
            "prio": 5,
            "page": 6,
            "header": 1,
            "func": 7,
        },
    }
    out = []
    for name, cfg in sheets.items():
        ws = wb[name]
        for r in range(cfg["header"] + 1, ws.max_row + 1):
            cid = ws.cell(r, cfg["id"]).value
            if not (isinstance(cid, str) and cid.startswith("TC-")):
                continue
            st = ws.cell(r, cfg["status"]).value
            st = (st or "").strip() if isinstance(st, str) else str(st or "")
            d = ws.cell(r, cfg["date"]).value
            if isinstance(d, datetime):
                d = d.strftime("%Y-%m-%d")
            elif d:
                d = str(d)
            else:
                d = ""
            item = {
                "module": cfg["module"],
                "id": cid,
                "title": ws.cell(r, cfg["title"]).value or "",
                "status": norm_status(st),
                "raw_status": st or "未执行",
                "date": d,
                "prio": ws.cell(r, cfg["prio"]).value or "",
                "page": ws.cell(r, cfg["page"]).value or "",
                "func": ws.cell(r, cfg["func"]).value if "func" in cfg else "",
            }
            item["bucket"] = executed_status(item["status"])
            out.append(item)
    return out


def page_id_from_list_code(code: str) -> str:
    m = re.search(r"P-?(\d+)", str(code))
    if not m:
        return ""
    return f"P{int(m.group(1)):02d}"


def load_prd_fields() -> list[dict]:
    pages = json.loads(PRD_PAGES.read_text())
    plist = json.loads(PRD_LIST.read_text())
    names = {}
    for p in plist:
        pid = page_id_from_list_code(p.get("编号") or "")
        names[pid] = p.get("页面名称") or pid

    fields = []
    seen = set()

    def add(page_id: str, page_name: str, field: str, source: str, gen: str = "", loc: str = "") -> None:
        field = (field or "").strip()
        if not field or field in CHROME or field in NOT_PAGE_DATA:
            return
        if field.startswith("打开原图"):
            return
        if "发布配置" in field or field.endswith("元数据"):
            return
        if page_id == "P01" and field == "协议版本":
            return
        key = (page_id, field)
        if key in seen:
            return
        seen.add(key)
        fields.append(
            {
                "page_id": page_id,
                "page_name": page_name,
                "field": field,
                "source": source,
                "gen": gen,
                "loc": loc or "",
            }
        )

    for page in pages:
        pid = page.get("pageId") or ""
        pname = page.get("pageName") or names.get(pid, pid)
        for sec in page.get("subsections") or []:
            title = sec.get("title") or ""
            if sec.get("kind") != "table":
                continue
            rows = sec.get("rows") or []
            if "页面元素说明" in title:
                for row in rows:
                    field = row.get("区域/元素") or ""
                    gen = row.get("内容生成方式") or ""
                    loc = row.get("全局规则定位") or ""
                    if not is_model_prd_field(field, gen, loc):
                        continue
                    add(pid, pname, field, "7.x.5 页面元素", gen, loc)
            elif "页面数据与内容生成规则" in title:
                for row in rows:
                    add(
                        pid,
                        pname,
                        row.get("页面内容") or "",
                        "7.x.6 页面数据",
                        row.get("计算或生成规则") or "",
                        row.get("全局规则定位") or "",
                    )

    return fields


def unique_metrics() -> list[dict]:
    data = json.loads(TP_JSON.read_text())
    seen = {}
    for tp in data.get("test_points") or []:
        if tp.get("family") != "metric_scenario":
            continue
        code = tp.get("metric_code")
        if not code or code in seen:
            continue
        seen[code] = {
            "code": code,
            "name": tp.get("metric_name") or "",
            "calc_type": tp.get("calc_type") or "",
            "calc_type_name": tp.get("calc_type_name") or "",
            "visible": tp.get("visible") or "",
            "modules": "、".join(tp.get("report_modules") or []),
            "json_path": tp.get("json_path") or "",
            "priority": tp.get("priority") or "",
        }
    return list(seen.values())


def module_page_for_report(modules: str) -> tuple[str, str]:
    mapping = [
        ("智能总结", "P08", "单场复盘·总览"),
        ("整体改进建议", "P08", "单场复盘·总览"),
        ("对手与位置", "P10", "单场复盘·对手"),
        ("关键手牌", "P11", "单手概览"),
        ("盈亏与期望", "P08", "单场复盘·总览"),
        ("情绪与心态", "P08", "单场复盘·总览"),
        ("重点注意", "P08", "单场复盘·总览"),
    ]
    for key, pid, pname in mapping:
        if key in (modules or ""):
            return pid, pname
    return "P08", "单场复盘·总览"


def is_model_prd_field(field: str, gen: str = "", loc: str = "") -> bool:
    """模型结论：第 15 章 AI-xxx，或字段/生成方式本身是 AI 文案。"""
    if any(k in (field or "") for k in MODEL_SKIP_CONTAINERS):
        return False
    if AI_LOC_RE.search(loc or ""):
        return True
    blob = f"{field} {gen}"
    if MODEL_NAME_RE.search(blob):
        return True
    if "AI 生成" in (gen or ""):
        return True
    return False


def classify_prd_field(page_id: str, field: str, gen: str, loc: str = "") -> str:
    if is_model_prd_field(field, gen, loc):
        return "模型"
    if page_id in NON_POKER_PAGES or page_id == "P07":
        return "非牌局业务字段"
    return "牌局事实"


def classify_metric(m: dict) -> str:
    code = m["code"]
    if m["calc_type"] == "T4" or code in LABEL_CODES or code.startswith("gto_"):
        return "模型"
    if "decision_quality" in code or "risk_by" in code:
        return "模型"
    return "牌局事实"


def pages_missing_model(prd_fields: list[dict], model_rows: list[dict]) -> list[tuple[str, str]]:
    """有 AI 结论的页面必须出现在模型结论表。"""
    expected: dict[str, str] = {}
    for f in prd_fields:
        if is_model_prd_field(f["field"], f.get("gen") or "", f.get("loc") or ""):
            expected[f["page_id"]] = f["page_name"]
    have = {r["page_id"] for r in model_rows}
    return [(pid, expected[pid]) for pid in sorted(expected) if pid not in have]


def module_stats(cases: list[dict]) -> list[dict]:
    order = ["核心业务流程", "页面测试", "数据流测试", "切局模块测试", "数据准确性"]
    by = defaultdict(list)
    for c in cases:
        by[c["module"]].append(c)
    rows = []
    for name in order:
        items = by.get(name, [])
        n = len(items)
        n_pass = sum(1 for x in items if x["bucket"] == "pass")
        n_fail = sum(1 for x in items if x["bucket"] == "fail")
        n_block = sum(1 for x in items if x["bucket"] == "block")
        n_skip = sum(1 for x in items if x["bucket"] == "skip")
        done = n_pass + n_fail + n_block + n_skip
        rows.append(
            {
                "module": name,
                "n": n,
                "done": done,
                "pass": n_pass,
                "fail": n_fail,
                "block": n_block,
                "skip": n_skip,
                "todo": n - done,
                "exec_rate": (done / n) if n else None,
                "pass_rate": (n_pass / done) if done else None,
            }
        )
    return rows


def write_overview(wb, stats, n_fact, n_model, n_bill, n_na, n_slice):
    ws = wb.active
    ws.title = "00_看板总览"
    ws["A1"] = "每周质量看板（展开明细）"
    ws["A1"].font = TITLE_FONT
    ws.merge_cells("A1:F1")
    ws["A2"] = (
        "9 个总数保留；测试执行率拆到五模块再拆到每条用例；事实数据按页面→字段，覆盖率和准确率同一张表两列；"
        "模型结论一层写成 页面/字段；切局一层对着测试集；耗时和并发只挂值。"
        "覆盖/准确/切局三条件/耗时/并发请在对应 Sheet 手工填。建议目标可改。"
    )
    ws["A2"].alignment = WRAP
    ws.merge_cells("A2:F2")
    ws.row_dimensions[2].height = 48

    headers = ["编号", "指标", "当前值", "建议目标", "明细在哪", "口径"]
    for i, h in enumerate(headers, 1):
        ws.cell(4, i, h)
    style_header(ws, 4, 6)

    total_n = sum(s["n"] for s in stats)
    total_done = sum(s["done"] for s in stats)
    total_pass = sum(s["pass"] for s in stats)
    exec_s = f"{total_done/total_n:.1%}" if total_n else "—"
    rows = [
        ("M1", "测试执行率", f"{exec_s}（{total_done}/{total_n}）", "P0 过程≥80%；范围内发版 100%", "01 五个模块", "已执行/范围内总数"),
        ("M2", "切局准确率", "待按测试集三条件打分", "≥95%", "02_切局准确率", "三条全过的条数/测试集条数"),
        ("M3", "事实数据覆盖率", f"分母已列 {n_fact} 个字段，待你标已实现", "过程≥90%；适用字段发版 100%", "03_事实数据字段", "已实现/（全集−不适用）"),
        ("M4", "事实数据准确率", "待按字段核对 32手+e2e", "≥95%；牌面/行动/底池≥98%", "03_事实数据字段（准确列）", "对的字段/已实现且有真值"),
        ("M5", "模型结论覆盖率", f"分母已列 {n_model} 个字段，待你标已实现", "过程≥90%；适用字段发版 100%", "04_模型结论字段", "已实现/（全集−不适用）"),
        ("M6", "报告耗时·均值", "待填（线上停止录屏→报告可打开）", "≤5 分钟（一周数据后校准）", "05_耗时与并发", "本周线上任务算术平均"),
        ("M7", "报告耗时·P95", "待填", "≤12 分钟（一周数据后校准）", "05_耗时与并发", "本周线上任务 95 分位"),
        ("M8", "同时录屏任务数", "待手工填", "先登记现状；占位≥5，压测后冻结", "05_耗时与并发", "当前支持上限"),
        ("M9", "同时解析/出报告任务数", "待手工填", "先登记现状；占位≥5，压测后冻结", "05_耗时与并发", "当前支持上限"),
    ]
    for i, row in enumerate(rows, 5):
        for c, v in enumerate(row, 1):
            ws.cell(i, c, v)
        apply_border_wrap(ws, i, 6)
        ws.row_dimensions[i].height = 32

    ws["A15"] = "M1 第一层 · 五个模块"
    ws["A15"].font = Font(bold=True, name="Microsoft YaHei", size=12)
    h2 = ["模块", "总数", "已执行", "通过", "失败", "跳过", "未完成", "执行率", "通过率"]
    for i, h in enumerate(h2, 1):
        ws.cell(16, i, h)
    style_header(ws, 16, 9)
    for i, s in enumerate(stats, 17):
        vals = [
            s["module"],
            s["n"],
            s["done"],
            s["pass"],
            s["fail"],
            s["skip"],
            s["todo"],
            f"{s['exec_rate']:.1%}" if s["exec_rate"] is not None else "—",
            f"{s['pass_rate']:.1%}" if s["pass_rate"] is not None else "—",
        ]
        for c, v in enumerate(vals, 1):
            ws.cell(i, c, v)
        apply_border_wrap(ws, i, 9)

    ws["A24"] = (
        f"字段分母：事实 {n_fact} · 模型 {n_model} · 非牌局事实 {n_bill}。"
        f"切局测试集 {n_slice} 条。P12 本阶段适用，进覆盖率分母。"
        "未实现不记准确率的错。Credits/会员/订单只覆盖。模型只覆盖。"
    )
    ws["A24"].alignment = WRAP
    ws.merge_cells("A24:I24")
    ws.row_dimensions[24].height = 40
    autosize(ws, {1: 18, 2: 28, 3: 42, 4: 36, 5: 28, 6: 28, 7: 12, 8: 12, 9: 12})
    ws.freeze_panes = "A5"


def write_module_and_cases(wb, stats, cases):
    ws = wb.create_sheet("01_执行率_五模块")
    ws["A1"] = "M1 测试执行率 · 第一层五个模块"
    ws["A1"].font = TITLE_FONT
    headers = ["模块", "总数", "已执行", "通过", "失败", "阻塞", "跳过", "未完成", "执行率", "通过率", "建议目标"]
    for i, h in enumerate(headers, 1):
        ws.cell(3, i, h)
    style_header(ws, 3, 11)
    targets = {
        "核心业务流程": "过程优先闭合，执行率→100%",
        "页面测试": "P0 先跑完；P1 可并行不卡发版",
        "数据流测试": "资金 P0 100% 才谈发版",
        "切局模块测试": "与 M2 测试集分开看；本表是用例执行",
        "数据准确性": "尚无用例，字段核对走 M3/M4",
    }
    for i, s in enumerate(stats, 4):
        vals = [
            s["module"],
            s["n"],
            s["done"],
            s["pass"],
            s["fail"],
            s["block"],
            s["skip"],
            s["todo"],
            f"{s['exec_rate']:.1%}" if s["exec_rate"] is not None else "—",
            f"{s['pass_rate']:.1%}" if s["pass_rate"] is not None else "—",
            targets.get(s["module"], ""),
        ]
        for c, v in enumerate(vals, 1):
            ws.cell(i, c, v)
        apply_border_wrap(ws, i, 11)
    autosize(ws, {1: 18, 2: 10, 3: 10, 4: 10, 5: 10, 6: 10, 7: 10, 8: 10, 9: 12, 10: 12, 11: 36})


def write_slice(wb, cases):
    ws = wb.create_sheet("02_切局准确率")
    ws["A1"] = "M2 切局准确率 · 一层：准备的测试集（当前用切局模块 33 条；前期样本可换）"
    ws["A1"].font = TITLE_FONT
    ws.merge_cells("A1:L1")
    ws["A2"] = (
        "一条算对必须同时：①切出手数=真值手数 ②每段能播放 ③起止落在两手之间。"
        "三列填 是/否。总判定公式会自动算。用例状态仅作参考，M2 以三条件为准。"
    )
    ws["A2"].alignment = WRAP
    ws.merge_cells("A2:L2")
    ws.row_dimensions[2].height = 32
    h = [
        "用例ID",
        "标题",
        "场景",
        "优先级",
        "用例状态(参考)",
        "手数相等",
        "每段能播",
        "起止在两手之间",
        "三条件总判定",
        "真值手数",
        "切出手数",
        "备注",
    ]
    for i, x in enumerate(h, 1):
        ws.cell(4, i, x)
    style_header(ws, 4, 12)
    slices = [c for c in cases if c["module"] == "切局模块测试"]
    dv = DataValidation(type="list", formula1='"是,否"', allow_blank=True)
    ws.add_data_validation(dv)
    for i, c in enumerate(slices, 5):
        ws.cell(i, 1, c["id"])
        ws.cell(i, 2, c["title"])
        ws.cell(i, 3, c["func"])
        ws.cell(i, 4, c["prio"])
        ws.cell(i, 5, c["status"])
        ws.cell(i, 9, f'=IF(COUNTA(F{i}:H{i})<3,"待打分",IF(COUNTIF(F{i}:H{i},"是")=3,"对","错"))')
        apply_border_wrap(ws, i, 12)
        if c["status"] == "通过":
            ws.cell(i, 5).fill = PASS_FILL
        elif c["status"] == "失败":
            ws.cell(i, 5).fill = FAIL_FILL
        dv.add(ws.cell(i, 6))
        dv.add(ws.cell(i, 7))
        dv.add(ws.cell(i, 8))
    last = 4 + len(slices)
    ws.cell(last + 2, 1, "M2 准确率")
    ws.cell(last + 2, 2, f'=IF(COUNTIF(I5:I{last},"待打分")={len(slices)},"待打分",COUNTIF(I5:I{last},"对")/COUNTA(A5:A{last}))')
    ws.cell(last + 2, 2).number_format = "0.0%"
    ws.cell(last + 3, 1, "建议目标")
    ws.cell(last + 3, 2, "≥95%")
    autosize(ws, {1: 22, 2: 48, 3: 22, 4: 10, 5: 16, 6: 12, 7: 12, 8: 18, 9: 14, 10: 12, 11: 12, 12: 20})
    ws.freeze_panes = "A5"
    return slices


def collect_field_rows(prd_fields: list[dict], metrics: list[dict]):
    fact_rows = []
    model_rows = []
    bill_rows = []

    for f in prd_fields:
        kind = classify_prd_field(f["page_id"], f["field"], f["gen"], f.get("loc") or "")
        row = {
            "id": f"{f['page_id']}::{f['field']}",
            "page_id": f["page_id"],
            "page_name": f["page_name"],
            "field": f["field"],
            "kind": kind,
            "origin": f["source"],
            "note": f["gen"],
            "accuracy": kind != "模型",
        }
        if kind == "模型":
            model_rows.append(row)
        elif kind == "非牌局业务字段":
            bill_rows.append(row)
        else:
            fact_rows.append(row)

    for m in metrics:
        kind = classify_metric(m)
        vis = m.get("visible") or ""
        if kind != "模型" and vis != "是" and "单手展示" not in vis:
            continue
        pid, pname = module_page_for_report(m["modules"])
        field = f"{m['name']}（{m['code']}）"
        row = {
            "id": f"{pid}::{m['code']}",
            "page_id": pid,
            "page_name": pname,
            "field": field,
            "kind": kind,
            "origin": f"指标字典 {m['calc_type']} · {m['json_path']}",
            "note": m["modules"],
            "accuracy": kind != "模型",
        }
        if kind == "模型":
            model_rows.append(row)
        else:
            fact_rows.append(row)

    def sort_key(r):
        return (r["page_id"], r["field"])

    fact_rows.sort(key=sort_key)
    model_rows.sort(key=sort_key)
    bill_rows.sort(key=sort_key)

    by_page: dict[str, dict] = defaultdict(lambda: {"name": "", "fact": 0, "bill": 0, "model": 0})
    for row in fact_rows + bill_rows + model_rows:
        by_page[row["page_id"]]["name"] = row["page_name"]
        if row["kind"] == "牌局事实":
            by_page[row["page_id"]]["fact"] += 1
        elif row["kind"] == "非牌局业务字段":
            by_page[row["page_id"]]["bill"] += 1
        else:
            by_page[row["page_id"]]["model"] += 1
    return fact_rows, model_rows, bill_rows, dict(by_page)


def write_html(payload: dict, dest: Path) -> None:
    data = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>每周质量看板</title>
<style>
:root {{
  --bg: #f6f3ee;
  --panel: #fffdf9;
  --ink: #1c1917;
  --muted: #78716c;
  --line: #e7e0d5;
  --ok: #166534;
  --ok-bg: #dcfce7;
  --bad: #9f1239;
  --bad-bg: #ffe4e6;
  --warn: #9a3412;
  --warn-bg: #ffedd5;
  --accent: #0f766e;
  --accent-2: #134e4a;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  font-family: "IBM Plex Sans", "Noto Sans SC", sans-serif;
  background: linear-gradient(180deg, #efe8dc 0%, var(--bg) 220px);
  color: var(--ink);
  line-height: 1.45;
}}
a {{ color: var(--accent); text-decoration: none; }}
.wrap {{ max-width: 1280px; margin: 0 auto; padding: 24px 20px 80px; }}
h1 {{ font-family: "Source Serif 4", "Noto Serif SC", serif; font-weight: 600; margin: 0 0 6px; font-size: 1.85rem; }}
h2 {{ margin: 0; font-size: 1.2rem; }}
.sub {{ color: var(--muted); margin: 0 0 20px; max-width: 72ch; }}
nav.toc {{
  position: sticky; top: 0; z-index: 20;
  background: rgba(246,243,238,.92); backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--line);
  margin: 0 -20px 22px; padding: 10px 20px;
  display: flex; flex-wrap: wrap; gap: 8px;
}}
nav.toc a {{
  padding: 6px 10px; border-radius: 999px; background: #fffdf9;
  border: 1px solid var(--line); font-size: 13px; font-weight: 600;
}}
nav.toc a:hover {{ background: #f3ebe1; text-decoration: none; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(168px, 1fr)); gap: 12px; }}
.card {{
  background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 14px 16px;
}}
.card .label {{ color: var(--muted); font-size: 12px; }}
.card .value {{ font-size: 26px; font-weight: 650; margin-top: 4px; font-variant-numeric: tabular-nums; }}
.card .hint {{ font-size: 12px; color: var(--muted); margin-top: 4px; }}
.section {{
  background: var(--panel); border: 1px solid var(--line); border-radius: 14px;
  padding: 18px 18px 8px; margin-top: 22px;
}}
.section-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: baseline; margin-bottom: 12px; }}
.section-head p {{ margin: 0; color: var(--muted); font-size: 13px; }}
.toolbar {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 12px; }}
input[type=search], select, input[type=number] {{
  font: inherit; border: 1px solid var(--line); background: #fff; border-radius: 8px;
  padding: 7px 10px;
}}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ padding: 9px 10px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; font-size: 13px; }}
th {{ color: var(--muted); font-weight: 650; background: #faf6f0; position: sticky; top: 48px; }}
td.num {{ font-variant-numeric: tabular-nums; white-space: nowrap; }}
.badge {{
  display: inline-block; padding: 1px 8px; border-radius: 999px; font-size: 12px; font-weight: 650;
}}
.badge.ok {{ background: var(--ok-bg); color: var(--ok); }}
.badge.bad {{ background: var(--bad-bg); color: var(--bad); }}
.badge.warn {{ background: var(--warn-bg); color: var(--warn); }}
.badge.muted {{ background: #f5f5f4; color: var(--muted); }}
.badge.fact {{ background: #dcfce7; color: #166534; }}
.badge.bill {{ background: #ffedd5; color: #9a3412; }}
.badge.model {{ background: #e0e7ff; color: #3730a3; }}
details.page {{
  border: 1px solid var(--line); border-radius: 10px; margin-bottom: 10px; background: #fffdf9;
}}
details.page > summary {{
  list-style: none; cursor: pointer; padding: 12px 14px; display: flex; justify-content: space-between;
  gap: 12px; align-items: center; font-weight: 650;
}}
details.page > summary::-webkit-details-marker {{ display: none; }}
details.page[open] > summary {{ border-bottom: 1px solid var(--line); }}
.meta {{ color: var(--muted); font-size: 12px; font-weight: 500; }}
.field-name {{ font-weight: 600; }}
.origin {{ font-size: 12px; color: var(--muted); }}
.actions {{ display: flex; gap: 8px; flex-wrap: wrap; margin: 10px 0 16px; }}
button {{
  font: inherit; border: 1px solid var(--line); background: #fff; border-radius: 8px;
  padding: 7px 12px; cursor: pointer;
}}
button.primary {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
.note {{ font-size: 12px; color: var(--muted); margin: 8px 0 16px; }}
</style>
</head>
<body>
<div class="wrap">
  <nav class="toc">
    <a href="#top">总览</a>
    <a href="#m1">执行率</a>
    <a href="#m2">切局</a>
    <a href="#m3">事实数据</a>
    <a href="#m5">模型结论</a>
    <a href="#m6">耗时并发</a>
  </nav>
  <h1 id="top">每周质量看板</h1>
  <p class="sub">测试执行率只拆到五个模块。事实数据按页面展开到字段，覆盖率和准确率同一行两列。模型结论一层写成 页面/字段。P12 单手逐节点复盘本阶段适用，计入覆盖率分母。标记保存在本机浏览器，可导出。</p>
  <div class="cards" id="kpis"></div>

  <section class="section" id="m1">
    <div class="section-head">
      <h2>M1 测试执行率</h2>
      <p>已执行 / 范围内用例。不展开到每条用例。</p>
    </div>
    <div class="table-scroll">
      <table>
        <thead><tr><th>模块</th><th>总数</th><th>已执行</th><th>通过</th><th>失败</th><th>跳过</th><th>未完成</th><th>执行率</th><th>通过率</th></tr></thead>
        <tbody id="m1-body"></tbody>
      </table>
    </div>
    <p class="note">建议：P0 过程 ≥80%，范围内发版 100%。切局模块的用例通过率不是 M2 切局准确率。</p>
  </section>

  <section class="section" id="m2">
    <div class="section-head">
      <h2>M2 切局准确率</h2>
      <p>一层：准备的测试集。三条同时满足才算对。目标 ≥95%。</p>
    </div>
    <div class="table-scroll">
      <table>
        <thead><tr><th>用例</th><th>场景</th><th>用例状态</th><th>手数相等</th><th>每段能播</th><th>起止在两手之间</th><th>判定</th></tr></thead>
        <tbody id="m2-body"></tbody>
      </table>
    </div>
  </section>

  <section class="section" id="m3">
    <div class="section-head">
      <h2>M3 / M4 事实数据</h2>
      <p>按页面展开字段。覆盖：已实现 / 未实现。准确：对 / 错 / 未核 / 无真值。未实现不记错。非牌局字段只覆盖。</p>
    </div>
    <div class="toolbar">
      <input type="search" id="fact-q" placeholder="搜索字段或页面"/>
      <select id="fact-kind">
        <option value="">全部归类</option>
        <option value="事实">事实（进准确率）</option>
        <option value="非牌局事实">非牌局事实（只覆盖）</option>
      </select>
      <select id="fact-mark">
        <option value="">全部标记</option>
        <option value="unmarked">未标覆盖</option>
        <option value="done">已实现</option>
        <option value="todo">未实现</option>
      </select>
    </div>
    <div id="m3-pages"></div>
  </section>

  <section class="section" id="m5">
    <div class="section-head">
      <h2>M5 模型结论覆盖率</h2>
      <p>一层列完，写成 页面/字段。无准确率。目标：过程 ≥90%，适用字段发版 100%。</p>
    </div>
    <div class="table-scroll">
      <table>
        <thead><tr><th>页面/字段</th><th>覆盖</th><th>来源</th></tr></thead>
        <tbody id="m5-body"></tbody>
      </table>
    </div>
  </section>

  <section class="section" id="m6">
    <div class="section-head">
      <h2>M6–M9 耗时与并发</h2>
      <p>各只挂一个值。耗时来自线上「停止录屏 → 报告可打开」。</p>
    </div>
    <div class="cards" id="m6-cards"></div>
  </section>

  <div class="actions">
    <button class="primary" id="btn-export">导出本周标记 JSON</button>
    <button id="btn-clear">清空本机标记</button>
  </div>
  <p class="note">来源：App 用例表 2026-09-03；字段来自 PRD 页面元素/数据规则 + 123 个复盘指标字典。前期测试集可换。</p>
</div>
<script id="board-data" type="application/json">{data}</script>
<script>
const DATA = JSON.parse(document.getElementById("board-data").textContent);
const KEY = "quality-board-marks-v1";

function loadMarks() {{
  try {{ return JSON.parse(localStorage.getItem(KEY) || "{{}}"); }} catch {{ return {{}}; }}
}}
function saveMarks(m) {{ localStorage.setItem(KEY, JSON.stringify(m)); }}
let marks = loadMarks();

function pct(n, d) {{
  if (!d) return "—";
  return (100 * n / d).toFixed(1) + "%";
}}
function badge(text, cls) {{
  return `<span class="badge ${{cls}}">${{text}}</span>`;
}}
function sel(id, value, options) {{
  return `<select data-id="${{id}}" data-k="${{options.k}}">${{options.opts.map(o =>
    `<option value="${{o.v}}" ${{value===o.v?"selected":""}}>${{o.t}}</option>`
  ).join("")}}</select>`;
}}

function sliceVerdict(id) {{
  const a = marks["s:"+id+":hands"];
  const b = marks["s:"+id+":play"];
  const c = marks["s:"+id+":gap"];
  if (!a || !b || !c) return ["待打分", "muted"];
  if (a==="是" && b==="是" && c==="是") return ["对", "ok"];
  return ["错", "bad"];
}}

function kpis() {{
  const m1 = DATA.m1;
  const slices = DATA.slices;
  let sDone=0,sOk=0;
  slices.forEach(s => {{
    const [v] = sliceVerdict(s.id);
    if (v !== "待打分") sDone++;
    if (v === "对") sOk++;
  }});
  const facts = [...DATA.facts, ...DATA.bills];
  let covD=0, covN=0, accD=0, accN=0;
  facts.forEach(f => {{
    const cov = marks["c:"+f.id] || "";
    if (cov) {{ covD++; if (cov==="已实现") covN++; }}
    if (f.accuracy) {{
      const acc = marks["a:"+f.id] || "";
      if (acc && acc !== "未核") {{ accD++; if (acc==="对") accN++; }}
    }}
  }});
  let m5d=0, m5n=0;
  DATA.models.forEach(f => {{
    const cov = marks["c:"+f.id] || "";
    if (cov) {{ m5d++; if (cov==="已实现") m5n++; }}
  }});
  const nums = {{
    m6: marks.m6 || "",
    m7: marks.m7 || "",
    m8: marks.m8 || "",
    m9: marks.m9 || "",
  }};
  document.getElementById("kpis").innerHTML = [
    ["M1 执行率", pct(m1.done, m1.n), `${{m1.done}}/${{m1.n}} · 目标范围内 100%`],
    ["M2 切局准确率", sDone ? pct(sOk, slices.length) : "待打分", `${{sOk}}/${{slices.length}} 三条件全过 · 目标 ≥95%`],
    ["M3 事实覆盖率", covD ? pct(covN, covD) : "待标", `${{covN}} 已实现 / 已标 ${{covD}} · 分母 ${{facts.length}}`],
    ["M4 事实准确率", accD ? pct(accN, accD) : "待核", `只核已实现且有真值 · 目标 ≥95%`],
    ["M5 模型覆盖率", m5d ? pct(m5n, m5d) : "待标", `${{DATA.models.length}} 个字段 · 目标 ≥90%`],
    ["M6 耗时均值", nums.m6 ? nums.m6 + " 分" : "待填", "停止录屏 → 报告可打开 · ≤5 分"],
    ["M7 耗时 P95", nums.m7 ? nums.m7 + " 分" : "待填", "同上 · ≤12 分"],
    ["M8 同时录屏", nums.m8 || "待填", "先手工 · 占位 ≥5"],
    ["M9 同时解析", nums.m9 || "待填", "先手工 · 占位 ≥5"],
  ].map(([l,v,h]) => `<div class="card"><div class="label">${{l}}</div><div class="value">${{v}}</div><div class="hint">${{h}}</div></div>`).join("");
}}

function renderM1() {{
  document.getElementById("m1-body").innerHTML = DATA.m1.modules.map(s => {{
    const exec = s.exec_rate == null ? "—" : pct(s.done, s.n);
    const pr = s.pass_rate == null ? "—" : (100*s.pass_rate).toFixed(1)+"%";
    return `<tr>
      <td>${{s.module}}</td><td class="num">${{s.n}}</td><td class="num">${{s.done}}</td>
      <td class="num">${{s.pass}}</td><td class="num">${{s.fail}}</td><td class="num">${{s.skip}}</td>
      <td class="num">${{s.todo}}</td><td class="num">${{exec}}</td><td class="num">${{pr}}</td>
    </tr>`;
  }}).join("");
}}

const yn = [{{v:"", t:"—"}}, {{v:"是", t:"是"}}, {{v:"否", t:"否"}}];
function renderM2() {{
  document.getElementById("m2-body").innerHTML = DATA.slices.map(s => {{
    const [v, cls] = sliceVerdict(s.id);
    const st = s.status === "通过" ? "ok" : s.status === "失败" ? "bad" : "muted";
    return `<tr>
      <td><div class="field-name">${{s.id}}</div><div class="origin">${{s.title}}</div></td>
      <td>${{s.func}}</td>
      <td>${{badge(s.status, st)}}</td>
      <td>${{sel("s:"+s.id+":hands", marks["s:"+s.id+":hands"]||"", {{k:"slice", opts: yn}})}}</td>
      <td>${{sel("s:"+s.id+":play", marks["s:"+s.id+":play"]||"", {{k:"slice", opts: yn}})}}</td>
      <td>${{sel("s:"+s.id+":gap", marks["s:"+s.id+":gap"]||"", {{k:"slice", opts: yn}})}}</td>
      <td>${{badge(v, cls)}}</td>
    </tr>`;
  }}).join("");
}}

function factMatch(f, q, kind, mark) {{
  if (kind && f.kind !== kind) return false;
  const cov = marks["c:"+f.id] || "";
  if (mark === "unmarked" && cov) return false;
  if (mark === "done" && cov !== "已实现") return false;
  if (mark === "todo" && cov !== "未实现") return false;
  if (!q) return true;
  const hay = (f.page_id + f.page_name + f.field).toLowerCase();
  return hay.includes(q.toLowerCase());
}}

function renderM3() {{
  const q = document.getElementById("fact-q").value;
  const kind = document.getElementById("fact-kind").value;
  const mark = document.getElementById("fact-mark").value;
  const rows = [...DATA.facts, ...DATA.bills].filter(f => factMatch(f, q, kind, mark));
  const by = {{}};
  rows.forEach(f => {{
    const k = f.page_id;
    if (!by[k]) by[k] = {{ name: f.page_name, items: [] }};
    by[k].items.push(f);
  }});
  const covOpts = [{{v:"", t:"未标"}}, {{v:"已实现", t:"已实现"}}, {{v:"未实现", t:"未实现"}}];
  const accOpts = [{{v:"", t:"未核"}}, {{v:"对", t:"对"}}, {{v:"错", t:"错"}}, {{v:"样本无真值", t:"无真值"}}];
  document.getElementById("m3-pages").innerHTML = Object.keys(by).sort().map(pid => {{
    const g = by[pid];
    const body = g.items.map(f => {{
      const kindB = f.kind === "事实" ? "fact" : "bill";
      const acc = f.accuracy
        ? sel("a:"+f.id, marks["a:"+f.id]||"", {{k:"acc", opts: accOpts}})
        : `<span class="meta">不核</span>`;
      return `<tr>
        <td><div class="field-name">${{f.field}}</div><div class="origin">${{f.origin}}</div></td>
        <td>${{badge(f.kind, kindB)}}</td>
        <td>${{sel("c:"+f.id, marks["c:"+f.id]||"", {{k:"cov", opts: covOpts}})}}</td>
        <td>${{acc}}</td>
      </tr>`;
    }}).join("");
    return `<details class="page" open>
      <summary><span>${{pid}} ${{g.name}}</span><span class="meta">${{g.items.length}} 个字段</span></summary>
      <table>
        <thead><tr><th>字段</th><th>归类</th><th>覆盖</th><th>准确</th></tr></thead>
        <tbody>${{body}}</tbody>
      </table>
    </details>`;
  }}).join("") || `<p class="note">没有匹配的字段。</p>`;
}}

function renderM5() {{
  const covOpts = [{{v:"", t:"未标"}}, {{v:"已实现", t:"已实现"}}, {{v:"未实现", t:"未实现"}}];
  document.getElementById("m5-body").innerHTML = DATA.models.map(f => `<tr>
    <td><div class="field-name">${{f.page_id}} ${{f.page_name}} / ${{f.field}}</div></td>
    <td>${{sel("c:"+f.id, marks["c:"+f.id]||"", {{k:"cov", opts: covOpts}})}}</td>
    <td class="origin">${{f.origin}}</td>
  </tr>`).join("");
}}

function renderM6() {{
  const items = [
    ["m6", "M6 报告耗时 · 均值", "分钟", "≤5"],
    ["m7", "M7 报告耗时 · P95", "分钟", "≤12"],
    ["m8", "M8 同时录屏任务数", "个", "占位 ≥5"],
    ["m9", "M9 同时解析/出报告", "个", "占位 ≥5"],
  ];
  document.getElementById("m6-cards").innerHTML = items.map(([id, label, unit, target]) =>
    `<div class="card"><div class="label">${{label}}</div>
     <div style="margin-top:8px;display:flex;gap:8px;align-items:center">
       <input type="number" min="0" step="0.1" data-num="${{id}}" value="${{marks[id]||""}}" style="width:120px"/>
       <span class="meta">${{unit}} · 目标 ${{target}}</span>
     </div></div>`
  ).join("");
}}

function bind() {{
  document.body.addEventListener("change", e => {{
    const t = e.target;
    if (t.dataset.id) {{
      marks[t.dataset.id] = t.value;
      saveMarks(marks);
      if (t.dataset.id.startsWith("s:")) renderM2();
      kpis();
    }}
    if (t.dataset.num) {{
      marks[t.dataset.num] = t.value;
      saveMarks(marks);
      kpis();
    }}
  }});
  ["fact-q","fact-kind","fact-mark"].forEach(id =>
    document.getElementById(id).addEventListener("input", renderM3)
  );
  document.getElementById("fact-kind").addEventListener("change", renderM3);
  document.getElementById("fact-mark").addEventListener("change", renderM3);
  document.getElementById("btn-export").onclick = () => {{
    const blob = new Blob([JSON.stringify({{exportedAt: new Date().toISOString(), marks}}, null, 2)], {{type:"application/json"}});
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "质量看板标记.json";
    a.click();
  }};
  document.getElementById("btn-clear").onclick = () => {{
    if (!confirm("清空本机全部标记？")) return;
    marks = {{}};
    saveMarks(marks);
    renderAll();
  }};
}}

function renderAll() {{
  kpis(); renderM1(); renderM2(); renderM3(); renderM5(); renderM6();
}}
bind();
renderAll();
</script>
</body>
</html>
"""
    dest.write_text(html, encoding="utf-8")


def write_fact_and_model(wb, prd_fields, metrics):
    fact_rows = []
    model_rows = []
    bill_rows = []
    na_rows = []

    for f in prd_fields:
        kind = classify_prd_field(f["page_id"], f["field"], f["gen"], f.get("loc") or "")
        row = {
            "page_id": f["page_id"],
            "page_name": f["page_name"],
            "field": f["field"],
            "kind": kind,
            "origin": f"页面|{f['source']}",
            "note": f["gen"],
            "accuracy": "否" if kind != "事实" else "是",
        }
        if kind == "模型":
            model_rows.append(row)
        elif kind == "非牌局事实":
            bill_rows.append(row)
        elif kind == "不适用":
            na_rows.append(row)
        else:
            fact_rows.append(row)

    for m in metrics:
        kind = classify_metric(m)
        pid, pname = module_page_for_report(m["modules"])
        row = {
            "page_id": pid,
            "page_name": pname,
            "field": f"{m['name']}（{m['code']}）",
            "kind": kind,
            "origin": f"指标字典|{m['calc_type']} {m['calc_type_name']}|{m['json_path']}|可见:{m['visible']}",
            "note": m["modules"],
            "accuracy": "是" if kind == "事实" else "否",
        }
        if kind == "模型":
            model_rows.append(row)
        else:
            fact_rows.append(row)

    def sort_key(r):
        return (r["page_id"], r["field"])

    fact_rows.sort(key=sort_key)
    model_rows.sort(key=sort_key)
    bill_rows.sort(key=sort_key)

    ws = wb.create_sheet("03_事实数据字段")
    ws["A1"] = "M3 覆盖率 + M4 准确率 · 同一张表两列 · 第一层页面，第二层该页字段"
    ws["A1"].font = TITLE_FONT
    ws.merge_cells("A1:J1")
    ws["A2"] = (
        "覆盖列填：已实现 / 未实现 / 不适用。准确列填：对 / 错 / 未核 / 样本无真值。"
        "未实现不记准确率的错。仅「进准确率=是」的字段用 32 手黄金集 + e2e 核对。"
        "下半部分是 Credits/会员/订单等非牌局事实，只做覆盖、不算准确率。"
    )
    ws["A2"].alignment = WRAP
    ws.merge_cells("A2:J2")
    ws.row_dimensions[2].height = 40

    h = ["页面", "页面名", "字段", "归类", "覆盖(已实现/未实现/不适用)", "准确(对/错/未核/样本无真值)", "进准确率", "来源", "备注", "页面小计用"]
    for i, x in enumerate(h, 1):
        ws.cell(4, i, x)
    style_header(ws, 4, 10)
    dv_c = DataValidation(type="list", formula1='"已实现,未实现,不适用"', allow_blank=True)
    dv_a = DataValidation(type="list", formula1='"对,错,未核,样本无真值"', allow_blank=True)
    ws.add_data_validation(dv_c)
    ws.add_data_validation(dv_a)

    r = 5
    all_factish = fact_rows + bill_rows
    all_factish.sort(key=sort_key)
    for row in all_factish:
        vals = [
            row["page_id"],
            row["page_name"],
            row["field"],
            row["kind"],
            "",
            "",
            row["accuracy"],
            row["origin"],
            row["note"],
            f"{row['page_id']}|{row['page_name']}",
        ]
        for i, v in enumerate(vals, 1):
            ws.cell(r, i, v)
        apply_border_wrap(ws, r, 10)
        if row["kind"] == "事实":
            ws.cell(r, 4).fill = FACT_FILL
        else:
            ws.cell(r, 4).fill = BILL_FILL
        dv_c.add(ws.cell(r, 5))
        if row["accuracy"] == "是":
            dv_a.add(ws.cell(r, 6))
        r += 1
    last = r - 1
    ws.cell(last + 2, 1, "M3 覆盖率（已实现/非空覆盖列）")
    ws.cell(last + 2, 2, f'=IF(COUNTA(E5:E{last})=0,"待标",COUNTIF(E5:E{last},"已实现")/(COUNTA(E5:E{last})-COUNTIF(E5:E{last},"不适用")))')
    ws.cell(last + 3, 1, "M4 准确率（对/已填准确且进准确率=是）")
    ws.cell(last + 3, 2, f'=IF(COUNTIFS(G5:G{last},"是",F5:F{last},"<>")=0,"待核",COUNTIFS(G5:G{last},"是",F5:F{last},"对")/COUNTIFS(G5:G{last},"是",F5:F{last},"<>"))')
    ws.cell(last + 2, 2).number_format = "0.0%"
    ws.cell(last + 3, 2).number_format = "0.0%"
    autosize(ws, {1: 10, 2: 20, 3: 42, 4: 14, 5: 28, 6: 32, 7: 12, 8: 40, 9: 28, 10: 8})
    ws.freeze_panes = "A5"
    ws.auto_filter.ref = f"A4:J{last}"
    ws.column_dimensions["J"].hidden = True

    ws3 = wb.create_sheet("03b_事实_按页面汇总")
    ws3["A1"] = "事实数据第一层 · 按页面汇总（字段条数；覆盖/准确待你在 03 表标注后回看）"
    ws3["A1"].font = TITLE_FONT
    hh = ["页面", "页面名", "事实字段数", "非牌局事实字段数"]
    for i, x in enumerate(hh, 1):
        ws3.cell(3, i, x)
    style_header(ws3, 3, 4)
    by_page = defaultdict(lambda: {"name": "", "fact": 0, "bill": 0})
    for row in all_factish:
        by_page[row["page_id"]]["name"] = row["page_name"]
        if row["kind"] == "事实":
            by_page[row["page_id"]]["fact"] += 1
        else:
            by_page[row["page_id"]]["bill"] += 1
    rr = 4
    for pid in sorted(by_page):
        ws3.cell(rr, 1, pid)
        ws3.cell(rr, 2, by_page[pid]["name"])
        ws3.cell(rr, 3, by_page[pid]["fact"])
        ws3.cell(rr, 4, by_page[pid]["bill"])
        apply_border_wrap(ws3, rr, 4)
        rr += 1
    autosize(ws3, {1: 10, 2: 24, 3: 16, 4: 20})

    ws4 = wb.create_sheet("04_模型结论字段")
    ws4["A1"] = "M5 模型结论覆盖率 · 一层列完，写成 页面/字段（无准确率）"
    ws4["A1"].font = TITLE_FONT
    ws4.merge_cells("A1:G1")
    ws4["A2"] = "覆盖列填：已实现 / 未实现 / 不适用。看板只盯覆盖率。"
    h4 = ["页面/字段", "页面", "页面名", "字段", "覆盖(已实现/未实现/不适用)", "来源", "备注"]
    for i, x in enumerate(h4, 1):
        ws4.cell(4, i, x)
    style_header(ws4, 4, 7)
    dv4 = DataValidation(type="list", formula1='"已实现,未实现,不适用"', allow_blank=True)
    ws4.add_data_validation(dv4)
    r = 5
    for row in model_rows:
        label = f"{row['page_id']} {row['page_name']} / {row['field']}"
        vals = [label, row["page_id"], row["page_name"], row["field"], "", row["origin"], row["note"]]
        for i, v in enumerate(vals, 1):
            ws4.cell(r, i, v)
        apply_border_wrap(ws4, r, 7)
        ws4.cell(r, 1).fill = MODEL_FILL
        dv4.add(ws4.cell(r, 5))
        r += 1
    last4 = r - 1
    ws4.cell(last4 + 2, 1, "M5 覆盖率")
    ws4.cell(last4 + 2, 2, f'=IF(COUNTA(E5:E{last4})=0,"待标",COUNTIF(E5:E{last4},"已实现")/(COUNTA(E5:E{last4})-COUNTIF(E5:E{last4},"不适用")))')
    ws4.cell(last4 + 2, 2).number_format = "0.0%"
    autosize(ws4, {1: 56, 2: 10, 3: 20, 4: 42, 5: 28, 6: 40, 7: 24})
    ws4.freeze_panes = "A5"
    ws4.auto_filter.ref = f"A4:G{last4}"

    return fact_rows, model_rows, bill_rows, na_rows, by_page


def write_latency(wb):
    ws = wb.create_sheet("05_耗时与并发")
    ws["A1"] = "M6/M7 耗时只挂两个值；M8/M9 并发只挂两个值"
    ws["A1"].font = TITLE_FONT
    ws["A2"] = "耗时：每周统计线上真实「停止录屏 → 报告可打开」。并发：先手工填当前支持上限，后期性能测试替换。"
    headers = ["编号", "指标", "本周值", "单位", "建议目标", "数据来源"]
    for i, h in enumerate(headers, 1):
        ws.cell(4, i, h)
    style_header(ws, 4, 6)
    rows = [
        ("M6", "报告产出耗时 · 均值", "", "分钟", "≤5（一周后校准）", "线上真实任务"),
        ("M7", "报告产出耗时 · P95", "", "分钟", "≤12（一周后校准）", "线上真实任务"),
        ("M8", "同时录屏任务数", "", "个", "先填现状；占位≥5", "手工 → 性能测试"),
        ("M9", "同时解析/出报告任务数", "", "个", "先填现状；占位≥5", "手工 → 性能测试"),
    ]
    for i, row in enumerate(rows, 5):
        for c, v in enumerate(row, 1):
            ws.cell(i, c, v)
        apply_border_wrap(ws, i, 6)
    autosize(ws, {1: 10, 2: 32, 3: 14, 4: 10, 5: 28, 6: 24})


def main() -> None:
    cases = load_cases()
    stats = module_stats(cases)
    prd_fields = load_prd_fields()
    metrics = unique_metrics()
    fact_rows, model_rows, bill_rows, by_page = collect_field_rows(prd_fields, metrics)
    slices = [c for c in cases if c["module"] == "切局模块测试"]

    payload = {
        "generated_at": "2026-09-03",
        "m1": {
            "n": sum(s["n"] for s in stats),
            "done": sum(s["done"] for s in stats),
            "pass": sum(s["pass"] for s in stats),
            "fail": sum(s["fail"] for s in stats),
            "modules": stats,
        },
        "slices": [
            {
                "id": c["id"],
                "title": c["title"],
                "func": c["func"],
                "status": c["status"],
                "prio": c["prio"],
            }
            for c in slices
        ],
        "facts": fact_rows,
        "bills": bill_rows,
        "models": model_rows,
        "pages": [
            {"id": pid, "name": v["name"], "fact": v["fact"], "bill": v["bill"], "model": v["model"]}
            for pid, v in sorted(by_page.items())
        ],
    }
    SNAP.parent.mkdir(parents=True, exist_ok=True)
    SNAP.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    html_out = ROOT / "output/quality-board.html"
    html_dl = Path("/Users/xixi/Downloads/质量看板.html")
    write_html(payload, html_out)
    html_dl.write_text(html_out.read_text(encoding="utf-8"), encoding="utf-8")
    print("wrote", html_out)
    print("wrote", html_dl)
    p12 = [r for r in fact_rows + model_rows + bill_rows if r["page_id"] == "P12"]
    print(
        "cases",
        len(cases),
        "fact",
        len(fact_rows),
        "model",
        len(model_rows),
        "bill",
        len(bill_rows),
        "p12",
        len(p12),
    )


if __name__ == "__main__":
    main()
