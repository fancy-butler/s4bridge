# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Fancy Butler
"""Physical model of the Traktor Kontrol S4 MK1 as exposed by snd-usb-caiaq.

Event codes come from the Linux kernel's sound/usb/caiaq/input.c:
  * buttons: BTN_MISC (256) + bit index (96 bits)
  * axes:    ABS_HAT0X (16) + axis index

Where each mapping comes from (``source``):
  kernel   - named in the kernel driver source itself
  tested   - from blaxpot/traktor-s4-mk1-midify's hardware-tested sheet (MIT)
  reported - from jmanera/traktor-kontrol-s4-mk1-driver-linux only
  unknown  - control exists on the unit but its event code is not yet known;
             use Identify in the app to capture it on your own S4

Layout coordinates are in a 1200 x 760 canvas traced from a top-down photo.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Optional

USB_VENDOR = 0x17CC
USB_PRODUCT = 0xBAFF
CANVAS_W, CANVAS_H = 1200, 760

BTN_BASE = 256
ABS_BASE = 16

POT_MAX = 0xFFF        # 12-bit pots/faders/touch sensors
JOG_RANGE = 0x400      # 10-bit wrapping jog counter
ENC_RANGE = 0x10       # 4-bit wrapping encoders

# kinds
BUTTON, POT, ENCODER, JOG, TOUCH = "button", "pot", "encoder", "jog", "touch"


@dataclass(frozen=True)
class Control:
    cid: str                 # stable id, e.g. "L.play", "A.hi", "FX1.k1"
    label: str
    kind: str
    code: Optional[int]      # evdev code (None = unknown)
    area: str                # L, R (deck sides) | A B C D (mixer strips) | G | FX1 | FX2
    func: str                # function name inside its area ("play", "hi", ...)
    shape: str               # knob, enc, btn, pad, fader, hfader, jog, small
    x: float
    y: float
    w: float = 0
    h: float = 0
    led: tuple = ()          # kernel LED control names driven for this control
    source: str = "tested"
    note: str = ""

    @property
    def is_deck(self) -> bool:
        return self.area in ("L", "R")


@dataclass(frozen=True)
class Indicator:
    """An LED that has no button under it (displays, VU, status lamps)."""
    iid: str
    label: str
    area: str
    func: str
    x: float
    y: float
    leds: tuple
    shape: str = "lamp"      # lamp, meter, seg, bar


def _btn(n: int) -> int:
    return BTN_BASE + n


def _abs(n: int) -> int:
    return ABS_BASE + n


# ---------------------------------------------------------------- deck sides
# (func, label, kind, left code, right code, shape, lx, ly, led suffix, source)
_DECK_ROWS = [
    ("hotcue1", "1", BUTTON, 256, 312, "pad", 145, 559, ("1 (blue)", "1 (green)"), "tested"),
    ("hotcue2", "2", BUTTON, 258, 314, "pad", 205, 559, ("2 (blue)", "2 (green)"), "tested"),
    ("hotcue3", "3", BUTTON, 260, 316, "pad", 266, 559, ("3 (blue)", "3 (green)"), "tested"),
    ("hotcue4", "4", BUTTON, 262, 318, "pad", 327, 559, ("4 (blue)", "4 (green)"), "tested"),
    ("sample1", "▶", BUTTON, 265, 305, "pad", 145, 515, ("Sample 1",), "tested"),
    ("sample2", "▶", BUTTON, 267, 307, "pad", 205, 515, ("Sample 2",), "tested"),
    ("sample3", "▶", BUTTON, 269, 309, "pad", 266, 515, ("Sample 3",), "tested"),
    ("sample4", "▶", BUTTON, 271, 311, "pad", 327, 515, ("Sample 4",), "tested"),
    ("shift", "SHIFT", BUTTON, 257, 313, "pad", 135, 620, ("Shift",), "reported"),
    ("sync", "SYNC", BUTTON, 259, 315, "pad", 196, 620, ("Sync",), "tested"),
    ("cue", "CUE", BUTTON, 261, 317, "pad", 256, 620, ("Cue",), "tested"),
    ("play", "PLAY", BUTTON, 263, 319, "pad", 319, 620, ("Play",), "tested"),
    ("loop_in", "IN", BUTTON, 266, 306, "pad", 210, 456, ("In",), "tested"),
    ("loop_out", "OUT", BUTTON, 268, 308, "pad", 270, 456, ("Out",), "tested"),
    ("move_press", "MOVE push", BUTTON, 275, 299, "none", 148, 456, (), "tested"),
    ("size_press", "SIZE push", BUTTON, 274, 298, "none", 330, 456, (), "tested"),
    ("tempo_down", "▼", BUTTON, 273, 297, "small", 65, 411, ("Tempo down",), "tested"),
    ("tempo_up", "▲", BUTTON, 272, 296, "small", 92, 411, ("Tempo up",), "tested"),
]


def _deck_controls() -> list[Control]:
    out: list[Control] = []
    for side, prefix in (("L", "LED: Deck A: "), ("R", "LED: Deck B: ")):
        right = side == "R"
        for func, label, kind, lc, rc, shape, x, y, leds, src in _DECK_ROWS:
            if right:
                if func in ("tempo_down", "tempo_up"):
                    x = {"tempo_down": 1112, "tempo_up": 1136}[func]
                    y = 415
                else:
                    x, y = x + 731, y + 4
            out.append(Control(
                cid=f"{side}.{func}", label=label, kind=kind, code=rc if right else lc,
                area=side, func=func, shape=shape, x=x, y=y,
                led=tuple(prefix + s for s in leds), source=src))

        # encoders (loop move / size) share position with their push switch
        out += [
            Control(f"{side}.move", "MOVE", ENCODER, 57 if right else 55, side, "move", "enc",
                    873 if right else 148, 460 if right else 456, source="tested"),
            Control(f"{side}.size", "SIZE", ENCODER, 58 if right else 56, side, "size", "enc",
                    1053 if right else 330, 460 if right else 456, source="tested"),
            Control(f"{side}.tempo", "TEMPO", POT, 22 if right else 21, side, "tempo", "fader",
                    1146 if right else 57, 549, 14, 142, source="kernel"),
            Control(f"{side}.jog", "Jog", JOG, 53 if right else 52, side, "jog", "jog",
                    981 if right else 219, 252, 132, 132, source="kernel"),
            Control(f"{side}.touch", "Jog touch", TOUCH, 27 if right else 26, side, "touch",
                    "none", 981 if right else 219, 252, source="kernel",
                    note="Wheel distance sensor; touched above threshold"),
            Control(f"{side}.load", "LOAD", BUTTON, 310 if right else 270, side, "load", "small",
                    831 if right else 371, 130, led=(prefix + "Load",), source="tested"),
            Control(f"{side}.deck_toggle", "DECK D" if right else "DECK C", BUTTON,
                    304 if right else 264, side, "deck_toggle", "small",
                    1109 if right else 94, 130,
                    led=(prefix + ("Deck D button" if right else "Deck C button"),),
                    source="reported", note="Handled by S4 Bridge: flips this side between decks"),
        ]
    return out


# ---------------------------------------------------------------- mixer
# strip x positions follow the hardware order C A | B D
STRIP_X = {"C": 435, "A": 516, "B": 686, "D": 772}
_STRIP_CODES = {
    #        gain  fx1  fx2  cue  hi  mid low filter vol
    "A": (59, 330, 331, 289, 43, 42, 41, 40, 18),
    "B": (60, 332, 333, 290, 39, 38, 37, 36, 17),
    "C": (61, 328, 329, 288, 47, 46, 45, 44, 19),
    "D": (62, 334, 335, 291, 31, 30, 29, 28, 16),
}
_GAIN_PRESS = {"A": 327, "B": None, "C": None, "D": None}
_FX_BTN_X = {"C": (416, 457), "A": (499, 539), "B": (662, 703), "D": (744, 787)}


def _mixer_controls() -> list[Control]:
    out: list[Control] = []
    for ch, x in STRIP_X.items():
        gain, fx1, fx2, cue, hi, mid, low, flt, vol = _STRIP_CODES[ch]
        p = f"LED: Channel {ch}: "
        out += [
            Control(f"{ch}.gain", "GAIN", ENCODER, gain, ch, "gain", "enc", x + 3, 48, source="tested"),
            Control(f"{ch}.gain_press", "GAIN push", BUTTON, _GAIN_PRESS[ch], ch, "gain_press", "none",
                    x + 3, 50, source="reported" if _GAIN_PRESS[ch] else "unknown"),
            Control(f"{ch}.fx1", "1", BUTTON, fx1, ch, "fx1", "small", _FX_BTN_X[ch][0], 80,
                    led=(p + "FX1",), source="tested"),
            Control(f"{ch}.fx2", "2", BUTTON, fx2, ch, "fx2", "small", _FX_BTN_X[ch][1], 80,
                    led=(p + "FX2",), source="tested"),
            Control(f"{ch}.hi", "HI", POT, hi, ch, "hi", "knob", x, 135, source="kernel"),
            Control(f"{ch}.mid", "MID", POT, mid, ch, "mid", "knob", x, 195, source="kernel"),
            Control(f"{ch}.low", "LOW", POT, low, ch, "low", "knob", x, 256, source="kernel"),
            Control(f"{ch}.filter", "FILTER", POT, flt, ch, "filter", "knob", x, 320, source="kernel"),
            Control(f"{ch}.cue", "CUE", BUTTON, cue, ch, "cue", "pad", x, 376,
                    led=(p + "Cue",), source="tested"),
            Control(f"{ch}.volume", ch, POT, vol, ch, "volume", "fader", x, 505, 14, 108, source="kernel"),
        ]
    return out


def _global_controls() -> list[Control]:
    m = "LED: Master: "
    return [
        Control("G.browse", "BROWSE", ENCODER, 54, "G", "browse", "enc", 602, 135, source="tested"),
        Control("G.browse_press", "BROWSE push", BUTTON, 292, "G", "browse_press", "none", 602, 135, source="tested"),
        Control("G.snap", "SNAP", BUTTON, 285, "G", "snap", "small", 571, 209,
                led=(m + "Snap button",), source="reported"),
        Control("G.master", "MASTER", BUTTON, 286, "G", "master", "small", 602, 209,
                led=(m + "Master button",), source="reported"),
        Control("G.quant", "QUANT", BUTTON, 287, "G", "quant", "small", 630, 209,
                led=(m + "Quant button",), source="reported"),
        # block 2 word 5, found on hardware; the kernel driver never reads it (built-in USB driver only)
        Control("G.loop_drywet", "DRY/WET", POT, 64, "G", "loop_drywet", "knob", 602, 258, source="tested"),
        Control("G.loop_size", "SIZE", BUTTON, 280, "G", "loop_size", "small", 581, 300,
                led=(m + "Size",), source="tested"),
        Control("G.loop_undo", "UNDO", BUTTON, 282, "G", "loop_undo", "small", 621, 300,
                led=(m + "Undo button",), source="tested"),
        Control("G.loop_rec", "REC", BUTTON, 281, "G", "loop_rec", "small", 581, 340,
                led=(m + "Rec",), source="tested"),
        Control("G.loop_play", "PLAY", BUTTON, 283, "G", "loop_play", "small", 621, 340,
                led=(m + "Play button",), source="tested"),
        Control("G.browse_btn", "BROWSE", BUTTON, 284, "G", "browse_btn", "small", 602, 379,
                led=(m + "Browser button",), source="tested"),
        Control("G.crossfader", "X-FADER", POT, 23, "G", "crossfader", "hfader", 601, 637, 104, 14, source="kernel"),
        Control("G.mic_volume", "MIC VOL", POT, 24, "G", "mic_volume", "knob", 1090, 722, source="kernel",
                note="Front panel"),
        Control("G.cue_mix", "CUE MIX", POT, 25, "G", "cue_mix", "knob", 900, 722, source="kernel",
                note="Front panel. On the MK1 the cue mix is done by the DJ software"),
    ]


def _fx_controls() -> list[Control]:
    out: list[Control] = []
    # FX1 left, FX2 right.  Knob order within a unit: blaxpot's tested sheet
    # (the kernel comments list the opposite order; verify with Identify).
    spec = {
        "FX1": dict(knobs=(51, 50, 49, 48), btns=(321, 322, 323, 324), mode=325,
                    kx=(111, 178, 249, 320), bx=(133, 204, 275, 347), mx=374),
        "FX2": dict(knobs=(35, 34, 33, 32), btns=(345, 346, 347, 348), mode=349,
                    kx=(839, 910, 981, 1051), bx=(866, 937, 1008, 1078), mx=1102),
    }
    for unit, s in spec.items():
        p = f"LED: {unit}: "
        names = ("drywet", "k1", "k2", "k3")
        labels = ("DRY/WET", "1", "2", "3")
        bnames = ("on", "b1", "b2", "b3")
        bleds = ("dry/wet", "1", "2", "3")
        for i in range(4):
            out.append(Control(f"{unit}.{names[i]}", labels[i], POT, s["knobs"][i], unit, names[i],
                               "knob", s["kx"][i], 46, source="tested"))
            out.append(Control(f"{unit}.{bnames[i]}", "⏻" if i == 0 else labels[i], BUTTON, s["btns"][i],
                               unit, bnames[i], "small", s["bx"][i], 82, led=(p + bleds[i],), source="tested"))
        out.append(Control(f"{unit}.mode", "MODE", BUTTON, s["mode"], unit, "mode", "small", s["mx"], 38,
                           led=(p + "Mode",), source="tested"))
    return out


def _indicators() -> list[Indicator]:
    out: list[Indicator] = []
    for side, prefix, dx in (("L", "LED: Deck A: ", 0), ("R", "LED: Deck B: ", 712)):
        top, bot = ("Deck A", "Deck C") if side == "L" else ("Deck B", "Deck D")
        y0 = 404 if side == "L" else 409
        out += [
            Indicator(f"{side}.on_air", "ON AIR", side, "on_air", 160 + dx, y0, (prefix + "On Air",)),
            Indicator(f"{side}.samples", "SAMPLES", side, "samples", 160 + dx, y0 + 18, (prefix + "Samples",)),
            Indicator(f"{side}.ind_top", top.upper(), side, "ind_top", 222 + dx, y0, (prefix + top,)),
            Indicator(f"{side}.ind_bottom", bot.upper(), side, "ind_bottom", 222 + dx, y0 + 18, (prefix + bot,)),
            Indicator(f"{side}.keylock", "KEYLOCK", side, "keylock", 285 + dx, y0, (prefix + "Keylock",)),
            Indicator(f"{side}.master_ind", "MASTER", side, "master_ind", 285 + dx, y0 + 18, (prefix + "Master",)),
            Indicator(f"{side}.display", "", side, "display", 338 + dx, y0 + 9,
                      tuple(f"{prefix}Digit {d} - {s}" for d in (1, 2) for s in "ABCDEFG")
                      + (f"{prefix}Digit 1 - dot", f"{prefix}Digit 2 - dot"), shape="seg"),
        ]
    for ch, x in STRIP_X.items():
        p = f"LED: Channel {ch}: "
        out += [
            Indicator(f"{ch}.meter", "", ch, "meter", x + 26, 505,
                      tuple(p + f"Meter {i}" for i in range(1, 7)) + (p + "Meter clip",), shape="meter"),
            Indicator(f"{ch}.xf_left", "◂", ch, "xf_left", x - 8, 580, (p + "<",)),
            Indicator(f"{ch}.xf_right", "▸", ch, "xf_right", x + 8, 580, (p + ">",)),
            Indicator(f"{ch}.active", "", ch, "active", x, 413, (p + "Active",), shape="bar"),
        ]
    m = "LED: Master: "
    out += [
        Indicator("G.warning", "⚠", "G", "warning", 571, 177, (m + "Warning",)),
        Indicator("G.master_ind", "⇄", "G", "master_ind", 602, 177, (m + "Master",)),
        Indicator("G.headphone_ind", "∩", "G", "headphone_ind", 630, 177, (m + "Headphone",)),
        Indicator("G.snap_ind", "SNAP", "G", "snap_ind", 571, 193, (m + "Snap",)),
        Indicator("G.quant_ind", "QUANT", "G", "quant_ind", 633, 193, (m + "Quant",)),
    ]
    return out


CONTROLS: list[Control] = _deck_controls() + _mixer_controls() + _global_controls() + _fx_controls()
INDICATORS: list[Indicator] = _indicators()
BY_ID: dict[str, Control] = {c.cid: c for c in CONTROLS}
IND_BY_ID: dict[str, Indicator] = {i.iid: i for i in INDICATORS}


def all_led_names() -> list[str]:
    names: list[str] = []
    for c in CONTROLS:
        names += c.led
    for i in INDICATORS:
        names += i.leds
    return list(dict.fromkeys(names))


@dataclass
class HardwareMap:
    """Event-code lookup, with per-user overrides captured by Identify."""
    overrides: dict = field(default_factory=dict)   # cid -> code (or None)

    def __post_init__(self):
        self.rebuild()

    def rebuild(self):
        self.controls: dict[str, Control] = {}
        for c in CONTROLS:
            if c.cid in self.overrides:
                c = replace(c, code=self.overrides[c.cid], source="user")
            self.controls[c.cid] = c
        self.by_code: dict[int, Control] = {}
        for c in self.controls.values():
            if c.code is not None:
                # user overrides win: a code moved to another control is freed
                prev = self.by_code.get(c.code)
                if prev is None or c.source == "user":
                    self.by_code[c.code] = c
        # controls that lost their code to an override are now unknown
        for cid, c in list(self.controls.items()):
            if c.code is not None and self.by_code.get(c.code) is not c:
                self.controls[cid] = replace(c, code=None, source="unknown")

    def assign(self, cid: str, code: int):
        self.overrides[cid] = code
        for other, oc in list(self.overrides.items()):
            if other != cid and oc == code:
                del self.overrides[other]
        self.rebuild()

    def lookup(self, code: int) -> Optional[Control]:
        return self.by_code.get(code)

    def unknown_codes_kind(self, code: int) -> str:
        return BUTTON if code >= BTN_BASE else POT


FRIENDLY = {
    "shift": "Shift", "sync": "Sync", "cue": "Cue", "play": "Play", "loop_in": "Loop in",
    "loop_out": "Loop out", "move_press": "Loop move (push)", "size_press": "Loop size (push)",
    "tempo_down": "Offset down", "tempo_up": "Offset up", "move": "Loop move", "size": "Loop size",
    "tempo": "Tempo fader", "jog": "Jog wheel", "touch": "Jog touch", "load": "Load",
    "deck_toggle": "Deck toggle", "gain": "Gain", "gain_press": "Gain (push)", "fx1": "FX 1 assign",
    "fx2": "FX 2 assign", "hi": "EQ hi", "mid": "EQ mid", "low": "EQ low", "filter": "Filter",
    "volume": "Channel fader", "browse": "Browse knob", "browse_press": "Browse (push)", "snap": "Snap",
    "master": "Master", "quant": "Quant", "loop_drywet": "Loop recorder dry/wet",
    "loop_size": "Loop recorder size", "loop_undo": "Loop recorder undo", "loop_rec": "Loop recorder rec",
    "loop_play": "Loop recorder play", "browse_btn": "Browse view", "crossfader": "Crossfader",
    "mic_volume": "Mic volume", "cue_mix": "Cue mix", "drywet": "Dry/wet", "on": "Unit on",
    "mode": "Mode",
}


def friendly(c: Control) -> str:
    f = c.func
    if f.startswith("hotcue"):
        return f"Hot cue {f[-1]}"
    if f.startswith("sample"):
        return f"Sample {f[-1]}"
    if f in ("k1", "k2", "k3"):
        return f"Knob {f[-1]}"
    if f in ("b1", "b2", "b3"):
        return f"Button {f[-1]}"
    if c.area in "ABCD" and f == "cue":
        return "Headphone cue"
    return FRIENDLY.get(f, f)
