# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Fancy Butler
"""The standalone mixer's signal processing (numpy/scipy, block based).

Per strip (A-D, stereo):  gain -> 3-band EQ (with kill) -> DJ filter -> fader
Mix:  crossfader (A, C left; B, D right) -> main, soft limiter
Cue:  pre-fader cue bus, blended with main by CUE MIX for the headphones
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy.signal import sosfilt

STRIPS = "ABCD"
XF_SIDE = {"A": "L", "C": "L", "B": "R", "D": "R"}   # as printed under the S4's faders

EQ_KILL_DB = -40.0     # knob fully left
EQ_BOOST_DB = 6.0      # knob fully right
LOW_HZ, MID_HZ, HIGH_HZ = 250.0, 1200.0, 2500.0
FILTER_DEADZONE = 0.04


# ------------------------------------------------------------------ RBJ biquads -> SOS rows
def _norm(b0, b1, b2, a0, a1, a2):
    return np.array([b0 / a0, b1 / a0, b2 / a0, 1.0, a1 / a0, a2 / a0])


def low_shelf(fs, f0, db, s=1.0):
    A = 10 ** (db / 40)
    w = 2 * math.pi * f0 / fs
    c, sn = math.cos(w), math.sin(w)
    alpha = sn / 2 * math.sqrt((A + 1 / A) * (1 / s - 1) + 2)
    sa = 2 * math.sqrt(A) * alpha
    return _norm(A * ((A + 1) - (A - 1) * c + sa), 2 * A * ((A - 1) - (A + 1) * c), A * ((A + 1) - (A - 1) * c - sa),
                 (A + 1) + (A - 1) * c + sa, -2 * ((A - 1) + (A + 1) * c), (A + 1) + (A - 1) * c - sa)


def high_shelf(fs, f0, db, s=1.0):
    A = 10 ** (db / 40)
    w = 2 * math.pi * f0 / fs
    c, sn = math.cos(w), math.sin(w)
    alpha = sn / 2 * math.sqrt((A + 1 / A) * (1 / s - 1) + 2)
    sa = 2 * math.sqrt(A) * alpha
    return _norm(A * ((A + 1) + (A - 1) * c + sa), -2 * A * ((A - 1) + (A + 1) * c), A * ((A + 1) + (A - 1) * c - sa),
                 (A + 1) - (A - 1) * c + sa, 2 * ((A - 1) - (A + 1) * c), (A + 1) - (A - 1) * c - sa)


def peaking(fs, f0, db, q=0.7):
    A = 10 ** (db / 40)
    w = 2 * math.pi * f0 / fs
    alpha = math.sin(w) / (2 * q)
    c = math.cos(w)
    return _norm(1 + alpha * A, -2 * c, 1 - alpha * A, 1 + alpha / A, -2 * c, 1 - alpha / A)


def lowpass(fs, f0, q=0.8):
    w = 2 * math.pi * f0 / fs
    alpha = math.sin(w) / (2 * q)
    c = math.cos(w)
    return _norm((1 - c) / 2, 1 - c, (1 - c) / 2, 1 + alpha, -2 * c, 1 - alpha)


def highpass(fs, f0, q=0.8):
    w = 2 * math.pi * f0 / fs
    alpha = math.sin(w) / (2 * q)
    c = math.cos(w)
    return _norm((1 + c) / 2, -(1 + c), (1 + c) / 2, 1 + alpha, -2 * c, 1 - alpha)


PASS = np.array([1.0, 0, 0, 1.0, 0, 0])


# ------------------------------------------------------------------ knob laws
def eq_db(v: float) -> float:
    """0..1 knob -> dB: centre = flat, left = kill, right = +6."""
    v = min(1.0, max(0.0, v))
    if abs(v - 0.5) < 0.01:
        return 0.0
    return (v - 0.5) * 2 * (EQ_BOOST_DB if v > 0.5 else -EQ_KILL_DB)


def filter_section(fs: float, v: float):
    """FILTER knob: left = low-pass sweeping down, right = high-pass sweeping up, centre = off."""
    d = v - 0.5
    if abs(d) < FILTER_DEADZONE:
        return PASS
    t = (abs(d) - FILTER_DEADZONE) / (0.5 - FILTER_DEADZONE)      # 0..1
    nyq = fs / 2 * 0.9
    if d < 0:
        f = 20000 * (80 / 20000) ** t                            # 20 kHz -> 80 Hz
        return lowpass(fs, min(f, nyq), q=0.9)
    f = 20 * (8000 / 20) ** t                                     # 20 Hz -> 8 kHz
    return highpass(fs, min(f, nyq), q=0.9)


def fader_gain(v: float) -> float:
    v = min(1.0, max(0.0, v))
    return v * v                                                  # audio taper


def xfader_gains(x: float) -> tuple[float, float]:
    """Constant-power crossfader: (left, right). Centre = both at 0 dB (DJ 'cut' style dip-free)."""
    x = min(1.0, max(0.0, x))
    left = 1.0 if x <= 0.5 else math.cos((x - 0.5) * math.pi)
    right = 1.0 if x >= 0.5 else math.cos((0.5 - x) * math.pi)
    return left, right


def soft_limit(x: np.ndarray, knee: float = 0.85) -> np.ndarray:
    """Transparent below the knee, smoothly saturating above: the main out never hard-clips."""
    a = np.abs(x)
    over = a > knee
    if not over.any():
        return x
    y = x.copy()
    head = 1.0 - knee
    y[over] = np.sign(x[over]) * (knee + head * np.tanh((a[over] - knee) / head))
    return y


# ------------------------------------------------------------------ strip
@dataclass
class StripState:
    gain_db: float = 0.0
    hi: float = 0.5
    mid: float = 0.5
    low: float = 0.5
    filter: float = 0.5
    volume: float = 0.75
    cue: bool = False


class Strip:
    def __init__(self, name: str, fs: float):
        self.name = name
        self.fs = fs
        self.p = StripState()
        self._sos = None
        self._zi = None
        self._g_prev = 0.0
        self.dirty = True

    def set(self, **kw):
        for k, v in kw.items():
            if hasattr(self.p, k):
                setattr(self.p, k, v)
        if any(k in kw for k in ("hi", "mid", "low", "filter")):
            self.dirty = True

    def _design(self):
        p, fs = self.p, self.fs
        sos = np.vstack([
            low_shelf(fs, LOW_HZ, eq_db(p.low)),
            peaking(fs, MID_HZ, eq_db(p.mid)),
            high_shelf(fs, HIGH_HZ, eq_db(p.hi)),
            filter_section(fs, p.filter),
        ])
        if self._zi is None:
            self._zi = np.zeros((sos.shape[0], 2, 2))
        self._sos = sos
        self.dirty = False

    def process(self, x: np.ndarray):
        """x: (2, N) float32 -> (pre_fader, post_fader) both (2, N)."""
        if self.dirty:
            self._design()
        g = 10 ** (self.p.gain_db / 20)
        y, self._zi = sosfilt(self._sos, x * g, axis=1, zi=self._zi)
        # ramp the fader across the block (no zipper noise)
        g_new = fader_gain(self.p.volume)
        ramp = np.linspace(self._g_prev, g_new, x.shape[1], dtype=np.float64)
        self._g_prev = g_new
        return y, y * ramp


# ------------------------------------------------------------------ mixer
@dataclass
class MixState:
    xfader: float = 0.5
    cue_mix: float = 0.5           # 0 = cue only, 1 = main only


class Mixer:
    def __init__(self, fs: float):
        self.fs = fs
        self.strips = {s: Strip(s, fs) for s in STRIPS}
        self.m = MixState()
        self._xf_prev = xfader_gains(0.5)
        self.peaks = {s: 0.0 for s in STRIPS}
        self.peaks["main"] = 0.0
        self.clipped = False

    def set(self, msg: dict):
        if "strip" in msg:
            self.strips[msg["strip"]].set(**{k: v for k, v in msg.items() if k != "strip"})
        if "xfader" in msg:
            self.m.xfader = float(msg["xfader"])
        if "cue_mix" in msg:
            self.m.cue_mix = float(msg["cue_mix"])

    def process(self, inputs: dict[str, np.ndarray], n: int):
        """inputs: strip -> (2, n) array (missing = silence). Returns (main, phones) (2, n) float32."""
        main = np.zeros((2, n))
        cue = np.zeros((2, n))
        xl, xr = xfader_gains(self.m.xfader)
        pl, pr = self._xf_prev
        self._xf_prev = (xl, xr)
        ramp_l = np.linspace(pl, xl, n)
        ramp_r = np.linspace(pr, xr, n)
        any_cue = False
        for s, strip in self.strips.items():
            x = inputs.get(s)
            if x is None:
                self.peaks[s] = 0.0
                continue
            pre, post = strip.process(np.asarray(x, dtype=np.float64))
            post = post * (ramp_l if XF_SIDE[s] == "L" else ramp_r)
            main += post
            self.peaks[s] = float(np.max(np.abs(post))) if n else 0.0
            if strip.p.cue:
                cue += pre
                any_cue = True
        self.clipped = bool(np.max(np.abs(main)) > 1.0) if n else False
        main = soft_limit(main)
        self.peaks["main"] = float(np.max(np.abs(main))) if n else 0.0
        # headphones: constant-power blend of cue and main (no cue pressed = main)
        m = self.m.cue_mix if any_cue else 1.0
        phones = cue * math.cos(m * math.pi / 2) + main * math.sin(m * math.pi / 2)
        phones = soft_limit(phones)
        return main.astype(np.float32), phones.astype(np.float32)
