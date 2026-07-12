"""Cloudflare D1 client (HTTP API) for Lumen.

Primary durable store for waitlist and future app rows (users, render jobs).

Env (Fly secrets):
  CLOUDFLARE_ACCOUNT_ID   default: f23d40d6e8e5a8ba907fec5d01d3f37b
  CLOUDFLARE_API_TOKEN    Account API token with D1:Edit (required for production)
  D1_DATABASE_ID          default: f7c44f86-9b4c-4e5e-9033-00fb12c44587
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

_DEFAULT_ACCOUNT = "f23d40d6e8e5a8ba907fec5d01d3f37b"
_DEFAULT_DB = "f7c44f86-9b4c-4e5e-9033-00fb12c44587"

# Applied once per process when first query runs.
_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS waitlist (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL COLLATE NOCASE,
  name TEXT,
  source TEXT DEFAULT 'composer',
  ip TEXT,
  created_at TEXT NOT NULL,
  UNIQUE(email)
);
CREATE INDEX IF NOT EXISTS idx_waitlist_created ON waitlist(created_at);

CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL COLLATE NOCASE,
  created_at TEXT NOT NULL,
  UNIQUE(email)
);

CREATE TABLE IF NOT EXISTS render_jobs (
  id TEXT PRIMARY KEY,
  user_id TEXT,
  template TEXT NOT NULL,
  params_json TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'queued',
  r2_prefix TEXT,
  error TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_render_jobs_status ON render_jobs(status);
"""

_schema_ready = False


class D1Error(Exception):
    def __init__(self, message: str, status: int | None = None, body: Any = None):
        super().__init__(message)
        self.status = status
        self.body = body


class D1NotConfigured(Exception):
    pass


def configured() -> bool:
    return bool(os.environ.get("CLOUDFLARE_API_TOKEN") or os.environ.get("CF_API_TOKEN"))


def _token() -> str:
    tok = os.environ.get("CLOUDFLARE_API_TOKEN") or os.environ.get("CF_API_TOKEN")
    if not tok:
        raise D1NotConfigured(
            "CLOUDFLARE_API_TOKEN (or CF_API_TOKEN) must be set for D1 access"
        )
    return tok


def _account() -> str:
    return os.environ.get("CLOUDFLARE_ACCOUNT_ID", _DEFAULT_ACCOUNT).strip()


def _db_id() -> str:
    return os.environ.get("D1_DATABASE_ID", _DEFAULT_DB).strip()


def query(sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
    """Run one SQL statement (optionally parameterized). Returns result rows."""
    ensure_schema()
    return _query_raw(sql, params)


def _query_raw(sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
    url = (
        f"https://api.cloudflare.com/client/v4/accounts/{_account()}"
        f"/d1/database/{_db_id()}/query"
    )
    payload: dict[str, Any] = {"sql": sql}
    if params is not None:
        # D1 HTTP API expects JSON-serializable params; stringify non-primitives.
        payload["params"] = [
            p if isinstance(p, (str, int, float, type(None), bool)) else json.dumps(p)
            for p in params
        ]

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {_token()}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(err_body)
        except json.JSONDecodeError:
            parsed = err_body
        raise D1Error(f"D1 HTTP {e.code}: {err_body[:400]}", status=e.code, body=parsed) from e
    except urllib.error.URLError as e:
        raise D1Error(f"D1 network error: {e}") from e

    if not body.get("success"):
        raise D1Error(f"D1 query failed: {body.get('errors')}", body=body)

    results = body.get("result") or []
    # result is a list of statement results; take first statement's rows
    if not results:
        return []
    first = results[0] if isinstance(results, list) else results
    return list(first.get("results") or [])


def ensure_schema() -> None:
    global _schema_ready
    if _schema_ready:
        return
    if not configured():
        raise D1NotConfigured("D1 not configured")
    # Multi-statement: D1 query supports joined statements
    _query_raw(_SCHEMA_SQL)
    _schema_ready = True


def register_waitlist(
    email: str,
    *,
    ip: str | None = None,
    source: str | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    """Insert waitlist row. Returns joined | already."""
    email = email.strip().lower()
    iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    # Check existing
    existing = query("SELECT email, created_at FROM waitlist WHERE email = ? LIMIT 1", [email])
    if existing:
        return {
            "ok": True,
            "status": "already",
            "email": email,
            "created_at": existing[0].get("created_at"),
            "storage": "d1",
        }
    try:
        query(
            "INSERT INTO waitlist (email, name, source, ip, created_at) VALUES (?, ?, ?, ?, ?)",
            [
                email,
                (name or None),
                (source or "composer"),
                ip,
                iso,
            ],
        )
    except D1Error as e:
        # Race: unique constraint
        msg = str(e).lower()
        if "unique" in msg or "constraint" in msg:
            return {"ok": True, "status": "already", "email": email, "storage": "d1"}
        raise
    return {"ok": True, "status": "joined", "email": email, "created_at": iso, "storage": "d1"}


def waitlist_count() -> int:
    rows = query("SELECT COUNT(*) AS n FROM waitlist")
    if not rows:
        return 0
    return int(rows[0].get("n") or 0)


def health_info() -> dict[str, Any]:
    return {
        "d1_configured": configured(),
        "d1_database_id": _db_id(),
        "d1_account_id": _account(),
    }
