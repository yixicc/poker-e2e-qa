"""数据问答页 Page Object（对齐 scripts/chat_page.py DOM）。"""

from __future__ import annotations

from playwright.sync_api import Page, expect


class ChatPage:
    def __init__(self, page: Page, base_url: str) -> None:
        self.page = page
        self.base_url = base_url.rstrip("/")

    def open(self) -> None:
        self.page.goto(self.base_url, wait_until="domcontentloaded")
        expect(self.page.locator("#chat-input")).to_be_visible(timeout=15000)

    def send(self, question: str, *, timeout_ms: int = 120_000) -> str:
        self.page.fill("#chat-input", question)
        self.page.click("#chat-send")
        # 等待「正在查数据…」消失，出现 assistant 气泡
        self.page.wait_for_function(
            """() => {
              const nodes = [...document.querySelectorAll('.bubble.assistant')];
              if (!nodes.length) return false;
              const last = nodes[nodes.length - 1];
              return last && last.textContent && !last.textContent.includes('正在查数据');
            }""",
            timeout=timeout_ms,
        )
        return self.last_assistant_text()

    def last_assistant_text(self) -> str:
        bubbles = self.page.locator(".bubble.assistant")
        n = bubbles.count()
        if n == 0:
            return ""
        return bubbles.nth(n - 1).inner_text()

    def tool_chip_names(self) -> list[str]:
        chips = self.page.locator(".tool-chip")
        return [chips.nth(i).inner_text() for i in range(chips.count())]

    def banner_text(self) -> str:
        banner = self.page.locator("#chat-banner")
        if not banner.is_visible():
            return ""
        return banner.inner_text()
