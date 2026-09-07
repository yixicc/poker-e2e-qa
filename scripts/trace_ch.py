#!/usr/bin/env python3
"""ClickHouse Trace 查询（对齐 TexasDataCenter traces.py / frames.py）。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from trace_envs import DEFAULT_TRACE_ENV, get_trace_env, normalize_trace_env

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENV_FILE = ROOT / "data" / "trace_ch.env"

_CLIENT_CACHE: dict[str, Any] = {}
_ENV_LOADED = False

_CH_KEYS = ("CH_HOST", "CH_PORT", "CH_USER", "CH_PASSWORD", "CH_HTTP_PROXY")
_PROXY_ENV_KEYS = ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy")


def reset_ch_runtime(*, clear_os_env: bool = False) -> None:
    """Drop cached clients; optionally clear CH_* from process env so file reloads."""
    global _ENV_LOADED
    _CLIENT_CACHE.clear()
    _ENV_LOADED = False
    if clear_os_env:
        for k in _CH_KEYS:
            os.environ.pop(k, None)


def _normalize_proxy_url(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return ""
    if "://" not in s:
        s = "http://" + s
    return s


def _apply_process_proxy(proxy_url: str) -> None:
    """Point urllib3 / clickhouse-connect at an HTTP proxy (Clash etc.)."""
    proxy_url = _normalize_proxy_url(proxy_url)
    if proxy_url:
        for k in _PROXY_ENV_KEYS:
            os.environ[k] = proxy_url
        os.environ["CH_HTTP_PROXY"] = proxy_url
    else:
        for k in _PROXY_ENV_KEYS:
            os.environ.pop(k, None)
        os.environ["CH_HTTP_PROXY"] = ""


def apply_ch_env_overrides(values: dict[str, Any]) -> None:
    """Write CH_* into process env and invalidate client cache."""
    if "host" in values or "CH_HOST" in values:
        os.environ["CH_HOST"] = str(values.get("host") or values.get("CH_HOST") or "")
    if "port" in values or "CH_PORT" in values:
        os.environ["CH_PORT"] = str(values.get("port") or values.get("CH_PORT") or "8123")
    if "user" in values or "CH_USER" in values:
        os.environ["CH_USER"] = str(values.get("user") or values.get("CH_USER") or "root")
    if "password" in values or "CH_PASSWORD" in values:
        pw = values["password"] if "password" in values else values.get("CH_PASSWORD")
        os.environ["CH_PASSWORD"] = "" if pw is None else str(pw)
    if (
        "http_proxy" in values
        or "proxy" in values
        or "CH_HTTP_PROXY" in values
    ):
        raw = (
            values.get("http_proxy")
            if "http_proxy" in values
            else values.get("proxy")
            if "proxy" in values
            else values.get("CH_HTTP_PROXY")
        )
        _apply_process_proxy("" if raw is None else str(raw))
    reset_ch_runtime(clear_os_env=False)


def load_ch_env_file(path: Path = DEFAULT_ENV_FILE) -> dict[str, str]:
    """Read data/trace_ch.env (or defaults from example)."""
    out = {
        "CH_HOST": "",
        "CH_PORT": "8123",
        "CH_USER": "root",
        "CH_PASSWORD": "",
        "CH_HTTP_PROXY": "",
    }
    for candidate in (path, ROOT / "data" / "trace_ch.env.example"):
        if not candidate.is_file():
            continue
        try:
            for line in candidate.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                k = k.strip()
                v = v.strip().strip("'").strip('"')
                if k in out:
                    out[k] = v
            if candidate == path:
                break
        except OSError:
            continue
    # Process env wins for live values
    _load_env_file(path)
    for k in list(out):
        if k in os.environ:
            out[k] = os.environ.get(k) or ""
    # Also accept generic HTTP_PROXY if CH_HTTP_PROXY empty
    if not (out.get("CH_HTTP_PROXY") or "").strip():
        for k in _PROXY_ENV_KEYS:
            if (os.environ.get(k) or "").strip():
                out["CH_HTTP_PROXY"] = os.environ.get(k) or ""
                break
    return out


def save_ch_env_file(
    values: dict[str, Any],
    *,
    path: Path = DEFAULT_ENV_FILE,
    keep_password_if_blank: bool = True,
) -> dict[str, str]:
    """Persist CH settings to gitignored env file and apply to process."""
    cur = load_ch_env_file(path)
    host = str(values.get("host") or values.get("CH_HOST") or cur.get("CH_HOST") or "").strip()
    port = str(values.get("port") or values.get("CH_PORT") or cur.get("CH_PORT") or "8123").strip()
    user = str(values.get("user") or values.get("CH_USER") or cur.get("CH_USER") or "root").strip()
    if "http_proxy" in values or "proxy" in values or "CH_HTTP_PROXY" in values:
        proxy = str(
            values.get("http_proxy")
            if "http_proxy" in values
            else values.get("proxy")
            if "proxy" in values
            else values.get("CH_HTTP_PROXY")
            or ""
        ).strip()
    else:
        proxy = str(cur.get("CH_HTTP_PROXY") or "").strip()
    proxy = _normalize_proxy_url(proxy)
    clear_pw = bool(values.get("clear_password"))
    if clear_pw:
        password = ""
    elif "password" in values:
        password = str(values.get("password") if values.get("password") is not None else "")
        if keep_password_if_blank and password == "" and (cur.get("CH_PASSWORD") or ""):
            password = cur.get("CH_PASSWORD") or ""
    elif "CH_PASSWORD" in values:
        password = str(values.get("CH_PASSWORD") if values.get("CH_PASSWORD") is not None else "")
        if keep_password_if_blank and password == "" and (cur.get("CH_PASSWORD") or ""):
            password = cur.get("CH_PASSWORD") or ""
    else:
        password = cur.get("CH_PASSWORD") or ""

    if not host:
        raise ValueError("CH_HOST 不能为空")
    try:
        int(port)
    except ValueError as e:
        raise ValueError(f"无效 CH_PORT: {port!r}") from e

    path.parent.mkdir(parents=True, exist_ok=True)
    text = (
        "# ClickHouse credentials for Trace (gitignored). Do not commit.\n"
        f"CH_HOST={host}\n"
        f"CH_PORT={port}\n"
        f"CH_USER={user}\n"
        f"CH_PASSWORD={password}\n"
        f"CH_HTTP_PROXY={proxy}\n"
    )
    path.write_text(text, encoding="utf-8")
    apply_ch_env_overrides(
        {
            "host": host,
            "port": port,
            "user": user,
            "password": password,
            "http_proxy": proxy,
        }
    )
    return {
        "CH_HOST": host,
        "CH_PORT": port,
        "CH_USER": user,
        "CH_PASSWORD": password,
        "CH_HTTP_PROXY": proxy,
    }


def ch_settings_public() -> dict[str, Any]:
    """Safe payload for settings UI (password masked)."""
    raw = load_ch_env_file()
    pw = raw.get("CH_PASSWORD") or ""
    try:
        from trace_envs import DEFAULT_TRACE_ENV, get_trace_env

        env = get_trace_env(DEFAULT_TRACE_ENV)
        env_label = env.get("env_label") or DEFAULT_TRACE_ENV
        ch_database = env.get("ch_database") or ""
    except Exception:
        env_label = "uat"
        ch_database = "otel_uat"
    return {
        "host": raw.get("CH_HOST") or "",
        "port": raw.get("CH_PORT") or "8123",
        "user": raw.get("CH_USER") or "root",
        "password_set": bool(pw),
        "http_proxy": raw.get("CH_HTTP_PROXY") or "",
        "trace_env": "uat",
        "env_label": env_label,
        "ch_database": ch_database,
        "env_path": "data/trace_ch.env",
    }


def test_ch_connection(
    env_id: Optional[str] = None,
    *,
    overrides: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Ping ClickHouse with a trivial query. Optional overrides apply only for this call."""
    saved: dict[str, str] = {}
    saved_missing: list[str] = []
    watch_keys = list(_CH_KEYS) + list(_PROXY_ENV_KEYS)
    if overrides:
        for key in watch_keys:
            if key in os.environ:
                saved[key] = os.environ[key]
            else:
                saved_missing.append(key)
        apply_ch_env_overrides(overrides)
    try:
        client, env = get_ch_client(env_id)
        db = env["ch_database"]
        result = client.query("SELECT 1 AS ok, currentDatabase() AS db")
        rows = _rows_from_result(result)
        row = rows[0] if rows else {}
        return {
            "ok": True,
            "database": db,
            "current_database": row.get("db") or db,
            "env_id": env["id"],
            "env_label": env.get("env_label") or env["id"],
            "host": (os.environ.get("CH_HOST") or "").strip(),
            "http_proxy": (os.environ.get("CH_HTTP_PROXY") or os.environ.get("HTTP_PROXY") or "").strip(),
        }
    finally:
        if overrides:
            for key in watch_keys:
                if key in saved:
                    os.environ[key] = saved[key]
                elif key in saved_missing:
                    os.environ.pop(key, None)
            reset_ch_runtime(clear_os_env=False)


