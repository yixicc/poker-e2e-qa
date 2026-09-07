#!/usr/bin/env python3
"""全站返回导航：从哪进回哪（同站 history.back），否则走 fallback href。"""

from __future__ import annotations

SMART_BACK_SNIPPET = """
<script>
(function(){
  function sameOriginReferrer(){
    try {
      if (!document.referrer) return false;
      return new URL(document.referrer).origin === location.origin;
    } catch (e) { return false; }
  }
  window.smartBack = function(fallback){
    var fb = fallback || '/';
    if (sameOriginReferrer() && window.history.length > 1) {
      history.back();
      return;
    }
    location.href = fb;
  };
  function markBackLinks(){
    document.querySelectorAll('a').forEach(function(a){
      if (a.classList.contains('js-back') || a.classList.contains('js-no-back')) return;
      var t = (a.textContent || '').replace(/\\s+/g, ' ').trim();
      // 仅「返回…」类导航，避免误伤「返回列表查看」等业务 CTA 时可加 js-no-back
      if (t.indexOf('←') === 0 || /^返回/.test(t) || t.indexOf('返回') === 0) {
        // 「返回列表查看」等明确跳转保留原 href，不劫持
        if (t.indexOf('查看') >= 0 || t.indexOf('打开') >= 0) return;
        a.classList.add('js-back');
      }
    });
    document.querySelectorAll('.nav > a, .back > a, .back a').forEach(function(a){
      var t = (a.textContent || '');
      if (t.indexOf('查看') >= 0) return;
      a.classList.add('js-back');
    });
  }
  document.addEventListener('click', function(e){
    var a = e.target && e.target.closest && e.target.closest('a.js-back');
    if (!a) return;
    e.preventDefault();
    smartBack(a.getAttribute('href') || '/');
  }, true);
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', markBackLinks);
  } else {
    markBackLinks();
  }
})();
</script>
""".strip()


def inject_smart_back(html: str) -> str:
    """Idempotently inject smart-back behavior into an HTML document."""
    if not html:
        return html
    if "window.smartBack" in html:
        return html
    lower = html.lower()
    idx = lower.rfind("</body>")
    if idx >= 0:
        return html[:idx] + "\n" + SMART_BACK_SNIPPET + "\n" + html[idx:]
    return html + "\n" + SMART_BACK_SNIPPET + "\n"
