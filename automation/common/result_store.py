"""用例执行结果收集，供导出 Excel。"""

from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ExecRecord:
    # 原始用例
    case_id: str = ""
    group: str = ""
    title: str = ""
    priority: str = ""
    step_no: int | str = ""
    user_question: str = ""
    assert_hints: str = ""
    expect_tools: str = ""
    notes: str = ""
    # 自动化参数
    tool_name: str = ""
    role: str = ""
    metric_codes: str = ""
    assert_expr: str = ""
    request_body: str = ""
    # 返回结果
    result: str = ""  # passed / failed / skipped / error
    http_status: str | int = ""
    elapsed_ms: str | float = ""
    response_summary: str = ""
    response_raw: str = ""
    model_reply: str = ""
    error_message: str = ""
    nodeid: str = ""
    started_at: float = 0.0
    finished_at: float = 0.0

    def to_row(self) -> dict[str, Any]:
        return asdict(self)


class ResultStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_node: dict[str, ExecRecord] = {}
        self._ordered: list[str] = []

    def start(self, nodeid: str, record: ExecRecord) -> None:
        record.nodeid = nodeid
        record.started_at = time.time()
        with self._lock:
            if nodeid not in self._by_node:
                self._ordered.append(nodeid)
            self._by_node[nodeid] = record

    def update(self, nodeid: str, **kwargs: Any) -> None:
        with self._lock:
            rec = self._by_node.get(nodeid)
            if not rec:
                return
            for k, v in kwargs.items():
                if hasattr(rec, k):
                    setattr(rec, k, v)

    def finish(self, nodeid: str, result: str, error_message: str = "") -> None:
        with self._lock:
            rec = self._by_node.get(nodeid)
            if not rec:
                # 未走 start 的用例（如收集阶段失败）也记一条
                rec = ExecRecord(nodeid=nodeid, title=nodeid)
                self._ordered.append(nodeid)
                self._by_node[nodeid] = rec
            rec.result = result
            rec.error_message = (error_message or "")[:2000]
            rec.finished_at = time.time()
            if rec.started_at and not rec.elapsed_ms:
                rec.elapsed_ms = round((rec.finished_at - rec.started_at) * 1000, 1)

    def records(self) -> list[ExecRecord]:
        with self._lock:
            return [self._by_node[k] for k in self._ordered if k in self._by_node]

    def clear(self) -> None:
        with self._lock:
            self._by_node.clear()
            self._ordered.clear()


STORE = ResultStore()
