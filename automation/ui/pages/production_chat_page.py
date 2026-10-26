"""GameWise production Flutter Web 聊天页（语义树 + chat/stream）。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from playwright.sync_api import Page, Response


@dataclass
class ChatTurnResult:
    question: str
    reply: str
    tools: list[str] = field(default_factory=list)
    stream_raw: str = ""
    elapsed_ms: float = 0.0
    conversation_id: str = ""
    error: str = ""


def _with_openid(url: str, open_id: str) -> str:
    if not open_id:
        return url
    parts = urlparse(url)
    q = parse_qs(parts.query, keep_blank_values=True)
    q["openid"] = [open_id]
    return urlunparse(parts._replace(query=urlencode({k: v[0] for k, v in q.items()})))


def _parse_sse(text: str) -> tuple[str, list[str], str]:
    """从 assistant/chat/stream SSE 拼回复文本、工具名、conversation_id。"""
    chunks: list[str] = []
    tools: list[str] = []
    conv = ""
    for line in (text or "").splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload:
            continue
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        ev = str(obj.get("event") or "")
        if ev == "delta" and obj.get("text"):
            chunks.append(str(obj["text"]))
        elif ev == "tool" and obj.get("tool"):
            tools.append(str(obj["tool"]))
        elif ev == "done":
            conv = str(obj.get("conversation_id") or conv)
    # 去重保序
    seen: set[str] = set()
    uniq_tools: list[str] = []
    for t in tools:
        if t not in seen:
            seen.add(t)
            uniq_tools.append(t)
    return "".join(chunks), uniq_tools, conv


class ProductionChatPage:
    """production Flutter 页：先开语义树，再用 mouse/keyboard 输入并点发送。"""

    STREAM_URL_PART = "/api/v1/assistant/chat/stream"

    def __init__(self, page: Page, base_url: str, *, open_id: str = "") -> None:
        self.page = page
        self.base_url = _with_openid(base_url, open_id)
        self.open_id = open_id
        self.shots: list[tuple[str, bytes]] = []

    def open(self) -> None:
        self.page.goto(self.base_url, wait_until="domcontentloaded", timeout=60_000)
        self.page.wait_for_timeout(3500)
        self._enable_semantics()
        # Flutter 语义树里的 textarea 常对 Playwright 报 not visible，用 attached
        self.page.wait_for_selector("textarea", state="attached", timeout=45_000)
        self.page.wait_for_timeout(500)
        self.snap("聊天页已打开")

    def _enable_semantics(self) -> None:
        for _ in range(3):
            ok = self.page.evaluate(
                """() => {
                  const el = document.querySelector('flt-semantics-placeholder')
                    || document.querySelector('[aria-label="Enable accessibility"]');
                  if (el) { el.click(); return true; }
                  return !!document.querySelector('textarea');
                }"""
            )
            self.page.wait_for_timeout(1000)
            if ok and self.page.locator("textarea").count() > 0:
                return
        # 再等一轮渲染
        self.page.wait_for_timeout(2000)

    def snap(self, name: str) -> None:
        """截当前可见画面，留给步骤附件。失败不打断用例。"""
        try:
            png = self.page.screenshot(type="png")
        except Exception:  # noqa: BLE001
            return
        if png:
            self.shots.append((name, png))

    def _focus_input(self) -> None:
        # 语音模式时可能没有 textarea，先尝试切回键盘
        if self.page.locator("textarea").count() == 0:
            self._enable_semantics()
            self.page.wait_for_timeout(500)
        ta = self.page.locator("textarea").first
        ta.wait_for(state="attached", timeout=20_000)
        box = ta.bounding_box()
        if not box:
            # 语义节点可能宽高为 0，点底部输入带区域
            vp = self.page.viewport_size or {"width": 390, "height": 844}
            self.page.mouse.click(vp["width"] * 0.5, vp["height"] * 0.88)
            self.page.wait_for_timeout(300)
            box = ta.bounding_box()
        if not box:
            raise RuntimeError("找不到输入框坐标")
        self.page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        self.page.wait_for_timeout(200)

    def _click_send(self) -> None:
        best = self.page.evaluate(
            """() => {
              const skip = new Set([
                '首页','复盘','准则','我的','手牌复盘','开牌范围','底池赔率','对手分析',
                'GTO 开','新会话','Home','Review','Principles','Me','复制','点赞','点踩','朗读','分享'
              ]);
              let best = null;
              for (const e of document.querySelectorAll('[role=button]')) {
                const t = (e.innerText || '').trim();
                if (skip.has(t) || t.includes('豆包') || t.includes('GTO')) continue;
                const r = e.getBoundingClientRect();
                if (r.width <= 0 || r.height <= 0) continue;
                if (r.y > 500 && r.y < 820 && r.width <= 72 && r.height <= 72 && r.x > 220) {
                  if (!best || r.x > best.x) best = {x:r.x, y:r.y, w:r.width, h:r.height};
                }
              }
              return best;
            }"""
        )
        if not best:
            raise RuntimeError("未找到发送按钮（请确认已输入文字且非语音模式）")
        self.page.mouse.click(best["x"] + best["w"] / 2, best["y"] + best["h"] / 2)

    def send(self, question: str, *, timeout_ms: int = 180_000) -> ChatTurnResult:
        import time

        q = (question or "").strip()
        if not q:
            return ChatTurnResult(question="", reply="", error="空问题")

        stream_box: dict[str, Any] = {"text": "", "done": False}

        def on_response(resp: Response) -> None:
            if self.STREAM_URL_PART not in resp.url:
                return
            try:
                body = resp.text()
            except Exception as e:  # noqa: BLE001
                stream_box["error"] = str(e)
                stream_box["done"] = True
                return
            stream_box["text"] = body or ""
            stream_box["status"] = resp.status
            stream_box["done"] = True

        self.page.on("response", on_response)
        t0 = time.time()
        try:
            self._focus_input()
            # 清空：全选删除（Flutter 上 fill 不可靠）
            self.page.keyboard.press("Meta+A")
            self.page.keyboard.press("Backspace")
            self.page.keyboard.type(q, delay=35)
            self.page.wait_for_timeout(400)
            self.snap("已输入问题")
            self._click_send()
            self.page.wait_for_timeout(600)
            self.snap("已发送")

            deadline = time.time() + timeout_ms / 1000
            while time.time() < deadline:
                if stream_box.get("done"):
                    break
                self.page.wait_for_timeout(400)
            else:
                self.snap("等待超时")
                return ChatTurnResult(
                    question=q,
                    reply="",
                    stream_raw=str(stream_box.get("text") or ""),
                    elapsed_ms=round((time.time() - t0) * 1000, 1),
                    error="等待 chat/stream 超时",
                )

            raw = str(stream_box.get("text") or "")
            reply, tools, conv = _parse_sse(raw)
            # 流结束后再留一点时间让 UI 渲染完
            self.page.wait_for_timeout(800)
            self.snap("回答已展示")
            return ChatTurnResult(
                question=q,
                reply=reply,
                tools=tools,
                stream_raw=raw,
                elapsed_ms=round((time.time() - t0) * 1000, 1),
                conversation_id=conv,
                error="" if reply else "stream 无 delta 文本",
            )
        except Exception:
            self.snap("失败现场")
            raise
        finally:
            try:
                self.page.remove_listener("response", on_response)
            except Exception:  # noqa: BLE001
                pass

    def new_session(self) -> None:
        """点「新会话」隔离上下文（找不到则刷新页面）。"""
        btn = self.page.get_by_role("heading", name="新会话")
        if btn.count():
            try:
                btn.first.click(timeout=2000)
                self.page.wait_for_timeout(1000)
                return
            except Exception:  # noqa: BLE001
                pass
        self.open()


_HINT_SPLIT = re.compile(r"[➕、;；\n|/]+")


def data_points_from_expected(expected: str) -> list[str]:
    """从预期描述里取出要核对的数据项，去掉指标 code 和工具名。"""
    body = re.sub(r"^出现指标[：:]", "", expected or "").strip()
    parts = [p.strip() for p in _HINT_SPLIT.split(body) if p.strip()]
    out: list[str] = []
    for part in parts:
        label = re.sub(r"[（(][^）)]*[）)]", "", part)
        label = re.sub(r"tool_[A-Za-z0-9_]+", "", label).strip(" ：:，,")
        if label and label not in out:
            out.append(label)
    return out


def _data_point_in_reply(label: str, text: str) -> bool:
    if label and label in text:
        return True
    has_number = bool(re.search(r"\d|[一二三四五六七八九十两几]", text))
    keys: list[str] = []
    if "场" in label:
        keys.append("场")
    if any(k in label for k in ("盈", "亏", "BB", "bb", "赢", "输")):
        keys.extend(["BB", "bb", "盈", "亏", "赢", "输"])
    if "手" in label:
        keys.append("手")
    if "胜" in label or "率" in label:
        keys.extend(["%", "胜", "率"])
    if "对手" in label:
        keys.append("对手")
    if "位置" in label:
        keys.extend(["BTN", "CO", "位置", "盲"])
    return bool(keys) and has_number and any(k in text for k in keys)


def missing_reply_data(reply: str, expected: str) -> list[str]:
    """只核对最终回答里的数据，不看工具名、指标 code。未命中的预期数据项。"""
    text = reply or ""
    if not text.strip():
        return ["模型回答为空"]
    expected_body = re.sub(r"[（(][^）)]*[）)]", "", expected or "")
    expected_body = re.sub(r"tool_[A-Za-z0-9_]+", "", expected_body)
    missing: list[str] = []
    for match in re.finditer(
        r"([+-]?\d+(?:\.\d+)?)(\s*(?:场|手|BB|bb|%))?",
        expected_body,
    ):
        num, unit = match.group(1), match.group(2) or ""
        if not unit and not num.startswith(("+", "-")):
            continue
        shown = num + unit.strip()
        if num not in text and shown not in text:
            missing.append(shown)
    for label in data_points_from_expected(expected):
        if not _data_point_in_reply(label, text):
            missing.append(label)
    return missing


def assert_hints_against_reply(reply: str, assert_hints: str) -> list[str]:
    """兼容旧调用：只按预期描述里的数据项核对回答。"""
    return missing_reply_data(reply, assert_hints)
