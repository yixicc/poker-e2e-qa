#!/usr/bin/env python3
"""生成「切局质量核心指标」单表 Excel：一页看板，每版本更新一行。"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

OUT_DEFAULT = Path.home() / "Downloads" / "切局测试基线指标_20261022.xlsx"

THIN = Border(
    left=Side(style="thin", color="D0D5DD"),
    right=Side(style="thin", color="D0D5DD"),
    top=Side(style="thin", color="D0D5DD"),
    bottom=Side(style="thin", color="D0D5DD"),
)
FILL_TITLE = PatternFill("solid", fgColor="0F2942")
FILL_HEADER = PatternFill("solid", fgColor="1F4E79")
FILL_SECTION = PatternFill("solid", fgColor="D6E3F0")
FILL_PASS = PatternFill("solid", fgColor="C6EFCE")
FILL_WARN = PatternFill("solid", fgColor="FFEB9C")
FILL_FAIL = PatternFill("solid", fgColor="FFC7CE")
FILL_INPUT = PatternFill("solid", fgColor="FFF2CC")
FILL_MUTED = PatternFill("solid", fgColor="F2F4F7")
FONT_TITLE = Font(name="PingFang SC", bold=True, color="FFFFFF", size=14)
FONT_HEADER = Font(name="PingFang SC", bold=True, color="FFFFFF", size=10)
FONT_SECTION = Font(name="PingFang SC", bold=True, size=11, color="1F4E79")
FONT_BODY = Font(name="PingFang SC", size=10)
FONT_BOLD = Font(name="PingFang SC", bold=True, size=10)
FONT_HINT = Font(name="PingFang SC", size=9, color="667085")


def _widths(ws, widths: dict[int, float]) -> None:
    for i, w in widths.items():
        ws.column_dimensions[get_column_letter(i)].width = w


def _header(ws, row: int, cols: int) -> None:
    for c in range(1, cols + 1):
        cell = ws.cell(row, c)
        cell.fill = FILL_HEADER
        cell.font = FONT_HEADER
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = THIN


def _cell(ws, r, c, v, *, fill=None, bold=False, wrap=True):
    cell = ws.cell(r, c, v)
    cell.font = FONT_BOLD if bold else FONT_BODY
    cell.border = THIN
    cell.alignment = Alignment(wrap_text=wrap, vertical="center", horizontal="center" if c > 1 else "left")
    if fill is not None:
        cell.fill = fill
    return cell


# 版本记录列：指标在行，版本在列 —— 更适合「每版本更新」
# 用户说「每个版本更新即可」，单 sheet 放核心指标。
# 布局：左侧指标名+口径+门槛，右侧按版本填值（先放 10/22 基线，再留 2 个空版本列）。

METRICS = [
    # (指标名, 口径, 建议门槛, 10/22基线值, 着色)
    ("版本/构建号", "本次上线标识", "—", "2026-10-22 基线", None),
    ("环境", "内网 / UAT / 生产", "—", "内网测试", None),
    ("主样本 Session", "连续多手场 sessionId", "—", "1792483028902", None),
    ("真值手数 G", "录像实际德州手数（扣等待/补码/换桌；一段两局算2）", "≥32", "48", None),
    ("切片完整手数", "一手一段且内容完整", "—", "48", "pass"),
    ("切片异常手数", "粘连/截断/切错边界", "—", "0", "pass"),
    ("切手完整率", "完整手数 / G", "≥98%", "100%", "pass"),
    ("切片异常率", "异常手数 / G", "≤2%", "0%", "pass"),
    ("漏切率", "应切未切 / G", "0（硬门槛）", "0%", "pass"),
    ("多切率", "不该切却切出 / G（开头结尾单独段不算）", "尽量 0", "0%", "pass"),
    ("开头单独切出", "片头是否单独切出、不并入第1手", "是", "是", "pass"),
    ("结尾单独切出", "片尾是否单独切出、不并入最后一手", "是", "是（主样本）", "pass"),
    ("场景覆盖", "必测6场景是否跑完", "6/6", "6/6", "pass"),
    ("场景通过率", "通过场景数 / 6（有待优化不算硬失败）", "≥83%，争取100%", "83%（5/6）", "warn"),
    ("硬失败数", "漏切或切错导致不可用", "0", "0", "pass"),
    ("可优化项数", "通过但有已知瑕疵", "记录", "2", "warn"),
    ("入坐无手牌切分", "无底牌段单独切出", "合格", "合格", "pass"),
    ("入坐结尾处理", "冻结/无牌尾段可识别或标记", "合格", "不合格", "fail"),
    ("围观 invalid_hand", "围观摊牌标 invalid，不入库有效手", "合格", "合格", "pass"),
    ("无关视频拒绝", "解析失败 + invalid 标记", "合格", "合格", "pass"),
    ("黑屏隔离", "黑屏不生成有效手", "合格", "合格", "pass"),
    ("上线结论", "可上线 / 带病上线 / 阻断", "—", "带病上线", "warn"),
    ("主要问题", "一句话", "—", "入坐结尾冻结未识别；第48手漏1秒邻牌（视频）", None),
]

COLOR = {
    "pass": FILL_PASS,
    "warn": FILL_WARN,
    "fail": FILL_FAIL,
}


def build(out: Path) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "切局质量指标"
    ws.freeze_panes = "D4"  # 冻住指标名/口径/门槛，版本列可横滚

    # 标题
    ws.merge_cells("A1:G1")
    title = ws.cell(1, 1, "切局质量核心指标（每版本更新一列）")
    title.fill = FILL_TITLE
    title.font = FONT_TITLE
    title.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 28

    ws.merge_cells("A2:G2")
    hint = ws.cell(
        2,
        1,
        "用法：黄色列为待填版本；复制整列到右侧即可开新版本。P0阻断=漏切>0或完整率<95%或无关视频误入有效手；P1带病=硬失败0且完整率≥98%；P2达标=6场景全通过+完整率100%+边界全切出。",
    )
    hint.font = FONT_HINT
    hint.alignment = Alignment(wrap_text=True, vertical="center")
    ws.row_dimensions[2].height = 36

    # 表头：指标 | 口径 | 门槛 | 版本列…
    headers = ["指标", "口径", "建议门槛", "v20261022（基线）", "v________", "v________", "备注"]
    for i, h in enumerate(headers, 1):
        ws.cell(3, i, h)
    _header(ws, 3, len(headers))
    ws.row_dimensions[3].height = 24

    for i, (name, caliber, gate, baseline, tone) in enumerate(METRICS, start=4):
        _cell(ws, i, 1, name, bold=True, fill=FILL_MUTED)
        ws.cell(i, 1).alignment = Alignment(wrap_text=True, vertical="center", horizontal="left")
        _cell(ws, i, 2, caliber)
        ws.cell(i, 2).alignment = Alignment(wrap_text=True, vertical="center", horizontal="left")
        _cell(ws, i, 3, gate)
        base_fill = COLOR.get(tone) if tone else None
        _cell(ws, i, 4, baseline, fill=base_fill)
        # 两个空版本列（黄格）
        _cell(ws, i, 5, "", fill=FILL_INPUT)
        _cell(ws, i, 6, "", fill=FILL_INPUT)
        _cell(ws, i, 7, "")
        ws.row_dimensions[i].height = 22 if name not in ("主要问题", "口径") else 36

    # 主要问题行加高
    ws.row_dimensions[4 + len(METRICS) - 1].height = 40

    _widths(
        ws,
        {
            1: 18,
            2: 42,
            3: 22,
            4: 28,
            5: 16,
            6: 16,
            7: 28,
        },
    )

    # 底部必测场景速查（仍在同一 sheet，压缩成一块）
    r0 = 4 + len(METRICS) + 1
    ws.merge_cells(start_row=r0, start_column=1, end_row=r0, end_column=7)
    sec = ws.cell(r0, 1, "必测场景（每次上线固定跑，session 可换）")
    sec.fill = FILL_SECTION
    sec.font = FONT_SECTION

    scene_headers = ["#", "场景", "验收要点", "10/22 Session", "10/22结果", "本次", "说明"]
    for i, h in enumerate(scene_headers, 1):
        ws.cell(r0 + 1, i, h)
    _header(ws, r0 + 1, 7)

    scenes = [
        (1, "连续多手（≥32）", "每手完整；开头/结尾单独切出", "1792483028902", "通过", "", "可优化：第48手漏1秒"),
        (2, "生产真实切片", "同左，贴近生产", "11792479998678", "通过", "", ""),
        (3, "入坐无手牌", "无牌段单独切；结尾可识别", "1792479281617", "有待优化", "", "结尾16s冻结未识别"),
        (4, "围观/摊牌", "invalid_hand，不污染有效手", "1792721277727", "通过", "", ""),
        (5, "与牌局无关视频", "解析失败+invalid", "1792481067832", "通过", "", ""),
        (6, "中间黑屏", "黑屏不成有效手", "1792480268460", "通过", "", ""),
    ]
    for i, row in enumerate(scenes, start=r0 + 2):
        for j, v in enumerate(row, 1):
            fill = FILL_INPUT if j == 6 else None
            if j == 5:
                if v == "通过":
                    fill = FILL_PASS
                elif v == "有待优化":
                    fill = FILL_WARN
            _cell(ws, i, j, v, fill=fill)
            if j in (2, 3, 7):
                ws.cell(i, j).alignment = Alignment(wrap_text=True, vertical="center", horizontal="left")

    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return out


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description="生成切局质量核心指标单表")
    p.add_argument("-o", "--out", type=Path, default=OUT_DEFAULT)
    args = p.parse_args()
    print(f"wrote {build(args.out)}")


if __name__ == "__main__":
    main()
