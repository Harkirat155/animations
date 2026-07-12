"""Waitlist registration — D1 first, then R2, then local JSONL.

Order matches product intent: queryable SQL in D1 for Maker signups;
R2 remains available for render blobs later.
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend import d1, r2

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_email(email: str) -> str:
    e = email.strip().lower()
    if not _EMAIL_RE.match(e) or len(e) > 254:
        raise ValueError("Invalid email")
    return e


def register(
    email: str,
    *,
    ip: str | None = None,
    source: str | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    email = validate_email(email)
    name_clean = (name or "").strip()[:120] or None
    source_clean = (source or "composer").strip()[:80]

    # 1) D1 (preferred)
    if d1.configured():
        return d1.register_waitlist(
            email, ip=ip, source=source_clean, name=name_clean
        )

    # 2) R2 (if S3 keys present)
    if r2.configured():
        return r2.register_waitlist(
            email, ip=ip, source=source_clean, name=name_clean
        )

    # 3) Local JSONL (dev only)
    path = Path(os.environ.get("WAITLIST_PATH", "analytics/waitlist.jsonl"))
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                if json.loads(line).get("email") == email:
                    return {"ok": True, "status": "already", "email": email, "storage": "local"}
            except json.JSONDecodeError:
                continue
    entry = {
        "email": email,
        "name": name_clean,
        "source": source_clean,
        "ts": time.time(),
        "iso": datetime.now(timezone.utc).isoformat(),
        "ip": ip,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return {"ok": True, "status": "joined", "email": email, "storage": "local"}


def storage_status() -> dict[str, Any]:
    return {
        **d1.health_info(),
        "r2_configured": r2.configured(),
        "r2_bucket": os.environ.get("R2_BUCKET", "animations"),
        "waitlist_backend": (
            "d1" if d1.configured() else "r2" if r2.configured() else "local"
        ),
    }
