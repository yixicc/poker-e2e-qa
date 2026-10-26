"""UI 冒烟：本地管理台「数据问答」页。

依赖：
  1. 复制 automation/.env.example → automation/.env，设 UI_ENABLED=1
  2. 启动管理台：python3 scripts/trace_config_server.py（默认 :8765）
  3. 可选配置 data/chat.env 才能真正出模型回答
"""

from __future__ import annotations

import pytest

from common.reporting import attach_text
from config.settings import settings
from ui.pages.chat_page import ChatPage

try:
    import allure
except ImportError:  # pragma: no cover
    allure = None


pytestmark = [pytest.mark.ui]


@pytest.fixture
def chat_page(page, ui_settings):
    if not ui_settings.ui_enabled:
        pytest.skip("UI_ENABLED=0，跳过 UI。在 automation/.env 打开并启动管理台后再跑。")
    if "production" in (ui_settings.ui_chat_path or "") or "production" in (
        ui_settings.ui_base_url or ""
    ):
        pytest.skip("当前配置为 production Flutter，请跑 test_production_chat_excel")
    cp = ChatPage(page, ui_settings.ui_chat_url)
    cp.open()
    return cp


@pytest.mark.smoke
def test_chat_page_loads(chat_page: ChatPage):
    if allure is not None:
        allure.dynamic.title("UI 冒烟：数据问答页可打开")
    assert chat_page.page.locator("#chat-form").is_visible()
    attach_text("banner", chat_page.banner_text())


@pytest.mark.smoke
@pytest.mark.P0
def test_chat_ask_today_overview(chat_page: ChatPage):
    """对应 M3-01 口语：今天打了几场、输赢多少（需模型+MCP 已配置）。"""
    if allure is not None:
        allure.dynamic.title("UI：今天打了几场、输赢多少")
        allure.dynamic.severity(allure.severity_level.CRITICAL)

    q = "今天这场我打了多少手，总共赢输多少"
    reply = chat_page.send(q)
    attach_text("question", q)
    attach_text("reply", reply)
    chips = chat_page.tool_chip_names()
    attach_text("tools", ", ".join(chips))

    assert reply, "无助手回复"
    # 未配置模型时页面会提示；配置后期望出现数字相关内容
    if "还没配置" in chat_page.banner_text() or "未配置" in reply or "配置模型" in reply:
        pytest.skip("聊天模型未配置，仅验证了页面可交互")
    # 软断言：回复里最好有数字
    assert any(ch.isdigit() for ch in reply), f"回复缺少数字: {reply[:200]}"
