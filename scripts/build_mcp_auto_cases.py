#!/usr/bin/env python3
"""从 MCP 专项测试用例表生成「自动化请求用例」Excel。

产出 3 个核心 sheet，供后续 Python 直连 MCP POST：
  - config   全局参数（URL/open_id/时间，不含 token 明文）
  - cases    用例元数据（1 case 1 行）
  - requests 可执行请求（1 step 1 行，含完整 JSON-RPC body）

用法：
  python3 scripts/build_mcp_auto_cases.py \\
    --source "/Users/xixi/Downloads/MCP专项测试用例_含边界补充（适应郑秀雨数据版）.xlsx" \\
    --out "/Users/xixi/Downloads/MCP自动化请求用例_郑秀雨.xlsx"
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

# 郑秀雨对照集固定参数
OPEN_ID = "1ad0c14143ae4d12894c41c89e603e94"
TODAY_START = "2026-10-22 00:00:00"
TODAY_END = "2026-10-22 23:59:59"
YDAY_START = "2026-10-21 00:00:00"
YDAY_END = "2026-10-21 23:59:59"
SESSION_ID = "1792639765135"
HAND_LOSS = "1792639765135_QHTH_1792640896015"  # 第21手 最大亏
HAND_WIN = "1792639765135_9HQH_1792640971544"  # 第24手附近样本
HAND_2ND_LOSS = "1792639765135_3CAC_1792640325740"
HAND_PAIR = "1792639765135_7C7S_1792640324776"
OPP_MAIN = "Keppel"
OPP_LOW = "日月明F88"
OPP_MID = "Surfer99"

TOOL_RE = re.compile(
    r"(tool_[a-z_]+|opponent_profile|list_metrics|query_metrics|run_sql|describe_tables)"
)

# 非直连 tools/call 的分组 → skip/manual
SKIP_GROUP_PREFIXES = (
    "3.3 ",  # 故障开关
    "3.5 ",  # 会话串扰（偏 Agent）
    "3.6 ",  # 注入/越狱（偏 Agent）
    "3.8 ",  # 传输层专项
    "3.9 ",  # 协议层专项
    "3.11",  # Agent-MCP 集成
)


def rpc_body(tool: str, arguments: dict[str, Any], req_id: int = 3) -> str:
    return json.dumps(
        {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments},
        },
        ensure_ascii=False,
        indent=2,
    )


def overview(start: str, end: str) -> dict[str, Any]:
    return {"open_id": "{{open_id}}", "time_start": start, "time_end": end}


def sessions(start: str, end: str, limit: int = 20) -> dict[str, Any]:
    return {
        "open_id": "{{open_id}}",
        "time_start": start,
        "time_end": end,
        "limit": limit,
    }


def find_hands(
    *,
    start: str = TODAY_START,
    end: str = TODAY_END,
    hole_cards: str = "",
    order_by: str = "profit_bb",
    sort_order: str = "desc",
    limit: int = 10,
    offset: int = 0,
) -> dict[str, Any]:
    return {
        "open_id": "{{open_id}}",
        "time_start": start,
        "time_end": end,
        "hole_cards": hole_cards,
        "order_by": order_by,
        "sort_order": sort_order,
        "limit": limit,
        "offset": offset,
    }


def hand_detail(hand_id: str) -> dict[str, Any]:
    return {"open_id": "{{open_id}}", "hand_id": hand_id}


def opponent(name: str = OPP_MAIN) -> dict[str, Any]:
    return {"open_id": "{{open_id}}", "opponent_name": name}


def user_metrics(
    metrics: list[str],
    *,
    start: str = TODAY_START,
    end: str = TODAY_END,
    dimensions: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "open_id": "{{open_id}}",
        "time_start": start,
        "time_end": end,
        "metrics": json.dumps(metrics, ensure_ascii=False),
        "ad_hoc_json": "[]",
        "dimensions": json.dumps(dimensions or [], ensure_ascii=False),
        "filters": "{}",
        "limit": 1000,
    }


def query_metrics(metrics: list[str], session_id: str = SESSION_ID) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "metrics": json.dumps(metrics, ensure_ascii=False),
        "dimensions": "[]",
        "filters": "{}",
        "ad_hoc_json": "[]",
        "page": 0,
        "page_size": 0,
    }


def list_metrics(category: str = "") -> dict[str, Any]:
    return {"category": category}


def extract_question(steps: str) -> str:
    if not steps:
        return ""
    m = re.search(r"输入[:：]\s*(.+)", steps)
    if not m:
        return ""
    return m.group(1).strip().split("\n")[0].strip()


def extract_assert_hints(expected: str) -> str:
    if not expected:
        return ""
    lines = []
    for line in str(expected).splitlines():
        s = line.strip()
        if "数据基准" in s or s.startswith("【") or "场次" in s or "BB" in s:
            lines.append(s)
        if len(lines) >= 4:
            break
    if not lines:
        # fallback first 2 non-empty
        lines = [ln.strip() for ln in str(expected).splitlines() if ln.strip()][:2]
    return "\n".join(lines)


def run_mode_for(group: str, module: str, tools: list[str]) -> tuple[str, str]:
    g = str(group or "")
    for p in SKIP_GROUP_PREFIXES:
        if g.startswith(p):
            return "skip", f"分组 {g} 需 Agent/故障开关/协议层，不直连 tools/call"
    if "故障" in str(module) or "超时" in str(module):
        return "skip", "依赖故障开关"
    if not tools and "3.1" not in g and "3.4" not in g and "3.7" not in g:
        return "manual", "预期未写明工具"
    if "3.4" in g:
        return "auto", "空结果场景，仍直连验证"
    if "3.7" in g:
        return "auto", ""
    return "auto", ""


def pick_time_range(title: str, question: str, expected: str) -> tuple[str, str, str]:
    """返回 (label, start, end)。label=today/yesterday/both。"""
    q = question or ""
    blob = f"{title}\n{q}\n{expected}"
    has_yday = any(x in blob for x in ("昨天", "昨日", "10-21", "10 月 21", "10月21"))
    has_today = any(x in blob for x in ("今天", "今日", "10-22", "10 月 22", "10月22", "本场"))
    # 问句本身只问昨天 → 昨天
    if any(x in q for x in ("昨天", "昨日")) and not any(x in q for x in ("今天", "今日")):
        return "yesterday", YDAY_START, YDAY_END
    if has_yday and has_today and (
        "必须不同" in blob or "不能算成" in blob or "互相串" in blob or "然后再问昨天" in blob
    ):
        return "both", TODAY_START, TODAY_END
    if has_yday and not has_today:
        return "yesterday", YDAY_START, YDAY_END
    if "昨天" in blob and ("空" in blob or "0 场" in blob or "0场" in blob or "0 手" in blob):
        return "yesterday", YDAY_START, YDAY_END
    return "today", TODAY_START, TODAY_END


def unique_tools(tools: list[str], module: str) -> list[str]:
    out: list[str] = []
    for t in tools:
        if t not in out:
            out.append(t)
    if out:
        return out
    # fallback from module column
    m = str(module or "")
    for name in (
        "tool_get_user_overview",
        "tool_list_user_sessions",
        "tool_query_user_metrics",
        "tool_find_hands",
        "tool_get_hand_detail",
        "tool_get_snowie_advice",
        "opponent_profile",
        "list_metrics",
        "query_metrics",
        "run_sql",
        "describe_tables",
    ):
        if name in m:
            out.append(name)
    return out


def build_steps_for_case(
    case_id: str,
    title: str,
    module: str,
    expected: str,
    question: str,
    tools: list[str],
) -> list[dict[str, Any]]:
    """按用例推断 requests 行。"""
    tools = unique_tools(tools, module)
    blob = f"{title}\n{question}\n{expected}\n{module}"
    time_label, t0, t1 = pick_time_range(title, question, expected)
    steps: list[dict[str, Any]] = []

    def add(
        tool: str,
        args: dict[str, Any],
        *,
        role: str = "preferred",
        enabled: str = "Y",
        extract: str = "",
        depends_on: str = "",
        assert_type: str = "contains",
        assert_expr: str = "",
        notes: str = "",
    ) -> None:
        steps.append(
            {
                "tool_name": tool,
                "role": role,
                "enabled": enabled,
                "request_body": rpc_body(tool, args, req_id=3 + len(steps)),
                "depends_on": depends_on,
                "extract": extract,
                "assert_type": assert_type,
                "assert_expr": assert_expr,
                "notes": notes,
            }
        )

    # —— 明确复合链 ——
    if "→" in module or "复合" in title or case_id in {"M3-66", "M3-67", "M3-68"}:
        if case_id == "M3-66" or ("find_hands" in module and "hand_detail" in module and "×3" not in module):
            add(
                "tool_find_hands",
                find_hands(hole_cards="A", limit=10),
                extract="hand_id",
                assert_expr="matched_count",
                notes="找带 A 的牌，抽出第一手 hand_id",
            )
            add(
                "tool_get_hand_detail",
                hand_detail("{{hand_id}}"),
                role="chain",
                depends_on=f"{case_id}#1.hand_id",
                notes="用上一步 hand_id 查牌谱",
            )
            return steps
        if case_id == "M3-68" or "×3" in module:
            add(
                "tool_find_hands",
                find_hands(order_by="profit_bb", sort_order="asc", limit=3),
                extract="hand_ids",
                notes="最亏 3 手",
            )
            for idx, (hid, label) in enumerate(
                [
                    (HAND_LOSS, "最亏第1手（已知样本，可被 extract 覆盖）"),
                    (HAND_2ND_LOSS, "最亏第2手"),
                    ("{{hand_id_3}}", "最亏第3手（脚本从 step1 列表取）"),
                ],
                start=1,
            ):
                add(
                    "tool_get_hand_detail",
                    hand_detail(hid),
                    role="chain",
                    depends_on=f"{case_id}#1",
                    notes=label,
                )
            return steps
        if case_id == "M3-67":
            add(
                "tool_query_user_metrics",
                user_metrics(["profit_by_position"], dimensions=["by_position"]),
                notes="按位置盈亏",
            )
            add(
                "tool_find_hands",
                find_hands(order_by="profit_bb", sort_order="asc", limit=10),
                role="chain",
                extract="hand_id",
                notes="找亏的手（HJ）",
            )
            add(
                "tool_get_hand_detail",
                hand_detail("{{hand_id}}"),
                role="chain",
                depends_on=f"{case_id}#2.hand_id",
            )
            return steps

    # —— OR 关系：overview 或 find_hands ——
    if "或" in expected and len(tools) >= 2:
        primary, alt = tools[0], tools[1]
        if primary == "tool_get_user_overview":
            add(primary, overview(t0, t1), role="preferred", notes="主路径")
        elif primary == "tool_find_hands":
            add(
                primary,
                find_hands(sort_order="asc", limit=5),
                role="preferred",
                notes="主路径：按盈亏升序找最亏",
            )
        else:
            add(primary, overview(t0, t1), role="preferred")
        if alt == "tool_find_hands":
            add(
                alt,
                find_hands(sort_order="asc", limit=5),
                role="alt",
                enabled="N",
                notes="备选路径，默认不跑；脚本 --include-alt 时启用",
            )
        elif alt == "tool_get_user_overview":
            add(alt, overview(t0, t1), role="alt", enabled="N", notes="备选")
        else:
            add(alt, overview(t0, t1), role="alt", enabled="N")
        return steps

    # —— 昨天+今天对比（仅单工具 overview 时拆两步）——
    if tools == ["tool_get_user_overview"] and (
        time_label == "both"
        or ("今天" in blob and "昨天" in blob)
    ):
        add(
            "tool_get_user_overview",
            overview(TODAY_START, TODAY_END),
            assert_expr="hands==27",
            notes="今天",
        )
        add(
            "tool_get_user_overview",
            overview(YDAY_START, YDAY_END),
            assert_expr="hands==0",
            notes="昨天，应与今天不同",
        )
        return steps

    # —— 多工具且非 OR：按 tools 顺序各一步 ——
    if len(tools) >= 2:
        for t in tools:
            if t == "tool_get_user_overview":
                add(t, overview(t0, t1))
            elif t == "tool_list_user_sessions":
                add(t, sessions(t0, t1))
            elif t == "tool_find_hands":
                so = "asc" if any(x in blob for x in ("输最多", "最亏", "亏损")) else "desc"
                hole = ""
                if "带 A" in blob or "带A" in blob:
                    hole = "A"
                elif "对子" in blob:
                    hole = "22+"  # 口语；服务端若只认简写可再改
                add(t, find_hands(start=t0, end=t1, hole_cards=hole, sort_order=so))
            elif t == "tool_get_hand_detail":
                add(t, hand_detail(HAND_LOSS))
            elif t == "opponent_profile":
                name = OPP_LOW if "日月明" in blob else OPP_MAIN
                if "Surfer" in blob:
                    name = OPP_MID
                add(t, opponent(name))
            elif t == "tool_query_user_metrics":
                mets = ["vpip_rate", "pfr_rate", "three_bet_rate"]
                add(t, user_metrics(mets, start=t0, end=t1))
            elif t == "list_metrics":
                add(t, list_metrics("打法画像"))
            elif t == "query_metrics":
                add(t, query_metrics(["vpip_rate"]))
            else:
                add(t, overview(t0, t1), notes=f"未特化参数的工具 {t}")
        return steps

    # —— 单工具 ——
    tool = tools[0] if tools else ""
    if not tool:
        # 3.4 空数据等：默认 overview 昨天或假对手
        if "查无" in blob or "没有交手" in blob:
            add(
                "opponent_profile",
                opponent("不存在的对手XYZ"),
                notes="期望空/无记录",
                assert_expr="empty_or_zero",
            )
        else:
            add(
                "tool_get_user_overview",
                overview(t0, t1),
                notes="工具未解析到，默认 overview",
                enabled="N",
            )
        return steps

    if tool == "tool_get_user_overview":
        add(
            tool,
            overview(t0, t1),
            assert_expr="hands" if time_label == "today" else "session_count==0",
            notes=time_label,
        )
    elif tool == "tool_list_user_sessions":
        add(tool, sessions(t0, t1), assert_expr="session_count")
    elif tool == "tool_find_hands":
        hole = ""
        so = "desc"
        limit = 10
        if "带 A" in blob or "带A" in blob:
            hole = "A"
        elif "对子" in blob or "口袋对" in blob:
            hole = "22"
        elif "同花" in blob:
            hole = "AKs"
        elif "AK" in blob:
            hole = "AK"
        if any(x in blob for x in ("输最多", "最亏", "输超过", "亏损")):
            so = "asc"
        note = f"hole={hole or '(空)'} sort={so}"
        if "超过 50" in blob or "超过50" in blob:
            so = "asc"
            limit = 50
            note = "脚本侧可再按 profit_bb<=-50 过滤；MCP 参数以 hole/order 为主"
        add(
            tool,
            find_hands(start=t0, end=t1, hole_cards=hole, sort_order=so, limit=limit),
            notes=note,
        )
    elif tool == "tool_get_hand_detail":
        hid = HAND_WIN if ("赢最多" in blob or "9h" in blob or "9H" in blob) else HAND_LOSS
        if HAND_WIN.split("_")[1] in blob.upper().replace("QH9H", "9HQH"):
            hid = HAND_WIN
        if "QHTH" in blob.upper() or "QhTh" in blob:
            hid = HAND_LOSS
        add(tool, hand_detail(hid), assert_expr="hand_id")
    elif tool == "tool_get_snowie_advice":
        add(
            tool,
            {
                "open_id": "{{open_id}}",
                "hand_id": HAND_LOSS,
                "action_index": 1,
            },
        )
    elif tool == "opponent_profile":
        name = OPP_MAIN
        if "日月明" in blob:
            name = OPP_LOW
        elif "Surfer" in blob:
            name = OPP_MID
        elif "空" in title or "查无" in blob:
            name = ""
        add(tool, opponent(name), assert_expr="opponent")
    elif tool == "tool_query_user_metrics":
        mets = ["vpip_rate", "pfr_rate", "three_bet_rate"]
        dims: list[str] = []
        if "CBet" in blob or "cbet" in blob.lower() or "翻后" in blob:
            mets = ["cbet_flop_rate", "turn_barrel_rate", "river_bet_rate"]
        elif "盲" in blob and "防守" in blob:
            mets = ["bb_defense_rate", "sb_defense_rate"]
        elif "4bet" in blob.lower() or "limp" in blob.lower():
            mets = [
                "vpip_rate",
                "pfr_rate",
                "three_bet_rate",
                "four_bet_rate",
                "limp_rate",
            ]
        elif "摊牌" in blob:
            mets = ["showdown_rate", "showdown_win_rate"]
        elif "BB/100" in blob or "bb_per_100" in blob:
            mets = ["bb_per_100", "total_profit_bb"]
        elif "位置" in blob or "BTN" in blob or "CO" in blob or "HJ" in blob:
            mets = ["vpip_by_position", "profit_by_position"]
            dims = ["by_position"]
        elif "多人" in blob or "全下" in blob:
            mets = ["multiway_pot_rate", "all_in_hand_rate", "showdown_rate"]
        add(tool, user_metrics(mets, start=t0, end=t1, dimensions=dims or None))
    elif tool == "list_metrics":
        # 不带 category 会截断；样例默认打法画像，全量由脚本循环 category
        cat = "打法画像"
        if "GTO" in blob:
            cat = "GTO决策"
        elif "盈亏" in blob:
            cat = "盈亏EV"
        add(tool, list_metrics(cat), notes="全量目录请对 8 个 category 循环")
    elif tool == "query_metrics":
        mets = ["river_bet_rate"] if "河牌" in blob else ["vpip_rate"]
        add(tool, query_metrics(mets))
    elif tool == "run_sql":
        add(
            tool,
            {
                "open_id": "{{open_id}}",
                "sql": "SELECT count() AS n FROM texas_hand_detail WHERE open_id = %(open_id)s",
            },
        )
    elif tool == "describe_tables":
        add(tool, {"table": "texas_hand_detail"})
    else:
        add(tool, overview(t0, t1), notes="fallback overview args")

    return steps


def load_source_cases(path: Path) -> list[dict[str, Any]]:
    wb = load_workbook(path, data_only=True)
    ws = wb["MCP专项"]
    rows: list[dict[str, Any]] = []
    for r in range(2, ws.max_row + 1):
        case_id = ws.cell(r, 1).value
        if not case_id:
            continue
        expected = ws.cell(r, 7).value or ""
        steps = ws.cell(r, 14).value or ""
        tools = TOOL_RE.findall(str(expected))
        rows.append(
            {
                "case_id": str(case_id).strip(),
                "group": ws.cell(r, 2).value or "",
                "title": ws.cell(r, 3).value or "",
                "module": ws.cell(r, 4).value or "",
                "priority": ws.cell(r, 5).value or "",
                "status": ws.cell(r, 6).value or "",
                "expected": expected,
                "question": extract_question(str(steps)),
                "pre": ws.cell(r, 13).value or "",
                "remark": ws.cell(r, 16).value or "",
                "tools": tools,
                "assert_hints": extract_assert_hints(str(expected)),
            }
        )
    return rows


def style_header(ws, fill_color: str = "1F4E79") -> None:
    fill = PatternFill("solid", fgColor=fill_color)
    font = Font(color="FFFFFF", bold=True)
    for cell in ws[1]:
        cell.fill = fill
        cell.font = font
        cell.alignment = Alignment(wrap_text=True, vertical="center")


def autosize(ws, max_width: int = 60) -> None:
    for col in ws.columns:
        letter = get_column_letter(col[0].column)
        width = 10
        for cell in col[:80]:
            if cell.value is None:
                continue
            width = max(width, min(max_width, len(str(cell.value).split("\n")[0]) + 2))
        ws.column_dimensions[letter].width = width


def write_excel(cases: list[dict[str, Any]], out: Path) -> dict[str, int]:
    wb = Workbook()

    # —— readme ——
    ws0 = wb.active
    ws0.title = "readme"
    readme_lines = [
        ["MCP 自动化请求用例（郑秀雨数据版）"],
        [],
        ["用法"],
        ["1. 改 config 里的 base_url；token 用环境变量 MCP_TOKEN，不要写进表"],
        ["2. Python 读取 requests 中 enabled=Y 的行，按 case_id + step_no 顺序 POST"],
        ["3. 先 initialize 拿 mcp-session-id，再带 Header 发 tools/call"],
        ["4. Body 用 request_body；替换 {{open_id}}/{{hand_id}} 等占位符"],
        ["5. role=alt 默认不跑；需要覆盖 OR 备选路径时加 --include-alt"],
        ["6. run_mode=skip/manual 的 case 不进自动执行"],
        [],
        ["占位符"],
        ["{{open_id}}", "来自 config.default_open_id"],
        ["{{hand_id}}", "来自上一步 extract，或写死的 hand_id"],
        ["{{hand_id_3}}", "find_hands 返回列表第 3 个"],
        ["{{time_start}} / {{time_end}}", "可选，当前样例多数已写死日期"],
        [],
        ["Sheet 说明"],
        ["config", "全局配置"],
        ["cases", "用例元数据"],
        ["requests", "自动化主入参：完整 JSON-RPC POST body"],
    ]
    for row in readme_lines:
        ws0.append(row)
    ws0["A1"].font = Font(bold=True, size=14)

    # —— config ——
    ws_cfg = wb.create_sheet("config")
    ws_cfg.append(["key", "value", "note"])
    config_rows = [
        ("base_url", "https://d943-223-70-117-10.ngrok-free.app/mcp", "ngrok 会变，跑前改"),
        ("token_env", "MCP_TOKEN", "Authorization: Bearer $MCP_TOKEN"),
        ("default_open_id", OPEN_ID, "郑秀雨对照 open_id"),
        ("day_today_start", TODAY_START, "东八区"),
        ("day_today_end", TODAY_END, ""),
        ("day_yesterday_start", YDAY_START, ""),
        ("day_yesterday_end", YDAY_END, ""),
        ("default_session_id", SESSION_ID, "query_metrics 用"),
        ("sample_hand_loss", HAND_LOSS, "最大亏 QhTh"),
        ("sample_hand_win", HAND_WIN, "样本赢手"),
        ("sample_opponent", OPP_MAIN, ""),
        ("concurrency", "1", "建议串行"),
        ("timeout_sec", "30", ""),
        ("protocol_version", "2024-11-05", "initialize 用"),
    ]
    for row in config_rows:
        ws_cfg.append(list(row))
    style_header(ws_cfg, "2E7D32")
    autosize(ws_cfg)

    # —— cases / requests ——
    ws_cases = wb.create_sheet("cases")
    case_headers = [
        "case_id",
        "group",
        "title",
        "priority",
        "run_mode",
        "skip_reason",
        "expect_tools",
        "user_question",
        "assert_hints",
        "source_module",
        "remark",
    ]
    ws_cases.append(case_headers)

    ws_req = wb.create_sheet("requests")
    req_headers = [
        "case_id",
        "step_no",
        "enabled",
        "tool_name",
        "role",
        "method",
        "request_body",
        "depends_on",
        "extract",
        "assert_type",
        "assert_expr",
        "notes",
    ]
    ws_req.append(req_headers)

    stats = {"cases": 0, "auto": 0, "skip": 0, "manual": 0, "request_rows": 0, "enabled_rows": 0}

    for c in cases:
        mode, reason = run_mode_for(c["group"], c["module"], c["tools"])
        tools = unique_tools(c["tools"], c["module"])
        expect_tools = "|".join(tools) if tools else ""
        # OR 标记
        if "或" in str(c["expected"]) and len(tools) >= 2:
            expect_tools = f"{tools[0]}|{tools[1]}(OR)"

        ws_cases.append(
            [
                c["case_id"],
                c["group"],
                c["title"],
                str(c["priority"]),
                mode,
                reason,
                expect_tools,
                c["question"],
                c["assert_hints"],
                c["module"],
                c["remark"],
            ]
        )
        stats["cases"] += 1
        stats[mode] = stats.get(mode, 0) + 1

        if mode != "auto":
            continue

        steps = build_steps_for_case(
            c["case_id"],
            c["title"],
            c["module"],
            str(c["expected"]),
            c["question"],
            tools,
        )
        for i, st in enumerate(steps, start=1):
            enabled = st["enabled"]
            ws_req.append(
                [
                    c["case_id"],
                    i,
                    enabled,
                    st["tool_name"],
                    st["role"],
                    "tools/call",
                    st["request_body"],
                    st.get("depends_on", ""),
                    st.get("extract", ""),
                    st.get("assert_type", "contains"),
                    st.get("assert_expr", ""),
                    st.get("notes", ""),
                ]
            )
            stats["request_rows"] += 1
            if enabled == "Y":
                stats["enabled_rows"] += 1

    style_header(ws_cases)
    style_header(ws_req, "6A1B9A")
    autosize(ws_cases, 40)
    ws_req.column_dimensions["G"].width = 50  # request_body
    for row in ws_req.iter_rows(min_row=2, min_col=7, max_col=7):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")

    # —— 统计摘要写到 readme 底部 ——
    ws0.append([])
    ws0.append(["生成统计"])
    for k, v in stats.items():
        ws0.append([k, v])

    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description="生成 MCP 自动化请求用例 Excel")
    ap.add_argument(
        "--source",
        type=Path,
        default=Path(
            "/Users/xixi/Downloads/MCP专项测试用例_含边界补充（适应郑秀雨数据版）.xlsx"
        ),
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=Path("/Users/xixi/Downloads/MCP自动化请求用例_郑秀雨.xlsx"),
    )
    args = ap.parse_args()
    if not args.source.exists():
        raise SystemExit(f"找不到源表: {args.source}")
    cases = load_source_cases(args.source)
    stats = write_excel(cases, args.out)
    print(f"wrote {args.out}")
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