def _load_env_file(path: Path = DEFAULT_ENV_FILE) -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True
    # Also honor process env; file fills missing keys only.
    candidates = [
        path,
        ROOT / ".env",
        Path(os.environ.get("TRACE_CH_ENV", "") or ""),
    ]
    for p in candidates:
        if not p or not str(p) or not p.is_file():
            continue
        try:
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                k = k.strip()
                v = v.strip().strip("'").strip('"')
                if k and k not in os.environ:
                    os.environ[k] = v
        except OSError:
            continue


def ch_connection_settings() -> dict[str, Any]:
    _load_env_file()
    host = (os.environ.get("CH_HOST") or "").strip()
    user = (os.environ.get("CH_USER") or "").strip() or "root"
    password = os.environ.get("CH_PASSWORD")
    if password is None:
        password = ""
    port_s = (os.environ.get("CH_PORT") or "8123").strip()
    try:
        port = int(port_s)
    except ValueError as e:
        raise RuntimeError(f"无效 CH_PORT: {port_s!r}") from e
    if not host:
        raise RuntimeError(
            "未配置 CH_HOST。请复制 data/trace_ch.env.example 为 data/trace_ch.env 并填写凭证。"
        )
    proxy = _normalize_proxy_url(
        (os.environ.get("CH_HTTP_PROXY") or os.environ.get("HTTP_PROXY") or "").strip()
    )
    if proxy:
        _apply_process_proxy(proxy)
    return {
        "host": host,
        "port": port,
        "username": user,
        "password": password,
        "http_proxy": proxy,
    }


