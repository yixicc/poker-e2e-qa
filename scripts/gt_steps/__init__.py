"""P0 决策点报文：从正确值 gt_raw 拆出每一次 P0 行动前的请求快照。

独立于「正确值管理」页；只读派生现有 gt_store，不改 hands.json。
"""

from .split import (  # noqa: F401
    list_version_steps_brief,
    split_gt_into_p0_steps,
    truncate_before_p0_nth,
)

__all__ = [
    "list_version_steps_brief",
    "split_gt_into_p0_steps",
    "truncate_before_p0_nth",
]
