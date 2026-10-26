"""Allure / 附件辅助。"""

from __future__ import annotations

import json
from typing import Any

try:
    import allure
except ImportError:  # pragma: no cover
    allure = None  # type: ignore


def attach_json(name: str, data: Any) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2, default=str)
    if allure is None:
        return
    allure.attach(text, name=name, attachment_type=allure.attachment_type.JSON)


def attach_text(name: str, text: str) -> None:
    if allure is None:
        return
    allure.attach(text or "", name=name, attachment_type=allure.attachment_type.TEXT)


def attach_png(name: str, png: bytes) -> None:
    if allure is None or not png:
        return
    allure.attach(png, name=name, attachment_type=allure.attachment_type.PNG)


def step(title: str):
    if allure is None:
        from contextlib import nullcontext

        return nullcontext()
    return allure.step(title)
