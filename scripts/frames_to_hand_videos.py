#!/usr/bin/env python3
"""把 0713 图+JSON 按「一手一个视频」切片（按时间戳真实时长）。

切点：公牌从 3～5 张清零后的下一手开局，或 D 钮换到下一座位且站稳。
Hero 底牌只用来给文件命名，不用来切。
「等待下一手」挂在上手末尾。
"""

from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

SEAT_RE = re.compile(r"^P[0-8]$")
TOKEN_RE = re.compile(r"^([0-9a-f]+)_\d+$", re.I)


def val(obj, *path):
    cur = obj
    for k in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    if isinstance(cur, dict) and "value" in cur:
        return cur["value"]
    return cur


def load_frames(src: Path) -> list[dict]:
    frames = []
    for jp in sorted(src.glob("*.json")):
        jpg = jp.with_suffix(".jpg")
        if not jpg.exists():
            continue
        d = json.loads(jp.read_text(encoding="utf-8"))
        players = d.get("players") or []
        table = d.get("table") or {}
        hero = None
        dealer = None
        p0_status = None
        for pl in players:
            seat = val(pl, "seat")
            if val(pl, "dealer") in ("1", 1, "true", True) and isinstance(seat, str) and SEAT_RE.match(seat):
                dealer = seat
            if seat == "P0":
                p0_status = val(pl, "status")
                cards = tuple(
                    (c.get("value") if isinstance(c, dict) else c) for c in (pl.get("cards") or [])
                )
                if len(cards) == 2 and all(isinstance(x, str) and len(x) >= 2 and x != "XX" for x in cards):
                    hero = tuple(sorted(cards))
        cc = tuple(
            (c.get("value") if isinstance(c, dict) else c) for c in (table.get("community_cards") or [])
        )
        cc_ok = (
            cc
            if 0 <= len(cc) <= 5 and all(isinstance(x, str) and x not in ("", "XX") and len(x) >= 2 for x in cc)
            else None
        )
        pot = val(table, "pot")
        try:
            pot_n = float(str(pot).replace(",", "")) if pot not in (None, "") else None
        except ValueError:
            pot_n = None
        stem = jp.stem
        ts = int(stem.split("_", 1)[1])
        m = TOKEN_RE.match(stem)
        token = m.group(1) if m else stem.split("_", 1)[0]
        frames.append(
            {
                "stem": stem,
                "ts": ts,
                "dealer": dealer,
                "hero": hero,
                "cc_ok": cc_ok,
                "p0_status": p0_status,
                "pot": pot_n,
                "n_players": len(players),
                "jpg": jpg,
                "token": token,
            }
        )
    if not frames:
        raise SystemExit(f"no paired jpg+json in {src}")
    return frames


def next_seat(dealer: str | None) -> str | None:
    if not dealer or not SEAT_RE.match(dealer):
        return None
    return f"P{(int(dealer[1]) + 1) % 9}"


def majority_hero(frames: list[dict], a: int, b: int):
    c = Counter(f["hero"] for f in frames[a:b] if f["hero"])
    return c.most_common(1)[0][0] if c else None


def majority_dealer(frames: list[dict], a: int, b: int) -> str:
    c = Counter(f["dealer"] for f in frames[a:b] if f["dealer"])
    return c.most_common(1)[0][0] if c else ""


def first_stable_dealer(frames: list[dict], start: int, persist: int = 8) -> str | None:
    n = len(frames)
    i = start
    while i < n:
        d = frames[i]["dealer"]
        if not d:
            i += 1
            continue
        j = i
        while j < n and frames[j]["dealer"] == d:
            j += 1
        if (j - i) >= persist:
            return d
        i = j
    return majority_dealer(frames, start, min(start + 40, n))


def hand_segments(frames: list[dict]) -> list[tuple[int, int, str, object]]:
    """公牌清零后的下一手开局，或 D 钮换到下一座位且站稳。等待帧留在上手。"""
    n = len(frames)
    segs: list[tuple[int, int, str, object]] = []
    i = 0
    empty_need = 3  # ~1s 空公牌，标记上手结束
    fold_need = 8
    new_deal_pot = 280.0

    while i < n:
        committed_d = first_stable_dealer(frames, i)
        had_flop = False
        last_flop3 = None
        ending = False
        empty_run = 0
        fold_run = 0
        j = i
        cut = n
        while j < n:
            f = frames[j]
            board = f["cc_ok"]
            if board is not None and len(board) >= 3:
                had_flop = True
                last_flop3 = board[:3]
                ending = False
                empty_run = 0
                fold_run = 0
            if had_flop and board is not None and len(board) == 0:
                empty_run += 1
                if empty_run >= empty_need:
                    ending = True
            elif board is None or len(board) != 0:
                empty_run = 0

            if f["p0_status"] == "FOLD":
                fold_run += 1
                if not had_flop and fold_run >= fold_need:
                    ending = True
            else:
                fold_run = 0

            if j > i + 12 and ending:
                new_flop = (
                    board is not None
                    and len(board) == 3
                    and last_flop3 is not None
                    and board[:3] != last_flop3
                )
                pot = f["pot"]
                new_deal = (
                    f["p0_status"] == "HOLD"
                    and f["hero"]
                    and (board is None or len(board) == 0)
                    and pot is not None
                    and pot <= new_deal_pot
                )
                # 底牌完全不同才算新手；只差一张多半是 OCR。D 换到下一座可确认。
                hero_now = f["hero"]
                hero_cur = majority_hero(frames, i, j)
                share = len(set(hero_now) & set(hero_cur)) if hero_now and hero_cur else -1
                new_hole = share == 0
                d_advanced = bool(committed_d and f["dealer"] == next_seat(committed_d))
                if new_flop or (new_deal and (new_hole or d_advanced)):
                    cut = j
                    break
            j += 1

        if cut <= i:
            cut = n
        segs.append((i, cut, majority_dealer(frames, i, cut), majority_hero(frames, i, cut)))
        if cut >= n:
            break
        i = cut

    return segs


