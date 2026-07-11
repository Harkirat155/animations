"""Post-production spine: a square 'master' clip -> ready-to-post deliverables.

Given a 1:1 master mp4 (what every template renders), produce:
  - vertical.mp4  9:16 1080x1920 (Shorts / Reels / TikTok) with a blurred fill bg
  - square.mp4    1:1 1080x1080  (feed posts)
  - still.png     high-res single frame (the 'photo' deliverable)
  - thumb.jpg     thumbnail
plus an optional seamless boomerang loop, royalty-free audio, and a watermark.

Everything is ffmpeg, deterministic, and unattended. CLI:

    .venv/bin/python -m pipeline.post --master output/foo/master.mp4 --name foo \
        --audio assets/audio/bed.mp3 --watermark-text "@yourhandle" --loop boomerang
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from pipeline.encode import probe_dims, require_ffmpeg, run_checked

SYSTEM_FONTS = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial.ttf",
]

# x264 quality: near-lossless for intermediates (avoid generational softening of
# the crisp cell boundaries), normal for the final encode.
_CRF_INTERMEDIATE = "12"
_CRF_FINAL = "18"


def _run(args: list[str]) -> None:
    run_checked(args)


def _ff(*args: str) -> list[str]:
    return [require_ffmpeg(), "-y", *args]


def _x264(crf: str = _CRF_FINAL) -> list[str]:
    return ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", crf]


def find_font() -> str | None:
    return next((f for f in SYSTEM_FONTS if Path(f).exists()), None)


def make_boomerang(master: Path, out: Path, n_frames: int | None = None) -> Path:
    """Forward + reverse = palindrome loop. Trim the reversed segment so the seam
    frame (last forward == first reverse) and the wrap frame (first forward == last
    reverse) are not duplicated — otherwise the loop stutters at both junctions."""
    if n_frames and n_frames > 2:
        rev = f"[0:v]reverse,trim=start_frame=1:end_frame={n_frames - 1},setpts=PTS-STARTPTS[r]"
    else:
        # Unknown length: at least drop the more-visible mid-loop seam duplicate.
        rev = "[0:v]reverse,trim=start_frame=1,setpts=PTS-STARTPTS[r]"
    _run(_ff("-i", str(master),
             "-filter_complex", f"{rev};[0:v][r]concat=n=2:v=1[v]",
             "-map", "[v]", *_x264(_CRF_INTERMEDIATE), str(out)))
    return out


def make_vertical(master: Path, out: Path, blur_bg: bool = True) -> Path:
    """9:16 1080x1920. Centered square over a blurred, zoomed copy of itself."""
    if blur_bg:
        fc = (
            "[0:v]scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos,"
            "crop=1080:1920,gblur=sigma=24[bg];"
            "[0:v]scale=1080:1080:force_original_aspect_ratio=decrease:flags=lanczos[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2"
        )
    else:
        fc = ("[0:v]scale=1080:1080:force_original_aspect_ratio=decrease:flags=lanczos,"
              "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black")
    _run(_ff("-i", str(master), "-filter_complex", fc,
             *_x264(_CRF_INTERMEDIATE), "-movflags", "+faststart", str(out)))
    return out


def make_square(master: Path, out: Path) -> Path:
    _run(_ff("-i", str(master), "-vf", "scale=1080:1080:flags=lanczos",
             *_x264(_CRF_INTERMEDIATE), "-movflags", "+faststart", str(out)))
    return out


def _render_text_png(text: str, video_h: int, out_png: Path) -> Path | None:
    """Render `text` to a transparent PNG sized for the video (Pillow, not ffmpeg
    drawtext — this Homebrew ffmpeg ships without libfreetype). Returns None if no
    usable system font is found."""
    font_path = find_font()
    if not font_path:
        return None
    size = max(18, video_h // 26)
    try:
        font = ImageFont.truetype(font_path, size)
    except OSError:
        return None
    pad = max(4, size // 6)
    tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    l, t, r, b = tmp.textbbox((0, 0), text, font=font)
    w, h = (r - l) + 2 * pad, (b - t) + 2 * pad
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((pad - l + 2, pad - t + 2), text, font=font, fill=(0, 0, 0, 130))   # shadow
    d.text((pad - l, pad - t), text, font=font, fill=(255, 255, 255, 217))     # text
    img.save(out_png)
    return out_png


def _watermark_position(w: int, h: int) -> str:
    """ffmpeg overlay x:y for the watermark, kept clear of platform UI.

    On a 9:16 vertical the bottom-right is buried under the caption block + the
    like/comment/share rail, so a faceless creator's @handle would be hidden.
    Place it centered, just below the content square (~y0.80H), inside the safe
    band. Square/other: conventional bottom-right with a 40px margin.
    """
    if h >= w * 1.4:  # vertical (9:16)
        return "(W-w)/2:H*0.80"
    return "W-w-40:H-h-40"


def _overlay_png(video: Path, png: Path, out: Path, position: str,
                 scale_expr: str | None) -> Path:
    """Overlay a PNG at `position` (an ffmpeg overlay x:y expr). `scale_expr` scales
    the watermark (e.g. 'iw*0.18:-1' for a logo); None overlays at native size."""
    if scale_expr:
        fc = f"[1:v]scale={scale_expr}[wm];[0:v][wm]overlay={position}"
    else:
        fc = f"[0:v][1:v]overlay={position}"
    _run(_ff("-i", str(video), "-i", str(png), "-filter_complex", fc,
             *_x264(_CRF_INTERMEDIATE), str(out)))
    return out


def add_watermark(video: Path, out: Path, text: str | None = None,
                  png: Path | None = None) -> Path:
    """Overlay a logo PNG or a text handle, placed clear of platform UI. No-op copy
    if neither is usable (warns to stderr if text was requested but unrenderable)."""
    w, h = probe_dims(video)
    pos = _watermark_position(w, h)
    if png and png.exists():
        return _overlay_png(video, png, out, pos, scale_expr="iw*0.18:-1")
    if text:
        wm = _render_text_png(text, h, out.parent / "_wm.png")
        if wm:
            return _overlay_png(video, wm, out, pos, scale_expr=None)
        print("WARN: watermark text requested but no usable system font found — "
              "shipping without watermark", file=sys.stderr)
    # Nothing usable to apply -> stream copy through.
    _run(_ff("-i", str(video), "-c", "copy", str(out)))
    return out


def add_audio(video: Path, audio: Path, out: Path) -> Path:
    """Loop the audio bed under the video and cut to the video length."""
    _run(_ff("-i", str(video), "-stream_loop", "-1", "-i", str(audio),
             "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
             "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)))
    return out


def make_still(master: Path, out: Path, size: int = 1080,
               text: str | None = None, png: Path | None = None) -> Path:
    """The 'photo' deliverable: the master's final (most-developed) frame, upscaled
    and watermarked. Composited in PIL so it doesn't depend on ffmpeg drawtext.
    Uses -sseof -3 + -update 1 so it always lands the true last frame, even on a
    sub-0.1s clip (a plain -sseof -0.1 would underflow to the seed frame)."""
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "frame.png"
        _run(_ff("-sseof", "-3", "-i", str(master), "-update", "1", str(raw)))
        img = Image.open(raw).convert("RGBA").resize((size, size), Image.LANCZOS)
        wm = None
        if png and png.exists():
            logo = Image.open(png).convert("RGBA")
            w = int(size * 0.18)
            logo = logo.resize((w, int(w * logo.height / logo.width)), Image.LANCZOS)
            wm = logo
        elif text:
            wm_path = _render_text_png(text, size, Path(tmp) / "wm.png")
            wm = Image.open(wm_path).convert("RGBA") if wm_path else None
        if wm is not None:
            img.alpha_composite(wm, (size - wm.width - 40, size - wm.height - 40))
        img.convert("RGB").save(out)
    return out


def make_thumbnail(still_png: Path, out: Path, size: int = 640) -> Path:
    Image.open(still_png).convert("RGB").resize((size, size), Image.LANCZOS).save(out)
    return out


def process(master: Path, name: str, audio: Path | None = None,
            watermark_text: str | None = None, watermark_png: Path | None = None,
            loop: str = "none", blur_bg: bool = True, n_frames: int | None = None,
            render: dict | None = None) -> dict:
    """Run the full spine. Writes output/<name>/ and returns a metadata dict.

    `render` is provenance ({template, seed, params}) folded into metadata.json so
    the output is reproducible (the render is a pure function of template + params).
    `n_frames` (master frame count) lets boomerang trim its seam/wrap duplicates.
    """
    out_dir = Path("output") / name
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        src = master
        if loop == "boomerang":
            src = make_boomerang(master, t / "loop.mp4", n_frames=n_frames)

        vertical = make_vertical(src, t / "v0.mp4", blur_bg=blur_bg)
        square = make_square(src, t / "s0.mp4")

        vertical = add_watermark(vertical, t / "v1.mp4", watermark_text, watermark_png)
        square = add_watermark(square, t / "s1.mp4", watermark_text, watermark_png)

        if audio and audio.exists():
            vertical = add_audio(vertical, audio, t / "v2.mp4")
            square = add_audio(square, audio, t / "s2.mp4")

        # Final deliverables. Stream-copy re-mux writes the moov atom at the end by
        # default, stripping the +faststart set upstream — re-assert it here.
        final_vertical = out_dir / "vertical.mp4"
        final_square = out_dir / "square.mp4"
        _run(_ff("-i", str(vertical), "-c", "copy", "-movflags", "+faststart",
                 str(final_vertical)))
        _run(_ff("-i", str(square), "-c", "copy", "-movflags", "+faststart",
                 str(final_square)))
        # Still = master's climax frame (NOT the boomerang end, which loops to the
        # near-empty seed state), watermarked. Thumbnail derives from the still.
        make_still(master, out_dir / "still.png", text=watermark_text, png=watermark_png)
        make_thumbnail(out_dir / "still.png", out_dir / "thumb.jpg")

    meta = {
        "name": name,
        "deliverables": {
            "vertical_9x16": "vertical.mp4",
            "square_1x1": "square.mp4",
            "still_png": "still.png",
            "thumbnail": "thumb.jpg",
        },
        "source_master": str(master),
        "audio": str(audio) if audio else None,
        "watermark": watermark_text or (str(watermark_png) if watermark_png else None),
        "loop": loop,
        # Provenance: enough to regenerate byte-identical output from this JSON.
        "render": render,
    }
    (out_dir / "metadata.json").write_text(json.dumps(meta, indent=2))
    return meta


def main() -> int:
    p = argparse.ArgumentParser(description="Post-production spine")
    p.add_argument("--master", required=True, help="square 1:1 master mp4")
    p.add_argument("--name", required=True, help="output folder name under output/")
    p.add_argument("--audio", help="audio bed (looped, cleared for monetization)")
    p.add_argument("--watermark-text", help="text handle overlay, e.g. @yourhandle")
    p.add_argument("--watermark-png", help="PNG watermark overlay")
    p.add_argument("--loop", choices=["none", "boomerang"], default="none")
    p.add_argument("--no-blur-bg", action="store_true", help="black pad instead of blur fill")
    a = p.parse_args()

    meta = process(
        master=Path(a.master),
        name=a.name,
        audio=Path(a.audio) if a.audio else None,
        watermark_text=a.watermark_text,
        watermark_png=Path(a.watermark_png) if a.watermark_png else None,
        loop=a.loop,
        blur_bg=not a.no_blur_bg,
    )
    print(f"OK: output/{a.name}/ -> {list(meta['deliverables'].values())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
