from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import settings  # noqa: E402


def pytest_configure(config):  # noqa: ARG001
    settings.html_report_path.parent.mkdir(parents=True, exist_ok=True)


@pytest.fixture(scope="session")
def ui_settings():
    return settings


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    """UI_HEADED=1 或 ./scripts/run_ui.sh headed 时打开可见浏览器窗口。"""
    args = dict(browser_type_launch_args)
    if settings.ui_headed:
        args["headless"] = False
    return args


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {
        **browser_context_args,
        "viewport": {"width": 1280, "height": 800},
        "locale": "zh-CN",
    }