def get_ch_client(env_id: Optional[str] = None):
    """Return a clickhouse-connect client bound to the env database."""
    eid = normalize_trace_env(env_id)
    conn = ch_connection_settings()
    cache_key = f"{eid}|{conn['host']}|{conn['port']}|{conn['username']}|{conn.get('http_proxy') or ''}"
    if cache_key in _CLIENT_CACHE:
        return _CLIENT_CACHE[cache_key], get_trace_env(eid)

    try:
        import clickhouse_connect
    except ImportError as e:
        raise RuntimeError(
            "缺少依赖 clickhouse-connect，请执行: pip install -r requirements.txt"
        ) from e

    env = get_trace_env(eid)
    client = clickhouse_connect.get_client(
        host=conn["host"],
        port=conn["port"],
        username=conn["username"],
        password=conn["password"],
        database=str(env["ch_database"]),
        connect_timeout=15,
        send_receive_timeout=60,
    )
    _CLIENT_CACHE[cache_key] = client
    return client, env


def _rows_from_result(result) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for r in result.named_results():
        row = dict(r)
        for k, v in list(row.items()):
            if hasattr(v, "isoformat"):
                row[k] = v.isoformat()
        rows.append(row)
    return rows


def _escape_lit(s: str) -> str:
    """Minimal escaping for Map attribute equality (TDC style)."""
    return str(s).replace("\\", "\\\\").replace("'", "\\'")


def ch_trace_query(
    *,
    env_id: Optional[str] = None,
    open_id: str = "",
    hole_cards: str = "",
    start_time: str = "",
    end_time: str = "",
) -> list[dict[str, Any]]:
    client, env = get_ch_client(env_id)
    db = env["ch_database"]
    conditions: list[str] = []
    if open_id:
        conditions.append(f"SpanAttributes['business.openId']='{_escape_lit(open_id)}'")
    if hole_cards:
        conditions.append(f"SpanAttributes['business.holeCards']='{_escape_lit(hole_cards)}'")
    if start_time:
        conditions.append(f"Timestamp>='{_escape_lit(start_time)}'")
    if end_time:
        conditions.append(f"Timestamp<='{_escape_lit(end_time)}'")
    if not conditions:
        return []

    sql = (
        f"SELECT *, sum(gap) OVER (ORDER BY Timestamp) AS session_id"
        f" FROM (SELECT *,"
        f" if(Timestamp - lagInFrame(Timestamp) OVER (ORDER BY Timestamp) > 300, 1, 0) AS gap"
        f" FROM (SELECT * FROM {db}.otel_traces WHERE "
        + " AND ".join(conditions)
        + ")) ORDER BY Timestamp ASC LIMIT 1000"
    )
    try:
        result = client.query(sql)
        return _rows_from_result(result)
    except Exception as e:
        raise RuntimeError(f"ClickHouse traceQuery 失败 ({env['id']}): {e}") from e


