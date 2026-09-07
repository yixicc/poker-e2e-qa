"""从 fusion 按 sessionId 拉视觉 / 规则。"""

from __future__ import annotations

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen

FUSION_BASE = os.environ.get("FUSION_BASE", "http://192.168.110.81:8080").rstrip("/")
VIDEO_NUM = re.compile(r"^(\d+)\.mp4$", re.I)


def parse_session_ids(raw: str) -> list[str]:
    parts = re.split(r"[\s,;，、]+", str(raw or "").strip())
    out: list[str] = []
    for p in parts:
        p = p.strip()
        if p and p not in out:
            out.append(p)
    return out


def fusion_get(path: str, timeout: int = 25) -> Any:
    url = FUSION_BASE + path
    req = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except HTTPError as e:
        raise ValueError(f"fusion {e.code} {path}") from e
    except URLError as e:
        raise ValueError(f"fusion 连不上 {FUSION_BASE}：{e.reason}") from e


def _result(payload: Any) -> Any:
    if isinstance(payload, dict) and "result" in payload:
        return payload["result"]
    return payload


def list_session_records(session_id: str) -> list[dict]:
    out: list[dict] = []
    page = 1
    total = None
    while page <= 50:
        q = urlencode({"page": page, "size": 100, "sessionId": session_id})
        res = _result(fusion_get("/api/fusion/hand-records?" + q))
        if not isinstance(res, dict):
            break
        chunk = res.get("list") or []
        out.extend(chunk)
        total = int(res.get("total") or 0)
        if not chunk or (total and len(out) >= total):
            break
        page += 1
    return out


def list_session_hands(session_id: str) -> list[dict]:
    raw = _result(fusion_get("/api/fusion/hands-by-session?sessionId=" + quote(str(session_id))))
    lst = raw if isinstance(raw, list) else (raw.get("list") if isinstance(raw, dict) else []) or []
    recs = list_session_records(session_id)
    by_id = {str(r.get("handId")): r for r in recs if r.get("handId")}
    hands: list[dict] = []
    seen: set[str] = set()
    src = lst or [
        {
            "handId": r.get("handId"),
            "sessionId": r.get("sessionId") or session_id,
            "status": r.get("status"),
            "createTime": r.get("createTime"),
            "videoUrl": r.get("videoUrl"),
        }
        for r in recs
    ]
    for item in src:
        hid = str(item.get("handId") or "")
        if not hid or hid in seen:
            continue
        seen.add(hid)
        rec = by_id.get(hid) or {}
        hands.append(
            {
                "handId": hid,
                "sessionId": str(item.get("sessionId") or rec.get("sessionId") or session_id),
                "status": item.get("status") or rec.get("status"),
                "videoUrl": rec.get("videoUrl") or item.get("videoUrl") or "",
                "createTimeMs": rec.get("createTime") or 0,
            }
        )
    return sort_session_hands(hands)


def sort_session_hands(hands: list[dict]) -> list[dict]:
    def key(h: dict):
        name = Path(urlparse(h.get("videoUrl") or "").path).name
        m = VIDEO_NUM.match(name)
        if m:
            return (0, int(m.group(1)), 0)
        ms = h.get("createTimeMs") or 0
        try:
            ms = int(ms)
        except (TypeError, ValueError):
            ms = 0
        return (1, ms, 0)

    return sorted(hands, key=key)


def fetch_hand_result(session_id: str, hand_id: str) -> dict | None:
    path = f"/api/fusion/hand-result?sessionId={quote(str(session_id))}&handId={quote(str(hand_id))}"
    payload = fusion_get(path)
    res = _result(payload)
    return res if isinstance(res, dict) else None


def fetch_session_results(session_ids: list[str], *, workers: int = 8) -> list[dict]:
    listed: list[dict] = []
    for sid in session_ids:
        listed.extend(list_session_hands(sid))
    if not listed:
        raise ValueError("fusion 这个 sessionId 下没有手牌")

    def one(meta: dict) -> dict:
        try:
            body = fetch_hand_result(meta["sessionId"], meta["handId"])
        except ValueError:
            body = None
        return {**meta, "body": body}

    out: list[dict] = [None] * len(listed)  # type: ignore
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futs = {pool.submit(one, h): i for i, h in enumerate(listed)}
        for fut in as_completed(futs):
            out[futs[fut]] = fut.result()
    return out


def video_stem(url: str) -> str:
    return Path(urlparse(url or "").path).stem


def align_to_cases(cases: list[dict], fusion_hands: list[dict]) -> list[dict | None]:
    by_stem: dict[str, dict] = {}
    for h in fusion_hands:
        stem = video_stem(h.get("videoUrl") or "")
        if stem:
            by_stem[stem] = h
    ids = [str(c.get("hand_id") or "") for c in cases]
    n_hit = sum(1 for i in ids if i and i in by_stem)
    if fusion_hands and n_hit and (n_hit == len(fusion_hands) or n_hit >= max(1, int(0.8 * len(fusion_hands)))):
        return [by_stem.get(str(c.get("hand_id") or "")) for c in cases]
    paired: list[dict | None] = []
    for i, _ in enumerate(cases):
        paired.append(fusion_hands[i] if i < len(fusion_hands) else None)
    return paired