RANK_ORDER = "AKQJT98765432"


def hole_id(hero: tuple[str, str] | None) -> str:
    if not hero:
        return "UNK"

    def key(card: str) -> tuple:
        r = RANK_ORDER.find(card[0].upper()) if card else 99
        return (r if r >= 0 else 99, card[1:])

    return "".join(sorted(hero, key=key))


def segment_duration_s(frames: list[dict], a: int, b: int) -> float:
    t0 = frames[a]["ts"]
    if b < len(frames):
        return (frames[b]["ts"] - t0) / 1000.0
    return (frames[b - 1]["ts"] - t0) / 1000.0 + 0.333


def write_concat(path: Path, frames: list[dict], a: int, b: int) -> None:
    lines = ["ffconcat version 1.0"]
    last = b - 1
    for i in range(a, b):
        jpg = frames[i]["jpg"].resolve().as_posix().replace("'", r"'\''")
        if i < last:
            dt = (frames[i + 1]["ts"] - frames[i]["ts"]) / 1000.0
        elif b < len(frames):
            dt = (frames[b]["ts"] - frames[i]["ts"]) / 1000.0
        else:
            dt = 0.333
        dt = max(dt, 0.05)
        lines.append(f"file '{jpg}'")
        lines.append(f"duration {dt:.6f}")
    # concat demuxer 要求最后一帧再写一次，否则最后 duration 不生效
    jpg = frames[last]["jpg"].resolve().as_posix().replace("'", r"'\''")
    lines.append(f"file '{jpg}'")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def encode_one(ffmpeg: str, concat: Path, out_mp4: Path) -> tuple[str, int, str]:
    cmd = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat),
        "-vf",
        "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "18",
        "-tune",
        "stillimage",
        "-an",
        "-movflags",
        "+faststart",
        "-fps_mode",
        "vfr",
        str(out_mp4),
    ]
    p = subprocess.run(cmd, capture_output=True, text=True)
    err = (p.stderr or p.stdout or "").strip()
    return (out_mp4.name, p.returncode, err)


def ffmpeg_bin() -> str:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def main() -> None:
    src = Path(sys.argv[1] if len(sys.argv) > 1 else "/Users/xixi/Downloads/0713图片和json")
    outdir = Path(sys.argv[2] if len(sys.argv) > 2 else "/Users/xixi/Downloads/0713手牌视频")
    outdir.mkdir(parents=True, exist_ok=True)
    work = outdir / "_concat"
    work.mkdir(exist_ok=True)

    frames = load_frames(src)
    segs = hand_segments(frames)

    used_names: set[str] = set()
    jobs = []
    rows = []
    for idx, (a, b, dealer, hero) in enumerate(segs, 1):
        hole = hole_id(hero)
        token = frames[a]["token"]
        start_ts = frames[a]["ts"]
        name = f"{hole}_{token}_{start_ts}.mp4"
        if name in used_names:
            name = f"{hole}_{token}_{start_ts}_{idx:02d}.mp4"
        used_names.add(name)
        concat = work / f"H{idx:03d}.ffconcat"
        write_concat(concat, frames, a, b)
        out_mp4 = outdir / name
        jobs.append((idx, concat, out_mp4, a, b, dealer, hole, start_ts))
        rows.append(
            {
                "hand": f"H{idx:03d}",
                "file": name,
                "dealer": dealer,
                "hero": hole,
                "start_ts": start_ts,
                "end_ts": frames[min(b, len(frames) - 1)]["ts"] if b <= len(frames) else frames[-1]["ts"],
                "n_frames": b - a,
                "duration_s": round(segment_duration_s(frames, a, b), 3),
                "first_jpg": frames[a]["jpg"].name,
                "last_jpg": frames[b - 1]["jpg"].name,
            }
        )

    man = outdir / "manifest.csv"
    with man.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"frames={len(frames)} hands={len(segs)} manifest={man}")
    for r in rows:
        print(f"{r['hand']} n={r['n_frames']:4d} {r['duration_s']:7.1f}s D={r['dealer']} {r['hero']} {r['file']}")

    ff = ffmpeg_bin()
    ok = 0
    fail = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(encode_one, ff, c, o): (idx, o) for idx, c, o, *_ in jobs}
        for fut in as_completed(futs):
            idx, o = futs[fut]
            name, code, err = fut.result()
            if code == 0 and o.exists() and o.stat().st_size > 0:
                ok += 1
                print(f"OK  {name}")
            else:
                fail.append((name, code, err))
                print(f"FAIL {name} code={code}\n{err}")

    print(f"done ok={ok}/{len(jobs)} fail={len(fail)}")
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
