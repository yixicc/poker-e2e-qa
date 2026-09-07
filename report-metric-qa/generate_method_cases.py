#!/usr/bin/env python3
"""每个测试点至少 1 条用例；用等价类/边界值/场景/错误推断/判定表/因果图/正交生成正反向用例。"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from business_scenes import SCENES
from product_scenes import PRODUCT_META, PRODUCT_SCENES
from generate_test_points import load_source
from metric_card_expect import expect_for
from case_labels import neg_given, neg_title, pos_title
from metric_fixtures import MODULE_FIXTURES, fixture_for

ROOT = Path(__file__).resolve().parent
POINTS = json.loads((ROOT / "test-points.json").read_text(encoding="utf-8"))
BATCH = "BATCH-RPT-METRIC-001"
VERSION = "6.2"

FILL_TITLE = PatternFill("solid", fgColor="123E65")
FILL_EXEC = PatternFill("solid", fgColor="F4F6F8")

EXEC_STATUS_OPTIONS = ("未执行", "通过", "失败", "阻塞", "跳过")
FILL_INTRO = PatternFill("solid", fgColor="EAF2F8")
FILL_NOTE = PatternFill("solid", fgColor="FFF4D2")
FILL_HEAD = PatternFill("solid", fgColor="D9EAF7")
FILL_P0 = PatternFill("solid", fgColor="FCE4D6")
FILL_P1 = PatternFill("solid", fgColor="FFF4D2")
FILL_POS = PatternFill("solid", fgColor="C6EFCE")
FILL_NEG = PatternFill("solid", fgColor="F8CBAD")
FILL_ID = PatternFill("solid", fgColor="F5F9FC")
FONT_WHITE = Font(bold=True, color="FFFFFF", size=16, name="Microsoft YaHei")
FONT_INTRO = Font(bold=True, color="17324D", name="Microsoft YaHei")
FONT_NOTE = Font(color="6D5200", name="Microsoft YaHei", size=10)
FONT_HEAD = Font(bold=True, color="17324D", name="Microsoft YaHei", size=10)
WRAP = Alignment(wrap_text=True, vertical="top")
CENTER = Alignment(wrap_text=True, vertical="center", horizontal="center")
THIN = Border(
    left=Side(style="thin", color="D9E2EA"),
    right=Side(style="thin", color="D9E2EA"),
    top=Side(style="thin", color="D9E2EA"),
    bottom=Side(style="thin", color="D9E2EA"),
)

HEADERS = [
    "用例ID",
    "指标编码",
    "中文名称",
    "优先级",
    "测试方法",
    "数据层级",
    "是否用户可见",
    "含义（字典原文）",
    "统计方法 / 口径（字典原文）",
    "测试用例标题",
    "正/反例",
    "前置条件",
    "测试步骤",
    "预期结果",
    "对应字段",
    "执行状态",
    "时间",
    "备注",
]


def bullets(items: list[str]) -> str:
    return "\n".join(f"· {x}" for x in items if x)


def pick_method(tp: dict) -> str:
    s = tp["scenario"]
    typ = tp.get("calc_type") or ""
    code = tp.get("metric_code") or ""
    if code == "video_duration":
        return "边界值分析法"
    if s == "S1" and (
        "position" in code
        or code in {"position_name", "hero_position", "hands_by_position"}
    ):
        return "正交试验法"
    if s == "S1" and typ == "T4":
        return "判定表法"
    if s == "S1" and typ == "T7":
        return "判定表法"
    if s == "S1":
        return "等价类划分法"
    if s == "S2" and typ == "T4":
        return "边界值分析法"
    if s == "S2" and typ == "T7":
        return "判定表法"
    if s == "S2":
        return "等价类划分法"
    if s == "S3":
        return "因果图法"
    if s in {"S4", "S6"}:
        return "边界值分析法"
    if s == "S5":
        return "场景设计法"
    if s == "S7":
        return "错误推断法"
    if s == "S8":
        return "判定表法"
    if s == "G4":
        return "判定表法"
    if s in {"G1", "G2", "G3"}:
        return "场景设计法"
    return "错误推断法"


def pn_for(tp: dict) -> str:
    s = tp["scenario"]
    name = tp.get("scenario_name") or ""
    if tp.get("metric_code") == "video_duration":
        return "反例" if s in {"S2", "S7"} else "正例"
    if s in {"S2", "S7"} or "omit" in name or "degraded" in name:
        return "反例"
    if s in {"S4"}:
        return "反例"
    if s == "S8":
        return "反例"
    if s == "S3" and tp.get("calc_type") == "T7":
        return "反例"
    return "正例"


S3_TITLE = {
    "participation_rate": "Hero前位翻前弃牌盈亏为0",
    "preflop_fold_rate": "翻前跟注或加注后进翻牌后",
    "postflop_entry_rate": "翻前结束未发翻牌",
    "limp_rate": "前面无人加注时加注或弃牌",
    "call_open_rate": "面对加注弃牌或再加注",
    "three_bet_rate": "面对加注跟注或弃牌",
    "four_bet_rate": "面对再加注跟注或弃牌",
    "fold_to_3bet_rate": "面对再加注跟注或再加注",
    "bb_defense_rate": "大盲被加注后弃牌",
    "sb_defense_rate": "小盲被加注后弃牌",
    "cbet_flop_rate": "翻前加注后进翻牌过牌",
    "turn_barrel_rate": "翻牌下注后转牌过牌",
    "river_bet_rate": "到河牌过牌或弃牌",
    "river_call_vs_raise_rate": "河牌被再加注后弃牌",
    "postflop_call_rate": "翻后面对下注弃牌或加注",
    "postflop_raise_rate": "翻后面对下注跟注或弃牌",
    "weak_top_pair_continue_rate": "弱顶对过牌或弃牌",
    "marginal_hand_entry_rate": "拿到边缘牌却弃牌",
    "opponent_raise_rate": "对手可加注却跟或弃",
    "opponent_call_rate": "对手面对下注弃或加",
    "opponent_fold_rate": "对手面对下注跟或加",
    "opponent_3bet_rate": "对手面对加注跟或弃",
    "opponent_cbet_rate": "对手翻前加注后进翻牌过牌",
}


def case_title(tp: dict, name: str, kind: str, fx=None) -> str:
    s = tp["scenario"]
    code = tp.get("metric_code") or ""
    if code == "video_duration":
        return {
            "S1": "视频时长正例-单位精确到秒",
            "S2": "视频时长反例-上传时长为0",
            "S5": "视频时长正例-上传超长视频",
            "S7": "视频时长反例-读不到时长不得写成0秒",
        }.get(s, tp["title"])
    if s == "S3":
        if tp.get("calc_type") == "T7":
            return f"{name}反例-只满足一半条件不含"
        tail = S3_TITLE.get(code)
        if tail:
            return f"{name}正例-{tail}"
    titles = {
        "S1": f"{name}正例-{pos_title(code, name, tp.get('calc_type') or '')}",
        "S2": f"{name}反例-{neg_title(code)}",
        "S3": f"{name}正例-{S3_TITLE.get(code, '没做成的只算分母不算分子')}",
        "S4": f"{name}反例-分母为0字段不出现",
        "S5": f"{name}正例-与明细自洽",
        "S6": f"{name}正例-单位与换算正确",
        "S7": f"{name}反例-源数据缺失不得编造",
        "S8": f"{name}反例-按字典口径不得走Skill",
        "G1": tp["title"],
        "G2": tp["title"],
        "G3": tp["title"],
        "G4": tp["title"],
    }
    return titles.get(s, tp["title"] or f"{name}{kind}")


# 缺失场：只有测员能准备的才写进用例。读不到/元数据坏/识别不出不写。
UNCONSTRUCTABLE = ("读不到", "元数据", "损坏", "识别不出", "解析不到", "识别不到", "无法识别")
KEEP_S7 = (
    "没有每手结算",
    "该手没有结算",
    "没有可信整场盈亏",
    "没有一手盈利",
    "没有一手亏损",
    "没有任何 per_hand_ev",
    "无 GTO",
    "没有 GTO",
    "该手无 GTO",
    "缺实际盈亏",
    "缺 EV",
    "GTO 与盈亏都不足以",
    "没有同时满足",
    "没有「风险偏高",
    "未摊牌",
    "没进翻后",
    "没到转牌",
    "没到河牌",
    "没到翻牌",
    "手牌被遮挡",
    "没亮",
    "单人底池",
    "全场没有一手盈利",
    "全场没有一手亏损",
)


# 口径已拆成单独路径时，不再写模板总正例 / 打包反例
SKIP_S1_TEMPLATE = {
    "hands_played",
    "vpip_rate",
    "pfr_rate",
    "showdown_hands",
    "showdown_result",
    "post翻牌_call_rate",
    "post翻牌_raise_rate",
    "folded_pre翻牌_hands",
    "hero_position",
}
# 没做成场面已写成具体牌，不再套模板
SKIP_S3_HAS_EXTRA = {
    "showdown_rate",
    "marginal_hand_entry_rate",
}
# 分母不是「做成/没做成」动作点，或写不出具体牌
SKIP_S3_EMPTY = (
    "有机会但没做",
    "分母是总手数",
    "有机会自愿",
)

SKIP_S2_TEMPLATE = {
    "hands_played",
    "vpip_rate",
    "pfr_rate",
    "showdown_hands",
    "showdown_rate",
    "showdown_result",
    "post翻牌_call_rate",
    "post翻牌_raise_rate",
    "folded_pre翻牌_hands",
    "pre翻牌_fold_rate",
    "post翻牌_hands",
    "post翻牌_entry_rate",
    "participation_rate",
    "board_翻牌",
    "board_turn",
    "board_river",
    "action_sequence_翻牌",
    "action_sequence_turn",
    "action_sequence_river",
    "winning_hands_count",
    "losing_hands_count",
    "breakeven_hands_count",
    "hero_position",
}

SPLIT_S2 = {
    "total_hands": [
        {
            "title": "总手数反例-登录用户旁观未入座",
            "given": "录屏为登录用户旁观牌局，本人未入座、没有自己的手牌。本场应计入总手数=n（通常为 0）",
            "value": "n",
        },
        {
            "title": "总手数反例-另一场手不能算进来",
            "given": "另录一场对照。本场应计入总手数=n，另一场的手不能算进来",
            "value": "n",
        },
        {
            "title": "总手数反例-半手录不全",
            "given": "录像从一手中间开始或中途停录，看不全完整一手。本场应计入总手数=n",
            "value": "n",
        },
    ],
}


def skip_reason(tp: dict, fx) -> str | None:
    """造不出或不属于该指标可测维的，不写进用例表。"""
    code = tp.get("metric_code") or ""
    s = tp.get("scenario") or ""
    family = tp.get("family") or ""
    if family == "metric_scenario" and s == "S5" and code != "video_duration":
        return "与正例重复：素材数出 n、字段=n 即自洽，不单写一条"
    if family == "metric_scenario" and s == "S8":
        return "口径差要用具体牌来说，不写「字典 vs Skill」"
    # 口径已拆成单独路径时，不再写「含全部业务场景」总正例 / 打包反例
    if family == "metric_scenario" and s == "S1" and code in SKIP_S1_TEMPLATE:
        return "口径已按路径拆开，不写含全部业务场景"
    if family == "metric_scenario" and s == "S2" and code in SKIP_S2_TEMPLATE:
        return "反例已按情况拆开，不写打包反例"
    if family == "metric_scenario" and s == "S3" and tp.get("calc_type") != "T7":
        if code in SKIP_S3_HAS_EXTRA:
            return "没做成场面已写成具体牌"
        opp = " ".join((fx or {}).get("opportunity") or [])
        if not opp.strip() or any(k in opp for k in SKIP_S3_EMPTY):
            return "写不出具体没做成的牌，不套「机会」"
    if code == "video_duration" and s == "S7":
        return "视频时长只测 0 / 超长 / 到秒；读不到时长造不出"
    if s != "S7":
        return None
    miss = (fx or {}).get("missing") or ""
    title = tp.get("title") or ""
    if any(k in miss for k in UNCONSTRUCTABLE):
        return f"造不出：{miss}"
    if any(k in miss for k in KEEP_S7):
        return None
    if "空列表" in title or "无入选" in title:
        return None
    if miss:
        return f"缺失条件造不出或不清：{miss}"
    return "S7 无明确可准备素材，不写进用例"


def method_cases(metrics: dict[str, dict]) -> tuple[list[dict], list[dict]]:
    rows = []
    skipped = []
    n = 0
    seq = 0
    for tp in POINTS["test_points"]:
        code = tp.get("metric_code") or ""
        m = metrics.get(code, {})
        fx = fixture_for(code) if code in metrics else None
        reason = skip_reason(tp, fx)
        if reason:
            skipped.append(
                {
                    "tp": tp["id"],
                    "code": code or "-",
                    "name": tp.get("metric_name") or tp["title"],
                    "scene": tp.get("scenario") or "",
                    "reason": reason,
                }
            )
            continue
        if code == "total_hands" and tp.get("scenario") == "S2":
            name = tp.get("metric_name") or "总手数"
            path = tp.get("json_path") or ""
            for spec in SPLIT_S2["total_hands"]:
                n += 1
                seq += 1
                rows.append(
                    {
                        "id": f"TC-RPT-{n:03d}",
                        "tp": tp["id"],
                        "code": code,
                        "name": name,
                        "priority": tp["priority"],
                        "method": "等价类划分法",
                        "layer": m.get("level") or tp.get("data_layer") or "",
                        "visible": m.get("visible") or tp.get("visible") or "",
                        "meaning": m.get("meaning") or "",
                        "formula": m.get("method") or "",
                        "title": spec["title"],
                        "kind": "反例",
                        "pre": numbered(["已登录，当前用户是 Hero。准备下列不该计入的素材。", spec["given"]]),
                        "steps": check_steps(name, spec["value"]),
                        "expect": f"{name}={spec['value']}",
                        "field": path,
                        "family": "metric_scenario",
                        "_src": 0,
                        "_i": seq,
                    }
                )
            continue
        ex = expect_for(code) if code in metrics else None
        meaning = m.get("meaning") or tp.get("title") or ""
        method_txt = m.get("method") or tp.get("formula") or ""
        layer = m.get("level") or tp.get("data_layer") or ""
        visible = m.get("visible") or tp.get("visible") or ""
        path = tp.get("json_path") or ""
        name = tp.get("metric_name") or code or tp["title"]
        method = pick_method(tp)
        kind = pn_for(tp)
        pre, steps, expect = body(tp, fx, ex, kind, method)
        n += 1
        seq += 1
        rows.append(
            {
                "id": f"TC-RPT-{n:03d}",
                "tp": tp["id"],
                "code": code or "-",
                "name": name,
                "priority": tp["priority"],
                "method": method,
                "layer": layer,
                "visible": visible,
                "meaning": meaning,
                "formula": method_txt,
                "title": case_title(tp, name, kind, fx),
                "kind": kind,
                "pre": pre,
                "steps": steps,
                "expect": expect,
                "field": path,
                "family": tp["family"],
                "_src": 0,
                "_i": seq,
            }
        )
    return rows, skipped


def tp_by_code_scene() -> dict[tuple[str, str], dict]:
    out = {}
    for p in POINTS["test_points"]:
        if p["family"] == "metric_scenario" and p.get("metric_code"):
            out[(p["metric_code"], p["scenario"])] = p
    return out


def extra_scene_rows(metrics: dict[str, dict]) -> list[dict]:
    idx = tp_by_code_scene()
    rows = []
    for i, sc in enumerate(SCENES):
        tp = idx.get((sc["code"], sc["scene"])) or idx.get((sc["code"], "S1"))
        if not tp:
            continue
        m = metrics[sc["code"]]
        rows.append(
            {
                "id": "",
                "tp": tp["id"],
                "code": sc["code"],
                "name": m["name"],
                "priority": m["priority"] if m["priority"] in {"P0", "P1", "P2"} else "P1",
                "method": sc["method"],
                "layer": m["level"],
                "visible": m["visible"],
                "meaning": m["meaning"],
                "formula": m["method"],
                "title": sc["title"],
                "kind": sc["kind"],
                "pre": sc["pre"],
                "steps": sc["steps"],
                "expect": sc["expect"],
                "field": tp["json_path"],
                "family": "metric_scenario",
                "_src": 1,
                "_i": i,
            }
        )
    return rows


def product_scene_rows() -> list[dict]:
    rows = []
    for i, sc in enumerate(PRODUCT_SCENES):
        meta = PRODUCT_META[sc["code"]]
        rows.append(
            {
                "id": "",
                "tp": f"PROD-{sc['code']}",
                "code": sc["code"],
                "name": meta["name"],
                "priority": meta.get("priority", "P1"),
                "method": sc["method"],
                "layer": meta["layer"],
                "visible": meta.get("visible", "是"),
                "meaning": meta.get("meaning", ""),
                "formula": meta.get("formula", ""),
                "title": sc["title"],
                "kind": sc["kind"],
                "pre": sc["pre"],
                "steps": sc["steps"],
                "expect": sc["expect"],
                "field": meta.get("field", ""),
                "family": "product_scenario",
                "_src": 2,
                "_i": i,
            }
        )
    return rows


def product_metric_order() -> list[str]:
    order: list[str] = []
    seen: set[str] = set()
    for sc in PRODUCT_SCENES:
        code = sc["code"]
        if code not in seen:
            order.append(code)
            seen.add(code)
    return order


def group_and_renumber(
    rows: list[dict], metric_order: list[str], product_order: list[str]
) -> list[dict]:
    """同一指标的用例放一块：先字典顺序，再产品指标，再门控。"""
    order = {c: i for i, c in enumerate(metric_order)}
    prod_order = {c: i for i, c in enumerate(product_order)}
    fam_rank = {"metric_scenario": 0, "product_scenario": 0, "json_gate": 1, "module_status": 2}

    def key(r: dict) -> tuple:
        fam = r.get("family") or ""
        code = r.get("code") or ""
        src = r.get("_src", 0)
        extra_i = r.get("_i", 0)
        if fam == "metric_scenario":
            return (0, order.get(code, 9999), src, extra_i, r.get("title") or "")
        if fam == "product_scenario":
            return (0, 15000 + prod_order.get(code, 9999), src, extra_i, r.get("title") or "")
        return (1, fam_rank.get(fam, 9), r.get("title") or "")

    ordered = sorted(rows, key=key)
    out = []
    for i, r in enumerate(ordered, 1):
        r = dict(r)
        r["id"] = f"TC-RPT-{i:03d}"
        r.pop("_src", None)
        r.pop("_i", None)
        out.append(r)
    return out


def gen_report() -> str:
    return "上传素材，生成复盘报告，等到能打开。"


def numbered(items: list[str]) -> str:
    return "\n".join(f"{i}、{x}" for i, x in enumerate(items, 1) if x)


def check_steps(name: str, value: str) -> str:
    return f"1、{gen_report()}\n2、打开「{name}」，检查是否为{value}。"


COUNT_GIVEN = {
    "total_hands": "视频素材里的手数=n",
    "hands_played": "素材里应计入参与的手数=n",
    "showdown_hands": "素材里摊牌/亮牌的手数=n",
    "folded_pre翻牌_hands": "素材里翻前弃牌的手数=n",
    "post翻牌_hands": "素材里进入翻后的手数=n",
    "winning_hands_count": "素材里盈利手数=n",
    "losing_hands_count": "素材里亏损手数=n",
    "breakeven_hands_count": "素材里打平手数=n",
    "total_decision_points": "素材里 Hero 决策次数=n",
}


def s1_compare(code: str, name: str, typ: str, method: str) -> tuple[str, str]:
    if method == "正交试验法":
        return "2人/6人/9人桌各一场，每场位置名按该人数映射，对应值=n", "n"
    if method == "判定表法" and typ == "T4":
        return "素材里 4 类决策点各至少 1 个，标签已定：符合GTO / 基本可接受 / 风险偏高 / 信息不够", "前置里的标签"
    if code in COUNT_GIVEN:
        return COUNT_GIVEN[code], "n"
    if typ == "T2" or name.endswith("率"):
        return f"素材里分子次数=a，分母次数=b，「{name}」应对=a/b", "a/b"
    if typ in {"T3", "T5"}:
        return f"素材里按口径手算「{name}」=n", "n"
    if typ == "T7":
        return f"素材里满足「{name}」全部条件的条数=n", "n"
    return f"素材里「{name}」应对的值=n", "n"


def video_duration_body(tp: dict) -> tuple[str, str, str]:
    s = tp["scenario"]
    if s == "S1":
        return (
            numbered(["已登录。", "播放器时长=t秒（带到秒，如 12:30=750）"]),
            check_steps("视频时长", "t"),
            "视频时长=t",
        )
    if s == "S2":
        return (
            numbered(["已登录。", "播放器时长=0秒"]),
            check_steps("视频时长", "0"),
            "视频时长=0",
        )
    if s == "S5":
        return (
            numbered(["已登录。", "播放器时长=t秒，且 t>2小时"]),
            check_steps("视频时长", "t"),
            "视频时长=t",
        )
    if s == "S7":
        return (
            numbered(["已登录。", "文件能上传但读不到时长（不是 0 秒）"]),
            check_steps("视频时长", "空或不出现"),
            "视频时长为空或不出现",
        )
    return "", check_steps("视频时长", "t"), tp["pass_criteria"]


def body(tp: dict, fx, ex, kind: str, method: str) -> tuple[str, str, str]:
    s = tp["scenario"]
    name = tp["metric_name"] or tp["title"]
    family = tp["family"]
    code = tp.get("metric_code") or ""
    typ = tp.get("calc_type") or ""

    if family == "json_gate":
        return json_body(tp)
    if family == "module_status":
        return module_body(tp)
    if code == "video_duration":
        return video_duration_body(tp)

    assert fx and ex
    if s == "S1":
        given, value = s1_compare(code, name, typ, method)
        return numbered(["已登录，当前用户是 Hero。只用正例场。", given]), check_steps(name, value), f"{name}={value}"

    if s == "S2":
        is_rate = typ == "T2" or name.endswith("率")
        if typ == "T4":
            given = "边界样本标签已定：频率刚好 30%，或加注额刚好比推荐多/少 30%，对应值=n"
            return numbered(["已登录，当前用户是 Hero。准备下列不该计入的素材。", given]), check_steps(name, "n"), f"{name}=n"
        if typ == "T7":
            half = fx.get("half") or []
            given = "只满足一半条件，应计入条数=0\n" + bullets(half)
            return numbered(["已登录，当前用户是 Hero。准备下列不该计入的素材。", given]), check_steps(name, "0"), f"{name}=0"
        given = neg_given(code, name, is_rate)
        value = "a/b" if is_rate else "n"
        return numbered(["已登录，当前用户是 Hero。准备下列不该计入的素材。", given]), check_steps(name, value), f"{name}={value}"

    if s == "S3":
        if typ == "T7":
            half = fx.get("half") or []
            given = "只满足一半条件，应计入条数=0\n" + bullets(half)
            return numbered(["已登录，当前用户是 Hero。", given]), check_steps(name, "0"), f"{name}=0"
        opp = [x for x in (fx.get("opportunity") or []) if x]
        given_lines = opp + [f"手算分子=a、分母=b，「{name}」应为=a/b"]
        return numbered(["已登录，当前用户是 Hero。"] + given_lines), check_steps(name, "a/b"), f"{name}=a/b"

    if s == "S4":
        zero = fx.get("zero_denom") or "本场分母次数为 0。"
        given = f"{zero}「{name}」应为空或不出现，不能写成 0% 或 100%。"
        return numbered(["已登录，当前用户是 Hero。", given]), check_steps(name, "空或不出现"), f"{name}为空或不出现"

    if s == "S5":
        given = f"汇总「{name}」应对=n，明细按同一口径加总也应=n"
        return numbered(["已登录，当前用户是 Hero。", given]), check_steps(name, "n"), f"{name}=n，且等于明细加总"

    if s == "S6":
        given = f"各手筹码和大盲已记下，按该手换算后「{name}」=n"
        return numbered(["已登录，当前用户是 Hero。", given]), check_steps(name, "n"), f"{name}=n"

    if s == "S7":
        miss = fx.get("missing") or "缺该字段的源数据。"
        given = f"本场缺少「{name}」源数据。{miss}"
        return numbered(["已登录。本条只跑缺失场。", given]), check_steps(name, "空或不出现"), f"{name}为空或不出现"

    if s == "S8":
        given = f"按字典算出「{name}」=n，按 Skill 算出=m，且 n≠m。冲突点：{tp.get('conflict_note')}"
        return numbered(["已登录，当前用户是 Hero。", given]), check_steps(name, "n"), f"{name}=n（字典，不能等于 m）"

    return "", check_steps(name, "n"), tp["pass_criteria"]


def json_body(tp: dict) -> tuple[str, str, str]:
    path = tp["json_path"]
    s = tp["scenario"]
    if s == "G1":
        return (
            numbered(["已登录。", f"自己入座的牌局应有对象「{path}」；登录用户旁观未入座/无关视频不应有完整战绩包"]),
            f"1、{gen_report()}\n2、检查整包是否有「{path}」。\n3、再用旁观未入座/无关视频生成一次，检查不应出现完整战绩包。",
            f"入座场有「{path}」；旁观未入座/无关没有完整战绩包",
        )
    if s == "G2":
        return (
            numbered(["已登录。", "用户可见字段的明细手算值=汇总"]),
            f"1、{gen_report()}\n2、打开用户可见字段，检查是否等于明细手算。",
            "用户可见字段=明细手算",
        )
    return (
        numbered(["已登录。", f"式子左边=右边：{tp['formula']}"]),
        f"1、{gen_report()}\n2、检查该式子是否成立。",
        "等式成立",
    )


def module_body(tp: dict) -> tuple[str, str, str]:
    state = tp["scenario_name"].replace("模块", "")
    spec = MODULE_FIXTURES.get(tp["metric_code"], {})
    inc = spec.get(state, f"素材能让「{tp['metric_name']}」变成 {state}")
    name = tp["metric_name"] + "状态"
    return (
        numbered(["已登录。", f"{inc}。本场该模块状态应对={state}"]),
        check_steps(name, state),
        f"{name}={state}",
    )


def style_top(ws, title: str, intro: str, note: str) -> None:
    last = get_column_letter(len(HEADERS))
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
    ws.row_dimensions[3].height = 40
    for col, h in enumerate(HEADERS, 1):
        cell = ws.cell(4, col, h)
        cell.fill = FILL_HEAD
        cell.font = FONT_HEAD
        cell.alignment = CENTER
        cell.border = THIN
    ws.row_dimensions[4].height = 28
    ws.freeze_panes = "D5"
    ws.sheet_view.showGridLines = False


def write_excel(rows: list[dict], skipped: list[dict] | None = None) -> Path:
    wb = Workbook()
    sheet = wb.active
    sheet.title = "测试用例"
    style_top(
        sheet,
        "测试用例",
        "表头含数据层级、是否用户可见、字典原文、测试用例标题、正/反例、前置条件、测试步骤、预期结果、对应字段；末三列为执行状态、时间、备注。",
        "前置写清对比数据（如手数=n）。步骤和预期只对目标。执行状态/时间/备注由测试人员填写；勿手改其它列。",
    )
    for r, row in enumerate(rows, 5):
        vals = [
            row["id"],
            row["code"],
            row["name"],
            row["priority"],
            row["method"],
            row["layer"],
            row["visible"],
            row["meaning"],
            row["formula"],
            row["title"],
            row["kind"],
            row["pre"],
            row["steps"],
            row["expect"],
            row["field"],
            "未执行",
            "",
            "",
        ]
        exec_status_col = len(HEADERS) - 2
        exec_time_col = len(HEADERS) - 1
        remark_col = len(HEADERS)
        for c, v in enumerate(vals, 1):
            cell = sheet.cell(r, c, v)
            cell.alignment = WRAP
            cell.border = THIN
            cell.font = Font(name="Microsoft YaHei", size=9)
            if c <= 4:
                cell.fill = FILL_ID
            if c == 4:
                if row["priority"] == "P0":
                    cell.fill = FILL_P0
                elif row["priority"] == "P1":
                    cell.fill = FILL_P1
                cell.alignment = CENTER
            if c in {5, 6, 7, 11, exec_status_col, exec_time_col}:
                cell.alignment = CENTER
            if c == 11:
                cell.fill = FILL_POS if row["kind"] == "正例" else FILL_NEG
            if c in {exec_status_col, exec_time_col, remark_col}:
                cell.fill = FILL_EXEC
        sheet.row_dimensions[r].height = 72
    status_col = get_column_letter(len(HEADERS) - 2)
    dv = DataValidation(
        type="list",
        formula1=f'"{",".join(EXEC_STATUS_OPTIONS)}"',
        allow_blank=True,
    )
    dv.error = "请从下拉选择：未执行 / 通过 / 失败 / 阻塞 / 跳过"
    dv.errorTitle = "执行状态"
    sheet.add_data_validation(dv)
    dv.add(f"{status_col}5:{status_col}{4+len(rows)}")
    last = get_column_letter(len(HEADERS))
    sheet.auto_filter.ref = f"A4:{last}{4+len(rows)}"
    widths = [12, 24, 14, 8, 14, 12, 12, 26, 32, 32, 8, 32, 42, 42, 32, 10, 14, 28]
    for i, w in enumerate(widths, 1):
        sheet.column_dimensions[get_column_letter(i)].width = w

    write_metric_stats_sheet(
        wb, rows, [m["code"] for m in load_source()[0]], product_metric_order()
    )

    out = ROOT / "指标测试用例.xlsx"
    wb.save(out)
    return out


def write_metric_stats_sheet(
    wb: Workbook,
    rows: list[dict],
    metric_order: list[str],
    product_order: list[str],
) -> None:
    ws = wb.create_sheet("指标用例统计")
    style_top(
        ws,
        "各指标测试用例数量统计",
        f"基于「测试用例」表汇总。批次 {BATCH}  v{VERSION}",
        f"用例总数 {len(rows)} 条（正例 {sum(1 for r in rows if r['kind'] == '正例')}，反例 {sum(1 for r in rows if r['kind'] == '反例')}）。G列起为执行进度（联动测试用例表）。",
    )
    headers = ["指标编码", "中文名称", "数据层级", "优先级", "正例", "反例", "合计"]
    for c, h in enumerate(headers, 1):
        cell = ws.cell(4, c, h)
        cell.fill = FILL_HEAD
        cell.font = FONT_HEAD
        cell.alignment = CENTER
        cell.border = THIN

    tallies: dict[str, dict] = {}
    for r in rows:
        code = r.get("code") or "-"
        if code == "-":
            fam = r.get("family") or "other"
            code = f"__{fam}"
            default_name = {
                "json_gate": "JSON整包门控",
                "module_status": "模块状态门控",
            }.get(fam, "非指标用例")
            name = default_name
            layer = ""
        else:
            name = r.get("name") or code
            layer = r.get("layer") or ""
        t = tallies.setdefault(
            code,
            {
                "name": name,
                "layer": layer,
                "priority": r.get("priority") or "",
                "pos": 0,
                "neg": 0,
            },
        )
        if not t["name"]:
            t["name"] = name
        if not t["layer"] and layer:
            t["layer"] = layer
        if r.get("kind") == "正例":
            t["pos"] += 1
        else:
            t["neg"] += 1

    order = [c for c in metric_order if c in tallies]
    order += [c for c in product_order if c in tallies]
    order += sorted(c for c in tallies if c not in order and not c.startswith("__"))
    order += sorted(c for c in tallies if c.startswith("__"))

    row_i = 5
    sum_pos = sum_neg = 0
    for code in order:
        t = tallies[code]
        total = t["pos"] + t["neg"]
        sum_pos += t["pos"]
        sum_neg += t["neg"]
        vals = [
            code if not code.startswith("__") else "",
            t["name"],
            t["layer"],
            t["priority"],
            t["pos"],
            t["neg"],
            total,
        ]
        for c, v in enumerate(vals, 1):
            cell = ws.cell(row_i, c, v)
            cell.alignment = CENTER if c in {4, 5, 6, 7} else WRAP
            cell.border = THIN
            cell.font = Font(name="Microsoft YaHei", size=9)
            if c == 4 and v == "P0":
                cell.fill = FILL_P0
            elif c == 4 and v == "P1":
                cell.fill = FILL_P1
        ws.row_dimensions[row_i].height = 22
        row_i += 1

    for c, v in enumerate(["合计", "", "", "", sum_pos, sum_neg, sum_pos + sum_neg], 1):
        cell = ws.cell(row_i, c, v)
        cell.fill = FILL_INTRO
        cell.font = Font(bold=True, name="Microsoft YaHei", size=9)
        cell.alignment = CENTER if c >= 4 else WRAP
        cell.border = THIN
    ws.row_dimensions[row_i].height = 24

    ws.auto_filter.ref = f"A4:G{row_i - 1}"
    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 32
    ws.column_dimensions["C"].width = 14
    ws.column_dimensions["D"].width = 10
    ws.column_dimensions["E"].width = 8
    ws.column_dimensions["F"].width = 8
    ws.column_dimensions["G"].width = 8
    ws.freeze_panes = "A5"

    # 执行进度与数据层级（联动「测试用例」sheet）
    data_end = 4 + len(rows)
    case_ref = "'测试用例'"
    status_range = f"{case_ref}!$P$5:$P${data_end}"
    id_range = f"{case_ref}!$A$5:$A${data_end}"

    ws["G4"] = "执行进度"
    ws["H4"] = "数量"
    ws["G4"].fill = FILL_HEAD
    ws["H4"].fill = FILL_HEAD
    ws["G4"].font = FONT_HEAD
    ws["H4"].font = FONT_HEAD
    exec_rows = [
        ("未执行", f"=COUNTIF({status_range},\"未执行\")+COUNTBLANK({status_range})"),
        ("通过", f"=COUNTIF({status_range},\"通过\")"),
        ("失败", f"=COUNTIF({status_range},\"失败\")"),
        ("阻塞", f"=COUNTIF({status_range},\"阻塞\")"),
        ("跳过", f"=COUNTIF({status_range},\"跳过\")"),
        ("合计", f"=COUNTA({id_range})"),
    ]
    for i, (label, formula) in enumerate(exec_rows, 5):
        ws.cell(i, 7, label)
        c = ws.cell(i, 8)
        c.value = formula
        c.font = Font(name="Microsoft YaHei", size=9)
        c.border = THIN
        c.alignment = CENTER
        ws.cell(i, 7).border = THIN
        ws.cell(i, 7).font = Font(name="Microsoft YaHei", size=9)
    ws["G11"] = "完成率"
    ws["H11"] = f"=IF(H10=0,0,(H10-H5)/H10)"
    ws["G11"].font = Font(bold=True, name="Microsoft YaHei", size=9)
    ws["H11"].font = Font(bold=True, name="Microsoft YaHei", size=9)
    ws["H11"].number_format = "0.0%"

    layer_counts: Counter[str] = Counter()
    for r in rows:
        layer_counts[r.get("layer") or "未标注"] += 1
    ws["G13"] = "数据层级"
    ws["H13"] = "用例数"
    ws["G13"].fill = FILL_HEAD
    ws["H13"].fill = FILL_HEAD
    ws["G13"].font = FONT_HEAD
    ws["H13"].font = FONT_HEAD
    lr = 14
    for layer, cnt in sorted(layer_counts.items(), key=lambda x: (-x[1], x[0])):
        ws.cell(lr, 7, layer)
        ws.cell(lr, 8, cnt)
        ws.cell(lr, 7).border = THIN
        ws.cell(lr, 8).border = THIN
        ws.cell(lr, 7).font = Font(name="Microsoft YaHei", size=9)
        ws.cell(lr, 8).font = Font(name="Microsoft YaHei", size=9)
        ws.cell(lr, 8).alignment = CENTER
        lr += 1

    ws.column_dimensions["H"].width = 12


def main() -> None:
    metrics, _obj, _mod = load_source()
    by = {m["code"]: m for m in metrics}
    rows, skipped = method_cases(by)
    rows.extend(extra_scene_rows(by))
    rows.extend(product_scene_rows())
    prod_order = product_metric_order()
    rows = group_and_renumber(rows, [m["code"] for m in metrics], prod_order)
    tps = {p["id"] for p in POINTS["test_points"]}
    covered = {r["tp"] for r in rows}
    skip_ids = {s["tp"] for s in skipped}
    missing = sorted(tps - covered - skip_ids)
    if missing:
        raise SystemExit(f"测试点未覆盖: {missing[:10]}")
    unknown = covered - tps
    unknown = {t for t in unknown if not str(t).startswith("PROD-")}
    if unknown:
        raise SystemExit(f"用例挂了不存在的测试点: {list(unknown)[:5]}")
    path = write_excel(rows, skipped)
    payload = {
        "batchId": BATCH,
        "version": VERSION,
        "status": "ready_for_review",
        "counts": {
            "test_points": len(tps),
            "cases": len(rows),
            "skipped": len(skipped),
            "positive": sum(1 for r in rows if r["kind"] == "正例"),
            "negative": sum(1 for r in rows if r["kind"] == "反例"),
            "methods": dict(Counter(r["method"] for r in rows)),
        },
        "skipped": skipped,
        "cases": [
            {
                "id": r["id"],
                "testPointIds": [r["tp"]],
                "title": r["title"],
                "priority": r["priority"],
                "type": "negative" if r["kind"] == "反例" else "functional",
                "level": "api",
                "preconditions": [r["pre"]] if r["pre"] else [],
                "testData": [f"method={r['method']}", f"field={r['field']}"],
                "environment": [
                    "可生成复盘报告并取整包 JSON",
                    "当前用户=Hero",
                    "口径以指标字典为准",
                ],
                "steps": [
                    {"action": r["steps"], "expectedResult": r["expect"]},
                ],
                "status": "ready_for_review",
                "version": VERSION,
                "batchId": BATCH,
                "automationCandidate": True,
            }
            for r in rows
        ],
    }
    (ROOT / "test-cases.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("cases", len(rows), Counter(r["kind"] for r in rows))
    print("skipped", len(skipped))
    print("methods", Counter(r["method"] for r in rows))
    print("wrote", path)


if __name__ == "__main__":
    main()
