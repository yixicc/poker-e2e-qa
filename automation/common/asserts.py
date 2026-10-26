"""业务断言：基于 Excel assert_expr / 返回 payload。"""

from __future__ import annotations

import json
import re
from typing import Any


def _dig(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        try:
            obj = json.loads(payload)
            return obj if isinstance(obj, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def extract_field(payload: Any, name: str) -> Any:
    """从 tool 返回里尽量抽出字段（兼容嵌套 data）。"""
    obj = _dig(payload)
    if name in obj:
        return obj[name]
    data = obj.get("data")
    if isinstance(data, dict) and name in data:
        return data[name]
    if isinstance(data, list) and data and isinstance(data[0], dict) and name in data[0]:
        return data[0][name]
    # 常见：result 字符串再包一层
    if "result" in obj and isinstance(obj["result"], str):
        try:
            inner = json.loads(obj["result"])
            if isinstance(inner, dict) and name in inner:
                return inner[name]
        except json.JSONDecodeError:
            pass
    return None


def extract_hand_id(payload: Any) -> str | None:
    obj = _dig(payload)
    if obj.get("hand_id"):
        return str(obj["hand_id"])
    hands = obj.get("hands")
    if isinstance(hands, list) and hands:
        first = hands[0]
        if isinstance(first, dict) and first.get("hand_id"):
            return str(first["hand_id"])
    return None


def extract_hand_ids(payload: Any, n: int = 3) -> list[str]:
    obj = _dig(payload)
    hands = obj.get("hands") or []
    out: list[str] = []
    if isinstance(hands, list):
        for h in hands:
            if isinstance(h, dict) and h.get("hand_id"):
                out.append(str(h["hand_id"]))
            if len(out) >= n:
                break
    return out


def apply_assert_expr(payload: Any, expr: str, raw_text: str = "") -> None:
    """
    支持：
      - 空：只要求有返回
      - hands / session_count（字段存在）
      - hands==27 / session_count==0
      - contains:94.5
      - empty_or_zero
    """
    expr = (expr or "").strip()
    if not expr:
        return

    if expr == "empty_or_zero":
        obj = _dig(payload)
        # 空列表 / 0 手数都算过
        for key in ("hands", "session_count", "matched_count"):
            if key in obj and obj[key] in (0, 0.0, None, []):
                return
        if payload in (None, "", {}, []):
            return
        # 文本里明确无数据
        blob = raw_text or json.dumps(payload, ensure_ascii=False)
        if any(x in blob for x in ("没有", "无记录", "0 手", "0手", "null")):
            return
        raise AssertionError(f"期望空/零结果，实际: {payload!r}")

    if expr.startswith("contains:"):
        needle = expr.split(":", 1)[1]
        blob = raw_text or json.dumps(payload, ensure_ascii=False)
        assert needle in blob, f"响应中未包含 {needle!r}"
        return

    m = re.fullmatch(r"([A-Za-z0-9_]+)\s*==\s*(.+)", expr)
    if m:
        key, expect = m.group(1), m.group(2).strip()
        actual = extract_field(payload, key)
        if expect.lower() in {"null", "none"}:
            assert actual is None, f"{key} 期望 null，实际 {actual!r}"
            return
        # 数字比较
        try:
            if "." in expect:
                assert float(actual) == float(expect), f"{key}: {actual!r} != {expect}"
            else:
                assert int(float(actual)) == int(expect), f"{key}: {actual!r} != {expect}"
            return
        except (TypeError, ValueError):
            assert str(actual) == expect, f"{key}: {actual!r} != {expect!r}"
            return

    # 仅字段名：要求存在且非 None
    val = extract_field(payload, expr)
    assert val is not None, f"缺少字段 {expr}，payload={payload!r}"