def ch_trace_discover(
    *,
    env_id: Optional[str] = None,
    start_time: str,
    end_time: str,
) -> list[dict[str, Any]]:
    client, env = get_ch_client(env_id)
    db = env["ch_database"]
    st = _escape_lit(start_time)
    et = _escape_lit(end_time)
    sql = (
        f"SELECT openId, holeCards,"
        f" min(Timestamp) AS firstSeen,"
        f" max(Timestamp) AS lastSeen,"
        f" count() AS spanCount,"
        f" session_id"
        f" FROM ("
        f" SELECT openId, holeCards, Timestamp,"
        f" sum(gap) OVER (PARTITION BY openId, holeCards ORDER BY Timestamp) AS session_id"
        f" FROM ("
        f" SELECT SpanAttributes['business.openId'] AS openId,"
        f" SpanAttributes['business.holeCards'] AS holeCards,"
        f" Timestamp,"
        f" if(Timestamp - lagInFrame(Timestamp) OVER ("
        f" PARTITION BY SpanAttributes['business.openId'], SpanAttributes['business.holeCards']"
        f" ORDER BY Timestamp) > 300, 1, 0) AS gap"
        f" FROM {db}.otel_traces"
        f" WHERE Timestamp>='{st}' AND Timestamp<='{et}'"
        f" AND SpanAttributes['business.openId']!=''"
        f" AND SpanAttributes['business.holeCards']!=''"
        f" )) GROUP BY openId, holeCards, session_id"
        f" ORDER BY firstSeen DESC"
        f" LIMIT 500"
    )
    try:
        result = client.query(sql)
        return _rows_from_result(result)
    except Exception as e:
        raise RuntimeError(f"ClickHouse traceDiscover 失败 ({env['id']}): {e}") from e


def ch_image_frames_by_keys(
    *,
    env_id: Optional[str] = None,
    open_id: str,
    msg_keys: list[Any],
) -> list[dict[str, Any]]:
    if not msg_keys:
        return []
    key_list: list[int] = []
    for p in msg_keys:
        try:
            key_list.append(int(p))
        except (TypeError, ValueError):
            continue
    if not key_list:
        return []

    client, env = get_ch_client(env_id)
    db = env["ch_database"]
    in_clause = ",".join(str(k) for k in key_list)
    sql = (
        f"SELECT JSONExtractUInt(JSONExtractRaw(json_content, 'parameters'), 'time_stamp') AS msg_key,"
        f" oss_url, oss_bucket, json_content, timestamp, received_at, userid"
        f" FROM {db}.image_upload_records"
        f" WHERE userid = %(oid)s"
        f" AND timestamp IN ({in_clause})"
        f" ORDER BY timestamp ASC LIMIT 500"
    )
    try:
        result = client.query(sql, parameters={"oid": open_id})
        return _rows_from_result(result)
    except Exception as e:
        raise RuntimeError(f"ClickHouse imageFramesByKeys 失败 ({env['id']}): {e}") from e


def ch_image_frames_by_range(
    *,
    env_id: Optional[str] = None,
    open_id: str,
    min_msg_key: Any,
    max_msg_key: Any,
) -> list[dict[str, Any]]:
    client, env = get_ch_client(env_id)
    db = env["ch_database"]
    sql = (
        f"SELECT timestamp AS msg_key,"
        f" oss_url, oss_bucket, json_content, timestamp, received_at, userid"
        f" FROM {db}.image_upload_records"
        f" WHERE userid = %(oid)s"
        f" AND timestamp >= %(min_ts)s"
        f" AND timestamp <= %(max_ts)s"
        f" ORDER BY timestamp ASC LIMIT 500"
    )
    try:
        result = client.query(
            sql,
            parameters={
                "oid": open_id,
                "min_ts": int(min_msg_key),
                "max_ts": int(max_msg_key),
            },
        )
        return _rows_from_result(result)
    except Exception as e:
        raise RuntimeError(f"ClickHouse imageFramesByRange 失败 ({env['id']}): {e}") from e


def ping_ch(env_id: Optional[str] = None) -> dict[str, Any]:
    """Lightweight connectivity check."""
    client, env = get_ch_client(env_id or DEFAULT_TRACE_ENV)
    client.query("SELECT 1")
    return {"ok": True, "env": env["id"], "database": env["ch_database"]}
