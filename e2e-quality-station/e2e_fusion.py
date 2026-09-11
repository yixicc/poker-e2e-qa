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
                "errorMsg": rec.get("errorMsg") or item.get("errorMsg") or "",
                "segmentId": rec.get("segmentId") or item.get("segmentId") or "",
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


def _card_key(cards) -> str:
    out = []
    for c in cards or []:
        s = str(c or "").strip().upper().replace(" ", "")
        if s.startswith("10"):
            s = "T" + s[2:]
        if s:
            out.append(s)
    return " ".join(sorted(out))


def _gold_hero_flop(tree: dict | None, hist: dict | None) -> tuple[str, str]:
    hero: list = []
    for p in (hist or {}).get("players") or []:
        if p and p.get("hero") and p.get("cards"):
            hero = list(p.get("cards") or [])
            break
    if not hero:
        p0 = ((tree or {}).get("players") or {}).get("P0") or {}
        cards = p0.get("cards") or {}
        hero = [cards[k]["value"] for k in ("P0", "P1") if k in cards and (cards[k] or {}).get("value")]
    flop = ((hist or {}).get("board") or {}).get("flop") or []
    if not flop:
        raw = ((tree or {}).get("table") or {}).get("community_cards") or []
        flop = [x.get("value") for x in raw if isinstance(x, dict) and x.get("value")][:3]
    return _card_key(hero), _card_key(flop)


def _vis_hero_flop(body: dict | None) -> tuple[str, str]:
    from e2e_match import extract_vis  # noqa: WPS433

    hand, _ = extract_vis(body)
    if not isinstance(hand, dict):
        return "", ""
    hero = list(hand.get("hero_cards") or [])
    if len(hero) < 2:
        for p in hand.get("players") or []:
            if isinstance(p, dict) and p.get("is_hero"):
                hero = list(p.get("shown_cards") or p.get("hole_cards") or p.get("cards") or []) or hero
                if not hero:
                    hero = list(hand.get("hero_cards") or [])
                break
    board = list(hand.get("community_cards") or [])
    by = hand.get("community_cards_by_street") or {}
    flop = list(by.get("flop") or []) or board[:3]
    return _card_key(hero), _card_key(flop)


def _cards_from_fusion_id(hand_id: str) -> str:
    m = re.search(r"_([2-9TJQKA][HDCS][2-9TJQKA][HDCS])(?:_|$)", str(hand_id or ""), re.I)
    if not m:
        return ""
    s = m.group(1).upper()
    return _card_key([s[:2], s[2:4]])


def _fusion_hero_key(h: dict | None) -> str:
    from_id = _cards_from_fusion_id((h or {}).get("handId") or "")
    if from_id:
        return from_id
    v_hero, _ = _vis_hero_flop((h or {}).get("body"))
    return v_hero


def _align_by_hero(
    cases: list[dict],
    fusion_hands: list[dict],
    gold_trees: list | None,
    gold_hists: list | None,
) -> list[dict | None]:
    trees = gold_trees or []
    hists = gold_hists or []
    aligned: list[dict | None] = [None] * len(cases)
    last = -1
    for i, _ in enumerate(cases):
        g_hero, _ = _gold_hero_flop(trees[i] if i < len(trees) else None, hists[i] if i < len(hists) else None)
        if not g_hero:
            continue
        for j in range(last + 1, len(fusion_hands)):
            v_hero = _fusion_hero_key(fusion_hands[j])
            if not v_hero or v_hero != g_hero:
                continue
            aligned[i] = fusion_hands[j]
            last = j
            break
    return aligned


def align_to_cases(
    cases: list[dict],
    fusion_hands: list[dict],
    gold_trees: list | None = None,
    gold_hists: list | None = None,
) -> list[dict | None]:
    by_stem: dict[str, dict] = {}
    for h in fusion_hands:
        stem = video_stem(h.get("videoUrl") or "")
        if stem:
            by_stem[stem] = h
    ids = [str(c.get("hand_id") or "") for c in cases]
    n_hit = sum(1 for i in ids if i and i in by_stem)
    if fusion_hands and n_hit and (n_hit == len(fusion_hands) or n_hit >= max(1, int(0.8 * len(fusion_hands)))):
        return [by_stem.get(str(c.get("hand_id") or "")) for c in cases]
    hero = _align_by_hero(cases, fusion_hands, gold_trees, gold_hists)
    n_hero = sum(1 for x in hero if x)
    n_gold_hero = 0
    for i, _ in enumerate(cases):
        g_hero, _ = _gold_hero_flop(
            gold_trees[i] if gold_trees and i < len(gold_trees) else None,
            gold_hists[i] if gold_hists and i < len(gold_hists) else None,
        )
        if g_hero:
            n_gold_hero += 1
    use_hero = n_hero and n_gold_hero and n_hero >= max(1, int(0.5 * n_gold_hero))
    if not use_hero and len(fusion_hands) != len(cases) and n_hero >= max(1, int(0.3 * n_gold_hero)):
        use_hero = True
    if use_hero:
        return hero
    paired: list[dict | None] = []
    for i, _ in enumerate(cases):
        paired.append(fusion_hands[i] if i < len(fusion_hands) else None)
    return paired
