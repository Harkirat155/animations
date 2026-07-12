"""S3-compatible Cloudflare R2 client for Lumen.

Configured via env (set as Fly secrets in production):

  R2_ACCOUNT_ID          — Cloudflare account id (also embedded in endpoint)
  R2_ACCESS_KEY_ID       — R2 API token access key
  R2_SECRET_ACCESS_KEY   — R2 API token secret
  R2_BUCKET              — default: animations
  R2_ENDPOINT            — optional full endpoint override
                           default: https://{account_id}.r2.cloudflarestorage.com

Waitlist objects land under waitlist/ as individual JSON files so concurrent
signups never clobber each other. Local file fallback when R2 is not configured.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Defaults from the bucket the product owns.
_DEFAULT_ACCOUNT = "f23d40d6e8e5a8ba907fec5d01d3f37b"
_DEFAULT_BUCKET = "animations"


class R2NotConfigured(Exception):
    pass


def _endpoint() -> str:
    explicit = os.environ.get("R2_ENDPOINT", "").strip().rstrip("/")
    if explicit:
        # Accept either bare endpoint or .../bucket form; strip trailing bucket.
        bucket = os.environ.get("R2_BUCKET", _DEFAULT_BUCKET)
        if explicit.endswith(f"/{bucket}"):
            return explicit[: -(len(bucket) + 1)]
        return explicit
    account = os.environ.get("R2_ACCOUNT_ID", _DEFAULT_ACCOUNT).strip()
    return f"https://{account}.r2.cloudflarestorage.com"


def configured() -> bool:
    return bool(
        os.environ.get("R2_ACCESS_KEY_ID") and os.environ.get("R2_SECRET_ACCESS_KEY")
    )


def _client():
    if not configured():
        raise R2NotConfigured(
            "R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY must be set"
        )
    try:
        import boto3
        from botocore.config import Config
    except ImportError as e:
        raise R2NotConfigured("boto3 is required for R2") from e

    return boto3.client(
        "s3",
        endpoint_url=_endpoint(),
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
        config=Config(signature_version="s3v4"),
    )


def _bucket() -> str:
    return os.environ.get("R2_BUCKET", _DEFAULT_BUCKET)


def put_json(key: str, payload: dict[str, Any]) -> str:
    """Write a JSON object to R2. Returns the object key."""
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    client = _client()
    client.put_object(
        Bucket=_bucket(),
        Key=key,
        Body=body,
        ContentType="application/json",
    )
    return key


def object_exists(key: str) -> bool:
    client = _client()
    try:
        client.head_object(Bucket=_bucket(), Key=key)
        return True
    except Exception:
        return False


def email_fingerprint(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()[:16]


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(email: str) -> str:
    return email.strip().lower()


def validate_email(email: str) -> str:
    e = normalize_email(email)
    if not _EMAIL_RE.match(e) or len(e) > 254:
        raise ValueError("Invalid email")
    return e


def waitlist_keys(email: str) -> tuple[str, str]:
    """Return (dedupe key, entry key) for a waitlist signup."""
    fp = email_fingerprint(email)
    now = datetime.now(timezone.utc)
    dedupe = f"waitlist/by-email/{fp}.json"
    entry = f"waitlist/entries/{now.strftime('%Y/%m')}/{int(now.timestamp())}-{fp}.json"
    return dedupe, entry


def register_waitlist(
    email: str,
    *,
    ip: str | None = None,
    source: str | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    """Register an email on the Maker waitlist.

    Uses R2 when configured; otherwise appends to a local JSONL file so
    development still works. Returns {ok, status: 'joined'|'already', email}.
    """
    email = validate_email(email)
    entry = {
        "email": email,
        "name": (name or "").strip()[:120] or None,
        "source": (source or "composer").strip()[:80],
        "ts": time.time(),
        "iso": datetime.now(timezone.utc).isoformat(),
        "ip": ip,
    }

    if configured():
        dedupe_key, entry_key = waitlist_keys(email)
        if object_exists(dedupe_key):
            return {"ok": True, "status": "already", "email": email}
        put_json(entry_key, entry)
        # Dedupe marker — last-write-wins is fine; existence is what matters.
        put_json(dedupe_key, {"email": email, "first_seen": entry["iso"], "entry": entry_key})
        return {"ok": True, "status": "joined", "email": email, "key": entry_key}

    # Local fallback (dev / R2 not wired yet)
    path = Path(os.environ.get("WAITLIST_PATH", "analytics/waitlist.jsonl"))
    path.parent.mkdir(parents=True, exist_ok=True)
    # Soft dedupe against local file
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                if json.loads(line).get("email") == email:
                    return {"ok": True, "status": "already", "email": email}
            except json.JSONDecodeError:
                continue
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return {"ok": True, "status": "joined", "email": email, "storage": "local"}
