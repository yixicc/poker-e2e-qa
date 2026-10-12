#!/usr/bin/env python3
"""数据问答页。模型通过 MCP 自己决定调用哪些只读工具。"""

from __future__ import annotations

from manage_page import _CSS, _shell_close, _shell_open

_CHAT_CSS = """
.chat-wrap { max-width: 820px; display: flex; flex-direction: column; min-height: calc(100vh - 44px); }
.chat-log {
  flex: 1; display: flex; flex-direction: column; gap: 12px;
  margin: 8px 0 14px;
}
.bubble {
  max-width: 92%; padding: 10px 12px; border-radius: 12px;
  white-space: pre-wrap; word-break: break-word; font-size: 14px;
}
.bubble.user { align-self: flex-end; background: var(--accent); color: #fff; }
.bubble.assistant { align-self: flex-start; background: #fff; border: 1px solid var(--line); }
.tools { align-self: flex-start; display: flex; flex-wrap: wrap; gap: 6px; max-width: 92%; }
.tool-chip {
  font-size: 11px; font-weight: 700; color: #115e59; background: var(--accent-soft);
  border-radius: 999px; padding: 3px 8px;
}
.tool-chip.bad { color: var(--warn); background: #ffe4e6; }
.chat-box { display: flex; gap: 8px; align-items: flex-end; }
.chat-box textarea {
  flex: 1; min-height: 72px; resize: vertical; border: 1px solid var(--line);
  border-radius: 10px; padding: 10px 12px; font: inherit; font-size: 14px;
  background: #fff; color: var(--ink);
}
.prompts { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
.banner {
  background: #fff7ed; border: 1px solid #fed7aa; color: #9a3412;
  border-radius: 10px; padding: 10px 12px; font-size: 13px; margin-bottom: 8px;
}
"""


def render_chat_page() -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>数据问答</title>
<style>{_CSS}{_CHAT_CSS}</style>
</head>
<body>
{_shell_open("chat", wrap_class="wrap chat-wrap")}
<div class="topbar">
  <div class="topbar-text">
    <h1>数据问答</h1>
    <p class="lead" id="chat-lead">跑批、正确值、Bug、Trace、fusion 都包成只读工具。模型自己决定要不要查。</p>
  </div>
</div>
<div id="chat-banner" class="banner" hidden></div>
<div id="chat-log" class="chat-log"></div>
<form id="chat-form">
  <div class="chat-box">
    <textarea id="chat-input" placeholder="例如：最近一次跑批的新版准确率是多少？"></textarea>
    <button class="btn primary" id="chat-send" type="submit">发送</button>
  </div>
  <div class="prompts">
    <button class="btn" type="button" data-q="最近有哪些对比跑批？最新一次的新版准确率和主要问题类是什么？">最近跑批</button>
    <button class="btn" type="button" data-q="当前正确值版本里有多少手？列出前 10 手的手牌号和底牌。">当前正确值</button>
    <button class="btn" type="button" data-q="现在标记了哪些手牌 Bug？按状态概括一下。">手牌 Bug</button>
  </div>
</form>
{_shell_close()}
<script>
const log = document.getElementById('chat-log');
const input = document.getElementById('chat-input');
const send = document.getElementById('chat-send');
const banner = document.getElementById('chat-banner');
const lead = document.getElementById('chat-lead');
const history = [];

function addBubble(role, text) {{
  const el = document.createElement('div');
  el.className = 'bubble ' + role;
  el.textContent = text;
  log.appendChild(el);
  el.scrollIntoView({{block: 'nearest'}});
  return el;
}}

function addTools(calls) {{
  if (!calls || !calls.length) return;
  const row = document.createElement('div');
  row.className = 'tools';
  calls.forEach(function(call) {{
    const chip = document.createElement('span');
    chip.className = 'tool-chip' + (call.ok ? '' : ' bad');
    chip.textContent = call.name || 'tool';
    chip.title = JSON.stringify(call.arguments || {{}});
    row.appendChild(chip);
  }});
  log.appendChild(row);
}}

document.querySelectorAll('[data-q]').forEach(function(btn) {{
  btn.addEventListener('click', function() {{
    input.value = btn.getAttribute('data-q');
    input.focus();
  }});
}});

fetch('/api/chat/status').then(function(r) {{ return r.json(); }}).then(function(data) {{
  if (data.tool_error) {{
    banner.hidden = false;
    banner.textContent = '数据工具暂时不可用：' + data.tool_error;
  }}
  if (!data.configured) {{
    banner.hidden = false;
    banner.textContent = '还没配置模型。复制 data/chat.env.example 为 data/chat.env，填上接口地址、密钥和模型名。';
  }} else if (data.model) {{
    lead.textContent = '当前模型 ' + data.model + '。工具只读，由模型自己决定调用。';
  }}
}}).catch(function() {{}});

document.getElementById('chat-form').addEventListener('submit', function(ev) {{
  ev.preventDefault();
  const text = input.value.trim();
  if (!text || send.disabled) return;
  input.value = '';
  history.push({{role: 'user', content: text}});
  addBubble('user', text);
  const pending = addBubble('assistant', '正在查数据…');
  send.disabled = true;
  fetch('/api/chat', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{messages: history}})
  }}).then(function(r) {{ return r.json(); }}).then(function(data) {{
    if (!data.ok) {{
      pending.textContent = data.error || '发送失败';
      history.pop();
      return;
    }}
    pending.remove();
    addTools(data.tool_calls);
    addBubble('assistant', data.reply || '');
    history.push({{role: 'assistant', content: data.reply || ''}});
  }}).catch(function(err) {{
    pending.textContent = '发送失败：' + err;
    history.pop();
  }}).finally(function() {{
    send.disabled = false;
    input.focus();
  }});
}});

input.addEventListener('keydown', function(e) {{
  if (e.key === 'Enter' && !e.shiftKey) {{
    e.preventDefault();
    document.getElementById('chat-form').requestSubmit();
  }}
}});
</script>
</body>
</html>
"""
