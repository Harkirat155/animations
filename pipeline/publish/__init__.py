"""Publishing layer — SCAFFOLD ONLY. Posting is currently MANUAL (see POSTING.md).

This defines the interface a future auto-publisher would implement, so the
pipeline can be automated later without restructuring. None of these actually
call a platform API today — they raise NotImplementedError by design.

Why manual for now (decided with the user):
  - X: no free API tier since 2026-02-06 (pay-per-use; $0.20/post with a URL).
  - Instagram: Graph API publishing needs Meta app review (often delayed/rejected
    for solo creators).
  - YouTube Data API works free within quota, but isn't worth wiring until a
    format is proven to resonate.
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol


class Publisher(Protocol):
    """Contract a real platform publisher would satisfy."""

    platform: str

    def publish(self, deliverable: Path, caption: str, metadata: dict) -> str:
        """Upload `deliverable` with `caption`; return the post URL/id."""
        ...


class ManualPublisher:
    """The current 'publisher': it doesn't post — it tells you what to do by hand."""

    def __init__(self, platform: str) -> None:
        self.platform = platform

    def publish(self, deliverable: Path, caption: str, metadata: dict) -> str:
        raise NotImplementedError(
            f"Posting to {self.platform} is manual — see pipeline/publish/POSTING.md. "
            f"Post {deliverable} with the caption from metadata."
        )
