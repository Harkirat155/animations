"""Shared, family-agnostic synthesis primitives for generative audio.

Every sonify recipe builds on these: a WAV writer, oscillator/envelope
primitives, mixing/gain-staging, and two control-rate helpers (mirror_trace
for boomerang, sample_trace for reading a per-frame trace at arbitrary times).
Zero new dependencies — numpy is already required; WAV writing uses stdlib
`wave`.
"""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SR = 44100


def write_wav(path: Path, samples: np.ndarray, sr: int = SR) -> Path:
    """Write float samples in [-1, 1] as 16-bit PCM. Mono (N,) or stereo (N,2)."""
    samples = np.clip(np.asarray(samples, dtype=np.float64), -1.0, 1.0)
    pcm = (samples * 32767.0).astype("<i2")
    n_channels = 1 if pcm.ndim == 1 else pcm.shape[1]
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(n_channels)
        f.setsampwidth(2)
        f.setframerate(sr)
        f.writeframes(pcm.tobytes())
    return path


def osc_sine(freq_hz, t: np.ndarray, phase0: float = 0.0) -> np.ndarray:
    """Sine oscillator. `freq_hz` may be a scalar (constant frequency) or an
    array matching `t` (time-varying). Time-varying frequency is integrated
    via cumsum to keep phase continuous — evaluating sin(2*pi*f(t)*t) directly
    would introduce an audible discontinuity every time f changes.
    """
    freq_hz = np.asarray(freq_hz, dtype=np.float64)
    if freq_hz.ndim == 0:
        phase = 2 * np.pi * freq_hz * t + phase0
    else:
        dt = np.diff(t, prepend=t[0])
        phase = phase0 + 2 * np.pi * np.cumsum(freq_hz * dt)
    return np.sin(phase)


def env_pluck(n: int, sr: int = SR, attack_s: float = 0.005, decay_s: float = 0.25) -> np.ndarray:
    """Fast attack, exponential decay — a struck/plucked-note envelope."""
    t = np.arange(n) / sr
    attack = np.clip(t / max(attack_s, 1e-6), 0.0, 1.0)
    decay = np.exp(-t / max(decay_s, 1e-6))
    return attack * decay


def env_pad(n: int, sr: int = SR, attack_s: float = 0.05, release_s: float = 0.05) -> np.ndarray:
    """Linear attack/release around a sustained middle — for continuous beds."""
    t = np.arange(n) / sr
    dur = n / sr
    attack = np.clip(t / max(attack_s, 1e-6), 0.0, 1.0)
    release = np.clip((dur - t) / max(release_s, 1e-6), 0.0, 1.0)
    return np.minimum(attack, release)


def mix(tracks: list[np.ndarray], weights: list[float] | None = None) -> np.ndarray:
    """Zero-pad every track to the longest and sum (optionally weighted)."""
    if not tracks:
        return np.zeros(0, dtype=np.float64)
    n = max(len(t) for t in tracks)
    weights = weights if weights is not None else [1.0] * len(tracks)
    out = np.zeros(n, dtype=np.float64)
    for track, w in zip(tracks, weights):
        out[: len(track)] += np.asarray(track, dtype=np.float64) * w
    return out


def normalize_and_soft_clip(x: np.ndarray, target_peak: float = 0.891) -> np.ndarray:
    """Scale to `target_peak`, then a tanh soft-clip as a safety net only.

    Voices should already be gain-staged (amplitude divided by voice count)
    before summing — this should rarely need to do real clipping work; it
    exists to catch the occasional constructive-interference peak, not to
    substitute for per-voice gain staging.
    """
    x = np.asarray(x, dtype=np.float64)
    if x.size == 0:
        return x
    peak = np.max(np.abs(x))
    if peak > 1e-9:
        x = x * (target_peak / peak)
    return np.tanh(x)


def mirror_trace(trace: list) -> list:
    """Frame-domain mirror matching `pipeline.post.make_boomerang`'s exact
    seam/wrap trim math, so a synthesized track has one entry per boomeranged
    VIDEO frame, in the same order the video ends up in (verified against
    make_boomerang: forward 0..n-1, then reversed-trimmed n-2..1).
    """
    n = len(trace)
    if n > 2:
        return list(trace) + list(trace[-2:0:-1])
    return list(trace) + list(trace[-2::-1])


def sample_trace(trace: np.ndarray, t_query: np.ndarray, fps: float) -> np.ndarray:
    """Interpolate a per-frame control-rate trace at arbitrary times `t_query`
    (seconds), against frame_times = arange(len(trace)) / fps. `trace` is 1-D
    (one scalar per frame) — callers with multi-component traces (e.g. (m, n)
    pairs) call this once per component.
    """
    trace = np.asarray(trace, dtype=np.float64)
    frame_times = np.arange(len(trace)) / fps
    return np.interp(t_query, frame_times, trace)
