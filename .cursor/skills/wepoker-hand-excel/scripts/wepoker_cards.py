#!/usr/bin/env python3
"""WePoker 4-color hole/board crops + Vision rank OCR. Call set_work() first."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
SWIFT = HERE / "ocr_vision.swift"
HOLE = HERE / "_hole"
BOARD = HERE / "_board"

RANK_MAP = {
    "A": "A", "K": "K", "Q": "Q", "J": "J", "T": "T",
    "10": "T", "1O": "T", "IO": "T",
    "9": "9", "8": "8", "7": "7", "6": "6", "5": "5", "4": "4", "3": "3", "2": "2",
}


def set_work(root: Path) -> None:
    global HOLE, BOARD
    root = Path(root)
    HOLE = root / "hole_work"
    BOARD = root / "board_work"
    HOLE.mkdir(parents=True, exist_ok=True)
    BOARD.mkdir(parents=True, exist_ok=True)


def _runs(on: np.ndarray, min_w: int) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    i, n = 0, len(on)
    while i < n:
        if on[i]:
            j = i
            while j < n and on[j]:
                j += 1
            if j - i >= min_w:
                runs.append((i, j))
            i = j
        else:
            i += 1
    return runs


def _merge_splits(runs: list[tuple[int, int]]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    i = 0
    while i < len(runs):
        a, b = runs[i]
        if i + 1 < len(runs):
            c, d = runs[i + 1]
            if (b - a) < 40 and (d - c) < 40 and 0 <= c - b <= 14 and 40 <= d - a <= 80:
                out.append((a, d))
                i += 2
                continue
        out.append((a, b))
        i += 1
    return out


def bottom_crop(im: Image.Image) -> Image.Image:
    w, h = im.size
    return im.crop((int(w * 0.20), int(h * 0.74), int(w * 0.80), int(h * 0.98)))


def board_crop(im: Image.Image) -> Image.Image:
    w, h = im.size
    return im.crop((int(w * 0.15), int(h * 0.36), int(w * 0.85), int(h * 0.50)))


def _felt(r, g, b) -> np.ndarray:
    return (g > r + 15) & (g > b + 8)


def _pick_hole_pair(runs: list[tuple[int, int]], width: int) -> list[tuple[int, int]]:
    runs = _merge_splits(runs)
    split: list[tuple[int, int]] = []
    for a, b in runs:
        if b - a >= 90:
            m = (a + b) // 2
            split.extend([(a, m - 1), (m + 1, b)])
        else:
            split.append((a, b))
    cands = [r for r in split if 28 <= r[1] - r[0] <= 80]
    if len(cands) < 2:
        return []
    cx = width / 2.0
    best = None
    for i, a in enumerate(cands):
        for b in cands[i + 1 :]:
            gap = b[0] - a[1]
            if gap < 0 or gap > 28:
                continue
            w0, w1 = a[1] - a[0], b[1] - b[0]
            if abs(w0 - w1) > 22:
                continue
            score = abs((a[0] + b[1]) / 2.0 - cx) + 0.4 * abs(w0 - w1) + 0.2 * gap
            if best is None or score < best[0]:
                best = (score, a, b)
    return [best[1], best[2]] if best else []


def hole_boxes(rgb: np.ndarray) -> list[tuple[int, int, int, int]]:
    h, w, _ = rgb.shape
    y0, y1 = int(h * 0.30), int(h * 0.88)
    band = rgb[y0:y1]
    r, g, b = band[:, :, 0].astype(int), band[:, :, 1].astype(int), band[:, :, 2].astype(int)
    lum = (r + g + b) / 3.0
    card = (lum > 90) & (~_felt(r, g, b))
    pair = _pick_hole_pair(_runs(card.mean(axis=0) > 0.16, 16), w)
    if len(pair) != 2:
        return []
    boxes = []
    for x0, x1 in pair:
        rows = np.where(card[:, x0:x1].mean(axis=1) > 0.12)[0]
        if len(rows) < 8:
            return []
        yy0, yy1 = int(rows[0]), int(rows[-1] + 1)
        max_h = int(max(36, (x1 - x0) * 1.52))
        if yy1 - yy0 > max_h:
            yy1 = yy0 + max_h
        boxes.append((x0, y0 + yy0, x1, y0 + yy1))
    h0 = boxes[0][3] - boxes[0][1]
    h1 = boxes[1][3] - boxes[1][1]
    if min(h0, h1) < 16 or abs(h0 - h1) > 80:
        return []
    return boxes


def board_boxes(rgb: np.ndarray) -> list[tuple[int, int, int, int]]:
    r, g, b = rgb[:, :, 0].astype(int), rgb[:, :, 1].astype(int), rgb[:, :, 2].astype(int)
    lum = (r + g + b) / 3.0
    card = (lum > 90) & (~_felt(r, g, b))
    cands = [(a, b) for a, b in _merge_splits(_runs(card.mean(0) > 0.16, 14)) if 36 <= b - a <= 75]
    groups: list[list[tuple[int, int]]] = []
    cur: list[tuple[int, int]] = []
    for a, b in cands:
        if cur and a - cur[-1][1] <= 16:
            cur.append((a, b))
        else:
            if cur:
                groups.append(cur)
            cur = [(a, b)]
    if cur:
        groups.append(cur)
    best = None
    cx = rgb.shape[1] / 2.0
    for g in groups:
        if len(g) < 3:
            continue
        if len(g) > 5:
            g = g[:5]
        score = (-len(g), abs((g[0][0] + g[-1][1]) / 2.0 - cx))
        if best is None or score < best[0]:
            best = (score, g)
    if not best:
        return []
    boxes = []
    for x0, x1 in best[1]:
        rows = np.where(card[:, x0:x1].mean(1) > 0.12)[0]
        if len(rows) < 8:
            return []
        yy0, yy1 = int(rows[0]), int(rows[-1] + 1)
        max_h = int(max(36, (x1 - x0) * 1.52))
        if yy1 - yy0 > max_h:
            yy1 = yy0 + max_h
        boxes.append((x0, yy0, x1, yy1))
    return boxes


def suit_of(card: np.ndarray) -> str:
    h, w, _ = card.shape
    r, g, b = card[:, :, 0].astype(float), card[:, :, 1].astype(float), card[:, :, 2].astype(float)
    felt = (g > r + 14) & (g > b + 8)
    border = np.zeros((h, w), dtype=bool)
    m = max(2, int(min(h, w) * 0.08))
    border[:m, :] = True
    border[-m:, :] = True
    border[:, :m] = True
    border[:, -m:] = True
    chroma = np.maximum(np.maximum(r, g), b) - np.minimum(np.minimum(r, g), b)
    colorful = (chroma > 24) & (~(felt & border))
    if colorful.sum() >= 12:
        pr, pg, pb = r[colorful], g[colorful], b[colorful]
        red_n = int(((pr > pg + 10) & (pr > pb + 10)).sum())
        blu_n = int(((pb > pr + 8) & (pb > pg + 6)).sum())
        grn_n = int(((pg > pr + 10) & (pg > pb + 8)).sum())
        winner = max(red_n, blu_n, grn_n)
        if winner >= 10:
            return "H" if winner == red_n else "D" if winner == blu_n else "C"
    return "S"


def _face_box(card: np.ndarray) -> tuple[int, int, int, int] | None:
    r, g, b = card[:, :, 0].astype(float), card[:, :, 1].astype(float), card[:, :, 2].astype(float)
    lum = (r + g + b) / 3.0
    chroma = np.maximum(np.maximum(r, g), b) - np.minimum(np.minimum(r, g), b)
    hi = (lum > 155) & (chroma < 55)
    lo = (lum > 98) & (chroma < 40)
    mask = hi if hi.mean() > 0.10 else lo
    if mask.mean() < 0.08:
        return None
    rows, cols = np.where(mask.mean(1) > 0.18)[0], np.where(mask.mean(0) > 0.18)[0]
    if len(rows) < 10 or len(cols) < 10:
        return None
    y0, y1, x0, x1 = int(rows[0]), int(rows[-1] + 1), int(cols[0]), int(cols[-1] + 1)
    hh, ww = y1 - y0, x1 - x0
    y0 = max(0, y0 - int(hh * 0.18))
    x0 = max(0, x0 - int(ww * 0.18))
    y1 = min(card.shape[0], y1 + int(hh * 0.06))
    x1 = min(card.shape[1], x1 + int(ww * 0.06))
    if y1 - y0 < 16 or x1 - x0 < 14:
        return None
    return x0, y0, x1, y1


def _is_back(face: np.ndarray) -> bool:
    lum = face.mean(axis=2)
    r, g, b = face.mean(axis=(0, 1))
    return float((lum > 150).mean()) < 0.12 and r > g + 20 and r > b + 15


def rank_crop(card_im: Image.Image, dest: Path) -> None:
    arr0 = np.array(card_im.convert("RGB"))
    r, g, b = arr0[:, :, 0].astype(int), arr0[:, :, 1].astype(int), arr0[:, :, 2].astype(int)
    felt_row = (g.mean(1) > r.mean(1) + 14) & (g.mean(1) > b.mean(1) + 8)
    y0 = 0
    while y0 < max(0, len(felt_row) - 6) and felt_row[y0]:
        y0 += 1
    card_im = Image.fromarray(arr0[y0:])
    w, h = card_im.size
    raw = card_im.crop((1, 1, max(2, int(w * 0.78)), max(2, int(h * 0.55)))).resize((160, 160), Image.LANCZOS)
    arr = np.array(raw).astype(float)
    lo, hi = np.percentile(arr, (8, 92))
    stretched = np.clip((arr - lo) * 255.0 / max(1.0, hi - lo), 0, 255).astype(np.uint8)
    canvas = Image.new("RGB", (220, 220), (255, 255, 255))
    canvas.paste(Image.fromarray(stretched), (30, 30))
    canvas.save(dest, quality=95)
    lum = stretched.mean(axis=2)
    bw = np.where(lum < 150, 0, 255).astype(np.uint8)
    bcanvas = Image.new("RGB", (220, 220), (255, 255, 255))
    bcanvas.paste(Image.fromarray(np.stack([bw, bw, bw], 2)), (30, 30))
    bcanvas.save(dest.with_name(dest.name.replace("_r", "_rb", 1)), quality=95)


def parse_rank(text: str) -> str | None:
    t = (text or "").strip().upper().replace(" ", "")
    if t in RANK_MAP:
        return RANK_MAP[t]
    m = re.search(r"10|[AKQJT2-9]", t)
    return RANK_MAP.get(m.group(0)) if m else None


def _save_face(raw: Image.Image, dest_prefix: Path, i: int) -> Path | None:
    fb = _face_box(np.array(raw))
    if not fb:
        return None
    face = raw.crop(fb)
    if min(face.size) < 14 or _is_back(np.array(face)):
        return None
    cpath = dest_prefix.parent / f"{dest_prefix.name}_c{i}.jpg"
    rpath = dest_prefix.parent / f"{dest_prefix.name}_r{i}.jpg"
    face.save(cpath, quality=95)
    rank_crop(face, rpath)
    (dest_prefix.parent / f"{dest_prefix.name}_c{i}.suit").write_text(suit_of(np.array(face)))
    return rpath


def extract_holes(frame: Path, tag: str) -> int:
    try:
        im = Image.open(frame).convert("RGB")
    except OSError:
        return 0
    crop = bottom_crop(im)
    boxes = hole_boxes(np.array(crop))
    if len(boxes) != 2:
        return 0
    for i, box in enumerate(boxes):
        if _save_face(crop.crop(box), HOLE / tag, i) is None:
            return 0
    return 2


def extract_board(frame: Path, tag: str) -> int:
    try:
        im = Image.open(frame).convert("RGB")
    except OSError:
        return 0
    crop = board_crop(im)
    boxes = board_boxes(np.array(crop))
    if len(boxes) < 3:
        return 0
    for i, box in enumerate(boxes):
        if _save_face(crop.crop(box), BOARD / tag, i) is None:
            return 0
    return len(boxes)


def ocr_ranks(paths: list[Path]) -> dict[str, str]:
    if not paths:
        return {}
    lst = HOLE / "ocr_ranks.txt"
    lst.parent.mkdir(parents=True, exist_ok=True)
    lst.write_text("\n".join(str(p.resolve()) for p in paths) + "\n")
    p = subprocess.run(["swift", str(SWIFT), str(lst)], capture_output=True, text=True, timeout=600)
    out = (p.stdout or "").strip()
    if not out:
        return {}
    try:
        boxes = json.loads(out)
    except json.JSONDecodeError:
        return {}
    by: dict[str, list[tuple[float, str]]] = {}
    for b in boxes:
        by.setdefault(b["path"], []).append((float(b.get("conf") or 0), b.get("text") or ""))
    ranks = {}
    for path, cands in by.items():
        cands.sort(reverse=True)
        for _, text in cands:
            rk = parse_rank(text)
            if rk:
                ranks[path] = rk
                break
    return ranks


def rank_69_from_image(path: Path) -> str | None:
    """6 vs 9 by ink mass: 6 heavier on the bottom, 9 on the top."""
    try:
        arr = np.array(Image.open(path).convert("L"))
    except OSError:
        return None
    ink = arr < 150
    if ink.mean() < 0.04:
        return None
    h = ink.shape[0]
    top, bot = float(ink[: h // 2].mean()), float(ink[h // 2 :].mean())
    if bot > top * 1.12:
        return "6"
    if top > bot * 1.12:
        return "9"
    return None


def _fix_69(root: Path, tag: str, i: int, rk: str) -> str:
    if rk not in {"6", "9"}:
        return rk
    for k in ("r", "rb", "c"):
        p = root / f"{tag}_{k}{i}.jpg"
        if p.is_file():
            g = rank_69_from_image(p)
            if g:
                return g
    return rk


def _cards_from(root: Path, tag: str, n: int, ranks: dict[str, str]) -> str | None:
    got = []
    for i in range(n):
        suit = (root / f"{tag}_c{i}.suit").read_text() if (root / f"{tag}_c{i}.suit").exists() else ""
        rk = None
        for k in ("r", "rb", "c"):
            rk = ranks.get(str((root / f"{tag}_{k}{i}.jpg").resolve()))
            if rk:
                break
        if rk:
            rk = _fix_69(root, tag, i, rk)
        if not rk or not suit:
            return None
        got.append(rk + suit)
    if n == 2 and got[0] == got[1]:
        return None
    return " ".join(got)


def holes_from_tag(tag: str, ranks: dict[str, str]) -> str | None:
    return _cards_from(HOLE, tag, 2, ranks)


def board_from_tag(tag: str, n: int, ranks: dict[str, str]) -> str | None:
    return _cards_from(BOARD, tag, n, ranks)


def card_eq(a: str, b: str) -> bool:
    if a == b:
        return True
    if a[1:] == b[1:] and {a[0], b[0]} <= {"6", "9"}:
        return True
    return a[0] == b[0] and {a[1], b[1]} <= {"C", "S"}


def board_compatible(b1: str | None, b2: str | None) -> bool:
    if not b1 or not b2:
        return True
    a, b = b1.split(), b2.split()
    n = min(len(a), len(b))
    return all(card_eq(x, y) for x, y in zip(a[:n], b[:n]))


def holes_compatible(h1: str | None, h2: str | None) -> bool:
    if not h1 or not h2:
        return True
    a, b = h1.split(), h2.split()
    if len(a) != 2 or len(b) != 2:
        return True
    return (card_eq(a[0], b[0]) and card_eq(a[1], b[1])) or (card_eq(a[0], b[1]) and card_eq(a[1], b[0]))
