# Manual posting checklist

Posting is done by hand. The pipeline does the hard part (generate → deliverables);
this is the fast 5-minute step. Each `output/<name>/` folder has everything you need.

## What's in each output folder
| File | Use for |
|------|---------|
| `vertical.mp4` | YouTube Shorts, Instagram Reels, TikTok, X video |
| `square.mp4` | Instagram/X feed post |
| `still.png` | Photo post, carousel cover, print-on-demand source |
| `thumb.jpg` | YouTube thumbnail |
| `metadata.json` | Title / caption / hashtags (once `metadata.py` lands) |

## Daily routine (per clip)
1. **Pick** a clip from `output/` you're happy with (quality-gate: would *you* stop scrolling?).
2. **YouTube Shorts** — upload `vertical.mp4`, set `thumb.jpg`, paste title + description.
3. **Instagram Reels** — upload `vertical.mp4`, paste caption + hashtags. Square feed: `square.mp4`.
4. **X** — post `vertical.mp4` or `square.mp4`. Put any link in a **reply**, not the post.
5. **TikTok** (optional) — upload `vertical.mp4`.
6. **Log** the post in `analytics/log.csv` (date, name, platform) so you can rank winners later.

## Rules that protect monetization
- **Audio must be cleared** — CC / royalty-free / your own. Borrowed music blocks ad revenue.
- **No noise-spam.** Every post needs a point of view; near-identical batch dumps get de-ranked.
- **X links cost money via API** and hurt reach in-post — keep them in replies/bio.

## When to automate this away
Only after a format has *proven* it resonates (Phase 2). At that point implement a
`Publisher` (see `__init__.py`) for YouTube first (free Data API), keep IG/X manual until
their access/cost tradeoffs are worth it.
