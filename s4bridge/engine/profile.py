# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Fancy Butler
"""Mapping profiles: how each physical control becomes MIDI, and which MIDI
messages coming back light which LEDs.

Keys in ``map`` / ``leds``:
  deck.<func>   - deck-side controls; channel = the deck that side is on (A/C or B/D)
  strip.<func>  - mixer channel strips; channel = that strip's deck
  G.<func>, FX1.<func>, FX2.<func> - global channel
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "s4bridge"
PROFILE_DIR = CONFIG_DIR / "profiles"


def N(num, **kw):
    return {"type": "note", "num": num, **kw}


def CC(num, **kw):
    return {"type": "cc", "num": num, **kw}


DEFAULT_PROFILE = {
    "name": "S4 Bridge Standard",
    "version": 1,
    "description": "Stable layout used by the bundled Mixxx mapping. "
                   "Decks A-D on MIDI channels 1-4, everything else on channel 5.",
    "deck_channels": {"A": 0, "B": 1, "C": 2, "D": 3},
    "global_channel": 4,
    "deck_shift_offset": 0x20,     # shifted deck buttons/encoders: number + 0x20
    "global_shift_offset": 0x40,   # shifted global/FX buttons: number + 0x40
    "relative_encoding": "offset",  # "offset" (64 +/- n) or "twos" (1..63 / 127..65)
    "jog_scale": 1.0,
    "touch_threshold": 3050,
    "led_feedback": True,
    "local_press_feedback": False,  # light buttons while held (handy without feedback)
    "display_swap_digits": False,
    "soft_takeover": True,          # tempo faders wait to catch the deck's tempo after a deck flip
    "map": {
        # ---- deck sides
        "deck.load": N(0x01),
        "deck.jog": CC(0x02),
        "deck.touch": N(0x03),
        "deck.tempo": CC(0x04, hires=True),
        "deck.tempo_down": N(0x05),
        "deck.tempo_up": N(0x06),
        "deck.shift": N(0x07, shiftable=False),
        "deck.sync": N(0x08),
        "deck.cue": N(0x09),
        "deck.play": N(0x0A),
        "deck.hotcue1": N(0x0B), "deck.hotcue2": N(0x0C),
        "deck.hotcue3": N(0x0D), "deck.hotcue4": N(0x0E),
        "deck.sample1": N(0x0F), "deck.sample2": N(0x10),
        "deck.sample3": N(0x11), "deck.sample4": N(0x12),
        "deck.move": CC(0x13), "deck.move_press": N(0x13),
        "deck.size": CC(0x15), "deck.size_press": N(0x15),
        "deck.loop_in": N(0x17), "deck.loop_out": N(0x18),
        "deck.deck_toggle": N(0x19, shiftable=False),
        # ---- mixer strips
        "strip.gain": CC(0x3C), "strip.gain_press": N(0x3D),
        "strip.fx1": N(0x3E), "strip.fx2": N(0x3F),
        "strip.hi": CC(0x40), "strip.mid": CC(0x41), "strip.low": CC(0x42), "strip.filter": CC(0x43),
        "strip.cue": N(0x44),
        "strip.volume": CC(0x45),
        # ---- global
        "G.browse": CC(0x02), "G.browse_press": N(0x03),
        "G.loop_drywet": CC(0x04),
        "G.loop_size": N(0x05), "G.loop_undo": N(0x06), "G.loop_rec": N(0x07), "G.loop_play": N(0x08),
        "G.browse_btn": N(0x09),
        "G.crossfader": CC(0x0A),
        "G.snap": N(0x0B), "G.master": N(0x0C), "G.quant": N(0x0D),
        "G.mic_volume": CC(0x0E), "G.cue_mix": CC(0x0F),
        "FX1.drywet": CC(0x14), "FX1.k1": CC(0x15), "FX1.k2": CC(0x16), "FX1.k3": CC(0x17),
        "FX1.on": N(0x18), "FX1.b1": N(0x19), "FX1.b2": N(0x1A), "FX1.b3": N(0x1B), "FX1.mode": N(0x1C),
        "FX2.drywet": CC(0x1E), "FX2.k1": CC(0x1F), "FX2.k2": CC(0x20), "FX2.k3": CC(0x21),
        "FX2.on": N(0x22), "FX2.b1": N(0x23), "FX2.b2": N(0x24), "FX2.b3": N(0x25), "FX2.mode": N(0x26),
    },
    # LED-only targets (no button underneath).  Button LEDs reuse the
    # button's own note number on the same channel.
    "leds": {
        "deck.on_air": N(0x60), "deck.samples": N(0x61),
        "deck.keylock": N(0x62), "deck.master_ind": N(0x63),
        "deck.display": CC(0x50),           # 0-99 = number, 100 = blank, 101 = "--", 102+ = words (see translator)
        "deck.rate_fb": CC(0x51),
        "deck.display_dot": CC(0x54),       # decimal point on the right digit (minutes / Camelot B)           # the deck's current tempo-fader position (0-127), for soft takeover
        "strip.meter": CC(0x46),            # 0-126 = 6-step meter, 127 = clip
        "strip.xf_left": N(0x47), "strip.xf_right": N(0x48), "strip.active": N(0x49),
        "G.quant_ind": N(0x70), "G.headphone_ind": N(0x71), "G.master_ind": N(0x72),
        "G.snap_ind": N(0x73), "G.warning": N(0x74),
    },
}


def area_key(area: str, func: str) -> str:
    if area in ("L", "R"):
        return f"deck.{func}"
    if area in ("A", "B", "C", "D"):
        return f"strip.{func}"
    return f"{area}.{func}"


def load_profile(path: Path | str | None = None) -> dict:
    prof = copy.deepcopy(DEFAULT_PROFILE)
    if path:
        with open(path) as f:
            user = json.load(f)
        for k, v in user.items():
            if k in ("map", "leds"):
                prof[k].update(v)
            else:
                prof[k] = v
    return prof


def save_profile(prof: dict, path: Path | str):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(prof, f, indent=2)


def list_profiles() -> list[Path]:
    if not PROFILE_DIR.exists():
        return []
    return sorted(PROFILE_DIR.glob("*.json"))


def settings_path() -> Path:
    return CONFIG_DIR / "settings.json"


def load_settings() -> dict:
    try:
        return json.loads(settings_path().read_text())
    except (OSError, ValueError):
        return {}


def save_settings(s: dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    settings_path().write_text(json.dumps(s, indent=2))
