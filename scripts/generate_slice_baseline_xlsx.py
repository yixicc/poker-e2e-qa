#!/usr/bin/env python3
"""生成「切局/切片测试基线指标」汇报用 Excel。

默认写出 2026-10-22 内网切片测试基线；之后上线可复制「上线填写模板」sheet 填新版本。
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

OUT_DEFAULT = Path.home() / "Downloads" / "切局测试基线指标_20261022.xlsx"

# —— 样式 ——
THIN = Border(
    left=Side(style="thin", color="D0D5DD"),
    right=Side(style="thin", color="D0D5DD"),
    top=Side(style="thin", color="D0D5DD"),
    bottom=Side(style="thin", color="D0D5DD"),
)
FILL_HEADER = PatternFill("solid", fgColor="1F4E79")
FILL_TITLE = PatternFill("solid", fgColor="0F2942")
FILL_SECTION = PatternFill("solid", fgColor="D6E3F0")
FILL_PASS = PatternFill("solid", fgColor="C6EFCE")
FILL_WARN = PatternFill("solid", fgColor="FFEB9C")
FILL_FAIL = PatternFill("solid", fgColor="FFC7CE")
FILL_INPUT = PatternFill("solid", fgColor="FFF2CC")
FILL_MUTED = PatternFill("solid", fgColor="F2F4F7")
FONT_HEADER = Font(name="PingFang SC", bold=True, color="FFFFFF", size=11)
FONT_TITLE = Font(name="PingFang SC", bold=True, color="FFFFFF", size=14)
FONT_SECTION = Font(name="PingFang SC", bold=True, size=11, color="1F4E79")
FONT_BODY = Font(name="PingFang SC", size=10)
FONT_BOLD = Font(name="PingFang SC", bold=True, size=10)


def _set_col_widths(ws, widths: dict[int, float]) -> None:
    for idx, w in widths.items():
        ws.column_dimensions[get_column_letter(idx)].width = w


def _style_header_row(ws, row: int, cols: int) -> None:
    for c in range(1, cols + 1):
        cell = ws.cell(row, c)
        cell.fill = FILL_HEADER
        cell.font = FONT_HEADER
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = THIN


def _paint_result(cell, value: str | None) -> None:
    if value is None:
        return
    text = str(value)
    cell.font = FONT_BODY
    if text in ("通过", "是", "合格", "可上线", "达标", "✅"):
        cell.fill = FILL_PASS
    elif text in ("有待优化", "有代优化点", "可优化", "带病上线", "⚠️"):
        cell.fill = FILL_WARN
    elif text in ("失败", "否", "阻断", "不合格", "❌"):
        cell.fill = FILL_FAIL


def _write_title(ws, text: str, cols: int) -> None:
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=cols)
    cell = ws.cell(1, 1, text)
    cell.fill = FILL_TITLE
    cell.font = FONT_TITLE
    cell.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 28


def sheet_dashboard(wb: Workbook) -> None:
    ws = wb.active
    ws.title = "00_汇总看板"
    cols = 6
    _write_title(ws, "切局/切片测试基线指标 · 汇总看板（汇报用）", cols)
    _set_col_widths(ws, {1: 18, 2: 22, 3: 14, 4: 14, 5: 14, 6: 42})

    meta = [
        ("基线日期", "2026-10-22"),
        ("环境", "内网测试"),
        ("数据来源", "内网测试环境切片_10月22日.xlsx"),
        ("版本/构建号", "（填本次上线版本）"),
        ("结论", "可作为上线基线；入坐结尾冻结记已知待优化，不阻断"),
        ("门槛判定", "P1 带病可上线（硬失败=0，主样本完整率100%）"),
    ]
    ws.cell(3, 1, "本场元信息").font = FONT_SECTION
    ws.cell(3, 1).fill = FILL_SECTION
    ws.merge_cells("A3:B3")
    for i, (k, v) in enumerate(meta, start=4):
        ws.cell(i, 1, k).font = FONT_BOLD
        ws.cell(i, 1).fill = FILL_MUTED
        ws.cell(i, 1).border = THIN
        c = ws.cell(i, 2, v)
        c.font = FONT_BODY
        c.border = THIN
        if k == "结论":
            c.fill = FILL_WARN

    # 核心 KPI
    r = 11
    ws.cell(r, 1, "核心 KPI（每次上线必报）").font = FONT_SECTION
    ws.cell(r, 1).fill = FILL_SECTION
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=cols)
    headers = ["指标", "口径", "建议门槛", "10/22基线", "本次实测", "备注"]
    r = 12
    for i, h in enumerate(headers, 1):
        ws.cell(r, i, h)
    _style_header_row(ws, r, cols)

    kpis = [
        ("场景覆盖数", "必测场景已跑完数 / 6", "6/6", "6/6", "", "场景类型固定，session 可换"),
        ("场景通过率", "结果=通过 的场景 / 总场景", "≥83%（争取100%）", "5/6 = 83%", "", "「有待优化」不算硬失败"),
        ("硬阻断失败数", "切错/漏切导致不可用", "0", "0", "", "P0：>0 不可上线"),
        ("可优化项数", "通过但有已知瑕疵", "记录即可", "2", "", "32手漏1秒；入坐结尾冻结"),
        ("切手完整率", "切片完整手数 / 真值手数G", "≥98%", "100%（48/48）", "", "主样本：连续多手场"),
        ("切片异常率", "切片异常手数 / G", "≤2%", "0%", "", ""),
        ("漏切率", "应切未切 / G", "0（硬门槛）", "0%", "", "P0"),
        ("多切率", "不该切却切出 / G", "尽量0", "0%", "", ""),
        ("开头单独切出", "片头是否单独切出", "100%", "是", "", "主样本"),
        ("结尾单独切出", "片尾是否单独切出", "100%", "是（主样本）", "", "入坐场结尾：否/未识别"),
    ]
    for i, row in enumerate(kpis, start=13):
        for j, v in enumerate(row, 1):
            cell = ws.cell(i, j, v)
            cell.font = FONT_BODY
            cell.border = THIN
            cell.alignment = Alignment(wrap_text=True, vertical="center")
            if j == 5:
                cell.fill = FILL_INPUT
            if j == 4 and row[0] in ("场景通过率", "可优化项数"):
                cell.fill = FILL_WARN
            elif j == 4 and row[0] in (
                "场景覆盖数",
                "硬阻断失败数",
                "切手完整率",
                "切片异常率",
                "漏切率",
                "多切率",
                "开头单独切出",
            ):
                cell.fill = FILL_PASS

    # 对比上版
    r = 24
    ws.cell(r, 1, "与上版对比（上线填）").font = FONT_SECTION
    ws.cell(r, 1).fill = FILL_SECTION
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
    for i, h in enumerate(["对比项", "上版基线", "本次", "Δ / 说明"], 1):
        ws.cell(r + 1, i, h)
    _style_header_row(ws, r + 1, 4)
    for i, name in enumerate(
        ["场景通过率", "切手完整率", "硬失败数", "可优化项", "新增回归"],
        start=r + 2,
    ):
        ws.cell(i, 1, name).font = FONT_BODY
        ws.cell(i, 1).border = THIN
        for j in range(2, 5):
            c = ws.cell(i, j, "")
            c.fill = FILL_INPUT
            c.border = THIN

    r = 31
    ws.cell(r, 1, "上线结论（勾选其一）").font = FONT_SECTION
    ws.cell(r, 1).fill = FILL_SECTION
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)
    conclusions = [
        ("可上线（达标）", "场景6/6全通过 + 完整率100% + 边界全切出"),
        ("带病上线（本基线档）", "硬失败=0，完整率≥98%，有已知可优化"),
        ("阻断", "漏切>0 或完整率<95% 或无关视频误入有效手"),
    ]
    for i, (name, desc) in enumerate(conclusions, start=r + 1):
        ws.cell(i, 1, name).font = FONT_BOLD
        ws.cell(i, 1).border = THIN
        _paint_result(ws.cell(i, 1), "可上线" if "可上线" in name else ("带病上线" if "带病" in name else "阻断"))
        ws.cell(i, 2, desc).font = FONT_BODY
        ws.cell(i, 2).border = THIN
        ws.merge_cells(start_row=i, start_column=2, end_row=i, end_column=3)
        ws.cell(i, 3).border = THIN
    ws.cell(r + 2, 4, "← 10/22 落在此档").font = FONT_BOLD


def sheet_scenarios(wb: Workbook) -> None:
    ws = wb.create_sheet("01_场景矩阵")
    cols = 8
    _write_title(ws, "必测场景矩阵（每次上线固定跑；session 可换，场景类型不变）", cols)
    _set_col_widths(ws, {1: 6, 2: 18, 3: 36, 4: 22, 5: 14, 6: 14, 7: 36, 8: 28})

    headers = [
        "#",
        "场景",
        "验收要点",
        "Session ID（10/22）",
        "切片情况",
        "测试结果",
        "说明 / 瑕疵",
        "本次实测（填）",
    ]
    for i, h in enumerate(headers, 1):
        ws.cell(3, i, h)
    _style_header_row(ws, 3, cols)

    rows = [
        (
            1,
            "连续多手正常局（≥32手）",
            "每手完整；开头/结尾单独切出；无漏切多切",
            "1792483028902",
            "完整",
            "通过",
            "可优化：第48手漏出一秒别的牌（视频原因）",
            "",
        ),
        (
            2,
            "生产真实切片",
            "同连续多手；贴近生产链路",
            "11792479998678",
            "完整",
            "通过",
            "开头/结尾单独切除；4手均完整",
            "",
        ),
        (
            3,
            "入坐无手牌",
            "无底牌段单独切出，不并入下一手；结尾冻结可识别",
            "1792479281617",
            "完整",
            "有待优化",
            "结尾16秒后冻结未识别出",
            "",
        ),
        (
            4,
            "围观/摊牌",
            "异常可标 invalid_hand，不污染正常有效手",
            "1792721277727",
            "围观摊牌两手异常",
            "通过",
            "多手 invalid_hand；结尾未单独切除（记观察项）",
            "",
        ),
        (
            5,
            "与牌局无关视频",
            "整体解析失败 + invalid_hand 标记正确",
            "1792481067832",
            "—",
            "通过",
            "invalid_hand 标记正常，整体解析失败",
            "",
        ),
        (
            6,
            "中间黑屏",
            "黑屏不并成一手有效牌",
            "1792480268460",
            "—",
            "通过",
            "",
            "",
        ),
    ]
    for i, row in enumerate(rows, start=4):
        for j, v in enumerate(row, 1):
            cell = ws.cell(i, j, v)
            cell.font = FONT_BODY
            cell.border = THIN
            cell.alignment = Alignment(wrap_text=True, vertical="center")
            if j == 6:
                _paint_result(cell, str(v))
            if j == 8:
                cell.fill = FILL_INPUT
        ws.row_dimensions[i].height = 36

    ws.cell(11, 1, "统计").font = FONT_SECTION
    ws.cell(11, 1).fill = FILL_SECTION
    ws.merge_cells("A11:C11")
    stats = [
        ("覆盖", "6/6"),
        ("通过", "5"),
        ("有待优化", "1"),
        ("失败", "0"),
        ("通过率", "83%"),
    ]
    for i, (k, v) in enumerate(stats, start=12):
        ws.cell(i, 1, k).font = FONT_BOLD
        ws.cell(i, 1).border = THIN
        c = ws.cell(i, 2, v)
        c.font = FONT_BODY
        c.border = THIN
        _paint_result(c, "通过" if k == "通过" else ("有待优化" if k == "有待优化" else ("失败" if k == "失败" else None)))
        if k == "通过率":
            c.fill = FILL_WARN


def sheet_hand_metrics(wb: Workbook) -> None:
    ws = wb.create_sheet("02_手级口径与门槛")
    cols = 5
    _write_title(ws, "手级指标口径 · 分层门槛（与研发对齐用）", cols)
    _set_col_widths(ws, {1: 16, 2: 48, 3: 18, 4: 18, 5: 36})

    ws.cell(3, 1, "口径定义").font = FONT_SECTION
    ws.cell(3, 1).fill = FILL_SECTION
    ws.merge_cells("A3:E3")

    defs = [
        ("符号", "定义", "计入", "不计入", "备注"),
        (
            "真值手数 G",
            "录像里实际德州手数",
            "一段视频里两局算 2",
            "等待 / 补码弹窗 / 换桌动画",
            "对账分母",
        ),
        (
            "切片完整",
            "一手一段且内容完整（底牌可见时段覆盖该手）",
            "边界清晰、无粘连",
            "漏出邻手画面过久（可记可优化）",
            "主样本逐手标注",
        ),
        (
            "切片异常",
            "粘连、截断、切错边界、一手拆成多段错误等",
            "影响可用性",
            "仅视频源 1 秒级瑕疵且手仍可辨",
            "算异常率分子",
        ),
        (
            "漏切",
            "应单独成手却未切出",
            "少一手",
            "—",
            "硬门槛，必须为 0",
        ),
        (
            "多切",
            "不该成手却切出一段",
            "多一段有效/脏段",
            "合法的开头/结尾单独段",
            "开头结尾单独切出不算多切",
        ),
        (
            "命中",
            "真值手与切片结果一一对应上的手",
            "用于算漏=G−命中、多=S−命中",
            "—",
            "有 pipeline 入库时用",
        ),
    ]
    for i, h in enumerate(defs[0], 1):
        ws.cell(4, i, h)
    _style_header_row(ws, 4, cols)
    for ri, row in enumerate(defs[1:], start=5):
        for j, v in enumerate(row, 1):
            cell = ws.cell(ri, j, v)
            cell.font = FONT_BODY
            cell.border = THIN
            cell.alignment = Alignment(wrap_text=True, vertical="center")
        ws.row_dimensions[ri].height = 40

    ws.cell(12, 1, "分层门槛").font = FONT_SECTION
    ws.cell(12, 1).fill = FILL_SECTION
    ws.merge_cells("A12:E12")
    for i, h in enumerate(["级别", "条件", "动作", "10/22是否命中", "说明"], 1):
        ws.cell(13, i, h)
    _style_header_row(ws, 13, cols)
    gates = [
        (
            "P0 阻断",
            "漏切>0，或正常局完整率<95%，或无关视频误当成有效手",
            "不可上线",
            "否",
            "",
        ),
        (
            "P1 带病",
            "完整率≥98%，硬失败=0，有已知可优化",
            "可上线，进 backlog",
            "是",
            "当前基线档",
        ),
        (
            "P2 达标",
            "场景6/6全通过 + 完整率100% + 边界全切出",
            "健康基线",
            "否",
            "入坐结尾未达标故未到 P2",
        ),
    ]
    for ri, row in enumerate(gates, start=14):
        for j, v in enumerate(row, 1):
            cell = ws.cell(ri, j, v)
            cell.font = FONT_BODY
            cell.border = THIN
            cell.alignment = Alignment(wrap_text=True, vertical="center")
            if j == 1:
                if "P0" in str(v):
                    cell.fill = FILL_FAIL
                elif "P1" in str(v):
                    cell.fill = FILL_WARN
                else:
                    cell.fill = FILL_PASS
            if j == 4:
                _paint_result(cell, "是" if v == "是" else "否")


def sheet_main_sample(wb: Workbook) -> None:
    ws = wb.create_sheet("03_主样本手级明细")
    cols = 5
    _write_title(
        ws,
        "主样本手级明细 · session 1792483028902（32手切片场，实为48手）· 10/22",
        cols,
    )
    _set_col_widths(ws, {1: 14, 2: 14, 3: 14, 4: 36, 5: 56})

    summary = [
        ("真值手数 G", "48"),
        ("切片完整", "48"),
        ("切片异常", "0"),
        ("开头单独切出", "是"),
        ("结尾切出", "是"),
        ("切手完整率", "100%"),
        ("已知可优化", "第48手：漏出一秒别的牌（视频原因）"),
    ]
    ws.cell(3, 1, "汇总").font = FONT_SECTION
    ws.cell(3, 1).fill = FILL_SECTION
    for i, (k, v) in enumerate(summary, start=4):
        ws.cell(i, 1, k).font = FONT_BOLD
        ws.cell(i, 1).border = THIN
        ws.cell(i, 1).fill = FILL_MUTED
        c = ws.cell(i, 2, v)
        c.font = FONT_BODY
        c.border = THIN
        if k == "切手完整率":
            c.fill = FILL_PASS

    ws.cell(12, 1, "逐手标注摘要（完整明细见源表「32手切片情况」）").font = FONT_SECTION
    ws.cell(12, 1).fill = FILL_SECTION
    ws.merge_cells("A12:E12")
    for i, h in enumerate(["分段", "手数", "切片情况", "备注", "视频链路"], 1):
        ws.cell(13, i, h)
    _style_header_row(ws, 13, cols)

    detail = [
        ("开头", "—", "单独切出", "", ""),
        ("第1–47手", "47", "切片完整", "其中第5/6/24/45手重点检查手牌", ""),
        (
            "第48手",
            "1",
            "切片完整",
            "可优化，漏出一秒别的牌",
            "…/1792483028902/51_cv.mp4",
        ),
        ("结尾", "—", "切出", "", ""),
    ]
    for ri, row in enumerate(detail, start=14):
        for j, v in enumerate(row, 1):
            cell = ws.cell(ri, j, v)
            cell.font = FONT_BODY
            cell.border = THIN
            if j == 3:
                _paint_result(cell, "通过" if v in ("切片完整", "单独切出", "切出") else v)
            if "可优化" in str(row[3]) and j == 4:
                cell.fill = FILL_WARN

    # 其他场景速览
    ws.cell(19, 1, "其他场景手级速览（10/22）").font = FONT_SECTION
    ws.cell(19, 1).fill = FILL_SECTION
    ws.merge_cells("A19:E19")
    for i, h in enumerate(["场景", "Session", "手数概况", "关键结果", "瑕疵"], 1):
        ws.cell(20, i, h)
    _style_header_row(ws, 20, cols)
    others = [
        (
            "生产切片",
            "11792479998678",
            "4手 + 开头结尾单独切",
            "4/4 完整",
            "",
        ),
        (
            "入坐无手牌",
            "1792479281617",
            "无牌段单独切 + 4手完整",
            "手级完整；结尾未识别",
            "结尾16s冻结",
        ),
        (
            "围观",
            "1792721277727",
            "5手（含摊牌）",
            "多手 invalid_hand；1手切片异常",
            "结尾未单独切除",
        ),
    ]
    for ri, row in enumerate(others, start=21):
        for j, v in enumerate(row, 1):
            cell = ws.cell(ri, j, v)
            cell.font = FONT_BODY
            cell.border = THIN
            cell.alignment = Alignment(wrap_text=True, vertical="center")
            if j == 5 and v:
                cell.fill = FILL_WARN


def sheet_special(wb: Workbook) -> None:
    ws = wb.create_sheet("04_特殊场景勾选")
    cols = 5
    _write_title(ws, "特殊场景合格判定（布尔勾选 · 每次上线）", cols)
    _set_col_widths(ws, {1: 22, 2: 48, 3: 14, 4: 14, 5: 36})

    for i, h in enumerate(["指标", "合格条件", "10/22", "本次", "备注"], 1):
        ws.cell(3, i, h)
    _style_header_row(ws, 3, cols)

    rows = [
        ("入坐无手牌切分", "「无（入座无手牌）」单独切出，不并入有牌手", "合格", "", ""),
        ("入坐结尾处理", "冻结/无牌尾段识别并切除或明确标记", "不合格", "", "16s后冻结未识别"),
        ("围观 invalid_hand", "围观摊牌标 invalid_hand，不入库为有效手", "合格", "", ""),
        ("无关视频拒绝", "解析失败 + invalid 标记", "合格", "", ""),
        ("黑屏隔离", "黑屏不生成有效手", "合格", "", ""),
        ("开头单独切出（主样本）", "片头等待不并入第1手", "合格", "", ""),
        ("结尾单独切出（主样本）", "片尾不并入最后一手", "合格", "", ""),
    ]
    for ri, row in enumerate(rows, start=4):
        for j, v in enumerate(row, 1):
            cell = ws.cell(ri, j, v)
            cell.font = FONT_BODY
            cell.border = THIN
            cell.alignment = Alignment(wrap_text=True, vertical="center")
            if j == 3:
                _paint_result(cell, "通过" if v == "合格" else "失败")
            if j == 4:
                cell.fill = FILL_INPUT


def sheet_onepager(wb: Workbook) -> None:
    ws = wb.create_sheet("05_上线填写模板")
    cols = 4
    _write_title(ws, "上线一页纸（复制本页或另存为新日期文件后填写）", cols)
    _set_col_widths(ws, {1: 20, 2: 28, 3: 28, 4: 40})

    fields = [
        ("环境", "", "内网 / UAT / 生产", ""),
        ("日期", "", "YYYY-MM-DD", ""),
        ("版本/构建号", "", "", ""),
        ("测试人", "", "", ""),
        ("场景覆盖", "", "_/6", ""),
        ("场景通过率", "", "_%", ""),
        ("硬失败数", "", "目标 0", ""),
        ("可优化项数", "", "", ""),
        ("主样本 Session", "", "", ""),
        ("主样本 G / 完整 / 异常", "", "例：48 / 48 / 0", ""),
        ("切手完整率", "", "_%", ""),
        ("漏切率 / 多切率", "", "_% / _%", ""),
        ("开头单独切出", "", "是/否", ""),
        ("结尾单独切出", "", "是/否", ""),
        ("入坐无牌 / 围观invalid / 无关视频 / 黑屏", "", "各填 合格/不合格", ""),
        ("对比上版完整率 Δ", "", "", ""),
        ("新增回归", "", "", ""),
        ("结论", "", "可上线 / 带病上线 / 阻断", ""),
        ("已知问题清单", "", "编号+一句话", ""),
    ]
    for i, h in enumerate(["字段", "本次填写", "填写提示", "备注"], 1):
        ws.cell(3, i, h)
    _style_header_row(ws, 3, cols)
    for ri, (name, val, hint, note) in enumerate(fields, start=4):
        ws.cell(ri, 1, name).font = FONT_BOLD
        ws.cell(ri, 1).border = THIN
        ws.cell(ri, 1).fill = FILL_MUTED
        c = ws.cell(ri, 2, val)
        c.fill = FILL_INPUT
        c.border = THIN
        ws.cell(ri, 3, hint).font = FONT_BODY
        ws.cell(ri, 3).border = THIN
        ws.cell(ri, 4, note).font = FONT_BODY
        ws.cell(ri, 4).border = THIN

    # 预填一页纸：10/22 示例
    ws.cell(24, 1, "10/22 基线已填示例（只读对照）").font = FONT_SECTION
    ws.cell(24, 1).fill = FILL_SECTION
    ws.merge_cells("A24:D24")
    example = (
        "【切局/切片基线】环境：内网 | 日期：2026-10-22 | 版本：—\n"
        "1. 场景：覆盖 6/6，通过率 83%，硬失败 0，可优化 2\n"
        "2. 主样本切手完整率：100%（G=48，完整=48，异常=0）\n"
        "3. 开头/结尾单独切出：开头 是 / 结尾 是（主样本）\n"
        "4. 特殊场景：入坐无牌合格 | 入坐结尾不合格 | 围观invalid合格 | 无关视频合格 | 黑屏合格\n"
        "5. 对比上版：—（首版基线）\n"
        "6. 结论：带病上线（可作为上线基线）"
    )
    ws.merge_cells("A25:D30")
    cell = ws.cell(25, 1, example)
    cell.alignment = Alignment(wrap_text=True, vertical="top")
    cell.font = FONT_BODY
    cell.border = THIN


def sheet_howto(wb: Workbook) -> None:
    ws = wb.create_sheet("06_使用说明")
    _write_title(ws, "使用说明 · 每次上线怎么用这份表", 3)
    _set_col_widths(ws, {1: 8, 2: 28, 3: 72})
    steps = [
        ("1", "固定跑 6 个场景", "场景类型见「01_场景矩阵」；session 可换，类型不能少。"),
        ("2", "主样本逐手标注", "至少 ≥32 手连续局；逐手标完整/异常/漏切；填 G 与完整率。"),
        ("3", "特殊场景勾选", "在「04_特殊场景勾选」把本次列填完。"),
        ("4", "填一页纸", "「05_上线填写模板」填完后，复制到汇报/飞书。"),
        ("5", "更新看板", "把本次实测写进「00_汇总看板」黄色格，并写与上版对比。"),
        ("6", "定结论", "按 P0/P1/P2 门槛选：可上线 / 带病上线 / 阻断。"),
        ("7", "存档", "另存为 切局测试基线指标_YYYYMMDD.xlsx，与上一版并排归档。"),
    ]
    for i, h in enumerate(["#", "步骤", "说明"], 1):
        ws.cell(3, i, h)
    _style_header_row(ws, 3, 3)
    for ri, row in enumerate(steps, start=4):
        for j, v in enumerate(row, 1):
            cell = ws.cell(ri, j, v)
            cell.font = FONT_BODY
            cell.border = THIN
            cell.alignment = Alignment(wrap_text=True, vertical="center")
        ws.row_dimensions[ri].height = 28

    ws.cell(12, 1, "黄色单元格 = 每次上线填写区；绿/黄/红 = 通过/可优化/失败。").font = FONT_BOLD
    ws.merge_cells("A12:C12")
    ws.cell(13, 1, "重新生成本文件：python3 scripts/generate_slice_baseline_xlsx.py").font = FONT_BODY
    ws.merge_cells("A13:C13")


def build(out: Path) -> Path:
    wb = Workbook()
    sheet_dashboard(wb)
    sheet_scenarios(wb)
    sheet_hand_metrics(wb)
    sheet_main_sample(wb)
    sheet_special(wb)
    sheet_onepager(wb)
    sheet_howto(wb)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return out


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description="生成切局测试基线指标 Excel")
    p.add_argument(
        "-o",
        "--out",
        type=Path,
        default=OUT_DEFAULT,
        help=f"输出路径（默认 {OUT_DEFAULT}）",
    )
    args = p.parse_args()
    path = build(args.out)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
