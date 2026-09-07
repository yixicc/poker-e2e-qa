#!/usr/bin/env python3
"""合成一份文档：指标正反例 + 按 qa-case-system 用例编写工作流格式的 TC。"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from generate_test_points import (
    CONFLICT,
    OPPORTUNITY_RATES,
    SRC,
    calc_type,
    json_path,
    load_source,
)
from metric_card_expect import expect_for
from metric_fixtures import fixture_for

ROOT = Path(__file__).resolve().parent
POINTS = json.loads((ROOT / "test-points.json").read_text(encoding="utf-8"))
BATCH = "BATCH-RPT-METRIC-001"
VERSION = "3.0"
STATUS = "ready_for_review"

FILL_TITLE = PatternFill("solid", fgColor="123E65")
FILL_INTRO = PatternFill("solid", fgColor="EAF2F8")
FILL_NOTE = PatternFill("solid", fgColor="FFF4D2")
FILL_HEAD = PatternFill("solid", fgColor="D9EAF7")
FILL_BLOCK = PatternFill("solid", fgColor="0F3554")
FILL_GROUP = PatternFill("solid", fgColor="1F5E88")
FILL_ID = PatternFill("solid", fgColor="F5F9FC")
FILL_P0 = PatternFill("solid", fgColor="FCE4D6")
FILL_P1 = PatternFill("solid", fgColor="FFF4D2")
FILL_POS = PatternFill("solid", fgColor="C6EFCE")
FILL_NEG = PatternFill("solid", fgColor="F8CBAD")
FILL_OPINION = PatternFill("solid", fgColor="FFFDF4")
FONT_WHITE = Font(bold=True, color="FFFFFF", size=16, name="Microsoft YaHei")
FONT_INTRO = Font(bold=True, color="17324D", name="Microsoft YaHei")
FONT_NOTE = Font(color="6D5200", name="Microsoft YaHei", size=10)
FONT_HEAD = Font(bold=True, color="17324D", name="Microsoft YaHei", size=10)
FONT_BLOCK = Font(bold=True, color="FFFFFF", size=13, name="Microsoft YaHei")
FONT_GROUP = Font(bold=True, color="FFFFFF", size=12, name="Microsoft YaHei")
FONT_P0 = Font(bold=True, color="C65911", name="Microsoft YaHei")
WRAP = Alignment(wrap_text=True, vertical="top")
CENTER = Alignment(wrap_text=True, vertical="center", horizontal="center")
THIN = Border(
    left=Side(style="thin", color="D9E2EA"),
    right=Side(style="thin", color="D9E2EA"),
    top=Side(style="thin", color="D9E2EA"),
    bottom=Side(style="thin", color="D9E2EA"),
)

CASE_HEADERS = [
    "用例 ID",
    "标题",
    "关联测试点",
    "优先级",
    "数据层级",
    "关联功能",
    "类型",
    "测试层级",
    "正反例",
    "前置条件",
    "测试数据",
    "测试环境",
    "逐步操作",
    "逐步预期",
    "通过标准",
    "PRD 来源",
    "状态",
    "批次",
    "自动化候选",
    "关联需求",
    "意见",
]

CARD_HEADERS = [
    "需求编号",
    "指标编码",
    "中文名称",
    "优先级",
    "数据层级",
    "是否用户可见",
    "含义（字典原文）",
    "统计方法 / 口径（字典原文）",
    "正例素材",
    "反例素材",
    "用哪一场",
    "正例手算期望",
    "反例手算期望（必须排除）",
    "看哪个字段",
    "口径冲突",
]

ENV = [
    "测试环境可生成复盘报告并取出整包 JSON（或等价数据接口）",
    "当前登录用户视为 Hero；围观、无关视频不得当成该用户本场战绩",
    "口径只认《德州扑克复盘报告_数据指标需求清单》01_指标字典；标了口径冲突的条目不认 Skill 指南",
    "可用播放器或文件属性核对视频时长；可用 hands[] / 决策点手算对照",
]


def slug(code: str) -> str:
    return code.upper().replace("_", "-")


def req_id(code: str) -> str:
    return f"REQ-RPT-{slug(code)}"


def tc_id(code: str, seq: int) -> str:
    return f"TC-RPT-{slug(code)}-{seq:03d}"


def bullets(items: list[str]) -> str:
    return "\n".join(f"· {x}" for x in items if x)


def numbered(items, key: str | None = None) -> str:
    lines = []
    for i, item in enumerate(items, 1):
        text = item[key] if key else item
        lines.append(f"{i}. {text}")
    return "\n".join(lines)


def tp_index() -> dict[tuple[str, str], str]:
    out = {}
    for p in POINTS["test_points"]:
        if p["family"] == "metric_scenario" and p["metric_code"]:
            out[(p["metric_code"], p["scenario"])] = p["id"]
    return out


def first_tp(idx: dict[tuple[str, str], str], code: str, *scenes: str) -> list[str]:
    for s in scenes:
        if (code, s) in idx:
            return [idx[(code, s)]]
    # 兜底：任意一个该指标测试点
    for (c, _s), pid in idx.items():
        if c == code:
            return [pid]
    return [f"TP-RPT-{code}"]


def compact_case(case: dict) -> dict:
    rec = {
        "id": case["id"],
        "title": case["title"],
        "testPointIds": case["testPointIds"],
        "requirementIds": case["requirementIds"],
        "priority": case["priority"],
        "type": case["type"],
        "level": case["level"],
        "preconditions": case["preconditions"],
        "testData": case["testData"],
        "environment": case["environment"],
        "steps": [{"action": s["action"], "expectedResult": s["expectedResult"]} for s in case["steps"]],
        "status": case["status"],
        "version": case["version"],
        "batchId": case["batchId"],
        "automationCandidate": case["automationCandidate"],
    }
    if case.get("releaseImpact"):
        rec["releaseImpact"] = case["releaseImpact"]
    return rec


def build_card_row(m: dict, obj_map: dict) -> dict:
    fx = fixture_for(m["code"])
    ex = expect_for(m["code"])
    return {
        **m,
        "req": req_id(m["code"]),
        "include": fx["include"],
        "exclude": fx["exclude"],
        "session": ex["session"],
        "expect": ex["expect"],
        "fail": ex["fail"],
        "json_path": json_path(m["code"], obj_map),
        "conflict": m["code"] in CONFLICT,
        "mix": fx.get("mix") or "",
        "zero": fx.get("zero_denom") or "",
        "missing": fx.get("missing") or "",
        "typ": calc_type(m["code"]),
    }


def make_case(
    *,
    cid: str,
    title: str,
    tps: list[str],
    m: dict,
    card: dict,
    kind: str,
    ctype: str,
    pre: list[str],
    data: list[str],
    steps: list[dict],
    criterion: str,
) -> dict:
    return {
        "id": cid,
        "title": title,
        "testPointIds": tps,
        "requirementIds": [card["req"]],
        "priority": m["priority"] if m["priority"] in {"P0", "P1", "P2"} else "P1",
        "type": ctype,
        "level": "api",
        "preconditions": pre,
        "testData": data,
        "environment": ENV,
        "steps": steps,
        "status": STATUS,
        "version": VERSION,
        "batchId": BATCH,
        "automationCandidate": True,
        "releaseImpact": "报告数字错会导致用户可见复盘结论错误" if m["priority"] == "P0" else "",
        "layer": m["level"],
        "func": f"{m['code']} / {m['name']}",
        "kind": kind,
        "criterion": criterion,
        "source": f"指标字典 {m['code']}：{m['method']}",
    }


def cases_for(m: dict, card: dict, idx: dict[tuple[str, str], str]) -> list[dict]:
    code, name, path = m["code"], m["name"], card["json_path"]
    out: list[dict] = []

    out.append(
        make_case(
            cid=tc_id(code, 1),
            title=f"{name}按正例素材计入",
            tps=first_tp(idx, code, "S1"),
            m=m,
            card=card,
            kind="正例",
            ctype="functional",
            pre=[
                f"本条只验正例计入，不把反例场的结果算作通过。",
                f"准备正例素材（见测试数据）。配场：{card['session']}",
                "测试入口：生成复盘报告 → 取整包 JSON，不做 App 页面点击验收。",
            ],
            data=[
                f"metric_code={code}",
                f"json_path={path}",
                f"正例素材：{'；'.join(card['include'])}",
                f"手算期望：{card['expect']}",
            ],
            steps=[
                {
                    "action": f"按正例素材准备场次并生成复盘报告。\n正例：\n{bullets(card['include'])}",
                    "expectedResult": "报告生成成功（或按规则明确拒绝无关素材）。测试员能指出本场哪些手/哪段视频是正例。",
                },
                {
                    "action": f"打开整包 JSON，定位 `{path}`。",
                    "expectedResult": f"字段可定位。正例手算：{card['expect']}",
                },
                {
                    "action": "按字典口径手算一遍，与字段值比较。需要时长时用播放器核对。",
                    "expectedResult": f"实际值等于正例手算。对不上则本条失败。通过标准：{card['expect']}",
                },
            ],
            criterion=card["expect"],
        )
    )

    out.append(
        make_case(
            cid=tc_id(code, 2),
            title=f"{name}失败-反例素材不得计入",
            tps=first_tp(idx, code, "S2", "S1"),
            m=m,
            card=card,
            kind="反例",
            ctype="negative",
            pre=[
                "本条只验反例排除。正例场通过不能代替本条。",
                "反例必须真正跑一遍，不能只写在纸上。",
                "测试入口：生成复盘报告 → 取整包 JSON。",
            ],
            data=[
                f"metric_code={code}",
                f"json_path={path}",
                f"反例素材：{'；'.join(card['exclude'])}",
                f"反例期望：{card['fail']}",
            ],
            steps=[
                {
                    "action": f"按反例素材准备对照场（或同一场混入反例手）并生成报告。\n反例：\n{bullets(card['exclude'])}",
                    "expectedResult": "对照场已生成或按规则被拒；测试员能指出哪些是反例。",
                },
                {
                    "action": f"打开 `{path}`，对照正例场的手算值。",
                    "expectedResult": f"反例不得改变结果或不得生成该用户战绩。{card['fail']}",
                },
            ],
            criterion=card["fail"],
        )
    )

    typ = card["typ"]
    if typ == "T2" or code in OPPORTUNITY_RATES or (typ == "T7" and code.endswith("_rate")):
        zero = card["zero"] or "用户真实入座并参与了若干手，但从未出现该指标的机会。不要用围观视频。"
        out.append(
            make_case(
                cid=tc_id(code, 3),
                title=f"{name}分母为0时不造假百分比",
                tps=first_tp(idx, code, "S4", "S3"),
                m=m,
                card=card,
                kind="边界",
                ctype="boundary",
                pre=[
                    "本条只验分母为 0。围观不是分母为 0。",
                    f"素材：{zero}",
                ],
                data=[f"metric_code={code}", f"json_path={path}", f"分母为0素材：{zero}"],
                steps=[
                    {
                        "action": f"准备分母为 0 的参与场：{zero}",
                        "expectedResult": "场次能生成，该指标没有任何一次机会。",
                    },
                    {
                        "action": f"看 `{path}` 和对应报告小节。",
                        "expectedResult": "字段为 null/省略，不得输出 0% 或 100%。用户侧不展示假百分比。",
                    },
                ],
                criterion=f"`{path}` 省略或 null，不得 0%/100%。",
            )
        )

    need_miss = typ in {"T0", "T3", "T5"} or bool(card["missing"])
    if need_miss:
        miss = card["missing"] or "缺该字段源数据。另备一场齐全对照，不得把对照值抄过来。"
        seq = 4 if any(c["kind"] == "边界" for c in out) else 3
        out.append(
            make_case(
                cid=tc_id(code, seq),
                title=f"{name}失败-源数据缺失不得编造",
                tps=first_tp(idx, code, "S7"),
                m=m,
                card=card,
                kind="反例",
                ctype="negative",
                pre=["本条只验缺失。不得用 0、空串、默认牌面、默认时长冒充。", f"素材：{miss}"],
                data=[f"metric_code={code}", f"json_path={path}", f"缺失素材：{miss}"],
                steps=[
                    {
                        "action": f"准备缺失素材：{miss}",
                        "expectedResult": "系统仍能出报告或按规则整场 omit，不得崩溃后填默认值。",
                    },
                    {
                        "action": f"看 `{path}`。",
                        "expectedResult": "字段省略或 null。对照场的齐全值不得被抄到本场。",
                    },
                ],
                criterion=f"`{path}` 省略或 null，不得编造。",
            )
        )

    if code in CONFLICT:
        out.append(
            make_case(
                cid=tc_id(code, 8),
                title=f"{name}按字典口径判定-不得走Skill",
                tps=first_tp(idx, code, "S8"),
                m=m,
                card=card,
                kind="边界",
                ctype="functional",
                pre=[
                    f"口径冲突：{CONFLICT[code]}",
                    "只认需求清单。两种口径必须能算出不同数字，否则本条无法验收。",
                ],
                data=[
                    f"metric_code={code}",
                    f"冲突点：{CONFLICT[code]}",
                    f"字典期望：{card['expect']}",
                ],
                steps=[
                    {
                        "action": "准备能让字典口径和 Skill 口径算出不同数字的场（场A 摊牌率 3/6=50% vs 3/8=37.5%）。",
                        "expectedResult": "手算两个候选值，两者不同。",
                    },
                    {
                        "action": f"看 `{path}`。",
                        "expectedResult": f"必须等于字典/基准。若等于 Skill，记口径冲突不通过。{CONFLICT[code]}",
                    },
                ],
                criterion=f"等于字典值。等于 Skill 则失败。{CONFLICT[code]}",
            )
        )
    return out


def style_top(ws, title: str, intro: str, note: str, headers: list[str], freeze: str) -> None:
    last = get_column_letter(len(headers))
    ws.merge_cells(f"A1:{last}1")
    ws["A1"] = title
    ws["A1"].fill = FILL_TITLE
    ws["A1"].font = FONT_WHITE
    ws["A1"].alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height = 30
    ws.merge_cells(f"A2:{last}2")
    ws["A2"] = intro
    ws["A2"].fill = FILL_INTRO
    ws["A2"].font = FONT_INTRO
    ws["A2"].alignment = Alignment(wrap_text=True, vertical="center")
    ws.row_dimensions[2].height = 40
    ws.merge_cells(f"A3:{last}3")
    ws["A3"] = note
    ws["A3"].fill = FILL_NOTE
    ws["A3"].font = FONT_NOTE
    ws["A3"].alignment = Alignment(wrap_text=True, vertical="center")
    ws.row_dimensions[3].height = 36
    for col, header in enumerate(headers, 1):
        cell = ws.cell(4, col, header)
        cell.fill = FILL_HEAD
        cell.font = FONT_HEAD
        cell.alignment = CENTER
        cell.border = THIN
    ws.row_dimensions[4].height = 28
    ws.freeze_panes = freeze
    ws.sheet_view.showGridLines = False


def write_intro(ws) -> None:
    ws.title = "00_使用说明"
    style_top(
        ws,
        "复盘报告指标测试用例 · 正反例对照",
        "一份文档：指标正反例 + 按测试用例编写工作流格式的 TC。不接 App 页面批次。",
        "一条用例只验一个结论。正例、反例拆开。逐步操作和逐步预期必须对着看。涉及报告数字时必须核 JSON 字段，页面展示不能单独当证据。",
        ["章节", "说明"],
        "A5",
    )
    rows = [
        ("01_指标正反例", "字典一行一张卡。正例素材 / 反例素材分列。数字默认场A～场I，见 sample_sessions.md。"),
        ("02_测试用例", "格式同 qa-case-system：用例ID、标题、关联测试点/需求、优先级、类型、层级、前置条件、测试数据、环境、逐步操作、逐步预期、状态 ready_for_review。"),
        ("正例", "functional。对象+结果，例如「视频时长按用户参与录像元数据写出」。"),
        ("反例", "negative。对象+失败-原因，例如「视频时长失败-围观或无关视频不得当作本场时长」。"),
        ("边界", "分母为 0、源数据缺失、口径冲突。围观不能冒充分母为 0。"),
        ("编号", "REQ-RPT-<指标>；TC-RPT-<指标>-001 正例、-002 反例、-003/004 边界。发布后不复用。"),
        ("场A摘要", "用户入座 12:30=750秒，8手。参与6、翻前弃3、进翻后5、摊牌3、VPIP5、PFR2、筹码−120、BB−0.1。H4 有亏损算参与、不算VPIP。"),
        ("场B/C", "围观 20 分钟 / 无关视频。不得当作用户本场战绩。"),
        ("批次", f"{BATCH}  v{VERSION}  状态 {STATUS}"),
    ]
    for i, (a, b) in enumerate(rows, 5):
        ws.cell(i, 1, a).alignment = WRAP
        ws.cell(i, 2, b).alignment = WRAP
        ws.cell(i, 1).border = THIN
        ws.cell(i, 2).border = THIN
        ws.row_dimensions[i].height = 32
    ws.column_dimensions["A"].width = 20
    ws.column_dimensions["B"].width = 120


def write_cards(ws, cards: list[dict]) -> None:
    ws.title = "01_指标正反例"
    style_top(
        ws,
        "指标正反例 · 顺序与指标字典相同",
        "左边是字典原文，不改写。右边用正例 / 反例区分，不要混成一句「按口径计算」。",
        "换了真实录像，先改场再改期望。P0 橙底。口径冲突列标「是」的，Skill 算对也不算过。",
        CARD_HEADERS,
        "C5",
    )
    last = len(CARD_HEADERS)
    for r, card in enumerate(cards, 5):
        vals = [
            card["req"],
            card["code"],
            card["name"],
            card["priority"],
            card["level"],
            card["visible"],
            card["meaning"],
            card["method"],
            bullets(card["include"]),
            bullets(card["exclude"]),
            card["session"] + ("。 " + card["mix"] if card["mix"] else ""),
            card["expect"],
            card["fail"],
            card["json_path"],
            "是" if card["conflict"] else "否",
        ]
        for c, v in enumerate(vals, 1):
            cell = ws.cell(r, c, v)
            cell.alignment = WRAP
            cell.border = THIN
            cell.font = Font(name="Microsoft YaHei", size=9)
            if card["priority"] == "P0":
                cell.fill = FILL_P0
            elif card["priority"] == "P1":
                cell.fill = FILL_P1
            if c == 9:
                cell.fill = FILL_POS
            if c == 10:
                cell.fill = FILL_NEG
            if card["conflict"] and c == 15:
                cell.fill = FILL_NEG
        ws.row_dimensions[r].height = 84
    ws.auto_filter.ref = f"A4:{get_column_letter(last)}{4+len(cards)}"
    widths = [28, 26, 16, 8, 12, 12, 26, 34, 42, 42, 26, 40, 36, 30, 10]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def excel_case_row(case: dict) -> list[str]:
    return [
        case["id"],
        case["title"],
        "、".join(case["testPointIds"]),
        case["priority"],
        case["layer"],
        case["func"],
        case["type"],
        case["level"],
        case["kind"],
        numbered(case["preconditions"]),
        numbered(case["testData"]),
        numbered(case["environment"]),
        numbered(case["steps"], "action"),
        numbered(case["steps"], "expectedResult"),
        case["criterion"],
        case["source"],
        case["status"],
        case["batchId"],
        "是" if case["automationCandidate"] else "否",
        "、".join(case["requirementIds"]),
        "",
    ]


def write_cases(ws, cases: list[dict], cards: list[dict]) -> None:
    ws.title = "02_测试用例"
    style_top(
        ws,
        "测试用例 · 编写工作流格式",
        "字段同 test-case.schema：一条一个结论；每步有可观察预期；后台/JSON 核对写进步骤。状态 ready_for_review。",
        "执行：先看正反例列，再对逐步操作和逐步预期。不要手改本表，改脚本后重导。",
        CASE_HEADERS,
        "E5",
    )
    last = len(CASE_HEADERS)
    by_layer: dict[str, list[dict]] = {}
    order = []
    for c in cases:
        by_layer.setdefault(c["layer"], []).append(c)
    for card in cards:
        if card["level"] not in order:
            order.append(card["level"])
    r = 5
    for layer in order:
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=last)
        cell = ws.cell(r, 1, f"数据层级｜{layer}")
        cell.fill = FILL_BLOCK
        cell.font = FONT_BLOCK
        cell.alignment = Alignment(vertical="center")
        ws.row_dimensions[r].height = 26
        r += 1
        for case in by_layer.get(layer, []):
            for c, v in enumerate(excel_case_row(case), 1):
                cell = ws.cell(r, c, v)
                cell.alignment = WRAP
                cell.border = THIN
                cell.font = Font(name="Microsoft YaHei", size=9)
                if c <= 4:
                    cell.fill = FILL_ID
                if c == 4:
                    cell.fill = FILL_P0 if case["priority"] == "P0" else FILL_P1
                    cell.font = FONT_P0 if case["priority"] == "P0" else Font(bold=True, name="Microsoft YaHei")
                if c == 9:
                    cell.fill = FILL_POS if case["kind"] == "正例" else FILL_NEG
                if c == last:
                    cell.fill = FILL_OPINION
            ws.row_dimensions[r].height = 92
            r += 1
    ws.auto_filter.ref = f"A4:{get_column_letter(last)}{r-1}"
    widths = [28, 28, 16, 8, 14, 28, 12, 10, 8, 32, 32, 28, 42, 42, 32, 28, 16, 22, 10, 26, 12]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def main() -> None:
    metrics, obj_map, _ = load_source()
    idx = tp_index()
    cards = [build_card_row(m, obj_map) for m in metrics]
    cases: list[dict] = []
    for m, card in zip(metrics, cards):
        cases.extend(cases_for(m, card, idx))

    wb = Workbook()
    write_intro(wb.active)
    write_cards(wb.create_sheet(), cards)
    write_cases(wb.create_sheet(), cases, cards)
    xlsx = ROOT / "指标测试用例.xlsx"
    wb.save(xlsx)

    payload = {
        "batchId": BATCH,
        "version": VERSION,
        "status": STATUS,
        "source": str(SRC),
        "counts": {
            "metrics": len(cards),
            "cases": len(cases),
            "positive": sum(1 for c in cases if c["kind"] == "正例"),
            "negative": sum(1 for c in cases if c["kind"] == "反例"),
            "boundary": sum(1 for c in cases if c["kind"] == "边界"),
            "P0": sum(1 for c in cases if c["priority"] == "P0"),
            "P1": sum(1 for c in cases if c["priority"] == "P1"),
            "P2": sum(1 for c in cases if c["priority"] == "P2"),
        },
        "notes": [
            "正例、反例拆成两条 TC，格式遵守 test-case.schema.json。",
            "不接 BATCH-PHASE-4 页面用例。",
        ],
        "cases": [compact_case(c) for c in cases],
    }
    (ROOT / "test-cases.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("cards", len(cards), "cases", len(cases), Counter(c["kind"] for c in cases))
    print("wrote", xlsx)


if __name__ == "__main__":
    main()
